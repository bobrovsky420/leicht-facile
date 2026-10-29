"""The national varieties (docs/architecture.md section 8): the keys, the table, the
fallback to the language, and what setup offers while only Swiss German ships."""

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


def test_the_table_holds_the_swiss_varieties_and_falls_back_to_the_language() -> None:
    assert set(varieties()) == {"de", "fr", "it"}
    assert table("de").word_lang == "de-CH" and table("de").hyphenation == "de_CH"
    assert table("fr", "DE") is table("fr")  # French is Swiss whatever the region
    assert table("de-AT").notice == table("de").notice  # no Austrian table yet
    with pytest.raises(KeyError):
        table("rm")
    assert table("de").notice.endswith("Massgebend ist der Entscheid.")
    assert region_for("de", "AT") == "AT" and region_for("fr", "AT") == "CH"


def test_only_switzerland_is_complete_so_setup_asks_nothing() -> None:
    assert complete("de") and complete("fr") and complete("it")
    assert not complete("de-DE") and not complete("de-AT")
    assert regions() == ("CH",)


def test_lookups_by_a_variety_key_take_the_language_until_the_variety_has_its_own() -> None:
    # The prompts, the few-shot examples, the style guide and the rule checks of `de-AT`
    # are the German ones today; the Zurich baseline is Swiss and is not inherited.
    assert render("de-AT", "baseline", level_name="x", level="A2", text="t") == render(
        "de", "baseline", level_name="x", level="A2", text="t"
    )
    assert examples("de-AT") == examples("de")
    assert style_guide("de-AT", "A2") == style_guide("de", "A2")
    assert has_prompt("de", "baseline_zh") and not has_prompt("de-AT", "baseline_zh")
    spec = RULES["LEN-01"]
    assert spec.check_for("de-AT") is spec.check_for("de")
    assert spec.guide_for("de-AT", "A2") == spec.guide_for("de", "A2")
    checker = get_checker("de-AT")
    assert (checker.lang, checker.variety) == ("de", "de-AT")
    assert checker.nlp is get_checker("de").nlp  # one spaCy pipeline per language
