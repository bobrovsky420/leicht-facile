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
| [1. Run with uvx](#1-run-with-uvx-no-install) | `uvx leichtfacile serve` | uv, a model's key |
| [2. Clone and run](#2-clone-and-run-development) | `git clone`, `uv run leichtfacile setup`, `uv run leichtfacile serve` | git, uv |
| [3. Install the command](#3-install-the-command) | `uv tool install leichtfacile` (or `pip install`), `leichtfacile setup`, `leichtfacile serve` | uv or pip, Python 3.12+ |
| [4. Command line only](#4-command-line-only) | `leichtfacile simplify <file or URL> --out <folder>` | as 1, 2 or 3 |
| [5. On a server](#5-on-a-server) | `leichtfacile serve --no-browser` as a system service (systemd, Windows) | as 3, a login or a reverse proxy |
| [6. Offline install](#6-offline-install-air-gapped) | `pip wheel` on a connected machine; `pip install --no-index` on the target | a connected machine of the same kind |

Every way needs a model that is ready to make drafts: a preset and its key
([The model](#the-model)). The language packages the rule checker parses German and
French and tags Italian with (about 95 MB) are dependencies of the package, the packages
leichtfacile-model-de, leichtfacile-model-fr and leichtfacile-model-it on PyPI (spaCy's
models, their files unchanged, and the Italian pipeline built on the Morph-it! lexicon),
so every way brings them. The examples below write `leichtfacile`; with way 1 it is `uvx
leichtfacile`, with way 2 `uv run leichtfacile`. How each way gets a newer release:
[Updates](#updates).

The web UI runs at <http://127.0.0.1:8000>: `/healthz` says the process is up, `/readyz`
whether the model's provider answers and lists the configured models. The interface is in
English, German, French or Italian. The New draft form and the empty drafts list offer the
example letters of the package leichtfacile-samples, which comes with the app, as
one-click fills ([samples/README.md](../samples/README.md)).

## The model

The app needs a model that is ready: a preset, which names a provider (where the models
run, with its address and key) and the models that write, read and check. The presets
below come with the app; each lacks only what the program cannot know, mostly the key.
There are three ways to make one ready:

- **The model page.** `leichtfacile serve` starts without a ready model and opens the
  browser on its page **AI model**, which
  lists every preset with where the text goes, what a page costs and what it lacks,
  takes the key, checks it and makes a test call. The preset of a fresh install is
  `publicai-apertus`.
- **The key alone.** With a provider's key variable set, in the environment or in a
  `.env` in the current folder (`PUBLICAI_API_KEY=...`, `CSCS_API_KEY=...`), its presets
  are ready without any setup.
- **`leichtfacile setup`** on the command line: asks where the model should run, for the
  key (hidden input, saved in the `.env` next to the user's config file) and which of
  the provider's presets to use, or any model the provider lists (`GET /models`), saved
  as a preset of your own; `setup <preset>` asks for the key alone. A server of your
  own becomes a provider with its address. It also asks once which German the texts
  use, Switzerland (the default), Germany or Austria; `setup --region DE` changes that
  alone ([configuration.md](configuration.md#texts)).

`setup` uses the preset it set up. `leichtfacile preset list` shows every preset,
whether it is ready (else what it lacks) and the one in use; `leichtfacile preset use
<name>` switches, and `--preset <name>` picks one for a single `serve`, `simplify` or
`check-llm`. `serve <preset>` is the same for the app: `uvx leichtfacile serve
claude-sonnet-5-5` runs that preset for one session, asks nothing and saves nothing,
and stops with the reason when the preset is not ready (its key in the environment or
a `.env` makes it ready). With several ready, the New draft form offers them for each
draft.

| Provider | Presets | Notes |
|----------|---------|-------|
| `publicai` | `publicai-apertus`: Apertus 8B writes, the 70B checks | The shipped default: Apertus on the Public AI gateway; needs a Public AI key (`PUBLICAI_API_KEY`). Public documents only: run by Metagov Inc. (US nonprofit), requests go to compute partners; pay per token after USD 2 of starter credit. Neither model thinks there: both ignore the thinking switch, and so does the gateway's response cache, which the provider turns off |
| `cscs` | `cscs-apertus`: Apertus 8B writes, the 70B checks | CSCS inference API, Lugano: the endpoint of the reference numbers ([evaluation.md](evaluation.md)); needs a CSCS key (`CSCS_API_KEY`), granted on application. Thinking models are separate names ending in `-thinking` |
| `anthropic` | `claude-haiku-5-5`, `claude-haiku-5-5-sonnet` (Haiku writes, Sonnet checks), `claude-sonnet-5-5`, `claude-opus-5-5` | Anthropic's Claude through its OpenAI-compatible endpoint; needs the key (`ANTHROPIC_API_KEY`); the tables of Haiku and Sonnet switch their thinking off, Opus always thinks. US cloud: public documents only |
| `openai` | `gpt-5-6-luna`, `gpt-5-6-terra`, `gpt-5-4-nano` | OpenAI; needs the key (`OPENAI_API_KEY`). US cloud: public documents only |
| `gemini` | `gemini-3-8-flash` | Google's Gemini through its OpenAI-compatible endpoint; needs the key (`GEMINI_API_KEY`, from Google AI Studio); the model's table asks for its lowest thinking level. On the free tier Google uses the texts to improve its products: anything but test texts needs a paid account. Not run with the app yet |
| `openrouter` | `openrouter-claude-haiku-5-5`, `openrouter-claude-haiku-5-5-sonnet`, `openrouter-gpt-5-6-luna`, `openrouter-gemini-3-8-flash`, `openrouter-qwen3-5-27b` | OpenRouter, a gateway to many providers; needs the key (`OPENROUTER_API_KEY`); routes to no provider that stores prompts, and the models' own providers see the text. Public documents only. Haiku ran a whole letter; the others not yet |
| `local` | the models the server lists | llama.cpp (llama-server, port 8080) on this machine, or another OpenAI-compatible server (`setup local --base-url`); takes any key; switches thinking through the chat template (llama.cpp with `--jinja`) and allows 30 minutes per call; [Running a model yourself](#running-a-model-yourself) |
| `ollama` | the models `ollama list` shows | Ollama on this machine (port 11434); takes any key; a Qwen model sends `reasoning_effort` none on every call |
| `vllm` | the models the server lists | vLLM (port 8000), mostly a GPU machine of the organisation: `setup vllm --base-url http://<server>:8000/v1 --model <name>`; switches thinking through the chat template. On one machine vLLM and the app both want port 8000: start one of them elsewhere |
| `mistral`, `groq`, `huggingface` | the models the provider lists | Mistral AI; Groq; the Hugging Face Inference Providers router. Need the key (`MISTRAL_API_KEY`, `GROQ_API_KEY`, `HF_TOKEN`); `leichtfacile setup groq` lists the models. EU, US and third-party clouds: public documents only |
| another server | | `leichtfacile setup <name> --base-url <address>`: any OpenAI-compatible endpoint, for example a gateway of the organisation's own |

Flags answer the questions in advance: `--name` (the preset saved for `--model`, or
the server), `--base-url` (a server of your own), `--api-key`, `--api-key-env` (a
variable that holds the key), `--model`, `--judge` and `--force` to update a preset
saved already. With the provider, the key and the preset or model given or known, setup asks nothing,
so it runs from a script. `--api-key` ends up in the shell history; leave it out to be
asked.

```bash
leichtfacile setup publicai-apertus  # asks for the key; the rest is shipped
leichtfacile serve claude-sonnet-5-5 # this preset for one run, nothing saved
leichtfacile preset list             # every preset, ready or what it lacks, the one in use
leichtfacile check-llm               # lists the provider's models and makes one short call
leichtfacile config show             # every setting, its value and where it comes from
```

### The settings

[configuration.md](configuration.md) explains the config file, the providers and
presets, the keys, the commands that change settings (`leichtfacile config set`,
`leichtfacile config edit`) and every setting with its default. In short: the user's
config file is a TOML file with a section per topic; a `leichtfacile.toml` in the current
folder overrides it, `LEICHTFACILE_<SECTION>__<KEY>` variables override both, and the
command line (`--preset`, `serve --host`, `serve --port`) overrides everything. A
`.env` holds keys only. The data (the database `leichtfacile.sqlite` and the caches)
lives in `data.dir`:

| System | Config file | `data.dir` by default |
|--------|-------------|-----------------------|
| Windows | `%APPDATA%\leichtfacile\config.toml` | `%LOCALAPPDATA%\leichtfacile` |
| macOS | `~/Library/Application Support/leichtfacile/config.toml` | `~/Library/Application Support/leichtfacile` |
| Linux and others | `$XDG_CONFIG_HOME/leichtfacile/config.toml`, else `~/.config/leichtfacile/config.toml` | `$XDG_DATA_HOME/leichtfacile`, else `~/.local/share/leichtfacile` |

`data.examples_dir` points the New draft form at another folder of letters (`.txt` or
`.md`, each with an optional `.json` of job settings next to it); by default it offers
the letters of the package leichtfacile-samples that fit the installation's region
([samples/README.md](../samples/README.md) lists them): the premium-reduction letter in German, French
and Italian, decisions with their decision-mode settings, and two school letters in the
three languages, to parents and to students.

### Thinking

Thinking is off by default (`thinking = "off"`), since every provider switches it its own
way:

- `model-suffix`: the thinking model is a separate model named `<model>-thinking`
  (Apertus on CSCS);
- `chat-template`: the request switches it through the chat template (vLLM, llama.cpp);
- `reasoning-effort`: the request says `reasoning_effort = "none"` for the stages that do
  not think (a thinking model such as Qwen on Ollama).

It applies to the stages in `thinking_stages` (default `["understand", "judge"]`). The
shipped providers and their models tables set the mode; a preset of your own overrides
it, from the model page's fine-tune panel or in the file: `leichtfacile config set
presets.<name>.thinking_stages '["understand"]'`. `leichtfacile check-llm --thinking`
makes its test call with thinking and says whether reasoning came back.

### The judge

The judge grades the drafts. Its model is `models.judge` when set; else the 70B of an
Apertus 8B writer when the provider lists it (the setup the evaluation measured); else
the writer's model, as on a server with one model. `/readyz` names the judge model in use.

## 1. Run with uvx (no install)

Leicht·Facile is on [PyPI](https://pypi.org/project/leichtfacile/) from version 0.7.0
on. With [uv](https://docs.astral.sh/uv/), `uvx` runs it from there without installing
anything; uv picks or downloads a suitable Python (3.12 or newer).

```bash
uvx leichtfacile serve        # opens http://127.0.0.1:8000/model
```

The first start downloads the app with its dependencies, the language packages among them
(95 MB), and opens the browser on the AI model page, which takes the key of the pre-selected preset (`publicai-apertus`) or of any
other. `uvx leichtfacile setup` asks the same on the command line. With a provider's key
in a `.env` in the current folder (or in the environment), its presets are ready without
either, and the first start uses the first of them, in the order setup lists the
providers (Public AI, CSCS, Anthropic, OpenAI, ...;
[configuration.md](configuration.md#the-model)):

```bash
echo "PUBLICAI_API_KEY=<your key>" > .env
uvx leichtfacile serve publicai-apertus
```

- `uvx` (short for `uv tool run`) checks PyPI at every start and runs the newest release
  ([Updates](#updates)); uv keeps each release in its cache, so a start without a new one
  is quick. `uvx leichtfacile@0.13.2 serve` runs that version.
- Nothing lands on the PATH or in the current folder: uv unpacks the app with its
  dependencies into its cache, a Python it downloads goes to its Python folder.
  `uv cache dir` and `uv python dir` print both; by default:

  | System | uv's cache (the app) | uv's Python folder |
  |--------|----------------------|--------------------|
  | Windows | `%LOCALAPPDATA%\uv\cache` | `%APPDATA%\uv\python` |
  | macOS, Linux | `$XDG_CACHE_HOME/uv`, else `~/.cache/uv` | `$XDG_DATA_HOME/uv/python`, else `~/.local/share/uv/python` |

  `uv cache clean leichtfacile` removes the app from the cache (the next `uvx` downloads
  it again); the config file and the data stay.
- The config file, the keys and the data live in the user's folders
  ([The settings](#the-settings)), as with an installed command: way 3 later finds them.
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
(3.14; 3.12 or newer works) and the dependencies, the spaCy models among them, from
`uv.lock` into the checkout's `.venv`; every later one keeps it in step with `uv.lock`.

```bash
git clone https://github.com/bobrovsky420/leicht-facile.git
cd leicht-facile
uv run leichtfacile setup       # or the key alone in the checkout's .env, see below
uv run leichtfacile serve
```

- A `.env` in the checkout (git ignores it) with a provider's key makes its presets
  ready without setup: `PUBLICAI_API_KEY=...` or `CSCS_API_KEY=...`.
- A `leichtfacile.toml` in the checkout (git ignores it too) overrides the user's config
  file there, for example with presets of its own for the evaluation runs. `[data] dir = "data"` in it keeps the
  database and the caches in the repository's `data/`, where git ignores them (the
  evaluation's page cache lives in `data/cache/`)
  ([configuration.md](configuration.md#in-a-checkout)).
- `uv sync` does the install step alone, for example after `git pull`.
- With live reload while editing code (`--no-access-log` and `--no-proxy-headers`, as
  `serve` runs it: the app writes its own access line, with the request id and without
  the query string, and reads the reverse proxy's headers itself):

  ```bash
  uv run uvicorn leichtfacile.web.app:create_app --factory --reload --no-access-log --no-proxy-headers
  ```

The development tasks run with uv:

| Command | Does |
|---------|------|
| `uv run pytest` | the test suite |
| `uv run pytest --cov`, then `uv run coverage report` | the test suite with the coverage of the package; CI writes the same report into the summary of the test job on the pinned Python version, as a number to read, not a threshold |
| `uv run ruff check .`, `uv run ruff format --check .` | the checks CI runs; `uv run ruff format .` and `uv run ruff check --fix .` fix what they can |
| `uv run leichtfacile check-llm` | lists the provider's models and makes one short call |
| `uv run leichtfacile simplify samples/leichtfacile_samples/letters/praemienverbilligung-brief.txt --out out/smoke` | the smoke run: the German example letter through the whole pipeline against the live endpoint (the command line never replays a recorded run); it succeeds when the job reaches review |
| `uv run python scripts/record_samples.py` | records the runs the web app replays for the sample letters again, on the default preset with its key from `.env`; `--check` replays them without an endpoint and names those a prompt change has made stale ([samples/README.md](../samples/README.md)) |
| `make run` | builds the image from the checkout, starts it with `compose.yaml` and the checkout's `.env` in the background, waits until it answers and opens the web UI ([way 7](#7-in-a-container)); `make logs` follows its log, `make stop` stops it (the data stays in the volume). Needs Docker, and make with Git for Windows' shell on Windows |
| `uv run python scripts/config_reference.py` | writes the settings reference in [configuration.md](configuration.md#reference) again after a change of the settings |
| `git config core.hooksPath scripts/hooks` | once per checkout: before each commit, ruff on the staged Python files and, with [gitleaks](https://github.com/gitleaks/gitleaks) installed, a scan of the staged changes for secrets; CI scans the whole history in any case |
| `uv lock --upgrade` | newer dependencies, a release only once it is a week old (`[tool.uv] exclude-newer` in pyproject.toml); Dependabot opens the same as a pull request every week |

### The evaluation

The evaluation runs the conditions on the held-out pairs and writes the tables of
[evaluation.md](evaluation.md). `--results` keeps one preset's results together
(`eval/results-cscs` for the reference numbers, `eval/results-publicai` for the shipped
default's), and `eval run --preset cscs-apertus`
runs on that preset whatever the configuration selects; `--cache` reuses the cached
answers, so an interrupted run resumes cheaply. `uv run leichtfacile eval --help` lists
every evaluation command.

```bash
# the pairs, and the rule checker on the official easy-language pages (no model)
uv run leichtfacile eval fetch --role all
uv run leichtfacile eval calibrate --role all --lang de
uv run leichtfacile eval calibrate --role all --lang fr
uv run leichtfacile eval calibrate --role all --lang it
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
# Italian ran on the Public AI gateway, the 70B at every stage (28 October 2026; the
# preset's 8B writer is replaced by the 70B with --writer)
uv run leichtfacile eval reference --role all --lang it --results eval/results-publicai
uv run leichtfacile eval run --cache --condition P2 --lang it --preset publicai-apertus --writer swiss-ai/apertus-v1.5-70b --results eval/results-publicai
uv run leichtfacile eval report --results eval/results-publicai --role eval --out docs/evaluation-publicai.md
# Germany and Austria (30 October 2026): the pairs of one variety (--region), the same
# preset and folder; the rows carry the region and the report gives each variety its own
# section. eval reference keeps the rows of the other pairs in REF.jsonl.
uv run leichtfacile eval reference --role all --lang de --region DE --results eval/results-publicai
uv run leichtfacile eval run --cache --condition P2 --lang de --region DE --preset publicai-apertus --writer swiss-ai/apertus-v1.5-70b --results eval/results-publicai
# the Swiss pairs on Public AI (3 November 2026): the 70B at every stage, then the shipped
# default, on the pairs of the reference numbers, every condition; the comparison takes
# the P2 rows from the same folder
uv run leichtfacile eval reference --role all --lang de --region CH --results eval/results-publicai
uv run leichtfacile eval reference --role all --lang fr --results eval/results-publicai
uv run leichtfacile eval run --cache --condition P2 --lang de --region CH --preset publicai-apertus --writer swiss-ai/apertus-v1.5-70b --results eval/results-publicai
uv run leichtfacile eval run --cache --condition P2 --lang fr --preset publicai-apertus --writer swiss-ai/apertus-v1.5-70b --results eval/results-publicai
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
`uv tool install https://github.com/bobrovsky420/leicht-facile/releases/download/v0.13.2/leichtfacile-0.13.2-py3-none-any.whl`.
Every release made after 31 October 2026 carries signed provenance and a bill of
materials, for the wheel and for the container image;
[SECURITY.md](../SECURITY.md#verifying-a-release) has the commands that verify a
download against this repository.

```bash
leichtfacile serve        # opens http://127.0.0.1:8000/model
```

- Everything said under way 1 holds, without the `uvx` in front.
- `uv tool install` puts the app into a virtual environment of its own in uv's tools
  folder (`uv tool dir`: `%APPDATA%\uv\tools` on Windows, `~/.local/share/uv/tools`
  elsewhere) and the `leichtfacile` command into `uv tool dir --bin` (`~/.local/bin`, on
  Windows `%USERPROFILE%\.local\bin`).
- `python -m leichtfacile` does the same as `leichtfacile`.
- `uv tool upgrade leichtfacile` (or `pip install -U leichtfacile`) gets a newer release;
  nothing updates it by itself ([Updates](#updates)).
- `uv tool uninstall leichtfacile` removes the program with the language models; the
  config file and the data stay.

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
  ([docs/use-case-decisions.md](use-case-decisions.md)); without `--notice` the export
  carries the default notice of the installation's variety (`varieties.toml`), as the
  web form does:

  ```bash
  leichtfacile simplify entscheid.txt --mode decision --addressee "Lea Muster" \
    --notice "Diese Erklärung hilft Ihnen, den Entscheid zu verstehen. Massgebend ist der Entscheid."
  ```

  `--sender school` (or `organisation`) and `--address informal` (or `plural`) make the
  prompts call the text a school's or an organisation's and let it address the reader
  with du or ihr (tu; tu or voi), as the two selects of the New draft form do
  ([docs/architecture.md §4.3](architecture.md#43-plan-and-write-model)).

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
sudo /opt/leichtfacile/bin/leichtfacile $CONFIG setup
sudo /opt/leichtfacile/bin/leichtfacile $CONFIG config set data.dir /var/lib/leichtfacile
sudo chown -R leichtfacile /etc/leichtfacile
sudo install -d -o leichtfacile /var/lib/leichtfacile
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
curl http://127.0.0.1:8000/readyz          # "ok" once the provider answers
```

- `setup` writes the preset into `/etc/leichtfacile/config.toml` and its key into
  `/etc/leichtfacile/.env`, both readable by the service's user alone after the `chown`.
  The app's model page is read-only on a published server (every user shares one
  login); `[llm] offer = ["<preset>"]` shows the users one model and no page at all.
- `StateDirectory` keeps `/var/lib/leichtfacile` for the service's user.
- The app reads the config file itself through `LEICHTFACILE_CONFIG`;
  `Environment=LEICHTFACILE_<SECTION>__<KEY>=...` lines override single settings.
- For the direct way, `config set auth.token <secret>` and `config set server.host
  0.0.0.0` (with `$CONFIG`, as above): the secret goes into `/etc/leichtfacile/.env` as
  `LEICHTFACILE_TOKEN`, and the config file names the variable (`auth.token_env`), so no
  secret stands in it. Without the value the command asks for it, hidden, and nothing
  lands in the shell history.
- `data.retention_days` deletes jobs after so many days, `log.format = "json"` writes one
  JSON object per line for a log collector, and `jobs.workers` runs jobs side by side when
  the provider serves parallel requests ([configuration.md](configuration.md#reference)).
- The container image (way 7) brings the service user and the data folder with it, and
  its login rule follows the address the port is published on; the service is then
  `docker compose up -d` in the folder of `compose.yaml`.

### Windows

The same on Windows Server, in PowerShell as an administrator: Python 3.12 or newer
installed for all users (python.org's installer with "Install for all users"; a Python
that uv or the Microsoft Store installed lives in one user's profile, which a service
account cannot read), the program in `C:\Program Files\leichtfacile`, the config file,
the `.env` and the data under `C:\ProgramData\leichtfacile`, the app under the built-in
account `NT AUTHORITY\LocalService`:

```powershell
py -3 -m venv "C:\Program Files\leichtfacile"
& "C:\Program Files\leichtfacile\Scripts\pip" install leichtfacile
New-Item -ItemType Directory C:\ProgramData\leichtfacile
icacls C:\ProgramData\leichtfacile /inheritance:r /grant:r "BUILTIN\Administrators:(OI)(CI)F" "NT AUTHORITY\SYSTEM:(OI)(CI)F" "NT AUTHORITY\LocalService:(OI)(CI)M"
$lf = "C:\Program Files\leichtfacile\Scripts\leichtfacile.exe"
$config = "C:\ProgramData\leichtfacile\config.toml"
& $lf --config $config setup
& $lf --config $config config set data.dir C:\ProgramData\leichtfacile\data
```

- `icacls` stands in for the `chown` above: the owner-only mode that `setup` gives the
  config file and the `.env` on Linux has no counterpart on Windows, and a folder under
  `%ProgramData%` is readable by every user of the machine otherwise. Run it before
  `setup`, so the files it writes inherit the folder's permissions: administrators, the
  system and the service account alone.
- `--config` names the file at every call (the variable `LEICHTFACILE_CONFIG` does the
  same); without it the service would look for `%APPDATA%\leichtfacile\config.toml` of
  its own account, under `C:\Windows\ServiceProfiles\LocalService`.

Windows runs a program as a service through a service wrapper;
[WinSW](https://github.com/winsw/winsw) (MIT licence) is one. Put its `WinSW-x64.exe`
from the releases page into `C:\ProgramData\leichtfacile` as `leichtfacile-service.exe`,
after checking its SHA-256 (`Get-FileHash`) against the digest the page shows, with
`leichtfacile-service.xml` next to it:

```xml
<service>
  <id>leichtfacile</id>
  <name>Leicht-Facile</name>
  <description>Leicht-Facile, letters in Easy Language</description>
  <executable>C:\Program Files\leichtfacile\Scripts\leichtfacile.exe</executable>
  <arguments>--config C:\ProgramData\leichtfacile\config.toml serve --no-browser</arguments>
  <serviceaccount>
    <username>NT AUTHORITY\LocalService</username>
  </serviceaccount>
  <logpath>C:\ProgramData\leichtfacile\logs</logpath>
  <log mode="roll-by-size">
    <sizeThreshold>10240</sizeThreshold>
    <keepFiles>8</keepFiles>
  </log>
  <onfailure action="restart" delay="10 sec"/>
</service>
```

```powershell
& C:\ProgramData\leichtfacile\leichtfacile-service.exe install
Start-Service leichtfacile
Get-Content C:\ProgramData\leichtfacile\logs\leichtfacile-service.err.log -Wait   # the log
Invoke-RestMethod http://127.0.0.1:8000/readyz        # "ok" once the provider answers
```

- The service appears in `services.msc` as Leicht-Facile, starts with the system and is
  restarted when it fails; `Stop-Service leichtfacile` stops it,
  `leichtfacile-service.exe uninstall` removes it. Without a wrapper, a scheduled task
  runs the same command at startup under the service account (`Register-ScheduledTask`
  with `New-ScheduledTaskTrigger -AtStartup`, `New-ScheduledTaskPrincipal -UserId
  'NT AUTHORITY\LocalService' -LogonType ServiceAccount` and a
  `New-ScheduledTaskSettingsSet` with restarts and no execution time limit); its output
  goes nowhere unless the command redirects it to a file.
- Behind IIS (URL Rewrite with Application Request Routing) with Windows Authentication,
  the users log in with their domain accounts: the reverse-proxy rule sets the server
  variables `HTTP_X_FORWARDED_USER` to `{LOGON_USER}`, `HTTP_X_FORWARDED_PROTO` to
  `https` and `HTTP_X_FORWARDED_FOR` to `{REMOTE_ADDR}` (allowed first under the site's
  URL Rewrite, View Server Variables), and the app takes `auth.proxy_header =
  "X-Forwarded-User"` with `auth.proxy_from = ["127.0.0.1"]`.
- For the direct way, `config set auth.token <secret>` and `config set server.host
  0.0.0.0` as above, and a firewall rule: `New-NetFirewallRule -DisplayName Leicht-Facile
  -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow`.

## 6. Offline install (air-gapped)

On a connected machine with the same operating system, CPU architecture and Python
version as the target, collect the app with every dependency, the three language
packages among them, in one folder:

```bash
pip wheel leichtfacile -w wheelhouse
```

`pip wheel` downloads the wheels and builds one for any dependency published only as
source. Carry the folder over and install on the target:

```bash
python3 -m venv /opt/leichtfacile
/opt/leichtfacile/bin/pip install --no-index --find-links wheelhouse leichtfacile
```

The model server runs inside the network too, with its weights carried over the same way
(llama-server takes a local file with `-m <file>.gguf` instead of `-hf`). Point the app at
it with `leichtfacile setup local` and run it as in way 5.

## 7. In a container

The image `ghcr.io/bobrovsky420/leichtfacile` holds the app with every dependency, the
language packages of the checker among them, so a container needs no network but the
model endpoint. One tag per release (`:0.13.2`) and `:latest`, x86-64, built from the
`Dockerfile` of the checkout and published by a release. The app runs as a user of its
own and keeps everything it writes in `/data` (the config file, the `.env` with the key,
the database). On this machine, for the browser on it, as with `leichtfacile serve`:

```bash
docker run -d --name leichtfacile -p 127.0.0.1:8000:8000 -v leichtfacile:/data \
  -e LEICHTFACILE_SERVER__PUBLISHED_ON=127.0.0.1 -e PUBLICAI_API_KEY=<key> \
  ghcr.io/bobrovsky420/leichtfacile:0.13.2
```

- The app listens on every interface of its container, and `-p` says where Docker
  publishes the port; `server.published_on` tells the app the same, and the login rule
  judges it instead of the bind address
  ([Reaching the app from other machines](#reaching-the-app-from-other-machines)).
  `-p 127.0.0.1:8000:8000` with `LEICHTFACILE_SERVER__PUBLISHED_ON=127.0.0.1` reaches
  this machine alone, for the browser on it or a reverse proxy on it, and no login is
  needed. `-p 8000:8000` publishes the app on every interface; then it needs a login, as
  any app published beyond one machine does: `-e LEICHTFACILE_AUTH__TOKEN=<secret>` for
  the token login inside a trusted network, or, behind the proxy, its user header
  `-e LEICHTFACILE_AUTH__PROXY_HEADER=X-Forwarded-User -e LEICHTFACILE_AUTH__PROXY_FROM=172.16.0.0/12`,
  the proxy's address as the container sees it (Docker's bridge networks). Without
  `published_on` the app takes its bind address as published; without a login it then
  stops at once, and `docker logs leichtfacile` says what it lacks.
- Any setting is a variable, `LEICHTFACILE_<SECTION>__<KEY>`
  ([configuration.md](configuration.md#environment-variables)); a provider's key is its
  variable (`PUBLICAI_API_KEY`, `CSCS_API_KEY`, ...), and the first preset whose key is set
  is in use. Or run setup inside the container once, which writes the preset and the key
  into the volume: `docker run --rm -it -v leichtfacile:/data
  ghcr.io/bobrovsky420/leichtfacile:0.13.2 leichtfacile setup`. The model page is
  read-only on a published server, as in way 5.
- The named volume `leichtfacile` holds `config.toml`, `.env` and the database (a folder
  of the host does too, when the user 10001 may write to it). `/healthz` and `/readyz`
  answer without a login, and the image's own health check asks `/healthz`.

`compose.yaml` in the repository does the same with `docker compose up -d`: the settings
and the keys in a `.env` next to it (`PUBLICAI_API_KEY=...`; `LEICHTFACILE_VERSION=0.13.2` pins
the tag), the data in the volume `leichtfacile_data`, the port published on this machine
alone and the app told so, without a login; `LEICHTFACILE_PUBLISH=0.0.0.0` in `.env`
publishes it on every interface, and the app then needs its login there too
(`LEICHTFACILE_AUTH__TOKEN=...`). It also starts the model server
of way (a) on one NVIDIA GPU of the same machine (Docker with the NVIDIA Container
Toolkit): `--profile vllm` runs Apertus 1.5 8B on vLLM with the official image and the
flags measured on an L4 ([Apertus 1.5 8B on vLLM](#apertus-15-8b-on-vllm-one-24-gb-gpu);
`HF_TOKEN=...` in `.env` for the gated weights, about 18 GB downloaded on the first start),
`--profile llamacpp` the 4-bit conversion on llama.cpp for an 8 GB GPU. Both images are
pinned by digest in `compose.yaml`, so a pull brings the same server until the digest is
changed (Dependabot proposes the next one once it is a week old), and every container runs
with every capability dropped, the app's and llama.cpp's on a read-only root. The app
reaches the server on the compose network, and one `setup` points it there:

```bash
docker compose --profile vllm up -d
docker compose run --rm app leichtfacile setup vllm --model swiss-ai/Apertus-v1.5-8B
```

(`setup local --name llamacpp --model apertus-v1.5-8b-q4-llamacpp` for the other
profile.) Air-gapped, as way 6 for containers: on a connected machine
`docker save ghcr.io/bobrovsky420/leichtfacile:0.13.2 | gzip > leichtfacile-0.13.2.tar.gz`,
carry it over, `docker load < leichtfacile-0.13.2.tar.gz`; the model server's image and its
weights the same way. A build from a checkout: `docker build -t leichtfacile .` (or
`docker compose up -d --build`; `make run` does that and opens the web UI). CI builds the image, starts it with a token against an
unreachable endpoint, checks the probes and the login and scans it for vulnerabilities
that have a fix (`.github/workflows/ci.yml`).

## Updates

Only way 1 gets a newer release by itself; the others are updated by hand. An update
keeps the config file, the keys and the data, and a newer release brings the database up
to date on its first start, keeping a copy of it as it was in `backups/` next to it
(`leichtfacile-v<schema>.sqlite`, one per schema version, replaced at the next update
from the same version). A running app stays on its version until it starts again. An
older release refuses a database a newer one has written and says so; to go back,
restore the copy ("Backup and restore" below). The copies hold the documents: delete
them under the same records rules as the data.

| Way | A newer release arrives | By hand |
|-----|-------------------------|---------|
| 1. `uvx leichtfacile` | at the next start: uvx checks PyPI each time and trusts its list for up to 10 minutes, so a release arrives at the latest 10 minutes after it is out | `uvx leichtfacile@latest serve` checks at once |
| 2. A checkout | after a pull | `git pull`; the next `uv run` installs what changed |
| 3. `uv tool install leichtfacile` | never by itself | `uv tool upgrade leichtfacile`. An install of one version (`leichtfacile==0.7.0`) or of a wheel's address stays on it even then: `uv tool install leichtfacile@latest` |
| 3. `pip install leichtfacile` | never by itself | `pip install -U leichtfacile` |
| 5. On a server | never by itself | `sudo /opt/leichtfacile/bin/pip install -U leichtfacile`, then `sudo systemctl restart leichtfacile` |
| 6. Offline | never by itself | a new wheelhouse from a connected machine, then `/opt/leichtfacile/bin/pip install -U --no-index --find-links wheelhouse leichtfacile` |
| 7. A container | never by itself | `docker compose pull && docker compose up -d` (or `docker run` with the new tag); the volume keeps the config file, the key and the data |

With the command installed (way 3), `uvx leichtfacile` runs the installed version, not
the newest one; `uvx leichtfacile@latest` runs the newest and leaves the installed one as
it is. `leichtfacile --version` shows the version in use, and each release on the
[releases page](https://github.com/bobrovsky420/leicht-facile/releases) links its changes.

Up to 0.7.1, `leichtfacile models` unpacked the spaCy models into `models/` in
`data.dir`. They come with the package now, so that folder (about 120 MB) is no longer
read and can be deleted.

### Backup and restore

`leichtfacile backup <folder>` writes a consistent copy of the job database into the
folder, named with the moment (`leichtfacile-20261103T201500Z.sqlite`), while the app
runs or not. The response cache (`llm_cache.sqlite`) is not copied: a deleted job's
prompts must not outlive it there either. Keep the copies under the same rules as the
data; they hold the documents.

To restore: stop the app, replace `leichtfacile.sqlite` in `data.dir` with the copy,
delete `leichtfacile.sqlite-wal` and `leichtfacile.sqlite-shm` next to it if they exist,
and start the app. A copy from an older release is brought up to date on that start; one
from a newer release is refused with a message, so going back to an older release needs
the copy made before the update (`backups/`, above).

## Running a model yourself

Running a model is outside the app: start a model server, and the app's model page lists
its models under "This computer" (the providers `local` for llama.cpp, `ollama` and
`vllm` know the server's port and thinking switch); choosing one saves it as a preset of
your own. On the command line, `leichtfacile setup local` (or `ollama`, `vllm`) asks for
the model from the server's list. Two setups are known to work.

### Apertus 1.5 8B on vLLM, one 24 GB GPU

The Swiss AI team's official vLLM image ran Apertus 1.5 8B (the official bf16 weights) on
one NVIDIA L4 with 24 GB; [docs/hardware/aws-l4-2026-10-10/](hardware/aws-l4-2026-10-10/)
shows the commands used, the memory and the timings. On a 24 GB card the server needs
`--kv-cache-dtype=fp8` and `--max-num-seqs=16` next to `--max-model-len=32768`: the stages
ask for up to 16,000 output tokens on top of the prompt. The weights are gated: accept
their terms on Hugging Face once and give the server a token (`HF_TOKEN`). The app's
preset:

```bash
leichtfacile setup vllm --base-url http://<model server>:8000/v1 --model swiss-ai/Apertus-v1.5-8B
```

- The `vllm` provider brings `thinking = "chat-template"` and the key `local` (any value,
  unless the server was started with a key); the command saves the address in
  `[providers.vllm]` and the model as the preset `vllm-swiss-ai-apertus-v1-5-8b`.
- The judge is then the 8B too, the only model the server lists.
- vLLM serves parallel requests, so `[jobs] workers = 2` or more runs jobs side by side.
- On the L4 one letter took 63 minutes with the default thinking stages and 22 minutes
  with `thinking_stages = ["understand"]`.
- vLLM listens on port 8000 by default, as the app does: on one machine, start one of
  them on another port.
- `compose.yaml` starts the same server next to the app's container, with these flags:
  `docker compose --profile vllm up -d` (way 7).

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

The `local` provider switches thinking through the chat template (`--jinja`) and allows
30 minutes per call, since a thinking call takes minutes on a small GPU; the command
saves the preset `laptop`, and `leichtfacile config set presets.laptop.thinking_stages
'["understand"]'` keeps the judge from thinking too (or the model page's fine-tune panel
does).

### Other models

Ollama: the model page lists the models `ollama list` shows; `leichtfacile setup ollama`
does the same on the command line. Any other OpenAI-compatible server: `leichtfacile
setup` with its address, or `setup <name> --base-url <address>`. Thinking stays off
unless the server switches it through the chat template. The reported numbers hold for
Apertus 1.5 only.

## Reaching the app from other machines

By default the app answers on this machine only (`127.0.0.1:8000`). Published on any
other address, it needs one of two logins and refuses to start without one.

- **Behind a reverse proxy (recommended).** Keep `--host 127.0.0.1` (the default) and let
  the proxy end TLS, log the users in and publish the app. Optionally trust its user
  header: `auth.proxy_header = "X-Forwarded-User"` (or `Remote-User`) with
  `auth.proxy_from`, the proxy's addresses or networks (`["127.0.0.1"]` for a proxy on the
  same machine). A request from elsewhere is refused (403), one without the header is not
  logged in (401). With the proxy on another machine, `--host` names an address the proxy
  reaches, and the header counts as the login. The user the header names is recorded: on
  the job they submit, on every review decision they save, on the audit bundle and in the
  Word footer, and in the access line, so the audit trail says who approved what. The app takes the user's address from the
  proxy's `X-Forwarded-For` (for its rate limit and its log) and the scheme from its
  `X-Forwarded-Proto` (so its cookies are marked `Secure` and its links are https),
  trusted from the addresses in `auth.proxy_from`, or, without it, from a proxy on this
  machine (127.0.0.1); from anywhere else the headers mean nothing.
- **Directly.** `leichtfacile serve --host 0.0.0.0` (every interface) with a token:
  `leichtfacile config set auth.token <secret>` stores it in the `.env` next to the
  config file as `LEICHTFACILE_TOKEN` and names the variable in the file
  (`auth.token_env`); the variable can also come from the environment
  ([configuration.md](configuration.md#keys)). A token written into the config file
  itself (`auth.token = "..."`) works, with a warning at every start. Browsers ask for it
  (HTTP Basic: any user name, the token as the password); scripts send
  `Authorization: Bearer <secret>`. Without TLS the token crosses the network readable, so
  use this inside a trusted network. A secret:
  `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- **In a container.** The app binds every interface of its container, and the runtime
  publishes the port: `server.published_on` names the address it is published on
  (`-p 127.0.0.1:8000:8000`: `127.0.0.1`), and the login rule judges it instead of
  `--host`. Without it a container counts as published everywhere (way 7).

`auth.token` and `auth.proxy_header` exclude each other. `/healthz`, `/readyz` and the
static files need no login. Details:
[docs/operations.md](operations.md#6-security-and-privacy).

## When it does not start

| Message or symptom | Fix |
|--------------------|-----|
| `The preset publicai-apertus is not ready: - llm.api_key: the variable PUBLICAI_API_KEY ... is not set` (a command that calls the model) | `leichtfacile setup <preset>` (for example `setup publicai-apertus`), the key in a `.env` in the current folder, or another preset: `leichtfacile preset list`. `serve` starts anyway and its model page asks for the key |
| `The settings are not valid: - server.prot (...): Extra inputs are not permitted` | a misspelt key or a wrong value; the message names the file or the variable it came from |
| `llm.preset = '...': no such preset; known: ...` | a preset that is not shipped and not in the file: `leichtfacile preset list`, or `leichtfacile setup` for a new one |
| `failed to hardlink file ... incompatible hardlinks. (os error 396)` from `uvx` or `uv tool install` (Windows) | uv links files from its cache, and Windows refuses another link to a file that already has one in a OneDrive folder (for example a checkout's `.venv` there). Add `--link-mode=copy` (`uvx --link-mode=copy leichtfacile setup`), or set it for good in PowerShell with `[Environment]::SetEnvironmentVariable('UV_LINK_MODE', 'copy', 'User')` and open a new terminal |
| `leichtfacile: command not found` after `uv tool install` | `uv tool update-shell`, then open a new terminal |
| setup says `Nothing changed (... exists in ...; --force updates it)` | `leichtfacile setup --force`, or `leichtfacile config edit` |
| setup says `The provider's model list could not be read` | the address or the key is wrong, or the server is not running; setup goes on, and `leichtfacile check-llm` (or the model page's Check the key) checks again later |
| settings seem to be ignored | `leichtfacile config show` names the source of each setting: a `leichtfacile.toml` in the current folder, a `LEICHTFACILE_` variable or a flag wins over the config file |
| `server.host = '0.0.0.0' publishes the app beyond this machine` | set a token (`leichtfacile config set auth.token <secret>`), or `auth.proxy_header` with `auth.proxy_from`, or serve on 127.0.0.1; in a container whose port is published on this machine alone, `server.published_on = "127.0.0.1"` (way 7) |
| `auth.proxy_header needs auth.proxy_from` | set the proxy's addresses or networks |
| `set auth.token or auth.proxy_header, not both` | keep one of them |
| the browser does not open | it opens only for an app on this machine and, on Linux, with a desktop; open <http://127.0.0.1:8000> yourself |
| `/readyz` says `degraded` | the preset is not ready (no key), its provider is unreachable or does not list the writer's or the judge's model; the model page and `leichtfacile check-llm` show why. Review, export and Check my text still work |
| port 8000 in use (also by vLLM) | `leichtfacile serve --port 8001`, or move the other service |
