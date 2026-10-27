# Configuration

Leicht·Facile keeps its settings in one TOML file with a section per topic. The known
model providers and the presets on them come with the app, so the file names the preset
in use and holds what is the user's own: a key's variable, a preset or a server of their
own, a changed setting. The model page of the web app and `leichtfacile setup` write it,
`leichtfacile config` shows and changes it, and every setting has a default, the preset
included (`cscs-apertus`).

```toml
[llm]
preset = "claude-haiku-5-5"           # the preset in use: shipped, or one of your own

[presets.laptop]                      # a preset of your own: a provider and its models
provider = "local"
models = { writer = "apertus-v1.5-8b-q4-llamacpp" }
thinking_stages = ["understand"]

[server]
port = 8001

[data]
retention_days = 90
```

The key of the `claude-haiku-5-5` preset is not in the file: its provider names the
variable `ANTHROPIC_API_KEY`, which comes from the environment or from a `.env` file
([Keys](#keys)).

## Where the settings come from

Each source overrides the one before:

1. the defaults ([Reference](#reference));
2. the shipped providers and presets ([Providers and presets](#providers-and-presets));
3. the user's config file, written by the model page, `leichtfacile setup` and
   `leichtfacile config set`;
4. `leichtfacile.toml` in the current folder: a checkout's or a project's own settings;
5. environment variables `LEICHTFACILE_<SECTION>__<KEY>` ([Environment
   variables](#environment-variables));
6. the command line: `--preset` (or `serve <preset>`), and `--host` and `--port` of
   `serve`.

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

## The model

Any OpenAI-compatible endpoint works: a cloud API, a gateway or a model server the
organisation runs. The app itself never runs a model. Three kinds of table describe
the model:

- A **provider** (`[providers.<name>]`) is where models run and how to reach them: the
  address (`url`), the key (`api_key`, or `api_key_env`, the variable that holds it),
  headers, and the request settings every model there takes (how it switches thinking,
  whether it takes a temperature, the output budget's field, extra body fields, the
  timeout). `location` (`ch`, `eu`, `us`, `world`, `local`) and `documents` (`any`,
  `public`) tell the interface where the text goes; `key_url` is where a key comes from;
  `discover = true` offers every model a local server lists.
- A provider's **models tables** (`[providers.<name>.models.<model>]`) hold what one
  model there needs, by its name or a pattern (`"gpt-5*"`): the tables whose pattern
  matches apply in the file's order, the one named after the model over them. `input_usd`
  and `output_usd` are USD per million tokens, for the cost per page the interface shows
  and the evaluation's "USD per page".
- A **preset** (`[presets.<name>]`) is what the user picks: a provider, the models that
  write, read and check (`models.writer`, `models.understand`, `models.judge`), a `label`,
  and any request setting as an override.

A request's settings come from the provider, then the table of the model called, then
the preset, then the user's tables of the same names (the config file extends a shipped
provider or preset with a table of its name, and adds new ones). A later value replaces
an earlier one, except in `extra_body`, whose fields add up: OpenRouter's provider table
sends `{ provider = { data_collection = "deny" } }`, a model's table adds
`{ reasoning = { enabled = false } }`, and the request carries both; a field set in both
tables (`reasoning`) takes the later value. Names are lowercase letters, digits, `-` and
`_`.

- A preset is ready when its provider has an address and a key (given, or its variable
  set) and it names a writer. `leichtfacile preset list` shows every preset and what it
  lacks; the model page shows the same.
- `[llm]` names the preset in use: `llm.preset` is a shipped preset or one of the user's
  own; without it the shipped default (`cscs-apertus`) is in use. Nothing is guessed
  from the keys in the shell: a forgotten key never picks a provider. `[llm]` takes two
  more keys, `cache` (keep the answers and reuse them, whichever preset is in use) and
  `offer` (the presets the interface offers, an organisation's choice; one preset alone
  hides the model page); a provider's or a preset's keys live in their tables, never in
  `[llm]`, so every value has one place to come from.
- The model page of the web app (`/model`, on the machine the app runs on) and
  `leichtfacile setup` pick a preset and take its key; `leichtfacile preset use <name>`
  switches, and `--preset <name>` (for the app also `serve <preset>`) picks one for a
  single run of `serve`, `simplify`, `check-llm` or `eval run`, nothing saved; a preset
  named so must be ready, since the model page cannot change what the command line
  picks, and `serve` stops with what it lacks.
- The New draft form offers every ready preset for one draft when there are at least
  two: the job records its choice and runs on that preset, and the one in use stays.
  The app starts without a ready preset: the checker, the review pages and the exports
  need no model, and the model page asks for the key.

### Providers and presets

The shipped providers and presets are the tables of `src/leichtfacile/presets/presets.toml`,
in the order the interface and `leichtfacile setup` list them; `default` names the
preset of a fresh install. A new table there is a new provider or preset;
`tests/test_config.py` checks every table's keys and values. A preset is named after
its models' versions and never changes meaning: a new model is a new preset, so a
name in a config file, a job or an evaluation run keeps pointing at the same thing.

```toml
# src/leichtfacile/presets/presets.toml
[providers.anthropic]
label = "Anthropic"
url = "https://api.anthropic.com/v1"
api_key_env = "ANTHROPIC_API_KEY"
key_url = "https://platform.claude.com/settings/keys"
location = "us"
documents = "public"
send_temperature = false
headers = { anthropic-version = "2023-06-01" }

[providers.anthropic.models.claude-haiku-5-5]
extra_body = { thinking = { type = "disabled" } }
input_usd = 0.10
output_usd = 0.50

[presets.claude-haiku-5-5-sonnet]
provider = "anthropic"
label = "Claude Haiku 5.5, checked by Sonnet 5.5"
models = { writer = "claude-haiku-5-5", judge = "claude-sonnet-5-5" }
```

| Provider | Where the text goes | What it sets, and its presets |
|----------|---------------------|-------------------------------|
| `cscs` | CSCS inference API, Lugano (`ch`, any document): the endpoint of the reported numbers | the key from `CSCS_API_KEY`, `thinking = "model-suffix"` (thinking models are separate names ending in `-thinking`). Preset `cscs-apertus`: the 8B writes, the 70B judges |
| `publicai` | The Public AI gateway (`world`, public documents only): run by Metagov Inc. (US nonprofit), requests go to compute partners | the key from `PUBLICAI_API_KEY`, `thinking = "chat-template"`, `extra_body` turning the gateway's response cache off; Apertus at Public AI's list prices, by pattern, which the evaluation uses for every Apertus run. Preset `publicai-apertus`: the 8B and the 70B in the gateway's spelling |
| `anthropic` | Anthropic's Claude through its OpenAI-compatible endpoint, chat completions only (`us`, public) | the key from `ANTHROPIC_API_KEY`, `send_temperature = false` (the 5.5 models refuse a temperature), the header `anthropic-version` the model list needs. The endpoint ignores `reasoning_effort` and counts Claude's adaptive thinking in `max_tokens`, so each model's table switches it off with the native field: `{ thinking = { type = "disabled" } }` for Haiku 5.5, `{ type = "between_tools" }` for Sonnet 5.5 (each refuses the other's value). Opus 5.5 always thinks, at its default effort (the endpoint ignores `output_config`), so its table adds 12,000 tokens to every call's output budget (`thinking_tokens = 12000`; an Understand answer on a long document passed the 12,000 of a thinking stage). Presets `claude-haiku-5-5`, `claude-haiku-5-5-sonnet` (Haiku writes, Sonnet judges), `claude-sonnet-5-5`, `claude-opus-5-5` |
| `openai` | OpenAI (`us`, public) | the key from `OPENAI_API_KEY`, `max_tokens_key = "max_completion_tokens"` and `send_temperature = false` (its GPT-5 models refuse `max_tokens` and any temperature but their default; the `gpt-4*` table takes the old fields back). The `gpt-5*` table sets `thinking = "reasoning-effort"` (`reasoning_effort` none for the stages that do not think) and leaves Understand a thinking stage for its larger budget (`thinking_stages = ["understand"]`; without the field these models do not reason either), since on long German documents Understand's answer passed the 6,000 tokens of a stage that does not think. Presets `gpt-5-6-luna`, `gpt-5-6-terra`, `gpt-5-4-nano` |
| `gemini` | Google's Gemini through its OpenAI-compatible endpoint, in beta (`us`, public; on the free tier Google uses the texts to improve its products) | the key from `GEMINI_API_KEY`, `send_temperature = false` (Google advises against a temperature on Gemini 3: below its default of 1.0 it may loop). Gemini 3 models always think (`reasoning_effort` none switches off only Gemini 2.5) and count the thinking in `max_tokens`, so the model's table sends `reasoning_effort = "low"`, the lowest level 3.8 Flash takes (`minimal` is an error), on every call. Preset `gemini-3-8-flash`. From Google's documentation (26 October 2026), not run yet |
| `openrouter` | OpenRouter, a gateway to many providers (`world`, public) | the key from `OPENROUTER_API_KEY`, `extra_body = { provider = { data_collection = "deny" } }` so that it routes to no provider that stores prompts; each model's table switches thinking through OpenRouter's `reasoning` field. Presets `openrouter-claude-haiku-5-5`, `openrouter-claude-haiku-5-5-sonnet`, `openrouter-gpt-5-6-luna`, `openrouter-gemini-3-8-flash`, `openrouter-qwen3-5-27b`. From its model list (26 October 2026), not run yet |
| `local` | llama.cpp (llama-server) on this machine, or another OpenAI-compatible server (`setup local --base-url`) (`local`, any) | `http://127.0.0.1:8080/v1`, the key `local` (such a server takes any key), `thinking = "chat-template"` (llama.cpp with `--jinja`), 30 minutes per call (a thinking call on a small GPU takes minutes), `discover = true`. No preset: the server names its models |
| `ollama` | Ollama on this machine (`local`, any) | `http://127.0.0.1:11434/v1`, the key `ollama` (ignored), `discover = true`; the `qwen3*` table sends `reasoning_effort` none on every call (Ollama ignores the chat-template switch) |
| `vllm` | vLLM, mostly a GPU machine of the organisation (`setup vllm --base-url http://<server>:8000/v1`) (`local`, any) | `http://127.0.0.1:8000/v1` (the app's port too: on one machine start one of them elsewhere), the key `local`, `thinking = "chat-template"`, `discover = true` |
| `mistral` | Mistral AI (`eu`, public) | the key from `MISTRAL_API_KEY`; no preset: `leichtfacile setup mistral` lists the models |
| `groq` | Groq, a US cloud with very fast inference (`us`, public) | the key from `GROQ_API_KEY`; no preset, since Groq's catalogue changes (several models are previews): `setup groq` lists it. Thinking stays off: Qwen reasons on Groq only when asked with `reasoning_effort` low, medium or high, and the gpt-oss models refuse `none` |
| `huggingface` | The Hugging Face Inference Providers router, which sends each request to a third-party provider (`world`, public) | the token from `HF_TOKEN`; no preset: Hugging Face ids with an optional provider suffix (`Qwen/Qwen3.5-9B:groq`), `setup huggingface` lists them; the gpt-oss tables send `reasoning_effort = "low"` |

The three servers of one's own have no preset, since each server names its own models:
the model page lists them under "This computer" when the server answers, and
`leichtfacile setup local` (or `ollama`, `vllm`) asks which one; the choice is saved as
a preset of the user's own (`ollama-qwen3-5-9b`). A preset with a model would count as
ready while nothing listens at its address.

Notes on the providers:

- CSCS closes about one long thinking stream in four midway (checked 6 October 2026);
  the client retries (`max_retries`, 8 by default), which makes a hard failure rare.
- Public AI is run by Metagov Inc. (US nonprofit) and routes requests to compute
  partners: not a sovereign deployment, never for documents with personal data. Pay per
  token after USD 2 of starter credit; the key comes from platform.publicai.co. Checked
  on 6 October 2026: `apertus-v1.5-8b` goes to Juelich (vLLM) and thinks when asked
  through the chat template, but about one call in three answers without reasoning;
  `apertus-v1.5-70b` goes to Infomaniak and ignores the switch, so the 70B judges without
  thinking. Its `-thinking` names serve the older Apertus 1 without thinking: do not use
  them. Thinking comparisons need the CSCS endpoint.
- A provider's cloud (OpenAI, Anthropic, Google, OpenRouter, Mistral AI, others): check
  where it processes the text before sending anything confidential; the interface marks
  them "public documents only".
- Groq and the Hugging Face router process the text in the United States or on
  third-party clouds: development and public documents only. The Hugging Face router
  served the older Apertus 1 (2509) when checked; results from either are no Apertus 1.5
  numbers.

### Models

`models.writer` reads, writes and repairs. `models.judge` grades the drafts; when it is
not set, the judge is the 70B of an Apertus 8B writer if the provider lists it (the setup
the evaluation measured), else the writer. `models.understand` lets another model read
the source. The tiers compared in [evaluation.md](evaluation.md):

- default: the 8B reads, writes and repairs, the 70B judges (one GPU on-premise);
- quality: `models = { writer = "swiss-ai/Apertus-v1.5-70B" }` runs every stage on the
  70B (cleaner style, fewer facts kept, about twice the price per page; the judge then
  grades its own drafts);
- hybrid: `models = { understand = "swiss-ai/Apertus-v1.5-70B" }` lets the 70B read and
  the 8B write (it kept the fewest facts, [prompts.md](prompts.md)).

`/readyz` names the models in use; the New draft form takes other models for one job,
and the model page's fine-tune panel saves such a combination as a preset of the user's
own.

### Thinking

Thinking is off by default (`thinking = "off"`), since every provider switches it its own
way:

- `model-suffix`: the thinking model is a separate model named `<model>-thinking`
  (Apertus on CSCS; `thinking_suffix` changes the ending);
- `chat-template`: the request switches it through the chat template (vLLM, llama.cpp);
- `reasoning-effort`: the request sends the OpenAI field `reasoning_effort = "none"` for
  the stages that do not think and leaves the model's default for the others: for a
  thinking model such as Qwen on Ollama, whose `/v1` endpoint ignores the other switches.

It applies to the stages in `thinking_stages` (default `["understand", "judge"]`), as
the provider, the model's table and the preset set them for the model a stage calls.
`leichtfacile check-llm --thinking` makes its test call with thinking and says whether
reasoning came back.

## Keys

A key is given in a file or named by a variable:

```toml
[providers.mine]
url = "https://llm.example.org/v1"
api_key_env = "MINE_API_KEY"          # or: api_key = "..."
```

A named variable comes from the environment, else from `.env` in the current folder, else
from `.env` next to the config file. A `.env` file holds such keys (`MINE_API_KEY=...`)
and nothing else: settings in it are not read. `auth.token` and `auth.token_env` work the
same way.

The model page and `leichtfacile setup` take the key (hidden input on the command line;
the page never shows it again) and write it into the `.env` next to the config file,
readable by its owner only where the system supports it, under the provider's variable
(`CSCS_API_KEY`) or `<NAME>_API_KEY` for a server of the user's own. `--api-key-env
<variable>` names a variable that is set already, and nothing is stored.

## Commands

| Command | Does |
|---------|------|
| `leichtfacile setup [name]` | sets a preset up and uses it: asks for the provider (or takes a preset's name, which names its provider, or a provider's), its key (nothing when the key's variable is set or the provider needs none), then one of the provider's presets or any model the provider lists, saved as a preset of the user's own; for a server of the user's own asks its address and a name and saves it as a provider too; a preset saved already is updated with `--force`, its other keys kept |
| `leichtfacile preset list` | every preset, shipped or the user's own, with its label, its provider, its writer model and whether it is ready (else what it lacks), the one in use marked `*` |
| `leichtfacile preset use <name>` | uses that preset from now on |
| `leichtfacile preset remove <name>` | removes a preset of the user's own, or the user's table that extends a shipped preset (the shipped one stays) |
| `leichtfacile config show` | every setting, its value and its source; keys masked; what keeps the preset from working |
| `leichtfacile config show --defaults` | every setting with its default and meaning, as a config file to copy from |
| `leichtfacile config set <key> <value>` | sets a key (`server.port 8001`, `llm.cache true`, `presets.laptop.timeout_s 1800`) |
| `leichtfacile config unset <key>` | removes a key from the file, so the default or another source applies |
| `leichtfacile config edit` | opens the file in `VISUAL` or `EDITOR` (else Notepad, TextEdit, nano or vi) and checks it when the editor closes |
| `leichtfacile config path` | the config file's path |

`setup` takes its answers as flags too: `--name` (the preset saved for `--model`, or the
server), `--base-url` (a server of your own), `--api-key`, `--api-key-env`, `--model`,
`--judge` and `--force` (update a preset saved already). It asks only for what the flags leave open, and nothing at all when
the key's variable is set, so it runs from a script:

```bash
leichtfacile setup cscs-apertus                   # asks for the key; the rest is shipped
leichtfacile setup cscs --model swiss-ai/Apertus-v1.5-70B   # a preset of your own on CSCS
leichtfacile setup local --model apertus-v1.5-8b-q4-llamacpp --name laptop
leichtfacile setup gpu --base-url http://gpu:8000/v1 --model swiss-ai/Apertus-v1.5-8B
leichtfacile check-llm                            # lists the provider's models, one short call
```

`--api-key` ends up in the shell history; leave it out to be asked. A value of
`config set` is read as TOML (`8001`, `true`, `["understand"]`), else taken as text.
Every change is checked with all the other sources before it is written: a key the app
does not know, a wrong value or an app published without a login leaves the file
unchanged. The file keeps its comments and order. `--local` makes `preset use`,
`preset remove` and the `config` commands work on `./leichtfacile.toml` instead.

## Environment variables

`LEICHTFACILE_<SECTION>__<KEY>`, the parts joined by two underscores, sets any key:

```bash
LEICHTFACILE_LLM__PRESET=publicai-apertus
LEICHTFACILE_SERVER__PORT=8001
LEICHTFACILE_PRESETS__CSCS_APERTUS__MODELS__WRITER=swiss-ai/Apertus-v1.5-70B
LEICHTFACILE_PRESETS__CSCS_APERTUS__THINKING_STAGES=understand,judge
```

A value is text, which the setting converts; a list is comma-separated; an empty
variable sets nothing. A table (`extra_body`, `headers`, a models table) is set in a
file, not in a variable. In a container or a CI job, five variables make a preset
without any file: `LEICHTFACILE_LLM__PRESET=ci`, the provider's
`LEICHTFACILE_PROVIDERS__CI__URL` and `LEICHTFACILE_PROVIDERS__CI__API_KEY`, and the
preset's `LEICHTFACILE_PRESETS__CI__PROVIDER=ci` and
`LEICHTFACILE_PRESETS__CI__MODELS__WRITER`.

## In a checkout

A `leichtfacile.toml` in the checkout (git ignores it) holds what differs there, for
example the data in the repository's `data/`, where git ignores the database and the
caches, the cached answers for the evaluation, and the presets of its evaluation runs:

```toml
[llm]
cache = true

[presets.ollama-qwen3-5-9b]
provider = "ollama"
label = "Qwen 3.5 9B on Ollama"
models = { writer = "qwen3.5:9b", judge = "qwen3.5:9b" }

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

The preset in use, and the two switches that apply to every preset. A provider's keys live in its [providers.<name>] table, a preset's in its [presets.<name>] table.

| Key | Default | Meaning |
|-----|---------|---------|
| `preset` |  | The preset in use: a shipped one or one of your own. Default: cscs-apertus. |
| `cache` | `false` | Keep the answers in data.dir and reuse them (development, evaluation), whichever preset is in use. |
| `offer` | `[]` | The presets the interface offers (an organisation's choice); empty: every ready one. |

### `[providers.<name>]`

Where models run and how to reach them. Its request settings apply to every model there unless a models table or the preset says otherwise.

| Key | Default | Meaning |
|-----|---------|---------|
| `thinking` | `"off"` | How the provider switches thinking: model-suffix (a separate model named &lt;model>-thinking, Apertus on CSCS), chat-template (vLLM, llama.cpp), reasoning-effort (the OpenAI field, none for the stages that do not think; a thinking model on Ollama) or off. |
| `thinking_suffix` | `"-thinking"` | The thinking models' suffix. |
| `thinking_stages` | `["understand", "judge"]` | The stages that think, when thinking is on. |
| `stream` | `true` | Streamed answers, so that a proxy cannot time out a long one; false only for a server that cannot stream. |
| `max_tokens_key` | `"max_tokens"` | The request field for the output budget: max_tokens, or max_completion_tokens (OpenAI's GPT-5 models refuse max_tokens). |
| `thinking_tokens` | `0` | Tokens added to every call's output budget, for a model that thinks whatever the request says and counts the thinking in that budget. |
| `send_temperature` | `true` | Send each stage's temperature; false for a model that takes only its default (OpenAI's GPT-5 models, Gemini 3). |
| `timeout_s` | `300.0` | Seconds one call may take. |
| `max_retries` | `8` | Retries of a failed call. |
| `extra_body` | `{}` | Fields sent with every request: a gateway's switches, a model's thinking switch. A later table's fields add to the earlier ones. |
| `input_usd` |  | USD per million input tokens, for the cost per page. |
| `output_usd` |  | USD per million output tokens. |
| `label` |  | The name the interface shows. |
| `url` |  | The endpoint's address, for most servers ending in /v1. Required. |
| `api_key` |  | The key, written into the file. A server of your own takes any key. |
| `api_key_env` |  | Or the variable that holds the key: from the environment, else from .env in the current folder, else from .env next to the config file. |
| `key_url` |  | Where a key comes from, linked by the interface. |
| `location` | `"world"` | Where the text is processed: ch, eu, us, world (several countries) or local (this machine or the organisation's network). |
| `documents` | `"any"` | Which documents may go there: any, or public (no personal data). |
| `headers` | `{}` | Headers sent with every request (anthropic-version for Anthropic's OpenAI-compatible endpoint). |
| `discover` | `false` | Offer every model the server lists as a preset (a server of one's own, which names its own models). |
| `models` | `{}` | What one model there needs, by its name or a pattern ("gpt-5*"): [providers.&lt;name>.models.&lt;model>] tables. |

### `[providers.<name>.models.<model>]`

What the calls to a model take and cost. Set on a provider for all its models, in a provider's models table for one model (or a pattern), or on a preset; thinking is off unless set, since each provider switches it its own way.

| Key | Default | Meaning |
|-----|---------|---------|
| `thinking` | `"off"` | How the provider switches thinking: model-suffix (a separate model named &lt;model>-thinking, Apertus on CSCS), chat-template (vLLM, llama.cpp), reasoning-effort (the OpenAI field, none for the stages that do not think; a thinking model on Ollama) or off. |
| `thinking_suffix` | `"-thinking"` | The thinking models' suffix. |
| `thinking_stages` | `["understand", "judge"]` | The stages that think, when thinking is on. |
| `stream` | `true` | Streamed answers, so that a proxy cannot time out a long one; false only for a server that cannot stream. |
| `max_tokens_key` | `"max_tokens"` | The request field for the output budget: max_tokens, or max_completion_tokens (OpenAI's GPT-5 models refuse max_tokens). |
| `thinking_tokens` | `0` | Tokens added to every call's output budget, for a model that thinks whatever the request says and counts the thinking in that budget. |
| `send_temperature` | `true` | Send each stage's temperature; false for a model that takes only its default (OpenAI's GPT-5 models, Gemini 3). |
| `timeout_s` | `300.0` | Seconds one call may take. |
| `max_retries` | `8` | Retries of a failed call. |
| `extra_body` | `{}` | Fields sent with every request: a gateway's switches, a model's thinking switch. A later table's fields add to the earlier ones. |
| `input_usd` |  | USD per million input tokens, for the cost per page. |
| `output_usd` |  | USD per million output tokens. |

### `[presets.<name>]`

A provider with the models that write, read and check: what the user picks. Any request setting here overrides the provider's and the model's.

| Key | Default | Meaning |
|-----|---------|---------|
| `provider` |  | The provider the preset runs on. Required for a preset of your own; a table named like a shipped preset extends it. |
| `thinking` | `"off"` | How the provider switches thinking: model-suffix (a separate model named &lt;model>-thinking, Apertus on CSCS), chat-template (vLLM, llama.cpp), reasoning-effort (the OpenAI field, none for the stages that do not think; a thinking model on Ollama) or off. |
| `thinking_suffix` | `"-thinking"` | The thinking models' suffix. |
| `thinking_stages` | `["understand", "judge"]` | The stages that think, when thinking is on. |
| `stream` | `true` | Streamed answers, so that a proxy cannot time out a long one; false only for a server that cannot stream. |
| `max_tokens_key` | `"max_tokens"` | The request field for the output budget: max_tokens, or max_completion_tokens (OpenAI's GPT-5 models refuse max_tokens). |
| `thinking_tokens` | `0` | Tokens added to every call's output budget, for a model that thinks whatever the request says and counts the thinking in that budget. |
| `send_temperature` | `true` | Send each stage's temperature; false for a model that takes only its default (OpenAI's GPT-5 models, Gemini 3). |
| `timeout_s` | `300.0` | Seconds one call may take. |
| `max_retries` | `8` | Retries of a failed call. |
| `extra_body` | `{}` | Fields sent with every request: a gateway's switches, a model's thinking switch. A later table's fields add to the earlier ones. |
| `input_usd` |  | USD per million input tokens, for the cost per page. |
| `output_usd` |  | USD per million output tokens. |
| `label` |  | The name the interface shows. Default: the preset's name. |
| `models.writer` |  | The model that reads, writes and repairs. Required. |
| `models.understand` |  | The Understand stage's model, when it differs from the writer. |
| `models.judge` |  | The judge's model. Default: the 70B of an Apertus 8B writer when the provider lists it, else the writer. |

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
| `workers` | `1` | Threads that run jobs; more than 1 needs a provider that serves parallel requests (vLLM does). |
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
| `dir` | the user's app-data folder | The database and the caches. |
| `examples_dir` | the letters shipped with the package | A folder of example letters for the New draft form (.txt or .md, a .json of job settings next to each). |
| `retention_days` | `0` | Jobs nobody changed for this many days are deleted; 0 keeps everything. |

### `[log]`

The app's log. Document text is only ever logged at DEBUG (docs/architecture.md §10).

| Key | Default | Meaning |
|-----|---------|---------|
| `level` | `"INFO"` | DEBUG, INFO, WARNING, ERROR or CRITICAL. |
| `format` | `"text"` | text, or json: one JSON object per line (time, level, logger, message, request_id, job_id) for a log collector. |

<!-- reference:end -->
