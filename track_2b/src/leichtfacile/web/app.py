"""FastAPI application: pages, JSON API, health check, and the job runner.

Run with `uvicorn leichtfacile.web.app:create_app --factory`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from leichtfacile import __version__
from leichtfacile.config import Settings, get_settings
from leichtfacile.examples import load_examples
from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline.orchestrator import Orchestrator
from leichtfacile.pipeline.runner import JobRunner
from leichtfacile.store import Store
from leichtfacile.web import api, pages
from leichtfacile.web.security import CrossSiteGuard

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

    app.add_middleware(CrossSiteGuard)  # unsafe requests from another site: 403
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(api.router)
    app.include_router(pages.router)

    @app.get("/healthz")
    def healthz() -> dict:
        """Liveness plus a check of the model endpoint.

        Always answers 200 while the service runs; the `llm` block reports whether the
        endpoint is reachable and whether the configured models are listed.
        """
        status: dict = {
            "base_url": _host_only(settings.llm_base_url),
            "model": settings.llm_name,
            "judge_model": settings.judge_name,
        }
        if settings.llm_understand_name:
            status["understand_model"] = settings.understand_name
        try:
            models = llm.list_models()
        except Exception as exc:  # any failure is reported, never raised
            log.warning("LLM endpoint check failed: %s", type(exc).__name__)
            status.update(reachable=False, error=_error_text(exc))
        else:
            judge = settings.judge_for(models)
            status.update(
                judge_model=judge,
                reachable=True,
                models=models,
                model_listed=settings.llm_name in models,
                judge_model_listed=judge in models,
            )
            if settings.llm_understand_name:
                status["understand_model_listed"] = settings.understand_name in models
        return {"status": "ok", "version": __version__, "llm": status}

    return app


def _host_only(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.hostname}" if parts.hostname else url


def _error_text(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    return f"{type(exc).__name__} {status}" if status else type(exc).__name__
