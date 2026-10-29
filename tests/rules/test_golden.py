"""Golden sentences: every rule fires on its positive and stays silent on its negative
examples (tests/rules/golden_<key>.yaml), for German, French and Italian and for the
German varieties of Germany and Austria, whose files hold the rules with a check or a
table of their own; the German file runs under the varieties too for the other rules."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from leichtfacile.rules import RULES, check_draft
from leichtfacile.schemas import Block, Draft, GlossaryEntry, base_lang

LANGS = ("de", "fr", "it", "de-DE", "de-AT")
VARIETIES = ("de-DE", "de-AT")
# The rules whose check, table or guide differs by variety: the German golden sentences
# of every other rule must give the same answer in Germany and Austria.
VARIETY_RULES = frozenset(
    {"REG-01", "REG-02", "REG-03", "LEX-01", "LEX-02", "LEX-07", "NUM-01", "NUM-02", "NUM-03",
     "NUM-04", "NUM-07", "NUM-08", "GRAM-08", "LEN-01"}
)  # fmt: skip
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
        lang=base_lang(lang),
        region=lang.partition("-")[2] or "CH",
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
    checked = {
        r.id for r in RULES.values() if lang in r.checks and r.scope in ("sentence", "block")
    }
    missing = checked - set(golden)
    assert not missing, f"rules without golden sentences: {sorted(missing)}"
    for rule_id, groups in golden.items():
        assert lang in RULES[rule_id].checks, f"{rule_id} has no {lang} check"
        assert len(groups.get("positive", [])) >= 2, f"{rule_id}: fewer than 2 positives"
        assert groups.get("negative"), f"{rule_id}: no negatives"


@pytest.mark.parametrize("variety", VARIETIES)
def test_the_swiss_golden_sentences_hold_in_the_other_german_varieties(variety: str) -> None:
    """A rule without a check, table or guide of its own for the variety decides the
    German golden sentences exactly as in Switzerland."""
    mismatches = []
    for rule_id, groups in GOLDEN["de"].items():
        if rule_id in VARIETY_RULES:
            continue
        for polarity in ("positive", "negative"):
            for entry in groups.get(polarity, []):
                case = entry if isinstance(entry, dict) else {"text": entry}
                fired = rule_id in _rule_ids(variety, case)
                if fired != (polarity == "positive"):
                    mismatches.append(f"{rule_id} {polarity}: {case['text']}")
    assert mismatches == []
