from __future__ import annotations
import ast
import os
import pickle
import random
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
from django.core.cache import cache
from . import tmdb, i18n

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'

MOVIE_DICT_FILE = DATA_DIR / 'movie_dict.pkl'
NEIGHBORS_FILE = DATA_DIR / 'neighbors.pkl'
MOVIES_CSV_FILE = DATA_DIR / 'movies.csv'
VECTORS_FILE = DATA_DIR / 'vectors.npz'


import re

def clean_overview_from_tags(tags: str) -> str:
    """Extract clean, capitalized English overview from tags string."""
    if not tags or not isinstance(tags, str):
        return ""
    m = re.search(r'^(.*?[.!?…])\s+(?:[a-z0-9]+(?:\s+[a-z0-9]+)*)$', tags)
    if m:
        text = m.group(1).strip()
    else:
        last_punct = max(tags.rfind('.'), tags.rfind('!'), tags.rfind('?'))
        if last_punct > 20:
            text = tags[:last_punct + 1].strip()
        else:
            text = tags.strip()
    sentences = re.split(r'([.!?…]\s+)', text)
    capitalized = "".join(part if re.match(r'^[.!?…]\s+$', part) else part.capitalize() for part in sentences)
    return capitalized


def parse_genres(genres_str) -> list[str]:
    try:
        return [g["name"] for g in ast.literal_eval(genres_str)]
    except Exception:
        return []


@lru_cache(maxsize=1)
def load_dataset():
    """Load and merge movie dataset and precomputed similarity matrix."""
    if not MOVIE_DICT_FILE.exists() or not NEIGHBORS_FILE.exists() or not MOVIES_CSV_FILE.exists():
        raise FileNotFoundError("Dataset files missing in data/ directory.")

    with open(MOVIE_DICT_FILE, "rb") as f:
        movies_dict = pickle.load(f)
    movies_df = pd.DataFrame(movies_dict)

    with open(NEIGHBORS_FILE, "rb") as f:
        neighbors = pickle.load(f)

    raw_df = pd.read_csv(MOVIES_CSV_FILE)
    raw_df["year"] = pd.to_datetime(raw_df.get("release_date"), errors="coerce").dt.year.fillna(0).astype(int)
    raw_df["genres_list"] = raw_df.get("genres", "[]").apply(parse_genres)
    raw_df = raw_df.rename(columns={"id": "movie_id"})

    cols_to_merge = ["movie_id", "year", "genres_list"]
    for col in ["poster_path", "backdrop_path", "vote_average", "runtime", "overview", "tagline", "original_language"]:
        if col in raw_df.columns:
            cols_to_merge.append(col)

    merged = movies_df.merge(raw_df[cols_to_merge], on="movie_id", how="left")

    for col in ["poster_path", "backdrop_path", "overview", "tagline", "original_language"]:
        if col not in merged.columns:
            merged[col] = ""
        else:
            merged[col] = merged[col].fillna("")

    # Multilingual overview & title fallbacks
    merged["overview_pl"] = merged["overview"]
    merged["overview_en"] = [clean_overview_from_tags(t) for t in merged.get("tags", [""] * len(merged))]
    merged["title_pl"] = merged["title"]
    merged["title_en"] = merged["title"]

    if "vote_average" not in merged.columns:
        merged["vote_average"] = 0.0
    else:
        merged["vote_average"] = merged["vote_average"].fillna(0.0).round(1)

    if "runtime" not in merged.columns:
        merged["runtime"] = 0
    else:
        merged["runtime"] = merged["runtime"].fillna(0).astype(int)

    merged["year"] = merged["year"].fillna(0).astype(int)

    return merged, neighbors


@lru_cache(maxsize=1)
def load_dataset_with_vectors():
    """Load movies dataframe along with sentence transformer dense embeddings vectors."""
    movies_df, _ = load_dataset()
    vectors = None
    is_dense = True

    if VECTORS_FILE.exists():
        npz = np.load(VECTORS_FILE)
        if "vectors" in npz:
            vectors = npz["vectors"]
            is_dense = True

    return movies_df, vectors, is_dense


@lru_cache(maxsize=1)
def get_movie_indices() -> dict[int, int]:
    """Precomputed mapping from movie_id to DataFrame row index."""
    movies_df, _ = load_dataset()
    return dict(zip(movies_df["movie_id"].astype(int), range(len(movies_df))))


@lru_cache(maxsize=1)
def get_movie_dict() -> dict[int, dict]:
    """Precomputed mapping from movie_id to movie record dict for O(1) access."""
    movies_df, _ = load_dataset()
    records = movies_df.to_dict(orient="records")
    return {int(m["movie_id"]): m for m in records}


def get_all_movies():
    """Return all movie records using cached dict values."""
    return list(get_movie_dict().values())


def get_movie_by_id(movie_id: int, lang: str = "PL"):
    """O(1) movie lookup by movie_id with language localization."""
    try:
        raw = get_movie_dict().get(int(movie_id))
        if not raw:
            return None
        movie = dict(raw)
        lang_upper = (lang or "PL").upper()
        lang_lower = lang_upper.lower()

        if lang_upper == "PL":
            if movie.get("overview_pl"):
                movie["overview"] = movie["overview_pl"]
            if movie.get("title_pl"):
                movie["title"] = movie["title_pl"]
            if movie.get("tagline_pl"):
                movie["tagline"] = movie["tagline_pl"]
        else:
            if movie.get(f"overview_{lang_lower}"):
                movie["overview"] = movie[f"overview_{lang_lower}"]
            elif movie.get("overview_en"):
                movie["overview"] = movie["overview_en"]

            if movie.get(f"title_{lang_lower}"):
                movie["title"] = movie[f"title_{lang_lower}"]
            elif movie.get("title_en"):
                movie["title"] = movie["title_en"]

            if movie.get(f"tagline_{lang_lower}"):
                movie["tagline"] = movie[f"tagline_{lang_lower}"]
            elif movie.get("tagline_en"):
                movie["tagline"] = movie["tagline_en"]
            else:
                movie["tagline"] = ""
        return movie
    except (ValueError, TypeError):
        return None


def get_movie_by_index(idx: int):
    all_movies = get_all_movies()
    if 0 <= idx < len(all_movies):
        return all_movies[idx]
    return None


def get_recommendations(movie_id: int, top_n: int = 10, lang: str = "PL"):
    try:
        mid = int(movie_id)
    except (ValueError, TypeError):
        return []

    id_to_idx = get_movie_indices()
    idx = id_to_idx.get(mid)
    if idx is None:
        return []

    movies_df, neighbors = load_dataset()
    indices_matrix = neighbors["indices"]
    scores_matrix = neighbors["scores"]

    n_movies = len(movies_df)
    neighbor_indices = indices_matrix[idx][1:top_n+1]
    neighbor_scores = scores_matrix[idx][1:top_n+1]

    recommendations = []
    all_movies = get_all_movies()
    lang_upper = (lang or "PL").upper()
    for neighbor_idx, score in zip(neighbor_indices, neighbor_scores):
        if neighbor_idx < n_movies:
            rec_row = dict(all_movies[neighbor_idx])
            rec_row["match_score"] = int(round(float(score) * 100))
            rec_row["similarity"] = rec_row["match_score"]
            rec_row["match_reason"] = i18n.t("match_reason_similar", lang)
            if lang_upper == "PL":
                if rec_row.get("overview_pl"):
                    rec_row["overview"] = rec_row["overview_pl"]
                if rec_row.get("title_pl"):
                    rec_row["title"] = rec_row["title_pl"]
                if rec_row.get("tagline_pl"):
                    rec_row["tagline"] = rec_row["tagline_pl"]
            else:
                lang_lower = lang_upper.lower()
                if rec_row.get(f"overview_{lang_lower}"):
                    rec_row["overview"] = rec_row[f"overview_{lang_lower}"]
                elif rec_row.get("overview_en"):
                    rec_row["overview"] = rec_row["overview_en"]

                if rec_row.get(f"title_{lang_lower}"):
                    rec_row["title"] = rec_row[f"title_{lang_lower}"]
                elif rec_row.get("title_en"):
                    rec_row["title"] = rec_row["title_en"]

                if rec_row.get(f"tagline_{lang_lower}"):
                    rec_row["tagline"] = rec_row[f"tagline_{lang_lower}"]
                elif rec_row.get("tagline_en"):
                    rec_row["tagline"] = rec_row["tagline_en"]
                else:
                    rec_row["tagline"] = ""
            recommendations.append(rec_row)

    return recommendations


def search_movies(query: str, lang: str = "PL", limit: int = 12):
    if not query or len(query.strip()) < 2:
        return []
    movies_df, _ = load_dataset()
    q = query.strip().lower()
    matches = movies_df[movies_df["title"].str.lower().str.contains(q, na=False)]
    local_results = matches.head(limit).to_dict(orient="records")
    lang_upper = (lang or "PL").upper()
    for r in local_results:
        r["media_badge"] = f"🎬 {i18n.t('badge_movie', lang)}"
        r["media_type"] = "movie"
        if lang_upper == "PL":
            if r.get("overview_pl"):
                r["overview"] = r["overview_pl"]
            if r.get("title_pl"):
                r["title"] = r["title_pl"]
        else:
            lang_lower = lang_upper.lower()
            if r.get(f"overview_{lang_lower}"):
                r["overview"] = r[f"overview_{lang_lower}"]
            elif r.get("overview_en"):
                r["overview"] = r["overview_en"]

            if r.get(f"title_{lang_lower}"):
                r["title"] = r[f"title_{lang_lower}"]
            elif r.get("title_en"):
                r["title"] = r["title_en"]

    # Also search TMDB for live movies and TV series
    tmdb_results = tmdb.search_tmdb_multi(query, lang=lang, limit=limit)

    seen_ids = set()
    combined = []

    for item in tmdb_results:
        mid = item["movie_id"]
        if mid not in seen_ids:
            seen_ids.add(mid)
            combined.append(item)

    for item in local_results:
        mid = item["movie_id"]
        if mid not in seen_ids:
            seen_ids.add(mid)
            combined.append(item)

    return combined[:limit]


def filter_movies(
    genre: str = None,
    year_min: int = None,
    year_max: int = None,
    vote_min: float = None,
    language: str = None,
    sort_by: str = "popularity",
    page: int = 1,
    per_page: int = 24,
    lang: str = "PL",
):
    movies_df, _ = load_dataset()
    df = movies_df.copy()

    if genre and genre != "All":
        df = df[df["genres_list"].apply(lambda g: isinstance(g, list) and genre in g)]

    if year_min:
        df = df[df["year"] >= int(year_min)]
    if year_max and int(year_max) > 0:
        df = df[df["year"] <= int(year_max)]

    if vote_min:
        df = df[df["vote_average"] >= float(vote_min)]

    if language:
        df = df[df["original_language"].str.lower() == language.lower()]

    if sort_by in ("vote_desc", "rating_desc"):
        df = df.sort_values(by="vote_average", ascending=False)
    elif sort_by == "vote_asc":
        df = df.sort_values(by="vote_average", ascending=True)
    elif sort_by == "year_desc":
        df = df.sort_values(by="year", ascending=False)
    elif sort_by == "year_asc":
        df = df.sort_values(by="year", ascending=True)
    elif sort_by == "title_asc":
        df = df.sort_values(by="title", ascending=True)

    total_count = len(df)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    items = df.iloc[start_idx:end_idx].to_dict(orient="records")
    lang_upper = (lang or "PL").upper()
    for item in items:
        if lang_upper == "PL":
            if item.get("overview_pl"):
                item["overview"] = item["overview_pl"]
            if item.get("title_pl"):
                item["title"] = item["title_pl"]
            if item.get("tagline_pl"):
                item["tagline"] = item["tagline_pl"]
        else:
            lang_lower = lang_upper.lower()
            if item.get(f"overview_{lang_lower}"):
                item["overview"] = item[f"overview_{lang_lower}"]
            elif item.get("overview_en"):
                item["overview"] = item["overview_en"]

            if item.get(f"title_{lang_lower}"):
                item["title"] = item[f"title_{lang_lower}"]
            elif item.get("title_en"):
                item["title"] = item["title_en"]

            if item.get(f"tagline_{lang_lower}"):
                item["tagline"] = item[f"tagline_{lang_lower}"]
            elif item.get("tagline_en"):
                item["tagline"] = item["tagline_en"]
            else:
                item["tagline"] = ""

    return {
        "items": items,
        "total_count": total_count,
        "page": page,
        "total_pages": (total_count + per_page - 1) // per_page if total_count > 0 else 1,
    }


def get_all_genres():
    movies_df, _ = load_dataset()
    all_g = set()
    for genres in movies_df["genres_list"].dropna():
        if isinstance(genres, list):
            all_g.update(genres)
    return sorted(list(all_g))


MOOD_GENRES = {
    "fun": ["Comedy", "Animation", "Family"],
    "thrill": ["Thriller", "Horror", "Mystery"],
    "action": ["Action", "Adventure"],
    "romance": ["Romance", "Drama"],
    "chill": ["Drama", "Documentary", "Music"],
    "mindfuck": ["Science Fiction", "Mystery"],
}


def get_random_movie(genre: str = None):
    """Backward compatible helper returning a single random movie."""
    winner, _ = get_random_movie_pool(genre=genre)
    return winner


def get_random_movie_pool(
    genre: str = None,
    mood: str = None,
    max_runtime: int = None,
    min_rating: float = None,
    candidate_ids: list[int] = None,
    exclude_ids: list[int] = None,
    pool_size: int = 8,
) -> tuple[dict | None, list[dict]]:
    """Return a randomly picked movie along with a teaser pool for spinning animation."""
    movies_df, _ = load_dataset()
    df = movies_df.copy()

    # 1. Exclude already watched or disliked movies
    if exclude_ids:
        try:
            ex_set = {int(x) for x in exclude_ids}
            df = df[~df["movie_id"].isin(ex_set)]
        except Exception:
            pass

    # 2. Candidate restriction (e.g. from user's watchlist or VOD pool)
    if candidate_ids is not None:
        try:
            cand_set = {int(x) for x in candidate_ids}
            df = df[df["movie_id"].isin(cand_set)]
        except Exception:
            pass

    # 3. Genre filter
    if genre and genre != "All":
        df = df[df["genres_list"].apply(lambda g: isinstance(g, list) and genre in g)]

    # 4. Mood / Vibe filter
    if mood and mood in MOOD_GENRES:
        target_genres = MOOD_GENRES[mood]
        df = df[df["genres_list"].apply(lambda g: isinstance(g, list) and any(t in g for t in target_genres))]
        if mood == "mindfuck":
            df = df[df["vote_average"] >= 6.8]

    # 5. Runtime filter
    if max_runtime:
        try:
            rt = int(max_runtime)
            if rt == 121:  # 120+ minutes / epic
                df = df[df["runtime"] >= 120]
            elif rt > 0:
                df = df[(df["runtime"] > 0) & (df["runtime"] <= rt)]
        except (ValueError, TypeError):
            pass

    # 6. Minimum rating
    if min_rating:
        try:
            df = df[df["vote_average"] >= float(min_rating)]
        except (ValueError, TypeError):
            pass

    if df.empty:
        return None, []

    # Pick winner
    sample_row = df.sample(n=1).iloc[0].to_dict()

    # Pick up to pool_size distinct items for the reel animation
    pool_n = min(len(df), pool_size)
    teaser_rows = df.sample(n=pool_n).to_dict(orient="records")

    return sample_row, teaser_rows


def get_trending_content(category: str = "movies", lang: str = "PL") -> list[dict]:
    """Fetch live trending content from TMDB with fallback to dataset and 4h cache."""
    cache_key = f"trending_{category}_{lang}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    if category == "tv":
        results = tmdb.fetch_trending(media_type="tv", time_window="day", lang=lang, limit=12)
    elif category == "upcoming":
        results = tmdb.fetch_upcoming(lang=lang, limit=12)
    else:
        results = tmdb.fetch_trending(media_type="movie", time_window="day", lang=lang, limit=12)

    if not results:
        filtered = filter_movies(genre="All", sort_by="vote_desc", per_page=12, lang=lang)
        results = filtered.get("items", [])
        for r in results:
            r["media_type"] = "movie"
            r["is_tv"] = False
            r["media_badge"] = f"🎬 {i18n.t('badge_movie', lang)}"

    if results:
        cache.set(cache_key, results, timeout=60 * 60 * 4)
    return results

