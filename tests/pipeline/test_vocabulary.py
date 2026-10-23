"""The vocabulary in the pipeline (rules/vocabulary.py): checked explanations in the fact
sheet, the office words of the source in the write prompt, missing glossary entries by
code, office words in the repair rounds, and the setting that leaves all of it out."""

from __future__ import annotations

import pytest

from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline import stages
from leichtfacile.pipeline.models import RepairOut
from leichtfacile.pipeline.orchestrator import Orchestrator, build_request
from leichtfacile.pipeline.stages import RepairRequest, apply_repairs
from leichtfacile.rules.glossary import MAX_ADDED, fill_glossary, unexplained_terms
from leichtfacile.rules.vocabulary import OFFICE_RULES, load_vocabulary
from leichtfacile.schemas import (
    Block,
    Draft,
    FactSheet,
    Finding,
    GlossaryEntry,
    HardTerm,
    PipelineSummary,
    RepairRecord,
    RuleFindings,
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
    settings = make_settings(llm__max_retries=0, pipeline__vocabulary=on, pipeline__polish_rounds=0)
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
        assert "Gesuch" in [g.term for g in draft.glossary if g.origin == "vocabulary"]
        assert summary.vocabulary
    else:
        assert origins == {"model"}
        assert summary.vocabulary is None
    # The writer never gets a list of office words: it primed the 8B (docs/prompts.md).
    assert "einreichen: schicken" not in write_prompt


# -- the vocabulary round ----------------------------------------------------------------

REPAIR_OFFICE = {
    **fx.REPAIR,
    "repairs": [
        {"id": "b002", "texts": ["Schicken Sie das Gesuch gemäss dem Merkblatt an die Gemeinde.",
                                 "Das Gesuch muss bis 31. März 2026 dort sein."]},
        *fx.REPAIR["repairs"][1:],
    ],
}  # fmt: skip
VOCABULARY_ANSWER = {
    "repairs": [
        {"id": "b002", "texts": ["Schicken Sie das Gesuch nach dem Merkblatt an die Gemeinde."]}
    ],
    "additions": [],
}  # fmt: skip


def test_the_vocabulary_round_asks_for_the_office_words_alone() -> None:
    draft = _draft("Sie zahlen innert 30 Tagen.", "Das kostet 20 Franken.")
    findings = [
        Finding(block_id="b001", rule_id="LEX-07", severity="warn", message="Office word 'innert'.",
                suggestion="innerhalb von"),
        Finding(block_id="b002", rule_id="GRAM-01", severity="error", message="Passive voice."),
        Finding(block_id=None, rule_id="FACT-01", severity="error", message="Fact f01 is missing.",
                fact_id="f01"),
    ]  # fmt: skip
    rules = RuleFindings(draft_version=1, level="A2", findings=findings)
    request = build_request(draft, rules, None, FactSheet(doc_id="d"), only=OFFICE_RULES)
    assert list(request.problems) == ["b001"] and request.missing == []
    assert "LEX-07" in request.problems["b001"][0]


def test_a_round_from_an_earlier_version_gets_the_next_free_number() -> None:
    draft = _draft("Sie zahlen innert 30 Tagen.").model_copy(update={"version": 2})
    out = RepairOut.model_validate(
        {"repairs": [{"id": "b001", "texts": ["Sie zahlen innerhalb von 30 Tagen."]}]}
    )
    request = RepairRequest({"b001": ["  - LEX-07: ..."]}, [])
    new = apply_repairs(draft, out, request, FactSheet(doc_id="d"), version=5)
    assert (new.version, new.parent_version) == (5, 2)
    assert new.blocks[0].text == "Sie zahlen innerhalb von 30 Tagen."


@pytest.mark.parametrize("on", [True, False])
def test_the_vocabulary_round_rewrites_the_office_words_of_the_best_version(
    store, endpoint, sleeps, on
) -> None:
    settings = make_settings(
        llm__models__judge="swiss-ai/Apertus-v1.5-70B", llm__max_retries=0, pipeline__vocabulary=on,
        pipeline__polish_rounds=0,
    )  # fmt: skip
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    answers = [fx.UNDERSTAND, fx.WRITE, fx.JUDGE_FIRST, REPAIR_OFFICE, fx.JUDGE_SECOND]
    endpoint.push(*(chat_response(fx.as_json(a)) for a in answers))
    if on:
        endpoint.push(chat_response(fx.as_json(VOCABULARY_ANSWER)))
    job_id = new_job(store, condition="P2")
    Orchestrator(store, llm, settings).run(job_id)
    assert store.get_job(job_id).status == "needs_review", store.get_job(job_id).error
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    v2 = store.get_artifact(job_id, "draft", Draft, version=2)
    assert "gemäss" in v2.by_id()["b002"].text  # the repair round left an office word
    if not on:
        assert summary.final_version == 2 and summary.vocabulary_rounds == 0
        assert len(endpoint.chat_bodies()) == 5
        return
    assert summary.final_version == 3 and summary.vocabulary_rounds == 1
    v3 = store.get_artifact(job_id, "draft", Draft, version=3)
    assert v3.parent_version == 2 and v3.origin == "repair"
    assert v3.by_id()["b002"].text == "Schicken Sie das Gesuch nach dem Merkblatt an die Gemeinde."
    record = store.get_artifact(job_id, "repair", RepairRecord, version=3)
    assert record.kind == "vocabulary" and record.requested_blocks == ["b002"]
    prompt = endpoint.chat_bodies()[5]["messages"][-1]["content"]
    assert "LEX-07" in prompt and "FACT-01" not in prompt
    assert len(endpoint.chat_bodies()) == 6  # no judge call: no fact was involved
