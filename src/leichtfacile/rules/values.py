"""Find and normalise checkable values in text: dates, amounts, numbers, phone
numbers, e-mail addresses, URLs, percentages and times.

This is the exact half of fact checking (rules.md FACT-01 and FACT-05) and the basis
of the model-independent "hard fact" metric in the evaluation. A value is reduced to
a canonical string, so "31. März 2026", "31.3.2026" and "2026-03-31" are the same
date, and "1'500 Franken", "CHF 1500.-" and "1 500.00" the same amount.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

ValueKind = Literal["date", "amount", "number", "phone", "email", "url", "percent", "time"]
HARD_KINDS: tuple[ValueKind, ...] = ("date", "amount", "phone", "email", "url", "percent", "time")

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


# -- extraction ----------------------------------------------------------------------


def mask(text: str, spans: Iterable[tuple[int, int]]) -> str:
    """Replace the spans with spaces, keeping all offsets valid."""
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " "
    return "".join(chars)


def extract_values(text: str, lang: str = "de") -> list[Value]:
    """All values in the text, in order of appearance, without overlaps."""
    found: list[Value] = []
    masked = text

    def take(kind: ValueKind, pattern: re.Pattern[str], canon, trim: str = "") -> None:
        nonlocal masked
        spans = []
        for m in pattern.finditer(masked):
            canonical = canon(m)
            if canonical is None:
                continue
            start, end = m.start(), m.end()
            while trim and end > start and text[end - 1] in trim:
                end -= 1  # a sentence-final dot is not part of a URL
            found.append(Value(kind, canonical, text[start:end], start, end))
            spans.append((start, end))
        masked = mask(masked, spans)

    take("email", EMAIL_RE, lambda m: m.group(0).lower())
    take("url", URL_RE, lambda m: canonical_url(m.group(0)), trim=".,;:!?")
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
    if value.kind == "number" and fact_kind == "amount":
        return Value("amount", value.canonical)
    return Value(value.kind, value.canonical)


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
        return candidate.kind in ("amount", "number") and candidate.canonical == target.canonical
    return candidate.kind == target.kind and candidate.canonical == target.canonical


def find_value(target: Value, text: str, lang: str = "de") -> list[Value]:
    return [v for v in extract_values(text, lang) if matches(target, v)]


def hard_values(text: str, lang: str = "de") -> set[tuple[str, str]]:
    """Canonical keys of the values that matter in any rewrite (no plain numbers)."""
    return {v.key for v in extract_values(text, lang) if v.kind in HARD_KINDS}


def hard_value_found(key: tuple[str, str], text_values: Iterable[Value]) -> bool:
    target = Value(key[0], key[1])  # type: ignore[arg-type]
    return any(matches(target, v) for v in text_values)
