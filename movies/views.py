import os
import json
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from . import services, tmdb, recommender, taste, nl_query, profiles, i18n


def prepare_movie_item(item: dict, lang: str = "PL") -> dict:
    lang_upper = (lang or "PL").upper()
    lang_lower = lang_upper.lower()

    if lang_upper == "PL":
        if item.get("overview_pl"):
            item["overview"] = item["overview_pl"]
        if item.get("title_pl"):
            item["title"] = item["title_pl"]
        if item.get("tagline_pl"):
            item["tagline"] = item["tagline_pl"]
    else:
        # Non-PL languages (EN, DE, ES, FR, IT)
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


def index(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    ratings = profiles.get_active_ratings(request.session)
    watchlist_ids = profiles.get_active_watchlist(request.session)
    watched_ids = profiles.get_active_watched(request.session)
    my_subs = profiles.get_active_vod_subscriptions(request.session)
    supported_services = tmdb.get_supported_vod_services()
    for s in supported_services:
        s["is_subscribed"] = s["id"] in my_subs
    subscribed_services = [s for s in supported_services if s["is_subscribed"]]

    genres = services.get_all_genres()
    filtered = services.filter_movies(genre="All", sort_by="vote_desc", per_page=24, lang=lang)

    for item in filtered["items"]:
        prepare_movie_item(item, lang=lang)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    # Enrich catalog items with TMDB VOD data in background
    def _enrich_cat(item):
        mid = item.get("movie_id")
        if mid:
            t_info = tmdb.fetch_movie_details(mid, lang=lang)
            if t_info:
                item["vod_flatrate"] = t_info.get("vod_flatrate", [])
                item["vod_providers"] = t_info.get("vod_providers", [])
                item["justwatch_url"] = t_info.get("justwatch_url")
        enrich_movie_with_user_vod(item, my_subs)
        return item

    if filtered["items"]:
        with ThreadPoolExecutor(max_workers=min(len(filtered["items"]), 8)) as executor:
            filtered["items"] = list(executor.map(_enrich_cat, filtered["items"]))

    hero_movie = None
    if filtered["items"]:
        for candidate in filtered["items"]:
            if candidate.get("poster_path") and candidate.get("overview") and candidate.get("vote_average", 0) > 0:
                hero_movie = candidate
                break
        if not hero_movie:
            hero_movie = filtered["items"][0]

    if hero_movie:
        tmdb_info = tmdb.fetch_movie_details(hero_movie["movie_id"], lang=lang)
        if tmdb_info:
            for k, v in tmdb_info.items():
                if v:
                    hero_movie[k] = v
        enrich_movie_with_user_vod(hero_movie, my_subs)
        lang_upper = (lang or "PL").upper()
        if lang_upper in ["ES", "DE", "FR", "IT"]:
            from . import translator
            if hero_movie.get("overview"):
                hero_movie["overview"] = translator.translate_text(hero_movie["overview"], target_lang=lang_upper)
            if hero_movie.get("tagline"):
                hero_movie["tagline"] = translator.translate_text(hero_movie["tagline"], target_lang=lang_upper)

    recommended_movies = recommender.recommend_for_user(
        ratings,
        watchlist_ids,
        top_n=10,
        lang=lang,
        watched_ids=watched_ids,
    )
    for rec in recommended_movies:
        prepare_movie_item(rec, lang=lang)
        rec["user_rating"] = ratings.get(rec["movie_id"], 0)
        enrich_movie_with_user_vod(rec, my_subs)

    trending_items = services.get_trending_content(category="movies", lang=lang)
    for item in trending_items:
        prepare_movie_item(item, lang=lang)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    # Enrich trending items with VOD
    def _enrich_trending(item):
        mid = item.get("movie_id")
        if mid:
            t_info = tmdb.fetch_movie_details(mid, lang=lang, media_type=item.get("media_type"))
            if t_info:
                item["vod_flatrate"] = t_info.get("vod_flatrate", [])
                item["vod_providers"] = t_info.get("vod_providers", [])
                item["justwatch_url"] = t_info.get("justwatch_url")
        enrich_movie_with_user_vod(item, my_subs)
        return item

    if trending_items:
        with ThreadPoolExecutor(max_workers=min(len(trending_items), 8)) as executor:
            trending_items = list(executor.map(_enrich_trending, trending_items))

    ctx.update({
        "genres": genres,
        "movies": filtered["items"],
        "recommended_movies": recommended_movies,
        "trending_items": trending_items,
        "current_category": "movies",
        "total_count": filtered["total_count"],
        "page": filtered["page"],
        "total_pages": filtered["total_pages"],
        "hero_movie": hero_movie,
        "my_subscriptions": my_subs,
        "supported_services": supported_services,
        "subscribed_services": subscribed_services,
        "vod_filter": "all",
    })
    return render(request, "movies/index.html", ctx)


def trending_partial(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    category = request.GET.get("category", "movies").strip()
    my_subs = profiles.get_active_vod_subscriptions(request.session)

    if category == "my_vod":
        if not my_subs:
            ctx.update({
                "trending_items": [],
                "current_category": "my_vod",
                "no_vod_configured": True,
                "my_subscriptions": my_subs,
            })
            return render(request, "movies/partials/trending_section.html", ctx)

        # Gather both trending movies and trending TV shows, then filter for user's VOD
        t_movies = services.get_trending_content(category="movies", lang=lang)
        t_shows = services.get_trending_content(category="tv", lang=lang)
        combined = (t_movies + t_shows)

        def _enrich_cand(item):
            mid = item.get("movie_id")
            if mid:
                t_info = tmdb.fetch_movie_details(mid, lang=lang, media_type=item.get("media_type"))
                if t_info:
                    item["vod_flatrate"] = t_info.get("vod_flatrate", [])
                    item["vod_providers"] = t_info.get("vod_providers", [])
                    item["justwatch_url"] = t_info.get("justwatch_url")
            enrich_movie_with_user_vod(item, my_subs)
            return item

        with ThreadPoolExecutor(max_workers=min(len(combined), 8)) as executor:
            enriched = list(executor.map(_enrich_cand, combined))

        my_vod_items = [m for m in enriched if m.get("is_available_on_my_vod")]

        # Supplement if pool is small
        if len(my_vod_items) < 6:
            for top_m in services.filter_movies(sort_by="rating_desc", per_page=40, lang=lang).get("items", []):
                mid = top_m.get("movie_id")
                if mid and not any(x.get("movie_id") == mid for x in my_vod_items):
                    _enrich_cand(top_m)
                    if top_m.get("is_available_on_my_vod"):
                        my_vod_items.append(top_m)
                        if len(my_vod_items) >= 12:
                            break

        ratings = profiles.get_active_ratings(request.session)
        for item in my_vod_items:
            prepare_movie_item(item, lang=lang)
            item["user_rating"] = ratings.get(item["movie_id"], 0)

        ctx.update({
            "trending_items": my_vod_items[:12],
            "current_category": "my_vod",
            "no_vod_configured": False,
            "my_subscriptions": my_subs,
        })
        return render(request, "movies/partials/trending_section.html", ctx)

    trending_items = services.get_trending_content(category=category, lang=lang)
    ratings = profiles.get_active_ratings(request.session)
    for item in trending_items:
        prepare_movie_item(item, lang=lang)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    def _enrich_trending_simple(item):
        mid = item.get("movie_id")
        if mid:
            t_info = tmdb.fetch_movie_details(mid, lang=lang, media_type=item.get("media_type"))
            if t_info:
                item["vod_flatrate"] = t_info.get("vod_flatrate", [])
                item["vod_providers"] = t_info.get("vod_providers", [])
                item["justwatch_url"] = t_info.get("justwatch_url")
        enrich_movie_with_user_vod(item, my_subs)
        return item

    if trending_items:
        with ThreadPoolExecutor(max_workers=min(len(trending_items), 8)) as executor:
            trending_items = list(executor.map(_enrich_trending_simple, trending_items))

    ctx.update({
        "trending_items": trending_items,
        "current_category": category,
        "my_subscriptions": my_subs,
        "no_vod_configured": False,
    })
    return render(request, "movies/partials/trending_section.html", ctx)


def movie_grid_partial(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    genre = request.GET.get("genre", "All")
    year_min = request.GET.get("year_min")
    year_max = request.GET.get("year_max")
    vote_min = request.GET.get("vote_min")
    sort_by = request.GET.get("sort_by", "vote_desc")
    page = int(request.GET.get("page", 1))
    vod_filter = request.GET.get("vod", "all").strip()

    ratings = profiles.get_active_ratings(request.session)
    my_subs = profiles.get_active_vod_subscriptions(request.session)

    if vod_filter == "my_vod" or vod_filter.isdigit():
        target_pids = [int(vod_filter)] if vod_filter.isdigit() else list(my_subs)
        # Fetch candidate movies to filter by VOD
        filtered_all = services.filter_movies(
            genre=genre,
            year_min=year_min,
            year_max=year_max,
            vote_min=vote_min,
            sort_by=sort_by,
            page=1,
            per_page=100,
            lang=lang,
        )
        cands = filtered_all["items"]

        def _check_vod(item):
            mid = item.get("movie_id")
            if mid:
                t_info = tmdb.fetch_movie_details(mid, lang=lang)
                if t_info:
                    item["vod_flatrate"] = t_info.get("vod_flatrate", [])
                    item["vod_providers"] = t_info.get("vod_providers", [])
            enrich_movie_with_user_vod(item, target_pids)
            return item

        with ThreadPoolExecutor(max_workers=min(len(cands), 8)) as executor:
            cands = list(executor.map(_check_vod, cands))

        matched_items = [m for m in cands if m.get("is_available_on_my_vod")]
        for item in matched_items:
            prepare_movie_item(item, lang=lang)
            item["user_rating"] = ratings.get(item["movie_id"], 0)

        ctx.update({
            "movies": matched_items[:24],
            "total_count": len(matched_items),
            "page": 1,
            "total_pages": 1,
            "current_genre": genre,
            "sort_by": sort_by,
            "vod_filter": vod_filter,
            "my_subscriptions": my_subs,
        })
        return render(request, "movies/partials/movie_grid.html", ctx)

    filtered = services.filter_movies(
        genre=genre,
        year_min=year_min,
        year_max=year_max,
        vote_min=vote_min,
        sort_by=sort_by,
        page=page,
        per_page=24,
        lang=lang,
    )

    def _enrich_cat_item(item):
        mid = item.get("movie_id")
        if mid:
            t_info = tmdb.fetch_movie_details(mid, lang=lang)
            if t_info:
                item["vod_flatrate"] = t_info.get("vod_flatrate", [])
                item["vod_providers"] = t_info.get("vod_providers", [])
        enrich_movie_with_user_vod(item, my_subs)
        return item

    with ThreadPoolExecutor(max_workers=min(len(filtered["items"]), 8)) as executor:
        filtered["items"] = list(executor.map(_enrich_cat_item, filtered["items"]))

    for item in filtered["items"]:
        prepare_movie_item(item, lang=lang)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    ctx.update({
        "movies": filtered["items"],
        "total_count": filtered["total_count"],
        "page": filtered["page"],
        "total_pages": filtered["total_pages"],
        "current_genre": genre,
        "sort_by": sort_by,
        "vod_filter": vod_filter,
        "my_subscriptions": my_subs,
    })
    return render(request, "movies/partials/movie_grid.html", ctx)


def search_live_partial(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    query = request.GET.get("q", "")
    results = services.search_movies(query, lang=lang, limit=8)
    ratings = profiles.get_active_ratings(request.session)

    for item in results:
        prepare_movie_item(item, lang=lang)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    ctx.update({
        "query": query,
        "results": results,
    })
    return render(request, "movies/partials/search_results.html", ctx)


def movie_modal_partial(request, movie_id):
    lang = i18n.get_lang(request.session)
    media_type = request.GET.get("media_type")
    movie = services.get_movie_by_id(movie_id, lang=lang) if media_type != "tv" else None
    if not movie:
        movie = {
            "movie_id": int(movie_id),
            "title": "",
            "poster_url": "",
            "backdrop_url": "",
            "vote_average": 0.0,
            "year": None,
        }
    if media_type:
        movie["media_type"] = media_type
        if media_type == "tv":
            movie["is_tv"] = True

    prepare_movie_item(movie, lang=lang)
    tmdb_info = tmdb.fetch_movie_details(movie_id, lang=lang, media_type=media_type)
    if tmdb_info:
        for k, v in tmdb_info.items():
            if v is not None:
                movie[k] = v
        prepare_movie_item(movie, lang=lang)

    # Fallback to offline VOD if providers missing
    if not movie.get("vod_flatrate") and not movie.get("vod_providers"):
        offline = tmdb.get_offline_vod(movie_id, title=movie.get("title", ""), lang=lang)
        if offline:
            for k, v in offline.items():
                movie[k] = v

    # Translate overview & tagline for foreign languages (ES, DE, FR, IT)
    lang_upper = (lang or "PL").upper()
    if lang_upper in ["ES", "DE", "FR", "IT"]:
        from . import translator
        if movie.get("overview"):
            movie["overview"] = translator.translate_text(movie["overview"], target_lang=lang_upper)
        if movie.get("tagline"):
            movie["tagline"] = translator.translate_text(movie["tagline"], target_lang=lang_upper)

    if not movie.get("title"):
        return HttpResponse(i18n.t("movie_not_found", lang), status=404)

    if not movie.get("justwatch_url") and movie.get("title"):
        movie["justwatch_url"] = tmdb.get_justwatch_url(movie["title"], lang=lang)

    recommendations = services.get_recommendations(movie_id, top_n=8, lang=lang)
    for rec in recommendations:
        prepare_movie_item(rec, lang=lang)

    watchlist_ids = profiles.get_active_watchlist(request.session)
    watched_ids = profiles.get_active_watched(request.session)
    ratings = profiles.get_active_ratings(request.session)

    is_in_watchlist = int(movie_id) in watchlist_ids
    is_watched = int(movie_id) in watched_ids
    user_rating = ratings.get(int(movie_id), 0)

    context = {
        "movie": movie,
        "recommendations": recommendations,
        "is_in_watchlist": is_in_watchlist,
        "is_watched": is_watched,
        "user_rating": user_rating,
        "current_lang": lang,
    }

    if request.headers.get("HX-Request"):
        return render(request, "movies/partials/movie_modal.html", context)

    # Direct browser link (/movie/<id>/)
    ctx = get_base_context(request)
    ctx.update(context)
    return render(request, "movies/movie_detail.html", ctx)


ROULETTE_MOODS = [
    {"id": "all", "label_key": "vibe_all", "desc_key": "vibe_all_desc", "icon": "sparkles"},
    {"id": "fun", "label_key": "vibe_fun", "desc_key": "vibe_fun_desc", "icon": "smile"},
    {"id": "thrill", "label_key": "vibe_thrill", "desc_key": "vibe_thrill_desc", "icon": "zap"},
    {"id": "action", "label_key": "vibe_action", "desc_key": "vibe_action_desc", "icon": "flame"},
    {"id": "mindfuck", "label_key": "vibe_mindfuck", "desc_key": "vibe_mindfuck_desc", "icon": "brain"},
    {"id": "romance", "label_key": "vibe_romance", "desc_key": "vibe_romance_desc", "icon": "heart"},
    {"id": "chill", "label_key": "vibe_chill", "desc_key": "vibe_chill_desc", "icon": "coffee"},
]

ROULETTE_RUNTIMES = [
    {"val": "0", "label_key": "runtime_any"},
    {"val": "90", "label_key": "runtime_short"},
    {"val": "105", "label_key": "runtime_medium"},
    {"val": "120", "label_key": "runtime_standard"},
    {"val": "121", "label_key": "runtime_epic"},
]

ROULETTE_SOURCES = [
    {"val": "all", "label_key": "source_all", "desc_key": "roulette_source_all_desc", "icon": "globe"},
    {"val": "watchlist_vod", "label_key": "source_watchlist_vod", "desc_key": "roulette_source_watchlist_vod_desc", "icon": "sparkles"},
    {"val": "my_vod", "label_key": "source_my_vod", "desc_key": "roulette_source_my_vod_desc", "icon": "tv"},
    {"val": "watchlist", "label_key": "source_watchlist", "desc_key": "roulette_source_watchlist_desc", "icon": "bookmark"},
]


def roulette(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    genre = request.GET.get("genre", "All")
    genres = services.get_all_genres()
    mood = request.GET.get("mood", "all")
    runtime = request.GET.get("runtime", "0")
    source = request.GET.get("source", "all")
    target_vod = request.GET.get("target_vod", "any")
    only_subs = request.GET.get("only_subs", "1") in ["1", "true", "True"]
    exclude_watched = request.GET.get("exclude_watched", "1") in ["1", "true", "True"]

    my_subs = profiles.get_active_vod_subscriptions(request.session)
    supported_services = tmdb.get_supported_vod_services()
    for s in supported_services:
        s["is_subscribed"] = s["id"] in my_subs

    subscribed_services = [s for s in supported_services if s["is_subscribed"]]

    ctx.update({
        "genres": genres,
        "selected_genre": genre,
        "selected_mood": mood,
        "selected_runtime": runtime,
        "selected_source": source,
        "selected_target_vod": target_vod,
        "only_subs": only_subs,
        "exclude_watched": exclude_watched,
        "moods": ROULETTE_MOODS,
        "runtimes": ROULETTE_RUNTIMES,
        "sources": ROULETTE_SOURCES,
        "my_subscriptions": my_subs,
        "supported_services": supported_services,
        "subscribed_services": subscribed_services,
    })
    return render(request, "movies/roulette.html", ctx)


def roulette_spin_partial(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]

    genre = request.GET.get("genre", "All").strip()
    mood = request.GET.get("mood", "all").strip()
    max_runtime = request.GET.get("runtime", "0").strip()
    min_rating = request.GET.get("rating", "0").strip()
    source = request.GET.get("source", "all").strip()
    target_vod = request.GET.get("target_vod", "any").strip()
    only_subs = request.GET.get("only_subs", "1").strip() in ["1", "true", "True"]
    exclude_watched = request.GET.get("exclude_watched", "1") in ["1", "true", "True"]

    watchlist_ids = profiles.get_active_watchlist(request.session)
    watched_ids = profiles.get_active_watched(request.session)
    my_subs = profiles.get_active_vod_subscriptions(request.session)
    ratings = profiles.get_active_ratings(request.session)

    # If VOD-focused source selected but user has 0 VOD subscriptions configured
    if source in ["watchlist_vod", "my_vod"] and not my_subs:
        ctx.update({
            "no_vod_configured": True,
            "movie": None,
            "teaser_pool": [],
            "selected_source": source,
            "my_subscriptions": my_subs,
        })
        return render(request, "movies/partials/roulette_result.html", ctx)

    target_pids = [int(target_vod)] if target_vod.isdigit() else list(my_subs)

    exclude_ids = list(watched_ids) if exclude_watched else []

    candidate_ids = None
    if source == "watchlist":
        candidate_ids = list(watchlist_ids)
    elif source == "watchlist_vod":
        vod_cands = []
        for mid in watchlist_ids:
            t_info = tmdb.fetch_movie_details(mid, lang=lang)
            if t_info:
                provs = t_info.get("vod_flatrate", []) if only_subs else t_info.get("vod_providers", [])
                if any(p.get("id") in target_pids for p in provs):
                    vod_cands.append(mid)
        candidate_ids = vod_cands
    elif source == "my_vod":
        # First gather candidates from watchlist matching subscriptions
        vod_cands = []
        for mid in watchlist_ids:
            t_info = tmdb.fetch_movie_details(mid, lang=lang)
            if t_info:
                provs = t_info.get("vod_flatrate", []) if only_subs else t_info.get("vod_providers", [])
                if any(p.get("id") in target_pids for p in provs):
                    vod_cands.append(mid)
        # Supplement from trending / top movies available on user's VOD
        if len(vod_cands) < 15:
            trending = services.get_trending_content(category="movies", lang=lang)
            for item in trending:
                mid = item.get("movie_id")
                if mid and mid not in vod_cands:
                    t_info = tmdb.fetch_movie_details(mid, lang=lang)
                    if t_info:
                        provs = t_info.get("vod_flatrate", []) if only_subs else t_info.get("vod_providers", [])
                        if any(p.get("id") in target_pids for p in provs):
                            vod_cands.append(mid)
        # Also check top rated movies from local dataset if needed
        if len(vod_cands) < 15:
            for item in services.filter_movies(sort_by="rating_desc")[:80]:
                mid = item.get("movie_id")
                if mid and mid not in vod_cands:
                    t_info = tmdb.fetch_movie_details(mid, lang=lang)
                    if t_info:
                        provs = t_info.get("vod_flatrate", []) if only_subs else t_info.get("vod_providers", [])
                        if any(p.get("id") in target_pids for p in provs):
                            vod_cands.append(mid)
        candidate_ids = list(set(vod_cands))

    if candidate_ids is not None and not candidate_ids:
        winner, teaser_pool = None, []
    else:
        winner, teaser_pool = services.get_random_movie_pool(
            genre=genre if genre != "All" else None,
            mood=mood if mood != "all" else None,
            max_runtime=int(max_runtime) if max_runtime.isdigit() and int(max_runtime) > 0 else None,
            min_rating=float(min_rating) if min_rating and float(min_rating) > 0 else None,
            candidate_ids=candidate_ids,
            exclude_ids=exclude_ids,
            pool_size=10,
        )
        if not winner and candidate_ids:
            # Fallback for candidates outside local dataset (e.g. TV shows or external TMDB movies)
            avail_cands = [c for c in candidate_ids if c not in exclude_ids]
            if avail_cands:
                import random
                chosen_mid = random.choice(avail_cands)
                winner_t = tmdb.fetch_movie_details(chosen_mid, lang=lang)
                if winner_t:
                    winner = dict(winner_t)
                    winner["movie_id"] = chosen_mid
                    teaser_pool = [winner]

    if winner:
        prepare_movie_item(winner, lang=lang)
        tmdb_info = tmdb.fetch_movie_details(winner["movie_id"], lang=lang)
        if tmdb_info:
            for k, v in tmdb_info.items():
                if v:
                    winner[k] = v
        winner["is_watched"] = winner["movie_id"] in watched_ids
        winner["is_in_watchlist"] = winner["movie_id"] in watchlist_ids
        winner["user_rating"] = ratings.get(winner["movie_id"], 0)

        # Match with user's subscriptions and find direct streaming link
        flat_provs = winner.get("vod_flatrate", [])
        all_provs = winner.get("vod_providers", [])
        my_flat = [p for p in flat_provs if p.get("id") in my_subs]
        my_all = [p for p in all_provs if p.get("id") in my_subs]
        winner["is_available_on_my_flatrate"] = bool(my_flat)
        winner["is_available_on_my_vod"] = bool(my_all)
        winner["my_flatrate_providers"] = my_flat

        target_int = int(target_vod) if target_vod.isdigit() else None
        primary_match = None
        if target_int:
            primary_match = next((p for p in (flat_provs + all_provs) if p.get("id") == target_int and p.get("direct_url")), None)
        if not primary_match and my_flat:
            primary_match = next((p for p in my_flat if p.get("direct_url")), my_flat[0])
        elif not primary_match and my_all:
            primary_match = next((p for p in my_all if p.get("direct_url")), my_all[0])
        elif not primary_match and flat_provs:
            primary_match = next((p for p in flat_provs if p.get("direct_url")), flat_provs[0])
        elif not primary_match and all_provs:
            primary_match = next((p for p in all_provs if p.get("direct_url")), all_provs[0])

        if primary_match and primary_match.get("direct_url"):
            winner["primary_vod_name"] = primary_match.get("name")
            winner["primary_vod_logo"] = primary_match.get("logo_url")
            winner["primary_vod_url"] = primary_match.get("direct_url")
        else:
            winner["primary_vod_name"] = None
            winner["primary_vod_logo"] = None
            winner["primary_vod_url"] = None

        # Translate overview & tagline for foreign languages (ES, DE, FR, IT)
        lang_upper = (lang or "PL").upper()
        if lang_upper in ["ES", "DE", "FR", "IT"]:
            from . import translator
            if winner.get("overview"):
                winner["overview"] = translator.translate_text(winner["overview"], target_lang=lang_upper)
            if winner.get("tagline"):
                winner["tagline"] = translator.translate_text(winner["tagline"], target_lang=lang_upper)

        if not winner.get("justwatch_url") and winner.get("title"):
            winner["justwatch_url"] = tmdb.get_justwatch_url(winner["title"], lang=lang)

        # Format runtime display string e.g. "1h 45m"
        rt = winner.get("runtime") or 0
        try:
            rt_int = int(rt)
            if rt_int > 0:
                hours = rt_int // 60
                mins = rt_int % 60
                winner["runtime_display"] = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        except (ValueError, TypeError):
            pass

    # Ensure winner is part of reel
    prepared_teasers = []
    for item in teaser_pool:
        prepare_movie_item(item, lang=lang)
        prepared_teasers.append(item)

    if winner and not any(t.get("movie_id") == winner["movie_id"] for t in prepared_teasers):
        prepared_teasers.insert(0, winner)

    ctx.update({
        "movie": winner,
        "teaser_pool": prepared_teasers,
        "selected_genre": genre,
        "selected_mood": mood,
        "selected_runtime": max_runtime,
        "selected_source": source,
        "selected_target_vod": target_vod,
        "only_subs": only_subs,
        "exclude_watched": exclude_watched,
        "my_subscriptions": my_subs,
    })
    return render(request, "movies/partials/roulette_result.html", ctx)


def get_watchlist_data(request) -> dict:
    lang = i18n.get_lang(request.session)
    tab = request.GET.get("tab", "watchlist").strip()
    if tab not in ["watchlist", "watched"]:
        tab = "watchlist"

    vod_filter = request.GET.get("vod", "all").strip()

    watchlist_ids = profiles.get_active_watchlist(request.session)
    watched_ids = profiles.get_active_watched(request.session)
    ratings = profiles.get_active_ratings(request.session)
    my_subscriptions = profiles.get_active_vod_subscriptions(request.session)
    supported_services = tmdb.get_supported_vod_services()

    active_ids = watched_ids if tab == "watched" else watchlist_ids

    parsed_ids = []
    for mid in active_ids:
        try:
            parsed_ids.append(int(mid))
        except (ValueError, TypeError):
            continue

    resolved_movies: dict[int, dict] = {}
    missing_ids: list[int] = []

    # 1. Fast O(1) lookup in local dataset
    for mid_int in parsed_ids:
        m = services.get_movie_by_id(mid_int, lang=lang)
        if m:
            resolved_movies[mid_int] = dict(m)
        else:
            missing_ids.append(mid_int)

    # 2. Parallel fetch for items outside local dataset (e.g. TV series or TMDB-only movies)
    if missing_ids:
        def _fetch_external(mid: int):
            tmdb_info = tmdb.fetch_movie_details(mid, lang=lang)
            if tmdb_info:
                return mid, {
                    "movie_id": mid,
                    "title": tmdb_info.get("title", ""),
                    "year": tmdb_info.get("year"),
                    "poster_path": tmdb_info.get("poster_path"),
                    "backdrop_path": tmdb_info.get("backdrop_path"),
                    "poster_url": tmdb_info.get("poster_url"),
                    "backdrop_url": tmdb_info.get("backdrop_url"),
                    "vote_average": tmdb_info.get("vote_average", 0.0),
                    "overview": tmdb_info.get("overview", ""),
                    "vod_flatrate": tmdb_info.get("vod_flatrate", []),
                    "vod_rent": tmdb_info.get("vod_rent", []),
                    "vod_buy": tmdb_info.get("vod_buy", []),
                    "vod_providers": tmdb_info.get("vod_providers", []),
                    "justwatch_url": tmdb_info.get("justwatch_url"),
                    "is_tv": tmdb_info.get("is_tv", False),
                    "tv_info": tmdb_info.get("tv_info", ""),
                }
            return mid, None

        with ThreadPoolExecutor(max_workers=min(len(missing_ids), 8)) as executor:
            for mid, m in executor.map(_fetch_external, missing_ids):
                if m:
                    resolved_movies[mid] = m

    # 3. Enrich local movies with TMDB VOD providers if not already present
    need_vod_enrichment = [mid for mid in parsed_ids if mid in resolved_movies and "vod_flatrate" not in resolved_movies[mid]]
    if need_vod_enrichment:
        def _fetch_vod(mid: int):
            t_info = tmdb.fetch_movie_details(mid, lang=lang)
            if not t_info:
                return mid, [], [], [], [], None
            return (
                mid,
                t_info.get("vod_flatrate", []),
                t_info.get("vod_rent", []),
                t_info.get("vod_buy", []),
                t_info.get("vod_providers", []),
                t_info.get("justwatch_url"),
            )

        with ThreadPoolExecutor(max_workers=min(len(need_vod_enrichment), 8)) as executor:
            for mid, flat_list, rent_list, buy_list, all_list, jw_url in executor.map(_fetch_vod, need_vod_enrichment):
                if mid in resolved_movies:
                    resolved_movies[mid]["vod_flatrate"] = flat_list
                    resolved_movies[mid]["vod_rent"] = rent_list
                    resolved_movies[mid]["vod_buy"] = buy_list
                    resolved_movies[mid]["vod_providers"] = all_list
                    resolved_movies[mid]["justwatch_url"] = jw_url

    # Preferences: only included with subscription (flatrate) vs rent/buy
    only_subs = request.GET.get("only_subs", "1").strip() in ["1", "true", "True"]
    view_mode = request.GET.get("view_mode", "grid").strip()
    if view_mode not in ["grid", "by_platform"]:
        view_mode = "grid"

    # 4. Assemble movies in original order & calculate availability per subscription
    all_movies = []
    for mid_int in parsed_ids:
        m = resolved_movies.get(mid_int)
        if m:
            prepare_movie_item(m, lang=lang)
            m["user_rating"] = ratings.get(m["movie_id"], 0)
            m["is_watched"] = mid_int in watched_ids
            m["is_in_watchlist"] = mid_int in watchlist_ids

            flat_provs = m.get("vod_flatrate", [])
            all_provs = m.get("vod_providers", [])

            # Match with user's subscriptions
            my_flatrate = [p for p in flat_provs if p.get("id") in my_subscriptions]
            my_other = [p for p in all_provs if p.get("id") in my_subscriptions and p.get("id") not in [f.get("id") for f in my_flatrate]]

            m["my_flatrate_providers"] = my_flatrate
            m["my_other_providers"] = my_other
            m["is_available_on_my_flatrate"] = bool(my_flatrate)
            m["is_available_on_my_vod"] = bool(my_flatrate or my_other)

            # Direct quick watch link to user's subscribed platform
            if my_flatrate and my_flatrate[0].get("direct_url"):
                m["primary_vod_name"] = my_flatrate[0]["name"]
                m["primary_vod_logo"] = my_flatrate[0].get("logo_url")
                m["primary_vod_url"] = my_flatrate[0].get("direct_url")
            elif flat_provs and flat_provs[0].get("direct_url"):
                m["primary_vod_name"] = flat_provs[0]["name"]
                m["primary_vod_logo"] = flat_provs[0].get("logo_url")
                m["primary_vod_url"] = flat_provs[0].get("direct_url")
            else:
                m["primary_vod_name"] = None
                m["primary_vod_logo"] = None
                m["primary_vod_url"] = None

            all_movies.append(m)

    # 5. Calculate counts per service
    my_vod_count = sum(
        1 for m in all_movies
        if (m["is_available_on_my_flatrate"] if only_subs else m["is_available_on_my_vod"])
    )

    for s in supported_services:
        s["flatrate_count"] = sum(
            1 for m in all_movies
            if any(p.get("id") == s["id"] for p in m.get("vod_flatrate", []))
        )
        s["total_count"] = sum(
            1 for m in all_movies
            if any(p.get("id") == s["id"] for p in m.get("vod_providers", []))
        )
        s["movie_count"] = s["flatrate_count"] if only_subs else s["total_count"]
        s["is_subscribed"] = s["id"] in my_subscriptions

    # 6. Build Platform Groups for 'by_platform' view mode
    platform_groups = []
    seen_in_groups = set()

    for s in supported_services:
        if s["id"] in my_subscriptions:
            s_movies = [
                m for m in all_movies
                if any(p.get("id") == s["id"] for p in (m.get("vod_flatrate", []) if only_subs else m.get("vod_providers", [])))
            ]
            if s_movies:
                platform_groups.append({
                    "service": s,
                    "movies": s_movies,
                    "count": len(s_movies),
                })
                for m in s_movies:
                    seen_in_groups.add(m["movie_id"])

    other_movies = [m for m in all_movies if m["movie_id"] not in seen_in_groups]

    # 7. Apply VOD filter for 'grid' view mode
    if vod_filter == "my_vod":
        filtered_movies = [
            m for m in all_movies
            if (m["is_available_on_my_flatrate"] if only_subs else m["is_available_on_my_vod"])
        ]
    elif vod_filter.isdigit():
        target_provider = int(vod_filter)
        filtered_movies = [
            m for m in all_movies
            if any(p.get("id") == target_provider for p in (m.get("vod_flatrate", []) if only_subs else m.get("vod_providers", [])))
        ]
    else:
        filtered_movies = all_movies

    return {
        "movies": filtered_movies,
        "all_movies": all_movies,
        "all_movies_count": len(all_movies),
        "tab": tab,
        "vod_filter": vod_filter,
        "only_subs": only_subs,
        "view_mode": view_mode,
        "my_subscriptions": my_subscriptions,
        "my_subscriptions_count": len(my_subscriptions),
        "supported_services": supported_services,
        "my_vod_count": my_vod_count,
        "platform_groups": platform_groups,
        "other_movies": other_movies,
        "watchlist_count": len(watchlist_ids),
        "watched_count": len(watched_ids),
    }


def watchlist(request):
    ctx = get_base_context(request)
    w_data = get_watchlist_data(request)
    ctx.update(w_data)
    return render(request, "movies/watchlist.html", ctx)


def watchlist_grid_partial(request):
    ctx = get_base_context(request)
    w_data = get_watchlist_data(request)
    ctx.update(w_data)
    return render(request, "movies/partials/watchlist_grid.html", ctx)


def vod_subscription_modal_partial(request):
    ctx = get_base_context(request)
    my_subs = profiles.get_active_vod_subscriptions(request.session)
    services_list = tmdb.get_supported_vod_services()
    for s in services_list:
        s["is_subscribed"] = s["id"] in my_subs
    
    current_url = request.headers.get("HX-Current-URL", "") or request.META.get("HTTP_REFERER", "")
    is_watchlist = "/watchlist" in current_url

    ctx.update({
        "supported_services": services_list,
        "my_subscriptions": my_subs,
        "is_watchlist": is_watchlist,
    })
    return render(request, "movies/partials/vod_subscriptions_modal.html", ctx)


@require_POST
def set_vod_subscriptions_view(request):
    raw_services = request.POST.getlist("services")
    provider_ids = []
    for s in raw_services:
        try:
            provider_ids.append(int(s))
        except (ValueError, TypeError):
            continue

    saved = profiles.set_vod_subscriptions(request.session, provider_ids)
    request.session.modified = True

    if request.headers.get("HX-Request"):
        current_url = request.headers.get("HX-Current-URL", "") or request.META.get("HTTP_REFERER", "")
        if "/watchlist" in current_url:
            ctx = get_base_context(request)
            w_data = get_watchlist_data(request)
            ctx.update(w_data)
            response = render(request, "movies/partials/watchlist_grid.html", ctx)
            response["HX-Trigger"] = json.dumps({
                "showToast": {"title": "Zaktualizowano Twoje serwisy VOD", "type": "success"},
                "closeVodModal": True
            })
            return response
        else:
            response = HttpResponse("")
            response["HX-Refresh"] = "true"
            return response

    return redirect("watchlist")


@require_POST
def toggle_watchlist(request, movie_id):
    added, count = profiles.toggle_watchlist_item(request.session, movie_id)
    request.session.modified = True
    lang = i18n.get_lang(request.session)
    msg = i18n.t("toast_added_to_watchlist", lang) if added else i18n.t("toast_removed_from_watchlist", lang)
    response = JsonResponse({"added": added, "count": count})
    response["HX-Trigger"] = json.dumps({
        "showToast": {"title": msg, "type": "success" if added else "info"},
        "watchlistChanged": {"movieId": int(movie_id), "added": added, "count": count}
    })
    return response


@require_POST
def toggle_watched(request, movie_id):
    marked, count = profiles.toggle_watched_item(request.session, movie_id)
    request.session.modified = True
    watchlist_count = len(profiles.get_active_watchlist(request.session))
    lang = i18n.get_lang(request.session)
    toast_msg = i18n.t("toast_marked_watched", lang) if marked else i18n.t("toast_unmarked_watched", lang)
    response = JsonResponse({
        "marked": marked,
        "watched_count": count,
        "watchlist_count": watchlist_count
    })
    response["HX-Trigger"] = json.dumps({
        "showToast": {"title": toast_msg, "type": "success" if marked else "info"},
        "watchedChanged": {
            "movieId": int(movie_id),
            "marked": marked,
            "watchedCount": count,
            "watchlistCount": watchlist_count
        }
    })
    return response


@require_POST
def rate_movie(request, movie_id):
    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
        stars = int(body.get("stars", 0))
    except Exception:
        stars = int(request.POST.get("stars", 0))

    ratings = profiles.set_movie_rating(request.session, movie_id, stars)
    request.session.modified = True
    lang = i18n.get_lang(request.session)
    if stars > 0:
        msg = f"{i18n.t('toast_rating_saved', lang)}: {stars}/5 ★"
    else:
        msg = i18n.t("toast_rating_removed", lang)
    response = JsonResponse({"status": "ok", "movie_id": movie_id, "rating": stars})
    response["HX-Trigger"] = json.dumps({"showToast": {"title": msg, "type": "success" if stars > 0 else "info"}})
    return response


def discover(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    genre = request.GET.get("genre", "All")
    language = request.GET.get("language")
    vote_min = request.GET.get("vote_min")
    year_min = request.GET.get("year_min")
    year_max = request.GET.get("year_max")
    sort_by = request.GET.get("sort_by", "vote_desc")
    page = int(request.GET.get("page", 1))
    per_page = 24

    filtered = services.filter_movies(
        genre=genre,
        year_min=year_min,
        year_max=year_max,
        vote_min=vote_min,
        language=language,
        sort_by=sort_by,
        page=page,
        per_page=per_page,
        lang=lang,
    )

    ratings = profiles.get_active_ratings(request.session)
    for item in filtered["items"]:
        prepare_movie_item(item, lang=lang)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    has_next = page < filtered["total_pages"]
    next_page = page + 1 if has_next else None

    ctx.update({
        "genres": services.get_all_genres(),
        "movies": filtered["items"],
        "total_count": filtered["total_count"],
        "total_pages": filtered["total_pages"],
        "page": page,
        "has_next": has_next,
        "next_page": next_page,
        "selected_genre": genre,
        "selected_language": language,
        "vote_min": vote_min,
        "sort_by": sort_by,
    })

    if request.headers.get("HX-Request") and request.GET.get("page"):
        return render(request, "movies/partials/discover_grid.html", ctx)

    return render(request, "movies/discover.html", ctx)


def taste_dna(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    ratings = profiles.get_active_ratings(request.session)
    watchlist_ids = profiles.get_active_watchlist(request.session)
    active_profile = profiles.get_active_profile_name(request.session)

    import hashlib
    raw_sig = f"{active_profile}:{sorted(ratings.items())}:{sorted(watchlist_ids)}:{lang}"
    cache_key = f"taste_dna_{hashlib.md5(raw_sig.encode()).hexdigest()}"
    taste_data = cache.get(cache_key)

    if taste_data is None:
        taste_data = taste.compute_taste_profile(ratings, watchlist_ids, lang=lang)
        cache.set(cache_key, taste_data, timeout=60 * 60 * 24)

    ctx.update({
        "taste_data": taste_data,
        "taste_data_json": json.dumps(taste_data),
    })
    return render(request, "movies/taste_dna.html", ctx)


def compare(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    all_profiles_dict = profiles.get_profile_data(request.session)
    profile_names = list(all_profiles_dict.keys())
    genres = services.get_all_genres()

    preset = request.GET.get("preset", "").strip()
    if preset == "couple":
        vibe1, vibe2 = "Action", "Romance"
    elif preset == "friends":
        vibe1, vibe2 = "Action", "Science Fiction"
    elif preset == "horror":
        vibe1, vibe2 = "Horror", "Thriller"
    elif preset == "family":
        vibe1, vibe2 = "Animation", "Adventure"
    else:
        vibe1 = request.GET.get("vibe1", "Action")
        vibe2 = request.GET.get("vibe2", "Comedy")

    p1 = request.GET.get("p1", profiles.get_active_profile_name(request.session))
    p2 = request.GET.get("p2", profile_names[1] if len(profile_names) > 1 else p1)

    p1_data = all_profiles_dict.get(p1, {"ratings": {}, "watchlist": []})
    p2_data = all_profiles_dict.get(p2, {"ratings": {}, "watchlist": []})

    recommendations = recommender.recommend_for_group(
        user1_ratings=p1_data.get("ratings", {}),
        user1_watchlist=p1_data.get("watchlist", []),
        user2_ratings=p2_data.get("ratings", {}),
        user2_watchlist=p2_data.get("watchlist", []),
        top_n=12,
        lang=lang
    )

    if not recommendations:
        recommendations = recommender.recommend_for_vibes(vibe1, vibe2, top_n=12, lang=lang)

    harmony_score = recommender.get_harmony_score(vibe1, vibe2)

    for rec in recommendations:
        prepare_movie_item(rec, lang=lang)

    default_trans = i18n.t("default_profile", lang)
    p1_display = default_trans if p1 == "Główny" else p1
    p2_display = default_trans if p2 == "Główny" else p2

    ctx.update({
        "profile_names": profile_names,
        "genres": genres,
        "vibe1": vibe1,
        "vibe2": vibe2,
        "preset": preset,
        "harmony_score": harmony_score,
        "p1": p1,
        "p2": p2,
        "p1_display": p1_display,
        "p2_display": p2_display,
        "recommendations": recommendations,
    })
    return render(request, "movies/compare.html", ctx)


def assistant(request):
    ctx = get_base_context(request)
    return render(request, "movies/assistant.html", ctx)


def assistant_chat_partial(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    user_message = request.POST.get("message", "").strip() or request.GET.get("message", "").strip()
    if not user_message:
        return HttpResponse("", status=400)

    parsed = nl_query.parse_natural_query(user_message)

    filtered = services.filter_movies(
        genre=parsed["genre"],
        year_min=parsed["year_min"],
        year_max=parsed["year_max"],
        vote_min=parsed["vote_min"],
        language=parsed["language"],
        sort_by=parsed["sort_by"],
        per_page=6,
        lang=lang,
    )

    results = filtered["items"]
    for item in results:
        prepare_movie_item(item, lang=lang)

    ctx.update({
        "user_message": user_message,
        "parsed": parsed,
        "movies": results,
    })
    return render(request, "movies/partials/assistant_response.html", ctx)


@require_POST
def switch_profile(request):
    profile_name = request.POST.get("profile_name", "").strip()
    if profile_name:
        profiles.set_active_profile(request.session, profile_name)
    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_POST
def create_profile(request):
    profile_name = request.POST.get("new_profile_name", "").strip()
    if profile_name:
        profiles.add_profile(request.session, profile_name)
    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_POST
def switch_language(request):
    lang_code = request.POST.get("lang", "PL").strip()
    i18n.set_lang(request.session, lang_code)
    return redirect(request.META.get("HTTP_REFERER", "/"))


def manifest_view(request):
    """Serve PWA manifest.json."""
    manifest_path = os.path.join(settings.BASE_DIR, "templates", "pwa", "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()
    response = HttpResponse(content, content_type="application/manifest+json; charset=utf-8")
    response["Cache-Control"] = "public, max-age=86400"
    return response


def service_worker_view(request):
    """Serve PWA service worker with root scope permissions."""
    sw_path = os.path.join(settings.BASE_DIR, "templates", "pwa", "sw.js")
    with open(sw_path, "r", encoding="utf-8") as f:
        content = f.read()
    response = HttpResponse(content, content_type="application/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


def offline_view(request):
    """Render dedicated offline fallback page."""
    ctx = get_base_context(request)
    return render(request, "offline.html", ctx)

