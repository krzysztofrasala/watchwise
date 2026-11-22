"""Taste-DNA profiling: genre/decade affinity scores and viewer personas for Cinescope Django."""

from __future__ import annotations
from typing import Any
import pandas as pd
from . import services, tmdb

CRITIC_STYLES = {
    "PL": {
        "harsh": ("🧐", "Surowy Krytyk", "Oceniasz filmy ostrzej niż średnia światowa TMDB — u Ciebie na 5★ trzeba naprawdę zasłużyć."),
        "enthusiast": ("🤩", "Entuzjasta Kina", "Czerpiesz czystą radość z seansów i oceniasz filmy wyżej niż globalna średnia TMDB."),
        "balanced": ("⚖️", "Zbalansowany Kinoman", "Twoje oceny są w idealnej harmonii ze światowymi ocenami krytyków i widzów."),
        "unrated": ("🍿", "Odkrywca", "Oceń kilka filmów gwiazdkami, aby odkryć swój styl oceniania na tle społeczności."),
    },
    "EN": {
        "harsh": ("🧐", "Harsh Critic", "You rate movies more strictly than the global TMDB average — 5★ must be truly earned."),
        "enthusiast": ("🤩", "Cinema Enthusiast", "You find joy in cinema and rate movies more generously than the global average."),
        "balanced": ("⚖️", "Balanced Cinephile", "Your ratings align closely with global audience and critic consensus."),
        "unrated": ("🍿", "Explorer", "Rate a few movies with stars to unlock your critic style comparison."),
    },
    "DE": {
        "harsh": ("🧐", "Strenger Kritiker", "Du bewertest Filme strenger als der weltweite TMDB-Durchschnitt."),
        "enthusiast": ("🤩", "Kino-Enthusiast", "Du bewertest Filme großzügiger als der weltweite Durchschnitt."),
        "balanced": ("⚖️", "Ausgewogener Cineast", "Deine Bewertungen stimmen eng mit dem weltweiten Publikum überein."),
        "unrated": ("🍿", "Entdecker", "Bewerte einige Filme, um deinen Kritiker-Stil freizuschalten."),
    },
    "ES": {
        "harsh": ("🧐", "Crítico Exigente", "Calificas las películas con más rigor que el promedio mundial de TMDB."),
        "enthusiast": ("🤩", "Entusiasta del Cine", "Disfrutas cada película y calificas con más generosidad que el promedio."),
        "balanced": ("⚖️", "Cinéfilo Equilibrado", "Tus calificaciones coinciden con el consenso mundial."),
        "unrated": ("🍿", "Explorador", "Califica algunas películas para descubrir tu estilo de crítico."),
    },
    "FR": {
        "harsh": ("🧐", "Critique Exigeant", "Vous notez les films plus sévèrement que la moyenne mondiale TMDB."),
        "enthusiast": ("🤩", "Cinéphile Enthousiaste", "Vous notez les films plus généreusement que la moyenne mondiale."),
        "balanced": ("⚖️", "Cinéphile Équilibré", "Vos notes sont en harmonie avec le consensus mondial."),
        "unrated": ("🍿", "Explorateur", "Notez quelques films pour découvrir votre profil de critique."),
    },
    "IT": {
        "harsh": ("🧐", "Critico Severo", "Valuti i film in modo più rigoroso rispetto alla media globale TMDB."),
        "enthusiast": ("🤩", "Entusiasta del Cinema", "Valuti i film con più generosità rispetto alla media globale."),
        "balanced": ("⚖️", "Cinefilo Equilibrato", "I tuoi voti sono in perfetto equilibrio con il pubblico globale."),
        "unrated": ("🍿", "Esploratore", "Valuta alcuni film per scoprire il tuo stile di critica."),
    },
    "UK": {
        "harsh": ("🧐", "Суворий критик", "Ви оцінюєте фільми суворіше за світове середнє TMDB — п'ять зірок у вас треба заслужити."),
        "enthusiast": ("🤩", "Кіноентузіаст", "Ви щиро насолоджуєтесь переглядом і оцінюєте фільми вище за світове середнє TMDB."),
        "balanced": ("⚖️", "Врівноважений кіноман", "Ваші оцінки в ідеальній гармонії зі світовими оцінками критиків і глядачів."),
        "unrated": ("🍿", "Дослідник", "Оцініть кілька фільмів зірками, щоб відкрити свій стиль оцінювання."),
    },
}

PERSONAS = {
    "PL": [
        (["Horror", "Thriller"], ("🌑", "Mroczny Umysł", "Uwielbiasz psychologiczną presję, mroczne klimaty i niespodziewane zwroty akcji.")),
        (["Action", "Thriller"], ("🎯", "Łowca Adrenaliny", "Nic nie rozgrzewa Cię tak bardzo jak widowiskowe kina akcji i pościgi.")),
        (["Drama", "Romance"], ("🌹", "Romantyk z Wyboru", "Wierzysz, że najlepsze historie to te o prawdziwych i głębokich uczuciach.")),
        (["Science Fiction", "Action"], ("🚀", "Podróżnik Przyszłości", "Chętnie odkrywasz futurystyczne wizje świata i epickie światy sci-fi.")),
        (["Crime", "Drama"], ("🕵️", "Poszukiwacz Prawdy", "Zafascynowany mrocznymi sekretami, ludzkimi wyborami i grami półświatka.")),
        (["Animation", "Family"], ("🎠", "Wieczne Dziecko", "Cenisz magię, wyobraźnię i wspaniałe historie familijne bez względu na wiek.")),
        (["Comedy"], ("😂", "Koneser Humoru", "Życie jest zbyt krótkie, by brać je zbyt serio. Szukasz lekkiego kina i rozrywki.")),
        (["Science Fiction"], ("🛸", "Wizjoner", "Fascynuje Cię to, co może nadejść i tajemnice kosmosu.")),
        (["Horror"], ("👻", "Łowca Strachu", "Dla Ciebie strach w kinie to czysta ekscytacja i rozrywka.")),
        (["Action", "Adventure"], ("💥", "Fan Kina Epickiego", "Szybciej, głośniej i z większym rozmahem – widowisko ponad wszystko.")),
        (["History", "Drama"], ("📜", "Podróżnik w Czasie", "Odkrywasz teraźniejszość poprzez dramaty historyczne i minione epoki.")),
        (["Adventure", "Fantasy"], ("⚔️", "Marzyciel", "Twój żywioł to epickie wyprawy, magia i niezwykłe krainy.")),
        (["Drama"], ("🎭", "Głęboki Myśliciel", "Każdy film to dla Ciebie okno na złożoność ludzkiej natury.")),
    ],
    "EN": [
        (["Horror", "Thriller"], ("🌑", "The Dark Mind", "You thrive in psychological tension and shadowy narratives.")),
        (["Action", "Thriller"], ("🎯", "The Adrenaline Hunter", "Nothing gets your blood pumping like high-octane cinema.")),
        (["Drama", "Romance"], ("🌹", "The Hopeless Romantic", "You believe every great story deserves love at its center.")),
        (["Science Fiction", "Action"], ("🚀", "The Future Voyager", "You boldly go where no film has gone before.")),
        (["Crime", "Drama"], ("🕵️", "The Truth Seeker", "Obsessed with the human cost of decisions — right or wrong.")),
        (["Animation", "Family"], ("🎠", "The Eternal Child", "Young at heart, appreciating magic and imagination.")),
        (["Comedy"], ("😂", "The Laughter Seeker", "Life's too short to take too seriously.")),
        (["Science Fiction"], ("🛸", "The Visionary", "Fascinated by what could be, not just what is.")),
        (["Horror"], ("👻", "The Thrill Chaser", "Fear is just excitement in disguise.")),
        (["Action", "Adventure"], ("💥", "The Epic Action Fan", "Bigger, louder, faster — bring it on.")),
        (["History", "Drama"], ("📜", "The Time Traveler", "Finds the present by exploring the past.")),
        (["Adventure", "Fantasy"], ("⚔️", "The Epic Dreamer", "Born for grand journeys and impossible worlds.")),
        (["Drama"], ("🎭", "The Deep Thinker", "Every film is a window into the human condition.")),
    ],
    "DE": [
        (["Horror", "Thriller"], ("🌑", "Der Düstere Geist", "Du liebst psychologische Spannung und düstere Wendungen.")),
        (["Action", "Thriller"], ("🎯", "Der Adrenalin-Jäger", "Nichts geht über spektakuläre Action und Verfolgungsjagden.")),
        (["Drama", "Romance"], ("🌹", "Der Romantiker", "Großartige Geschichten brauchen wahre Gefühle.")),
        (["Science Fiction", "Action"], ("🚀", "Zukunftsreisender", "Erkunde futuristische Welten und Sci-Fi-Epen.")),
        (["Crime", "Drama"], ("🕵️", "Der Wahrheitssucher", "Fasziniert von dunklen Geheimnissen und menschlichen Schicksalen.")),
        (["Animation", "Family"], ("🎠", "Ewig Jung", "Magie und Fantasie für jedes Alter.")),
        (["Comedy"], ("😂", "Humor-Kenner", "Das Leben ist zu kurz für zu viel Ernst.")),
        (["Science Fiction"], ("🛸", "Der Visionär", "Fasziniert von den Geheimnissen des Universums.")),
        (["Horror"], ("👻", "Angst-Hunter", "Nervenkitzel und Gänsehaut sind deine Leidenschaft.")),
        (["Action", "Adventure"], ("💥", "Action-Gigant", "Spektakel, Tempo und Adrenalin pur.")),
        (["History", "Drama"], ("📜", "Zeitreisender", "Entdecke historische Dramen und vergangene Epochen.")),
        (["Adventure", "Fantasy"], ("⚔️", "Der Träumer", "Epos, Magie und unentdeckte Welten.")),
        (["Drama"], ("🎭", "Der Denker", "Jeder Film ist ein Fenster zur menschlichen Natur.")),
    ],
    "ES": [
        (["Horror", "Thriller"], ("🌑", "La Mente Oscura", "Te apasiona la tensión psicológica y los giros oscuros.")),
        (["Action", "Thriller"], ("🎯", "Cazador de Adrenalina", "Nada te emociona más que la acción espectacular.")),
        (["Drama", "Romance"], ("🌹", "El Romántico", "Las mejores historias son las del corazón.")),
        (["Science Fiction", "Action"], ("🚀", "Viajero del Futuro", "Explora mundos futuristas y épicas de ciencia ficción.")),
        (["Crime", "Drama"], ("🕵️", "Buscador de la Verdad", "Fascinado por los secretos oscuros y el drama humano.")),
        (["Animation", "Family"], ("🎠", "Eterno Niño", "Aprecias la magia y la fantasía a cualquier edad.")),
        (["Comedy"], ("😂", "Amante del Humor", "La vida es demasiado corta para no reír.")),
        (["Science Fiction"], ("🛸", "El Visionario", "Fascinado por lo que está por venir.")),
        (["Horror"], ("👻", "Buscador de Emociones", "El miedo en el cine es pura diversión.")),
        (["Action", "Adventure"], ("💥", "Fan del Cine Épico", "Espectáculo, velocidad y emoción sin límites.")),
        (["History", "Drama"], ("📜", "Viajero del Tiempo", "Descubre el presente a través del cine histórico.")),
        (["Adventure", "Fantasy"], ("⚔️", "El Soñador Épico", "Tu elemento son los grandes viajes y la magia.")),
        (["Drama"], ("🎭", "El Pensador Profundo", "Cada película es una ventana a la condición humana.")),
    ],
    "FR": [
        (["Horror", "Thriller"], ("🌑", "L'Esprit Sombre", "Vous aimez la tension psychologique et les intrigues sombres.")),
        (["Action", "Thriller"], ("🎯", "Le Chasseur d'Adrénaline", "Rien ne vaut l'action spectaculaire et les courses-poursuites.")),
        (["Drama", "Romance"], ("🌹", "Le Romantique", "Les plus belles histoires sont celles du cœur.")),
        (["Science Fiction", "Action"], ("🚀", "Voyageur du Futur", "Explorez des visions futuristes et des épopées sci-fi.")),
        (["Crime", "Drama"], ("🕵️", "Chercheur de Vérité", "Fasciné par les secrets sombres et la nature humaine.")),
        (["Animation", "Family"], ("🎠", "Enfant Éternel", "La magie et l'imagination n'ont pas d'âge.")),
        (["Comedy"], ("😂", "L'Amoureux du Rire", "La vie est trop courte pour être trop sérieuse.")),
        (["Science Fiction"], ("🛸", "Le Visionnaire", "Fasciné par les mystères du cosmos.")),
        (["Horror"], ("👻", "Amateur de Frissons", "La peur au cinéma est un pur plaisir.")),
        (["Action", "Adventure"], ("💥", "Fan de Grand Spectacle", "Plus grand, plus fort, plus vite.")),
        (["History", "Drama"], ("📜", "Voyageur du Temps", "Découvrez l'histoire à travers les grands drames.")),
        (["Adventure", "Fantasy"], ("⚔️", "Le Rêveur Épique", "Les grandes quêtes et la magie sont votre passion.")),
        (["Drama"], ("🎭", "Le Penseur", "Chaque film est un miroir de l'âme humaine.")),
    ],
    "IT": [
        (["Horror", "Thriller"], ("🌑", "La Mente Oscura", "Ami la tensione psicologica e i colpi di scena.")),
        (["Action", "Thriller"], ("🎯", "Cacciatore di Adrenalina", "Niente batte l'azione spettacolare e l'adrenalina.")),
        (["Drama", "Romance"], ("🌹", "Il Romantico", "Le storie migliori sono quelle dei grandi sentimenti.")),
        (["Science Fiction", "Action"], ("🚀", "Viaggiatore del Futuro", "Esplora mondi futuristici ed epiche sci-fi.")),
        (["Crime", "Drama"], ("🕵️", "Cercatore di Verità", "Affascinato dai segreti oscuri e dal dramma umano.")),
        (["Animation", "Family"], ("🎠", "Eterno Bambino", "Ami la magia e l'immaginazione a qualsiasi età.")),
        (["Comedy"], ("😂", "Amante dell'Umorismo", "La vita è troppo breve per prendersi troppo sul serio.")),
        (["Science Fiction"], ("🛸", "Il Visionario", "Affascinato dai misteri del cosmo.")),
        (["Horror"], ("👻", "Cacciatore di Brividi", "La paura al cinema è puro divertimento.")),
        (["Action", "Adventure"], ("💥", "Fan del Grande Spettacolo", "Spettacolo, velocità ed emozione pura.")),
        (["History", "Drama"], ("📜", "Viaggiatore nel Tempo", "Scopri la storia attraverso i drammi storici.")),
        (["Adventure", "Fantasy"], ("⚔️", "Il Sognatore Epico", "Il tuo elemento sono le grandi avventure e la magia.")),
        (["Drama"], ("🎭", "Il Pensatore", "Ogni film è una finestra sulla natura umana.")),
    ],
    "UK": [
        (["Horror", "Thriller"], ("🌑", "Темний розум", "Ви обожнюєте психологічну напругу та похмурі історії з несподіваними поворотами.")),
        (["Action", "Thriller"], ("🎯", "Мисливець за адреналіном", "Ніщо не розганяє вам кров так, як видовищний екшн і погоні.")),
        (["Drama", "Romance"], ("🌹", "Невиліковний романтик", "Ви вірите, що кожна велика історія має кохання в центрі.")),
        (["Science Fiction", "Action"], ("🚀", "Мандрівник у майбутнє", "Ви сміливо йдете туди, де ще не бував жоден фільм.")),
        (["Crime", "Drama"], ("🕵️", "Шукач правди", "Вас захоплюють темні таємниці та ціна людських рішень.")),
        (["Animation", "Family"], ("🎠", "Вічна дитина", "Ви молоді душею та цінуєте магію й уяву в будь-якому віці.")),
        (["Comedy"], ("😂", "Любитель сміху", "Життя надто коротке, щоб сприймати його занадто серйозно.")),
        (["Science Fiction"], ("🛸", "Візіонер", "Вас захоплює те, що могло б бути, а не лише те, що є.")),
        (["Horror"], ("👻", "Мисливець за дрижаками", "Страх у кіно — це чиста насолода.")),
        (["Action", "Adventure"], ("💥", "Фанат епічного кіно", "Більше, гучніше, швидше — видовище понад усе.")),
        (["History", "Drama"], ("📜", "Мандрівник у часі", "Ви пізнаєте сучасність через історичні драми та минулі епохи.")),
        (["Adventure", "Fantasy"], ("⚔️", "Мрійник", "Ваша стихія — епічні походи, магія та незвичайні світи.")),
        (["Drama"], ("🎭", "Глибокий мислитель", "Кожен фільм для вас — вікно у складність людської природи.")),
    ],
}

FALLBACK_PERSONA = {
    "PL": ("🎬", "Koneser Kina", "Prawdziwy kinoman o wszechstronnym i otwartym guście filmowym."),
    "EN": ("🎬", "The Movie Lover", "A true cinephile with eclectic and open taste."),
    "DE": ("🎬", "Der Filmkenner", "Ein wahrer Cineast mit vielseitigem Geschmack."),
    "ES": ("🎬", "El Cinefilo", "Un verdadero cinéfilo de gusto ecléctico y abierto."),
    "FR": ("🎬", "Le Cinéphile", "Un vrai passionné de cinéma au goût éclectique."),
    "IT": ("🎬", "Il Cinefilo", "Un vero appassionato di cinema con un gusto eclettico."),
    "UK": ("🎬", "Знавець кіно", "Справжній кіноман із різнобарвним і відкритим смаком."),
}


def compute_taste_profile(
    user_ratings: dict[int, int],
    watchlist_ids: list[int],
    lang: str = "PL",
    watched_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Calculate genre distribution, decade distribution, persona, and total stats."""
    genre_scores: dict[str, float] = {}
    decade_scores: dict[int, float] = {}

    id_to_movie = services.get_movie_dict()

    total_rated = len(user_ratings)
    total_watchlist = len(watchlist_ids)
    rated_mids = set()
    runtimes: list[int] = []
    tmdb_votes_for_rated: list[float] = []
    user_stars_list: list[int] = []
    top_rated_candidates: list[tuple[int, float, dict[str, Any]]] = []

    code = (lang or "PL").upper().strip()
    if code not in CRITIC_STYLES:
        code = "PL"

    # Process rated movies (only positive/neutral ratings >= 3 contribute to affinity)
    for mid, stars in user_ratings.items():
        mid = int(mid)
        stars_int = int(stars)
        rated_mids.add(mid)
        user_stars_list.append(stars_int)
        movie = id_to_movie.get(mid)
        if movie:
            v_avg = float(movie.get("vote_average", 0.0) or 0.0)
            if v_avg > 0:
                tmdb_votes_for_rated.append(v_avg)
            rt = int(movie.get("runtime", 0) or 0)
            if rt > 0:
                runtimes.append(rt)
            if stars_int >= 4:
                loc_movie = services.get_movie_by_id(mid, lang=lang) or movie
                top_rated_candidates.append((stars_int, v_avg, {
                    "movie_id": mid,
                    "title": loc_movie.get("title", movie.get("title", "")),
                    "year": movie.get("year") or "",
                    "poster_url": tmdb.get_poster_url(movie.get("poster_path")),
                    "vote_average": round(v_avg, 1),
                    "user_rating": stars_int,
                }))

        if stars_int < 3 or not movie:
            continue
        weight = float(stars_int) / 3.0  # rating weight

        genres = movie.get("genres_list", [])
        for g in genres:
            genre_scores[g] = genre_scores.get(g, 0.0) + weight

        year = movie.get("year", 0)
        if year and year > 1900:
            decade = (int(year) // 10) * 10
            decade_scores[decade] = decade_scores.get(decade, 0.0) + weight

    # Process watched movies not already rated (weight 0.6)
    watched_set = set()
    for mid in (watched_ids or []):
        mid = int(mid)
        watched_set.add(mid)
        if mid in rated_mids:
            continue
        movie = id_to_movie.get(mid)
        if not movie:
            continue
        rt = int(movie.get("runtime", 0) or 0)
        if rt > 0:
            runtimes.append(rt)
        weight = 0.6
        genres = movie.get("genres_list", [])
        for g in genres:
            genre_scores[g] = genre_scores.get(g, 0.0) + weight

        year = movie.get("year", 0)
        if year and year > 1900:
            decade = (int(year) // 10) * 10
            decade_scores[decade] = decade_scores.get(decade, 0.0) + weight

    # Process watchlist movies (weight 0.5)
    for mid in watchlist_ids:
        mid = int(mid)
        if mid in rated_mids:
            continue
        movie = id_to_movie.get(mid)
        if not movie:
            continue
        rt = int(movie.get("runtime", 0) or 0)
        if rt > 0:
            runtimes.append(rt)
        weight = 0.5
        genres = movie.get("genres_list", [])
        for g in genres:
            genre_scores[g] = genre_scores.get(g, 0.0) + weight

        year = movie.get("year", 0)
        if year and year > 1900:
            decade = (int(year) // 10) * 10
            decade_scores[decade] = decade_scores.get(decade, 0.0) + weight

    # Determine top persona
    persona = assign_persona(genre_scores, lang=lang)

    # Format genre chart data (top 8)
    sorted_genres = sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)[:8]
    genre_labels = [g[0] for g in sorted_genres]
    genre_values = [round(g[1], 1) for g in sorted_genres]

    # Format decade chart data
    sorted_decades = sorted(decade_scores.items(), key=lambda x: x[0])
    decade_labels = [f"{d[0]}s" for d in sorted_decades]
    decade_values = [round(d[1], 1) for d in sorted_decades]

    avg_user_rating = round(sum(user_stars_list) / len(user_stars_list), 2) if user_stars_list else 0.0
    avg_tmdb_rating = round(sum(tmdb_votes_for_rated) / len(tmdb_votes_for_rated), 1) if tmdb_votes_for_rated else 0.0
    avg_runtime = int(round(sum(runtimes) / len(runtimes))) if runtimes else 0

    styles = CRITIC_STYLES[code]
    if not user_stars_list:
        critic_icon, critic_title, critic_desc = styles["unrated"]
    else:
        diff = (avg_user_rating * 2.0) - (avg_tmdb_rating if avg_tmdb_rating > 0 else 7.0)
        if diff <= -0.6:
            critic_icon, critic_title, critic_desc = styles["harsh"]
        elif diff >= 0.6:
            critic_icon, critic_title, critic_desc = styles["enthusiast"]
        else:
            critic_icon, critic_title, critic_desc = styles["balanced"]

    top_rated_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top_rated_movies = [x[2] for x in top_rated_candidates[:6]]

    return {
        "persona_icon": persona[0],
        "persona_title": persona[1],
        "persona_desc": persona[2],
        "total_rated": total_rated,
        "total_watchlist": total_watchlist,
        "total_watched": len(watched_set.union(rated_mids)),
        "avg_user_rating": avg_user_rating,
        "avg_tmdb_rating": avg_tmdb_rating,
        "avg_runtime": avg_runtime,
        "critic_icon": critic_icon,
        "critic_title": critic_title,
        "critic_desc": critic_desc,
        "top_rated_movies": top_rated_movies,
        "genre_labels": genre_labels,
        "genre_values": genre_values,
        "decade_labels": decade_labels,
        "decade_values": decade_values,
    }


def assign_persona(genre_scores: dict[str, float], lang: str = "PL") -> tuple[str, str, str]:
    """Match the user's top genres to a named persona in active language."""
    code = lang.upper().strip()
    if code not in PERSONAS:
        code = "PL"
    persona_list = PERSONAS[code]
    fallback = FALLBACK_PERSONA.get(code, FALLBACK_PERSONA["PL"])

    if not genre_scores:
        return fallback
    top = [g[0] for g in sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)[:3]]
    for genres, persona in persona_list:
        if all(g in top for g in genres):
            return persona
    for genres, persona in persona_list:
        if genres[0] in top:
            return persona
    return fallback
