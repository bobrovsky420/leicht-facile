"""The style guide for the writer prompt, generated from the rule registry.

The lines are the `guide` texts of the registered rules in the document's language,
so the prompt asks for exactly what the checker checks, for German, French and
Italian alike. The level names follow the federal guides: Leichte Sprache and
Einfache Sprache, FALC and langage clair, lingua facile and linguaggio chiaro.
"""

from __future__ import annotations

from leichtfacile.rules.base import RULES
from leichtfacile.rules.vocabulary import standard_spelling
from leichtfacile.schemas import base_lang
from leichtfacile.senders import address_form

# The Italian names carry their article, because the header says "Regole per la
# lingua facile" and "Regole per il linguaggio chiaro".
LEVEL_NAMES = {
    "de": {"A2": "Leichte Sprache", "B1": "Einfache Sprache"},
    "fr": {"A2": "FALC (facile à lire et à comprendre)", "B1": "langage clair"},
    "it": {"A2": "la lingua facile", "B1": "il linguaggio chiaro"},
}

_HEADER = {
    "de": "Regeln für {name} (Niveau {level}):",
    "fr": "Règles pour le {name}, niveau {level} :",
    "it": "Regole per {name} (livello {level}):",
}


def style_guide(lang: str, level: str, address: str = "formal") -> str:
    """`lang`: a language or a variety key (`de-AT`): the level names are the
    language's, the guides the variety's where a rule has its own. `address`: the form
    of address (schemas.Address); LEX-06's line follows it (senders/senders.toml)."""
    language = base_lang(lang)
    # The guides are written in the Swiss spelling; Germany and Austria read them with the
    # sharp s (rules/data/spelling_de.toml: Grosse Zahlen, gemäss).
    standard = lang.partition("-")[2] in ("DE", "AT")
    name = LEVEL_NAMES.get(language, LEVEL_NAMES["de"])[level]
    lines = [_HEADER.get(language, _HEADER["de"]).format(name=name, level=level)]
    for spec in RULES.values():
        text = spec.guide_for(lang, level)
        if spec.id == "LEX-06" and text and address != "formal":
            text = address_form(address).guide(language)
        if text:
            lines.append(f"- {standard_spelling(text) if standard else text}")
    return "\n".join(lines)
