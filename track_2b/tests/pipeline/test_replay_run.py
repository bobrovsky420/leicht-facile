"""A recorded job replayed through the orchestrator (llm/replay.py): the first run of an
identical job needs no endpoint, a rerun asks the model again."""

from __future__ import annotations

import pytest

from leichtfacile.llm.client import LLMClient
from leichtfacile.llm.replay import Recorder, Replay
from leichtfacile.pipeline.orchestrator import Orchestrator
from leichtfacile.schemas import Draft, JobConfig
from leichtfacile.store import Store
from tests.conftest import FakeEndpoint, chat_response, make_settings
from tests.llm.test_replay import recording_of
from tests.pipeline import fixtures as fx

SETTINGS = make_settings(
    llm_judge_name="swiss-ai/Apertus-v1.5-70B",
    llm_max_retries=0,
    use_vocabulary=False,
    max_recover_facts=0,
    max_polish_rounds=0,
)
ANSWERS = (fx.UNDERSTAND, fx.WRITE, fx.JUDGE_FIRST, fx.REPAIR, fx.JUDGE_SECOND)


@pytest.fixture
def store(tmp_path) -> Store:
    s = Store(tmp_path / "test.sqlite")
    yield s
    s.close()


def new_job(store: Store) -> str:
    job = store.create_job(JobConfig(condition="P2"), title="Brief")
    store.put_artifact(job.id, "source", fx.letter())
    return job.id


@pytest.fixture
def replay(store) -> Replay:
    """The recording of a P2 job on the fake endpoint."""
    endpoint = FakeEndpoint()
    endpoint.push(*(chat_response(fx.as_json(a)) for a in ANSWERS))
    recorder = Recorder()
    llm = LLMClient(
        SETTINGS, http_client=endpoint.http_client(), cache=recorder, usage_sink=recorder.observe
    )
    job_id = new_job(store)
    Orchestrator(store, llm, SETTINGS).run(job_id)
    assert store.get_job(job_id).status == "needs_review"
    return Replay([(recording_of(recorder.answers), recorder.answers)])


def test_the_first_run_of_the_same_job_is_answered_from_the_recording(store, replay) -> None:
    endpoint = FakeEndpoint()  # no answer queued: a call would fail the job
    llm = LLMClient(SETTINGS, http_client=endpoint.http_client(), replay=replay)
    job_id = new_job(store)
    Orchestrator(store, llm, SETTINGS).run(job_id)

    job = store.get_job(job_id)
    assert job.status == "needs_review", job.error
    assert [u.stage for u in job.usage] == ["understand", "write", "judge", "repair", "judge"]
    assert all(u.cached and u.latency_ms == 0 for u in job.usage)
    assert endpoint.chat_bodies() == []
    assert replay.recording_for(store.cache_keys(job_id)).letter == "brief"
    assert store.get_artifact(job_id, "draft", Draft, version=2) is not None


def test_a_rerun_asks_the_model(store, replay) -> None:
    endpoint = FakeEndpoint()
    llm = LLMClient(SETTINGS, http_client=endpoint.http_client(), replay=replay)
    orchestrator = Orchestrator(store, llm, SETTINGS)
    job_id = new_job(store)
    orchestrator.run(job_id)

    endpoint.push(*(chat_response(fx.as_json(a)) for a in ANSWERS[1:]))
    orchestrator.rerun(job_id, "write")
    orchestrator.run(job_id)

    job = store.get_job(job_id)
    assert job.status == "needs_review", job.error
    assert len(endpoint.chat_bodies()) == 4  # write, judge, repair, judge: live
    assert [u.cached for u in job.usage[5:]] == [False] * 4
