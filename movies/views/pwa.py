"""PWA endpoints: manifest, service worker and offline page."""

import os

from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse

from .common import get_base_context


def manifest_view(request):
    """Serve PWA manifest.json."""
    manifest_path = os.path.join(settings.BASE_DIR, "templates", "pwa", "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()
    response = HttpResponse(content, content_type="application/manifest+json; charset=utf-8")
    response["Cache-Control"] = "public, max-age=86400"
    return response


def service_worker_view(request):
    """Serve PWA service worker with root scope permissions."""
    sw_path = os.path.join(settings.BASE_DIR, "templates", "pwa", "sw.js")
    with open(sw_path, "r", encoding="utf-8") as f:
        content = f.read()
    response = HttpResponse(content, content_type="application/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


def offline_view(request):
    """Render dedicated offline fallback page."""
    ctx = get_base_context(request)
    return render(request, "offline.html", ctx)
