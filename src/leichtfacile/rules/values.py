"""Find and normalise checkable values in text: dates, amounts, numbers, phone
numbers, e-mail addresses, URLs, percentages, times, periods, identifiers, postal
addresses, quantities and dosing schemes.

This is the exact half of fact checking (rules.md FACT-01 and FACT-05) and the basis
of the model-independent "hard fact" metric in the evaluation. A value is reduced to
a canonical string, so "31. März 2026", "31.3.2026" and "2026-03-31" are the same
date, "1'500 Franken", "CHF 1500.-" and "1 500.00" the same amount, "30 Tagen",
"dreissig Tage" and "30-tägige" the same period, and "2,5 mg" and "2.5 Milligramm"
the same quantity. A medication name is no pattern (there is no drug list): the fact
sheet gives it as the value of a fact of kind `medication`, and it is searched as
written, case-insensitive, ignoring the Mediopunkt.

The shapes are code; the words a language says (its months, its clock word, its
currency, multiplier and number words, its period units) and the formats of its
varieties are data in rules/data/values_<lang>.toml, read by rules/value_grammar.py:
a text is read with its own language's words alone.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Literal

from leichtfacile.rules.value_grammar import (
    DASHES,
    PERIOD_UNITS,
    QUOTES,
    Grammar,
    grammar_for,
    languages,
)

ValueKind = Literal[
    "date", "amount", "number", "phone", "email", "url", "percent", "time",
    "period", "identifier", "address", "quantity", "schedule", "medication",
]  # fmt: skip
# The kinds a rewrite must keep exactly (plain numbers are not among them). A
# medication is not among them either: no pattern extracts it from a text.
HARD_KINDS: tuple[ValueKind, ...] = (
    "date", "amount", "phone", "email", "url", "percent", "time",
    "period", "identifier", "address", "quantity", "schedule",
)  # fmt: skip

# The month tables of the languages, from their grammars, for callers that list every
# month name (eval/diagnose.py): name or abbreviation to number, and the names written.
MONTHS: dict[str, dict[str, int]] = {lang: grammar_for(lang).months for lang in languages()}
MONTH_NAMES: dict[str, list[str]] = {
    **{lang: list(grammar_for(lang).month_names) for lang in languages()},
    "de-AT": list(grammar_for("de-AT").month_names),
}

EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-zA-Z]{2,}(?![\w-])")
URL_RE = re.compile(
    r"(?:(?:https?://|www\.)[^\s<>()" + QUOTES + r"]+"
    r"|(?<![\w@.-])(?:[a-z0-9-]+\.)+(?:ch|swiss|com|org|net|info|li|eu|de|fr|it)"
    r"(?:/[^\s<>()" + QUOTES + r"]*)?)(?![\w@-])",
    re.IGNORECASE,
)
# Service numbers (free 0800, shared-cost 084x, premium 090x) have ten digits and come
# in two groupings: `0800 123 456` and `0800 33 66 55` (the cantonal emergency pages
# write the hotlines the second way; found 7 October 2026 as four plain numbers).
PHONE_RE = re.compile(
    r"(?<![\d+])(?:"
    r"(?:\+41|0041)[ ./-]?(?:\(0\)[ ]?)?\d{2}[ ./-]?\d{3}[ ./-]?\d{2}[ ./-]?\d{2}"
    r"|0(?:800|84[0-9]|90[0-9])[ ./-]?(?:\d{3}[ ./-]?\d{3}|\d{2}[ ./-]?\d{2}[ ./-]?\d{2})"
    r"|0\d{2}[ ./-]?\d{3}[ ./-]?\d{2}[ ./-]?\d{2}"
    r")(?!\d)"
)
DATE_ISO_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
# 31.3., 31.3.26, 31.3.2026, 31. 3. 2026. A space stands only before a four-digit year (`am
# 1.3. 20 Personen` is a date and a count), and no digit right after a date without a
# year (`Ziffer 3.2.1` is a section of a text, not the 3rd of February).
DATE_NUM_RE = re.compile(
    r"(?<![\d.])(\d{1,2})\.[ ]?(\d{1,2})\.(?:(?:[ ](?=\d{4}(?!\d)))?(\d{4}|\d{2})(?!\d)|(?!\d))"
)
DATE_SLASH_RE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
# The text after a number that the currency, subunit and multiplier words are read in:
# long enough for the longest of them (` di franchi`) and the letter after it.
_AFTER_WINDOW = 16
# German and Austrian numbers have area codes of two to five digits and subscriber
# numbers of three to eight, written with spaces, slashes, hyphens or brackets, never
# with dots: `030 1234567`, `0221 / 12 34 56`, `(05544) 332211`, `0 55 44 33 22 11`,
# `01 53115-0` (Vienna), `+49 30 1234567`, `+43 1 711 00-0`. Seven to thirteen digits in
# the national form (`_phone_de`); PHONE_RE above runs first and takes what it fits. Read
# where the grammar says so (`phone.style = "german"`: the varieties of Germany and
# Austria).
_PHONE_DE_RE = re.compile(
    r"(?<![\w+])(?:(?:\+4[39]|004[39])[ /-]?(?:\(0\)[ ]?)?|\(?0)[\d ()/-]{6,19}\d(?!\w)"
)

# -- identifiers: AHV number, IBAN, postal account, UID, a reference after a keyword ----

_AHV_RE = re.compile(r"(?<!\d)756[. ]?\d{4}[. ]?\d{4}[. ]?\d{2}(?!\d)")
# A Swiss or Liechtenstein IBAN (21 characters), a German one (22) or an Austrian one
# (20), with or without spaces; whatever the variety, a letter may cite any of them.
_IBAN_RE = re.compile(
    r"(?<![A-Z0-9])(?:(?:CH|LI)\d{2}(?:[ ]?[0-9A-Z]{4}){4}[ ]?[0-9A-Z]"
    r"|DE\d{2}(?:[ ]?\d{4}){4}[ ]?\d{2}|AT\d{2}(?:[ ]?\d{4}){4})(?![0-9A-Z])"
)
_POSTAL_ACCOUNT_RE = re.compile(
    r"(?<![\d-])\d{2}[" + DASHES + r"]\d{1,6}[" + DASHES + r"]\d(?![\d-])"
)
_UID_RE = re.compile(r"(?<![\w-])CHE[- ]?\d{3}\.\d{3}\.\d{3}(?!\d)")
# A reference after a keyword: `Referenz 2026-0042`, `Dossier-Nr. 12345`, `Geschäfts·nummer:
# K-4711` (a keyword split by code keeps its Mediopunkt, or its hyphen in Germany and
# Austria: `Geschäfts-Nummer`), `N° de dossier 12345`. Words that
# are identifiers on their own, compounds with -nummer, and words that need Nr. or Nummer;
# up to four small words may stand between keyword and code ("Die Nummer von Ihrem
# Dossier ist 2026-0042"). The value is the code alone.
_REF_KEYWORDS = (
    r"Referenz[·-]?nummern?|Referenz|Ref\.|Dossier[·-]?nummern?|Dossier|Akten[·-]?zeichen|Geschäfts[·-]?zeichen"
    r"|(?:Geschäfts|Kunden|Versicherten|Versicherungs|Policen|Fall|Rechnungs|Vertrags|Betreibungs"
    r"|Verfahrens|Gesuchs|Entscheid|Verfügungs|Mitglieder|Partner|Vorgangs|Konto|Akten|Schaden"
    r"|Steuer|Patienten|Personal|Register|Kontroll|Auftrags|Mandats|Antrags|Bewilligungs|Objekt"
    r"|Zahlungsbefehls|Strafbefehls|Beschwerde|Bedarfsgemeinschafts|Buchungs)"
    r"[·-]?nummern?"
    # Germany and Austria (29 October 2026): the file numbers of a Bescheid and of the
    # tax and social insurance letters.
    r"|Kassen[·-]?zeichen|Geschäfts[·-]?zahl|Akten[·-]?zahl|GZ|Zl\.|BG-Nummer"
    r"|(?:Verfügung|Entscheid|Fall|Police|Rechnung|Vertrag|Gesuch|Betreibung|Verfahren|Urteil"
    r"|Beschluss|Konto|Dossier|Referenz|Geschäft|Akte|Schaden|Steuer|Patient|Register|Auftrag"
    r"|Mandat|Antrag|Bewilligung|Objekt|Zahlungsbefehl|Strafbefehl|Beschwerde|Mahnung)"
    r"s?[ -]?(?:Nr\.?|Nummer)"
    r"|Référence|Réf\.|Riferimento|Rif\.|Incarto|Pratica"
    r"|(?:Numéro|N°|No\.?)[ ](?:de[ ]|du[ ]|d')?(?:référence|dossier|client|cliente|police|contrat"
    r"|facture|cas|décision|assuré|affaire|procédure|membre|compte|sinistre|contribuable"
    r"|patient|poursuite|commandement[ ]de[ ]payer|mandat|objet)"
    r"|(?:Décision|Facture|Contrat|Police|Cas|Affaire|Procédure|Compte|Dossier|Référence|Sinistre"
    r"|Commandement[ ]de[ ]payer|Poursuite|Patient|Mandat|Objet|Rappel)"
    r"[ ]?(?:n°|no\.?|numéro)"
    r"|(?:Numero|N\.|N°)[ ](?:di[ ]|del[ ]|della[ ]|dell')?(?:riferimento|incarto|cliente|polizza"
    r"|contratto|fattura|caso|decisione|procedura|conto|pratica|contribuente|paziente|esecuzione"
    r"|precetto[ ]esecutivo)"
    r"|(?:Decisione|Fattura|Contratto|Polizza|Caso|Procedura|Conto|Incarto|Pratica|Esecuzione"
    r"|Precetto[ ]esecutivo|Paziente)[ ]?(?:n\.|n°|numero)"
)
_REF_FILLER = (
    r"(?:[ ]+(?:ist|lautet|heisst|hat|die|der|das|Ihre?[nmrs]?|unsere?[nmrs]?|von|vom|Nr\.?"
    r"|Nummer|est|votre|notre|le|la|du|de|è|il|vostro|nostro|numero|numéro|n°|no\.?)){0,4}?"
)
# Built from DASHES, so that no dash character stands in the source; a leading hyphen
# in a class is literal, which also keeps "/" from forming a range with the dashes.
_CODE_SEP = "[" + DASHES + "./]"
_REF_CODE = (
    r"(?P<code>(?=(?:[A-Za-z0-9]|"
    + _CODE_SEP
    + r")*\d)[A-Za-z0-9]+(?:"
    + _CODE_SEP
    + r"[A-Za-z0-9]+)*)"
)
_NOT_AFTER_CODE = (
    r"(?![ ]?(?:Tag|Tage|Tagen|Woche|Wochen|Monat|Monate|Monaten|Jahr|Jahre|Jahren|Franken"
    r"|Rappen|Euro|Cent|Prozent|Uhr|Minuten|Stunden|Mal|Seiten|Personen|jours?|semaines?|mois"
    r"|ans?|francs?|heures|giorni|mesi|anni|franchi)(?![\w·]))"
)
# The spaced numbers of German and Austrian insurance and tax letters, after their
# keyword: the Steuer-ID (`12 345 678 901`), the Rentenversicherungsnummer
# (`65 170839 J 003`), the Austrian Sozialversicherungsnummer (`1234 010180`). The
# reference pattern above takes a code up to its first space; these keywords take the
# groups together (29 October 2026). Swiss letters use none of the keywords.
_SPACED_ID_RE = re.compile(
    r"(?<![\w·])(?:Steuer-?ID|IdNr\.?|Steuer·?identifikations·?nummer"
    r"|Sozial·?versicherungs·?nummer|SVNR|SV-Nummer|Renten·?versicherungs·?nummer)"
    r"[ ]*:?[ ]*(?P<code>[\dA-Z]{2,4}(?:[ ][\dA-Z]{1,6}){1,4})(?![\w·])",
    re.IGNORECASE,
)
REFERENCE_RE = re.compile(
    r"(?<![\w·])(?P<keyword>"
    + _REF_KEYWORDS
    + r")"
    + _REF_FILLER
    + r"[ ]*:?[ ]*"
    + _REF_CODE
    + r"(?![\w·])"
    + _NOT_AFTER_CODE,
    re.IGNORECASE,
)
_BARE_CODE_RE = re.compile(
    r"(?=.*\d)(?=.*[" + DASHES + r"A-Za-z/])[A-Za-z0-9]+(?:" + _CODE_SEP + r"[A-Za-z0-9]+)*"
)
_CODE_RE = re.compile(r"(?=.*\d)[A-Za-z0-9]+(?:" + _CODE_SEP + r"[A-Za-z0-9]+)*")
_EXPLICIT_NUMBER = re.compile(r"nr\.?$|nummer|n°|no\.?$|numéro|numero|n\.$")

# -- postal addresses: street and number, Postfach, postcode and place ----------------

_NBSP = chr(0xA0)  # web pages set a no-break space in "St. Gallen" and after a postcode
_SP = "[ " + _NBSP + "]"
_UPPER = r"[A-ZÄÖÜÉÈÀÇ]"
_WORD_CAP = _UPPER + r"(?:[^\W\d_]|[·'’-])*"  # a capitalised word, Mediopunkt allowed
# A street name ends in a street word; an adjective of place or kind may precede it
# (Untere Zollgasse, Alte Landstrasse), never the town or office in front of the
# address (Biel Bahnhofsplatz 2D), which a draft rightly leaves out, nor the surname
# above it in an address block (Lea Muster / Beispielweg 14, Anna Huber / ...).
_STREET_ADJECTIVE = (
    r"(?:Ober|Unter|Hinter|Vorder|Inner|Äusser|Mittler|Nieder|Alt|Neu|Lang|Hoh|Gross|Klein"
    r"|Breit|Schmal|Krumm|Still|Weiss|Schwarz|Rot|Grün)(?:e|er|en|es)"
)
_STREET_DE = (
    r"(?:" + _STREET_ADJECTIVE + _SP + r")?" + _UPPER + r"(?:[^\W\d_]|[·'’-])*?"
    r"(?i:strasse|straße|str\.|weg|gasse|platz|allee|quai|promenade|ring|rain|halde|matte|steig"
    r"|graben|damm|ufer|chaussee|gürtel|kai|lände|zeile)"
)  # the German and Austrian street words since 29 October 2026 (damm, ufer, gürtel, ...)
_STREET_FR_IT = (
    r"(?:Rue|Avenue|Av\.|Chemin|Ch\.|Route|Rte|Place|Boulevard|Bd|Impasse|Allée|Quai|Promenade"
    r"|Via|Viale|Piazza|Piazzale|Corso|Strada|Vicolo|Salita)(?:"
    + _SP
    + r"(?:[^\W\d_]|[·'’-])+){1,4}?"
)
# A house number, with a letter (12a), a range (12-14) or, in Austria, the stair and the
# door after slashes (5/2/7).
_HOUSE = r"(?P<house>\d{1,4}(?:" + _SP + r"?[a-zA-Z](?![^\W\d_])|[-/]\d{1,4}(?:/\d{1,4})?)?)"
_POBOX = (
    r"(?P<pobox>(?:Post·?fach|Case" + _SP + r"postale|CP|Casella" + _SP + r"postale)"
    r"(?:" + _SP + r"\d{1,6})?)"
)
_PLACE = (
    r"(?P<place>(?:(?:St\.|Sankt|Saint|Le|La|Les|Bad)"
    + _SP
    + r"?)?"
    + _WORD_CAP
    + r"(?:/"
    + _WORD_CAP
    + r")?(?:"
    + _SP
    + r"(?:am|an|bei|im|ob|sur|sous|près|de|di)(?:"
    + _SP
    + r"(?:der|la|le))?"
    + _SP
    + _WORD_CAP
    + r")?)"
)
ADDRESS_RE = re.compile(
    r"(?<![\w·'’-])"
    r"(?:(?P<street>"
    + _STREET_DE
    + r"|"
    + _STREET_FR_IT
    + r")"
    + _SP
    + _HOUSE
    + _SP
    + r"*(?:,|[ ](?:in|à|a))?\s*)?"  # a word may stand between the street and the postcode
    r"(?:" + _POBOX + _SP + r"*,?\s*)?"
    r"(?P<ch>(?:CH|D|A)[- ])?(?<!\d)(?P<plz>[1-9]\d{3}|\d{5})"
    + _SP
    + r"+"
    + _PLACE
    + r"(?![\w·'’-])"
)  # five digits are a German postcode: taken where the grammar reads them, elsewhere
# only with a street, a Postfach or the country letter in front (`_address`)
# What may follow a postcode and place that have no street in front: the end, a
# punctuation mark, a line break, a digit (the phone number) or a capitalised word
# (Telefon). A lowercase word means a count ("6000 Stimmberechtigte können ...").
_AFTER_PLACE = re.compile(_SP + r"*(?:[.,;:)!?\n]|[0-9]|[A-ZÄÖÜÉÈÀ]|$)")
# A German noun after a four-digit number is mostly a count, not a place; a web page's
# captions (Photos, Bilder) come right after a box number.
_NOT_A_PLACE_WORDS = (
    "franken rappen prozent personen einwohner einwohnerinnen kinder jugendliche erwachsene "
    "mitarbeitende mitarbeiter mitarbeiterinnen plätze stellen wörter zeichen tage tagen wochen "
    "monate monaten jahre jahren stunden minuten meter kilometer quadratmeter liter kilogramm "
    "gramm euro dollar stück exemplare fahrzeuge haushalte haushalten unterschriften mal punkte "
    "seiten zeilen betriebe firmen unternehmen schüler schülerinnen studierende lernende "
    "gemeinden wohnungen familien menschen leute teilnehmende mitglieder steuerpflichtige "
    "stimmberechtigte anträge gesuche fälle francs photos photo bilder bild video videos "
    "impressum kontakt login suche newsletter download downloads drucken teilen"
)
_NOT_A_PLACE = frozenset(_NOT_A_PLACE_WORDS.split())

# -- quantities and dosing schemes (patient letters, information for study participants)

# A unit as written, with its symbol: a name equals its symbol (Milligramm is mg). The
# list is the one of rules.md; everyday units of length or money are not quantities.
_UNIT_SYMBOLS: dict[str, str] = {
    "mg": "mg", "milligramm": "mg", "milligramme": "mg", "milligrammes": "mg",
    "milligrammi": "mg", "milligrammo": "mg",
    "µg": "µg", "mcg": "µg", "mikrogramm": "µg", "microgramme": "µg", "microgrammes": "µg",
    "microgrammi": "µg",
    "g": "g", "gramm": "g", "gramme": "g", "grammes": "g", "grammi": "g", "grammo": "g",
    "kg": "kg", "kilogramm": "kg", "kilogramme": "kg", "kilogrammes": "kg", "chilogrammi": "kg",
    "chilogrammo": "kg", "kilo": "kg", "kilos": "kg",
    "ml": "ml", "milliliter": "ml", "millilitre": "ml", "millilitres": "ml", "millilitri": "ml",
    "millilitro": "ml",
    "dl": "dl", "deziliter": "dl", "décilitre": "dl", "décilitres": "dl", "decilitri": "dl",
    "decilitro": "dl",
    "l": "l", "liter": "l", "litre": "l", "litres": "l", "litri": "l", "litro": "l",
    "ie": "IE", "i.e.": "IE", "ui": "IE", "u.i.": "IE",  # international units
    "tropfen": "Tropfen", "goutte": "Tropfen", "gouttes": "Tropfen", "goccia": "Tropfen",
    "gocce": "Tropfen",
    "tablette": "Tablette", "tabletten": "Tablette", "comprimé": "Tablette",
    "comprimés": "Tablette", "compressa": "Tablette", "compresse": "Tablette",
    "kapsel": "Kapsel", "kapseln": "Kapsel", "gélule": "Kapsel", "gélules": "Kapsel",
    "capsule": "Kapsel", "capsules": "Kapsel", "capsula": "Kapsel",
    "hub": "Hub", "hübe": "Hub", "bouffée": "Hub", "bouffées": "Hub", "spruzzo": "Hub",
    "spruzzi": "Hub",
    "°c": "°C", "° c": "°C", "grad": "°C", "grad celsius": "°C", "degré": "°C",
    "degrés": "°C", "gradi": "°C", "grado": "°C",
    "mmhg": "mmHg", "mmol/l": "mmol/l", "mg/dl": "mg/dl", "mg/kg": "mg/kg",
}  # fmt: skip
_FRACTIONS = {"½": "0.5", "¼": "0.25", "¾": "0.75"}
_QUANTITY_UNITS = "|".join(re.escape(u) for u in sorted(_UNIT_SYMBOLS, key=len, reverse=True))
_QUANTITY_RE = re.compile(
    r"(?<![" + DASHES + r"\d.,'’/])(?P<num>\d+(?:[.,]\d+)?[½¼¾]?|[½¼¾])" + _SP + r"?"
    r"(?P<unit>" + _QUANTITY_UNITS + r")(?![\w·/])",
    re.IGNORECASE,
)
# A dosing scheme: three or four doses for the times of day, 1-0-1 or 1-0-0-1, also
# with halves (½-0-½, 1.5-0-1).
_DOSE_PART = r"(?:[0-9][.,]5|[0-9]|[½¼¾])"
_SCHEDULE_RE = re.compile(
    r"(?<!["
    + DASHES
    + r"\w.,/])(?P<parts>"
    + _DOSE_PART
    + r"(?:[ ]?["
    + DASHES
    + r"][ ]?"
    + _DOSE_PART
    + r"){2,3})(?!["
    + DASHES
    + r"\w/])(?![.,]\d)"
)


@dataclass(frozen=True)
class Value:
    kind: ValueKind
    canonical: str
    text: str = ""  # the surface form found
    start: int = -1
    end: int = -1

    @property
    def key(self) -> tuple[str, str]:
        return (self.kind, self.canonical)


# -- canonical forms ---------------------------------------------------------------


def canonical_date(day: int, month: int, year: int | None) -> str | None:
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    if year is not None and year < 100:
        year += 2000
    return f"{year:04d}-{month:02d}-{day:02d}" if year else f"--{month:02d}-{day:02d}"


def canonical_number(
    integer: str, decimals: str | None = None, seps: str | None = None
) -> str | None:
    """`seps`: the character class of the thousands separators the integer may carry,
    the Swiss ones by default (the grammar's `numbers.thousands`)."""
    digits = re.sub(seps or grammar_for("de").thousands_class, "", integer)
    if not digits.isdigit():
        return None
    try:
        value = Decimal(digits + ("." + decimals if decimals and decimals.isdigit() else ""))
    except InvalidOperation:
        return None
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def mask_links(text: str) -> str:
    """The text with its web and e-mail addresses masked (the rules on words skip them)."""
    text = mask(text, [m.span() for m in URL_RE.finditer(text)])
    return mask(text, [m.span() for m in EMAIL_RE.finditer(text)])


def mask_numbers(text: str) -> str:
    """The text with its addresses, phone numbers, dates and IBANs masked, for the rules
    on the plain numbers that remain."""
    spans = [m.span() for r in (URL_RE, EMAIL_RE, PHONE_RE) for m in r.finditer(text)]
    spans += [m.span() for r in (DATE_ISO_RE, DATE_NUM_RE, DATE_SLASH_RE) for m in r.finditer(text)]
    spans += [m.span() for m in re.finditer(r"\b(?:CH|LI|DE|AT)\d{2}(?:\s?[\dA-Z]{4}){4,7}", text)]
    return mask(text, spans)


def after_currency(text: str, start: int, lang: str = "de") -> bool:
    """Whether a currency stands right before `start`: `CHF 20`, `Fr. 3.10.`, but not the
    Friday of `Mo.-Fr. 8.00` (the language's weekday abbreviations)."""
    g = grammar_for(lang)
    before = text[max(0, start - 16) : start]
    m = g.currency_before_re.search(before)
    if m is None:
        return False
    weekday = g.weekday_before_re
    return not (
        m.group(0).startswith("Fr") and weekday is not None and weekday.search(before[: m.start()])
    )


def amount_range(text: str, start: int, end: int, lang: str = "de") -> bool:
    """Whether the range of decimals from `start` to `end` is one of amounts, not of times
    (NUM-04): a currency right before or after it, `CHF 1.50-2.50 pro Stück`, `1.50-2.50
    Franken`."""
    g = grammar_for(lang)
    after = text[end : end + _AFTER_WINDOW]
    return after_currency(text, start, lang) or bool(
        g.currency_after_re.search(after) or (g.subunit_re and g.subunit_re.search(after))
    )


def canonical_phone(text: str) -> str:
    """The national digits: +41, +43 and +49 (and 0041, ...) become the leading 0."""
    stripped = text.strip()
    digits = re.sub(r"\D", "", stripped.replace("(0)", ""))
    if digits.startswith(("0041", "0043", "0049")):
        digits = "0" + digits[4:]
    elif stripped.startswith(("+41", "+43", "+49")):
        digits = "0" + digits[2:]
    return digits


def _phone_de(m: re.Match[str]) -> str | None:
    """A German or Austrian number: seven to thirteen national digits, at least one pair
    of digits together, and no separator doubled up once the spaces around a slash, a
    hyphen or a bracket are taken away (`0221 / 221-30700` and `0 55 44 - 33 22 11`
    pass, a column of single digits does not)."""
    text = m.group(0)
    compact = re.sub(r" ?([()/-]) ?", r"\1", text)
    if re.search(r"[ ()/-]{2,}", compact) or text.count("(") != text.count(")"):
        return None
    if not re.search(r"\d{2}", text):
        return None
    digits = canonical_phone(text)
    return digits if 7 <= len(digits) <= 13 else None


def canonical_url(text: str) -> str:
    url = text.strip().rstrip(".,;:!?)").lower()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    return url.rstrip("/")


def format_date(canonical: str, lang: str = "de") -> str:
    """Render a canonical date the way easy language writes it: 4. Februar 2020, 4
    février 2020, 1er mars; `lang` may be a variety key (`de-AT`: 4. Jänner 2020)."""
    m = re.fullmatch(r"(\d{4}|-)-(\d{2})-(\d{2})", canonical)
    if not m:
        return canonical
    g = grammar_for(lang)
    year = None if m.group(1) == "-" else int(m.group(1))
    month, day = int(m.group(2)), int(m.group(3))
    day_text = g.first_day if day == 1 and g.first_day else g.day_format.format(day=day)
    out = f"{day_text} {g.month_names[month - 1]}"
    return f"{out} {year}" if year else out


# Service numbers have their own grouping (0800 123 456, 0848 35 45 55, 0900 ...). Not
# every number starting with 08 or 09 is one: 081 is Graubünden, 091 Ticino.
_SERVICE_PHONE_RE = re.compile(r"0(?:800|84\d|90\d)")


def format_phone(canonical: str, lang: str = "de") -> str:
    """0441234567 -> 044 123 45 67; a service number 0800123456 -> 0800 123 456. In the
    German and Austrian varieties the digits go in pairs after the leading 0, as the
    Netzwerk Leichte Sprache writes them (`0 55 44 33 22 11`, rule Z8); the area code
    is not known, so an odd count ends in a group of three."""
    digits = re.sub(r"\D", "", canonical)
    if grammar_for(lang).german_phones and 7 <= len(digits) <= 13:
        rest = digits[1:]
        groups = [rest[i : i + 2] for i in range(0, len(rest) - len(rest) % 2, 2)]
        if len(rest) % 2:
            groups[-1] += rest[-1]
        return " ".join([digits[0], *groups])
    if len(digits) == 10 and _SERVICE_PHONE_RE.match(digits):
        return f"{digits[:4]} {digits[4:7]} {digits[7:]}"
    if len(digits) == 10:
        return f"{digits[:3]} {digits[3:6]} {digits[6:8]} {digits[8:]}"
    return canonical


def format_thousands(canonical: str, lang: str = "de") -> str:
    """500000 -> 500'000 (Swiss German, Italian), 500 000 (French), 500.000 (Germany and
    Austria, where the decimals take a comma: 20,50): the grammar's `writes_thousands`
    and `writes_decimal`."""
    g = grammar_for(lang)
    integer, _, decimals = canonical.partition(".")
    groups: list[str] = []
    while len(integer) > 3:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    groups.insert(0, integer)
    out = g.writes_thousands.join(groups)
    return f"{out}{g.writes_decimal}{decimals}" if decimals else out


def period_parts(canonical: str) -> tuple[int, str]:
    """ "30d" -> (30, "d"); units d, w, m, y, wd."""
    m = re.fullmatch(r"(\d+)(wd|d|w|m|y)", canonical)
    if not m:
        raise ValueError(f"not a period: {canonical!r}")
    return int(m.group(1)), m.group(2)


def format_period(canonical: str, lang: str = "de") -> str:
    """ "30d" -> 30 Tage, "1y" -> 1 Jahr, "5wd" -> 5 jours ouvrables (French)."""
    count, unit = period_parts(canonical)
    one, many = grammar_for(lang).period_names[unit]
    return f"{count} {one if count == 1 else many}"


def format_identifier(canonical: str) -> str:
    """An IBAN in groups of four; every other identifier as it is."""
    if re.fullmatch(r"(?:CH|LI)\d{2}[0-9A-Z]{17}|DE\d{20}|AT\d{18}", canonical):
        return " ".join(canonical[i : i + 4] for i in range(0, len(canonical), 4))
    return canonical


def format_address(canonical: str) -> str:
    """ "Gerichtsstrasse 12||8000 Musterwil" -> Gerichtsstrasse 12, 8000 Musterwil."""
    return ", ".join(part for part in canonical.split("|") if part)


def number_word(word: str, lang: str = "de") -> int | None:
    """The number a word of the language names: dreissig -> 30, einundzwanzig -> 21,
    vingt-cinq -> 25, ventuno -> 21, duecento -> 200; None for a word that is none."""
    return grammar_for(lang).number_word(word)


# -- extraction ----------------------------------------------------------------------


def mask(text: str, spans: Iterable[tuple[int, int]]) -> str:
    """Replace the spans with spaces, keeping all offsets valid."""
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " "
    return "".join(chars)


def extract_values(text: str, lang: str = "de") -> list[Value]:  # noqa: C901, PLR0915
    """All values in the text, in order of appearance, without overlaps. Each kind is
    taken from the text with the earlier kinds masked, so an IBAN is never also a
    phone number and the count of a period never also a plain number. `lang` is a
    language or a variety key, whose grammar (rules/data/values_<lang>.toml) gives the
    words: the month, time, percent, currency, multiplier and number words and the
    period units are the language's alone, and the number format, the phone shapes and
    the five-digit postcodes the variety's (`de-DE`, `de-AT`: the thousands dot and the
    decimal comma)."""
    found: list[Value] = []
    masked = text
    g = grammar_for(lang)

    def take(
        kind: ValueKind, pattern: re.Pattern[str], canon, trim: str = "", group: int | str = 0
    ) -> None:
        nonlocal masked
        spans = []
        for m in pattern.finditer(masked):
            canonical = canon(m)
            if canonical is None:
                continue
            start, end = m.span(group)  # the value may be one group of a larger match
            while trim and end > start and text[end - 1] in trim:
                end -= 1  # a sentence-final dot is not part of a URL
            found.append(Value(kind, canonical, text[start:end], start, end))
            spans.append((start, end))
        masked = mask(masked, spans)

    take("email", EMAIL_RE, lambda m: m.group(0).lower())
    take("url", URL_RE, lambda m: canonical_url(m.group(0)), trim=".,;:!?")
    take("identifier", _IBAN_RE, lambda m: m.group(0).replace(" ", "").upper())
    take("identifier", _AHV_RE, lambda m: canonical_ahv(m.group(0)))
    take("identifier", _POSTAL_ACCOUNT_RE, lambda m: re.sub("[" + DASHES + "]", "-", m.group(0)))
    take("identifier", _UID_RE, lambda m: "CHE-" + m.group(0)[-11:])
    take("identifier", _SPACED_ID_RE, _spaced_id, group="code")
    take("identifier", REFERENCE_RE, _reference, group="code")
    take("schedule", _SCHEDULE_RE, _schedule)
    take("quantity", _QUANTITY_RE, _quantity)  # before addresses: "1000 IE" is no postcode
    take("address", ADDRESS_RE, lambda m: _address(m, g))
    take("phone", PHONE_RE, lambda m: canonical_phone(m.group(0)))
    if g.german_phones:
        take("phone", _PHONE_DE_RE, _phone_de)
    take(
        "date",
        DATE_ISO_RE,
        lambda m: canonical_date(int(m.group(3)), int(m.group(2)), int(m.group(1))),
    )
    spans = []
    for m in g.date_range_re.finditer(masked):  # before the single dates, which it holds
        month = g.month(m.group(3))
        if month is None:
            continue
        year = int(m.group(4)) if m.group(4) else None
        for group in (1, 2):
            canonical = canonical_date(int(re.sub(r"\D", "", m.group(group)) or "1"), month, year)
            if canonical is not None:
                start, end = m.start(group), m.end() if group == 2 else m.end(group)
                found.append(Value("date", canonical, text[start:end], start, end))
        spans.append(m.span())
    masked = mask(masked, spans)
    take("date", g.date_text_re, lambda m: _text_date(m, g))
    take("date", DATE_NUM_RE, lambda m: numeric_date(m, lang))
    take(
        "date",
        DATE_SLASH_RE,
        lambda m: canonical_date(int(m.group(1)), int(m.group(2)), int(m.group(3))),
    )
    take("percent", g.percent_re, lambda m: canonical_number(*_split_decimal(m.group(1))))
    spans = []
    for pattern in g.time_range_res:
        for m in pattern.finditer(masked):
            for h, mi in ((1, 2), (3, 4)):
                hour, minute = int(m.group(h)), int(m.group(mi))
                if hour <= 24 and minute <= 59:
                    start, end = m.start(h), m.end(mi)
                    found.append(
                        Value("time", f"{hour:02d}:{minute:02d}", text[start:end], start, end)
                    )
            spans.append(m.span())
    masked = mask(masked, spans)
    take("time", g.time_re, lambda m: _time(m, g))
    take("period", g.period_re, lambda m: _period(m, g))

    numbers = (_number(m, text, g) for m in g.number_re.finditer(masked))
    found.extend(value for value in numbers if value is not None)
    found.sort(key=lambda v: v.start)
    return found


def _number_parts(m: re.Match[str], dot_decimals: bool) -> tuple[str, str | None, str | None]:
    """The integer, the separator and the decimals of a number match; with `dot_decimals`
    (Germany, Austria) the pattern has a second pair of groups for a dotted decimal."""
    if not dot_decimals or m.group(2):
        return m.group(1), m.group(2), m.group(3)
    return m.group(1), m.group(4), m.group(5)


def _number(m: re.Match[str], text: str, g: Grammar) -> Value | None:
    """An amount or a plain number, with the multiplier after it (`1,5 Mio.`) and in
    francs when its unit is a hundredth (`70 Rappen` is 0.7)."""
    integer, _, decimals = _number_parts(m, g.dot_decimals)
    dash_decimals = bool(decimals and not decimals.isdigit())  # "500.-" is 500
    canonical = canonical_number(integer, None if dash_decimals else decimals, g.thousands_class)
    if canonical is None:
        return None
    end = m.end()
    if g.multiplier_re and (multiplier := g.multiplier_re.match(text[end : end + 12])):
        canonical = _scaled(canonical, g.multiplier(multiplier.group("word")))
        end += multiplier.end()
    after = text[end : end + _AFTER_WINDOW]
    hundredths = bool(g.subunit_re and g.subunit_re.search(after))
    if hundredths:
        canonical = _scaled(canonical, Decimal("0.01"))
    is_amount = (
        dash_decimals
        or hundredths
        or after_currency(text, m.start(), g.key)
        or bool(g.currency_after_re.search(after))
    )
    kind: ValueKind = "amount" if is_amount else "number"
    return Value(kind, canonical, text[m.start() : end], m.start(), end)


def _scaled(canonical: str, factor: int | Decimal) -> str:
    """1.5 by a million is 1500000, 70 by a hundredth 0.7."""
    return format((Decimal(canonical) * factor).normalize(), "f")


def _split_decimal(number: str) -> tuple[str, str | None]:
    integer, _, decimals = number.replace(",", ".").partition(".")
    return integer, decimals or None


def _text_date(m: re.Match[str], g: Grammar) -> str | None:
    day_text = re.sub(r"\D", "", m.group(1)) or "1"
    month = g.month(m.group(2))
    if month is None:
        return None
    year = int(m.group(3)) if m.group(3) else None
    return canonical_date(int(day_text), month, year)


def numeric_date(m: re.Match[str], lang: str = "de") -> str | None:
    """The date of a DATE_NUM_RE match; none without a year after a currency, where the
    dots are those of a price and the sentence: `Das kostet Fr. 3.10.`"""
    year = int(m.group(3)) if m.group(3) else None
    if year is None and after_currency(m.string, m.start(), lang):
        return None
    return canonical_date(int(m.group(1)), int(m.group(2)), year)


def _time(m: re.Match[str], g: Grammar) -> str | None:
    """A dotted hour without the clock word (`9.00`) counts only with a colon or with one
    of the grammar's time words before it (Italian `ore 9.00`, `dalle 8.00`): otherwise
    it is an amount or a decimal (`1.50`, the German `für alle 3.50 Franken`)."""
    groups = m.groupdict()
    if groups.get("h1"):
        hour, minute = int(groups["h1"]), int(groups["m1"])
        text = m.group(0)
        clock = bool(g.clock_word) and g.clock_word in text
        word = text.lower().startswith(tuple(w.lower() for w in g.time_prefix_words))
        if not clock and ":" not in text and not word:
            return None
    elif groups.get("h2"):
        hour, minute = int(groups["h2"]), int(groups.get("m2") or 0)
    elif groups.get("h3"):
        hour, minute = int(groups["h3"]), 0
    elif groups.get("h4"):
        hour, minute = int(groups["h4"]), 0
    else:
        return None
    if hour > 24 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _period(m: re.Match[str], g: Grammar) -> str | None:
    num = m.group("num")
    count = int(num) if num.isdigit() else g.number_word(num)
    if count is None:
        return None  # "pro Tag", "Montag": no count in front of the unit
    if g.frequency_re and g.frequency_re.match(m.string, m.end()):
        return None  # "an vier Tagen pro Woche": how often, not how long
    unit = next(u for u in PERIOD_UNITS if m.groupdict().get(u))
    return f"{count}{unit}"


def canonical_ahv(text: str) -> str:
    """756.1234.5678.97 for the dotted, spaced or bare 13 digits."""
    digits = re.sub(r"\D", "", text)
    return f"{digits[:3]}.{digits[3:7]}.{digits[7:11]}.{digits[11:]}"


def _dose_number(text: str) -> str | None:
    """2,5 -> 2.5, ½ -> 0.5, 1½ -> 1.5; the decimal comma and point are the same."""
    if text in _FRACTIONS:
        return _FRACTIONS[text]
    whole, fraction = (text[:-1], text[-1]) if text[-1] in _FRACTIONS else (text, "")
    number = canonical_number(*_split_decimal(whole))
    if number is None:
        return None
    if fraction:
        number = format((Decimal(number) + Decimal(_FRACTIONS[fraction])).normalize(), "f")
    return number


def _quantity(m: re.Match[str]) -> str | None:
    number = _dose_number(m.group("num"))
    if number is None:
        return None
    return f"{number} {_UNIT_SYMBOLS[m.group('unit').lower()]}"


def _schedule(m: re.Match[str]) -> str | None:
    parts = re.split("[" + DASHES + "]", m.group("parts").replace(" ", ""))
    numbers = [_dose_number(p) for p in parts]
    return None if None in numbers else "-".join(n for n in numbers if n is not None)


def _spaced_id(m: re.Match[str]) -> str:
    """The groups of a Steuer-ID or an insurance number as one code: `12 345 678 901`."""
    return m.group("code").replace(" ", "").upper()


def _reference(m: re.Match[str]) -> str | None:
    """The code after a keyword, with plain hyphens. After a bare keyword (`Dossier`,
    `Referenz`) a one- or two-digit code is a count, not a reference."""
    code = m.group("code")
    explicit = _EXPLICIT_NUMBER.search(m.group("keyword").lower()) or ":" in m.group(0)
    if code.isdigit() and len(code) < 3 and not explicit:
        return None
    return re.sub("[" + DASHES + "]", "-", code)


def _clean(text: str) -> str:
    return " ".join(text.replace("·", "").split())


def _address(m: re.Match[str], g: Grammar) -> str | None:
    """street number|Postfach|postcode place; empty parts for what the text lacks. A
    postcode without a street, Postfach or CH- in front counts only after a boundary
    (line start, comma, colon) and never in 1900-2099 (a year followed by a noun). A
    five-digit postcode is German: taken as it stands where the grammar reads them
    (`five_digit_postcodes`), elsewhere only with a street, a Postfach or `D-` in front."""
    plz, place = m.group("plz"), m.group("place")
    strong = bool(m.group("street") or m.group("pobox") or m.group("ch"))
    if len(plz) == 5 and not (g.five_digit_postcodes or strong):
        return None
    if place.split()[0].lower().replace("·", "") in _NOT_A_PLACE:
        return None
    if not m.group("street") and not _AFTER_PLACE.match(m.string[m.end() :]):
        return None  # a count, or a box number and the next sentence
    if not strong:
        if len(plz) == 4 and 1900 <= int(plz) <= 2099:
            return None
        before = m.string[: m.start()].rstrip(" " + _NBSP)
        if before and before[-1] not in ",:;(\n":
            return None
        if g.currency_before_re.search(before):
            return None
    street = ""
    if m.group("street"):
        street = _clean(f"{m.group('street')} {m.group('house')}")
        street = re.sub(r"[ ](?:in|à|a)$", "", street)  # the word before the postcode
        street = re.sub(r"(?i)str\.(?=[ ])", g.street_word, street)
    pobox = _clean(m.group("pobox")) if m.group("pobox") else ""
    return f"{street}|{pobox}|{plz} {_clean(place)}"


# -- medication names (patient letters) --------------------------------------------

# The units of a dose, as opposed to a measurement (`38,5 Grad`, `120 mmHg`) or an
# everyday amount (`2 Liter`, `5 kg`): what FACT-09 keeps next to a medication's name.
DOSE_UNITS = frozenset(
    {"mg", "µg", "g", "ml", "IE", "Tropfen", "Tablette", "Kapsel", "Hub", "mg/kg"}
)
# Words for the form of a medication, which the fact sheet's name leaves out: the 8B
# writes `Dafalgan 500 mg Tabletten` where the name is `Dafalgan`.
_FORM_WORDS = re.compile(
    r"(?<![\w·])(?:(?:Film|Brause|Retard|Lutsch|Kau|Schmelz)?Tabletten?|Kapseln?|Dragées?"
    r"|Tropfen|Sirup|Saft|Salbe|Creme|Gel|Spray|Pflaster|Zäpfchen|Injektion(?:en)?|Ampullen?"
    r"|Inhalation|Lösung|Suspension|comprimés?(?:[ ](?:pelliculés?|effervescents?))?|gélules?"
    r"|capsules?|gouttes|sirop|pommade|crème|patch|suppositoires?|solution|injection"
    r"|compress[ae]|capsul[ae]|gocce|sciroppo|pomata|cerotto|supposte?|soluzione|iniezione)"
    r"(?![\w·])",
    re.IGNORECASE,
)


def medication_name(value_norm: str) -> str | None:
    """The name in a medication fact's value, without the dose, scheme, strength, form
    or a part in brackets that the model added: `Dafalgan 500 mg Tabletten (Paracetamol)`
    is `Dafalgan`. None when no word is left."""
    name = re.sub(r"\([^)]*\)", " ", value_norm)
    name = _SCHEDULE_RE.sub(" ", name)
    name = _QUANTITY_RE.sub(" ", name)
    name = _FORM_WORDS.sub(" ", name)
    name = " ".join(name.split()).strip(" ,;:." + DASHES)
    name = re.sub(r"(?:[ ]\d+(?:[.,]\d+)?)+$", "", name)  # a strength without its unit
    return name if re.search(r"[^\W\d_]", name) else None


@lru_cache(maxsize=256)
def _name_pattern(canonical: str) -> re.Pattern[str]:
    """A name as a word or words of a text, any case, a Mediopunkt between any letters."""
    words = ["·?".join(re.escape(c) for c in word) for word in canonical.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)


def find_medication(target: Value, text: str) -> list[Value]:
    """The places where a text names the medication."""
    return [
        Value("medication", target.canonical, m.group(0), m.start(), m.end())
        for m in _name_pattern(target.canonical).finditer(text)
    ]


# -- normalised fact values --------------------------------------------------------


def parse_value_norm(  # noqa: C901
    value_norm: str | None, fact_kind: str = "other", lang: str = "de"
) -> Value | None:
    """Interpret a fact sheet's value_norm; None when code cannot check it."""
    if not value_norm or not value_norm.strip():
        return None
    raw = value_norm.strip()
    if fact_kind == "medication":
        name = medication_name(raw)
        if name is None:
            return None
        return Value("medication", " ".join(name.replace("·", "").lower().split()), name)
    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw):
        canonical = canonical_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        return Value("date", canonical) if canonical else None
    if m := re.fullmatch(r"--(\d{2})-(\d{2})", raw):
        canonical = canonical_date(int(m.group(2)), int(m.group(1)), None)
        return Value("date", canonical) if canonical else None
    if m := re.fullmatch(r"(\d{1,2}):(\d{2})", raw):
        return Value("time", f"{int(m.group(1)):02d}:{m.group(2)}")
    if re.fullmatch(r"(?:\+|00)?\d{9,13}", raw.replace(" ", "")) and raw.lstrip("+").startswith(
        ("0", "41", "43", "49")
    ):
        return Value(
            "phone", canonical_phone("+" + raw if raw.startswith(("41", "43", "49")) else raw)
        )
    if fact_kind == "identifier" and _CODE_RE.fullmatch(raw) and not raw.isdigit():
        # A dotted or lettered code the model names as an identifier (`482.317.556`,
        # `TIC-9988`) is one; its first digits are no plain number (12 October 2026).
        return Value("identifier", re.sub("[" + DASHES + "]", "-", raw))
    values = extract_values(raw, lang)
    if not values:
        return None
    value = values[0]
    if value.kind == "number":
        if fact_kind == "amount":
            return Value("amount", value.canonical)
        if _BARE_CODE_RE.fullmatch(raw):
            # A code without its keyword (2026-0042, K-4711) is a reference, not the
            # plain number its first digits make.
            return Value("identifier", re.sub("[" + DASHES + "]", "-", raw))
    return Value(value.kind, value.canonical)


def _period_length(canonical: str) -> tuple[str, int]:
    """A period in days, months or working days: 2w is 14 days, 1y 12 months."""
    count, unit = period_parts(canonical)
    if unit == "wd":
        return ("wd", count)
    if unit in ("d", "w"):
        return ("d", count * (7 if unit == "w" else 1))
    return ("m", count * (12 if unit == "y" else 1))


def _address_matches(target: Value, candidate: Value) -> bool:
    """Postcode and place must agree; street and Postfach only when the target has them
    (an address without its street is a loss, a street the source lacks an invention)."""
    if candidate.kind != "address":
        return False
    # casefold: `Musterstraße 1` and `Musterstrasse 1` are one street (ß folds to ss)
    t_street, t_pobox, t_place = target.canonical.casefold().split("|")
    c_street, c_pobox, c_place = candidate.canonical.casefold().split("|")
    if t_place != c_place or (t_street and t_street != c_street):
        return False
    return not t_pobox or c_pobox.startswith(t_pobox)


def matches(target: Value, candidate: Value) -> bool:  # noqa: C901
    """Whether a value found in a text is the fact's value."""
    if target.kind == "date":
        if candidate.kind != "date":
            return False
        t_year, c_year = target.canonical[:4], candidate.canonical[:4]
        # A text date without a year still keeps the fact (Bis 31. März ...).
        same_day = target.canonical[-5:] == candidate.canonical[-5:]
        return same_day and ("-" in (t_year[0], c_year[0]) or t_year == c_year)
    if target.kind in ("amount", "number"):
        if candidate.kind == "period":
            # A fact "30" written as "30 Tage", or a plain number the draft gives a unit.
            return target.kind == "number" and str(period_parts(candidate.canonical)[0]) == (
                target.canonical
            )
        if candidate.kind == "identifier":
            return target.kind == "number" and candidate.canonical == target.canonical
        if candidate.kind == "quantity":
            # A fact "2" written as "2 Tabletten"; the unit the other way round is a loss.
            return target.kind == "number" and candidate.canonical.split(" ")[0] == (
                target.canonical
            )
        return candidate.kind in ("amount", "number") and candidate.canonical == target.canonical
    if target.kind == "period":
        if candidate.kind == "period":
            return _period_length(target.canonical) == _period_length(candidate.canonical)
        # "Kinder bis 16 Jahre" survives as "Kinder unter 16": the count alone passes.
        return candidate.kind == "number" and candidate.canonical == str(
            period_parts(target.canonical)[0]
        )
    if target.kind == "identifier":
        if candidate.kind == "identifier":
            return candidate.canonical == target.canonical
        return candidate.kind == "number" and candidate.canonical == target.canonical
    if target.kind == "address":
        return _address_matches(target, candidate)
    return candidate.kind == target.kind and candidate.canonical == target.canonical


def find_value(target: Value, text: str, lang: str = "de") -> list[Value]:
    if target.kind == "medication":
        return find_medication(target, text)
    return [v for v in extract_values(text, lang) if matches(target, v)]


def contains(target: Value, text: str, values: Iterable[Value]) -> bool:
    """Whether a text carries the fact's value; `values` are the text's values, which a
    caller extracts once for many facts. A medication is searched by its name, which no
    pattern extracts."""
    if target.kind == "medication":
        return bool(find_medication(target, text))
    return any(matches(target, v) for v in values)


def hard_values(text: str, lang: str = "de") -> set[tuple[str, str]]:
    """Canonical keys of the values that matter in any rewrite (no plain numbers)."""
    return {v.key for v in extract_values(text, lang) if v.kind in HARD_KINDS}


def hard_value_found(key: tuple[str, str], text_values: Iterable[Value]) -> bool:
    target = Value(key[0], key[1])  # type: ignore[arg-type]
    return any(matches(target, v) for v in text_values)
