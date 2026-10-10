"""Text normalisation shared by every ingest path.

`normalize_text` makes text from web pages, PDFs and pasted input comparable:

- Unicode NFC;
- soft hyphens, zero-width characters and other invisible control characters removed;
- no-break, thin and other special spaces turned into a plain space;
- typographic ligatures (fi, fl, ff, ...) expanded;
- non-breaking hyphens turned into a plain hyphen;
- a dot-like character between two letters turned into the Mediopunkt U+00B7. Leichte
  Sprache writes long compounds as "Merk·blatt"; PDFs often deliver a bullet, a
  dot operator or a katakana middle dot instead (track_2b/docs/sources.md, section 5);
- a typographic apostrophe between digits (1\u2019500) turned into the ASCII apostrophe;
- runs of spaces and tabs collapsed. Line breaks are kept; more than one blank line
  becomes one blank line.

`join_lines` joins the lines of one paragraph and undoes hyphenation at line ends.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

MEDIOPUNKT = "\u00b7"

# Characters that look like a raised dot. Between two letters they are a Mediopunkt.
DOT_LIKE = (
    "\u00b7"  # middle dot
    "\u0387"  # greek ano teleia
    "\u16eb"  # runic single punctuation
    "\u2022"  # bullet
    "\u2024"  # one dot leader
    "\u2027"  # hyphenation point
    "\u2219"  # bullet operator
    "\u22c5"  # dot operator
    "\u2e31"  # word separator middle dot
    "\u2e33"  # raised dot
    "\u30fb"  # katakana middle dot
    "\ua78f"  # latin letter sinological dot
    "\uf0b7"  # bullet of the Symbol font (private use area)
    "\uff65"  # halfwidth katakana middle dot
)

# Soft hyphen, Mongolian vowel separator, zero-width space, non-joiner and joiner,
# word joiner, byte order mark.
_REMOVE = "\u00ad\u180e\u200b\u200c\u200d\u2060\ufeff"
# Tab, no-break space, Ogham space, en/em quads and spaces up to the hair space,
# narrow no-break space, medium mathematical space, ideographic space.
_SPACES = "\t\u00a0\u1680" + "".join(chr(c) for c in range(0x2000, 0x200B)) + "\u202f\u205f\u3000"
_LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "st",
    "\ufb06": "st",
}
_HYPHENS = "\u2010\u2011"  # hyphen, non-breaking hyphen

_TABLE: dict[int, str | None] = {ord(c): None for c in _REMOVE}
_TABLE.update({ord(c): " " for c in _SPACES})
_TABLE.update({ord(k): v for k, v in _LIGATURES.items()})
_TABLE.update({ord(c): "-" for c in _HYPHENS})
# Remaining C0 and C1 control characters (tab and line feed are handled above).
_TABLE.update({c: None for c in range(0x20) if c not in (0x09, 0x0A)})
_TABLE.update({c: None for c in range(0x7F, 0xA0)})

# Carriage returns, vertical tab, form feed, next line, line separator.
_NEWLINES = re.compile(r"\r\n?|[\x0b\x0c\x85\u2028]")
_PARAGRAPH_SEPARATOR = "\u2029"
_MEDIOPUNKT_RE = re.compile(rf"(?<=[^\W\d_])[{DOT_LIKE}](?=[^\W\d_])")
# Right single quotation mark, modifier letter apostrophe, left single quotation mark,
# prime, acute accent.
_NUMBER_APOSTROPHE_RE = re.compile(r"(?<=\d)[\u2019\u02bc\u2018\u2032\u00b4](?=\d)")
_SPACE_RUN = re.compile(r" {2,}")
_SPACE_AROUND_NEWLINE = re.compile(r" *\n *")
_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_newlines(text: str) -> str:
    """Turn every kind of line break into a line feed (a paragraph separator into two)."""
    return _NEWLINES.sub("\n", text).replace(_PARAGRAPH_SEPARATOR, "\n\n")


def normalize_text(text: str) -> str:
    """Normalise one text (see the module docstring). The result is stripped."""
    text = unicodedata.normalize("NFC", normalize_newlines(text))
    text = text.translate(_TABLE)
    text = _MEDIOPUNKT_RE.sub(MEDIOPUNKT, text)
    text = _NUMBER_APOSTROPHE_RE.sub("'", text)
    text = _SPACE_RUN.sub(" ", text)
    text = _SPACE_AROUND_NEWLINE.sub("\n", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


# -- hyphenation at line ends ------------------------------------------------------

_LINE_END_HYPHEN = re.compile(r"(?<=[^\W_])[-\u2010\u2011]$")
# A hyphen before one of these words shortens a compound ("Kranken- und
# Unfallversicherung") and stays, although the next line starts in lower case.
_CONJUNCTIONS_WORDS = """
    als beziehungsweise bis bzw noch oder resp respektive sowie und wie et ou e ed o od
    oppure
"""
_CONJUNCTIONS = frozenset(_CONJUNCTIONS_WORDS.split())
_FIRST_WORD = re.compile(r"[^\W\d_]+")


def join_lines(lines: Iterable[str]) -> str:
    """Join the lines of one paragraph with spaces, undoing hyphenation at line ends.

    "Prämien-" + "verbilligung" becomes "Prämienverbilligung" because the next
    line starts in lower case; "E-" + "Mail" and "Kranken-" + "Kasse" keep their hyphen;
    "Kranken-" + "und Unfallversicherung" keeps hyphen and space. A soft hyphen at the
    end of a line always marks a hyphenation point.
    """
    out = ""
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        out = _join_two(out, line) if out else line
    return out


def _join_two(left: str, right: str) -> str:
    if left.endswith("\u00ad"):
        return left[:-1] + right
    if _LINE_END_HYPHEN.search(left):
        first = right[0]
        if left[-2].isalpha() and first.islower():
            word = _FIRST_WORD.match(right)
            if word and word.group(0).lower() in _CONJUNCTIONS:
                return f"{left} {right}"
            return left[:-1] + right
        if first.isalnum():
            return left + right
    return f"{left} {right}"
