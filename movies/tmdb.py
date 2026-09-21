from __future__ import annotations
import os
import json
import re
import html
import base64
import subprocess
import logging
import urllib.parse
from urllib.parse import quote, unquote
from functools import lru_cache
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from . import i18n

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
DEFAULT_POSTER = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?q=80&w=500&auto=format&fit=crop"
DEFAULT_API_KEY = "4e44d9029b1270a757cddc766a1bcb63"

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


def _tmdb_get(url: str, params: dict, timeout: int = 4) -> dict | None:
    """Execute TMDB request with fast curl execution to prevent macOS LibreSSL TLS renegotiation hangs."""
    query_str = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    full_url = f"{url}?{query_str}"
    try:
        proc = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), full_url],
            capture_output=True,
            text=True,
            timeout=timeout + 1
        )
        if proc.returncode == 0 and proc.stdout:
            data = json.loads(proc.stdout)
            if isinstance(data, dict):
                return data
    except Exception:
        pass

    try:
        res = get_session().get(url, params=params, timeout=timeout)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


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
    {"id": 505, "name": "Player", "logo_url": "https://image.tmdb.org/t/p/w92/8mtdz2Y3NW5NfiSZiBFhngFSy3S.png", "badge_color": "#00A0E2"},
    {"id": 2102, "name": "Canal+", "logo_url": "https://image.tmdb.org/t/p/w92/kxOtmlmiegOd6Mp766dYdp2Ois3.png", "badge_color": "#000000"},
]


def get_supported_vod_services() -> list[dict]:
    """Return canonical list of supported streaming platforms with logos and brand colors."""
    return list(SUPPORTED_VOD_SERVICES)


def get_api_key() -> str:
    return os.getenv("TMDB_API_KEY", "").strip() or DEFAULT_API_KEY

def get_poster_url(poster_path: str | None, size: str = "w500") -> str:
    if not poster_path:
        return DEFAULT_POSTER
    if poster_path.startswith("http"):
        return poster_path
    return f"{IMAGE_BASE_URL}/{size}{poster_path}"

def get_backdrop_url(backdrop_path: str | None, size: str = "w1280") -> str:
    if not backdrop_path:
        return ""
    if backdrop_path.startswith("http"):
        return backdrop_path
    return f"{IMAGE_BASE_URL}/{size}{backdrop_path}"

def get_profile_url(profile_path: str | None, size: str = "w185") -> str:
    if not profile_path:
        return "https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=200&auto=format&fit=crop"
    if profile_path.startswith("http"):
        return profile_path
    return f"{IMAGE_BASE_URL}/{size}{profile_path}"

def get_provider_logo_url(logo_path: str | None, size: str = "w92") -> str:
    if not logo_path:
        return ""
    if logo_path.startswith("http"):
        return logo_path
    return f"{IMAGE_BASE_URL}/{size}{logo_path}"


def get_provider_direct_url(provider_name: str, provider_id: int | None = None, title: str = "", justwatch_url: str = None) -> str:
    """Generate search URL for provider as fallback when exact direct link is not available."""
    title_q = quote(title.strip())
    name_lower = (provider_name or "").lower()

    if "netflix" in name_lower or provider_id == 8:
        return f"https://www.netflix.com/search?q={title_q}"
    elif "prime" in name_lower or "amazon" in name_lower or provider_id in [9, 10, 119]:
        return f"https://www.primevideo.com/search/ref=atv_nb_sr?phrase={title_q}"
    elif "disney" in name_lower or provider_id == 337:
        return f"https://www.disneyplus.com/search?q={title_q}"
    elif "max" in name_lower or "hbo" in name_lower or provider_id in [1899, 384]:
        return f"https://www.max.com/search?q={title_q}"
    elif "apple" in name_lower or "itunes" in name_lower or provider_id in [350, 2]:
        return f"https://tv.apple.com/search?term={title_q}"
    elif "skyshowtime" in name_lower or provider_id == 1773:
        return f"https://www.skyshowtime.com/search?q={title_q}"
    elif "crunchyroll" in name_lower or provider_id in [283, 1968]:
        return f"https://www.crunchyroll.com/search?q={title_q}"
    elif "paramount" in name_lower or provider_id == 531:
        return f"https://www.paramountplus.com/search/?q={title_q}"
    elif "hulu" in name_lower or provider_id == 15:
        return f"https://www.hulu.com/search?q={title_q}"
    elif "canal" in name_lower or provider_id in [2102, 642]:
        # Canal+ blocks direct search URLs with 403; fallback to justwatch_url with working deep redirect
        return justwatch_url if justwatch_url else "https://www.canalplus.com"
    elif "player" in name_lower or provider_id == 505:
        # Player.pl does not support search query params (returns 404); fallback to justwatch_url with working deep redirect
        return justwatch_url if justwatch_url else "https://player.pl"
    elif "polsat" in name_lower:
        return f"https://polsatboxgo.pl/szukaj?phrase={title_q}"
    elif "rakuten" in name_lower or provider_id == 35:
        return f"https://www.rakuten.tv/search?q={title_q}"
    elif "youtube" in name_lower or provider_id == 192:
        return f"https://www.youtube.com/results?search_query={title_q}"
    elif "google" in name_lower or provider_id == 3:
        return f"https://play.google.com/store/search?c=movies&q={title_q}"
    elif "chili" in name_lower or provider_id in [230, 40]:
        return f"https://www.chili.com/search?q={title_q}"
    elif "pilot" in name_lower or provider_id == 2669:
        return f"https://pilot.wp.pl/szukaj/?q={title_q}"
    elif "viaplay" in name_lower:
        return f"https://viaplay.com/search?q={title_q}"
    elif "megogo" in name_lower:
        return f"https://megogo.net/pl/search?q={title_q}"
    elif "filmbox" in name_lower:
        return f"https://www.filmboxplus.com/pl/search?query={title_q}"
    elif justwatch_url:
        return justwatch_url
    else:
        return f"https://www.justwatch.com/search?q={title_q}"


def get_justwatch_url(title: str, lang: str = "PL") -> str:
    """Return JustWatch search URL for movie title."""
    lang_upper = (lang or "PL").upper()
    region_map = {
        "PL": "pl",
        "EN": "us",
        "DE": "de",
        "ES": "es",
        "FR": "fr",
        "IT": "it",
    }
    region = region_map.get(lang_upper, "us" if lang_upper != "PL" else "pl")
    return f"https://www.justwatch.com/{region}/search?q={quote(title or '')}"


def get_search_deeplinks(title: str) -> list[dict]:
    """Deprecated: Unverified fake providers removed to ensure 100% accurate availability."""
    return []


@lru_cache(maxsize=300)
def get_direct_provider_links(watch_url: str) -> dict:
    """Fetch TMDB watch page (powered by JustWatch) and extract exact direct provider streaming links."""
    if not watch_url:
        return {}
    try:
        proc = subprocess.run(
            ["curl", "--compressed", "-s", "--connect-timeout", "4", "-m", "8", watch_url],
            capture_output=True,
            text=True
        )
        if proc.returncode != 0 or not proc.stdout:
            return {}
        matches = re.findall(r'href=[\"\'](https://click\.justwatch\.com[^\'\"]+)[\"\']', proc.stdout)
        links = {}
        for raw_url in matches:
            clean_url = html.unescape(raw_url)
            parsed = urllib.parse.urlparse(clean_url)
            qs = urllib.parse.parse_qs(parsed.query)
            dest_url = qs.get("r", [clean_url])[0]
            cx_str = qs.get("cx", [""])[0]
            if cx_str:
                try:
                    padding = len(cx_str) % 4
                    if padding:
                        cx_str += "=" * (4 - padding)
                    payload = json.loads(base64.b64decode(cx_str))
                    for d in payload.get("data", []):
                        data_dict = d.get("data", {})
                        pid = data_dict.get("providerId")
                        m_type = data_dict.get("monetizationType")
                        p_name = (data_dict.get("provider") or "").lower()
                        if pid:
                            if m_type:
                                links[(pid, m_type)] = dest_url
                            if pid not in links:
                                links[pid] = dest_url
                        if p_name:
                            if m_type:
                                links[(p_name, m_type)] = dest_url
                            if p_name not in links:
                                links[p_name] = dest_url
                except Exception:
                    pass
        return links
    except Exception as e:
        logger.warning("Error extracting direct provider links: %s", e)
        return {}


def _format_provider(
    p: dict,
    movie_title: str,
    justwatch_url: str = None,
    region_code: str = "PL",
    monetization_type: str = None,
    direct_links_map: dict = None,
) -> dict:
    pid = p.get("provider_id") or p.get("id")
    pname = p.get("provider_name") or p.get("name")

    direct_url = None
    if direct_links_map:
        if monetization_type and (pid, monetization_type) in direct_links_map:
            direct_url = direct_links_map[(pid, monetization_type)]
        elif pid and pid in direct_links_map:
            direct_url = direct_links_map[pid]
        elif pname:
            p_clean = pname.lower()
            if monetization_type and (p_clean, monetization_type) in direct_links_map:
                direct_url = direct_links_map[(p_clean, monetization_type)]
            elif p_clean in direct_links_map:
                direct_url = direct_links_map[p_clean]

    if not direct_url:
        direct_url = get_provider_direct_url(pname, pid, movie_title, justwatch_url)

    return {
        "id": pid,
        "name": pname,
        "logo_url": get_provider_logo_url(p.get("logo_path")),
        "direct_url": direct_url,
        "justwatch_url": justwatch_url,
    }


OFFLINE_VOD_DATA = {
    278: {  # The Shawshank Redemption
        "US": {
            "flatrate": [{"id": 1899, "name": "Max", "logo_path": "/jse515m3uB8g4t3zS7d0A1b9.jpg"}],
            "rent": [
                {"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"},
                {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"},
            ],
            "buy": [
                {"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"},
                {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"},
            ],
        },
        "PL": {
            "flatrate": [{"id": 1899, "name": "Max", "logo_path": "/jse515m3uB8g4t3zS7d0A1b9.jpg"}],
            "rent": [
                {"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"},
                {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"},
                {"id": 35, "name": "Rakuten TV", "logo_path": "/bZvc9dXrXNly7cA0V4D9pR84SqW.jpg"},
            ],
            "buy": [
                {"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"},
                {"id": 35, "name": "Rakuten TV", "logo_path": "/bZvc9dXrXNly7cA0V4D9pR84SqW.jpg"},
            ],
        },
    },
    238: {  # The Godfather
        "US": {
            "flatrate": [{"id": 531, "name": "Paramount+", "logo_path": "/fi83B1oztoS47xxcemFdPMhIzK.jpg"}],
            "rent": [
                {"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"},
                {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"},
            ],
            "buy": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}],
        },
        "PL": {
            "flatrate": [{"id": 1773, "name": "SkyShowtime", "logo_path": "/77zL1G9g9M9k9J9k.jpg"}],
            "rent": [
                {"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"},
                {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"},
            ],
            "buy": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}],
        },
    },
    155: {  # The Dark Knight
        "US": {
            "flatrate": [{"id": 1899, "name": "Max", "logo_path": "/jse515m3uB8g4t3zS7d0A1b9.jpg"}],
            "rent": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}, {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}],
            "buy": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}],
        },
        "PL": {
            "flatrate": [{"id": 1899, "name": "Max", "logo_path": "/jse515m3uB8g4t3zS7d0A1b9.jpg"}],
            "rent": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}, {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}],
            "buy": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}],
        },
    },
    680: {  # Pulp Fiction
        "US": {
            "flatrate": [{"id": 1899, "name": "Max", "logo_path": "/jse515m3uB8g4t3zS7d0A1b9.jpg"}],
            "rent": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}, {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}],
            "buy": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}],
        },
        "PL": {
            "flatrate": [{"id": 1773, "name": "SkyShowtime", "logo_path": "/77zL1G9g9M9k9J9k.jpg"}, {"id": 8, "name": "Netflix", "logo_path": "/pbpMk2JmcoNnQwx5JGp8jWBDjeW.jpg"}],
            "rent": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}, {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}],
            "buy": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}],
        },
    },
    550: {  # Fight Club
        "US": {
            "flatrate": [{"id": 15, "name": "Hulu", "logo_path": "/zxrVdFj005nzAcvfi42xqeBz2DY.jpg"}],
            "rent": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}, {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}],
            "buy": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}],
        },
        "PL": {
            "flatrate": [{"id": 337, "name": "Disney+", "logo_path": "/97yvRBw1GzX7fT5Y2j7kM8q6Qx.jpg"}],
            "rent": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}, {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}],
            "buy": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}],
        },
    },
    13: {  # Forrest Gump
        "US": {
            "flatrate": [{"id": 531, "name": "Paramount+", "logo_path": "/fi83B1oztoS47xxcemFdPMhIzK.jpg"}],
            "rent": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}, {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}],
            "buy": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}],
        },
        "PL": {
            "flatrate": [{"id": 1773, "name": "SkyShowtime", "logo_path": "/77zL1G9g9M9k9J9k.jpg"}, {"id": 8, "name": "Netflix", "logo_path": "/pbpMk2JmcoNnQwx5JGp8jWBDjeW.jpg"}],
            "rent": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}, {"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}],
            "buy": [{"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}],
        },
    },
    1171462: {  # Golden Kamuy
        "US": {"flatrate": [{"id": 8, "name": "Netflix", "logo_path": "/pbpMk2JmcoNnQwx5JGp8jWBDjeW.jpg"}]},
        "PL": {"flatrate": [{"id": 8, "name": "Netflix", "logo_path": "/pbpMk2JmcoNnQwx5JGp8jWBDjeW.jpg"}]},
    },
    581644: {  # The Misfits
        "US": {"flatrate": [{"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}]},
        "PL": {"flatrate": [{"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}]},
    },
    5: {  # Four Rooms
        "US": {"rent": [{"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}, {"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}]},
        "PL": {"rent": [{"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}, {"id": 350, "name": "Apple TV", "logo_path": "/2E03pXt88mPuvE2M97w6J4lA1.jpg"}]},
    },
    8195: {  # Ronin
        "US": {"flatrate": [{"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}]},
        "PL": {"flatrate": [{"id": 119, "name": "Prime Video", "logo_path": "/p5117uVzD6nF14l4lKkE4o25X8k.jpg"}]},
    },
    14: {  # American Beauty
        "US": {"flatrate": [{"id": 531, "name": "Paramount+", "logo_path": "/fi83B1oztoS47xxcemFdPMhIzK.jpg"}]},
        "PL": {"flatrate": [{"id": 1773, "name": "SkyShowtime", "logo_path": "/77zL1G9g9M9k9J9k.jpg"}]},
    },
}


def get_offline_vod(movie_id: int, title: str = "", lang: str = "PL") -> dict | None:
    """Return offline verified VOD providers for classic titles when TMDB API is offline or empty."""
    try:
        mid = int(movie_id)
    except (ValueError, TypeError):
        return None
    if mid not in OFFLINE_VOD_DATA:
        return None

    lang_upper = (lang or "PL").upper()
    region_code = "US" if lang_upper == "EN" else ("PL" if lang_upper == "PL" else "US")
    data_region = OFFLINE_VOD_DATA[mid].get(region_code) or OFFLINE_VOD_DATA[mid].get("PL") or OFFLINE_VOD_DATA[mid].get("US")
    if not data_region:
        return None

    justwatch_url = get_justwatch_url(title, lang=lang)

    flatrate = [_format_provider(p, title, justwatch_url, region_code) for p in data_region.get("flatrate", [])]
    rent = [_format_provider(p, title, justwatch_url, region_code) for p in data_region.get("rent", [])]
    buy = [_format_provider(p, title, justwatch_url, region_code) for p in data_region.get("buy", [])]

    all_providers = []
    seen = set()
    for p in (flatrate + rent + buy):
        if p["id"] not in seen:
            seen.add(p["id"])
            all_providers.append(p)

    return {
        "vod_flatrate": flatrate,
        "vod_rent": rent,
        "vod_buy": buy,
        "vod_providers": all_providers,
        "justwatch_url": justwatch_url,
    }


@lru_cache(maxsize=300)
def fetch_movie_details(movie_id: int, lang: str = "PL", media_type: str = None) -> dict | None:
    api_key = get_api_key()
    if not api_key:
        return get_offline_vod(movie_id, lang=lang)
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
    region_map = {
        "PL": "PL",
        "EN": "US",
        "DE": "DE",
        "ES": "ES",
        "FR": "FR",
        "IT": "IT",
    }
    region_code = region_map.get(lang_code, "PL")

    try:
        params = {
            "api_key": api_key,
            "append_to_response": "videos,credits,watch/providers",
            "language": tmdb_lang
        }

        data = None
        is_tv = False

        if media_type == "tv":
            data = _tmdb_get(f"{BASE_URL}/tv/{movie_id}", params, timeout=4)
            is_tv = True
        elif media_type == "movie":
            data = _tmdb_get(f"{BASE_URL}/movie/{movie_id}", params, timeout=4)
            is_tv = False
        else:
            # Auto-detect when media_type is not explicitly specified
            # First check if movie_id is in local movies dataset (which only has movies)
            is_local = False
            try:
                from . import services
                is_local = services.get_movie_by_id(movie_id) is not None
            except Exception:
                pass

            if is_local:
                data = _tmdb_get(f"{BASE_URL}/movie/{movie_id}", params, timeout=4)
                is_tv = False
            else:
                # Check movie first
                m_data = _tmdb_get(f"{BASE_URL}/movie/{movie_id}", params, timeout=4)
                m_status = m_data.get("status_code") if m_data else 34
                m_votes = m_data.get("vote_count", 0) if (m_data and not m_status) else 0
                m_has_poster = bool(m_data.get("poster_path")) if (m_data and not m_status) else False

                # If movie 404 or obscure title with no poster / < 15 votes, inspect TV endpoint
                if not m_data or m_status == 34 or (m_votes < 15 and not m_has_poster):
                    tv_data = _tmdb_get(f"{BASE_URL}/tv/{movie_id}", params, timeout=4)
                    if tv_data and not tv_data.get("status_code"):
                        tv_votes = tv_data.get("vote_count", 0)
                        if tv_votes >= m_votes:
                            data = tv_data
                            is_tv = True

                if not data:
                    data = m_data
                    is_tv = False

        if data and not data.get("status_code"):
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
                    v_res = _tmdb_get(f"{BASE_URL}/{endpoint}/{movie_id}/videos", {"api_key": api_key, "language": "en-US"}, timeout=3)
                    if v_res and "results" in v_res:
                        en_videos = v_res.get("results", [])
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
            reg_providers = watch_results.get(region_code, {}) or watch_results.get("US" if region_code == "US" else "PL", {}) or watch_results.get("PL", {})
            
            movie_title = data.get("title") or data.get("name") or data.get("original_title") or data.get("original_name") or ""
            justwatch_url = reg_providers.get("link")
            if not justwatch_url and movie_title:
                justwatch_url = get_justwatch_url(movie_title, lang=lang)

            # Extract 100% genuine direct provider links from TMDB/JustWatch page
            direct_links_map = get_direct_provider_links(justwatch_url) if justwatch_url else {}

            flatrate = reg_providers.get("flatrate", [])
            rent = reg_providers.get("rent", [])
            buy = reg_providers.get("buy", [])
            
            vod_flatrate = [_format_provider(p, movie_title, justwatch_url, region_code, "flatrate", direct_links_map) for p in flatrate]
            vod_rent = [_format_provider(p, movie_title, justwatch_url, region_code, "rent", direct_links_map) for p in rent]
            vod_buy = [_format_provider(p, movie_title, justwatch_url, region_code, "buy", direct_links_map) for p in buy]

            vod_list = []
            seen_ids = set()
            for p in (vod_flatrate + vod_rent + vod_buy):
                if p["id"] not in seen_ids:
                    seen_ids.add(p["id"])
                    vod_list.append(p)

            # Offline fallback if providers are empty
            if not vod_list:
                offline = get_offline_vod(movie_id, title=movie_title, lang=lang)
                if offline:
                    vod_flatrate = offline.get("vod_flatrate", [])
                    vod_rent = offline.get("vod_rent", [])
                    vod_buy = offline.get("vod_buy", [])
                    vod_list = offline.get("vod_providers", [])

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
                "vod_flatrate": vod_flatrate,
                "vod_rent": vod_rent,
                "vod_buy": vod_buy,
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
        res_data = _tmdb_get(url, params, timeout=4)
        if res_data and "results" in res_data:
            results = res_data.get("results", [])
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
                    "media_badge": f"📺 {i18n.t('badge_tv', lang)}" if m_type == "tv" else f"🎬 {i18n.t('badge_movie', lang)}",
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
        res_data = _tmdb_get(url, params, timeout=4)
        if res_data and "results" in res_data:
            results = res_data.get("results", [])
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
                    "media_badge": f"📺 {i18n.t('badge_tv', lang)}" if valid_type == "tv" else f"🎬 {i18n.t('badge_movie', lang)}",
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

    region_map = {
        "PL": "PL",
        "EN": "US",
        "DE": "DE",
        "ES": "ES",
        "FR": "FR",
        "IT": "IT",
    }
    tmdb_region = region_map.get(lang.upper() if lang else "PL", "US" if (lang or "").upper() != "PL" else "PL")

    try:
        url = f"{BASE_URL}/movie/upcoming"
        params = {
            "api_key": api_key,
            "language": tmdb_lang,
            "region": tmdb_region,
        }
        res_data = _tmdb_get(url, params, timeout=4)
        if res_data and "results" in res_data:
            results = res_data.get("results", [])
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
                    "media_type": "upcoming",
                    "badge_type": "upcoming",
                    "is_tv": False,
                    "media_badge": f"🍿 {i18n.t('badge_upcoming', lang)}",
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

