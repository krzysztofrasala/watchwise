from django import template
from movies import i18n

register = template.Library()

@register.filter(name='t')
def translate_key(key: str, lang: str = "PL") -> str:
    """Translate string key based on active language (PL/EN)."""
    return i18n.t(key, lang)


@register.filter(name='genre')
def genre_label(genre, lang: str = "PL") -> str:
    return i18n.genre_name(str(genre), lang)
