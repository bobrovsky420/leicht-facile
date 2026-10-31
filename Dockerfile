# The application image: Leicht·Facile with every dependency, the checker's language
# packages among them, installed at build time, so that a container needs no network at
# runtime but the model endpoint (docs/quickstart.md way 7, docs/architecture.md §10).
# .github/workflows/ci.yml builds, starts and scans it on every change; release.yml
# publishes it as ghcr.io/bobrovsky420/leichtfacile:<version> and :latest.
#
# Two stages: the first installs the environment with uv from uv.lock (the versions of
# every other install of this commit), the second carries that environment alone, on the
# same base image, without uv, pip or the build context. The base image is pinned to the
# minor version of .python-version (tests/test_container.py), and its tag moves with
# Debian's security updates; uv is pinned to a release. x86-64 only: the model servers
# the image runs next to are.

FROM python:3.14-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv

# Bytecode compiled at build time (a faster start), the packages copied and not linked
# from the cache mount, the image's own Python (no download), the environment outside
# the build context.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/leichtfacile

WORKDIR /build

# The dependencies first, in a layer of their own: a change of the code leaves it in the
# build cache. The uv cache is a mount at build time and never part of the image.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Then the package itself, built and installed as a wheel (not editable): the runtime
# stage needs the environment alone. The README is the package's long description.
COPY README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable


FROM python:3.14-slim

LABEL org.opencontainers.image.title="Leicht·Facile" \
      org.opencontainers.image.description="Easy-language drafts of official texts with a large language model; every fact checked by code, every draft reviewed by a person" \
      org.opencontainers.image.url="https://leichtfacile.ch" \
      org.opencontainers.image.source="https://github.com/bobrovsky420/leicht-facile" \
      org.opencontainers.image.documentation="https://github.com/bobrovsky420/leicht-facile/blob/main/docs/quickstart.md" \
      org.opencontainers.image.licenses="Apache-2.0"

# Debian's fixes since the base image was built, so that the vulnerability scan in CI
# reports what has no fix yet and nothing else. pip is never used (uv installed
# everything in the build stage) and the packages it vendors are what scanners flag. The
# app runs as a system user of its own; /data is its one writable folder (below).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall --yes pip \
    && useradd --system --uid 10001 --user-group --create-home --shell /usr/sbin/nologin leichtfacile \
    && install -d -o leichtfacile -g leichtfacile /data

COPY --from=build /opt/leichtfacile /opt/leichtfacile

# Everything the app writes goes to /data, the volume: the config file and the .env that
# `leichtfacile setup` writes, the database and the caches. The port is published by the
# container runtime, so the app listens on every interface of its container and judges
# from server.published_on, the address the runtime publishes the port on, whether it is
# reachable beyond this machine: `docker run -p 127.0.0.1:8000:8000 -e
# LEICHTFACILE_SERVER__PUBLISHED_ON=127.0.0.1` runs without a login, like the native app
# (compose.yaml passes the address it publishes on). Without the setting the app takes
# its bind address, every interface, as published and refuses to start without a login
# (auth.token, or the reverse proxy's user header: docs/quickstart.md way 7).
ENV PATH=/opt/leichtfacile/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    LEICHTFACILE_CONFIG=/data/config.toml \
    LEICHTFACILE_DATA__DIR=/data \
    LEICHTFACILE_SERVER__HOST=0.0.0.0

USER leichtfacile
WORKDIR /data
EXPOSE 8000

# Liveness from the process alone (web/health.py): 200 even while the model endpoint is
# down, which /readyz reports instead. The probes need no login.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"]

CMD ["leichtfacile", "serve", "--no-browser"]
