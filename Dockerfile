# Leicht·Facile application image.
# Everything is installed at build time (Python packages, spaCy models), so the
# container needs no network at runtime except the model endpoint (LLM_BASE_URL).

FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

# The base image's pip is never used (uv installs everything) and its vendored
# urllib3, msgpack and setuptools are what vulnerability scanners flag.
RUN python -m pip uninstall --yes pip

# Dependencies first, so code changes do not invalidate this layer. The uv cache
# is a build-time mount, so it speeds up rebuilds without ending up in the image.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# /app keeps the repository's layout (track_2b/src, track_2b/data), so the relative
# default paths work in the container as they do on a checkout.
COPY track_2b/src ./track_2b/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Example documents and pre-computed example jobs (team-written texts only).
COPY track_2b/data/examples ./track_2b/data/examples

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown app /data
USER app

ENV DATA_DIR=/data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=15s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=12)"

# The app writes its own access line per request (request id, no query string); uvicorn's
# would double it.
CMD ["uvicorn", "leichtfacile.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
