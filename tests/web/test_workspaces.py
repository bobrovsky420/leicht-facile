"""Workspaces (`server.workspaces`, web/workspaces.py): every browser its own drafts list
behind a link anyone may open; and the notice under the app bar (`server.notice`)."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from leichtfacile.llm.client import LLMClient
from leichtfacile.store import Store
from leichtfacile.web.app import create_app
from leichtfacile.web.jobs import Submission, create_job
from leichtfacile.web.workspaces import COOKIE, TOKEN, new_token
from tests.conftest import FakeEndpoint, make_settings

TEXT = "Das Gesuch ist bis 31. März 2026 einzureichen. Die Gebühr beträgt CHF 20.-."


@pytest.fixture
def make_app(tmp_path, endpoint: FakeEndpoint, sleeps):
    """An application with its own settings and store; a test opens as many clients on
    it as it needs browsers (each its own cookie jar). No lifespan: no worker runs, so
    a submitted job stays queued and in its workspace."""
    stores: list[Store] = []

    def factory(**overrides):
        settings = make_settings(data__dir=tmp_path, llm__max_retries=0, **overrides)
        llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
        store = Store(tmp_path / f"workspaces-{len(stores)}.sqlite")
        stores.append(store)
        return create_app(settings, llm, store), store, settings

    yield factory
    for store in stores:
        store.close()


def token_of(client: TestClient) -> str:
    """The workspace the browser was given."""
    token = client.cookies.get(COOKIE)
    assert token and TOKEN.fullmatch(token), token
    return token


def submit(client: TestClient) -> str:
    response = client.post("/api/v1/jobs", data={"text": TEXT, "title": "Gesuch"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_off_by_default_nothing_changes(make_app) -> None:
    app, _, _ = make_app()
    client = TestClient(app)
    page = client.get("/")
    assert page.status_code == 200
    assert COOKIE not in client.cookies and "data-copy-link" not in page.text
    created = client.post("/api/v1/jobs", data={"text": TEXT}).json()
    assert "workspace" not in created
    assert client.get(f"/w/{new_token()}").status_code == 404
    assert client.post("/w/new").status_code == 404


def test_each_browser_gets_a_workspace_and_sees_its_own_jobs_alone(make_app) -> None:
    app, _, _ = make_app(server__workspaces=True)
    mine = TestClient(app)
    page = mine.get("/")
    cookie = page.headers["set-cookie"]
    token = token_of(mine)
    assert cookie.startswith(f"{COOKIE}={token}; ")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    assert "Secure" not in cookie  # plain HTTP: the test client's
    assert f'href="/w/{token}"' in page.text and "data-copy-link" in page.text
    assert "set-cookie" not in mine.get("/").headers  # given once

    created = mine.post("/api/v1/jobs", data={"text": TEXT, "title": "Gesuch"})
    assert created.status_code == 201 and created.json()["workspace"] == token
    job_id = created.json()["id"]
    assert mine.get(f"/jobs/{job_id}").status_code == 200
    assert [j["id"] for j in mine.get("/api/v1/jobs").json()] == [job_id]
    assert "Gesuch" in mine.get("/").text

    other = TestClient(app)
    assert other.get("/api/v1/jobs").json() == []
    assert token_of(other) != token
    assert "Gesuch" not in other.get("/").text
    for path in (
        f"/jobs/{job_id}",
        f"/jobs/{job_id}/progress",
        f"/api/v1/jobs/{job_id}",
        f"/api/v1/jobs/{job_id}/export?format=json",
    ):
        assert other.get(path).status_code == 404, path
    assert other.delete(f"/api/v1/jobs/{job_id}").status_code == 404
    assert other.post(f"/api/v1/jobs/{job_id}/cancel").status_code == 404
    assert mine.get(f"/jobs/{job_id}").status_code == 200  # untouched

    # The page's own form puts the job into the browser's workspace too.
    posted = mine.post("/jobs", data={"text": TEXT, "title": "Formular"}, follow_redirects=False)
    assert posted.status_code == 303
    assert mine.get(posted.headers["location"]).status_code == 200
    assert other.get(posted.headers["location"]).status_code == 404


def test_the_link_opens_the_workspace_in_another_browser(make_app) -> None:
    app, _, _ = make_app(server__workspaces=True)
    mine = TestClient(app)
    job_id = submit(mine)
    token = token_of(mine)

    # A browser that has never been here: the link is its first request, and the
    # workspace the middleware would issue must not win over the link's.
    fresh = TestClient(app)
    landed = fresh.get(f"/w/{token}")
    assert landed.status_code == 200 and "Gesuch" in landed.text
    assert token_of(fresh) == token

    other = TestClient(app)
    assert other.get(f"/api/v1/jobs/{job_id}").status_code == 404
    opened = other.get(f"/w/{token}", follow_redirects=False)
    assert opened.status_code == 303 and opened.headers["location"] == "/"
    assert token_of(other) == token
    assert other.get(f"/api/v1/jobs/{job_id}").status_code == 200
    assert "Gesuch" in other.get("/").text

    assert other.get("/w/too-short").status_code == 404
    assert other.get(f"/w/{token}x").status_code == 404  # 23 characters: never a token
    assert other.get(f"/w/{token[:-1]}!").status_code == 404
    assert token_of(other) == token  # a refused link changes nothing


def test_a_new_link_moves_the_jobs_and_retires_the_old_link(make_app) -> None:
    app, store, _ = make_app(server__workspaces=True)
    mine = TestClient(app)
    job_id = submit(mine)
    old = token_of(mine)
    before = store.get_job(job_id).updated_at

    renewed = mine.post("/w/new", follow_redirects=False)
    assert renewed.status_code == 303 and renewed.headers["location"] == "/"
    new = token_of(mine)
    assert new != old and TOKEN.fullmatch(new)
    assert [j["id"] for j in mine.get("/api/v1/jobs").json()] == [job_id]  # followed along
    assert store.get_job(job_id).updated_at == before  # moved, not changed

    other = TestClient(app)
    other.get(f"/w/{old}")
    assert other.get("/api/v1/jobs").json() == []  # the old link: an empty workspace
    assert other.get(f"/api/v1/jobs/{job_id}").status_code == 404
    other.get(f"/w/{new}")
    assert [j["id"] for j in other.get("/api/v1/jobs").json()] == [job_id]


def test_a_script_names_its_workspace_in_the_header(make_app) -> None:
    app, _, _ = make_app(server__workspaces=True)
    mine = TestClient(app)
    job_id = submit(mine)
    token = token_of(mine)

    script = TestClient(app, headers={"X-Workspace": token})
    found = script.get(f"/api/v1/jobs/{job_id}")
    assert found.status_code == 200
    assert "set-cookie" not in found.headers and COOKIE not in script.cookies
    assert script.post("/api/v1/jobs", data={"text": TEXT}).json()["workspace"] == token
    assert len(script.get("/api/v1/jobs").json()) == 2

    stranger = TestClient(app, headers={"X-Workspace": new_token()})
    assert stranger.get(f"/api/v1/jobs/{job_id}").status_code == 404
    garbled = TestClient(app, headers={"X-Workspace": "not a token"})
    response = garbled.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 400 and "X-Workspace" in response.text.replace("x-w", "X-W")

    # A script without a header gets a workspace of its own, named in the answer.
    anonymous = TestClient(app)
    created = anonymous.post("/api/v1/jobs", data={"text": TEXT}).json()
    assert TOKEN.fullmatch(created["workspace"]) and created["workspace"] != token


def test_the_cookie_is_secure_over_https_and_the_access_line_hides_the_token(
    make_app, caplog
) -> None:
    app, _, _ = make_app(server__workspaces=True)
    caplog.set_level(logging.INFO, logger="leichtfacile.web.access")
    secure = TestClient(app, base_url="https://testserver")
    assert "; Secure" in secure.get("/").headers["set-cookie"]
    token = token_of(secure)
    secure.get(f"/w/{token}")
    lines = [r for r in caplog.records if r.name == "leichtfacile.web.access"]
    opened = [r for r in lines if r.path.startswith("/w/")]
    assert opened and opened[-1].path == "/w/[token]"
    assert token not in "".join(r.getMessage() for r in lines)


def test_jobs_outside_every_workspace_stay_out_while_workspaces_are_on(make_app) -> None:
    """A job the command line made, or one from before the setting was switched on, is
    in no workspace: no browser sees it, the store still lists it unscoped."""
    app, store, settings = make_app(server__workspaces=True)
    job = create_job(store, settings, Submission(text=TEXT, title="Kommandozeile"))
    client = TestClient(app)
    assert client.get(f"/jobs/{job.id}").status_code == 404
    assert "Kommandozeile" not in client.get("/").text
    assert [j.id for j in store.list_jobs()] == [job.id]


def test_the_notice_stands_under_the_app_bar_in_the_interface_language(make_app) -> None:
    app, _, _ = make_app()
    assert "site-notice" not in TestClient(app).get("/").text

    app, _, _ = make_app(server__notice="Demo: public texts only, <b>no</b> personal data")
    page = TestClient(app).get("/new").text
    assert (
        '<div class="site-notice" role="note">Demo: public texts only, &lt;b&gt;no&lt;/b&gt; '
        "personal data</div>" in page
    )

    app, _, _ = make_app(server__notice={"en": "In English", "de": "Auf Deutsch"})
    client = TestClient(app)
    assert ">In English<" in client.get("/").text
    client.get("/ui/de?next=/")
    assert ">Auf Deutsch<" in client.get("/").text
    client.get("/ui/fr?next=/")
    assert ">In English<" in client.get("/").text  # no French text: the English one

    app, _, settings = make_app(server__notice={"de": "Nur Deutsch"})
    assert settings.server.notice_for("fr") == "Nur Deutsch"  # no English either: the first
    assert ">Nur Deutsch<" in TestClient(app).get("/check").text
