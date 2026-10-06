"""Whole jobs through the orchestrator against the fake endpoint."""

from __future__ import annotations

import pytest

from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline.orchestrator import Orchestrator, blocking_count
from leichtfacile.schemas import (
    Draft,
    FactSheet,
    JobConfig,
    JudgeReport,
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
    settings = make_settings(llm_judge_name="swiss-ai/Apertus-v1.5-70B", llm_max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    return Orchestrator(store, llm, settings)


def new_job(store: Store, **config) -> str:
    job = store.create_job(JobConfig(**config), title="Brief")
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
    job_id = new_job(store, condition="C2")
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
    assert summary.final_version == 2 and summary.rounds == 1
    assert summary.stop_reason == "no blocking problems left"
    assert summary.prompt_versions["write"] != "none"

    # The model ran with the settings of each stage.
    bodies = endpoint.chat_bodies()
    assert bodies[0]["model"].endswith("-8B-thinking") and bodies[0]["temperature"] == 0.1
    assert bodies[2]["model"].endswith("-70B-thinking") and bodies[2]["temperature"] == 0.0
    assert not bodies[3]["model"].endswith("-thinking")  # repair runs without thinking


def test_c1_stops_after_the_rule_check(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="C1")
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
    job_id = new_job(store, condition="C0")
    orchestrator(store, endpoint, sleeps).run(job_id)
    draft = store.get_artifact(job_id, "draft", Draft)
    assert draft.origin == "baseline"
    assert [b.kind for b in draft.blocks] == [
        "heading", "sentence", "sentence", "sentence", "list_item", "list_item",
    ]  # fmt: skip
    assert all(not b.segment_ids for b in draft.blocks)
    assert endpoint.chat_bodies()[0]["messages"][0]["content"].startswith(
        "Schreiben Sie diesen Text in Leichter Sprache:"
    )


def test_failed_stage_resumes_without_repeating_earlier_stages(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), error_response(400))
    job_id = new_job(store, condition="C1")
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
    job_id = new_job(store, condition="C2")
    orchestrator(store, endpoint, sleeps).run(job_id, stop_after="write")
    job = store.get_job(job_id)
    assert job.status == "needs_review" and job.stage == "stopped after write"
    assert "rules" not in store.artifact_names(job_id)


def test_invalid_json_gets_one_repair_round(store, endpoint, sleeps) -> None:
    endpoint.push(
        chat_response("Hier ist das Faktenblatt: {kaputt"),
        chat_response(fx.as_json(fx.UNDERSTAND)),
    )
    job_id = new_job(store, condition="C2")
    orchestrator(store, endpoint, sleeps).run(job_id, stop_after="understand")
    assert store.get_artifact(job_id, "factsheet", FactSheet) is not None
    second = endpoint.chat_bodies()[1]["messages"]
    assert second[-1]["role"] == "user" and "could not be used" in second[-1]["content"]


def test_no_judge_and_no_repair_switches(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="C2", use_judge=False, max_repair_rounds=0)
    orchestrator(store, endpoint, sleeps).run(job_id)
    assert store.get_job(job_id).status == "needs_review"
    names = store.artifact_names(job_id)
    assert "judge" not in names and names["draft"] == [1]
    assert store.get_artifact(job_id, "summary", PipelineSummary).judge_model is None


def test_rerun_from_write_deletes_later_artifacts(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="C1")
    orch = orchestrator(store, endpoint, sleeps)
    orch.run(job_id)
    orch.rerun(job_id, "write")
    assert set(store.artifact_names(job_id)) == {"source", "factsheet"}
    assert store.get_job(job_id).status == "queued"


def test_repair_rounds_focus_on_blocking_problems_first() -> None:
    from leichtfacile.pipeline.orchestrator import build_request
    from leichtfacile.schemas import Block, Draft, Finding, RuleFindings

    draft = Draft(doc_id="d", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Das Formular wird geprüft."),
        Block(id="b002", kind="sentence", text="Die Prämienverbilligung hilft."),
    ])  # fmt: skip
    rules = RuleFindings(draft_version=1, level="A2", findings=[
        Finding(block_id="b001", rule_id="GRAM-01", severity="error", message="passive"),
        Finding(block_id="b002", rule_id="LEX-01", severity="warn", message="long word"),
    ])  # fmt: skip
    from leichtfacile.pipeline.models import UnderstandOut
    from leichtfacile.pipeline.stages import to_factsheet
    from tests.pipeline.fixtures import UNDERSTAND

    fs = to_factsheet(UnderstandOut.model_validate(UNDERSTAND), "d")
    focused = build_request(draft, rules, None, fs, include_warnings=False)
    assert set(focused.problems) == {"b001"}
    assert set(build_request(draft, rules, None, fs).problems) == {"b001", "b002"}


def test_missing_facts_come_in_small_batches_most_important_first() -> None:
    from leichtfacile.pipeline.orchestrator import MAX_MISSING_PER_ROUND, build_request
    from leichtfacile.schemas import Block, Draft, Fact, FactSheet, Finding, RuleFindings

    kinds = ["other", "contact", "amount", "deadline", "other", "amount", "condition", "other"]
    fs = FactSheet(doc_id="d", facts=[
        Fact(id=f"f{i:02d}", kind=k, text=f"Tatsache {i}", value_norm="2026-03-31")
        for i, k in enumerate(kinds, 1)
    ])  # fmt: skip
    draft = Draft(doc_id="d", lang="de", level="A2",
                  blocks=[Block(id="b001", kind="sentence", text="Hallo.")])  # fmt: skip
    rules = RuleFindings(draft_version=1, level="A2", findings=[
        Finding(block_id=None, rule_id="FACT-01", severity="error", message="x", fact_id=f.id)
        for f in fs.facts
    ])  # fmt: skip
    request = build_request(draft, rules, None, fs)
    assert len(request.missing) == MAX_MISSING_PER_ROUND
    assert [f.kind for f in request.missing][:3] == ["deadline", "amount", "amount"]


def test_repair_requests_skip_headings_and_speak_the_draft_language() -> None:
    from leichtfacile.pipeline.models import UnderstandOut
    from leichtfacile.pipeline.orchestrator import build_request
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
        Finding(block_id="b002", rule_id="NUM-03-FR", severity="warn", message="numeric date",
                suggestion="31 mars 2027"),
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
