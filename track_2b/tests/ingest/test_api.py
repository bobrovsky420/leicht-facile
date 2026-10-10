from __future__ import annotations

import hashlib
import logging

import httpx
import pytest

from leichtfacile.ingest import (
    ExtractionError,
    SectionNotFoundError,
    UnsupportedSourceError,
    ingest_file,
    ingest_html,
    ingest_pdf,
    ingest_text,
    ingest_url,
    select_section,
)
from leichtfacile.ingest.__main__ import main
from tests.ingest import pdfs
from tests.ingest.test_html import PAGE

TEXT = """\
# Merkblatt Prämienverbilligung

Sie haben Anspruch auf eine Prämienverbilligung. Der Kanton bezahlt einen Teil Ihrer Prämie.

## Frist·verlängerung

Die Frist endet am 31. März 2027. Danach ist es zu spät.

### Kosten

- Bis 15. Juli: 20 Franken.
- Bis 15. September: 40 Franken.

## Kontakt

Rufen Sie uns an: 044 123 45 67.
"""


def test_ingest_text():
    doc = ingest_text(TEXT)
    assert doc.lang == "de"
    assert doc.title == "Merkblatt Prämienverbilligung"
    assert doc.source.type == "text"
    assert doc.source.uri is None
    assert doc.id.startswith("doc-") and len(doc.id) == 14
    assert [s.id for s in doc.segments] == [f"s{i:04d}" for i in range(1, len(doc.segments) + 1)]
    kosten = next(s for s in doc.segments if s.text == "Bis 15. Juli: 20 Franken.")
    assert kosten.kind == "list_item"
    assert kosten.heading_path == ["Merkblatt Prämienverbilligung", "Frist·verlängerung", "Kosten"]
    contact = doc.segments[-1]
    assert contact.heading_path == ["Merkblatt Prämienverbilligung", "Kontakt"]


def test_doc_id_is_a_hash_of_the_normalised_text():
    assert ingest_text(TEXT).id == ingest_text(TEXT.replace(" ", "  ")).id
    assert ingest_text(TEXT).id != ingest_text(TEXT + "\nNoch ein Satz.").id
    plain = "Sie haben Anspruch auf eine Prämienverbilligung."
    expected = "doc-" + hashlib.sha256(plain.encode("utf-8")).hexdigest()[:10]
    assert ingest_text(plain).id == expected


def test_ingest_text_options():
    doc = ingest_text(
        "Le délai expire le 31 mars. Vous pouvez demander une prolongation.",
        title="Délai",
        doc_id="be-tax-extension-fr",
        license_note="manifest only",
    )
    assert (doc.lang, doc.title, doc.id) == ("fr", "Délai", "be-tax-extension-fr")
    assert doc.source.license_note == "manifest only"
    assert ingest_text("Il termine scade il 31 marzo. Grazie.").lang == "it"
    assert ingest_text("Die Frist endet heute.", lang="FR-ch").lang == "fr"


def test_language_falls_back_to_german_with_a_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="leichtfacile.ingest"):
        doc = ingest_text("Prämienverbilligung 2027")
    assert doc.lang == "de"
    assert "language not detected" in caplog.text


def test_invalid_input():
    with pytest.raises(ValueError, match="unsupported language"):
        ingest_text("The deadline is today.", lang="en")
    with pytest.raises(ExtractionError, match="no text"):
        ingest_text(" \n\n ")


def test_ingest_html_from_bytes():
    doc = ingest_html(PAGE.encode("utf-8"), url="https://www.example.ch/steuern.html")
    assert doc.source.type == "html"
    assert doc.source.uri == "https://www.example.ch/steuern.html"
    assert doc.title == "Steuern verstehen"
    assert doc.lang == "de"
    assert doc.segments[0].kind == "heading"


def test_ingest_pdf():
    doc = ingest_pdf(pdfs.letter(), filename="brief.pdf", doc_id="letter")
    assert (doc.id, doc.source.type, doc.source.uri) == ("letter", "pdf", "brief.pdf")
    assert doc.title == "Prämienverbilligung 2027"
    assert doc.segments[1].text == "Sie haben Anspruch auf eine Prämienverbilligung."


def _client(content: bytes, content_type: str) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "https://www.example.ch/final"})
        return httpx.Response(200, content=content, headers={"content-type": content_type})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _resolve(host: str, port: int) -> list[str]:
    """No DNS in the tests: every name is a public address."""
    return ["93.184.216.34"]


@pytest.mark.parametrize(
    ("content", "content_type", "source_type"),
    [
        (PAGE.encode("utf-8"), "text/html; charset=utf-8", "html"),
        (pdfs.letter(), "application/pdf", "pdf"),
        (pdfs.letter(), "application/octet-stream", "pdf"),  # recognised by its magic bytes
        (
            "Die Frist endet am 31. März.".encode("cp1252"),
            "text/plain; charset=windows-1252",
            "text",
        ),
    ],
    ids=["html", "pdf", "pdf-by-magic-bytes", "text"],
)
def test_ingest_url(content, content_type, source_type):
    doc = ingest_url(
        "https://www.example.ch/start", client=_client(content, content_type), resolve=_resolve
    )
    assert doc.source.type == source_type
    assert doc.source.uri == "https://www.example.ch/final"
    assert doc.source.fetched_at is not None
    assert doc.segments


def test_ingest_url_rejects_other_content():
    with pytest.raises(UnsupportedSourceError, match="image/png"):
        ingest_url(
            "https://www.example.ch/start",
            client=_client(b"\x89PNG", "image/png"),
            resolve=_resolve,
        )


def test_ingest_file(tmp_path):
    (tmp_path / "brief.md").write_text(TEXT, encoding="utf-8")
    (tmp_path / "seite.html").write_text(PAGE, encoding="utf-8")
    (tmp_path / "brief.pdf").write_bytes(pdfs.letter())
    (tmp_path / "alt.txt").write_bytes("Die Frist endet am 31. März.".encode("cp1252"))
    (tmp_path / "brief.docx").write_bytes(b"PK")
    assert ingest_file(tmp_path / "brief.md").source.uri == "brief.md"
    assert ingest_file(tmp_path / "seite.html").source.type == "html"
    assert ingest_file(tmp_path / "brief.pdf").source.type == "pdf"
    assert ingest_file(tmp_path / "alt.txt").segments[0].text == "Die Frist endet am 31. März."
    with pytest.raises(UnsupportedSourceError, match=".docx"):
        ingest_file(tmp_path / "brief.docx")


def test_select_section():
    doc = ingest_text(TEXT, doc_id="merkblatt")
    section = select_section(doc, "fristverlängerung")  # ignores case and Mediopunkt
    assert [s.text for s in section.segments] == [
        "Frist·verlängerung",
        "Die Frist endet am 31. März 2027.",
        "Danach ist es zu spät.",
        "Kosten",
        "Bis 15. Juli: 20 Franken.",
        "Bis 15. September: 40 Franken.",
    ]
    assert [s.id for s in section.segments] == [f"s{i:04d}" for i in range(1, 7)]
    assert section.segments[0].para == 0
    assert section.id == "merkblatt"
    assert select_section(doc, "KOSTEN", doc_id="kosten").id == "kosten"
    assert [s.text for s in select_section(doc, "kosten").segments][-1] == (
        "Bis 15. September: 40 Franken."
    )
    assert doc.segments[0].id == "s0001" and len(doc.segments) == 11  # unchanged
    with pytest.raises(SectionNotFoundError):
        select_section(doc, "Gebühren")
    with pytest.raises(ValueError):
        select_section(doc, "  ")


def test_command_line(tmp_path, capsys):
    path = tmp_path / "brief.md"
    path.write_text(TEXT, encoding="utf-8")
    assert main([str(path), "--section", "Kontakt"]) == 0
    out = capsys.readouterr().out
    assert "s0001 h2" in out
    assert "Rufen Sie uns an: 044 123 45 67." in out
    assert main([str(tmp_path / "fehlt.pdf")]) == 1
