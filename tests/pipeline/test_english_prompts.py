"""English instructions for German and French documents (LLM_ENGLISH_PROMPTS,
docs/prompts.md "English instructions"): the frozen templates stay the default, and the
English ones carry the document's language wherever the model reads or writes it."""

from __future__ import annotations

import re
import string

import pytest

from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline import render as r
from leichtfacile.pipeline import stages
from leichtfacile.pipeline.labels import LABELS
from leichtfacile.pipeline.orchestrator import Orchestrator, build_request
from leichtfacile.pipeline.prompts import (
    ENGLISH_STAGES,
    available_languages,
    level_name,
    prompt_versions,
    render,
)
from leichtfacile.rules.base import RULES, params_for
from leichtfacile.rules.styleguide import ENGLISH_GUIDES, style_guide
from leichtfacile.schemas import (
    Block,
    Draft,
    Finding,
    JobConfig,
    JudgeReport,
    PipelineSummary,
    RuleFindings,
    Unsupported,
)
from leichtfacile.store import Store
from tests.conftest import chat_response, make_settings
from tests.pipeline import fixtures as fx

LANGS = ("de", "fr")
LANGUAGE = {"de": "German", "fr": "French"}


def _json_example(text: str) -> str:
    match = re.search(r"\n(\{\n.*?\n\})\n", text, re.S)
    assert match, text[:200]
    return match.group(1)


def _judge_prompt(lang: str, english: bool, **mode) -> str:
    return render(
        lang,
        "judge",
        english=english,
        **{**stages.mode_context("judge"), **mode},
        level_name=level_name(lang, "A2", english),
        factsheet="F",
        source="S",
        draft="D",
        glossary="G",
    )


def test_by_default_every_stage_has_the_documents_language() -> None:
    settings = make_settings()
    assert settings.english_prompt_stages == set()
    llm = LLMClient(settings)
    assert not any(stages.english_for(llm, s) for s in ENGLISH_STAGES)
    assert stages.labels_for("fr", False) == "fr"


def test_only_the_named_model_stages_get_english_instructions() -> None:
    llm = LLMClient(make_settings(llm_english_prompts="repair, judge,baseline"))
    assert [s for s in ENGLISH_STAGES if stages.english_for(llm, s)] == ["judge", "repair"]
    assert not stages.english_for(llm, "baseline")  # the baselines stay as a user types
    assert stages.labels_for("de", True) == "en"


def test_english_is_no_document_language() -> None:
    assert available_languages() == ["de", "fr"]


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("stage", ["understand", "write", "repair"])
def test_the_english_template_keeps_the_json_example_word_for_word(lang, stage) -> None:
    for frozen, english in zip(
        stages._static_renders(lang, stage), stages._static_renders(lang, stage, True), strict=True
    ):
        assert "{{" not in english and "{%" not in english
        assert _json_example(english) == _json_example(frozen)
        assert english.startswith("You ")


@pytest.mark.parametrize("lang", LANGS)
def test_the_english_judge_keeps_the_json_example_and_the_rule_words(lang) -> None:
    english = _judge_prompt(lang, True)
    assert _json_example(english) == _json_example(_judge_prompt(lang, False))
    assert f"Write the notes in {LANGUAGE[lang]}." in english
    words = {"de": '"müssen" must not become "können"', "fr": '"devoir" must not become "pouvoir"'}
    assert words[lang] in english


@pytest.mark.parametrize("lang", LANGS)
def test_the_english_prompts_name_the_language_of_the_answer(lang) -> None:
    understand, write, repair = (
        stages._static_renders(lang, s, True)[0] for s in ("understand", "write", "repair")
    )
    assert f"Write all texts in {LANGUAGE[lang]}." in understand
    assert f"Write every text in {LANGUAGE[lang]}." in write
    assert f"- Write every text in {LANGUAGE[lang]}." in repair
    assert f"easy-to-read {LANGUAGE[lang]}" in write  # the level, as English names it
    phone = {"de": "(0441234567)", "fr": "(0321234567)"}
    assert phone[lang] in understand  # the frozen template's example number


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("stage", ["understand", "write", "judge", "repair"])
@pytest.mark.parametrize("addressee", ["", "Lea Muster"])
def test_the_english_partials_render(lang, stage, addressee) -> None:
    common = {"level_name": level_name(lang, "A2", True), "level": "A2", "factsheet": "F",
              "source": "S", "draft": "D", "glossary": "G", "style_guide": "", "flagged": "",
              "missing": "", "section": "", "examples": "", "medication": True}  # fmt: skip
    mode = stages.mode_context(stage, "decision", addressee)
    text = render(lang, stage, english=True, **mode, **common)
    assert "{{" not in text and "{%" not in text
    marker = {"understand": "is a decision of an authority", "write": "is a decision of",
              "judge": "SEM-10: a period", "repair": "The document is a decision."}  # fmt: skip
    assert marker[stage] in text
    if stage in ("understand", "write"):
        assert "medicine" in text
    period = {
        "de": "innert 30 Tagen seit Mitteilung",
        "fr": "dans les 30 jours dès la notification",
    }
    if stage in ("understand", "write"):
        assert period[lang] in text
    assert ("Lea Muster" in text) == bool(addressee)


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("level", ["A2", "B1"])
def test_the_english_style_guide_has_every_rule(lang, level) -> None:
    frozen = style_guide(lang, level).splitlines()
    english = style_guide(lang, level, english=True).splitlines()
    assert len(english) == len(frozen)
    assert english[0].startswith("Rules for ")
    limit = params_for(lang, level).max_words
    assert f"- Write short sentences: at most {limit} words per sentence." in english


def test_every_rule_guide_has_its_english_text() -> None:
    def fields(text: str) -> set[str]:
        return {f for _, f, _, _ in string.Formatter().parse(text) if f}

    guided = {spec.id: spec for spec in RULES.values() if spec.guide}
    assert set(ENGLISH_GUIDES) == set(guided)
    for rule_id, spec in guided.items():
        english = ENGLISH_GUIDES[rule_id]
        assert isinstance(english, dict) == isinstance(spec.guide, dict), rule_id
        if isinstance(spec.guide, dict):
            assert english.keys() == spec.guide.keys(), rule_id
            pairs = [(english[k], spec.guide[k]) for k in spec.guide]
        else:
            pairs = [(english, spec.guide)]
        for text, frozen in pairs:
            assert fields(text) == fields(frozen), rule_id


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("stage", ["understand", "write", "repair"])
def test_the_copy_guard_knows_the_same_example_values(lang, stage) -> None:
    frozen = {v.key for v in stages.example_values(lang, stage)}
    english = {v.key for v in stages.example_values(lang, stage, True)}
    assert frozen <= english
    # The examples' own sentences are copies under either instructions.
    copied = "Die Hunde·steuer kostet 120 Franken pro Hund."
    if lang == "de":
        assert stages.copied_sentences([copied], "de", "write", True) == 1


def test_the_english_labels_have_every_key() -> None:
    assert LABELS["en"].keys() == LABELS["de"].keys() == LABELS["fr"].keys()
    fs = stages.to_factsheet(stages.UnderstandOut.model_validate(fx.UNDERSTAND), "doc")
    text = r.factsheet_text(fs, lang="en")
    assert "Facts:" in text and "Tatsachen:" not in text
    assert "Prämien" in text  # the facts stay German


def test_a_repair_request_in_english_words() -> None:
    draft = Draft(doc_id="d", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Die Prämie wird verbilligt."),
        Block(id="b002", kind="sentence", text="Sie bekommen Geld vom Kanton."),
    ])  # fmt: skip
    rules = RuleFindings(draft_version=1, level="A2", findings=[
        Finding(rule_id="GRAM-01", severity="error", block_id="b001",
                message="Passive voice: 'wird verbilligt'. Say who does what.",
                suggestion="Der Kanton verbilligt die Prämie."),
    ])  # fmt: skip
    judge = JudgeReport(
        draft_version=1, model="m", unsupported=[Unsupported(block_id="b002", note="Nicht so.")]
    )
    fs = stages.to_factsheet(stages.UnderstandOut.model_validate(fx.UNDERSTAND), "doc")
    frozen = build_request(draft, rules, judge, fs)
    english = build_request(draft, rules, judge, fs, labels="en")
    assert "Vorschlag: Der Kanton" in frozen.problems["b001"][0]
    assert "Suggestion: Der Kanton" in english.problems["b001"][0]
    assert english.problems["b002"] == ["  - SEM-06: This is not in the original. Nicht so."]
    fact = fs.facts[0]
    assert stages.missing_value_label(fact, "de", "en").startswith(" (value: ")


def test_a_p2_job_with_english_instructions(tmp_path, endpoint, sleeps) -> None:
    settings = make_settings(
        llm_judge_name="swiss-ai/Apertus-v1.5-70B",
        llm_max_retries=0,
        use_vocabulary=False,
        llm_english_prompts="understand,write,judge,repair",
    )
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    store = Store(tmp_path / "test.sqlite")
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.JUDGE_FIRST)),
        chat_response(fx.as_json(fx.REPAIR)),
        chat_response(fx.as_json(fx.JUDGE_SECOND)),
    )
    job = store.create_job(JobConfig(condition="P2"), title="Brief")
    store.put_artifact(job.id, "source", fx.letter())
    Orchestrator(store, llm, settings).run(job.id)
    assert store.get_job(job.id).status == "needs_review"
    prompts = [b["messages"][0]["content"] for b in endpoint.chat_bodies()]
    assert prompts[0].startswith("You are preparing a version in Leichte Sprache")
    assert prompts[1].startswith("You write official texts in Leichte Sprache")
    assert prompts[2].startswith("You check a draft in Leichte Sprache")
    assert prompts[3].startswith("You improve single blocks")
    assert "Problems:" in prompts[3] and "Probleme:" not in prompts[3]
    assert "Facts:" in prompts[1] and "Tatsachen:" not in prompts[1]
    assert "Sie melden Ihren Hund" in prompts[1]  # the German JSON example
    summary = store.get_artifact(job.id, "summary", PipelineSummary)
    assert all(summary.prompt_versions[s].startswith("en:") for s in ENGLISH_STAGES)
    assert not summary.prompt_versions["baseline"].startswith("en:")
    store.close()


def test_the_frozen_templates_stay_the_default_versions() -> None:
    versions = prompt_versions("de")
    assert versions == prompt_versions("de", ())
    english = prompt_versions("de", {"repair"})
    assert english["repair"].startswith("en:") and english["write"] == versions["write"]
