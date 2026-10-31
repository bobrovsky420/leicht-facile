"""Turning a submitted document into a job: the form fields read once for the page and
the API (`submission_form`), the ingest, the store, the queue (`start_job`).

The ingest (the fetch of a URL, the parse of a PDF, the segmentation) runs in the
request's thread so that the submitter gets a 400 with the reason at once; at most
`jobs.ingest_slots` submissions are read at a time, the next one is refused with 429 and
asked to try again (`ServerBusy`), so slow documents never fill the thread pool and
the other requests, the probes included, keep their threads (audit V4).
"""

from __future__ import annotations

import threading
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool

from leichtfacile.config import Settings
from leichtfacile.ingest.errors import IngestError, PrivateAddressError, UnknownHostError
from leichtfacile.lifecycle import source_counts
from leichtfacile.pipeline.prompts import available_languages
from leichtfacile.schemas import (
    ADDRESS_FORMS,
    JOB_MODES,
    LANGS,
    LEVELS,
    SENDERS,
    Job,
    JobConfig,
    SourceDocument,
)
from leichtfacile.store import Store
from leichtfacile.varieties import region_for, variety
from leichtfacile.web.i18n import ENGLISH, Translator

MAX_TEXT_CHARS = 200_000
MAX_FILE_BYTES = 15_000_000
# The fields of the New draft form, which the page shows again after a refusal.
FORM_FIELDS = (
    "text", "url", "lang", "level", "condition", "endpoint", "title", "writer_model",
    "understand_model", "judge_model", "mode", "addressee", "notice", "sender", "address",
)  # fmt: skip


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
        if "max" in params:  # a count, with the thousands as the interface writes them
            params["max"] = t.number(params["max"])  # type: ignore[arg-type]
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
    """One of the `jobs.ingest_slots` while the document is read; `ServerBusy` at once when
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
    endpoint: str | None = None  # the preset for this job; None or "": the one in use
    writer_model: str | None = None
    understand_model: str | None = None
    judge_model: str | None = None
    title: str | None = None
    mode: str = "standard"  # or "decision" (docs/use-case-decisions.md)
    addressee: str | None = None
    notice: str | None = None
    sender: str = "authority"  # or "school", "organisation" (schemas.Sender)
    address: str = "formal"  # or "informal", "plural" (schemas.Address)

    def form(self) -> dict[str, str]:
        """The fields as the New draft form shows them again after a refusal."""
        return {key: getattr(self, key) or "" for key in FORM_FIELDS}


def _model(name: str | None) -> str | None:
    return (name or "").strip() or None


async def submission_form(
    text: Annotated[str | None, Form()] = None,
    url: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    lang: Annotated[str | None, Form()] = None,
    level: Annotated[str, Form()] = "A2",
    condition: Annotated[str, Form()] = "P2",
    endpoint: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form()] = None,
    writer_model: Annotated[str | None, Form()] = None,
    understand_model: Annotated[str | None, Form()] = None,
    judge_model: Annotated[str | None, Form()] = None,
    mode: Annotated[str, Form()] = "standard",
    addressee: Annotated[str | None, Form()] = None,
    notice: Annotated[str | None, Form()] = None,
    sender: Annotated[str, Form()] = "authority",
    address: Annotated[str, Form()] = "formal",
) -> Submission:
    """The multipart form of `POST /jobs` and `POST /api/jobs` as one submission; FastAPI
    fills it for both routes (`Depends`). `endpoint` runs the job on another ready
    preset (docs/configuration.md); `mode` is `standard` or `decision`
    (docs/use-case-decisions.md); `addressee` and `notice` belong to the decision mode."""
    data = await file.read() if file is not None and file.filename else None
    return Submission(
        text=text,
        url=url,
        file_name=file.filename if file is not None else None,
        file_data=data,
        lang=lang,
        level=level,
        condition=condition,
        endpoint=endpoint,
        writer_model=_model(writer_model),
        understand_model=_model(understand_model),
        judge_model=_model(judge_model),
        title=title,
        mode=mode,
        addressee=addressee,
        notice=notice,
        sender=sender,
        address=address,
    )


async def start_job(state: Any, sub: Submission) -> Job:
    """The job for a submission, stored and queued. The ingest (the fetch of a URL, the
    parse of a PDF, the segmentation) runs in the thread pool, so a slow URL never stops
    the server. `QueueFull`, `ServerBusy` and `SubmissionError` say why a submission was
    refused; the routes turn them into their answers."""
    state.runner.ensure_room()
    job = await run_in_threadpool(
        create_job,
        state.store,
        state.settings,
        sub,
        state.ingest_slots,
        presets=[name for name, _ in state.registry.ready()],
    )
    state.runner.submit(job.id)
    return job


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
    store: Store,
    settings: Settings,
    sub: Submission,
    slots: threading.Semaphore | None = None,
    *,
    presets: Collection[str] | None = None,
) -> Job:
    """The job for a submission, queued and with its source stored. `slots` limits how
    many submissions are read at once (`ingest_slot`); `presets` are the ready presets
    a submission may pick, the one in use among them when it is ready (None: no
    check, a command's own client)."""
    if sub.level not in LEVELS:
        raise SubmissionError("unknown_level", level=sub.level)
    condition = sub.condition
    if condition not in ("P0", "P1", "P2"):
        raise SubmissionError("unknown_condition", condition=sub.condition)
    if sub.mode not in JOB_MODES:
        raise SubmissionError("unknown_mode", mode=sub.mode)
    if sub.sender not in SENDERS:
        raise SubmissionError("unknown_sender", sender=sub.sender)
    if sub.address not in ADDRESS_FORMS:
        raise SubmissionError("unknown_address", address=sub.address)
    endpoint = (sub.endpoint or "").strip() or None
    if presets is not None and (endpoint or settings.llm.preset) not in presets:
        if endpoint is None or endpoint == settings.llm.preset:
            raise SubmissionError("no_model")  # the preset in use is not ready
        raise SubmissionError("unknown_endpoint", name=endpoint)
    # server.allow_private_urls: an intranet that needs internal pages
    with ingest_slot(slots):
        source = ingest_submission(sub, allow_private_urls=settings.server.allow_private_urls)
    if not source.segments:
        raise SubmissionError("no_text")
    if source.lang not in available_languages():
        raise SubmissionError(
            "unsupported_lang", lang=source.lang, langs=tuple(available_languages())
        )
    # The installation's variety (texts.region, set by setup) goes onto the source and
    # the job: a later setup leaves this job as it was.
    region = region_for(source.lang, settings.texts.region)
    source = source.model_copy(update={"region": region})
    notice = (sub.notice or "").strip() or None
    if sub.mode == "decision" and notice is None:
        notice = variety(source.variety).notice  # the authority's text, per variety
    config = JobConfig(
        lang=source.lang,
        region=region,  # type: ignore[arg-type]
        level=sub.level,  # type: ignore[arg-type]
        condition=condition,  # type: ignore[arg-type]
        endpoint=endpoint,
        writer_model=sub.writer_model or None,
        understand_model=sub.understand_model or None,
        judge_model=sub.judge_model or None,
        pipeline=settings.pipeline,
        mode=sub.mode,  # type: ignore[arg-type]
        sender=sub.sender,  # type: ignore[arg-type]
        address=sub.address,  # type: ignore[arg-type]
        addressee=(sub.addressee or "").strip() or None,
        notice=notice,
    )
    title = sub.title or source.title or sub.url or sub.file_name or "Pasted text"
    job = store.create_job(config, title=title[:200], counts=source_counts(source))
    store.put_artifact(job.id, "source", source)
    return job
