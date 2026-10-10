"""The probes (web/health.py): liveness from the process alone, readiness with the
cached check of the model endpoint, booleans and names in the answer, never the
endpoint's catalogue."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from leichtfacile.llm.client import LLMClient
from leichtfacile.web.app import create_app
from leichtfacile.web.health import EndpointCheck
from tests.conftest import MODEL, FakeEndpoint, make_settings


def _app(endpoint: FakeEndpoint):
    settings = make_settings()
    llm = LLMClient(settings, http_client=endpoint.http_client())
    return TestClient(create_app(settings, llm))


def _model_requests(endpoint: FakeEndpoint) -> int:
    return sum(1 for r in endpoint.requests if r.url.path.endswith("/models"))


def _refusing() -> FakeEndpoint:
    endpoint = FakeEndpoint()

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    endpoint.handler = refuse  # type: ignore[method-assign]
    return endpoint


def test_healthz_is_liveness_alone():
    endpoint = FakeEndpoint()
    response = _app(endpoint).get("/healthz")
    assert response.status_code == 200
    assert set(response.json()) == {"status", "version"}
    assert response.json()["status"] == "ok"
    assert endpoint.requests == [], "no call left the server"
    assert _app(_refusing()).get("/healthz").status_code == 200


def test_readyz_reports_the_endpoint_without_its_catalogue():
    endpoint = FakeEndpoint()
    body = _app(endpoint).get("/readyz").json()
    assert body["status"] == "ok"
    assert body["llm"]["reachable"] is True
    assert body["llm"]["model_listed"] is True
    assert body["llm"]["model"] == MODEL
    assert body["llm"]["base_url"] == "http://llm.test"
    assert body["llm"]["checked_at"]
    assert "models" not in body["llm"], "the endpoint's model list stays inside"
    assert _model_requests(endpoint) == 1


def test_readyz_stays_up_when_endpoint_is_down():
    response = _app(_refusing()).get("/readyz")
    assert response.status_code == 200, "the pages, the exports and the checker still work"
    body = response.json()
    assert body["status"] == "degraded"
    assert body["llm"]["reachable"] is False
    assert body["llm"]["error"] == "APIConnectionError"
    assert "model_listed" not in body["llm"]


def test_readyz_names_the_judge_the_endpoint_decides():
    big = "swiss-ai/Apertus-v1.5-70B"
    body = _app(FakeEndpoint(models=[MODEL, big])).get("/readyz").json()
    assert body["llm"]["judge_model"] == big and body["llm"]["judge_model_listed"] is True
    body = _app(FakeEndpoint()).get("/readyz").json()  # no 70B: the writer judges
    assert body["llm"]["judge_model"] == MODEL


def test_readyz_flags_missing_model():
    body = _app(FakeEndpoint(models=["other-model"])).get("/readyz").json()
    assert body["status"] == "degraded"
    assert body["llm"]["reachable"] is True
    assert body["llm"]["model_listed"] is False


def test_readyz_asks_the_endpoint_at_most_once_per_interval():
    endpoint = FakeEndpoint()
    client = _app(endpoint)
    now = [1000.0]
    client.app.state.endpoint_check = EndpointCheck(
        client.app.state.llm, ttl_s=30, clock=lambda: now[0]
    )
    for _ in range(5):
        assert client.get("/readyz").json()["llm"]["reachable"] is True
    assert _model_requests(endpoint) == 1, "whoever asks, however often"
    now[0] += 29.9
    client.get("/readyz")
    assert _model_requests(endpoint) == 1
    now[0] += 0.1
    client.get("/readyz")
    assert _model_requests(endpoint) == 2, "a fresh check once the interval is over"


def test_readyz_notices_the_endpoint_coming_back():
    endpoint = FakeEndpoint()
    down = [True]
    answer = endpoint.handler

    def handler(request: httpx.Request) -> httpx.Response:
        if down[0]:
            raise httpx.ConnectError("refused")
        return answer(request)

    endpoint.handler = handler  # type: ignore[method-assign]
    client = _app(endpoint)
    now = [0.0]
    client.app.state.endpoint_check = EndpointCheck(
        client.app.state.llm, ttl_s=30, clock=lambda: now[0]
    )
    assert client.get("/readyz").json()["llm"]["reachable"] is False
    down[0] = False
    assert client.get("/readyz").json()["llm"]["reachable"] is False, "cached"
    now[0] = 30.0
    assert client.get("/readyz").json()["llm"]["reachable"] is True


def test_probes_never_expose_the_key():
    client = _app(FakeEndpoint())
    for path in ("/healthz", "/readyz"):
        assert "test-key" not in client.get(path).text


def test_index_page():
    response = _app(FakeEndpoint()).get("/")
    assert response.status_code == 200
    assert "Leicht·Facile" in response.text
