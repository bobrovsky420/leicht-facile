"""FastAPI application. For now: a landing page and the health check.

Run with `uvicorn leichtfacile.web.app:create_app --factory`.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from leichtfacile import __version__
from leichtfacile.config import Settings, get_settings
from leichtfacile.llm.client import LLMClient

log = logging.getLogger(__name__)

_INDEX = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Leicht·Facile</title>
<style>
  body { font: 18px/1.5 system-ui, sans-serif; max-width: 40rem; margin: 3rem auto;
         padding: 0 1rem; color: #1b1b1b; background: #fff; }
  code { background: #f2f2f2; padding: 0 .25rem; }
</style>
</head>
<body>
<h1>Leicht·Facile</h1>
<p>The service is running (version {version}).</p>
<p>The review interface comes in a later version.
Health and model endpoint status: <a href="/healthz"><code>/healthz</code></a>.</p>
</body>
</html>
"""


def create_app(settings: Settings | None = None, llm: LLMClient | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.getLogger("leichtfacile").setLevel(settings.log_level.upper())
    llm = llm or LLMClient.from_settings(settings)

    app = FastAPI(title="Leicht·Facile", version=__version__)
    app.state.settings = settings
    app.state.llm = llm

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _INDEX.replace("{version}", __version__)

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
        try:
            models = llm.list_models()
        except Exception as exc:  # any failure is reported, never raised
            log.warning("LLM endpoint check failed: %s", type(exc).__name__)
            status.update(reachable=False, error=_error_text(exc))
        else:
            status.update(
                reachable=True,
                models=models,
                model_listed=settings.llm_name in models,
                judge_model_listed=settings.judge_name in models,
            )
        return {"status": "ok", "version": __version__, "llm": status}

    return app


def _host_only(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.hostname}" if parts.hostname else url


def _error_text(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    return f"{type(exc).__name__} {status}" if status else type(exc).__name__
