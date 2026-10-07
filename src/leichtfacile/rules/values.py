"""Find and normalise checkable values in text: dates, amounts, numbers, phone
numbers, e-mail addresses, URLs, percentages, times, periods, identifiers and postal
addresses.

This is the exact half of fact checking (rules.md FACT-01 and FACT-05) and the basis
of the model-independent "hard fact" metric in the evaluation. A value is reduced to
a canonical string, so "31. März 2026", "31.3.2026" and "2026-03-31" are the same
date, "1'500 Franken", "CHF 1500.-" and "1 500.00" the same amount, and "30 Tagen",
"dreissig Tage" and "30-tägige" the same period.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

ValueKind = Literal[
    "date", "amount", "number", "phone", "email", "url", "percent", "time",
    "period", "identifier", "address",
]  # fmt: skip
# The kinds a rewrite must keep exactly (plain numbers are not among them).
HARD_KINDS: tuple[ValueKind, ...] = (
    "date", "amount", "phone", "email", "url", "percent", "time",
    "period", "identifier", "address",
)  # fmt: skip

MONTHS: dict[str, dict[str, int]] = {
    "de": {
        "januar": 1, "jan": 1, "februar": 2, "feb": 2, "märz": 3, "maerz": 3, "mär": 3,
        "april": 4, "apr": 4, "mai": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7,
        "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "oktober": 10,
        "okt": 10, "november": 11, "nov": 11, "dezember": 12, "dez": 12,
    },
    "fr": {
        "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
        "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10,
        "novembre": 11, "décembre": 12, "decembre": 12,
    },
    "it": {
        "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
        "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11,
        "dicembre": 12,
    },
}  # fmt: skip
MONTH_NAMES = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
           "September", "Oktober", "November", "Dezember"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
           "agosto", "settembre", "ottobre", "novembre", "dicembre"],
}  # fmt: skip

DASHES = "-\u2010\u2011\u2012\u2013\u2014"
_SEP = r"[ '\u2019\u02bc\u00a0\u202f\u2009]"  # thousands separators seen in Swiss texts
_QUOTES = "\"'\u00ab\u00bb\u201c\u201d\u201e"
_ALL_MONTHS = sorted({m for names in MONTHS.values() for m in names}, key=len, reverse=True)
_ABBREVIATED = {"jan", "feb", "mär", "apr", "jun", "jul", "aug", "sep", "sept", "okt", "nov", "dez"}
# Abbreviated months may carry a dot (31. Jan. 2026); full names may not, so a
# sentence-final dot is never part of the date.
_MONTH_RE = "|".join(re.escape(m) + (r"\.?" if m in _ABBREVIATED else "") for m in _ALL_MONTHS)

EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-zA-Z]{2,}(?![\w-])")
URL_RE = re.compile(
    r"(?:(?:https?://|www\.)[^\s<>()" + _QUOTES + r"]+"
    r"|(?<![\w@.-])(?:[a-z0-9-]+\.)+(?:ch|swiss|com|org|net|info|li|eu|de|fr|it)"
    r"(?:/[^\s<>()" + _QUOTES + r"]*)?)(?![\w@-])",
    re.IGNORECASE,
)
PHONE_RE = re.compile(
    r"(?<![\d+])(?:"
    r"(?:\+41|0041)[ ./-]?(?:\(0\)[ ]?)?\d{2}[ ./-]?\d{3}[ ./-]?\d{2}[ ./-]?\d{2}"
    r"|0(?:800|84[0-9]|90[0-9])[ ./-]?\d{3}[ ./-]?\d{3}"
    r"|0\d{2}[ ./-]?\d{3}[ ./-]?\d{2}[ ./-]?\d{2}"
    r")(?!\d)"
)
DATE_ISO_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
DATE_NUM_RE = re.compile(r"(?<![\d.])(\d{1,2})\.[ ]?(\d{1,2})\.(?:[ ]?(\d{4}|\d{2})(?!\d))?")
DATE_SLASH_RE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
DATE_TEXT_RE = re.compile(
    r"(?<!\d)(1er|1°|1º|\d{1,2})\.?[ ]?(" + _MONTH_RE + r")(?:[ ](\d{4}))?(?!\w)",
    re.IGNORECASE,
)
TIME_RE = re.compile(
    r"(?<![\d.:'])(?:"
    r"(\d{1,2})[.:](\d{2})(?!\d)(?![.,']\d)(?:[ ]?Uhr)?"  # 9.00 Uhr, 09:00
    r"|(\d{1,2})[ ]?h[ ]?(\d{2})?(?!\w)"  # 9 h 00, 9h
    r"|(\d{1,2})[ ]?Uhr"  # 9 Uhr
    r")"
)
TIME_RANGE_RE = re.compile(
    r"(?<![\d.:'])(\d{1,2})[.:](\d{2})[ ]?(?:Uhr[ ]?)?(?:bis|-|\u2013)[ ]?"
    r"(\d{1,2})[.:](\d{2})(?:[ ]?Uhr)"
)  # 8.30 bis 11.30 Uhr: the first time has no "Uhr" of its own
PERCENT_RE = re.compile(
    r"(?<![\d.,])(\d+(?:[.,]\d+)?)[ ]?(?:%|Prozent|pour[ ]?cent|per[ ]?cento)", re.IGNORECASE
)
NUMBER_RE = re.compile(
    r"(?<![\d.,'/])(\d{1,3}(?:" + _SEP + r"\d{3})+|\d+)"
    r"(?:([.,])(\d{1,2}|[" + DASHES + r"]{1,2})(?!\d))?(?![\d'])"
)
_CURRENCY_BEFORE = re.compile(r"(?:CHF|Fr\.|SFr\.|sFr\.)[ ]?$")
_CURRENCY_AFTER = re.compile(
    r"^[ ]?(?:CHF|Fr\.|Franken|Rappen|francs?|franchi|franco)", re.IGNORECASE
)

# -- periods: a count with days, weeks, months or years --------------------------------

# Number words for periods (`dreissig Tage`, `deux semaines`). NUM-01 keeps its own
# table for the rule; a period also needs ein/eine and the teens.
_NUMBER_WORDS: dict[str, dict[str, int]] = {
    "de": {
        "ein": 1, "eine": 1, "einem": 1, "einen": 1, "einer": 1, "eines": 1, "zwei": 2,
        "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9,
        "zehn": 10, "elf": 11, "zwölf": 12, "dreizehn": 13, "vierzehn": 14, "fünfzehn": 15,
        "sechzehn": 16, "siebzehn": 17, "achtzehn": 18, "neunzehn": 19, "zwanzig": 20,
        "dreissig": 30, "dreißig": 30, "vierzig": 40, "fünfzig": 50, "sechzig": 60,
        "siebzig": 70, "achtzig": 80, "neunzig": 90, "hundert": 100,
    },
    "fr": {
        "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
        "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13,
        "quatorze": 14, "quinze": 15, "seize": 16, "dix-sept": 17, "dix-huit": 18,
        "dix-neuf": 19, "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50,
        "soixante": 60, "soixante-dix": 70, "septante": 70, "quatre-vingt": 80,
        "quatre-vingts": 80, "huitante": 80, "octante": 80, "quatre-vingt-dix": 90,
        "nonante": 90, "cent": 100,
    },
    "it": {
        "un": 1, "uno": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6,
        "sette": 7, "otto": 8, "nove": 9, "dieci": 10, "undici": 11, "dodici": 12,
        "tredici": 13, "quattordici": 14, "quindici": 15, "sedici": 16, "diciassette": 17,
        "diciotto": 18, "diciannove": 19, "venti": 20, "trenta": 30, "quaranta": 40,
        "cinquanta": 50, "sessanta": 60, "settanta": 70, "ottanta": 80, "novanta": 90,
        "cento": 100,
    },
}  # fmt: skip
# The unit as written: d(ays), w(eeks), m(onths), y(ears), wd (working days). The
# canonical form keeps count and unit ("2w"); `matches` makes weeks equal to days and
# years to months, and working days equal to nothing else. Adjective forms (`30-tägige
# Frist`, `einjährig`) count too; a Mediopunkt inside a compound unit is allowed.
_PERIOD_UNITS: dict[str, str] = {
    "de": (
        r"(?P<wd>(?:Arbeits|Werk)·?tag(?:e|en|es)?)"
        r"|(?P<d>(?:Kalender·?)?tag(?:e|en|es)?|tägig(?:e[nmrs]?)?)"
        r"|(?P<w>wochen?|wöchig(?:e[nmrs]?)?)"
        r"|(?P<m>monat(?:e|en|s)?|monatig(?:e[nmrs]?)?)"
        r"|(?P<y>jahr(?:e|en|es)?|jährig(?:e[nmrs]?)?)"
    ),
    "fr": (
        r"(?P<wd>jours?[ ]ouvr(?:able|é)s?)|(?P<d>jours?)|(?P<w>semaines?)|(?P<m>mois)"
        r"|(?P<y>ans?|années?)"
    ),
    "it": (
        r"(?P<wd>giorn[oi][ ]lavorativ[oi])|(?P<d>giorn[oi])|(?P<w>settiman[ae])"
        r"|(?P<m>mes[ei])|(?P<y>ann[oi])"
    ),
}
_PERIOD_RE: dict[str, re.Pattern[str]] = {
    lang: re.compile(
        r"(?<![\w·.,'’-])"
        r"(?P<num>\d{1,4}|(?:[a-zäöüéèêß]+[ ]et[ ])?[a-zäöüéèêß]+(?:-[a-zäöüéèê]+)*)"
        r"[ -]?(?:" + units + r")(?![\w·])",
        re.IGNORECASE,
    )
    for lang, units in _PERIOD_UNITS.items()
}
_PERIOD_WORDS: dict[str, dict[str, tuple[str, str]]] = {
    "de": {"d": ("Tag", "Tage"), "w": ("Woche", "Wochen"), "m": ("Monat", "Monate"),
           "y": ("Jahr", "Jahre"), "wd": ("Arbeitstag", "Arbeitstage")},
    "fr": {"d": ("jour", "jours"), "w": ("semaine", "semaines"), "m": ("mois", "mois"),
           "y": ("an", "ans"), "wd": ("jour ouvrable", "jours ouvrables")},
    "it": {"d": ("giorno", "giorni"), "w": ("settimana", "settimane"), "m": ("mese", "mesi"),
           "y": ("anno", "anni"), "wd": ("giorno lavorativo", "giorni lavorativi")},
}  # fmt: skip

# -- identifiers: AHV number, IBAN, postal account, UID, a reference after a keyword ----

_AHV_RE = re.compile(r"(?<!\d)756[. ]?\d{4}[. ]?\d{4}[. ]?\d{2}(?!\d)")
_IBAN_RE = re.compile(r"(?<![A-Z0-9])(?:CH|LI)\d{2}(?:[ ]?[0-9A-Z]{4}){4}[ ]?[0-9A-Z](?![0-9A-Z])")
_POSTAL_ACCOUNT_RE = re.compile(
    r"(?<![\d-])\d{2}[" + DASHES + r"]\d{1,6}[" + DASHES + r"]\d(?![\d-])"
)
_UID_RE = re.compile(r"(?<![\w-])CHE[- ]?\d{3}\.\d{3}\.\d{3}(?!\d)")
# A reference after a keyword: `Referenz 2026-0042`, `Dossier-Nr. 12345`, `Geschäfts·nummer:
# K-4711` (a keyword split by code keeps its Mediopunkt), `N° de dossier 12345`. Words that
# are identifiers on their own, compounds with -nummer, and words that need Nr. or Nummer;
# up to four small words may stand between keyword and code ("Die Nummer von Ihrem
# Dossier ist 2026-0042"). The value is the code alone.
_REF_KEYWORDS = (
    r"Referenz·?nummern?|Referenz|Ref\.|Dossier·?nummern?|Dossier|Akten·?zeichen|Geschäfts·?zeichen"
    r"|(?:Geschäfts|Kunden|Versicherten|Versicherungs|Policen|Fall|Rechnungs|Vertrags|Betreibungs"
    r"|Verfahrens|Gesuchs|Entscheid|Verfügungs|Mitglieder|Partner|Vorgangs|Konto|Akten|Schaden)"
    r"·?nummern?"
    r"|(?:Verfügung|Entscheid|Fall|Police|Rechnung|Vertrag|Gesuch|Betreibung|Verfahren|Urteil"
    r"|Beschluss|Konto|Dossier|Referenz|Geschäft|Akte|Schaden)s?[ -]?(?:Nr\.?|Nummer)"
    r"|Référence|Réf\.|Riferimento|Rif\.|Incarto"
    r"|(?:Numéro|N°|No\.?)[ ](?:de[ ]|du[ ]|d')?(?:référence|dossier|client|cliente|police|contrat"
    r"|facture|cas|décision|assuré|affaire|procédure|membre|compte|sinistre)"
    r"|(?:Décision|Facture|Contrat|Police|Cas|Affaire|Procédure|Compte|Dossier|Référence|Sinistre)"
    r"[ ]?(?:n°|no\.?|numéro)"
    r"|(?:Numero|N\.|N°)[ ](?:di[ ]|del[ ]|della[ ]|dell')?(?:riferimento|incarto|cliente|polizza"
    r"|contratto|fattura|caso|decisione|procedura|conto)"
    r"|(?:Decisione|Fattura|Contratto|Polizza|Caso|Procedura|Conto|Incarto)[ ]?(?:n\.|n°|numero)"
)
_REF_FILLER = (
    r"(?:[ ]+(?:ist|lautet|heisst|hat|die|der|das|Ihre?[nmrs]?|unsere?[nmrs]?|von|vom|Nr\.?"
    r"|Nummer|est|votre|notre|le|la|du|de|è|il|vostro|nostro|numero|numéro|n°|no\.?)){0,4}?"
)
_CODE_SEP = r"[.\-/‐-—]"
_REF_CODE = (
    r"(?P<code>(?=(?:[A-Za-z0-9]|"
    + _CODE_SEP
    + r")*\d)[A-Za-z0-9]+(?:"
    + _CODE_SEP
    + r"[A-Za-z0-9]+)*)"
)
_NOT_AFTER_CODE = (
    r"(?![ ]?(?:Tag|Tage|Tagen|Woche|Wochen|Monat|Monate|Monaten|Jahr|Jahre|Jahren|Franken"
    r"|Rappen|Prozent|Uhr|Minuten|Stunden|Mal|Seiten|Personen|jours?|semaines?|mois|ans?|francs?"
    r"|heures|giorni|mesi|anni|franchi)(?![\w·]))"
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
    r"(?=.*\d)(?=.*[A-Za-z/\-‐-—])[A-Za-z0-9]+(?:" + _CODE_SEP + r"[A-Za-z0-9]+)*"
)
_EXPLICIT_NUMBER = re.compile(r"nr\.?$|nummer|n°|no\.?$|numéro|numero|n\.$")

# -- postal addresses: street and number, Postfach, postcode and place ----------------

_NBSP = chr(0xA0)  # web pages set a no-break space in "St. Gallen" and after a postcode
_SP = "[ " + _NBSP + "]"
_UPPER = r"[A-ZÄÖÜÉÈÀÇ]"
_WORD_CAP = _UPPER + r"(?:[^\W\d_]|[·'’-])*"  # a capitalised word, Mediopunkt allowed
# A street name ends in a street word; a short adjective may precede it (Untere
# Zollgasse), never the town or office in front of the address (Biel Bahnhofsplatz 2D),
# which a draft rightly leaves out.
_STREET_DE = (
    r"(?:[A-ZÄÖÜ][a-zäöü]{1,5}(?:e|er|en|es)" + _SP + r")?" + _UPPER + r"(?:[^\W\d_]|[·'’-])*?"
    r"(?i:strasse|str\.|weg|gasse|platz|allee|quai|promenade|ring|rain|halde|matte|steig|graben)"
)
_STREET_FR_IT = (
    r"(?:Rue|Avenue|Av\.|Chemin|Ch\.|Route|Rte|Place|Boulevard|Bd|Impasse|Allée|Quai|Promenade"
    r"|Via|Viale|Piazza|Piazzale|Corso|Strada|Vicolo|Salita)(?:"
    + _SP
    + r"(?:[^\W\d_]|[·'’-])+){1,4}?"
)
_HOUSE = r"(?P<house>\d{1,4}(?:" + _SP + r"?[a-zA-Z](?![^\W\d_])|[-/]\d{1,4})?)"
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
    r"(?:(?P<street>" + _STREET_DE + r"|" + _STREET_FR_IT + r")" + _SP + _HOUSE + _SP + r"*,?\s*)?"
    r"(?:" + _POBOX + _SP + r"*,?\s*)?"
    r"(?P<ch>CH[- ])?(?<!\d)(?P<plz>[1-9]\d{3})" + _SP + r"+" + _PLACE + r"(?![\w·'’-])"
)
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


def canonical_number(integer: str, decimals: str | None = None) -> str | None:
    digits = re.sub(_SEP, "", integer)
    if not digits.isdigit():
        return None
    try:
        value = Decimal(digits + ("." + decimals if decimals and decimals.isdigit() else ""))
    except InvalidOperation:
        return None
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def canonical_phone(text: str) -> str:
    stripped = text.strip()
    digits = re.sub(r"\D", "", stripped.replace("(0)", ""))
    if digits.startswith("0041"):
        digits = "0" + digits[4:]
    elif stripped.startswith("+41"):
        digits = "0" + digits[2:]
    return digits


def canonical_url(text: str) -> str:
    url = text.strip().rstrip(".,;:!?)").lower()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    return url.rstrip("/")


def format_date(canonical: str, lang: str = "de") -> str:
    """Render a canonical date the way easy language writes it: 4. Februar 2020."""
    m = re.fullmatch(r"(\d{4}|-)-(\d{2})-(\d{2})", canonical)
    if not m:
        return canonical
    year = None if m.group(1) == "-" else int(m.group(1))
    month, day = int(m.group(2)), int(m.group(3))
    name = MONTH_NAMES.get(lang, MONTH_NAMES["de"])[month - 1]
    if lang == "de":
        out = f"{day}. {name}"
    else:
        out = f"{'1er' if lang == 'fr' and day == 1 else day} {name}"
    return f"{out} {year}" if year else out


def format_phone(canonical: str) -> str:
    """0441234567 -> 044 123 45 67; service numbers 0800123456 -> 0800 123 456."""
    digits = re.sub(r"\D", "", canonical)
    if len(digits) == 10 and digits[:2] in ("08", "09"):
        return f"{digits[:4]} {digits[4:7]} {digits[7:]}"
    if len(digits) == 10:
        return f"{digits[:3]} {digits[3:6]} {digits[6:8]} {digits[8:]}"
    return canonical


def format_thousands(canonical: str, lang: str = "de") -> str:
    """500000 -> 500'000 (German, Italian), 500 000 (French)."""
    integer, _, decimals = canonical.partition(".")
    sep = " " if lang == "fr" else "'"
    groups: list[str] = []
    while len(integer) > 3:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    groups.insert(0, integer)
    out = sep.join(groups)
    return f"{out}.{decimals}" if decimals else out


def period_parts(canonical: str) -> tuple[int, str]:
    """ "30d" -> (30, "d"); units d, w, m, y, wd."""
    m = re.fullmatch(r"(\d+)(wd|d|w|m|y)", canonical)
    if not m:
        raise ValueError(f"not a period: {canonical!r}")
    return int(m.group(1)), m.group(2)


def format_period(canonical: str, lang: str = "de") -> str:
    """ "30d" -> 30 Tage, "1y" -> 1 Jahr, "5wd" -> 5 jours ouvrables (French)."""
    count, unit = period_parts(canonical)
    one, many = _PERIOD_WORDS.get(lang, _PERIOD_WORDS["de"])[unit]
    return f"{count} {one if count == 1 else many}"


def format_identifier(canonical: str) -> str:
    """An IBAN in groups of four; every other identifier as it is."""
    if re.fullmatch(r"(?:CH|LI)\d{2}[0-9A-Z]{17}", canonical):
        return " ".join(canonical[i : i + 4] for i in range(0, len(canonical), 4))
    return canonical


def format_address(canonical: str) -> str:
    """ "Gerichtsstrasse 12||8000 Musterwil" -> Gerichtsstrasse 12, 8000 Musterwil."""
    return ", ".join(part for part in canonical.split("|") if part)


# -- extraction ----------------------------------------------------------------------


def mask(text: str, spans: Iterable[tuple[int, int]]) -> str:
    """Replace the spans with spaces, keeping all offsets valid."""
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " "
    return "".join(chars)


def extract_values(text: str, lang: str = "de") -> list[Value]:
    """All values in the text, in order of appearance, without overlaps. Each kind is
    taken from the text with the earlier kinds masked, so an IBAN is never also a
    phone number and the count of a period never also a plain number."""
    found: list[Value] = []
    masked = text

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
    take("identifier", REFERENCE_RE, _reference, group="code")
    take("address", ADDRESS_RE, _address)
    take("phone", PHONE_RE, lambda m: canonical_phone(m.group(0)))
    take(
        "date",
        DATE_ISO_RE,
        lambda m: canonical_date(int(m.group(3)), int(m.group(2)), int(m.group(1))),
    )
    take("date", DATE_TEXT_RE, lambda m: _text_date(m, lang))
    take("date", DATE_NUM_RE, _numeric_date)
    take(
        "date",
        DATE_SLASH_RE,
        lambda m: canonical_date(int(m.group(1)), int(m.group(2)), int(m.group(3))),
    )
    take("percent", PERCENT_RE, lambda m: canonical_number(*_split_decimal(m.group(1))))
    spans = []
    for m in TIME_RANGE_RE.finditer(masked):
        for h, mi in ((1, 2), (3, 4)):
            hour, minute = int(m.group(h)), int(m.group(mi))
            if hour <= 24 and minute <= 59:
                start, end = m.start(h), m.end(mi)
                found.append(Value("time", f"{hour:02d}:{minute:02d}", text[start:end], start, end))
        spans.append(m.span())
    masked = mask(masked, spans)
    take("time", TIME_RE, _time)
    take("period", _PERIOD_RE.get(lang, _PERIOD_RE["de"]), lambda m: _period(m, lang))

    for m in NUMBER_RE.finditer(masked):
        decimals = m.group(3)
        dash_decimals = bool(decimals) and not decimals.isdigit()  # "500.-" is 500
        canonical = canonical_number(m.group(1), None if dash_decimals else decimals)
        if canonical is None:
            continue
        before = text[max(0, m.start() - 6) : m.start()]
        after = text[m.end() : m.end() + 10]
        is_amount = dash_decimals or bool(
            _CURRENCY_BEFORE.search(before) or _CURRENCY_AFTER.search(after)
        )
        kind: ValueKind = "amount" if is_amount else "number"
        found.append(Value(kind, canonical, text[m.start() : m.end()], m.start(), m.end()))
    found.sort(key=lambda v: v.start)
    return found


def _split_decimal(number: str) -> tuple[str, str | None]:
    integer, _, decimals = number.replace(",", ".").partition(".")
    return integer, decimals or None


def _text_date(m: re.Match[str], lang: str) -> str | None:
    day_text = re.sub(r"\D", "", m.group(1)) or "1"
    month = None
    for names in (MONTHS.get(lang, {}), *MONTHS.values()):
        month = names.get(m.group(2).lower().rstrip("."))
        if month:
            break
    if month is None:
        return None
    year = int(m.group(3)) if m.group(3) else None
    return canonical_date(int(day_text), month, year)


def _numeric_date(m: re.Match[str]) -> str | None:
    year = int(m.group(3)) if m.group(3) else None
    return canonical_date(int(m.group(1)), int(m.group(2)), year)


def _time(m: re.Match[str]) -> str | None:
    if m.group(1):
        hour, minute = int(m.group(1)), int(m.group(2))
        if "Uhr" not in m.group(0) and ":" not in m.group(0):
            return None  # "1.50" is an amount or a decimal, not a time
    elif m.group(3):
        hour, minute = int(m.group(3)), int(m.group(4) or 0)
    else:
        hour, minute = int(m.group(5)), 0
    if hour > 24 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _number_word(word: str, lang: str) -> int | None:
    """dreissig -> 30, einundzwanzig -> 21, vingt-cinq -> 25, quatre-vingt-onze -> 91."""
    table = _NUMBER_WORDS.get(lang, _NUMBER_WORDS["de"])
    word = word.replace(" et ", "-").replace("-et-", "-")
    if word in table:
        return table[word]
    if lang == "de":
        first, _, rest = word.partition("und")
        if first in table and rest in table and table[first] < 10 <= table[rest]:
            return table[first] + table[rest]
        return None
    head, _, last = word.rpartition("-")
    if head in table and last in table and table[last] < 20 <= table[head]:
        return table[head] + table[last]
    return None


def _period(m: re.Match[str], lang: str) -> str | None:
    num = m.group("num")
    count = int(num) if num.isdigit() else _number_word(num.lower(), lang)
    if count is None:
        return None  # "pro Tag", "Montag": no count in front of the unit
    unit = next(u for u in ("wd", "d", "w", "m", "y") if m.group(u))
    return f"{count}{unit}"


def canonical_ahv(text: str) -> str:
    """756.1234.5678.97 for the dotted, spaced or bare 13 digits."""
    digits = re.sub(r"\D", "", text)
    return f"{digits[:3]}.{digits[3:7]}.{digits[7:11]}.{digits[11:]}"


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


def _address(m: re.Match[str]) -> str | None:
    """street number|Postfach|postcode place; empty parts for what the text lacks. A
    postcode without a street, Postfach or CH- in front counts only after a boundary
    (line start, comma, colon) and never in 1900-2099 (a year followed by a noun)."""
    plz, place = m.group("plz"), m.group("place")
    strong = bool(m.group("street") or m.group("pobox") or m.group("ch"))
    if place.split()[0].lower().replace("·", "") in _NOT_A_PLACE:
        return None
    if not m.group("street") and not _AFTER_PLACE.match(m.string[m.end() :]):
        return None  # a count, or a box number and the next sentence
    if not strong:
        if 1900 <= int(plz) <= 2099:
            return None
        before = m.string[: m.start()].rstrip(" " + _NBSP)
        if before and before[-1] not in ",:;(\n":
            return None
        if _CURRENCY_BEFORE.search(before):
            return None
    street = ""
    if m.group("street"):
        street = _clean(f"{m.group('street')} {m.group('house')}")
        street = re.sub(r"(?i)str\.(?=[ ])", "strasse", street)
    pobox = _clean(m.group("pobox")) if m.group("pobox") else ""
    return f"{street}|{pobox}|{plz} {_clean(place)}"


# -- normalised fact values --------------------------------------------------------


def parse_value_norm(
    value_norm: str | None, fact_kind: str = "other", lang: str = "de"
) -> Value | None:
    """Interpret a fact sheet's value_norm; None when code cannot check it."""
    if not value_norm or not value_norm.strip():
        return None
    raw = value_norm.strip()
    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw):
        canonical = canonical_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        return Value("date", canonical) if canonical else None
    if m := re.fullmatch(r"--(\d{2})-(\d{2})", raw):
        canonical = canonical_date(int(m.group(2)), int(m.group(1)), None)
        return Value("date", canonical) if canonical else None
    if m := re.fullmatch(r"(\d{1,2}):(\d{2})", raw):
        return Value("time", f"{int(m.group(1)):02d}:{m.group(2)}")
    if re.fullmatch(r"(?:\+|00)?\d{9,13}", raw.replace(" ", "")) and raw.lstrip("+").startswith(
        ("0", "41")
    ):
        return Value("phone", canonical_phone(raw if not raw.startswith("41") else "+" + raw))
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
    t_street, t_pobox, t_place = target.canonical.lower().split("|")
    c_street, c_pobox, c_place = candidate.canonical.lower().split("|")
    if t_place != c_place or (t_street and t_street != c_street):
        return False
    return not t_pobox or c_pobox.startswith(t_pobox)


def matches(target: Value, candidate: Value) -> bool:
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
    return [v for v in extract_values(text, lang) if matches(target, v)]


def hard_values(text: str, lang: str = "de") -> set[tuple[str, str]]:
    """Canonical keys of the values that matter in any rewrite (no plain numbers)."""
    return {v.key for v in extract_values(text, lang) if v.kind in HARD_KINDS}


def hard_value_found(key: tuple[str, str], text_values: Iterable[Value]) -> bool:
    target = Value(key[0], key[1])  # type: ignore[arg-type]
    return any(matches(target, v) for v in text_values)
