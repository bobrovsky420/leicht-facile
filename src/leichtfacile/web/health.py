"""Liveness and readiness.

`GET /healthz` answers from the process alone: a service manager's health check, the
browser opener of `leichtfacile serve` and a load balancer ask it every few seconds, and
none of them should make the server call the paid model endpoint with the organisation's key.

`GET /readyz` adds the model: is the preset in use ready (its key present), is its
provider reachable, and are the configured models listed. The provider is asked at most
once per `READY_CACHE_S` seconds, whoever asks and however often (one lock, so
concurrent callers wait for one answer instead of each making a call), and the answer
carries booleans and the configured names, never the provider's catalogue. The service
stays `200` while it runs, `status` says `ok` or `degraded`: the review pages, the
exports and the checker work without the model.
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
from leichtfacile.config import listed
from leichtfacile.llm.client import LLMClient
from leichtfacile.llm.registry import Registry

log = logging.getLogger(__name__)
router = APIRouter()
READY_CACHE_S = 30.0
NOT_READY = "the preset is not ready (no key)"


@dataclass(frozen=True)
class EndpointStatus:
    reachable: bool
    checked_at: datetime
    models: list[str] = field(default_factory=list)  # kept here, never answered
    error: str | None = None


class EndpointCheck:
    """`list_models()` of the client in use at most once per `ttl_s` seconds, and anew
    when the preset in use changed (the registry reloaded)."""

    def __init__(
        self,
        source: Registry | LLMClient,
        ttl_s: float = READY_CACHE_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.source = source
        self.ttl_s = ttl_s
        self._clock = clock
        self._lock = threading.Lock()
        self._status: EndpointStatus | None = None
        self._at = -float("inf")
        self._for: tuple[str, str] | None = None

    def status(self) -> EndpointStatus:
        with self._lock:
            now = self._clock()
            current = self._current()
            if self._status is None or now - self._at >= self.ttl_s or current != self._for:
                self._status = self._check()
                self._at = now
                self._for = current
            return self._status

    def _current(self) -> tuple[str, str]:
        if isinstance(self.source, Registry):
            return (self.source.in_use, self.source.settings.llm.url)
        return ("", self.source.settings.llm.url)

    def _check(self) -> EndpointStatus:
        llm = self.source.llm if isinstance(self.source, Registry) else self.source
        if llm is None:
            return EndpointStatus(False, datetime.now(UTC), error=NOT_READY)
        try:
            models = llm.list_models()
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
    """Readiness: liveness plus the cached check of the model."""
    state = request.app.state
    settings = state.settings
    status: EndpointStatus = state.endpoint_check.status()
    llm: dict = {
        "preset": settings.llm.preset,
        "ready": state.registry.is_ready(),
        "base_url": _host_only(settings.llm.url),
        "model": settings.llm.models.writer,
        "judge_model": settings.llm.judge_model,
        "reachable": status.reachable,
        "checked_at": status.checked_at.isoformat(timespec="seconds"),
    }
    if settings.llm.models.understand:
        llm["understand_model"] = settings.llm.understand_model
    ready = status.reachable
    if status.reachable:
        judge = settings.llm.judge_for(status.models)
        llm["judge_model"] = judge
        llm["model_listed"] = listed(settings.llm.models.writer, status.models)
        llm["judge_model_listed"] = listed(judge, status.models)
        ready = llm["model_listed"] and llm["judge_model_listed"]
        if settings.llm.models.understand:
            llm["understand_model_listed"] = listed(settings.llm.understand_model, status.models)
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
