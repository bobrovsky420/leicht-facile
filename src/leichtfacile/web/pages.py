"""Server-rendered pages: start page, job progress, review."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from leichtfacile import __version__
from leichtfacile.pipeline.orchestrator import PipelineError
from leichtfacile.web.jobs import Submission, SubmissionError, create_job
from leichtfacile.web.views import STAGE_LABELS, review_view

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.globals.update(version=__version__, stage_labels=STAGE_LABELS)

router = APIRouter()


def _render(request: Request, name: str, status_code: int = 200, **context) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, name, context, status_code=status_code)


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    state = request.app.state
    return _render(
        request,
        "index.html",
        jobs=state.store.list_jobs(50),
        settings=state.settings,
        error=None,
        form={},
    )


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
):
    data = await file.read() if file is not None and file.filename else None
    sub = Submission(
        text=text, url=url, file_name=file.filename if file else None, file_data=data,
        lang=lang, level=level, condition=condition, title=title,
    )  # fmt: skip
    state = request.app.state
    try:
        job = create_job(state.store, state.settings, sub)
    except SubmissionError as exc:
        form = {"text": text or "", "url": url or "", "lang": lang, "level": level,
                "condition": condition, "title": title or ""}  # fmt: skip
        return _render(
            request, "index.html", 400, jobs=state.store.list_jobs(50), settings=state.settings,
            error=str(exc), form=form,
        )  # fmt: skip
    state.runner.submit(job.id)
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str, version: int | None = None) -> HTMLResponse:
    state = request.app.state
    job = state.store.get_job(job_id)
    if job is None:
        raise HTTPException(404, f"no job {job_id}")
    if job.status in ("needs_review", "done"):
        view = review_view(state.store, job, version)
        if view is not None:
            return _render(request, "review.html", job=job, v=view)
    return _render(request, "job.html", job=job)


@router.post("/jobs/{job_id}/rerun")
def rerun_page(request: Request, job_id: str, stage: Annotated[str, Form()] = "understand"):
    state = request.app.state
    if state.store.get_job(job_id) is None:
        raise HTTPException(404, f"no job {job_id}")
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
