"""Export of the reviewed draft: Markdown, HTML and the JSON audit bundle.

Layout follows the easy-language rules checked by LAY-01 and LAY-02: one sentence per
line, lines of at most 85 characters, broken at clause boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass

from leichtfacile.rules.layout import wrap_sentence
from leichtfacile.schemas import Block, Draft, ReviewState

LABELS = {
    "de": {"glossary": "Wörterbuch", "draft_note": "Entwurf: noch nicht geprüft."},
    "fr": {"glossary": "Lexique", "draft_note": "Brouillon : pas encore relu."},
    "it": {"glossary": "Glossario", "draft_note": "Bozza: non ancora rivista."},
}


@dataclass(frozen=True)
class FinalText:
    """The blocks a reader gets: review decisions applied."""

    blocks: list[Block]
    reviewed: bool
    complete: bool  # the reviewer marked the review as complete
    undecided: int = 0  # blocks without a decision; they stay in, as drafted


def final_blocks(draft: Draft, review: ReviewState | None) -> FinalText:
    if review is None or review.draft_version != draft.version:
        return FinalText(list(draft.blocks), reviewed=False, complete=False)
    decisions = review.by_block()
    blocks = []
    for b in draft.blocks:
        d = decisions.get(b.id)
        if d is None or d.decision == "approved":
            blocks.append(b)
        elif d.decision == "edited" and d.text and d.text.strip():
            blocks.append(b.model_copy(update={"text": d.text.strip()}))
    undecided = sum(1 for b in draft.blocks if b.id not in decisions)
    return FinalText(blocks, reviewed=True, complete=review.completed, undecided=undecided)


def layout_lines(blocks: list[Block], width: int = 85) -> list[str]:
    """Plain text layout: the lines the layout rules check."""
    lines: list[str] = []
    previous = None
    for b in blocks:
        if b.kind == "heading":
            if lines:
                lines.append("")
            lines.append(b.text)
        elif b.kind == "list_item":
            wrapped = wrap_sentence(b.text, width - 2)
            lines.append(f"- {wrapped[0]}")
            lines += [f"  {line}" for line in wrapped[1:]]
        else:
            if previous == "list_item":
                lines.append("")
            lines += wrap_sentence(b.text, width)
        previous = b.kind
    return lines
