import json
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from . import services, tmdb, recommender, taste, nl_query, profiles, i18n


def prepare_movie_item(item: dict) -> dict:
    item["poster_url"] = tmdb.get_poster_url(item.get("poster_path") or item.get("poster_url"))
    item["backdrop_url"] = tmdb.get_backdrop_url(item.get("backdrop_path") or item.get("backdrop_url"))
    try:
        item["vote_average"] = round(float(item.get("vote_average") or 0.0), 1)
    except (ValueError, TypeError):
        item["vote_average"] = 0.0
    return item


def get_base_context(request) -> dict:
    lang = i18n.get_lang(request.session)
    raw_active = profiles.get_active_profile_name(request.session)
    raw_profiles = list(profiles.get_profile_data(request.session).keys())
    watchlist_ids = profiles.get_active_watchlist(request.session)

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
    }


def index(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]

    watchlist_ids = profiles.get_active_watchlist(request.session)
    ratings = profiles.get_active_ratings(request.session)

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

    recommended_movies = recommender.recommend_for_user(ratings, watchlist_ids, top_n=10, lang=lang)
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

    prepare_movie_item(movie)
    tmdb_info = tmdb.fetch_movie_details(movie_id, lang=lang)
    if tmdb_info:
        for k, v in tmdb_info.items():
            if v is not None:
                movie[k] = v

    if not movie.get("title"):
        return HttpResponse("Film lub serial nie został znaleziony.", status=404)

    recommendations = services.get_recommendations(movie_id, top_n=8)
    for rec in recommendations:
        prepare_movie_item(rec)

    watchlist_ids = profiles.get_active_watchlist(request.session)
    ratings = profiles.get_active_ratings(request.session)

    is_in_watchlist = int(movie_id) in watchlist_ids
    user_rating = ratings.get(int(movie_id), 0)

    context = {
        "movie": movie,
        "recommendations": recommendations,
        "is_in_watchlist": is_in_watchlist,
        "user_rating": user_rating,
        "current_lang": lang,
    }
    return render(request, "movies/partials/movie_modal.html", context)


def roulette(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    genre = request.GET.get("genre", "All")
    genres = services.get_all_genres()
    selected_movie = None

    if request.GET.get("spin") == "true":
        selected_movie = services.get_random_movie(genre=genre)
        if selected_movie:
            prepare_movie_item(selected_movie)
            tmdb_info = tmdb.fetch_movie_details(selected_movie["movie_id"], lang=lang)
            if tmdb_info:
                for k, v in tmdb_info.items():
                    if v:
                        selected_movie[k] = v

    ctx.update({
        "genres": genres,
        "selected_genre": genre,
        "movie": selected_movie,
    })
    return render(request, "movies/roulette.html", ctx)


def watchlist(request):
    ctx = get_base_context(request)
    watchlist_ids = profiles.get_active_watchlist(request.session)
    ratings = profiles.get_active_ratings(request.session)

    movies = []
    for mid in watchlist_ids:
        m = services.get_movie_by_id(mid)
        if m:
            prepare_movie_item(m)
            m["user_rating"] = ratings.get(m["movie_id"], 0)
            movies.append(m)

    ctx.update({
        "movies": movies,
    })
    return render(request, "movies/watchlist.html", ctx)


@require_POST
def toggle_watchlist(request, movie_id):
    added, count = profiles.toggle_watchlist_item(request.session, movie_id)
    return JsonResponse({"added": added, "count": count})


@require_POST
def rate_movie(request, movie_id):
    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
        stars = int(body.get("stars", 0))
    except Exception:
        stars = int(request.POST.get("stars", 0))

    ratings = profiles.set_movie_rating(request.session, movie_id, stars)
    return JsonResponse({"status": "ok", "movie_id": movie_id, "rating": stars})


def discover(request):
    ctx = get_base_context(request)
    genre = request.GET.get("genre", "All")
    language = request.GET.get("language")
    vote_min = request.GET.get("vote_min")
    year_min = request.GET.get("year_min")
    year_max = request.GET.get("year_max")
    sort_by = request.GET.get("sort_by", "vote_desc")

    filtered = services.filter_movies(
        genre=genre,
        year_min=year_min,
        year_max=year_max,
        vote_min=vote_min,
        language=language,
        sort_by=sort_by,
        page=int(request.GET.get("page", 1)),
        per_page=24
    )

    ratings = profiles.get_active_ratings(request.session)
    for item in filtered["items"]:
        prepare_movie_item(item)
        item["user_rating"] = ratings.get(item["movie_id"], 0)

    ctx.update({
        "genres": services.get_all_genres(),
        "movies": filtered["items"],
        "total_count": filtered["total_count"],
        "selected_genre": genre,
        "selected_language": language,
    })
    return render(request, "movies/discover.html", ctx)


def taste_dna(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    ratings = profiles.get_active_ratings(request.session)
    watchlist_ids = profiles.get_active_watchlist(request.session)

    taste_data = taste.compute_taste_profile(ratings, watchlist_ids, lang=lang)

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

    for rec in recommendations:
        prepare_movie_item(rec)

    default_trans = i18n.t("default_profile", lang)
    p1_display = default_trans if p1 == "Główny" else p1
    p2_display = default_trans if p2 == "Główny" else p2

    ctx.update({
        "profile_names": profile_names,
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
