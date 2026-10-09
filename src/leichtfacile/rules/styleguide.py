"""The style guide for the writer prompt, generated from the rule registry.

German and French come from the `guide` texts of the registered rules, so the prompt
asks for exactly what the checker checks. Italian has no checker rules yet; until it
does, a short fixed guide based on Inclusion Europe's rules is used.

With English instructions (LLM_ENGLISH_PROMPTS, docs/prompts.md "English
instructions"), each rule's guide comes from `ENGLISH_GUIDES`: the same instruction in
English, with the German or French examples word for word.
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
_ENGLISH_HEADER = "Rules for {name}, level {level}:"

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

# The guide of every German and French rule in English, by rule id: one text for all
# levels or one per level, as in the registry. A test keeps the ids, the levels and the
# placeholders in step with the registry.
ENGLISH_GUIDES: dict[str, str | dict[str, str]] = {
    # -- German
    "LEN-01": "Write short sentences: at most {max_words} words per sentence.",
    "LEN-02": {
        "A2": "One statement per sentence. No subordinate clauses: no sentence with weil, "
        "dass, wenn, damit, obwohl, um ... zu or a relative clause. Write two short "
        "sentences instead.",
        "B1": "At most one subordinate clause per sentence. Write two short sentences instead.",
    },
    "LEN-03": "Do you list 3 or more things? Then write a list.",
    "ORD-01": "Word order: first who, then what they do. Example: Sie bekommen einen Brief.",
    "GRAM-01": "No passive voice. Say who does something. Not: Das Formular wird geprüft. "
    "But: Das Amt prüft das Formular.",
    "GRAM-02": "No genitive. Write von + dative: das Auto von meinem Vater.",
    "GRAM-03": "No Konjunktiv (not: würde, hätte, wäre, könnte). Write directly.",
    "GRAM-04": "For the past, use the Perfekt: Sie haben einen Brief bekommen. Not: Sie "
    "bekamen einen Brief.",
    "GRAM-05": "Verbs instead of nouns. Not: Die Anmeldung erfolgt online. But: Sie melden "
    "sich im Internet an.",
    "GRAM-06": "Use pronouns such as er, sie or dieser only when it is clear whom they "
    "mean. Repeat the noun instead.",
    "GRAM-07": "No indirect speech. Write who says what.",
    "NEG-01": "No double negation.",
    "NEG-02": "Write positively when you can: Sie dürfen ... instead of Sie dürfen nicht ...",
    "LEX-01": "Split long words with the Mediopunkt: Prämien·verbilligung, Kranken·kasse. "
    "After the dot, go on in lowercase.",
    "LEX-02": "No abbreviations (not: z. B., bzw., ggf., Art.). CHF, AHV, IV, SBB, WC and "
    "PDF are allowed. Explain other abbreviations.",
    "LEX-03": "Use simple, well-known words. No foreign words and no technical terms. If a "
    "hard word is needed, explain it in the glossary.",
    "LEX-04": "No special characters: no semicolon, no brackets, no & and no / between words.",
    "LEX-05": "No gender characters such as * or :. Write both forms: Mitarbeiterinnen und "
    "Mitarbeiter.",
    "LEX-06": "Address the reader directly with Sie.",
    "LEX-07": "Use everyday words instead of office words: innerhalb von instead of innert, "
    "nach instead of gemäss, wenn nötig instead of gegebenenfalls.",
    "NUM-01": "Write numbers as digits: 2, 3, 12. Only ein and eine are written as words.",
    "NUM-02": "Write large numbers with an apostrophe: 1'500 Franken, 500'000.",
    "NUM-03": "Write a date like this: 4. Februar 2026.",
    "NUM-04": "Write times like this: 9 Uhr or 9.30 Uhr. Time spans like this: 9 Uhr bis 12 Uhr.",
    "NUM-05": "Write a duration like this: 1 Stunde und 30 Minuten.",
    "NUM-06": "Write percent as a word: 10 Prozent.",
    "NUM-07": "Write amounts of money like this: 500 Franken or CHF 500.",
    "NUM-08": "Write phone numbers with spaces: 044 123 45 67.",
    "CH-01": "Swiss spelling: always ss, never ß.",
    "CH-02": "No quotation marks.",
    "CH-03": "Use Swiss words: Velo, parkieren, Trottoir, Spital.",
    # -- French
    "LEN-01-FR": "Write short sentences: at most {max_words} words per sentence.",
    "LEN-02-FR": {
        "A2": "One piece of information per sentence. No subordinate clauses: no sentence "
        "with parce que, que, si, quand, pour que, pour + verb or a relative clause with "
        "qui, que, dont, où. Write 2 short sentences instead.",
        "B1": "At most one subordinate clause per sentence. Write 2 short sentences instead.",
    },
    "LEN-03-FR": "Do you list 3 or more things? Make a list.",
    "GRAM-01-FR": "No passive voice. Say who does what. Not: Le formulaire est contrôlé "
    "par l'office. But: L'office contrôle le formulaire.",
    "GRAM-03-FR": "No subjunctive and no conditional (not: il faudrait, vous pourriez, "
    "pour que vous puissiez). Write directly: vous devez, vous pouvez.",
    "GRAM-04-FR": "Write in the present tense. For the past, use the passé composé: vous "
    "avez reçu une lettre. For the future, use aller + verb: vous allez recevoir une "
    "lettre.",
    "GRAM-05-FR": "Verbs rather than nouns. Not: Le dépôt de la demande s'effectue en "
    "ligne. But: Vous faites la demande sur internet.",
    "GRAM-06-FR": "Use il, elle or celui-ci only when it is clear whom or what you mean. "
    "Otherwise, repeat the noun.",
    "GRAM-07-FR": "No reported speech. Say who says what.",
    "GRAM-08-FR": "No impersonal phrases such as il convient de or il y a lieu de. Say "
    "who must do what: vous devez.",
    "NEG-01-FR": "No double negation (not: ce n'est pas impossible).",
    "NEG-02-FR": "Write positively when you can: vous pouvez ... rather than vous ne "
    "pouvez pas ...",
    "LEX-01-FR": "Avoid long words. Use the short, well-known word.",
    "LEX-02-FR": "No abbreviations (not: p. ex., etc., art.). You may write CHF, AVS, AI "
    "and CFF. Explain other abbreviations.",
    "LEX-03-FR": "Use simple, well-known words. No foreign words and no technical terms. "
    "If a hard word is needed, explain it in the glossary.",
    "LEX-04-FR": "No rare characters: no semicolon, no brackets, no & and no / between words.",
    "LEX-05-FR": "No inclusive writing with dots or brackets (employé·e·s). Write both "
    "forms: les employées et les employés.",
    "LEX-06-FR": "Address the reader directly with vous.",
    "LEX-07-FR": "Use everyday words, not the words of the administration (not: "
    "émolument, moyennant, le cas échéant, dûment).",
    "NUM-01-FR": "Write numbers as digits: 2, 3, 12. Only un and une are written as words.",
    "NUM-02-FR": "Write large numbers with a space: 1 500 francs, 500 000.",
    "NUM-03-FR": "Write a date like this: 4 février 2026.",
    "NUM-04-FR": "Write a time like this: 9 h 00 or 9 h 30. A period like this: de 9 h 00 "
    "à 12 h 00.",
    "NUM-05-FR": "Write a duration like this: 1 heure et 30 minutes.",
    "NUM-06-FR": "Write pour cent in words: 10 pour cent.",
    "NUM-07-FR": "Write amounts like this: 500 francs or CHF 500.",
    "NUM-08-FR": "Write phone numbers with spaces: 022 123 45 67.",
    "CH-03-FR": "If a number is written in words, use the Swiss words: septante, nonante.",
}


def _english_guide(rule_id: str, lang: str, level: str) -> str | None:
    from leichtfacile.rules.base import params_for

    guide = ENGLISH_GUIDES.get(rule_id)
    text = guide.get(level) if isinstance(guide, dict) else guide
    return text.format(**params_for(lang, level).__dict__) if text else None


def style_guide(lang: str, level: str, english: bool = False) -> str:
    """The rules for the writer and repair prompts; with `english`, in English for the
    English instructions (German and French only)."""
    from leichtfacile.rules.base import params_for

    name = LEVEL_NAMES.get(lang, LEVEL_NAMES["de"])[level]
    header = _ENGLISH_HEADER if english else _HEADER.get(lang, _HEADER["de"])
    lines = [header.format(name=name, level=level)]
    if lang in _FIXED:
        params = params_for(lang, level).__dict__
        lines += [f"- {text.format(**params)}" for text in _FIXED[lang]]
        return "\n".join(lines)
    for spec in RULES.values():
        if spec.lang != lang:
            continue
        text = spec.guide_for(level)
        if text and english:
            text = _english_guide(spec.id, lang, level)
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines)
