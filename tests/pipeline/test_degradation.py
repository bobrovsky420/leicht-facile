"""Thinking per stage, the fallback for runaway reasoning, and jobs that survive a failing
judge or repair (lessons from the first local runs, docs/prompts.md)."""

from __future__ import annotations

import pytest

from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline.orchestrator import Orchestrator
from leichtfacile.schemas import Draft, FactSheet, JobConfig, PipelineSummary
from leichtfacile.store import Store
from tests.conftest import MODEL, chat_response, make_settings
from tests.pipeline import fixtures as fx

RUNAWAY = "<|inner_prefix|>Ich denke nach, und nach, und nach"  # cut off while reasoning


@pytest.fixture
def store(tmp_path) -> Store:
    s = Store(tmp_path / "t.sqlite")
    yield s
    s.close()


def orchestrator(store, endpoint, sleeps, **settings) -> Orchestrator:
    cfg = make_settings(llm_max_retries=0, **settings)
    llm = LLMClient(cfg, http_client=endpoint.http_client(), sleep=sleeps.append)
    return Orchestrator(store, llm, cfg)


def new_job(store: Store, **config) -> str:
    job = store.create_job(JobConfig(**config), title="Brief")
    store.put_artifact(job.id, "source", fx.letter())
    return job.id


def test_thinking_follows_the_configured_stages(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="C1")
    orchestrator(store, endpoint, sleeps, llm_thinking_stages="write").run(job_id)
    models = [b["model"] for b in endpoint.chat_bodies()]
    assert not models[0].endswith("-thinking")  # understand
    assert models[1].endswith("-thinking")  # write


BIG = "swiss-ai/Apertus-v1.5-70B"


def test_understand_can_run_on_another_model(store, endpoint, sleeps) -> None:
    """The hybrid: LLM_UNDERSTAND_NAME reads (with thinking), LLM_NAME writes."""
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="C1")
    orchestrator(store, endpoint, sleeps, llm_understand_name=BIG).run(job_id)
    assert [b["model"] for b in endpoint.chat_bodies()] == [BIG + "-thinking", MODEL]
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.writer_model == MODEL and summary.understand_model == BIG


def test_understand_follows_the_job_writer_unless_overridden(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="C1", writer_model=BIG)
    orchestrator(store, endpoint, sleeps).run(job_id)
    assert [b["model"] for b in endpoint.chat_bodies()] == [BIG + "-thinking", BIG]
    assert store.get_artifact(job_id, "summary", PipelineSummary).understand_model is None

    # The job's own understand model wins over LLM_UNDERSTAND_NAME.
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = new_job(store, condition="C1", understand_model="other-reader")
    orchestrator(store, endpoint, sleeps, llm_understand_name=BIG).run(job_id)
    assert [b["model"] for b in endpoint.chat_bodies()][2:] == ["other-reader-thinking", MODEL]
    assert store.get_artifact(job_id, "summary", PipelineSummary).understand_model == "other-reader"


def test_runaway_reasoning_falls_back_to_an_answer_without_thinking(store, endpoint, sleeps):
    endpoint.push(
        chat_response(RUNAWAY, finish_reason="length"),  # understand, thinking, cut off
        chat_response(fx.as_json(fx.UNDERSTAND)),  # at once without thinking, no repair round
        chat_response(fx.as_json(fx.WRITE)),
    )
    job_id = new_job(store, condition="C1")
    orchestrator(store, endpoint, sleeps).run(job_id)
    job = store.get_job(job_id)
    assert job.status == "needs_review", job.error
    assert store.get_artifact(job_id, "factsheet", FactSheet) is not None
    models = [b["model"] for b in endpoint.chat_bodies()]
    assert models[0].endswith("-thinking") and not models[1].endswith("-thinking")
    assert [u.stage for u in job.usage] == ["understand"] * 2 + ["write"]  # all calls billed


def test_a_failing_judge_leaves_a_reviewable_draft(store, endpoint, sleeps) -> None:
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response("kein JSON"),
        chat_response("wieder kein JSON"),  # judge: invalid twice
        chat_response(fx.as_json(fx.REPAIR)),  # the rule findings still get repaired
    )
    job_id = new_job(store, condition="C2", max_repair_rounds=1)
    orchestrator(store, endpoint, sleeps).run(job_id)
    job = store.get_job(job_id)
    assert job.status == "needs_review", job.error
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert any(n.startswith("judge on draft 1 failed") for n in summary.notes)
    assert store.versions(job_id, "draft") == [1, 2]


def test_a_failing_repair_keeps_the_drafts(store, endpoint, sleeps) -> None:
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.JUDGE_FIRST)),
        chat_response("kaputt"),
        chat_response("immer noch kaputt"),  # repair: invalid twice
    )
    job_id = new_job(store, condition="C2")
    orchestrator(store, endpoint, sleeps).run(job_id)
    job = store.get_job(job_id)
    assert job.status == "needs_review", job.error
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.stop_reason == "a repair round failed"
    assert summary.final_version == 1 and summary.rounds == 0
    assert store.get_artifact(job_id, "draft", Draft, version=1) is not None
