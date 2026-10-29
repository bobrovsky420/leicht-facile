"""The national varieties (docs/architecture.md section 8): the keys, the table, the
fallback along the chain, and what setup offers: Switzerland, Germany and Austria since
the German and Austrian prompts of 29 October 2026."""

from __future__ import annotations

import pytest

from leichtfacile.pipeline.labels import label
from leichtfacile.pipeline.prompts import examples, has_prompt, render
from leichtfacile.rules import get_checker, style_guide
from leichtfacile.rules.base import RULES
from leichtfacile.rules.document import display_value
from leichtfacile.rules.readability import count_syllables, readability
from leichtfacile.rules.values import extract_values
from leichtfacile.rules.vocabulary import vocabulary_files
from leichtfacile.schemas import (
    LANGS,
    Draft,
    JobConfig,
    SourceDocument,
    SourceInfo,
    base_lang,
    canonical_variety,
    variety,
    variety_chain,
)
from leichtfacile.varieties import complete, region_for, regions, varieties
from leichtfacile.varieties import variety as table


def test_variety_keys_and_their_language() -> None:
    assert variety("de") == "de-CH" and variety("de", "CH") == "de-CH"
    assert variety("de", "DE") == "de-DE" and variety("de", "AT") == "de-AT"
    assert variety("fr") == "fr-CH" and variety("it") == "it-CH"
    assert base_lang("de-AT") == "de" and base_lang("de-CH") == "de" and base_lang("fr") == "fr"
    # A bare language code, the Swiss key until 29 October 2026, still names the Swiss
    # variety wherever a key is taken.
    assert canonical_variety("de") == "de-CH" and canonical_variety("de-AT") == "de-AT"
    assert variety_chain("de-AT") == ("de-AT", "de-CH", "de")
    assert variety_chain("de-CH") == variety_chain("de") == ("de-CH", "de")
    assert variety_chain("fr") == ("fr-CH", "fr")


def test_artifacts_are_swiss_unless_they_say_otherwise() -> None:
    source = SourceDocument(id="d", lang="de", source=SourceInfo(type="text"), segments=[])
    assert source.region == "CH" and source.variety == "de-CH"
    assert Draft(doc_id="d", lang="de", level="A2", blocks=[]).variety == "de-CH"
    assert Draft(doc_id="d", lang="de", region="AT", level="A2", blocks=[]).variety == "de-AT"
    assert Draft(doc_id="d", lang="fr", level="A2", blocks=[]).variety == "fr-CH"
    assert JobConfig().region == "CH"
    # A stored artifact from before the field read as Swiss (the default), as the
    # evaluation's cached pages do.
    assert (
        SourceDocument.model_validate_json(
            '{"id": "d", "lang": "fr", "source": {"type": "text"}, "segments": []}'
        ).region
        == "CH"
    )


def test_the_table_holds_the_varieties_and_falls_back_to_the_swiss_one() -> None:
    assert set(varieties()) == {"de-CH", "de-DE", "de-AT", "fr-CH", "it-CH"}
    assert table("de-CH").word_lang == "de-CH" and table("de-CH").hyphenation == "de_CH"
    assert table("de") is table("de-CH") and table("fr") is table("fr-CH")  # a bare code
    assert table("de", "DE") is table("de-DE") and table("de", "AT") is table("de-AT")
    assert (table("de-DE").word_lang, table("de-DE").hyphenation) == ("de-DE", "de_DE")
    assert (table("de-AT").word_lang, table("de-AT").hyphenation) == ("de-AT", "de_AT")
    assert table("fr", "DE") is table("fr-CH")  # French is Swiss whatever the region
    assert table("de-XX") is table("de-CH")  # a key without a table: its language's Swiss one
    with pytest.raises(KeyError):
        table("rm")
    assert table("de-CH").notice.endswith("Massgebend ist der Entscheid.")
    assert table("de-DE").notice.endswith("Maßgebend ist der Bescheid.")
    assert table("de-AT").notice == table("de-DE").notice
    assert region_for("de", "AT") == "AT" and region_for("fr", "AT") == "CH"


def test_the_three_german_varieties_are_complete_so_setup_asks_for_one() -> None:
    assert complete("de-CH") and complete("fr-CH") and complete("it-CH") and complete("de")
    assert complete("de-DE") and complete("de-AT")  # their tables and few-shot examples
    assert not complete("de-XX")
    assert regions() == ("CH", "DE", "AT")


def test_lookups_by_a_variety_key_take_the_swiss_variety_until_it_has_its_own() -> None:
    # A key without a table or a prompt folder of its own (made up: there is no region
    # XX) takes the German templates and the Swiss few-shot examples, style guide and
    # rule checks; the Zurich baseline is Swiss and is not inherited.
    key = "de-XX"
    assert render(key, "baseline", level_name="x", level="A2", text="t") == render(
        "de-CH", "baseline", level_name="x", level="A2", text="t"
    )
    assert examples(key) == examples("de-CH") == examples("de") != ""
    assert style_guide(key, "A2") == style_guide("de-CH", "A2")
    assert has_prompt("de-CH", "baseline_zh") and has_prompt("de", "baseline_zh")
    assert not has_prompt(key, "baseline_zh")
    spec = RULES["LEN-01"]  # a check of the language, shared by its varieties
    assert spec.check_for(key) is spec.check_for("de-CH") is spec.check_for("de")
    assert spec.guide_for(key, "A2") == spec.guide_for("de-CH", "A2")
    reg = RULES["REG-01"]  # a check per variety: the Swiss one for a key without its own
    assert reg.check_for(key) is reg.check_for("de-CH") is reg.check_for("de")
    assert reg.check_for("de-DE") is not reg.check_for("de-CH")
    checker = get_checker(key)
    assert (checker.lang, checker.variety) == ("de", key)
    assert get_checker("de") is get_checker("de-CH")  # one checker per variety
    assert checker.nlp is get_checker("de-CH").nlp  # one spaCy pipeline per language
    # Germany and Austria bring their own few-shot examples and decision partial and
    # inherit the rest (tests/pipeline/test_prompt_varieties.py).
    assert examples("de-AT") != examples("de-CH") and "Jänner" in examples("de-AT")
    assert not has_prompt("de-AT", "baseline_zh")


def test_a_bare_language_code_answers_as_the_swiss_key_everywhere() -> None:
    """Every lookup that takes a key accepts the bare language code, the Swiss key until
    29 October 2026, and answers as for the Swiss variety. A `lang == "fr"` left in a
    branch turns a French variety into a German one without a word: the parity check
    found one in the readability's mute-e rule when the keys were renamed."""
    french = ["Vous payez la prime chaque mois.", "La commune vous envoie une lettre."]
    assert readability(french, "fr-CH") == readability(french, "fr")
    assert count_syllables("dépense", "fr-CH") == count_syllables("dépense", "fr") == 2
    texts = {
        "de": "Am 4. Mai 2026 zahlen Sie 1'500 Franken.",
        "fr": "Le 4 mai 2026, vous payez 1 500 francs.",
        "it": "Il 4 maggio 2026 paga 1'500 franchi.",
    }
    for lang in LANGS:
        key = variety(lang)
        assert style_guide(key, "A2") == style_guide(lang, "A2")
        assert examples(key) == examples(lang) != ""
        assert label(key, "none") == label(lang, "none")
        assert vocabulary_files(key) == vocabulary_files(lang)
        values = extract_values(texts[lang], key)
        assert "2026-05-04" in [v.canonical for v in values]
        assert values == extract_values(texts[lang], lang)
        assert [display_value(v, key) for v in values] == [display_value(v, lang) for v in values]
