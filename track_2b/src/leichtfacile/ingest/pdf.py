"""PDFs with a text layer: pdfplumber words to units.

Words come with font size and font name (`extract_words(extra_attrs=...)`). Steps:

1. Running headers and footers are removed: lines in the top or bottom tenth of a page
   that repeat (digits ignored) at the same height on at least half of the pages, and
   page numbers ("3", "Seite 3 | 17", "- 3 -") in those margins.
2. Columns: the left edge of a right-hand column is a position between 20 and 85
   percent of the page width where several words start. It is accepted when at most
   two words cross it, there is text on its left, and at least two lines start at it
   without continuing a line of the left side (that would be a word gap, not a
   gutter). Lines that cross the gutter or run across it with a plain word space
   (titles, full-width paragraphs), together with the other lines of the same title,
   split the page into regions; each region is read left column first, then right
   column. Both St. Gallen PDFs of track_2b/docs/sources.md use two columns; the easy-language
   version puts a glossary in a narrow side column, which therefore follows the main
   text of each region. Three or more columns are not detected.
3. Lines are grouped by vertical overlap. Words that touch are joined without a space:
   pdfplumber splits a word where the font changes, for example at a Mediopunkt taken
   from another font.
4. Paragraphs end at a vertical gap larger than the usual line spacing, at a change of
   font size, at a bold heading line and at a bullet. A paragraph that runs over a
   column or page break continues when its last line has no final punctuation.
5. Headings are short paragraphs set clearly larger than the body text (the most
   frequent size), or bold at body size without final . : , ; Levels follow the size
   rank; bold body-size headings come after all larger sizes.
6. List items start with a bullet character, a dash, a Symbol-font bullet, or an "o"
   that is set in another size or font than the text or starts several lines of the
   column. Following lines at the indentation of the item text continue the item.
7. Hyphenated line breaks are joined (`join_lines`).

A PDF without any extractable text raises `NoTextLayerError`: scans need the model's
image input, which is not available yet.
"""

from __future__ import annotations

import io
import logging
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import pdfplumber

from leichtfacile.ingest.errors import ExtractionError, NoTextLayerError
from leichtfacile.ingest.normalize import DOT_LIKE, join_lines, normalize_text
from leichtfacile.ingest.segment import Unit
from leichtfacile.schemas import SegmentKind

log = logging.getLogger(__name__)

_BOLD = re.compile(r"bold|black|heavy|demi(?!light)", re.IGNORECASE)
_MARGIN = 0.1  # share of the page height searched for running headers and footers
_PAGE_NUMBER = re.compile(
    r"^[-\u2013\u2014\s]*(?:(?:seite|page|pagina|pag\.|p\.|s\.)\s*)?\d{1,4}"
    r"(?:\s*(?:/|\||von|of|de|di|sur|su)\s*\d{1,4})?[-\u2013\u2014\s]*$",
    re.IGNORECASE,
)
_DIGITS = re.compile(r"\d+")
# Bullet glyphs: hyphen, asterisk, bullet, triangular bullet, hyphen bullet, en dash,
# em dash, middle dot, bullet operator, squares, circles, arrows, check marks, diamonds,
# and the private-use bullets of the Symbol and Wingdings fonts.
_BULLET_GLYPHS = (
    "- * \u2022 \u2023 \u2043 \u2013 \u2014 \u00b7 \u2219 \u25aa \u25ab \u25a0 \u25a1 "
    "\u25cf \u25cb \u25e6 \u25ba \u25b6 \u27a2 \u2192 \u2713 \u2714 \u2756 "
    "\u25c6 \u25c7 \uf0b7 \uf0a7 \uf0a8 \uf0d8 \uf076 \uf0fc"
)
_BULLETS = frozenset(_BULLET_GLYPHS.split())
_TERMINAL = ".!?:;"
_CLOSING = "\"')]\u00bb\u201c\u201d\u2019"


@dataclass
class _Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    font: str

    @property
    def bold(self) -> bool:
        return bool(_BOLD.search(self.font))

    @property
    def height(self) -> float:
        return self.bottom - self.top


class _Line:
    """Words on one baseline, sorted left to right."""

    def __init__(self, words: list[_Word], page: int) -> None:
        self.words = sorted(words, key=lambda w: w.x0)
        self.page = page
        self.x0 = min(w.x0 for w in words)
        self.x1 = max(w.x1 for w in words)
        self.top = min(w.top for w in words)
        self.bottom = max(w.bottom for w in words)
        self.size, self.bold = _style(self.words)
        self.text = _join_words(self.words)


@dataclass
class _Page:
    number: int
    width: float
    height: float
    words: list[_Word]


@dataclass
class _Paragraph:
    lines: list[_Line]
    marker: int = 0  # leading words of the first line that form a bullet
    text_x0: float = 0.0  # left edge of the text after the bullet
    size: float = 0.0
    bold: bool = False
    texts: list[str] = field(default_factory=list)

    def finish(self) -> None:
        words = [w for line in self.lines for w in line.words]
        self.size, self.bold = _style(words)
        first = self.lines[0]
        self.texts = [_join_words(first.words[self.marker :])]
        self.texts += [line.text for line in self.lines[1:]]


def extract_pdf(data: bytes) -> tuple[str | None, list[Unit]]:
    """Return the title and the units of a PDF with a text layer."""
    meta_title, pages = _read(data)
    if not any(page.words for page in pages):
        raise NoTextLayerError(
            "the PDF has no text layer (a scan?); scanned documents need image input, "
            "which is not available yet"
        )
    without_text = [page.number for page in pages if not page.words]
    if without_text:
        log.warning("PDF pages without a text layer are skipped: %s", without_text)
    _drop_running_lines(pages)
    blocks = [block for page in pages for block in _page_blocks(page)]
    lines = [line for block in blocks for line in block]
    if not lines:
        raise ExtractionError("the PDF contains only headers, footers and page numbers")
    body = _body_size(lines)
    paragraphs = _paragraphs(blocks, _line_spacing(blocks), body)
    units = _units(paragraphs, body)
    return _title(meta_title, units), units


# -- reading -------------------------------------------------------------------------


def _read(data: bytes) -> tuple[str | None, list[_Page]]:
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as exc:  # pdfminer raises many exception types for broken files
        raise ExtractionError(f"not a readable PDF ({type(exc).__name__})") from exc
    pages = []
    with pdf:
        try:
            title = (pdf.metadata or {}).get("Title")
            for number, page in enumerate(pdf.pages, start=1):
                raw = page.extract_words(extra_attrs=["size", "fontname"])
                words = [
                    _Word(
                        w["text"],
                        float(w["x0"]),
                        float(w["x1"]),
                        float(w["top"]),
                        float(w["bottom"]),
                        float(w["size"]),
                        str(w["fontname"]),
                    )
                    for w in raw
                    if w.get("upright", True) and w["text"].strip()
                ]
                pages.append(_Page(number, float(page.width), float(page.height), words))
        except Exception as exc:
            raise ExtractionError(f"the PDF could not be read ({type(exc).__name__})") from exc
    return (title if isinstance(title, str) else None), pages


def _round(size: float) -> float:
    return round(size * 2) / 2


def _style(words: list[_Word]) -> tuple[float, bool]:
    """The size that covers most characters, and whether 80 percent of them are bold."""
    sizes: Counter[float] = Counter()
    bold = total = 0
    for word in words:
        n = len(word.text)
        sizes[_round(word.size)] += n
        total += n
        bold += n if word.bold else 0
    return sizes.most_common(1)[0][0], bold >= 0.8 * total


def _join_words(words: list[_Word]) -> str:
    if not words:
        return ""
    out = words[0].text
    for previous, word in zip(words, words[1:], strict=False):
        touching = word.x0 - previous.x1 < 0.12 * min(previous.size, word.size)
        mediopunkt = (
            len(previous.text) > 1
            and previous.text[-1] in DOT_LIKE
            and previous.text[-2].isalpha()
            and word.text[:1].isalpha()
        )
        out += word.text if touching or mediopunkt else " " + word.text
    return out


def _group_lines(words: list[_Word], page: int) -> list[_Line]:
    """Group words into lines by vertical overlap."""
    groups: list[list[_Word]] = []
    spans: list[tuple[float, float]] = []
    for word in sorted(words, key=lambda w: (w.top, w.x0)):
        for i in range(len(groups) - 1, max(-1, len(groups) - 4), -1):
            top, bottom = spans[i]
            overlap = min(bottom, word.bottom) - max(top, word.top)
            if overlap >= 0.5 * min(bottom - top, word.height):
                groups[i].append(word)
                if word.height > bottom - top:
                    spans[i] = (word.top, word.bottom)
                break
        else:
            groups.append([word])
            spans.append((word.top, word.bottom))
    return sorted((_Line(group, page) for group in groups), key=lambda line: line.top)


# -- running headers and footers -----------------------------------------------------


def _drop_running_lines(pages: list[_Page]) -> None:
    margin_lines: dict[int, list[tuple[_Line, tuple[str, str] | None]]] = {}
    tops: dict[tuple[str, str], list[tuple[int, float]]] = defaultdict(list)
    for page in pages:
        entries: list[tuple[_Line, tuple[str, str] | None]] = []
        for line in _group_lines(page.words, page.number):
            zone = _zone(line, page)
            key = None
            if zone:
                key = (zone, _DIGITS.sub("#", normalize_text(line.text).lower()))
                tops[key].append((page.number, line.top))
            entries.append((line, key))
        margin_lines[page.number] = entries

    needed = max(2, math.ceil(len(pages) / 2))
    running: dict[tuple[str, str], float] = {}
    for key, places in tops.items():
        middle = statistics.median(top for _, top in places)
        if len({number for number, top in places if abs(top - middle) <= 6}) >= needed:
            running[key] = middle

    for page in pages:
        kept: list[_Word] = []
        for line, key in margin_lines[page.number]:
            if key is not None and (
                (key in running and abs(line.top - running[key]) <= 6)
                or _PAGE_NUMBER.match(normalize_text(line.text))
            ):
                continue
            kept.extend(line.words)
        page.words = kept


def _zone(line: _Line, page: _Page) -> str | None:
    if line.bottom <= page.height * _MARGIN:
        return "top"
    if line.top >= page.height * (1 - _MARGIN):
        return "bottom"
    return None


# -- columns -------------------------------------------------------------------------


_CROSSING = 6.0  # a word crosses the gutter only if it reaches this far into both sides


def _page_blocks(page: _Page) -> list[list[_Line]]:
    """The lines of a page in reading order, as blocks (columns and full-width runs)."""
    if not page.words:
        return []
    lines = _group_lines(page.words, page.number)
    boundary = _column_boundary(page.words, page.width)
    if boundary is None:
        return [lines]
    full = [_is_full_width(line, boundary) for line in lines]
    # A title over both columns often has only one line that crosses the gutter: the
    # neighbouring lines in the same style on the left side belong to it.
    for i in range(1, len(lines)):
        if not full[i] and full[i - 1] and _same_run(lines[i - 1], lines[i], boundary):
            full[i] = True
    for i in range(len(lines) - 2, -1, -1):
        if not full[i] and full[i + 1] and _same_run(lines[i + 1], lines[i], boundary):
            full[i] = True

    blocks: list[list[_Line]] = []
    left: list[_Word] = []
    right: list[_Word] = []
    run: list[_Line] | None = None  # the current run of full-width lines

    def close_columns() -> None:
        for side in (left, right):
            if side:
                blocks.append(_group_lines(side, page.number))
                side.clear()

    for line, is_full in zip(lines, full, strict=True):
        if is_full:
            close_columns()  # the region above this line comes first
            if run is None:
                run = []
                blocks.append(run)
            run.append(line)
        else:
            run = None
            for word in line.words:
                (left if (word.x0 + word.x1) / 2 < boundary else right).append(word)
    close_columns()
    return blocks


def _is_full_width(line: _Line, boundary: float) -> bool:
    """A word crosses the gutter, or the text flows across it with a plain word space."""
    if any(w.x0 < boundary - _CROSSING and w.x1 > boundary + _CROSSING for w in line.words):
        return True
    left = [w for w in line.words if (w.x0 + w.x1) / 2 < boundary]
    right = [w for w in line.words if (w.x0 + w.x1) / 2 >= boundary]
    if not left or not right:
        return False
    last = max(left, key=lambda w: w.x1)
    first = min(right, key=lambda w: w.x0)
    same_size = _round(last.size) == _round(first.size)
    return same_size and first.x0 - last.x1 < 0.6 * last.size


def _same_run(full_line: _Line, line: _Line, boundary: float) -> bool:
    return (
        line.x1 <= boundary
        and line.size == full_line.size
        and line.bold == full_line.bold
        and abs(line.top - full_line.top) <= 1.6 * full_line.size
    )


def _column_boundary(words: list[_Word], width: float) -> float | None:
    """The left edge of a right-hand column, or None for a single-column page.

    Candidates are x positions between 20 and 85 percent of the page width where
    several words start (within 3 points of each other): the left edge of a column. A
    candidate is accepted when at most two words cross it (a title over both columns)
    and `_is_column_split` confirms it. The most frequent start position is tried first.
    """
    if len(words) < 20:
        return None
    low, high = 0.2 * width, 0.85 * width
    clusters: list[list[float]] = []
    for x in sorted(w.x0 for w in words if low <= w.x0 <= high):
        if clusters and x - clusters[-1][-1] <= 3:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    for cluster in sorted(clusters, key=len, reverse=True):
        if len(cluster) < 2:
            break
        boundary = cluster[0] - 0.5
        crossing = sum(
            1 for w in words if w.x0 < boundary - _CROSSING and w.x1 > boundary + _CROSSING
        )
        if crossing <= 2 and _is_column_split(words, boundary):
            return boundary
    return None


def _is_column_split(words: list[_Word], boundary: float) -> bool:
    """Check a candidate edge: text on the left, lines on the right that start at the edge.

    The right side may be small (a glossary entry of two lines). Lines whose left part
    stops just before the edge do not count: that is a word gap inside a single column,
    not a gutter, and most right-hand lines must not be of that kind.
    """
    left = [w for w in words if w.x1 <= boundary]
    if len(left) < 8:
        return False
    right_lines = _group_lines([w for w in words if w.x0 >= boundary], 0)
    free = [
        line
        for line in right_lines
        if not any(
            w.bottom > line.top and w.top < line.bottom and line.x0 - w.x1 < 1.5 * w.size
            for w in left
        )
    ]
    at_edge = [line for line in free if line.x0 <= boundary + 8]
    return len(at_edge) >= 2 and len(at_edge) >= 0.5 * len(free) >= 0.25 * len(right_lines)


# -- paragraphs ----------------------------------------------------------------------


def _body_size(lines: list[_Line]) -> float:
    sizes: Counter[float] = Counter()
    for line in lines:
        for word in line.words:
            sizes[_round(word.size)] += len(word.text)
    return sizes.most_common(1)[0][0]


def _line_spacing(blocks: list[list[_Line]]) -> dict[float, float]:
    """Typical distance from one line top to the next, per font size."""
    distances: dict[float, list[float]] = defaultdict(list)
    for block in blocks:
        for a, b in zip(block, block[1:], strict=False):
            distance = b.top - a.top
            if a.size == b.size and 0.8 * a.size < distance < 2 * a.size:
                distances[a.size].append(distance)
    return {size: statistics.median(values) for size, values in distances.items()}


def _paragraphs(
    blocks: list[list[_Line]], spacing: dict[float, float], body: float
) -> list[_Paragraph]:
    paragraphs: list[_Paragraph] = []
    for block in blocks:
        o_bullets = _o_bullet_lines(block)
        current: _Paragraph | None = None
        for line in block:
            marker = _bullet_marker(line, o_bullets)
            if current is None and paragraphs and _continues(paragraphs[-1], line, marker, body):
                current = paragraphs[-1]
                current.lines.append(line)
            elif current is None or _breaks(current, line, marker, spacing):
                current = _Paragraph([line], marker, line.words[marker].x0)
                paragraphs.append(current)
            else:
                current.lines.append(line)
    for paragraph in paragraphs:
        paragraph.finish()
    return paragraphs


def _o_bullet_lines(block: list[_Line]) -> set[int]:
    """Lines that start with a lone "o": a bullet when several lines of the block do."""
    lines = [line for line in block if len(line.words) > 1 and line.words[0].text == "o"]
    return {id(line) for line in lines} if len(lines) >= 2 else set()


def _bullet_marker(line: _Line, o_bullets: set[int]) -> int:
    """1 when the first word of the line is a bullet, else 0."""
    if len(line.words) < 2:
        return 0
    first, second = line.words[0], line.words[1]
    if first.text in _BULLETS:
        return 1
    if first.text == "o" and (
        id(line) in o_bullets or first.size < 0.95 * second.size or first.font != second.font
    ):
        return 1
    return 0


def _headingish(line: _Line) -> bool:
    return line.bold and not line.text.rstrip().endswith((".", ":", ",", ";"))


def _breaks(paragraph: _Paragraph, line: _Line, marker: int, spacing: dict[float, float]) -> bool:
    """True when the line starts a new paragraph."""
    previous = paragraph.lines[-1]
    if marker:
        return True
    if abs(line.size - previous.size) > 0.08 * previous.size:
        return True
    if line.top - previous.top > 1.4 * spacing.get(previous.size, 1.2 * previous.size):
        return True
    if line.bold != previous.bold and (_headingish(previous) or _headingish(line)):
        return True
    return bool(paragraph.marker) and line.x0 < paragraph.text_x0 - 3


def _continues(paragraph: _Paragraph, line: _Line, marker: int, body: float) -> bool:
    """True when a body paragraph runs on from the previous column or page."""
    last = paragraph.lines[-1]
    if marker or paragraph.marker or line.bold or last.bold:
        return False
    if not (line.size == last.size == body):
        return False
    text = last.text.rstrip().rstrip(_CLOSING)
    return bool(text) and text[-1] not in _TERMINAL


# -- units ---------------------------------------------------------------------------


def _units(paragraphs: list[_Paragraph], body: float) -> list[Unit]:
    kinds: list[SegmentKind] = []
    texts: list[str] = []
    for paragraph in paragraphs:
        text = join_lines(paragraph.texts)
        texts.append(text)
        if paragraph.marker:
            kinds.append("list_item")
        elif _is_heading(paragraph, text, body):
            kinds.append("heading")
        else:
            kinds.append("paragraph")
    sizes = sorted(
        {p.size for p, kind in zip(paragraphs, kinds, strict=True) if kind == "heading"},
        reverse=True,
    )
    large = [size for size in sizes if size >= 1.1 * body]
    units = []
    for paragraph, kind, text in zip(paragraphs, kinds, texts, strict=True):
        level = None
        if kind == "heading":
            rank = large.index(paragraph.size) if paragraph.size in large else len(large)
            level = min(rank + 1, 6)
        units.append(Unit(kind, text, heading_level=level, page=paragraph.lines[0].page))
    return units


def _is_heading(paragraph: _Paragraph, text: str, body: float) -> bool:
    words = len(text.split())
    if not words or words > 25 or len(paragraph.lines) > 4:
        return False
    ratio = paragraph.size / body
    if ratio >= 1.25:
        return True
    if ratio >= 1.1 and (paragraph.bold or words <= 12):
        return True
    return (
        paragraph.bold
        and ratio >= 0.95
        and words <= 15
        and not text.rstrip().endswith((".", ":", ",", ";"))
    )


_NOT_A_TITLE = re.compile(
    r"\.(?:docx?|dotx?|pdf|indd|rtf|odt|qxp|pages)$|^(?:microsoft word|untitled|unbenannt)",
    re.IGNORECASE,
)


def _title(meta_title: str | None, units: list[Unit]) -> str | None:
    """The metadata title when it looks like one, else the first top-level heading."""
    if meta_title:
        title = normalize_text(meta_title)
        if len(title) >= 3 and any(c.isalpha() for c in title) and not _NOT_A_TITLE.search(title):
            return title
    headings = [u for u in units if u.kind == "heading"]
    if not headings:
        return None
    top = min(u.heading_level or 6 for u in headings)
    return next(u.text for u in headings if (u.heading_level or 6) == top)
