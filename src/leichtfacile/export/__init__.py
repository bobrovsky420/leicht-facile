"""Export of the reviewed draft: Markdown, HTML, Word (DOCX) and the JSON audit bundle.

The review decisions are applied here (`final_blocks`); `layout.py` builds the one
layout every writer serialises (one sentence per line, lines of at most `LINE_CHARS`
characters broken at clause boundaries, the layout rules LAY-01 and LAY-02).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from leichtfacile.schemas import Block, Draft, GlossaryEntry, ReviewState

LABELS = {
    "de": {
        "glossary": "Wörterbuch",
        "draft_note": "Entwurf: noch nicht geprüft.",
        "version": "Entwurf v{version}",
    },
    "fr": {
        "glossary": "Lexique",
        "draft_note": "Brouillon : pas encore relu.",
        "version": "Brouillon v{version}",
    },
    "it": {
        "glossary": "Glossario",
        "draft_note": "Bozza: non ancora rivista.",
        "version": "Bozza v{version}",
    },
}


@dataclass(frozen=True)
class FinalText:
    """The blocks a reader gets: review decisions applied."""

    blocks: list[Block]
    reviewed: bool
    complete: bool  # the reviewer marked the review as complete
    undecided: int = 0  # blocks without a decision; they stay in, as drafted
    glossary: list[GlossaryEntry] = field(default_factory=list)
    undecided_glossary: int = 0  # glossary entries without a decision; they stay in too


def glossary_id(index: int) -> str:
    """The id a glossary entry is decided by, from 1 in the draft's order: g01, g02. A
    review decision names it in `block_id`, next to the block ids."""
    return f"g{index:02d}"


def glossary_ids(draft: Draft) -> dict[str, GlossaryEntry]:
    return {glossary_id(i): g for i, g in enumerate(draft.glossary, 1)}


def final_blocks(draft: Draft, review: ReviewState | None) -> FinalText:
    """The blocks and the glossary a reader gets: a rejected block or glossary entry is
    left out, an edited one carries the reviewer's text (for an entry, its
    explanation), an undecided one stays as drafted."""
    if review is None or review.draft_version != draft.version:
        return FinalText(
            list(draft.blocks), reviewed=False, complete=False, glossary=list(draft.glossary)
        )
    decisions = review.by_block()
    blocks = []
    for b in draft.blocks:
        d = decisions.get(b.id)
        if d is None or d.decision == "approved":
            blocks.append(b)
        elif d.decision == "edited" and d.text and d.text.strip():
            blocks.append(b.model_copy(update={"text": d.text.strip()}))
    glossary = []
    for gid, g in glossary_ids(draft).items():
        d = decisions.get(gid)
        if d is None or d.decision == "approved":
            glossary.append(g)
        elif d.decision == "edited" and d.text and d.text.strip():
            glossary.append(g.model_copy(update={"explanation": d.text.strip()}))
    undecided = sum(1 for b in draft.blocks if b.id not in decisions)
    return FinalText(
        blocks,
        reviewed=True,
        complete=review.completed,
        undecided=undecided,
        glossary=glossary,
        undecided_glossary=sum(1 for gid in glossary_ids(draft) if gid not in decisions),
    )
