"""Keeps per-language HTML from being reused across language switches.

The UI language lives in the session, so the same URL renders differently per user. Without explicit
headers, browsers (back/forward cache, HTTP cache) and the service worker can keep showing a page in the
previously selected language.
"""
from __future__ import annotations

LANG_COOKIE = "ww_lang"


class LanguageCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        ctype = response.get("Content-Type", "")
        if path.startswith(("/static/", "/sw.js", "/manifest")) or not ctype.startswith(("text/html", "application/json")):
            return response
        # Language-dependent response: never serve it from a shared/stale HTTP cache without revalidation.
        response["Cache-Control"] = "private, no-cache, max-age=0"
        response["Vary"] = "Cookie" if not response.get("Vary") else response["Vary"] + ", Cookie"
        session = getattr(request, "session", None)
        lang = (session.get("lang") if session is not None else None) or "PL"
        response["X-App-Lang"] = str(lang).upper()
        return response
