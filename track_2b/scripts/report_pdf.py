"""The technical report as a designed PDF (track_2b/docs/submission.md §5).

Usage: uv run python track_2b/scripts/report_pdf.py [--out FILE] [--html FILE] [--browser PATH]
(or `make pdf`). Lays out track_2b/technical_report.md on A4 in two columns with
report/report.html and report/report.css, in the web UI's fonts and colours. The Mermaid
diagrams become the drawings in report/ (FIGURES), every relative link a link to the
repository on GitHub, and the first page gets four key figures read from the results table
in §5. A headless Chromium (Edge or Chrome; --browser or CHROME_PATH names another) prints
the page; the PDF gets its document information and goes to
track_2b/RoestigrabenBridgers_Report.pdf, or to --out. The target-architecture table goes
to the foot of its page: the page is printed with the table moved down its subsection
block by block, and the last place where it still starts on the subsection's page wins.
Prints the pages and how full the last one is, with and without the references, and
fails when more than six pages come before the references: the hackathon's limit leaves
them out (organisers, 11 October 2026).
"""

from __future__ import annotations

import argparse
import base64
import codecs
import html
import io
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import jinja2
import pdfplumber
import pypdfium2 as pdfium
from markdown_it import MarkdownIt
from markdown_it.token import Token
from markupsafe import Markup

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "track_2b" / "technical_report.md"
PDF = ROOT / "track_2b" / "RoestigrabenBridgers_Report.pdf"
ASSETS = Path(__file__).resolve().parent / "report"
UI_CSS = ROOT / "track_2b" / "src" / "leichtfacile" / "web" / "static" / "app.css"
FIGURES = ("architecture.svg", "pipeline.svg")  # the report's Mermaid diagrams, in order
# The table, by the first cell of its header, that spans the page at the foot of the page
# its subsection starts on (owner, 11 October 2026).
FOOT_TABLE = "Architecture"
# Columns, by their header, whose cells do not wrap (owner, 11 October 2026).
UNWRAPPED = ("Model and server",)
# Chapters, by their title without the number, set in one column across the page (owner,
# 11 October 2026).
SINGLE_COLUMN = ("Data",)
# Wide tables, by the first cell of their header, whose introducing paragraph stays in the
# columns instead of spanning the page as their caption (owner, 11 October 2026).
NO_CAPTION = ("Setup",)
# Paragraphs, by their first words, that start a new column (owner, 11 October 2026).
NEW_COLUMN = ("One container plus an",)
MAX_PAGES = 6  # before the references, which do not count (organisers, 11 October 2026)
MARGIN_TOP, MARGIN_BOTTOM = 17, 15  # mm, as in report.css
KEYWORDS = "Apertus, easy language, Leichte Sprache, FALC, Swiss official texts, Hack Apertus"

# The key figures: our pipeline against the strong single prompt, read from the results
# table in §5 so that they cannot drift from it. (column, label, explanation)
OURS, BASELINE = "P2 (ours)", "P0-ZH complete"
KEY_FIGURES = (
    ("Fact coverage", "fact coverage", "must-keep facts found"),
    ("Hard facts kept", "hard facts kept", "the source’s countable values"),
    ("Silent losses", "silent losses", "values lost without a trace"),
    ("Rule errors /100", "rule errors", "per 100 blocks"),
)
KEY_NOTE = (
    "Our pipeline (P2) against the strong single prompt (P0-ZH complete) on the same model "
    "and the same held-out pairs; §5 has the setup and every row."
)

BROWSERS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)
BROWSER_NAMES = ("google-chrome", "chromium", "chromium-browser", "microsoft-edge", "msedge")

NBSP = chr(0xA0)  # no-break space
HYPHENATED = re.compile(r"\S*\w-\w\S*")  # a word with a hyphen inside
UNIT = re.compile(r"(?<=\d) (?=%|(?:percent|USD|GiB|GB|ms|s|min|minutes|\d+B)\b)")
LINKABLE = re.compile(r"https?://[^\s<>()]*[^\s<>().,;:!?'\"]|[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
NOT_RELATIVE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:|#|/")  # URL, anchor, from the root
NUMBER = re.compile(r"-|[-+]?\d[\d,.]*(?: ?%)?")
DONE_BY = {"apertus": "who ai", "code": "who code", "human": "who human"}


@dataclass
class Report:
    title: str  # the first heading: "Technical report - Leicht·Facile"
    kind: str  # "Technical report"
    name: str  # "Leicht·Facile"
    subtitle: Markup
    subtitle_text: str
    meta: dict[str, Markup] = field(default_factory=dict)  # the list under the title
    meta_text: dict[str, str] = field(default_factory=dict)
    body: Markup = Markup()
    key_figures: list[dict[str, str]] = field(default_factory=list)
    # the foot table: how many blocks it can move down, its subsection's heading, its header
    foot: tuple[int, str, str] | None = None

    @property
    def wordmark(self) -> Markup:
        return Markup(html.escape(self.name).replace("·", '<span class="dot">·</span>'))

    @property
    def team(self) -> str:
        return self.meta_text.get("Team", "").split(" - ")[0]

    @property
    def authors(self) -> str:
        """The team line without the e-mail addresses."""
        return re.sub(r" \([^()]*@[^()]*\)", "", self.meta_text.get("Team", ""))


def markdown() -> MarkdownIt:
    # Curly quotes, but not the typographer's other replacements: "--" would become a dash.
    md = MarkdownIt("commonmark", {"typographer": True}).enable(["table", "smartquotes"])
    md.add_render_rule("fence", render_fence)
    md.add_render_rule("code_inline", render_code)
    return md


def render_fence(self, tokens: list[Token], idx: int, options, env: dict) -> str:
    """A Mermaid diagram becomes the next drawing of FIGURES."""
    if tokens[idx].info.strip() != "mermaid":
        return self.fence(tokens, idx, options, env)
    number = env["figure"] = env.get("figure", -1) + 1
    return f'<figure class="diagram">\n{env["figures"][number]}</figure>\n'


def render_code(self, tokens: list[Token], idx: int, options, env: dict) -> str:
    return f"<code>{breakable(tokens[idx].content)}</code>"


def breakable(text: str) -> str:
    """Code as HTML that breaks at its spaces and, when long, after a slash, underscore or
    dot, never at a hyphen."""
    chunks = re.split(r"(?<=[/_.])(?=[^/_.])", text) if len(text) >= 16 else [text]
    return "<wbr>".join(unbroken(chunk) for chunk in chunks)


def unbroken(text: str) -> str:
    """Text as HTML with each word that holds a hyphen kept on one line: Chromium would
    break after the hyphen, which reads as hyphenation, and the report has none."""
    escaped = html.escape(text, quote=False)
    return HYPHENATED.sub(lambda m: f'<span class="nobr">{m[0]}</span>', escaped)


def html_text(text: str) -> Token:
    """A text token as HTML: the same text, its hyphenated words kept on one line."""
    return Token("html_inline", "", 0, content=unbroken(text))


def typeset(text: str) -> str:
    """No-break spaces between a number and its unit."""
    return UNIT.sub(NBSP, text)


def absolute(href: str, repo: str, folder: str) -> str:
    """A link relative to the report's folder as a link to the repository on GitHub, which
    works from both copies of the PDF and from the file uploaded with the form."""
    if NOT_RELATIVE.match(href):
        return href
    path, sep, anchor = href.partition("#")
    full = posixpath.normpath(posixpath.join(folder, path))
    if path.endswith("/"):
        return f"{repo}/tree/main/{full}/{sep}{anchor}"
    return f"{repo}/blob/main/{full}{sep}{anchor}"


def pieces(text: str) -> list[Token]:
    """An address or a path, with a line break allowed after each slash only."""
    out: list[Token] = []
    for i, piece in enumerate(re.split(r"(?<=[^/]/)(?=[^/])", text)):
        if i:
            out.append(Token("html_inline", "", 0, content="<wbr>"))
        out.append(html_text(piece))
    return out


def refine(inline: Token, repo: str, folder: str, short_urls: bool) -> None:
    """Absolute links, bare addresses as links, no-break spaces, no break at a hyphen; with
    short_urls an address is shown without its scheme."""
    children: list[Token] = []
    link: Token | None = None
    for child in inline.children or []:
        if child.type == "link_open":
            link = child
            child.attrSet("href", absolute(str(child.attrGet("href")), repo, folder))
        elif child.type == "link_close":
            link = None
        elif child.type == "text" and link is not None:
            text = child.content
            if short_urls and LINKABLE.fullmatch(text):
                text = re.sub(r"^https?://", "", text)
            children += pieces(typeset(text)) if "/" in text else [html_text(typeset(text))]
            continue
        elif child.type == "text":
            start = 0
            for m in LINKABLE.finditer(child.content):
                href = m[0] if "://" in m[0] else f"mailto:{m[0]}"
                shown = re.sub(r"^https?://", "", m[0]) if short_urls else m[0]
                children.append(html_text(typeset(child.content[start : m.start()])))
                children.append(Token("link_open", "a", 1, attrs={"href": href}))
                children += [*pieces(shown), Token("link_close", "a", -1)]
                start = m.end()
            children.append(html_text(typeset(child.content[start:])))
            continue
        children.append(child)
    inline.children = children


def cells(table: list[Token]) -> list[tuple[Token, list[tuple[Token, Token]]]]:
    """The rows of a table: (tr_open, [(th_open or td_open, inline)])."""
    rows: list[tuple[Token, list[tuple[Token, Token]]]] = []
    for i, token in enumerate(table):
        if token.type == "tr_open":
            rows.append((token, []))
        elif token.type in ("th_open", "td_open"):
            rows[-1][1].append((token, table[i + 1]))
    return rows


def add_class(token: Token, name: str) -> None:
    if name:
        token.attrSet("class", f"{token.attrGet('class') or ''} {name}".strip())


def style_table(table: list[Token]) -> None:
    """Wide tables span both columns; a table of long texts may break between its rows;
    numeric columns align right; a first column of short labels and the UNWRAPPED columns do
    not wrap; a bold first cell marks our own row; the "Done by" column gets the diagrams'
    colours."""
    head, *body = cells(table)
    names = [inline.content for _, inline in head[1]]
    longest = max(len(inline.content) for _, row in [head, *body] for _, inline in row)
    if names[0] == FOOT_TABLE:
        add_class(table[0], "span foot")
    elif len(names) >= 6 or (len(names) >= 3 and longest > 60):
        add_class(table[0], "span")
    elif longest > 120:
        add_class(table[0], "text")
    if max((len(row[0][1].content.strip("* ")) for _, row in body), default=0) <= 26:
        add_class(table[0], "keys")
    for col, name in enumerate(names):
        values = [row[col][1].content.strip("* ") for _, row in body]
        if all(NUMBER.fullmatch(v) for v in values) and any(v != "-" for v in values):
            for _, row in [head, *body]:
                add_class(row[col][0], "num")
        if name in UNWRAPPED:
            for _, row in body:
                add_class(row[col][0], "nobr")
        if name == "Done by":
            for _, row in body:
                who = (row[col][1].content.split() or [""])[0].strip(":,").lower()
                add_class(row[col][0], DONE_BY.get(who, ""))
    for tr, row in body:
        if row[0][1].content.startswith("**"):
            add_class(tr, "ours")


def key_figures(tokens: list[Token]) -> list[dict[str, str]]:
    for i, token in enumerate(tokens):
        if token.type != "table_open":
            continue
        end = next(j for j in range(i, len(tokens)) if tokens[j].type == "table_close")
        head, *body = cells(tokens[i : end + 1])
        names = [inline.content for _, inline in head[1]]
        if names[:1] != ["Setup"] or "Fact coverage" not in names:
            continue
        rows = {
            row[0][1].content.strip("* "): [c.content.strip("* ") for _, c in row]
            for _, row in body
        }
        if OURS not in rows or BASELINE not in rows:
            raise SystemExit(f"report_pdf: the results table has no row {OURS!r} or {BASELINE!r}")
        figures = []
        for column, label, explanation in KEY_FIGURES:
            if column not in names:
                raise SystemExit(f"report_pdf: the results table has no column {column!r}")
            col = names.index(column)
            figures.append(
                {
                    "value": rows[OURS][col].replace(" %", f"{NBSP}%"),
                    "label": label,
                    "explanation": explanation,
                    "baseline": rows[BASELINE][col].replace(" %", f"{NBSP}%"),
                }
            )
        return figures
    raise SystemExit("report_pdf: no results table (a first column 'Setup', 'Fact coverage')")


def parse(
    text: str, folder: str = "track_2b", shift: int = 0, breaks: frozenset[str] = frozenset()
) -> Report:
    """The report's Markdown as the parts of the page: title, subtitle, the list under the
    title, the key figures and the sections; the foot table moved `shift` blocks down, the
    chapters titled in `breaks` on a new page."""
    repo = re.search(r"\*\*Repository:\*\*\s*(\S+)", text)
    if not repo:
        raise SystemExit("report_pdf: the report names no repository (**Repository:** URL)")
    md = markdown()
    env: dict = {"figures": [(ASSETS / name).read_text(encoding="utf-8") for name in FIGURES]}
    tokens = md.parse(text, env)
    diagrams = sum(t.type == "fence" and t.info.strip() == "mermaid" for t in tokens)
    if diagrams != len(FIGURES):
        raise SystemExit(
            f"report_pdf: {diagrams} Mermaid diagrams in the report, {len(FIGURES)} figures"
        )
    first = next(i for i, t in enumerate(tokens) if t.type == "heading_open" and t.tag == "h2")
    for i, token in enumerate(tokens):
        if token.type == "inline":
            refine(token, repo[1], folder, short_urls=i < first)
        elif token.type == "table_open":
            end = next(j for j in range(i, len(tokens)) if tokens[j].type == "table_close")
            style_table(tokens[i : end + 1])

    foot = place_foot_table(tokens, shift)
    captions(tokens)
    for i, token in enumerate(tokens):
        if token.type == "paragraph_open" and tokens[i + 1].content.startswith(NEW_COLUMN):
            add_class(token, "new-column")
    front = tokens[:first]
    title = next(t for i, t in enumerate(front) if front[i - 1].type == "heading_open")
    kind, _, name = title.content.rpartition(" - ")
    subtitle = next(t for i, t in enumerate(front) if front[i - 1].type == "paragraph_open")
    report = Report(
        title=title.content,
        kind=kind,
        name=name,
        subtitle=Markup(md.renderer.renderInline(subtitle.children, md.options, env)),
        subtitle_text=" ".join(subtitle.content.split()),
        key_figures=key_figures(tokens),
        foot=foot,
    )
    for i, token in enumerate(front):
        if token.type == "inline" and front[i - 2].type == "list_item_open":
            label = re.match(r"\*\*(.+?):\*\*\s*(.*)", token.content, re.DOTALL)
            if label:
                value = token.children[3:]  # after **Label:**
                value[0].content = value[0].content.lstrip()
                report.meta[label[1]] = Markup(md.renderer.renderInline(value, md.options, env))
                report.meta_text[label[1]] = " ".join(label[2].split())
    if "Team" in report.meta:
        report.meta["Team"] = team_lines(report.meta["Team"])
    report.body = Markup(sections(md, tokens[first:], env, breaks))
    return report


def team_lines(value: Markup) -> Markup:
    """The team line, "Name - A (a@x), B (b@y)", as the team's name and one member per
    line."""
    name, sep, members = str(value).replace("\n", " ").partition(" - ")
    if not sep:
        return value
    lines = [f'<span class="team-name">{name}</span>', *re.split(r"(?<=\)),\s+", members)]
    return Markup("<br>".join(lines))


def block_ends(tokens: list[Token], start: int) -> list[int]:
    """Where each top-level block from start on ends, up to the next heading. A paragraph
    that ends with a colon introduces the next block and stays with it."""
    ends, depth, begin = [], 0, start
    for i in range(start, len(tokens)):
        if depth == 0 and tokens[i].type == "heading_open":
            break
        depth += tokens[i].nesting
        if depth == 0:
            intro = tokens[begin].type == "paragraph_open" and tokens[begin + 1].content.endswith(
                ":"
            )
            if not intro:
                ends.append(i + 1)
            begin = i + 1
    return ends


def place_foot_table(tokens: list[Token], shift: int) -> tuple[int, str, str] | None:
    """Move the FOOT_TABLE down its subsection by `shift` blocks. Returns how many blocks
    follow it there, the subsection's heading and the table's header row."""
    for i, token in enumerate(tokens):
        if "foot" not in str(token.attrGet("class")).split():
            continue
        end = next(j for j in range(i, len(tokens)) if tokens[j].type == "table_close") + 1
        header = " ".join(inline.content for _, inline in cells(tokens[i:end])[0][1])
        heading = next(
            tokens[j + 1].content for j in reversed(range(i)) if tokens[j].type == "heading_open"
        )
        ends = block_ends(tokens, end)
        if shift and ends:
            to = ends[min(shift, len(ends)) - 1]
            tokens[i:to] = tokens[end:to] + tokens[i:end]
        return len(ends), heading, header
    return None


def foot_fits(pdf: bytes, foot: tuple[int, str, str]) -> bool:
    """Whether the foot table starts on the page of its subsection's heading."""
    _, heading, header = foot
    doc = pdfium.PdfDocument(pdf)
    marks = [b.get_dest().get_index() for b in doc.get_toc() if b.get_title() == heading]
    pages = [
        i
        for i in range(len(doc))
        if header in " ".join(doc[i].get_textpage().get_text_range().split())
    ]
    return bool(marks and pages) and pages[0] == marks[0]


def stranded_titles(pdf: bytes) -> set[str]:
    """Chapter titles with no text under them on their page, found by their bookmarks:
    Chromium keeps no title that spans both columns with what follows it."""
    stranded = set()
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        for mark in pdfium.PdfDocument(pdf).get_toc():
            if mark.level != 1:
                continue
            dest = mark.get_dest()
            page = doc.pages[dest.get_index()]
            top = float(page.height) - dest.get_view()[1][1]
            bottom = float(page.height) - MARGIN_BOTTOM * 72 / 25.4
            under = [
                w for w in page.extract_words() if w["top"] > top + 24 and w["bottom"] <= bottom
            ]
            if not under:
                stranded.add(mark.get_title())
    return stranded


def captions(tokens: list[Token]) -> None:
    """A paragraph right before a wide table introduces it: both span the page together,
    the paragraph as the table's caption. In the columns, the paragraph would be balanced
    into both and could stay behind at the foot of a page. The NO_CAPTION tables keep their
    paragraph in the columns."""
    for i in reversed(range(len(tokens) - 3)):
        classes = str(tokens[i + 3].attrGet("class")).split()
        if (
            tokens[i].type == "paragraph_open"
            and tokens[i + 3].type == "table_open"
            and "span" in classes
            and "foot" not in classes
        ):
            end = next(j for j in range(i, len(tokens)) if tokens[j].type == "table_close")
            if cells(tokens[i + 3 : end + 1])[0][1][0][1].content in NO_CAPTION:
                continue
            tokens.insert(end + 1, Token("html_block", "", 0, content="</div>\n"))
            tokens.insert(i, Token("html_block", "", 0, content='<div class="spread">\n'))


def sections(
    md: MarkdownIt, tokens: list[Token], env: dict, breaks: frozenset[str] = frozenset()
) -> str:
    """Each second-level heading starts a section; the numbered ones carry their number
    apart, the others (licence, references) are end matter. A heading followed by diagrams
    or a wide table spans both columns with them, so that it never stays behind at the
    foot of a page; a heading in `breaks` (it stood alone at the foot of a page) starts a
    new page; a chapter in SINGLE_COLUMN runs across the page."""
    starts = [i for i, t in enumerate(tokens) if t.type == "heading_open" and t.tag == "h2"]
    out = []
    for start, end in zip(starts, [*starts[1:], len(tokens)], strict=True):
        inline = tokens[start + 1]
        number = re.match(r"(\d+)\.\s+", inline.content)
        if number:
            inline.children[0].content = inline.children[0].content[number.end() :]
        title = md.renderer.renderInline(inline.children, md.options, env)
        if number:
            title = f'<span class="num">{number[1]}.</span> {title}'
        heading, body = f"<h2>{title}</h2>\n", start + 3
        while (
            body < end and tokens[body].type == "fence" and tokens[body].info.strip() == "mermaid"
        ):
            body += 1
        if body == start + 3 and body < end and "span" in str(tokens[body].attrGet("class")):
            body = next(j for j in range(body, end) if tokens[j].type == "table_close") + 1
        if body > start + 3:
            wide = md.renderer.render(tokens[start + 3 : body], md.options, env)
            heading = f'<div class="spread">\n{heading}{wide}</div>\n'
        elif body < end and tokens[body].type == "html_block" and "spread" in tokens[body].content:
            heading, body = tokens[body].content + heading, body + 1  # into the caption's spread
        if inline.content in breaks and heading.startswith('<div class="spread">'):
            heading = heading.replace('<div class="spread">', '<div class="spread new-page">', 1)
        elif inline.content in breaks:
            heading = heading.replace("<h2>", '<h2 class="new-page">', 1)
        rest = md.renderer.render(tokens[body:end], md.options, env)
        kind = "numbered" if number else "end"
        if inline.content[number.end() if number else 0 :] in SINGLE_COLUMN:
            kind += " single"
        out.append(f'<section class="{kind}">\n{heading}{rest}</section>\n')
    return "".join(out)


def font_faces() -> str:
    """The web UI's @font-face rules with each font file inline: Chromium refuses fonts from
    file:// pages, and nothing is fetched while printing."""

    def inline(m: re.Match[str]) -> str:
        data = base64.b64encode((UI_CSS.parent / m[1]).read_bytes()).decode()
        return f'url("data:font/woff2;base64,{data}")'

    css = UI_CSS.read_text(encoding="utf-8")
    faces = re.findall(r"@font-face \{.*?\}", css, flags=re.DOTALL)
    return "\n".join(
        re.sub(r"url\(([^)]+)\)", inline, face).replace("font-display: swap", "font-display: block")
        for face in faces
    )


def page_html(report: Report) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(ASSETS),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # A CSS string for the running headers; JSON escapes quotes and backslashes the same way.
    env.filters["css_string"] = lambda text: Markup(json.dumps(str(text), ensure_ascii=False))
    return env.get_template("report.html").render(
        report=report,
        fonts=Markup(font_faces()),
        css=Markup((ASSETS / "report.css").read_text(encoding="utf-8")),
        key_note=KEY_NOTE,
    )


def find_browser(given: str | None) -> str:
    for candidate in (given, os.environ.get("CHROME_PATH")):
        if candidate:
            return candidate
    for path in BROWSERS:
        if Path(path).exists():
            return path
    for name in BROWSER_NAMES:
        if found := shutil.which(name):
            return found
    raise SystemExit("report_pdf: no Edge or Chrome found; name one with --browser or CHROME_PATH")


def print_pdf(browser: str, page: Path, pdf: Path, profile: Path) -> None:
    subprocess.run(
        [
            browser,
            "--headless",
            "--disable-gpu",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile}",
            "--no-pdf-header-footer",
            "--generate-pdf-document-outline",
            f"--print-to-pdf={pdf}",
            page.as_uri(),
        ],
        check=True,
        timeout=180,
    )
    # On Windows the launcher can return before the browser has written the file.
    size, deadline = -1, time.monotonic() + 60
    while time.monotonic() < deadline:
        now = pdf.stat().st_size if pdf.exists() else -1
        if now > 0 and now == size:
            return
        size = now
        time.sleep(0.5)
    raise SystemExit(f"report_pdf: {browser} wrote no PDF")


def pdf_text(text: str) -> bytes:
    return b"<" + (codecs.BOM_UTF16_BE + text.encode("utf-16-be")).hex().upper().encode() + b">"


def set_info(pdf: bytes, fields: dict[str, str]) -> bytes:
    """Append an incremental update with a new document information dictionary: Chromium
    writes only the title, and its user agent as the creator. Its producer and dates stay."""
    trailer = pdf[pdf.rindex(b"trailer") :]
    size = int(re.search(rb"/Size (\d+)", trailer)[1])
    root = re.search(rb"/Root (\d+ \d+ R)", trailer)[1]
    previous = int(re.search(rb"startxref\s+(\d+)", trailer)[1])
    ids = re.search(rb"/ID\s*\[[^\]]*\]", trailer)
    kept = b""
    if old := re.search(rb"/Info (\d+) 0 R", trailer):
        obj = re.search(rb"(?<!\d)" + old[1] + rb" 0 obj\s*<<(.*?)>>\s*endobj", pdf, re.DOTALL)
        kept = b"".join(re.findall(rb"/(?:Producer|CreationDate|ModDate) \([^)]*\)\s*", obj[1]))
    entries = b"".join(
        b"/%s %s\n" % (key.encode(), pdf_text(value)) for key, value in fields.items()
    )
    out = pdf if pdf.endswith(b"\n") else pdf + b"\n"
    offset = len(out)
    out += b"%d 0 obj\n<<%s%s>>\nendobj\n" % (size, entries, kept)
    xref = len(out)
    out += b"xref\n%d 1\n%010d 00000 n \n" % (size, offset)
    out += b"trailer\n<</Size %d /Root %s /Info %d 0 R /Prev %d%s>>\n" % (
        size + 1,
        root,
        size,
        previous,
        b" " + ids[0] if ids else b"",
    )
    return out + b"startxref\n%d\n%%%%EOF\n" % xref


def fill(page: pdfplumber.page.Page, keep=lambda word: True) -> float:
    """How far down the kept words of a page reach, between the top and the bottom margin
    (running headers and page numbers stand in the margins)."""
    top = MARGIN_TOP * 72 / 25.4
    bottom = float(page.height) - MARGIN_BOTTOM * 72 / 25.4
    lows = [
        w["bottom"]
        for w in page.extract_words()
        if w["top"] >= top and w["bottom"] <= bottom and keep(w)
    ]
    return (max(lows) - top) / (bottom - top) if lows else 0.0


def measure(pdf: bytes) -> tuple[tuple[int, float], tuple[int, float]]:
    """Pages and how full the last one is, for the whole PDF and for the part the limit
    counts: everything before the references, which the organisers leave out (11 October
    2026). The bookmark of the references' heading says where they start."""
    start = next(
        (b.get_dest() for b in pdfium.PdfDocument(pdf).get_toc() if b.get_title() == "References"),
        None,
    )
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        pages = doc.pages
        whole = (len(pages), fill(pages[-1]))
        if start is None:
            return whole, whole
        index, (x, y, _) = start.get_index(), start.get_view()[1]
        page = pages[index]
        mid, heading = float(page.width) / 2, float(page.height) - y

        def before(word: dict) -> bool:
            """Before the heading in reading order: higher in its column, or in the left
            column when the heading stands in the right one."""
            left = word["x0"] < mid
            return (left or word["top"] < heading) if x >= mid else (left and word["top"] < heading)

        if share := fill(page, before):
            return whole, (index + 1, share)
        return whole, (index, fill(pages[index - 1]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the technical report as a designed PDF.")
    parser.add_argument("--source", type=Path, default=SOURCE, help="the report's Markdown")
    parser.add_argument("--out", type=Path, default=PDF, help="where to write the PDF")
    parser.add_argument("--html", type=Path, help="also save the laid-out page")
    parser.add_argument(
        "--browser", help="a Chromium to print with (default: CHROME_PATH, Edge, Chrome)"
    )
    args = parser.parse_args(argv)

    folder = args.source.resolve().parent.relative_to(ROOT).as_posix()
    text = args.source.read_text(encoding="utf-8")
    for words in NEW_COLUMN:
        if not re.search(rf"^{re.escape(words)}", text, re.MULTILINE):
            print(f"report_pdf: no paragraph starts with {words!r} (NEW_COLUMN)", file=sys.stderr)
    browser = find_browser(args.browser)
    reach = (parse(text, folder).foot or (0, "", ""))[0]
    breaks: set[str] = set()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        for attempt in range(4):
            # Down its subsection, the foot table stays at the last place that keeps it
            # on the page the subsection starts on: the foot of that page.
            for shift in range(reach, -1, -1):
                report = parse(text, folder, shift, frozenset(breaks))
                page = page_html(report)
                (work / "report.html").write_text(page, encoding="utf-8")
                printed = work / f"report-{attempt}-{shift}.pdf"
                print_pdf(browser, work / "report.html", printed, work / "profile")
                if not shift or foot_fits(printed.read_bytes(), report.foot):
                    break
            # A chapter title left alone at the foot of a page starts the next one.
            stranded = stranded_titles(printed.read_bytes()) - breaks
            if not stranded:
                break
            breaks |= stranded
        info = {
            "Title": report.title,
            "Author": report.authors,
            "Subject": report.subtitle_text,
            "Keywords": KEYWORDS,
            "Creator": "track_2b/scripts/report_pdf.py",
        }
        pdf = set_info(printed.read_bytes(), info)
    if args.html:
        args.html.write_text(page, encoding="utf-8")
    if re.search(rb"/URI\s*\(file:", pdf):
        raise SystemExit("report_pdf: the PDF links to a local file")
    args.out.write_bytes(pdf)
    (pages, last), (counted, counted_last) = measure(pdf)
    out = args.out.resolve()
    shown = out.relative_to(ROOT).as_posix() if out.is_relative_to(ROOT) else str(out)
    print(
        f"{shown}: {pages} pages, the last {last:.0%} full; without the references "
        f"{counted} pages, the last {counted_last:.0%} full"
    )
    if report.foot:
        print(f"the {FOOT_TABLE} table moved {shift} of {reach} blocks down its subsection")
    if breaks:
        print(f"started on a new page, as their titles stood alone: {', '.join(sorted(breaks))}")
    if counted > MAX_PAGES:
        print(
            f"report_pdf: more than {MAX_PAGES} pages before the references, the hackathon's limit",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
