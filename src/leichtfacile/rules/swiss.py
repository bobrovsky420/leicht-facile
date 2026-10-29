"""Swiss spelling written by code (docs/rules.md, REG-01, CH-01 until 29 October 2026):
`ß` becomes `ss`.

Rule REG-01 flags every `ß` and proposes the word with `ss`; this step writes it, in the
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
from leichtfacile.rules.vocabulary import standard_spelling
from leichtfacile.schemas import CodeEdit, Draft

RULE_ID = "REG-01"
LANGS = ("de",)
STANDARD_REGIONS = ("DE", "AT")  # the varieties that write the sharp s
_WORD_WITH_SZ = re.compile(r"[^\W\d_·]*ß[^\W\d_·]*")
_WORD_RE = re.compile(r"[^\W\d_]+(?:·[^\W\d_]+)*")  # a word, its Mediopunkt parts included


def replace_ss(text: str) -> tuple[str, list[tuple[str, str]]]:
    """The text with every `ß` written as `ss`, and (before, after) per changed word."""
    changes = [(m.group(0), m.group(0).replace("ß", "ss")) for m in _WORD_WITH_SZ.finditer(text)]
    return (text.replace("ß", "ss"), changes) if changes else (text, [])


def replace_sz(text: str) -> tuple[str, list[tuple[str, str]]]:
    """The text in the spelling of Germany and Austria: the sharp s for the Swiss `ss` of
    the stems in rules/data/spelling_de.toml (`vocabulary.standard_spelling`), and
    (before, after) per changed word."""
    changes: list[tuple[str, str]] = []

    def standard(m: re.Match[str]) -> str:
        word = m.group(0)
        out = standard_spelling(word)
        if out != word:
            changes.append((word, out))
        return out

    return _WORD_RE.sub(standard, text), changes


def apply_spelling(draft: Draft) -> tuple[Draft, list[CodeEdit]]:
    """The variety's spelling written by code: `ss` for `ß` in Swiss German (`apply_ss`),
    the sharp s for the Swiss `ss` in the German of Germany and Austria (`apply_sz`);
    nothing for the other languages. The orchestrator runs it after the write stage and
    every repair round, in P1 and P2 (docs/architecture.md §4.3)."""
    if draft.lang not in LANGS:
        return draft, []
    return apply_sz(draft) if draft.region in STANDARD_REGIONS else apply_ss(draft)


def apply_ss(draft: Draft) -> tuple[Draft, list[CodeEdit]]:
    """The draft with `ss` for `ß` in its blocks and glossary, and the edits made, which
    are also recorded on the returned draft (`code_edits`, one entry per changed word);
    a draft without `ß` comes back as it is."""
    if draft.lang not in LANGS:
        return draft, []
    return _apply(draft, replace_ss)


def apply_sz(draft: Draft) -> tuple[Draft, list[CodeEdit]]:
    """The draft with the sharp s where Germany and Austria write it, recorded like
    `apply_ss`; a draft without a Swiss `ss` comes back as it is."""
    if draft.lang not in LANGS:
        return draft, []
    return _apply(draft, replace_sz)


def _apply(draft: Draft, replace) -> tuple[Draft, list[CodeEdit]]:
    edits: list[CodeEdit] = []
    blocks = []
    for block in draft.blocks:
        text, changes = replace(block.text)
        edits += _edits(block.id, changes)
        blocks.append(block.model_copy(update={"text": text}) if changes else block)
    glossary = []
    for entry in draft.glossary:
        term, term_changes = replace(entry.term)
        explanation, text_changes = replace(entry.explanation)
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
