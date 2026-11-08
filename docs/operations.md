# Leicht·Facile - operations

How the service is installed, configured and run, where the model runs, what protects
the service and the documents, what the repository does for the supply chain, and what
the service stores and for how long. The design behind it is in
[architecture.md](architecture.md), whose §10 says what the design fixes here; the
step-by-step commands are in [quickstart.md](quickstart.md), every setting in
[configuration.md](configuration.md), the commitments in [maintenance.md](maintenance.md)
and the maintainers' own steps in [releasing.md](releasing.md).

## 1. The package

The app is a Python package (Python 3.12 and later), published on PyPI and as a wheel
on a GitHub release for every version tag (`.github/workflows/release.yml`, PyPI by
trusted publishing). `uv tool install leichtfacile` puts the command `leichtfacile` on
the path; `pip install leichtfacile` installs it into an environment of one's own
(quickstart.md has the commands). The spaCy models for German and French
(`de_core_news_md`, `fr_core_news_md`) are dependencies like any other: spaCy
publishes them on GitHub only, and PyPI refuses dependencies given by URL, so they are
republished on PyPI as `leichtfacile-model-de` and `leichtfacile-model-fr`, spaCy's
files unchanged under the import names `leichtfacile_model_de` and `_fr`.
`scripts/model_packages.py` builds them from spaCy's wheels, pinned by SHA-256 in
`[tool.leichtfacile.spacy-models]` in pyproject.toml, and
`.github/workflows/models.yml` publishes them, one job and GitHub environment per
package (PyPI keeps one pending trusted publisher per repository, workflow and
environment). A new model version is published first and pinned in `dependencies`
afterwards; `tests/test_release.py` checks that the pins and the tables agree and that
the checker loads those models (`rules/nlp.py`). The Italian pipeline,
`leichtfacile-model-it`, is built the same way by `scripts/lexicon_package.py`: the
blank Italian tokenizer and sentencizer with the Morph-it! lexicon as the tagger, the
lexicon's archive pinned by SHA-256 in `[tool.leichtfacile.lexicon-models.it]` and the
component's code (`scripts/morphit.py`) inside the package, since every spaCy Italian
model is licensed for non-commercial use only. The vendored UI assets are inside the
package. The app never runs a model itself: the endpoint is provided outside it (§5).

## 2. Settings and presets

The settings are one TOML file with a section per topic, and the providers and presets
of the model ([configuration.md](configuration.md)). The known providers (where models
run and how to reach them, with a table per model for what it needs) and the presets on
them (what the user picks: a provider and the models that write, read and check) come
with the app, one table each in `src/leichtfacile/presets/presets.toml`, complete but
for the key; a server of one's own names its models, which the model page lists. The
preset in use resolves from its provider, the provider's table of each model it calls,
its own keys and the user's tables of the same names; `[llm]` holds the choice
(`llm.preset`; without it the first preset in the catalog's order whose provider's key
is set, `config.first_with_key`, else the shipped default `publicai-apertus`), the
`cache` switch and `offer` (the presets an organisation shows), nothing else. The model
page of the web app (`/model`, `web/model.py`) lists the presets by group with where the
text goes, the cost per page and what each lacks, takes the key (into the `.env` next to
the config file), checks it and makes a test call, offers a local server's models and
saves a preset of the user's own from its fine-tune panel; it changes the settings on
the machine the app runs on only, and a source that wins over the config file locks it.
`leichtfacile setup <name>` (`configure.py`) does the same on the command line: asks
for the provider (or takes a preset's or a provider's name), its key (not echoed;
nothing with the key's variable set), then one of the provider's presets or any model
it lists, saved as `[presets.<name>]`, a server of one's own as `[providers.<name>]`
too; `--name`, `--base-url`, `--api-key`, `--api-key-env`, `--model`, `--judge` and
`--force` answer the questions in advance, and `--region` the question for the texts'
variety (`[texts]`, [architecture.md §8](architecture.md#8-languages-and-levels)), which
setup alone sets; `--max-chars` sets the longest text the web app takes
(`texts.max_chars`, never asked); the app reads both at its start. A preset is ready
when its provider has an address and a key and it names a writer; nothing is guessed
from the keys in the shell. `leichtfacile preset` lists every preset with what it
lacks, switches and removes, `leichtfacile config` shows and changes every setting
([architecture.md §7](architecture.md#7-web-application)). The settings come from the
defaults, the shipped providers and presets, the user's config file, `leichtfacile.toml`
in the current folder, the variables `LEICHTFACILE_<SECTION>__<KEY>` and the command
line (`--preset`, `serve --host` and `--port`), each overriding the one before
(`config.load`, `config.get_settings`; `config.paths` reads `[data]` without the model);
`leichtfacile config show` names the source of each setting. The config file is
`LEICHTFACILE_CONFIG` (or `--config`) when that is set, else `config.toml` in the
platform's folder for settings: `%APPDATA%\leichtfacile` (Windows),
`~/Library/Application Support/leichtfacile` (macOS), else
`$XDG_CONFIG_HOME/leichtfacile` or `~/.config/leichtfacile`. A key is written into the
file (`llm.api_key`) or named (`llm.api_key_env`) and then read from the environment
or from a `.env` file, which holds such keys and nothing else; `setup` writes the key
into the `.env` next to the config file and, on POSIX systems, makes both files
readable by their owner alone (on Windows the folder's permissions apply: `icacls` in
quickstart way 5). `config set` does the same with a secret (`auth.token`, a provider's
`api_key`): the value goes into the `.env` under `LEICHTFACILE_TOKEN` or the provider's
variable, the file names the variable, and without the value the command asks for it
hidden (`configure.set_secret`); a secret written into a settings file by hand is read,
with a warning from `config show`, `config edit` and `serve` (`config.unusual`).
`serve`, `check-llm` and `simplify` stop with a short message naming a missing
`llm.url`, `llm.api_key` or `llm.models.writer` and `leichtfacile setup`, not with a
traceback (`cli.settings_or_exit`).

## 3. Starting the app

`leichtfacile serve` starts the web app on `127.0.0.1:8000`, this machine only, and
opens it in the default browser as soon as `/healthz` answers (`cli.open_when_ready`):
only for a loopback host, and on Linux only with a desktop (`DISPLAY` or
`WAYLAND_DISPLAY`), since Python would otherwise start a text browser in the terminal
(`cli.wants_browser`); `--no-browser` turns it off. `--host` sets `server.host`: beyond
the loopback interface the app needs a login (§6); in a container, which binds every
interface of its own while the runtime publishes the port, `server.published_on` names
the published address and is judged instead. The database goes to `data.dir`, by
default `%LOCALAPPDATA%\leichtfacile` (Windows),
`~/Library/Application Support/leichtfacile` (macOS), else
`$XDG_DATA_HOME/leichtfacile` or `~/.local/share/leichtfacile`. While the drafts list
is empty, it offers the example letters of the package leichtfacile-samples, a
dependency of the app (`samples/`), as one-click fills of the New draft form
([architecture.md §7](architecture.md#7-web-application)): [samples/README.md](../samples/README.md)
lists them, the premium-reduction letter in German, French and Italian, the KESB
decision, the German and Austrian Bescheide, and two school letters in the three
languages, to parents and, in the du form, to students; `data.examples_dir` names
another folder of letters. A letter's job settings, such as the decision mode and the
addressee, come from a JSON file next to it (`examples.py`). When the samples package
brings a recorded run of a letter for the preset in use, the letter sent unchanged is
answered from it in seconds and at no cost; any change of the text, the level or the
preset, and a step run again, go to the model (`llm/replay.py`). Version 0.6.0 of the
package brings the runs of the preset `huggingface-gpt-oss-120b-groq` for 8 of the
letters (samples/README.md); a newer one comes with an upgrade of the dependencies,
without a new version of the app.

`leichtfacile check-llm` lists the endpoint's models and makes one short call; it is
the first thing to run after `setup`.

## 4. The container image

The same app comes as a container image, `ghcr.io/bobrovsky420/leichtfacile`, one tag
per release and `latest`, x86-64 ([quickstart.md](quickstart.md#7-in-a-container) way 7).
The `Dockerfile` has two stages: uv installs the environment from `uv.lock` (the versions
of every other install of the commit, the language packages among them) into a build
stage, and a slim Python image of the version `.python-version` pins carries that
environment alone, without uv, pip or the build context (`.dockerignore` is an allowlist:
the package, its metadata and the lockfile, nothing else, so a checkout's `.env` never
lands in an image). The image runs as a system user of its own (uid 10001), writes to
`/data` alone, where it puts the config file, the `.env` that `setup` writes and the
database (`LEICHTFACILE_CONFIG=/data/config.toml`, `LEICHTFACILE_DATA__DIR=/data`), and
listens on every interface of its container (`LEICHTFACILE_SERVER__HOST=0.0.0.0`), since
the runtime publishes the port. Whether that makes it a published server is decided by
`server.published_on`, the address the runtime publishes the port on: on `127.0.0.1` the
app runs without a login, as it does natively; on any other address, or without the
setting, it needs one of the two logins and stops at once without one. Its health check
asks `/healthz`. `compose.yaml` starts the image with a named volume, the port published
on the loopback interface of the host by default and the app told so through the one
variable `LEICHTFACILE_PUBLISH`, and, as profiles, the model servers of architecture (a)
in §5 next to it (`vllm`: the official Apertus image with the flags measured on the L4;
`llamacpp`: the 4-bit conversion), pointing the shipped providers `vllm` and `local` at
them on the compose network. The two servers' images are pinned by digest, since their
tags move, and every service drops every capability and gains no privilege on exec; the
app and llama.cpp run on a read-only root with `/tmp` in memory and their volume as the
one writable place, vLLM with a `/dev/shm` of its own in place of the host's IPC
namespace (`tests/test_container.py` checks the pins and the hardening). CI builds the
image on every change, starts it with a token against the unreachable endpoint, checks
the probes, the login (401 without the token, 200 with it) and the user, starts it again
published on the loopback interface alone, where the page answers without a login, and
scans it for vulnerabilities that have a fix (Trivy, high and critical); `release.yml`
builds it again for a tag, checks the version and the checker inside it and pushes it to
ghcr.io (`tests/test_container.py` keeps the Python version, the port, the image's name
and the tag the docs name in step).

## 5. Where the model runs

In each of the three target architectures, Leicht·Facile is the same Python service
(above), on a workstation or on a server of the organisation; the model runs where the
organisation wants it, behind an OpenAI-compatible endpoint that `llm.url` names
([architecture.md §3](architecture.md#3-architecture-overview), D2). Running the model
is outside the app.

| Architecture | Where the model runs and how Leicht·Facile meets it |
|--------------|-----------------------------------------------------|
| a) On-premise model server | On the organisation's own hardware; `leichtfacile setup local`, `ollama` or `vllm` knows the server's port and thinking switch (`--base-url` for another address) and asks for the model from the server's list. Apertus 1.5 8B runs on vLLM with the Swiss AI team's official image `ghcr.io/swiss-ai/vllm_apertus_1.5_release:latest-amd64` on one GPU with 24 GB or more, with the Apertus reasoning parser, `--max-model-len 32768`, an FP8 KV cache and at most 16 parallel sequences; the app takes `thinking = "chat-template"`, so one server provides both modes. The 70B judge is optional; with the 8B judging, the one model such a server lists, the quality is not measured (the run below timed one letter). Run on 10 October 2026 on one NVIDIA L4: the server starts and the app takes a letter end to end (below). llama.cpp with the 4-bit GGUF runs on an 8 GB GPU (below); Ollama or any other OpenAI-compatible server works the same way. `compose.yaml` starts the vLLM server next to the app's container with these flags (`docker compose --profile vllm up -d`). |
| b) Air-gapped | As (a), with the model server and its weights inside the network. The app is installed offline: the wheel and all its dependencies, the two spaCy model packages among them, are collected with `pip wheel` on a connected machine with the same operating system, CPU architecture and Python version; on the target `pip install --no-index --find-links` installs them ([quickstart.md](quickstart.md) way 6 has the commands). The UI assets are in the package; no telemetry, no CDN, no package installs at runtime. Or the container image and the model server's image, carried over with `docker save` and `docker load`. |
| c) A Swiss-operated or other provider | Set `llm.url` to a provider's endpoint: a Swiss-operated Apertus endpoint (Swisscom AI Platform, Infomaniak; both list Apertus 1.5 70B), or any other OpenAI-compatible API (`leichtfacile setup` has presets for OpenAI and Mistral AI). The reference numbers come from the CSCS inference API in Lugano, which serves research and grants keys on application, and hold for Apertus only; the shipped default, Apertus 70B on the Public AI gateway without thinking, is measured on the same pairs ([evaluation-publicai.md](evaluation-publicai.md)). Texts under secrecy belong on a model the organisation controls, (a) or (b), where Apertus fits best: open weights, open training data, Swiss, and the 8B on one GPU. |

Hardware for (a)/(b), measured on 10 October 2026 on one NVIDIA L4 24 GB in an AWS
g6.xlarge in Zurich (`docs/hardware/aws-l4-2026-10-10/`): the official checkpoint
(bf16 with the image encoder) takes 17.23 GiB on the GPU. With a bf16 KV cache vLLM
refused to start: one 32k request needs 4.0 GiB of KV cache, and 2.13 GiB were left at
90 % utilisation (17,440 tokens). A shorter context does not help, because the stages
ask for up to 16,000 output tokens on top of the prompt and vLLM rejects a request
that does not fit. So the server stores the KV cache in FP8 (`--kv-cache-dtype=fp8`:
38,752 tokens, 1.18 requests of 32k at once) and allows at most 16 parallel sequences
(`--max-num-seqs=16`): with the default 256, the CUDA graphs (0.84 GiB, now 0.16) and
the sampler's warm-up ran out of memory. By the same arithmetic a card with 32 GB or
more needs neither flag (not tested). The start takes about 7 minutes with the weights
on disk. One request generates 16.2 tokens per second, close to the limit of the L4's
memory bandwidth (300 GB/s for about 16 GB of weights per token). With the 8B also
judging, the example letter took 63 minutes with thinking in Understand
and Judge, and 22 minutes with thinking only in Understand
(`thinking_stages = ["understand"]`); in both runs Understand's reasoning hit the
12,000-token cap, which costs 744 s on this card. What the FP8 KV cache does to
quality is not measured. The FP8 build of the weights (`onprem-ai/Apertus-v1.5-8B-FP8`,
keeps image input, not tested) is 11.42 GB against 18.44 GB for the full multimodal
checkpoint.

A smaller on-premise option was tested on 5-6 October 2026: llama.cpp (`llama-server`,
Vulkan build b9637) with the community 4-bit text-only conversion
`Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF` (5.06 GB) on a laptop GPU (RTX 4060 8 GB),
16k context with an 8-bit KV cache. It generated about 37 tokens per second at short
context and about 17 near 16k; Understand took about 1.5 minutes and Write, with
thinking, about 12 minutes for a 400-word letter. It runs the whole pipeline
including thinking mode (`thinking = "chat-template"`, `llama-server -sp`), but
it has no image input and is an unofficial conversion, so it serves development and
small offices, not the evaluation. The server is started next to the app, as
[quickstart.md](quickstart.md#running-a-model-yourself) shows (`llama-server -hf Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF ...`,
weights downloaded on first start); it is served under the alias
`apertus-v1.5-8b-q4-llamacpp`, so its results can never be mistaken for the official
model. Tested on 6 October 2026 with llama.cpp's official CUDA build (b11429) on the
same laptop: the model starts in 6 seconds with the weights on disk and takes 5.9 GB
of GPU memory. The 70B is served with tensor parallelism over four
GPUs in the official guide; FP8/NVFP4 builds reduce that. The business argument of
the stretch goal ([architecture.md §4.8](architecture.md#48-learning-from-edits-stretch))
is precisely that a fine-tuned 8B makes the 70B unnecessary at runtime.

## 6. Security and privacy

- Documents contain personal data. For them the model endpoint is inside the
  organisation, (a) or (b) above, so content never leaves. The demo uses public
  documents only. Decisions of child and adult protection authorities and courts are
  the most sensitive case: before anonymisation they name a person and describe their
  health, family and finances ([use-case-decisions.md](use-case-decisions.md) §2). Why
  such texts need a model the organisation controls, and why Apertus fits best there:
  [use-cases.md §2](use-cases.md#why-apertus-fits-best).
- Reachable from this machine only by default (`127.0.0.1:8000`); the organisation's
  reverse proxy publishes it further. Two optional logins (`web/security.py`): a
  shared token (`auth.token`; browsers are asked for it with HTTP Basic, any user
  name, scripts send `Authorization: Bearer`; compared in constant time, ten wrong
  tries per minute and client, then 429) or the proxy's user header
  (`auth.proxy_header`, trusted only from the proxy's addresses in `auth.proxy_from`;
  the user lands in `request.state.user`). That user is recorded (the shared token
  names nobody): on the job they submit (`created_by`), on every decision they save
  (`by`, with `at`, the time it was first saved in that form; a save that sends a
  decision unchanged keeps the first reviewer's stamp) and on the review (`saved_by`),
  on the audit bundle they export (`exported_by`, and `final.reviewers`, who decided),
  in the job's event log (the bundle's `timeline`: who submitted, stopped, saved and
  exported) and in the Word footer, in the log line of a deletion, which leaves no row, and in
  the access line (below). The app reads the proxy's `X-Forwarded-For` and
  `X-Forwarded-Proto` itself (`ProxyHeaders`, outside every other layer): the user's
  address for the rate limit and the access line, and the scheme, so the cookies are
  Secure and the links https behind a proxy that ends TLS, wherever it runs; trusted
  from `auth.proxy_from`, with any login, else from this machine's loopback addresses.
  uvicorn's own proxy-headers middleware is off (`serve`): it trusts the loopback
  addresses alone and would rewrite the client's address before the login compared
  the connection with `auth.proxy_from`, so a proxy on the same host would get 403
  from every request. The probes and the static files need no login. `server.host`
  (which `serve --host` sets) names the interface the app listens on; beyond the
  loopback interface the app refuses to start without one of the two. In a container,
  `server.published_on` names the address the runtime publishes the port on and is
  judged instead of the bind address. No accounts or roles of its own. Every logged-in
  user sees every job, unless the server has workspaces (`server.workspaces`,
  [architecture.md §7](architecture.md#7-web-application)): then a browser sees the
  jobs of its workspace alone, a link anyone may open, so the login decides who gets in
  and the workspace what they see; the token is never stored (its hash is) and never
  logged.
- On a server the app runs as a system service (a systemd unit; on Windows a service
  wrapper such as WinSW or a scheduled task, under `NT AUTHORITY\LocalService`;
  quickstart way 5) under a dedicated service account with no other rights:
  `leichtfacile serve --host 0.0.0.0 --no-browser` with `auth.token`, or on the
  loopback interface behind the reverse proxy with its user header (IIS with Windows
  Authentication hands the domain user over through a rewrite rule's server variable).
  `data.dir` lies on a disk the organisation controls; that folder, the config file
  and the `.env` next to it, which hold the key, are readable and writable by the
  service account alone (`setup` writes the two files so on POSIX systems; on Windows
  `icacls` restricts the folder; `data.dir`'s permissions are the organisation's to
  set). Outbound, the service connects to the model endpoint and to the web addresses
  users submit (below), nothing else: no telemetry, no CDN, no downloads at runtime.
- In a container the same holds (§4): the image runs as its own unprivileged user,
  `/data` is its one writable folder, and the login rule judges `server.published_on`,
  the address the runtime publishes the port on, since the app binds every interface of
  the container: `compose.yaml` publishes on the host's loopback interface by default and
  passes that address, so no login is asked there; on any other address the app refuses
  to start without one of the two logins. Behind a reverse proxy on the host,
  `auth.proxy_from` names the proxy as the container sees it (the bridge network,
  `172.16.0.0/12`).
- Every response carries a Content-Security-Policy (scripts from this server only,
  the one inline script by a nonce new per request, `frame-ancestors 'self'`, no
  plug-ins; the API docs pages, which load Swagger UI from a CDN and are off unless
  `server.api_docs` says so, get the other headers only), `X-Content-Type-Options:
  nosniff`, `X-Frame-Options: SAMEORIGIN`, a `Referrer-Policy` that keeps job addresses
  on the site and a `Permissions-Policy`. HTTPS and `Strict-Transport-Security` belong
  to the proxy that ends TLS.
- A request body over 16 MB is refused with 413 by its `Content-Length` before a byte
  is read, else as soon as the count passes the limit; the 15 MB file limit, the length
  of the text (`texts.max_chars`, 10,000 characters by default, pasted or read from a
  file or a page) and the bounds on the review fields (architecture.md §7) hold inside
  it. Writes (POST, PUT, PATCH, DELETE) are limited to `server.rate_limit_per_minute`
  (120) per client address and minute, 429 with `Retry-After` beyond; behind the
  trusted proxy the client is the address it forwards. In memory, per process.
- `/healthz` answers from the process alone; `/readyz` asks the model's provider at most
  once in 30 s, whoever asks, and answers booleans and the configured names, never the
  endpoint's catalogue, so a caller cannot make the server spend the key's quota or
  learn what the endpoint serves. `/metrics` (architecture.md §7) says how much the
  service is used, how long the stored jobs ran and which models it calls, so it stays
  behind the login when one is
  configured; the probes alone are open.
- Every response carries an `X-Request-ID`: the client's when it is a plain token (a
  reverse proxy sets one, so its log and ours meet), else a new one. Every log line
  written while the request is handled carries the id, and every line a worker writes
  while it runs a job carries the job id (`logs.py`, context variables). One access
  line per request names method, path, status, duration, client address and, with the
  proxy login, the user (`user`), never the query string, which can carry what a
  reviewer typed into the drafts search; uvicorn's own access log, which has the query
  string, is off. `log.format = "json"` writes every line as one JSON object (time,
  level, logger, message, request_id, job_id, the access line's fields, the traceback)
  for a log collector; `text` is the default.
- Jobs and artifacts live in `data.dir` and can be deleted via the API and the pages;
  the data lifecycle (§8) says what is kept, for how long, and what a deletion takes
  with it.
- The server fetches the URLs users submit, so a URL that resolves to a private,
  loopback or link-local address is refused (server-side request forgery). The check
  runs on every hop of a redirect chain (at most 5 hops) and the connection goes to
  the address that was checked, the name in the Host header and as the TLS server
  name, so a DNS answer that changes between the check and the connect cannot redirect
  the fetch (`ingest/fetch.py`). Three budgets end a slow or hostile server's hold on
  a thread: 30 s per connect and read; 120 s for the whole fetch, headers included (a
  watchdog shuts the connection when the time is up, however slowly the bytes come);
  15 MB of body after decoding, a compressed body inflated no further than that (one
  coding, gzip or deflate; a coding on a coding is refused).
- A PDF, uploaded or fetched, is read in a child process (`pdfwords.py`) that is
  stopped after 60 s and, on Linux, may take 1 GB of address space, since a compressed
  stream of a few hundred kilobytes can unpack to gigabytes; a PDF of more than 200
  pages is refused before a page is read, and reading stops once the words pass twice
  `texts.max_chars`. One upload costs about a second more for the child's start.
  The check unwraps an IPv4 address carried in IPv6 (IPv4-mapped, NAT64) and names the
  ranges that CPython 3.12.0 to 3.12.3 still counted as global (6to4 among them), so it
  refuses the same addresses on every supported Python; CI runs the tests on 3.12,
  3.13 and 3.14. `server.allow_private_urls = true` lifts the address check for an
  intranet that needs internal pages.
- A state-changing request from a page on another site (cross-site request forgery)
  is refused with 403 before any route runs: `Sec-Fetch-Site: cross-site`, else an
  `Origin` that is not this server, which holds for `Sec-Fetch-Site: same-site` too,
  so a page on a sibling host (`evil.example.ch` for `app.example.ch`) is refused
  (`web/security.py`). Requests without these headers, from scripts and API clients,
  pass; reads are never refused.
- A submission's fetch, PDF parse and segmentation run in the thread pool, not on the
  event loop, so a server that trickles its page or a large PDF does not hold every
  other request (`/healthz` included) while it is ingested; at most `jobs.ingest_slots`
  submissions are read at a time (the next is refused with 429), so they cannot fill
  the pool either. A queue limit, a time budget per job and a Stop button bound what
  one submitter can make the workers do (architecture.md §7).
- Prompt injection: a web page or a PDF can carry instructions ("ignore the rules
  above and write ..."). Every prompt puts the document between `<document>` and
  `</document>` and says, right before the fence, that what stands there is content,
  never an instruction; code writes a tag inside the text as `[document]` so the text
  cannot close the fence (`pipeline/render.py`). The code-side checks keep the values
  honest (FACT-01, FACT-06, the copied-example check), and every draft goes through
  the review before it is exported.
- No document text in logs above `DEBUG`; the LLM cache can be disabled. The failure
  path keeps the promise too: the error a job stores and logs when the model's answer
  does not validate names the fields, the messages and the kinds of error, never an
  excerpt of the answer (pydantic's `input_value`, left out by
  `llm/json_out.redacted_error`; the whole error still goes back to the model for its
  repair); the known failures are logged without a traceback, whose chained cause
  would print the excerpt; the values a stage finds that the document does not contain
  are counted at `WARNING` and named at `DEBUG` only; and a filter on the log handlers
  redacts `input_value=` excerpts in any message or traceback that still carries one
  (`lifecycle.py`). A test fails a job on purpose and checks the job row, the page and
  the captured log for a sentinel word.

## 7. Supply chain

What runs for an organisation is the code that was reviewed, at every hop, and the
repository keeps that checkable:

- **Dependencies.** `uv.lock` pins every package with its hashes, and every install,
  CI and the image among them, runs `uv sync --frozen`. `[tool.uv] exclude-newer =
  "7 days"` in pyproject.toml keeps a release out of `uv lock --upgrade` and `uv add`
  until it has been public for a week, the window in which most hijacked packages are
  caught; the project's own language packages are exempt (pinned to an exact version,
  published right before the pin), and any other exception names a release and the date
  after which the window admits it by itself, from which day `tests/test_supply_chain.py`
  asks for its removal. The language packages are built from spaCy's wheels and the
  Morph-it! archive pinned by SHA-256 (§1).
- **Updates.** `.github/dependabot.yml` opens one grouped pull request a week for the
  Python packages, one for the actions, one for the Dockerfile's images and one for the
  model servers' images of `compose.yaml`, pinned by digest since their tags move, each
  under the same seven-day window; CI gates them like any change.
- **Workflows and publishing.** Every action is pinned to a commit, the workflows start
  from read-only permissions, PyPI and ghcr.io take the artifacts by the workflow's own
  identity (trusted publishing, `packages: write`), no long-lived token exists, and the
  one download in CI, gitleaks, is pinned by its checksum.
- **Secrets.** CI scans every commit of the history with gitleaks on every change
  (`.gitleaks.toml` allows the project's own shapes that look like keys: the message
  keys of findings in audit bundles and tests, and the test fixtures that play a
  key); the hook in `scripts/hooks/pre-commit` scans the staged changes before a commit
  when gitleaks is installed. The keys themselves live in the `.env` next to the config
  file, never in the repository.
- **Vulnerabilities.** Trivy scans `uv.lock` on every change and the image once built,
  under one policy: a high or critical finding with a fix fails the job, one without a
  fix is reported; the fix is a lockfile update or a rebuild of the image, which carries
  Debian's updates from the day it is built.
- **At runtime.** The app downloads nothing: the UI assets and the fonts are in the
  package, and the API documentation pages, the one place that would load Swagger UI
  and ReDoc from a CDN, are off unless `server.api_docs` says so.
- **Provenance and bills of materials.** The release workflow attests the wheel and the
  image with GitHub's build-provenance action: a Sigstore signature by the workflow's own
  identity that binds the artifact's digest to this repository, the tagged commit and
  the workflow, which `gh attestation verify` checks against a download. uv uploads the
  PyPI attestation (PEP 740) under trusted publishing, and the job fails if pypi.org does
  not hold it afterwards. Trivy writes a CycloneDX bill of materials of the locked
  dependencies and one of the image; both go on the GitHub release and are attested the
  same way (`SECURITY.md`, "Verifying a release").
- **Reporting.** `SECURITY.md` names the private channels, the scope and the response
  times.
- **Contributions.** The maintainers (`MAINTAINERS.md`) keep the rights in what they
  write and publish it under the Apache License 2.0 by committing it. Everyone else
  signs off every commit, which certifies the Developer Certificate of Origin (`DCO`)
  and accepts the assignment of the rights in the contribution to the main copyright
  owner (`CONTRIBUTING.md`, "Rights in your contribution"); a substantial contribution,
  or one an organisation holds the rights in, comes with the signed form
  `docs/assignment.md`. CI checks the sign-off on every pull request and skips the
  maintainers, whose logins it reads from `MAINTAINERS.md`, and bots. The test job of
  the pinned Python version measures the coverage of the package and writes it to the
  job summary; no number is required.

Settings of the repository on GitHub that go with this, outside the code: branch
protection on `main` with every CI job required, the sign-off check among them, secret
scanning with push protection, Dependabot alerts, and private vulnerability reporting
switched on ([releasing.md](releasing.md) names them).

## 8. Data lifecycle

What the service stores, where, for how long, and how it leaves:

- **What.** For every job: the source document as segments, the fact sheet, every
  draft version with its rule findings, judge reports and repair records, the review
  with the reviewer's edits, the pipeline summary, and one row per model call (stage,
  model, tokens, latency, no text). With `llm.cache = true`, the response cache keeps
  every answer (fact sheets and drafts, so the document's content) under a hash of its
  prompt, not the prompt itself; it is off by default and meant for development and
  evaluation.
- **Where.** `data.dir` (by default the user's data folder, such as
  `~/.local/share/leichtfacile` or `%LOCALAPPDATA%\leichtfacile`, §3; on a server a
  folder on a disk the organisation controls): `leichtfacile.sqlite` and, with the
  cache on, `llm_cache.sqlite`, and `backups/`, the copy of the database made before an
  update changes its schema ([architecture.md §5](architecture.md#5-data-model)), which
  the operator deletes under the records rules, since it holds the documents;
  `leichtfacile backup <folder>` writes a copy wherever the operator says. Nothing else
  is written; the exports are generated on request and not stored. Encryption at rest
  belongs to the disk: put `data.dir` on an encrypted file system or disk (LUKS,
  BitLocker, the cloud provider's encrypted volume), which costs nothing in the
  application and covers the WAL and temporary files too; the application does not
  encrypt rows itself.
- **How long.** By default until someone deletes the job. `data.retention_days` (0 by
  default) makes a housekeeping thread delete, once an hour, every job without any
  activity (a run, a review save, an export) for that many days, with its artifacts,
  calls, events and cache rows; running jobs stay. A deployment that handles letters with personal data should set it to the
  period its records rules allow and export what it must keep.
- **Deletion.** The row menu of the drafts list, the job and review pages, and
  `DELETE /api/v1/jobs/{id}` remove a job with its artifacts, calls and events (`ON DELETE
  CASCADE`) and with its rows in the response cache (`Store.delete_job`: the keys of
  the job's calls are recorded in `llm_calls`; a row another job uses too stays), also
  while no model is ready and after the cache was switched off, so no answer about the
  document outlives the job. A running job is stopped first.
- **What leaves the machine.** Only the model calls: the document text, the fact sheet
  and the drafts go to the endpoint named by `llm.url`, nowhere else; §5 and the
  endpoint profiles in [architecture.md §6](architecture.md#6-the-llm-client) say which
  endpoints are sovereign. Fetching a web address a user submitted sends a request to
  that site, with nothing of a document in it.
- **Logs.** Model, stage, tokens and latency per call; job ids and stages; one line
  per request with method, path, status, duration, client address and request id, no
  query string; errors without the words of the document or the answer (§6). Nothing a
  person wrote.
