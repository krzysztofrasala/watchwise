from django import template
from movies import i18n

register = template.Library()

@register.filter(name='t')
def translate_key(key: str, lang: str = "PL") -> str:
    """Translate string key based on active language (PL/EN)."""
    return i18n.t(key, lang)
