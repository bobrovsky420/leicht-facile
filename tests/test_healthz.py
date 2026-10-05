from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from leichtfacile.llm.client import LLMClient
from leichtfacile.web.app import create_app
from tests.conftest import MODEL, FakeEndpoint, make_settings


def _app(endpoint: FakeEndpoint):
    settings = make_settings()
    llm = LLMClient(settings, http_client=endpoint.http_client())
    return TestClient(create_app(settings, llm))


def test_healthz_reports_reachable_endpoint():
    client = _app(FakeEndpoint())
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["llm"]["reachable"] is True
    assert body["llm"]["model_listed"] is True
    assert MODEL in body["llm"]["models"]
    assert body["llm"]["base_url"] == "http://llm.test"


def test_healthz_stays_up_when_endpoint_is_down():
    endpoint = FakeEndpoint()

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    endpoint.handler = refuse  # type: ignore[method-assign]
    response = _app(endpoint).get("/healthz")
    assert response.status_code == 200
    assert response.json()["llm"]["reachable"] is False
    assert response.json()["llm"]["error"] == "APIConnectionError"


def test_healthz_flags_missing_model():
    body = _app(FakeEndpoint(models=["other-model"])).get("/healthz").json()
    assert body["llm"]["reachable"] is True
    assert body["llm"]["model_listed"] is False


def test_healthz_never_exposes_the_key():
    text = _app(FakeEndpoint()).get("/healthz").text
    assert "test-key" not in text


def test_index_page():
    response = _app(FakeEndpoint()).get("/")
    assert response.status_code == 200
    assert "Leicht·Facile" in response.text
