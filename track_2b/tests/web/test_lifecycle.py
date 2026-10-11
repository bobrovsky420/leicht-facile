"""The job lifecycle through the web layer (audit T3 and T4): stopping a job, the
guards on a running one, the queue limit and the ingest slots, the review save that
names the review it saw, the counts on the job row, deletion with the cache rows, and
the privacy of a failed job's error."""

from __future__ import annotations

import logging
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from leichtfacile.lifecycle import RedactingFilter, redact
from leichtfacile.llm.cache import ResponseCache
from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline.orchestrator import CANCELLED
from leichtfacile.store import Store
from leichtfacile.web.app import create_app
from leichtfacile.web.views import review_view
from tests.conftest import FakeEndpoint, chat_response, make_settings
from tests.pipeline import fixtures as fx
from tests.web.test_web import LETTER, run_job

P1 = (fx.as_json(fx.UNDERSTAND), fx.as_json(fx.WRITE))


@pytest.fixture
def make_env(tmp_path, endpoint: FakeEndpoint, sleeps):
    """An application with its own settings; `cache` adds a response cache."""
    made: list[tuple[TestClient, Store]] = []

    def factory(cache: ResponseCache | None = None, **overrides):
        settings = make_settings(data_dir=tmp_path, llm_max_retries=0, **overrides)
        llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append,
                        cache=cache)  # fmt: skip
        store = Store(tmp_path / f"lifecycle-{len(made)}.sqlite")
        app = create_app(settings, llm, store, load_examples_on_start=False)
        client = TestClient(app)
        client.__enter__()
        made.append((client, store))
        return client, app, store

    yield factory
    for client, store in made:
        client.__exit__(None, None, None)
        store.close()


def held_call(endpoint: FakeEndpoint) -> tuple[threading.Event, threading.Event]:
    """The next model call waits until the test releases it; `in_call` says it began."""
    in_call, release = threading.Event(), threading.Event()

    def hold(request: httpx.Request) -> httpx.Response:
        in_call.set()
        release.wait(10)
        return chat_response(fx.as_json(fx.UNDERSTAND))

    endpoint.push(hold)
    return in_call, release


def submit(client: TestClient, **form) -> str:
    response = client.post("/api/jobs", data={"text": LETTER, "condition": "P1", **form})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_a_job_is_stopped_while_waiting_or_running_and_runs_again(make_env, endpoint) -> None:
    client, app, store = make_env()
    in_call, release = held_call(endpoint)
    running = submit(client, title="A")
    assert in_call.wait(10)
    waiting = submit(client, title="B")
    assert store.get_job(waiting).status == "queued"

    stopped = client.post(f"/api/jobs/{waiting}/cancel")
    assert stopped.status_code == 200 and stopped.json()["status"] == "cancelled"
    page = client.get(f"/jobs/{waiting}")
    assert "The job was stopped." in page.text and "Run again from the start" in page.text
    assert client.post(f"/api/jobs/{waiting}/cancel").status_code == 409  # not live any more

    # The job page offers Stop while the job is live, Delete afterwards.
    live = client.get(f"/jobs/{running}").text
    assert (
        f'action="/jobs/{running}/cancel"' in live
        and f'action="/jobs/{running}/delete"' not in live
    )
    stopping = client.post(f"/jobs/{running}/cancel", follow_redirects=False)
    assert stopping.status_code == 303
    release.set()
    assert app.state.runner.wait_idle(30)
    job = store.get_job(running)
    assert job.status == "failed" and job.error == CANCELLED
    index = client.get("/").text
    assert ">stopped</span>" in index  # the list's note, not the raw error
    done = client.get(f"/jobs/{running}").text
    assert f'action="/jobs/{running}/delete"' in done

    endpoint.push(*(chat_response(a) for a in P1))
    assert client.post(f"/api/jobs/{running}/rerun?from=understand").status_code == 200
    assert app.state.runner.wait_idle(30)
    assert store.get_job(running).status == "needs_review"


def test_a_running_job_is_neither_deleted_nor_rerun(make_env, endpoint) -> None:
    client, app, store = make_env()
    in_call, release = held_call(endpoint)
    job_id = submit(client)
    assert in_call.wait(10)
    for refused in (
        client.delete(f"/api/jobs/{job_id}"),
        client.post(f"/api/jobs/{job_id}/rerun?from=write"),
        client.post(f"/jobs/{job_id}/rerun", data={"stage": "write"}),
        client.post(f"/jobs/{job_id}/delete", follow_redirects=False),
    ):
        assert refused.status_code == 409, refused.text
        assert "stop it first" in refused.text
    assert store.get_job(job_id).status == "running"
    release.set()
    endpoint.push(chat_response(fx.as_json(fx.WRITE)))
    assert app.state.runner.wait_idle(30)
    assert client.delete(f"/api/jobs/{job_id}").status_code == 200
    assert client.delete(f"/api/jobs/{job_id}").status_code == 404


def test_the_queue_limit_and_the_ingest_slots_answer_429(make_env, endpoint) -> None:
    client, app, store = make_env(job_queue_limit=1, ingest_slots=1)
    in_call, release = held_call(endpoint)
    submit(client)  # runs, held in its first call
    assert in_call.wait(10)
    waiting = submit(client)  # waits: the queue holds its one job
    refused = client.post("/api/jobs", data={"text": LETTER})
    assert refused.status_code == 429 and refused.headers["retry-after"] == "60"
    assert "queue is full" in refused.json()["detail"]
    page = client.post("/jobs", data={"text": LETTER, "condition": "P1"})
    assert page.status_code == 429 and "The queue is full: 1 draft is waiting" in page.text
    assert store.count_jobs() == 2
    assert client.post(f"/api/jobs/{waiting}/cancel").status_code == 200  # room again

    # Every ingest slot taken: the submission is refused at once, not queued behind
    # the slow document (the thread pool keeps its threads for the other requests).
    assert app.state.ingest_slots.acquire(blocking=False)
    try:
        busy = client.post("/api/jobs", data={"text": LETTER})
        assert busy.status_code == 429 and busy.headers["retry-after"] == "5"
        assert "reading other documents" in busy.json()["detail"]
        page = client.post("/jobs", data={"text": LETTER})
        assert page.status_code == 429 and "reading other documents" in page.text
    finally:
        app.state.ingest_slots.release()
    release.set()
    endpoint.push(chat_response(fx.as_json(fx.WRITE)))
    assert app.state.runner.wait_idle(30)


def test_a_review_save_names_the_review_it_saw(app_env) -> None:
    """Optimistic concurrency (audit V14): the page sends the `saved_at` it loaded; a
    save over a review stored since is refused with 409."""
    client, app, endpoint = app_env
    endpoint.push(*(chat_response(a) for a in P1))
    job_id = run_job(client, app, text=LETTER, condition="P1")
    page = client.get(f"/jobs/{job_id}").text
    assert 'data-saved-at=""' in page  # nothing saved yet
    body = {"draft_version": 1, "decisions": [{"block_id": "b001", "decision": "approved"}]}

    first = client.post(f"/api/jobs/{job_id}/review", json={**body, "saved_at": None})
    assert first.status_code == 200
    stamp = first.json()["saved_at"]
    assert f'data-saved-at="{stamp}"' in client.get(f"/jobs/{job_id}").text

    stale = client.post(f"/api/jobs/{job_id}/review", json={**body, "saved_at": None})
    assert stale.status_code == 409 and "saved by someone else" in stale.json()["detail"]
    other = client.post(
        f"/api/jobs/{job_id}/review", json={**body, "saved_at": "2020-01-01T00:00:00+00:00"}
    )
    assert other.status_code == 409
    fresh = client.post(f"/api/jobs/{job_id}/review", json={**body, "saved_at": stamp})
    assert fresh.status_code == 200 and fresh.json()["saved_at"] != stamp
    # A script that sends no `saved_at` is not checked: the field is the page's.
    assert client.post(f"/api/jobs/{job_id}/review", json=body).status_code == 200


def test_the_drafts_list_reads_its_counts_from_the_job_row(app_env) -> None:
    """Audit B3: the counts are written when the pipeline ends and when a review is
    saved; a job from before the column gets them once, on its first listing."""
    client, app, endpoint = app_env
    endpoint.push(*(chat_response(a) for a in P1))
    job_id = run_job(client, app, text=LETTER, condition="P1")
    store = app.state.store
    job = store.get_job(job_id)
    view = review_view(store, job)
    assert job.counts.has_draft and job.counts.source_type == "text"
    assert (job.counts.errors, job.counts.warnings) == (view.counts["error"], view.counts["warn"])
    assert (job.counts.facts_present, job.counts.facts_total) == (
        view.fact_counts["present"], view.fact_counts["total"],
    )  # fmt: skip
    assert (job.counts.blocks, job.counts.decided, job.counts.complete) == (view.items, 0, False)

    decisions = [{"block_id": b, "decision": "approved"} for b in ("b001", "b002")]
    saved = client.post(
        f"/api/jobs/{job_id}/review",
        json={"draft_version": 1, "decisions": decisions, "completed": True},
    )
    assert saved.status_code == 200
    counts = store.get_job(job_id).counts
    assert (counts.decided, counts.complete) == (2, True)
    assert f"2 of {counts.blocks}, complete" in client.get("/").text

    store.update_job(job_id, counts=None)  # as a job stored before 11 October 2026
    assert store.get_job(job_id).counts is None
    page = client.get("/")
    assert f"2 of {counts.blocks}, complete" in page.text
    assert store.get_job(job_id).counts == counts  # written back once


def test_deleting_a_job_drops_its_rows_in_the_response_cache(make_env, endpoint, tmp_path) -> None:
    cache = ResponseCache(tmp_path / "cache.sqlite")
    client, app, store = make_env(cache=cache)
    endpoint.push(*(chat_response(a) for a in P1))
    job_id = submit(client)
    assert app.state.runner.wait_idle(30)
    keys = store.cache_keys(job_id)
    assert len(keys) == 2 and all(cache.get(k) is not None for k in keys)
    assert client.delete(f"/api/jobs/{job_id}").status_code == 200
    assert all(cache.get(k) is None for k in keys)
    cache.close()


def test_a_failed_job_carries_no_word_of_the_answer_in_its_error_or_the_logs(
    app_env, caplog
) -> None:
    """Audit V10: the privacy promise on the failure path. The model answers with a
    sentinel in a field of the wrong type; pydantic's `input_value` excerpt must reach
    neither the job row nor a log line above DEBUG."""
    client, app, endpoint = app_env
    sentinel = "Zebrastreifenmeldung4711"
    caplog.set_level(logging.INFO)
    caplog.handler.addFilter(RedactingFilter())
    wrong = f'{{"doc_type": "x", "audience": "y", "facts": "{sentinel}"}}'
    endpoint.push(chat_response(wrong), chat_response(wrong))
    job_id = run_job(client, app, text=LETTER, condition="P1")
    job = app.state.store.get_job(job_id)
    assert job.status == "failed" and job.error.startswith("LLMOutputError")
    assert sentinel not in job.error
    assert "facts: Input should be a valid list" in job.error
    leaked = [r for r in caplog.records if r.levelno > logging.DEBUG and sentinel in r.getMessage()]
    assert leaked == []
    assert sentinel not in caplog.text
    assert any("job %s failed" in r.msg for r in caplog.records if r.levelno == logging.ERROR)
    assert sentinel not in client.get(f"/jobs/{job_id}").text


def test_the_log_filter_redacts_input_values_in_messages_and_tracebacks() -> None:
    assert redact("x [type=int, input_value='Geheim 4711', input_type=str]") == (
        "x [type=int, input_value=<redacted>, input_type=str]"
    )
    logger = logging.getLogger("tests.redaction")
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append  # type: ignore[method-assign]
    handler.addFilter(RedactingFilter())
    logger.addHandler(handler)
    logger.propagate = False
    try:
        logger.error("bad %s", "input_value='Geheim', input_type=str")
        try:
            raise ValueError("input_value='Geheim 4711', input_type=str")
        except ValueError:
            logger.exception("failed")
    finally:
        logger.removeHandler(handler)
    assert records[0].getMessage() == "bad input_value=<redacted>, input_type=str"
    text = logging.Formatter().format(records[1])
    assert "Geheim" not in text and "ValueError: input_value=<redacted>" in text
