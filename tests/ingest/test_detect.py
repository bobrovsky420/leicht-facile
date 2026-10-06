from __future__ import annotations

import pytest

from leichtfacile.ingest.detect import detect_language


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Die Frist endet am 31. März 2026.", "de"),
        ("Bitte rufen Sie uns an.", "de"),
        ("Der Kanton bezahlt einen Teil der Prämie. Sie müssen nichts tun.", "de"),
        ("Die Kranken·kasse kostet Geld.", "de"),
        ("Le délai expire le 31 mars 2026.", "fr"),
        ("Merci de nous contacter.", "fr"),
        ("Vous avez droit à une réduction de primes. Le canton paie une partie.", "fr"),
        ("La SVA vous aide.", "fr"),
        ("Il termine scade il 31 marzo 2026.", "it"),
        ("Grazie per la vostra pazienza.", "it"),
        ("La domanda deve essere presentata entro il 31 marzo.", "it"),
        ("Avete diritto a una riduzione dei premi.", "it"),
    ],
)
def test_detects_short_texts(text, lang):
    detected, score = detect_language(text)
    assert detected == lang
    assert 0.6 <= score <= 1.0


@pytest.mark.parametrize(
    "text", ["The deadline is 31 March 2026.", "Please send us the form by e-mail."]
)
def test_english_is_rejected(text):
    detected, score = detect_language(text)
    assert detected is None
    assert score > 0.5  # confident that it is English, which is not supported


@pytest.mark.parametrize(
    "text", ["", "Prämienverbilligung", "Steuern bezahlen", "CHF 1500", "La SVA"]
)
def test_too_little_evidence(text):
    assert detect_language(text)[0] is None


def test_long_text_is_clear():
    text = (
        "Sie erhalten jedes Jahr einen Brief. Im Brief ist ein Antrag. Sie müssen den "
        "Antrag ausfüllen und bis 31. März an die SVA schicken. Dann prüft die SVA, ob "
        "Sie eine Prämienverbilligung bekommen."
    )
    assert detect_language(text) == ("de", 1.0)
