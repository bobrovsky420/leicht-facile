from __future__ import annotations

import pytest

from leichtfacile.ingest import ingest_pdf
from leichtfacile.ingest.errors import ExtractionError, NoTextLayerError
from leichtfacile.ingest.pdf import extract_pdf, hyphens_of_text_layer
from tests.ingest import pdfs


def test_letter_structure():
    title, units = extract_pdf(pdfs.letter())
    assert title == "Prämienverbilligung 2027"
    assert [(u.kind, u.heading_level, u.text) for u in units] == [
        ("heading", 1, "Prämienverbilligung 2027"),
        (
            "paragraph",
            None,
            "Sie haben Anspruch auf eine Prämienverbilligung. Der Kanton bezahlt einen Teil "
            "Ihrer Prämie für die Krankenkasse.",
        ),
        ("paragraph", None, "Schreiben Sie uns eine E-Mail, wenn Sie Fragen haben."),
        ("heading", 2, "Was müssen Sie tun"),
        ("paragraph", None, "Schicken Sie den Antrag bis 31. März 2027 an die SVA."),
        ("list_item", None, "den Antrag"),
        ("list_item", None, "eine Kopie der Steuererklärung"),
        ("paragraph", None, "Freundliche Grüsse"),
    ]
    assert {u.page for u in units} == {1}


def test_two_columns_are_read_one_after_the_other():
    title, units = extract_pdf(pdfs.two_columns())
    assert title == "Merkblatt zu den Kosten"
    assert [(u.kind, u.text) for u in units] == [
        ("heading", "Merkblatt zu den Kosten"),
        ("paragraph", " ".join(pdfs.LEFT)),
        ("paragraph", " ".join(pdfs.RIGHT)),
    ]


def test_running_footer_is_removed_and_paragraph_continues_on_the_next_page():
    title, units = extract_pdf(pdfs.two_pages_with_footer())
    assert title == "Merkblatt 99: Rückvergütung"  # from the PDF metadata
    assert [(u.page, u.text) for u in units] == [
        (
            1,
            "Die erste Seite erklärt, wer Geld zurück bekommt. Wer Ergänzungsleistungen "
            "bezieht, kann Kosten für Krankheit und Behinderung zurück verlangen. Dafür "
            "schicken Sie die Rechnung innerhalb von 15 Monaten an die Ausgleichskasse. Die "
            "zweite Seite enthält die Adresse der Ausgleichskasse.",
        )
    ]


def test_symbol_font_bullet_between_letters_becomes_a_mediopunkt():
    _, units = extract_pdf(pdfs.mediopunkt_and_symbol_bullets())
    assert units[1].text == "Merk\u2022blatt für Sie. Ergänzungs\u2022leistungen helfen."
    doc = ingest_pdf(pdfs.mediopunkt_and_symbol_bullets(), filename="merkblatt.pdf")
    assert [s.text for s in doc.segments] == [
        "Ein Merkblatt in Leichter Sprache",
        "Merk\u00b7blatt für Sie.",
        "Ergänzungs\u00b7leistungen helfen.",
    ]
    assert doc.source.type == "pdf"
    assert doc.source.uri == "merkblatt.pdf"
    assert {s.page for s in doc.segments} == {1}


def test_pdf_without_text_layer():
    with pytest.raises(NoTextLayerError, match="no text layer"):
        extract_pdf(pdfs.without_text())


def test_not_a_pdf():
    with pytest.raises(ExtractionError, match="not a readable PDF"):
        extract_pdf(b"Dies ist keine PDF-Datei.")


def test_soft_hyphens_of_the_text_layer_are_drawn_hyphens():
    # The DRV brochure (deutsche-rentenversicherung.de, 30 October 2026) maps every hyphen
    # glyph to U+00AD; dropped as invisible, its addresses read "MartinLutherStrasse 24".
    # fpdf cannot write such a PDF (its core fonts decode the glyph as a space), so the
    # text function is tested on the brochure's strings.
    shy = "\N{SOFT HYPHEN}"
    text = f"Martin{shy}Luther{shy}Straße 2{shy}4, 66111 Saarbrücken Telefon 0681 3093{shy}0"
    assert (
        hyphens_of_text_layer(text)
        == "Martin-Luther-Straße 2-4, 66111 Saarbrücken Telefon 0681 3093-0"
    )
    assert hyphens_of_text_layer(f"Rheinland{shy}Pfalz") == "Rheinland-Pfalz"
