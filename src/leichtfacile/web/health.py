"""Liveness and readiness.

`GET /healthz` answers from the process alone: the Docker health check, the browser
opener of `make run` and a load balancer ask it every few seconds, and none of them
should make the server call the paid model endpoint with the organisation's key.

`GET /readyz` adds the model endpoint: reachable, and are the configured models
listed. The endpoint is asked at most once per `READY_CACHE_S` seconds, whoever asks
and however often (one lock, so concurrent callers wait for one answer instead of each
making a call), and the answer carries booleans and the configured names, never the
endpoint's catalogue. The service stays `200` while it runs, `status` says `ok` or
`degraded`: the review pages, the exports and the checker work without the endpoint.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Request

from leichtfacile import __version__
from leichtfacile.llm.client import LLMClient

log = logging.getLogger(__name__)
router = APIRouter()
READY_CACHE_S = 30.0


@dataclass(frozen=True)
class EndpointStatus:
    reachable: bool
    checked_at: datetime
    models: list[str] = field(default_factory=list)  # kept here, never answered
    error: str | None = None


class EndpointCheck:
    """`llm.list_models()` at most once per `ttl_s` seconds."""

    def __init__(
        self,
        llm: LLMClient,
        ttl_s: float = READY_CACHE_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.llm = llm
        self.ttl_s = ttl_s
        self._clock = clock
        self._lock = threading.Lock()
        self._status: EndpointStatus | None = None
        self._at = -float("inf")

    def status(self) -> EndpointStatus:
        with self._lock:
            now = self._clock()
            if self._status is None or now - self._at >= self.ttl_s:
                self._status = self._check()
                self._at = now
            return self._status

    def _check(self) -> EndpointStatus:
        try:
            models = self.llm.list_models()
        except Exception as exc:  # any failure is reported, never raised
            log.warning("LLM endpoint check failed: %s", type(exc).__name__)
            return EndpointStatus(False, datetime.now(UTC), error=_error_text(exc))
        return EndpointStatus(True, datetime.now(UTC), models)


@router.get("/healthz")
def healthz() -> dict:
    """Liveness: the process answers. No call leaves the server."""
    return {"status": "ok", "version": __version__}


@router.get("/readyz")
def readyz(request: Request) -> dict:
    """Readiness: liveness plus the cached check of the model endpoint."""
    settings = request.app.state.settings
    status: EndpointStatus = request.app.state.endpoint_check.status()
    llm: dict = {
        "base_url": _host_only(settings.llm_base_url),
        "model": settings.llm_name,
        "judge_model": settings.judge_name,
        "reachable": status.reachable,
        "checked_at": status.checked_at.isoformat(timespec="seconds"),
    }
    if settings.llm_understand_name:
        llm["understand_model"] = settings.understand_name
    ready = status.reachable
    if status.reachable:
        listed = set(status.models)
        judge = settings.judge_for(listed)
        llm["judge_model"] = judge
        llm["model_listed"] = settings.llm_name in listed
        llm["judge_model_listed"] = judge in listed
        ready = llm["model_listed"] and llm["judge_model_listed"]
        if settings.llm_understand_name:
            llm["understand_model_listed"] = settings.understand_name in listed
            ready = ready and llm["understand_model_listed"]
    else:
        llm["error"] = status.error
    return {"status": "ok" if ready else "degraded", "version": __version__, "llm": llm}


def _host_only(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.hostname}" if parts.hostname else url


def _error_text(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    return f"{type(exc).__name__} {status}" if status else type(exc).__name__
