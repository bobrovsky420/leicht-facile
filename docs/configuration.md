# Configuration

Leicht·Facile keeps its settings in one TOML file with a section per topic. The known
model endpoints come with the app as presets, so the file names the one in use and holds
what differs from it. `leichtfacile setup` writes it, `leichtfacile config` shows and
changes it, and every setting has a default except the model endpoint.

```toml
[llm]
endpoint = "cscs"                     # the endpoint in use: a preset or a saved one

[endpoints.laptop]
url = "http://127.0.0.1:8080/v1"
api_key = "local"
thinking = "chat-template"
thinking_stages = ["understand"]
timeout_s = 1800
models = { writer = "apertus-v1.5-8b-q4-llamacpp" }

[server]
port = 8001

[data]
retention_days = 90
```

The key of the `cscs` endpoint is not in the file: the preset names the variable
`CSCS_API_KEY`, which comes from the environment or from a `.env` file
([Keys](#keys)).

## Where the settings come from

Each source overrides the one before:

1. the defaults ([Reference](#reference));
2. the preset an endpoint starts from ([Presets](#presets));
3. the user's config file, written by `leichtfacile setup` and `leichtfacile config set`;
4. `leichtfacile.toml` in the current folder: a checkout's or a project's own settings;
5. environment variables `LEICHTFACILE_<SECTION>__<KEY>` ([Environment
   variables](#environment-variables));
6. the command line: `--endpoint`, and `--host` and `--port` of `serve`.

`leichtfacile config show` lists every setting with its value and the source it came
from, so a setting that seems ignored shows what overrides it.

| System | Config file | `data.dir` by default |
|--------|-------------|-----------------------|
| Windows | `%APPDATA%\leichtfacile\config.toml` | `%LOCALAPPDATA%\leichtfacile` |
| macOS | `~/Library/Application Support/leichtfacile/config.toml` | `~/Library/Application Support/leichtfacile` |
| Linux and others | `$XDG_CONFIG_HOME/leichtfacile/config.toml`, else `~/.config/leichtfacile/config.toml` | `$XDG_DATA_HOME/leichtfacile`, else `~/.local/share/leichtfacile` |

`--config <file>` (before the command: `leichtfacile --config /etc/leichtfacile/config.toml
serve`) or the variable `LEICHTFACILE_CONFIG` names another config file. A relative
folder in a file (`data.dir`, `data.examples_dir`) is taken from that file's folder.
A key the app does not know is an error, so a misspelt key never goes unnoticed.

## Endpoints

Any OpenAI-compatible endpoint works: a cloud API, a gateway or a model server the
organisation runs. The app itself never runs a model.

- The presets ([Presets](#presets)) are endpoints as they come: `cscs` and `apertus` need
  nothing but their key. `[endpoints.<name>]` saves another endpoint, or what differs from
  the preset of the same name: its address (`url`), its key, its models, how it switches
  thinking, a `label` for the New draft form. Names are lowercase letters, digits, `-`
  and `_`.
- An endpoint is ready when it has an address, a writer model and a key (given, or its
  variable set). `leichtfacile endpoint list` shows every endpoint and what it lacks.
- `[llm]` is the endpoint in use. `llm.endpoint` names a preset or a saved endpoint;
  without it, the only ready endpoint is in use, so one key in the environment is enough
  (two ready and none named: `leichtfacile endpoint use <name>`). Every other key in
  `[llm]` overrides the endpoint's, whichever it is: `[llm] cache = true` caches the
  answers of every endpoint.
- `leichtfacile setup <name>` gives a preset its key and uses it, `leichtfacile endpoint
  use <name>` switches, and `--endpoint <name>` picks one for a single run of `serve`,
  `simplify`, `check-llm` or `eval run`.
- The New draft form offers every ready endpoint for one draft when there are at least
  two: the job records its choice and runs on that endpoint, and the one in use stays.

### Presets

A preset holds what is known about an endpoint and is an endpoint itself. A saved
`[endpoints.<name>]` of the preset's name extends it and holds only what differs; one of
another name names it with `preset = "<name>"`. The presets ship with the package, so an
upgrade fixes a known endpoint for every user.

The presets are the tables of `src/leichtfacile/presets.toml`, one per preset and named
after it, in the order `leichtfacile setup` offers them. A table takes the keys of an
`[endpoints.<name>]` table, `label` among them (the name in setup's list and in the New
draft form). A new table is a new preset; `tests/test_config.py` checks every table's
keys and values.

```toml
# src/leichtfacile/presets.toml
[cscs]
label = "Apertus on the CSCS inference API"
url = "https://api.inference.cscs.ch/v1"
api_key_env = "CSCS_API_KEY"
models = { writer = "swiss-ai/Apertus-v1.5-8B", judge = "swiss-ai/Apertus-v1.5-70B" }
thinking = "model-suffix"
```

| Preset | Endpoint | What it sets |
|--------|----------|--------------|
| `cscs` | Apertus on the CSCS inference API, Lugano: the endpoint of the reported numbers | the address, the key from `CSCS_API_KEY`, the 8B writing and the 70B judging, `thinking = "model-suffix"` (thinking models are separate names ending in `-thinking`) |
| `apertus` | Apertus on the Public AI gateway, for public documents only | the address, the key from `PUBLICAI_API_KEY`, the 8B and the 70B in the gateway's spelling, `thinking = "chat-template"`, and `extra_body` turning the gateway's response cache off |
| `local` | llama.cpp (llama-server) on this machine, or another OpenAI-compatible server (`--base-url`) | `http://127.0.0.1:8080/v1`, the key `local` (such a server takes any key), `thinking = "chat-template"` (llama.cpp with `--jinja`) and 30 minutes per call (a thinking call on a small GPU takes minutes) |
| `ollama` | Ollama on this machine | `http://127.0.0.1:11434/v1` and the key `ollama` (ignored); thinking off, since Ollama ignores the chat-template switch: a thinking model such as Qwen takes `thinking = "reasoning-effort"` on the saved endpoint |
| `vllm` | vLLM, mostly a GPU machine of the organisation (`--base-url http://<server>:8000/v1`) | `http://127.0.0.1:8000/v1` (the app's port too: on one machine start one of them elsewhere), the key `local`, `thinking = "chat-template"` |
| `openai` | OpenAI; public documents only | the address, the key from `OPENAI_API_KEY`, `max_tokens_key = "max_completion_tokens"` and `send_temperature = false` (its GPT-5 models refuse `max_tokens` and any temperature but their default; a GPT-4.1 model takes `send_temperature = true` on the saved endpoint). Thinking is `reasoning_effort`: `thinking = "reasoning-effort"` on the saved endpoint, `thinking_stages = []` for none everywhere |
| `mistral` | Mistral AI | the address and the key from `MISTRAL_API_KEY` |
| `groq` | Groq, a US cloud with very fast inference; public documents only | the address and the key from `GROQ_API_KEY`; no model, since Groq's catalogue changes (several models are previews): `setup groq` lists it. thinking stays off: Qwen reasons on Groq only when asked with `reasoning_effort` low, medium or high, and the gpt-oss models refuse `none` |
| `huggingface` | The Hugging Face Inference Providers router, which sends each request to a third-party provider; development and public documents only | the address and the token from `HF_TOKEN`; no model: Hugging Face ids with an optional provider suffix (`Qwen/Qwen3.5-9B:groq`), `setup huggingface` lists them |
| `anthropic` | Anthropic's Claude through its OpenAI-compatible endpoint (chat completions only); public documents only | the address, the key from `ANTHROPIC_API_KEY`, `send_temperature = false` (the 5.5 models refuse a temperature) and the header `anthropic-version` the model list needs; no model: `setup anthropic` lists them. The endpoint ignores `reasoning_effort` and counts Claude's adaptive thinking in `max_tokens`; switch it off on the saved endpoint with the native field, `extra_body = { thinking = { type = "disabled" } }` on Haiku 5.5 or `{ type = "between_tools" }` on Sonnet 5.5 (Opus 5.5 always thinks) |

The three servers of one's own have no model in the preset, since each server names its
own: `leichtfacile setup local` (or `ollama`, `vllm`) lists the server's models and asks
which one; `--model <name>` gives it. A preset with a model would count as ready while
nothing listens at its address.

Notes on the endpoints:

- CSCS closes about one long thinking stream in four midway (checked 6 October 2026);
  the client retries (`llm.max_retries`, 8 by default), which makes a hard failure rare.
- Public AI is run by Metagov Inc. (US nonprofit) and routes requests to compute
  partners: not a sovereign deployment, never for documents with personal data. Pay per
  token after USD 2 of starter credit; the key comes from platform.publicai.co. Checked
  on 6 October 2026: `apertus-v1.5-8b` goes to Juelich (vLLM) and thinks when asked
  through the chat template, but about one call in three answers without reasoning;
  `apertus-v1.5-70b` goes to Infomaniak and ignores the switch, so the 70B judges without
  thinking. Its `-thinking` names serve the older Apertus 1 without thinking: do not use
  them. Thinking comparisons need the CSCS endpoint.
- A provider's cloud (OpenAI, Mistral AI, others): check where it processes the text
  before sending anything confidential. Thinking stays off.
- Groq and the Hugging Face router process the text in the United States or on
  third-party clouds: development and public documents only. The Hugging Face router
  served the older Apertus 1 (2509) when checked; results from either are no Apertus 1.5
  numbers.

### Models

`models.writer` reads, writes and repairs. `models.judge` grades the drafts; when it is
not set, the judge is the 70B of an Apertus 8B writer if the endpoint lists it (the setup
the evaluation measured), else the writer. `models.understand` lets another model read
the source. The tiers compared in [evaluation.md](evaluation.md):

- default: the 8B reads, writes and repairs, the 70B judges (one GPU on-premise);
- quality: `models = { writer = "swiss-ai/Apertus-v1.5-70B" }` runs every stage on the
  70B (cleaner style, fewer facts kept, about twice the price per page; the judge then
  grades its own drafts);
- hybrid: `models = { understand = "swiss-ai/Apertus-v1.5-70B" }` lets the 70B read and
  the 8B write (it kept the fewest facts, [prompts.md](prompts.md)).

`/readyz` names the models in use; the New draft form takes other models for one job.

### Thinking

Thinking is off by default (`thinking = "off"`), since every endpoint switches it its own
way:

- `model-suffix`: the thinking model is a separate model named `<model>-thinking`
  (Apertus on CSCS; `thinking_suffix` changes the ending);
- `chat-template`: the request switches it through the chat template (vLLM, llama.cpp);
- `reasoning-effort`: the request sends the OpenAI field `reasoning_effort = "none"` for
  the stages that do not think and leaves the model's default for the others: for a
  thinking model such as Qwen on Ollama, whose `/v1` endpoint ignores the other switches.

It applies to the stages in `thinking_stages` (default `["understand", "judge"]`).
`leichtfacile check-llm --thinking` makes its test call with thinking and says whether
reasoning came back.

## Keys

A key is given in a file or named by a variable:

```toml
[endpoints.mine]
url = "https://llm.example.org/v1"
api_key_env = "MINE_API_KEY"          # or: api_key = "..."
```

A named variable comes from the environment, else from `.env` in the current folder, else
from `.env` next to the config file. A `.env` file holds such keys (`MINE_API_KEY=...`)
and nothing else: settings in it are not read. `auth.token` and `auth.token_env` work the
same way.

`leichtfacile setup` asks for the key with hidden input and writes it into the `.env`
next to the config file, readable by its owner only where the system supports it, under
the preset's variable (`CSCS_API_KEY`) or `<NAME>_API_KEY` for an endpoint without one.
`--api-key-env <variable>` names a variable that is set already, and nothing is stored.

## Commands

| Command | Does |
|---------|------|
| `leichtfacile setup [name]` | gives a preset (`cscs`, `apertus`, ...) its key and uses it, asking nothing when the key's variable is set; without a name offers the presets and `other`; for another endpoint asks the address, a name, the key and the model (from the endpoint's list); saves what differs from a preset as `[endpoints.<name>]`; an endpoint saved already is updated with `--force`, its other keys kept |
| `leichtfacile endpoint list` | every endpoint, preset or saved, with its label, its writer model and whether it is ready (else what it lacks), the one in use marked `*` |
| `leichtfacile endpoint use <name>` | uses that endpoint, a preset or a saved one, from now on |
| `leichtfacile endpoint remove <name>` | removes a saved endpoint, or the saved settings that extend a preset (the preset stays) |
| `leichtfacile config show` | every setting, its value and its source; keys masked; what keeps the endpoint from working |
| `leichtfacile config show --defaults` | every setting with its default and meaning, as a config file to copy from |
| `leichtfacile config set <key> <value>` | sets a key (`server.port 8001`, `llm.cache true`, `endpoints.laptop.timeout_s 1800`) |
| `leichtfacile config unset <key>` | removes a key from the file, so the default or another source applies |
| `leichtfacile config edit` | opens the file in `VISUAL` or `EDITOR` (else Notepad, TextEdit, nano or vi) and checks it when the editor closes |
| `leichtfacile config path` | the config file's path |

`setup` takes its answers as flags too: `--preset`, `--name`, `--base-url`, `--api-key`,
`--api-key-env`, `--model`, `--judge`, `--force` (update an endpoint saved already) and
`--no-models` (leave the spaCy models for later). It asks only for what the preset and the
flags leave open, and nothing at all when the key's variable is set, so it runs from a
script:

```bash
leichtfacile setup cscs                           # asks for the key; the rest is the preset's
leichtfacile setup cscs --model swiss-ai/Apertus-v1.5-70B   # the preset with another writer
leichtfacile setup local --model apertus-v1.5-8b-q4-llamacpp --name laptop
leichtfacile check-llm                            # lists the endpoint's models, one short call
```

`--api-key` ends up in the shell history; leave it out to be asked. A value of
`config set` is read as TOML (`8001`, `true`, `["understand"]`), else taken as text.
Every change is checked with all the other sources before it is written: a key the app
does not know, a wrong value or an endpoint published without a login leaves the file
unchanged. The file keeps its comments and order. `--local` makes `endpoint use`,
`endpoint remove` and the `config` commands work on `./leichtfacile.toml` instead.

## Environment variables

`LEICHTFACILE_<SECTION>__<KEY>`, the parts joined by two underscores, sets any key:

```bash
LEICHTFACILE_LLM__ENDPOINT=apertus
LEICHTFACILE_SERVER__PORT=8001
LEICHTFACILE_LLM__MODELS__WRITER=swiss-ai/Apertus-v1.5-70B
LEICHTFACILE_ENDPOINTS__CI__URL=http://127.0.0.1:9/v1
LEICHTFACILE_LLM__THINKING_STAGES=understand,judge     # or JSON: ["understand", "judge"]
LEICHTFACILE_LLM__EXTRA_BODY='{"cache": {"no-cache": true}}'
```

A list is JSON or comma-separated, a table JSON; an empty variable sets nothing. In a
container or a CI job, three variables make an endpoint without any file:
`LEICHTFACILE_LLM__URL`, `LEICHTFACILE_LLM__API_KEY` and
`LEICHTFACILE_LLM__MODELS__WRITER`.

## In a checkout

A `leichtfacile.toml` in the checkout (git ignores it) holds what differs there, for
example the data in the repository's `data/`, where git ignores the database and the
caches, and the cached answers for the evaluation:

```toml
[llm]
endpoint = "cscs"
cache = true

[data]
dir = "data"
```

with the keys in the checkout's `.env`:

```bash
CSCS_API_KEY=...
PUBLICAI_API_KEY=...
```

## Reference

Every key with its default. `leichtfacile config show --defaults` prints the same as a
config file.

<!-- reference:start -->

### `[llm]`

The endpoint in use: `endpoint` picks a saved one, and every other key set here overrides that endpoint's.

A saved `[endpoints.<name>]` takes the same keys but `endpoint`.

| Key | Default | Meaning |
|-----|---------|---------|
| `endpoint` |  | The saved endpoint in use ([endpoints.&lt;name>]). Default: the only one saved. |
| `preset` |  | A known endpoint whose settings this one starts from: cscs, apertus, local, ollama, vllm, openai, mistral, groq, huggingface, anthropic. Default: the preset of the endpoint's own name, if there is one. |
| `label` |  | What the New draft form calls the endpoint. Default: the preset's label, else the endpoint's name. |
| `url` |  | The endpoint's address, for most servers ending in /v1. Required. |
| `api_key` |  | The key, written into the file. A server of your own takes any key. |
| `api_key_env` |  | Or the variable that holds the key: from the environment, else from .env in the current folder, else from .env next to the config file. |
| `models.writer` |  | The model that reads, writes and repairs. Required. |
| `models.understand` |  | The Understand stage's model, when it differs from the writer. |
| `models.judge` |  | The judge's model. Default: the 70B of an Apertus 8B writer when the endpoint lists it, else the writer. |
| `thinking` | `"off"` | How the endpoint switches thinking: model-suffix (a separate model named &lt;model>-thinking, Apertus on CSCS), chat-template (vLLM, llama.cpp), reasoning-effort (the OpenAI field, none for the stages that do not think; a thinking model on Ollama) or off. |
| `thinking_suffix` | `"-thinking"` | The thinking models' suffix. |
| `thinking_stages` | `["understand", "judge"]` | The stages that think, when thinking is on. |
| `stream` | `true` | Streamed answers, so that a proxy cannot time out a long one; false only for a server that cannot stream. |
| `max_tokens_key` | `"max_tokens"` | The request field for the output budget: max_tokens, or max_completion_tokens (OpenAI's GPT-5 models refuse max_tokens). |
| `send_temperature` | `true` | Send each stage's temperature; false for a model that takes only its default (OpenAI's GPT-5 models). |
| `timeout_s` | `300.0` | Seconds one call may take. |
| `max_retries` | `8` | Retries of a failed call. |
| `cache` | `false` | Keep the answers in data.dir and reuse them (development, evaluation). |
| `extra_body` | `{}` | Fields sent with every request, for a gateway's switches. |
| `headers` | `{}` | Headers sent with every request (anthropic-version for Anthropic's OpenAI-compatible endpoint). |

### `[pipeline]`

The rounds after the first draft (docs/architecture.md §4.6).

| Key | Default | Meaning |
|-----|---------|---------|
| `repair_rounds` | `3` | Repair rounds on the rule findings and the judge's; 0: none. |
| `facts_rounds` | `1` | Rounds that ask only for the must-keep facts still missing after the repair rounds; 0: none. |
| `missing_per_facts_round` | `10` | Missing facts one such round asks for (a repair round asks for 5). |
| `recover_facts` | `10` | Must-keep values still missing then, asked for one by one with their source paragraph, as one new version; 0: none. |
| `polish_rounds` | `1` | Repair rounds on the best version's rule findings alone, at the end; 0: none. |
| `vocabulary` | `true` | The vocabulary of hard words in the pipeline; false only to measure what it brings. |

### `[jobs]`

The job queue (docs/architecture.md §7).

| Key | Default | Meaning |
|-----|---------|---------|
| `workers` | `1` | Threads that run jobs; more than 1 needs an endpoint that serves parallel requests (vLLM does). |
| `queue_limit` | `50` | Jobs that may wait; a submission beyond them is refused (429). |
| `time_budget_s` | `7200.0` | Seconds a job may run before it stops with its finished stages kept; 0: no limit. |
| `ingest_slots` | `4` | Submissions read (fetched, parsed, segmented) at once; one beyond them is refused (429). |

### `[server]`

The web application (`leichtfacile serve`).

| Key | Default | Meaning |
|-----|---------|---------|
| `host` | `"127.0.0.1"` | The interface the app is published on (0.0.0.0: every interface); anything but this machine needs a login ([auth]). |
| `port` | `8000` | The port. |
| `open_browser` | `true` | Open the browser at the start, on this machine and, on Linux, with a desktop. |
| `ui_lang` | `"auto"` | Interface language for visitors who have not picked one: en, de, fr, or auto (the browser's). |
| `allow_private_urls` | `false` | Let users submit URLs of the internal network (an intranet). |
| `rate_limit_per_minute` | `120` | Writes (POST, PUT, PATCH, DELETE) per client address and minute; 0: no limit. |

### `[auth]`

The login, needed when the app is published beyond this machine (docs/architecture.md §10).

| Key | Default | Meaning |
|-----|---------|---------|
| `token` |  | A shared secret: browsers ask for it (any user name, the token as the password), scripts send Authorization: Bearer &lt;token>. |
| `token_env` |  | Or the variable that holds the token. |
| `proxy_header` |  | Or the header a reverse proxy fills with the logged-in user (X-Forwarded-User, Remote-User) ... |
| `proxy_from` | `[]` | ... trusted from these addresses or networks only (127.0.0.1, 172.16.0.0/12). |

### `[data]`

Where the app keeps its data. A relative folder is taken from the folder of the file that names it.

| Key | Default | Meaning |
|-----|---------|---------|
| `dir` | the user's app-data folder | The database, the caches and the spaCy models (models/). |
| `examples_dir` | the letters shipped with the package | A folder of example letters for the New draft form (.txt or .md, a .json of job settings next to each). |
| `retention_days` | `0` | Jobs nobody changed for this many days are deleted; 0 keeps everything. |

### `[log]`

The app's log. Document text is only ever logged at DEBUG (docs/architecture.md §10).

| Key | Default | Meaning |
|-----|---------|---------|
| `level` | `"INFO"` | DEBUG, INFO, WARNING, ERROR or CRITICAL. |
| `format` | `"text"` | text, or json: one JSON object per line (time, level, logger, message, request_id, job_id) for a log collector. |

<!-- reference:end -->
