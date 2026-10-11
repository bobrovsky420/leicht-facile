"""Turning a submitted document into a job: ingest, store, queue.

The ingest (the fetch of a URL, the parse of a PDF, the segmentation) runs in the
request's thread so that the submitter gets a 400 with the reason at once; at most
`INGEST_SLOTS` submissions are read at a time, the next one is refused with 429 and
asked to try again (`ServerBusy`), so slow documents never fill the thread pool and
the other requests, the probes included, keep their threads (audit V4).
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit

from leichtfacile.config import Settings
from leichtfacile.ingest.errors import IngestError, PrivateAddressError, UnknownHostError
from leichtfacile.lifecycle import source_counts
from leichtfacile.pipeline.labels import label
from leichtfacile.pipeline.prompts import available_languages
from leichtfacile.schemas import (
    JOB_MODES,
    LANGS,
    LEVELS,
    Job,
    JobConfig,
    SourceDocument,
    canonical_condition,
)
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


class ServerBusy(SubmissionError):
    """Every ingest slot is taken: the submitter should try again in a moment."""

    def __init__(self) -> None:
        super().__init__("busy")


@contextmanager
def ingest_slot(slots: threading.Semaphore | None) -> Iterator[None]:
    """One of the `INGEST_SLOTS` while the document is read; `ServerBusy` at once when
    none is free (never a wait, which would hold the thread the limit protects)."""
    if slots is None:
        yield
        return
    if not slots.acquire(blocking=False):
        raise ServerBusy
    try:
        yield
    finally:
        slots.release()


@dataclass
class Submission:
    text: str | None = None
    url: str | None = None
    file_name: str | None = None
    file_data: bytes | None = None
    lang: str | None = None  # None or "auto": detect
    level: str = "A2"
    condition: str = "P2"
    writer_model: str | None = None
    understand_model: str | None = None
    judge_model: str | None = None
    title: str | None = None
    mode: str = "standard"  # or "decision" (track_2b/docs/use-case-decisions.md)
    addressee: str | None = None
    notice: str | None = None


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
            if not urlsplit(url).hostname:
                raise SubmissionError("no_host")
            # The fetch refuses every hop into the private network, redirects included,
            # and connects to the address it checked (ingest/fetch.py).
            return ingest.ingest_url(url, lang=lang, allow_private=allow_private_urls)
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
    except PrivateAddressError as exc:
        raise SubmissionError("private_url", host=exc.host) from exc
    except UnknownHostError as exc:
        raise SubmissionError("unknown_host", host=exc.host) from exc
    except IngestError as exc:
        raise SubmissionError("ingest", detail=str(exc)) from exc


def create_job(
    store: Store, settings: Settings, sub: Submission, slots: threading.Semaphore | None = None
) -> Job:
    """The job for a submission, queued and with its source stored. `slots` limits how
    many submissions are read at once (`ingest_slot`)."""
    if sub.level not in LEVELS:
        raise SubmissionError("unknown_level", level=sub.level)
    condition = canonical_condition(sub.condition)
    if condition not in ("P0", "P1", "P2"):
        raise SubmissionError("unknown_condition", condition=sub.condition)
    if sub.mode not in JOB_MODES:
        raise SubmissionError("unknown_mode", mode=sub.mode)
    # ALLOW_PRIVATE_URLS=1: an intranet deployment that needs internal pages.
    allow = os.environ.get("ALLOW_PRIVATE_URLS", "").lower() in ("1", "true", "yes")
    with ingest_slot(slots):
        source = ingest_submission(sub, allow_private_urls=allow)
    if not source.segments:
        raise SubmissionError("no_text")
    if source.lang not in available_languages():
        raise SubmissionError(
            "unsupported_lang", lang=source.lang, langs=tuple(available_languages())
        )
    notice = (sub.notice or "").strip() or None
    if sub.mode == "decision" and notice is None:
        notice = label(source.lang, "notice_default")  # the authority's text, per language
    config = JobConfig(
        lang=source.lang,
        level=sub.level,  # type: ignore[arg-type]
        condition=condition,  # type: ignore[arg-type]
        writer_model=sub.writer_model or None,
        understand_model=sub.understand_model or None,
        judge_model=sub.judge_model or None,
        max_repair_rounds=settings.max_repair_rounds,
        max_facts_rounds=settings.max_facts_rounds,
        mode=sub.mode,  # type: ignore[arg-type]
        addressee=(sub.addressee or "").strip() or None,
        notice=notice,
    )
    title = sub.title or source.title or sub.url or sub.file_name or "Pasted text"
    job = store.create_job(config, title=title[:200], counts=source_counts(source))
    store.put_artifact(job.id, "source", source)
    return job
