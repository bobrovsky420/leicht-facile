"""One German template set for every German variety (docs/prompts.md, "Design choices"):
the templates take the variety's facts as `v.prompt` from
src/leichtfacile/varieties/varieties.toml and include the decision and medication
partials by the path `prompts.render` chooses. tests/pipeline/test_prompt_snapshots.py
freezes the Swiss rendering; these tests keep the Swiss facts out of the templates,
check that a variety gets its own facts and partials, or its language's while it has
none, and that the German and Austrian prompts (since 29 October 2026) carry their own
facts, examples and law and no Swiss word."""

from __future__ import annotations

import dataclasses
import re
import shutil
from pathlib import Path

import pytest
from jinja2 import FileSystemLoader

from leichtfacile.pipeline import prompts
from leichtfacile.pipeline.prompts import PROMPTS_DIR, examples, render
from leichtfacile.pipeline.stages import mode_context
from leichtfacile.rules import style_guide
from leichtfacile.rules.lexicon import hyphenated
from leichtfacile.senders import senders
from leichtfacile.varieties import varieties, variety
from tests.pipeline.test_prompt_snapshots import rendered_prompts

GERMAN = PROMPTS_DIR / "de"  # the stage templates, one set for every German variety
# The Swiss facts the templates carried until 29 October 2026. Zurich's prompt
# (baseline_zh.md), the few-shot examples and the decision partial are the Swiss
# variety's own (prompts/de-CH/), so none of them is in the German folder or scanned; the
# medication partial is, since every German variety includes it.
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
# Made up for the test, not the researched Austrian facts of varieties.toml, so that the
# mechanism is tested on facts that stay fixed: a neuter office, whose articles differ
# from the Swiss office's.
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
    return sorted(GERMAN.glob("*.md"))


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
    assert {p.stem for p in templates} >= stages | {"medication"}
    for path in templates:
        text = path.read_text(encoding="utf-8")
        assert not [token for token in SWISS if token in text], path.name


def test_every_german_variety_sets_the_fields_the_templates_use() -> None:
    used: set[str] = set()
    for path in german_templates():
        used |= set(re.findall(r"\bv\.prompt\.(\w+)", path.read_text(encoding="utf-8")))
    # The senders' German phrases take the facts too (senders.toml: {country_adjective}).
    for profile in senders().values():
        for phrase in profile.phrases["de"].values():
            used |= set(re.findall(r"\{(\w+)\}", phrase))
    # Jinja looks up an attribute of the dict before its key: a field named `items`
    # would render the method.
    assert used and not used & set(dir(dict))
    german = [v for v in varieties().values() if v.lang == "de"]
    assert {v.key for v in german} == {"de-CH", "de-DE", "de-AT"}
    for v in german:
        assert set(v.prompt) == used, v.key


@pytest.mark.parametrize("stage", ["understand", "write"])
@pytest.mark.parametrize(
    ("mode", "medication"), [("standard", False), ("decision", False), ("standard", True)]
)
def test_a_variety_without_a_table_renders_as_its_language(
    stage: str, mode: str, medication: bool
) -> None:
    # A key without a table or a prompt folder of its own (made up: there is no region
    # XX); Germany and Austria have both since 29 October 2026.
    context = small_context(stage, mode, medication)
    swiss = render("de-CH", stage, **context)
    assert render("de-XX", stage, **context) == swiss
    assert "Einwohner" in swiss  # the Swiss facts, from the `de-CH` table
    assert ("Das Dokument ist ein Entscheid" in swiss) == (mode == "decision")
    assert ("Medikament" in swiss) == medication


def test_a_variety_with_a_table_renders_its_own_facts(monkeypatch) -> None:
    austrian = dataclasses.replace(
        variety("de-CH"), key="de-AT", region="AT", prompt=AUSTRIAN, compound_mark="hyphen"
    )
    tables = {**varieties(), "de-AT": austrian}
    monkeypatch.setattr("leichtfacile.varieties.varieties", lambda: tables)
    texts = {stage: render("de-AT", stage, **small_context(stage)) for stage in SMALL}
    assert "Dafür liest du ein amtliches österreichisches Dokument" in texts["understand"]
    assert "Jeder Hund muss beim Gemeindeamt angemeldet sein." in texts["understand"]
    assert "für Menschen in Österreich." in texts["write"]
    assert "Sie melden Ihren Hund beim Gemeinde-Amt an." in texts["write"]  # the hyphen: AT
    assert "Was das Gemeindeamt ist, wird nicht erklärt." in texts["judge"]
    assert "Rufen Sie das Gemeinde-Amt an: 01 987 65 43." in texts["repair"]
    for stage, text in texts.items():
        assert not [token for token in SWISS if token in text], stage
    assert "Einwohnerkontrolle" in render("de-CH", "understand", **small_context("understand"))


def test_a_variety_includes_its_own_partial_else_its_languages(tmp_path, monkeypatch) -> None:
    # A copy of the German folders (the templates, the Swiss variety's partial) next to
    # an Austrian decision partial, so that the package's prompt folders stay as they are.
    shutil.copytree(GERMAN, tmp_path / "de")
    shutil.copytree(PROMPTS_DIR / "de-CH", tmp_path / "de-CH")
    (tmp_path / "de-AT").mkdir()
    (tmp_path / "de-AT" / "decision.md").write_text("\nDer österreichische Teil.\n", "utf-8")
    monkeypatch.setattr(prompts, "PROMPTS_DIR", tmp_path)
    monkeypatch.setattr(prompts, "_env", prompts._env.overlay(loader=FileSystemLoader(tmp_path)))
    context = small_context("understand", "decision", medication=True)
    austrian = render("de-AT", "understand", **context)
    swiss = render("de-CH", "understand", **context)
    assert "Der österreichische Teil." in austrian
    assert "Der österreichische Teil." not in swiss
    assert "Das Dokument ist ein Entscheid" in swiss
    assert "Das Dokument ist ein Entscheid" not in austrian
    assert "Das Dokument nennt Dosen von Medikamenten." in austrian  # the language's partial


# The Swiss words of the standard templates' facts and of the Swiss decision partial;
# `innert` as a word, since "erinnert" is standard German.
SWISS_WORDS = re.compile(
    r"Schweiz|Franken|Einwohner·?kontrolle|031 987|Verfügung|\binnert\b|Beist(?:and|ändin)"
    r"|Einsprache|Dispositiv"
)
# The synthetic letter's fact sheet and draft are Swiss (tests/pipeline/fixtures.py) and
# come into the prompts of every variety, and the style guide is the rules' own
# (rules/styleguide.py): the scan leaves both out, it is about what the variety's table,
# few-shot examples and partials put in.
LETTER_WORDS = ("Gebühr 20 Franken.", "Die Gebühr ist 20 Franken.", "Das kostet 20 Franken.")
# Per variety: the office of the standard templates' examples, as written there, and the
# words of the decision partial's law.
COUNTRIES = {
    "de-DE": (
        ("Bürgeramt", "Bürger-Amt"),  # the compound mark of Germany (rules/lexicon.hyphenated)
        ("Bescheid", "Widerspruch", "Klage", "Rechtsbehelfsbelehrung", "nach Bekanntgabe",
         "Betreuerin"),
    ),
    "de-AT": (
        ("Gemeindeamt", "Gemeinde-Amt"),
        ("Bescheid", "Spruch", "Beschwerde", "Rechtsmittelbelehrung", "nach Zustellung",
         "Erwachsenenvertreterin"),
    ),
}  # fmt: skip


def own_text(key: str, text: str) -> str:
    """A rendered prompt without the synthetic letter's Swiss words and the style guide."""
    for level in ("A2", "B1"):
        text = text.replace(style_guide(key, level), "")
    for words in LETTER_WORDS:
        text = text.replace(words, "")
    return text


def added(texts: dict[str, str], form: str, standard: str) -> str:
    """The lines a form adds to the standard prompt: the partial's section."""
    lines = set(texts[standard].splitlines())
    return "\n".join(line for line in texts[form].splitlines() if line not in lines)


@pytest.mark.parametrize("key", sorted(COUNTRIES))
def test_germany_and_austria_render_their_own_facts_and_law(key: str) -> None:
    offices, law = COUNTRIES[key]
    texts = rendered_prompts(key)  # every stage and form, on the synthetic letter
    swiss = rendered_prompts("de-CH")
    assert set(texts) == {name for name in swiss if not name.startswith("baseline_zh")}
    for name, text in texts.items():
        assert "{{" not in text and "{%" not in text, name
        found = SWISS_WORDS.findall(own_text(key, text))
        assert not found, (name, found)
    assert SWISS_WORDS.search(own_text("de-CH", swiss["write A2"]))  # the scan sees Swiss facts
    # The office and the currency of the variety's table, its own few-shot examples.
    for stage in ("understand", "write", "judge", "repair"):
        assert any(office in texts[f"{stage} A2"] for office in offices), stage
    for stage in ("understand", "write", "judge"):
        assert "120 Euro" in texts[f"{stage} A2"], stage
    # The examples are written with the Mediopunkt and rendered with the variety's mark.
    assert examples(key) != examples("de-CH") and hyphenated(examples(key)) in texts["write A2"]
    # The decision partial is the variety's own: a Bescheid and the country's appeal.
    assert prompts._partial(key, "decision") == f"{key}/decision.md"
    for stage in ("understand", "write", "judge", "repair"):
        assert "Bescheid" in added(texts, f"{stage} A2 decision", f"{stage} A2"), stage
    understand = added(texts, "understand A2 decision", "understand A2")
    assert [word for word in law if word not in understand] == []
    # The medication partial is the language's, word for word.
    assert prompts._partial(key, "medication") == "de/medication.md"
    for stage in ("understand", "write"):
        form, standard = f"{stage} A2 medication", f"{stage} A2"
        assert "Medikament" in added(texts, form, standard)
        assert added(texts, form, standard) == added(swiss, form, standard)
