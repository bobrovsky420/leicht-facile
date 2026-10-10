"""The cross-site guard (web/security.py): a state-changing request from a page on
another site is refused; the app's own pages, scripts and the API clients still write."""

from __future__ import annotations

import pytest
from starlette.datastructures import Headers

from leichtfacile.web.security import is_cross_site
from tests.conftest import chat_response
from tests.pipeline import fixtures as fx
from tests.web.test_web import LETTER, run_job

EVIL = {"origin": "https://evil.example"}
OWN = {"origin": "http://testserver", "sec-fetch-site": "same-origin"}


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
