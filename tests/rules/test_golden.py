"""Golden sentences: every rule fires on its positive and stays silent on its negative
examples (tests/rules/golden_<lang>.yaml), for German and French."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from leichtfacile.rules import RULES, check_draft
from leichtfacile.schemas import Block, Draft, GlossaryEntry

LANGS = ("de", "fr")
HERE = Path(__file__).parent
GOLDEN = {
    lang: yaml.safe_load((HERE / f"golden_{lang}.yaml").read_text(encoding="utf-8"))
    for lang in LANGS
}


def _cases(polarity: str) -> list[tuple[str, str, dict]]:
    cases = []
    for lang, golden in GOLDEN.items():
        for rule_id, groups in golden.items():
            for entry in groups.get(polarity, []):
                case = entry if isinstance(entry, dict) else {"text": entry}
                cases.append((lang, rule_id, case))
    return cases


def _rule_ids(lang: str, case: dict) -> set[str]:
    draft = Draft(
        doc_id="golden",
        lang=lang,
        level=case.get("level", "A2"),
        blocks=[Block(id="b001", kind=case.get("kind", "sentence"), text=case["text"])],
        glossary=[GlossaryEntry(term=t, explanation="...") for t in case.get("glossary", [])],
    )
    return {f.rule_id for f in check_draft(draft).findings if f.block_id == "b001"}


@pytest.mark.parametrize(("lang", "rule_id", "case"), _cases("positive"), ids=lambda v: str(v)[:60])
def test_rule_fires(lang: str, rule_id: str, case: dict) -> None:
    assert rule_id in _rule_ids(lang, case), f"{rule_id} did not fire on: {case['text']}"


@pytest.mark.parametrize(("lang", "rule_id", "case"), _cases("negative"), ids=lambda v: str(v)[:60])
def test_rule_stays_silent(lang: str, rule_id: str, case: dict) -> None:
    assert rule_id not in _rule_ids(lang, case), f"{rule_id} fired on: {case['text']}"


@pytest.mark.parametrize("lang", LANGS)
def test_every_sentence_and_block_rule_has_golden_cases(lang: str) -> None:
    golden = GOLDEN[lang]
    checked = {r.id for r in RULES.values() if r.lang == lang and r.scope in ("sentence", "block")}
    missing = checked - set(golden)
    assert not missing, f"rules without golden sentences: {sorted(missing)}"
    for rule_id, groups in golden.items():
        assert RULES[rule_id].lang == lang, f"{rule_id} is not a {lang} rule"
        assert len(groups.get("positive", [])) >= 2, f"{rule_id}: fewer than 2 positives"
        assert groups.get("negative"), f"{rule_id}: no negatives"
