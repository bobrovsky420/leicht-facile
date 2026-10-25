"""Markdown export: the layout (export/layout.py) with headings as ##, list items as -,
the glossary at the end. Lines inside a paragraph end with a backslash, the CommonMark
hard line break, so every sentence keeps its own line when the Markdown is rendered.
The no-break spaces inside values become plain spaces: Markdown is for editing, and a
no-break space would be an invisible character in an editor."""

from __future__ import annotations

from leichtfacile.export.layout import Layout


def to_markdown(layout: Layout) -> str:
    out: list[str] = []
    if layout.title:
        out += [f"# {layout.title}", ""]
    if layout.note:
        out += [f"> {layout.note}", ""]
    if layout.notice:
        out += [layout.notice, ""]
    paragraph: list[str] = []  # consecutive paragraphs form one Markdown paragraph

    def flush() -> None:
        if paragraph:
            out.extend(line + " \\" for line in paragraph[:-1])
            out.append(paragraph[-1])
            out.append("")
            paragraph.clear()

    previous = None
    for item in layout.items:
        if item.kind == "heading":
            flush()
            out += [f"## {item.lines[0]}", ""]
        elif item.kind == "list_item":
            if previous != "list_item":
                flush()
            last = len(item.lines) - 1
            for i, line in enumerate(item.lines):
                out.append(("- " if i == 0 else "  ") + line + (" \\" if i < last else ""))
        else:
            if previous == "list_item":
                out.append("")
            paragraph += item.lines
        previous = item.kind
    flush()
    if previous == "list_item":
        out.append("")
    if layout.glossary:
        out += [f"## {layout.glossary_title}", ""]
        for entry in layout.glossary:
            out += [f"**{entry.term}**  ", *entry.lines, ""]
    if layout.notice:
        out += [layout.notice, ""]
    return ("\n".join(out).rstrip() + "\n").replace("\xa0", " ")
