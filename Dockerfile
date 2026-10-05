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

# Dependencies first, so code changes do not invalidate this layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown app /data
USER app

ENV DATA_DIR=/data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=15s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=12)"

CMD ["uvicorn", "leichtfacile.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
