"""The job page says when a draft's answers came from a recorded run of a sample letter
(llm/replay.py), and only then."""

from __future__ import annotations

from fastapi.testclient import TestClient

from leichtfacile.llm.client import LLMClient, Usage
from leichtfacile.llm.replay import Replay
from leichtfacile.schemas import JobConfig
from leichtfacile.store import Store
from leichtfacile.web.app import create_app
from tests.conftest import make_settings
from tests.llm.test_replay import recording_of

ANSWER = {
    "key": "k-recorded", "stage": "understand", "model": "m", "latency_ms": 900,
    "tokens_in": 10, "tokens_out": 5, "finish_reason": "stop", "text": "{}",
}  # fmt: skip


def page(tmp_path, endpoint, keys: list[str]) -> str:
    """The job page of a failed job whose calls had these cache keys."""
    settings = make_settings(data__dir=tmp_path, llm__max_retries=0)
    store = Store(tmp_path / "web.sqlite")
    job = store.create_job(JobConfig(), title="Brief")
    for key in keys:
        store.add_usage(job.id, Usage("understand", "m", 10, 5, 0, cached=True, cache_key=key))
    store.update_job(job.id, status="failed", error="stopped")
    llm = LLMClient(settings, http_client=endpoint.http_client())
    replay = Replay([(recording_of([ANSWER]), [ANSWER])])
    try:
        with TestClient(create_app(settings, llm, store, replay=replay)) as client:
            return client.get(f"/jobs/{job.id}").text
    finally:
        store.close()


def test_a_replayed_job_says_its_answers_were_recorded(tmp_path, endpoint) -> None:
    text = page(tmp_path, endpoint, ["k-recorded"])
    assert "come from a run recorded on 08.11.2026 with test, which took 42 s of model" in text


def test_a_live_job_says_nothing_of_a_recording(tmp_path, endpoint) -> None:
    assert "recorded on" not in page(tmp_path, endpoint, ["k-live"])
