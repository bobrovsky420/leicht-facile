"""The rule registry, docs/rules.md and the generated style guide stay in sync."""

from __future__ import annotations

import re
from pathlib import Path

from leichtfacile.rules import PARAMS, RULES, check_draft, get_checker, style_guide
from leichtfacile.rules.base import checked_languages
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
    return sum(1 for spec in RULES.values() if spec.check_for(lang))


def test_the_readme_states_the_rule_counts() -> None:
    """The counts the README states follow the registry."""
    de, fr, it = checked_rules("de"), checked_rules("fr"), checked_rules("it")
    readme = (RULES_MD.parents[1] / "README.md").read_text(encoding="utf-8")
    assert f"{de} deterministic rules for German, {fr} for French and {it} for Italian" in readme
    stated = re.findall(r"(\d+) deterministic rules", readme)
    assert stated and {int(n) for n in stated} == {de}


def test_the_check_page_offers_the_languages_with_checks() -> None:
    assert checked_languages() == ("de", "fr", "it")


def test_every_registered_rule_is_documented() -> None:
    assert set(RULES) - documented_ids() == set()


def test_style_guide_follows_the_level() -> None:
    a2, b1 = style_guide("de", "A2"), style_guide("de", "B1")
    assert "höchstens 12 Wörter" in a2 and "höchstens 15 Wörter" in b1
    assert "Keine Nebensätze" in a2 and "Höchstens ein Nebensatz" in b1
    assert "Medio·punkt" in a2
    # every rule with a German guide text appears in the A2 guide
    guided = [r for r in RULES.values() if r.guide_for("de", "A2")]
    assert len(a2.splitlines()) == len(guided) + 1


def test_french_guide_follows_the_registry_and_the_french_limits() -> None:
    a2, b1 = style_guide("fr", "A2"), style_guide("fr", "B1")
    assert "au plus 15 mots" in a2 and "au plus 18 mots" in b1
    assert "Pas de subordonnée" in a2 and "Au plus une subordonnée" in b1
    guided = [r for r in RULES.values() if r.guide_for("fr", "A2")]
    assert len(a2.splitlines()) == len(guided) + 1


def test_italian_guide_follows_the_registry_and_the_italian_limits() -> None:
    a2, b1 = style_guide("it", "A2"), style_guide("it", "B1")
    assert a2.startswith("Regole per la lingua facile (livello A2):")
    assert b1.startswith("Regole per il linguaggio chiaro (livello B1):")
    assert "al massimo 18 parole" in a2 and "al massimo 21 parole" in b1
    guided = [r for r in RULES.values() if r.guide_for("it", "A2")]
    assert len(a2.splitlines()) == len(guided) + 1


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
