"""JSON API (docs/architecture.md §7)."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from leichtfacile.export.bundle import build_bundle
from leichtfacile.export.html import to_html
from leichtfacile.export.markdown import to_markdown
from leichtfacile.pipeline.orchestrator import ARTIFACTS_FROM, PipelineError
from leichtfacile.schemas import Decision, Draft, PipelineSummary, ReviewState
from leichtfacile.web.jobs import Submission, SubmissionError, create_job

router = APIRouter(prefix="/api")
ARTIFACT_NAMES = ("source", "factsheet", "draft", "rules", "judge", "review", "summary")


class DecisionIn(BaseModel):
    block_id: str
    decision: Literal["approved", "edited", "rejected"]
    text: str | None = None
    comment: str | None = None


class ReviewIn(BaseModel):
    draft_version: int
    decisions: list[DecisionIn] = Field(default_factory=list)
    completed: bool = False


def _state(request: Request):
    return request.app.state


def _job_or_404(request: Request, job_id: str):
    job = _state(request).store.get_job(job_id)
    if job is None:
        raise HTTPException(404, f"no job {job_id}")
    return job


@router.post("/jobs", status_code=201)
async def post_job(
    request: Request,
    text: Annotated[str | None, Form()] = None,
    url: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    lang: Annotated[str | None, Form()] = None,
    level: Annotated[str, Form()] = "A2",
    condition: Annotated[str, Form()] = "P2",
    writer_model: Annotated[str | None, Form()] = None,
    understand_model: Annotated[str | None, Form()] = None,
    judge_model: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form()] = None,
) -> dict:
    """Create a job from pasted text, a URL or an uploaded file (multipart form)."""
    data = await file.read() if file is not None and file.filename else None
    sub = Submission(
        text=text,
        url=url,
        file_name=file.filename if file is not None else None,
        file_data=data,
        lang=lang,
        level=level,
        condition=condition,
        writer_model=writer_model,
        understand_model=understand_model,
        judge_model=judge_model,
        title=title,
    )
    state = _state(request)
    try:
        job = create_job(state.store, state.settings, sub)
    except SubmissionError as exc:
        raise HTTPException(400, str(exc)) from exc
    state.runner.submit(job.id)
    return {"id": job.id, "status": "queued", "links": _links(job.id)}


@router.get("/jobs")
def list_jobs(request: Request, limit: int = 50) -> list[dict]:
    return [
        {"id": j.id, "title": j.title, "status": j.status, "stage": j.stage,
         "created_at": j.created_at.isoformat(), "condition": j.config.condition}
        for j in _state(request).store.list_jobs(limit)
    ]  # fmt: skip


@router.get("/jobs/{job_id}")
def get_job(request: Request, job_id: str) -> dict:
    job = _job_or_404(request, job_id)
    store = _state(request).store
    usage = job.usage
    return {
        **job.model_dump(mode="json", exclude={"usage"}),
        "usage": {
            "calls": len(usage),
            "tokens_in": sum(u.tokens_in for u in usage),
            "tokens_out": sum(u.tokens_out for u in usage),
            "latency_ms": sum(u.latency_ms for u in usage),
            "by_call": [u.model_dump() for u in usage],
        },
        "artifacts": store.artifact_names(job_id),
        "links": _links(job_id),
    }


@router.get("/jobs/{job_id}/artifacts/{name}")
def get_artifact(
    request: Request, job_id: str, name: str, version: int | None = None
) -> JSONResponse:
    _job_or_404(request, job_id)
    if name not in ARTIFACT_NAMES:
        raise HTTPException(404, f"unknown artifact {name!r}; use one of {ARTIFACT_NAMES}")
    data = _state(request).store.get_artifact_json(job_id, name, version)
    if data is None:
        raise HTTPException(
            404, f"job {job_id} has no {name} artifact" + (f" v{version}" if version else "")
        )
    return JSONResponse(data)


@router.post("/jobs/{job_id}/review")
def post_review(request: Request, job_id: str, body: ReviewIn) -> dict:
    job = _job_or_404(request, job_id)
    store = _state(request).store
    draft = store.get_artifact(job_id, "draft", Draft, version=body.draft_version)
    if draft is None:
        raise HTTPException(400, f"no draft version {body.draft_version}")
    known = set(draft.by_id())
    unknown = [d.block_id for d in body.decisions if d.block_id not in known]
    if unknown:
        raise HTTPException(400, f"unknown blocks: {', '.join(unknown)}")
    for d in body.decisions:
        if d.decision == "edited" and not (d.text and d.text.strip()):
            raise HTTPException(400, f"block {d.block_id}: an edit needs a text")
    review = ReviewState(
        draft_version=body.draft_version,
        decisions=[Decision(**d.model_dump()) for d in body.decisions],
        completed=body.completed,
    )
    store.put_artifact(job_id, "review", review)
    if job.status in ("needs_review", "done"):
        store.update_job(job_id, status="done" if body.completed else "needs_review")
    return {"saved": len(review.decisions), "completed": review.completed}


@router.api_route("/jobs/{job_id}/export", methods=["GET", "POST"])
def export(
    request: Request,
    job_id: str,
    format: Annotated[Literal["md", "html", "json"], Query()] = "md",
    version: int | None = None,
) -> Response:
    job = _job_or_404(request, job_id)
    store = _state(request).store
    if format == "json":
        body = json.dumps(build_bundle(store, job), ensure_ascii=False, indent=2)
        return _download(body, "application/json", f"{job_id}-audit.json")
    if version is None:
        summary = store.get_artifact(job_id, "summary", PipelineSummary)
        version = summary.final_version if summary else None
    draft = store.get_artifact(job_id, "draft", Draft, version=version)
    if draft is None:
        raise HTTPException(409, "the job has no draft yet")
    review = store.get_artifact(job_id, "review", ReviewState)
    if format == "md":
        return _download(
            to_markdown(draft, review, title=job.title), "text/markdown", f"{job_id}.md"
        )
    return _download(to_html(draft, review, title=job.title), "text/html", f"{job_id}.html")


@router.post("/jobs/{job_id}/rerun")
def rerun(
    request: Request, job_id: str, from_: Annotated[str, Query(alias="from")] = "understand"
) -> dict:
    _job_or_404(request, job_id)
    state = _state(request)
    try:
        state.orchestrator.rerun(job_id, from_)
    except PipelineError as exc:
        raise HTTPException(400, str(exc)) from exc
    state.runner.submit(job_id)
    return {"id": job_id, "status": "queued", "from": from_, "stages": sorted(ARTIFACTS_FROM)}


@router.delete("/jobs/{job_id}")
def delete(request: Request, job_id: str) -> dict:
    _job_or_404(request, job_id)
    _state(request).store.delete_job(job_id)
    return {"deleted": job_id}


def _download(body: str, media_type: str, filename: str) -> Response:
    cls = {"text/html": HTMLResponse, "application/json": Response}.get(
        media_type, PlainTextResponse
    )
    return cls(
        body,
        media_type=f"{media_type}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _links(job_id: str) -> dict:
    return {
        "self": f"/api/jobs/{job_id}",
        "page": f"/jobs/{job_id}",
        "export_md": f"/api/jobs/{job_id}/export?format=md",
        "export_html": f"/api/jobs/{job_id}/export?format=html",
        "export_json": f"/api/jobs/{job_id}/export?format=json",
    }
