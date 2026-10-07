"""The vocabulary in the pipeline (rules/vocabulary.py): checked explanations in the fact
sheet, the office words of the source in the write prompt, missing glossary entries by
code, office words in the repair rounds, and the setting that leaves all of it out."""

from __future__ import annotations

import pytest

from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline import stages
from leichtfacile.pipeline.orchestrator import Orchestrator, build_request
from leichtfacile.rules.glossary import MAX_ADDED, fill_glossary, unexplained_terms
from leichtfacile.rules.vocabulary import load_vocabulary
from leichtfacile.schemas import (
    Block,
    Draft,
    FactSheet,
    Finding,
    GlossaryEntry,
    HardTerm,
    PipelineSummary,
    RuleFindings,
    Segment,
)
from leichtfacile.store import Store
from tests.conftest import chat_response, make_settings
from tests.pipeline import fixtures as fx
from tests.pipeline.test_orchestrator import new_job


@pytest.fixture
def store(tmp_path) -> Store:
    s = Store(tmp_path / "vocabulary.sqlite")
    yield s
    s.close()


def _explanation(lang: str, term: str) -> str | None:
    return next(e.explanation for e in load_vocabulary(lang) if e.term == term)


def _draft(*texts: str, glossary: list[GlossaryEntry] | None = None) -> Draft:
    blocks = [Block(id=f"b{i:03d}", kind="sentence", text=t) for i, t in enumerate(texts, 1)]
    return Draft(doc_id="d", lang="de", level="A2", blocks=blocks, glossary=glossary or [])


def test_the_fact_sheet_gets_the_checked_explanations_and_the_terms_of_the_source() -> None:
    source = fx.letter()
    fs = FactSheet(
        doc_id=source.id,
        hard_terms=[
            HardTerm(term="Prämien·verbilligung", explanation="Der Kanton bezahlt einen Teil."),
            HardTerm(term="Sozialamt", explanation="Ein Amt."),
        ],
    )
    out = stages.vocabulary_terms(fs, source)
    by_term = {t.term: t for t in out.hard_terms}
    listed = by_term["Prämien·verbilligung"]
    assert listed.explanation == _explanation("de", "Prämienverbilligung")
    assert listed.origin == "vocabulary"
    assert by_term["Sozialamt"].origin == "model"  # the vocabulary has no entry: unchanged
    added = out.hard_terms[2:]
    assert {"Gesuch", "Anspruch"} <= {t.term for t in added}
    assert all(t.origin == "vocabulary" and t.segment_ids for t in added)
    assert by_term["Gesuch"].segment_ids == ["s0003"]
    assert len(out.hard_terms) <= stages.MAX_HARD_TERMS


def test_the_write_prompt_lists_office_words_but_not_role_nouns() -> None:
    segments = [
        *fx.letter().segments,
        Segment(id="s0007", kind="paragraph", text="Der Gesuchsteller zahlt innert 30 Tagen."),
    ]
    lines = stages.word_list(segments, "de").splitlines()
    assert lines[:3] == ["- einreichen: schicken", "- Auskunft: Information", "- erteilen: geben"]
    assert "- innert: innerhalb von" in lines
    assert not [line for line in lines if "Gesuchsteller" in line]  # LEX-06 asks for Sie


def test_the_glossary_gets_the_missing_hard_terms_once() -> None:
    draft = _draft(
        "Die Franchise und der Selbstbehalt stehen Ihnen zur Verfügung.",
        "Die Leistung ist gut.",
        glossary=[GlossaryEntry(term="Franchise", explanation="Ein Betrag.")],
    )
    out, edits = fill_glossary(draft)
    assert [(g.term, g.origin) for g in out.glossary] == [
        ("Franchise", "model"),
        ("Selbstbehalt", "vocabulary"),
    ]  # not Verfügung (zur Verfügung), not Leistung (context-dependent)
    assert out.glossary[1].explanation == _explanation("de", "Selbstbehalt")
    assert [(e.block_id, e.rule_id, e.before, e.after) for e in edits] == [
        ("glossary", "SEM-05", "", "Selbstbehalt")
    ]
    assert out.code_edits == edits
    assert fill_glossary(out) == (out, [])  # a second run changes nothing
    assert unexplained_terms(out) == []


def test_code_adds_a_few_entries_per_version() -> None:
    terms = ["Franchise", "Selbstbehalt", "Kostengutsprache", "Spitex", "Rechtsvorschlag",
             "Zahlungsbefehl", "Verlustschein", "Quellensteuer"]  # fmt: skip
    out, edits = fill_glossary(_draft(*(f"Hier steht {t}." for t in terms)))
    assert len(edits) == len(out.glossary) == MAX_ADDED
    assert [g.term for g in out.glossary] == [t for t in terms if t in {e.after for e in edits}]


def test_office_words_go_to_the_repair_round_only_with_the_vocabulary() -> None:
    draft = _draft("Sie zahlen innert 30 Tagen.")
    finding = Finding(
        block_id="b001",
        rule_id="LEX-07",
        severity="warn",
        message="Office word 'innert': simpler is innerhalb von.",
        suggestion="innerhalb von",
    )
    rules = RuleFindings(draft_version=1, level="A2", findings=[finding])
    factsheet = FactSheet(doc_id="d")
    assert build_request(draft, rules, None, factsheet).problems == {
        "b001": ["  - LEX-07: Office word 'innert': simpler is innerhalb von. "
                 "Vorschlag: innerhalb von"]
    }  # fmt: skip
    assert not build_request(draft, rules, None, factsheet, vocabulary=False)


@pytest.mark.parametrize("on", [True, False])
def test_a_job_uses_the_vocabulary_unless_it_is_switched_off(store, endpoint, sleeps, on) -> None:
    settings = make_settings(llm_max_retries=0, use_vocabulary=on, vocabulary_prompt=True)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="P1")
    Orchestrator(store, llm, settings).run(job_id)
    assert store.get_job(job_id).status == "needs_review", store.get_job(job_id).error
    factsheet = store.get_artifact(job_id, "factsheet", FactSheet)
    draft = store.get_artifact(job_id, "draft", Draft, version=1)
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    write_prompt = endpoint.chat_bodies()[1]["messages"][-1]["content"]
    origins = {t.origin for t in factsheet.hard_terms} | {g.origin for g in draft.glossary}
    if on:
        assert factsheet.hard_terms[0].origin == "vocabulary"  # Prämienverbilligung
        assert "- einreichen: schicken" in write_prompt
        assert "Gesuch" in [g.term for g in draft.glossary if g.origin == "vocabulary"]
        assert summary.vocabulary
    else:
        assert origins == {"model"}
        assert "einreichen: schicken" not in write_prompt
        assert summary.vocabulary is None


def test_the_word_list_is_off_by_default(store, endpoint, sleeps) -> None:
    settings = make_settings(llm_max_retries=0)
    assert settings.use_vocabulary and not settings.vocabulary_prompt
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="P1")
    Orchestrator(store, llm, settings).run(job_id)
    write_prompt = endpoint.chat_bodies()[1]["messages"][-1]["content"]
    assert "einreichen: schicken" not in write_prompt  # it primed the 8B (docs/prompts.md)
    draft = store.get_artifact(job_id, "draft", Draft, version=1)
    assert "Gesuch" in [g.term for g in draft.glossary if g.origin == "vocabulary"]
