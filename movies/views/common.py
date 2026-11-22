"""Shared helpers for the movie views: card preparation, VOD badges, base context, rate limiting."""

from concurrent.futures import ThreadPoolExecutor

from django.core.cache import cache

from .. import tmdb, profiles, i18n


def prepare_movie_item(item: dict, lang: str = "PL") -> dict:
    lang_upper = (lang or "PL").upper()
    lang_lower = lang_upper.lower()
    localize_catalog_item(item, lang)

    if item.get("_localized"):
        pass  # title/overview/tagline/poster already come from TMDB in the UI language
    elif lang_upper == "PL":
        if item.get("overview_pl"):
            item["overview"] = item["overview_pl"]
        if item.get("title_pl"):
            item["title"] = item["title_pl"]
        if item.get("tagline_pl"):
            item["tagline"] = item["tagline_pl"]
    else:
        # Non-PL languages (EN, DE, ES, FR, IT, UK)
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
            item["tagline"] = ""  # never leak Polish tagline on non-PL languages

    # Localize media_badge dynamically
    if item.get("is_tv") or item.get("media_type") == "tv":
        item["is_tv"] = True
        if not item.get("tv_info"):
            item["tv_info"] = i18n.t("badge_tv", lang)
        item["media_badge"] = f"📺 {i18n.t('badge_tv', lang)}"
    elif item.get("media_type") == "upcoming" or item.get("badge_type") == "upcoming":
        item["media_badge"] = f"🍿 {i18n.t('badge_upcoming', lang)}"
    elif item.get("media_badge") or item.get("media_type") == "movie":
        item["media_badge"] = f"🎬 {i18n.t('badge_movie', lang)}"

    item["poster_url"] = tmdb.get_poster_url(item.get("poster_path") or item.get("poster_url"))
    item["backdrop_url"] = tmdb.get_backdrop_url(item.get("backdrop_path") or item.get("backdrop_url"))
    try:
        item["vote_average"] = round(float(item.get("vote_average") or 0.0), 1)
    except (ValueError, TypeError):
        item["vote_average"] = 0.0

    title = item.get("title") or item.get("name") or ""
    if title:
        item["justwatch_url"] = tmdb.get_justwatch_url(title, lang=lang)
    return item


def enrich_movie_with_user_vod(item: dict, my_subs=None):
    """Enrich movie item with user's VOD subscription availability, logo, and direct URL."""
    if not item:
        return item
    sub_set = set(my_subs or [])
    flat_provs = item.get("vod_flatrate", [])
    all_provs = item.get("vod_providers", [])
    my_flat = [p for p in flat_provs if p.get("id") in sub_set]
    my_all = [p for p in all_provs if p.get("id") in sub_set]

    item["is_available_on_my_flatrate"] = bool(my_flat)
    item["is_available_on_my_vod"] = bool(my_all)
    item["my_flatrate_providers"] = my_flat

    primary_match = None
    if my_flat and my_flat[0].get("direct_url"):
        primary_match = my_flat[0]
    elif my_all and my_all[0].get("direct_url"):
        primary_match = my_all[0]
    elif my_flat:
        primary_match = my_flat[0]
    elif my_all:
        primary_match = my_all[0]

    if primary_match:
        item["primary_vod_name"] = primary_match.get("name")
        item["primary_vod_logo"] = primary_match.get("logo_url")
        item["primary_vod_url"] = primary_match.get("direct_url")
    else:
        item["primary_vod_name"] = None
        item["primary_vod_logo"] = None
        item["primary_vod_url"] = None

    return item


def localize_catalog_item(item: dict, lang: str) -> dict:
    """Catalog (dataset) items only have one language: pull title/overview/poster in the UI language from TMDB."""
    if (lang or "PL").upper() == "PL" or item.get("_localized") or "title_en" not in item:
        return item  # PL = dataset language; items without title_en already came from TMDB in `lang`
    basics = tmdb.fetch_localized_basics(item.get("movie_id"), lang=lang, media_type=item.get("media_type"))
    if not basics:
        return item
    for key in ("title", "overview", "tagline", "poster_path", "backdrop_path"):
        if basics.get(key):
            item[key] = basics[key]
    if basics.get("overview"):
        item["_overview_localized"] = True  # otherwise the (Polish) dataset text is machine-translated later
    elif basics.get("_overview_fallback"):
        item["overview"] = basics["_overview_fallback"]  # English source translates better than the Polish dataset text
    if not basics.get("tagline"):
        item["tagline"] = ""
    item["_localized"] = True
    # prepare_movie_item may already have derived these from the dataset values
    item["poster_url"] = tmdb.get_poster_url(item.get("poster_path"))
    item["backdrop_url"] = tmdb.get_backdrop_url(item.get("backdrop_path"))
    if item.get("title"):
        item["justwatch_url"] = tmdb.get_justwatch_url(item["title"], lang=lang)
    return item


def warm_localized(items, lang: str) -> None:
    """Localize a list of catalog items in parallel so the per-item calls that follow are cache hits."""
    todo = [it for it in (items or []) if isinstance(it, dict) and not it.get("_localized")]
    if (lang or "PL").upper() == "PL" or not todo:
        return
    with ThreadPoolExecutor(max_workers=min(len(todo), 8)) as executor:
        list(executor.map(lambda it: localize_catalog_item(it, lang), todo))


def attach_vod(item: dict, lang: str, my_subs=None) -> dict:
    """Attach cached VOD availability to a list item and match it against the user's subscriptions."""
    mid = item.get("movie_id")
    localize_catalog_item(item, lang)
    if mid:
        info = tmdb.fetch_vod_info(mid, lang=lang, media_type=item.get("media_type"), title=item.get("title") or "")
        item["vod_flatrate"] = info.get("vod_flatrate", [])
        item["vod_providers"] = info.get("vod_providers", [])
        if info.get("justwatch_url"):
            item["justwatch_url"] = info["justwatch_url"]
    return enrich_movie_with_user_vod(item, my_subs)


def attach_vod_parallel(items: list[dict], lang: str, my_subs=None) -> list[dict]:
    if not items:
        return items
    with ThreadPoolExecutor(max_workers=min(len(items), 8)) as executor:
        return list(executor.map(lambda it: attach_vod(it, lang, my_subs), items))


def get_base_context(request) -> dict:
    lang = i18n.get_lang(request.session)
    raw_active = profiles.get_active_profile_name(request.session)
    raw_profiles = list(profiles.get_profile_data(request.session).keys())
    watchlist_ids = profiles.get_active_watchlist(request.session)
    watched_ids = profiles.get_active_watched(request.session)

    default_trans = i18n.t("default_profile", lang)
    active_profile_display = default_trans if raw_active == "Główny" else raw_active
    all_profiles_display = []
    for name in raw_profiles:
        d_name = default_trans if name == "Główny" else name
        all_profiles_display.append({"raw": name, "display": d_name})

    return {
        "current_lang": lang,
        "active_profile": raw_active,
        "active_profile_display": active_profile_display,
        "all_profiles": raw_profiles,
        "all_profiles_display": all_profiles_display,
        "watchlist_count": len(watchlist_ids),
        "watched_count": len(watched_ids),
    }


def client_ip(request) -> str:
    """Client IP behind Render's proxy: the rightmost X-Forwarded-For entry is added by the proxy itself."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def rate_limited(request, scope: str, limit: int, window: int) -> bool:
    """Fixed-window counter in the cache. Returns True when the client exceeded the limit."""
    key = f"rl:{scope}:{client_ip(request)}"
    cache.add(key, 0, window)
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)
        count = 1
    return count > limit
