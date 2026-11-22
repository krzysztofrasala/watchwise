"""Add vote_count and popularity columns to data/movies.csv (one TMDB request per movie).

Usage: TMDB_API_KEY=... python add_vote_counts.py   (reads .env automatically if present)
Without vote_count the app cannot tell a film with 5 votes from one with 20,000.
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

BASE_URL = "https://api.themoviedb.org/3"
CSV_PATH = os.path.join("data", "movies.csv")


def load_env() -> None:
    if os.path.exists(".env"):
        for line in open(".env", encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if v:
                    os.environ.setdefault(k.strip(), v)


def fetch(session: requests.Session, api_key: str, movie_id: int):
    for attempt in range(3):
        try:
            r = session.get(f"{BASE_URL}/movie/{movie_id}", params={"api_key": api_key}, timeout=10)
            if r.status_code == 200:
                d = r.json()
                return movie_id, int(d.get("vote_count") or 0), float(d.get("popularity") or 0.0)
            if r.status_code == 429:
                time.sleep(2 + attempt * 2)
                continue
            if r.status_code == 404:
                return movie_id, 0, 0.0
        except requests.RequestException:
            time.sleep(1 + attempt)
    return movie_id, None, None


def main() -> int:
    load_env()
    api_key = os.environ.get("TMDB_API_KEY", "")
    if not api_key:
        print("TMDB_API_KEY missing")
        return 1
    df = pd.read_csv(CSV_PATH)
    ids = df["id"].tolist()
    results = {}
    session = requests.Session()
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(fetch, session, api_key, mid) for mid in ids]
        for i, fut in enumerate(as_completed(futures), 1):
            mid, votes, pop = fut.result()
            results[mid] = (votes, pop)
            if i % 500 == 0:
                print(f"{i}/{len(ids)}", flush=True)
    failed = [m for m, (v, _) in results.items() if v is None]
    print(f"failed: {len(failed)}")
    df["vote_count"] = df["id"].map(lambda m: results[m][0] if results[m][0] is not None else df.loc[df["id"] == m, "vote_count"].iloc[0] if "vote_count" in df else 0).astype(int)
    df["popularity"] = df["id"].map(lambda m: results[m][1] if results[m][1] is not None else 0.0)
    df.to_csv(CSV_PATH, index=False)
    print("Done:", CSV_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
