"""The vocabulary lists (rules/data/vocabulary_<lang>.toml): well formed, no duplicate
terms, and every glossary explanation passes the checker at A2."""

from __future__ import annotations

import re

import pytest

from leichtfacile.rules import check_draft
from leichtfacile.rules.vocabulary import load_vocabulary
from leichtfacile.schemas import Block, Draft, GlossaryEntry

LANGS = ("de", "fr")
# LEX-01 wants a Mediopunkt in long German words; code adds it to drafts at A2 only,
# so the level-neutral list keeps the plain spelling.
SKIP_RULES = {"LEX-01"}
DASHES = {chr(0x2013), chr(0x2014)}  # en and em dash: plain hyphen only
SHARP_S = chr(0xDF)  # Swiss German writes ss


@pytest.mark.parametrize("lang", LANGS)
def test_vocabulary_is_well_formed(lang: str) -> None:
    entries = load_vocabulary(lang)
    replace = [e for e in entries if e.kind == "replace"]
    explain = [e for e in entries if e.kind == "explain"]
    assert len(replace) >= 150 and len(explain) >= 90

    seen: dict[str, str] = {}
    for e in entries:
        key = e.term.casefold()
        assert key not in seen, f"{e.term!r} in {e.group} and {seen[key]}"
        seen[key] = e.group
        text = e.easy if e.kind == "replace" else e.explanation
        assert text and text == text.strip() and e.term == e.term.strip()
        assert not DASHES & set(e.term + text), e.term
        if lang == "de":
            assert SHARP_S not in e.term + text, e.term
        if e.kind == "replace":
            assert e.easy != e.term
        else:
            assert text[-1] in ".?", e.term


@pytest.mark.parametrize("lang", LANGS)
def test_explanations_pass_the_checker(lang: str) -> None:
    explain = [e for e in load_vocabulary(lang) if e.kind == "explain"]
    blocks, owner = [], {}
    for i, e in enumerate(explain):
        for j, sentence in enumerate(re.split(r"(?<=[.?])\s+", e.explanation)):
            block = Block(id=f"b{i:03d}.{j}", kind="sentence", text=sentence)
            blocks.append(block)
            owner[block.id] = e.term
    draft = Draft(
        doc_id="vocabulary",
        lang=lang,
        level="A2",
        blocks=blocks,
        glossary=[GlossaryEntry(term=e.term, explanation=e.explanation) for e in explain],
    )
    findings = [
        f"{owner.get(f.block_id, '-')}: {f.rule_id} {f.message}"
        for f in check_draft(draft).findings
        if f.severity != "info" and f.rule_id not in SKIP_RULES
    ]
    assert findings == []
