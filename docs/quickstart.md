# Quick start

Leicht·Facile drafts easy-language versions of Swiss official texts with any
OpenAI-compatible model endpoint. The endpoint comes from outside the app: a cloud API,
a gateway or a model server the organisation runs. The app itself never runs a model. It
was built and evaluated with Apertus 1.5 (the 8B writes, the 70B judges), and the
reported numbers are Apertus results. For texts under secrecy, use a model the
organisation controls; Apertus fits best
([docs/use-cases.md](use-cases.md#why-apertus-fits-best)).

The app is a Python package (Python 3.12 or newer) with one command, `leichtfacile`.

| Way | Commands | Needs |
|-----|----------|-------|
| [1. Install and run](#1-install-and-run) | `uv tool install leichtfacile`, `leichtfacile setup`, `leichtfacile serve` | uv or pip, Python 3.12+, an endpoint |
| [2. From a checkout (development)](#2-from-a-checkout-development) | `uv sync`, `uv run leichtfacile serve` | git, uv |
| [3. Command line only](#3-command-line-only) | `leichtfacile simplify <file or URL> --out <folder>` | as 1 or 2 |
| [4. On a server](#4-on-a-server) | `leichtfacile serve --no-browser` as a system service | as 1, a login or a reverse proxy |
| [5. Offline install](#5-offline-install-air-gapped) | `pip wheel` and `pip download` on a connected machine; `pip install --no-index` and `leichtfacile models --from` on the target | a connected machine of the same kind |

The web UI runs at <http://127.0.0.1:8000>: `/healthz` says the process is up, `/readyz`
whether the model endpoint answers and lists the configured models. The interface is in
English, German or French. The New draft form and the empty drafts list offer the
example letters shipped with the package as one-click fills.

## The model endpoint

Three settings are required: `LLM_BASE_URL` (the endpoint's address, for most servers
ending in `/v1`), `LLM_API_KEY` and `LLM_NAME` (the model that reads, writes and
repairs). `leichtfacile setup` asks for them and writes the user's config file. It asks
which endpoint to use, its address and the API key (hidden input), lists the endpoint's
models (`GET /models`) and asks for the model and an optional judge model.

| Preset | Endpoint | Notes |
|--------|----------|-------|
| `cscs` | Apertus on the CSCS inference API, Lugano | The endpoint of the reported numbers; needs a CSCS key. Also writes `LLM_THINKING_MODE=model-suffix` (thinking models are separate names ending in `-thinking`) and `LLM_MAX_RETRIES=8` (CSCS closes about one long thinking stream in four midway, and the client retries) |
| `publicai` | Apertus on the Public AI gateway | Public documents only: run by Metagov Inc. (US nonprofit), requests go to compute partners; pay per token after USD 2 of starter credit. Also writes `LLM_THINKING_MODE=chat-template` and `LLM_EXTRA_BODY={"cache": {"no-cache": true}}` (the gateway's cache ignores the thinking switch) |
| `local` | A server of your own: llama.cpp (port 8080), Ollama (port 11434), vLLM | Takes any key; [Running a model yourself](#running-a-model-yourself) |
| `openai`, `mistral` | OpenAI, Mistral AI | Check where the provider processes the text before sending anything confidential |
| `other` | Any OpenAI-compatible endpoint | For example a gateway of the organisation's own |

Flags answer the questions in advance: `--preset`, `--base-url`, `--api-key`, `--model`,
`--judge`, `--force` to replace an existing config file, and `--no-models` to leave the
spaCy models for later (`leichtfacile models`). With the address, the key
and the model given, setup asks nothing, so it runs from a script. `--api-key` ends up in
the shell history; leave it out to be asked.

```bash
leichtfacile setup --preset cscs     # asks for the key, the model and the judge
leichtfacile check-llm               # lists the endpoint's models and makes one short call
```

[.env.example](../.env.example) lists every setting with its default and the reasons
behind the endpoint settings, including the Hugging Face router (development only: it
serves Apertus 1, not 1.5).

### Where the settings come from

Each source overrides the one before:

1. the user's config file, written by `leichtfacile setup`;
2. `.env` in the current folder;
3. the environment.

The config file is the path in `LEICHTFACILE_CONFIG` when that is set in the
environment, else as below. It is a plain `KEY=value` file, readable by its owner only
where the system supports it (the key is in it); edit it or run `leichtfacile setup`
again. The data (the database `leichtfacile.sqlite`, the caches and the spaCy models in
`models/`) lives in `DATA_DIR`:

| System | Config file | `DATA_DIR` by default |
|--------|-------------|-----------------------|
| Windows | `%APPDATA%\leichtfacile\config.env` | `%LOCALAPPDATA%\leichtfacile` |
| macOS | `~/Library/Application Support/leichtfacile/config.env` | `~/Library/Application Support/leichtfacile` |
| Linux and others | `$XDG_CONFIG_HOME/leichtfacile/config.env`, else `~/.config/leichtfacile/config.env` | `$XDG_DATA_HOME/leichtfacile`, else `~/.local/share/leichtfacile` |

`EXAMPLES_DIR` points the New draft form at another folder of letters (`.txt` or `.md`,
each with an optional `.json` of job settings next to it); by default it offers the
letters in `src/leichtfacile/letters/`: the premium-reduction letter in German and in
French, and a KESB decision with its decision-mode settings.

### Thinking

Thinking is off by default (`LLM_THINKING_MODE=off`), since every endpoint switches it its
own way:

- `model-suffix`: the thinking model is a separate model named `<name>-thinking`
  (Apertus on CSCS);
- `chat-template`: the request switches it through the chat template (vLLM, llama.cpp).

It applies to the stages in `LLM_THINKING_STAGES` (default `understand,judge`). The
`cscs` and `publicai` presets write the mode; for a server of your own, add
`LLM_THINKING_MODE=chat-template` to the config file. `leichtfacile check-llm --thinking`
makes its test call with thinking and says whether reasoning came back.

### The judge

The judge grades the drafts. Its model is `LLM_JUDGE_NAME` when set; else the 70B of an
Apertus 8B writer when the endpoint lists it (the setup the evaluation measured); else the
writer's model, as on a server with one model. `/readyz` names the judge model in use.

## 1. Install and run

Leicht·Facile is on [PyPI](https://pypi.org/project/leichtfacile/) from version 0.7.0
on. Needs Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) or pip.

```bash
# as a command on the PATH (uv picks or installs a suitable Python)
uv tool install leichtfacile

# or into a virtual environment of your own
pip install leichtfacile
```

Every release's wheel is also on the
[releases page](https://github.com/bobrovsky420/leicht-facile/releases), for this one:
`uv tool install https://github.com/bobrovsky420/leicht-facile/releases/download/v0.7.0/leichtfacile-0.7.0-py3-none-any.whl`.

```bash
leichtfacile setup        # the endpoint, the key and the model; then the language models
leichtfacile serve        # http://127.0.0.1:8000, opens the browser
```

- `setup` ends by offering the spaCy models the rule checker parses German and French
  with: about 90 MB from spaCy's releases on GitHub, checked against pinned SHA-256
  hashes and unpacked into `DATA_DIR/models` (they are not on PyPI, so the package
  cannot bring them). `leichtfacile models` gets them at any time; `setup --no-models`
  skips them. Without them `serve`, `check` and `simplify` stop with a hint instead of
  checking less.
- `serve` opens the default browser once `/healthz` answers, but only when the app runs on
  this machine (`--host` 127.0.0.1, localhost or ::1) and, on Linux, only with a desktop
  (`DISPLAY` or `WAYLAND_DISPLAY`). `--no-browser` leaves it closed.
- `--port 8001` picks another port; `--host` publishes the app beyond this machine and
  needs a login ([Reaching the app from other machines](#reaching-the-app-from-other-machines)).
- Ctrl+C stops the server; the jobs stay in `DATA_DIR`.
- `leichtfacile --help` lists the commands, `leichtfacile <command> --help` their options;
  `python -m leichtfacile` does the same as `leichtfacile`.
- `uv tool uninstall leichtfacile` removes the program; the config file and the data (with
  the models) stay.

## 2. From a checkout (development)

Needs git and uv. `uv sync` installs the Python version in `.python-version` (3.14; 3.12
or newer works), the dependencies and the spaCy models from `uv.lock`.

```bash
git clone https://github.com/bobrovsky420/leicht-facile.git
cd leicht-facile
uv sync                         # once, and after every dependency change
uv run leichtfacile setup       # or: cp .env.example .env and fill it in
uv run leichtfacile serve
```

- A `.env` in the checkout overrides the user's config file there, for example to try
  another endpoint. `DATA_DIR=data` in it keeps the database and the caches in the
  repository's `data/`, where git ignores them (the evaluation's page cache lives in
  `data/cache/`).
- With live reload while editing code (`--no-access-log`: the app writes its own access
  line, with the request id and without the query string):

  ```bash
  uv run uvicorn leichtfacile.web.app:create_app --factory --reload --no-access-log
  ```

The Makefile has the development tasks; the app itself needs no make.

| Target | Does |
|--------|------|
| `make test` | the test suite |
| `make lint`, `make format` | ruff checks; ruff fixes and formats |
| `make check-llm` | `leichtfacile check-llm` |
| `make smoke` | the German example letter through the whole pipeline against the live endpoint; the artifacts land in `out/smoke` |
| `make calibrate` | the rule checker on the official easy-language pages, no model |
| `make eval` | conditions P0, P0-ZH, P1 and P2 on the held-out pairs, then the report tables; `RESULTS=eval/results-<endpoint>` keeps one endpoint's results together |
| `make eval-70b` | P2 with the 70B writer and with the hybrid (the 70B reads, the 8B writes) |

On Windows, make needs a POSIX shell: the Makefile uses `sh.exe` from Git for Windows
(`C:/Program Files/Git/usr/bin`; `make test GIT_SH_DIR=...` if Git lives elsewhere).
`uv run leichtfacile eval --help` lists the evaluation's commands
([docs/evaluation.md](evaluation.md)).

## 3. Command line only

The pipeline, the rule checker and the ingest step also run without the web UI, after way 1
(or with `uv run` in a checkout):

```bash
leichtfacile simplify letter.pdf --lang de --level A2 --out out    # the whole pipeline
leichtfacile check easy-text.txt --lang de                         # rule checker, no model
leichtfacile ingest letter.pdf                                     # the segments the pipeline reads
leichtfacile check-llm                                             # lists the models, one short call
```

- `simplify` takes a file (`.txt`, `.md`, `.html`, `.htm`, `.pdf`) or an http(s) URL and
  writes `draft.md`, `draft.html`, `draft.docx` and `bundle.json` (the audit bundle) to
  `<out>/<job id>/`. The job is also stored in the database, so the web UI shows it for
  review.
- Its options: `--lang` (de, fr, it; detected when left out), `--level` (A2, B1),
  `--condition` (P0, P1 or P2; default P2, the full pipeline), `--writer`, `--understand`
  and `--judge` (models other than the settings'), and `--mode decision` with
  `--addressee` and `--notice` for the letter that goes out with a decision
  ([docs/use-case-decisions.md](use-case-decisions.md)):

  ```bash
  leichtfacile simplify entscheid.txt --mode decision --addressee "Lea Muster" \
    --notice "Diese Erklärung hilft Ihnen, den Entscheid zu verstehen. Massgebend ist der Entscheid."
  ```

## 4. On a server

Install as in way 1 (or way 5 without internet) and run the app as a service of the
system, in one of two ways:

- behind a reverse proxy (recommended): `leichtfacile serve --no-browser` on 127.0.0.1;
  the proxy ends TLS and logs the users in;
- directly: `leichtfacile serve --host 0.0.0.0 --no-browser` with `AUTH_TOKEN` set.

[Reaching the app from other machines](#reaching-the-app-from-other-machines) explains
both logins. On Linux with systemd, with a dedicated user, the program in
`/opt/leichtfacile`, the config in `/etc/leichtfacile` and the data in
`/var/lib/leichtfacile` (Python 3.12 or newer with venv, on Debian and Ubuntu the package
`python3-venv`):

```bash
sudo useradd --system --home-dir /var/lib/leichtfacile --shell /usr/sbin/nologin leichtfacile
sudo python3 -m venv /opt/leichtfacile
sudo /opt/leichtfacile/bin/pip install leichtfacile
sudo mkdir -p /etc/leichtfacile
sudo env LEICHTFACILE_CONFIG=/etc/leichtfacile/config.env /opt/leichtfacile/bin/leichtfacile setup --no-models
sudo chown leichtfacile /etc/leichtfacile/config.env
sudo install -d -o leichtfacile /var/lib/leichtfacile
sudo -u leichtfacile env DATA_DIR=/var/lib/leichtfacile /opt/leichtfacile/bin/leichtfacile models
```

`/etc/systemd/system/leichtfacile.service`:

```ini
[Unit]
Description=Leicht-Facile
After=network-online.target
Wants=network-online.target

[Service]
User=leichtfacile
StateDirectory=leichtfacile
Environment=DATA_DIR=/var/lib/leichtfacile
Environment=LEICHTFACILE_CONFIG=/etc/leichtfacile/config.env
ExecStart=/opt/leichtfacile/bin/leichtfacile serve --no-browser
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now leichtfacile
journalctl -u leichtfacile -f              # the log
curl http://127.0.0.1:8000/readyz          # "ok" once the endpoint answers
```

- `StateDirectory` keeps `/var/lib/leichtfacile` for the service's user; the models are
  in its `models/` folder, so `leichtfacile models` runs as that user with that
  `DATA_DIR`.
- The app reads the config file itself through `LEICHTFACILE_CONFIG`; `Environment=` lines
  or an `EnvironmentFile=` override it.
- For the direct way, add `--host 0.0.0.0` to `ExecStart` and `AUTH_TOKEN=<secret>` to the
  config file.
- `DATA_RETENTION_DAYS` deletes jobs after so many days, `LOG_FORMAT=json` writes one JSON
  object per line for a log collector, and `JOB_WORKERS` runs jobs side by side when the
  endpoint serves parallel requests ([.env.example](../.env.example)).

## 5. Offline install (air-gapped)

On a connected machine with the same operating system, CPU architecture and Python
version as the target, collect the app with every dependency, and the two spaCy
models, in one folder:

```bash
pip wheel leichtfacile -w wheelhouse
pip download --no-deps -d wheelhouse \
  https://github.com/explosion/spacy-models/releases/download/de_core_news_md-3.8.0/de_core_news_md-3.8.0-py3-none-any.whl \
  https://github.com/explosion/spacy-models/releases/download/fr_core_news_md-3.8.0/fr_core_news_md-3.8.0-py3-none-any.whl
```

`pip wheel` downloads the wheels and builds one for any dependency published only as
source. Carry the folder over and install on the target:

```bash
python3 -m venv /opt/leichtfacile
/opt/leichtfacile/bin/pip install --no-index --find-links wheelhouse leichtfacile
/opt/leichtfacile/bin/leichtfacile models --from wheelhouse
```

`models --from` checks the two models' SHA-256 as the download does and unpacks them
into `DATA_DIR/models`; on a server, run it as the service's user with its `DATA_DIR`
(way 4).

The model server runs inside the network too, with its weights carried over the same way
(llama-server takes a local file with `-m <file>.gguf` instead of `-hf`). Point the app at
it with `leichtfacile setup --preset local` and run it as in way 4.

## Running a model yourself

Running a model is outside the app: start a model server and point `LLM_BASE_URL` at it
(`leichtfacile setup --preset local`). Two setups are known to work.

### Apertus 1.5 8B on vLLM, one 24 GB GPU

The Swiss AI team's official vLLM image ran Apertus 1.5 8B (the official bf16 weights) on
one NVIDIA L4 with 24 GB; [docs/hardware/aws-l4-2026-10-10/](hardware/aws-l4-2026-10-10/)
shows the commands used, the memory and the timings. On a 24 GB card the server needs
`--kv-cache-dtype=fp8` and `--max-num-seqs=16` next to `--max-model-len=32768`: the stages
ask for up to 16,000 output tokens on top of the prompt. The weights are gated: accept
their terms on Hugging Face once and give the server a token (`HF_TOKEN`). The app's
settings:

```bash
LLM_BASE_URL=http://<model server>:8000/v1
LLM_API_KEY=local                  # any value, unless the server was started with a key
LLM_NAME=swiss-ai/Apertus-v1.5-8B
LLM_THINKING_MODE=chat-template
```

- The judge is then the 8B too, the only model the server lists.
- vLLM serves parallel requests, so `JOB_WORKERS=2` or more runs jobs side by side.
- On the L4 one letter took 63 minutes with the default thinking stages and 22 minutes
  with `LLM_THINKING_STAGES=understand`.
- vLLM listens on port 8000 by default, as the app does: on one machine, start one of
  them on another port.

### Apertus 1.5 8B on llama.cpp, one 8 GB GPU

A community 4-bit, text-only conversion of Apertus 1.5 8B (unofficial, no image input)
runs on llama.cpp on a GPU with 8 GB, for development and small offices without any key.
The weights (5 GB) download on the first start:

```bash
llama-server -hf Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF -ngl 99 -c 16384 -fa on \
  -ctk q8_0 -ctv q8_0 --jinja -sp -np 1 --alias apertus-v1.5-8b-q4-llamacpp --port 8080
```

`-sp` keeps the reasoning markers visible so that the client can strip the reasoning; the
alias names what runs, so that results from this setup are never mistaken for the
official model (they are never reported as CSCS numbers). The server answers on this
machine only; `--host 0.0.0.0` opens it to an app on another machine, and to anyone else
unless it is started with `--api-key`. Then:

```bash
leichtfacile setup --preset local --base-url http://127.0.0.1:8080/v1 --api-key local --model apertus-v1.5-8b-q4-llamacpp
```

and add to the config file:

```bash
LLM_THINKING_MODE=chat-template
LLM_TIMEOUT_S=1800                 # thinking calls take minutes on a small GPU
```

### Other models

Ollama (`http://127.0.0.1:11434/v1`, the model names `ollama list` shows) or any other
OpenAI-compatible server works the same way. Thinking stays off unless the server
switches it through the chat template. The reported numbers hold for Apertus 1.5 only.

## Reaching the app from other machines

By default the app answers on this machine only (`127.0.0.1:8000`). Published on any
other address, it needs one of two logins and refuses to start without one.

- **Behind a reverse proxy (recommended).** Keep `--host 127.0.0.1` (the default) and let
  the proxy end TLS, log the users in and publish the app. Optionally trust its user
  header: `AUTH_PROXY_HEADER=X-Forwarded-User` (or `Remote-User`) with `AUTH_PROXY_FROM`,
  the proxy's addresses or networks, comma-separated (`127.0.0.1` for a proxy on the same
  machine). A request from elsewhere is refused (403), one without the header is not
  logged in (401). With the proxy on another machine, `--host` names an address the proxy
  reaches, and the header counts as the login.
- **Directly.** `leichtfacile serve --host 0.0.0.0` (every interface) with
  `AUTH_TOKEN=<secret>` in the config file, `.env` or the environment. Browsers ask for it
  (HTTP Basic: any user name, the token as the password); scripts send
  `Authorization: Bearer <secret>`. Without TLS the token crosses the network readable, so
  use this inside a trusted network. A secret:
  `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

`AUTH_TOKEN` and `AUTH_PROXY_HEADER` exclude each other. `/healthz`, `/readyz` and the
static files need no login. Details:
[docs/architecture.md §10](architecture.md#10-deployment-and-sovereignty).

## When it does not start

| Message or symptom | Fix |
|--------------------|-----|
| `Not set: LLM_BASE_URL, ... Run leichtfacile setup, ...` | run `leichtfacile setup`, or set them in the config file, in `.env` or in the environment |
| `Missing the spaCy models ...: run leichtfacile models` | `leichtfacile models` (about 90 MB from GitHub), offline `leichtfacile models --from <folder>` (way 5) |
| `leichtfacile: command not found` after `uv tool install` | `uv tool update-shell`, then open a new terminal |
| setup says `Nothing changed (... exists; --force replaces it)` | `leichtfacile setup --force`, or edit the config file |
| setup says `The endpoint's model list could not be read` | the address or the key is wrong, or the server is not running; setup still asks for the model, and `leichtfacile check-llm` checks again later |
| settings seem to be ignored | a `.env` in the current folder or a variable in the environment overrides the config file |
| `BIND_HOST='0.0.0.0' publishes the app beyond this machine` | set `AUTH_TOKEN`, or `AUTH_PROXY_HEADER` with `AUTH_PROXY_FROM`, or serve on 127.0.0.1 |
| `AUTH_PROXY_HEADER needs AUTH_PROXY_FROM` | set the proxy's addresses or networks |
| `set AUTH_TOKEN or AUTH_PROXY_HEADER, not both` | keep one of them |
| the browser does not open | it opens only for an app on this machine and, on Linux, with a desktop; open <http://127.0.0.1:8000> yourself |
| `/readyz` says `degraded` | the endpoint is unreachable or does not list `LLM_NAME` or the judge's model; `leichtfacile check-llm` shows why. Review, export and Check my text still work |
| port 8000 in use (also by vLLM) | `leichtfacile serve --port 8001`, or move the other service |
| make runs the recipes in `cmd.exe` (Windows) | install Git for Windows, or set `GIT_SH_DIR` |
