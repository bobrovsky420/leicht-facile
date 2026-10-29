"""JSON API (docs/architecture.md §7)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from leichtfacile.export import glossary_ids
from leichtfacile.export.bundle import build_bundle
from leichtfacile.export.docx import DOCX_TYPE, to_docx
from leichtfacile.export.html import to_html
from leichtfacile.export.layout import build_layout
from leichtfacile.export.markdown import to_markdown
from leichtfacile.lifecycle import job_counts, remove_job
from leichtfacile.llm.client import LLMError
from leichtfacile.pipeline import stages
from leichtfacile.pipeline.orchestrator import ARTIFACTS_FROM, JobBusy, PipelineError
from leichtfacile.pipeline.prompts import PromptNotAvailable
from leichtfacile.pipeline.runner import QueueFull
from leichtfacile.schemas import (
    Decision,
    Draft,
    FactSheet,
    PipelineSummary,
    ReviewState,
    SourceDocument,
    utcnow,
)
from leichtfacile.web.i18n import COOKIE, Translator, pick_language
from leichtfacile.web.jobs import (
    ServerBusy,
    Submission,
    SubmissionError,
    start_job,
    submission_form,
)
from leichtfacile.web.views import finding_text

router = APIRouter(prefix="/api")
ARTIFACT_NAMES = (
    "source", "factsheet", "draft", "rules", "judge", "repair", "review", "summary",
)  # fmt: skip


# Bounds on what a review may carry: an edit is a sentence or a short paragraph, a
# comment a note; beyond them a body is a mistake or an attack, not a review.
MAX_EDIT_CHARS = 10_000
MAX_COMMENT_CHARS = 2_000
MAX_DECISIONS = 2_000
MAX_LIST_LIMIT = 200


class DecisionIn(BaseModel):
    block_id: str = Field(max_length=16)
    decision: Literal["approved", "edited", "rejected"]
    text: str | None = Field(default=None, max_length=MAX_EDIT_CHARS)
    comment: str | None = Field(default=None, max_length=MAX_COMMENT_CHARS)


class ReviewIn(BaseModel):
    draft_version: int = Field(ge=1)
    decisions: list[DecisionIn] = Field(default_factory=list, max_length=MAX_DECISIONS)
    completed: bool = False
    # The `saved_at` of the review the client loaded (null: it saw none). When the
    # field is sent and the stored review was saved at another time, the save is
    # refused with 409 so that two reviewers never overwrite each other unseen.
    saved_at: datetime | None = None


BUSY = "the job is running; stop it first"


def _state(request: Request):
    return request.app.state


def _job_or_404(request: Request, job_id: str):
    job = _state(request).store.get_job(job_id)
    if job is None:
        raise HTTPException(404, f"no job {job_id}")
    return job


@router.post("/jobs", status_code=201)
async def post_job(request: Request, sub: Annotated[Submission, Depends(submission_form)]) -> dict:
    """Create a job from pasted text, a URL or an uploaded file (the multipart form of
    `web/jobs.py: submission_form`, the New draft form's fields)."""
    try:
        job = await start_job(_state(request), sub)
    except QueueFull as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": "60"}) from exc
    except ServerBusy as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": "5"}) from exc
    except SubmissionError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"id": job.id, "status": "queued", "links": _links(job.id)}


@router.get("/jobs")
def list_jobs(
    request: Request, limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = 50
) -> list[dict]:
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
    known = set(draft.by_id()) | set(glossary_ids(draft))  # g01, g02: glossary entries
    unknown = [d.block_id for d in body.decisions if d.block_id not in known]
    if unknown:
        raise HTTPException(400, f"unknown blocks: {', '.join(unknown)}")
    for d in body.decisions:
        if d.decision == "edited" and not (d.text and d.text.strip()):
            raise HTTPException(400, f"block {d.block_id}: an edit needs a text")
    if "saved_at" in body.model_fields_set:
        stored = store.get_artifact(job_id, "review", ReviewState)
        current = stored.saved_at if stored else None
        if current != body.saved_at:
            raise HTTPException(
                409,
                "the review was saved by someone else since this page was loaded"
                + (f" (at {current.isoformat(timespec='seconds')})" if current else "")
                + "; reload the page to see their decisions",
            )
    review = ReviewState(
        draft_version=body.draft_version,
        decisions=[Decision(**d.model_dump()) for d in body.decisions],
        completed=body.completed,
        saved_at=utcnow(),
    )
    store.put_artifact(job_id, "review", review)
    fields: dict[str, object] = {"counts": job_counts(store, job)}
    if job.status in ("needs_review", "done"):
        fields["status"] = "done" if body.completed else "needs_review"
    store.update_job(job_id, **fields)
    return {
        "saved": len(review.decisions),
        "completed": review.completed,
        "saved_at": review.saved_at.isoformat() if review.saved_at else None,
    }


@router.api_route("/jobs/{job_id}/export", methods=["GET", "POST"])
def export(
    request: Request,
    job_id: str,
    format: Annotated[Literal["md", "html", "docx", "json"], Query()] = "md",
    version: int | None = None,
) -> Response:
    job = _job_or_404(request, job_id)
    store = _state(request).store
    if format == "json":
        body = json.dumps(build_bundle(store, job), ensure_ascii=False, indent=2)
        return _download(body, "application/json", f"{job_id}-audit.json")
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    if version is None:
        version = summary.final_version if summary else None
    draft = store.get_artifact(job_id, "draft", Draft, version=version)
    if draft is None:
        raise HTTPException(409, "the job has no draft yet")
    review = store.get_artifact(job_id, "review", ReviewState)
    layout = build_layout(draft, review, title=job.title, notice=job.config.notice)
    if format == "md":
        return _download(to_markdown(layout), "text/markdown", f"{job_id}.md")
    if format == "docx":
        return _download(to_docx(layout, summary=summary), DOCX_TYPE, f"{job_id}.docx")
    return _download(to_html(layout), "text/html", f"{job_id}.html")


@router.post("/jobs/{job_id}/facts/{fact_id}/recover")
def recover(request: Request, job_id: str, fact_id: str, version: int | None = None) -> dict:
    """Sentences for a missing fact from its source paragraph, one writer call
    (stages.recover_fact). Nothing is stored but the call's usage: the reviewer adds the
    sentences to a block, as an edit, or leaves them. The rule findings come in the
    interface language."""
    job = _job_or_404(request, job_id)
    state = _state(request)
    store = state.store
    if version is None:
        summary = store.get_artifact(job_id, "summary", PipelineSummary)
        version = summary.final_version if summary else None
    source = store.get_artifact(job_id, "source", SourceDocument)
    factsheet = store.get_artifact(job_id, "factsheet", FactSheet)
    draft = store.get_artifact(job_id, "draft", Draft, version=version)
    if source is None or factsheet is None or draft is None:
        raise HTTPException(409, "the job has no draft yet")
    if fact_id not in factsheet.fact_ids():
        raise HTTPException(404, f"no fact {fact_id}")
    try:
        llm = state.orchestrator.client_for(job)  # the job's endpoint, as the pipeline's
    except PipelineError as exc:
        raise HTTPException(409, str(exc)) from exc
    try:
        with llm.recording(lambda usage: store.add_usage(job_id, usage)):
            rec, results = stages.recover_fact(
                llm, source, factsheet, draft, fact_id, model=job.config.writer_model
            )
    except PromptNotAvailable as exc:
        raise HTTPException(400, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(502, f"the model endpoint failed: {exc}") from exc
    t = Translator(
        pick_language(
            request.cookies.get(COOKIE),
            request.headers.get("accept-language"),
            state.settings.server.ui_lang,
        ),
        state.settings.texts.region,  # the installation's variety, as the pages
    )
    fact = next(f for f in factsheet.facts if f.id == fact_id)
    segments = source.by_id()
    return {
        "fact_id": fact_id,
        "draft_version": draft.version,
        "block_id": rec.block_id,
        "texts": rec.texts,
        "resolved": rec.resolved,
        "rejected": rec.rejected,
        "foreign": rec.foreign,
        "dropped": rec.dropped,
        "findings": [
            {"rule_id": f.rule_id, "severity": f.severity, "message": finding_text(t, f)}
            for f in rec.findings
        ],
        "source": [{"id": i, "text": segments[i].text} for i in fact.segment_ids if i in segments],
        "calls": len(results),
    }


@router.post("/jobs/{job_id}/rerun")
def rerun(
    request: Request, job_id: str, from_: Annotated[str, Query(alias="from")] = "understand"
) -> dict:
    _job_or_404(request, job_id)
    state = _state(request)
    try:
        state.orchestrator.rerun(job_id, from_)
    except JobBusy as exc:
        raise HTTPException(409, BUSY) from exc
    except PipelineError as exc:
        raise HTTPException(400, str(exc)) from exc
    state.runner.submit(job_id)
    return {"id": job_id, "status": "queued", "from": from_, "stages": sorted(ARTIFACTS_FROM)}


@router.post("/jobs/{job_id}/cancel")
def cancel(request: Request, job_id: str) -> dict:
    """Stop the job: a waiting one leaves the queue (`cancelled`), a running one ends at
    its next stage, model attempt or streamed chunk (`stopping`). Either way it is then
    `failed` with the error `cancelled` and keeps the stages that finished; `rerun`
    takes it up again."""
    _job_or_404(request, job_id)
    outcome = _state(request).runner.cancel(job_id)
    if outcome is None:
        raise HTTPException(409, f"job {job_id} is neither queued nor running")
    return {"id": job_id, "status": outcome}


@router.delete("/jobs/{job_id}")
def delete(request: Request, job_id: str) -> dict:
    _job_or_404(request, job_id)
    state = _state(request)
    if not remove_job(state.store, state.registry.llm, job_id):
        raise HTTPException(409, BUSY)
    return {"deleted": job_id}


def _download(body: str | bytes, media_type: str, filename: str) -> Response:
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if isinstance(body, bytes):  # a binary file (DOCX): no charset
        return Response(body, media_type=media_type, headers=headers)
    cls = {"text/html": HTMLResponse, "application/json": Response}.get(
        media_type, PlainTextResponse
    )
    return cls(body, media_type=f"{media_type}; charset=utf-8", headers=headers)


def _links(job_id: str) -> dict:
    return {
        "self": f"/api/jobs/{job_id}",
        "page": f"/jobs/{job_id}",
        "export_md": f"/api/jobs/{job_id}/export?format=md",
        "export_html": f"/api/jobs/{job_id}/export?format=html",
        "export_docx": f"/api/jobs/{job_id}/export?format=docx",
        "export_json": f"/api/jobs/{job_id}/export?format=json",
    }
