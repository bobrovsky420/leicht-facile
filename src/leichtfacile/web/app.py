"""FastAPI application: pages, JSON API, probes and metrics, and the job runner.

Run with `uvicorn leichtfacile.web.app:create_app --factory --no-access-log
--no-proxy-headers`, as `leichtfacile serve` does (cli.py): the app writes its own access
line and reads the reverse proxy's headers itself (web/security.py).
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from leichtfacile import __version__, config
from leichtfacile.config import Settings
from leichtfacile.llm.cache import open_cache
from leichtfacile.llm.client import LLMClient
from leichtfacile.llm.registry import Registry
from leichtfacile.llm.replay import Replay
from leichtfacile.logs import configure_logging
from leichtfacile.pipeline.orchestrator import Orchestrator
from leichtfacile.pipeline.runner import JobRunner
from leichtfacile.store import Store
from leichtfacile.web import api, health, model, observability, pages, security, workspaces

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"
DATABASE_NAME = "leichtfacile.sqlite"


def create_app(
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    store: Store | None = None,
    clients: dict[str, LLMClient] | None = None,
    replay: Replay | None = None,
) -> FastAPI:
    """The application on a registry of the presets' clients (`llm/registry.py`): with
    `llm` (the client of the preset in use) and `clients` (the other ready presets, by
    name) given, on those; else on the settings as they are now, the clients made on
    first use and made anew when the model page changes the settings. The app starts
    without a ready preset: its model page asks for the key. The store owns the response
    cache (`open_cache`), so that a deleted job takes its rows with it while no preset
    is ready too; the registry's clients use it. `replay` is the recorded runs of the
    sample letters (llm/replay.py), by default those of the package leichtfacile-samples;
    the registry's clients answer a job's first run from them, given clients keep their
    own."""
    if llm is not None and settings is None:
        raise TypeError("a client needs its settings")
    settings = settings or config.load(strict=False).settings
    # One line per record, text or JSON, with the request and job ids (logs.py); no
    # excerpt of a document or an answer in an error's line (docs/operations.md).
    configure_logging(settings.log.level, settings.log.format)
    store = store or Store(
        settings.data.dir / DATABASE_NAME, cache=open_cache(settings.data.dir, settings.llm.cache)
    )
    replay = replay if replay is not None else Replay.load()
    if llm is not None:
        registry = Registry(settings, llm=llm, clients=clients)
    else:
        registry = Registry.from_settings(
            settings, cache=store.cache if settings.llm.cache else None, replay=replay
        )
    orchestrator = Orchestrator(store, registry)
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

    # The documentation pages load Swagger UI and ReDoc from a CDN, the only download the
    # app would ever make: off unless server.api_docs says so; /openapi.json stays.
    docs = settings.server.api_docs
    app = FastAPI(
        title="Leicht·Facile",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
    )
    app.state.settings = settings  # replaced when the model page changes the settings
    app.state.registry = registry
    app.state.replay = replay  # the pages say when a draft's answers were recorded
    app.state.store = store
    app.state.orchestrator = orchestrator
    app.state.runner = runner
    # How many submissions are read at a time (web/jobs.py).
    app.state.ingest_slots = threading.BoundedSemaphore(settings.jobs.ingest_slots)
    app.state.endpoint_check = health.EndpointCheck(registry)
    app.state.metrics = metrics

    # Inside everything, the request's workspace (web/workspaces.py); then headers, rate
    # limit, login, cross-site guard, body limit: web/security.py; outside them the
    # request id and the access line: web/observability.py; outside even that, the
    # client address and scheme the trusted reverse proxy forwards (web/security.py, 0),
    # so that the access line and every layer see the same client.
    app.add_middleware(api.LegacyHeaders)  # innermost: the old API prefix's headers
    workspaces.install(app, settings)
    security.install(app, settings)
    observability.install(app, metrics)
    app.add_middleware(security.ProxyHeaders, settings=settings)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(api.router, prefix=api.API_PREFIX)
    # The same routes under the prefix of 0.11 and earlier, outside the schema, until
    # the sunset that api.LegacyHeaders announces (docs/maintenance.md, "Until 1.0").
    app.include_router(api.router, prefix=api.LEGACY_PREFIX, include_in_schema=False)
    app.include_router(pages.router)
    app.include_router(model.router)
    app.include_router(health.router)
    app.include_router(observability.router)
    app.include_router(workspaces.router)
    return app


def api_schema() -> dict:
    """The OpenAPI description of the JSON API alone, under its prefix, with the API's
    version (1) rather than the app's: what docs/openapi.json holds (written by
    scripts/openapi.py) and tests/web/test_api_version.py keeps equal to the code."""
    bare = FastAPI(title="Leicht·Facile", version="1")
    bare.include_router(api.router, prefix=api.API_PREFIX)
    return bare.openapi()
