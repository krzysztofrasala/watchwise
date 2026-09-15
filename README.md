# 🎬 Watch Wise 2.0 — AI-Powered Movie & TV Series Recommender Web App

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Django](https://img.shields.io/badge/Django-4.2+-092E20.svg)
![HTMX](https://img.shields.io/badge/HTMX-1.9-blueviolet.svg)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.0-38BDF8.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

Watch Wise is a modern, high-performance web application for movie and TV series recommendations built with **Python 3**, **Django 4**, **HTMX**, and **Tailwind CSS**, featuring an ultra-sleek dark cinematic UI design.

---

## 🌟 Key Features

- 🚀 **ML-Powered Recommendation Engine**: Uses TF-IDF vectorization, dense sentence-embeddings, and Cosine Similarity for intelligent content-based movie recommendations.
- ⚡ **HTMX Live Search & Real-time Auto-complete**: Fast, instant multi-search supporting both **Movies and TV Series** without full page reloads.
- 🍿 **Interactive Movie & TV Show Modals**: Dynamic YouTube trailer player, cast photo grids, season & episode counts, and TMDB integration.
- 🔗 **Direct VOD Deep-links & JustWatch Integration**: Clickable platform badges linking directly to titles on **Netflix**, **Disney+**, **Prime Video**, **Max (HBO)**, **Apple TV+**, **SkyShowtime**, and **JustWatch**.
- 🎛️ **Discover Pro**: Advanced multi-criterion filtering by genre, original language (Polish, English, French, Spanish, Japanese, Korean, German, Italian, etc.), release year, and rating threshold.
- 🤖 **AI Movie Assistant**: Conversational natural language query engine to find films matching any mood or description.
- 🧬 **Taste DNA & Persona Profile**: Visual analytics (Chart.js) breaking down genre affinity, favorite eras, and cinema personas based on user ratings.
- 👥 **Social Matchmaker**: Multi-profile compromise vector algorithm to compute joint recommendations for two viewers.
- 🎲 **Movie Roulette**: Random movie selector filtered by chosen genre.
- 📌 **Watchlist & Rating System**: Session-persistent watchlists and 5-star interactive rating widget.
- 🌍 **Multi-language Support (i18n)**: Seamless language switching (EN, PL, DE, ES, FR, IT).

---

## 🛠️ Tech Stack

- **Backend**: Python 3.9+, Django 5.x, Pandas, NumPy, Scikit-learn, Requests (Connection Pooling), WhiteNoise, Gunicorn
- **Frontend**: HTML5, Pre-built Minified Tailwind CSS, HTMX, Lucide Icons, Chart.js
- **Caching & Storage**: Django Cache Framework (LocMemCache / Redis ready), WhiteNoise Compressed Manifest Static Files
- **Data Source**: TMDB API (Session-pooled), Custom Movie Vectors & Metadata Dataset

---

## ⚡ Performance & Production Architecture

Watch Wise 2.0 incorporates high-efficiency backend optimizations:
- **$O(1)$ In-Memory Indexing**: Eliminates full DataFrame scans with precomputed dictionary mappings (`movie_id -> record` and `movie_id -> index`), enabling sub-millisecond retrieval.
- **Zero `iterrows()` Overhead**: Recommendation algorithms (`recommend_for_user`, `recommend_for_vibes`) use vectorized numpy operations and pre-indexed records, accelerating recommendations by over 10x.
- **HTTP Connection Pooling & Retries**: TMDB queries use a thread-safe `requests.Session` with `HTTPAdapter` and exponential backoff retry policies, reusing TCP/TLS handshakes.
- **Parallel Metadata Resolution**: Missing external titles in watchlists are resolved concurrently via `ThreadPoolExecutor` workers.
- **Multi-Tier Cache Layer**: Live trending queries are cached for 4 hours and Taste DNA analytics are cached by taste signature for 24 hours.
- **Pre-Built Tailwind CSS**: Replaced runtime CDN script with pre-compiled 36 KB minified CSS bundle for instant rendering and high First Contentful Paint (FCP) scores.
- **Production-Ready Security**: Environment-driven `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, and secure credential management.

---

## 🚀 Local Setup Guide

1. **Clone the repository**:
   ```bash
   git clone https://github.com/krzysztofrasala/watchwise.git
   cd watchwise
   ```

2. **Create and activate a virtual environment (`venv`)**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **(Optional) Build or watch CSS**:
   ```bash
   npm run build:css
   ```

5. **Run database migrations & collect static files**:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --no-input
   ```

6. **Run tests**:
   ```bash
   python manage.py test
   ```

7. **Start the Django development server**:
   ```bash
   python manage.py runserver 8000
   ```

8. **Open in your browser**:
   Navigate to [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## ☁️ Deployment Guide (Render.com)

1. Connect your repository to [Render.com](https://render.com) using the included `render.yaml` or as a new **Web Service**.
2. Configure Environment Variables:
   - `PYTHON_VERSION`: `3.11.9`
   - `DJANGO_DEBUG`: `False`
   - `DJANGO_SECRET_KEY`: `[your-strong-random-key]`
   - `TMDB_API_KEY`: `[your-tmdb-api-key]`
3. Specify build and start commands:
   - **Build Command**: `pip install -r requirements.txt && python manage.py collectstatic --no-input`
   - **Start Command**: `python manage.py migrate && gunicorn config.wsgi:application`
4. Deploy! Your app will be live with WhiteNoise compressed assets and production security.

---

## 📜 License

Distributed under the **MIT License**. See `LICENSE` for details.
