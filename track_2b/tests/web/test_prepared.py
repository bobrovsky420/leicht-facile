"""The prepared letters on the drafts list: one click starts a letter, and its recorded
run replays it without the endpoint (llm/replay.py, track_2b/data/examples/README.md)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from leichtfacile.examples import example_sources
from leichtfacile.llm.client import LLMClient, Usage
from leichtfacile.llm.replay import FOLDER, Replay
from leichtfacile.store import Store
from leichtfacile.web.app import create_app
from tests.conftest import FakeEndpoint, make_settings

EXAMPLES = Path(__file__).resolve().parents[2] / "data" / "examples"
LETTER = "praemienverbilligung-brief"
KESB = "entscheid-beistandschaft-musterwil"
# The settings the shipped recordings were made with: the defaults, the 70B judging.
RECORDED = {"llm_judge_name": "swiss-ai/Apertus-v1.5-70B"}


def app_env(tmp_path, endpoint: FakeEndpoint, replay: Replay | None, **settings):
    settings = make_settings(
        data_dir=tmp_path, examples_dir=EXAMPLES, llm_max_retries=0, **settings
    )
    llm = LLMClient(settings, http_client=endpoint.http_client(), replay=replay)
    store = Store(tmp_path / "web.sqlite")
    app = create_app(settings, llm, store, load_examples_on_start=False)
    return app, store


@pytest.fixture
def live(tmp_path, endpoint):
    """The app without recordings."""
    app, store = app_env(tmp_path, endpoint, None)
    with TestClient(app) as client:
        yield client, app, store
    store.close()


@pytest.fixture
def recorded(tmp_path, endpoint):
    """The app with the shipped recordings, under the settings they were made with."""
    app, store = app_env(tmp_path, endpoint, Replay.load(EXAMPLES / FOLDER), **RECORDED)
    with TestClient(app) as client:
        yield client, app, store, endpoint
    store.close()


def test_the_recorded_letters_get_a_run_button(recorded) -> None:
    """A letter is prepared once a clean run of it is recorded; the other example
    texts stay in the New draft form."""
    client, _, _, _ = recorded
    page = client.get("/").text
    assert "Try a prepared letter" in page and "No drafts yet" in page
    letters = {p.stem for p in (EXAMPLES / FOLDER).glob("*.json")}
    assert LETTER in letters
    for example in example_sources(EXAMPLES):
        run = f'action="/examples/{example["id"]}/run"' in page
        assert run is (example["id"] in letters), example["id"]
        assert (f'href="/new?example={example["id"]}"' in page) is run
    assert 'aria-label="Run: Individuelle Prämienverbilligung 2027"' in page


def test_without_recordings_the_empty_list_offers_the_example_texts(live) -> None:
    client, _, _ = live
    page = client.get("/").text
    assert "Try a prepared letter" not in page and "/examples/" not in page
    for example in example_sources(EXAMPLES):
        assert f'href="/new?example={example["id"]}"' in page


def test_a_run_button_starts_the_letter_with_its_settings(live) -> None:
    """The route takes every example text, with the settings of the file next to it."""
    client, app, store = live
    response = client.post(f"/examples/{KESB}/run", follow_redirects=False)
    assert response.status_code == 303
    job_id = response.headers["location"].removeprefix("/jobs/")
    app.state.runner.wait_idle(30)  # nothing answers: the job fails, its settings stay
    job = store.get_job(job_id)
    assert job.config.mode == "decision" and job.config.addressee == "Lea Muster"
    assert job.config.notice.endswith("Massgebend ist der Entscheid.")
    assert job.config.level == "A2" and job.config.condition == "P2"
    assert job.title.startswith("Entscheid über eine Vertretungsbeistandschaft")


def test_an_unknown_letter_is_not_found(live) -> None:
    client, _, _ = live
    assert client.post("/examples/nope/run", follow_redirects=False).status_code == 404


def _run_to_review(client, app, response) -> str:
    assert response.status_code == 303, response.text
    job_id = response.headers["location"].removeprefix("/jobs/")
    assert app.state.runner.wait_idle(60)
    return job_id


def test_a_prepared_letter_replays_its_recorded_run(recorded) -> None:
    client, app, store, endpoint = recorded
    page = client.get("/").text
    assert "were recorded on CSCS on" in page
    assert re.search(r"replays the recorded run \(\d+ (min|s)", page)

    job_id = _run_to_review(
        client, app, client.post(f"/examples/{LETTER}/run", follow_redirects=False)
    )
    job = store.get_job(job_id)
    assert job.status == "needs_review", job.error
    assert job.usage and all(u.cached for u in job.usage)
    assert endpoint.chat_bodies() == []  # no prompt went to the endpoint

    review = client.get(f"/jobs/{job_id}").text
    assert "Recorded answers" in review
    assert "replayed from the run recorded on CSCS on" in review

    # After a rerun the model answered too: the page no longer says it replayed.
    store.add_usage(job_id, Usage("judge", "swiss-ai/Apertus-v1.5-70B", 10, 10, 900))
    assert "Recorded answers" not in client.get(f"/jobs/{job_id}").text


def test_the_new_draft_form_with_an_unchanged_example_replays_too(recorded) -> None:
    """The second way: the example's text in the form (the browser sends CRLF line
    ends) and the form's defaults."""
    client, app, store, endpoint = recorded
    text = next(e["text"] for e in example_sources(EXAMPLES) if e["id"] == LETTER)
    form = {"text": text.replace("\n", "\r\n"), "lang": "auto", "level": "A2",
            "condition": "P2", "title": "", "writer_model": "", "understand_model": "",
            "judge_model": "", "mode": "standard", "addressee": "", "notice": ""}  # fmt: skip
    job_id = _run_to_review(client, app, client.post("/jobs", data=form, follow_redirects=False))
    job = store.get_job(job_id)
    assert job.status == "needs_review", job.error
    assert all(u.cached for u in job.usage) and endpoint.chat_bodies() == []


def test_under_other_settings_a_prepared_letter_runs_live(tmp_path, endpoint) -> None:
    app, store = app_env(
        tmp_path, endpoint, Replay.load(EXAMPLES / FOLDER), llm_name="swiss-ai/Apertus-v1.5-70B"
    )
    with TestClient(app) as client:
        page = client.get("/").text
    store.close()
    assert "replays the recorded run" not in page
    assert "Apertus answers live" in page and "runs live" in page
