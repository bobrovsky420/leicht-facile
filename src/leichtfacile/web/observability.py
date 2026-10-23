"""Observability (audit T6): a request id and an access line per request, and
`GET /metrics` for Prometheus. The log output itself is logs.py.

`RequestContext` is the outermost middleware (`install` adds it after the hardening
layer, so it sees a request first and its response last, refusals included). It takes
the client's `X-Request-ID` when that is a plain token (letters, digits, `.`, `_`,
`-`, at most 64 characters; a reverse proxy sets one so that its log and ours meet),
else makes one. The id is on `request.state.request_id`, in the response header and,
for the time the request is handled, in `logs.request_id`, so every line written
meanwhile carries it. When the response is out it writes one line to
`leichtfacile.web.access`: method, path, status, duration and the client address,
never the query string (the drafts list's search is what a reviewer typed), and counts
the request for `/metrics`. uvicorn's own access log, whose line has the query string,
is off (`leichtfacile serve`).

`GET /metrics` answers in the Prometheus text format from three sources: the jobs
table (jobs by status, the queue depth), the runner (workers, busy workers, the
durations of the jobs this process ran, by final status) and the `llm_calls` table
(calls, tokens and latency per stage and model, totals over the stored jobs; a deleted
job takes its calls with it, so these are gauges), plus the requests this process
answered. Behind the login when one is configured: the figures say how much the
service is used and which models it calls.
"""

from __future__ import annotations

import bisect
import logging
import math
import re
import secrets
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from leichtfacile import __version__, logs

if TYPE_CHECKING:
    from fastapi import FastAPI

    from leichtfacile.config import Settings
    from leichtfacile.pipeline.runner import JobRunner
    from leichtfacile.store import Store

access_log = logging.getLogger("leichtfacile.web.access")
router = APIRouter()
TOKEN = re.compile(r"[A-Za-z0-9._-]{1,64}")
CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
REQUEST_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
JOB_BUCKETS = (30.0, 60.0, 120.0, 300.0, 600.0, 1200.0, 1800.0, 3600.0, 7200.0)
JOB_STATUSES = ("queued", "running", "needs_review", "done", "failed")


def install(app: FastAPI, metrics: Metrics) -> None:
    """Outside the hardening layer: called after `security.install`, since Starlette
    runs the middleware added last first."""
    app.add_middleware(RequestContext, metrics=metrics)


# -- counting ---------------------------------------------------------------------------


class Histogram:
    """Observations in cumulative buckets, as Prometheus wants them."""

    def __init__(self, buckets: Iterable[float]) -> None:
        self.buckets = tuple(buckets)
        self.counts = [0] * (len(self.buckets) + 1)  # the last one: +Inf
        self.sum = 0.0
        self.count = 0

    def observe(self, value: float) -> None:
        self.counts[bisect.bisect_left(self.buckets, value)] += 1
        self.sum += value
        self.count += 1

    def cumulative(self) -> list[tuple[float, int]]:
        running, out = 0, []
        for upper, n in zip((*self.buckets, math.inf), self.counts, strict=True):
            running += n
            out.append((upper, running))
        return out


class Metrics:
    """What this process counted since it started: requests by method and status
    with their durations, and the durations of the jobs its workers ran, by final
    status. Thread-safe; the workers and the handlers write from their threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests: Counter[tuple[str, int]] = Counter()
        self.request_seconds = Histogram(REQUEST_BUCKETS)
        self.job_seconds: dict[str, Histogram] = {}

    def observe_request(self, method: str, status: int, seconds: float) -> None:
        with self._lock:
            self.requests[(method, status)] += 1
            self.request_seconds.observe(seconds)

    def observe_job(self, status: str, seconds: float) -> None:
        with self._lock:
            self.job_seconds.setdefault(status, Histogram(JOB_BUCKETS)).observe(seconds)


# -- the request id and the access line -------------------------------------------------


class RequestContext:
    """ASGI middleware: the request id, the access line, the request counted."""

    def __init__(
        self, app: ASGIApp, metrics: Metrics, clock: Callable[[], float] = time.perf_counter
    ) -> None:
        self.app = app
        self.metrics = metrics
        self.clock = clock

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        rid = request_id_for(Headers(scope=scope).get("x-request-id"))
        scope.setdefault("state", {})["request_id"] = rid
        status = 500  # what the client gets when no response starts (the error handler's)
        started = self.clock()
        token = logs.request_id.set(rid)

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = rid
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            seconds = self.clock() - started
            method, path = scope["method"], scope["path"]
            client = scope.get("client")
            self.metrics.observe_request(method, status, seconds)
            access_log.info(
                "%s %s %d %.0f ms",
                method,
                path,
                status,
                seconds * 1000,
                extra={
                    "method": method,
                    "path": path,  # never the query string
                    "status": status,
                    "duration_ms": round(seconds * 1000, 1),
                    "client": client[0] if client else None,
                },
            )
            logs.request_id.reset(token)


def request_id_for(header: str | None) -> str:
    """The client's id when it is a plain token, else a new one."""
    return header if header and TOKEN.fullmatch(header) else secrets.token_hex(8)


# -- /metrics ---------------------------------------------------------------------------


class Exposition:
    """Lines in the Prometheus text format."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def metric(self, name: str, kind: str, help_text: str) -> None:
        self.lines += [f"# HELP {name} {help_text}", f"# TYPE {name} {kind}"]

    def sample(self, name: str, value: float, **labels: object) -> None:
        self.lines.append(f"{name}{_labels(labels)} {_number(value)}")

    def histogram(self, name: str, help_text: str, series: list[tuple[dict, Histogram]]) -> None:
        """One histogram per label set in `series`: the cumulative buckets, the sum and
        the count."""
        self.metric(name, "histogram", help_text)
        for labels, hist in series:
            for upper, running in hist.cumulative():
                self.sample(f"{name}_bucket", running, **labels, le=_number(upper))
            self.sample(f"{name}_sum", hist.sum, **labels)
            self.sample(f"{name}_count", hist.count, **labels)

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def _labels(labels: dict[str, object]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{_escape(str(v))}"' for k, v in labels.items())
    return "{" + inner + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _number(value: float) -> str:
    if value == math.inf:
        return "+Inf"
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return repr(float(value))


def render(store: Store, runner: JobRunner, metrics: Metrics, settings: Settings) -> str:
    out = Exposition()
    out.metric("leichtfacile_info", "gauge", "The service and its version.")
    out.sample("leichtfacile_info", 1, version=__version__)

    counts = store.status_counts()
    out.metric("leichtfacile_jobs", "gauge", "Jobs in the database by status.")
    for status in JOB_STATUSES:
        out.sample("leichtfacile_jobs", counts.get(status, 0), status=status)
    out.metric("leichtfacile_queue_depth", "gauge", "Jobs waiting for a worker.")
    out.sample("leichtfacile_queue_depth", counts.get("queued", 0))
    out.metric(
        "leichtfacile_queue_limit",
        "gauge",
        "Waiting jobs beyond which a submission is refused (JOB_QUEUE_LIMIT).",
    )
    out.sample("leichtfacile_queue_limit", settings.job_queue_limit)
    out.metric("leichtfacile_workers", "gauge", "Worker threads (JOB_WORKERS).")
    out.sample("leichtfacile_workers", runner.workers)
    out.metric("leichtfacile_workers_busy", "gauge", "Workers running a job now.")
    out.sample("leichtfacile_workers_busy", runner.busy)

    with metrics._lock:
        jobs = [({"status": s}, h) for s, h in sorted(metrics.job_seconds.items())]
        requests = sorted(metrics.requests.items())
        request_seconds = metrics.request_seconds
        out.histogram(
            "leichtfacile_job_duration_seconds",
            "Seconds a job ran, from a worker taking it to its end, by final status; "
            "the jobs this process ran.",
            jobs,
        )

    totals = store.usage_totals()
    out.metric(
        "leichtfacile_llm_calls",
        "gauge",
        "Model calls stored, by stage, model and whether the response cache answered; "
        "a deleted job takes its calls with it.",
    )
    for row in totals:
        cached = str(bool(row["cached"])).lower()
        out.sample(
            "leichtfacile_llm_calls",
            row["calls"],
            stage=row["stage"],
            model=row["model"],
            cached=cached,
        )
    out.metric(
        "leichtfacile_llm_tokens",
        "gauge",
        "Tokens of the stored model calls, by stage, model and direction "
        "(in: the prompt, out: the answer).",
    )
    for row in totals:
        for direction in ("in", "out"):
            tokens = row[f"tokens_{direction}"]
            out.sample(
                "leichtfacile_llm_tokens",
                tokens,
                stage=row["stage"],
                model=row["model"],
                direction=direction,
            )
    out.metric(
        "leichtfacile_llm_latency_seconds",
        "gauge",
        "Seconds the stored model calls took, summed by stage and model.",
    )
    for row in totals:
        seconds = row["latency_ms"] / 1000
        out.sample(
            "leichtfacile_llm_latency_seconds", seconds, stage=row["stage"], model=row["model"]
        )

    out.metric(
        "leichtfacile_http_requests_total",
        "counter",
        "Requests this process answered, by method and status.",
    )
    for (method, status), n in requests:
        out.sample("leichtfacile_http_requests_total", n, method=method, status=status)
    out.histogram(
        "leichtfacile_http_request_duration_seconds",
        "Seconds from a request's arrival to the end of its response; this process.",
        [({}, request_seconds)],
    )
    return out.text()


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def metrics(request: Request) -> PlainTextResponse:
    """Prometheus text format: jobs, queue, workers, job durations, model calls and
    tokens per stage, requests."""
    state = request.app.state
    text = render(state.store, state.runner, state.metrics, state.settings)
    return PlainTextResponse(text, media_type=CONTENT_TYPE)
