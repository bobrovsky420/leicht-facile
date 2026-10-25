"""HTML export: a standalone page laid out for easy language (large type, one sentence
per line, no hyphenation, left-aligned). No external assets: the font stack names
Atkinson Hyperlegible Next first, used where it is installed (and in the reader view,
which adds the vendored font), and falls back to Arial and Helvetica.

The lines are the layout's (export/layout.py, at most `LINE_CHARS` characters, never
inside a value), joined by line breaks, and the column is wide enough for such a line,
so the browser does not break it a second time. Printed on A4, the page keeps the same
lines at 14 points."""

from __future__ import annotations

from html import escape

from leichtfacile.export.layout import Layout

_STYLE = """
body { font: 1.25rem/1.6 "Atkinson Hyperlegible Next", Arial, Helvetica, sans-serif;
       max-width: 36em; margin: 2rem auto;
       padding: 0 1rem; color: #111; background: #fff; hyphens: none; text-align: left; }
h1 { font-size: 1.8rem; } h2 { font-size: 1.45rem; margin-top: 2rem; }
p { margin: 0 0 .9rem; } .note { border-left: 4px solid #b00; padding-left: .8rem; }
.notice { border-top: 1px solid #888; border-bottom: 1px solid #888; padding: .6rem 0; }
ul { padding-left: 1.4rem; } li { margin-bottom: .4rem; }
dt { font-weight: bold; margin-top: .8rem; } dd { margin-left: 0; }
@page { size: A4; margin: 20mm; }
@media print {
  body { font-size: 14pt; max-width: none; margin: 0; padding: 0; }
  h1 { font-size: 20pt; } h2 { font-size: 17pt; break-after: avoid; }
  p, li, dt, dd, .notice { break-inside: avoid; } dt { break-after: avoid; }
}
"""


def _lines(lines: list[str]) -> str:
    return "<br>\n".join(escape(line) for line in lines)


def to_html(layout: Layout) -> str:
    body: list[str] = []
    if layout.title:
        body.append(f"<h1>{escape(layout.title)}</h1>")
    if layout.note:
        body.append(f'<p class="note">{escape(layout.note)}</p>')
    if layout.notice:
        body.append(f'<p class="notice">{escape(layout.notice)}</p>')
    in_list = False
    for item in layout.items:
        if item.kind == "list_item" and not in_list:
            body.append("<ul>")
            in_list = True
        elif item.kind != "list_item" and in_list:
            body.append("</ul>")
            in_list = False
        if item.kind == "heading":
            body.append(f"<h2>{escape(item.lines[0])}</h2>")
        elif item.kind == "list_item":
            body.append(f"<li>{_lines(item.lines)}</li>")
        else:
            body.append(f"<p>{_lines(item.lines)}</p>")
    if in_list:
        body.append("</ul>")
    if layout.glossary:
        body.append(f"<h2>{escape(layout.glossary_title)}</h2>")
        body.append("<dl>")
        for entry in layout.glossary:
            body.append(f"<dt>{escape(entry.term)}</dt><dd>{_lines(entry.lines)}</dd>")
        body.append("</dl>")
    if layout.notice:
        body.append(f'<p class="notice">{escape(layout.notice)}</p>')
    page_title = escape(layout.title or "Leicht·Facile")
    return (
        f'<!doctype html>\n<html lang="{layout.lang}">\n<head>\n<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{page_title}</title>\n<style>{_STYLE}</style>\n</head>\n<body>\n"
        + "\n".join(body)
        + "\n</body>\n</html>\n"
    )
