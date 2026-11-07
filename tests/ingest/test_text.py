from __future__ import annotations

import pytest

from leichtfacile.ingest.text import parse_text

LETTER = """\
# Prämienverbilligung 2027

Sehr geehrte Frau Muster

Sie haben Anspruch auf eine Prämien-
verbilligung. Der Kanton bezahlt einen Teil
Ihrer Prämie.

## Was müssen Sie tun?

Sie brauchen:
- den Antrag
* eine Kopie der Steuer-
  erklärung
\u2022 Ihre AHV-Nummer
\u2013 einen Ausweis

1. Füllen Sie den Antrag aus.
2) Schicken Sie ihn bis 31. März 2027 an die SVA.
a) Am Schalter
   oder per Post.

1. Januar 2027 ist der Stichtag für die Berechnung.

Fristen

Zürich, 5. Oktober 2026

Freundliche Grüsse

---

Ihre SVA Zürich
"""


def test_letter_structure():
    units = parse_text(LETTER)
    assert [(u.kind, u.heading_level, u.text) for u in units] == [
        ("heading", 1, "Prämienverbilligung 2027"),
        ("paragraph", None, "Sehr geehrte Frau Muster"),
        (
            "paragraph",
            None,
            "Sie haben Anspruch auf eine Prämienverbilligung. Der Kanton bezahlt einen Teil "
            "Ihrer Prämie.",
        ),
        ("heading", 2, "Was müssen Sie tun?"),
        ("paragraph", None, "Sie brauchen:"),
        ("list_item", None, "den Antrag"),
        ("list_item", None, "eine Kopie der Steuererklärung"),
        ("list_item", None, "Ihre AHV-Nummer"),
        ("list_item", None, "einen Ausweis"),
        ("list_item", None, "Füllen Sie den Antrag aus."),
        ("list_item", None, "Schicken Sie ihn bis 31. März 2027 an die SVA."),
        ("list_item", None, "Am Schalter oder per Post."),
        ("paragraph", None, "1. Januar 2027 ist der Stichtag für die Berechnung."),
        ("heading", 2, "Fristen"),
        ("paragraph", None, "Zürich, 5. Oktober 2026"),
        ("paragraph", None, "Freundliche Grüsse"),
        ("heading", 2, "Ihre SVA Zürich"),
    ]


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Kurze Zeile ohne Punkt", "heading"),
        ("Kurze Zeile mit Punkt.", "paragraph"),
        ("Sie brauchen:", "paragraph"),
        ("Eins zwei drei vier fünf sechs sieben acht neun zehn elf", "paragraph"),
        ("kleiner Anfang", "paragraph"),
        ("Liebe Leserin", "paragraph"),
        ("Madame, Monsieur", "paragraph"),
        ("Lausanne, le 1er octobre 2026", "paragraph"),
        ("Cordiali saluti", "paragraph"),
        ("12345", "paragraph"),
        ("Verfahrensnummer: KES-2026-0187", "paragraph"),  # a field line, not a heading
        ("Telefon 044 123 45 67", "paragraph"),
        ("kesb@musterwil.example", "paragraph"),
        ("Mehr unter www.musterwil.example", "paragraph"),
        ("Betreff: Staats- und Gemeindesteuern 2025", "heading"),
        ("Prämienverbilligung 2027", "heading"),
        # A value a fact needs is no heading (headings until 6 November 2026).
        ("Rechnungsbetrag CHF 1'250.00", "paragraph"),
        ("IBAN CH93 0076 2011 6238 5295 7", "paragraph"),
        ("Rechnung Nr. 2026123456 vom Steueramt", "paragraph"),
    ],
)
def test_single_short_line(text, kind):
    (unit,) = parse_text(text)
    assert unit.kind == kind


def test_a_letter_pasted_from_word_is_one_paragraph_per_line():
    """Word and Outlook paste a letter with one line break per paragraph and no blank
    line between them: until 6 November 2026 it was one paragraph, the title and the
    salutation glued into the sentences. The address stays one paragraph, as does the
    closing with the signature after it."""
    letter = """\
Steueramt Musterhausen
Bahnhofstrasse 5
8001 Zürich
Zürich, 5. Oktober 2026
Veranlagungsverfügung 2025
Sehr geehrte Frau Muster
Wir haben Ihre Steuererklärung 2025 geprüft und die Steuern berechnet.
Rechnungsbetrag CHF 1'250.00
Bitte bezahlen Sie den Betrag bis zum 30. November 2026.
Freundliche Grüsse
Steueramt Musterhausen
Hans Beispiel, Sachbearbeiter
"""
    assert [(u.kind, u.text) for u in parse_text(letter)] == [
        ("paragraph", "Steueramt Musterhausen Bahnhofstrasse 5 8001 Zürich"),
        ("paragraph", "Zürich, 5. Oktober 2026"),
        ("heading", "Veranlagungsverfügung 2025"),
        ("paragraph", "Sehr geehrte Frau Muster"),
        ("paragraph", "Wir haben Ihre Steuererklärung 2025 geprüft und die Steuern berechnet."),
        ("paragraph", "Rechnungsbetrag CHF 1'250.00"),
        ("paragraph", "Bitte bezahlen Sie den Betrag bis zum 30. November 2026."),
        ("paragraph", "Freundliche Grüsse Steueramt Musterhausen Hans Beispiel, Sachbearbeiter"),
    ]


def test_a_numbered_line_is_a_list_item_only_in_a_sequence():
    """A line that opened with a number was a list item and lost the number until
    6 November 2026 ("3. Stock, Zimmer 304" became "Stock, Zimmer 304"). A list is the
    numbers in a row, with blank lines between its items too."""
    address = "Frau Maria Muster\nVerwaltungsgebäude\n3. Stock, Zimmer 304\n8000 Zürich"
    assert [(u.kind, u.text) for u in parse_text(address)] == [
        ("paragraph", "Frau Maria Muster Verwaltungsgebäude 3. Stock, Zimmer 304 8000 Zürich")
    ]
    # Not a sequence: "2." comes after "3.".
    text = f"{address}\n\nDie Rechnung:\n\n2. Rate CHF 400 bis 31. Januar 2027"
    assert parse_text(text)[-1].text == "2. Rate CHF 400 bis 31. Januar 2027"
    loose = (
        "1. Zuständig ist die KESB.\n\n2. Die Frist beträgt 30 Tage:\na) per Post\nb) am Schalter"
    )
    assert [(u.kind, u.text) for u in parse_text(loose)] == [
        ("list_item", "Zuständig ist die KESB."),
        ("list_item", "Die Frist beträgt 30 Tage:"),
        ("list_item", "per Post"),
        ("list_item", "am Schalter"),
    ]


def test_lines_of_a_paragraph_are_joined():
    (unit,) = parse_text("Erste Zeile\nzweite Zeile\n  dritte Zeile")
    assert unit.text == "Erste Zeile zweite Zeile dritte Zeile"


def test_list_item_ends_at_unindented_line():
    units = parse_text("- Punkt eins\nNeuer Absatz beginnt hier.")
    assert [(u.kind, u.text) for u in units] == [
        ("list_item", "Punkt eins"),
        ("paragraph", "Neuer Absatz beginnt hier."),
    ]


def test_markdown_heading_levels_and_closing_hashes():
    units = parse_text("### Dritte Ebene ###\n\n###### Sechste Ebene")
    assert [(u.heading_level, u.text) for u in units] == [(3, "Dritte Ebene"), (6, "Sechste Ebene")]


def test_empty_text():
    assert parse_text("") == []
    assert parse_text(" \n\n \t \n") == []
