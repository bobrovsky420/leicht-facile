"""The checks German, French and Italian share: the logic once, the language's words
and patterns in a table (`TABLES`). The checks that differ between the languages stay
in `de.py`, `fr.py` and `it.py`; the rules themselves are declared in `catalog.py`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace

from spacy.tokens import Span

from leichtfacile.rules import de, fr, it
from leichtfacile.rules.base import BlockInfo, Context, Hit, rule
from leichtfacile.rules.messages import hit
from leichtfacile.rules.values import (
    DATE_ISO_RE,
    DATE_NUM_RE,
    DATE_SLASH_RE,
    PHONE_RE,
    URL_RE,
    canonical_date,
    canonical_phone,
    extract_values,
    format_date,
    format_phone,
    format_thousands,
    mask,
    mask_links,
    mask_numbers,
)
from leichtfacile.rules.vocabulary import find_terms, office_words
from leichtfacile.schemas import variety as variety_key
from leichtfacile.senders import address_form

LANGS = ("de", "fr", "it")  # a check registered by language serves every variety of it
# The German varieties (schemas.variety) have tables of their own below and, where the
# writer's instruction differs, a guide of their own; French and Italian have one variety
# each, so their checks are the language's.
GERMAN = ("de-CH", "de-DE", "de-AT")
KEYS = (*GERMAN, "fr", "it")
LEN_TOLERANCE = 3  # words over the limit that are a warning, not an error
RARE_PUNCTUATION_RE = re.compile(r"[;()\[\]{}&]")
BIG_NUMBER_RE = re.compile(r"(?<![\d'.,:/+’])\d{4,}(?![\d'’])")
ACCEPTED_PHONE_RE = re.compile(
    r"0\d{2} \d{3} \d{2} \d{2}|\+41 \d{2} \d{3} \d{2} \d{2}"
    r"|0(?:800|84\d|90\d) (?:\d{3} \d{3}|\d{2} \d{2} \d{2})"
)  # the Zürich easy-language pages write +41 44 123 45 67; that is fine.
# A service number in either usual grouping (0800 123 456, 0848 35 45 55) is fine too.


@dataclass(frozen=True)
class Table:
    """What a shared check needs to know about a language."""

    word_count: Callable[[Span], int]
    slash_re: re.Pattern[str]  # a slash between two words
    slash_words: tuple[str, str]  # the two words that replace it
    role_noun_re: re.Pattern[str]  # the reader named in the third person (LEX-06)
    address: str  # the pronoun that addresses the reader
    office_exclude_re: re.Pattern[str]  # the role nouns LEX-07 leaves to LEX-06
    identifier_before_re: re.Pattern[str]  # words before a number that is no amount
    currency_near_re: re.Pattern[str]
    date_short_re: re.Pattern[str] | None  # a day and month without a year, where it exists
    duration_re: re.Pattern[str]
    percent_word: str
    amount_re: re.Pattern[str]
    currency_word: str


TABLES: dict[str, Table] = {
    "de-CH": Table(
        word_count=de.word_count,
        slash_re=de.SLASH_RE,
        slash_words=("und", "oder"),
        role_noun_re=de.ROLE_NOUN_RE,
        address="Sie",
        office_exclude_re=de.ROLE_NOUN_RE,
        identifier_before_re=de.IDENTIFIER_BEFORE_RE,
        currency_near_re=de.CURRENCY_NEAR_RE,
        date_short_re=None,
        duration_re=de.DURATION_RE,
        percent_word="Prozent",
        amount_re=de.AMOUNT_STYLE_RE,
        currency_word="Franken",
    ),
    "fr-CH": Table(
        word_count=fr.word_count,
        slash_re=fr.SLASH_RE,
        slash_words=("et", "ou"),
        role_noun_re=fr.ROLE_NOUN_RE,
        address="vous",
        office_exclude_re=fr.ROLE_NOUN_WORD_RE,
        identifier_before_re=fr.IDENTIFIER_BEFORE_RE,
        currency_near_re=fr.CURRENCY_NEAR_RE,
        date_short_re=fr.DATE_SHORT_RE,
        duration_re=fr.DURATION_RE,
        percent_word="pour cent",
        amount_re=fr.AMOUNT_STYLE_RE,
        currency_word="francs",
    ),
    "it-CH": Table(
        word_count=it.word_count,
        slash_re=it.SLASH_RE,
        slash_words=("e", "o"),
        role_noun_re=it.ROLE_NOUN_RE,
        address="Lei",
        office_exclude_re=it.ROLE_NOUN_WORD_RE,
        identifier_before_re=it.IDENTIFIER_BEFORE_RE,
        currency_near_re=it.CURRENCY_NEAR_RE,
        date_short_re=it.DATE_SHORT_RE,
        duration_re=it.DURATION_RE,
        percent_word="per cento",
        amount_re=it.AMOUNT_STYLE_RE,
        currency_word="franchi",
    ),
}


# Germany and Austria (29 October 2026): the German table with the euro, the file numbers
# of a Bescheid before a number that is no amount, the amount styles NUM-07 flags there,
# and hyphenated compounds counted as one word. format_thousands and format_date read the
# variety (the thousands dot, Jänner).
for _key in ("de-DE", "de-AT"):
    TABLES[_key] = replace(
        TABLES["de-CH"],
        word_count=de.word_count_joined,
        currency_near_re=de.CURRENCY_NEAR_RE_DE,
        identifier_before_re=de.IDENTIFIER_BEFORE_RE_DE,
        amount_re=de.AMOUNT_STYLE_DE_RE,
        currency_word="Euro",
    )


def table(ctx: Context) -> Table:
    """The table of the text's variety; a variety without one reads as its language's
    Swiss variety."""
    return TABLES.get(ctx.variety) or TABLES[variety_key(ctx.lang)]


# -- sentence structure ------------------------------------------------------------


@rule(
    "LEN-01",
    lang=LANGS,
    guide={
        "de": "Schreibe kurze Sätze: höchstens {max_words} Wörter pro Satz.",
        "fr": "Écris des phrases courtes : au plus {max_words} mots par phrase.",
        "it": "Scrivi frasi corte: al massimo {max_words} parole per frase.",
    },
)
def len_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    n = table(ctx).word_count(sent)
    limit = ctx.params.max_words
    if n > limit:
        # Professional easy-language texts often run a few words over the limit; that is
        # a warning. Far over the limit is an error (calibration, docs/rules.md).
        yield hit(
            "LEN-01",
            words=n,
            limit=limit,
            level=ctx.level,
            evidence=sent.text,
            severity="error" if n > limit + LEN_TOLERANCE else "warn",
        )


# -- words --------------------------------------------------------------------------


@rule(
    "LEX-04",
    lang=LANGS,
    guide={
        "de": "Keine Sonder·zeichen: kein Semikolon, keine Klammern, kein & und kein / "
        "zwischen Wörtern.",
        "fr": "Pas de signes rares : pas de point-virgule, pas de parenthèses, pas de & et "
        "pas de / entre les mots.",
        "it": "Niente segni rari: niente punto e virgola, niente parentesi, niente & e "
        "niente / tra le parole.",
    },
)
def lex_04(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    text = mask_links(block.text)
    seen = set()
    for m in RARE_PUNCTUATION_RE.finditer(text):
        char = {")": "(", "]": "[", "}": "{"}.get(m.group(0), m.group(0))
        if char not in seen:
            seen.add(char)
            yield hit("LEX-04", found=m.group(0), evidence=m.group(0))
    first, second = table(ctx).slash_words
    for m in table(ctx).slash_re.finditer(text):
        word = block.text[max(0, m.start() - 12) : m.end() + 12].strip()
        yield hit("LEX-04.slash", first=first, second=second, evidence=word)


@rule(
    "LEX-06",
    lang=LANGS,
    guide={
        "de": "Sprich die Leserin oder den Leser direkt mit Sie an.",
        "fr": "Parle directement à la lectrice ou au lecteur avec vous.",
        "it": "Rivolgiti direttamente alla lettrice o al lettore con Lei.",
    },
)
def lex_06(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in table(ctx).role_noun_re.finditer(block.text):
        # A text that never addresses the reader gets the reminder with the finding.
        yield hit(
            "LEX-06" if ctx.addresses_reader else "LEX-06.no_address",
            found=m.group(0),
            address=address_form(ctx.address).pronoun(ctx.lang),
            evidence=m.group(0),
        )


@rule(
    "LEX-07",
    lang=KEYS,
    guide={
        "de-CH": "Nimm Alltags·wörter statt Amts·wörtern: innerhalb von statt innert, "
        "nach statt gemäss, wenn nötig statt gegebenenfalls.",
        "de-DE": "Nimm Alltags·wörter statt Amts·wörtern: innerhalb von statt binnen, "
        "nach statt gemäss, wenn nötig statt gegebenenfalls.",
        "de-AT": "Nimm Alltags·wörter statt Amts·wörtern: innerhalb von statt binnen, "
        "nach statt gemäss, wenn nötig statt gegebenenfalls.",
        "fr": "Prends les mots de tous les jours, pas les mots de l'administration (pas : "
        "émolument, moyennant, le cas échéant, dûment).",
        "it": "Usa le parole di tutti i giorni, non le parole dell'amministrazione (non: "
        "istanza, ai sensi di, qualora, debitamente).",
    },
)
def lex_07(sent: Span, ctx: Context) -> Iterator[Hit]:
    # Words of rules/data/vocabulary_<lang>.toml; the role nouns are LEX-06's.
    for m in office_words(find_terms(ctx.variety, sent), exclude=table(ctx).office_exclude_re):
        easy = m.entry.easy or ""
        yield hit("LEX-07", found=m.text, easy=easy, evidence=m.text, suggestion=easy)


# -- numbers, dates, times, amounts -----------------------------------------------


@rule(
    "NUM-02",
    lang=KEYS,
    guide={
        "de-CH": "Grosse Zahlen schreibst du mit Apostroph: 1'500 Franken, 500'000.",
        "de-DE": "Grosse Zahlen schreibst du mit Punkt: 1.500 Euro, 500.000.",
        "de-AT": "Grosse Zahlen schreibst du mit Punkt: 1.500 Euro, 500.000.",
        "fr": "Les grands nombres s'écrivent avec une espace : 1 500 francs, 500 000.",
        "it": "I numeri grandi si scrivono con l'apostrofo: 1'500 franchi, 500'000.",
    },
)
def num_02(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    text = mask_numbers(block.text)
    if ctx.region in ("DE", "AT"):
        # Five-digit postcodes (51103 Köln), the digits of the German phone shapes
        # (0221 / 221-30700) and the spaced insurance numbers (SV-Nummer 1230 140104) are
        # no big numbers; the Swiss masking knows none of them (calibration on the Köln
        # pages, 29 October 2026; the Austrian Bescheid of the evaluation, 30 October).
        values = extract_values(block.text, ctx.variety)
        kinds = ("address", "phone", "identifier")
        text = mask(text, [(v.start, v.end) for v in values if v.kind in kinds])
    for m in BIG_NUMBER_RE.finditer(text):
        digits = m.group(0)
        before, after = text[max(0, m.start() - 14) : m.start()], text[m.end() : m.end() + 12]
        if table(ctx).identifier_before_re.search(before):
            continue
        near = table(ctx).currency_near_re
        currency = bool(near.search(before[-6:]) or near.search(after[:10]))
        if len(digits) == 4 and not currency:
            continue  # years, postal codes and form numbers have 4 digits
        expected = format_thousands(digits, ctx.variety)
        yield hit("NUM-02", found=digits, expected=expected, evidence=digits, suggestion=expected)


@rule(
    "NUM-03",
    lang=KEYS,
    guide={
        "de-CH": "Ein Datum schreibst du so: 4. Februar 2026.",
        "de-DE": "Ein Datum schreibst du so: 4. Februar 2026.",
        "de-AT": "Ein Datum schreibst du so: 4. Jänner 2026.",
        "fr": "Une date s'écrit ainsi : 4 février 2026.",
        "it": "Una data si scrive così: 4 febbraio 2026.",
    },
)
def num_03(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    text = mask(block.text, [m.span() for r in (URL_RE, PHONE_RE) for m in r.finditer(block.text)])
    short = table(ctx).date_short_re
    if short is not None:  # "au 15.09": a day and a month without a year
        for m in short.finditer(text):
            canonical = canonical_date(int(m.group(1)), int(m.group(2)), None)
            if canonical is not None:
                found = m.group(0).split()[-1]
                written = format_date(canonical, ctx.variety)
                yield hit("NUM-03", found=found, evidence=found, suggestion=written)
    for regex, order in ((DATE_ISO_RE, "ymd"), (DATE_NUM_RE, "dmy"), (DATE_SLASH_RE, "dmy")):
        for m in regex.finditer(text):
            if order == "ymd":
                y, mo, d = m.group(1), m.group(2), m.group(3)
            else:
                d, mo, y = m.group(1), m.group(2), m.group(3)
            canonical = canonical_date(int(d), int(mo), int(y) if y else None)
            if canonical is None:
                continue
            yield hit(
                "NUM-03",
                found=m.group(0).strip(),
                evidence=m.group(0).strip(),
                suggestion=format_date(canonical, ctx.variety),
            )


@rule(
    "NUM-05",
    lang=LANGS,
    guide={
        "de": "Eine Dauer schreibst du so: 1 Stunde und 30 Minuten.",
        "fr": "Une durée s'écrit ainsi : 1 heure et 30 minutes.",
        "it": "Una durata si scrive così: 1 ora e 30 minuti.",
    },
)
def num_05(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in table(ctx).duration_re.finditer(block.text):
        yield hit("NUM-05", found=m.group(0), evidence=m.group(0))


@rule(
    "NUM-06",
    lang=LANGS,
    guide={
        "de": "Schreibe Prozent als Wort: 10 Prozent.",
        "fr": "Écris pour cent en lettres : 10 pour cent.",
        "it": "Scrivi per cento in lettere: 10 per cento.",
    },
)
def num_06(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    word = table(ctx).percent_word
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)?\s?%", block.text):
        number = m.group(1)
        yield hit(
            "NUM-06",
            expected=word,
            evidence=m.group(0).strip(),
            suggestion=f"{number} {word}" if number else word,
        )


@rule(
    "NUM-07",
    lang=KEYS,
    guide={
        "de-CH": "Geld·beträge schreibst du so: 500 Franken oder CHF 500.",
        "de-DE": "Geld·beträge schreibst du so: 500 Euro.",
        "de-AT": "Geld·beträge schreibst du so: 500 Euro.",
        "fr": "Les montants s'écrivent ainsi : 500 francs ou CHF 500.",
        "it": "Gli importi si scrivono così: 500 franchi o CHF 500.",
    },
)
def num_07(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in table(ctx).amount_re.finditer(block.text):
        number = re.sub(r"\D", "", next(g for g in m.groups() if g))
        figure = format_thousands(number, ctx.variety) if len(number) > 3 else number
        amount = f"{figure} {table(ctx).currency_word}"
        yield hit(
            "NUM-07", found=m.group(0), expected=amount, evidence=m.group(0), suggestion=amount
        )


@rule(
    "NUM-08",
    lang=KEYS,
    guide={
        "de-CH": "Telefon·nummern schreibst du mit Abständen: 044 123 45 67.",
        "de-DE": "Telefon·nummern schreibst du mit Abständen: 0 55 44 33 22 11.",
        "de-AT": "Telefon·nummern schreibst du mit Abständen: 0 55 44 33 22 11.",
        "fr": "Les numéros de téléphone s'écrivent avec des espaces : 022 123 45 67.",
        "it": "I numeri di telefono si scrivono con gli spazi: 091 123 45 67.",
    },
)
def num_08(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    if ctx.region in ("DE", "AT"):
        # The German and Austrian shapes have no fixed grouping (rules/values.py); the
        # official pages write slashes and hyphens, so only a run of glued digits is a
        # finding, with the Netzwerk's pairs as the suggestion (29 October 2026).
        for value in extract_values(block.text, ctx.variety):
            if value.kind == "phone" and re.fullmatch(r"\+?\d{8,}", value.text):
                grouped = format_phone(value.canonical, ctx.variety)
                yield hit(
                    "NUM-08.grouped",
                    found=value.text,
                    expected=grouped,
                    evidence=value.text,
                    suggestion=grouped,
                )
        return
    for m in PHONE_RE.finditer(block.text):
        number = m.group(0)
        if ACCEPTED_PHONE_RE.fullmatch(number):
            continue
        spaced = format_phone(canonical_phone(number))
        yield hit("NUM-08", found=number, expected=spaced, evidence=number, suggestion=spaced)
