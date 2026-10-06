"""Web pages: download with httpx, extract the main content with trafilatura, map to units.

Extraction uses trafilatura's XML output in its default (balanced) mode with tables,
without comments, links, images, formatting and metadata (the metadata step parses
dates in 200 locales and costs seconds per page; the title comes from og:title or
<title>). `<head rend="hN">` becomes a heading of level N, `<p>` a paragraph,
`<list>`/`<item>` list items and `<table>`/`<cell>` table cells; an item or cell that
contains block elements is flattened into its blocks. favor_precision dropped whole
sections of zh.ch pages and favor_recall lost the accordion sections of bag.admin.ch,
so neither is used.

Tuning for Swiss official pages, checked on zh.ch, be.ch and bag.admin.ch and on the
pages of data/pairs/manifest.jsonl (5 and 6 October 2026). The page is prepared before
trafilatura sees it:

- Scripts, styles and templates are removed.
- Phone and e-mail links (tel:, mailto:) are unwrapped. trafilatura deletes short
  blocks that are dense with links, which removed lines such as "Polizei: 117" and
  most contact cards.
- Accordion and tab panels are revealed. trafilatura discards elements hidden with
  `hidden`, `aria-hidden="true"` or an inline `display:none` / `visibility:hidden`, and
  that is how collapsed accordion panels are marked (be.ch, bag.admin.ch). A panel is an
  element referenced by `aria-controls`, labelled by a disclosure button
  (`aria-labelledby`), an element with `role="tabpanel"` or `role="region"`, or a
  `<details>` element. Without this step the fees, addresses and opening hours of the
  Bern tax page and all accordion sections of the BAG page are lost. Tab panels hidden
  by CSS classes (be.ch) are extracted by trafilatura anyway.
- Disclosure buttons (`aria-expanded` or `aria-controls`) that contain a heading or sit
  inside one are unwrapped, so the accordion title survives as a heading (trafilatura
  drops buttons). A disclosure button with plain text becomes a paragraph.
- Screen-reader-only text (`visually-hidden`, `sr-only`, ...) is removed. It holds hints
  such as "Verwenden Sie die Akkordeon-Bedienelemente ..." and hidden headings.
- Inline formatting (b, strong, em, ...) is unwrapped and block elements get spaces
  around them; otherwise trafilatura glues words ("zahlenjedes", "Schritt1").
- Navigation widgets are removed: a heading followed only by links or buttons (language
  switch, feedback buttons, "News" with a "Mehr Beiträge" link) and lists of teaser
  cards (every item a link around a heading or paragraph).

After extraction, paragraphs that start with a bullet character become list items, and
headings at the end of the page that have no content (feedback widgets) are dropped.

Contact blocks: trafilatura still drops many contact cards and contact boxes (zh.ch,
be.ch, sg.ch, zg.ch), although phone numbers and e-mail addresses are exactly the facts
the checker verifies. A compact block (at most 2000 characters, outside header, footer
and navigation) that holds a phone number or e-mail address missing from the
extraction is put back at its place in the document (see `_rescue_contacts`).

If trafilatura finds nothing, a simple fallback converts the prepared page itself.
"""

from __future__ import annotations

import codecs
import copy
import difflib
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import trafilatura
from trafilatura.utils import load_html

from leichtfacile import __version__
from leichtfacile.ingest.errors import ExtractionError, FetchError
from leichtfacile.ingest.normalize import join_lines, normalize_text
from leichtfacile.ingest.segment import Unit
from leichtfacile.schemas import SegmentKind

log = logging.getLogger(__name__)

USER_AGENT = f"leicht-facile/{__version__} (+https://github.com/bobrovsky420/leicht-facile)"
DEFAULT_TIMEOUT_S = 30.0
DEFAULT_MAX_BYTES = 15_000_000

_CHARSET = re.compile(r"charset\s*=\s*[\"']?([\w.:-]+)", re.IGNORECASE)
_META_CHARSET = re.compile(rb"<meta[^>]+charset\s*=\s*[\"']?([\w.:-]+)", re.IGNORECASE)


@dataclass(frozen=True)
class FetchedResource:
    content: bytes
    content_type: str  # the Content-Type header as sent, possibly with parameters
    final_url: str  # after redirects
    fetched_at: datetime

    @property
    def media_type(self) -> str:
        return self.content_type.split(";", 1)[0].strip().lower()

    @property
    def charset(self) -> str | None:
        match = _CHARSET.search(self.content_type)
        return match.group(1) if match else None


def fetch_url(
    url: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_bytes: int = DEFAULT_MAX_BYTES,
    client: httpx.Client | None = None,
) -> FetchedResource:
    """Download a URL (following redirects) with a size limit."""
    try:
        scheme = httpx.URL(url).scheme
    except (httpx.InvalidURL, TypeError) as exc:
        raise FetchError(f"invalid URL {url!r}") from exc
    if scheme not in ("http", "https"):
        raise FetchError(f"only http and https URLs can be fetched, not {url!r}")
    http = client or httpx.Client()
    try:
        with http.stream(
            "GET",
            url,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=timeout_s,
        ) as response:
            response.raise_for_status()
            declared = response.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > max_bytes:
                raise FetchError(f"{url} is larger than {max_bytes} bytes")
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise FetchError(f"{url} is larger than {max_bytes} bytes")
                chunks.append(chunk)
            return FetchedResource(
                content=b"".join(chunks),
                content_type=response.headers.get("content-type", ""),
                final_url=str(response.url),
                fetched_at=datetime.now(UTC),
            )
    except httpx.HTTPStatusError as exc:
        raise FetchError(f"GET {url} failed: HTTP {exc.response.status_code}") from exc
    except httpx.TimeoutException as exc:
        raise FetchError(f"GET {url} timed out after {timeout_s:g} s") from exc
    except httpx.HTTPError as exc:
        raise FetchError(f"GET {url} failed: {type(exc).__name__}: {exc}") from exc
    finally:
        if client is None:
            http.close()


def decode_html(content: bytes, charset: str | None = None) -> str:
    """Decode HTML bytes: BOM, declared charset, meta charset, UTF-8, then Windows-1252."""
    meta = _META_CHARSET.search(content[:4096])
    declared = meta.group(1).decode("ascii", "ignore") if meta else None
    return decode_bytes(content, charset, declared)


def decode_bytes(content: bytes, *charsets: str | None) -> str:
    """Decode with the first charset that works; Latin-1 labels are read as Windows-1252."""
    if content.startswith(codecs.BOM_UTF8):
        return content[len(codecs.BOM_UTF8) :].decode("utf-8", errors="replace")
    for name in (*charsets, "utf-8"):
        if not name:
            continue
        try:
            codec = codecs.lookup(name).name
        except LookupError:
            continue
        if codec in ("ascii", "iso8859-1"):
            codec = "cp1252"  # what browsers do
        try:
            return content.decode(codec)
        except UnicodeDecodeError:
            continue
    return content.decode("cp1252", errors="replace")


# -- extraction ----------------------------------------------------------------------


def extract_html(html: str, url: str | None = None) -> tuple[str | None, list[Unit]]:
    """Return the page title and the units of the main content."""
    tree = _prepare(_parse(html))
    title = _page_title(tree)
    xml = trafilatura.extract(
        copy.deepcopy(tree),  # trafilatura prunes the tree it gets
        url=url,
        output_format="xml",
        include_tables=True,
        include_comments=False,
        include_formatting=False,
        include_links=False,
        include_images=False,
        with_metadata=False,  # metadata means date parsing in 200 locales: seconds per page
        deduplicate=False,
    )
    units: list[Unit] = []
    if xml:
        main = ET.fromstring(xml).find("main")
        if main is not None:
            _walk(main, units)
    if not units or _flattened(units, tree):
        units = _fallback_units(tree)
    else:
        units = _rescue_contacts(tree, _tidy(units))
    return normalize_text(title or "") or None, _tidy(units)


def _flattened(units: list[Unit], tree: Any) -> bool:
    """True for a short page that trafilatura returned without its headings.

    On very short inputs trafilatura falls back to a baseline extractor that merges
    headings into paragraphs; the page's own structure is better then.
    """
    if any(unit.kind == "heading" for unit in units):
        return False
    body = tree.find(".//body")
    root = body if body is not None else tree
    if len(_text_outside(root, _FALLBACK_SKIP)) > _SHORT_PAGE_CHARS:
        return False
    return any(_text_outside(h, frozenset()).strip() for h in root.iter(*_HEADING_TAGS))


def _parse(html: str) -> Any:
    if not re.search(r"<(?:html|body)\b", html[:5000], re.IGNORECASE):
        html = f"<html><body>{html}</body></html>"
    tree = load_html(html)
    if tree is None:
        raise ExtractionError("the input is not readable HTML")
    return tree


def _page_title(tree: Any) -> str | None:
    """og:title, else the <title> without the site name after " | ", else the first <h1>."""
    for meta in tree.iter("meta"):
        if (meta.get("property") or meta.get("name") or "").lower() == "og:title":
            content = (meta.get("content") or "").strip()
            if content:
                return content
    element = tree.find(".//title")
    if element is not None:
        text = element.text_content().split(" | ")[0].strip()
        if text:
            return text
    for heading in tree.iter("h1"):
        text = heading.text_content().strip()
        if text:
            return text
    return None


# -- preparing the page --------------------------------------------------------------

_SR_ONLY = re.compile(
    r"(?:^|\s)(?:visually-?hidden|sr-only|sr-text|screen-?reader-(?:text|only)|show-for-sr"
    r"|element-invisible|hidden-visually|u-visually-hidden|a11y-hidden)(?:\s|$)",
    re.IGNORECASE,
)
_HIDING_STYLE = re.compile(
    r"(?:display\s*:\s*none|visibility\s*:\s*hidden)\s*(?:!\s*important)?\s*;?", re.IGNORECASE
)
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_BLOCK_TAGS = (
    "address",
    "article",
    "aside",
    "blockquote",
    "dd",
    "details",
    "div",
    "dl",
    "dt",
    "figcaption",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "summary",
    "table",
    "td",
    "th",
    "tr",
    "ul",
)
_INLINE_TAGS = ("abbr", "acronym", "b", "big", "cite", "dfn", "em", "font", "i", "mark")
_INLINE_TAGS += ("small", "strong", "tt", "u")
_INTERACTIVE_TAGS = frozenset({"a", "button", "input", "label", "option", "select", "textarea"})
_CONTAINER_TAGS = frozenset(
    {"article", "dd", "details", "div", "dl", "li", "ol", "p", "section", "table", "ul"}
)
_CHROME_TAGS = frozenset({"header", "nav", "footer"})
_PANEL_ROLES = frozenset({"tabpanel", "region"})
_CONTACT_SCHEMES = ("tel:", "mailto:", "fax:", "callto:", "sms:")


def _prepare(tree: Any) -> Any:
    for element in list(tree.iter("script", "style", "noscript", "template")):
        if element.getparent() is not None:
            element.drop_tree()
    _drop_screen_reader_text(tree)
    _unwrap_contact_links(tree)
    _reveal_panels(tree)
    _unwrap_disclosure_buttons(tree)
    _drop_navigation_widgets(tree)
    _separate_blocks(tree)
    for element in list(tree.iter(*_INLINE_TAGS)):
        if element.getparent() is not None:
            element.drop_tag()
    return tree


def _elements(tree: Any) -> list[Any]:
    return [e for e in tree.iter() if isinstance(e.tag, str)]


def _drop_screen_reader_text(tree: Any) -> None:
    for element in _elements(tree):
        if element.getparent() is not None and _SR_ONLY.search(element.get("class") or ""):
            element.drop_tree()


def _unwrap_contact_links(tree: Any) -> None:
    """Phone and e-mail links are content: keep their text, drop the link.

    trafilatura deletes short blocks dense with links, which removes contact cards and
    lines such as "Polizei: 117" when the number is a tel: link.
    """
    for link in list(tree.iter("a")):
        href = (link.get("href") or "").strip().lower()
        if href.startswith(_CONTACT_SCHEMES) and link.getparent() is not None:
            tail = link.tail or ""
            if not tail or tail[0].isalnum():
                link.tail = " " + tail  # "Tel. 031 638 81 11" + "Kontaktformular" side by side
            link.drop_tag()


def _reveal_panels(tree: Any) -> None:
    by_id = {e.get("id"): e for e in _elements(tree) if e.get("id")}
    panels = []
    for element in _elements(tree):
        for ref in (element.get("aria-controls") or "").split():
            if ref in by_id:
                panels.append(by_id[ref])
        if (element.get("role") or "").lower() in _PANEL_ROLES or element.tag == "details":
            panels.append(element)
        labels = (element.get("aria-labelledby") or "").split()
        if any(_is_trigger(by_id.get(ref)) for ref in labels):
            panels.append(element)
    for panel in panels:
        for element in panel.iter():
            if not isinstance(element.tag, str):
                continue
            element.attrib.pop("hidden", None)
            if element.tag in _CONTAINER_TAGS and element.get("aria-hidden") == "true":
                del element.attrib["aria-hidden"]
            style = element.get("style")
            if style and _HIDING_STYLE.search(style):
                element.set("style", _HIDING_STYLE.sub("", style))


def _is_trigger(element: Any) -> bool:
    if element is None:
        return False
    return (
        element.tag == "button"
        or element.get("role") in ("button", "tab")
        or element.get("aria-expanded") is not None
    )


def _unwrap_disclosure_buttons(tree: Any) -> None:
    by_id = {e.get("id"): e for e in _elements(tree) if e.get("id")}
    for button in list(tree.iter("button")):
        if button.getparent() is None:
            continue
        controls = (button.get("aria-controls") or "").split()
        if button.get("aria-expanded") is None and not controls:
            continue
        in_heading = any(a.tag in _HEADING_TAGS for a in button.iterancestors())
        has_heading = any(d.tag in _HEADING_TAGS for d in button.iterdescendants())
        if in_heading or has_heading:
            button.drop_tag()
            continue
        controlled = [by_id[ref] for ref in controls if ref in by_id]
        has_content = any(len(c.text_content().strip()) >= 20 for c in controlled)
        in_chrome = any(a.tag in _CHROME_TAGS for a in button.iterancestors())
        if has_content and not in_chrome and button.text_content().strip():
            button.tag = "p"  # the accordion title of a plain-text disclosure button


def _drop_navigation_widgets(tree: Any) -> None:
    for heading in list(tree.iter(*_HEADING_TAGS)):
        if heading.getparent() is None:
            continue
        following = []
        for sibling in heading.itersiblings():
            if not isinstance(sibling.tag, str):
                continue
            if sibling.tag in _HEADING_TAGS or _has(sibling, _HEADING_TAGS):
                break
            following.append(sibling)
        with_text = [s for s in following if s.text_content().strip()]
        if with_text and all(not _free_text(s).strip() for s in with_text):
            controls = sum(_count_controls(s) for s in with_text)
            bare = any(s.tag in _INTERACTIVE_TAGS for s in with_text)
            if controls >= 2 or bare:
                for sibling in with_text:
                    sibling.drop_tree()
                heading.drop_tree()
    for element in list(tree.iter("ul", "ol")):
        if element.getparent() is None:
            continue
        items = [li for li in element if li.tag == "li" and li.text_content().strip()]
        if len(items) >= 2 and all(_is_teaser(li) for li in items):
            element.drop_tree()


def _free_text(element: Any) -> str:
    """Text of the element that is not inside a link, button or form control."""
    return _text_outside(element, _INTERACTIVE_TAGS)


def _text_outside(element: Any, tags: frozenset[str]) -> str:
    """Text of the element that is not inside an element with one of the tags."""
    if not isinstance(element.tag, str) or element.tag in tags:
        return ""
    parts = [element.text or ""]
    for child in element:
        parts.append(_text_outside(child, tags))
        parts.append(child.tail or "")
    return "".join(parts)


def _count_controls(element: Any) -> int:
    return sum(
        1
        for e in element.iter(*_INTERACTIVE_TAGS)
        if isinstance(e.tag, str) and e.text_content().strip()
    )


def _is_teaser(item: Any) -> bool:
    if _free_text(item).strip():
        return False
    return any(_has(link, (*_HEADING_TAGS, "p")) for link in item.iter("a"))


def _has(element: Any, tags: Any) -> bool:
    """True when the element or a descendant has one of the tags."""
    return next(element.iter(*tags), None) is not None


def _separate_blocks(tree: Any) -> None:
    for element in list(tree.iter(*_BLOCK_TAGS)):
        parent = element.getparent()
        if parent is None:
            continue
        previous = element.getprevious()
        if previous is not None:
            previous.tail = (previous.tail or "") + " "
        else:
            parent.text = (parent.text or "") + " "
        element.tail = " " + (element.tail or "")


# -- trafilatura XML to units --------------------------------------------------------

_XML_BLOCKS = frozenset({"head", "p", "list", "table", "quote", "code", "div", "main"})
_BULLET_PARAGRAPH = re.compile(
    r"^[-*\u2022\u2023\u2043\u2013\u2014\u25aa\u25cf\u25e6\u00b7]\s+(?=\S)"
)
_HEADING_REND = re.compile(r"^h([1-6])$")


def _walk(element: ET.Element, units: list[Unit], kind: SegmentKind = "paragraph") -> None:
    """Add the units of an element; loose inline text becomes a unit of `kind`."""
    buffer = [element.text or ""]

    def flush() -> None:
        _add(units, kind, "".join(buffer))
        buffer.clear()

    for child in element:
        if child.tag in _XML_BLOCKS:
            flush()
            _block(child, units)
        elif child.tag == "lb":
            buffer.append("\n")
        else:
            buffer.append(_xml_text(child))
        buffer.append(child.tail or "")
    flush()


def _block(element: ET.Element, units: list[Unit]) -> None:
    tag = element.tag
    if tag == "head":
        match = _HEADING_REND.match(element.get("rend") or "")
        level = int(match.group(1)) if match else None
        _add(units, "heading", _xml_text(element), level)
    elif tag == "list":
        for child in element:
            if child.tag == "item":
                _walk(child, units, "list_item")
            else:
                _block(child, units)
    elif tag == "table":
        for row in element.iter("row"):
            for cell in row:
                if cell.tag == "cell":
                    _walk(cell, units, "table_cell")
    else:
        _walk(element, units, "paragraph")


def _xml_text(element: ET.Element) -> str:
    parts = [element.text or ""]
    for child in element:
        parts.append("\n" if child.tag == "lb" else _xml_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _add(units: list[Unit], kind: SegmentKind, text: str, level: int | None = None) -> None:
    text = normalize_text(join_lines(text.split("\n")))
    if text:
        units.append(Unit(kind, text, heading_level=level if kind == "heading" else None))


def _tidy(units: list[Unit]) -> list[Unit]:
    out = []
    for unit in units:
        if unit.kind == "paragraph" and (match := _BULLET_PARAGRAPH.match(unit.text)):
            unit = Unit("list_item", unit.text[match.end() :])
        out.append(unit)
    while out and out[-1].kind == "heading":
        out.pop()  # headings of widgets whose content was removed
    return out


# -- fallback ------------------------------------------------------------------------

_FALLBACK_DROP = (
    "script",
    "style",
    "noscript",
    "template",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "button",
    "svg",
)


def _fallback_units(tree: Any) -> list[Unit]:
    """Units of the prepared page itself, without page chrome."""
    body = tree.find(".//body")
    units: list[Unit] = []
    _walk_html(body if body is not None else tree, units, "paragraph", _FALLBACK_SKIP)
    return units


_HTML_KINDS: dict[str, SegmentKind] = {
    **dict.fromkeys(_HEADING_TAGS, "heading"),
    "li": "list_item",
    "dt": "list_item",
    "td": "table_cell",
    "th": "table_cell",
}
_HTML_BLOCKS = frozenset(_BLOCK_TAGS) | {"figure", "hr", "tbody", "tfoot", "thead"}


def _walk_html(
    element: Any,
    units: list[Unit],
    kind: SegmentKind,
    skip: frozenset[str],
    marks: dict[int, int] | None = None,
    origins: list[int] | None = None,
    origin: int = -1,
) -> None:
    """Append the units under element in document order.

    Headings, list items and table cells become units of their kind; any other text
    between block boundaries becomes a paragraph, so text that sits directly in a
    container next to other blocks is kept. Elements in `skip` are left out, and so is
    text made only of links (navigation, "Route (Google)"). `marks` maps elements to an
    origin that is recorded in `origins` for every unit below them.
    """
    if marks is not None:
        origin = marks.get(id(element), origin)
    if element.tag in _HEADING_TAGS:  # a heading is one unit, whatever its markup
        count = len(units)
        _add(units, "heading", element.text_content(), int(element.tag[1]))
        if origins is not None and len(units) > count:
            origins.append(origin)
        return
    pieces: list[tuple[str, bool]] = [(element.text or "", False)]  # (text, inside a link)

    def flush() -> None:
        if any(text.strip() and not linked for text, linked in pieces):
            count = len(units)
            _add(units, kind, "".join(text for text, _ in pieces))
            if origins is not None and len(units) > count:
                origins.append(origin)
        pieces.clear()

    for child in element:
        if not isinstance(child.tag, str):
            pieces.append((child.tail or "", False))
            continue
        if child.tag in skip or (child.get("role") or "").lower() in _CHROME_ROLES:
            pieces.append((child.tail or "", False))
            continue
        if child.tag in _HTML_BLOCKS:
            flush()
            child_kind = _HTML_KINDS.get(child.tag, "paragraph")
            _walk_html(child, units, child_kind, skip, marks, origins, origin)
        elif child.tag == "br":
            pieces.append(("\n", False))
        else:
            pieces.append((child.text_content(), child.tag == "a" or not _free_text(child).strip()))
        pieces.append((child.tail or "", False))
    flush()


# -- rescue of contact blocks --------------------------------------------------------

# Swiss phone numbers (+41 / 0041 / 0 and nine digits in any grouping) and e-mail addresses.
_PHONE = re.compile(r"(?:\+41|(?<!\d)0041|(?<!\d)0)(?:[\s./-]?\(0\))?(?:[\s./-]?\d){9}(?!\d)")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63})+")
_CHROME_ROLES = frozenset({"banner", "contentinfo", "navigation", "search"})
_RESCUE_MAX_CHARS = 2000
_SHORT_PAGE_CHARS = 2000
_CONTEXT_CHARS = 200
_RESCUE_SKIP = frozenset(_FALLBACK_DROP) - {"aside"}  # contact boxes often sit in an aside
_FALLBACK_SKIP = frozenset(_FALLBACK_DROP)


def _facts(text: str) -> set[str]:
    """Phone numbers (as national digits) and e-mail addresses (lower case) in a text."""
    facts = {address.lower().rstrip(".") for address in _EMAIL.findall(text)}
    for match in _PHONE.findall(text):
        digits = re.sub(r"\D", "", match)
        if digits.startswith("0041"):
            digits = "0" + digits[4:]
        elif digits.startswith("41") and len(digits) == 11:
            digits = "0" + digits[2:]
        facts.add(digits)
    return facts


def _rescue_contacts(tree: Any, units: list[Unit]) -> list[Unit]:
    """Put back contact blocks that trafilatura dropped.

    trafilatura drops many contact cards and contact boxes of official pages (zh.ch,
    be.ch, sg.ch, zg.ch), but phone numbers and e-mail addresses are facts the checker
    verifies. A contact block is a compact element (at most 2000 characters, outside
    header, footer and navigation) with a phone number or e-mail address that the
    extraction lacks. The whole page is converted to units in document order and the
    extracted units are aligned to them; the units of contact blocks that the
    extraction lacks are inserted at their place in the document.
    """
    have = _facts(" ".join(unit.text for unit in units))
    body = tree.find(".//body")
    root = body if body is not None else tree
    blocks: list[Any] = []

    def visit(element: Any) -> None:
        if not isinstance(element.tag, str) or element.tag in _RESCUE_SKIP:
            return
        if (element.get("role") or "").lower() in _CHROME_ROLES:
            return
        text = element.text_content()
        if not _facts(text) - have:
            return
        if len(text) <= _RESCUE_MAX_CHARS and element is not root and element.tag != "main":
            blocks.extend(_contact_blocks(element, _facts(text) - have))
            return
        for child in element:
            visit(child)

    visit(root)
    if not blocks:
        return units

    page: list[Unit] = []
    origins: list[int] = []
    marks = {id(block): i for i, block in enumerate(blocks)}
    _walk_html(root, page, "paragraph", _RESCUE_SKIP, marks, origins)
    page_keys = [_key(u.text) for u in page]
    keys = [_key(u.text) for u in units]
    matcher = difflib.SequenceMatcher(None, keys, page_keys, autojunk=False)
    place: list[int | None] = [None] * len(units)
    for a, b, size in matcher.get_matching_blocks():
        for k in range(size):
            place[a + k] = b + k
    matched = {p for p in place if p is not None}
    extracted = " ".join(keys)
    missing = [
        (i, page[i])
        for i in range(len(page))
        if origins[i] >= 0
        and i not in matched
        and not (len(page_keys[i]) >= 40 and page_keys[i] in extracted)
    ]
    result: list[Unit] = []
    pending = iter(missing)
    upcoming = next(pending, None)
    for unit, position in zip(units, place, strict=True):
        while upcoming is not None and position is not None and upcoming[0] < position:
            result.append(upcoming[1])
            upcoming = next(pending, None)
        result.append(unit)
    while upcoming is not None:
        result.append(upcoming[1])
        upcoming = next(pending, None)
    # A rescued heading with nothing under it belongs to a widget around the contact
    # block (for example "Danke für die Rückmeldung!" of a feedback form).
    rescued = {id(unit) for _, unit in missing}
    kept = []
    for i, unit in enumerate(result):
        if id(unit) in rescued and unit.kind == "heading":
            following = result[i + 1] if i + 1 < len(result) else None
            level = unit.heading_level or 2
            if following is None or (
                following.kind == "heading" and (following.heading_level or 2) <= level
            ):
                continue
        kept.append(unit)
    if missing:
        log.debug("rescued %d units from %d contact blocks", len(missing), len(blocks))
    return kept


def _contact_blocks(element: Any, missing: set[str]) -> list[Any]:
    """The smallest elements around the missing facts that keep the card around them.

    An element is a block when the content beside the elements holding the facts is
    small (headings plus at most 200 characters, such as the title and info line of a
    contact card). Otherwise, for example when the compact element is the whole content
    area of a short page, the search goes on in the children that hold the facts.
    """
    children = [
        c
        for c in element
        if isinstance(c.tag, str) and c.tag not in _RESCUE_SKIP and c.text_content().strip()
    ]
    holders = [c for c in children if _facts(c.text_content()) & missing]
    if not holders:
        return [element]  # the facts are in the element's own text
    others = [c for c in children if all(c is not h for h in holders)]
    if len(holders) == 1 and not others:
        return _contact_blocks(holders[0], missing)  # a wrapper
    context = sum(len(_text_outside(o, _HEADING_TAGS).strip()) for o in others)
    if context <= _CONTEXT_CHARS:
        return [element]
    return [block for child in holders for block in _contact_blocks(child, missing)]


def _key(text: str) -> str:
    return " ".join(normalize_text(text).split()).casefold()
