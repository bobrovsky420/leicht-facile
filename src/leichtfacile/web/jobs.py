"""Turning a submitted document into a job: the form fields read once for the page and
the API (`submission_form`), the ingest, the store, the queue (`start_job`).

The ingest (the fetch of a URL, the parse of a PDF, the segmentation) runs in the
request's thread so that the submitter gets a 400 with the reason at once; at most
`jobs.ingest_slots` submissions are read at a time, the next one is refused with 429 and
asked to try again (`ServerBusy`), so slow documents never fill the thread pool and
the other requests, the probes included, keep their threads (audit V4).
"""

from __future__ import annotations

import codecs
import threading
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool

from leichtfacile.config import Settings
from leichtfacile.ingest.errors import (
    DocumentTooLongError,
    IngestError,
    PrivateAddressError,
    UnknownHostError,
)
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

MAX_FILE_BYTES = 15_000_000  # the text's own limit is texts.max_chars
# How a file that is no text starts: Word, OpenDocument and other ZIP files, an old
# Office file, PNG, JPEG, GIF, WebP, TIFF, PostScript, RTF (`_not_text`). Read as text,
# they became a job of garbage that went to the model.
_BINARY_STARTS = (
    b"PK\x03\x04", b"\xd0\xcf\x11\xe0", b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF",
    b"II*\x00", b"MM\x00*", b"%!PS", b"{\\rtf",
)  # fmt: skip
# The fields of the New draft form, which the page shows again after a refusal.
FORM_FIELDS = (
    "text", "url", "lang", "level", "condition", "endpoint", "title", "writer_model",
    "understand_model", "judge_model", "mode", "addressee", "notice", "sender", "address",
)  # fmt: skip
# What an example letter's file next to it sets in the form (examples.py, app.js).
EXAMPLE_FIELDS = ("mode", "addressee", "notice", "sender", "address")


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
        for count in ("max", "chars"):  # with the thousands as the interface writes them
            if count in params:
                params[count] = t.number(params[count])  # type: ignore[arg-type]
        if "lang" in params:
            params["lang"] = t.get(f"lang.{params['lang']}", str(params["lang"]))
        if "langs" in params:  # language codes, written as "German and French"
            names = [t.get(f"lang.{code}", code) for code in params["langs"]]  # type: ignore[attr-defined]
            params["langs"] = (
                t("list.and", first=", ".join(names[:-1]), last=names[-1])
                if len(names) > 1
                else "".join(names)
            )
        return t.fill(f"error.{self.key}", params)


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


def example_submission(example: dict[str, str]) -> Submission:
    """What the New draft form sends for an example letter (`example_sources`) left as it
    is: the text with the browser's CR LF line breaks, the language detected, level A2,
    P2, the preset in use, no title, and the letter's own settings. Its recorded run
    (llm/replay.py) is made, and checked, with this submission."""
    return Submission(
        text=example["text"].replace("\r\n", "\n").replace("\n", "\r\n"),
        mode=example.get("mode") or "standard",
        addressee=example.get("addressee") or None,
        notice=example.get("notice") or None,
        sender=example.get("sender") or "authority",
        address=example.get("address") or "formal",
    )


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
    """The multipart form of `POST /jobs` and `POST /api/v1/jobs` as one submission; FastAPI
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


async def start_job(
    state: Any, sub: Submission, workspace: str | None = None, created_by: str | None = None
) -> Job:
    """The job for a submission, stored and queued, in the request's `workspace`
    (web/workspaces.py) and recorded as submitted by `created_by`, the user the login
    named (web/security.py). The ingest (the fetch of a URL, the parse of a PDF, the
    segmentation) runs in the thread pool, so a slow URL never stops the server.
    `QueueFull`, `ServerBusy` and `SubmissionError` say why a submission was refused;
    the routes turn them into their answers."""
    state.runner.ensure_room()
    job = await run_in_threadpool(
        create_job,
        state.store,
        state.settings,
        sub,
        state.ingest_slots,
        presets=[name for name, _ in state.registry.ready()],
        workspace=workspace,
        created_by=created_by,
    )
    state.runner.submit(job.id)
    return job


def text_chars(text: str) -> int:
    """A pasted text's length as the form's counter shows it: the browser sends each
    line break as CR LF but counts it as one character."""
    return len(text.replace("\r\n", "\n"))


def _not_text(data: bytes) -> bool:
    """An upload that is no text: it starts like a known binary format, or a NUL byte
    stands in its first 8 KB, which no text has; UTF-16 and UTF-32 start with their byte
    order mark and are text."""
    if data.startswith(_BINARY_STARTS):
        return True
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE, codecs.BOM_UTF32_BE)):
        return False  # UTF-32 LE starts with UTF-16 LE's mark
    return b"\x00" in data[:8192]


def ingest_submission(  # noqa: C901, PLR0912
    sub: Submission, *, max_chars: int, allow_private_urls: bool = False
) -> SourceDocument:
    """The submission's document. A pasted text longer than `max_chars`
    (`texts.max_chars`) is refused before it is read, a file or a web page once its
    text is known."""
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
            if text_chars(sub.text) > max_chars:
                raise SubmissionError("text_too_long", max=max_chars)
            return ingest.ingest_text(sub.text, lang=lang, title=sub.title or None)
        if sub.url and sub.url.strip():
            url = sub.url.strip()
            if not url.lower().startswith(("http://", "https://")):
                raise SubmissionError("url_scheme")
            if not urlsplit(url).hostname:
                raise SubmissionError("no_host")
            # The fetch refuses every hop into the private network, redirects included,
            # and connects to the address it checked (ingest/fetch.py).
            source = ingest.ingest_url(
                url, lang=lang, allow_private=allow_private_urls, max_chars=max_chars, isolated=True
            )
        else:
            data = sub.file_data or b""
            if len(data) > MAX_FILE_BYTES:
                raise SubmissionError("file_too_large", mb=MAX_FILE_BYTES // 1_000_000)
            name = (sub.file_name or "upload").lower()
            if name.endswith(".pdf") or data[:5] == b"%PDF-":
                # In a child process with a time and a memory limit, and no further than
                # the text limit (pdfwords.py): a small file can unpack to gigabytes.
                source = ingest.ingest_pdf(
                    data, filename=sub.file_name, lang=lang, max_chars=max_chars, isolated=True
                )
            elif _not_text(data):
                raise SubmissionError("upload_format")
            else:
                # Read as the command line reads a file (ingest_file): a byte order mark,
                # UTF-8, else Windows-1252, and a page by the charset it declares (the
                # bytes go to ingest_html). UTF-8 with replacement characters lost every
                # umlaut of a Windows-1252 file.
                text = ingest.decode_bytes(data)
                if name.endswith((".html", ".htm")) or text.lstrip()[:15].lower().startswith(
                    ("<!doctype", "<html")
                ):
                    source = ingest.ingest_html(data, url=None, lang=lang)
                else:
                    source = ingest.ingest_text(text, lang=lang, title=sub.title or sub.file_name)
    except PrivateAddressError as exc:
        raise SubmissionError("private_url", host=exc.host) from exc
    except UnknownHostError as exc:
        raise SubmissionError("unknown_host", host=exc.host) from exc
    except DocumentTooLongError as exc:  # a PDF whose reading stopped at the limit
        raise SubmissionError("document_too_long_more", chars=exc.chars, max=max_chars) from exc
    except IngestError as exc:
        raise SubmissionError("ingest", detail=str(exc)) from exc
    if (chars := len(source.text())) > max_chars:
        raise SubmissionError("document_too_long", chars=chars, max=max_chars)
    return source


def create_job(  # noqa: C901
    store: Store,
    settings: Settings,
    sub: Submission,
    slots: threading.Semaphore | None = None,
    *,
    presets: Collection[str] | None = None,
    workspace: str | None = None,
    created_by: str | None = None,
) -> Job:
    """The job for a submission, queued and with its source stored. `slots` limits how
    many submissions are read at once (`ingest_slot`); `presets` are the ready presets
    a submission may pick, the one in use among them when it is ready (None: no
    check, a command's own client); `workspace` is the hash of the workspace the job
    belongs to (web/workspaces.py; None: none); `created_by` the user the login named
    (None: no login)."""
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
        source = ingest_submission(
            sub,
            max_chars=settings.texts.max_chars,
            allow_private_urls=settings.server.allow_private_urls,
        )
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
        region=region,
        level=sub.level,
        condition=condition,
        endpoint=endpoint,
        writer_model=sub.writer_model or None,
        understand_model=sub.understand_model or None,
        judge_model=sub.judge_model or None,
        pipeline=settings.pipeline,
        mode=sub.mode,
        sender=sub.sender,
        address=sub.address,
        addressee=(sub.addressee or "").strip() or None,
        notice=notice,
    )
    title = sub.title or source.title or sub.url or sub.file_name or "Pasted text"
    job = store.create_job(
        config,
        title=title[:200],
        counts=source_counts(source),
        workspace=workspace,
        created_by=created_by,
    )
    store.put_artifact(job.id, "source", source)
    return job
