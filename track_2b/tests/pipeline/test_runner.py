"""The job lifecycle (audit T3): the queue in the jobs table, its limit, workers that
share one orchestrator, cancellation, the time budget, the recovery on start, and the
retention purge (T4)."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from leichtfacile.lifecycle import purge_expired, remove_job
from leichtfacile.llm.cache import ResponseCache
from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline.orchestrator import CANCELLED, JobBusy, Orchestrator
from leichtfacile.pipeline.runner import JobRunner, QueueFull
from leichtfacile.schemas import Draft, FactSheet, JobConfig, PipelineSummary
from leichtfacile.store import Store
from tests.conftest import chat_response, error_response, make_settings
from tests.pipeline import fixtures as fx


@pytest.fixture
def store(tmp_path) -> Store:
    s = Store(tmp_path / "runner.sqlite")
    yield s
    s.close()


@pytest.fixture
def runners():
    """Runners made by a test, stopped before its store closes, also when it fails."""
    made: list[JobRunner] = []

    def make(orch: Orchestrator, **kwargs) -> JobRunner:
        runner = JobRunner(orch, **kwargs)
        made.append(runner)
        return runner

    yield make
    for runner in made:
        runner.stop()


def by_stage(request: httpx.Request) -> httpx.Response:
    """An answer that fits the call, whatever the order the calls arrive in: parallel
    workers interleave them. Understand uses the thinking model, Write does not."""
    thinking = json.loads(request.content)["model"].endswith("-thinking")
    return chat_response(fx.as_json(fx.UNDERSTAND if thinking else fx.WRITE))


def orchestrator(store, endpoint, sleeps, *, clock=None, **settings) -> Orchestrator:
    settings.setdefault("use_vocabulary", False)
    settings.setdefault("max_recover_facts", 0)
    settings.setdefault("max_polish_rounds", 0)
    cfg = make_settings(llm_max_retries=0, **settings)
    llm = LLMClient(cfg, http_client=endpoint.http_client(), sleep=sleeps.append)
    kwargs = {"clock": clock} if clock else {}
    return Orchestrator(store, llm, cfg, **kwargs)


def new_job(store: Store, **config) -> str:
    job = store.create_job(JobConfig(**config), title="Brief")
    store.put_artifact(job.id, "source", fx.letter())
    return job.id


P1 = (fx.as_json(fx.UNDERSTAND), fx.as_json(fx.WRITE))


def test_workers_take_queued_jobs_from_the_table_and_wait_idle_sees_them_through(
    store, endpoint, sleeps, runners
) -> None:
    endpoint.push(*(chat_response(a) for a in P1 * 2))
    runner = runners(orchestrator(store, endpoint, sleeps), workers=1)
    first, second = new_job(store, condition="P1"), new_job(store, condition="P1")
    assert runner.submit(first) and runner.submit(second)  # queued: the rows are the queue
    runner.start()
    assert runner.wait_idle(30)
    assert {store.get_job(j).status for j in (first, second)} == {"needs_review"}
    assert store.get_job(first).counts.has_draft  # written when the pipeline ended (B3)
    assert runner.submit(first)  # idle again: may be queued once more
    assert store.get_job(first).status == "queued"


def test_the_queue_has_a_limit(store, endpoint, sleeps) -> None:
    runner = JobRunner(orchestrator(store, endpoint, sleeps), queue_limit=2)
    new_job(store), new_job(store)
    with pytest.raises(QueueFull, match="2 jobs are waiting"):
        runner.ensure_room()
    store.update_job(store.list_jobs()[0].id, status="failed")
    runner.ensure_room()


def test_a_queued_job_is_cancelled_before_it_runs(store, endpoint, sleeps) -> None:
    runner = JobRunner(orchestrator(store, endpoint, sleeps))
    job_id = new_job(store, condition="P1")
    assert runner.cancel(job_id) == "cancelled"
    job = store.get_job(job_id)
    assert job.status == "failed" and job.error == CANCELLED
    assert runner.cancel(job_id) is None  # neither queued nor running
    assert store.claim_next_queued() is None  # the worker never sees it
    assert endpoint.chat_bodies() == []


def test_a_running_job_stops_at_its_next_check_and_keeps_its_stages(
    store, endpoint, sleeps, runners
) -> None:
    """Cancel while the model writes: the call ends at the next streamed chunk or, as
    here with a plain response, right after it; the fact sheet it stored stays."""
    in_call, release = threading.Event(), threading.Event()

    def slow_understand(request: httpx.Request) -> httpx.Response:
        in_call.set()
        release.wait(10)
        return chat_response(fx.as_json(fx.UNDERSTAND))

    endpoint.push(slow_understand, chat_response(fx.as_json(fx.WRITE)))
    orch = orchestrator(store, endpoint, sleeps)
    runner = runners(orch)
    job_id = new_job(store, condition="P1")
    runner.start()
    assert in_call.wait(10)
    assert orch.running() == [job_id]
    assert runner.cancel(job_id) == "stopping"
    release.set()
    assert runner.wait_idle(30)
    job = store.get_job(job_id)
    assert job.status == "failed" and job.error == CANCELLED
    assert store.get_artifact(job_id, "factsheet", FactSheet) is not None  # kept
    assert store.get_artifact(job_id, "draft", Draft) is None  # never written
    assert len(endpoint.chat_bodies()) == 1
    assert orch.running() == []


def test_a_job_over_its_time_budget_is_stopped(store, endpoint, sleeps) -> None:
    now = [1000.0]
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    orch = orchestrator(store, endpoint, sleeps, clock=lambda: now[0], job_time_budget_s=60)
    job_id = new_job(store, condition="P1")

    def tick(request: httpx.Request) -> httpx.Response:
        now[0] += 61  # the Understand call took longer than the whole budget
        return chat_response(fx.as_json(fx.UNDERSTAND))

    endpoint.queue[0] = tick
    orch.run(job_id)
    job = store.get_job(job_id)
    assert job.status == "failed" and job.error == "stopped after the time budget of 60 s"
    assert store.get_artifact(job_id, "factsheet", FactSheet) is not None
    assert len(endpoint.chat_bodies()) == 1  # Write was never called


def test_without_a_budget_a_job_runs_as_long_as_it_takes(store, endpoint, sleeps) -> None:
    now = [0.0]
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    orch = orchestrator(store, endpoint, sleeps, clock=lambda: now[0], job_time_budget_s=0)
    job_id = new_job(store, condition="P1")
    now[0] += 1e9
    orch.run(job_id)
    assert store.get_job(job_id).status == "needs_review"


def test_a_rerun_or_a_deletion_waits_for_a_running_job(store, endpoint, sleeps, runners) -> None:
    in_call, release = threading.Event(), threading.Event()

    def hold(request: httpx.Request) -> httpx.Response:
        in_call.set()
        release.wait(10)
        return chat_response(fx.as_json(fx.UNDERSTAND))

    endpoint.push(hold, chat_response(fx.as_json(fx.WRITE)))
    orch = orchestrator(store, endpoint, sleeps)
    runner = runners(orch)
    job_id = new_job(store, condition="P1")
    runner.start()
    assert in_call.wait(10)
    with pytest.raises(JobBusy):
        orch.rerun(job_id, "understand")
    assert not remove_job(store, orch.llm, job_id)
    assert not runner.submit(job_id)
    release.set()
    assert runner.wait_idle(30)
    assert store.get_job(job_id).status == "needs_review"
    runner.stop()  # so that the requeued job is not taken before the deletion
    orch.rerun(job_id, "write")  # idle now: allowed
    assert store.get_job(job_id).status == "queued"
    assert remove_job(store, orch.llm, job_id)


def test_jobs_left_running_by_a_stopped_process_are_queued_again(store, endpoint, sleeps) -> None:
    job_id = new_job(store, condition="P1")
    store.update_job(job_id, status="running", stage="write")
    runner = JobRunner(orchestrator(store, endpoint, sleeps))
    assert runner.recover_on_start() == 1
    assert store.get_job(job_id).status == "queued"


def test_two_workers_share_one_orchestrator_without_sharing_run_state(
    store, endpoint, sleeps, runners
) -> None:
    """Per-run state (audit B2): the first job's judge fails and leaves a note; the
    second job, which has no judge, must not inherit it. Before the `RunState` the
    notes and the last round's failure lived on the orchestrator."""
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        error_response(500),  # the judge
    )
    orch = orchestrator(store, endpoint, sleeps, llm_judge_name="swiss-ai/Apertus-v1.5-70B")
    first = new_job(store, condition="P2", max_repair_rounds=0)
    orch.run(first)
    notes = store.get_artifact(first, "summary", PipelineSummary).notes
    assert notes and notes[0].startswith("judge on draft 1 failed")

    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    second = new_job(store, condition="P1")
    orch.run(second)
    assert store.get_artifact(second, "summary", PipelineSummary).notes == []

    # And two workers at once: the lock on the shared spaCy pipeline and the guarded
    # claim keep them apart; every job ends once. The answers fit the calls whatever
    # their order, since the workers interleave them.
    endpoint.push(*([by_stage] * 6))
    runner = runners(orch, workers=2)
    jobs = [new_job(store, condition="P1") for _ in range(3)]
    runner.start()
    assert runner.wait_idle(60)
    assert {store.get_job(j).status for j in jobs} == {"needs_review"}
    assert len(endpoint.chat_bodies()) == 2 + 1 + 2 + 6
    assert {t.name for t in threading.enumerate()} >= {"job-runner-1", "job-runner-2"}


def test_the_purge_deletes_old_jobs_with_their_cache_rows_and_keeps_the_examples(
    store, endpoint, sleeps, tmp_path
) -> None:
    cache = ResponseCache(tmp_path / "cache.sqlite")
    cfg = make_settings(llm_max_retries=0, use_vocabulary=False, max_recover_facts=0,
                        max_polish_rounds=0)  # fmt: skip
    llm = LLMClient(cfg, http_client=endpoint.http_client(), sleep=sleeps.append, cache=cache)
    orch = Orchestrator(store, llm, cfg)
    endpoint.push(*(chat_response(a) for a in P1 * 2))
    old = new_job(store, condition="P1")
    example = new_job(store, condition="P1")
    store.update_job(example, title="Example: Brief")
    for job_id in (old, example):
        orch.run(job_id)
    keys = store.cache_keys(old)
    assert len(keys) == 2 and all(cache.get(k) for k in keys)

    long_ago = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    with sqlite3.connect(store.path) as db:  # back-dated behind the store's back
        db.execute("UPDATE jobs SET updated_at = ?", (long_ago,))
    assert purge_expired(store, llm, 0) == []  # 0: keep everything
    assert purge_expired(store, llm, 30) == [old]
    assert store.get_job(old) is None and store.get_job(example) is not None
    assert all(cache.get(k) is None for k in keys)  # the prompts with the document are gone
    cache.close()
