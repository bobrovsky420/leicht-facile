"""The pages a reviewer or a judge sees: start page with examples, progress, review,
reader preview. The pipeline runs against the fake endpoint."""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from leichtfacile.llm.client import LLMClient
from leichtfacile.schemas import CoreAnswer, CoreQuestions, Fact, FactSheet
from leichtfacile.store import Store
from leichtfacile.web.app import create_app
from leichtfacile.web.jobs import Submission, create_job
from leichtfacile.web.views import format_duration, progress_view
from tests.conftest import FakeEndpoint, chat_response, make_settings
from tests.pipeline import fixtures as fx

REPO = Path(__file__).resolve().parents[2]

LETTER = """# Prämienverbilligung 2026

Personen mit geringem Einkommen haben Anspruch auf eine Prämienverbilligung.
Das Gesuch ist bis spätestens 31. März 2026 bei der Gemeinde einzureichen.

Für die Bearbeitung wird eine Gebühr von CHF 20.- erhoben.

Auskunft erteilt das Sozialamt unter Telefon 044 123 45 67.
"""


@pytest.fixture
def env(tmp_path, endpoint: FakeEndpoint, sleeps, monkeypatch):
    monkeypatch.setenv("EXAMPLES_DIR", str(REPO / "data" / "examples"))
    settings = make_settings(data_dir=tmp_path, llm_max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    store = Store(tmp_path / "ui.sqlite")
    app = create_app(settings, llm, store, load_examples_on_start=False)
    with TestClient(app) as client:
        yield client, app, store, settings, endpoint
    store.close()


def queued_job(store, settings, **options):
    """A job in the store that the worker has not picked up."""
    return create_job(store, settings, Submission(text=LETTER, **options))


def run_c1(client, app, endpoint) -> str:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    response = client.post("/api/jobs", data={"text": LETTER, "condition": "P1", "title": "Brief"})
    assert response.status_code == 201, response.text
    assert app.state.runner.wait_idle(30)
    return response.json()["id"]


def test_start_page_offers_the_examples_and_explains_the_pipeline(env) -> None:
    client, _, _, settings, _ = env
    page = client.get("/")
    assert page.status_code == 200
    assert "Try an example" in page.text
    assert "Individuelle Prämienverbilligung 2027" in page.text
    assert 'id="example-texts"' in page.text
    assert "rules from the Swiss guidelines" in page.text
    assert settings.llm_name in page.text


def test_form_passes_model_overrides_to_the_job(env) -> None:
    client, app, _, _, endpoint = env
    endpoint.push(chat_response(fx.BASELINE_TEXT))
    response = client.post(
        "/jobs",
        data={
            "text": LETTER,
            "condition": "P0",
            "writer_model": " my-writer ",
            "understand_model": " my-reader ",
            "judge_model": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    job_id = response.headers["location"].rsplit("/", 1)[-1]
    config = client.get(f"/api/jobs/{job_id}").json()["config"]
    assert config["writer_model"] == "my-writer" and config["judge_model"] is None
    assert config["understand_model"] == "my-reader"


def test_progress_page_lists_the_stages_of_a_queued_job(env) -> None:
    client, _, store, settings, _ = env
    job = queued_job(store, settings, condition="P2")
    page = client.get(f"/jobs/{job.id}")
    assert page.status_code == 200
    for title in ("Read", "Write", "Check", "Judge", "Repair", "Review"):
        assert f'step-title">{title} ' in page.text
    assert "waiting for the worker" in page.text
    assert page.text.count("step-pending") == 6

    fragment = client.get(f"/jobs/{job.id}/progress")
    assert fragment.status_code == 200
    assert fragment.headers["x-job-status"] == "queued"
    assert "<html" not in fragment.text and "step-pending" in fragment.text


def test_progress_view_follows_the_stage_and_shows_what_exists(env) -> None:
    _, _, store, settings, _ = env
    job = queued_job(store, settings, condition="P2")
    store.update_job(job.id, status="running", stage="write")
    factsheet = FactSheet(
        doc_id="x",
        core=CoreQuestions(what=CoreAnswer(text="Der Kanton zahlt.", segment_ids=["s0002"])),
        facts=[
            Fact(id="f01", kind="deadline", text="Bis 31. März 2026.", value_norm="2026-03-31"),
            Fact(id="f02", kind="other", text="Hintergrund", must_keep=False),
        ],
    )
    store.put_artifact(job.id, "factsheet", factsheet)

    view = progress_view(store, store.get_job(job.id), now=job.created_at + timedelta(seconds=90))
    states = {s.key: s.state for s in view.steps}
    assert states == {"understand": "done", "write": "running", "check": "pending",
                      "judge": "pending", "repair": "pending", "review": "pending"}  # fmt: skip
    assert "facts" in view.steps[0].detail and "must survive" in view.steps[0].detail
    assert view.current.key == "write" and view.live
    assert [c.label for c in view.core][0] == "What is it about?"
    assert 85 <= view.elapsed_s <= 100

    store.update_job(job.id, stage="repair 2")
    view = progress_view(store, store.get_job(job.id))
    repair = next(s for s in view.steps if s.key == "repair")
    assert repair.state == "running" and repair.detail == "round 2"
    assert {s.key for s in view.steps if s.state == "done"} == {"understand", "write", "check"}
    # No judge artifact in this test: the step reads as skipped, not done.
    assert next(s for s in view.steps if s.key == "judge").state == "skipped"


def test_failed_job_marks_the_failed_step_with_the_error(env) -> None:
    client, app, _, _, endpoint = env
    endpoint.push(chat_response("kein JSON"), chat_response("immer noch kein JSON"))
    response = client.post("/api/jobs", data={"text": LETTER, "condition": "P1"})
    job_id = response.json()["id"]
    assert app.state.runner.wait_idle(30)
    page = client.get(f"/jobs/{job_id}")
    assert "step-failed" in page.text and "LLMOutputError" in page.text
    assert "Run again from the start" in page.text


def test_review_page_shows_core_questions_versions_and_counts(env) -> None:
    client, app, _, _, endpoint = env
    job_id = run_c1(client, app, endpoint)
    page = client.get(f"/jobs/{job_id}")
    assert page.status_code == 200
    assert "What must you do?" in page.text
    assert "Ein Gesuch an die Gemeinde schicken." in page.text
    assert 'class="version current"' in page.text
    assert f"0 of {len(fx.WRITE['blocks'])} decided" in page.text
    assert 'data-filter="issues"' in page.text
    assert "Reader view" in page.text


def test_reader_preview_is_served_inline(env) -> None:
    client, app, _, _, endpoint = env
    job_id = run_c1(client, app, endpoint)
    preview = client.get(f"/jobs/{job_id}/preview")
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("text/html")
    assert "content-disposition" not in preview.headers
    assert '<html lang="de">' in preview.text and "Was müssen Sie tun?" in preview.text
    assert client.get("/jobs/nope/preview").status_code == 404


def test_reader_preview_of_unsaved_decisions_stores_nothing(env) -> None:
    client, app, _, _, endpoint = env
    job_id = run_c1(client, app, endpoint)
    version = int(re.search(r'data-version="(\d+)"', client.get(f"/jobs/{job_id}").text)[1])
    draft = client.get(f"/api/jobs/{job_id}/artifacts/draft", params={"version": version}).json()
    rejected, edited = draft["blocks"][2], draft["blocks"][4]
    body = {
        "draft_version": version,
        "decisions": [
            {"block_id": rejected["id"], "decision": "rejected"},
            {"block_id": edited["id"], "decision": "edited", "text": "Neu geschrieben."},
        ],
    }
    preview = client.post(f"/jobs/{job_id}/preview", json=body)
    assert preview.status_code == 200
    assert rejected["text"] not in preview.text and edited["text"] not in preview.text
    assert "Neu geschrieben." in preview.text and "noch nicht geprüft" not in preview.text
    assert client.get(f"/api/jobs/{job_id}/artifacts/review").status_code == 404

    untouched = client.post(f"/jobs/{job_id}/preview", json={"draft_version": version})
    assert "noch nicht geprüft" in untouched.text
    missing = client.post(f"/jobs/{job_id}/preview", json={"draft_version": 99})
    assert missing.status_code == 404


def test_format_duration() -> None:
    assert format_duration(4.4) == "4 s"
    assert format_duration(65) == "1 min 05 s"
    assert format_duration(3600 * 2 + 60 * 7) == "2 h 07 min"
