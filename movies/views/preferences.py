"""Profile management, UI language and profile import/export."""

import json

from django.shortcuts import redirect
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from .. import profiles, i18n
from ..middleware import LANG_COOKIE


@require_POST
def switch_profile(request):
    profile_name = request.POST.get("profile_name", "").strip()
    if profile_name:
        profiles.set_active_profile(request.session, profile_name)
    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_POST
def create_profile(request):
    profile_name = request.POST.get("new_profile_name", "").strip()
    if profile_name:
        profiles.add_profile(request.session, profile_name)
    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_POST
def delete_profile_view(request):
    profile_name = request.POST.get("profile_name", "").strip()
    if profile_name:
        profiles.delete_profile(request.session, profile_name)
    return redirect(request.META.get("HTTP_REFERER", "/"))


@require_POST
def switch_language(request):
    lang_code = request.POST.get("lang", "PL").strip()
    code = i18n.set_lang(request.session, lang_code)
    target = request.META.get("HTTP_REFERER", "/")
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        target = "/"
    response = redirect(target)
    # Readable by JS so already-open pages/tabs/bfcache entries can detect a stale language and reload.
    response.set_cookie(LANG_COOKIE, code, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return response


IMPORT_MAX_BYTES = 1024 * 1024     # 1 MB


def export_profile(request):
    """Export current profiles and watchlists as downloadable JSON."""
    data = profiles.export_profiles_data(request.session)
    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type="application/json; charset=utf-8"
    )
    response["Content-Disposition"] = 'attachment; filename="watchwise_profiles_backup.json"'
    return response


@require_POST
def import_profile(request):
    """Import profiles from uploaded JSON file."""
    uploaded_file = request.FILES.get("profile_file")
    if uploaded_file and uploaded_file.size > IMPORT_MAX_BYTES:
        return HttpResponse("File too large (max 1 MB).", status=413)
    if uploaded_file:
        try:
            content = uploaded_file.read().decode("utf-8")
            data = json.loads(content)
            profiles.import_profiles_data(request.session, data)
        except Exception:
            pass
    return redirect(request.META.get("HTTP_REFERER", "/"))
