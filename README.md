# 🎬 CineScope Django — AI-Powered Movie & TV Series Recommender Web App

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Django](https://img.shields.io/badge/Django-4.2+-092E20.svg)
![HTMX](https://img.shields.io/badge/HTMX-1.9-blueviolet.svg)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.0-38BDF8.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

CineScope is a modern, high-performance web application for movie and TV series recommendations built with **Python 3**, **Django 4**, **HTMX**, and **Tailwind CSS**, featuring an ultra-sleek dark cinematic UI design.

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

- **Backend**: Python 3.9+, Django 4.2+, Pandas, NumPy, Scikit-learn, Requests, Gunicorn
- **Frontend**: HTML5, Vanilla CSS, Tailwind CSS CDN, HTMX, Lucide Icons, Chart.js
- **Data Source**: TMDB API, Custom Movie Vectors & Metadata Dataset

---

## 🚀 Local Setup Guide

1. **Clone the repository**:
   ```bash
   git clone https://github.com/krzysztofrasala/cinescope-django.git
   cd cinescope-django
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

4. **Run database migrations & system check**:
   ```bash
   python manage.py migrate
   python manage.py check
   ```

5. **Start the Django development server**:
   ```bash
   python manage.py runserver 8000
   ```

6. **Open in your browser**:
   Navigate to [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## ☁️ Deployment Guide (Render.com)

1. Create a free account on [Render.com](https://render.com).
2. Click **New +** -> **Web Service** and connect your GitHub repository `krzysztofrasala/cinescope-django`.
3. Render will auto-detect Python. Specify the build and start commands:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn config.wsgi:application`
4. Deploy! Your app will be live on a free `.onrender.com` domain.

---

## 📜 License

Distributed under the **MIT License**. See `LICENSE` for details.
