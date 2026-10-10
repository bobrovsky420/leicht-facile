"""The web application end to end: submit, run, review, export; against the fake endpoint."""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from leichtfacile import ingest
from leichtfacile.examples import EXAMPLE_PREFIX, load_examples
from leichtfacile.export.bundle import build_bundle
from leichtfacile.ingest.fetch import FetchedResource
from leichtfacile.store import Store
from tests.conftest import chat_response
from tests.pipeline import fixtures as fx

LETTER = """# Prämienverbilligung 2026

Personen mit geringem Einkommen haben Anspruch auf eine Prämienverbilligung.
Das Gesuch ist bis spätestens 31. März 2026 bei der Gemeinde einzureichen.

Für die Bearbeitung wird eine Gebühr von CHF 20.- erhoben.

Auskunft erteilt das Sozialamt unter Telefon 044 123 45 67.

Rechtsgrundlage ist Art. 5 des Einführungsgesetzes.
"""


def run_job(client: TestClient, app, **form) -> str:
    response = client.post("/api/jobs", data=form)
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    assert app.state.runner.wait_idle(30)
    return job_id


def test_submit_review_and_export(app_env) -> None:
    client, app, endpoint = app_env
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = run_job(client, app, text=LETTER, condition="P1", title="Brief")

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "needs_review", job["error"]
    assert job["usage"]["calls"] == 2
    assert job["artifacts"]["draft"] == [1]

    page = client.get(f"/jobs/{job_id}")
    assert page.status_code == 200
    assert "Das kostet 20 Franken." in page.text
    assert 'data-segments="s0004"' in page.text or "data-segments=" in page.text
    assert "Facts" in page.text and "Source" in page.text

    source = client.get(f"/api/jobs/{job_id}/artifacts/source").json()
    assert source["segments"][0]["kind"] == "heading"
    assert client.get(f"/api/jobs/{job_id}/artifacts/nonsense").status_code == 404

    review = {
        "draft_version": 1,
        "decisions": [
            {"block_id": "b001", "decision": "approved"},
            {
                "block_id": "b002",
                "decision": "edited",
                "text": "Schicken Sie das Gesuch bis 31. März 2026.",
            },
            {"block_id": "b005", "decision": "rejected"},
        ],
        "completed": True,
    }
    saved = client.post(f"/api/jobs/{job_id}/review", json=review)
    assert saved.status_code == 200 and saved.json() == {"saved": 3, "completed": True}
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "done"

    md = client.get(f"/api/jobs/{job_id}/export?format=md")
    assert md.status_code == 200
    assert "attachment" in md.headers["content-disposition"]
    assert "Schicken Sie das Gesuch bis 31. März 2026." in md.text
    assert "Sie haben wenig Geld." not in md.text  # rejected
    assert "noch nicht geprüft" not in md.text  # reviewed

    html = client.get(f"/api/jobs/{job_id}/export?format=html")
    assert '<html lang="de">' in html.text and "<h2>Was müssen Sie tun?</h2>" in html.text

    bundle = json.loads(client.post(f"/api/jobs/{job_id}/export?format=json").text)
    assert bundle["format"] == "leicht-facile/audit-bundle@1"
    assert bundle["final"]["reviewed"] and bundle["final"]["review_complete"]
    assert bundle["final"]["undecided_blocks"] == 2
    assert len(bundle["final"]["blocks"]) == 4
    assert bundle["factsheet"]["facts"][0]["id"] == "f01"


def test_bad_submissions_are_rejected(app_env) -> None:
    client, _, _ = app_env
    assert client.post("/api/jobs", data={}).status_code == 400
    both = client.post("/api/jobs", data={"text": "Hallo.", "url": "https://example.org"})
    assert both.status_code == 400 and "exactly one" in both.json()["detail"]
    assert client.post("/api/jobs", data={"text": "Hallo.", "level": "C1"}).status_code == 400
    assert client.get("/api/jobs/nope").status_code == 404
    page = client.post("/jobs", data={"url": "ftp://example.org"})
    assert page.status_code == 400 and "http" in page.text


def test_review_validation(app_env) -> None:
    client, app, endpoint = app_env
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = run_job(client, app, text=LETTER, condition="P1")
    unknown = {"draft_version": 1, "decisions": [{"block_id": "b999", "decision": "approved"}]}
    assert client.post(f"/api/jobs/{job_id}/review", json=unknown).status_code == 400
    empty_edit = {"draft_version": 1, "decisions": [{"block_id": "b001", "decision": "edited"}]}
    assert client.post(f"/api/jobs/{job_id}/review", json=empty_edit).status_code == 400
    no_entry = {"draft_version": 1, "decisions": [{"block_id": "g99", "decision": "approved"}]}
    assert client.post(f"/api/jobs/{job_id}/review", json=no_entry).status_code == 400


def test_glossary_entries_are_decided_like_blocks(app_env) -> None:
    client, app, endpoint = app_env
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = run_job(client, app, text=LETTER, condition="P1")
    draft = client.get(f"/api/jobs/{job_id}/artifacts/draft").json()
    terms = [g["term"] for g in draft["glossary"]]
    assert terms[0] == "Prämien·verbilligung" and len(terms) == 2  # the model's and Gesuch

    page = client.get(f"/jobs/{job_id}").text
    assert 'data-block="g01"' in page and 'name="d-g02"' in page

    # g01 edited, g02 rejected: the export carries the edited explanation only.
    review = {
        "draft_version": 1,
        "decisions": [
            {"block_id": "g01", "decision": "edited", "text": "Der Kanton zahlt einen Teil."},
            {"block_id": "g02", "decision": "rejected"},
        ],
    }
    assert client.post(f"/api/jobs/{job_id}/review", json=review).status_code == 200
    md = client.get(f"/api/jobs/{job_id}/export?format=md").text
    assert "Der Kanton zahlt einen Teil." in md and "Der Kanton bezahlt einen Teil." not in md
    assert f"**{terms[1]}**" not in md
    html = client.get(f"/api/jobs/{job_id}/export?format=html").text
    assert "Der Kanton zahlt einen Teil." in html and f"<dt>{terms[1]}</dt>" not in html
    bundle = json.loads(client.get(f"/api/jobs/{job_id}/export?format=json").text)
    assert [g["term"] for g in bundle["final"]["glossary"]] == [terms[0]]
    assert bundle["final"]["undecided_glossary"] == 0


def test_form_submission_redirects_and_lists_the_job(app_env) -> None:
    client, app, endpoint = app_env
    endpoint.push(chat_response(fx.BASELINE_TEXT))
    response = client.post(
        "/jobs", data={"text": LETTER, "condition": "P0"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert app.state.runner.wait_idle(30)
    index = client.get("/")
    assert "Prämienverbilligung 2026" in index.text
    job_page = client.get(response.headers["location"])
    assert job_page.status_code == 200 and "Prämien·verbilligung" in job_page.text


def test_failed_job_shows_the_error_and_can_run_again(app_env) -> None:
    client, app, endpoint = app_env
    endpoint.push(chat_response("kein JSON"), chat_response("immer noch kein JSON"))
    job_id = run_job(client, app, text=LETTER, condition="P1")
    page = client.get(f"/jobs/{job_id}")
    assert "The job failed" in page.text and "LLMOutputError" in page.text
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    rerun = client.post(f"/api/jobs/{job_id}/rerun?from=understand")
    assert rerun.status_code == 200
    assert app.state.runner.wait_idle(30)
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "needs_review"


def test_example_bundles_are_imported_once(app_env, tmp_path) -> None:
    client, app, endpoint = app_env
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = run_job(client, app, text=LETTER, condition="P1", title="Brief")
    bundle = build_bundle(app.state.store, app.state.store.get_job(job_id))
    bundle["job"]["id"] = "example-brief"
    folder = tmp_path / "examples"
    (folder / "jobs").mkdir(parents=True)
    (folder / "jobs" / "brief.json").write_text(json.dumps(bundle), encoding="utf-8")

    fresh = Store(tmp_path / "fresh.sqlite")
    assert load_examples(fresh, folder) == ["example-brief"]
    assert load_examples(fresh, folder) == []  # already there
    job = fresh.get_job("example-brief")
    assert job.title.startswith(EXAMPLE_PREFIX) and job.status == "needs_review"
    assert fresh.versions("example-brief", "draft") == [1]
    assert len(job.usage) == 2
    fresh.close()


def test_document_text_never_reaches_the_logs_above_debug(app_env, caplog) -> None:
    """Privacy guard (PLAN §6): logs carry model, stage and tokens, never the text."""
    client, app, endpoint = app_env
    sentinel = "Zebrastreifenmeldung4711"
    caplog.set_level(logging.INFO)
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    run_job(client, app, text=LETTER + f"\nDie {sentinel} ist wichtig.\n", condition="P1")
    leaked = [r for r in caplog.records if r.levelno > logging.DEBUG and sentinel in r.getMessage()]
    assert leaked == []
    assert any("llm_call" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:8080/v1/models", "http://localhost/", "http://192.168.1.1/admin"]
)
def test_urls_into_the_private_network_are_refused(app_env, url) -> None:
    client, _, _ = app_env
    response = client.post("/api/jobs", data={"url": url})
    assert response.status_code == 400 and "private network" in response.json()["detail"]


def test_a_redirect_into_the_private_network_is_refused(app_env, monkeypatch) -> None:
    """A public page that answers 302 to the app, the model server or the cloud metadata
    address: every hop is checked before it is fetched (ingest/fetch.py)."""
    client, _, _ = app_env

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1:8000/api/jobs"})

    def resolve(host: str, port: int) -> list[str]:
        return [host] if host[0].isdigit() else ["93.184.216.34"]  # a public name

    http = httpx.Client(transport=httpx.MockTransport(handler))
    real = ingest.fetch_url

    def fetch(url: str, **kwargs):  # the fetcher on the mock transport and the stub resolver
        return real(url, **{**kwargs, "client": http, "resolve": resolve})

    monkeypatch.setattr(ingest, "fetch_url", fetch)
    response = client.post("/api/jobs", data={"url": "https://public.example/start"})
    assert response.status_code == 400
    assert "private network (127.0.0.1)" in response.json()["detail"]
    assert client.get("/api/jobs").json() == []


def test_a_slow_fetch_does_not_stop_other_requests(app_env, monkeypatch) -> None:
    """The audit's probe: a URL whose server trickles its body held every other request,
    `/healthz` included, because the ingest ran on the event loop. It runs in the
    thread pool now."""
    client, app, endpoint = app_env
    started, release = threading.Event(), threading.Event()

    def slow_fetch(url: str, **kwargs) -> FetchedResource:
        started.set()
        release.wait(10)
        return FetchedResource(
            content=LETTER.encode(), content_type="text/plain", final_url=url,
            fetched_at=datetime.now(UTC),
        )  # fmt: skip

    monkeypatch.setattr(ingest, "fetch_url", slow_fetch)
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    results: dict[str, httpx.Response] = {}
    submit = threading.Thread(
        target=lambda: results.update(
            job=client.post(
                "/api/jobs", data={"url": "https://public.example/slow", "condition": "P1"}
            )
        )
    )
    health = threading.Thread(target=lambda: results.update(health=client.get("/healthz")))
    submit.start()
    assert started.wait(5), "the fetch began"
    health.start()
    health.join(5)
    stuck = health.is_alive()
    release.set()
    submit.join(30)
    health.join(30)
    assert not stuck, "/healthz waited for the ingest of another request"
    assert results["health"].status_code == 200
    assert results["job"].status_code == 201, results["job"].text
    assert app.state.runner.wait_idle(30)


LETTRE = """# Taxe des chiens 2026

La taxe des chiens s'élève à CHF 120.00 par chien.
Elle doit être acquittée au plus tard le 30 avril 2026.

Renseignements : contrôle des habitants, téléphone 032 987 65 43.
"""

UNDERSTAND_FR = {
    "doc_type": "Lettre",
    "audience": "Les personnes qui ont un chien",
    "core": {
        "what": {"text": "La commune demande une taxe.", "segment_ids": ["s0002"]},
        "must_do": {"text": "Payer la taxe.", "segment_ids": ["s0003"]},
        "deadline": {"text": "Jusqu'au 30 avril 2026.", "segment_ids": ["s0003"]},
        "cost": {"text": "120 francs par chien.", "segment_ids": ["s0002"]},
        "contact": {"text": "Le contrôle des habitants.", "segment_ids": ["s0004"]},
    },
    "facts": [
        {"id": "f01", "kind": "amount", "text": "La taxe coûte 120 francs par chien.",
         "value_norm": "120", "segment_ids": ["s0002"], "must_keep": True},
        {"id": "f02", "kind": "deadline", "text": "La taxe doit être payée le 30 avril 2026.",
         "value_norm": "2026-04-30", "segment_ids": ["s0003"], "must_keep": True},
    ],
    "hard_terms": [],
    "omit_candidates": [],
}  # fmt: skip

WRITE_FR = {
    "blocks": [
        {"kind": "heading", "text": "Que devez-vous faire ?"},
        {"kind": "sentence", "text": "La taxe est de 120 francs pour chaque chien.",
         "fact_ids": ["f01"], "segment_ids": ["s0002"]},
        {"kind": "sentence", "text": "Le formulaire est contrôlé par la commune.",
         "segment_ids": ["s0003"]},
        {"kind": "sentence", "text": "Pour des questions, appelez le 032 987 65 43.",
         "segment_ids": ["s0004"]},
    ],
    "omissions": [],
    "glossary": [],
}  # fmt: skip


def test_a_french_letter_runs_through_the_french_prompts_and_rules(app_env) -> None:
    client, app, endpoint = app_env
    endpoint.push(
        chat_response(json.dumps(UNDERSTAND_FR, ensure_ascii=False)),
        chat_response(json.dumps(WRITE_FR, ensure_ascii=False)),
    )
    job_id = run_job(client, app, text=LETTRE, lang="fr", condition="P1", title="Taxe")
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "needs_review", job["error"]
    assert job["config"]["lang"] == "fr"

    prompts = [body["messages"][0]["content"] for body in endpoint.chat_bodies()]
    assert prompts[0].startswith("Vous préparez une version en FALC.")
    assert "Faits :" in prompts[1] and "au plus 15 mots" in prompts[1]

    rules = client.get(f"/api/jobs/{job_id}/artifacts/rules").json()
    found = {(f["rule_id"], f.get("fact_id")) for f in rules["findings"]}
    assert ("GRAM-01-FR", None) in found  # "est contrôlé par la commune"
    assert ("FACT-01", "f02") in found  # the deadline is missing
    missing = next(f for f in rules["findings"] if f["rule_id"] == "FACT-01")
    assert "30 avril 2026" in missing["message"]
    assert rules["metrics"]["readability_formula"] == "kandel-moles"

    md = client.get(f"/api/jobs/{job_id}/export?format=md").text
    assert "Brouillon : pas encore relu." in md


def test_a_language_without_prompts_is_refused(app_env) -> None:
    client, _, _ = app_env
    italian = {"text": "Il termine scade il 31 marzo.", "lang": "it"}
    response = client.post("/api/jobs", data=italian)
    assert response.status_code == 400
    assert "German and French" in response.json()["detail"]


def test_a_decision_job_shows_the_notice_and_exports_it_first_and_last(app_env) -> None:
    client, app, endpoint = app_env
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    notice = "Massgebend ist der Entscheid."
    job_id = run_job(client, app, text=LETTER, condition="P1", title="Entscheid", mode="decision",
                     addressee="Lea Muster", notice=notice)  # fmt: skip
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "needs_review", job["error"]
    assert job["config"]["mode"] == "decision" and job["config"]["notice"] == notice

    page = client.get(f"/jobs/{job_id}")
    assert 'class="notice-banner"' in page.text and notice in page.text

    md = client.get(f"/api/jobs/{job_id}/export?format=md").text
    paragraphs = [p.strip() for p in md.split("\n\n") if p.strip()]
    assert paragraphs[-1] == notice and notice in paragraphs[:3]
    html = client.get(f"/api/jobs/{job_id}/export?format=html").text
    assert html.count(f'<p class="notice">{notice}</p>') == 2
    reader = client.get(f"/jobs/{job_id}/preview")
    assert reader.status_code == 200 and reader.text.count(notice) == 2

    bundle = json.loads(client.post(f"/api/jobs/{job_id}/export?format=json").text)
    assert bundle["final"]["notice"] == notice
    assert bundle["final"]["layout_findings"] == []


def test_the_new_draft_page_takes_the_decision_settings_from_the_example(app_env) -> None:
    client, app, endpoint = app_env
    page = client.get("/new?example=entscheid-beistandschaft-musterwil")
    assert page.status_code == 200
    assert '<option value="decision" selected>' in page.text
    assert 'value="Lea Muster"' in page.text
    assert "Massgebend ist der Entscheid." in page.text
    plain = client.get("/new?example=praemienverbilligung-brief")
    assert (
        '<option value="standard" selected>' in plain.text
        and 'value="Lea Muster"' not in plain.text
    )
    # The notice's default per language stands ready for the script and the server.
    assert 'data-default-fr="Cette explication' in page.text


def test_the_form_fills_the_notice_default_for_a_decision_without_one(app_env) -> None:
    client, app, endpoint = app_env
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    response = client.post(
        "/jobs",
        data={"text": LETTER, "condition": "P1", "mode": "decision", "addressee": "Lea Muster",
              "notice": "  "},
        follow_redirects=False,
    )  # fmt: skip
    assert response.status_code == 303, response.text
    job_id = response.headers["location"].rsplit("/", 1)[-1]
    assert app.state.runner.wait_idle(30)
    config = client.get(f"/api/jobs/{job_id}").json()["config"]
    assert config["mode"] == "decision" and config["addressee"] == "Lea Muster"
    assert config["notice"] == (
        "Diese Erklärung hilft Ihnen, den Entscheid zu verstehen. Massgebend ist der Entscheid."
    )
    listed = client.get("/")
    assert ">Decision</span>" in listed.text


def test_a_missing_fact_gets_a_suggested_sentence_from_its_paragraph(app_env) -> None:
    client, app, endpoint = app_env
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = run_job(client, app, text=LETTER, condition="P1", title="Brief")
    # The draft has the office's number wrong (044 123 45 76): f03 is missing.
    page = client.get(f"/jobs/{job_id}").text
    assert 'data-recover="f03"' in page and 'data-recover="f01"' not in page
    endpoint.push(chat_response(fx.as_json(
        {"after": "b004", "texts": ["Rufen Sie das Sozial·amt an: 044 123 45 67."]}
    )))  # fmt: skip
    res = client.post(f"/api/jobs/{job_id}/facts/f03/recover?version=1")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["texts"] == ["Rufen Sie das Sozial·amt an: 044 123 45 67."]
    assert data["block_id"] == "b004" and data["resolved"] is True and data["rejected"] is None
    assert data["source"] == [
        {"id": "s0005", "text": "Auskunft erteilt das Sozialamt unter Telefon 044 123 45 67."}
    ]
    assert all({"rule_id", "severity", "message"} <= set(f) for f in data["findings"])
    assert client.get(f"/api/jobs/{job_id}").json()["usage"]["calls"] == 3  # billed to the job
    draft = client.get(f"/api/jobs/{job_id}/artifacts/draft").json()
    assert draft["version"] == 1  # nothing stored
    assert client.post(f"/api/jobs/{job_id}/facts/f99/recover").status_code == 404
