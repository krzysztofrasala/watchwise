from __future__ import annotations
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import quote
from functools import lru_cache

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
DEFAULT_POSTER = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?q=80&w=500&auto=format&fit=crop"
DEFAULT_API_KEY = ""

_session: requests.Session | None = None


def get_session() -> requests.Session:
    """Thread-safe connection pooling session for TMDB requests."""
    global _session
    if _session is None:
        _session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=retries)
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
    return _session

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

SUPPORTED_VOD_SERVICES = [
    {"id": 8, "name": "Netflix", "logo_url": "https://image.tmdb.org/t/p/w92/pbpMk2JmcoNnQwx5JGp8jWBDjeW.jpg", "badge_color": "#E50914"},
    {"id": 1899, "name": "Max", "logo_url": "https://image.tmdb.org/t/p/w92/jse515m3uB8g4t3zS7d0A1b9.jpg", "badge_color": "#002BE7"},
    {"id": 337, "name": "Disney+", "logo_url": "https://image.tmdb.org/t/p/w92/97yvRBw1GzX7fT5Y2j7kM8q6Qx.jpg", "badge_color": "#113CCF"},
    {"id": 119, "name": "Prime Video", "logo_url": "https://image.tmdb.org/t/p/w92/p5117uVzD6nF14l4lKkE4o25X8k.jpg", "badge_color": "#00A8E1"},
    {"id": 350, "name": "Apple TV+", "logo_url": "https://image.tmdb.org/t/p/w92/2E03pXt88mPuvE2M97w6J4lA1.jpg", "badge_color": "#A2AAAD"},
    {"id": 1773, "name": "SkyShowtime", "logo_url": "https://image.tmdb.org/t/p/w92/77zL1G9g9M9k9J9k.jpg", "badge_color": "#FFC700"},
]


def get_supported_vod_services() -> list[dict]:
    """Return canonical list of supported streaming platforms with logos and brand colors."""
    return list(SUPPORTED_VOD_SERVICES)


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
        return "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?q=80&w=200&auto=format&fit=crop"
    if profile_path.startswith("http"):
        return profile_path
    path = profile_path if profile_path.startswith("/") else f"/{profile_path}"
    return f"{IMAGE_BASE_URL}/{size}{path}"

def get_provider_logo_url(logo_path: str, size: str = "w92") -> str:
    if not logo_path or str(logo_path) in ["nan", "None", ""]:
        return ""
    if logo_path.startswith("http"):
        return logo_path
    path = logo_path if logo_path.startswith("/") else f"/{logo_path}"
    return f"{IMAGE_BASE_URL}/{size}{path}"


def get_provider_direct_url(provider_name: str, provider_id: int, movie_title: str, justwatch_url: str = None) -> str:
    title_q = quote(movie_title or "")
    name_lower = (provider_name or "").lower()

    if "netflix" in name_lower or provider_id == 8:
        return f"https://www.netflix.com/search?q={title_q}"
    elif "disney" in name_lower or provider_id == 337:
        return f"https://www.disneyplus.com/search?q={title_q}"
    elif "prime" in name_lower or "amazon" in name_lower or provider_id in [119, 10, 9]:
        return f"https://www.primevideo.com/search?phrase={title_q}"
    elif "max" in name_lower or "hbo" in name_lower or provider_id in [1899, 384]:
        return f"https://www.max.com/search?q={title_q}"
    elif "apple" in name_lower or "itunes" in name_lower or provider_id in [350, 2]:
        if justwatch_url:
            return justwatch_url
        return f"https://www.justwatch.com/pl/search?q={title_q}"
    elif "skyshowtime" in name_lower or provider_id == 1773:
        return f"https://www.skyshowtime.com/search?q={title_q}"
    elif "canal" in name_lower:
        return f"https://www.canalplus.com/pl/szukaj/{title_q}"
    elif "player" in name_lower:
        return f"https://player.pl/szukaj?q={title_q}"
    elif "polsat" in name_lower:
        return f"https://polsatboxgo.pl/szukaj?phrase={title_q}"
    elif "rakuten" in name_lower or provider_id == 35:
        return f"https://www.rakuten.tv/pl/search?q={title_q}"
    elif "youtube" in name_lower or provider_id == 192:
        return f"https://www.youtube.com/results?search_query={title_q}"
    elif "google" in name_lower or provider_id == 3:
        return f"https://play.google.com/store/search?c=movies&q={title_q}"
    elif "chili" in name_lower or provider_id == 230:
        return f"https://pl.chili.com/search?q={title_q}"
    elif "pilot" in name_lower:
        return f"https://pilot.wp.pl/szukaj?q={title_q}"
    elif "viaplay" in name_lower:
        return f"https://viaplay.pl/search?q={title_q}"
    elif "megogo" in name_lower:
        return f"https://megogo.net/pl/search?q={title_q}"
    elif "filmbox" in name_lower:
        return f"https://www.filmboxplus.com/pl/search?query={title_q}"
    elif justwatch_url:
        return justwatch_url
    else:
        return f"https://www.justwatch.com/pl/search?q={title_q}"


def get_justwatch_url(title: str, lang: str = "PL") -> str:
    """Return JustWatch search URL for movie title."""
    region = "pl" if (lang or "PL").upper() == "PL" else "us"
    return f"https://www.justwatch.com/{region}/search?q={quote(title or '')}"


def get_search_deeplinks(title: str) -> list[dict]:
    """Provide direct search deeplinks for top streaming providers."""
    title_q = quote(title or "")
    return [
        {
            "id": 8,
            "name": "Netflix",
            "logo_url": "https://image.tmdb.org/t/p/w92/pbpMk2JmcoNnQwx5JGp8jWBDjeW.jpg",
            "direct_url": f"https://www.netflix.com/search?q={title_q}",
            "badge_color": "#E50914",
        },
        {
            "id": 1899,
            "name": "Max",
            "logo_url": "https://image.tmdb.org/t/p/w92/jse515m3uB8g4t3zS7d0A1b9.jpg",
            "direct_url": f"https://www.max.com/search?q={title_q}",
            "badge_color": "#002BE7",
        },
        {
            "id": 337,
            "name": "Disney+",
            "logo_url": "https://image.tmdb.org/t/p/w92/97yvRBw1GzX7fT5Y2j7kM8q6Qx.jpg",
            "direct_url": f"https://www.disneyplus.com/search?q={title_q}",
            "badge_color": "#113CCF",
        },
        {
            "id": 119,
            "name": "Prime Video",
            "logo_url": "https://image.tmdb.org/t/p/w92/p5117uVzD6nF14l4lKkE4o25X8k.jpg",
            "direct_url": f"https://www.primevideo.com/search?phrase={title_q}",
            "badge_color": "#00A8E1",
        },
        {
            "id": 350,
            "name": "Apple TV+",
            "logo_url": "https://image.tmdb.org/t/p/w92/2E03pXt88mPuvE2M97w6J4lA1.jpg",
            "direct_url": f"https://tv.apple.com/search?term={title_q}",
            "badge_color": "#A2AAAD",
        },
        {
            "id": 1773,
            "name": "SkyShowtime",
            "logo_url": "https://image.tmdb.org/t/p/w92/77zL1G9g9M9k9J9k.jpg",
            "direct_url": f"https://www.skyshowtime.com/search?q={title_q}",
            "badge_color": "#FFC700",
        },
    ]


@lru_cache(maxsize=300)
def fetch_movie_details(movie_id: int, lang: str = "PL") -> dict | None:
    api_key = get_api_key()
    if not api_key:
        return None
    lang_map = {
        "PL": "pl-PL",
        "EN": "en-US",
        "DE": "de-DE",
        "ES": "es-ES",
        "FR": "fr-FR",
        "IT": "it-IT",
    }
    lang_code = lang.upper() if lang else "PL"
    tmdb_lang = lang_map.get(lang_code, "pl-PL")
    region_code = lang_code if lang_code in ["PL", "US", "DE", "ES", "FR", "IT"] else "PL"

    try:
        url = f"{BASE_URL}/movie/{movie_id}"
        params = {
            "api_key": api_key,
            "append_to_response": "videos,credits,watch/providers",
            "language": tmdb_lang
        }
        res = get_session().get(url, params=params, timeout=4)
        is_tv = False

        # If movie not found, try TV show endpoint
        if res.status_code == 404:
            url = f"{BASE_URL}/tv/{movie_id}"
            res = get_session().get(url, params=params, timeout=4)
            is_tv = True

        if res.status_code == 200:
            data = res.json()
            trailer_key = None
            videos = data.get("videos", {}).get("results", [])
            
            # Find trailer or teaser in localized videos
            for v in videos:
                if v.get("site") == "YouTube" and v.get("type") in ["Trailer", "Teaser"]:
                    trailer_key = v.get("key")
                    break
            
            # If no localized trailer, fallback to English videos
            if not trailer_key and tmdb_lang != "en-US":
                try:
                    endpoint = "tv" if is_tv else "movie"
                    v_res = get_session().get(f"{BASE_URL}/{endpoint}/{movie_id}/videos", params={"api_key": api_key, "language": "en-US"}, timeout=3)
                    if v_res.status_code == 200:
                        en_videos = v_res.json().get("results", [])
                        for v in en_videos:
                            if v.get("site") == "YouTube" and v.get("type") in ["Trailer", "Teaser"]:
                                trailer_key = v.get("key")
                                break
                except Exception:
                    pass

            cast_raw = data.get("credits", {}).get("cast", [])[:8]
            cast_list = []
            for c in cast_raw:
                cast_list.append({
                    "name": c.get("name"),
                    "character": c.get("character"),
                    "profile_url": get_profile_url(c.get("profile_path"))
                })

            if is_tv:
                director = next((c.get("name") for c in data.get("created_by", []) if c.get("name")), None)
                if not director:
                    director = next((c.get("name") for c in data.get("credits", {}).get("crew", []) if c.get("job") in ["Executive Producer", "Director"]), None)
            else:
                director = next((c.get("name") for c in data.get("credits", {}).get("crew", []) if c.get("job") == "Director"), None)

            # Extract VOD providers for region (fallback to PL/US)
            watch_results = data.get("watch/providers", {}).get("results", {})
            reg_providers = watch_results.get(region_code, {}) or watch_results.get("PL", {}) or watch_results.get("US", {})
            
            movie_title = data.get("title") or data.get("name") or data.get("original_title") or data.get("original_name") or ""
            justwatch_url = reg_providers.get("link")
            if not justwatch_url and movie_title:
                justwatch_url = f"https://www.justwatch.com/{region_code.lower()}/search?q={quote(movie_title)}"

            flatrate = reg_providers.get("flatrate", [])
            rent = reg_providers.get("rent", [])
            buy = reg_providers.get("buy", [])
            
            vod_list = []
            seen_ids = set()
            for p in (flatrate + rent + buy):
                pid = p.get("provider_id")
                pname = p.get("provider_name")
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    direct_url = get_provider_direct_url(pname, pid, movie_title, justwatch_url)
                    vod_list.append({

                        "id": pid,
                        "name": pname,
                        "logo_url": get_provider_logo_url(p.get("logo_path")),
                        "direct_url": direct_url,
                        "justwatch_url": justwatch_url
                    })

            res_dict = {
                "title": movie_title,
                "tagline": data.get("tagline", ""),
                "overview": data.get("overview", "") or data.get("tagline", ""),
                "trailer_key": trailer_key,
                "justwatch_url": justwatch_url,
                "cast": [c["name"] for c in cast_list[:5]],
                "cast_details": cast_list,
                "director": director,
                "poster_path": data.get("poster_path"),
                "poster_url": get_poster_url(data.get("poster_path")),
                "backdrop_path": data.get("backdrop_path"),
                "backdrop_url": get_backdrop_url(data.get("backdrop_path")),
                "vote_count": data.get("vote_count", 0),
                "vote_average": round(float(data.get("vote_average", 0.0)), 1),
                "vod_providers": vod_list,
                "is_tv": is_tv,
                "media_type": "tv" if is_tv else "movie",
            }

            if is_tv:
                seasons = data.get("number_of_seasons", 0)
                episodes = data.get("number_of_episodes", 0)
                first_air = data.get("first_air_date") or ""
                res_dict["year"] = int(first_air[:4]) if first_air[:4].isdigit() else 0
                res_dict["seasons"] = seasons
                res_dict["episodes"] = episodes
                if lang_code == "PL":
                    res_dict["tv_info"] = f"{seasons} sez. • {episodes} odc."
                else:
                    res_dict["tv_info"] = f"{seasons} seasons • {episodes} eps."

            return res_dict
    except Exception:
        pass
    return None


def search_tmdb_multi(query: str, lang: str = "PL", limit: int = 8) -> list[dict]:
    """Search movies and TV series via TMDB multi search API."""
    if not query or len(query.strip()) < 2:
        return []
    api_key = get_api_key()
    if not api_key:
        return []
    lang_map = {
        "PL": "pl-PL",
        "EN": "en-US",
        "DE": "de-DE",
        "ES": "es-ES",
        "FR": "fr-FR",
        "IT": "it-IT",
    }
    tmdb_lang = lang_map.get(lang.upper() if lang else "PL", "pl-PL")

    try:
        url = f"{BASE_URL}/search/multi"
        params = {
            "api_key": api_key,
            "query": query.strip(),
            "language": tmdb_lang,
            "include_adult": False
        }
        res = get_session().get(url, params=params, timeout=4)
        if res.status_code == 200:
            results = res.json().get("results", [])
            items = []
            for item in results:
                m_type = item.get("media_type")
                if m_type not in ["movie", "tv"]:
                    continue

                movie_id = item.get("id")
                title = item.get("title") or item.get("name") or item.get("original_title") or item.get("original_name")
                if not title:
                    continue

                date_str = item.get("release_date") or item.get("first_air_date") or ""
                year = int(date_str[:4]) if date_str[:4].isdigit() else None

                items.append({
                    "movie_id": movie_id,
                    "title": title,
                    "media_type": m_type,
                    "is_tv": (m_type == "tv"),
                    "media_badge": "📺 Serial" if m_type == "tv" else "🎬 Film",
                    "year": year,
                    "poster_url": get_poster_url(item.get("poster_path")),
                    "backdrop_url": get_backdrop_url(item.get("backdrop_path")),
                    "vote_average": round(float(item.get("vote_average", 0.0)), 1),
                    "overview": item.get("overview", ""),
                })
                if len(items) >= limit:
                    break
            return items
    except Exception:
        pass
    return []


@lru_cache(maxsize=50)
def fetch_trending(media_type: str = "movie", time_window: str = "day", lang: str = "PL", limit: int = 12) -> list[dict]:
    """Fetch trending movies or TV series from TMDB API."""
    api_key = get_api_key()
    if not api_key:
        return []
    lang_map = {
        "PL": "pl-PL",
        "EN": "en-US",
        "DE": "de-DE",
        "ES": "es-ES",
        "FR": "fr-FR",
        "IT": "it-IT",
    }
    tmdb_lang = lang_map.get(lang.upper() if lang else "PL", "pl-PL")
    valid_type = "tv" if media_type == "tv" else "movie"

    try:
        url = f"{BASE_URL}/trending/{valid_type}/{time_window}"
        params = {
            "api_key": api_key,
            "language": tmdb_lang,
        }
        res = get_session().get(url, params=params, timeout=4)
        if res.status_code == 200:
            results = res.json().get("results", [])
            items = []
            for item in results:
                movie_id = item.get("id")
                title = item.get("title") or item.get("name") or item.get("original_title") or item.get("original_name")
                if not title or not movie_id:
                    continue

                date_str = item.get("release_date") or item.get("first_air_date") or ""
                year = int(date_str[:4]) if date_str[:4].isdigit() else None

                items.append({
                    "movie_id": movie_id,
                    "title": title,
                    "media_type": valid_type,
                    "is_tv": (valid_type == "tv"),
                    "media_badge": "📺 Serial" if valid_type == "tv" else "🎬 Film",
                    "year": year,
                    "poster_path": item.get("poster_path"),
                    "backdrop_path": item.get("backdrop_path"),
                    "poster_url": get_poster_url(item.get("poster_path")),
                    "backdrop_url": get_backdrop_url(item.get("backdrop_path")),
                    "vote_average": round(float(item.get("vote_average", 0.0)), 1),
                    "overview": item.get("overview", ""),
                    "release_date": date_str,
                })
                if len(items) >= limit:
                    break
            return items
    except Exception:
        pass
    return []


@lru_cache(maxsize=50)
def fetch_upcoming(lang: str = "PL", limit: int = 12) -> list[dict]:
    """Fetch upcoming movies from TMDB API."""
    api_key = get_api_key()
    if not api_key:
        return []
    lang_map = {
        "PL": "pl-PL",
        "EN": "en-US",
        "DE": "de-DE",
        "ES": "es-ES",
        "FR": "fr-FR",
        "IT": "it-IT",
    }
    tmdb_lang = lang_map.get(lang.upper() if lang else "PL", "pl-PL")

    try:
        url = f"{BASE_URL}/movie/upcoming"
        params = {
            "api_key": api_key,
            "language": tmdb_lang,
            "region": "PL",
        }
        res = get_session().get(url, params=params, timeout=4)
        if res.status_code == 200:
            results = res.json().get("results", [])
            items = []
            for item in results:
                movie_id = item.get("id")
                title = item.get("title") or item.get("original_title")
                if not title or not movie_id:
                    continue

                date_str = item.get("release_date") or ""
                year = int(date_str[:4]) if date_str[:4].isdigit() else None

                items.append({
                    "movie_id": movie_id,
                    "title": title,
                    "media_type": "movie",
                    "is_tv": False,
                    "media_badge": "🍿 Premiera",
                    "year": year,
                    "poster_path": item.get("poster_path"),
                    "backdrop_path": item.get("backdrop_path"),
                    "poster_url": get_poster_url(item.get("poster_path")),
                    "backdrop_url": get_backdrop_url(item.get("backdrop_path")),
                    "vote_average": round(float(item.get("vote_average", 0.0)), 1),
                    "overview": item.get("overview", ""),
                    "release_date": date_str,
                })
                if len(items) >= limit:
                    break
            return items
    except Exception:
        pass
    return []

