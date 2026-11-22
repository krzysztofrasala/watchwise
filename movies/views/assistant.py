"""AI assistant: natural-language movie search chat."""

import itertools
import re
from concurrent.futures import ThreadPoolExecutor

from django.shortcuts import render
from django.http import HttpResponse

from .. import services, tmdb, recommender, nl_query
from .common import get_base_context, prepare_movie_item, rate_limited, warm_localized


def assistant(request):
    ctx = get_base_context(request)
    return render(request, "movies/assistant.html", ctx)


ASSISTANT_MAX_MESSAGE_LEN = 300


ASSISTANT_RATE_LIMIT = 20          # requests ...


ASSISTANT_RATE_WINDOW = 60 * 60    # ... per hour per client


_ASSISTANT_FILLER = re.compile(
    r"\b(szukam|chce|chcialbym|chcialabym|poleć|polec|pokaz|pokaż|znajdz|znajdź|film[a-z]*|serial[a-z]*|z udzialem|z udziałem|"
    r"z|ze|w ktorym|w którym|gra|grajacy|grający|aktor[a-z]*|aktorem|reżyser[a-z]*|rezyser[a-z]*|"
    r"i'm|im|looking|for|want|find|show|me|a|an|the|movie[s]?|film[s]?|with|starring|featuring|by|directed|"
    r"suche|sucht|einen|ein|mit|von|busco|quiero|una|un|pelicula|película|cherche|je|avec|un|une|"
    r"cerco|voglio|con|di)\b",
    re.IGNORECASE,
)


def _assistant_subject(message: str) -> str:
    """Strip filler words so 'szukam filmu z nicolas cage' becomes 'nicolas cage'."""
    cleaned = _ASSISTANT_FILLER.sub(" ", message)
    cleaned = re.sub(r"[^\w\s'\-\.]", " ", cleaned, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip() or message.strip()


def _search_title_variants(title: str, lang: str, movies_only: bool = True) -> list[dict]:
    """Search a title, retrying with trimmed endings ('Incepcji' -> 'Incepcj') to survive Polish inflection."""
    candidates = [title]
    last = title.split()[-1] if title.split() else ""
    if len(last) > 4:
        head = title[: len(title) - len(last)]
        candidates += [head + last[:-1], head + last[:-2]]
    with ThreadPoolExecutor(max_workers=3) as pool:
        batches = list(pool.map(lambda t: tmdb.search_tmdb_multi(t, lang=lang, limit=6), candidates))
    for found in batches:
        if movies_only:
            found = [m for m in found if not m.get("is_tv")]
        if found:
            return found
    return []


def assistant_chat_partial(request):
    ctx = get_base_context(request)
    lang = ctx["current_lang"]
    user_message = request.POST.get("message", "").strip() or request.GET.get("message", "").strip()
    if not user_message:
        return HttpResponse("", status=400)
    user_message = user_message[:ASSISTANT_MAX_MESSAGE_LEN]
    if rate_limited(request, "assistant", ASSISTANT_RATE_LIMIT, ASSISTANT_RATE_WINDOW):
        return HttpResponse("Too many requests. Please try again later.", status=429)

    parsed = nl_query.parse_natural_query(user_message)

    person_name = None
    similar_to = None
    results: list = []

    def _filter_local():
        return services.filter_movies(
            genre=parsed["genre"], year_min=parsed["year_min"], year_max=parsed["year_max"],
            vote_min=parsed["vote_min"], language=parsed["language"], sort_by=parsed["sort_by"],
            per_page=6, lang=lang,
        )["items"]

    # 1) "similar to X": resolve X via TMDB, then use the local similarity engine (TMDB as fallback)
    similar_title = nl_query.extract_similar_title(user_message)
    if similar_title:
        base = _search_title_variants(similar_title, lang)
        if base:
            similar_to = base[0]["title"]
            results = recommender.recommend_movie(base[0]["movie_id"], top_n=6)
            if not results:
                results = tmdb.fetch_similar_movies(base[0]["movie_id"], lang=lang, limit=6)

    # 2) person (actor/director) possibly combined with genre / year / rating filters
    if not results and not similar_to:
        leftover = _assistant_subject(nl_query.strip_filter_terms(user_message))
        words = leftover.split()
        if 1 <= len(words) <= 3 and len(leftover) >= 3:
            sort_by = parsed["sort_by"] if parsed["sort_by"] in ("year_desc", "year_asc", "vote_asc") else "popularity"
            person_kwargs = dict(
                lang=lang, limit=6,
                genre=parsed["genre"], year_min=parsed["year_min"], year_max=parsed["year_max"],
                vote_min=parsed["vote_min"], language=parsed["language"], sort_by=sort_by,
            )
            person_name, results = tmdb.search_person_movies(leftover, **person_kwargs)
            if person_name is None:
                # Polish inflection: "tomem hanksem" -> "tom hanks", "brucem willisem" -> "bruce willis"
                def _variants(word: str) -> list[str]:
                    out = [word]
                    for suffix, keep in (("iem", 0), ("em", 1), ("em", 0), ("owi", 0), ("a", 0)):
                        if len(word) > 4 and word.endswith(suffix):
                            out.append(word[:len(word) - len(suffix) + keep])
                    return list(dict.fromkeys(out))

                combos = [" ".join(c) for c in itertools.islice(
                    itertools.product(*[_variants(w) for w in words]), 1, 9)]
                with ThreadPoolExecutor(max_workers=4) as pool:
                    attempts = list(pool.map(lambda name: tmdb.search_person_movies(name, **person_kwargs), combos))
                for cand_name, cand_results in attempts:
                    if cand_name is not None:
                        person_name, results = cand_name, cand_results
                        break

    # 3) plain filters (genre / year / rating ...) on the local dataset, else a title search
    if not results and person_name is None and not similar_to:
        if parsed.get("understood", True):
            results = _filter_local()
        else:
            results = tmdb.search_tmdb_multi(_assistant_subject(user_message), lang=lang, limit=6)
            if not results:
                results = _search_title_variants(_assistant_subject(user_message), lang, movies_only=False)[:6]

    not_found = not results

    warm_localized(results, lang)
    for item in results:
        prepare_movie_item(item, lang=lang)

    ctx.update({
        "user_message": user_message,
        "parsed": parsed,
        "movies": results,
        "person_name": person_name,
        "similar_to": similar_to,
        "not_found": not_found,
    })
    return render(request, "movies/partials/assistant_response.html", ctx)
