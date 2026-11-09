"""The value grammar of a language: the words and formats `rules/values.py` reads values
with, as data in rules/data/values_<lang>.toml, one file per language, with the keys a
variety replaces under `[variety.<REGION>]` (the thousands dot and the decimal comma of
Germany and Austria, Jänner). The shapes a value takes (the digits of a date, an IBAN,
a phone number, a postal address) are code in values.py; what a language says (its
months, its clock word, its currency, multiplier and number words, its period units) is
here, so that a German text reads German words alone: `mars` is a planet in German and
a month in French, `2 h` a duration in German and a time in French.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

from leichtfacile.schemas import base_lang, canonical_variety

DATA_DIR = Path(__file__).parent / "data"
DASHES = "-" + "\N{HYPHEN}\N{NON-BREAKING HYPHEN}\N{FIGURE DASH}\N{EN DASH}\N{EM DASH}"
QUOTES = "\"'" + (
    "\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}"
    "\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}\N{DOUBLE LOW-9 QUOTATION MARK}"
)
APOSTROPHES = "'\N{RIGHT SINGLE QUOTATION MARK}"
MEDIOPUNKT = "\N{MIDDLE DOT}"
LETTER = r"[^\W\d_]"
# The period units by key, working days first: `Arbeitstag` holds `Tag`.
PERIOD_UNITS = ("wd", "d", "w", "m", "y")
COMPOUNDS = ("und", "hyphen", "joined")
_SECTIONS = {
    "dates", "time", "percent", "currency", "numbers", "number_words", "periods", "phone",
    "addresses", "variety",
}  # fmt: skip
_FALLBACK = "de"  # the grammar of a language without a file of its own


def _words(items: Iterable[str], *, tolerant: bool = False) -> str:
    """An alternation of the words, longest first, a space in a word matching one space;
    `tolerant`: a Mediopunkt may stand between any two letters (Kalender·tag)."""
    forms = []
    for word in sorted(set(items), key=len, reverse=True):
        if tolerant:
            forms.append((MEDIOPUNKT + "?").join("[ ]" if c == " " else re.escape(c) for c in word))
        else:
            forms.append(re.escape(word).replace("\\ ", "[ ]"))
    return "|".join(forms)


def _ignoring_case(alternation: str) -> str:
    return "(?i:" + alternation + ")"


class Grammar:
    """One language's grammar, with its variety's keys, and the patterns built from it.
    Built once per variety key (`grammar_for`)."""

    def __init__(self, key: str, data: dict[str, Any]) -> None:
        self.key = key
        self.lang = base_lang(key)
        dates, time, percent = data["dates"], data["time"], data["percent"]
        currency, numbers, words = data["currency"], data["numbers"], data["number_words"]
        periods, phone, addresses = data["periods"], data["phone"], data["addresses"]
        # dates
        self.months: dict[str, int] = {k.lower(): int(v) for k, v in dates["months"].items()}
        self.month_names: tuple[str, ...] = tuple(dates["month_names"])
        self.abbreviations = frozenset(dates.get("abbreviations", ()))
        self.day_format: str = dates.get("day", "{day}")
        self.first_day: str | None = dates.get("first_day") or None
        self.date_range_words: tuple[str, ...] = tuple(dates.get("range_words", ()))
        # time
        self.clock_word: str = time.get("clock_word", "")
        self.hour_letter: bool = bool(time.get("hour_letter", False))
        self.time_prefix_words: tuple[str, ...] = tuple(time.get("prefix_words", ()))
        self.bare_hour_words: tuple[str, ...] = tuple(time.get("bare_hour_words", ()))
        self.time_range_words: tuple[str, ...] = tuple(time.get("range_words", ()))
        self.time_range_before: tuple[str, ...] = tuple(time.get("range_before", ()))
        self.time_range_between: tuple[str, ...] = tuple(time.get("range_between", ()))
        # percent and currency
        self.percent_words: tuple[str, ...] = tuple(percent["words"])
        self.currency_before: tuple[str, ...] = tuple(currency["before"])
        self.currency_after: tuple[str, ...] = tuple(currency["after"])
        self.currency_link_words: tuple[str, ...] = tuple(currency.get("link_words", ()))
        self.subunits: tuple[str, ...] = tuple(currency.get("subunits", ()))
        self.weekday_abbreviations: tuple[str, ...] = tuple(
            currency.get("weekday_abbreviations", ())
        )
        self.weekday_joiners: tuple[str, ...] = tuple(currency.get("weekday_joiners", ()))
        self.multipliers: dict[str, int] = {
            k.lower(): int(v) for k, v in currency.get("multipliers", {}).items()
        }
        # numbers
        self.thousands: tuple[str, ...] = tuple(numbers["thousands"])
        self.decimal_marks: tuple[str, ...] = tuple(numbers["decimal"])
        self.dot_decimals: bool = bool(numbers.get("dot_decimals", False))
        self.writes_thousands: str = numbers["writes_thousands"]
        self.writes_decimal: str = numbers["writes_decimal"]
        # number words and periods
        self.number_words: dict[str, int] = {
            k.lower(): int(v) for k, v in words.get("table", {}).items()
        }
        self.compound: str = words.get("compound", "und")
        if self.compound not in COMPOUNDS:
            raise ValueError(f"{key}: number_words.compound must be one of {COMPOUNDS}")
        self.and_word: str | None = words.get("and_word") or None
        self.period_adjectives: tuple[str, ...] = tuple(periods.get("adjectives", ()))
        self.frequency_words: tuple[str, ...] = tuple(periods.get("frequency_words", ()))
        self.frequency_cycles: tuple[str, ...] = tuple(periods.get("frequency_cycles", ()))
        self.period_units: dict[str, tuple[str, ...]] = {
            unit: tuple(periods["units"].get(unit, ())) for unit in PERIOD_UNITS
        }
        self.period_names: dict[str, tuple[str, str]] = {
            unit: (names[0], names[1]) for unit, names in periods["names"].items()
        }
        # phone and addresses
        self.phone_style: str = phone.get("style", "swiss")
        self.five_digit_postcodes: bool = bool(addresses.get("five_digit_postcodes", False))
        self.street_word: str = addresses.get("street_word", "strasse")
        self._compile()

    @property
    def german_phones(self) -> bool:
        """Whether the loose phone shapes of Germany and Austria are read and written."""
        return self.phone_style == "german"

    # -- the patterns -----------------------------------------------------------------

    def _compile(self) -> None:
        months = "|".join(
            re.escape(m) + (r"\.?" if m in self.abbreviations else "")
            for m in sorted(self.months, key=len, reverse=True)
        )
        day = r"(1er|1°|1º|\d{1,2})"
        self.date_text_re = re.compile(
            r"(?<!\d)" + day + r"\.?[ ]?(" + months + r")(?:[ ](\d{4}))?(?!\w)", re.IGNORECASE
        )
        # Two days of one month with the month (and the year) written once: `vom 7. bis
        # 11. Juni 2027`, `7.-11. Juni`, `du 7 au 11 juin`, `dal 7 all'11 giugno`.
        joins = [
            r"[ ]?" + re.escape(w[:-1]) + "[" + APOSTROPHES + "]" if w.endswith("'") else
            r"[ ]" + re.escape(w) + r"[ ]"
            for w in self.date_range_words
        ]  # fmt: skip
        joins.append(r"[ ]?[" + DASHES + r"/][ ]?")
        self.date_range_re = re.compile(
            r"(?<!\d)(1er|\d{1,2})\.?(?:" + "|".join(joins) + r")" + day + r"\.?[ ]?("
            + months + r")(?:[ ](\d{4}))?(?!\w)",
            re.IGNORECASE,
        )  # fmt: skip
        self.time_re = self._time_pattern()
        self.time_range_res = self._time_range_patterns()
        self.percent_re = re.compile(
            r"(?<![\d.,])(\d+(?:[.,]\d+)?)[ ]?(?:%|" + _words(self.percent_words) + r")",
            re.IGNORECASE,
        )
        self.thousands_class = "[" + "".join(re.escape(c) for c in self.thousands) + "]"
        decimal = "[" + "".join(re.escape(c) for c in self.decimal_marks) + "]"
        tail = r"(?:(" + decimal + r")(\d{1,2}|[" + DASHES + r"]{1,2})(?!\d)"
        if self.dot_decimals:
            tail += r"|(\.)(\d{1,2})(?!\d)"
        self.number_re = re.compile(
            r"(?<![\d.,'/])(\d{1,3}(?:" + self.thousands_class + r"\d{3})+|\d+)" + tail
            + r")?(?![\d'])"
        )  # fmt: skip
        self.currency_before_re = re.compile(r"(?:" + _words(self.currency_before) + r")[ ]?$")
        link = (
            r"(?:(?:" + _words(self.currency_link_words) + r")[ ])?"
            if self.currency_link_words
            else ""
        )
        self.currency_after_re = re.compile(
            r"^[ ]?" + link + r"(?:" + _words(self.currency_after) + r")(?![\w·])", re.IGNORECASE
        )
        self.subunit_re = (
            re.compile(r"^[ ]?(?:" + _words(self.subunits) + r")(?![\w·])", re.IGNORECASE)
            if self.subunits
            else None
        )
        self.multiplier_re = (
            re.compile(r"^[ ]?(?P<word>" + _words(self.multipliers) + r")(?![\w·])", re.IGNORECASE)
            if self.multipliers
            else None
        )
        self.weekday_before_re = (
            re.compile(
                r"\b(?:"
                + _words(self.weekday_abbreviations)
                + r")\.?[ ]?(?:["
                + DASHES
                + r"/,]|"
                + _words(self.weekday_joiners)
                + r")[ ]?$"
            )
            if self.weekday_abbreviations
            else None
        )
        self.period_re = self._period_pattern()
        self.frequency_re = (
            re.compile(
                r"[ ]+(?:"
                + _words(self.frequency_words)
                + r")[ ]+(?:"
                + _words(self.frequency_cycles)
                + r")(?![\w·])",
                re.IGNORECASE,
            )
            if self.frequency_words and self.frequency_cycles
            else None
        )

    def _time_pattern(self) -> re.Pattern[str]:
        """9.00 Uhr, 09:00, 9 Uhr; the French 9 h 00 and 9h; the Italian ore 9.00, alle
        9.00, dalle 8.00 (also at a sentence start) and alle ore 9. A dotted hour counts
        without the clock word only with such a word before it: 1.50 is an amount."""
        prefix = (
            r"(?:\b" + _ignoring_case(_words(self.time_prefix_words)) + r"[ ])?"
            if self.time_prefix_words
            else ""
        )
        clock = r"(?:[ ]?" + re.escape(self.clock_word) + r")?" if self.clock_word else ""
        parts = [prefix + r"(?P<h1>\d{1,2})[.:](?P<m1>\d{2})(?!\d)(?![.,']\d)" + clock]
        if self.hour_letter:
            parts.append(r"(?P<h2>\d{1,2})[ ]?h[ ]?(?P<m2>\d{2})?(?!\w)")
        if self.clock_word:
            parts.append(r"(?P<h3>\d{1,2})[ ]?" + re.escape(self.clock_word))
        if self.bare_hour_words:
            parts.append(
                r"\b" + _ignoring_case(_words(self.bare_hour_words))
                + r"[ ](?P<h4>\d{1,2})(?![\d:])(?![.,]\d)"
            )  # fmt: skip
        return re.compile(r"(?<![\d.:'])(?:" + "|".join(parts) + r")")

    def _time_range_patterns(self) -> tuple[re.Pattern[str], ...]:
        """Two hours as one span: with the clock word once at the end (8.30 bis 11.30
        Uhr), or introduced and joined by words (dalle 8.00 alle 11.30, dalle ore 8.30
        alle ore 11.30, tra le 11.00 e le 15.00). Groups 1 to 4: the hours and minutes."""
        patterns = []
        hour = r"(\d{1,2})[.:](\d{2})"
        if self.clock_word:
            clock = re.escape(self.clock_word)
            joins = [_words(self.time_range_words)] if self.time_range_words else []
            joins.append("[" + DASHES + "]")
            patterns.append(
                re.compile(
                    r"(?<![\d.:'])" + hour + r"[ ]?(?:" + clock + r"[ ]?)?(?:" + "|".join(joins)
                    + r")[ ]?" + hour + r"(?:[ ]?" + clock + r")"
                )
            )  # fmt: skip
        if self.time_range_before and self.time_range_between:
            bare = r"(?:" + _words(self.bare_hour_words) + r"[ ])?" if self.bare_hour_words else ""
            patterns.append(
                re.compile(
                    r"(?<![\d.:'])(?:" + _words(self.time_range_before) + r")[ ]" + bare + hour
                    + r"[ ](?:" + _words(self.time_range_between) + r")[ ]" + bare + hour
                    + r"(?!\d)",
                    re.IGNORECASE,
                )
            )  # fmt: skip
        return tuple(patterns)

    def _period_pattern(self) -> re.Pattern[str]:
        """A count (digits or words) and a unit, with one adjective allowed between them
        (`die zwei folgenden Wochen`). An apostrophe before the count is an elision
        (`d'un mois`) unless a digit stands before it: `1'000 jours` is not `000 jours`."""
        and_part = (
            r"(?:" + LETTER + r"+[ ]" + re.escape(self.and_word) + r"[ ])?" if self.and_word else ""
        )
        count = r"(?P<num>\d{1,4}|" + and_part + LETTER + r"+(?:-" + LETTER + r"+)*)"
        between = (
            r"(?:[ -]?|[ ](?:" + _words(self.period_adjectives) + r")[ ])"
            if self.period_adjectives
            else r"[ -]?"
        )
        units = "|".join(
            f"(?P<{unit}>{_words(forms, tolerant=True)})"
            for unit, forms in self.period_units.items()
            if forms
        )
        return re.compile(
            r"(?<![\w·.,-])(?<!\d[" + APOSTROPHES + r"])" + count + between + r"(?:" + units
            + r")(?![\w·])",
            re.IGNORECASE,
        )  # fmt: skip

    # -- the words ------------------------------------------------------------------

    def month(self, name: str) -> int | None:
        """The number of a month name or abbreviation of this language; None for another."""
        return self.months.get(name.lower().rstrip("."))

    def multiplier(self, word: str) -> int:
        return self.multipliers[word.lower()]

    def number_word(self, word: str) -> int | None:
        """dreissig -> 30, einundzwanzig -> 21, vingt-cinq -> 25, quatre-vingt-onze -> 91,
        vingt et un -> 21, ventuno -> 21, trentotto -> 38, duecento -> 200, duemila ->
        2000; None for a word that is no number."""
        table = self.number_words
        word = word.lower()
        if self.and_word:
            word = word.replace(f" {self.and_word} ", "-").replace(f"-{self.and_word}-", "-")
        if word in table:
            return table[word]
        if self.compound == "und":
            first, _, rest = word.partition("und")
            if first in table and rest in table and table[first] < 10 <= table[rest]:
                return table[first] + table[rest]
            return None
        if self.compound == "hyphen":
            head, _, last = word.rpartition("-")
            if head in table and last in table and table[last] < 20 <= table[head]:
                return table[head] + table[last]
            return None
        return self._joined(word.replace("é", "e").replace("è", "e"))

    def _joined(self, word: str) -> int | None:
        """The joined compounds of Italian: a ten and a unit (ventidue), the ten's final
        vowel elided before uno and otto (ventuno, trentotto), a unit before cento and
        mila (duecento, duemila)."""
        table = self.number_words
        if word in table:
            return table[word]
        units = {w: n for w, n in table.items() if n < 10}
        tens = {w: n for w, n in table.items() if 20 <= n <= 90 and n % 10 == 0}
        for ten, value in tens.items():
            rest = word[len(ten) :]
            if word.startswith(ten) and rest in units:
                return value + units[rest]
            stem = ten[:-1]
            if word.startswith(stem) and word[len(stem) :] in ("uno", "otto"):
                return value + units[word[len(stem) :]]
        for unit, value in units.items():
            if word == unit + "cento":
                return value * 100
            if word == unit + "mila":
                return value * 1000
        return None


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """The base tables with a variety's keys in their place, one level deep: `[variety.AT]
    dates = { month_names = [...] }` replaces the month names and keeps the months."""
    merged = {section: dict(table) for section, table in base.items() if section != "variety"}
    for section, table in override.items():
        if section not in merged:
            raise ValueError(f"unknown table {section!r} in a variety")
        merged[section].update(table)
    return merged


def _grammar_path(lang: str) -> Path:
    return DATA_DIR / f"values_{lang}.toml"


@lru_cache
def grammar_for(lang: str) -> Grammar:
    """The grammar of a language or variety key (`de`, `de-AT`, `fr-CH`); a language
    without a file reads as German."""
    key = canonical_variety(lang)
    language = base_lang(key)
    path = _grammar_path(language)
    if not path.is_file():
        path, key = _grammar_path(_FALLBACK), canonical_variety(_FALLBACK)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    unknown = set(data) - _SECTIONS
    if unknown:
        raise ValueError(f"{path.name}: unknown tables {sorted(unknown)}")
    region = key.partition("-")[2]
    override = data.get("variety", {}).get(region, {})
    return Grammar(key, _merge(data, override))


def languages() -> tuple[str, ...]:
    """The languages with a grammar file, in alphabetical order."""
    return tuple(sorted(p.stem.removeprefix("values_") for p in DATA_DIR.glob("values_*.toml")))
