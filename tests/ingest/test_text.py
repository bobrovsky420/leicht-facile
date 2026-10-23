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
    ],
)
def test_single_short_line(text, kind):
    (unit,) = parse_text(text)
    assert unit.kind == kind


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
