"""One German template set for every German variety (docs/prompts.md, "Design choices"):
the templates take the variety's facts as `v.prompt` from
src/leichtfacile/varieties/varieties.toml and include the decision and medication
partials by the path `prompts.render` chooses. tests/pipeline/test_prompt_snapshots.py
freezes the Swiss rendering; these tests keep the Swiss facts out of the templates and
check that a variety gets its own facts and partials, or its language's while it has
none."""

from __future__ import annotations

import dataclasses
import re
import shutil
from pathlib import Path

import pytest
from jinja2 import FileSystemLoader

from leichtfacile.pipeline import prompts
from leichtfacile.pipeline.prompts import PROMPTS_DIR, render
from leichtfacile.pipeline.stages import mode_context
from leichtfacile.varieties import varieties, variety

GERMAN = PROMPTS_DIR / "de"
# The Swiss facts the templates carried until 29 October 2026. Zurich's prompt
# (baseline_zh.md) is Swiss and verbatim and the few-shot examples are a variety's own
# (de/examples), so neither is scanned; the partials are, since every German variety
# includes them until it brings its own.
SWISS = ("Schweiz", "Franken", "Einwohnerkontrolle", "Einwohner·kontrolle", "031 987", "Verfügung")
SMALL = {
    "understand": {"source": "[s0001] Der Text."},
    "write": {
        "style_guide": "", "examples": "", "section": "", "factsheet": "",
        "source": "[s0001] Der Text.",
    },
    "judge": {"factsheet": "", "source": "", "draft": "", "glossary": ""},
    "repair": {
        "style_guide": "", "flagged": "", "missing": "", "factsheet": "", "draft": "",
        "source": "",
    },
}  # fmt: skip
# Made up for the test, not the researched Austrian facts (they come with the Austrian
# prompts): a neuter office, whose articles differ from the Swiss office's.
AUSTRIAN = {
    "country_in": "in Österreich",
    "country_adjective": "österreichisches",
    "doc_types": "Brief, Bescheid, Formular, Merkblatt, Webseite",
    "currency": "Euro",
    "amount_spellings": "42.000 Euro statt EUR 42.000,00",
    "office": "Gemeindeamt",
    "office_split": "Gemeinde·amt",
    "office_article": "das",
    "office_at": "beim",
    "phone": "01 987 65 43",
}


def german_templates() -> list[Path]:
    return [p for p in sorted(GERMAN.glob("*.md")) if p.name != "baseline_zh.md"]


def small_context(stage: str, mode: str = "standard", medication: bool = False) -> dict:
    """A stage's context without a style guide, few-shot examples or a real document."""
    return {
        **SMALL[stage],
        **mode_context(stage, mode, "Frau Muster"),
        "level_name": "Leichter Sprache",
        "level": "A2",
        "medication": medication,
    }


def test_the_german_templates_carry_no_swiss_fact() -> None:
    templates = german_templates()
    stages = {"understand", "write", "judge", "repair", "recover", "baseline"}
    assert {p.stem for p in templates} >= stages | {"decision", "medication"}
    for path in templates:
        text = path.read_text(encoding="utf-8")
        assert not [token for token in SWISS if token in text], path.name


def test_every_german_variety_sets_the_fields_the_templates_use() -> None:
    used: set[str] = set()
    for path in german_templates():
        used |= set(re.findall(r"\bv\.prompt\.(\w+)", path.read_text(encoding="utf-8")))
    # Jinja looks up an attribute of the dict before its key: a field named `items`
    # would render the method.
    assert used and not used & set(dir(dict))
    german = [v for v in varieties().values() if v.lang == "de"]
    assert german
    for v in german:
        assert set(v.prompt) == used, v.key


@pytest.mark.parametrize("stage", ["understand", "write"])
@pytest.mark.parametrize(
    ("mode", "medication"), [("standard", False), ("decision", False), ("standard", True)]
)
def test_a_variety_without_a_table_renders_as_its_language(
    stage: str, mode: str, medication: bool
) -> None:
    # de-AT has no table yet (29 October 2026); once it has, a variety without one
    # takes its place here.
    context = small_context(stage, mode, medication)
    swiss = render("de", stage, **context)
    assert render("de-AT", stage, **context) == swiss
    assert "Einwohner" in swiss  # the Swiss facts, from the `de` table
    assert ("Das Dokument ist ein Entscheid" in swiss) == (mode == "decision")
    assert ("Medikament" in swiss) == medication


def test_a_variety_with_a_table_renders_its_own_facts(monkeypatch) -> None:
    austrian = dataclasses.replace(variety("de"), key="de-AT", region="AT", prompt=AUSTRIAN)
    tables = {**varieties(), "de-AT": austrian}
    monkeypatch.setattr("leichtfacile.varieties.varieties", lambda: tables)
    texts = {stage: render("de-AT", stage, **small_context(stage)) for stage in SMALL}
    assert "Dafür liest du ein amtliches österreichisches Dokument" in texts["understand"]
    assert "Jeder Hund muss beim Gemeindeamt angemeldet sein." in texts["understand"]
    assert "für Menschen in Österreich." in texts["write"]
    assert "Sie melden Ihren Hund beim Gemeinde·amt an." in texts["write"]
    assert "Was das Gemeindeamt ist, wird nicht erklärt." in texts["judge"]
    assert "Rufen Sie das Gemeinde·amt an: 01 987 65 43." in texts["repair"]
    for stage, text in texts.items():
        assert not [token for token in SWISS if token in text], stage
    assert "Einwohnerkontrolle" in render("de", "understand", **small_context("understand"))


def test_a_variety_includes_its_own_partial_else_its_languages(tmp_path, monkeypatch) -> None:
    # A copy of the German folder next to an Austrian decision partial, so that the
    # package's prompt folders stay as they are.
    shutil.copytree(GERMAN, tmp_path / "de")
    (tmp_path / "de-AT").mkdir()
    (tmp_path / "de-AT" / "decision.md").write_text("\nDer österreichische Teil.\n", "utf-8")
    monkeypatch.setattr(prompts, "PROMPTS_DIR", tmp_path)
    monkeypatch.setattr(prompts, "_env", prompts._env.overlay(loader=FileSystemLoader(tmp_path)))
    context = small_context("understand", "decision", medication=True)
    austrian = render("de-AT", "understand", **context)
    swiss = render("de", "understand", **context)
    assert "Der österreichische Teil." in austrian
    assert "Der österreichische Teil." not in swiss
    assert "Das Dokument ist ein Entscheid" in swiss
    assert "Das Dokument ist ein Entscheid" not in austrian
    assert "Das Dokument nennt Dosen von Medikamenten." in austrian  # the language's partial
