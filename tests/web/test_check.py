"""The Check page: the rules alone on a pasted text, no job, no model."""

from __future__ import annotations

TEXT = """# Prämienverbilligung

Das Formular wird vom Amt geprüft.
Die Krankenversicherungspolice kostet 20 Franken.
Schicken Sie das Gesuch bis 31. März 2026.
"""


def test_the_check_page_runs_the_rules_on_a_text_without_a_job(app_env) -> None:
    client, app, endpoint = app_env
    page = client.get("/check")
    assert page.status_code == 200
    assert 'href="/check" aria-current="page"' in page.text and "Check my text" in page.text

    result = client.post("/check", data={"text": TEXT, "lang": "auto", "level": "A2"})
    assert result.status_code == 200
    assert "GRAM-01" in result.text and "Passive voice" in result.text  # wird ... geprüft
    assert "LEX-01" in result.text and "Kranken·versicherungs·police" in result.text
    assert "Per 100 blocks:" in result.text and "readability" in result.text
    assert "German" in result.text and "b0003" in result.text
    assert app.state.store.count_jobs() == 0  # nothing stored
    assert endpoint.chat_bodies() == []  # no model call


def test_the_check_page_refuses_an_empty_text_and_an_unchecked_language(app_env) -> None:
    client, app, endpoint = app_env
    empty = client.post("/check", data={"text": "   "})
    assert empty.status_code == 400 and "Paste a text first." in empty.text
    italian = client.post("/check", data={"text": "Il modulo deve essere compilato.", "lang": "it"})
    assert italian.status_code == 400 and "No checker rules for Italian yet" in italian.text
    too_long = client.post("/check", data={"text": "x" * 200_001})
    assert too_long.status_code == 400


def test_the_check_page_speaks_german_and_checks_french(app_env) -> None:
    client, app, endpoint = app_env
    client.get("/ui/de?next=/check")
    page = client.get("/check")
    assert "Text prüfen" in page.text and "Prüfen</button>" in page.text
    french = client.post(
        "/check",
        data={
            "text": "Le formulaire est contrôlé par l'office. Vous devez répondre.",
            "level": "B1",
        },
    )
    assert french.status_code == 200
    assert "GRAM-01" in french.text and "Französisch" in french.text
