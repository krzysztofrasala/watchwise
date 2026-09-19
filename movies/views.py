import json
from concurrent.futures import ThreadPoolExecutor
from django.core.cache import cache
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from . import services, tmdb, recommender, taste, nl_query, profiles, i18n


def prepare_movie_item(item: dict, lang: str = "PL") -> dict:
    item["poster_url"] = tmdb.get_poster_url(item.get("poster_path") or item.get("poster_url"))
    item["backdrop_url"] = tmdb.get_backdrop_url(item.get("backdrop_path") or item.get("backdrop_url"))
    try:
        item["vote_average"] = round(float(item.get("vote_average") or 0.0), 1)
    except (ValueError, TypeError):
        item["vote_average"] = 0.0

    title = item.get("title") or item.get("name") or ""
    if title:
        if not item.get("justwatch_url"):
            item["justwatch_url"] = tmdb.get_justwatch_url(title, lang=lang)
        if not item.get("search_deeplinks"):
            item["search_deeplinks"] = tmdb.get_search_deeplinks(title)
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
    genres = services.get_all_genres()
    filtered = services.filter_movies(genre="All", sort_by="vote_desc", per_page=24)

    for item in filtered["items"]:
        prepare_movie_item(item)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

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

    recommended_movies = recommender.recommend_for_user(
        ratings,
        watchlist_ids,
        top_n=10,
        lang=lang,
        watched_ids=watched_ids,
    )
    for rec in recommended_movies:
        prepare_movie_item(rec)
        rec["user_rating"] = ratings.get(rec["movie_id"], 0)

    trending_items = services.get_trending_content(category="movies", lang=lang)
    for item in trending_items:
        prepare_movie_item(item)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

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
    })
    return render(request, "movies/index.html", ctx)


def trending_partial(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    category = request.GET.get("category", "movies")
    trending_items = services.get_trending_content(category=category, lang=lang)

    ratings = profiles.get_active_ratings(request.session)
    for item in trending_items:
        prepare_movie_item(item)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    ctx.update({
        "trending_items": trending_items,
        "current_category": category,
    })
    return render(request, "movies/partials/trending_section.html", ctx)



def movie_grid_partial(request):
    ctx = get_base_context(request)
    genre = request.GET.get("genre", "All")
    year_min = request.GET.get("year_min")
    year_max = request.GET.get("year_max")
    vote_min = request.GET.get("vote_min")
    sort_by = request.GET.get("sort_by", "vote_desc")
    page = int(request.GET.get("page", 1))

    ratings = profiles.get_active_ratings(request.session)

    filtered = services.filter_movies(
        genre=genre,
        year_min=year_min,
        year_max=year_max,
        vote_min=vote_min,
        sort_by=sort_by,
        page=page,
        per_page=24
    )

    for item in filtered["items"]:
        prepare_movie_item(item)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    ctx.update({
        "movies": filtered["items"],
        "total_count": filtered["total_count"],
        "page": filtered["page"],
        "total_pages": filtered["total_pages"],
        "current_genre": genre,
        "sort_by": sort_by,
    })
    return render(request, "movies/partials/movie_grid.html", ctx)


def search_live_partial(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    query = request.GET.get("q", "")
    results = services.search_movies(query, lang=lang, limit=8)
    ratings = profiles.get_active_ratings(request.session)

    for item in results:
        prepare_movie_item(item)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    ctx.update({
        "query": query,
        "results": results,
    })
    return render(request, "movies/partials/search_results.html", ctx)


def movie_modal_partial(request, movie_id):
    lang = i18n.get_lang(request.session)
    movie = services.get_movie_by_id(movie_id)
    if not movie:
        movie = {
            "movie_id": int(movie_id),
            "title": "",
            "poster_url": "",
            "backdrop_url": "",
            "vote_average": 0.0,
            "year": None,
        }

    prepare_movie_item(movie, lang=lang)
    tmdb_info = tmdb.fetch_movie_details(movie_id, lang=lang)
    if tmdb_info:
        for k, v in tmdb_info.items():
            if v is not None:
                movie[k] = v

    if not movie.get("title"):
        return HttpResponse("Film lub serial nie został znaleziony.", status=404)

    if not movie.get("justwatch_url") and movie.get("title"):
        movie["justwatch_url"] = tmdb.get_justwatch_url(movie["title"], lang=lang)
    if not movie.get("search_deeplinks") and movie.get("title"):
        movie["search_deeplinks"] = tmdb.get_search_deeplinks(movie["title"])

    recommendations = services.get_recommendations(movie_id, top_n=8)
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
    {"val": "all", "label_key": "source_all", "icon": "globe"},
    {"val": "watchlist", "label_key": "source_watchlist", "icon": "bookmark"},
    {"val": "my_vod", "label_key": "source_my_vod", "icon": "tv"},
]


def roulette(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    genre = request.GET.get("genre", "All")
    genres = services.get_all_genres()
    mood = request.GET.get("mood", "all")
    runtime = request.GET.get("runtime", "0")
    source = request.GET.get("source", "all")
    exclude_watched = request.GET.get("exclude_watched", "1") in ["1", "true", "True"]

    my_subs = profiles.get_active_vod_subscriptions(request.session)
    supported_services = tmdb.get_supported_vod_services()
    for s in supported_services:
        s["is_subscribed"] = s["id"] in my_subs

    ctx.update({
        "genres": genres,
        "selected_genre": genre,
        "selected_mood": mood,
        "selected_runtime": runtime,
        "selected_source": source,
        "exclude_watched": exclude_watched,
        "moods": ROULETTE_MOODS,
        "runtimes": ROULETTE_RUNTIMES,
        "sources": ROULETTE_SOURCES,
        "my_subscriptions": my_subs,
        "supported_services": supported_services,
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
    exclude_watched = request.GET.get("exclude_watched", "1") in ["1", "true", "True"]

    watchlist_ids = profiles.get_active_watchlist(request.session)
    watched_ids = profiles.get_active_watched(request.session)
    my_subs = profiles.get_active_vod_subscriptions(request.session)
    ratings = profiles.get_active_ratings(request.session)

    exclude_ids = list(watched_ids) if exclude_watched else []

    candidate_ids = None
    if source == "watchlist":
        candidate_ids = list(watchlist_ids)
    elif source == "my_vod":
        # First gather candidates from watchlist matching subscriptions
        vod_cands = []
        for mid in watchlist_ids:
            t_info = tmdb.fetch_movie_details(mid, lang=lang)
            if t_info and any(p.get("id") in my_subs for p in t_info.get("vod_providers", [])):
                vod_cands.append(mid)
        # If pool is small, supplement from trending titles available on user's VOD
        if len(vod_cands) < 8:
            trending = services.get_trending_content(category="movies", lang=lang)
            for item in trending:
                mid = item.get("movie_id")
                if mid:
                    t_info = tmdb.fetch_movie_details(mid, lang=lang)
                    if t_info and any(p.get("id") in my_subs for p in t_info.get("vod_providers", [])):
                        vod_cands.append(mid)
        candidate_ids = list(set(vod_cands))

    winner, teaser_pool = services.get_random_movie_pool(
        genre=genre if genre != "All" else None,
        mood=mood if mood != "all" else None,
        max_runtime=int(max_runtime) if max_runtime.isdigit() and int(max_runtime) > 0 else None,
        min_rating=float(min_rating) if min_rating and float(min_rating) > 0 else None,
        candidate_ids=candidate_ids,
        exclude_ids=exclude_ids,
        pool_size=10,
    )

    if winner:
        prepare_movie_item(winner)
        tmdb_info = tmdb.fetch_movie_details(winner["movie_id"], lang=lang)
        if tmdb_info:
            for k, v in tmdb_info.items():
                if v:
                    winner[k] = v
        winner["is_watched"] = winner["movie_id"] in watched_ids
        winner["is_in_watchlist"] = winner["movie_id"] in watchlist_ids
        winner["user_rating"] = ratings.get(winner["movie_id"], 0)

        if not winner.get("justwatch_url") and winner.get("title"):
            winner["justwatch_url"] = tmdb.get_justwatch_url(winner["title"], lang=lang)
        if not winner.get("search_deeplinks") and winner.get("title"):
            winner["search_deeplinks"] = tmdb.get_search_deeplinks(winner["title"])

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
        prepare_movie_item(item)
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
        m = services.get_movie_by_id(mid_int)
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
                    "vod_providers": tmdb_info.get("vod_providers", []),
                    "justwatch_url": tmdb_info.get("justwatch_url"),
                }
            return mid, None

        with ThreadPoolExecutor(max_workers=min(len(missing_ids), 8)) as executor:
            for mid, m in executor.map(_fetch_external, missing_ids):
                if m:
                    resolved_movies[mid] = m

    # 3. Enrich local movies with TMDB VOD providers if not already present
    need_vod_enrichment = [mid for mid in parsed_ids if mid in resolved_movies and "vod_providers" not in resolved_movies[mid]]
    if need_vod_enrichment:
        def _fetch_vod(mid: int):
            t_info = tmdb.fetch_movie_details(mid, lang=lang)
            return mid, (t_info.get("vod_providers", []) if t_info else []), (t_info.get("justwatch_url") if t_info else None)

        with ThreadPoolExecutor(max_workers=min(len(need_vod_enrichment), 8)) as executor:
            for mid, vod_list, jw_url in executor.map(_fetch_vod, need_vod_enrichment):
                if mid in resolved_movies:
                    resolved_movies[mid]["vod_providers"] = vod_list
                    resolved_movies[mid]["justwatch_url"] = jw_url

    # 4. Assemble movies in original order
    all_movies = []
    for mid_int in parsed_ids:
        m = resolved_movies.get(mid_int)
        if m:
            prepare_movie_item(m)
            m["user_rating"] = ratings.get(m["movie_id"], 0)
            m["is_watched"] = mid_int in watched_ids
            m["is_in_watchlist"] = mid_int in watchlist_ids
            all_movies.append(m)

    # 5. Calculate counts per service
    my_vod_count = sum(
        1 for m in all_movies
        if any(p.get("id") in my_subscriptions for p in m.get("vod_providers", []))
    )

    for s in supported_services:
        s["movie_count"] = sum(
            1 for m in all_movies
            if any(p.get("id") == s["id"] for p in m.get("vod_providers", []))
        )
        s["is_subscribed"] = s["id"] in my_subscriptions

    # 6. Apply VOD filter
    if vod_filter == "my_vod":
        filtered_movies = [
            m for m in all_movies
            if any(p.get("id") in my_subscriptions for p in m.get("vod_providers", []))
        ]
    elif vod_filter.isdigit():
        target_provider = int(vod_filter)
        filtered_movies = [
            m for m in all_movies
            if any(p.get("id") == target_provider for p in m.get("vod_providers", []))
        ]
    else:
        filtered_movies = all_movies

    return {
        "movies": filtered_movies,
        "all_movies_count": len(all_movies),
        "tab": tab,
        "vod_filter": vod_filter,
        "my_subscriptions": my_subscriptions,
        "my_subscriptions_count": len(my_subscriptions),
        "supported_services": supported_services,
        "my_vod_count": my_vod_count,
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
    ctx.update({
        "supported_services": services_list,
        "my_subscriptions": my_subs,
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
        ctx = get_base_context(request)
        w_data = get_watchlist_data(request)
        ctx.update(w_data)
        response = render(request, "movies/partials/watchlist_grid.html", ctx)
        response["HX-Trigger"] = json.dumps({
            "showToast": {"title": "Zaktualizowano Twoje serwisy VOD", "type": "success"},
            "closeVodModal": True
        })
        return response

    return redirect("watchlist")


@require_POST
def toggle_watchlist(request, movie_id):
    added, count = profiles.toggle_watchlist_item(request.session, movie_id)
    request.session.modified = True
    lang = i18n.get_lang(request.session)
    msg = "Dodano do Twojej biblioteki" if added else "Usunięto z biblioteki"
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
    toast_msg = "Oznaczono jako obejrzane" if marked else "Usunięto z obejrzanych"
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
    msg = f"Zapisano ocenę {stars}/5 ★" if stars > 0 else "Usunięto ocenę"
    response = JsonResponse({"status": "ok", "movie_id": movie_id, "rating": stars})
    response["HX-Trigger"] = json.dumps({"showToast": {"title": msg, "type": "success" if stars > 0 else "info"}})
    return response


def discover(request):
    ctx = get_base_context(request)
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
        per_page=per_page
    )

    ratings = profiles.get_active_ratings(request.session)
    for item in filtered["items"]:
        prepare_movie_item(item)
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
        prepare_movie_item(rec)

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
        per_page=6
    )

    results = filtered["items"]
    for item in results:
        prepare_movie_item(item)

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


def export_profile(request):
    """Export current profiles and watchlists as downloadable JSON."""
    data = profiles.export_profiles_data(request.session)
    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type="application/json; charset=utf-8"
    )
    response["Content-Disposition"] = 'attachment; filename="watchwise_profiles_backup.json"'
    return response


@require_POST
def import_profile(request):
    """Import profiles from uploaded JSON file."""
    uploaded_file = request.FILES.get("profile_file")
    if uploaded_file:
        try:
            content = uploaded_file.read().decode("utf-8")
            data = json.loads(content)
            profiles.import_profiles_data(request.session, data)
        except Exception:
            pass
    return redirect(request.META.get("HTTP_REFERER", "/"))
