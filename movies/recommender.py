"""Content-based & hybrid recommendation logic using dense embeddings and user profiles for Cinescope Django."""

from __future__ import annotations
from typing import Any
import numpy as np
from . import services, tmdb

TOP_N = 12
MIN_STARS_FOR_PROFILE = 3


def recommend_movie(movie_id: int, top_n: int = TOP_N) -> list[dict[str, Any]]:
    """Return top_n most similar movies for a specific movie_id, with match scores & reasons."""
    return services.get_recommendations(movie_id, top_n=top_n)


def recommend_for_user(user_ratings: dict[int, int], watchlist_ids: list[int], top_n: int = TOP_N, lang: str = "PL") -> list[dict[str, Any]]:
    """Generate personalized recommendations (V_user) based on ratings and watchlist."""
    movies_df, vectors, is_dense = services.load_dataset_with_vectors()
    if movies_df.empty or vectors is None:
        return []

    code = lang.upper().strip()

    # Map movie_id to df row index
    id_to_idx = {row["movie_id"]: i for i, row in movies_df.iterrows()}

    user_vector = None
    seen_indices = set()
    user_top_genres: set[str] = set()

    # 1. Process rated movies
    for mid, stars in user_ratings.items():
        if stars < MIN_STARS_FOR_PROFILE:
            continue
        mid = int(mid)
        if mid not in id_to_idx:
            continue

        idx = id_to_idx[mid]
        seen_indices.add(idx)

        # Weight by stars (1..5) -> 0.2 .. 1.0
        weight = float(stars) / 5.0
        row = movies_df.iloc[idx]
        genres = row.get("genres_list", [])
        if isinstance(genres, list):
            user_top_genres.update(genres)

        vec = vectors[idx]
        if is_dense:
            norm = np.linalg.norm(vec)
            vec_norm = vec / norm if norm > 0 else vec
            user_vector = (weight * vec_norm) if user_vector is None else (user_vector + weight * vec_norm)
        else:
            vec_dense = vec.toarray().ravel()
            norm = np.linalg.norm(vec_dense)
            vec_norm = vec_dense / norm if norm > 0 else vec_dense
            user_vector = (weight * vec_norm) if user_vector is None else (user_vector + weight * vec_norm)

    # 2. Process watchlist items (weight 0.5)
    for mid in watchlist_ids:
        mid = int(mid)
        if mid not in id_to_idx or mid in user_ratings:
            continue
        idx = id_to_idx[mid]
        seen_indices.add(idx)

        weight = 0.5
        row = movies_df.iloc[idx]
        genres = row.get("genres_list", [])
        if isinstance(genres, list):
            user_top_genres.update(genres)

        vec = vectors[idx]
        if is_dense:
            norm = np.linalg.norm(vec)
            vec_norm = vec / norm if norm > 0 else vec
            user_vector = (weight * vec_norm) if user_vector is None else (user_vector + weight * vec_norm)
        else:
            vec_dense = vec.toarray().ravel()
            norm = np.linalg.norm(vec_dense)
            vec_norm = vec_dense / norm if norm > 0 else vec_dense
            user_vector = (weight * vec_norm) if user_vector is None else (user_vector + weight * vec_norm)

    if user_vector is None:
        return []

    # Normalize V_user
    u_norm = np.linalg.norm(user_vector)
    if u_norm > 0:
        user_vector /= u_norm

    # Compute similarity between user_vector and all movie vectors
    if is_dense:
        vec_norms = np.linalg.norm(vectors, axis=1)
        vec_norms[vec_norms == 0] = 1.0
        sim_scores = np.dot(vectors, user_vector) / vec_norms
    else:
        sim_scores = vectors.dot(user_vector)
        row_norms = np.sqrt(vectors.multiply(vectors).sum(axis=1)).A1
        row_norms[row_norms == 0] = 1.0
        sim_scores = sim_scores / row_norms

    # Exclude already seen/rated movies
    for idx in seen_indices:
        sim_scores[idx] = -1.0

    # Get top-N indices
    top_indices = np.argsort(-sim_scores)[:top_n]

    recommendations = []
    n_movies = len(movies_df)

    for i in top_indices:
        if i >= n_movies or sim_scores[i] <= 0:
            continue
        row_dict = movies_df.iloc[i].to_dict()
        match_pct = int(round(max(0.0, min(1.0, float(sim_scores[i]))) * 100))
        row_dict["match_score"] = match_pct

        cand_genres = set(row_dict.get("genres_list", []))
        shared = user_top_genres.intersection(cand_genres)
        
        if shared:
            genre_str = ', '.join(sorted(shared)[:2])
            if code == "EN":
                row_dict["match_reason"] = f"Matches your taste in {genre_str}"
            elif code == "DE":
                row_dict["match_reason"] = f"Passt zu deinem Geschmack: {genre_str}"
            elif code == "ES":
                row_dict["match_reason"] = f"Coincide con tu gusto en {genre_str}"
            elif code == "FR":
                row_dict["match_reason"] = f"Correspond à vos goûts en {genre_str}"
            elif code == "IT":
                row_dict["match_reason"] = f"Corrisponde ai tuoi gusti in {genre_str}"
            else:
                row_dict["match_reason"] = f"Dopasowane do gatunków: {genre_str}"
        else:
            if code == "EN":
                row_dict["match_reason"] = "Matches your overall film profile"
            elif code == "DE":
                row_dict["match_reason"] = "Passend zu deinem Filmprofil"
            elif code == "ES":
                row_dict["match_reason"] = "Coincide con tu perfil de cine"
            elif code == "FR":
                row_dict["match_reason"] = "Correspond à votre profil cinéma"
            elif code == "IT":
                row_dict["match_reason"] = "In linea con il tuo profilo cinema"
            else:
                row_dict["match_reason"] = "Zgodne z Twoim ogólnym gustem filmowym"

        recommendations.append(row_dict)

    return recommendations


def recommend_for_group(
    user1_ratings: dict[int, int],
    user1_watchlist: list[int],
    user2_ratings: dict[int, int],
    user2_watchlist: list[int],
    top_n: int = TOP_N,
    lang: str = "PL"
) -> list[dict[str, Any]]:
    """Compute joint recommendation matching tastes of two users/profiles."""
    code = lang.upper().strip()
    recs1 = recommend_for_user(user1_ratings, user1_watchlist, top_n=50, lang=lang)
    recs2 = recommend_for_user(user2_ratings, user2_watchlist, top_n=50, lang=lang)

    if not recs1 and not recs2:
        return []

    scores1 = {m["movie_id"]: m.get("match_score", 0) for m in recs1}
    scores2 = {m["movie_id"]: m.get("match_score", 0) for m in recs2}

    all_mids = set(scores1.keys()).union(scores2.keys())
    combined = []

    movies_dict = {m["movie_id"]: m for m in recs1 + recs2}

    for mid in all_mids:
        s1 = scores1.get(mid, 0)
        s2 = scores2.get(mid, 0)
        avg_score = (s1 + s2) / 2.0
        min_score = min(s1, s2)
        joint_score = int(round(0.7 * avg_score + 0.3 * min_score))

        movie = movies_dict.get(mid)
        if movie:
            m_copy = dict(movie)
            m_copy["match_score"] = joint_score
            if code == "EN":
                m_copy["match_reason"] = f"Matches both tastes ({joint_score}%)"
            elif code == "DE":
                m_copy["match_reason"] = f"Passt für beide ({joint_score}%)"
            elif code == "ES":
                m_copy["match_reason"] = f"Coincide para ambos ({joint_score}%)"
            elif code == "FR":
                m_copy["match_reason"] = f"Convient aux deux ({joint_score}%)"
            elif code == "IT":
                m_copy["match_reason"] = f"Perfetto per entrambi ({joint_score}%)"
            else:
                m_copy["match_reason"] = f"Dopasowanie dla 2 osób ({joint_score}%)"
            combined.append((joint_score, m_copy))

    combined.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in combined[:top_n]]
