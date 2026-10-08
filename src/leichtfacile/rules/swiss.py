"""Swiss spelling written by code (docs/rules.md, CH-01): `ß` becomes `ss`.

Rule CH-01 flags every `ß` and proposes the word with `ss`; this step writes it, in the
blocks and in the glossary, after the write stage and after every repair round, before
the check, like the Mediopunkt (rules/mediopunkt.py). The 8B writes `ß` now and then
(`Straße`, `außerdem`), and a repair round for a letter is a poor use of a model call
when the fix is one character. The CLI `check` is untouched: it checks a text as it is,
and a baseline measures the prompt alone (the orchestrator runs the step in P1 and P2
only). No value of the fact contract can change: `ß` stands in no number, date,
address or web address.
"""

from __future__ import annotations

import re

from leichtfacile.rules.mediopunkt import GLOSSARY
from leichtfacile.schemas import CodeEdit, Draft

RULE_ID = "CH-01"
LANGS = ("de",)
_WORD_WITH_SZ = re.compile(r"[^\W\d_·]*ß[^\W\d_·]*")


def replace_ss(text: str) -> tuple[str, list[tuple[str, str]]]:
    """The text with every `ß` written as `ss`, and (before, after) per changed word."""
    changes = [(m.group(0), m.group(0).replace("ß", "ss")) for m in _WORD_WITH_SZ.finditer(text)]
    return (text.replace("ß", "ss"), changes) if changes else (text, [])


def apply_ss(draft: Draft) -> tuple[Draft, list[CodeEdit]]:
    """The draft with `ss` for `ß` in its blocks and glossary, and the edits made, which
    are also recorded on the returned draft (`code_edits`, one entry per changed word);
    a draft without `ß` comes back as it is."""
    if draft.lang not in LANGS:
        return draft, []
    edits: list[CodeEdit] = []
    blocks = []
    for block in draft.blocks:
        text, changes = replace_ss(block.text)
        edits += _edits(block.id, changes)
        blocks.append(block.model_copy(update={"text": text}) if changes else block)
    glossary = []
    for entry in draft.glossary:
        term, term_changes = replace_ss(entry.term)
        explanation, text_changes = replace_ss(entry.explanation)
        edits += _edits(GLOSSARY, term_changes + text_changes)
        if term_changes or text_changes:
            entry = entry.model_copy(update={"term": term, "explanation": explanation})
        glossary.append(entry)
    if not edits:
        return draft, []
    update = {"blocks": blocks, "glossary": glossary, "code_edits": [*draft.code_edits, *edits]}
    return draft.model_copy(update=update), edits


def _edits(block_id: str, changes: list[tuple[str, str]]) -> list[CodeEdit]:
    return [CodeEdit(block_id=block_id, rule_id=RULE_ID, before=a, after=b) for a, b in changes]
