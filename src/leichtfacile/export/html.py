"""HTML export: a standalone page laid out for easy language (large type, one sentence
per line, no hyphenation, left-aligned). No external assets: the font stack names
Atkinson Hyperlegible Next first, used where it is installed (and in the reader view,
which adds the vendored font), and falls back to Arial and Helvetica.

Lines break at sense units (`wrap_sentence`) at most `HTML_LINE_CHARS` characters
long, and the column is wide enough for such a line, so the browser does not break
it a second time: at 85 characters, the layout rules' limit, the reader view's
column broke "8.30 bis 11.30 Uhr erreichbar." into three lines with "Uhr" alone.
Printed on A4, the page keeps the same lines at 14 points."""

from __future__ import annotations

from html import escape

from leichtfacile.export import LABELS, final_blocks, keep_values_together
from leichtfacile.rules.layout import wrap_sentence
from leichtfacile.schemas import Draft, ReviewState

HTML_LINE_CHARS = 60  # within LAY's 85; fits the 36em column at any common font

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


def _lines(text: str, width: int, lang: str) -> str:
    kept = keep_values_together(text, lang)
    return "<br>\n".join(escape(line) for line in wrap_sentence(kept, width))


def to_html(
    draft: Draft,
    review: ReviewState | None = None,
    *,
    title: str | None = None,
    width: int = HTML_LINE_CHARS,
    notice: str | None = None,
) -> str:
    """`notice`: the authority's fixed text (decision mode), the first and the last
    paragraph, as it is."""
    labels = LABELS.get(draft.lang, LABELS["de"])
    final = final_blocks(draft, review)
    body: list[str] = []
    if title:
        body.append(f"<h1>{escape(title)}</h1>")
    if not final.reviewed:
        body.append(f'<p class="note">{escape(labels["draft_note"])}</p>')
    if notice:
        body.append(f'<p class="notice">{escape(notice)}</p>')
    in_list = False
    for b in final.blocks:
        if b.kind == "list_item" and not in_list:
            body.append("<ul>")
            in_list = True
        elif b.kind != "list_item" and in_list:
            body.append("</ul>")
            in_list = False
        if b.kind == "heading":
            body.append(f"<h2>{escape(b.text)}</h2>")
        elif b.kind == "list_item":
            body.append(f"<li>{_lines(b.text, width - 2, draft.lang)}</li>")
        else:
            body.append(f"<p>{_lines(b.text, width, draft.lang)}</p>")
    if in_list:
        body.append("</ul>")
    if final.glossary:
        body.append(f"<h2>{escape(labels['glossary'])}</h2>")
        body.append("<dl>")
        for g in final.glossary:
            body.append(
                f"<dt>{escape(g.term)}</dt><dd>{_lines(g.explanation, width, draft.lang)}</dd>"
            )
        body.append("</dl>")
    if notice:
        body.append(f'<p class="notice">{escape(notice)}</p>')
    page_title = escape(title or "Leicht·Facile")
    return (
        f'<!doctype html>\n<html lang="{draft.lang}">\n<head>\n<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{page_title}</title>\n<style>{_STYLE}</style>\n</head>\n<body>\n"
        + "\n".join(body)
        + "\n</body>\n</html>\n"
    )
