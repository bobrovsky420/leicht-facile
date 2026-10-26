"""The model page (web/model.py) and the app without a ready preset: the app starts and
says so, the page lists the presets by group with their status, takes a key, checks it,
makes a test call, offers a local server's models and saves a preset of the user's own;
a published server and an overriding source lock the choice."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from leichtfacile import config, configure
from leichtfacile.llm.client import LLMClient
from leichtfacile.llm.registry import Registry
from leichtfacile.store import Store
from leichtfacile.web.app import create_app
from tests.conftest import FakeEndpoint, sse_response
from tests.web.test_web import LETTER


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    """A writable config file of its own, no keys in the shell, the app's data in
    tmp_path."""
    path = tmp_path / "home" / "config.toml"
    monkeypatch.setenv("LEICHTFACILE_CONFIG", str(path))
    monkeypatch.setenv("LEICHTFACILE_DATA__DIR", str(tmp_path / "data"))
    return path


@pytest.fixture
def fake() -> FakeEndpoint:
    return FakeEndpoint(models=["swiss-ai/apertus-v1.5-8b", "swiss-ai/apertus-v1.5-70b"])


@pytest.fixture
def app(home, fake):
    """The app on the settings as they are (no client given): the registry makes the
    clients, on the fake endpoint instead of the providers' addresses."""
    store = Store(home.parent / "model.sqlite")
    app = create_app(store=store)
    app.state.registry.make_client = lambda settings, cache: LLMClient(
        settings, http_client=fake.http_client()
    )
    with TestClient(app) as client:
        yield client, app
    store.close()


def toml(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_the_app_starts_without_a_ready_preset_and_says_so(app) -> None:
    client, app = app
    assert app.state.settings.llm.preset == "cscs-apertus" and app.state.registry.llm is None
    page = client.get("/")
    assert page.status_code == 200 and "No AI model is ready yet" in page.text
    assert 'href="/model"' in page.text
    form = client.get("/new").text
    assert "No AI model is ready yet" in form and "Choose one on the AI model page" in form
    refused = client.post("/jobs", data={"text": LETTER})
    assert refused.status_code == 400 and "No AI model is ready" in refused.text
    api = client.post("/api/jobs", data={"text": LETTER})
    assert api.status_code == 400 and "No AI model is ready" in api.json()["detail"]
    ready = client.get("/readyz").json()
    assert ready["status"] == "degraded"
    assert (ready["llm"]["preset"], ready["llm"]["ready"], ready["llm"]["reachable"]) == (
        "cscs-apertus", False, False,
    )  # fmt: skip
    assert "no key" in ready["llm"]["error"]


def test_the_page_lists_the_groups_and_a_key_puts_a_preset_to_use(app, home, fake) -> None:
    client, app = app
    page = client.get("/model").text
    assert page.index("Switzerland") < page.index("Clouds: public documents only")
    assert 'value="cscs-apertus" checked' in page  # the shipped default, pre-selected
    assert "needs a key" in page and 'name="api_key_publicai"' in page
    assert "Where do I get a key?" in page and "about USD 0.02 per page" in page
    # The key goes into the .env next to the config file, the choice into the file.
    response = client.post(
        "/model",
        data={"action": "use", "preset": "publicai-apertus", "api_key_publicai": "pk-1"},
        follow_redirects=False,
    )
    assert (
        response.status_code == 303
        and response.headers["location"] == "/model?saved=publicai-apertus"
    )
    assert toml(home) == {"llm": {"preset": "publicai-apertus"}}
    assert "PUBLICAI_API_KEY=pk-1" in (home.parent / ".env").read_text(encoding="utf-8")
    assert "pk-1" not in client.get("/model").text  # never shown again
    saved = client.get("/model?saved=publicai-apertus").text
    assert "publicai-apertus is in use" in saved and "A key is saved" in saved
    # The app follows without a restart: the app bar, the probe, a draft.
    assert app.state.settings.llm.preset == "publicai-apertus"
    assert "Apertus 8B, checked by Apertus 70B" in client.get("/").text
    ready = client.get("/readyz").json()
    assert (ready["llm"]["preset"], ready["llm"]["ready"], ready["llm"]["reachable"]) == (
        "publicai-apertus", True, True,
    )  # fmt: skip
    fake.push(sse_response("Antwort"))
    submitted = client.post(
        "/jobs", data={"text": LETTER, "condition": "P0"}, follow_redirects=False
    )
    assert submitted.status_code == 303
    assert app.state.runner.wait_idle(30)
    assert fake.chat_bodies()[0]["model"] == "swiss-ai/apertus-v1.5-8b"
    assert fake.chat_bodies()[0]["cache"] == {"no-cache": True}  # the provider's extra_body


def test_the_key_is_checked_and_a_test_call_made(app, home, fake, monkeypatch) -> None:
    client, _ = app
    listed = {"calls": []}

    def list_models(url, key, headers=None, timeout_s=15.0):
        listed["calls"].append((url, key))
        if key != "ak":
            raise PermissionError("401")
        return ["claude-haiku-5-5", "claude-sonnet-5-5"]

    monkeypatch.setattr(configure, "list_models", list_models)
    wrong = client.post("/model", data={"action": "check", "preset": "claude-haiku-5-5",
                                        "api_key_anthropic": "nope"})  # fmt: skip
    assert wrong.status_code == 400 and "Anthropic did not answer: PermissionError" in wrong.text
    assert not (home.parent / ".env").exists()  # a check saves nothing
    right = client.post("/model", data={"action": "check", "preset": "claude-haiku-5-5",
                                        "api_key_anthropic": "ak"})  # fmt: skip
    assert right.status_code == 200
    assert "Anthropic answers and lists 2 models; claude-haiku-5-5 is among them" in right.text
    assert listed["calls"][-1] == ("https://api.anthropic.com/v1", "ak")
    none = client.post("/model", data={"action": "check", "preset": "claude-haiku-5-5"})
    assert none.status_code == 400 and "Anthropic needs a key" in none.text
    # A test call needs a ready preset; it answers with the model's text and the counts.
    early = client.post("/model", data={"action": "test", "preset": "claude-haiku-5-5"})
    assert early.status_code == 400 and "No test call: the variable ANTHROPIC_API_KEY" in early.text
    client.post(
        "/model", data={"action": "use", "preset": "claude-haiku-5-5", "api_key_anthropic": "ak"}
    )
    fake.push(sse_response("42", prompt_tokens=20, completion_tokens=1))
    made = client.post("/model", data={"action": "test", "preset": "claude-haiku-5-5"})
    assert (
        made.status_code == 200
        and "answered &#34;42&#34; in" in made.text
        and "20 tokens in, 1 out" in made.text
    )
    assert fake.chat_bodies()[-1]["thinking"] == {"type": "disabled"}  # Haiku's own table


def test_a_local_servers_models_are_offered_and_one_becomes_a_preset(app, home, monkeypatch):
    client, app = app
    monkeypatch.setattr(
        Registry,
        "discover",
        lambda self, provider: ["qwen3.5:9b"] if provider == "ollama" else None,
    )
    page = client.get("/model").text
    assert "This computer" in page and 'value="new:ollama:qwen3.5:9b"' in page
    assert "running" in page and "not running" in page  # Ollama answers, llama.cpp and vLLM do not
    response = client.post("/model", data={"action": "use", "preset": "new:ollama:qwen3.5:9b"},
                           follow_redirects=False)  # fmt: skip
    assert response.status_code == 303 and response.headers["location"].endswith(
        "ollama-qwen3-5-9b"
    )
    assert toml(home) == {
        "presets": {
            "ollama-qwen3-5-9b": {"provider": "ollama", "models": {"writer": "qwen3.5:9b"}}
        },
        "llm": {"preset": "ollama-qwen3-5-9b"},
    }
    llm = app.state.settings.llm
    assert (llm.url, llm.for_model("qwen3.5:9b").thinking) == (
        "http://127.0.0.1:11434/v1",
        "reasoning-effort",
    )
    page = client.get("/model").text
    assert 'value="ollama-qwen3-5-9b" checked' in page and "in use" in page
    assert 'value="new:ollama:qwen3.5:9b"' not in page  # listed once, as the preset now


def test_the_fine_tune_panel_saves_a_preset_of_ones_own(app, home) -> None:
    client, app = app
    missing = client.post("/model", data={"action": "save", "preset": "claude-haiku-5-5"})
    assert missing.status_code == 400 and "Give the preset a name" in missing.text
    response = client.post(
        "/model",
        data={
            "action": "save",
            "preset": "claude-haiku-5-5",
            "name": "mine",
            "writer": "",
            "understand": "claude-sonnet-5-5",
            "judge": "claude-sonnet-5-5",
            "think_understand": "1",
            "timeout_s": "600",
        },  # fmt: skip
        follow_redirects=False,
    )
    assert response.status_code == 303 and response.headers["location"] == "/model?saved=mine"
    assert toml(home)["presets"]["mine"] == {
        "provider": "anthropic",
        "label": "mine",
        "models": {"writer": "claude-haiku-5-5", "understand": "claude-sonnet-5-5",
                   "judge": "claude-sonnet-5-5"},
        "thinking_stages": ["understand"],
        "timeout_s": 600.0,
    }  # fmt: skip
    llm = app.state.settings.llm
    assert (llm.preset, llm.provider, llm.understand_model) == (
        "mine",
        "anthropic",
        "claude-sonnet-5-5",
    )
    assert "needs a key" in client.get("/model").text  # of its own, still without the key


def test_the_choice_is_locked_on_a_published_server_or_by_another_source(
    home, fake, monkeypatch
) -> None:
    monkeypatch.setenv("LEICHTFACILE_SERVER__HOST", "0.0.0.0")
    monkeypatch.setenv("LEICHTFACILE_AUTH__TOKEN", "t")
    with TestClient(create_app(store=Store(home.parent / "a.sqlite"))) as client:
        page = client.get("/model", auth=("x", "t"))
        assert page.status_code == 200 and "only on the machine the app runs on" in page.text
        assert 'name="api_key_' not in page.text and "Use this model" not in page.text
        refused = client.post("/model", data={"action": "use", "preset": "publicai-apertus"},
                              auth=("x", "t"))  # fmt: skip
        assert refused.status_code == 403
    monkeypatch.delenv("LEICHTFACILE_SERVER__HOST")
    monkeypatch.delenv("LEICHTFACILE_AUTH__TOKEN")
    monkeypatch.setenv("LEICHTFACILE_LLM__PRESET", "publicai-apertus")
    with TestClient(create_app(store=Store(home.parent / "b.sqlite"))) as client:
        page = client.get("/model").text
        assert "LEICHTFACILE_LLM__PRESET picks the model and wins over the config file" in page
        assert (
            client.post("/model", data={"action": "use", "preset": "cscs-apertus"}).status_code
            == 403
        )
    # One preset offered: nothing to choose, no page, no link.
    monkeypatch.delenv("LEICHTFACILE_LLM__PRESET")
    monkeypatch.setenv("LEICHTFACILE_LLM__OFFER", "publicai-apertus")
    with TestClient(create_app(store=Store(home.parent / "c.sqlite"))) as client:
        assert client.get("/model").status_code == 404
        assert 'href="/model"' not in client.get("/").text


def test_the_new_draft_form_offers_the_ready_presets_from_the_settings(app, monkeypatch) -> None:
    client, app = app
    assert 'name="endpoint"' not in client.get("/new").text  # nothing ready: no choice
    monkeypatch.setenv("PUBLICAI_API_KEY", "p")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    app.state.registry.reload()
    page = client.get("/new").text
    assert '<option value="publicai-apertus"' in page and "Claude Haiku 5.5 (Anthropic)" in page
    assert 'value="cscs-apertus"' not in page  # still without its key
    assert len([n for n, _ in app.state.registry.ready()]) == 4
    assert config.load(preset="claude-haiku-5-5").settings.llm.api_key is not None
