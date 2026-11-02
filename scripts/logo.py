"""The logo (docs/logo.md): the files the app, the project's site and the docs show.

Usage: uv run --with "fonttools[woff]" --with uharfbuzz python scripts/logo.py
       [--site ../leicht-facile-web/site] [--browser PATH]

Writes:

- docs/images/logo/: icon.svg (the app icon, 512 px), favicon.svg (the same tile drawn
  again on the 16 px grid, sharp at 16 and 32 px), logo.svg and logo-dark.svg (the tile and
  the wordmark, for light and for dark backgrounds), logo-mono.svg (one colour,
  `currentColor`: black as an image, the text colour when inlined) and social-preview.png
  (1280 x 640, the picture for the repository's settings on GitHub)
- src/leichtfacile/web/static/: favicon.svg, favicon.ico (16 and 32 px, for browsers
  without SVG favicons), apple-touch-icon.png (180 px, the tile without its round corners:
  a phone rounds them itself), logo.svg and logo-dark.svg
- the site (--site; by default the sibling checkout of leicht-facile-web, when it is
  there): the same favicons at its root, logo.svg and logo-dark.svg in images/logo/, and a
  social preview per language in images/social/ (1200 x 630, with the page's headline)

The symbol is one stroke that loops like a handwritten L, runs out straight and ends in a
full stop, in white on a tile in the accent. The wordmark is "Leicht·Facile" in the app's
own Atkinson Hyperlegible Next Bold (the woff2 files in src/leichtfacile/web/static/fonts),
shaped by HarfBuzz with the font's kerning and turned into outlines, so a logo needs no
font where it is shown; the SIL Open Font License allows a logo set in the font. The
Mediopunkt is a circle in the accent colour, a little larger than the font's own and with
a little more space on each side. Colours are the app's tokens (docs/ui-design.md §3.1):
ink, the accent and their dark-mode values; no logo uses a status colour.

Headless Edge draws the PNG files through the DevTools protocol, as for
guide_screenshots.py: EDGE below, or --browser for another Chromium.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import httpx
import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "images" / "logo"
STATIC = ROOT / "src" / "leichtfacile" / "web" / "static"
FONTS = STATIC / "fonts"
SITE = ROOT.parent / "leicht-facile-web" / "site"  # the project's page, a sibling checkout
EDGE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
DEBUG_PORT = 9340

INK, ACCENT = "#1A1E23", "#1F4E8A"
INK_DARK, ACCENT_DARK = "#E6E9ED", "#8FB1DE"
TILE_DOT = ACCENT_DARK  # the full stop on the blue tile
WASH, TEXT_2 = "#EAF0F7", "#49515C"  # the site's header wash and secondary text
THEMES = {
    "light": {"fg": INK, "accent": ACCENT},
    "dark": {"fg": INK_DARK, "accent": ACCENT_DARK},
    "mono": {"fg": "currentColor", "accent": "currentColor"},
}

# The site's headline in each language (site/index.html and its de/, fr/, it/ pages).
HEADLINES = {
    "en": "Easy-language drafts of official texts",
    "de": "Entwürfe für Behördentexte in Leichter Sprache",
    "fr": "Des brouillons FALC de textes officiels",
    "it": "Bozze in lingua facile di testi ufficiali",
}


def num(v: float) -> str:
    """A coordinate with at most two decimals and no trailing zeros."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def svg(w: float, h: float, body: str, size: tuple[float, float] | None = None) -> str:
    """An SVG of the viewBox w x h, drawn at `size` (by default the viewBox)."""
    width, height = size or (w, h)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {num(w)} {num(h)}" '
        f'width="{num(width)}" height="{num(height)}" role="img" aria-label="Leicht·Facile">'
        f"<title>Leicht·Facile</title>{body}</svg>\n"
    )


# -- the wordmark -------------------------------------------------------------------------


@cache
def _font(weight: int) -> tuple[TTFont, hb.Font]:
    font = TTFont(FONTS / f"atkinson-hyperlegible-next-latin-{weight}-normal.woff2")
    font.flavor = None  # HarfBuzz reads the plain sfnt, not woff2
    buf = io.BytesIO()
    font.save(buf)
    data = buf.getvalue()
    return TTFont(io.BytesIO(data)), hb.Font(hb.Face(data))


@dataclass
class Outline:
    d: str  # path of every glyph but the Mediopunkt
    cap: float  # cap height in output units
    ink: tuple[float, float, float, float]  # bounds of the letters, y down
    dots: list[tuple[float, float, float]] = field(default_factory=list)  # (cx, cy, r)


def outline(
    text: str,
    size: float,
    weight: int = 700,
    *,
    tracking: float = 0,
    dot_scale: float = 1.0,
    dot_space: float = 0,
) -> Outline:
    """`text` at `size` (one em), baseline at y=0. `tracking` and `dot_space` (the extra
    space each side of the Mediopunkt) are in font units; `dot_scale` sizes the
    Mediopunkt against the font's own."""
    tt, font = _font(weight)
    glyphs = tt.getGlyphSet()
    names = tt.getGlyphOrder()
    s = size / tt["head"].unitsPerEm
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True})

    pen = SVGPathPen(glyphs, ntos=num)
    dots = []
    cursor = 0.0
    x0 = y0 = float("inf")
    x1 = y1 = float("-inf")
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions, strict=True):
        name = names[info.codepoint]
        bounds = BoundsPen(glyphs)
        glyphs[name].draw(bounds)
        if name == "periodcentered":
            cursor += dot_space
            bx0, by0, bx1, by1 = bounds.bounds
            cx = cursor + pos.x_offset + (bx0 + bx1) / 2
            dots.append((cx * s, -(by0 + by1) / 2 * s, (bx1 - bx0) / 2 * dot_scale * s))
            cursor += pos.x_advance + tracking + dot_space
            continue
        ox, oy = (cursor + pos.x_offset) * s, -pos.y_offset * s
        glyphs[name].draw(TransformPen(pen, (s, 0, 0, -s, ox, oy)))
        if bounds.bounds:
            bx0, by0, bx1, by1 = bounds.bounds
            x0, x1 = min(x0, ox + bx0 * s), max(x1, ox + bx1 * s)
            y0, y1 = min(y0, oy - by1 * s), max(y1, oy - by0 * s)
        cursor += pos.x_advance + tracking
    return Outline(pen.getCommands(), tt["OS/2"].sCapHeight * s, (x0, y0, x1, y1), dots)


def wordmark(theme: str) -> tuple[str, Outline]:
    """Leicht·Facile at 100 units to the em, baseline at y=0."""
    text = outline("Leicht·Facile", 100, tracking=-8, dot_scale=1.15, dot_space=18)
    (cx, cy, r) = text.dots[0]
    colours = THEMES[theme]
    body = (
        f'<path d="{text.d}" fill="{colours["fg"]}"/>'
        f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}" fill="{colours["accent"]}"/>'
    )
    return body, text


# -- the symbol and the tile --------------------------------------------------------------

# The stroke and its full stop in a 24-unit box: the loop rises, turns over like a
# handwritten L, comes down and runs out straight; the dot ends it.
STROKE = (
    "M3.4 15.6C6.2 13.9 10.1 9.6 10.6 6.3 11 3.8 9.5 2.8 8.4 3.4 7 4.2 6.3 7.7 6.4 11.2 "
    "6.5 15.4 7.6 17.6 10.6 17.8H16.2"
)
STROKE_WIDTH = 2.6
DOT = (20.4, 17.8, STROKE_WIDTH * 0.8)
# the visible bounds of stroke and dot, and the space around them on the tile
BOUNDS = (
    3.4 - STROKE_WIDTH / 2,
    2.9 - STROKE_WIDTH / 2,
    DOT[0] + DOT[2],
    DOT[1] + DOT[2],
)
# the looped L alone, from the top of its loop (the curve's highest point, y 3.23) to the
# foot of the stroke: the part as tall as the name's capital L in the lockup
LETTER = (3.23 - STROKE_WIDTH / 2, 17.8 + STROKE_WIDTH / 2)
TILE_PAD = 0.21


def place(size: float) -> tuple[float, float, float]:
    """The symbol's scale and its offset (x, y) on a tile `size` units square."""
    x0, y0, x1, y1 = BOUNDS
    scale = size * (1 - 2 * TILE_PAD) / max(x1 - x0, y1 - y0)
    return scale, size / 2 - (x0 + x1) / 2 * scale, size / 2 - (y0 + y1) / 2 * scale


def tile(size: float, fill: str = ACCENT, dot: str = TILE_DOT, radius: float = 0.225) -> str:
    """The symbol in white on a tile `size` units square; radius 0 for a square tile."""
    scale, tx, ty = place(size)
    corner = f' rx="{num(size * radius)}"' if radius else ""
    return (
        f'<rect width="{num(size)}" height="{num(size)}"{corner} fill="{fill}"/>'
        f'<g transform="translate({num(tx)} {num(ty)}) scale({num(scale)})">'
        f'<path d="{STROKE}" fill="none" stroke="#FFFFFF" stroke-width="{num(STROKE_WIDTH)}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{num(DOT[0])}" cy="{num(DOT[1])}" r="{num(DOT[2])}" fill="{dot}"/></g>'
    )


# The favicon, drawn again on a 16-unit grid for 16 and 32 px: the stroke thicker, the loop
# simpler.
FAVICON = (
    f'<rect width="16" height="16" rx="3.6" fill="{ACCENT}"/>'
    '<path d="M3.1 10.6C4.8 9.6 6.9 7.2 7.2 5.2 7.4 3.7 6.5 3 5.7 3.4 4.8 3.9 4.4 5.7 4.5 '
    '7.8 4.6 10.6 5.3 12.3 7.3 12.3H9.9" fill="none" stroke="#fff" stroke-width="1.75" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    f'<circle cx="12.5" cy="12.3" r="1.4" fill="{TILE_DOT}"/>'
)


def lockup(theme: str, height: float | None = None) -> str:
    """The tile left of the wordmark, so large that its looped L is as tall as the name's
    capital L and stands on the name's baseline, a third of the tile between the two.
    `height` draws it at that many pixels."""
    body, text = wordmark(theme)
    size = text.cap / (place(1)[0] * (LETTER[1] - LETTER[0]))
    scale, _, ty = place(size)
    y = -ty - LETTER[1] * scale  # the tile's top, the L's foot on the baseline
    shift = size * 1.34 - text.ink[0]
    top = min(y, text.ink[1])
    bottom = max(y + size, text.ink[3])
    w, h = shift + text.ink[2], bottom - top
    mono = theme == "mono"
    symbol = tile(size, "currentColor" if mono else ACCENT, "#fff" if mono else TILE_DOT)
    return svg(
        w,
        h,
        f'<g transform="translate(0 {num(-top)})">'
        f'<g transform="translate(0 {num(y)})">{symbol}</g>'
        f'<g transform="translate({num(shift)} 0)">{body}</g></g>',
        (w * height / h, height) if height else None,
    )


# -- the pictures -------------------------------------------------------------------------


def social(width: int, height: int, lang: str) -> str:
    """A social preview: the logo, the site's headline, the address, on the site's wash."""
    pad = round(height * 0.13)
    regular = (FONTS / "atkinson-hyperlegible-next-latin-400-normal.woff2").as_uri()
    bold = (FONTS / "atkinson-hyperlegible-next-latin-700-normal.woff2").as_uri()
    return f"""<!doctype html><meta charset="utf-8"><style>
@font-face {{ font-family: A; font-weight: 400; src: url({regular}); }}
@font-face {{ font-family: A; font-weight: 700; src: url({bold}); }}
html, body {{ margin: 0; }}
body {{ width: {width}px; height: {height}px; box-sizing: border-box; padding: {pad}px;
  background: {WASH}; color: {INK}; font-family: A, sans-serif; display: flex;
  flex-direction: column; justify-content: space-between; }}
h1 {{ margin: 0; font-size: {round(height * 0.115)}px; line-height: 1.15;
  font-weight: 700; letter-spacing: -0.01em; text-wrap: balance; }}
p {{ margin: 0; font-size: {round(height * 0.045)}px; color: {TEXT_2}; }}
</style><body lang="{lang}">{lockup("light", round(height * 0.165))}
<h1>{HEADLINES[lang]}</h1><p>leichtfacile.ch</p></body>"""


def ico(pngs: list[tuple[int, bytes]]) -> bytes:
    """An .ico of PNG images, each (size, PNG bytes)."""
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset = len(head) + 16 * len(pngs)
    entries, data = b"", b""
    for size, png in pngs:
        entries += struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    return head + entries + data


def free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


class Page:
    """One headless page, driven through the DevTools protocol."""

    def __init__(self, ws, folder: Path) -> None:
        self.ws = ws
        self.folder = folder
        self.n = 0

    def call(self, method: str, **params: object) -> dict:
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def png(self, html: str, width: int, height: int) -> bytes:
        """The page `html` at width x height px, on a transparent background."""
        page = self.folder / f"page-{self.n}.html"
        page.write_text(html, encoding="utf-8")
        self.call(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=height,
            deviceScaleFactor=1,
            mobile=False,
        )
        self.call(
            "Emulation.setDefaultBackgroundColorOverride", color={"r": 0, "g": 0, "b": 0, "a": 0}
        )
        self.call("Page.navigate", url=page.as_uri())
        # the new page, not the one before it, loaded with its fonts
        ready = (
            f"location.href == {json.dumps(page.as_uri())} && document.readyState == 'complete'"
            " && document.fonts.ready.then(() => true)"
        )
        for _ in range(100):
            result = self.call(
                "Runtime.evaluate", expression=ready, awaitPromise=True, returnByValue=True
            )
            if result.get("result", {}).get("value") is True:
                break
            time.sleep(0.1)
        clip = {"x": 0, "y": 0, "width": width, "height": height, "scale": 1}
        data = self.call("Page.captureScreenshot", format="png", clip=clip)
        return base64.b64decode(data["data"])


@contextmanager
def browser(exe: Path) -> Iterator[Page]:
    if not free(DEBUG_PORT):
        sys.exit(f"port {DEBUG_PORT} is in use: close the browser that holds it")
    with tempfile.TemporaryDirectory(prefix="lf-logo-", ignore_cleanup_errors=True) as tmp:
        args = [
            str(exe),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={Path(tmp) / 'profile'}",
            f"--remote-debugging-port={DEBUG_PORT}",
            "about:blank",
        ]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            args.insert(1, "--no-sandbox")  # Chromium refuses to run as root otherwise
        proc = subprocess.Popen(args)
        try:
            for _ in range(100):
                try:
                    pages = httpx.get(f"http://127.0.0.1:{DEBUG_PORT}/json", timeout=2).json()
                    target = next(p for p in pages if p.get("type") == "page")
                    break
                except (httpx.HTTPError, StopIteration, ValueError):
                    time.sleep(0.2)
            else:
                sys.exit("the browser did not open its debugging port")
            with connect(target["webSocketDebuggerUrl"], max_size=None, open_timeout=30) as ws:
                yield Page(ws, Path(tmp))
        finally:
            with suppress(Exception):
                version = httpx.get(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=2)
                with connect(version.json()["webSocketDebuggerUrl"]) as ws:
                    ws.send(json.dumps({"id": 1, "method": "Browser.close"}))
            for _ in range(50):
                if free(DEBUG_PORT):
                    break
                time.sleep(0.2)
            proc.terminate()
            proc.wait(timeout=30)


def image(svg_text: str, size: int) -> str:
    """A page that shows `svg_text` at size x size px."""
    return (
        '<!doctype html><meta charset="utf-8"><style>html,body{margin:0}svg{display:block;'
        f"width:{size}px;height:{size}px}}</style>{svg_text}"
    )


# -- the files ----------------------------------------------------------------------------


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)
    print(f"  {path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", type=Path, default=SITE, help="the site/ folder of the page")
    ap.add_argument("--browser", type=Path, default=EDGE, help="a Chromium for the PNG files")
    args = ap.parse_args()

    icon = svg(512, 512, tile(512))
    favicon = svg(16, 16, FAVICON)
    logos = {theme: lockup(theme) for theme in THEMES}
    site = args.site.is_dir()
    with browser(args.browser) as page:
        icons = ico([(n, page.png(image(favicon, n), n, n)) for n in (16, 32)])
        touch = page.png(image(svg(180, 180, tile(180, radius=0)), 180), 180, 180)
        preview = page.png(social(1280, 640, "en"), 1280, 640)
        cards = {lang: page.png(social(1200, 630, lang), 1200, 630) for lang in HEADLINES if site}

    write(DOCS / "icon.svg", icon)
    write(DOCS / "favicon.svg", favicon)
    write(DOCS / "logo.svg", logos["light"])
    write(DOCS / "logo-dark.svg", logos["dark"])
    write(DOCS / "logo-mono.svg", logos["mono"])
    write(DOCS / "social-preview.png", preview)
    for folder in (STATIC, args.site) if site else (STATIC,):
        write(folder / "favicon.svg", favicon)
        write(folder / "favicon.ico", icons)
        write(folder / "apple-touch-icon.png", touch)
    write(STATIC / "logo.svg", logos["light"])
    write(STATIC / "logo-dark.svg", logos["dark"])
    if site:
        write(args.site / "images" / "logo" / "logo.svg", logos["light"])
        write(args.site / "images" / "logo" / "logo-dark.svg", logos["dark"])
        for lang, card in cards.items():
            write(args.site / "images" / "social" / f"{lang}.png", card)
    else:
        print(f"no site at {args.site}: its files were not written")


if __name__ == "__main__":
    main()
