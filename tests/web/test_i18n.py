"""Interface languages: complete catalogs, the language choice, translated pages."""

from __future__ import annotations

import re
import string
from pathlib import Path
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from leichtfacile.llm.client import LLMClient
from leichtfacile.rules import RULES
from leichtfacile.rules.messages import MESSAGES
from leichtfacile.schemas import (
    LANGS,
    Block,
    Condition,
    Draft,
    FactKind,
    FactStatus,
    Finding,
    JobStatus,
    RuleFindings,
)
from leichtfacile.store import Store
from leichtfacile.web.app import create_app
from leichtfacile.web.i18n import COOKIE, Translator, catalogs, pick_language, ui_languages
from leichtfacile.web.jobs import Submission, SubmissionError, create_job
from leichtfacile.web.views import (
    CORE_KEYS,
    STEP_WHO,
    STOP_KEYS,
    finding_text,
    progress_view,
    review_view,
    stop_reason,
)
from tests.conftest import FakeEndpoint, make_settings

WEB = Path(__file__).resolve().parents[2] / "src" / "leichtfacile" / "web"
LETTER = "# Gebühr\n\nDie Gebühr beträgt CHF 20.-.\nZahlen Sie bis 31. März 2026.\n"


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_every_catalog_has_the_english_keys_and_placeholders() -> None:
    english = catalogs()["en"]
    assert set(catalogs()) >= {"en", "de"}
    for code, catalog in catalogs().items():
        assert set(catalog) == set(english), code
        for key, text in english.items():
            assert _fields(catalog[key]) == _fields(text), f"{code}: {key}"


def test_catalogs_use_plain_hyphens_and_swiss_spelling() -> None:
    for code, catalog in catalogs().items():
        for key, text in catalog.items():
            assert chr(0x2013) not in text and chr(0x2014) not in text, f"{code}: {key}"
    assert not [k for k, v in catalogs()["de"].items() if chr(0xDF) in v]  # ss, not sharp s


def _used_keys() -> set[str]:
    """Literal keys the templates, app.js and the Python code ask for."""
    keys: set[str] = set()
    for path in (WEB / "templates").glob("*.html"):
        keys |= set(re.findall(r"""\bt\(\s*'([\w.]+)'\s*[,)]""", path.read_text("utf-8")))
    js = (WEB / "static" / "app.js").read_text("utf-8")
    for key in re.findall(r"""\bt\(\s*"([\w.]+)"\s*[,)]""", js):
        keys.add(key if key.startswith("status.") else f"js.{key}")
    for path in WEB.glob("*.py"):
        if path.name == "i18n.py":  # its docstring shows a made-up key
            continue
        text = path.read_text("utf-8")
        keys |= set(re.findall(r"""\bt\(\s*"([\w.]+)"\s*[,)]""", text))
        keys |= {f"error.{k}" for k in re.findall(r'SubmissionError\(\s*"(\w+)"', text)}
    return keys


def test_every_key_the_code_uses_exists() -> None:
    english = catalogs()["en"]
    plural = {k.rsplit(".", 1)[0] for k in english if k.endswith((".one", ".other"))}
    used = _used_keys()
    assert len(used) > 100
    missing = sorted(k for k in used if k not in english and k not in plural)
    assert not missing


def test_keys_built_from_data_exist() -> None:
    english = catalogs()["en"]
    built = (
        [f"status.{s}" for s in get_args(JobStatus)]
        + [f"kind.{k}" for k in get_args(FactKind)]
        + [f"fact.{s}" for s in (*get_args(FactStatus), "unchecked")]
        + [f"lang.{lang}" for lang in LANGS]
        + [f"condition.{c}" for c in get_args(Condition)]
        + [f"condition.short.{c}" for c in get_args(Condition)]
        + [f"finding.{k}" for k in MESSAGES]
        + [f"core.{k}" for k in CORE_KEYS]
        + [f"step.{k}.{part}" for k in STEP_WHO for part in ("title", "desc")]
        + [f"who.{w}" for w in set(STEP_WHO.values())]
        + list(STOP_KEYS.values())
        + ["stop.max_rounds.one", "stop.max_rounds.other"]
        # the workbench (docs/ui-design.md): states, severities, decisions, rule titles
        + [f"progress.state.{s}" for s in ("pending", "running", "done", "skipped", "failed")]
        + [f"sev.{s}" for s in ("error", "warn", "info")]
        + [f"review.decision.{d}" for d in ("undecided", "approved", "edited", "rejected")]
        + ["review.tag.code", "review.tag.judge"]
        + ["who.apertus", "who.code_title", "who.human_title"]
        + [f"new.level.{level}.desc" for level in ("A2", "B1")]
        + [f"new.condition.{c}.{part}" for c in ("P2", "P1", "P0") for part in ("title", "desc")]
        + [f"reader.{fmt}.desc" for fmt in ("md", "html", "json")]
        + [f"rule.{rule_id.removesuffix('-DE').removesuffix('-FR')}" for rule_id in RULES]
    )
    assert not [k for k in built if k not in english]


def test_translator_plurals_placeholders_and_fallback() -> None:
    de = Translator("de")
    assert de("detail.blocks", n=1) == "1 Block"
    assert de("detail.blocks", n=4) == "4 Blöcke"
    assert de("draft.version", version=2) == "Entwurf v2"
    assert de("no.such.key") == "no.such.key"
    assert de.get("kind.unknown", "unknown") == "unknown"
    assert Translator("xx").lang == "en"
    assert stop_reason(de, "stopped after 3 repair rounds") == "nach 3 Überarbeitungsrunden beendet"
    assert stop_reason(de, "something new") == "something new"
    assert de.js()["decided"] == "{decided} von {total} entschieden"
    assert de.js()["status.done"] == "Erledigt"


def test_the_language_choice() -> None:
    assert ui_languages()["de"] == "Deutsch"
    assert pick_language(None, None) == "en"
    assert pick_language(None, "de-CH,de;q=0.9,en;q=0.8") == "de"
    assert pick_language(None, "fr-CH, en;q=0.5, de;q=0.7") == "de"  # no French catalog yet
    assert pick_language(None, "de;q=0, en") == "en"
    assert pick_language(None, "de-CH", default="en") == "en"  # UI_LANG beats the browser
    assert pick_language("en", "de-CH", default="de") == "en"  # the switcher beats both
    assert pick_language("xx", "de-CH") == "de"


@pytest.fixture
def client(tmp_path, endpoint: FakeEndpoint, sleeps):
    settings = make_settings(data_dir=tmp_path, llm_max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    store = Store(tmp_path / "i18n.sqlite")
    app = create_app(settings, llm, store, load_examples_on_start=False)
    with TestClient(app) as test_client:
        yield test_client
    store.close()


def test_pages_follow_the_switcher(client) -> None:
    english = client.get("/")
    assert '<html lang="en">' in english.text and "New draft" in english.text
    assert 'href="/ui/de?next=/"' in english.text

    switch = client.get("/ui/de", params={"next": "/?x=1"}, follow_redirects=False)
    assert switch.status_code == 303 and switch.headers["location"] == "/?x=1"
    assert f"{COOKIE}=de" in switch.headers["set-cookie"]

    german = client.get("/")
    assert '<html lang="de">' in german.text
    assert "Neuer Entwurf" in german.text and "Noch keine Entwürfe" in german.text
    assert '"saving": "Wird gespeichert..."' in german.text  # the texts for app.js
    assert "Entwurf erstellen" in client.get("/new").text

    rejected = client.post("/jobs", data={"text": "Hallo.", "url": "https://example.org"})
    assert rejected.status_code == 400 and "Geben Sie genau eines an" in rejected.text
    assert 'href="/ui/en?next=/"' in rejected.text  # a POST page switches back to the start


def test_the_switcher_stays_on_this_site(client) -> None:
    for target in ("//evil.example/", "https://evil.example/", "/\\evil.example"):
        response = client.get("/ui/de", params={"next": target}, follow_redirects=False)
        assert response.headers["location"] == "/"
    assert client.get("/ui/xx", follow_redirects=False).status_code == 404


def test_the_browser_language_applies_without_a_choice(client) -> None:
    page = client.get("/", headers={"Accept-Language": "de-CH,de;q=0.9"})
    assert '<html lang="de">' in page.text


def test_progress_and_errors_in_german(tmp_path) -> None:
    settings = make_settings(data_dir=tmp_path)
    store = Store(tmp_path / "jobs.sqlite")
    job = create_job(store, settings, Submission(text=LETTER, condition="P2"))
    view = progress_view(store, job, t=Translator("de"))
    assert [s.title for s in view.steps][:2] == ["Lesen", "Schreiben"]
    assert view.steps[0].detail == "wartet auf den Worker"
    store.close()

    error = SubmissionError("unsupported_lang", lang="it", langs=("de", "fr"))
    assert str(error) == "The document is in Italian. This version writes German and French."
    assert error.text(Translator("de")) == (
        "Das Dokument ist auf Italienisch. Diese Version schreibt Deutsch und Französisch."
    )


def test_rule_findings_follow_the_interface_language(tmp_path) -> None:
    de, en = Translator("de"), Translator("en")
    finding = Finding(
        block_id="b001",
        rule_id="LEN-01",
        severity="warn",
        message="The sentence has 14 words; the limit for A2 is 12.",
        message_key="LEN-01",
        message_params={"words": 14, "limit": 12, "level": "A2"},
    )
    assert finding_text(de, finding) == "Der Satz hat 14 Wörter; die Grenze für A2 ist 12."
    assert finding_text(en, finding) == finding.message
    few = Finding(
        block_id=None,
        rule_id="LAY-03",
        severity="info",
        message="1 heading for 12 blocks: add headings, ideally as the reader's questions.",
        message_key="LAY-03.few",
        message_params={"n": 1, "blocks": 12},
    )
    assert finding_text(de, few).startswith("1 Überschrift für 12 Blöcke")
    assert finding_text(en, few) == few.message
    # Findings stored before the keys existed: the English text is read back, if it fits.
    old = Finding(
        block_id="b001",
        rule_id="LEN-02",
        severity="error",
        message="Subordinate clause ('die'): 3 clauses in one sentence. At most 1 for A2: "
        "one statement per sentence.",
    )
    assert finding_text(de, old) == (
        "Nebensatz ('die'): 3 Teilsätze in einem Satz. Höchstens 1 für A2: eine Aussage pro Satz."
    )
    legacy = Finding(block_id="b001", rule_id="LEN-01", severity="warn", message="legacy text")
    assert finding_text(de, legacy) == "legacy text"
    assert finding_text(de, legacy.model_copy(update={"message_key": "LEN-99"})) == "legacy text"

    # The review page builds its issues from the stored findings, in the reviewer's language.
    settings = make_settings(data_dir=tmp_path)
    store = Store(tmp_path / "jobs.sqlite")
    job = create_job(store, settings, Submission(text=LETTER))
    blocks = [Block(id="b001", kind="sentence", text="Ein Satz.")]
    store.put_artifact(
        job.id, "draft", Draft(doc_id=job.id, lang="de", level="A2", blocks=blocks), 1
    )
    rules = RuleFindings(draft_version=1, level="A2", findings=[finding, few])
    store.put_artifact(job.id, "rules", rules, 1)
    view = review_view(store, job, t=de)
    assert view.rows[0].issues[0].message == "Der Satz hat 14 Wörter; die Grenze für A2 ist 12."
    assert view.doc_issues[0].message.startswith("1 Überschrift für 12 Blöcke")
    assert review_view(store, job).rows[0].issues[0].message == finding.message
    store.close()
