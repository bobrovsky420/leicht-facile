"""The national varieties (docs/architecture.md section 8): the keys, the table, the
fallback to the language, and what setup offers: Switzerland, Germany and Austria since
the German and Austrian prompts of 29 October 2026."""

from __future__ import annotations

import pytest

from leichtfacile.pipeline.prompts import examples, has_prompt, render
from leichtfacile.rules import get_checker, style_guide
from leichtfacile.rules.base import RULES
from leichtfacile.schemas import Draft, JobConfig, SourceDocument, SourceInfo, base_lang, variety
from leichtfacile.varieties import complete, region_for, regions, varieties
from leichtfacile.varieties import variety as table


def test_variety_keys_and_their_language() -> None:
    assert variety("de") == "de" and variety("de", "CH") == "de"
    assert variety("de", "DE") == "de-DE" and variety("de", "AT") == "de-AT"
    assert base_lang("de-AT") == "de" and base_lang("fr") == "fr"


def test_artifacts_are_swiss_unless_they_say_otherwise() -> None:
    source = SourceDocument(id="d", lang="de", source=SourceInfo(type="text"), segments=[])
    assert source.region == "CH" and source.variety == "de"
    assert Draft(doc_id="d", lang="de", level="A2", blocks=[]).variety == "de"
    assert Draft(doc_id="d", lang="de", region="AT", level="A2", blocks=[]).variety == "de-AT"
    assert JobConfig().region == "CH"
    # A stored artifact from before the field read as Swiss (the default), as the
    # evaluation's cached pages do.
    assert (
        SourceDocument.model_validate_json(
            '{"id": "d", "lang": "fr", "source": {"type": "text"}, "segments": []}'
        ).region
        == "CH"
    )


def test_the_table_holds_the_varieties_and_falls_back_to_the_language() -> None:
    assert set(varieties()) == {"de", "de-DE", "de-AT", "fr", "it"}
    assert table("de").word_lang == "de-CH" and table("de").hyphenation == "de_CH"
    assert table("de", "DE") is table("de-DE") and table("de", "AT") is table("de-AT")
    assert (table("de-DE").word_lang, table("de-DE").hyphenation) == ("de-DE", "de_DE")
    assert (table("de-AT").word_lang, table("de-AT").hyphenation) == ("de-AT", "de_AT")
    assert table("fr", "DE") is table("fr")  # French is Swiss whatever the region
    assert table("de-XX") is table("de")  # a key without a table: its language's
    with pytest.raises(KeyError):
        table("rm")
    assert table("de").notice.endswith("Massgebend ist der Entscheid.")
    assert table("de-DE").notice.endswith("Maßgebend ist der Bescheid.")
    assert table("de-AT").notice == table("de-DE").notice
    assert region_for("de", "AT") == "AT" and region_for("fr", "AT") == "CH"


def test_the_three_german_varieties_are_complete_so_setup_asks_for_one() -> None:
    assert complete("de") and complete("fr") and complete("it")
    assert complete("de-DE") and complete("de-AT")  # their tables and few-shot examples
    assert not complete("de-XX")
    assert regions() == ("CH", "DE", "AT")


def test_lookups_by_a_variety_key_take_the_language_until_the_variety_has_its_own() -> None:
    # A key without a table or a prompt folder of its own (made up: there is no region
    # XX) takes the German prompts, few-shot examples, style guide and rule checks; the
    # Zurich baseline is Swiss and is not inherited.
    key = "de-XX"
    assert render(key, "baseline", level_name="x", level="A2", text="t") == render(
        "de", "baseline", level_name="x", level="A2", text="t"
    )
    assert examples(key) == examples("de")
    assert style_guide(key, "A2") == style_guide("de", "A2")
    assert has_prompt("de", "baseline_zh") and not has_prompt(key, "baseline_zh")
    spec = RULES["LEN-01"]
    assert spec.check_for(key) is spec.check_for("de")
    assert spec.guide_for(key, "A2") == spec.guide_for("de", "A2")
    checker = get_checker(key)
    assert (checker.lang, checker.variety) == ("de", key)
    assert checker.nlp is get_checker("de").nlp  # one spaCy pipeline per language
    # Germany and Austria bring their own few-shot examples and decision partial and
    # inherit the rest (tests/pipeline/test_prompt_varieties.py).
    assert examples("de-AT") != examples("de") and "Jänner" in examples("de-AT")
    assert not has_prompt("de-AT", "baseline_zh")
