"""The hardening layer (web/security.py): the headers and the policy, the body limit,
the bounds on the API's inputs, the two logins and the refusal to start published
without one, the rate limits, and the cross-site guard."""

from __future__ import annotations

import base64
import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.datastructures import Headers

from leichtfacile.llm.client import LLMClient
from leichtfacile.store import Store
from leichtfacile.web.api import MAX_EDIT_CHARS
from leichtfacile.web.app import create_app
from leichtfacile.web.jobs import MAX_FILE_BYTES
from leichtfacile.web.security import (
    AUTH_FAILURES_PER_MINUTE,
    MAX_BODY_BYTES,
    RateLimit,
    client_address,
    is_cross_site,
    token_matches,
)
from tests.conftest import FakeEndpoint, chat_response, make_settings
from tests.pipeline import fixtures as fx
from tests.web.test_web import LETTER, run_job

EVIL = {"origin": "https://evil.example"}
OWN = {"origin": "http://testserver", "sec-fetch-site": "same-origin"}
PROXY = {"auth_proxy_header": "X-Forwarded-User", "auth_proxy_from": "10.0.0.0/8, 192.168.1.5"}


@pytest.fixture
def make_app(tmp_path, endpoint: FakeEndpoint, sleeps):
    """An application with its own settings and store; `client_ip` is the address the
    test client connects from. No lifespan: the worker is not needed here."""
    stores: list[Store] = []

    def factory(client_ip: str = "testclient", **overrides) -> TestClient:
        settings = make_settings(data_dir=tmp_path, llm_max_retries=0, **overrides)
        llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
        store = Store(tmp_path / f"security-{len(stores)}.sqlite")
        stores.append(store)
        app = create_app(settings, llm, store)
        return TestClient(app, client=(client_ip, 50000))

    yield factory
    for store in stores:
        store.close()


# -- 1. Headers -----------------------------------------------------------------------------


def test_every_response_carries_the_security_headers(app_env) -> None:
    client, _, _ = app_env
    page = client.get("/")
    assert page.headers["x-content-type-options"] == "nosniff"
    assert page.headers["x-frame-options"] == "SAMEORIGIN"
    assert page.headers["referrer-policy"] == "same-origin"
    assert "camera=()" in page.headers["permissions-policy"]
    policy = page.headers["content-security-policy"]
    for directive in (
        "default-src 'self'",
        "frame-ancestors 'self'",
        "object-src 'none'",
        "form-action 'self'",
        "base-uri 'self'",
    ):
        assert directive in policy, directive
    scripts = re.search(r"script-src ([^;]+)", policy).group(1)  # type: ignore[union-attr]
    assert "'unsafe-inline'" not in scripts, "scripts: this server and the nonce only"
    nonce = re.search(r"'nonce-([\w-]+)'", scripts).group(1)  # type: ignore[union-attr]
    assert f'<script nonce="{nonce}">' in page.text, "the inline script carries the nonce"
    assert client.get("/").headers["content-security-policy"] != policy, "a new nonce each time"
    for path in ("/api/jobs", "/healthz", "/static/app.css", "/no-such-page"):
        response = client.get(path)
        assert "content-security-policy" in response.headers, path
        assert response.headers["x-content-type-options"] == "nosniff", path
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "content-security-policy" not in docs.headers, "Swagger UI comes from a CDN"
    assert docs.headers["x-frame-options"] == "SAMEORIGIN"


# -- 5. Body limit (the audit's probe 7) ----------------------------------------------------


def test_a_body_over_the_limit_is_refused_before_a_byte_is_read(app_env) -> None:
    client, _, _ = app_env
    assert MAX_BODY_BYTES > MAX_FILE_BYTES, "a 15 MB file plus its form still fits"
    pulled: list[int] = []

    def body():
        pulled.append(1)
        yield b"x"

    headers = {"Content-Length": str(MAX_BODY_BYTES + 1), "Content-Type": "text/plain"}
    response = client.post("/api/jobs", content=body(), headers=headers)
    assert response.status_code == 413
    assert response.json() == {"detail": "the request body is larger than 16 MB"}
    assert pulled == [], "refused by Content-Length"
    assert "content-security-policy" in response.headers, "the headers cover refusals too"

    upload = client.post("/api/jobs", files={"file": ("big.pdf", b"%PDF-" + b"x" * MAX_BODY_BYTES)})
    assert upload.status_code == 413
    at_the_file_limit = client.post(
        "/api/jobs", files={"file": ("big.pdf", b"%PDF-" + b"x" * MAX_FILE_BYTES)}
    )
    assert at_the_file_limit.status_code == 400, "inside the body limit, the file limit speaks"
    assert "15 MB" in at_the_file_limit.json()["detail"]
    assert client.get("/api/jobs").json() == []


def test_a_chunked_body_over_the_limit_is_refused_while_it_is_read(app_env) -> None:
    client, _, _ = app_env

    def body():  # no Content-Length: the count decides
        yield b"text=" + b"x" * (MAX_BODY_BYTES // 2)
        yield b"x" * (MAX_BODY_BYTES // 2 + 1)

    response = client.post(
        "/check", content=body(), headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "the request body is larger than 16 MB"}
    assert client.get("/check").status_code == 200, "the server goes on"


def test_the_bounds_on_the_list_and_the_review(app_env) -> None:
    client, app, endpoint = app_env
    assert client.get("/api/jobs?limit=1000000000").status_code == 422  # the audit's probe 2
    assert client.get("/api/jobs?limit=0").status_code == 422
    assert client.get("/api/jobs?limit=200").status_code == 200
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    job_id = run_job(client, app, text=LETTER, condition="P1")

    def review(**decision) -> int:
        body = {"draft_version": 1, "decisions": [{"block_id": "b001", **decision}]}
        return client.post(f"/api/jobs/{job_id}/review", json=body).status_code

    assert review(decision="edited", text="x" * (MAX_EDIT_CHARS + 1)) == 422
    assert review(decision="approved", comment="x" * 2_001) == 422
    assert review(decision="edited", text="x" * MAX_EDIT_CHARS) == 200
    negative = {"draft_version": 0, "decisions": []}
    assert client.post(f"/api/jobs/{job_id}/review", json=negative).status_code == 422
    long_id = {"draft_version": 1, "decisions": [{"block_id": "b" * 17, "decision": "approved"}]}
    assert client.post(f"/api/jobs/{job_id}/review", json=long_id).status_code == 422


# -- 3. Login ----------------------------------------------------------------------------------


def test_a_shared_token_protects_everything_but_the_probes_and_static_files(make_app) -> None:
    client = make_app(auth_token="s3cret")
    for open_path in ("/healthz", "/readyz", "/static/app.css"):
        assert client.get(open_path).status_code == 200, open_path
    refused = client.get("/")
    assert refused.status_code == 401
    assert refused.headers["www-authenticate"] == 'Basic realm="Leicht-Facile", charset="UTF-8"'
    assert refused.json() == {"detail": "login required"}
    assert client.get("/api/jobs").status_code == 401
    assert client.post("/jobs", data={"text": LETTER}).status_code == 401
    assert client.get("/docs").status_code == 401

    bearer = {"Authorization": "Bearer s3cret"}
    assert client.get("/", headers=bearer).status_code == 200, "a script"
    assert client.get("/api/jobs", headers=bearer).json() == []
    assert client.get("/", auth=("reviewer", "s3cret")).status_code == 200, "a browser's answer"
    assert client.get("/", auth=("", "s3cret")).status_code == 200, "any user name"
    assert client.get("/", auth=("reviewer", "guess")).status_code == 401
    assert client.get("/", headers={"Authorization": "Bearer s3cre"}).status_code == 401


def test_repeated_wrong_tokens_are_slowed_down(make_app) -> None:
    client = make_app(auth_token="s3cret")
    wrong = {"Authorization": "Bearer nope"}
    for _ in range(AUTH_FAILURES_PER_MINUTE):
        assert client.get("/", headers=wrong).status_code == 401
    slowed = client.get("/", headers=wrong)
    assert slowed.status_code == 429
    assert slowed.json() == {"detail": "too many failed logins"}
    assert int(slowed.headers["retry-after"]) >= 1
    assert client.get("/", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_token_matches() -> None:
    def basic(text: bytes) -> str:
        return "Basic " + base64.b64encode(text).decode()

    assert token_matches("Bearer abc", "abc")
    assert token_matches("bearer  abc ", "abc")
    assert token_matches(basic(b"reviewer:abc"), "abc")
    assert token_matches(basic(b":abc"), "abc")
    assert token_matches(basic("r:pässwört".encode()), "pässwört")
    assert not token_matches(basic(b"abc"), "abc"), "no colon: that is a user name"
    assert not token_matches(basic(b"reviewer:ab"), "abc")
    assert not token_matches("Basic not*base64", "abc")
    assert not token_matches("Digest abc", "abc")
    assert not token_matches("Bearer", "abc")
    assert not token_matches(None, "abc")
    assert not token_matches("Bearer ", ""), "an empty token never matches"


def test_the_proxys_user_header_is_trusted_from_its_addresses_only(make_app) -> None:
    from_proxy = make_app(client_ip="10.0.0.2", **PROXY)
    nobody = from_proxy.get("/")
    assert nobody.status_code == 401
    assert nobody.json() == {"detail": "the reverse proxy sent no user"}
    assert from_proxy.get("/", headers={"X-Forwarded-User": "a.muster"}).status_code == 200
    assert from_proxy.get("/api/jobs", headers={"x-forwarded-user": "a.muster"}).json() == []
    assert from_proxy.get("/healthz").status_code == 200

    elsewhere = make_app(client_ip="172.16.0.9", **PROXY)
    forged = elsewhere.get("/", headers={"X-Forwarded-User": "a.muster"})
    assert forged.status_code == 403
    assert forged.json() == {"detail": "not from the trusted reverse proxy"}
    assert elsewhere.get("/healthz").status_code == 200

    named = make_app(client_ip="192.168.1.5", **PROXY)  # a single address in the list
    assert named.get("/", headers={"X-Forwarded-User": "a.muster"}).status_code == 200


def test_the_app_refuses_to_start_published_without_a_login() -> None:
    with pytest.raises(ValidationError, match="AUTH_TOKEN"):
        make_settings(bind_host="0.0.0.0")
    with pytest.raises(ValidationError, match="AUTH_TOKEN"):
        make_settings(bind_host="192.168.1.20")
    with pytest.raises(ValidationError, match="AUTH_TOKEN"):
        make_settings(bind_host="")
    with pytest.raises(ValidationError, match="not both"):
        make_settings(auth_token="x", **PROXY)
    with pytest.raises(ValidationError, match="AUTH_PROXY_FROM"):
        make_settings(auth_proxy_header="X-Forwarded-User")
    with pytest.raises(ValidationError, match="does not appear to be an IPv4 or IPv6 network"):
        make_settings(auth_proxy_header="X-Forwarded-User", auth_proxy_from="the-proxy")
    for host in ("127.0.0.1", "localhost", "::1", "[::1]", "127.0.0.2"):
        assert make_settings(bind_host=host).bound_to_loopback, host
    assert make_settings().auth_mode == "none"
    exposed = make_settings(bind_host="0.0.0.0", auth_token="s3cret")
    assert exposed.auth_mode == "token" and not exposed.bound_to_loopback
    assert make_settings(bind_host="0.0.0.0", **PROXY).auth_mode == "proxy"
    assert make_settings(auth_token="").auth_mode == "none", "an empty token is none"


# -- 2. Rate limit -------------------------------------------------------------------------


def test_rate_limit_counts_a_sliding_minute() -> None:
    now = [100.0]
    limit = RateLimit(3, clock=lambda: now[0])
    assert [limit.take("a") for _ in range(3)] == [0.0, 0.0, 0.0]
    wait = limit.take("a")
    assert 59 < wait <= 60
    assert limit.take("b") == 0.0, "another client has its own budget"
    now[0] += 30
    assert 29 < limit.take("a") <= 30
    now[0] += 30.1
    assert limit.take("a") == 0.0, "the oldest event left the window"
    assert RateLimit(0).take("a") == 0.0, "0 means no limit"


def test_writes_beyond_the_budget_are_refused(make_app) -> None:
    client = make_app(rate_limit_per_minute=3)
    for _ in range(3):
        assert client.post("/check", data={"text": "Hallo."}).status_code != 429
    refused = client.post("/check", data={"text": "Hallo."})
    assert refused.status_code == 429
    assert refused.json() == {"detail": "too many requests"}
    assert int(refused.headers["retry-after"]) >= 1
    assert client.get("/").status_code == 200, "reads are never limited"
    assert client.get("/check").status_code == 200
    unlimited = make_app(rate_limit_per_minute=0)
    for _ in range(5):
        assert unlimited.post("/check", data={"text": "Hallo."}).status_code != 429


def test_client_address_behind_the_trusted_proxy() -> None:
    direct = make_settings()
    scope = {
        "type": "http",
        "client": ("203.0.113.7", 4000),
        "headers": [(b"x-forwarded-for", b"198.51.100.1, 203.0.113.9")],
    }
    assert client_address(scope, direct) == "203.0.113.7", "no proxy: the header is not trusted"
    proxied = make_settings(auth_proxy_header="X-Forwarded-User", auth_proxy_from="203.0.113.0/24")
    assert client_address(scope, proxied) == "203.0.113.9", "the entry the proxy added"
    assert client_address({**scope, "client": ("10.0.0.1", 1)}, proxied) == "10.0.0.1"
    assert client_address({**scope, "client": None}, direct) == "unknown"


# -- 4. Cross-site request forgery -----------------------------------------------------------


@pytest.mark.parametrize(
    ("headers", "cross"),
    [
        ({"sec-fetch-site": "cross-site", "origin": "http://testserver"}, True),  # browser's word
        ({"sec-fetch-site": "same-origin"}, False),
        ({"sec-fetch-site": "same-site"}, False),
        ({"sec-fetch-site": "none"}, False),  # a typed address, a bookmark
        ({"origin": "https://evil.example", "host": "testserver"}, True),
        ({"origin": "http://testserver", "host": "testserver"}, False),
        ({"origin": "https://app.example.ch", "host": "app.example.ch"}, False),  # proxy ends TLS
        ({"origin": "http://testserver:8000", "host": "testserver"}, True),  # another port
        ({"origin": "null", "host": "testserver"}, True),
        ({"host": "testserver"}, False),  # curl, the Python client
    ],
)
def test_is_cross_site(headers, cross):
    assert is_cross_site(Headers(headers)) is cross


def _job(app_env) -> str:
    client, app, endpoint = app_env
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    return run_job(client, app, text=LETTER, condition="P1", title="Brief")


def test_a_page_on_another_site_cannot_change_anything(app_env) -> None:
    client, app, _ = app_env
    job_id = _job(app_env)
    for method, path, headers in [
        ("POST", f"/jobs/{job_id}/delete", EVIL),
        ("POST", f"/jobs/{job_id}/delete", {"sec-fetch-site": "cross-site"}),
        ("POST", f"/jobs/{job_id}/rerun", {**EVIL, "sec-fetch-site": "cross-site"}),
        ("DELETE", f"/api/jobs/{job_id}", EVIL),
        ("POST", f"/api/jobs/{job_id}/rerun?from=understand", EVIL),
        ("POST", f"/api/jobs/{job_id}/facts/f01/recover", EVIL),
        ("POST", "/api/jobs", EVIL),
        ("POST", "/jobs", {"origin": "null"}),
    ]:
        response = client.request(method, path, headers=headers, data={"text": LETTER})
        assert response.status_code == 403, (method, path, response.text)
        assert response.json() == {"detail": "cross-site request refused"}
    assert app.state.store.get_job(job_id) is not None
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "needs_review"
    assert len(client.get("/api/jobs").json()) == 1


def test_the_own_pages_scripts_and_api_clients_still_write(app_env) -> None:
    client, app, endpoint = app_env
    job_id = _job(app_env)
    assert client.get(f"/jobs/{job_id}", headers=EVIL).status_code == 200, "reads pass"

    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    response = client.post("/api/jobs", data={"text": LETTER, "condition": "P1"}, headers=OWN)
    assert response.status_code == 201, "the app's own script"
    assert app.state.runner.wait_idle(30)

    typed = {"sec-fetch-site": "none"}
    response = client.post(f"/jobs/{job_id}/delete", headers=typed, follow_redirects=False)
    assert response.status_code == 303, "a navigation the user started"
    assert app.state.store.get_job(job_id) is None

    (job,) = client.get("/api/jobs").json()  # the second job, deleted by the app's own form
    form = {"origin": "http://testserver"}  # an older browser: Origin, no Sec-Fetch-Site
    response = client.post(f"/jobs/{job['id']}/delete", headers=form, follow_redirects=False)
    assert response.status_code == 303
    assert client.get("/api/jobs").json() == []
