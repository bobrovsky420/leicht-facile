"""Ingest: pasted text, web pages and PDFs to a `SourceDocument`
(track_2b/docs/architecture.md §4.1).

Every entry point returns a `SourceDocument` whose segments carry stable ids
("s0001", ...), a kind, the heading path and the paragraph index:

- `ingest_text(text)`: pasted plain text or simple Markdown;
- `ingest_html(html, url=...)`: a web page (main content via trafilatura);
- `ingest_pdf(data, filename=...)`: a PDF with a text layer (pdfplumber);
- `ingest_url(url)`: downloads the URL and dispatches on the content type;
- `ingest_file(path)`: dispatches on the extension (.txt, .md, .html, .htm, .pdf);
- `select_section(doc, heading_query)`: keeps one section of a document.

All text passes through `normalize_text`. The language is the given `lang`, else the
detected one; when detection is not confident the language falls back to German with
a warning. The document id is the given `doc_id`, else "doc-" plus the first ten hex
characters of the SHA-256 of the normalised text.

Privacy: document text is never logged.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import cast

import httpx

from leichtfacile.ingest.detect import detect_language
from leichtfacile.ingest.errors import (
    ExtractionError,
    FetchError,
    IngestError,
    NoTextLayerError,
    SectionNotFoundError,
    UnsupportedSourceError,
)
from leichtfacile.ingest.html import (
    FetchedResource,
    decode_bytes,
    decode_html,
    extract_html,
    fetch_url,
)
from leichtfacile.ingest.normalize import MEDIOPUNKT, normalize_text
from leichtfacile.ingest.pdf import extract_pdf
from leichtfacile.ingest.segment import Unit, build_segments, split_sentences
from leichtfacile.ingest.text import first_heading, parse_text
from leichtfacile.schemas import LANGS, Lang, SourceDocument, SourceInfo

log = logging.getLogger(__name__)

DEFAULT_LANG: Lang = "de"

__all__ = [
    "DEFAULT_LANG",
    "ExtractionError",
    "FetchError",
    "FetchedResource",
    "IngestError",
    "NoTextLayerError",
    "SectionNotFoundError",
    "Unit",
    "UnsupportedSourceError",
    "build_segments",
    "detect_language",
    "fetch_url",
    "ingest_file",
    "ingest_html",
    "ingest_pdf",
    "ingest_text",
    "ingest_url",
    "normalize_text",
    "select_section",
    "split_sentences",
]

_TEXT_SUFFIXES = frozenset({".txt", ".text", ".md", ".markdown"})
_HTML_SUFFIXES = frozenset({".html", ".htm", ".xhtml"})
_PDF_MEDIA = frozenset({"application/pdf", "application/x-pdf"})
_HTML_MEDIA = frozenset({"text/html", "application/xhtml+xml"})
_TEXT_MEDIA = frozenset({"text/plain", "text/markdown", "text/x-markdown"})


def ingest_text(
    text: str,
    *,
    lang: str | None = None,
    title: str | None = None,
    doc_id: str | None = None,
    license_note: str | None = None,
) -> SourceDocument:
    """Pasted plain text (or simple Markdown). Without a title, a leading heading is used."""
    units = parse_text(text)
    return _build(
        units,
        SourceInfo(type="text", license_note=license_note),
        lang=lang,
        title=title if title is not None else first_heading(units),
        doc_id=doc_id,
    )


def ingest_html(
    html: str | bytes,
    *,
    url: str | None = None,
    lang: str | None = None,
    doc_id: str | None = None,
    license_note: str | None = None,
) -> SourceDocument:
    """A web page; bytes are decoded with the charset declared in the page."""
    if isinstance(html, bytes):
        html = decode_html(html)
    title, units = extract_html(html, url)
    return _build(
        units,
        SourceInfo(type="html", uri=url, license_note=license_note),
        lang=lang,
        title=title,
        doc_id=doc_id,
    )


def ingest_pdf(
    data: bytes,
    *,
    filename: str | None = None,
    lang: str | None = None,
    doc_id: str | None = None,
    license_note: str | None = None,
) -> SourceDocument:
    """A PDF with a text layer. Raises `NoTextLayerError` for scans."""
    title, units = extract_pdf(data)
    return _build(
        units,
        SourceInfo(type="pdf", uri=filename, license_note=license_note),
        lang=lang,
        title=title,
        doc_id=doc_id,
    )


def ingest_url(
    url: str,
    *,
    lang: str | None = None,
    doc_id: str | None = None,
    license_note: str | None = None,
    client: httpx.Client | None = None,
) -> SourceDocument:
    """Download a URL and ingest it as HTML, PDF or plain text by its content type."""
    resource = fetch_url(url, client=client)
    kind = _content_kind(resource)
    source_type = "html" if kind == "html" else "pdf" if kind == "pdf" else "text"
    source = SourceInfo(
        type=source_type,
        uri=resource.final_url,
        fetched_at=resource.fetched_at,
        license_note=license_note,
    )
    if kind == "pdf":
        title, units = extract_pdf(resource.content)
    elif kind == "html":
        html = decode_html(resource.content, resource.charset)
        title, units = extract_html(html, resource.final_url)
    else:
        units = parse_text(decode_bytes(resource.content, resource.charset))
        title = first_heading(units)
    return _build(units, source, lang=lang, title=title, doc_id=doc_id)


def ingest_file(
    path: str | Path,
    *,
    lang: str | None = None,
    doc_id: str | None = None,
    license_note: str | None = None,
) -> SourceDocument:
    """A local .txt, .md, .html, .htm or .pdf file; `source.uri` is the file name."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in _TEXT_SUFFIXES | _HTML_SUFFIXES | {".pdf"}:
        raise UnsupportedSourceError(
            f"unsupported file type {suffix or '(none)'!r}; expected .txt, .md, .html, .htm or .pdf"
        )
    data = path.read_bytes()
    if suffix == ".pdf":
        title, units = extract_pdf(data)
        source = SourceInfo(type="pdf", uri=path.name, license_note=license_note)
    elif suffix in _HTML_SUFFIXES:
        title, units = extract_html(decode_html(data))
        source = SourceInfo(type="html", uri=path.name, license_note=license_note)
    else:
        units = parse_text(decode_bytes(data))
        title = first_heading(units)
        source = SourceInfo(type="text", uri=path.name, license_note=license_note)
    return _build(units, source, lang=lang, title=title, doc_id=doc_id)


def select_section(
    doc: SourceDocument, heading_query: str, *, doc_id: str | None = None
) -> SourceDocument:
    """Keep the first heading that contains `heading_query` and everything under it.

    The match ignores case and Mediopunkte ("Fristverlängerung" finds
    "Frist·verlängerung"). The section ends before the next heading of the same or a
    higher level. Segment ids are renumbered from s0001 and `para` from 0; the document
    keeps its id unless `doc_id` is given.
    """
    query = _fold(heading_query)
    if not query:
        raise ValueError("heading_query is empty")
    segments = doc.segments
    start = next(
        (i for i, s in enumerate(segments) if s.kind == "heading" and query in _fold(s.text)),
        None,
    )
    if start is None:
        raise SectionNotFoundError(f"no heading contains {heading_query!r}")
    level = segments[start].heading_level or 6
    end = next(
        (
            j
            for j in range(start + 1, len(segments))
            if segments[j].kind == "heading" and (segments[j].heading_level or 6) <= level
        ),
        len(segments),
    )
    base = segments[start].para
    picked = [
        segment.model_copy(update={"id": f"s{n:04d}", "para": segment.para - base}, deep=True)
        for n, segment in enumerate(segments[start:end], start=1)
    ]
    return doc.model_copy(update={"segments": picked, "id": doc_id or doc.id}, deep=True)


# -- internals -------------------------------------------------------------------------


def _build(
    units: list[Unit],
    source: SourceInfo,
    *,
    lang: str | None,
    title: str | None,
    doc_id: str | None,
) -> SourceDocument:
    texts = [normalize_text(unit.text) for unit in units]
    plain = "\n\n".join(text for text in texts if text)
    if not plain:
        raise ExtractionError("no text found in the source")
    resolved = _resolve_lang(lang, plain)
    segments = build_segments(units, resolved)
    if not segments:
        raise ExtractionError("no text found in the source")
    return SourceDocument(
        id=doc_id or "doc-" + hashlib.sha256(plain.encode("utf-8")).hexdigest()[:10],
        lang=resolved,
        title=normalize_text(title or "") or None,
        source=source,
        segments=segments,
    )


def _resolve_lang(lang: str | None, text: str) -> Lang:
    if lang is not None:
        code = lang.strip().lower().replace("_", "-").split("-")[0]
        if code not in LANGS:
            raise ValueError(f"unsupported language {lang!r}; expected one of {', '.join(LANGS)}")
        return cast(Lang, code)
    detected, score = detect_language(text)
    if detected in LANGS:
        return cast(Lang, detected)
    log.warning(
        "language not detected with confidence (score %.2f); using %r, pass lang to override",
        score,
        DEFAULT_LANG,
    )
    return DEFAULT_LANG


def _content_kind(resource: FetchedResource) -> str:
    media = resource.media_type
    head = resource.content[:1024].lstrip().lower()
    if media in _PDF_MEDIA or b"%pdf-" in head:
        return "pdf"
    if media in _HTML_MEDIA or head.startswith((b"<!doctype html", b"<html")):
        return "html"
    if media in _TEXT_MEDIA:
        return "text"
    raise UnsupportedSourceError(
        f"unsupported content type {media or 'unknown'!r} at {resource.final_url}"
    )


def _fold(text: str) -> str:
    return normalize_text(text).replace(MEDIOPUNKT, "").casefold()
