"""Turning a submitted document into a job: ingest, store, queue."""

from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

from leichtfacile.config import Settings
from leichtfacile.ingest.errors import IngestError
from leichtfacile.pipeline.prompts import available_languages
from leichtfacile.schemas import LANGS, LEVELS, Job, JobConfig, SourceDocument
from leichtfacile.store import Store

MAX_TEXT_CHARS = 200_000
MAX_FILE_BYTES = 15_000_000


class SubmissionError(ValueError):
    """The submission cannot become a job; the message is shown to the user."""


@dataclass
class Submission:
    text: str | None = None
    url: str | None = None
    file_name: str | None = None
    file_data: bytes | None = None
    lang: str | None = None  # None or "auto": detect
    level: str = "A2"
    condition: str = "C2"
    writer_model: str | None = None
    judge_model: str | None = None
    title: str | None = None


def check_public_url(url: str, *, allow_private: bool = False) -> None:
    """Refuse URLs that point into the private network (server-side request forgery):
    the server fetches what a user submits, so a URL must not reach internal services.
    Set ALLOW_PRIVATE_URLS=1 for an intranet deployment that needs internal pages."""
    if allow_private:
        return
    host = urlsplit(url).hostname
    if not host:
        raise SubmissionError("The URL has no host name.")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise SubmissionError(f"The host {host} cannot be found.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise SubmissionError(
                f"The URL points into a private network ({host}); only public pages are fetched."
            )


def ingest_submission(sub: Submission, *, allow_private_urls: bool = False) -> SourceDocument:
    from leichtfacile import ingest

    lang = None if sub.lang in (None, "", "auto") else sub.lang
    if lang is not None and lang not in LANGS:
        raise SubmissionError(f"Unknown language {sub.lang!r}; use de, fr or it.")
    given = [
        bool(sub.text and sub.text.strip()),
        bool(sub.url and sub.url.strip()),
        bool(sub.file_data),
    ]
    if sum(given) != 1:
        raise SubmissionError("Give exactly one of: pasted text, a URL or a file.")
    try:
        if sub.text and sub.text.strip():
            if len(sub.text) > MAX_TEXT_CHARS:
                raise SubmissionError(f"The text is longer than {MAX_TEXT_CHARS:,} characters.")
            return ingest.ingest_text(sub.text, lang=lang, title=sub.title or None)
        if sub.url and sub.url.strip():
            url = sub.url.strip()
            if not url.lower().startswith(("http://", "https://")):
                raise SubmissionError("The URL must start with http:// or https://.")
            check_public_url(url, allow_private=allow_private_urls)
            return ingest.ingest_url(url, lang=lang)
        data = sub.file_data or b""
        if len(data) > MAX_FILE_BYTES:
            raise SubmissionError("The file is larger than 15 MB.")
        name = (sub.file_name or "upload").lower()
        if name.endswith(".pdf") or data[:5] == b"%PDF-":
            return ingest.ingest_pdf(data, filename=sub.file_name, lang=lang)
        text = data.decode("utf-8", errors="replace")
        if name.endswith((".html", ".htm")) or text.lstrip()[:15].lower().startswith(
            ("<!doctype", "<html")
        ):
            return ingest.ingest_html(text, url=None, lang=lang)
        return ingest.ingest_text(text, lang=lang, title=sub.title or sub.file_name)
    except IngestError as exc:
        raise SubmissionError(str(exc)) from exc


def create_job(store: Store, settings: Settings, sub: Submission) -> Job:
    if sub.level not in LEVELS:
        raise SubmissionError(f"Unknown level {sub.level!r}; use A2 or B1.")
    if sub.condition not in ("C0", "C1", "C2"):
        raise SubmissionError(f"Unknown condition {sub.condition!r}; use C0, C1 or C2.")
    allow = os.environ.get("ALLOW_PRIVATE_URLS", "").lower() in ("1", "true", "yes")
    source = ingest_submission(sub, allow_private_urls=allow)
    if not source.segments:
        raise SubmissionError("No text was found in the document.")
    if source.lang not in available_languages():
        names = {"de": "German", "fr": "French", "it": "Italian"}
        writes = " and ".join(names.get(lang, lang) for lang in available_languages())
        raise SubmissionError(
            f"The document is in '{source.lang}'. This version writes {writes}; Italian follows."
        )
    config = JobConfig(
        lang=source.lang,
        level=sub.level,  # type: ignore[arg-type]
        condition=sub.condition,  # type: ignore[arg-type]
        writer_model=sub.writer_model or None,
        judge_model=sub.judge_model or None,
        max_repair_rounds=settings.max_repair_rounds,
    )
    title = sub.title or source.title or sub.url or sub.file_name or "Pasted text"
    job = store.create_job(config, title=title[:200])
    store.put_artifact(job.id, "source", source)
    return job
