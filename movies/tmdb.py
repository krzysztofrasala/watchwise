import os
import requests
from functools import lru_cache

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
DEFAULT_POSTER = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?q=80&w=500&auto=format&fit=crop"

def get_api_key():
    return os.environ.get("TMDB_API_KEY")

def get_poster_url(poster_path: str, size: str = "w500") -> str:
    if not poster_path or str(poster_path) == "nan":
        return DEFAULT_POSTER
    if poster_path.startswith("http"):
        return poster_path
    path = poster_path if poster_path.startswith("/") else f"/{poster_path}"
    return f"{IMAGE_BASE_URL}/{size}{path}"

@lru_cache(maxsize=200)
def fetch_movie_details(movie_id: int):
    """Fetch extended movie details from TMDB including videos (trailers) and cast."""
    api_key = get_api_key()
    if not api_key:
        return None

    try:
        url = f"{BASE_URL}/movie/{movie_id}"
        params = {
            "api_key": api_key,
            "append_to_response": "videos,credits",
            "language": "pl-PL"
        }
        res = requests.get(url, params=params, timeout=4)
        if res.status_code == 200:
            data = res.json()
            trailer_key = None
            videos = data.get("videos", {}).get("results", [])
            for v in videos:
                if v.get("site") == "YouTube" and v.get("type") in ["Trailer", "Teaser"]:
                    trailer_key = v.get("key")
                    break

            cast = [c.get("name") for c in data.get("credits", {}).get("cast", [])[:5]]
            director = next((c.get("name") for c in data.get("credits", {}).get("crew", []) if c.get("job") == "Director"), None)

            return {
                "tagline": data.get("tagline", ""),
                "overview": data.get("overview", ""),
                "trailer_key": trailer_key,
                "cast": cast,
                "director": director,
                "backdrop_path": f"{IMAGE_BASE_URL}/w1280{data['backdrop_path']}" if data.get("backdrop_path") else None,
                "vote_count": data.get("vote_count", 0),
            }
    except Exception:
        pass
    return None
