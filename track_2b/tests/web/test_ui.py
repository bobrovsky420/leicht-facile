"""The pages a reviewer or a judge sees: drafts list, new draft, progress, review,
reader preview. The pipeline runs against the fake endpoint."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from leichtfacile.examples import EXAMPLE_PREFIX
from leichtfacile.llm.client import LLMClient, Usage
from leichtfacile.rules import RULES
from leichtfacile.rules.vocabulary import load_vocabulary
from leichtfacile.schemas import (
    Block,
    CoreAnswer,
    CoreQuestions,
    Decision,
    Draft,
    Fact,
    FactCheck,
    FactSheet,
    Finding,
    JudgeReport,
    ReviewState,
    RuleFindings,
)
from leichtfacile.store import Store
from leichtfacile.web.app import create_app
from leichtfacile.web.i18n import Translator
from leichtfacile.web.jobs import Submission, create_job
from leichtfacile.web.pages import READER_FONTS
from leichtfacile.web.views import format_duration, progress_view, review_view
from tests.conftest import FakeEndpoint, chat_response, make_settings
from tests.pipeline import fixtures as fx

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "src" / "leichtfacile" / "web"

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


def test_start_page_lists_the_drafts_and_starts_empty_with_the_examples(env) -> None:
    client, _, store, settings, _ = env
    page = client.get("/")
    assert page.status_code == 200
    assert "No drafts yet" in page.text
    assert 'href="/new?example=praemienverbilligung-brief"' in page.text
    assert "Individuelle Prämienverbilligung 2027" in page.text
    assert settings.llm_name in page.text  # the endpoint indicator in the app bar

    queued_job(store, settings, title="Brief")
    page = client.get("/")
    assert "No drafts yet" not in page.text and ">Brief</a>" in page.text
    assert "rules and every value" in page.text  # the intro strip
    assert 'class="badge status-queued"' in page.text and "waiting for the worker" in page.text


def _titles(client, **params) -> list[str]:
    page = client.get("/", params=params).text
    return re.findall(r'class="doc-title"><a href="/jobs/\w+"(?: lang="\w+")?>([^<]+)</a>', page)


def test_drafts_list_filters_by_status_search_and_language(env) -> None:
    client, _, store, settings, _ = env
    french = (REPO / "data" / "examples" / "sources" / "reduction-primes-lettre.txt").read_text(
        encoding="utf-8"
    )
    queued_job(store, settings, title="Brief")
    create_job(store, settings, Submission(text=french, title="Lettre"))
    example = queued_job(store, settings, title=EXAMPLE_PREFIX + "Beispiel")
    store.update_job(example.id, status="failed", error="LLMOutputError: " + "x" * 80)

    page = client.get("/").text
    assert "3 drafts." in page and '<option value="fr">' in page
    assert '>Beispiel</a><span class="tag">Example</span>' in page  # the prefix becomes a tag
    assert EXAMPLE_PREFIX + "Beispiel" not in page
    assert "LLMOutputError: " + "x" * 43 + "…" in page  # a long error is cut

    assert sorted(_titles(client)) == ["Beispiel", "Brief", "Lettre"]
    assert _titles(client, status="failed") == ["Beispiel"]
    assert _titles(client, q="BRIEF") == ["Brief"]
    assert _titles(client, lang="fr") == ["Lettre"]
    assert len(_titles(client, status="nope")) == 3  # an unknown status shows all

    failed = client.get("/", params={"status": "failed"}).text
    assert 'aria-current="true">Failed<span class="n">1</span>' in failed
    assert '>All<span class="n">3</span>' in failed and "1 of 3 drafts" in failed
    nothing = client.get("/", params={"q": "zzz"}).text
    assert "No drafts match" in nothing and ">Clear filters</a>" in nothing


def test_the_app_bar_counts_the_drafts_to_review(env) -> None:
    client, _, store, settings, _ = env
    job = queued_job(store, settings)
    assert "1 draft needs review" not in client.get("/new").text
    store.update_job(job.id, status="needs_review")
    page = client.get("/new").text
    assert "1 draft needs review" in page and '<span aria-hidden="true">1</span>' in page


def test_pages_load_nothing_from_another_host() -> None:
    """Air-gapped use (track_2b/docs/ui-design.md): stylesheets, scripts and fonts come
    from /static."""
    external = re.compile(r"""<(?:link|script|img|source)\b[^>]*\b(?:src|href)=["']?(?:\w+:)?//""")
    for path in (WEB / "templates").glob("*.html"):
        assert not external.search(path.read_text("utf-8")), path.name
    css = (WEB / "static" / "app.css").read_text("utf-8")
    assert "@import" not in css
    fonts = re.findall(r"url\(([^)]+)\)", css)
    fonts += [f.removeprefix("/static/") for f in re.findall(r"url\(([^)]+)\)", READER_FONTS)]
    assert len(fonts) == 18
    for font in fonts:
        assert (WEB / "static" / font).is_file(), font
    assert len(list((WEB / "static" / "fonts").glob("OFL-*.txt"))) == 3  # the licences


def test_new_draft_page_offers_the_examples(env) -> None:
    client, _, _, settings, _ = env
    page = client.get("/new")
    assert page.status_code == 200
    assert "Try an example" in page.text and 'id="example-texts"' in page.text
    assert "Individuelle Prämienverbilligung 2027" in page.text
    assert 'name="condition" value="P2" checked' in page.text
    assert settings.llm_name in page.text
    empty_area = 'data-max="200000"></textarea>'
    assert empty_area in page.text
    filled = client.get("/new", params={"example": "praemienverbilligung-brief"})
    assert 'data-max="200000"># Individuelle Prämienverbilligung 2027' in filled.text
    assert empty_area in client.get("/new?example=nope").text


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
        assert f'step-title">{title}<' in page.text
    assert "waiting for the worker" in page.text
    assert page.text.count("step-pending") == 6

    fragment = client.get(f"/jobs/{job.id}/progress")
    assert fragment.status_code == 200
    assert fragment.headers["x-job-status"] == "queued"
    assert "<html" not in fragment.text and "step-pending" in fragment.text


def test_progress_view_follows_the_stage_and_shows_what_exists(env) -> None:
    client, _, store, settings, _ = env
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
    store.add_usage(job.id, Usage("understand", "m", 1200, 300, 4000))

    view = progress_view(store, store.get_job(job.id), now=job.created_at + timedelta(seconds=90))
    states = {s.key: s.state for s in view.steps}
    assert states == {"understand": "done", "write": "running", "check": "pending",
                      "judge": "pending", "repair": "pending", "review": "pending"}  # fmt: skip
    assert "facts" in view.steps[0].detail and "must survive" in view.steps[0].detail
    assert view.current.key == "write" and view.live and view.current_index == 2
    assert [c.label for c in view.core][0] == "What is it about?"
    assert 85 <= view.elapsed_s <= 100
    usage = view.steps[0].usage  # each step carries its model calls
    assert (usage.calls, usage.tokens_in, usage.tokens_out) == (1, 1200, 300)
    assert view.steps[1].usage is None
    assert "1 call · 1,500 tokens · 4 s" in client.get(f"/jobs/{job.id}").text

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
    # Blocks and glossary entries are decided alike (the letter's two glossary entries).
    draft = app.state.store.get_artifact(job_id, "draft", Draft, version=1)
    assert len(draft.glossary) == 2
    assert f"0 of {len(fx.WRITE['blocks']) + 2} decided" in page.text
    assert 'data-filter="issues"' in page.text
    assert "Reader view" in page.text


def test_review_page_marks_the_glossary_entries_code_added(env) -> None:
    client, app, _, _, endpoint = env
    job_id = run_c1(client, app, endpoint)
    page = client.get(f"/jobs/{job_id}")
    assert page.status_code == 200
    gesuch = next(e.explanation for e in load_vocabulary("de") if e.term == "Gesuch")
    assert gesuch in page.text  # the letter's Gesuch: the vocabulary's entry, added by code
    assert "from the vocabulary" in page.text


def reviewable_job(store, settings):
    """A job with what the review page reads, written straight into the store: rule
    findings on blocks and on the document, facts in every state, two saved decisions."""
    job = queued_job(store, settings, condition="P2")
    blocks = [
        Block(id="b001", kind="heading", text="Prämien·verbilligung"),
        Block(id="b002", kind="sentence", text="Sie bekommen Geld für die Kranken·kasse."),
        Block(id="b003", kind="sentence", text="Schicken Sie das Gesuch bis 31. März 2026."),
        Block(id="b004", kind="sentence", text="Die Gebühr kostet 20 Franken."),
    ]
    draft = Draft(doc_id=job.id, lang="de", level="A2", blocks=blocks)
    store.put_artifact(job.id, "draft", draft, 1)

    def finding(block_id, rule_id, severity, **extra) -> Finding:
        message = f"{rule_id} message"
        return Finding(
            block_id=block_id, rule_id=rule_id, severity=severity, message=message, **extra
        )

    findings = [
        finding("b003", "LEX-01", "warn", evidence="Gesuch", suggestion="Antrag"),
        finding("b004", "LEX-01", "warn", evidence="Bearbeitungsgebühr", suggestion="Gebühr"),
        finding("b004", "LEX-02", "warn", evidence="Gebühr", suggestion="Gebühr"),
        finding(None, "LAY-03", "info"),
        finding(None, "FACT-04", "warn", segment_ids=["s0004", "s0005"]),
        finding(None, "FACT-01", "error", fact_id="f02"),
        finding(None, "FACT-01", "error", fact_id="f06"),
    ]
    store.put_artifact(
        job.id, "rules", RuleFindings(draft_version=1, level="A2", findings=findings), 1
    )
    factsheet = FactSheet(
        doc_id=job.id,
        facts=[
            Fact(id="f01", kind="deadline", text="Bis 31. März 2026.", value_norm="2026-03-31"),
            Fact(id="f02", kind="contact", text="Telefon 044 123 45 67", value_norm="0441234567"),
            Fact(id="f03", kind="other", text="Hintergrund", must_keep=False),
            Fact(id="f04", kind="right", text="Anspruch auf Verbilligung"),
            Fact(id="f05", kind="procedure", text="Gesuch bei der Gemeinde"),
            Fact(id="f06", kind="amount", text="Höchstens CHF 50.-", value_norm="50"),
        ],
    )
    store.put_artifact(job.id, "factsheet", factsheet)
    check = FactCheck(fact_id="f04", status="distorted", block_ids=["b002"], note="zu ungenau")
    store.put_artifact(
        job.id, "judge", JudgeReport(draft_version=1, model="j", fact_checks=[check]), 1
    )
    decisions = [
        Decision(block_id="b001", decision="approved", at=datetime(2026, 10, 7, 8, 0, tzinfo=UTC)),
        Decision(
            block_id="b003",
            decision="edited",
            text="Schicken Sie den Antrag bis 31. März 2026.",
            at=datetime(2026, 10, 7, 9, 30, tzinfo=UTC),
        ),
    ]
    store.put_artifact(job.id, "review", ReviewState(draft_version=1, decisions=decisions))
    return store.get_job(job.id)


def test_review_view_groups_findings_sorts_facts_and_offers_apply(env) -> None:
    client, _, store, settings, _ = env
    job = reviewable_job(store, settings)
    view = review_view(store, job)

    groups = view.finding_groups  # document findings by rule, errors first
    assert [(g.rule_id, g.worst, len(g.issues)) for g in groups] == [
        ("FACT-01", "error", 2),
        ("FACT-04", "warn", 1),
        ("LAY-03", "info", 1),
    ]
    assert groups[0].title == RULES["FACT-01"].title
    assert [i.ref for i in groups[0].issues] == ["f02", "f06"]
    assert groups[1].issues[0].ref == "s0004-s0005"
    german = review_view(store, job, t=Translator("de"))
    assert german.finding_groups[0].title == Translator("de")("rule.FACT-01") != groups[0].title

    # Problems first (missing, distorted, unchecked, present), background facts last.
    assert [f.fact.id for f in view.facts_sorted] == ["f02", "f06", "f04", "f05", "f01", "f03"]

    # Apply only where the evidence stands in the block's text and the suggestion differs.
    applicable = {
        (row.block.id, i.rule_id): i.applicable
        for row in view.rows
        for i in row.issues
        if i.source == "rule"
    }
    assert applicable == {
        ("b003", "LEX-01"): True,
        ("b004", "LEX-01"): False,
        ("b004", "LEX-02"): False,
    }
    assert view.saved_at == datetime(2026, 10, 7, 9, 30, tzinfo=UTC)

    store.update_job(job.id, status="needs_review")
    page = client.get(f"/jobs/{job.id}").text
    assert page.count("data-apply ") == 1 and 'data-evidence="Gesuch"' in page
    assert "Saved 09:30 UTC" in page and RULES["FACT-01"].title in page


def test_a_fact_the_judge_misses_but_code_finds_is_doubted(env) -> None:
    client, _, store, settings, _ = env
    job = reviewable_job(store, settings)
    # The judge finds f01 missing, but b003 holds its date: code decides on values.
    checks = [
        FactCheck(fact_id="f01", status="missing", note="Die Frist fehlt."),
        FactCheck(fact_id="f04", status="distorted", block_ids=["b002"], note="zu ungenau"),
    ]
    report = JudgeReport(draft_version=1, model="j", fact_checks=checks)
    store.put_artifact(job.id, "judge", report, 1)
    view = review_view(store, job)
    assert {f.fact.id: f.status for f in view.facts}["f01"] == "doubted"
    assert view.fact_counts["doubted"] == 1 and view.fact_counts["missing"] == 2
    # After the missing and the distorted facts, before the unchecked and present ones.
    assert [f.fact.id for f in view.facts_sorted] == ["f02", "f06", "f04", "f01", "f05", "f03"]

    store.update_job(job.id, status="needs_review")
    page = client.get(f"/jobs/{job.id}").text
    assert 'class="fact fact-doubted"' in page and "judge doubts" in page
    assert "sb-doubted" in page and "1 doubted by the judge" in page
    client.get("/ui/de")  # the switcher's cookie
    german = client.get(f"/jobs/{job.id}").text
    assert "Prüfmodell zweifelt" in german and "1 vom Prüfmodell bezweifelt" in german


def test_the_html_export_breaks_lines_its_column_can_hold_and_prints_on_a4() -> None:
    from html import unescape

    from leichtfacile.export.html import HTML_LINE_CHARS, to_html

    text = (
        "Die Sozial·versicherungs·stelle ist von Montag bis Freitag von 8.30 bis 11.30 Uhr "
        "erreichbar, und Sie können auch eine E-Mail schreiben."
    )
    draft = Draft(doc_id="d", lang="de", level="A2",
                  blocks=[Block(id="b001", kind="sentence", text=text)])  # fmt: skip
    page = to_html(draft)
    paragraph = re.search(r"<p>(.*?)</p>", page, re.S).group(1)
    lines = [unescape(line.strip()) for line in paragraph.split("<br>")]
    assert len(lines) > 1 and all(len(line) <= HTML_LINE_CHARS for line in lines)
    assert " ".join(lines) == text
    assert "max-width: 36em" in page  # wide enough for a line of HTML_LINE_CHARS
    assert "@page { size: A4" in page and "@media print" in page

    # A value never breaks across lines (here the break fell inside the phone number).
    call = "Für Fragen rufen Sie die Sozial·versicherungs·stelle an: 044 123 45 67 oder mailen."
    draft = draft.model_copy(update={"blocks": [Block(id="b001", kind="sentence", text=call)]})
    paragraph = re.search(r"<p>(.*?)</p>", to_html(draft), re.S).group(1)
    assert any("044 123 45 67" in line for line in paragraph.split("<br>"))


def test_the_reader_view_offers_print(env) -> None:
    client, app, _, _, endpoint = env
    job_id = run_c1(client, app, endpoint)
    page = client.get(f"/jobs/{job_id}").text
    assert 'id="reader-print"' in page and "Print or save as PDF" in page
    assert 'sandbox="allow-same-origin allow-modals"' in page  # print() needs modals


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
