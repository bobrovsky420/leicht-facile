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
from leichtfacile.web.i18n import ENGLISH, Translator

MAX_TEXT_CHARS = 200_000
MAX_FILE_BYTES = 15_000_000


class SubmissionError(ValueError):
    """The submission cannot become a job. The message is the catalog text
    `error.<key>` (web/locales/): `str()` gives English for the API, `text()` the
    reviewer's language for the pages."""

    def __init__(self, key: str, **params: object) -> None:
        self.key = key
        self.params = params
        super().__init__(self.text(ENGLISH))

    def text(self, t: Translator) -> str:
        params = dict(self.params)
        if "lang" in params:
            params["lang"] = t.get(f"lang.{params['lang']}", str(params["lang"]))
        if "langs" in params:  # language codes, written as "German and French"
            names = [t.get(f"lang.{code}", code) for code in params["langs"]]  # type: ignore[attr-defined]
            params["langs"] = (
                t("list.and", first=", ".join(names[:-1]), last=names[-1])
                if len(names) > 1
                else "".join(names)
            )
        return t(f"error.{self.key}", **params)


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
        raise SubmissionError("no_host")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise SubmissionError("unknown_host", host=host) from exc
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
            raise SubmissionError("private_url", host=host)


def ingest_submission(sub: Submission, *, allow_private_urls: bool = False) -> SourceDocument:
    from leichtfacile import ingest

    lang = None if sub.lang in (None, "", "auto") else sub.lang
    if lang is not None and lang not in LANGS:
        raise SubmissionError("unknown_lang", lang=sub.lang)
    given = [
        bool(sub.text and sub.text.strip()),
        bool(sub.url and sub.url.strip()),
        bool(sub.file_data),
    ]
    if sum(given) != 1:
        raise SubmissionError("one_source")
    try:
        if sub.text and sub.text.strip():
            if len(sub.text) > MAX_TEXT_CHARS:
                raise SubmissionError("text_too_long", max=MAX_TEXT_CHARS)
            return ingest.ingest_text(sub.text, lang=lang, title=sub.title or None)
        if sub.url and sub.url.strip():
            url = sub.url.strip()
            if not url.lower().startswith(("http://", "https://")):
                raise SubmissionError("url_scheme")
            check_public_url(url, allow_private=allow_private_urls)
            return ingest.ingest_url(url, lang=lang)
        data = sub.file_data or b""
        if len(data) > MAX_FILE_BYTES:
            raise SubmissionError("file_too_large", mb=MAX_FILE_BYTES // 1_000_000)
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
        raise SubmissionError("ingest", detail=str(exc)) from exc


def create_job(store: Store, settings: Settings, sub: Submission) -> Job:
    if sub.level not in LEVELS:
        raise SubmissionError("unknown_level", level=sub.level)
    if sub.condition not in ("C0", "C1", "C2"):
        raise SubmissionError("unknown_condition", condition=sub.condition)
    allow = os.environ.get("ALLOW_PRIVATE_URLS", "").lower() in ("1", "true", "yes")
    source = ingest_submission(sub, allow_private_urls=allow)
    if not source.segments:
        raise SubmissionError("no_text")
    if source.lang not in available_languages():
        raise SubmissionError(
            "unsupported_lang", lang=source.lang, langs=tuple(available_languages())
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
