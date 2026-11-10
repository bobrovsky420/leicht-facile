"""What code changes after a model stage, declared once (docs/architecture.md §4): the
steps that complete the fact sheet after Understand, and the edits of a draft after the
write stage and after every round. The orchestrator runs a sequence with one call
(`completed`, `edited`) and holds no step of its own; it used to spell the draft's edits
out twice, after the write stage and after a round.

A step is pure: it takes the fact sheet or the draft with the run's `Context` and gives
a new one back. A draft's step also says which edits it made, and each of them stands
on the returned draft (`Draft.code_edits`): a glossary entry from the vocabulary, a
compound split, a word in the variety's spelling. The fact links are bookkeeping, no
edit of the text, so that step reports none.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from leichtfacile.pipeline import facts
from leichtfacile.rules.decision import protect_factsheet
from leichtfacile.rules.glossary import fill_glossary
from leichtfacile.rules.lists import protect_lists
from leichtfacile.rules.medication import medication_names
from leichtfacile.rules.mediopunkt import apply_mediopunkt
from leichtfacile.rules.swiss import apply_spelling
from leichtfacile.schemas import CodeEdit, Draft, FactSheet, SourceDocument


@dataclass(frozen=True)
class Context:
    """What a step may read besides what it changes: the job's source document, its mode
    (`JobConfig.mode`: a decision has protected parts) and whether the vocabulary is on
    (`JobConfig.pipeline.vocabulary`)."""

    source: SourceDocument
    mode: str = "standard"
    vocabulary: bool = True


class FactsTransform(Protocol):
    """A step on the fact sheet after Understand: the fact sheet with its change."""

    def __call__(self, factsheet: FactSheet, ctx: Context) -> FactSheet: ...


class DraftTransform(Protocol):
    """A step on a draft version: the draft with its change, and the edits made, which
    stand on the returned draft too (`Draft.code_edits`)."""

    def __call__(
        self, draft: Draft, factsheet: FactSheet, ctx: Context
    ) -> tuple[Draft, list[CodeEdit]]: ...


# -- the fact sheet after Understand ------------------------------------------------------


def hard_values(factsheet: FactSheet, ctx: Context) -> FactSheet:
    """Every hard value of the source is a fact, and one statement one fact
    (`facts.complete_factsheet`)."""
    return facts.complete_factsheet(factsheet, ctx.source)


def decision_parts(factsheet: FactSheet, ctx: Context) -> FactSheet:
    """In decision mode, the operative part and the appeal instructions are facts to
    keep (rules/decision.py)."""
    return protect_factsheet(factsheet, ctx.source) if ctx.mode == "decision" else factsheet


def list_items(factsheet: FactSheet, ctx: Context) -> FactSheet:
    """Every item of a list of the source is a fact (rules/lists.py). After the
    decision's parts: an item a code fact cites already gets no second one."""
    return protect_lists(factsheet, ctx.source)


def vocabulary_terms(factsheet: FactSheet, ctx: Context) -> FactSheet:
    """The vocabulary's checked explanations for the hard terms, and the source's terms
    the model did not list (`facts.vocabulary_terms`)."""
    return facts.vocabulary_terms(factsheet, ctx.source) if ctx.vocabulary else factsheet


AFTER_UNDERSTAND: tuple[FactsTransform, ...] = (
    hard_values,
    decision_parts,
    list_items,
    vocabulary_terms,
)

# -- a draft after the write stage and after a round ----------------------------------------


def fact_links(draft: Draft, factsheet: FactSheet, ctx: Context) -> tuple[Draft, list[CodeEdit]]:
    """The facts and the source sentences each block conveys (`facts.link_facts`)."""
    return facts.link_facts(draft, factsheet, ctx.source), []


def glossary(draft: Draft, factsheet: FactSheet, ctx: Context) -> tuple[Draft, list[CodeEdit]]:
    """The vocabulary's entries for the hard terms the draft uses unexplained
    (rules/glossary.py). Before the compound marks: they split the terms too."""
    return fill_glossary(draft) if ctx.vocabulary else (draft, [])


def compound_marks(
    draft: Draft, factsheet: FactSheet, ctx: Context
) -> tuple[Draft, list[CodeEdit]]:
    """The long compounds split with the variety's mark (rules/mediopunkt.py); the names
    of the fact sheet's medications stay as written."""
    return apply_mediopunkt(draft, keep=medication_names(factsheet))


def spelling(draft: Draft, factsheet: FactSheet, ctx: Context) -> tuple[Draft, list[CodeEdit]]:
    """The variety's spelling: `ss` in Swiss German, the sharp s in Germany and Austria
    (rules/swiss.py)."""
    return apply_spelling(draft)


# In P1 and P2 only: a baseline measures the prompt alone.
AFTER_WRITE: tuple[DraftTransform, ...] = (fact_links, glossary, compound_marks, spelling)
# A round can bring a new hard term, a long compound or a sharp s: the same steps, before
# the check, so that one text is checked, judged and shown.
AFTER_ROUND: tuple[DraftTransform, ...] = AFTER_WRITE


def completed(factsheet: FactSheet, ctx: Context) -> FactSheet:
    """The fact sheet of the Understand stage after code's steps (`AFTER_UNDERSTAND`)."""
    for step in AFTER_UNDERSTAND:
        factsheet = step(factsheet, ctx)
    return factsheet


def edited(
    steps: Sequence[DraftTransform], draft: Draft, factsheet: FactSheet, ctx: Context
) -> tuple[Draft, list[CodeEdit]]:
    """The draft after the steps, in order, and every edit they made."""
    edits: list[CodeEdit] = []
    for step in steps:
        draft, made = step(draft, factsheet, ctx)
        edits += made
    return draft, edits
