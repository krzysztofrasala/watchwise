"""Watchlist, watched list, ratings and VOD subscription settings."""

import json
from concurrent.futures import ThreadPoolExecutor

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST

from .. import services, tmdb, profiles, i18n
from .common import get_base_context, prepare_movie_item


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
            t_info = tmdb.fetch_vod_info(mid, lang=lang, title=resolved_movies[mid].get("title") or "")
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

    profiles.set_vod_subscriptions(request.session, provider_ids)
    request.session.modified = True

    if request.headers.get("HX-Request"):
        current_url = request.headers.get("HX-Current-URL", "") or request.META.get("HTTP_REFERER", "")
        if "/watchlist" in current_url:
            ctx = get_base_context(request)
            lang = ctx["current_lang"]
            w_data = get_watchlist_data(request)
            ctx.update(w_data)
            response = render(request, "movies/partials/watchlist_grid.html", ctx)
            response["HX-Trigger"] = json.dumps({
                "showToast": {"title": i18n.t("toast_vod_updated", lang), "type": "success"},
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
    trigger_payload = json.dumps({
        "showToast": {"title": toast_msg, "type": "success" if marked else "info"},
        "watchedChanged": {
            "movieId": int(movie_id),
            "marked": marked,
            "watchedCount": count,
            "watchlistCount": watchlist_count
        }
    })

    if request.headers.get("HX-Target") == "watchlist-grid-container":
        ctx = get_base_context(request)
        w_data = get_watchlist_data(request)
        ctx.update(w_data)
        response = render(request, "movies/partials/watchlist_grid.html", ctx)
        response["HX-Trigger"] = trigger_payload
        return response

    response = JsonResponse({
        "marked": marked,
        "watched_count": count,
        "watchlist_count": watchlist_count
    })
    response["HX-Trigger"] = trigger_payload
    return response


@require_POST
def rate_movie(request, movie_id):
    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
        stars = int(body.get("stars", 0))
    except Exception:
        try:
            stars = int(request.POST.get("stars", 0))
        except (ValueError, TypeError):
            stars = 0
    stars = max(0, min(5, stars))

    profiles.set_movie_rating(request.session, movie_id, stars)
    request.session.modified = True
    lang = i18n.get_lang(request.session)
    if stars > 0:
        msg = f"{i18n.t('toast_rating_saved', lang)}: {stars}/5 ★"
    else:
        msg = i18n.t("toast_rating_removed", lang)
    response = JsonResponse({"status": "ok", "movie_id": movie_id, "rating": stars})
    response["HX-Trigger"] = json.dumps({"showToast": {"title": msg, "type": "success" if stars > 0 else "info"}})
    return response
