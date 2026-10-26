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
| [1. Run with uvx](#1-run-with-uvx-no-install) | `uvx leichtfacile setup`, `uvx leichtfacile serve` | uv, an endpoint |
| [2. Clone and run](#2-clone-and-run-development) | `git clone`, `uv run leichtfacile setup`, `uv run leichtfacile serve` | git, uv |
| [3. Install the command](#3-install-the-command) | `uv tool install leichtfacile` (or `pip install`), `leichtfacile setup`, `leichtfacile serve` | uv or pip, Python 3.12+ |
| [4. Command line only](#4-command-line-only) | `leichtfacile simplify <file or URL> --out <folder>` | as 1, 2 or 3 |
| [5. On a server](#5-on-a-server) | `leichtfacile serve --no-browser` as a system service | as 3, a login or a reverse proxy |
| [6. Offline install](#6-offline-install-air-gapped) | `pip wheel` and `pip download` on a connected machine; `pip install --no-index` and `leichtfacile models --from` on the target | a connected machine of the same kind |

Every way needs the same two things before `serve`: an endpoint that is ready (an
address, a model and a key: [The model endpoint](#the-model-endpoint)) and the spaCy
models for German and French (`setup` offers them, `leichtfacile models` gets them, a
checkout has them from `uv.lock`). The examples below write `leichtfacile`; with way 1
it is `uvx leichtfacile`, with way 2 `uv run leichtfacile`.

The web UI runs at <http://127.0.0.1:8000>: `/healthz` says the process is up, `/readyz`
whether the model endpoint answers and lists the configured models. The interface is in
English, German or French. The New draft form and the empty drafts list offer the
example letters shipped with the package as one-click fills.

## The model endpoint

The app needs a model endpoint that is ready: its address, its key and the model that
reads, writes and repairs. The presets below are endpoints already; each lacks only what
the program cannot know, mostly the key. There are three ways to make one ready:

- **The key alone.** With a preset's key variable set, in the environment or in a `.env`
  in the current folder (`CSCS_API_KEY=...`, `PUBLICAI_API_KEY=...`), the preset is ready
  without any setup. When exactly one endpoint is ready, the app uses it.
- **`leichtfacile setup <preset>`**, for example `setup cscs`: asks for the key (hidden
  input) and saves it in the `.env` next to the user's config file. A preset used as it
  is needs no entry in the config file.
- **`leichtfacile setup`** without a name: asks which endpoint to use, offering the
  presets (but the rarely used `mistral`, `groq` and `huggingface`, which take
  `setup <name>`) and any other, then its address, a name and the key, lists the endpoint's
  models (`GET /models`) and asks for the model. For Anthropic and OpenAI it offers a few
  models with the settings they need, and any other model the endpoint lists as the last
  option. It saves what differs from the preset as `[endpoints.<name>]` in the user's
  config file.

`setup` uses the endpoint it set up. `leichtfacile endpoint list` shows every endpoint,
whether it is ready (else what it lacks) and the one in use;
`leichtfacile endpoint use <name>` switches, and `--endpoint <name>` picks one for a
single `serve`, `simplify` or `check-llm`. With several ready, the New draft form offers
them for each draft.

| Preset | Endpoint | Notes |
|--------|----------|-------|
| `cscs` | Apertus on the CSCS inference API, Lugano | The endpoint of the reported numbers; needs a CSCS key (`CSCS_API_KEY`). Thinking models are separate names ending in `-thinking` |
| `apertus` | Apertus on the Public AI gateway | Needs a Public AI key (`PUBLICAI_API_KEY`). Public documents only: run by Metagov Inc. (US nonprofit), requests go to compute partners; pay per token after USD 2 of starter credit. The preset turns the gateway's response cache off, which ignores the thinking switch |
| `anthropic` | Anthropic's Claude through its OpenAI-compatible endpoint | Needs the key (`ANTHROPIC_API_KEY`) and a model: setup offers Claude Haiku 5.5 and Sonnet 5.5, with their thinking switched off by the preset, or any model the endpoint lists. US cloud: public documents only |
| `openai`, `mistral` | OpenAI, Mistral AI | Need the key (`OPENAI_API_KEY`, `MISTRAL_API_KEY`) and a model: for OpenAI setup offers GPT-5.6 Luna, GPT-5.6 Terra and GPT-5.4 Nano, with the settings they need, or any model the endpoint lists. Check where the provider processes the text before sending anything confidential. `mistral` is not in setup's list: `leichtfacile setup mistral` |
| `local` | llama.cpp (llama-server, port 8080) on this machine, or another OpenAI-compatible server (`--base-url`) | Takes any key; switches thinking through the chat template (llama.cpp with `--jinja`) and allows 30 minutes per call; needs the model the server runs: `setup local` lists them and asks (`--model <name>` gives it); [Running a model yourself](#running-a-model-yourself) |
| `ollama` | Ollama on this machine (port 11434) | Takes any key; `setup ollama` lists the models `ollama list` shows and asks which one. For a thinking model such as Qwen: `config set endpoints.ollama.thinking reasoning-effort` |
| `vllm` | vLLM (port 8000), mostly a GPU machine of the organisation | `setup vllm --base-url http://<server>:8000/v1 --model <name>`; switches thinking through the chat template. On one machine vLLM and the app both want port 8000: start one of them elsewhere |
| `groq`, `huggingface` | Groq; the Hugging Face Inference Providers router | Need the key (`GROQ_API_KEY`, `HF_TOKEN`) and a model from the list `setup` shows. US and third-party clouds: public documents only. Not in setup's list: `leichtfacile setup groq` (or `huggingface`) |
| `other` | Any OpenAI-compatible endpoint | For example a gateway of the organisation's own |

Flags answer the questions in advance: `--preset` (the preset a differently named
endpoint starts from), `--name`, `--base-url`, `--api-key`,
`--api-key-env` (a variable that holds the key), `--model`, `--judge`, `--force` to
update an endpoint saved already, and `--no-models` to leave the spaCy models for later
(`leichtfacile models`). With the address, the key and the model given or known from the
preset, setup asks nothing, so it runs from a script. `--api-key` ends up in the shell
history; leave it out to be asked.

```bash
leichtfacile setup cscs              # asks for the key; the rest comes from the preset
leichtfacile endpoint list           # every endpoint, ready or what it lacks, the one in use
leichtfacile check-llm               # lists the endpoint's models and makes one short call
leichtfacile config show             # every setting, its value and where it comes from
```

### The settings

[configuration.md](configuration.md) explains the config file, the saved endpoints and
their presets, the keys, the commands that change settings (`leichtfacile config set`,
`leichtfacile config edit`) and every setting with its default. In short: the user's
config file is a TOML file with a section per topic; a `leichtfacile.toml` in the current
folder overrides it, `LEICHTFACILE_<SECTION>__<KEY>` variables override both, and the
command line (`--endpoint`, `serve --host`, `serve --port`) overrides everything. A
`.env` holds keys only. The data (the database `leichtfacile.sqlite`, the caches and the
spaCy models in `models/`) lives in `data.dir`:

| System | Config file | `data.dir` by default |
|--------|-------------|-----------------------|
| Windows | `%APPDATA%\leichtfacile\config.toml` | `%LOCALAPPDATA%\leichtfacile` |
| macOS | `~/Library/Application Support/leichtfacile/config.toml` | `~/Library/Application Support/leichtfacile` |
| Linux and others | `$XDG_CONFIG_HOME/leichtfacile/config.toml`, else `~/.config/leichtfacile/config.toml` | `$XDG_DATA_HOME/leichtfacile`, else `~/.local/share/leichtfacile` |

`data.examples_dir` points the New draft form at another folder of letters (`.txt` or
`.md`, each with an optional `.json` of job settings next to it); by default it offers
the letters in `src/leichtfacile/letters/`: the premium-reduction letter in German and in
French, and a KESB decision with its decision-mode settings.

### Thinking

Thinking is off by default (`thinking = "off"`), since every endpoint switches it its own
way:

- `model-suffix`: the thinking model is a separate model named `<model>-thinking`
  (Apertus on CSCS);
- `chat-template`: the request switches it through the chat template (vLLM, llama.cpp);
- `reasoning-effort`: the request says `reasoning_effort = "none"` for the stages that do
  not think (a thinking model such as Qwen on Ollama).

It applies to the stages in `thinking_stages` (default `["understand", "judge"]`). The
`cscs` and `apertus` presets set the mode; for a server of your own, set it on its
endpoint: `leichtfacile config set endpoints.<name>.thinking chat-template`.
`leichtfacile check-llm --thinking` makes its test call with thinking and says whether
reasoning came back.

### The judge

The judge grades the drafts. Its model is `models.judge` when set; else the 70B of an
Apertus 8B writer when the endpoint lists it (the setup the evaluation measured); else
the writer's model, as on a server with one model. `/readyz` names the judge model in use.

## 1. Run with uvx (no install)

Leicht·Facile is on [PyPI](https://pypi.org/project/leichtfacile/) from version 0.7.0
on. With [uv](https://docs.astral.sh/uv/), `uvx` runs it from there without installing
anything; uv picks or downloads a suitable Python (3.12 or newer).

```bash
uvx leichtfacile setup        # the endpoint and its key; then the language models
uvx leichtfacile serve        # http://127.0.0.1:8000, opens the browser
```

With a preset's key in a `.env` in the current folder (or in the environment), setup is
not needed:

```bash
echo "PUBLICAI_API_KEY=<your key>" > .env
uvx leichtfacile models       # once: the language models
uvx leichtfacile serve
```

- `uvx` (short for `uv tool run`) keeps the release in uv's cache, so later calls start
  at once. `uvx leichtfacile@latest serve` checks for a newer release;
  `uvx leichtfacile@0.7.1 serve` runs that version.
- The config file, the keys and the data live in the user's folders
  ([The settings](#the-settings)), as with an installed command: way 3 later finds them.
- `setup` ends by offering the spaCy models the rule checker parses German and French
  with: about 90 MB from spaCy's releases on GitHub, checked against pinned SHA-256
  hashes and unpacked into `models/` in `data.dir` (they are not on PyPI, so the package
  cannot bring them). `leichtfacile models` gets them at any time; `setup --no-models`
  skips them. Without them `serve`, `check` and `simplify` stop with a hint instead of
  checking less.
- `serve` opens the default browser once `/healthz` answers, but only when the app runs on
  this machine (`--host` 127.0.0.1, localhost or ::1) and, on Linux, only with a desktop
  (`DISPLAY` or `WAYLAND_DISPLAY`). `--no-browser` leaves it closed.
- `--port 8001` picks another port (`leichtfacile config set server.port 8001` keeps it);
  `--host` publishes the app beyond this machine and needs a login
  ([Reaching the app from other machines](#reaching-the-app-from-other-machines)).
- Ctrl+C stops the server; the jobs stay in `data.dir`.
- `leichtfacile --help` lists the commands, `leichtfacile <command> --help` their options.

## 2. Clone and run (development)

Needs git and uv. The first `uv run` installs the Python version in `.python-version`
(3.14; 3.12 or newer works), the dependencies and the spaCy models from `uv.lock` into
the checkout's `.venv`; every later one keeps it in step with `uv.lock`.

```bash
git clone https://github.com/bobrovsky420/leicht-facile.git
cd leicht-facile
uv run leichtfacile setup       # or the key alone in the checkout's .env, see below
uv run leichtfacile serve
```

- A `.env` in the checkout (git ignores it) with a preset's key makes that preset ready
  without setup: `CSCS_API_KEY=...` or `PUBLICAI_API_KEY=...`.
- A `leichtfacile.toml` in the checkout (git ignores it too) overrides the user's config
  file there, for example to try another endpoint. `[data] dir = "data"` in it keeps the
  database and the caches in the repository's `data/`, where git ignores them (the
  evaluation's page cache lives in `data/cache/`)
  ([configuration.md](configuration.md#in-a-checkout)).
- `uv sync` does the install step alone, for example after `git pull`.
- With live reload while editing code (`--no-access-log`: the app writes its own access
  line, with the request id and without the query string):

  ```bash
  uv run uvicorn leichtfacile.web.app:create_app --factory --reload --no-access-log
  ```

The development tasks run with uv:

| Command | Does |
|---------|------|
| `uv run pytest` | the test suite |
| `uv run ruff check .`, `uv run ruff format --check .` | the checks CI runs; `uv run ruff format .` and `uv run ruff check --fix .` fix what they can |
| `uv run leichtfacile check-llm` | lists the endpoint's models and makes one short call |
| `uv run leichtfacile simplify src/leichtfacile/letters/praemienverbilligung-brief.txt --out out/smoke` | the smoke run: the German example letter through the whole pipeline against the live endpoint; it succeeds when the job reaches review |
| `uv run python scripts/config_reference.py` | writes the settings reference in [configuration.md](configuration.md#reference) again after a change of the settings |

### The evaluation

The evaluation runs the conditions on the held-out pairs and writes the tables of
[evaluation.md](evaluation.md). `--results` keeps one endpoint's results together
(`eval/results-cscs` for the reported numbers); `--cache` reuses the cached answers, so
an interrupted run resumes cheaply. `uv run leichtfacile eval --help` lists every
evaluation command.

```bash
# the pairs, and the rule checker on the official easy-language pages (no model)
uv run leichtfacile eval fetch --role all
uv run leichtfacile eval calibrate --role all --lang de
uv run leichtfacile eval calibrate --role all --lang fr
# the originals and the official versions, P0, P0-ZH (the Canton of Zurich's prompt,
# German only), P1 and P2, then the tables
uv run leichtfacile eval reference --role all --results eval/results-cscs
uv run leichtfacile eval run --cache --condition P0 --results eval/results-cscs
uv run leichtfacile eval run --cache --condition P0-ZH-complete --lang de --results eval/results-cscs
uv run leichtfacile eval run --cache --condition P0-ZH-condensed --lang de --results eval/results-cscs
uv run leichtfacile eval run --cache --condition P1 --results eval/results-cscs
uv run leichtfacile eval run --cache --condition P2 --results eval/results-cscs
uv run leichtfacile eval report --results eval/results-cscs --out docs/evaluation.md
uv run leichtfacile eval compare      # docs/model-comparison.md: every run side by side
# the 70B: every stage on it, and the hybrid (the 70B reads, the 8B writes)
uv run leichtfacile eval run --cache --condition P2 --writer swiss-ai/Apertus-v1.5-70B --results eval/results-cscs
uv run leichtfacile eval run --cache --condition P2 --understand swiss-ai/Apertus-v1.5-70B --results eval/results-cscs
```

## 3. Install the command

For a `leichtfacile` command on the PATH, or a virtual environment of your own. Needs
Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) or pip.

```bash
# as a command on the PATH (uv picks or installs a suitable Python)
uv tool install leichtfacile

# or into a virtual environment of your own
pip install leichtfacile
```

Every release's wheel is also on the
[releases page](https://github.com/bobrovsky420/leicht-facile/releases), for this one:
`uv tool install https://github.com/bobrovsky420/leicht-facile/releases/download/v0.7.1/leichtfacile-0.7.1-py3-none-any.whl`.

```bash
leichtfacile setup        # the endpoint and its key; then the language models
leichtfacile serve        # http://127.0.0.1:8000, opens the browser
```

- Everything said under way 1 holds, without the `uvx` in front.
- `python -m leichtfacile` does the same as `leichtfacile`.
- `uv tool upgrade leichtfacile` (or `pip install -U leichtfacile`) gets a newer release.
- `uv tool uninstall leichtfacile` removes the program; the config file and the data (with
  the models) stay.

## 4. Command line only

The pipeline, the rule checker and the ingest step also run without the web UI, with any of
ways 1 to 3:

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

## 5. On a server

Install as in way 3 (or way 6 without internet) and run the app as a service of the
system, in one of two ways:

- behind a reverse proxy (recommended): `leichtfacile serve --no-browser` on 127.0.0.1;
  the proxy ends TLS and logs the users in;
- directly: `leichtfacile serve --host 0.0.0.0 --no-browser` with a token (`auth.token`).

[Reaching the app from other machines](#reaching-the-app-from-other-machines) explains
both logins. On Linux with systemd, with a dedicated user, the program in
`/opt/leichtfacile`, the config in `/etc/leichtfacile` and the data in
`/var/lib/leichtfacile` (Python 3.12 or newer with venv, on Debian and Ubuntu the package
`python3-venv`):

```bash
sudo useradd --system --home-dir /var/lib/leichtfacile --shell /usr/sbin/nologin leichtfacile
sudo python3 -m venv /opt/leichtfacile
sudo /opt/leichtfacile/bin/pip install leichtfacile
CONFIG="--config /etc/leichtfacile/config.toml"
sudo /opt/leichtfacile/bin/leichtfacile $CONFIG setup --no-models
sudo /opt/leichtfacile/bin/leichtfacile $CONFIG config set data.dir /var/lib/leichtfacile
sudo chown -R leichtfacile /etc/leichtfacile
sudo install -d -o leichtfacile /var/lib/leichtfacile
sudo -u leichtfacile /opt/leichtfacile/bin/leichtfacile $CONFIG models
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
Environment=LEICHTFACILE_CONFIG=/etc/leichtfacile/config.toml
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

- `setup` writes the endpoint into `/etc/leichtfacile/config.toml` and its key into
  `/etc/leichtfacile/.env`, both readable by the service's user alone after the `chown`.
- `StateDirectory` keeps `/var/lib/leichtfacile` for the service's user; the models are
  in its `models/` folder, so `leichtfacile models` runs as that user.
- The app reads the config file itself through `LEICHTFACILE_CONFIG`;
  `Environment=LEICHTFACILE_<SECTION>__<KEY>=...` lines override single settings.
- For the direct way, put a secret into `/etc/leichtfacile/.env`
  (`LEICHTFACILE_TOKEN=<secret>`), then `config set auth.token_env LEICHTFACILE_TOKEN` and
  `config set server.host 0.0.0.0` (with `$CONFIG`, as above).
- `data.retention_days` deletes jobs after so many days, `log.format = "json"` writes one
  JSON object per line for a log collector, and `jobs.workers` runs jobs side by side when
  the endpoint serves parallel requests ([configuration.md](configuration.md#reference)).

## 6. Offline install (air-gapped)

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
into `models/` in `data.dir`; on a server, run it as the service's user with its config
file (way 5).

The model server runs inside the network too, with its weights carried over the same way
(llama-server takes a local file with `-m <file>.gguf` instead of `-hf`). Point the app at
it with `leichtfacile setup local` and run it as in way 5.

## Running a model yourself

Running a model is outside the app: start a model server and set it up as an endpoint
with its preset, `leichtfacile setup local` (llama.cpp), `ollama` or `vllm`, which knows
the server's port and thinking switch and asks for the model from the server's list. Two
setups are known to work.

### Apertus 1.5 8B on vLLM, one 24 GB GPU

The Swiss AI team's official vLLM image ran Apertus 1.5 8B (the official bf16 weights) on
one NVIDIA L4 with 24 GB; [docs/hardware/aws-l4-2026-10-10/](hardware/aws-l4-2026-10-10/)
shows the commands used, the memory and the timings. On a 24 GB card the server needs
`--kv-cache-dtype=fp8` and `--max-num-seqs=16` next to `--max-model-len=32768`: the stages
ask for up to 16,000 output tokens on top of the prompt. The weights are gated: accept
their terms on Hugging Face once and give the server a token (`HF_TOKEN`). The app's
endpoint:

```bash
leichtfacile setup vllm --base-url http://<model server>:8000/v1 --model swiss-ai/Apertus-v1.5-8B
```

- The preset brings `thinking = "chat-template"` and the key `local` (any value, unless
  the server was started with a key); the command saves the address and the model as
  `[endpoints.vllm]`.
- The judge is then the 8B too, the only model the server lists.
- vLLM serves parallel requests, so `[jobs] workers = 2` or more runs jobs side by side.
- On the L4 one letter took 63 minutes with the default thinking stages and 22 minutes
  with `thinking_stages = ["understand"]`.
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
leichtfacile setup local --name laptop --model apertus-v1.5-8b-q4-llamacpp
```

The `local` preset switches thinking through the chat template (`--jinja`) and allows 30
minutes per call, since a thinking call takes minutes on a small GPU;
`leichtfacile config set endpoints.laptop.thinking_stages '["understand"]'` keeps the
judge from thinking too.

### Other models

Ollama: `leichtfacile setup ollama` lists the models `ollama list` shows and asks which
one. Any other OpenAI-compatible server: `leichtfacile setup` with its address, or
`setup local --base-url <address>`. Thinking stays off unless the server switches it
through the chat template. The reported numbers hold for Apertus 1.5 only.

## Reaching the app from other machines

By default the app answers on this machine only (`127.0.0.1:8000`). Published on any
other address, it needs one of two logins and refuses to start without one.

- **Behind a reverse proxy (recommended).** Keep `--host 127.0.0.1` (the default) and let
  the proxy end TLS, log the users in and publish the app. Optionally trust its user
  header: `auth.proxy_header = "X-Forwarded-User"` (or `Remote-User`) with
  `auth.proxy_from`, the proxy's addresses or networks (`["127.0.0.1"]` for a proxy on the
  same machine). A request from elsewhere is refused (403), one without the header is not
  logged in (401). With the proxy on another machine, `--host` names an address the proxy
  reaches, and the header counts as the login.
- **Directly.** `leichtfacile serve --host 0.0.0.0` (every interface) with a token:
  `auth.token = "<secret>"` in the config file, or `auth.token_env` naming a variable that
  holds it, in the environment or a `.env` ([configuration.md](configuration.md#keys)).
  Browsers ask for it
  (HTTP Basic: any user name, the token as the password); scripts send
  `Authorization: Bearer <secret>`. Without TLS the token crosses the network readable, so
  use this inside a trusted network. A secret:
  `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

`auth.token` and `auth.proxy_header` exclude each other. `/healthz`, `/readyz` and the
static files need no login. Details:
[docs/architecture.md §10](architecture.md#10-deployment-and-sovereignty).

## When it does not start

| Message or symptom | Fix |
|--------------------|-----|
| `No model endpoint is ready: give a preset its key with leichtfacile setup <name>, ...`, followed by what each endpoint lacks | `leichtfacile setup <preset>` (for example `setup cscs`), the preset's key in a `.env` in the current folder, or `leichtfacile setup` for another endpoint |
| `Settings are missing: - llm.api_key: the variable CSCS_API_KEY ... is not set` | put the key into the `.env` next to the config file (or the current folder's), or set the variable; `leichtfacile setup --force` asks for it again |
| `The settings are not valid: - server.prot (...): Extra inputs are not permitted` | a misspelt key or a wrong value; the message names the file or the variable it came from |
| `Several endpoints are ready (...) and llm.endpoint picks none` | `leichtfacile endpoint use <name>`, or `--endpoint <name>` for one run |
| `Missing the spaCy models ...: run leichtfacile models` | `leichtfacile models` (about 90 MB from GitHub), offline `leichtfacile models --from <folder>` (way 6) |
| `failed to hardlink file ... incompatible hardlinks. (os error 396)` from `uvx` or `uv tool install` (Windows) | uv links files from its cache, and Windows refuses another link to a file that already has one in a OneDrive folder (for example a checkout's `.venv` there). Add `--link-mode=copy` (`uvx --link-mode=copy leichtfacile setup`), or set it for good in PowerShell with `[Environment]::SetEnvironmentVariable('UV_LINK_MODE', 'copy', 'User')` and open a new terminal |
| `leichtfacile: command not found` after `uv tool install` | `uv tool update-shell`, then open a new terminal |
| setup says `Nothing changed (... exists in ...; --force updates it)` | `leichtfacile setup --force`, or `leichtfacile config edit` |
| setup says `The endpoint's model list could not be read` | the address or the key is wrong, or the server is not running; setup goes on, and `leichtfacile check-llm` checks again later |
| settings seem to be ignored | `leichtfacile config show` names the source of each setting: a `leichtfacile.toml` in the current folder, a `LEICHTFACILE_` variable or a flag wins over the config file |
| `server.host = '0.0.0.0' publishes the app beyond this machine` | set `auth.token` (or `auth.token_env`), or `auth.proxy_header` with `auth.proxy_from`, or serve on 127.0.0.1 |
| `auth.proxy_header needs auth.proxy_from` | set the proxy's addresses or networks |
| `set auth.token or auth.proxy_header, not both` | keep one of them |
| the browser does not open | it opens only for an app on this machine and, on Linux, with a desktop; open <http://127.0.0.1:8000> yourself |
| `/readyz` says `degraded` | the endpoint is unreachable or does not list the writer's or the judge's model; `leichtfacile check-llm` shows why. Review, export and Check my text still work |
| port 8000 in use (also by vLLM) | `leichtfacile serve --port 8001`, or move the other service |
