import os
import requests
from functools import lru_cache

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
DEFAULT_POSTER = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?q=80&w=500&auto=format&fit=crop"
DEFAULT_API_KEY = "REMOVED"

# Provider IDs for popular VOD platforms in Poland / Global
KNOWN_PROVIDERS = {
    8: {"name": "Netflix", "logo": "/pbpMk2JmcoNnQwx5JGp8jWBDjeW.jpg"},
    337: {"name": "Disney+", "logo": "/97yvRBw1GzX7fT5Y2j7kM8q6Qx.jpg"},
    119: {"name": "Prime Video", "logo": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"},
    1899: {"name": "Max", "logo": "/jse515m3uB8g4t3zS7d0A1b9.jpg"},
    384: {"name": "HBO Max", "logo": "/8z7rC8u0E4f8m1k5L5d2.jpg"},
    350: {"name": "Apple TV+", "logo": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"},
    1773: {"name": "SkyShowtime", "logo": "/77zL1G9g9M9k9J9k.jpg"},
}

def get_api_key():
    return os.environ.get("TMDB_API_KEY") or DEFAULT_API_KEY

def get_poster_url(poster_path: str, size: str = "w500") -> str:
    if not poster_path or str(poster_path) in ["nan", "None", ""]:
        return DEFAULT_POSTER
    if poster_path.startswith("http"):
        return poster_path
    path = poster_path if poster_path.startswith("/") else f"/{poster_path}"
    return f"{IMAGE_BASE_URL}/{size}{path}"

def get_backdrop_url(backdrop_path: str, size: str = "w1280") -> str:
    if not backdrop_path or str(backdrop_path) in ["nan", "None", ""]:
        return ""
    if backdrop_path.startswith("http"):
        return backdrop_path
    path = backdrop_path if backdrop_path.startswith("/") else f"/{backdrop_path}"
    return f"{IMAGE_BASE_URL}/{size}{path}"

def get_profile_url(profile_path: str, size: str = "w185") -> str:
    if not profile_path or str(profile_path) in ["nan", "None", ""]:
        return "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?q=80&w=150&auto=format&fit=crop"
    if profile_path.startswith("http"):
        return profile_path
    path = profile_path if profile_path.startswith("/") else f"/{profile_path}"
    return f"{IMAGE_BASE_URL}/{size}{path}"

def get_provider_logo_url(logo_path: str, size: str = "w92") -> str:
    if not logo_path:
        return ""
    path = logo_path if logo_path.startswith("/") else f"/{logo_path}"
    return f"{IMAGE_BASE_URL}/{size}{path}"


@lru_cache(maxsize=300)
def fetch_movie_details(movie_id: int, lang: str = "PL"):
    """Fetch extended movie details from TMDB including videos (trailers), cast, and VOD providers."""
    api_key = get_api_key()
    if not api_key:
        return None

    lang_code = lang.upper().strip()
    lang_map = {
        "PL": "pl-PL",
        "EN": "en-US",
        "DE": "de-DE",
        "ES": "es-ES",
        "FR": "fr-FR",
        "IT": "it-IT",
    }
    tmdb_lang = lang_map.get(lang_code, "pl-PL")
    region_code = lang_code if lang_code in ["PL", "US", "DE", "ES", "FR", "IT"] else "PL"

    try:
        url = f"{BASE_URL}/movie/{movie_id}"
        params = {
            "api_key": api_key,
            "append_to_response": "videos,credits,watch/providers",
            "language": tmdb_lang
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

            cast_raw = data.get("credits", {}).get("cast", [])[:8]
            cast_list = []
            for c in cast_raw:
                cast_list.append({
                    "name": c.get("name"),
                    "character": c.get("character"),
                    "profile_url": get_profile_url(c.get("profile_path"))
                })

            director = next((c.get("name") for c in data.get("credits", {}).get("crew", []) if c.get("job") == "Director"), None)

            # Extract VOD providers for region (fallback to PL/US)
            watch_results = data.get("watch/providers", {}).get("results", {})
            reg_providers = watch_results.get(region_code, {}) or watch_results.get("PL", {}) or watch_results.get("US", {})
            flatrate = reg_providers.get("flatrate", [])
            
            vod_list = []
            for p in flatrate:
                vod_list.append({
                    "id": p.get("provider_id"),
                    "name": p.get("provider_name"),
                    "logo_url": get_provider_logo_url(p.get("logo_path"))
                })

            return {
                "tagline": data.get("tagline", ""),
                "overview": data.get("overview", "") or data.get("tagline", ""),
                "trailer_key": trailer_key,
                "cast": [c["name"] for c in cast_list[:5]],
                "cast_details": cast_list,
                "director": director,
                "backdrop_url": f"{IMAGE_BASE_URL}/w1280{data['backdrop_path']}" if data.get("backdrop_path") else None,
                "vote_count": data.get("vote_count", 0),
                "vod_providers": vod_list,
            }
    except Exception:
        pass
    return None
