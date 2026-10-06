"""The style guide for the writer prompt, generated from the rule registry.

German and French come from the `guide` texts of the registered rules, so the prompt
asks for exactly what the checker checks. Italian has no checker rules yet; until it
does, a short fixed guide based on Inclusion Europe's rules is used.
"""

from __future__ import annotations

from leichtfacile.rules.base import RULES

LEVEL_NAMES = {
    "de": {"A2": "Leichte Sprache", "B1": "Einfache Sprache"},
    "fr": {"A2": "FALC (facile à lire et à comprendre)", "B1": "langage clair"},
    "it": {"A2": "lingua facile", "B1": "linguaggio semplice"},
}

_HEADER = {
    "de": "Regeln für {name} (Niveau {level}):",
    "fr": "Règles pour le {name}, niveau {level} :",
    "it": "Regole per la {name} (livello {level}):",
}

_FIXED = {
    "it": [
        "Scriva frasi brevi: al massimo {max_words} parole per frase.",
        "Una sola idea per frase. Niente frasi secondarie.",
        "Niente forma passiva, neanche con si: dica chi fa che cosa.",
        "Niente congiuntivo, niente condizionale, niente passato remoto, niente gerundio.",
        "Parole semplici e conosciute. Spieghi le parole difficili nel glossario.",
        "Niente abbreviazioni, tranne CHF, AVS, AI e FFS.",
        "I numeri in cifre: 2, 3, 12.",
        "Le date così: 4 febbraio 2026. Le ore così: ore 9.00.",
        "Gli importi così: 500 franchi o CHF 500. I grandi numeri: 1'500.",
        "I numeri di telefono con spazi: 091 123 45 67.",
        "Niente parentesi, niente punto e virgola, niente barre tra le parole.",
        "Si rivolga direttamente al lettore con Lei.",
    ],
}


def style_guide(lang: str, level: str) -> str:
    from leichtfacile.rules.base import params_for

    name = LEVEL_NAMES.get(lang, LEVEL_NAMES["de"])[level]
    lines = [_HEADER.get(lang, _HEADER["de"]).format(name=name, level=level)]
    if lang in _FIXED:
        params = params_for(lang, level).__dict__
        lines += [f"- {text.format(**params)}" for text in _FIXED[lang]]
        return "\n".join(lines)
    for spec in RULES.values():
        if spec.lang != lang:
            continue
        text = spec.guide_for(level)
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines)
