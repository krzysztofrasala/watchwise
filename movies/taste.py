"""Taste-DNA profiling: genre/decade affinity scores and viewer personas for Cinescope Django."""

from __future__ import annotations
from typing import Any
import pandas as pd
from . import services

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
    ]
}

FALLBACK_PERSONA = {
    "PL": ("🎬", "Koneser Kina", "Prawdziwy kinoman o wszechstronnym i otwartym guście filmowym."),
    "EN": ("🎬", "The Movie Lover", "A true cinephile with eclectic and open taste."),
    "DE": ("🎬", "Der Filmkenner", "Ein wahrer Cineast mit vielseitigem Geschmack."),
    "ES": ("🎬", "El Cinefilo", "Un verdadero cinéfilo de gusto ecléctico y abierto."),
    "FR": ("🎬", "Le Cinéphile", "Un vrai passionné de cinéma au goût éclectique."),
    "IT": ("🎬", "Il Cinefilo", "Un vero appassionato di cinema con un gusto eclettico.")
}


def compute_taste_profile(user_ratings: dict[int, int], watchlist_ids: list[int], lang: str = "PL") -> dict[str, Any]:
    """Calculate genre distribution, decade distribution, persona, and total stats."""
    genre_scores: dict[str, float] = {}
    decade_scores: dict[int, float] = {}

    all_movies = services.get_all_movies()
    id_to_movie = {m["movie_id"]: m for m in all_movies}

    total_rated = len(user_ratings)
    total_watchlist = len(watchlist_ids)

    # Process rated movies
    for mid, stars in user_ratings.items():
        mid = int(mid)
        movie = id_to_movie.get(mid)
        if not movie:
            continue
        weight = float(stars) / 3.0  # rating weight

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
        movie = id_to_movie.get(mid)
        if not movie:
            continue
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

    return {
        "persona_icon": persona[0],
        "persona_title": persona[1],
        "persona_desc": persona[2],
        "total_rated": total_rated,
        "total_watchlist": total_watchlist,
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
