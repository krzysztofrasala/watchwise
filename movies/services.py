import ast
import os
import pickle
import random
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
from . import tmdb

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'

MOVIE_DICT_FILE = DATA_DIR / 'movie_dict.pkl'
NEIGHBORS_FILE = DATA_DIR / 'neighbors.pkl'
MOVIES_CSV_FILE = DATA_DIR / 'movies.csv'
VECTORS_FILE = DATA_DIR / 'vectors.npz'


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


def get_all_movies():
    movies_df, _ = load_dataset()
    return movies_df.to_dict(orient="records")


def get_movie_by_id(movie_id: int):
    movies_df, _ = load_dataset()
    match = movies_df[movies_df["movie_id"] == int(movie_id)]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def get_movie_by_index(idx: int):
    movies_df, _ = load_dataset()
    if 0 <= idx < len(movies_df):
        return movies_df.iloc[idx].to_dict()
    return None


def get_recommendations(movie_id: int, top_n: int = 10):
    movies_df, neighbors = load_dataset()
    match = movies_df[movies_df["movie_id"] == int(movie_id)]
    if match.empty:
        return []

    idx = match.index[0]
    indices_matrix = neighbors["indices"]
    scores_matrix = neighbors["scores"]

    n_movies = len(movies_df)
    neighbor_indices = indices_matrix[idx][1:top_n+1]
    neighbor_scores = scores_matrix[idx][1:top_n+1]

    recommendations = []
    for neighbor_idx, score in zip(neighbor_indices, neighbor_scores):
        if neighbor_idx < n_movies:
            rec_row = movies_df.iloc[neighbor_idx].to_dict()
            rec_row["match_score"] = int(round(float(score) * 100))
            rec_row["similarity"] = rec_row["match_score"]
            rec_row["match_reason"] = "Wysokie podobieństwo tematyczne"
            recommendations.append(rec_row)

    return recommendations


def search_movies(query: str, lang: str = "PL", limit: int = 12):
    if not query or len(query.strip()) < 2:
        return []
    movies_df, _ = load_dataset()
    q = query.strip().lower()
    matches = movies_df[movies_df["title"].str.lower().str.contains(q, na=False)]
    local_results = matches.head(limit).to_dict(orient="records")
    for r in local_results:
        r["media_badge"] = "🎬 Film"
        r["media_type"] = "movie"

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

    if sort_by == "vote_desc":
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


def get_random_movie(genre: str = None):
    movies_df, _ = load_dataset()
    df = movies_df
    if genre and genre != "All":
        df = df[df["genres_list"].apply(lambda g: isinstance(g, list) and genre in g)]
    if df.empty:
        return None
    sample = df.sample(n=1).iloc[0].to_dict()
    return sample


def get_trending_content(category: str = "movies", lang: str = "PL") -> list[dict]:
    """Fetch live trending content from TMDB with fallback to dataset."""
    if category == "tv":
        results = tmdb.fetch_trending(media_type="tv", time_window="day", lang=lang, limit=12)
    elif category == "upcoming":
        results = tmdb.fetch_upcoming(lang=lang, limit=12)
    else:
        results = tmdb.fetch_trending(media_type="movie", time_window="day", lang=lang, limit=12)

    if not results:
        filtered = filter_movies(genre="All", sort_by="vote_desc", per_page=12)
        results = filtered.get("items", [])
        for r in results:
            r["media_type"] = "movie"
            r["is_tv"] = False
            r["media_badge"] = "🎬 Film"
    return results

