"""FastAPI application: pages, JSON API, probes and metrics, and the job runner.

Run with `uvicorn leichtfacile.web.app:create_app --factory`.
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from leichtfacile import __version__, config
from leichtfacile.config import Settings, get_settings
from leichtfacile.llm.client import LLMClient
from leichtfacile.logs import configure_logging
from leichtfacile.pipeline.orchestrator import Orchestrator
from leichtfacile.pipeline.runner import JobRunner
from leichtfacile.store import Store
from leichtfacile.web import api, health, observability, pages, security

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"
DATABASE_NAME = "leichtfacile.sqlite"


def create_app(
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    store: Store | None = None,
    clients: dict[str, LLMClient] | None = None,
) -> FastAPI:
    """The application on the endpoint in use (`llm`) and the other ready endpoints
    (`clients`, by name), which a draft may pick in the New draft form; both default to
    the settings'."""
    settings = settings or get_settings()
    # One line per record, text or JSON, with the request and job ids (logs.py); no
    # excerpt of a document or an answer in an error's line (§10).
    configure_logging(settings.log.level, settings.log.format)
    llm = llm or LLMClient.from_settings(settings)
    if clients is None:
        clients = other_clients(settings, llm)
    store = store or Store(settings.data.dir / DATABASE_NAME)
    orchestrator = Orchestrator(store, llm, settings, clients=clients)
    metrics = observability.Metrics()  # what this process counts for /metrics
    runner = JobRunner(
        orchestrator,
        workers=settings.jobs.workers,
        queue_limit=settings.jobs.queue_limit,
        retention_days=settings.data.retention_days,
        on_finished=metrics.observe_job,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resumed = runner.recover_on_start()
        if resumed:
            log.info("queued %d jobs again that were running when the service stopped", resumed)
        runner.start()
        yield
        runner.stop()

    app = FastAPI(title="Leicht·Facile", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.llm = llm
    app.state.store = store
    app.state.orchestrator = orchestrator
    app.state.runner = runner
    # How many submissions are read at a time (web/jobs.py).
    app.state.ingest_slots = threading.BoundedSemaphore(settings.jobs.ingest_slots)
    app.state.endpoint_check = health.EndpointCheck(llm)
    app.state.metrics = metrics

    # Headers, rate limit, login, cross-site guard, body limit: web/security.py; outside
    # them the request id and the access line: web/observability.py.
    security.install(app, settings)
    observability.install(app, metrics)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(api.router)
    app.include_router(pages.router)
    app.include_router(health.router)
    app.include_router(observability.router)
    return app


def other_clients(settings: Settings, llm: LLMClient) -> dict[str, LLMClient]:
    """A client for every other endpoint that is ready (docs/configuration.md), sharing
    the response cache of the endpoint in use when its own settings cache too."""
    clients = {}
    for item in config.available():
        if item.ready and item.name != settings.llm.endpoint:
            other = config.load(endpoint=item.name).settings
            cache = {"cache": llm.cache} if other.llm.cache and llm.cache else {}
            clients[item.name] = LLMClient.from_settings(other, **cache)
    return clients
