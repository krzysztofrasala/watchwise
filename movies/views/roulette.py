"""Movie roulette: random pick by mood, runtime and source."""

from concurrent.futures import ThreadPoolExecutor

from django.shortcuts import render

from .. import services, tmdb, profiles, i18n
from .common import get_base_context, prepare_movie_item, warm_localized


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

    def _filter_on_target_vod(ids) -> list:
        """Keep the ids available on the chosen platforms (cached lookups, run in parallel)."""
        ids = list(ids)
        if not ids:
            return []

        def _is_on_target(mid) -> bool:
            info = tmdb.fetch_vod_info(mid, lang=lang)
            provs = info.get("vod_flatrate", []) if only_subs else info.get("vod_providers", [])
            return any(p.get("id") in target_pids for p in provs)

        with ThreadPoolExecutor(max_workers=min(len(ids), 8)) as executor:
            return [mid for mid, ok in zip(ids, executor.map(_is_on_target, ids)) if ok]

    candidate_ids = None
    if source == "watchlist":
        candidate_ids = list(watchlist_ids)
    elif source == "watchlist_vod":
        candidate_ids = _filter_on_target_vod(watchlist_ids)
    elif source == "my_vod":
        # First gather candidates from watchlist matching subscriptions
        vod_cands = _filter_on_target_vod(watchlist_ids)
        # Supplement from trending / top movies available on user's VOD
        if len(vod_cands) < 15:
            trending = services.get_trending_content(category="movies", lang=lang)
            vod_cands += _filter_on_target_vod(
                i["movie_id"] for i in trending if i.get("movie_id") and i["movie_id"] not in vod_cands
            )
        # Also check top rated movies from local dataset if needed
        if len(vod_cands) < 15:
            top_movies = services.filter_movies(genre="All", sort_by="vote_desc", per_page=40, lang=lang).get("items", [])
            vod_cands += _filter_on_target_vod(
                i["movie_id"] for i in top_movies if i.get("movie_id") and i["movie_id"] not in vod_cands
            )
        candidate_ids = list(dict.fromkeys(vod_cands))[:30]

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

        # Translate overview & tagline for foreign languages (ES, DE, FR, IT, UK)
        lang_upper = (lang or "PL").upper()
        if lang_upper in i18n.MACHINE_TRANSLATED_LANGS and not winner.get("_overview_localized"):
            from .. import translator
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
    warm_localized(teaser_pool, lang)
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
