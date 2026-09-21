"""Dynamic translation helper with caching for movie overviews and taglines."""

from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from django.core.cache import cache
import requests

logger = logging.getLogger(__name__)

TRANSLATE_API_URL = "https://api.mymemory.translated.net/get"
CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "translations_cache.json"

_disk_cache: dict[str, str] | None = None


def _get_disk_cache() -> dict[str, str]:
    global _disk_cache
    if _disk_cache is None:
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    _disk_cache = json.load(f)
            except Exception:
                _disk_cache = {}
        else:
            _disk_cache = {}
    return _disk_cache


def _save_disk_cache() -> None:
    global _disk_cache
    if _disk_cache is not None:
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(_disk_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug("Failed to save translation disk cache: %s", e)


def translate_text(text: str, target_lang: str = "ES", source_lang: str | None = None) -> str:
    """Translate text to target_lang with in-memory, django cache, and persistent disk cache.

    If target_lang is 'EN' or 'PL', returns text as is (or source language).
    """
    if not text or not isinstance(text, str):
        return ""

    target_code = target_lang.lower().strip()
    if target_code in ["en", "pl"] and not source_lang:
        # Standard native languages already in dataset
        return text

    # Detect source language if not explicitly provided
    if not source_lang:
        is_pl = any(c in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ" for c in text)
        source_code = "pl" if is_pl else "en"
    else:
        source_code = source_lang.lower().strip()

    if target_code == source_code:
        return text

    # Cache key based on hash of text and language pair
    cache_key = f"trans_{source_code}_{target_code}_{abs(hash(text))}"

    # 1. Check disk cache first
    disk_cache = _get_disk_cache()
    if cache_key in disk_cache:
        return disk_cache[cache_key]

    # 2. Check Django cache
    try:
        cached = cache.get(cache_key)
        if cached:
            disk_cache[cache_key] = cached
            return cached
    except Exception:
        pass

    try:
        # MyMemory supports chunks up to 500 chars per query.
        sentences = [s.strip() for s in text.replace("\n", " ").split(". ") if s.strip()]
        chunks = []
        curr_chunk = ""

        for s in sentences:
            sentence = s if s.endswith(".") else s + "."
            if len(curr_chunk) + len(sentence) < 450:
                curr_chunk = f"{curr_chunk} {sentence}".strip()
            else:
                if curr_chunk:
                    chunks.append(curr_chunk)
                curr_chunk = sentence
        if curr_chunk:
            chunks.append(curr_chunk)

        translated_chunks = []
        for chunk in chunks[:5]:
            params = {
                "q": chunk,
                "langpair": f"{source_code}|{target_code}",
            }
            res = requests.get(TRANSLATE_API_URL, params=params, timeout=3.5)
            if res.status_code == 200:
                data = res.json()
                t_chunk = data.get("responseData", {}).get("translatedText")
                if t_chunk and not t_chunk.startswith("MYMEMORY WARNING"):
                    translated_chunks.append(t_chunk)
                else:
                    translated_chunks.append(chunk)
            else:
                translated_chunks.append(chunk)

        result = " ".join(translated_chunks) if translated_chunks else text
        if result and result != text:
            # Save to disk and django cache
            disk_cache[cache_key] = result
            _save_disk_cache()
            try:
                cache.set(cache_key, result, timeout=60 * 60 * 24 * 30)  # 30 days
            except Exception:
                pass
            return result
    except Exception as e:
        logger.debug("Translation failed: %s", e)

    return text

