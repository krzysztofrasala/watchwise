"""Multi-profile state management for Cinescope Django.

Stores profiles, watchlists, ratings, and active profile state in request.session.
"""

from __future__ import annotations
from typing import Any

DEFAULT_PROFILE_NAME = "Główny"
DEFAULT_VOD_SUBSCRIPTIONS = [8, 337, 1899]  # Netflix, Disney+, Max


def get_profile_data(session: dict[str, Any]) -> dict[str, Any]:
    """Ensure profiles state exists in session and return current state."""
    if "profiles" not in session:
        session["profiles"] = {
            DEFAULT_PROFILE_NAME: {
                "watchlist": [],
                "watched": [],
                "ratings": {},  # movie_id -> stars (1-5)
                "vod_subscriptions": list(DEFAULT_VOD_SUBSCRIPTIONS),
            }
        }
        session["active_profile"] = DEFAULT_PROFILE_NAME
        if hasattr(session, "modified"):
            session.modified = True
    else:
        # Backwards compatibility: ensure every profile has watched & vod_subscriptions
        updated = False
        for p_name, p_data in session["profiles"].items():
            if "watched" not in p_data:
                p_data["watched"] = []
                updated = True
            if "vod_subscriptions" not in p_data:
                p_data["vod_subscriptions"] = list(DEFAULT_VOD_SUBSCRIPTIONS)
                updated = True
        if updated and hasattr(session, "modified"):
            session.modified = True

    return session["profiles"]


def get_active_profile_name(session: dict[str, Any]) -> str:
    get_profile_data(session)
    return session.get("active_profile", DEFAULT_PROFILE_NAME)


def set_active_profile(session: dict[str, Any], name: str) -> None:
    profiles = get_profile_data(session)
    if name in profiles:
        session["active_profile"] = name
        if hasattr(session, "modified"):
            session.modified = True


def add_profile(session: dict[str, Any], name: str) -> bool:
    profiles = get_profile_data(session)
    clean_name = name.strip()
    if not clean_name or clean_name in profiles:
        return False

    profiles[clean_name] = {
        "watchlist": [],
        "watched": [],
        "ratings": {},
        "vod_subscriptions": list(DEFAULT_VOD_SUBSCRIPTIONS),
    }
    session["profiles"] = profiles
    session["active_profile"] = clean_name
    if hasattr(session, "modified"):
        session.modified = True
    return True


def get_active_watchlist(session: dict[str, Any]) -> list[int]:
    profiles = get_profile_data(session)
    active = get_active_profile_name(session)
    return profiles.get(active, {}).get("watchlist", [])


def toggle_watchlist_item(session: dict[str, Any], movie_id: int) -> tuple[bool, int]:
    profiles = get_profile_data(session)
    active = get_active_profile_name(session)

    if active not in profiles:
        profiles[active] = {
            "watchlist": [],
            "watched": [],
            "ratings": {},
            "vod_subscriptions": list(DEFAULT_VOD_SUBSCRIPTIONS),
        }

    watchlist = profiles[active]["watchlist"]
    mid = int(movie_id)

    if mid in watchlist:
        watchlist.remove(mid)
        added = False
    else:
        watchlist.append(mid)
        added = True

    profiles[active]["watchlist"] = watchlist
    session["profiles"] = profiles
    # Also sync to request.session["watchlist"] for backward compatibility
    session["watchlist"] = watchlist
    if hasattr(session, "modified"):
        session.modified = True
    return added, len(watchlist)


def get_active_watched(session: dict[str, Any]) -> list[int]:
    profiles = get_profile_data(session)
    active = get_active_profile_name(session)
    return profiles.get(active, {}).get("watched", [])


def toggle_watched_item(session: dict[str, Any], movie_id: int) -> tuple[bool, int]:
    """Toggle movie watched status. When marking as watched, optionally removes from to-watch watchlist."""
    profiles = get_profile_data(session)
    active = get_active_profile_name(session)

    if active not in profiles:
        profiles[active] = {
            "watchlist": [],
            "watched": [],
            "ratings": {},
            "vod_subscriptions": list(DEFAULT_VOD_SUBSCRIPTIONS),
        }

    watched = profiles[active].get("watched", [])
    watchlist = profiles[active].get("watchlist", [])
    mid = int(movie_id)

    if mid in watched:
        watched.remove(mid)
        marked = False
    else:
        watched.append(mid)
        marked = True
        # If moving to watched, remove from to-watch watchlist
        if mid in watchlist:
            watchlist.remove(mid)

    profiles[active]["watched"] = watched
    profiles[active]["watchlist"] = watchlist
    session["profiles"] = profiles
    session["watchlist"] = watchlist
    if hasattr(session, "modified"):
        session.modified = True
    return marked, len(watched)


def get_active_vod_subscriptions(session: dict[str, Any]) -> list[int]:
    profiles = get_profile_data(session)
    active = get_active_profile_name(session)
    return profiles.get(active, {}).get("vod_subscriptions", list(DEFAULT_VOD_SUBSCRIPTIONS))


def set_vod_subscriptions(session: dict[str, Any], provider_ids: list[int]) -> list[int]:
    profiles = get_profile_data(session)
    active = get_active_profile_name(session)

    if active not in profiles:
        profiles[active] = {
            "watchlist": [],
            "watched": [],
            "ratings": {},
            "vod_subscriptions": list(DEFAULT_VOD_SUBSCRIPTIONS),
        }

    clean_ids = []
    for pid in provider_ids:
        try:
            clean_ids.append(int(pid))
        except (ValueError, TypeError):
            continue

    profiles[active]["vod_subscriptions"] = clean_ids
    session["profiles"] = profiles
    if hasattr(session, "modified"):
        session.modified = True
    return clean_ids


def toggle_vod_subscription(session: dict[str, Any], provider_id: int) -> tuple[bool, list[int]]:
    subs = get_active_vod_subscriptions(session)
    pid = int(provider_id)

    if pid in subs:
        subs.remove(pid)
        enabled = False
    else:
        subs.append(pid)
        enabled = True

    set_vod_subscriptions(session, subs)
    return enabled, subs


def get_active_ratings(session: dict[str, Any]) -> dict[int, int]:
    profiles = get_profile_data(session)
    active = get_active_profile_name(session)
    return profiles.get(active, {}).get("ratings", {})


def set_movie_rating(session: dict[str, Any], movie_id: int, stars: int) -> dict[int, int]:
    profiles = get_profile_data(session)
    active = get_active_profile_name(session)

    if active not in profiles:
        profiles[active] = {
            "watchlist": [],
            "watched": [],
            "ratings": {},
            "vod_subscriptions": list(DEFAULT_VOD_SUBSCRIPTIONS),
        }

    ratings = profiles[active]["ratings"]
    mid = int(movie_id)

    if stars <= 0:
        ratings.pop(mid, None)
    else:
        ratings[mid] = min(5, max(1, int(stars)))

    profiles[active]["ratings"] = ratings
    session["profiles"] = profiles
    if hasattr(session, "modified"):
        session.modified = True
    return ratings

