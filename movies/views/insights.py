"""Taste DNA and Matchmaker (comparing two profiles)."""

import json

from django.core.cache import cache
from django.shortcuts import render

from .. import services, recommender, taste, profiles, i18n
from .common import get_base_context, prepare_movie_item, warm_localized


def taste_dna(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    ratings = profiles.get_active_ratings(request.session)
    watchlist_ids = profiles.get_active_watchlist(request.session)
    watched_ids = profiles.get_active_watched(request.session)
    active_profile = profiles.get_active_profile_name(request.session)

    import hashlib
    raw_sig = f"{active_profile}:{sorted(ratings.items())}:{sorted(watchlist_ids)}:{sorted(watched_ids)}:{lang}"
    cache_key = f"taste_dna_{hashlib.md5(raw_sig.encode()).hexdigest()}"
    taste_data = cache.get(cache_key)

    if taste_data is None:
        taste_data = taste.compute_taste_profile(ratings, watchlist_ids, lang=lang, watched_ids=watched_ids)
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

    p1_data = all_profiles_dict.get(p1, {"ratings": {}, "watchlist": [], "watched": []})
    p2_data = all_profiles_dict.get(p2, {"ratings": {}, "watchlist": [], "watched": []})

    mode_param = request.GET.get("mode", "").strip()
    use_profile_mode = (mode_param == "profiles") or (("p1" in request.GET and "p2" in request.GET) and not preset and "vibe1" not in request.GET)
    compare_mode = "profiles" if use_profile_mode else "vibes"
    recommendations = []
    if use_profile_mode:
        recommendations = recommender.recommend_for_group(
            user1_ratings=p1_data.get("ratings", {}),
            user1_watchlist=p1_data.get("watchlist", []),
            user2_ratings=p2_data.get("ratings", {}),
            user2_watchlist=p2_data.get("watchlist", []),
            top_n=12,
            lang=lang,
            user1_watched=p1_data.get("watched", []),
            user2_watched=p2_data.get("watched", []),
        )

    if not recommendations:
        recommendations = recommender.recommend_for_vibes(vibe1, vibe2, top_n=12, lang=lang)

    if use_profile_mode and recommendations:
        top_scores = [int(r.get("match_score", 80)) for r in recommendations[:5]]
        harmony_score = min(99, max(65, int(round(sum(top_scores) / len(top_scores)))))
    else:
        harmony_score = recommender.get_harmony_score(vibe1, vibe2)

    warm_localized(recommendations, lang)
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
        "compare_mode": compare_mode,
        "harmony_score": harmony_score,
        "p1": p1,
        "p2": p2,
        "p1_display": p1_display,
        "p2_display": p2_display,
        "recommendations": recommendations,
    })
    return render(request, "movies/compare.html", ctx)
