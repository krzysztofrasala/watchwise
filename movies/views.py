from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from . import services, tmdb

def prepare_movie_item(item: dict) -> dict:
    item["poster_url"] = tmdb.get_poster_url(item.get("poster_path"))
    item["backdrop_url"] = tmdb.get_backdrop_url(item.get("backdrop_path"))
    try:
        item["vote_average"] = round(float(item.get("vote_average") or 0.0), 1)
    except (ValueError, TypeError):
        item["vote_average"] = 0.0
    return item

def index(request):
    genres = services.get_all_genres()
    filtered = services.filter_movies(genre="All", sort_by="vote_desc", per_page=24)
    
    for item in filtered["items"]:
        prepare_movie_item(item)

    hero_movie = None
    if filtered["items"]:
        for candidate in filtered["items"]:
            if candidate.get("poster_path") and candidate.get("overview") and candidate.get("vote_average", 0) > 0:
                hero_movie = candidate
                break
        if not hero_movie:
            hero_movie = filtered["items"][0]

    if hero_movie:
        tmdb_info = tmdb.fetch_movie_details(hero_movie["movie_id"])
        if tmdb_info:
            for k, v in tmdb_info.items():
                if v:
                    hero_movie[k] = v

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
        prepare_movie_item(item)

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
        prepare_movie_item(item)

    context = {
        "query": query,
        "results": results,
    }
    return render(request, "movies/partials/search_results.html", context)


def movie_modal_partial(request, movie_id):
    movie = services.get_movie_by_id(movie_id)
    if not movie:
        return HttpResponse("Film nie został znaleziony.", status=404)

    prepare_movie_item(movie)
    tmdb_info = tmdb.fetch_movie_details(movie_id)
    if tmdb_info:
        for k, v in tmdb_info.items():
            if v:
                movie[k] = v

    recommendations = services.get_recommendations(movie_id, top_n=8)
    for rec in recommendations:
        prepare_movie_item(rec)

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
            prepare_movie_item(selected_movie)
            tmdb_info = tmdb.fetch_movie_details(selected_movie["movie_id"])
            if tmdb_info:
                for k, v in tmdb_info.items():
                    if v:
                        selected_movie[k] = v

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
            prepare_movie_item(m)
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
