"""Home page, trending strip, catalog grid, live search and the movie modal."""

from django.shortcuts import render
from django.http import HttpResponse

from .. import services, tmdb, recommender, profiles, i18n
from .common import (
    attach_vod_parallel,
    enrich_movie_with_user_vod,
    get_base_context,
    prepare_movie_item,
    warm_localized,
)


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

    warm_localized(filtered["items"], lang)
    for item in filtered["items"]:
        prepare_movie_item(item, lang=lang)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    filtered["items"] = attach_vod_parallel(filtered["items"], lang, my_subs)

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
        if lang_upper in i18n.MACHINE_TRANSLATED_LANGS:
            from .. import translator
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
    warm_localized(recommended_movies, lang)
    for rec in recommended_movies:
        prepare_movie_item(rec, lang=lang)
        rec["user_rating"] = ratings.get(rec["movie_id"], 0)
        enrich_movie_with_user_vod(rec, my_subs)

    trending_items = services.get_trending_content(category="movies", lang=lang)
    warm_localized(trending_items, lang)
    for item in trending_items:
        prepare_movie_item(item, lang=lang)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    trending_items = attach_vod_parallel(trending_items, lang, my_subs)

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

        enriched = attach_vod_parallel(combined, lang, my_subs)
        my_vod_items = [m for m in enriched if m.get("is_available_on_my_vod")]

        # Supplement if pool is small
        if len(my_vod_items) < 6:
            have = {x.get("movie_id") for x in my_vod_items}
            extra = [
                m for m in services.filter_movies(sort_by="rating_desc", per_page=40, lang=lang).get("items", [])
                if m.get("movie_id") and m["movie_id"] not in have
            ]
            for top_m in attach_vod_parallel(extra, lang, my_subs):
                if top_m.get("is_available_on_my_vod"):
                    my_vod_items.append(top_m)
                    if len(my_vod_items) >= 12:
                        break

        ratings = profiles.get_active_ratings(request.session)
        warm_localized(my_vod_items, lang)
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
    warm_localized(trending_items, lang)
    for item in trending_items:
        prepare_movie_item(item, lang=lang)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    trending_items = attach_vod_parallel(trending_items, lang, my_subs)

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
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
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

        cands = attach_vod_parallel(cands, lang, target_pids)

        matched_items = [m for m in cands if m.get("is_available_on_my_vod")]
        warm_localized(matched_items, lang)
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

    filtered["items"] = attach_vod_parallel(filtered["items"], lang, my_subs)

    warm_localized(filtered["items"], lang)
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

    warm_localized(results, lang)
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

    # Translate overview & tagline for foreign languages (ES, DE, FR, IT, UK)
    lang_upper = (lang or "PL").upper()
    if lang_upper in i18n.MACHINE_TRANSLATED_LANGS and not movie.get("_overview_localized"):
        from .. import translator
        if movie.get("overview"):
            movie["overview"] = translator.translate_text(movie["overview"], target_lang=lang_upper)
        if movie.get("tagline"):
            movie["tagline"] = translator.translate_text(movie["tagline"], target_lang=lang_upper)

    if not movie.get("title"):
        return HttpResponse(i18n.t("movie_not_found", lang), status=404)

    if not movie.get("justwatch_url") and movie.get("title"):
        movie["justwatch_url"] = tmdb.get_justwatch_url(movie["title"], lang=lang)

    recommendations = services.get_recommendations(movie_id, top_n=8, lang=lang)
    warm_localized(recommendations, lang)
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
