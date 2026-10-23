# Quick start: every way to start Leicht·Facile

This page lists every way to start the application, from the one default command to
a development server with live reload. Run every command from the repository
root: the recipes, `.env` and the default data folder are all resolved from there.

| Way | Command | Model endpoint | Needs |
|-----|---------|----------------|-------|
| [1. `make run`](#1-make-run-the-default) | `make run` | remote (CSCS by default) | Docker, make, an API key |
| [2. Docker Compose](#2-docker-compose-without-make) | `docker compose up --build` | remote | Docker, an API key |
| [3. Plain Docker](#3-plain-docker-without-compose) | `docker build` + `docker run` | remote | Docker, an API key |
| [4. Local vLLM](#4-on-premise-local-vllm-official-apertus-15-8b) | `docker compose --profile local-llm up` | in Compose, official 8B | NVIDIA GPU with 24 GB+ |
| [5. Local llama.cpp in Compose](#5-small-office-llamacpp-in-compose) | `docker compose --profile local-llm-small up` | in Compose, 4-bit 8B | NVIDIA GPU with 8 GB |
| [6. Without Docker](#6-without-docker-uv-on-the-host) | `uv run python -m leichtfacile serve` | any | uv, Python 3.12+ |
| [7. llama.cpp on the host](#7-llamacpp-on-the-host-no-key) | `llama-server ...` + 1, 2 or 6 | on the host, 4-bit 8B | GPU with 8 GB, llama.cpp |
| [8. Command line only](#8-command-line-only-no-web-ui) | `python -m leichtfacile simplify ...` | any | as 1 or 6 |
| [9. Release wheel](#9-from-the-release-wheel-no-checkout) | `uv tool install <wheel URL>` | any | uv or pip, Python 3.12+ |

Every way serves the web UI at <http://localhost:8000> (`/healthz` says the process is
up, `/readyz` whether the model endpoint answers). The interface is in English, German
or French; the New draft form offers the example letters as one-click fills
(data/examples/README.md).

## The endpoint settings

Every way needs three variables: `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_NAME`. Put them
in `.env`:

```bash
cp .env.example .env      # then fill in LLM_API_KEY; the CSCS profile is the default
```

or export them in the shell (for these three, the shell wins over `.env`):

```bash
export LLM_BASE_URL=https://api.inference.cscs.ch/v1 LLM_API_KEY=... LLM_NAME=swiss-ai/Apertus-v1.5-8B
```

`.env.example` lists five endpoint profiles with their settings and caveats:

| Profile | Endpoint | Use |
|---------|----------|-----|
| A (default) | CSCS inference API, Lugano | a CSCS key; the reported numbers |
| B | local vLLM (way 4) | on-premise, air-gapped |
| C | Public AI gateway | development with public documents only |
| D | Hugging Face router | development only; serves Apertus 1, not 1.5 |
| E | local llama.cpp (ways 5 and 7) | development, small offices, no key |

Every other setting (model tiers, jobs, retention, login) is optional and documented in
`.env.example`.

## 1. `make run` (the default)

The simplest way. Needs Docker with Compose v2 and GNU make.

```bash
cp .env.example .env      # set LLM_API_KEY
make run                  # builds the image, starts it, opens http://localhost:8000
```

- `make run` checks the three variables and that Docker is running before it builds,
  and fails with a short message otherwise.
- The browser opens once `/healthz` answers. The first build installs the Python
  packages and the spaCy models and can take a few minutes. `make run OPEN_BROWSER=0`
  only prints the address; on a machine without a desktop that happens anyway.
- Ctrl+C stops the containers; `make stop` (or `docker compose down`) removes them. The
  jobs stay in the Docker volume `appdata`.
- On Windows, make needs a POSIX shell: the Makefile uses `sh.exe` from Git for Windows
  (`C:/Program Files/Git/usr/bin`; `make run GIT_SH_DIR=...` if Git lives elsewhere).

Before the first real document, `make check-llm` lists the endpoint's models and makes
one short call, and `make smoke` sends one example letter through the whole pipeline.

## 2. Docker Compose without make

The same container as way 1, without the checks and the browser opener:

```bash
docker compose up --build          # in the foreground; Ctrl+C stops it
docker compose up --build -d       # in the background
docker compose logs -f app         # follow the log
docker compose down                # stop and remove the containers (the volume stays)
```

## 3. Plain Docker without Compose

For a host with Docker but without the Compose plugin. The image builds with BuildKit
(the default in current Docker).

```bash
docker build -t leicht-facile:latest .
docker run --rm --env-file .env -p 127.0.0.1:8000:8000 -v leicht-facile-data:/data leicht-facile:latest
```

Keep the port on `127.0.0.1` unless a login is set (see [Reaching the app from other
machines](#reaching-the-app-from-other-machines)).

## 4. On-premise: local vLLM, official Apertus 1.5 8B

Compose adds a vLLM server with the official Apertus 1.5 image on one NVIDIA GPU with
24 GB or more (run on an NVIDIA L4, `docs/hardware/`). Needs the NVIDIA
Container Toolkit. In `.env`, use profile B:

```bash
LLM_BASE_URL=http://vllm:8000/v1
LLM_API_KEY=local                  # any value; vLLM runs without a key
LLM_NAME=swiss-ai/Apertus-v1.5-8B
LLM_JUDGE_NAME=swiss-ai/Apertus-v1.5-8B
LLM_THINKING_MODE=chat-template
HF_TOKEN=...                       # to download the weights on first start
```

```bash
docker compose --profile local-llm up --build
```

The app starts at once; jobs work as soon as vLLM has loaded the weights (several
minutes on first start; `/readyz` turns `ok`). The weights stay in the volume
`hf-cache`. vLLM serves parallel requests, so `JOB_WORKERS=2` or more runs jobs side by
side.

**Air-gapped:** on a connected machine, build the app image, pull the vLLM image
(`docker compose --profile local-llm pull vllm`) and start once to fill the `hf-cache`
volume; then move both images (`docker save`, `docker load`) and the volume's content.
The app image holds everything else (Python packages, spaCy models, UI assets). A
one-step bundle (`make bundle`) is not implemented yet.

## 5. Small office: llama.cpp in Compose

Compose adds a llama.cpp server with a community 4-bit, text-only conversion of Apertus
1.5 8B (unofficial, no image input) that fits a GPU with 8 GB. In `.env`:

```bash
LLM_BASE_URL=http://llamacpp:8080/v1
LLM_API_KEY=local
LLM_NAME=apertus-v1.5-8b-q4-llamacpp
LLM_THINKING_MODE=chat-template
LLM_TIMEOUT_S=1800                 # thinking calls take minutes on a small GPU
```

```bash
docker compose --profile local-llm-small up --build
```

The weights (5 GB) download on first start into the volume `llamacpp-models`. Results
from this setup are never reported as CSCS numbers.

## 6. Without Docker: uv on the host

For development. Needs [uv](https://docs.astral.sh/uv/); uv installs the Python version
in `.python-version` (3.14; 3.12 or newer works) and the spaCy models from `uv.lock`.

```bash
uv sync                                     # once, and after every dependency change
uv run python -m leichtfacile serve         # http://127.0.0.1:8000
```

- The settings come from `.env` in the current folder and from the shell, as in Docker.
- The data lives in `data/` (`leichtfacile.sqlite`, git-ignored);
  `DATA_DIR=...` moves it.
- `serve --port 8001` picks another port. `serve --host 0.0.0.0` publishes the app on
  every interface and needs a login (below), as `BIND_HOST` does in Compose.
- With live reload while editing code (`--no-access-log`: the app writes its own
  access line, with the request id and without the query string):

  ```bash
  uv run uvicorn leichtfacile.web.app:create_app --factory --reload --no-access-log
  ```

- The same commands without uv, in a virtual environment with the project installed:
  `python -m leichtfacile serve` or the script `leichtfacile serve`.

## 7. llama.cpp on the host (no key)

A llama.cpp server on the host, for development on a laptop GPU without any API key
(profile E). Start the server:

```bash
llama-server -hf Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF -ngl 99 -c 16384 -fa on \
  -ctk q8_0 -ctv q8_0 --jinja -sp -np 1 --alias apertus-v1.5-8b-q4-llamacpp \
  --host 0.0.0.0 --port 8080
```

Then point the app at it in `.env` and start it with way 1, 2 or 6:

```bash
LLM_BASE_URL=http://host.docker.internal:8080/v1   # app in Docker (ways 1, 2)
# LLM_BASE_URL=http://127.0.0.1:8080/v1            # app on the host (way 6)
LLM_API_KEY=local
LLM_NAME=apertus-v1.5-8b-q4-llamacpp
LLM_THINKING_MODE=chat-template
LLM_TIMEOUT_S=1800
```

On Linux, `host.docker.internal` needs `extra_hosts: ["host.docker.internal:host-gateway"]`
on the app service; Docker Desktop (Windows, macOS) provides it.

## 8. Command line only (no web UI)

The pipeline and the checker also run from the command line, in the container or on
the host:

```bash
# in the container (as `make smoke` does)
docker compose run --rm --build app python -m leichtfacile simplify data/examples/sources/praemienverbilligung-brief.txt --out /data/out

# on the host (way 6)
uv run python -m leichtfacile simplify letter.pdf --lang de --level A2 --out out/
uv run python -m leichtfacile check easy-text.txt --lang de        # rule checker, no endpoint
uv run python -m leichtfacile check-llm                            # one call to the endpoint
```

`python -m leichtfacile --help` lists every command (`serve`, `check-llm`, `ingest`,
`check`, `simplify`, `eval`, `examples`); `simplify` accepts a file path or an http(s)
URL and writes every artifact to the output folder. On Windows in Git Bash, prefix a
command that names a container path with `MSYS_NO_PATHCONV=1`.

## 9. From the release wheel (no checkout)

Every version tag publishes a wheel on the
[releases page](https://github.com/bobrovsky420/leicht-facile/releases)
(`.github/workflows/release.yml`). It installs with uv or pip without the repository:
the spaCy models are direct references in its metadata. Needs Python 3.12 or newer.

```bash
# as a tool on the PATH (uv picks or installs the Python)
uv tool install https://github.com/bobrovsky420/leicht-facile/releases/download/v0.6.0/leichtfacile-0.6.0-py3-none-any.whl

# or into an environment of your own, for example in a custom image
pip install https://github.com/bobrovsky420/leicht-facile/releases/download/v0.6.0/leichtfacile-0.6.0-py3-none-any.whl
```

```bash
export LLM_BASE_URL=https://api.inference.cscs.ch/v1 LLM_API_KEY=... LLM_NAME=swiss-ai/Apertus-v1.5-8B
DATA_DIR=./leichtfacile-data leichtfacile serve      # http://127.0.0.1:8000
```

- The settings come from `.env` in the current folder and from the shell, as in way 6.
- Set `DATA_DIR`: its default, `data`, is a path in a checkout and would be
  created below the current folder.
- The wheel holds the app, the prompts, the rules and the UI, not the example letters:
  the New draft form offers none unless `EXAMPLES_DIR` points at a copy of
  `data/examples/`.
- In a Dockerfile, `pip install <wheel URL>` in a `python:3.14-slim` stage replaces the
  `uv sync` steps of the repository's Dockerfile; start the app with
  `uvicorn leichtfacile.web.app:create_app --factory --host 0.0.0.0 --port 8000`.

## Other make targets

Besides `make run`, the Makefile has:

- `make check-llm`: one call to the endpoint
- `make test`, `make lint`
- `make smoke`: one document through the pipeline
- `make calibrate`: the rule checker on official easy-language pages, no model needed
- `make eval`: conditions P0, P1, P2 on the reference pairs;
  `RESULTS=eval/results-cscs` keeps one endpoint's results together

`python -m leichtfacile eval sample` writes the hand-labelling sheets for the judge and
`eval kappa` scores a filled sheet; `eval diagnose` says why must-keep facts are missing
from the final drafts of a run, without a model call.

## Reaching the app from other machines

Every way above publishes the app on this machine only (`127.0.0.1:8000`). To reach it
from the organisation's network:

- **Behind a reverse proxy (recommended):** keep `BIND_HOST=127.0.0.1`, let the proxy
  log users in and publish the app, and optionally trust its user header
  (`AUTH_PROXY_HEADER`, `AUTH_PROXY_FROM`).
- **Directly:** set `BIND_HOST=0.0.0.0` in `.env` together with `AUTH_TOKEN=<secret>`.
  The browser asks for the token (any user name, the token as the password); scripts
  send `Authorization: Bearer <secret>`.

Without a login, the app refuses to start on anything but the loopback interface.
Details: [architecture.md §10](architecture.md#10-deployment-and-sovereignty).

## When it does not start

| Message or symptom | Fix |
|--------------------|-----|
| `Variable LLM_... is not set` | copy `.env.example` to `.env` and fill it in, or export the variable |
| `Docker is not running` | start Docker Desktop, or `sudo systemctl start docker` on Linux |
| `Docker Compose v2 is missing` | update Docker Desktop or install the Compose plugin |
| make runs the recipes in `cmd.exe` (Windows) | install Git for Windows, or set `GIT_SH_DIR` |
| the app refuses to start because of `BIND_HOST` | set `AUTH_TOKEN` or `AUTH_PROXY_HEADER`, or keep `BIND_HOST=127.0.0.1` |
| `/readyz` says `degraded` | the endpoint is unreachable or does not list `LLM_NAME`; `make check-llm` shows why. Review, export and Check my text still work |
| port 8000 in use | stop the other service; on the host, `serve --port 8001` |
