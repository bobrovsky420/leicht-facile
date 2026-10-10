"""Pasted plain text (or simple Markdown) to units.

- Paragraphs are separated by blank lines. The lines of a paragraph are joined with
  spaces; a word hyphenated at a line end is joined again (`join_lines`).
- "#", "##", ... at the start of a line make a heading of that level.
- A line that starts with a bullet (-, *, +, a bullet character, an en or em dash) or
  with "1." / "1)" / "a)" is a list item. A following line that is indented or starts
  in lower case continues the item. "1. Januar 2027 ..." is a date, not a list item.
- A paragraph of one short line (at most 10 words, no final . ! ? : ; ,) is a heading
  of level 2, unless it is a salutation, a closing formula, a place and date line or a
  field line: a label and a value (`Verfahrensnummer: KES-2026-0187`), a phone number,
  an e-mail or a web address. A value in a heading is not a must-keep fact.
"""

from __future__ import annotations

import re

from leichtfacile.ingest.normalize import join_lines, normalize_newlines, normalize_text
from leichtfacile.ingest.segment import DEFAULT_HEADING_LEVEL, MONTHS, Unit
from leichtfacile.schemas import SegmentKind

MAX_HEADING_WORDS = 10

_MARKDOWN_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_RULE = re.compile(r"^\s*([-*_=])(?:\s*\1){2,}\s*$")
# Bullets: - * + and the bullet, triangular bullet, hyphen bullet, black small square,
# black circle, white bullet, en dash, em dash, Symbol-font bullet.
_BULLET = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<marker>[-*+\u2022\u2023\u2043\u25aa\u25cf\u25e6\u2013\u2014\uf0b7]"
    r"|\d{1,3}[.)]|\(\d{1,3}\)|\(?[a-z]\))"
    r"\s+(?P<text>\S.*)$"
)
_FINAL_PUNCTUATION = ".!?:;,"
# Salutations and closing formulas of letters in German, French and Italian.
_LETTER_FORMULA = re.compile(
    r"^(?:sehr geehrte|liebe[rs]?\b|guten tag|gr\u00fcezi|hallo\b|freundliche gr|"
    r"mit freundlichen|beste gr|herzliche gr|madame|monsieur|mesdames|messieurs|"
    r"ch\u00e8re?s?\b|bonjour|salutations|meilleures salutations|avec (?:nos|mes) meilleures|"
    r"gentile|egregi[oa]\b|spettabile|buongiorno|cordiali saluti|distinti saluti|"
    r"cari?\b|care\b)",
    re.IGNORECASE,
)
# "Zürich, 5. Oktober 2026", "5.10.2026", "Lausanne, le 1er octobre 2026".
_DATE_LINE = re.compile(
    r"(?:\d{1,2}\.\s*\d{1,2}\.\s*\d{2,4}|\d{1,2}\.?(?:er)?\s+[^\W\d_]+\s+\d{4}"
    r"|\d{4}-\d{2}-\d{2})\s*$"
)
# A letter's field lines: "Verfahrensnummer: KES-2026-0187", "Telefon 044 123 45 67",
# an e-mail or web address. "Betreff: Staats- und Gemeindesteuern 2025" stays a
# heading: the word after its colon holds no digit.
_FIELD_LINE = re.compile(
    r"^[^:]{1,40}:\s*\S*[\d@]|@|\bwww\.|https?://"
    r"|(?<!\d)(?:\+41|0)\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}(?!\d)"
)


def parse_text(text: str) -> list[Unit]:
    """Split pasted text into headings, paragraphs and list items."""
    units: list[Unit] = []
    for block in _blocks(normalize_newlines(text)):
        units.extend(_parse_block(block))
    return units


def first_heading(units: list[Unit]) -> str | None:
    """The text of the first unit if it is a heading (a title candidate)."""
    if units and units[0].kind == "heading":
        return units[0].text
    return None


def _blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.split("\n"):
        if line.strip():
            current.append(line.rstrip())
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _parse_block(lines: list[str]) -> list[Unit]:
    units: list[Unit] = []
    kind: SegmentKind = "paragraph"
    pending: list[str] = []
    indent = 0

    def flush() -> None:
        if pending:
            text = normalize_text(join_lines(pending))
            if text:
                units.append(Unit(kind, text))
            pending.clear()

    for line in lines:
        heading = _MARKDOWN_HEADING.match(line)
        if heading:
            flush()
            units.append(
                Unit(
                    "heading", normalize_text(heading.group(2)), heading_level=len(heading.group(1))
                )
            )
            continue
        if _RULE.match(line):
            flush()
            continue
        bullet = _bullet(line)
        if bullet:
            flush()
            kind, indent = "list_item", len(bullet.group("indent").expandtabs(4))
            pending.append(bullet.group("text"))
            continue
        if kind == "list_item" and pending and _continues_item(line, indent, pending[-1]):
            pending.append(line)
            continue
        if kind == "list_item":
            flush()
            kind = "paragraph"
        pending.append(line)
    flush()

    single = len(lines) == 1 and len(units) == 1 and units[0].kind == "paragraph"
    if single and _looks_like_heading(units[0].text):
        units[0] = Unit("heading", units[0].text, heading_level=DEFAULT_HEADING_LEVEL)
    return units


def _bullet(line: str) -> re.Match[str] | None:
    match = _BULLET.match(line)
    if match is None:
        return None
    marker = match.group("marker")
    if marker[0].isdigit() and marker.endswith("."):
        first = match.group("text").split()[0].strip(".,").lower()
        if first in MONTHS:
            return None  # "1. Januar 2027 ..." is a date
    return match


def _continues_item(line: str, indent: int, previous: str) -> bool:
    stripped = line.lstrip()
    if len(line) - len(stripped) > indent or line[:1] == "\t":
        return True
    if stripped[:1].islower():
        return True
    return previous.endswith(("-", "\u00ad")) and previous[-2:-1].isalpha()


def _looks_like_heading(text: str) -> bool:
    words = text.split()
    if not words or len(words) > MAX_HEADING_WORDS:
        return False
    if text[-1] in _FINAL_PUNCTUATION or text[0].islower():
        return False
    if not any(c.isalpha() for c in text):
        return False
    return not (_LETTER_FORMULA.match(text) or _DATE_LINE.search(text) or _FIELD_LINE.search(text))
