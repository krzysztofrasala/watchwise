"""Natural language query parsing for Cinescope Django.

Converts free-text queries like 'mroczny thriller z lat 90' or 'śmieszna komedia'
into structured movie filtering parameters. Supports Gemini API with fallback to local regex parser.
"""

from __future__ import annotations
import datetime
import os
import re
from typing import Any

GENRE_KEYWORDS = {
    "komedia": "Comedy", "śmieszny": "Comedy", "śmieszne": "Comedy", "funny": "Comedy", "humor": "Comedy",
    "horror": "Horror", "straszny": "Horror", "straszne": "Horror", "scary": "Horror",
    "romans": "Romance", "romantyczny": "Romance", "love": "Romance",
    "akcja": "Action", "akcji": "Action", "sensacyjny": "Action", "action": "Action",
    "przygodowy": "Adventure", "przygoda": "Adventure", "adventure": "Adventure",
    "sci-fi": "Science Fiction", "scifi": "Science Fiction", "kosmos": "Science Fiction", "futurystyczny": "Science Fiction",
    "dramat": "Drama", "obyczajowy": "Drama", "drama": "Drama",
    "animacja": "Animation", "animowany": "Animation", "kreskówka": "Animation", "anime": "Animation",
    "thriller": "Thriller", "dreszczowiec": "Thriller",
    "kryminał": "Crime", "kryminalny": "Crime", "mafia": "Crime", "crime": "Crime",
    "fantasy": "Fantasy", "magia": "Fantasy",
    "wojenny": "War", "wojna": "War",
    "historyczny": "History", "historia": "History",
    "muzyczny": "Music", "musical": "Music",
    "dokumentalny": "Documentary", "dokument": "Documentary",
}

LANGUAGE_KEYWORDS = {
    "polski": "pl", "polskie": "pl", "polskiego": "pl", "polska": "pl", "polish": "pl",
    "francuski": "fr", "francuskie": "fr", "french": "fr",
    "hiszpański": "es", "hiszpańskie": "es", "spanish": "es",
    "japoński": "ja", "japońskie": "ja", "japanese": "ja",
    "koreański": "ko", "koreańskie": "ko", "korean": "ko",
    "niemiecki": "de", "niemieckie": "de", "german": "de",
    "włoski": "it", "włoskie": "it", "italian": "it",
    "angielski": "en", "angielskie": "en", "english": "en",
}


def parse_natural_query_regex(query_text: str) -> dict[str, Any]:
    """Parse text into filter arguments using keywords and regex."""
    q = query_text.lower()

    matched_genre = "All"
    year_min = None
    year_max = None
    vote_min = None
    sort_by = "vote_desc"
    language = None

    # Genre search
    for kw, g_name in GENRE_KEYWORDS.items():
        if re.search(r"\b" + re.escape(kw) + r"\b", q):
            matched_genre = g_name
            break

    # Language search
    for kw, lang_code in LANGUAGE_KEYWORDS.items():
        if re.search(r"\b" + re.escape(kw) + r"\b", q):
            language = lang_code
            break

    # Decade matching ("lat 90", "90s", "1980s", "lat 80-tych")
    decade_match = re.search(r"(?:lat\s*)?([0-9]{2}|19[0-9]{2}|20[0-9]{2})(?:s|-tych|-ch)?", q)
    if decade_match:
        raw = decade_match.group(1)
        if len(raw) == 2:
            n = int(raw)
            base = 2000 if n <= 20 else 1900
            start = base + (n // 10) * 10
        else:
            start = int(raw) // 10 * 10
        year_min = start
        year_max = start + 9

    # Specific phrases
    if "najnowsze" in q or "nowości" in q or "nowe" in q:
        year_min = datetime.date.today().year - 2
        sort_by = "year_desc"
    elif "klasyka" in q or "stare" in q or "klasyki" in q:
        year_max = 2000
        sort_by = "vote_desc"
        vote_min = 7.5

    if "arcydzieło" in q or "najlepsze" in q or "top" in q:
        vote_min = 8.0
        sort_by = "vote_desc"

    return {
        "genre": matched_genre,
        "year_min": year_min,
        "year_max": year_max,
        "vote_min": vote_min,
        "sort_by": sort_by,
        "language": language,
    }


def parse_natural_query_gemini(query_text: str, api_key: str) -> dict[str, Any] | None:
    """Use Google Gemini to extract nuanced cinema filters from natural language."""
    try:
        import json
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = (
            "You are an expert movie librarian. Extract structured movie search parameters from this user query:\n"
            f'"{query_text}"\n\n'
            "Valid genres: Action, Adventure, Animation, Comedy, Crime, Documentary, Drama, Family, Fantasy, "
            "History, Horror, Music, Mystery, Romance, Science Fiction, TV Movie, Thriller, War, Western, All.\n"
            "Valid ISO languages: en, pl, fr, es, ja, ko, de, it, or null.\n"
            "Valid sort_by: vote_desc, vote_asc, year_desc, year_asc, popularity.\n\n"
            "Return ONLY a JSON object with this exact schema:\n"
            "{\n"
            '  "genre": "Genre or All",\n'
            '  "year_min": integer or null,\n'
            '  "year_max": integer or null,\n'
            '  "vote_min": float or null,\n'
            '  "sort_by": "vote_desc",\n'
            '  "language": "code or null",\n'
            '  "ai_explanation": "one short sentence in Polish or English matching user language explaining what kind of movies to look for"\n'
            "}"
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        if isinstance(data, dict) and "genre" in data:
            return {
                "genre": data.get("genre", "All"),
                "year_min": data.get("year_min"),
                "year_max": data.get("year_max"),
                "vote_min": float(data["vote_min"]) if data.get("vote_min") is not None else None,
                "sort_by": data.get("sort_by", "vote_desc"),
                "language": data.get("language"),
                "ai_explanation": data.get("ai_explanation", ""),
            }
    except Exception:
        pass
    return None


def parse_natural_query(query_text: str) -> dict[str, Any]:
    """Parse text query using Gemini API if key is set, with seamless fallback to regex."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        result = parse_natural_query_gemini(query_text, api_key)
        if result:
            return result
    return parse_natural_query_regex(query_text)
