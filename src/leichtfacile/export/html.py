"""HTML export: a standalone page laid out for easy language (large type, one sentence
per line, no hyphenation, left-aligned). No external assets."""

from __future__ import annotations

from html import escape

from leichtfacile.export import LABELS, final_blocks
from leichtfacile.rules.layout import wrap_sentence
from leichtfacile.schemas import Draft, ReviewState

_STYLE = """
body { font: 1.25rem/1.6 Arial, Helvetica, sans-serif; max-width: 42rem; margin: 2rem auto;
       padding: 0 1rem; color: #111; background: #fff; hyphens: none; text-align: left; }
h1 { font-size: 1.8rem; } h2 { font-size: 1.45rem; margin-top: 2rem; }
p { margin: 0 0 .9rem; } .note { border-left: 4px solid #b00; padding-left: .8rem; }
ul { padding-left: 1.4rem; } li { margin-bottom: .4rem; }
dt { font-weight: bold; margin-top: .8rem; } dd { margin-left: 0; }
"""


def _lines(text: str, width: int) -> str:
    return "<br>\n".join(escape(line) for line in wrap_sentence(text, width))


def to_html(
    draft: Draft, review: ReviewState | None = None, *, title: str | None = None, width: int = 85
) -> str:
    labels = LABELS.get(draft.lang, LABELS["de"])
    final = final_blocks(draft, review)
    body: list[str] = []
    if title:
        body.append(f"<h1>{escape(title)}</h1>")
    if not final.reviewed:
        body.append(f'<p class="note">{escape(labels["draft_note"])}</p>')
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
            body.append(f"<li>{_lines(b.text, width - 2)}</li>")
        else:
            body.append(f"<p>{_lines(b.text, width)}</p>")
    if in_list:
        body.append("</ul>")
    if draft.glossary:
        body.append(f"<h2>{escape(labels['glossary'])}</h2>")
        body.append("<dl>")
        for g in draft.glossary:
            body.append(f"<dt>{escape(g.term)}</dt><dd>{_lines(g.explanation, width)}</dd>")
        body.append("</dl>")
    page_title = escape(title or "Leicht·Facile")
    return (
        f'<!doctype html>\n<html lang="{draft.lang}">\n<head>\n<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{page_title}</title>\n<style>{_STYLE}</style>\n</head>\n<body>\n"
        + "\n".join(body)
        + "\n</body>\n</html>\n"
    )
