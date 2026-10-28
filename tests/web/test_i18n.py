"""Interface languages: complete catalogs, the language choice, translated pages."""

from __future__ import annotations

import re
import string
from pathlib import Path
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from leichtfacile.config import Documents, Location
from leichtfacile.llm.client import LLMClient
from leichtfacile.rules import RULES
from leichtfacile.rules.messages import MESSAGES, render_finding
from leichtfacile.schemas import (
    LANGS,
    STOP_REASONS,
    Block,
    Condition,
    Draft,
    FactKind,
    FactStatus,
    Finding,
    JobStatus,
    PipelineSummary,
    RoundRecord,
    RuleFindings,
)
from leichtfacile.store import Store
from leichtfacile.web.app import create_app
from leichtfacile.web.i18n import COOKIE, Translator, catalogs, pick_language, ui_languages
from leichtfacile.web.jobs import Submission, SubmissionError, create_job
from leichtfacile.web.views import (
    CORE_KEYS,
    STEP_WHO,
    finding_text,
    progress_view,
    review_view,
    rule_title,
    stop_reason,
)
from tests.conftest import FakeEndpoint, make_settings

WEB = Path(__file__).resolve().parents[2] / "src" / "leichtfacile" / "web"
LETTER = "# Gebühr\n\nDie Gebühr beträgt CHF 20.-.\nZahlen Sie bis 31. März 2026.\n"


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_every_catalog_has_the_english_keys_and_placeholders() -> None:
    english = catalogs()["en"]
    assert set(catalogs()) >= {"en", "de", "fr", "it"}
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
        + [
            f"stop.{code}{form}"
            for code in STOP_REASONS
            for form in ((".one", ".other") if code.startswith("max_") else ("",))
        ]
        # the workbench (docs/ui-design.md): states, severities, decisions, rule titles
        + [f"progress.state.{s}" for s in ("pending", "running", "done", "skipped", "failed")]
        + [f"sev.{s}" for s in ("error", "warn", "info")]
        + [f"review.decision.{d}" for d in ("undecided", "approved", "edited", "rejected")]
        + ["review.tag.code", "review.tag.judge"]
        + ["who.model", "who.code_title", "who.human_title"]
        + [f"new.level.{level}.desc" for level in ("A2", "B1")]
        + [f"new.condition.{c}.{part}" for c in ("P2", "P1", "P0") for part in ("title", "desc")]
        + [f"reader.{fmt}.desc" for fmt in ("md", "html", "docx", "json")]
        # the model page (web/model.py): groups, where the text goes, the status
        + [f"model.group.{g}" for g in ("ch", "local", "cloud")]
        + [f"model.location.{loc}" for loc in get_args(Location)]
        + [f"model.documents.{d}" for d in get_args(Documents)]
        + [f"model.status.{s}" for s in ("ready", "needs_key", "running", "not_running", "missing")]
        + [f"rule.{rule_id}" for rule_id in RULES]
    )
    assert not [k for k in built if k not in english]


def test_rule_titles_are_one_per_rule() -> None:
    """A rule has one id whatever the language (rules/catalog.py): GRAM-08 (separable
    verbs, German) and GRAM-09 (impersonal phrases, French) each have their own title."""
    de, fr, it = Translator("de"), Translator("fr"), Translator("it")
    assert "Trennbare" in rule_title(de, "GRAM-08")
    assert "unpersönlich" in rule_title(de, "GRAM-09")
    assert "impersonnelles" in rule_title(fr, "GRAM-09")
    assert "vous" in rule_title(fr, "LEX-06")
    assert "impersonale" in rule_title(it, "GRAM-09")
    assert rule_title(it, "LEX-06").endswith("Lei")
    assert rule_title(de, "LEN-01") == "Höchstens N Wörter pro Satz"


def test_translator_plurals_placeholders_and_fallback() -> None:
    de = Translator("de")
    assert de("detail.blocks", n=1) == "1 Block"
    assert de("detail.blocks", n=4) == "4 Blöcke"
    assert de("draft.version", version=2) == "Entwurf v2"
    assert de("no.such.key") == "no.such.key"
    assert de.get("kind.unknown", "unknown") == "unknown"
    assert Translator("xx").lang == "en"
    three = [
        RoundRecord(kind="repair", number=n, parent_version=n, version=n + 1) for n in (1, 2, 3)
    ]
    summary = PipelineSummary(
        condition="P2", final_version=4, rounds=three, stop_reason="max_rounds"
    )
    assert stop_reason(de, summary) == "nach 3 Überarbeitungsrunden beendet"
    assert stop_reason(de, summary.model_copy(update={"stop_reason": "no_blocking"})) == de(
        "stop.no_blocking"
    )
    assert de.js()["decided"] == "{decided} von {total} entschieden"
    assert de.js()["status.done"] == "Erledigt"


def test_the_language_choice() -> None:
    assert ui_languages()["de"] == "Deutsch"
    assert pick_language(None, None) == "en"
    assert pick_language(None, "de-CH,de;q=0.9,en;q=0.8") == "de"
    assert ui_languages()["fr"] == "Français"
    assert pick_language(None, "fr-CH, en;q=0.5, de;q=0.7") == "fr"
    assert ui_languages()["it"] == "Italiano"
    assert pick_language(None, "it-CH, en;q=0.5, de;q=0.7") == "it"
    assert pick_language(None, "de;q=0, en") == "en"
    assert pick_language(None, "de-CH", default="en") == "en"  # server.ui_lang beats the browser
    assert pick_language("en", "de-CH", default="de") == "en"  # the switcher beats both
    assert pick_language("xx", "de-CH") == "de"


@pytest.fixture
def client(tmp_path, endpoint: FakeEndpoint, sleeps):
    settings = make_settings(data__dir=tmp_path, llm__max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    store = Store(tmp_path / "i18n.sqlite")
    app = create_app(settings, llm, store)
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


def test_the_interface_speaks_french(client) -> None:
    assert 'href="/ui/fr?next=/"' in client.get("/").text
    client.get("/ui/fr")
    french = client.get("/")
    assert '<html lang="fr">' in french.text
    assert "Nouveau brouillon" in french.text and "Pas encore de brouillon" in french.text
    assert '"saving": "Enregistrement..."' in french.text  # the texts for app.js
    assert "Créer le brouillon" in client.get("/new").text
    checked = client.post("/check", data={"text": "Das Formular wird geprüft.", "level": "A2"})
    assert "Voix passive" in checked.text  # the checker's findings follow the interface


def test_the_interface_speaks_italian(client) -> None:
    assert 'href="/ui/it?next=/"' in client.get("/").text
    client.get("/ui/it")
    italian = client.get("/")
    assert '<html lang="it">' in italian.text
    assert "Nuova bozza" in italian.text and "Ancora nessuna bozza" in italian.text
    assert '"saving": "Salvataggio..."' in italian.text  # the texts for app.js
    assert "Crea la bozza" in client.get("/new").text
    checked = client.post("/check", data={"text": "Das Formular wird geprüft.", "level": "A2"})
    assert "Forma passiva" in checked.text  # the findings follow the interface, with Lei
    assert "Dica chi fa che cosa" in checked.text


def test_the_switcher_stays_on_this_site(client) -> None:
    for target in ("//evil.example/", "https://evil.example/", "/\\evil.example"):
        response = client.get("/ui/de", params={"next": target}, follow_redirects=False)
        assert response.headers["location"] == "/"
    assert client.get("/ui/xx", follow_redirects=False).status_code == 404


def test_the_browser_language_applies_without_a_choice(client) -> None:
    page = client.get("/", headers={"Accept-Language": "de-CH,de;q=0.9"})
    assert '<html lang="de">' in page.text


def test_progress_and_errors_in_german(tmp_path) -> None:
    settings = make_settings(data__dir=tmp_path)
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
        key="LEN-01",
        params={"words": 14, "limit": 12, "level": "A2"},
    )
    assert finding_text(de, finding) == "Der Satz hat 14 Wörter; die Grenze für A2 ist 12."
    assert finding_text(en, finding) == "The sentence has 14 words; the limit for A2 is 12."
    assert finding_text(en, finding) == render_finding(finding)
    few = Finding(
        block_id=None, rule_id="LAY-03", severity="info", key="LAY-03.few",
        params={"n": 1, "blocks": 12},
    )  # fmt: skip
    assert finding_text(de, few).startswith("1 Überschrift für 12 Blöcke")
    assert finding_text(en, few).startswith("1 heading for 12 blocks")
    # A finding stored before the keys existed keeps its English text (store.py).
    legacy = Finding(
        block_id="b001", rule_id="LEN-01", severity="warn", key="legacy",
        params={"text": "legacy text"},
    )  # fmt: skip
    assert finding_text(de, legacy) == "legacy text"
    assert finding_text(de, legacy.model_copy(update={"key": "LEN-99"})) == "finding.LEN-99"

    # The review page builds its issues from the stored findings, in the reviewer's language.
    settings = make_settings(data__dir=tmp_path)
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
    assert review_view(store, job).rows[0].issues[0].message == render_finding(finding)
    store.close()
