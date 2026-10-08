"""Markdown export: headings as ##, one sentence per line, list items as -, glossary
at the end. Lines inside a paragraph end with a backslash, the CommonMark hard line
break, so every sentence keeps its own line when the Markdown is rendered."""

from __future__ import annotations

from leichtfacile.export import LABELS, final_blocks
from leichtfacile.rules.layout import wrap_sentence
from leichtfacile.schemas import Draft, ReviewState


def to_markdown(
    draft: Draft,
    review: ReviewState | None = None,
    *,
    title: str | None = None,
    width: int = 85,
    notice: str | None = None,
) -> str:
    """`notice`: the authority's fixed text (decision mode), the first and the last
    paragraph, as it is."""
    labels = LABELS.get(draft.lang, LABELS["de"])
    final = final_blocks(draft, review)
    out: list[str] = []
    if title:
        out += [f"# {title}", ""]
    if not final.reviewed:
        out += [f"> {labels['draft_note']}", ""]
    if notice:
        out += [notice, ""]
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            out.extend(line + " \\" for line in paragraph[:-1])
            out.append(paragraph[-1])
            out.append("")
            paragraph.clear()

    previous = None
    for b in final.blocks:
        if b.kind == "heading":
            flush()
            out += [f"## {b.text}", ""]
        elif b.kind == "list_item":
            if previous != "list_item":
                flush()
            wrapped = wrap_sentence(b.text, width - 2)
            out.append(f"- {wrapped[0]}" + (" \\" if len(wrapped) > 1 else ""))
            for i, line in enumerate(wrapped[1:], 1):
                out.append(f"  {line}" + (" \\" if i < len(wrapped) - 1 else ""))
        else:
            if previous == "list_item":
                out.append("")
            paragraph += wrap_sentence(b.text, width)
        previous = b.kind
    flush()
    if previous == "list_item":
        out.append("")
    if final.glossary:
        out += [f"## {labels['glossary']}", ""]
        for g in final.glossary:
            out += [f"**{g.term}**  ", *wrap_sentence(g.explanation, width), ""]
    if notice:
        out += [notice, ""]
    return "\n".join(out).rstrip() + "\n"
