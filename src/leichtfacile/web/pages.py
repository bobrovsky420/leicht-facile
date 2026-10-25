"""Server-rendered pages: drafts list, new draft, job progress, review, reader preview.

Every page is rendered in the reviewer's interface language (`i18n.py`): the choice
from the switcher in the header (a cookie), else `server.ui_lang`, else the browser's.
The layout and its parts are specified in docs/ui-design.md."""

from __future__ import annotations

from functools import cache, lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from leichtfacile import __version__
from leichtfacile.examples import example_sources, examples_dir
from leichtfacile.export.html import to_html
from leichtfacile.ingest.detect import detect_language
from leichtfacile.lifecycle import remove_job
from leichtfacile.pipeline.labels import label
from leichtfacile.pipeline.orchestrator import JobBusy, PipelineError
from leichtfacile.pipeline.prompts import available_languages
from leichtfacile.pipeline.runner import QueueFull
from leichtfacile.rules.base import RULES
from leichtfacile.schemas import LANGS, LEVELS, Decision, Draft, PipelineSummary, ReviewState
from leichtfacile.web.api import BUSY, ReviewIn
from leichtfacile.web.i18n import COOKIE, Translator, pick_language, ui_languages
from leichtfacile.web.jobs import (
    MAX_TEXT_CHARS,
    ServerBusy,
    Submission,
    SubmissionError,
    create_job,
)
from leichtfacile.web.views import (
    STEP_WHO,
    STEPS_BY_CONDITION,
    check_view,
    display_title,
    drafts_view,
    format_duration,
    format_number,
    progress_view,
    review_view,
    stop_reason,
)

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.globals.update(
    version=__version__,
    duration=format_duration,
    number=format_number,
    ui_languages=ui_languages,
    stop_reason=stop_reason,
)

router = APIRouter()
ONE_YEAR = 365 * 24 * 3600
LIST_LIMIT = 50  # rows the drafts list shows
STATUS_FILTERS = ("all", "needs_review", "running", "queued", "done", "failed")
FORM_CONDITIONS = ("P2", "P1", "P0")  # the pipelines the form offers, default first

# The reader view shows the export in the vendored Atkinson Hyperlegible Next. The
# exported file itself names the font first and falls back to Arial, without embedding it.
_LATIN = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, "
    "U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD"
)
_LATIN_EXT = (
    "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, "
    "U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, "
    "U+2C60-2C7F, U+A720-A7FF"
)
READER_FONTS = (
    "<style>\n"
    + "".join(
        f'@font-face {{ font-family: "Atkinson Hyperlegible Next"; font-weight: {weight}; '
        f"font-display: swap; src: url(/static/fonts/atkinson-hyperlegible-next-{subset}-"
        f'{weight}-normal.woff2) format("woff2"); unicode-range: {ranges}; }}\n'
        for weight in (400, 700)
        for subset, ranges in (("latin", _LATIN), ("latin-ext", _LATIN_EXT))
    )
    + "</style>\n"
)


def translator(request: Request) -> Translator:
    lang = pick_language(
        request.cookies.get(COOKIE),
        request.headers.get("accept-language"),
        request.app.state.settings.server.ui_lang,
    )
    return Translator(lang)


def _render(request: Request, name: str, status_code: int = 200, **context) -> HTMLResponse:
    t = context.get("t") or translator(request)  # built once, not once per call
    context["t"] = t
    # The switcher links back to this page; a page answering a POST goes to the start.
    here = request.url.path if request.method == "GET" else "/"
    if request.method == "GET" and request.url.query:
        here += f"?{request.url.query}"
    state = request.app.state
    context.setdefault("settings", state.settings)
    context.setdefault("review_count", state.store.count_jobs("needs_review"))
    context.update(ui_lang=t.lang, here=here)
    return TEMPLATES.TemplateResponse(request, name, context, status_code=status_code)


def _job_or_404(request: Request, job_id: str):
    job = request.app.state.store.get_job(job_id)
    if job is None:
        raise HTTPException(404, f"no job {job_id}")
    return job


@cache
def rule_count() -> int:
    """Rules code checks (the judge's rules are declared without a check and are not
    counted)."""
    return sum(1 for spec in RULES.values() if spec.checks)


@lru_cache(maxsize=4)
def _example_languages(folder: Path) -> dict[str, str]:
    """The detected language of each example letter, once per examples folder: the
    detection runs over the whole text and the files do not change while we run."""
    return {e["id"]: detect_language(e["text"])[0] or "" for e in example_sources(folder)}


def examples_for_page(t: Translator, folder: Path | None = None) -> list[dict[str, str]]:
    """The example letters with their language, for the New draft page and the empty
    list; `folder` is `settings.data.examples_dir`, else it is read from the settings."""
    folder = folder or examples_dir()
    langs = _example_languages(folder)
    out = []
    for example in example_sources(folder):
        lang = langs.get(example["id"], "")
        name = t.get(f"lang.{lang}", lang) if lang else ""
        out.append({**example, "lang": lang, "lang_name": name})
    return out


def _example(request: Request, example_id: str) -> dict[str, str] | None:
    folder = request.app.state.settings.data.examples_dir
    return next((e for e in example_sources(folder) if e["id"] == example_id), None)


def _list_url(status: str, q: str, lang: str) -> str:
    params = {k: v for k, v in (("status", status), ("q", q), ("lang", lang)) if v and v != "all"}
    return "/?" + urlencode(params) if params else "/"


@router.get("/", response_class=HTMLResponse)
def index(request: Request, status: str = "all", q: str = "", lang: str = "") -> HTMLResponse:
    """The drafts list: filters as GET parameters, so they work without JavaScript."""
    store = request.app.state.store
    t = translator(request)
    status = status if status in STATUS_FILTERS else "all"
    query = q.strip().casefold()
    total = store.count_jobs()
    settings = request.app.state.settings
    if query:
        # The title search stays in Python: SQLite's LIKE folds ASCII letters only.
        matching = [
            job
            for job in store.list_jobs(200, lang=lang or None)
            if query in display_title(job).casefold()
        ]
        counts = {k: sum(1 for j in matching if k in ("all", j.status)) for k in STATUS_FILTERS}
        shown = [j for j in matching if status in ("all", j.status)][:LIST_LIMIT]
    else:  # the filters and their counts in SQL (audit B3)
        by_status = store.status_counts(lang or None)
        counts = {k: by_status.get(k, 0) for k in STATUS_FILTERS}
        counts["all"] = sum(by_status.values())
        shown = store.list_jobs(
            LIST_LIMIT, status=None if status == "all" else status, lang=lang or None
        )
    filters = [
        {
            "key": key,
            "label": t("drafts.filter.all") if key == "all" else t(f"status.{key}"),
            "n": counts[key],
            "url": _list_url(key, q, lang),
            "current": key == status,
        }
        for key in STATUS_FILTERS
    ]
    return _render(
        request,
        "index.html",
        t=t,
        rows=drafts_view(store, shown, t),
        matching=counts[status],
        total=total,
        status=status,
        q=q,
        lang=lang,
        filtered=bool(query or lang or status != "all"),
        filters=filters,
        langs=store.langs(),
        # The empty state offers the example texts in the form.
        examples=examples_for_page(t, settings.data.examples_dir) if not total else [],
        rule_count=rule_count(),
        section="drafts",
        section_root=True,
    )


def _pipelines(t: Translator) -> list[dict]:
    """The pipelines the form offers, each with the stages it runs."""
    return [
        {
            "id": condition,
            "stages": [
                {"title": t(f"step.{key}.title"), "who": t(f"who.{STEP_WHO[key]}")}
                for key in STEPS_BY_CONDITION[condition]
            ],
        }
        for condition in FORM_CONDITIONS
    ]


def _new(
    request: Request, status_code: int = 200, error: str | None = None, form: dict | None = None
) -> HTMLResponse:
    t = translator(request)
    written = available_languages()
    form = form or {}
    return _render(
        request,
        "new.html",
        status_code,
        t=t,
        error=error,
        form=form,
        examples=examples_for_page(t, request.app.state.settings.data.examples_dir),
        doc_langs=[lang for lang in LANGS if lang in written],
        coming_langs=[lang for lang in LANGS if lang not in written],
        pipelines=_pipelines(t),
        endpoints=_endpoint_options(request.app.state),
        max_chars=MAX_TEXT_CHARS,
        chars=len(form.get("text") or ""),
        # Decision mode: the authority's notice, prefilled per document language.
        notice_defaults={lang: label(lang, "notice_default") for lang in LANGS if lang in written},
        section="new",
    )


@router.get("/new", response_class=HTMLResponse)
def new_draft(request: Request, example: str | None = None) -> HTMLResponse:
    """The form for a new draft; `?example=<id>` fills in one of the example letters."""
    found = _example(request, example) if example else None
    return _new(request, form=_example_form(found) if found else {})


def _endpoint_options(state) -> list[dict[str, str]]:
    """The endpoints a draft may pick, the one in use first, with the model names the
    form shows as placeholders; empty when there is no choice (the select stays away)."""
    found = [
        {
            "name": name,
            "label": llm.title,
            "writer": llm.models.writer,
            "understand": llm.understand_model,
            "judge": llm.judge_model,
        }
        for name, llm in state.orchestrator.endpoints()
    ]
    return found if len(found) > 1 else []


def _example_form(example: dict[str, str]) -> dict[str, str]:
    """The New draft form filled in with an example letter: its text and the decision
    mode's settings from the file next to it, if any."""
    settings = {k: example[k] for k in ("mode", "addressee", "notice") if example.get(k)}
    return {"text": example["text"], **settings}


def _refused(request: Request, exc: SubmissionError | QueueFull, form: dict) -> HTMLResponse:
    """The New draft form again, with the submission and why it was refused."""
    t = translator(request)
    if isinstance(exc, QueueFull):
        message = t("error.queue_full", n=request.app.state.settings.jobs.queue_limit)
    else:
        message = exc.text(t)
    busy = isinstance(exc, QueueFull | ServerBusy)  # 429: try again, nothing is wrong
    return _new(request, 429 if busy else 400, message, form)


# -- Check my text: the rules alone, on a text the writer wrote ---------------------------

CHECK_LANGS = ("de", "fr")  # the languages the checker has rules for


def _check(
    request: Request,
    form: dict,
    *,
    error: str | None = None,
    view=None,
    status_code: int = 200,
) -> HTMLResponse:
    return _render(
        request,
        "check.html",
        status_code,
        error=error,
        form=form,
        view=view,
        doc_langs=CHECK_LANGS,
        max_chars=MAX_TEXT_CHARS,
        chars=len(form.get("text") or ""),
        rules=rule_count(),
        section="check",
    )


@router.get("/check", response_class=HTMLResponse)
def check_page(request: Request) -> HTMLResponse:
    """The form: a text, its language and the level."""
    return _check(request, form={})


@router.post("/check", response_class=HTMLResponse)
def check_text(
    request: Request,
    text: Annotated[str, Form()] = "",
    lang: Annotated[str, Form()] = "auto",
    level: Annotated[str, Form()] = "A2",
) -> HTMLResponse:
    """The deterministic checker on the pasted text, as the CLI `check` runs it: one
    block per sentence, the rules of the document's language at the chosen level.
    No job, no model call, nothing stored; the page answers with the findings."""
    from leichtfacile.eval.calibrate import source_as_draft
    from leichtfacile.ingest import ingest_text
    from leichtfacile.ingest.errors import IngestError
    from leichtfacile.rules import check_draft

    t = translator(request)
    form = {"text": text, "lang": lang, "level": level}
    if not text.strip():
        return _check(request, form, error=t("check.error.empty"), status_code=400)
    if len(text) > MAX_TEXT_CHARS:
        error = SubmissionError("text_too_long", max=MAX_TEXT_CHARS).text(t)
        return _check(request, form, error=error, status_code=400)
    if level not in LEVELS:
        return _check(
            request,
            form,
            error=SubmissionError("unknown_level", level=level).text(t),
            status_code=400,
        )
    chosen = None if lang in ("", "auto") else lang
    if chosen is not None and chosen not in CHECK_LANGS:
        error = t("check.error.lang", lang=t.get(f"lang.{chosen}", chosen))
        return _check(request, form, error=error, status_code=400)
    try:
        doc = ingest_text(text, lang=chosen)
    except IngestError as exc:
        return _check(
            request, form, error=SubmissionError("ingest", detail=str(exc)).text(t), status_code=400
        )
    if doc.lang not in CHECK_LANGS:
        error = t("check.error.lang", lang=t.get(f"lang.{doc.lang}", doc.lang))
        return _check(request, form, error=error, status_code=400)
    draft = source_as_draft(doc, level)  # type: ignore[arg-type]
    view = check_view(draft, check_draft(draft), t)
    return _check(request, form, view=view)


@router.get("/ui/{lang}")
def set_ui_language(lang: str, next: str = "/") -> RedirectResponse:
    """The language switcher: remember the choice and go back to the page."""
    if lang not in ui_languages():
        raise HTTPException(404, f"no interface language {lang}")
    if not next.startswith("/") or next.startswith("//") or "\\" in next:
        next = "/"  # only paths on this site, never another host
    response = RedirectResponse(next, status_code=303)
    response.set_cookie(COOKIE, lang, max_age=ONE_YEAR, samesite="lax", httponly=True)
    return response


@router.post("/jobs", response_class=HTMLResponse)
async def submit(
    request: Request,
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
):
    data = await file.read() if file is not None and file.filename else None
    sub = Submission(
        text=text,
        url=url,
        file_name=file.filename if file else None,
        file_data=data,
        lang=lang,
        level=level,
        condition=condition,
        endpoint=endpoint,
        writer_model=(writer_model or "").strip() or None,
        understand_model=(understand_model or "").strip() or None,
        judge_model=(judge_model or "").strip() or None,
        title=title,
        mode=mode,
        addressee=addressee,
        notice=notice,
    )
    state = request.app.state
    try:  # fetch, parse and segment in the thread pool: a slow URL must not stop the server
        state.runner.ensure_room()
        job = await run_in_threadpool(
            create_job,
            state.store,
            state.settings,
            sub,
            state.ingest_slots,
            endpoints=state.orchestrator.clients,
        )
    except (SubmissionError, QueueFull) as exc:
        form = {
            "text": text or "",
            "url": url or "",
            "lang": lang,
            "level": level,
            "condition": condition,
            "endpoint": endpoint or "",
            "title": title or "",
            "writer_model": writer_model or "",
            "understand_model": understand_model or "",
            "judge_model": judge_model or "",
            "mode": mode,
            "addressee": addressee or "",
            "notice": notice or "",
        }
        return _refused(request, exc, form)
    state.runner.submit(job.id)
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str, version: int | None = None) -> HTMLResponse:
    state = request.app.state
    job = _job_or_404(request, job_id)
    t = translator(request)
    title = display_title(job)
    if job.status in ("needs_review", "done"):
        view = review_view(state.store, job, version, t)
        if view is not None:
            return _render(
                request,
                "review.html",
                job=job,
                v=view,
                t=t,
                title=title,
                section="drafts",
            )
    progress = progress_view(state.store, job, t=t)
    return _render(
        request,
        "job.html",
        job=job,
        job_llm=state.orchestrator.llm_for(job),
        p=progress,
        t=t,
        title=title,
        rule_count=rule_count(),
        section="drafts",
    )


@router.get("/jobs/{job_id}/progress", response_class=HTMLResponse)
def job_progress(request: Request, job_id: str) -> HTMLResponse:
    """The progress fragment the job page polls while the pipeline runs."""
    job = _job_or_404(request, job_id)
    t = translator(request)
    response = _render(
        request,
        "_progress.html",
        job=job,
        p=progress_view(request.app.state.store, job, t=t),
        t=t,
        rule_count=rule_count(),
    )
    response.headers["X-Job-Status"] = job.status
    response.headers["Cache-Control"] = "no-store"
    return response


def _reader_page(html: str) -> HTMLResponse:
    """The export as the reader view shows it: with the vendored reader font."""
    return HTMLResponse(html.replace("</head>", READER_FONTS + "</head>", 1))


@router.get("/jobs/{job_id}/preview", response_class=HTMLResponse)
def preview(request: Request, job_id: str, version: int | None = None) -> HTMLResponse:
    """The draft as a reader gets it: the HTML export shown in the browser."""
    job = _job_or_404(request, job_id)
    store = request.app.state.store
    if version is None:
        summary = store.get_artifact(job_id, "summary", PipelineSummary)
        version = summary.final_version if summary else None
    draft = store.get_artifact(job_id, "draft", Draft, version=version)
    if draft is None:
        raise HTTPException(404, "the job has no draft yet")
    review = store.get_artifact(job_id, "review", ReviewState)
    return _reader_page(to_html(draft, review, title=job.title, notice=job.config.notice))


@router.post("/jobs/{job_id}/preview", response_class=HTMLResponse)
def preview_unsaved(request: Request, job_id: str, body: ReviewIn) -> HTMLResponse:
    """The reader view of the decisions on screen, saved or not. Nothing is stored."""
    job = _job_or_404(request, job_id)
    draft = request.app.state.store.get_artifact(job_id, "draft", Draft, version=body.draft_version)
    if draft is None:
        raise HTTPException(404, f"no draft version {body.draft_version}")
    review = None
    if body.decisions:
        review = ReviewState(
            draft_version=body.draft_version,
            decisions=[Decision(**d.model_dump()) for d in body.decisions],
            completed=body.completed,
        )
    return _reader_page(to_html(draft, review, title=job.title, notice=job.config.notice))


@router.post("/jobs/{job_id}/rerun")
def rerun_page(request: Request, job_id: str, stage: Annotated[str, Form()] = "understand"):
    state = request.app.state
    _job_or_404(request, job_id)
    try:
        state.orchestrator.rerun(job_id, stage)
    except JobBusy as exc:
        raise HTTPException(409, BUSY) from exc
    except PipelineError as exc:
        raise HTTPException(400, str(exc)) from exc
    state.runner.submit(job_id)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@router.post("/jobs/{job_id}/cancel")
def cancel_page(request: Request, job_id: str):
    """The Stop button of the job page: the page then shows the stopped job."""
    _job_or_404(request, job_id)
    request.app.state.runner.cancel(job_id)  # None when it ended meanwhile: nothing to do
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@router.post("/jobs/{job_id}/delete")
def delete_page(request: Request, job_id: str):
    state = request.app.state
    if not remove_job(state.store, state.llm, job_id) and state.store.get_job(job_id):
        raise HTTPException(409, BUSY)
    return RedirectResponse("/", status_code=303)
