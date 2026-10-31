"""Server-rendered pages: drafts list, new draft, job progress, review, reader preview.

Every page is rendered in the reviewer's interface language (`i18n.py`): the choice
from the switcher in the header (a cookie), else `server.ui_lang`, else the browser's,
written as the installation's variety writes it (`texts.region`: the overlays of
Germany and Austria, the country the texts name, the thousands of a count).
The layout and its parts are specified in docs/ui-design.md."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from leichtfacile import __version__
from leichtfacile.examples import example_sources, examples_dir
from leichtfacile.export.html import to_html
from leichtfacile.export.layout import build_layout
from leichtfacile.pipeline.prompts import available_languages
from leichtfacile.pipeline.runner import QueueFull
from leichtfacile.rules.base import RULES, checked_languages
from leichtfacile.schemas import LANGS, LEVELS, Decision, Draft, PipelineSummary, ReviewState
from leichtfacile.varieties import region_for, variety
from leichtfacile.web import api
from leichtfacile.web.i18n import COOKIE, Translator, pick_language, ui_languages
from leichtfacile.web.jobs import (
    MAX_TEXT_CHARS,
    ServerBusy,
    Submission,
    SubmissionError,
    start_job,
    submission_form,
)
from leichtfacile.web.views import (
    EXPORT_FORMATS,
    STEP_WHO,
    STEPS_BY_CONDITION,
    check_view,
    display_title,
    drafts_view,
    format_duration,
    progress_view,
    review_view,
    stop_reason,
)

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.globals.update(
    version=__version__,
    duration=format_duration,
    ui_languages=ui_languages,
    stop_reason=stop_reason,
    export_formats=EXPORT_FORMATS,
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
    """The reviewer's interface language in the installation's variety (`texts.region`)."""
    settings = request.app.state.settings
    lang = pick_language(
        request.cookies.get(COOKIE),
        request.headers.get("accept-language"),
        settings.server.ui_lang,
    )
    return Translator(lang, settings.texts.region)


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
    # The app bar: the preset in use and whether it is ready; the link to the model
    # page, unless an organisation offers one preset alone (web/model.py).
    context.setdefault("model_ready", state.registry.is_ready())
    context.setdefault("model_page", len(state.settings.llm.offer) != 1)
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


def examples_for_page(t: Translator, folder: Path | None = None) -> list[dict[str, str]]:
    """The example letters the installation offers (those of its region, `t.region`)
    with their language's name, for the New draft page and the empty list; `folder` is
    `settings.data.examples_dir`, else it is read from the settings."""
    out = []
    for example in example_sources(folder or examples_dir(), t.region):
        lang = example["lang"]
        region = example.get("region") or region_for(lang, t.region)
        out.append({**example, "lang_name": t.language(lang, region) if lang else ""})
    return out


def _example(request: Request, example_id: str) -> dict[str, str] | None:
    """An example letter the installation offers, by its id; None for any other."""
    settings = request.app.state.settings
    found = example_sources(settings.data.examples_dir, settings.texts.region)
    return next((e for e in found if e["id"] == example_id), None)


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
        # Decision mode: the authority's notice, prefilled per document language, in the
        # installation's variety (texts.region).
        notice_defaults={
            lang: variety(lang, request.app.state.settings.texts.region).notice
            for lang in LANGS
            if lang in written
        },
        section="new",
    )


@router.get("/new", response_class=HTMLResponse)
def new_draft(request: Request, example: str | None = None) -> HTMLResponse:
    """The form for a new draft; `?example=<id>` fills in one of the example letters."""
    found = _example(request, example) if example else None
    return _new(request, form=_example_form(found) if found else {})


def _endpoint_options(state) -> list[dict[str, str]]:
    """The ready presets a draft may pick, the one in use first, with the model names
    the form shows as placeholders; empty when there is no choice (the select stays
    away)."""
    found = [
        {
            "name": name,
            "label": llm.title,
            "provider": llm.provider_label or "",
            "documents": llm.documents,
            "writer": llm.models.writer,
            "understand": llm.understand_model,
            "judge": llm.judge_model,
        }
        for name, llm in state.registry.ready()
    ]
    return found if len(found) > 1 else []


def _example_form(example: dict[str, str]) -> dict[str, str]:
    """The New draft form filled in with an example letter: its text and the decision
    mode's settings from the file next to it, if any."""
    keys = ("mode", "addressee", "notice", "sender", "address")
    settings = {k: example[k] for k in keys if example.get(k)}
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


@cache
def check_langs() -> tuple[str, ...]:
    """The languages the checker has rules for: the Check page offers them."""
    import leichtfacile.rules  # noqa: F401  (registers the rules)

    return checked_languages()


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
        doc_langs=check_langs(),
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
    from leichtfacile.ingest import ingest_text
    from leichtfacile.ingest.errors import IngestError
    from leichtfacile.rules import check_draft, source_as_draft

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
    if chosen is not None and chosen not in check_langs():
        error = t("check.error.lang", lang=t.get(f"lang.{chosen}", chosen))
        return _check(request, form, error=error, status_code=400)
    try:
        doc = ingest_text(text, lang=chosen)
    except IngestError as exc:
        return _check(
            request, form, error=SubmissionError("ingest", detail=str(exc)).text(t), status_code=400
        )
    if doc.lang not in check_langs():
        error = t("check.error.lang", lang=t.get(f"lang.{doc.lang}", doc.lang))
        return _check(request, form, error=error, status_code=400)
    region = region_for(doc.lang, request.app.state.settings.texts.region)
    doc = doc.model_copy(update={"region": region})  # checked in the installation's variety
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
async def submit(request: Request, sub: Annotated[Submission, Depends(submission_form)]):
    """The New draft form: the API's submission (`web/jobs.py`), then the job page; a
    refused submission renders the form again with the reason."""
    try:
        job = await start_job(request.app.state, sub)
    except (SubmissionError, QueueFull) as exc:
        return _refused(request, exc, sub.form())
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
    layout = build_layout(draft, review, title=job.title, notice=job.config.notice)
    return _reader_page(to_html(layout))


@router.post("/jobs/{job_id}/preview", response_class=HTMLResponse)
def preview_unsaved(request: Request, job_id: str, body: api.ReviewIn) -> HTMLResponse:
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
    layout = build_layout(draft, review, title=job.title, notice=job.config.notice)
    return _reader_page(to_html(layout))


# The forms of the job and review pages do what the API routes do (api.py), then go
# back to the page: one handler per action, the page's answer a redirect.


@router.post("/jobs/{job_id}/rerun")
def rerun_page(request: Request, job_id: str, stage: Annotated[str, Form()] = "understand"):
    api.rerun(request, job_id, stage)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@router.post("/jobs/{job_id}/cancel")
def cancel_page(request: Request, job_id: str):
    """The Stop button of the job page: the page then shows the stopped job; a job that
    ended meanwhile is nothing to stop."""
    try:
        api.cancel(request, job_id)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@router.post("/jobs/{job_id}/delete")
def delete_page(request: Request, job_id: str):
    api.delete(request, job_id)
    return RedirectResponse("/", status_code=303)
