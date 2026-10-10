"""FastAPI application: pages, JSON API, health checks, and the job runner.

Run with `uvicorn leichtfacile.web.app:create_app --factory`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from leichtfacile import __version__
from leichtfacile.config import Settings, get_settings
from leichtfacile.examples import load_examples
from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline.orchestrator import Orchestrator
from leichtfacile.pipeline.runner import JobRunner
from leichtfacile.store import Store
from leichtfacile.web import api, health, pages, security

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"
DATABASE_NAME = "leichtfacile.sqlite"


def create_app(
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    store: Store | None = None,
    *,
    load_examples_on_start: bool = True,
) -> FastAPI:
    settings = settings or get_settings()
    logging.getLogger("leichtfacile").setLevel(settings.log_level.upper())
    llm = llm or LLMClient.from_settings(settings)
    store = store or Store(settings.data_dir / DATABASE_NAME)
    orchestrator = Orchestrator(store, llm, settings)
    runner = JobRunner(orchestrator)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if load_examples_on_start:
            load_examples(store)
        runner.start()
        resumed = runner.resume_pending()
        if resumed:
            log.info("resumed %d unfinished jobs", resumed)
        yield
        runner.stop()

    app = FastAPI(title="Leicht·Facile", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.llm = llm
    app.state.store = store
    app.state.orchestrator = orchestrator
    app.state.runner = runner
    app.state.endpoint_check = health.EndpointCheck(llm)

    # Headers, rate limit, login, cross-site guard, body limit: web/security.py.
    security.install(app, settings)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(api.router)
    app.include_router(pages.router)
    app.include_router(health.router)
    return app
