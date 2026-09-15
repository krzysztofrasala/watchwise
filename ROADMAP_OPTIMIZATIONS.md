# 🚀 Audyt Projektu & Plan Usprawnień (WatchWise / Cinescope)

> **Data audytu:** Wrzesień 2026  
> **Status:** Oczekuje na wdrożenie (zaplanowane za tydzień)  
> **Środowisko:** Django 5.x, Python 3.9 (`./venv`), Pandas, HTMX, TailwindCSS

---

## 📌 Spis Treści
1. [Krótkie Podsumowanie](#krótkie-podsumowanie)
2. [Faza 1: Krytyczne Optymalizacje Wydajności (Backend)](#faza-1-krytyczne-optymalizacje-wydajności-backend)
3. [Faza 2: Produkcja, Bezpieczeństwo i Cache](#faza-2-produkcja-bezpieczeństwo-i-cache)
4. [Faza 3: Nowe Funkcjonalności & UX](#faza-3-nowe-funkcjonalności--ux)
5. [Jak Wznowić Pracę Za Tydzień](#jak-wznowić-pracę-za-tydzień)

---

## 🔍 Krótkie Podsumowanie
Podczas szczegółowej analizy projektu zidentyfikowano:
- **Wąskie gardła Pandas:** iterowanie w pętli przez 4800+ rekordów przy każdym zapytaniu o rekomendację.
- **Blokujące zapytania HTTP:** brak puli połączeń (`requests.Session()`) i sekwencyjne odpytywanie TMDB w widoku watchlisty.
- **Brak warstwy cache:** zapytania TMDB (Trending, Upcoming) i obliczenia profilu Taste DNA wykonują się na żywo za każdym przeładowaniem.
- **Kwestie deploymentu:** brak konfiguracji `WhiteNoise` (statyki na Renderze pod Gunicornem) oraz hardcoded `DEBUG = True` / API keys.

---

## ⚡ Faza 1: Krytyczne Optymalizacje Wydajności (Backend)

### 1. Eliminacja `iterrows()` w silniku rekomendacji
- **Plik:** [`movies/recommender.py`](file:///Users/krzysztofrasala/Developer/projects/github/cinescope-django/movies/recommender.py#L26)
- **Problem:**
  ```python
  id_to_idx = {row["movie_id"]: i for i, row in movies_df.iterrows()}
  ```
  Wywołuje się przy **każdym** `recommend_for_user()`. `iterrows()` tworzy obiekt `pd.Series` dla każdego z 4800 wierszy, co generuje olbrzymi narzut procesora.
- **Rozwiązanie:**
  Przeprowadzić prekomputację słownika mapującego `movie_id -> index` jednokrotnie w `movies/services.py` podczas ładowania datasetu:
  ```python
  id_to_idx = dict(zip(movies_df["movie_id"], range(len(movies_df))))
  ```

### 2. O(1) Dostęp do filmów zamiast skanowania DataFrame
- **Pliki:** [`movies/services.py:94`](file:///Users/krzysztofrasala/Developer/projects/github/cinescope-django/movies/services.py#L94) oraz [`movies/taste.py:116`](file:///Users/krzysztofrasala/Developer/projects/github/cinescope-django/movies/taste.py#L116)
- **Problem:**
  - `get_movie_by_id(movie_id)` wykonuje pełny skan DataFrame `movies_df[movies_df["movie_id"] == int(movie_id)]`.
  - `taste.py` wywołuje `services.get_all_movies()`, co konwertuje cały DataFrame do słownika (`.to_dict(orient="records")`) przy każdym wyświetleniu profilu.
- **Rozwiązanie:**
  Utworzenie globalnego słownika `_movie_id_dict = {row['movie_id']: row for row in ...}` przy starcie aplikacji – natychmiastowy dostęp $O(1)$ bez obciążania procesora.

### 3. Connection Pooling dla TMDB API
- **Plik:** [`movies/tmdb.py`](file:///Users/krzysztofrasala/Developer/projects/github/cinescope-django/movies/tmdb.py)
- **Problem:**
  Użycie nagich wywołań `requests.get(...)`. Każde zapytanie do API TMDB negocjuje od nowa handshake TCP + TLS.
- **Rozwiązanie:**
  Singleton `requests.Session()` z adapterem `HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=3)`.

### 4. Równoległe pobieranie danych w Watchliście
- **Plik:** [`movies/views.py`](file:///Users/krzysztofrasala/Developer/projects/github/cinescope-django/movies/views.py) (widok `watchlist`)
- **Problem:**
  Jeśli użytkownik dodał do watchlisty filmy spoza bazy CSV (lub seriale z TMDB), pobieranie metadanych odbywa się w pętli `for mid in watchlist_ids:` sekwencyjnie. 10 pozycji = kilkusekundowe oczekiwanie na odpowiedź.
- **Rozwiązanie:**
  Zastosowanie `concurrent.futures.ThreadPoolExecutor(max_workers=5)` do równoległego odpytania TMDB.

---

## 🛡️ Faza 2: Produkcja, Bezpieczeństwo i Cache

### 1. Bezpieczna konfiguracja produkcyjna (`config/settings.py`)
- `DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1')`
- `SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'default-dev-key')`
- Usunięcie zapasowego klucza TMDB z kodu źródłowego (`hydrate_dataset.py` i `movies/tmdb.py`).

### 2. Obsługa plików statycznych (WhiteNoise dla Render.com)
- Dodanie `whitenoise` do `requirements.txt`.
- Konfiguracja `whitenoise.middleware.WhiteNoiseMiddleware` w `config/settings.py`.
- Umożliwi bezproblemowe serwowanie CSS/JS/obrazów pod Gunicornem na Renderze bez konfiguracji zewnętrznego S3.

### 3. Django Cache Framework
- Konfiguracja pamięci podręcznej w `settings.py` (`LocMemCache` lokalnie, opcjonalnie Redis):
  - Cache dla zapytań `trending` i `upcoming` (TTL: 3–6 godzin).
  - Cache dla obliczonego Taste DNA per profil (inwalidowany tylko przy dodaniu nowej oceny).

### 4. TailwindCSS CDN vs Pre-built CSS
- Obecnie w `templates/base.html` ładowany jest `cdn.tailwindcss.com`.
- Skrypt kompiluje style w locie w przeglądarce klienta przy każdym odświeżeniu.
- Docelowo: kompilacja do statycznego pliku `main.css` przez Tailwind CLI (znaczący skok w metrykach First Contentful Paint).

---

## 💡 Faza 3: Nowe Funkcjonalności & UX

1. **Prawdziwa integracja Google Gemini w `movies/nl_query.py`**:
   - `google-genai` znajduje się już w `requirements.txt`.
   - Zastąpienie/wzbogacenie parsera regexowego modelem Gemini Flash do swobodnych zapytań użytkownika (np. *"znajdź coś mrocznego z lat 90. w stylu Davida Finchera z wysoką oceną"*).
   - Zachowanie fallbacku na regex, gdy brak klucza API.

2. **Deep-linking i bezpośrednie URL-e do filmów**:
   - Filmy otwierają się obecnie wyłącznie w modalach HTMX bez zmiany adresu URL.
   - Dodanie `hx-push-url="true"` lub dedykowanego widoku `/movie/<id>/` pozwoli dzielić się bezpośrednimi linkami ze znajomymi.

3. **Eksport i Import Profilu (JSON)**:
   - Profile, polubienia i watchlisty zapisywane są tylko w sesji przeglądarki (`request.session`).
   - Wyczyszczenie ciasteczek usuwa historię. Dodanie prostego przycisku *"Pobierz kopię zapasową (JSON)"* i *"Wgraj profil"* rozwiąże ten problem bez konieczności budowania skomplikowanego systemu autoryzacji z bazą kont.

4. **Odznaki platform VOD na kafelkach**:
   - Wyświetlanie miniaturowych ikonek (Netflix, HBO Max, Disney+, itp.) bezpośrednio w siatce filmów na stronie głównej i w Discover, bez konieczności otwierania każdego modala z osobna.

5. **Nieskończone przewijanie (Infinite Scroll)**:
   - Zastąpienie stronicowania w Discover Pro mechanizmem `hx-trigger="revealed"` z płynnym doładowywaniem kolejnych wierszy.

---

## 🛠️ Jak Wznowić Pracę Za Tydzień

Gdy włączysz komputer za tydzień i uruchomisz asystenta:
1. **Wystarczy wpisać:**  
   > *"Wracamy do projektu. Zaczynamy od Fazy 1 z pliku ROADMAP_OPTIMIZATIONS.md (optymalizacja recommender i services)."*
2. **Kluczowe polecenia deweloperskie:**
   - Testy jednostkowe: `./venv/bin/python manage.py test` (14 testów przechodzi pomyślnie)
   - Uruchomienie serwera: `./venv/bin/python manage.py runserver 8000`
