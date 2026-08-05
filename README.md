# 🎬 CineScope Django — Recommender System & Web App

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Django](https://img.shields.io/badge/Django-4.2+-092E20.svg)
![HTMX](https://img.shields.io/badge/HTMX-1.9-blueviolet.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

CineScope to nowoczesna, profesjonalna aplikacja internetowa do rekomendacji filmowych zbudowana w **Pythonie i Django** z użyciem **HTMX** oraz eleganckiego motywu kinowego w ciemnych barwach.

---

## 🌟 Funkcje Aplikacji

- 🚀 **Błyskawiczne Rekomendacje ML**: Wykorzystanie modelowania TF-IDF i cosinusa podobieństwa do wyszukiwania "Filmów w podobnym klimacie".
- ⚡ **HTMX Live Search & Filtering**: Autouzupełnianie w czasie rzeczywistym i filtrowanie bez przeładowywania całej strony.
- 🍿 **Kinowy Modal Filmu z YouTube**: Dynamicznie pobierane zwiastuny, obsada i szczegóły z TMDB.
- 🎲 **Movie Roulette**: Losowanie filmu wg wybranego gatunku.
- 📌 **Watchlista**: Zapisywanie ulubionych pozycji w sesji użytkownika.

---

## 🛠️ Lokalny Rozruch

1. Przejdź do folderu projektu:
   ```bash
   cd cinescope-django
   ```

2. Aktywuj wirtualne środowisko Pythona (`venv`):
   ```bash
   source venv/bin/activate
   ```

3. Uruchom serwer deweloperski Django:
   ```bash
   python manage.py runserver
   ```

4. Otwórz w przeglądarce: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## ☁️ Darmowy Deployment na Render.com

1. Załóż darmowe konto na [Render.com](https://render.com).
2. Stwórz nowe **Web Service** i połącz je ze swoim repozytorium GitHub `cinescope-django`.
3. Render automatycznie wykryje środowisko Python i komendę z pliku `Procfile`:
   ```bash
   gunicorn config.wsgi:application
   ```
4. Gotowe! Twoja aplikacja będzie dostępna pod darmową domeną `.onrender.com`.
