"""Observability (audit T6; logs.py, web/observability.py): a request id on every
response and every log line of the request, an access line without the query string,
the text and the JSON log formats with the ids, and `/metrics`."""

from __future__ import annotations

import io
import json
import logging
import re

import pytest
from fastapi.testclient import TestClient

from leichtfacile import logs
from leichtfacile.lifecycle import RedactingFilter
from leichtfacile.llm.client import LLMClient
from leichtfacile.store import Store
from leichtfacile.web.app import create_app
from leichtfacile.web.observability import Histogram, Metrics, render, request_id_for
from tests.conftest import MODEL, FakeEndpoint, chat_response, error_response, make_settings
from tests.pipeline import fixtures as fx
from tests.web.test_web import LETTER, run_job

HEX16 = re.compile(r"^[0-9a-f]{16}$")


@pytest.fixture
def make_app(tmp_path, endpoint: FakeEndpoint, sleeps):
    """An application with its own settings, the worker running (lifespan)."""
    made: list[tuple[TestClient, Store]] = []

    def factory(**overrides) -> tuple[TestClient, object]:
        settings = make_settings(data_dir=tmp_path, llm_max_retries=0, **overrides)
        llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
        store = Store(tmp_path / f"observability-{len(made)}.sqlite")
        app = create_app(settings, llm, store)
        client = TestClient(app)
        client.__enter__()
        made.append((client, store))
        return client, app

    yield factory
    for client, store in made:
        client.__exit__(None, None, None)
        store.close()


def _log_handler() -> logging.Handler:
    return next(h for h in logging.getLogger().handlers if h.name == logs.HANDLER_NAME)


# -- request ids and the access line ----------------------------------------------------


def test_every_response_carries_a_request_id_and_the_access_line_leaves_the_query_out(
    app_env, caplog
) -> None:
    client, _, _ = app_env
    caplog.set_level(logging.INFO, logger="leichtfacile.web.access")
    caplog.handler.addFilter(logs.ContextFilter())
    secret = "Geheimname4711"
    for path in ("/", "/api/jobs", "/healthz", "/no-such-page", "/static/app.css"):
        response = client.get(path, params={"q": secret})
        assert HEX16.match(response.headers["x-request-id"]), path
    lines = [r for r in caplog.records if r.name == "leichtfacile.web.access"]
    assert [r.status for r in lines] == [200, 200, 200, 404, 200]
    assert [r.path for r in lines][:2] == ["/", "/api/jobs"]
    assert all(r.method == "GET" and r.duration_ms >= 0 for r in lines)
    assert secret not in caplog.text, "the query string is what a reviewer typed"
    page = client.get("/")
    line = [r for r in caplog.records if r.name == "leichtfacile.web.access"][-1]
    assert line.request_id == page.headers["x-request-id"], "the line names the request"
    assert "GET / 200" in line.getMessage()


def test_a_proxys_request_id_is_kept_when_it_is_a_plain_token(app_env) -> None:
    client, _, _ = app_env
    kept = client.get("/healthz", headers={"X-Request-ID": "proxy-42.a_b"})
    assert kept.headers["x-request-id"] == "proxy-42.a_b"
    for bad in ("with space", "x" * 65, 'quote"', "nl\\n"):
        echoed = client.get("/healthz", headers={"X-Request-ID": bad}).headers["x-request-id"]
        assert echoed != bad and HEX16.match(echoed), bad
    assert request_id_for(None) != request_id_for(None)


def test_a_refusal_of_the_hardening_layer_carries_the_id_too(app_env) -> None:
    client, _, _ = app_env
    evil = {"origin": "https://evil.example"}
    refused = client.post("/api/jobs", data={"text": "x"}, headers=evil)
    assert refused.status_code == 403 and HEX16.match(refused.headers["x-request-id"])


# -- the log output ---------------------------------------------------------------------


def test_the_handler_follows_the_settings_and_is_installed_once(make_app) -> None:
    make_app(log_format="json", log_level="DEBUG")
    handler = _log_handler()
    assert isinstance(handler.formatter, logs.JsonFormatter)
    assert logging.getLogger("leichtfacile").level == logging.DEBUG
    assert any(isinstance(f, RedactingFilter) for f in handler.filters), "the privacy net"
    make_app(log_format="text", log_level="warning")
    handlers = [h for h in logging.getLogger().handlers if h.name == logs.HANDLER_NAME]
    assert len(handlers) == 1 and isinstance(handlers[0].formatter, logs.TextFormatter)
    assert logging.getLogger("leichtfacile").level == logging.WARNING


def test_json_and_text_lines_carry_the_request_and_job_ids_and_redact() -> None:
    stream = io.StringIO()
    handler = logs.configure_logging("INFO", "json", stream)
    logger = logging.getLogger("leichtfacile.tests.logs")
    request, job = logs.request_id.set("req-1"), logs.job_id.set("job-9")
    try:
        logger.info("hello %s", "world", extra={"method": "GET", "path": "/x", "status": 200})
        try:
            raise ValueError("bad [type=int, input_value='Geheim 4711', input_type=str]")
        except ValueError:
            logger.exception("failed")
    finally:
        logs.request_id.reset(request)
        logs.job_id.reset(job)
    logger.warning("outside any request")
    first, second, third = (json.loads(line) for line in stream.getvalue().splitlines())
    assert first["message"] == "hello world" and first["level"] == "INFO"
    assert first["logger"] == "leichtfacile.tests.logs" and first["time"].endswith("+00:00")
    assert (first["request_id"], first["job_id"]) == ("req-1", "job-9")
    assert (first["method"], first["path"], first["status"]) == ("GET", "/x", 200)
    assert "ValueError" in second["exception"] and "Geheim" not in second["exception"]
    assert "request_id" not in third and "job_id" not in third

    stream = io.StringIO()
    logs.configure_logging("INFO", "text", stream)
    token = logs.request_id.set("req-2")
    try:
        logger.error("boom input_value='Geheim', input_type=str")
    finally:
        logs.request_id.reset(token)
    line = stream.getvalue().strip()
    assert line == (
        "ERROR leichtfacile.tests.logs: boom input_value=<redacted>, input_type=str"
        " request_id=req-2"
    )
    logging.getLogger().removeHandler(handler)


# -- /metrics ---------------------------------------------------------------------------


def test_metrics_report_the_jobs_the_workers_the_calls_and_the_requests(app_env) -> None:
    client, app, endpoint = app_env
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    run_job(client, app, text=LETTER, condition="P1")
    endpoint.push(error_response(500))
    run_job(client, app, text=LETTER, condition="P1")  # fails: the model answers 500

    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    text = response.text
    assert 'leichtfacile_jobs{status="needs_review"} 1' in text
    assert 'leichtfacile_jobs{status="failed"} 1' in text
    assert "leichtfacile_queue_depth 0" in text
    assert "leichtfacile_workers 1" in text and "leichtfacile_workers_busy 0" in text
    assert 'leichtfacile_job_duration_seconds_count{status="needs_review"} 1' in text
    assert 'leichtfacile_job_duration_seconds_count{status="failed"} 1' in text
    assert 'leichtfacile_job_duration_seconds_bucket{status="failed",le="+Inf"} 1' in text
    thinking = MODEL + "-thinking"
    understand = f'stage="understand",model="{thinking}"'
    assert f'leichtfacile_llm_calls{{{understand},cached="false"}} 1' in text
    assert f'leichtfacile_llm_tokens{{{understand},direction="in"}} 11' in text
    assert f'leichtfacile_llm_tokens{{stage="write",model="{MODEL}",direction="out"}} 7' in text
    assert f'leichtfacile_llm_latency_seconds{{stage="write",model="{MODEL}"}}' in text
    assert 'leichtfacile_http_requests_total{method="POST",status="201"} 2' in text
    assert "leichtfacile_http_request_duration_seconds_count" in text
    assert "# TYPE leichtfacile_http_requests_total counter" in text
    assert "# TYPE leichtfacile_llm_tokens gauge" in text, "a deleted job lowers the totals"
    assert "test-key" not in text and LETTER.splitlines()[0].lstrip("# ") not in text


def test_metrics_stay_behind_the_login(make_app) -> None:
    client, _ = make_app(auth_token="s3cret")
    assert client.get("/metrics").status_code == 401
    assert client.get("/healthz").status_code == 200, "the probes stay open"
    ok = client.get("/metrics", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200 and "leichtfacile_info" in ok.text


def test_the_exposition_escapes_labels_and_renders_histograms() -> None:
    metrics = Metrics()
    metrics.observe_request("GET", 200, 0.003)
    metrics.observe_request("GET", 200, 0.3)
    metrics.observe_request("POST", 500, 12.0)
    metrics.observe_job('odd"status\\', 45.0)

    class _Store:
        def status_counts(self):
            return {"queued": 2}

        def usage_totals(self):
            row = {"stage": "write", "model": 'm"1', "cached": 1, "calls": 3}
            return [{**row, "tokens_in": 10, "tokens_out": 5, "latency_ms": 1500}]

    class _Runner:
        workers, busy = 2, 1

    text = render(_Store(), _Runner(), metrics, make_settings(job_queue_limit=7))  # type: ignore[arg-type]
    assert "leichtfacile_queue_depth 2" in text and "leichtfacile_queue_limit 7" in text
    assert "leichtfacile_workers 2\n" in text and "leichtfacile_workers_busy 1" in text
    assert 'leichtfacile_llm_calls{stage="write",model="m\\"1",cached="true"} 3' in text
    assert 'leichtfacile_llm_latency_seconds{stage="write",model="m\\"1"} 1.5' in text
    assert 'leichtfacile_job_duration_seconds_bucket{status="odd\\"status\\\\",le="30"} 0' in text
    assert 'leichtfacile_job_duration_seconds_bucket{status="odd\\"status\\\\",le="60"} 1' in text
    assert 'leichtfacile_http_requests_total{method="POST",status="500"} 1' in text
    assert 'leichtfacile_http_request_duration_seconds_bucket{le="0.005"} 1' in text
    assert 'leichtfacile_http_request_duration_seconds_bucket{le="10"} 2' in text
    assert 'leichtfacile_http_request_duration_seconds_bucket{le="+Inf"} 3' in text
    assert "leichtfacile_http_request_duration_seconds_count 3" in text
    hist = Histogram((1.0, 2.0))
    for value in (0.5, 1.0, 1.5, 9.0):
        hist.observe(value)
    assert hist.cumulative() == [(1.0, 2), (2.0, 3), (float("inf"), 4)]
    assert (hist.sum, hist.count) == (12.0, 4)
