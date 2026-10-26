"""Whole jobs through the orchestrator against the fake endpoint."""

from __future__ import annotations

import pytest

from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline.orchestrator import Orchestrator
from leichtfacile.pipeline.rounds import blocking_count
from leichtfacile.schemas import (
    Draft,
    FactSheet,
    JobConfig,
    JudgeReport,
    PipelineOptions,
    PipelineSummary,
    RuleFindings,
)
from leichtfacile.store import Store
from tests.conftest import FakeEndpoint, chat_response, error_response, make_settings
from tests.pipeline import fixtures as fx


@pytest.fixture
def store(tmp_path) -> Store:
    s = Store(tmp_path / "test.sqlite")
    yield s
    s.close()


def orchestrator(store: Store, endpoint: FakeEndpoint, sleeps: list[float]) -> Orchestrator:
    settings = make_settings(llm__models__judge="swiss-ai/Apertus-v1.5-70B", llm__max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    return Orchestrator(store, llm, settings)


def options(**overrides) -> PipelineOptions:
    """The rounds of a test job: without the vocabulary, the recover round and the polish
    round unless a test asks for them, since each has tests of its own and the answers
    queued below end before them."""
    return PipelineOptions(
        **{"vocabulary": False, "recover_facts": 0, "polish_rounds": 0, **overrides}
    )


def new_job(store: Store, *, rounds: PipelineOptions | None = None, **config) -> str:
    job = store.create_job(JobConfig(pipeline=rounds or options(), **config), title="Brief")
    store.put_artifact(job.id, "source", fx.letter())
    return job.id


def test_c2_runs_understand_write_judge_and_repair(store, endpoint, sleeps) -> None:
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.JUDGE_FIRST)),
        chat_response(fx.as_json(fx.REPAIR)),
        chat_response(fx.as_json(fx.JUDGE_SECOND)),
    )
    job_id = new_job(store, condition="P2")
    orchestrator(store, endpoint, sleeps).run(job_id)

    job = store.get_job(job_id)
    assert job.status == "needs_review", job.error
    assert len(job.usage) == 5
    assert [u.stage for u in job.usage] == ["understand", "write", "judge", "repair", "judge"]

    facts = store.get_artifact(job_id, "factsheet", FactSheet)
    assert [f.id for f in facts.facts] == ["f01", "f02", "f03"]
    assert facts.facts[0].kind == "deadline" and facts.facts[0].segment_ids == ["s0003"]
    assert facts.core.deadline.segment_ids == ["s0003"]

    v1 = store.get_artifact(job_id, "draft", Draft, version=1)
    assert v1.blocks[2].fact_ids == ["f02"]  # linked by code: the block contains 20 Franken
    rules_v1 = store.get_artifact(job_id, "rules", RuleFindings, version=1)
    assert {"GRAM-01", "FACT-01"} <= {f.rule_id for f in rules_v1.findings}

    v2 = store.get_artifact(job_id, "draft", Draft, version=2)
    assert v2.parent_version == 1 and v2.origin == "repair"
    assert [b.id for b in v2.blocks] == ["b001", "b002", "b002.1", "b003", "b004", "b005"]
    assert v2.blocks[2].fact_ids == ["f01"]  # the split keeps the block's facts
    rules_v2 = store.get_artifact(job_id, "rules", RuleFindings, version=2)
    assert "FACT-01" not in {f.rule_id for f in rules_v2.findings}
    judge_v2 = store.get_artifact(job_id, "judge", JudgeReport, version=2)
    assert judge_v2.model == "swiss-ai/Apertus-v1.5-70B-thinking"
    assert blocking_count(rules_v2, judge_v2) == 0

    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.final_version == 2 and summary.rounds_of("repair") == 1
    assert summary.stop_reason == "no_blocking"
    assert summary.prompt_versions["write"] != "none"

    # The model ran with the settings of each stage.
    bodies = endpoint.chat_bodies()
    assert bodies[0]["model"].endswith("-8B-thinking") and bodies[0]["temperature"] == 0.1
    assert bodies[2]["model"].endswith("-70B-thinking") and bodies[2]["temperature"] == 0.0
    assert not bodies[3]["model"].endswith("-thinking")  # repair runs without thinking


def test_c1_stops_after_the_rule_check(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="P1")
    orchestrator(store, endpoint, sleeps).run(job_id)
    assert store.get_job(job_id).status == "needs_review"
    assert store.artifact_names(job_id).keys() == {
        "source",
        "factsheet",
        "draft",
        "rules",
        "summary",
    }


def test_c0_baseline_has_no_provenance(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.BASELINE_TEXT))
    job_id = new_job(store, condition="P0")
    orchestrator(store, endpoint, sleeps).run(job_id)
    draft = store.get_artifact(job_id, "draft", Draft)
    assert draft.origin == "baseline"
    assert [b.kind for b in draft.blocks] == [
        "heading", "sentence", "sentence", "sentence", "list_item", "list_item",
    ]  # fmt: skip
    assert all(not b.segment_ids for b in draft.blocks)
    assert endpoint.chat_bodies()[0]["messages"][0]["content"].startswith(
        "Schreibe diesen Text in Leichter Sprache:"
    )


def test_failed_stage_resumes_without_repeating_earlier_stages(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), error_response(400))
    job_id = new_job(store, condition="P1")
    orch = orchestrator(store, endpoint, sleeps)
    orch.run(job_id)
    job = store.get_job(job_id)
    assert job.status == "failed" and "LLMError" in job.error
    assert store.get_artifact(job_id, "factsheet", FactSheet) is not None

    endpoint.push(chat_response(fx.as_json(fx.WRITE)))
    orch.run(job_id)
    assert store.get_job(job_id).status == "needs_review"
    stages = [u.stage for u in store.get_job(job_id).usage]
    assert stages.count("understand") == 1  # not repeated


def test_stop_after_write(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="P2")
    orchestrator(store, endpoint, sleeps).run(job_id, stop_after="write")
    job = store.get_job(job_id)
    assert job.status == "needs_review" and job.stage == "stopped after write"
    assert "rules" not in store.artifact_names(job_id)


def test_invalid_json_gets_one_repair_round(store, endpoint, sleeps) -> None:
    endpoint.push(
        chat_response("Hier ist das Faktenblatt: {kaputt"),
        chat_response(fx.as_json(fx.UNDERSTAND)),
    )
    job_id = new_job(store, condition="P2")
    orchestrator(store, endpoint, sleeps).run(job_id, stop_after="understand")
    assert store.get_artifact(job_id, "factsheet", FactSheet) is not None
    second = endpoint.chat_bodies()[1]["messages"]
    assert second[-1]["role"] == "user" and "could not be used" in second[-1]["content"]


def test_no_judge_and_no_repair_switches(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="P2", use_judge=False, rounds=options(repair_rounds=0))
    orchestrator(store, endpoint, sleeps).run(job_id)
    assert store.get_job(job_id).status == "needs_review"
    names = store.artifact_names(job_id)
    assert "judge" not in names and names["draft"] == [1]
    assert store.get_artifact(job_id, "summary", PipelineSummary).judge_model is None


def test_rerun_from_write_deletes_later_artifacts(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="P1")
    orch = orchestrator(store, endpoint, sleeps)
    orch.run(job_id)
    orch.rerun(job_id, "write")
    assert set(store.artifact_names(job_id)) == {"source", "factsheet"}
    assert store.get_job(job_id).status == "queued"


def test_repair_rounds_focus_on_blocking_problems_first() -> None:
    from leichtfacile.pipeline.rounds import build_request
    from leichtfacile.schemas import Block, Draft, Finding, RuleFindings

    draft = Draft(doc_id="d", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Das Formular wird geprüft."),
        Block(id="b002", kind="sentence", text="Die Prämienverbilligung hilft."),
    ])  # fmt: skip
    rules = RuleFindings(draft_version=1, level="A2", findings=[
        Finding(block_id="b001", rule_id="GRAM-01", severity="error", key="legacy",
                params={"text": "passive"}),
        Finding(block_id="b002", rule_id="LEX-01", severity="warn", key="legacy",
                params={"text": "long word"}),
    ])  # fmt: skip
    from leichtfacile.pipeline.models import UnderstandOut
    from leichtfacile.pipeline.stages import to_factsheet
    from tests.pipeline.fixtures import UNDERSTAND

    fs = to_factsheet(UnderstandOut.model_validate(UNDERSTAND), "d")
    focused = build_request(draft, rules, None, fs, include_warnings=False)
    assert set(focused.problems) == {"b001"}
    assert set(build_request(draft, rules, None, fs).problems) == {"b001", "b002"}


def test_a_foreign_value_blocks_the_draft_and_goes_to_repair_with_the_suggestion() -> None:
    from leichtfacile.pipeline.rounds import build_request
    from leichtfacile.schemas import Block, Draft, FactSheet, Finding, RuleFindings

    draft = Draft(doc_id="d", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Rufen Sie an: 031 987 65 43."),
    ])  # fmt: skip
    rules = RuleFindings(draft_version=1, level="A2", findings=[
        Finding(block_id="b001", rule_id="FACT-06", severity="error", key="legacy",
                params={"text": "The phone number 031 987 65 43 is not in the source."},
                suggestion="044 123 45 67"),
        Finding(block_id="b001", rule_id="FACT-03", severity="error", key="legacy",
                params={"text": "no provenance"}),
    ])  # fmt: skip
    assert blocking_count(rules, None) == 1  # FACT-03 is for the reviewer
    request = build_request(draft, rules, None, FactSheet(doc_id="d", facts=[]),
                            include_warnings=False)  # fmt: skip
    (line,) = request.problems["b001"]
    assert line.startswith("  - FACT-06:") and "Vorschlag: 044 123 45 67" in line


def test_missing_facts_come_in_small_batches_most_important_first() -> None:
    from leichtfacile.pipeline.rounds import MAX_MISSING_PER_ROUND, build_request
    from leichtfacile.schemas import Block, Draft, Fact, FactSheet, Finding, RuleFindings

    kinds = ["other", "contact", "amount", "deadline", "other", "amount", "condition", "other"]
    fs = FactSheet(doc_id="d", facts=[
        Fact(id=f"f{i:02d}", kind=k, text=f"Tatsache {i}", value_norm="2026-03-31")
        for i, k in enumerate(kinds, 1)
    ])  # fmt: skip
    draft = Draft(doc_id="d", lang="de", level="A2",
                  blocks=[Block(id="b001", kind="sentence", text="Hallo.")])  # fmt: skip
    rules = RuleFindings(draft_version=1, level="A2", findings=[
        Finding(block_id=None, rule_id="FACT-01", severity="error", key="legacy",
                params={"text": "x"}, fact_id=f.id)
        for f in fs.facts
    ])  # fmt: skip
    request = build_request(draft, rules, None, fs)
    assert len(request.missing) == MAX_MISSING_PER_ROUND
    assert [f.kind for f in request.missing][:3] == ["deadline", "amount", "amount"]
    # A facts-only round takes its own cap (pipeline.missing_per_facts_round).
    assert len(build_request(draft, rules, None, fs, facts_only=True, limit=8).missing) == 8
    assert len(build_request(draft, rules, None, fs, facts_only=True, limit=2).missing) == 2


def test_repair_requests_skip_headings_and_speak_the_draft_language() -> None:
    from leichtfacile.pipeline.models import UnderstandOut
    from leichtfacile.pipeline.rounds import build_request
    from leichtfacile.pipeline.stages import to_factsheet
    from leichtfacile.schemas import (
        Block,
        Draft,
        Finding,
        JudgeReport,
        RuleFindings,
        SemanticFinding,
        Unsupported,
    )
    from tests.pipeline.fixtures import UNDERSTAND

    draft = Draft(doc_id="d", lang="fr", level="A2", blocks=[
        Block(id="b001", kind="heading", text="Que faut-il joindre ?"),
        Block(id="b002", kind="sentence", text="Payez le 31.03.2027."),
    ])  # fmt: skip
    rules = RuleFindings(draft_version=1, level="A2", findings=[
        Finding(block_id="b002", rule_id="NUM-03", severity="warn", key="legacy",
                params={"text": "numeric date"}, suggestion="31 mars 2027"),
    ])  # fmt: skip
    judge = JudgeReport(
        draft_version=1,
        model="m",
        semantic_findings=[SemanticFinding(block_id="b001", rule_id="SEM-04", note="?")],
        unsupported=[Unsupported(block_id="b002", note="")],
    )
    fs = to_factsheet(UnderstandOut.model_validate(UNDERSTAND), "d")
    request = build_request(draft, rules, judge, fs)
    assert set(request.problems) == {"b002"}  # the heading is not sent for repair
    lines = " ".join(request.problems["b002"])
    assert "Suggestion : 31 mars 2027" in lines and "Ce n'est pas dans l'original." in lines


def test_a_facts_round_asks_for_the_missing_facts_alone(store, endpoint, sleeps) -> None:
    """The loop stops on "no progress"; a round for the missing facts alone follows,
    with no block flagged, and is measured by the FACT-01 count."""
    from leichtfacile.schemas import RepairRecord

    # Round 1 drops the wrong number instead of fixing it, and the judge then flags a
    # block: as many blocking problems as before, so the loop stops on "no progress"
    # with f03 still missing. The facts round adds the number.
    no_number = {"repairs": [{"id": "b004", "texts": ["Rufen Sie das Sozial·amt an."]}],
                 "additions": []}  # fmt: skip
    judge_before = {
        "fact_checks": [
            {"fact_id": "f01", "status": "present", "block_ids": ["b002"]},
            {"fact_id": "f02", "status": "present", "block_ids": ["b003"]},
            {"fact_id": "f03", "status": "missing", "block_ids": []},
        ]
    }
    judge_after = {**judge_before, "unsupported": [{"block_id": "b005", "note": "Woher?"}]}
    added = {"repairs": [], "additions": [{
        "after": "b004", "texts": ["Die Telefon·nummer ist 044 123 45 67."],
        "fact_ids": ["f03"], "segment_ids": ["s0005"],
    }]}  # fmt: skip
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(judge_before)),
        chat_response(fx.as_json(no_number)),  # repair 1
        chat_response(fx.as_json(judge_after)),  # judge again: a fact was involved
        chat_response(fx.as_json(added)),  # facts 1
        chat_response(fx.as_json(fx.JUDGE_SECOND)),
    )
    job_id = new_job(store, condition="P2", rounds=options(repair_rounds=3, facts_rounds=2))
    orchestrator(store, endpoint, sleeps).run(job_id)
    job = store.get_job(job_id)
    assert job.status == "needs_review", job.error
    assert [u.stage for u in job.usage] == [
        "understand", "write", "judge", "repair", "judge", "repair", "judge",
    ]  # fmt: skip
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.rounds_of("repair") == 1 and summary.rounds_of("facts") == 1
    assert summary.stop_reason == "no_missing_facts"
    assert summary.final_version == 3
    facts_prompt = endpoint.chat_bodies()[5]["messages"][0]["content"]
    assert "Die fehlenden Tatsachen" in facts_prompt
    assert "(Wert: 0441234567; schreibe: 044 123 45 67)" in facts_prompt
    assert "Die Blöcke, die du verbesserst:\n\n(keine)" in facts_prompt
    # The record of each round: what was asked, what came back, what code dropped.
    first = store.get_artifact(job_id, "repair", RepairRecord, version=2)
    assert first.kind == "repair" and first.requested_blocks == ["b002", "b004"]  # passive, number
    assert first.requested_facts == ["f03"] and first.dropped == []
    second = store.get_artifact(job_id, "repair", RepairRecord, version=3)
    assert second.kind == "facts" and second.requested_blocks == []
    assert second.requested_facts == ["f03"]
    assert second.additions[0].fact_ids == ["f03"]
    rules_v3 = store.get_artifact(job_id, "rules", RuleFindings, version=3)
    assert "FACT-01" not in {f.rule_id for f in rules_v3.findings}


def test_facts_rounds_stop_without_progress_and_are_off_with_the_repair(
    store, endpoint, sleeps
) -> None:
    no_number = {"repairs": [{"id": "b004", "texts": ["Rufen Sie das Sozial·amt an."]}],
                 "additions": []}  # fmt: skip
    judge_before = {"fact_checks": [{"fact_id": "f03", "status": "missing", "block_ids": []}]}
    judge_after = {**judge_before, "unsupported": [{"block_id": "b005", "note": "Woher?"}]}
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(judge_before)),
        chat_response(fx.as_json(no_number)),  # repair 1: no progress
        chat_response(fx.as_json(judge_after)),
        chat_response(fx.as_json({"repairs": [], "additions": []})),  # facts 1: nothing added
        chat_response(fx.as_json(judge_after)),
    )
    job_id = new_job(store, condition="P2", rounds=options(repair_rounds=1, facts_rounds=2))
    orchestrator(store, endpoint, sleeps).run(job_id)
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.rounds_of("repair") == 1 and summary.rounds_of("facts") == 1
    assert summary.stop_reason == "facts_no_progress"
    assert len(store.get_job(job_id).usage) == 7

    # Without repair rounds there are no facts rounds either.
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="P2", use_judge=False, rounds=options(repair_rounds=0))
    orchestrator(store, endpoint, sleeps).run(job_id)
    assert store.get_artifact(job_id, "summary", PipelineSummary).rounds_of("facts") == 0


def test_a_facts_only_request_flags_no_block() -> None:
    from leichtfacile.pipeline.models import UnderstandOut
    from leichtfacile.pipeline.rounds import build_request, missing_count
    from leichtfacile.pipeline.stages import to_factsheet
    from leichtfacile.schemas import Block, Draft, Finding, RuleFindings
    from tests.pipeline.fixtures import UNDERSTAND

    fs = to_factsheet(UnderstandOut.model_validate(UNDERSTAND), "d")
    draft = Draft(doc_id="d", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Das Formular wird geprüft."),
    ])  # fmt: skip
    rules = RuleFindings(draft_version=1, level="A2", findings=[
        Finding(block_id="b001", rule_id="GRAM-01", severity="error", key="legacy",
                params={"text": "passive"}),
        Finding(block_id=None, rule_id="FACT-01", severity="error", key="legacy",
                params={"text": "x"}, fact_id="f02"),
    ])  # fmt: skip
    assert missing_count(rules) == 1
    request = build_request(draft, rules, None, fs, facts_only=True)
    assert request.problems == {} and [f.id for f in request.missing] == ["f02"]
    assert bool(request)


def test_the_summary_and_the_judge_carry_the_mode(store, endpoint, sleeps) -> None:
    from leichtfacile.schemas import SemanticFinding

    judge = {
        "fact_checks": [{"fact_id": "f01", "status": "present", "block_ids": ["b002"]}],
        "unsupported": [],
        "semantic_findings": [
            {"block_id": "b002", "rule_id": "SEM-08", "note": "Aus muss wurde kann."},
            {"block_id": "b002", "rule_id": "SEM-09", "note": "Rat"},  # not a standard rule
        ],
    }
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(judge)),
    )
    job_id = new_job(store, condition="P2", rounds=options(repair_rounds=0))
    orchestrator(store, endpoint, sleeps).run(job_id)
    report = store.get_artifact(job_id, "judge", JudgeReport, version=1)
    assert report.semantic_findings == [
        SemanticFinding(block_id="b002", rule_id="SEM-08", note="Aus muss wurde kann.")
    ]
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.mode == "standard"
    judge_prompt = endpoint.chat_bodies()[2]["messages"][0]["content"]
    assert "SEM-08" in judge_prompt and "Entscheid" not in judge_prompt


def test_the_final_version_is_the_one_with_the_fewest_missing_facts(
    store, endpoint, sleeps
) -> None:
    """A facts round adds the number; the judge then flags more of the new version than
    before. Facts come first: the version with the number is final (bucket k of the
    diagnosis, docs/prompts.md)."""
    from leichtfacile.pipeline.rounds import version_key

    no_number = {"repairs": [{"id": "b004", "texts": ["Rufen Sie das Sozial·amt an."]}],
                 "additions": []}  # fmt: skip
    judge_before = {"fact_checks": [{"fact_id": "f03", "status": "missing", "block_ids": []}]}
    judge_after = {**judge_before, "unsupported": [{"block_id": "b005", "note": "Woher?"}]}
    added = {"repairs": [], "additions": [{
        "after": "b004", "texts": ["Die Telefon·nummer ist 044 123 45 67."],
        "fact_ids": ["f03"], "segment_ids": ["s0005"],
    }]}  # fmt: skip
    noisy = {  # every fact present, but four blocks called unsupported
        "fact_checks": [{"fact_id": "f03", "status": "present", "block_ids": ["b004.1"]}],
        "unsupported": [{"block_id": b, "note": "?"} for b in ("b002", "b003", "b005", "b004.1")],
    }
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(judge_before)),
        chat_response(fx.as_json(no_number)),  # repair 1: no progress
        chat_response(fx.as_json(judge_after)),
        chat_response(fx.as_json(added)),  # facts 1
        chat_response(fx.as_json(noisy)),
    )
    job_id = new_job(store, condition="P2", rounds=options(repair_rounds=1, facts_rounds=1))
    orchestrator(store, endpoint, sleeps).run(job_id)
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.stop_reason == "no_missing_facts"
    rules = {v: store.get_artifact(job_id, "rules", RuleFindings, version=v) for v in (2, 3)}
    judges = {v: store.get_artifact(job_id, "judge", JudgeReport, version=v) for v in (2, 3)}
    assert blocking_count(rules[3], judges[3]) > blocking_count(rules[2], judges[2])
    assert version_key(rules[3], judges[3]) < version_key(rules[2], judges[2])
    assert summary.final_version == 3


def test_an_unusable_repair_answer_does_not_cancel_the_facts_round(store, endpoint, sleeps) -> None:
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.JUDGE_FIRST)),
        chat_response("kaputt"),
        chat_response("immer noch kaputt"),  # repair 1: no usable answer
        chat_response(fx.as_json({"repairs": [], "additions": [{
            "after": "b004", "texts": ["Die Telefon·nummer ist 044 123 45 67."],
            "fact_ids": ["f03"], "segment_ids": ["s0005"],
        }]})),  # facts 1 still runs: a smaller prompt, a new try
        chat_response(fx.as_json(fx.JUDGE_SECOND)),
    )  # fmt: skip
    job_id = new_job(store, condition="P2", rounds=options(repair_rounds=2))
    orchestrator(store, endpoint, sleeps).run(job_id)
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.rounds_of("repair") == 0 and summary.rounds_of("facts") == 1
    assert summary.stop_reason == "no_missing_facts" and summary.final_version == 2
    assert any(n.startswith("repair round 1 failed") for n in summary.notes)

    # When the endpoint itself failed, the drafts so far stand: no facts round.
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.JUDGE_FIRST)),
        error_response(500),
    )
    job_id = new_job(store, condition="P2", rounds=options(repair_rounds=2))
    orchestrator(store, endpoint, sleeps).run(job_id)
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.stop_reason == "round_failed" and summary.rounds_of("facts") == 0
    assert len(endpoint.queue) == 0


def test_a_dropped_part_of_a_decision_blocks_and_is_asked_for_first() -> None:
    # FACT-08 (rules/decision.py) names the part's fact; the request puts it before any
    # missing value, and it counts like a missing value in the version choice.
    from leichtfacile.pipeline.rounds import build_request, missing_count
    from leichtfacile.schemas import Block, Draft, Fact, FactSheet, Finding, RuleFindings

    fs = FactSheet(doc_id="d", facts=[
        Fact(id="f01", kind="deadline", text="Frist", value_norm="2026-03-31"),
        Fact(id="f02", kind="other", text="Die Beschwerde wird abgewiesen.", segment_ids=["s0009"],
             origin="code"),
    ])  # fmt: skip
    draft = Draft(doc_id="d", lang="de", level="A2",
                  blocks=[Block(id="b001", kind="sentence", text="Hallo.")])  # fmt: skip
    rules = RuleFindings(draft_version=1, level="A2", findings=[
        Finding(block_id=None, rule_id="FACT-01", severity="error", key="legacy",
                params={"text": "x"}, fact_id="f01"),
        Finding(block_id=None, rule_id="FACT-08", severity="error", key="legacy",
                params={"text": "y"}, fact_id="f02", segment_ids=["s0009"]),
    ])  # fmt: skip
    assert blocking_count(rules, None) == 2 and missing_count(rules) == 2
    request = build_request(draft, rules, None, fs)
    assert [f.id for f in request.missing] == ["f02", "f01"]
    assert request.problems == {}


def test_the_recover_round_asks_for_a_missing_value_with_its_paragraph(
    store, endpoint, sleeps
) -> None:
    """pipeline.recover_facts: after the facts rounds, the value still missing is asked for
    alone with its source paragraph; its sentence goes after its block as a new version,
    judged, and the final version when it has fewer values missing."""
    no_number = {"repairs": [{"id": "b004", "texts": ["Rufen Sie das Sozial·amt an."]}],
                 "additions": []}  # fmt: skip
    judge_missing = {"fact_checks": [{"fact_id": "f03", "status": "missing", "block_ids": []}]}
    judge_present = {"fact_checks": [{"fact_id": "f03", "status": "present",
                                      "block_ids": ["b004.1"]}]}  # fmt: skip
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(judge_missing)),
        chat_response(fx.as_json(no_number)),  # repair 1: the number is gone
        chat_response(fx.as_json(judge_missing)),
        chat_response(fx.as_json({"repairs": [], "additions": []})),  # facts 1: nothing
        chat_response(fx.as_json(judge_missing)),
        chat_response(fx.as_json({"after": "b004", "texts": ["Die Nummer ist 044 123 45 67."]})),
        chat_response(fx.as_json(judge_present)),
    )
    rounds = options(repair_rounds=1, facts_rounds=1, recover_facts=3)
    job_id = new_job(store, condition="P2", rounds=rounds)
    orchestrator(store, endpoint, sleeps).run(job_id)
    job = store.get_job(job_id)
    assert job.status == "needs_review", job.error
    assert len(job.usage) == 9 and [u.stage for u in job.usage][7] == "recover"
    recover_prompt = endpoint.chat_bodies()[7]["messages"][0]["content"]
    assert "Im Text fehlt dieser Wert: 044 123 45 67" in recover_prompt
    assert "Gebühr" not in recover_prompt  # another paragraph
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.final_version == 4 and summary.stop_reason == "facts_no_progress"
    final = store.get_artifact(job_id, "draft", Draft, version=4)
    added = final.by_id()["b004.1"]
    assert added.text == "Die Nummer ist 044 123 45 67." and added.fact_ids == ["f03"]
    record = store.get_artifact_json(job_id, "repair", 4)
    assert record["kind"] == "recover" and record["requested_facts"] == ["f03"]
    rules = store.get_artifact(job_id, "rules", RuleFindings, version=4)
    assert not [f for f in rules.findings if f.rule_id == "FACT-01"]


def test_without_max_recover_facts_there_is_no_recover_round(store, endpoint, sleeps) -> None:
    no_number = {"repairs": [{"id": "b004", "texts": ["Rufen Sie das Sozial·amt an."]}],
                 "additions": []}  # fmt: skip
    judge_missing = {"fact_checks": [{"fact_id": "f03", "status": "missing", "block_ids": []}]}
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(judge_missing)),
        chat_response(fx.as_json(no_number)),
        chat_response(fx.as_json(judge_missing)),
        chat_response(fx.as_json({"repairs": [], "additions": []})),
        chat_response(fx.as_json(judge_missing)),
    )
    job_id = new_job(store, condition="P2", rounds=options(repair_rounds=1, facts_rounds=1))
    orchestrator(store, endpoint, sleeps).run(job_id)
    assert len(store.get_job(job_id).usage) == 7 and not endpoint.queue
    assert "recover" not in [u.stage for u in store.get_job(job_id).usage]


# -- the polish round (pipeline.polish_rounds) -----------------------------------------

REPAIR_LONG = {
    "repairs": [
        {"id": "b002", "texts": [
            "Schicken Sie das Gesuch an die Gemeinde.",
            "Das Gesuch muss bis 31. März 2026 dort sein, sonst kann die Gemeinde das "
            "Gesuch leider nicht mehr annehmen und auch nicht mehr bearbeiten.",
        ]},
        {"id": "b004", "texts": "Rufen Sie das Sozial·amt an: 044 123 45 67."},
        {"id": "b005", "texts": ["Sie haben wenig Geld?"]},
    ],
    "additions": [],
}  # fmt: skip
POLISH = {
    "repairs": [{"id": "b002.1", "texts": ["Das Gesuch muss bis 31. März 2026 dort sein."]}],
    "additions": [],
}


def test_the_polish_round_repairs_the_rule_errors_the_loop_left(store, endpoint, sleeps) -> None:
    """pipeline.polish_rounds: after the facts and recover rounds, the best version's rule
    errors go to one more repair round, without facts and without the judge's problems;
    its version is the final one when it loses no fact and adds no blocking finding."""
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.JUDGE_FIRST)),
        chat_response(fx.as_json(REPAIR_LONG)),  # repair 1: a 21-word sentence comes in
        chat_response(fx.as_json(fx.JUDGE_SECOND)),  # no fact problem left: the loop stops
        chat_response(fx.as_json(POLISH)),  # polish 1: the sentence shortened
    )
    rounds = options(repair_rounds=1, facts_rounds=0, polish_rounds=1)
    job_id = new_job(store, condition="P2", rounds=rounds)
    orchestrator(store, endpoint, sleeps).run(job_id)
    job = store.get_job(job_id)
    assert job.status == "needs_review", job.error
    assert len(job.usage) == 6 and not endpoint.queue  # the sixth call: the polish round
    polish_prompt = endpoint.chat_bodies()[5]["messages"][0]["content"]
    assert "[b002.1]" in polish_prompt and "LEN-01" in polish_prompt
    record = store.get_artifact_json(job_id, "repair", 3)
    assert record["kind"] == "polish" and record["parent_version"] == 2
    assert record["requested_blocks"] == ["b002.1"] and record["requested_facts"] == []
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.final_version == 3 and summary.rounds_of("polish") == 1
    assert summary.rounds_of("repair") == 1 and summary.stop_reason == "max_rounds"
    before = store.get_artifact(job_id, "rules", RuleFindings, version=2)
    after = store.get_artifact(job_id, "rules", RuleFindings, version=3)
    assert [f.rule_id for f in before.findings if f.severity == "error"] == ["LEN-01"]
    assert not [f for f in after.findings if f.severity == "error"]
    final = store.get_artifact(job_id, "draft", Draft, version=3)
    assert final.by_id()["b002.1"].text == "Das Gesuch muss bis 31. März 2026 dort sein."
    assert final.by_id()["b002.1"].fact_ids == ["f01"]  # the deadline stays linked


def test_without_max_polish_rounds_there_is_no_polish_round(store, endpoint, sleeps) -> None:
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.JUDGE_FIRST)),
        chat_response(fx.as_json(REPAIR_LONG)),
        chat_response(fx.as_json(fx.JUDGE_SECOND)),
    )
    job_id = new_job(store, condition="P2", rounds=options(repair_rounds=1, facts_rounds=0))
    orchestrator(store, endpoint, sleeps).run(job_id)  # no polish round in `options()`
    job = store.get_job(job_id)
    assert job.status == "needs_review" and not endpoint.queue
    assert "polish 1" not in [u.stage for u in job.usage]
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.final_version == 2 and summary.rounds_of("polish") == 0


def test_a_job_runs_on_the_endpoint_it_picked(store, endpoint, sleeps) -> None:
    other = FakeEndpoint(models=["other-model"])
    other.push(chat_response(fx.BASELINE_TEXT))
    settings = make_settings(llm__preset="main", llm__max_retries=0)
    other_settings = make_settings(
        llm__preset="other",
        llm__url="http://other.test/v1",
        llm__models__writer="other-model",
        llm__thinking="off",
        llm__max_retries=0,
    )
    orch = Orchestrator(
        store,
        LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append),
        settings,
        clients={"other": LLMClient(other_settings, http_client=other.http_client())},
    )
    job_id = new_job(store, condition="P0", endpoint="other")
    orch.run(job_id)
    job = store.get_job(job_id)
    assert job.status == "needs_review" and endpoint.chat_bodies() == []
    assert other.chat_bodies()[0]["model"] == "other-model"
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert (summary.endpoint, summary.writer_model) == ("other", "other-model")
    assert orch.llm_for(job).models.writer == "other-model"
    # The endpoint in use, by its name or by default; one that went away fails the job.
    assert orch.client_for(store.get_job(new_job(store, endpoint="main"))) is orch.llm
    assert orch.client_for(store.get_job(new_job(store))) is orch.llm
    gone = new_job(store, condition="P0", endpoint="gone")
    orch.run(gone)
    job = store.get_job(gone)
    assert job.status == "failed" and "preset gone is not available" in job.error
    assert orch.llm_for(job) is settings.llm
