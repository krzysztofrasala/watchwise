"""Discover Pro: advanced catalog filters."""

from django.shortcuts import render

from .. import services, tmdb, profiles
from .common import (
    attach_vod_parallel,
    get_base_context,
    prepare_movie_item,
    warm_localized,
)


def discover(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    genre = request.GET.get("genre", "All")
    language = request.GET.get("language")
    vote_min = request.GET.get("vote_min")
    year_min = request.GET.get("year_min")
    year_max = request.GET.get("year_max")
    max_runtime = request.GET.get("max_runtime")
    vod_filter = request.GET.get("vod", "all").strip()
    sort_by = request.GET.get("sort_by", "vote_desc")
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    per_page = 24

    my_subs = profiles.get_active_vod_subscriptions(request.session)
    supported_services = tmdb.get_supported_vod_services()
    for s in supported_services:
        s["is_subscribed"] = s["id"] in my_subs

    candidate_ids = None
    if vod_filter and vod_filter != "all":
        target_pids = list(my_subs) if vod_filter == "my_vod" else ([int(vod_filter)] if vod_filter.isdigit() else [])
        if target_pids:
            pre_filtered = services.filter_movies(
                genre=genre,
                year_min=year_min,
                year_max=year_max,
                vote_min=vote_min,
                language=language,
                max_runtime=max_runtime,
                sort_by=sort_by,
                page=1,
                per_page=180,
                lang=lang,
            )["items"]
            enriched = attach_vod_parallel(pre_filtered, lang, target_pids)
            candidate_ids = [
                m["movie_id"]
                for m in enriched
                if any(int(p.get("id", -1)) in target_pids for p in (m.get("vod_flatrate", []) + m.get("vod_providers", [])))
            ]
        else:
            candidate_ids = []

    filtered = services.filter_movies(
        genre=genre,
        year_min=year_min,
        year_max=year_max,
        vote_min=vote_min,
        language=language,
        max_runtime=max_runtime,
        candidate_ids=candidate_ids,
        sort_by=sort_by,
        page=page,
        per_page=per_page,
        lang=lang,
    )

    filtered["items"] = attach_vod_parallel(filtered["items"], lang, my_subs)

    ratings = profiles.get_active_ratings(request.session)
    warm_localized(filtered["items"], lang)
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
        "year_min": year_min,
        "year_max": year_max,
        "selected_runtime": max_runtime,
        "selected_vod": vod_filter,
        "supported_services": supported_services,
        "my_subscriptions": my_subs,
        "sort_by": sort_by,
    })

    if request.headers.get("HX-Request") and request.GET.get("page"):
        return render(request, "movies/partials/discover_grid.html", ctx)

    return render(request, "movies/discover.html", ctx)
