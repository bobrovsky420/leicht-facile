from __future__ import annotations

import sys

import pytest

from leichtfacile import pdfwords
from leichtfacile.ingest import ingest_pdf
from leichtfacile.ingest.errors import DocumentTooLongError, ExtractionError, NoTextLayerError
from leichtfacile.ingest.pdf import extract_pdf
from leichtfacile.pdfwords import hyphens_of_text_layer
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


def test_contact_lines_of_a_running_letterhead_and_footer_stay_once():
    """A letterhead or a footer on every page is a running line, but its web address,
    phone number and e-mail are facts: until 6 November 2026 they went on PDFs of two
    pages and more. One copy stays, the letterhead on its first page and the footer on
    its last, so the paragraph over the page break stays one; the page numbers go."""
    _, units = extract_pdf(pdfs.contacts_in_the_margins())
    assert [(u.page, u.kind, u.text) for u in units] == [
        (1, "paragraph", "Steueramt Musterhausen | www.musterhausen.example"),
        (
            1,
            "paragraph",
            "Wir haben Ihre Steuererklärung geprüft. Bitte bezahlen Sie den Betrag bis zum "
            "31. März 2027 und schreiben Sie uns, wenn Sie Fragen haben. Die Einsprache muss "
            "schriftlich begründet werden.",
        ),
        (3, "paragraph", "Freundliche Grüsse"),
        (3, "paragraph", "Telefon 044 123 45 67 | steuern@musterhausen.example"),
    ]


def test_a_line_with_a_value_is_no_heading():
    """A bill's total in bold and its due date set large were headings until 6 November
    2026, and a value only in a heading is no fact the draft must keep."""
    _, units = extract_pdf(pdfs.value_lines_in_bold())
    assert [(u.kind, u.heading_level, u.text) for u in units] == [
        ("heading", 1, "Steuerrechnung 2026"),
        ("paragraph", None, "Wir haben Ihre Steuern für das Jahr 2026 berechnet."),
        ("paragraph", None, "Total CHF 1'250.00"),
        ("paragraph", None, "Zahlbar bis 30. November 2026"),
        ("heading", 2, "Was müssen Sie tun"),
        ("paragraph", None, "Bezahlen Sie den Betrag mit dem Einzahlungsschein."),
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


def test_a_pdf_with_a_page_that_shows_pictures_but_no_text_is_refused_whole():
    """A scanned attachment or a table as an image in a PDF with text: the whole PDF is
    refused, naming the pages; until 6 November 2026 the page was left out with a log
    line only, and the draft missed what it said. Blank pages, and pages with only a
    rule and a small logo, are skipped as before."""
    with pytest.raises(NoTextLayerError, match=r"^page 2 of the PDF has no text layer"):
        extract_pdf(pdfs.with_pages_without_text("scan"))
    with pytest.raises(NoTextLayerError, match=r"^pages 2 and 4 of the PDF have no text"):
        extract_pdf(pdfs.with_pages_without_text("scan", "blank", "scan"))
    _, units = extract_pdf(pdfs.with_pages_without_text("blank", "rule"))
    assert [u.text for u in units] == [
        "Die Frist endet am 31. März 2027. Bitte zahlen Sie 500 Franken."
    ]


def test_a_pdf_over_the_page_limit_is_refused_before_its_pages_are_read():
    """Audit 2.6.18: a thousand pages from 159 kB took 4.2 s; the count is checked before
    a page is parsed."""
    assert len(extract_pdf(pdfs.pages(pdfwords.MAX_PAGES))[1]) == pdfwords.MAX_PAGES
    with pytest.raises(ExtractionError, match=r"^the PDF has 201 pages; at most 200 are read"):
        extract_pdf(pdfs.pages(201))


def test_reading_stops_past_twice_the_text_limit():
    """The whole PDF was read before the text limit refused it; reading stops when the
    words pass twice the limit (running lines and page numbers go later, so the job's
    own check decides below that)."""
    data = pdfs.contacts_in_the_margins()
    with pytest.raises(DocumentTooLongError) as refused:
        extract_pdf(data, max_chars=40)
    assert refused.value.chars > 80
    assert extract_pdf(data, max_chars=10_000) == extract_pdf(data)


def test_an_isolated_read_gives_the_same_units_and_ends_at_its_time_limit():
    """A file from outside is read in a child process (pdfwords.read_isolated): the same
    result as in this process, and a child that takes too long is stopped."""
    assert extract_pdf(pdfs.letter(), isolated=True) == extract_pdf(pdfs.letter())
    with pytest.raises(pdfwords.Refused, match=r"^the PDF took more than 0 s to read"):
        pdfwords.read_isolated(pdfs.letter(), time_limit_s=0.01)
    with pytest.raises(ExtractionError, match=r"^not a readable PDF"):
        extract_pdf(b"Dies ist keine PDF-Datei.", isolated=True)


@pytest.mark.skipif(sys.platform != "linux", reason="the address-space limit is Linux's")
def test_an_isolated_read_stops_at_its_memory_limit():
    """A compressed stream of 300 kB that unpacks to 300 MB, read under a limit of 200 MB:
    refused with the reason, the service's own memory untouched."""
    with pytest.raises(pdfwords.Refused, match="more memory than one file may take"):
        pdfwords.read_isolated(pdfs.unpacking(300), memory_limit=200_000_000)


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
