"""The rules of the language families, declared once (docs/rules.md).

A rule has one id, title, severity and scope whatever the language: the German check
lives in `de.py`, the French one in `fr.py`, the Italian one in `it.py`, and a check
the languages share, with the language's words and patterns in a table, in
`shared.py`. ORD-01, GRAM-02, GRAM-08, CH-01, CH-02 and CH-03 have a German or French
check only, GRAM-09 a French and an Italian one, GRAM-10 an Italian one only. The
facts, layout and readability rules apply to every language and declare themselves
where they are checked (document.py, decision.py, medication.py, layout.py).
"""

from __future__ import annotations

from leichtfacile.rules.base import declare, sev

SENTENCE_KINDS = ("sentence", "list_item")

# -- sentence structure
declare(
    "LEN-01",
    title="At most N words per sentence",
    severity=sev("error"),
    scope="sentence",
    kinds=SENTENCE_KINDS,
)
declare(
    "LEN-02",
    title="One clause per sentence; no subordinate clauses",
    severity=sev("error", "warn"),
    scope="sentence",
    kinds=SENTENCE_KINDS,
)
declare(
    "LEN-03",
    title="Enumerations of three or more items become a list",
    severity=sev("warn"),
    scope="sentence",
    kinds=("sentence",),
)
declare(
    "ORD-01",
    title="Subject - verb - object order",
    severity=sev("info"),
    scope="sentence",
    kinds=("sentence",),
)

# -- grammar
declare("GRAM-01", title="No passive", severity=sev("error", "warn"), scope="sentence")
declare(
    "GRAM-02", title="No genitive; use von + dative", severity=sev("warn", "info"), scope="sentence"
)
declare(
    "GRAM-03",
    title="No Konjunktiv, subjunctive or conditional",
    severity=sev("warn"),
    scope="sentence",
)
declare(
    "GRAM-04",
    title="The tenses of everyday speech: Perfekt, présent and passé composé, passato prossimo",
    severity=sev("warn"),
    scope="sentence",
)
declare("GRAM-05", title="No nominalisations", severity=sev("warn"), scope="sentence")
declare(
    "GRAM-06",
    title="Pronouns only with an unambiguous reference",
    severity=sev("info"),
    scope="sentence",
)
declare("GRAM-07", title="No indirect or reported speech", severity=sev("info"), scope="sentence")
declare(
    "GRAM-08",
    title="Separable verbs split in a main clause: Sie schicken ... mit",
    severity=sev("error", "warn"),
    scope="sentence",
)
declare(
    "GRAM-09",
    title="No impersonal phrases: il convient de, il y a lieu de, si prega di",
    severity=sev("warn"),
    scope="block",
)
declare("GRAM-10", title="No gerund clauses", severity=sev("warn"), scope="sentence")

# -- negation
declare("NEG-01", title="No double negation", severity=sev("error"), scope="sentence")
declare("NEG-02", title="Prefer positive formulation", severity=sev("info"), scope="sentence")

# -- words
declare(
    "LEX-01",
    title="No long words; German compounds get a Mediopunkt, lowercase after the dot",
    severity=sev("warn"),
    scope="sentence",
)
declare("LEX-02", title="No abbreviations except common ones", severity=sev("warn"), scope="block")
declare(
    "LEX-03", title="No foreign words, anglicisms, jargon", severity=sev("info"), scope="sentence"
)
declare("LEX-04", title="Rare punctuation", severity=sev("warn"), scope="block")
declare(
    "LEX-05",
    title="Gender-fair, concrete forms without typographic devices",
    severity=sev("info"),
    scope="block",
)
declare("LEX-06", title="Direct address with Sie, vous or Lei", severity=sev("info"), scope="block")
declare(
    "LEX-07",
    title="Everyday words instead of office words",
    severity=sev("warn", "info"),
    scope="sentence",
)

# -- numbers, dates, times, amounts
declare(
    "NUM-01",
    title="Numbers as digits, except one (ein, eine, un, une, uno, una)",
    severity=sev("warn"),
    scope="sentence",
)
declare(
    "NUM-02",
    title="Thousands separator for numbers of 4+ digits: 500'000 or 500 000",
    severity=sev("warn"),
    scope="block",
)
declare(
    "NUM-03",
    title="Dates with the month as a word: 4. Februar 2020, 4 février 2020, 4 febbraio 2020",
    severity=sev("warn"),
    scope="block",
)
declare(
    "NUM-04",
    title="Times as 9 Uhr or 9.30 Uhr, 9 h 00 or 9 h 30, ore 9.00; ranges with bis, de ... à "
    "or dalle ... alle",
    severity=sev("warn"),
    scope="block",
)
declare(
    "NUM-05",
    title="Durations in words and digits: 1 Stunde und 30 Minuten, 1 heure et 30 minutes, "
    "1 ora e 30 minuti",
    severity=sev("info"),
    scope="block",
)
declare("NUM-06", title="Percent written out", severity=sev("warn"), scope="block")
declare(
    "NUM-07",
    title="Amounts as 500 Franken, 500 francs, 500 franchi or CHF 500",
    severity=sev("info"),
    scope="block",
)
declare("NUM-08", title="Phone numbers spaced: 044 123 45 67", severity=sev("warn"), scope="block")

# -- Swiss usage
declare("CH-01", title="ss, never ß", severity=sev("error"), scope="block")
declare(
    "CH-02",
    title='No « » or „ “; use " sparingly or none',
    severity=sev("info"),
    scope="block",
)
declare(
    "CH-03",
    title="Swiss usage: Helvetisms, and septante or nonante when numbers are written out",
    severity=sev("info"),
    scope="block",
)
