# Changelog

All notable changes to Leicht·Facile. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Every release has a page on
[GitHub](https://github.com/bobrovsky420/leicht-facile/releases) with the wheel and the
list of its commits, and from 0.7.0 on it is on [PyPI](https://pypi.org/project/leichtfacile/).

## [Unreleased]

### Added

- A preset for gpt-oss-120b, an open-weights model, on the Hugging Face router:
  `huggingface-gpt-oss-120b-groq` writes and checks on Groq's hardware in Canada or the
  United States, for public documents (needs `HF_TOKEN` and Hugging Face credits). On a
  fresh install it is picked only when `HF_TOKEN` is the only key set.
- On that preset, 8 of the 12 sample letters sent unchanged are answered in seconds and
  at no cost from recorded runs (`leichtfacile-samples` 0.6.0); the other four run live.

### Changed

- The round that asks only for the facts still missing after the repair rounds is off
  by default (`pipeline.facts_rounds` 0, was 1): with the recover round after it, it kept
  no more facts on the evaluation pairs with three models and cost 7 to 8 percent more
  tokens. `[pipeline] facts_rounds = 1` brings it back.

### Fixed

- A model that writes a Unicode or non-breaking hyphen for a plain one (gpt-oss does,
  even inside e-mail addresses) no longer leaves it in the draft: an address written so
  failed when a reader copied or clicked it, and its value counted as missing.
- Rappen, centimes and cents count as hundredths: `70 Rappen` is now the amount of
  `CHF 0.70`, so a draft that writes one for the other keeps the value, and `50 Rappen`
  no longer passes for `CHF 50`. A word that only begins like a currency
  (`francophones`, `Europäer`) no longer makes an amount.
- A price at the end of a sentence (`Das kostet Fr. 3.10.`) and a section number
  (`Ziffer 3.2.1`) are no longer read as dates, and `am 1.3. 20 Personen` keeps its
  count instead of becoming 1 March 2020; NUM-03 stops suggesting dates for them.
- NUM-04 no longer reads a range of prices (`CHF 1.50-2.50`) as times, in German,
  French and Italian.
- Italian times at the start of a sentence (`Ore 9.00`) count as times; a word that
  ends in `ore` (`San Salvatore 3`) and the German `alle` before a price no longer make
  one.
- A draft that addresses the reader with `Sie` only at the start of its sentences no
  longer gets the LEX-06 reminder that it never addresses the reader.

## [0.13.2] - 2026-11-08

### Added

- The web app can answer a sample letter sent unchanged from the New draft form from a
  recorded run of it, in seconds and at no cost, and the job and review pages then say
  so; a changed text, another level or preset, and a step run again go to the model as
  before, and the command line never replays. The recordings come with a later version
  of the samples package (below), without a new version of the app.

### Changed

- The sample letters come in their own package, `leichtfacile-samples`, which the app
  installs with it: the letters and their recorded runs, apart from the code, with a
  version of their own (0.5.0; the app takes any later 0.x). `data.examples_dir` still points the
  app at a folder of your own letters.

### Security

- Deleting a draft, by hand or by the retention purge, removes its answers from the
  response cache also while no AI model is ready (no key yet) and after the cache was
  switched off; they stayed, with the document's fact sheet and drafts in them. An
  answer that another draft of the same text still uses stays until that draft goes.
- An uploaded or fetched PDF is read in a separate process that is stopped after 60
  seconds and, on Linux, may take 1 GB of memory, so a small file that unpacks to
  gigabytes can no longer exhaust the server; a PDF of more than 200 pages is refused,
  and one far over the text limit is refused without being read to the end. A PDF
  takes about a second longer to read.
- A key put into a provider's `headers` (or `extra_body`) is masked by `config show`,
  and `config set`, `config show` and `serve` warn that it sits in the config file in
  plain; `config show` printed it whole.

## [0.13.1] - 2026-11-06

### Fixed

- An export keeps the note "Entwurf: noch nicht geprüft" until the review is marked
  complete, and only then does a Word file name who decided; a few decisions of many
  removed the note and signed the document.
- Once one version of a draft has saved decisions, another version's page says so and
  links to it, and its first decision asks before it replaces them. Every save on that
  page was refused as "saved by someone else", even after a reload.
- The progress page stops asking for news when the draft is gone or the login has
  expired, and after five failed attempts in a row, and says so; it asked every few
  seconds for as long as the tab stayed open.
- An uploaded Word or OpenDocument file, an image or any other file that is no text is
  refused with a message naming the formats that are read; it became a draft of
  garbage that went to the model.
- A letter pasted from Word or Outlook (one line per paragraph, no blank lines) keeps
  its title, salutation and paragraphs apart; it became one long paragraph. An address
  stays one paragraph, and the closing keeps the signature after it.
- A pasted or PDF line that holds an amount, an IBAN, a date with its year or a phone
  number is no heading, so the draft has to keep the value; a bill's total set in bold
  was a heading, which the fact checks pass over.
- A PDF whose letterhead or footer repeats on every page keeps one copy of the phone
  number, e-mail and web address in it; from two pages on they went with the repeated
  lines.
- A pasted line that starts with a number, such as "3. Stock, Zimmer 304", keeps the
  number unless it is part of a numbered list; it became a list item without it. A
  numbered list with blank lines between its items stays a list.
- Sentences are split more reliably: "bis 30.6. Ihre Lohnausweise" stays one sentence,
  "Postf. 123", "Ziff. II", "lu. 8 h" and "lun. 8-12" are not cut, "5 m." and "12 h."
  can end a sentence, and the number that opens a paragraph ("2. Die Frist ...") is no
  segment of its own.
- A web page or text file that is UTF-8 but for one stray byte is read as UTF-8, with a
  replacement character for that byte; the whole page was read as Windows-1252, every
  umlaut broken. An en dash or a euro sign written `&#150;` or `&#128;` (old pages,
  HTML saved from Word) stays; it was deleted, and "8&#150;12 Uhr" read 812.

## [0.13.0] - 2026-11-06

### Added

- `[server] offer_pipelines = true` shows the pipelines P1 (no judge) and P0 (one
  prompt) on the New draft form next to P2, for an installation that compares them.
  The API and the command line take any pipeline as before.

### Changed

- The shipped default preset `publicai-apertus` lets the Apertus 1.5 8B write again and
  the 70B check, now that the Public AI gateway serves the 8B again; since 28 October
  2026 it ran every stage on the 70B. Neither model thinks on the gateway. The Public AI
  tables (docs/evaluation-publicai.md) were measured with the 70B at every stage, which
  a job still gets with the 70B as its writer model.
- The New draft form shows the choices a reviewer makes: the level, the document type,
  the sender and the form of address. The language of the document, the title, the AI
  model and the model names sit under "More options", and the pipeline choice is gone
  from the form (P2 runs). The form remembers the level, the sender and the form of
  address of the last draft made in the browser.
- The review saves by itself, a moment after each decision; the "Save review" button
  is gone. The note at the top right says when it last saved (Ctrl+S saves at once),
  a failed save shows "Try again", and a review a colleague saved in the meantime asks
  for a reload before anything is overwritten. An export waits for a pending save and
  downloads nothing while a save fails, and a save still pending when the page closes
  goes out with it.
- Typing in a block's field makes the block edited; a text set back to the original
  restores the decision made before. Until now a text typed without choosing Edit was
  not saved.
- One line says what is left to do. On the review page the strip shows "4 blocking
  problems" and "33 blocks undecided", each a button that shows those blocks, or "Ready
  to export"; the draft versions sit behind a "Versions" menu, and the error, warning
  and fact counts moved to the More tab. The list of drafts shows the same per row in
  one "To do" column in place of the Checks, Review and Pipeline columns (the pipeline
  joins the source line when it is not P2), and a click anywhere on a row opens the
  draft. Status filters with no draft are hidden.
- While a draft runs, the page header says the stage and about how long the run still
  takes, from the stage times of the last finished drafts on the same pipeline, and the
  browser tab names the stage. The calls, tokens, model time and model names are folded
  away under the stages.
- The exports live in one place, the reader view's panel: the review page's Export
  button opens it, and the row menu of the list offers "Reader view and export" in
  place of the list of formats.
- The explanations in the app are one-time hints: the notes on the Facts, Findings and
  Questions tabs and above the glossary of the review page, next to "Results so far"
  while a draft runs, and above Check my text each carry a cross that hides them for
  good in that browser. The four steps "How it works" show in the empty list of drafts
  alone, before the first draft.
- The app bar is for the reviewer: the model indicator shows the dot and the word
  "Model" (the model's name and status are its tooltip, and a screen reader hears them),
  the guide link reads "Help", and the API link moved to the foot of the list of drafts,
  where it appears only when `[server] api_docs` serves the documentation pages. The
  example letters on the New draft form show those in the interface language first, the
  others behind "More examples".
- Before the first draft, the start page shows the example letters as a card of
  mini-cards under the empty list, each with a short description, its language and its
  sender, those in the interface language first, instead of a row of buttons. The
  card's cross hides it in that browser; "Show the example letters" brings it back. The
  empty list no longer repeats the New draft button of the page header. An
  installation's own letters (`[data] examples_dir`) get their description from the
  `description` key of the JSON file next to each letter.

### Fixed

- A worker that met a busy or failing database while taking the next job no longer
  stops for good (the service then ran no job until a restart while `/healthz` said
  ok): it logs the error and tries again after five seconds. With `[jobs] workers`
  above 1, idle workers no longer wake each other without pause, which took tens of
  thousands of database write transactions a second.
- Opening the list of drafts no longer postpones the deletion of drafts stored before
  an upgrade or moves them in the queue: the counts it fills in for them no longer
  count as a change of the draft.
- Amounts in billions are read as billions: `2 Milliarden Franken`, `milliards` and
  `miliardi` counted as millions, so a draft that turned billions into millions passed
  the fact checks. The Swiss `Mia.` is read as well.
- The amount style finding (NUM-07) keeps the cents in its suggestion: `500.50 CHF`
  becomes `500.50 Franken` and `20,50 €` `20,50 Euro`, where the cents were dropped
  and a repair round that applied the suggestion changed the amount.
- A spaCy pipeline runs one text at a time, whoever uses it: the checkers of the Swiss
  and the German variety, the vocabulary matcher, the word splitting and the split of
  free text into blocks could run the same pipeline at once from the worker threads
  and the Check page.
- The word splitting keeps the linking s on its part: `Betreibungs·amt`,
  `Sozial·versicherungs·amt` and `Gemeinde·steuer`, no longer `Betreibung·samt` or
  `Gemeindes·teuer`.
- A repair answer that only repeats sentences the draft already has leaves the flagged
  block as it was. It used to take the block's place, and the original block it
  repeated, never flagged, went with its heading.
- A variable such as `LEICHTFACILE_PRESETS__CSCS_APERTUS__MODELS__WRITER` sets the
  preset `cscs-apertus`, as the documentation shows: the underscore stands for the
  name's hyphen. It made a preset `cscs_apertus` without a provider, which broke
  `leichtfacile preset list`, the model page and the New draft form.
- `eval rescore` keeps each row's region, so rescored rows of Germany and Austria are
  no longer counted as Swiss German.
- A web page whose `<body>` or page wrapper carries a cookie or consent class, as the
  WordPress plugin Cookie Notice sets it (`cookies-not-set`), keeps its content: it was
  taken for a cookie notice and dropped whole, leaving the page title alone.
- An uploaded text or HTML file is read as the command line reads it: a Windows-1252
  file keeps its umlauts and apostrophes, a page its declared charset, and a UTF-16 or
  UTF-32 file (Notepad's "Unicode") is read at all. Every upload that was no PDF was
  read as UTF-8 with replacement characters.
- The audit bundle's `final` is the version the review decided, the one that went out;
  it was the pipeline's final version, reported as not reviewed, when the reviewer had
  decided another version from the Versions menu.
- A PDF with a page that shows pictures but no text, such as a scanned attachment or a
  table as an image, is refused with the page numbers, as a scan is. The page was left
  out without a word, and the draft missed what it said. Blank pages are skipped as
  before.

### Security

- The cross-site guard refuses a state-changing request from a page on a sibling host
  (`Sec-Fetch-Site: same-site`, such as `evil.example.ch` for `app.example.ch`) unless
  its `Origin` is this server; such a page could submit, delete or rerun drafts
  through a logged-in browser.
- The text log format keeps one line per record: control characters in a request
  path (`%0A`) or a user name are written escaped, and a traceback line that begins
  like a record is indented, so a request can no longer forge a log line.
- Fetching a web page stays within 15 MB of memory for the body however it is
  compressed: a compressed body is inflated no further than the limit, and one with two
  codings (`gzip, gzip`) or a coding the request did not ask for is refused. A 612-byte
  answer took 618 MB before the limit was seen.
- The 120-second limit for fetching a web page holds while the headers arrive: a server
  that sent its headers one byte at a time kept a request and an ingest slot busy for
  as long as it liked.

## [0.12.0] - 2026-11-04

### Added

- `leichtfacile backup <folder>`: a consistent copy of the job database into the folder,
  named with the moment it was made, while the app runs or not. The response cache is
  not copied. Before a newer release brings a database up to date, the app now keeps a
  copy of it as it was, in `backups/` next to it (`leichtfacile-v<schema>.sqlite`, one
  per schema version): what a downgrade restores (docs/quickstart.md, "Updates").
- `docs/openapi.json` describes the JSON API (OpenAPI); a test keeps it equal to the code.
- Who did what, behind the proxy login (`auth.proxy_header`): the job records who
  submitted it, every review decision who made it and when it was first saved in that
  form (a later save that sends it unchanged keeps the stamp), the review who saved it
  last, the audit bundle who exported it and who decided (`final.reviewers`), and the
  Word footer names the latter ("Geprüft von a.muster, b.muster"). The deletion of a job
  is logged with the user, and the access line names the user of every request. Without
  the login the new fields stay empty. An existing database gets the new column when it
  is opened.

### Changed

- The audit bundle's `repair_records` and `GET /api/v1/jobs/{id}/artifacts/repair`
  name, for every sentence a repair round added, the block kind (`kind`) and the
  source sentences it cites (`segment_ids`), as a draft's blocks do. Rounds run before
  this version have neither field in their record.
- The JSON API lives under `/api/v1`. The old paths under `/api` answer the same until
  3 May 2027, each response with the headers `Deprecation`, `Sunset` and a `Link` to the
  same path under `/api/v1`, and are removed in the first minor release after that
  date. Scripts move to `/api/v1`; the web UI already has.
- The shipped default preset is `publicai-apertus`, Apertus 70B on the Public AI gateway,
  instead of `cscs-apertus`: the CSCS inference API grants keys on application, so most
  installations could not run the pre-selected preset. Setup and the model page list
  Public AI first, and a `PUBLICAI_API_KEY` picks its preset before a `CSCS_API_KEY`
  does. The default is measured on the same pairs as the reference numbers
  (docs/evaluation-publicai.md). An installation that named its preset is unchanged.
- The logo's tile is larger: its looped L is as tall as the capital L of the name next to
  it and stands on the same baseline. The name in the app bar keeps its size.
- `leichtfacile config set auth.token <secret>` (and `providers.<name>.api_key <key>`) no
  longer writes the secret into the config file: it goes into the `.env` next to it,
  under `LEICHTFACILE_TOKEN` or the provider's variable, and the file names the variable.
  Without the value the command asks for it, hidden. A secret that stands in a settings
  file by hand is still read, now with a warning from `config show`, `config edit` and
  `serve`.

### Deprecated

- The JSON API's paths under `/api` (without `/v1`): they answer until 3 May 2027 and are
  removed in the first minor release after that date.

### Fixed

- A database written by a newer release is refused with a message that says so and
  names the copy to restore, instead of being opened and read with the wrong models.
- Review page: long block ids such as `b007.2.1`, which blocks added by a repair or a
  recovered fact get, no longer run into the severity icons; the id column grows to fit.
- Behind a reverse proxy on the same machine with the proxy login (`auth.proxy_from =
  ["127.0.0.1"]`, the recommended server deployment), every request got 403 "not from the
  trusted reverse proxy": uvicorn's own proxy-headers middleware replaced the connection's
  address with the forwarded one before the login compared it with the proxy's addresses.
  `serve` turns that middleware off, and the app reads `X-Forwarded-For` and
  `X-Forwarded-Proto` itself, trusted from `auth.proxy_from` with any login, or without
  it from a proxy on this machine, so the rate limit, the access line and the Secure
  cookie still see the users behind a proxy.
- Screen readers no longer read out the job page's running time at every update (every
  2 to 5 seconds while a job runs); they hear the stage when the job reaches a new one,
  "Stage 3 of 6: Check". The page also replaces its progress view only when it changed,
  so a screen reader keeps its place in the results so far.
- Review page: the open block is marked as the current one for screen readers
  (`aria-current`); opening a block used to be silent.
- Dark mode: the outline of the selected filter, view or source tab stands out from the
  grey track at 3.1:1 instead of 2.98:1, which was under the 3:1 that WCAG asks for.
  Text fields share the slightly lighter outline.

### Security

- `compose.yaml` pins the vLLM and llama.cpp images by digest (their tags move), gives
  vLLM a shared memory of its own instead of the host's IPC namespace, and runs every
  container with every capability dropped and no new privileges, the app's and
  llama.cpp's on a read-only root with the volume as the one writable place. Dependabot
  proposes the next image digests weekly.

## [0.11.0] - 2026-11-02

### Added

- `make run` in a checkout builds the container image, starts it with `compose.yaml` and
  opens the web UI once it answers; `make stop` stops it and `make logs` follows its log.
- The Markdown, HTML and Word exports can carry the original text after the easy-language
  text, on a new page in Word and in print: "Add the original text" in the reader view's
  export panel, "... with original" in the Export menus, `original=1` on the API.
- An illustrated user's guide for the people who review the drafts, from the source text
  to the export: docs/user-guide.md, and on the site in English and German. The app bar
  links to it (Guide, Anleitung).
- Workspaces, off by default (`[server] workspaces = true`): every browser gets its own
  drafts list behind a link anyone may open (`/w/<token>`), with Copy link and New link
  on the drafts page; scripts send the token in the `X-Workspace` header. The login
  still decides who gets into the app; the server stores only the link's hash and never
  logs the link.
- `[server] notice`: a short text under the app bar on every page, one text or a table
  by interface language, for a demo's terms or a test installation.
- A logo (docs/logo.md): one stroke that loops like a handwritten L, runs out straight and
  ends in a full stop, on a blue tile, next to the name. The app shows it in the app bar
  and, for the first time, has a favicon and a touch icon; the README and the project's
  site show it too. `scripts/logo.py` makes the files.

### Changed

- The web app takes texts of up to 10,000 characters (about 1,400 words), now also when
  the text comes from a file or a web page; before, pasted text could have 200,000
  characters and files and pages had no limit. `leichtfacile setup --max-chars` or
  `[texts] max_chars` in the config file changes it, with a warning below 1,000 or above
  200,000 characters.

### Fixed

- Behind the trusted reverse proxy of the proxy login (`auth.proxy_header`), the app takes
  the scheme from the proxy's `X-Forwarded-Proto`, so its cookies are marked `Secure` and
  its links are https; before, a proxy that was not on 127.0.0.1 (a container network)
  left them http.
- On pypi.org, the README's picture of the review page showed no image: its files were
  relative. The build hook now makes the `src` and `srcset` of the README's pictures
  absolute too.

## [0.10.2] - 2026-11-01

### Fixed

- The release uploads the wheel's signed provenance (PEP 740) to PyPI together with the
  wheel, and stops before the upload when the two are not paired. The wheels of 0.10.0
  and 0.10.1 on PyPI have none, and neither version has a container image; their GitHub
  releases are complete. The app is the same in all three.

### Security

- The locked dependencies take opentelemetry-api 1.45.1 (unbounded parsing of the
  tracestate header) and setuptools 84.2.1 (a path escape when installing legacy wheels
  on Windows). This matters for the container image, which installs the locked
  versions.

## [0.10.1] - 2026-11-01

### Fixed

- The release signs the wheel before it uploads it to PyPI. The upload still left the
  signature behind, so the wheel of 0.10.1 on PyPI has no provenance either, and
  0.10.1 has no container image; its GitHub release is complete.

## [0.10.0] - 2026-11-01

### Added

- Letters from schools and other organisations. A job names its sender (authority,
  school or organisation) and the form of address (formal, informal or plural: Sie, du
  or ihr; vous or tu; Lei, tu or voi), in the New draft form, the API and the command
  line (`--sender`, `--address`). The prompts, the style guide and the check of the form
  of address (LEX-06) follow them. The profiles are data in
  `src/leichtfacile/senders/senders.toml`. The use case is
  [docs/use-case-schools.md](docs/use-case-schools.md).
- Six school example letters in German, French and Italian: a camp letter to parents
  and a letter about the trial-apprenticeship week to students, in the du form.
- FACT-10: every item of a list in the source is a fact the draft must carry. A
  dropped item blocks the draft, and a repair round asks for it. Intro lines, questions
  and lines that repeat a heading or an earlier line are no facts.
- A school group in the vocabulary (German, Swiss German, French and Italian), and the
  liability insurance in the insurance group.
- A dark mode in the app that follows the system setting.
- The drafts list filters by variety.
- A container image, `ghcr.io/bobrovsky420/leichtfacile`, and a `compose.yaml` that
  can start a model server next to the app (vLLM or llama.cpp). The setting
  `server.published_on` tells the app where Docker publishes its port.
- [SECURITY.md](SECURITY.md): how to report a vulnerability and how to verify a release.
- This changelog, linked from the project's page on PyPI.

### Changed

- The repair rounds no longer repeat what the draft already says. A fact the judge
  calls missing although a block carries it is sent back to that block, additions that
  restate a block are dropped, two facts with the same value become one, and a sentence
  the model split into two additions is joined again.
- The value extractor reads a range of days ("vom 7. bis 11. Juni 2027") as both dates,
  and an address with "in", "à" or "a" before the postcode.
- Three vocabulary explanations no longer assume an authority or an employee: a Gesuch
  (demande, domanda) asks an office or a school, and the accident insurance pays wages
  to employees only.
- German checks: GRAM-01 suggests the active voice and leaves "geboren wurden" alone,
  LEX-01 offers a Mediopunkt split for nouns only, and NUM-02 accepts spaced insurance
  numbers (the Austrian SV-Nummer). The German vocabulary names the Grundsicherungsgeld.
- The API documentation pages `/docs` and `/redoc` are off by default, since they load
  their scripts from a CDN (`server.api_docs`).
- Dependencies: fastapi 0.162.0, pydantic 2.14.1, openai 3.37.0, trafilatura 2.3.1.

### Fixed

- Web pages: cookie notices are no longer read as content, and the sections behind a
  page's jump list are kept.
- The vocabulary finds German participles and -ieren forms that the lemmatiser leaves
  as they stand (urgiert, aufgerechnet). Of two equal matches it keeps the term as
  written, the same on every run.

### Security

- New dependency releases wait a week before the lockfile takes them; Dependabot
  proposes updates weekly; CI scans the history for secrets and the lockfile and the
  image for known vulnerabilities.
- Every release carries signed build provenance for the wheel and the image, and a
  CycloneDX bill of materials for each. The release workflow checks the attestation
  PyPI holds for the wheel.

## [0.9.1] - 2026-10-30

### Changed

- The package summary on PyPI names Switzerland, Germany and Austria.

## [0.9.0] - 2026-10-30

### Added

- German for Germany and Austria. A job, its source and its draft carry the region (CH,
  DE or AT), set per installation with `texts.region`. Each country gets the rules of
  its sources (Netzwerk Leichte Sprache, DIN SPEC 33429), its spelling with ß, its
  numbers, euro amounts, dates, phone numbers and addresses, its office words and an
  example letter: a Wohngeld-Bescheid for Germany, a Familienbeihilfe-Bescheid for
  Austria.
- The decision mode reads a German or Austrian Bescheid.
- An evaluation on 8 official pages from each country, on Apertus 1.5 70B through
  Public AI.
- The project page <https://leichtfacile.ch>, in English and German.

### Changed

- The German vocabulary is split into the entries the three countries share and one
  file per country.
- The app uses the typefaces Atkinson Hyperlegible Next and Mono.

## [0.8.0] - 2026-10-28

### Added

- Italian (lingua facile): 28 checks of its own, a tagger built from the Morph-it!
  lexicon, a vocabulary, prompts, an example letter, the interface in Italian, and an
  evaluation through Public AI.
- The app's AI model page (`/model`): choose a preset, enter its key, or point the app
  at a server of your own.
- `leichtfacile serve <preset>` runs one preset for one session, without saving
  anything.
- The provider OpenRouter, and presets for Google Gemini and Claude Opus 5.5.
- A fresh install uses the first preset whose provider's key is set.

### Changed

- The model setup is split into providers, model tables and presets, kept as data in
  `src/leichtfacile/presets/presets.toml`. `leichtfacile preset` replaces
  `leichtfacile endpoint`.
- The language models for German, French and Italian are the PyPI packages
  `leichtfacile-model-de`, `-fr` and `-it`, installed with the app.
- `extra_body` merges key by key across the provider, the model table, the preset and
  the config files.

### Removed

- `leichtfacile models` and the download of the spaCy models.

### Fixed

- The job store queues its writers, so a waiting writer no longer fails with "database
  is locked".

## [0.7.1] - 2026-10-26

### Added

- Providers Groq, Hugging Face, OpenAI and Anthropic next to CSCS and Public AI, each
  with presets ready to use. Setup offers the providers' current models.
- `leichtfacile endpoint` (list, use, remove) and `leichtfacile config` (show, path,
  set, unset, edit).

### Changed

- The settings live in a TOML config file with sections; `.env` holds only the keys.
- Jobs stored by an earlier version are brought up to date when they are opened.
- The repair rounds, the evaluation rows, the export layouts and the review counts each
  have one implementation instead of several.

## [0.7.0] - 2026-10-23

### Added

- Leicht·Facile is on PyPI: `uv tool install leichtfacile` or `pip install leichtfacile`.
- `leichtfacile setup` asks for the endpoint, the key and the model; `leichtfacile
  serve` starts the app and opens the browser; `leichtfacile models` downloads the
  language models for German and French.
- The app works with any OpenAI-compatible endpoint. Apertus is the recommended model
  for confidential texts.

### Changed

- The repository has a flat layout without the hackathon's `track_2b/` folder, and the
  example letters ship inside the package.

### Removed

- The Docker image and the Compose setup.
- The hackathon's technical report, submission files and demo video, and the replay of
  recorded example runs.

## [0.6.0] - 2026-10-13

### Added

- Export to Word (`.docx`) in the reader layout with a provenance footer, in the API,
  every export menu and `simplify`.
- The German and French example letters run with one click, replaying runs recorded on
  CSCS.

### Changed

- The prompts address the model with du and tu.

### Fixed

- False alarms and gaps of the value extractor, and the judge's quote check.
- The URL filter blocks the address ranges that early Python 3.12 counts as public. CI
  tests Python 3.12, 3.13 and 3.14.

## [0.5.0] - 2026-10-11

The first release, built for Hack Apertus 2026.

### Added

- The pipeline for German (Leichte Sprache A2, Einfache Sprache B1) and French (FALC):
  a fact sheet of what must survive, a draft linked to its source sentences with every
  omission explained, a deterministic checker, a judge model, and repair rounds for the
  findings, the missing facts and the office words.
- The rules of the published Swiss guidelines and the exact fact checks FACT-01 to
  FACT-09: no value lost, no value invented, periods, identifiers and addresses as
  written, a medication with its dose in one block.
- The decision mode for decisions of child and adult protection authorities and courts:
  the operative part and the appeal instructions protected, the authority's notice
  first and last.
- The German and French vocabulary with checked explanations.
- The review page with source and draft side by side, provenance, the fact checklist
  and a decision per block; the reader view; the Check my text page; the interface in
  English, German and French.
- Exports as Markdown and HTML with a JSON audit bundle.
- The evaluation: the single prompt, the Canton of Zurich's published prompt and the
  full pipeline on 20 held-out German pairs and 3 French pairs on the CSCS endpoint.
- A wheel on the GitHub releases page, a Docker and Compose setup, CI.

### Security

- Security headers with a Content Security Policy, a rate limit, an optional login and a
  body limit; a URL fetcher that checks every redirect hop; a guard against cross-site
  requests; a job queue with limits and a time budget.

[Unreleased]: https://github.com/bobrovsky420/leicht-facile/compare/v0.13.2...HEAD
[0.13.2]: https://github.com/bobrovsky420/leicht-facile/compare/v0.13.1...v0.13.2
[0.13.1]: https://github.com/bobrovsky420/leicht-facile/compare/v0.13.0...v0.13.1
[0.13.0]: https://github.com/bobrovsky420/leicht-facile/compare/v0.12.0...v0.13.0
[0.12.0]: https://github.com/bobrovsky420/leicht-facile/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/bobrovsky420/leicht-facile/compare/v0.10.2...v0.11.0
[0.10.2]: https://github.com/bobrovsky420/leicht-facile/compare/v0.10.1...v0.10.2
[0.10.1]: https://github.com/bobrovsky420/leicht-facile/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/bobrovsky420/leicht-facile/compare/v0.9.1...v0.10.0
[0.9.1]: https://github.com/bobrovsky420/leicht-facile/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/bobrovsky420/leicht-facile/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/bobrovsky420/leicht-facile/compare/v0.7.1...v0.8.0
[0.7.1]: https://github.com/bobrovsky420/leicht-facile/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/bobrovsky420/leicht-facile/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/bobrovsky420/leicht-facile/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/bobrovsky420/leicht-facile/releases/tag/v0.5.0
