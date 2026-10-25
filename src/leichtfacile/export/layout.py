"""One layout for every export (docs/architecture.md §4.7).

`build_layout` applies the review decisions (`final_blocks`), cleans every text (a run
of white space, a line break in a reviewer's edit included, becomes one space; control
characters go), keeps the spaces inside a value from breaking (no-break spaces, so a
date, an amount or a phone number stays on one line in a browser and in Word) and
breaks each block at sense units into lines of at most `LINE_CHARS` characters
(`wrap_sentence`), a list item's lines by the width of its bullet. The writers
(markdown.py, html.py, docx.py) only serialise the layout, so every export prints the
same lines, and the audit bundle checks these very lines with the layout rules and
FACT-07 (`plain_lines`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from leichtfacile.export import LABELS, FinalText, final_blocks
from leichtfacile.rules.layout import wrap_sentence
from leichtfacile.rules.values import extract_values
from leichtfacile.schemas import Draft, ReviewState

# Within LAY-02's 85: a line this long fits the HTML export's column at any common font
# and an A4 page at 14 points, so neither the browser nor Word breaks it a second time.
# At 85 the reader view broke "8.30 bis 11.30 Uhr erreichbar." into three lines.
LINE_CHARS = 60
LIST_INDENT = 2  # a list item's lines are shorter by its bullet ("- ")

ItemKind = Literal["heading", "paragraph", "list_item"]
_ITEM_KINDS: dict[str, ItemKind] = {"heading": "heading", "list_item": "list_item"}
_SPACES = re.compile(r"[\t\n\r\x0b\x0c ]+")
_CONTROL = re.compile(r"[\x00-\x08\x0e-\x1f]")  # no place for them in XML 1.0


@dataclass(frozen=True)
class Item:
    kind: ItemKind
    lines: list[str]  # a heading has one line


@dataclass(frozen=True)
class Entry:
    term: str
    lines: list[str]


@dataclass(frozen=True)
class Layout:
    lang: str
    version: int
    title: str | None
    note: str | None  # the draft note, while the draft is not reviewed
    notice: str | None  # decision mode: the authority's fixed text, first and last, as it is
    items: list[Item]
    glossary_title: str
    glossary: list[Entry]
    final: FinalText  # the review applied: what the audit bundle reports


def clean(text: str) -> str:
    """Text for one line: a run of white space, a line break in a reviewer's edit
    included, becomes one space, and control characters go."""
    return _CONTROL.sub("", _SPACES.sub(" ", text)).strip()


def keep_values_together(text: str, lang: str) -> str:
    """No line break inside a value: the spaces of a date, an amount, a phone number or
    an address become no-break spaces ("044 123 45 67", "31. März 2027"), so neither
    `wrap_sentence` nor the browser or Word splits it."""
    chars = list(text)
    for value in extract_values(text, lang):
        for i in range(max(value.start, 0), value.end):
            if chars[i] == " ":
                chars[i] = "\xa0"
    return "".join(chars)


def lines_of(text: str, lang: str, width: int) -> list[str]:
    return wrap_sentence(keep_values_together(clean(text), lang), width)


def build_layout(
    draft: Draft,
    review: ReviewState | None = None,
    *,
    title: str | None = None,
    notice: str | None = None,
    width: int = LINE_CHARS,
) -> Layout:
    """The layout of a draft with the review applied; `notice` is the authority's fixed
    text of a decision (the first and the last paragraph, unwrapped)."""
    labels = LABELS.get(draft.lang, LABELS["de"])
    final = final_blocks(draft, review)
    items = []
    for b in final.blocks:
        kind = _ITEM_KINDS.get(b.kind, "paragraph")
        if kind == "heading":
            items.append(Item(kind, [clean(b.text)]))
        else:
            indent = LIST_INDENT if kind == "list_item" else 0
            items.append(Item(kind, lines_of(b.text, draft.lang, width - indent)))
    return Layout(
        lang=draft.lang,
        version=draft.version,
        title=clean(title) if title else None,
        note=None if final.reviewed else labels["draft_note"],
        notice=clean(notice) if notice else None,
        items=items,
        glossary_title=labels["glossary"],
        glossary=[
            Entry(clean(g.term), lines_of(g.explanation, draft.lang, width)) for g in final.glossary
        ],
        final=final,
    )


def plain_lines(layout: Layout) -> list[str]:
    """The text as the exports print it, line by line: what the layout rules (LAY-01,
    LAY-02) and FACT-07 check. The notice is the first and the last line; the title, the
    draft note and the glossary are not part of the text and not subject to the rules."""
    lines: list[str] = [layout.notice, ""] if layout.notice else []
    previous: ItemKind | None = None
    for item in layout.items:
        if item.kind == "heading":
            if lines:
                lines.append("")
            lines += item.lines
        elif item.kind == "list_item":
            lines.append(f"- {item.lines[0]}")
            lines += [f"  {line}" for line in item.lines[1:]]
        else:
            if previous == "list_item":
                lines.append("")
            lines += item.lines
        previous = item.kind
    if layout.notice:
        lines += ["", layout.notice]
    return lines
