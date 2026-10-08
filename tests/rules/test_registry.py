"""The rule registry, docs/rules.md and the generated style guide stay in sync."""

from __future__ import annotations

import re
from pathlib import Path

from leichtfacile.rules import PARAMS, RULES, check_draft, get_checker, style_guide
from leichtfacile.rules.layout import wrap_sentence
from leichtfacile.schemas import Block, Draft

RULES_MD = Path(__file__).parents[2] / "docs" / "rules.md"


def documented_ids() -> set[str]:
    text = RULES_MD.read_text(encoding="utf-8")
    return set(re.findall(r"^\| ((?:[A-Z]+)-\d{2}(?:-[A-Z]{2})?) \|", text, re.MULTILINE))


def test_every_documented_rule_is_registered() -> None:
    documented = documented_ids()
    pending = {i for i in documented if i.endswith("-IT")}  # Italian later
    assert documented - pending - set(RULES) == set()


def checked_rules(lang: str) -> int:
    """Rules code checks for a language (the judge's rules have no check function)."""
    return sum(1 for spec in RULES.values() if spec.check and spec.lang in (None, lang))


def test_readme_and_report_state_the_rule_counts() -> None:
    """The numbers audit (PLAN.md §13.6): the counts a juror reads follow the registry."""
    de, fr = checked_rules("de"), checked_rules("fr")
    root = RULES_MD.parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    report = (root / "technical_report.md").read_text(encoding="utf-8")
    assert f"{de} deterministic rules for German and {fr} for French" in readme
    assert f"{de} checks for German, {fr} for French" in report
    stated = re.findall(r"(\d+) (?:deterministic rules|checks for German)", readme + report)
    assert stated and {int(n) for n in stated} == {de}


def test_every_registered_rule_is_documented() -> None:
    assert set(RULES) - documented_ids() == set()


def test_style_guide_follows_the_level() -> None:
    a2, b1 = style_guide("de", "A2"), style_guide("de", "B1")
    assert "höchstens 12 Wörter" in a2 and "höchstens 15 Wörter" in b1
    assert "Keine Nebensätze" in a2 and "Höchstens ein Nebensatz" in b1
    assert "Medio·punkt" in a2
    # every German rule with a guide text appears in the A2 guide
    guided = [r for r in RULES.values() if r.lang == "de" and r.guide_for("A2")]
    assert len(a2.splitlines()) == len(guided) + 1


def test_french_guide_follows_the_registry_and_the_french_limits() -> None:
    a2, b1 = style_guide("fr", "A2"), style_guide("fr", "B1")
    assert "au plus 15 mots" in a2 and "au plus 18 mots" in b1
    assert "Pas de subordonnée" in a2 and "Au plus une subordonnée" in b1
    guided = [r for r in RULES.values() if r.lang == "fr" and r.guide_for("A2")]
    assert len(a2.splitlines()) == len(guided) + 1


def test_fixed_guide_for_italian() -> None:
    assert "12 parole" in style_guide("it", "A2")


def test_severity_depends_on_level() -> None:
    text = "Das Formular wird vom Amt geprüft."
    for level, expected in (("A2", "error"), ("B1", "warn")):
        d = Draft(
            doc_id="x", lang="de", level=level, blocks=[Block(id="b1", kind="sentence", text=text)]
        )
        (finding,) = [f for f in check_draft(d).findings if f.rule_id == "GRAM-01"]
        assert finding.severity == expected


def test_layout_rules_on_export_lines() -> None:
    checker = get_checker("de")
    lines = ["Sie bekommen einen Brief. Lesen Sie ihn gut.", "x" * 90, "Am 4. Februar 2026."]
    findings = checker.check_export(lines, "A2")
    assert [f.rule_id for f in findings] == ["LAY-01", "LAY-02"]


def test_wrap_sentence_respects_the_line_limit() -> None:
    sentence = (
        "Wenn Sie im letzten Jahr wenig verdient haben, bekommen Sie vielleicht Geld "
        "von der Gemeinde und vom Kanton zurück, auch für Ihre Kinder."
    )
    lines = wrap_sentence(sentence, PARAMS["A2"].max_line_chars)
    assert all(len(line) <= 85 for line in lines)
    assert " ".join(lines) == sentence
    assert lines[0].endswith(",") or lines[1].startswith(("und", "oder"))
