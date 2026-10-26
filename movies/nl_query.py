"""Natural language query parsing for Cinescope Django.

Converts free-text queries like 'mroczny thriller z lat 90' or 'comédie française des années 80'
into structured movie filtering parameters. The local parser understands PL, EN, DE, ES, FR and IT
(diacritics optional). If a Gemini API key is configured it is tried first, with the local
parser as the fallback.
"""

from __future__ import annotations
import datetime
import os
import re
import unicodedata
from typing import Any

# All keyword stems below are written lowercase and WITHOUT diacritics: the query is normalized the
# same way before matching, so "śmieszny" / "smieszny" / "komödie" / "komodie" all hit the same stem.
# Every stem is matched as a word prefix (\b + stem), which covers Polish/Romance inflections.

GENRE_PATTERNS: dict[str, list[str]] = {
    "Comedy": [
        "komedi", "smiesz", "zabawn", "humor", "rozweselaj", r"feel.?good", r"light.?hearted",
        "funny", "comed", "komod", "lustig", "witzig", "gracios", "divertid", "drole", "amusant",
        "commed", "divertent", "spassos", "hilarious",
    ],
    "Horror": [
        "horror", "strasz", "przerazaj", "scary", "spooky", "creepy", "terrif", "grus", "schreck",
        "miedo", "terror", "effray", "epouvant", "peur", "paura", "spavent",
    ],
    "Romance": [
        "romans", "romantycz", "milosn", "romanc", "romantic", r"love\b", r"love\s*stor", "liebes",
        "romantisch", "amor", "amour", "amore", "innamor",
    ],
    "Action": [
        "akcj", "sensacyj", "action", "aktion", "accion", "azione", "adrenalin", "explosi",
    ],
    "Adventure": ["przygod", "adventur", "abenteuer", "aventur", "avventur"],
    "Science Fiction": [
        r"sci.?fi", r"science.?fiction", r"fantastyk\w*\s+naukow", "fantascien", r"ciencia.?ficcion",
        "kosmi", "kosmos", r"space\b", "weltraum", "futury", "cyberpunk", "robot", "alien", "extraterr",
    ],
    "Drama": [
        "dramat", "obyczaj", "drama", "drame", "dramma", "smutn", r"sad\b", "traurig", "triste",
        "tragi", "wzrusz", "emocjon", "tearjerker", r"na\s+dola",
    ],
    "Animation": [
        "animac", "animat", "animowan", "kreskowk", "cartoon", "zeichentrick", "dibujos", "dessin",
        "cartone", "anime", "pixar",
    ],
    "Thriller": [
        "thriller", "dreszczowc", "dreszczowiec", "suspens", "spannend", r"zwrot\w*\s+akcji",
        r"plot\s*twist", r"mind.?bending", "psychologiczn", "psychological", "psychologisch",
    ],
    "Crime": [
        "crim", "krimi", "krymin", "mafi", "gangster", "polic", "polizi", "heist", "napad", "noir",
    ],
    "Fantasy": ["fantasy", "fantastyk", "magia", "magicz", "magic", "fantasia", "fantastique", "zauber"],
    "War": ["wojen", "wojn", r"war\b", "krieg", "guerr", "bellic"],
    "History": [
        "historycz", r"history\b", "historic", r"histori(?:sch|que|co|ca)", "geschicht", "storic",
    ],
    "Music": ["muzyczn", "musical", "music", "musik", "musique"],
    "Documentary": ["dokument", "document"],
    "Family": [
        "familijn", "rodzinn", "dla dzieci", "dzieci", "famil", r"kids?\b", "children", "kinder",
        "ninos", "enfants", "bambini", "bajk",
    ],
    "Mystery": [
        "tajemnic", "zagadk", "myst", "mister", "ratsel", "detektyw", "detective", "detektiv",
        "whodunit",
    ],
    "Western": ["western", r"dziki\s+zachod", r"wild\s+west", r"far\s+west", "oeste", "spaghetti"],
}

# Compound phrases that must win over their single-word parts (e.g. "romantic comedy" is Romance).
COMPOUND_GENRES: list[tuple[str, str]] = [
    (
        r"\b(?:romantic\w*\s+comed|komedi\w*\s+romantycz|rom.?com|romantische\s+komod|"
        r"comedia\s+romantic|comedie\s+romantique|commedia\s+romantic)",
        "Romance",
    ),
]

LANGUAGE_PATTERNS: dict[str, list[str]] = {
    "pl": ["polsk", "polish", "polnisch", "polac", "polonais", "polones", "polacc"],
    "fr": ["francusk", "french", "franzos", "frances", "francais"],
    "es": ["hiszpansk", "spanish", "spanisch", "espanol", "spagnol", "espagnol"],
    "ja": ["japonsk", "japanese", "japanisch", "japones", "japonais", "giapponese", "anime", "manga"],
    "ko": ["koreansk", "korean", "koreanisch", "coreano", "coreen"],
    "de": ["niemieck", "german", "deutsch", "aleman", "allemand", "tedesc"],
    "it": ["wlosk", "italian", "italienisch", "italien"],
    "en": ["angielsk", "english", "englisch", "ingles", "anglais", "inglese", "amerykansk", "american",
           "amerikanisch", "americano", "americain"],
}

RECENT = (
    r"\b(?:najnowsz|nowosc|nowosci|nowe\b|swiez|aktualn|newest|latest|recent|brand\s+new|new\s+releases?|"
    r"neu(?:e|en|es|er)?\b|neuerscheinung|nuev|reciente|ultim|nouveau|nouveaut|nuov|novita)"
)
CLASSIC = (
    r"\b(?:klasyk|stare\b|starych|classic|klassiker|clasic|classique|retro|vintage|old.?school)"
)
BEST = (
    r"\b(?:arcydziel|najlepsz|najwyzej|top\b|best|masterpiece|besten|beste\b|meisterwerk|mejor|"
    r"obra\s+maestra|meilleur|migliori|capolavor|highest.rated)"
)
GOOD = (
    r"\b(?:dobr\w*|good|great|well.rated|highly.rated|acclaimed|gut\w*|bueno\w*|buena\w*|"
    r"bon(?:s|ne|nes)?\b|buon\w*|ottim\w*)"
)
OLDEST = r"\b(?:najstarsz|oldest|altest|mas\s+antigu|plus\s+ancien|piu\s+vecch)"
WORST = r"\b(?:najgorsz|worst|schlechtest|\bpeor|\bpire\b|peggior)"

RATING_NUMBER = re.compile(
    r"(?:rating|ocen\w*|note\b|nota\b|bewertung|valoracion|puntuacion|voto|punteggio|score|powyzej|"
    r"ponad|above|over|mindestens|mas\s+de|plus\s+de|oltre)\s*(?:of|de|di|von|:)?\s*"
    r"(\d(?:[.,]\d)?)\b(?!\s*(?:godz|h\b|hour|stunden|min|heure|hora|ore\b|ora\b|uhr))"
)
RATING_PLUS = re.compile(r"(?<![\d.])(\d(?:[.,]\d)?)\s*(?:\+|/\s*10)")

YEAR = r"(?:19|20)\d{2}"
DECADE_MARKER = r"(?:lat|lata|latach|anni|annees|anos|years|jahre|jahren)"


def _normalize(text: str) -> str:
    """Lowercase and strip diacritics so 'Śmieszny' == 'smieszny' and 'Komödie' == 'komodie'."""
    text = (text or "").lower().replace("’", "'").replace("ł", "l").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def _best_match(patterns: dict[str, list[str]], text: str) -> str | None:
    """Return the key whose stem matches earliest in the text (longest match wins ties)."""
    best: tuple[int, int, str] | None = None
    for key, stems in patterns.items():
        m = re.search(r"\b(?:" + "|".join(stems) + ")", text)
        if m:
            cand = (m.start(), -(m.end() - m.start()), key)
            if best is None or cand < best:
                best = cand
    return best[2] if best else None


def _decade_range(start: int) -> tuple[int, int]:
    return start, start + 9


def _parse_years(q: str) -> tuple[int | None, int | None]:
    """Extract (year_min, year_max) from ranges, decades, 'after/before X' and plain years."""
    # "1995-2005", "od 2000 do 2010", "between 2000 and 2010", "zwischen 2000 und 2010"
    m = re.search(rf"\b({YEAR})\s*(?:-|do|to|and|und|y|et|e|bis|hasta|a|i|al)\s*({YEAR})\b", q)
    if m:
        lo, hi = sorted((int(m.group(1)), int(m.group(2))))
        return lo, hi

    # Decades: "1990s", "lat 90", "90s", "90er", "années 80", "anni '90", "lata 1980"
    m = re.search(rf"\b((?:19|20)\d0)(?:'?s|er|ies)\b", q) or re.search(
        rf"\b{DECADE_MARKER}\s*'?((?:19|20)\d0)\b", q
    )
    if m:
        return _decade_range(int(m.group(1)))
    m = re.search(rf"\b{DECADE_MARKER}\s*'?(\d0)\b", q) or re.search(
        r"(?<!\d)'?(\d0)(?:'?s|er|ies|-?tych|-?ych)\b", q
    )
    if m:
        n = int(m.group(1))
        base = 2000 if n <= 20 else 1900
        return _decade_range(base + (n // 10) * 10)

    # "po 2010", "after 2010", "seit 2015", "depuis 2015", "dopo il 2010"
    m = re.search(
        rf"\b(?:po|od|after|since|ab|seit|nach|despues\s+de|desde|apres|depuis|dopo(?:\s+il)?|dal)\s+({YEAR})\b", q
    )
    if m:
        return int(m.group(1)), None

    # "przed 2000", "before 2000", "vor 2000", "antes de 2000", "avant 2000", "prima del 2000"
    m = re.search(
        rf"\b(?:przed|before|until|till|do|vor|bis|antes\s+de|hasta|avant|prima\s+(?:del|di)|entro)\s+({YEAR})\b", q
    )
    if m:
        return None, int(m.group(1))

    # A single standalone year ("z 1995", "from 1994", "aus 2001") means exactly that year.
    m = re.search(rf"\b({YEAR})\b", q)
    if m:
        year = int(m.group(1))
        return year, year

    return None, None


def parse_natural_query_regex(query_text: str) -> dict[str, Any]:
    """Parse text into filter arguments using multilingual keywords and regex."""
    q = _normalize(query_text)

    genre = None
    for pattern, g_name in COMPOUND_GENRES:
        if re.search(pattern, q):
            genre = g_name
            break
    if genre is None:
        genre = _best_match(GENRE_PATTERNS, q)

    language = _best_match(LANGUAGE_PATTERNS, q)

    year_min, year_max = _parse_years(q)
    has_years = year_min is not None or year_max is not None

    vote_min = None
    sort_by = "vote_desc"

    m = RATING_NUMBER.search(q) or RATING_PLUS.search(q)
    if m:
        value = float(m.group(1).replace(",", "."))
        if 4.0 <= value <= 10.0:
            vote_min = value

    if re.search(WORST, q):
        sort_by = "vote_asc"
    elif re.search(OLDEST, q):
        sort_by = "year_asc"
    elif re.search(RECENT, q):
        sort_by = "year_desc"
        if not has_years:
            year_min = datetime.date.today().year - 2

    if re.search(CLASSIC, q) and not has_years:
        year_max = 1999
        vote_min = max(vote_min or 0.0, 7.5)

    if vote_min is None:
        if re.search(BEST, q):
            # "best" alone is very strict; relax when combined with other filters to avoid empty results
            narrowed = genre or language or year_min or year_max
            vote_min = 7.5 if narrowed else 8.0
        elif re.search(GOOD, q):
            vote_min = 7.0

    understood = any([genre, language, year_min, year_max, vote_min]) or sort_by != "vote_desc"

    return {
        "genre": genre or "All",
        "year_min": year_min,
        "year_max": year_max,
        "vote_min": vote_min,
        "sort_by": sort_by,
        "language": language,
        "understood": understood,
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
                "understood": True,
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
