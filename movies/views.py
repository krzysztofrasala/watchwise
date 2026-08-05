from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from . import services, tmdb

def index(request):
    genres = services.get_all_genres()
    filtered = services.filter_movies(genre="All", sort_by="vote_desc", per_page=24)
    hero_movie = services.get_random_movie()

    if hero_movie:
        hero_movie["poster_url"] = tmdb.get_poster_url(hero_movie.get("poster_path"))
        tmdb_info = tmdb.fetch_movie_details(hero_movie["movie_id"])
        if tmdb_info:
            hero_movie.update(tmdb_info)

    for item in filtered["items"]:
        item["poster_url"] = tmdb.get_poster_url(item.get("poster_path"))

    watchlist = request.session.get("watchlist", [])

    context = {
        "genres": genres,
        "movies": filtered["items"],
        "total_count": filtered["total_count"],
        "page": filtered["page"],
        "total_pages": filtered["total_pages"],
        "hero_movie": hero_movie,
        "watchlist_count": len(watchlist),
    }
    return render(request, "movies/index.html", context)


def movie_grid_partial(request):
    genre = request.GET.get("genre", "All")
    year_min = request.GET.get("year_min")
    year_max = request.GET.get("year_max")
    vote_min = request.GET.get("vote_min")
    sort_by = request.GET.get("sort_by", "vote_desc")
    page = int(request.GET.get("page", 1))

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
        item["poster_url"] = tmdb.get_poster_url(item.get("poster_path"))

    context = {
        "movies": filtered["items"],
        "total_count": filtered["total_count"],
        "page": filtered["page"],
        "total_pages": filtered["total_pages"],
        "current_genre": genre,
        "sort_by": sort_by,
    }
    return render(request, "movies/partials/movie_grid.html", context)


def search_live_partial(request):
    query = request.GET.get("q", "")
    results = services.search_movies(query, limit=8)
    for item in results:
        item["poster_url"] = tmdb.get_poster_url(item.get("poster_path"))

    context = {
        "query": query,
        "results": results,
    }
    return render(request, "movies/partials/search_results.html", context)


def movie_modal_partial(request, movie_id):
    movie = services.get_movie_by_id(movie_id)
    if not movie:
        return HttpResponse("Film nie został znaleziony.", status=404)

    movie["poster_url"] = tmdb.get_poster_url(movie.get("poster_path"))
    tmdb_info = tmdb.fetch_movie_details(movie_id)
    if tmdb_info:
        movie.update(tmdb_info)

    recommendations = services.get_recommendations(movie_id, top_n=8)
    for rec in recommendations:
        rec["poster_url"] = tmdb.get_poster_url(rec.get("poster_path"))

    watchlist = request.session.get("watchlist", [])
    is_in_watchlist = int(movie_id) in watchlist

    context = {
        "movie": movie,
        "recommendations": recommendations,
        "is_in_watchlist": is_in_watchlist,
    }
    return render(request, "movies/partials/movie_modal.html", context)


def roulette(request):
    genre = request.GET.get("genre", "All")
    genres = services.get_all_genres()
    selected_movie = None

    if request.GET.get("spin") == "true":
        selected_movie = services.get_random_movie(genre=genre)
        if selected_movie:
            selected_movie["poster_url"] = tmdb.get_poster_url(selected_movie.get("poster_path"))
            tmdb_info = tmdb.fetch_movie_details(selected_movie["movie_id"])
            if tmdb_info:
                selected_movie.update(tmdb_info)

    context = {
        "genres": genres,
        "selected_genre": genre,
        "movie": selected_movie,
    }
    return render(request, "movies/roulette.html", context)


def watchlist(request):
    watchlist_ids = request.session.get("watchlist", [])
    movies = []
    for mid in watchlist_ids:
        m = services.get_movie_by_id(mid)
        if m:
            m["poster_url"] = tmdb.get_poster_url(m.get("poster_path"))
            movies.append(m)

    context = {
        "movies": movies,
        "watchlist_count": len(movies),
    }
    return render(request, "movies/watchlist.html", context)


@require_POST
def toggle_watchlist(request, movie_id):
    watchlist_ids = request.session.get("watchlist", [])
    mid = int(movie_id)

    if mid in watchlist_ids:
        watchlist_ids.remove(mid)
        added = False
    else:
        watchlist_ids.append(mid)
        added = True

    request.session["watchlist"] = watchlist_ids
    return JsonResponse({"added": added, "count": len(watchlist_ids)})
