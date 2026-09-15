import ast
import json
import os
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests

API_KEY = os.environ.get("TMDB_API_KEY", "")
BASE_URL = "https://api.themoviedb.org/3"
DATA_DIR = "data"

def fetch_movie_meta(movie_id):
    url = f"{BASE_URL}/movie/{movie_id}"
    params = {"api_key": API_KEY, "language": "pl-PL"}
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            d = r.json()
            return {
                "movie_id": movie_id,
                "poster_path": d.get("poster_path") or "",
                "backdrop_path": d.get("backdrop_path") or "",
                "vote_average": round(float(d.get("vote_average", 0.0)), 1),
                "runtime": int(d.get("runtime") or 0),
                "overview": d.get("overview") or "",
                "tagline": d.get("tagline") or "",
                "original_language": d.get("original_language") or "",
            }
    except Exception:
        pass
    return {"movie_id": movie_id, "poster_path": "", "backdrop_path": "", "vote_average": 0.0, "runtime": 0, "overview": "", "tagline": "", "original_language": ""}

def main():
    print("Loading movies.csv...")
    csv_path = os.path.join(DATA_DIR, "movies.csv")
    df = pd.read_csv(csv_path)
    movie_ids = df["id"].tolist()
    print(f"Total movies to hydrate: {len(movie_ids)}")

    results = {}
    done = 0

    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(fetch_movie_meta, mid): mid for mid in movie_ids}
        for future in as_completed(futures):
            res = future.result()
            results[res["movie_id"]] = res
            done += 1
            if done % 500 == 0:
                print(f"Hydrated {done}/{len(movie_ids)} movies...")

    print("Updating movies.csv with hydrated metadata...")
    df["poster_path"] = df["id"].map(lambda x: results.get(x, {}).get("poster_path", ""))
    df["backdrop_path"] = df["id"].map(lambda x: results.get(x, {}).get("backdrop_path", ""))
    df["vote_average"] = df["id"].map(lambda x: results.get(x, {}).get("vote_average", 0.0))
    df["runtime"] = df["id"].map(lambda x: results.get(x, {}).get("runtime", 0))
    df["overview"] = df["id"].map(lambda x: results.get(x, {}).get("overview", ""))
    df["tagline"] = df["id"].map(lambda x: results.get(x, {}).get("tagline", ""))
    df["original_language"] = df["id"].map(lambda x: results.get(x, {}).get("original_language", ""))

    df.to_csv(csv_path, index=False)
    print("Done! Updated data/movies.csv successfully.")

if __name__ == "__main__":
    main()
