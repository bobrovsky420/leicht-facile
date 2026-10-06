"""Server-rendered pages: start page, job progress, review, reader preview."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from leichtfacile import __version__
from leichtfacile.examples import example_sources
from leichtfacile.export.html import to_html
from leichtfacile.pipeline.orchestrator import PipelineError
from leichtfacile.rules.base import RULES
from leichtfacile.schemas import Draft, PipelineSummary, ReviewState
from leichtfacile.web.jobs import Submission, SubmissionError, create_job
from leichtfacile.web.views import (
    CONDITION_LABELS,
    LANG_NAMES,
    STAGE_LABELS,
    format_duration,
    progress_view,
    review_view,
)

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.globals.update(
    version=__version__,
    stage_labels=STAGE_LABELS,
    condition_labels=CONDITION_LABELS,
    lang_names=LANG_NAMES,
    duration=format_duration,
)

router = APIRouter()


def _render(request: Request, name: str, status_code: int = 200, **context) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, name, context, status_code=status_code)


def _job_or_404(request: Request, job_id: str):
    job = request.app.state.store.get_job(job_id)
    if job is None:
        raise HTTPException(404, f"no job {job_id}")
    return job


def rule_count() -> int:
    """Rules code checks, counted once across the language variants (the judge's rules
    are declared without a check function and are not counted)."""
    return len(
        {
            rule_id.removesuffix("-DE").removesuffix("-FR")
            for rule_id, spec in RULES.items()
            if spec.check
        }
    )


def _index(
    request: Request, status_code: int = 200, error: str | None = None, form: dict | None = None
) -> HTMLResponse:
    state = request.app.state
    return _render(
        request,
        "index.html",
        status_code,
        jobs=state.store.list_jobs(50),
        settings=state.settings,
        error=error,
        form=form or {},
        examples=example_sources(),
        rule_count=rule_count(),
    )


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return _index(request)


@router.post("/jobs", response_class=HTMLResponse)
async def submit(
    request: Request,
    text: Annotated[str | None, Form()] = None,
    url: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    lang: Annotated[str | None, Form()] = None,
    level: Annotated[str, Form()] = "A2",
    condition: Annotated[str, Form()] = "C2",
    title: Annotated[str | None, Form()] = None,
    writer_model: Annotated[str | None, Form()] = None,
    judge_model: Annotated[str | None, Form()] = None,
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
        writer_model=(writer_model or "").strip() or None,
        judge_model=(judge_model or "").strip() or None,
        title=title,
    )
    state = request.app.state
    try:
        job = create_job(state.store, state.settings, sub)
    except SubmissionError as exc:
        form = {
            "text": text or "",
            "url": url or "",
            "lang": lang,
            "level": level,
            "condition": condition,
            "title": title or "",
            "writer_model": writer_model or "",
            "judge_model": judge_model or "",
        }
        return _index(request, 400, str(exc), form)
    state.runner.submit(job.id)
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str, version: int | None = None) -> HTMLResponse:
    state = request.app.state
    job = _job_or_404(request, job_id)
    if job.status in ("needs_review", "done"):
        view = review_view(state.store, job, version)
        if view is not None:
            return _render(request, "review.html", job=job, v=view)
    return _render(request, "job.html", job=job, p=progress_view(state.store, job))


@router.get("/jobs/{job_id}/progress", response_class=HTMLResponse)
def job_progress(request: Request, job_id: str) -> HTMLResponse:
    """The progress fragment the job page polls while the pipeline runs."""
    job = _job_or_404(request, job_id)
    response = _render(
        request, "_progress.html", job=job, p=progress_view(request.app.state.store, job)
    )
    response.headers["X-Job-Status"] = job.status
    response.headers["Cache-Control"] = "no-store"
    return response


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
    return HTMLResponse(to_html(draft, review, title=job.title))


@router.post("/jobs/{job_id}/rerun")
def rerun_page(request: Request, job_id: str, stage: Annotated[str, Form()] = "understand"):
    state = request.app.state
    _job_or_404(request, job_id)
    try:
        state.orchestrator.rerun(job_id, stage)
    except PipelineError as exc:
        raise HTTPException(400, str(exc)) from exc
    state.runner.submit(job_id)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@router.post("/jobs/{job_id}/delete")
def delete_page(request: Request, job_id: str):
    request.app.state.store.delete_job(job_id)
    return RedirectResponse("/", status_code=303)
