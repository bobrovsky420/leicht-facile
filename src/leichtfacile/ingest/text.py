"""Pasted plain text (or simple Markdown) to units.

- Paragraphs are separated by blank lines. The lines of a paragraph are joined with
  spaces; a word hyphenated at a line end is joined again (`join_lines`). A block whose
  lines are not wrapped, as Word and Outlook paste a letter (one line per paragraph, no
  blank line), is one paragraph per line (`_one_per_line`); short lines in a row (an
  address, a letterhead) stay one paragraph, and so does a closing formula with the
  signature after it.
- "#", "##", ... at the start of a line make a heading of that level.
- A line that starts with a bullet (-, *, +, a bullet character, an en or em dash) is a
  list item, and so is one that starts with "1." / "1)" / "a)" in a sequence: when the
  previous line that opens with a number has the one before, or the next the one after
  (blank lines between the items do not matter), and any one in a block that holds such
  a line. A lone one keeps its number in a paragraph ("3. Stock, Zimmer 304"; "2. Rate
  CHF 400 ..." after it is not its sequence). A following line that is
  indented or starts in lower case continues the item. "1. Januar 2027 ..." is a date,
  not a list item.
- A paragraph of one short line (at most 10 words, no final . ! ? : ; ,) is a heading
  of level 2, unless it is a salutation, a closing formula, a place and date line, a
  field line (a label and a value, `Verfahrensnummer: KES-2026-0187`, an e-mail or a web
  address) or holds a value a fact needs (`segment.HARD_VALUE`: an amount, an IBAN, a
  date with its year, a phone number): a value in a heading is not a must-keep fact.
"""

from __future__ import annotations

import re
from collections import defaultdict

from leichtfacile.ingest.normalize import join_lines, normalize_newlines, normalize_text
from leichtfacile.ingest.segment import DEFAULT_HEADING_LEVEL, HARD_VALUE, MONTHS, Unit
from leichtfacile.schemas import SegmentKind

MAX_HEADING_WORDS = 10
WRAP_WIDTH = 100  # no one wraps a text wider: a longer line is a paragraph of its own

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
# The markers of a numbered or lettered list: "1.", "1)", "(1)", "a)", "(a)".
_ORDERED = re.compile(r"\d{1,3}[.)]|\(\d{1,3}\)|\(?[a-z]\)")
Ordinals = frozenset[tuple[str, int]]  # places of `_place` that are in a sequence
_FINAL_PUNCTUATION = ".!?:;,"
_SENTENCE_END = (".", "!", "?", ":")
# Salutations and closing formulas of letters in German, French and Italian.
_LETTER_FORMULA = re.compile(
    r"^(?:sehr geehrte|liebe[rs]?\b|guten tag|gr\u00fcezi|hallo\b|freundliche gr|"
    r"mit freundlichen|beste gr|herzliche gr|madame|monsieur|mesdames|messieurs|"
    r"ch\u00e8re?s?\b|bonjour|salutations|meilleures salutations|avec (?:nos|mes) meilleures|"
    r"gentile|egregi[oa]\b|spettabile|buongiorno|cordiali saluti|distinti saluti|"
    r"cari?\b|care\b)",
    re.IGNORECASE,
)
# The closing formulas alone: in a block of one paragraph per line, the lines after one
# (the sender, a name, a function) are the signature and stay with it.
_CLOSING = re.compile(
    r"^(?:freundliche gr|mit freundlichen|beste gr|herzliche gr|salutations|"
    r"meilleures salutations|avec (?:nos|mes) meilleures|cordiali saluti|distinti saluti)",
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
    blocks = _blocks(normalize_newlines(text))
    ordinals = _sequences(blocks)
    units: list[Unit] = []
    for block in blocks:
        units.extend(_parse_block(block, ordinals))
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


def _parse_block(lines: list[str], ordinals: Ordinals | None) -> list[Unit]:
    if ordinals is not None and _in_sequence(lines, ordinals):
        ordinals = None  # a numbered list: every marker in it, "a) ..." under "2. ..." too
    if not _one_per_line(lines):
        return _parse_lines(lines, ordinals)
    return [
        unit for group in _line_groups(lines, ordinals) for unit in _parse_lines(group, ordinals)
    ]


def _one_per_line(lines: list[str]) -> bool:
    """A block pasted from Word or Outlook: one line per paragraph and no blank line
    between them, so a letter's title, salutation, paragraphs and closing ran together into
    one paragraph. Wrapped lines fill the width; these do not: a line longer than any wrap
    width, or a title, a salutation or an address line shorter than half the block's
    longest. A list's lines do not count, nor do sentences that each have a line of their
    own (a paragraph written one sentence per line)."""
    body = [line.strip() for line in lines[:-1] if not _bullet(line)]
    if not body:
        return False
    longest = max(len(line.strip()) for line in lines)
    return any(
        len(line) > WRAP_WIDTH or (2 * len(line) < longest and not line.endswith(_SENTENCE_END))
        for line in body
    )


def _line_groups(lines: list[str], ordinals: Ordinals | None) -> list[list[str]]:
    """The lines of a block that is one paragraph per line: each line alone, but a list
    item with the lines that continue it, a closing formula with the signature after it,
    and short lines in a row (an address, a letterhead) together, as before."""
    groups: list[list[str]] = []
    for line in lines:
        if groups and _CLOSING.match(groups[-1][0].strip()):
            groups[-1].append(line)
            continue
        item = _bullet(groups[-1][0], ordinals) if groups else None
        if item and not _bullet(line, ordinals):
            indent = len(item.group("indent").expandtabs(4))
            if _continues_item(line, indent, groups[-1][-1]):
                groups[-1].append(line)
                continue
        if groups and _short(groups[-1][-1], ordinals) and _short(line, ordinals):
            groups[-1].append(line)
            continue
        groups.append([line])
    return groups


def _short(line: str, ordinals: Ordinals | None) -> bool:
    """A line of an address, a letterhead or a list of names: a few words and no sentence
    end, no list item, salutation, closing or place and date line."""
    text = line.strip()
    return (
        len(text.split()) <= MAX_HEADING_WORDS
        and text[-1] not in ".!?:;"
        and not _bullet(line, ordinals)
        and not _LETTER_FORMULA.match(text)
        and not _DATE_LINE.search(text)
    )


def _parse_lines(lines: list[str], ordinals: Ordinals | None) -> list[Unit]:  # noqa: C901
    """The units of lines that belong together; `ordinals`: the numbers and letters that
    open a line of the text (see `_bullet`)."""
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
        bullet = _bullet(line, ordinals)
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


def _bullet(line: str, ordinals: Ordinals | None = None) -> re.Match[str] | None:
    """The line's list marker. A number or a letter only in a sequence (`ordinals`, see
    `_sequences`; None takes every one), and never before a month ("1. Januar 2027 ...")."""
    match = _BULLET.match(line)
    if match is None:
        return None
    marker = match.group("marker")
    if marker[0].isdigit() and marker.endswith("."):
        first = match.group("text").split()[0].strip(".,").lower()
        if first in MONTHS:
            return None  # "1. Januar 2027 ..." is a date
    place = _place(marker)
    if place and ordinals is not None and place not in ordinals:
        return None  # "3. Stock, Zimmer 304": a lone number keeps its place in the text
    return match


def _sequences(blocks: list[list[str]]) -> Ordinals:
    """The numbers and letters that open a line of a sequence: the previous line that
    opens with a number (or a letter) has the one before, or the next line the one after.
    Blank lines between the items do not matter."""
    rows: dict[str, list[int]] = defaultdict(list)
    for block in blocks:
        for line in block:
            match = _bullet(line)
            if match and (place := _place(match.group("marker"))):
                rows[place[0]].append(place[1])
    return frozenset(
        (kind, number)
        for kind, row in rows.items()
        for before, number, after in zip([None, *row[:-1]], row, [*row[1:], None], strict=True)
        if before == number - 1 or after == number + 1
    )


def _in_sequence(lines: list[str], ordinals: Ordinals) -> bool:
    """True when a line of the block opens with a number or a letter in a sequence."""
    for line in lines:
        match = _bullet(line, ordinals)
        if match and _place(match.group("marker")):
            return True
    return False


def _place(marker: str) -> tuple[str, int] | None:
    """A number's or a letter's place: ("0", 3) for "3.", "3)" and "(3)", ("a", 2) for
    "b)" and "(b)"; None for a bullet."""
    if not _ORDERED.fullmatch(marker):
        return None
    inner = marker.strip("().")
    if inner.isdigit():
        return "0", int(inner)
    return "a", ord(inner) - ord("a") + 1


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
    return not (
        _LETTER_FORMULA.match(text)
        or _DATE_LINE.search(text)
        or _FIELD_LINE.search(text)
        or HARD_VALUE.search(text)
    )
