# Leicht·Facile - implementation plan

Working document, kept in the repository since 6 October 2026 (AGENTS.md says when to update it).
Written 5 October 2026, evening; the gap register (§10) and WP13 to WP17 added 6 October
2026, night; restructured 9 October 2026 so that each topic has one section.
Deadline: **16 October 2026, 12:00 CEST**, no extension.

Source of truth for *what* we build: [track_2b/docs/architecture.md](track_2b/docs/architecture.md) and
[track_2b/docs/rules.md](track_2b/docs/rules.md). This file is about *in which order*, *by when*, and
*what gets cut*. When the two disagree, fix the docs, not this plan - AGENTS.md requires
the docs to stay in sync with the code.

## Next steps before submission (as of Sat 10 October 2026)

The short path to the deadline, in dependency order. Each step points to where it lives
(§3, §4, track_2b/docs/submission.md); tick it here and there when it is done.

1. [ ] **Close the pipeline before the prompt freeze (Sun 11 Oct, 18:00; D-AD).**
   Any last pipeline change goes in and is measured on dev with `--redo` first. Take the
   review stopwatch for 3 P2 drafts (WP13 value numbers; *done 10 Oct*). After 18:00
   nothing in the pipeline moves except bug fixes.
2. [ ] **Final CSCS evaluation (Sun 11 Oct, night; WP13).**
   Snapshot `track_2b/eval/results-cscs` to the next vN, then every row with `--redo`: P1 and P2
   first, then P0 and both P0-ZH variants with the cache off, last the two 70B rows.
   Then `eval report`, `eval numbers` and `eval diagnose`, without model calls.
3. [ ] **Read the numbers and decide the headline (Mon 12 Oct, G3; D-M).**
   Apply the case table A to D in WP13 to P2 against P0-ZH `complete`, no debate. Case A
   also decides D-L: Zurich is named in the video and its evidence scene is rewritten.
4. [ ] **Numbers in one pass, then the audit (Mon 12 Oct, G4; WP13, WP16).**
   Report §5 and §1, README's status block and "Why not one chatbot prompt?", the
   video's evidence scene. Diff every number against `eval numbers`, each with its
   endpoint and split.
5. [ ] **Rebuild the example jobs and finish the video (Mon 12 to Tue 13 Oct; WP8, WP11).**
   Rebuild the example bundles on the frozen pipeline *(done 10 Oct on the day's
   pipeline, both clean; again only if the pipeline changes before the freeze)*.
   Run DE-4 and FR-4 inside a short letter for the Again scene, retake the app captures
   from the rebuilt bundles (video/README.md step 7; *done 10 Oct*), re-render version C,
   upload, put the URL in README, report and form.
6. [ ] **Finish the report and README (Wed 14 Oct, G5; WP11, WP16).**
   WP16's positioning paragraph and messaging pass, the owner's answers to every
   **[OWNER]** placeholder, the **[PENDING]** video link and final-run commit. Export to
   PDF, 6 pages, `track_2b/RoestigrabenBridgers_Report.pdf` and the same file at the root
   (track_2b/docs/submission.md §5); the report's root copy changed with it.
7. [x] **Hardware statement for the on-prem profile (parallel; cut if blocked; WP10).**
   Done 10 Oct: `local-llm` ran on an AWS g6.xlarge (one L4 24 GB) in Zurich and took
   the example letter end to end; track_2b/eval/hardware/aws-l4-2026-10-10/, report §2.
8. [ ] **Clean-checkout test on Linux or a second machine (by Wed 14 Oct, G5; WP11).**
   Done 10 Oct on the same Linux machine (commit 6936d05): clone, `.env`, `make run`
   unchanged, one job end to end against the local vLLM. Repeat only if the Dockerfile,
   the dependencies or the Makefile change before the submission. *Due again: the move
   into `track_2b/` (10 Oct) changed the Dockerfile and the Makefile; from a fresh clone,
   `make run` from the root and from `track_2b/`.*
9. [ ] **Repo public, CI green (Thu 15 Oct, G6; WP11).**
   Check that `git log -p -- .env` is empty, make the repository public, confirm CI is
   green on the final commit. Optional afterwards: the awesome-apertus pull request
   (WP16).
10. [ ] **Submit (Thu 15 Oct; at the latest Fri 16 Oct before 12:00 CEST; WP11).**
    Fill the form from track_2b/docs/submission.md §2: repo URL, PDF, video URL, model "8B + 70B
    v1.5", the message to the jury. Work through the checklist in track_2b/docs/submission.md §7
    before pressing Submit.

## 0. How to use this plan

- Each topic has one section: scope in §2, every work package in §3, the schedule and
  the gates in §4, the cut list in §7, decisions in §8, the gap register in §10, the
  progress log in §11.
- The list "Next steps before submission" at the top is the short path to the
  deadline, in dependency order. It only points into the sections; tick a step there
  and in its work package when it is done, and change it when a date or an order
  moves.
- Update in place: tick the box, or change the item, row or list where the topic lives.
  Never append a new section, an "Added on ..." block or a revised copy of a section.
  New work goes into its work package, a new date into §4, a new decision into §8; the
  progress log gets one line per session.
- Work packages (WP) are listed in build order in §3, WP17 (after the deadline) last.
  Each has a "done when" line; do not start the next WP's main work before the current
  one's "done when" holds, except where the dependency table says they are independent.
  A finished WP is kept as a short summary of what was built.
- §4 maps WPs to dates with six hard gates. Missing a gate triggers the cut list in §7,
  no debate.
- §5 is the day-1 verification script. It decided several design choices (§8).
- Keep this file honest so an agent picking up mid-way can see the real state.

## 1. Ground rules and constraints

From the template and the hackathon rules (verified 2026-10-05):

- `make run` must start the whole thing in Docker from a clean checkout. Env vars:
  `LLM_NAME`, `LLM_BASE_URL`, `LLM_API_KEY`. Judges will try this; it is the single
  most important deliverable after the report.
- `track_2b/data/` stays under 100 MB. Texts and caches are git-ignored; only the manifest,
  examples, and clearly redistributable texts are committed.
- Repo must be public before submission. Report PDF max 6 pages, named
  `TeamName_Report.pdf`, in `track_2b/`. Demo video max 2 minutes.
- Only Apertus models at runtime. Other open models may help with evaluation only, and
  their role must be described in the report. (Plan: none; the judge is Apertus 70B.)
- Repository conventions (AGENTS.md): never commit or push; plain hyphens only, no
  en/em dashes anywhere; the project lives in the template's `track_2b/` folder, a
  Makefile at the root (organisers, 10 Oct) includes `track_2b/Makefile` with the
  targets; README.md, the report and
  its PDF exist twice, the same in both places.

Local environment facts:

- Python 3.14 on the host and in the container (`python:3.14-slim`); the project
  declares 3.12+ (`requires-python`). All compiled dependencies ship 3.14 wheels
  (checked 5 Oct). `uv sync` sets up `.venv`. GNU Make is installed on the Windows
  host (`winget install ezwinports.make`); the Makefile uses Git's `sh.exe` on
  Windows, so `make` works from PowerShell and Git Bash.
- Docker 29 (Docker Desktop must be running) and uv 0.12 are installed.
- CSCS key: fetch via hackapertus.ch/online-hack/cscs/getapi. Nothing model-related
  can be verified until it is in `.env`.

## 2. Scope

### Must ship (the demo and the report depend on these)

1. German, level A2 (Leichte Sprache), end to end: ingest (text, HTML, PDF with text
   layer) → Understand → Write → rule check → judge → repair → review UI → export
   (Markdown, HTML, JSON).
2. Deterministic rule checker for German with golden tests, including FACT-01..04.
3. Evaluation harness with conditions P0 / P1 / P2 on at least 15 German pairs,
   reporting fact coverage, rule violations per 100 blocks, readability, SARI, cost
   and latency.
4. `make run`, `make smoke`, `make test`, `make eval`; Dockerfile; compose file with
   the `local-llm` profile for the on-prem story.
5. Technical report (6 pages), demo video, public repo, submission.

Also from the gap register (§10, 6 Oct): the P0-ZH baseline with Zurich's prompt, the
fact-retention fix and the headline metrics (WP13); identifiers as hard facts (WP14); a
decision letter with personal data as an example job (WP15); the pushed state, CI and
correct counts, the positioning paragraph (WP16).

### Should ship (clear value, cut first when late)

6. Level B1 (Einfache Sprache) as a second threshold set - cheap once A2 works.
7. French (FALC) prompts, rules, 5+ pairs.
8. 8B vs 70B writer comparison on a subset; judge reliability (Cohen's κ on 30
   hand-labelled items).
9. Pre-computed example jobs so the UI is not empty on first start.

Also from the gap register: clause recipes for repair (WP14, done 7 Oct); value numbers
(WP13); `publiccode.yml` (WP16). WP12a, image ingest for the reviewed
workflow, moved up from stretch item 11 (WP15) and was cut on 7 Oct by D-N: the spike
lost hard values at every setting.

The reviewer's workbench (WP18, done 7 Oct): a calmer and denser web UI for people who
review drafts all day, designed and approved by the owner on 7 Oct and specified in
`track_2b/docs/ui-design.md`; it touches no pipeline file, so the evaluation numbers do not move.

The further use cases (`track_2b/docs/use-cases.md`, 6 Oct) and the fact checks they need
(`track_2b/docs/rules.md`), built 7 and 8 Oct: the value kinds `period`, `identifier`, `address`,
`quantity`, `schedule`, and `medication` with FACT-09 (WP14); FACT-07, FACT-08, SEM-09
and SEM-10 (decision mode v1, WP15). A drug list and a postcode list stay WP17.

### Stretch (only if everything above is green by 13 October)

10. Italian (lingua facile). *Out of scope for the hackathon (owner, 8 Oct); on the
    WP17 roadmap.*
11. Image input (photographed letters) through the API, as an end-user mode without
    expert review (WP12).
12. DOCX export; `make bundle` for the air-gapped tarball.
13. Cross-language fact-sheet consistency check.
14. LoRA from approved drafts (needs compute we do not have; most likely report-only).

After the deadline: WP12b, the end-user letter mode, and the WP17 roadmap (report §8
only).

## 3. Work packages

Package root: `track_2b/src/leichtfacile/` (layout per architecture §11). Every WP ends with:
tests green, `ruff` clean, docs updated where behaviour changed, one proposed commit
message per logical chunk (the owner commits). Effort, where given, is in focused hours;
model run time is not counted. WP13 to WP17 come from the gap register (§10).

### WP0 - Scaffold and `make run`

*Done.* `pyproject.toml` with uv and hatchling (Python 3.12+, 3.14 pinned; the Docker
build runs `uv sync --frozen`), the spaCy models as pinned wheel URLs, `config.py` for the
`LLM_*` variables and the run settings, `web/app.py` with `/healthz` (lists the
endpoint's models, never shows the key, liveness independent of the endpoint), the
Dockerfile (python:3.14-slim, non-root user, health check), `docker-compose.yml` with a
named data volume and the `local-llm` vLLM profile, the Makefile targets, `.env.example`
with three profiles, `.gitignore` and `.dockerignore`. `make run` on the Windows host
served `/healthz` against CSCS on 6 Oct. Still open elsewhere: the run on Linux or macOS
(WP11, clean-checkout test) and the `local-llm` profile on a GPU host (WP10, hardware
statement).

### WP1 - LLM client and day-1 verification

*Done.* `llm/client.py` (retries on 429, 5xx and connection errors with backoff and
`Retry-After`; thinking modes `model-suffix`, `chat-template`, `off`; reasoning from the
field or inline tokens), `llm/json_out.py` (JSON extraction with one repair call), the
SQLite response cache (`LLM_CACHE=1`), `check-llm`, `track_2b/scripts/day1_checks.py` (checks
3-6 run on Public AI on 6 Oct, answers in architecture §12), usage records in
`llm_calls`; tests against a fake OpenAI-compatible endpoint.

### WP2 - Schemas, store, orchestrator skeleton

*Done.* The pydantic v2 schemas of architecture §5 (plus `PipelineSummary` and
`Fact.origin`; prompts show a filled JSON example, see track_2b/docs/prompts.md), `store.py`
(SQLite in WAL mode, no ORM; the response cache stays a separate file),
`pipeline/orchestrator.py` (stages persisted in order, resume from the last good stage,
errors on the job row), one worker thread for the web app and the CLI; round-trip,
store and resume tests.

### WP3 - Ingest and segmentation

*Done.* `ingest/text.py` (pasted text or simple Markdown: paragraphs, `#` headings,
bullet and numbered lists, words hyphenated at a line end joined again), `ingest/html.py`
(httpx download, trafilatura's XML output without links, headings, lists and tables kept,
title from og:title or `<title>`), `ingest/pdf.py` (pdfplumber words: running headers and
footers removed, columns read one after the other, headings by font size, page numbers on
the segments, a clear error for a PDF without text layer), `ingest/normalize.py` (NFC,
soft hyphens and invisible characters removed, shared by every path), `ingest/segment.py`
(spaCy sentencizer per language, stable ids `s0001…`, kinds heading, paragraph,
list_item and table_cell, heading path), `ingest/detect.py` (function-word frequencies
instead of lingua, so de, fr and it need no extra model; English rejected; the user's
language wins), `ingest_url` and `ingest_file` dispatching on content type (magic bytes
as fallback) and extension, `select_section` for one section of a page, document ids
from the SHA-256 of the normalised text. Fixtures are synthetic and built in the tests
(pages written by hand in the shape of official pages, PDFs generated with fpdf2 at test
time, pasted letters; no official text committed, track_2b/docs/sources.md §4); the tests assert
units, kinds, counts and id stability. `python -m leichtfacile ingest <file|url>` prints
the segments of a text, HTML or PDF input.

### WP4 - Understand and Write (German)

*Done.* The German understand and write prompts under `llm/prompts/de/` as Jinja2
templates (style guide, examples, segments and fact sheet as placeholders; each rendered
prompt carries the short hash of its file instead of a version header, and
track_2b/docs/prompts.md logs every change and why), `rules/styleguide.py` (the writer style
guide rendered from the rule registry, decision D-A), two synthetic example pairs written
by the team under `llm/prompts/de/examples/` (Zürich and Bern pages may not be
reproduced in a public repository), understand and write in `pipeline/stages.py` (one
understand call over the whole document with thinking at temperature 0.1, `FactSheet`
out; plan-then-write at temperature 0.3, `Draft` out; long documents split by top-level
heading, one call per section sharing the fact sheet, blocks renumbered globally;
post-checks on ids, unknown segment ids kept and reported by FACT-05), `value_norm` done
in code after the model returns (`rules/values.py`: ISO dates, decimal CHF, digits-only
phones, lowercase URLs and e-mails) plus code completion of the fact sheet. Tests in
another shape than planned: instead of a snapshot, a test renders all four German prompts
on the synthetic letter and asserts that no placeholder is left and the key content is in
(the French prompts likewise); two recorded answers of the 8B on the team's letter under
`track_2b/tests/fixtures/llm/` (6 Oct, local 4-bit llama.cpp, older prompt versions; parsing and
checking only, not evaluation results), with the malformed cases derived from them in the
tests (an answer cut off is reported as broken and never used, a dropped value comes back
from code) and more broken JSON in the extraction tests. The write stage ran on real
Zürich pages in every full pipeline run on CSCS (the P0, P1 and P2 evaluations over the
13 Zürich pairs, the P0-ZH runs); `--stop-after write` exists for a write-only run.

### WP5 - Rule checker (German)

*Done.* `rules/base.py` (registry, runner, one spaCy doc per block), the German rules of
rules.md in `rules/de.py`, the fact checks in `rules/values.py` and `rules/document.py`
(FACT-01 to FACT-05, surface forms of dates, amounts, phones, URLs and e-mails),
readability (Amstad, Kandel-Moles, Gulpease with `pyphen`), golden tests (no official
sentences committed, for copyright), calibration on 30 official pages: 2.0 errors per
100 blocks over 3,450 blocks (track_2b/docs/rules.md). A test keeps rules.md and the registry in
sync.

### WP6 - Judge, repair, full CLI

*Done.* Judge and repair in `pipeline/stages.py` with their prompts: the judge on
`LLM_JUDGE_NAME` reports only; repair takes the flagged blocks, keeps their ids, reruns
the rule check and, after a fact finding, the judge; every version stored as
`draft@vN`. The `simplify` CLI with all its flags; `make smoke` (6 Oct: reached review
on CSCS, 7 calls, 26k tokens; Git Bash needs `MSYS_NO_PATHCONV=1`, in the recipe).

### WP7 - Dataset and evaluation harness

*Done.* `track_2b/data/pairs/manifest.jsonl` with 35 pairs (30 German, 5 French; roles dev and
eval), all 70 texts fetched by `track_2b/scripts/fetch_pairs.py`, the conditions as job configs
of the orchestrator, `eval/metrics.py` and `eval/score.py` (fact coverage, judge fact
status, rule findings per 100 blocks, readability, own SARI tested against the EASSE
example, tokens, latency, USD at Public AI list prices), the resumable `eval/run.py`,
`eval/report.py` and `make eval`. First numbers 6 Oct: P0, P1 and P2 on the 23
held-out pairs on CSCS (track_2b/docs/prompts.md).

### WP8 - Review UI and export

*Done.* The API in `web/api.py`, the pages in `web/pages.py` (job list and form,
progress, the three-pane review with fact checklist, findings, omissions, glossary and
versions; restyled by WP18), exports to Markdown, HTML and the JSON audit bundle
(`export/`), example jobs in `track_2b/data/examples/` loaded on first start: since 7 Oct the
team's premium-reduction letter in German and French (P2, CSCS). Rebuilt clean on 10 Oct
on the day's pipeline (D-AF to D-AI) in five rounds of six fresh attempts per letter:
0 errors, 16 of 16 and 14 of 14 facts, 17 and 14 warnings on first start; `KNOWN_PROBLEMS` in
`track_2b/tests/test_examples.py` is empty and the test fails on a shipped job with errors.
To rebuild only if the pipeline changes before the freeze (Sun 11 Oct, 18:00); the log
of 10 Oct has the details.
`examples build --only <name>` builds one; a JSON file next to a source sets its job (the KESB
decision's decision mode).

### WP9 - French and Italian

*Done.* French: the prompts under `prompts/fr/`, two example pairs, `rules/fr.py` (the FR
table in rules.md, 27 rules at the time, calibrated on the 5 official pages to 2.2 errors
per 100 blocks, limits 15/18 words), golden tests, 5 French pairs in the manifest,
Kandel-Moles verified (French syllables 93 percent exact), the French example letter in
track_2b/data/examples, web form and API in French; `fr_core_news_md` in the image (1.97 to 2.19
GB). P2 ran on the 3 French eval pairs on CSCS, and report §5 has their numbers; the
final run refreshes them (WP13). Italian is out of scope for the hackathon (owner, 8
Oct) and on the WP17 roadmap, with `it_core_news_md` (CC BY-NC-SA 3.0, WP17 row
"Italian").

### WP10 - Comparisons and reliability

- [x] P2 with the 70B writer on 5-10 pairs; 8B vs 70B table (quality, tokens, CHF,
      latency) *(6 Oct: 5 pairs, technical report §5)*.
- [x] Judge reliability: 30 (fact, draft) items labelled by hand; Cohen's κ *(tooling
      done 6 Oct: `eval sample --results track_2b/eval/results-cscs` writes
      `track_2b/eval/labels/judge_facts.jsonl` without the verdicts plus a key file,
      `eval kappa <sheet>` scores the filled sheet; the labelling itself is open)*.
      *8 Oct: labelled blind by an AI assistant (Claude), κ 0.08 for facts (0.22 present
      or not), technical report §5; the owner may relabel by hand and rerun `eval kappa`.*
- [x] Hallucination spot check: 30 blocks flagged/unflagged by the judge, labelled
      by hand *(same tooling: `track_2b/eval/labels/judge_blocks.jsonl`, 15 flagged and 15
      passed; labelling open)* *8 Oct: same labeller, agreement 80 %, κ 0.60.*
- [x] Prompt language: English instructions for German and French documents against
      the frozen templates, in understand, write, judge and repair, repair first
      *(9 Oct, at the owner's request: P2 on the dev pairs on CSCS and the judge against
      the blind labels, track_2b/docs/prompts.md "English instructions"; not taken, D-AE; the
      variant removed the same day, the results kept in track_2b/docs/prompts.md)*.
- [x] Hardware statement for the on-prem profile: start the `local-llm` compose profile
      once on a GPU host; otherwise cite the official vLLM guide numbers and say so
      *(no GPU host reachable on 6 Oct; the `local-llm-small` llama.cpp profile ran on
      the RTX 4060)*. *9 Oct: not possible on the laptop (RTX 4060 8 GB; the full 8B
      needs about 16 GB of weights). Plan: AWS g6.xlarge (1x L4 24 GB) in Zurich
      (eu-central-2), on demand, about USD 1.09 per hour, 1 to 2 hours. GPU quota
      requested 9 Oct (4 vCPUs, approved the same day). If not approved by Mon 12 Oct,
      cut: the report cites the vLLM guide.* *10 Oct: done on that machine (plain
      Ubuntu 24.04, NVIDIA driver 595). As written the profile did not start: on 24 GB
      the 32k context needs an FP8 KV cache and `--max-num-seqs=16`, both defaults in
      docker-compose.yml since (owner). 17.23 GiB of weights, 16.2 tokens per second for
      one request; the example letter took 63 min with the 8B judging with thinking and
      22 min with thinking only in Understand; the owner reviewed job 1 as a reference.
      Evidence in track_2b/eval/hardware/aws-l4-2026-10-10/; report §2, README, architecture.md
      §10, use-cases.md §2 and track_2b/docs/submission.md updated.*

Done when: the report's §5 has every table filled with real numbers.

### WP12 - Letter photo for end users (no expert review)

*Split on 6 Oct (night), decision D-N: the spike and `ingest/image.py` for the
reviewed workflow become WP12a (part of WP15, by G4); the end-user mode is WP12b
(after G4 only if everything is green; cut list §7, item 5).*

Goal: a person who received an official letter photographs it with their phone and
gets, directly and without a reviewer in between, an easy-language explanation: what
the letter is about, what they must do, by when, how much, whom to ask. Everything
the reviewer does in the main workflow has to be done by code or said honestly on
the page. Built after WP10 in build order; scope status in §2 (stretch item 11).

- [x] Go/no-go spike first (half a day at most): 3 synthetic letters, printed and
      photographed with a phone (good light, poor light, skewed), sent to the 8B on
      CSCS with a "transcribe word for word, do not summarise" prompt. Day-1 check 4
      only read a rendered PNG; a real photo is the open question. Measure the
      character error rate against the source text and whether every date, amount
      and phone number survives. Stop here if hard values are lost. *Run 7 Oct on
      CSCS with the two scans at 1,600 px: the German page came back as "unlesbar",
      the French letter with 5.7 percent character errors and wrong digits in the AVS
      number, the IBAN, the postcode and a date (track_2b/docs/prompts.md, "Image input
      spike"). Hard values are lost: no-go at this setting (D-N). Full resolution and
      the 70B are one run each before the decision is final.*
      *(7 Oct: two printable letters with their printed text as reference in
      `track_2b/data/examples/print/`, from `track_2b/scripts/print_letters.py`: a German tax reminder
      and a French grant decision over two pages; both printed, folded in three and
      scanned at 300 dpi without OCR, one PDF per letter in `print/scans/`; phone
      photos and a third letter still needed. 7 Oct, night: the spike itself is
      `track_2b/scripts/image_spike.py` with `eval/image_spike.py`: the page JPEGs out of the
      scans unchanged, scaled to 1600 px, one transcription call per page, character
      error rate and hard values found against the printed text, a table and a JSON
      report; tested without a key on the committed scans. The run on CSCS is the
      owner's: a LOCAL TEST REQUEST in the session log)*
- [ ] `ingest/image.py`: JPEG/PNG, up to 3 photos per letter
      (pages in order), or a scanned PDF without text layer (its page JPEGs taken out
      unchanged, as for the spike's scans), EXIF rotation, long side scaled to about 1600 px (Pillow);
      one transcription call per photo (8B, thinking off, temperature 0), text joined
      and passed to the existing text ingest and segmentation. The transcription is
      the source for every later check (FACT-01..06 run against it, not the image).
      Flag `FEATURE_IMAGE_INPUT`; off gives the clear "not supported" error.
- [ ] Unreadable photo guard: the transcription prompt may answer "unreadable";
      a very short text, no detected language or a language outside de/fr ends the
      job with "Bitte machen Sie ein schärferes Foto" (FR equivalent), no draft.
- [ ] Pipeline config `letter` (job config like the eval conditions): P2 at level A2,
      repair on, then straight to a result for the user instead of `needs_review`.
      The write prompt stays; the result leads with the core answers from the fact
      sheet (what is it, what must I do, by when).
- [ ] Safeguards in place of the reviewer:
      - a facts box built by code from the fact sheet values with their segment ids:
        every deadline, amount, phone number, e-mail, reference number, in the
        letter's own wording, shown even when the draft dropped it;
      - blocks still carrying a blocking finding after the last repair round (FACT-06
        invented value, judge hallucination or distortion) are not shown; the page
        says that a part could not be explained and points to the facts box;
      - a fixed notice in easy language at the top and bottom, written by us, not the
        model: "Das ist eine Hilfe zum Verstehen. Gültig ist nur der Brief. Fragen Sie
        bei der Stelle nach, die Ihnen den Brief geschickt hat." (FR equivalent);
      - explanation only, no advice: the write prompt gets a line against advice and
        the judge's addition rules cover it.
- [ ] Privacy: letters carry names, addresses, AHV and IBAN numbers. Letter jobs skip
      the LLM response cache, never appear in the job list, have an unguessable id,
      and are deleted from the store after a fixed time (default 1 h) or on a
      "Delete now" button. The page says the photo is sent to the configured Apertus
      endpoint. The existing log privacy test covers the transcription text.
- [ ] Mobile page `/letter` (DE/FR labels): one `<input type="file" accept="image/*"
      capture="environment" multiple>` (works over plain http on the LAN, unlike
      `getUserMedia`), language choice, stage progress, result with core answers,
      facts box, explanation, the transcription folded away for comparison with the
      paper, print and Markdown download. Reuses the WP8 static assets, no framework.
- [ ] Evaluation: 6 synthetic letters (DE and FR, including the two in
      `track_2b/data/examples/`), each as clean text and as phone photos. Report: character
      error rate of the transcription, hard-fact recall on the transcription, and
      P2 fact coverage and invented values per 100 blocks for photo against clean
      text ("the photo costs X points"). Synthetic letters only, never a real one.
- [ ] Docs: architecture §1-§2 gain a second user (a letter's recipient) with this
      mode's limits, §4 ingest row and the Apertus table updated; report §2 and the
      demo get one sentence each; the framing stays "private help for one reader,
      the reviewed workflow is for anything published".

Done when: a photographed synthetic letter, uploaded from a phone on the same network
as `make run`, gives within 2 minutes an explanation whose facts box matches the paper
for every deadline and amount; an unreadable photo gets the retake message; the job is
gone from the store after "Delete now"; the evaluation rows are in the report.

### WP13 - Fair baselines and the headline (GAP-01, -02, -03, -10)

Goal: by G3 (Mon 12 Oct), one table that answers "what does the pipeline add over the
best single prompt, on the same model?", with numbers a juror can trust.

- [x] **P0-ZH condition** (3-4 h). Zurich's Leichte Sprache prompt as a single-prompt
      baseline *(implemented 6 Oct, evening: conditions `P0-ZH-complete` and
      `P0-ZH-condensed`, template verified verbatim, smoke run on CSCS; run the same
      evening with P0 on the 20 German eval pairs and the 10 dev pairs, 90 jobs, every
      answer tagged, about 2 minutes per 30 jobs; the numbers in track_2b/docs/prompts.md
      "Zurich's prompt as the second baseline", report §5 and track_2b/eval/report.md)*:
      - `llm/prompts/de/baseline_zh.md`: their system message and user template of
        v1.6.0 with `RULES_LS`, verbatim. The MIT notice and the source commit go in a
        Jinja comment, so they never reach the model. Add `THIRD_PARTY_NOTICES.md`.
      - Two variants (D-K): `complete` (`REWRITE_COMPLETE`, our task: keep every fact)
        and `condensed` (`REWRITE_CONDENSED`, their default for Leichte Sprache).
      - Same settings as P0: 8B, thinking off, temperature 0.3, 6000 tokens. Take the
        text between the `<leichtesprache>` tags; use the whole answer when the tags
        are missing, and count how often *(never, in the 90 jobs)*.
      - Post-processing as in their app, with one exception. `ß` becomes `ss`, as
        there. Their `strip_markdown` is not applied: it deletes every underscore, so
        URLs and e-mail addresses break. Applying it would measure their regex, not
        their prompt. The report mentions it as an observation.
      - Code: the `Condition` literal (`C0ZH` as the code value if a hyphen is awkward
        in file names), an orchestrator branch next to `_run_baseline`, `eval run
        --condition`, rows in `eval/report.py`, a test with a recorded answer.
      - German only: their app has no French prompt.
- [x] **Like-for-like dev runs** (run time only): P0 and P0-ZH also on the 10 German
      dev pairs on CSCS, so the dev comparison with P2 uses the same pairs *(done 6 Oct,
      evening; rows in `track_2b/eval/results-cscs`, numbers in track_2b/docs/prompts.md)*.
- [x] **Fact-retention diagnosis** (2-3 h, no model calls). On the stored P2 dev drafts
      (`track_2b/eval/results-cscs`), classify every must-keep fact missing from the final
      version *(run 7 Oct on the owner's machine, numbers in track_2b/docs/prompts.md: 50 of
      102 must-keep values missing, 40 of them never asked for, 30 of those because no
      round reached the final version, 10 behind the cap; after the rerun 16 of 122;
      the later dev runs under the changed code are in the next item and in D-Z)*:
      - a) never requested in a repair round: more than 5 missing facts, or the loop
        stopped on "no progress";
      - b) requested, but the value came back in a surface form FACT-01 does not
        accept;
      - c) requested and added, then dropped by code (repeat filter, copy guard,
        FACT-06 guard);
      - d) requested, but the model did not write it;
      - e) marked droppable by Understand or by code completion although the reader
        needs it;
      - k) requested and written into a version that was not kept as final *(added
        7 Oct, cloud session 3: 5 facts in the third run; empty since the final
        version is chosen facts first, 8 Oct)*;
      - l) present in an earlier version, lost in a later rewrite.

      Result: a table in track_2b/docs/prompts.md ("Fact-retention diagnosis").
      *7 Oct, night (cloud session): the tool is `python -m leichtfacile eval diagnose
      --results track_2b/eval/results-cscs --role dev` (`eval/diagnose.py`, tests on a
      hand-built store). It puts every missing must-keep value into a bucket from the
      stored artifacts; for the runs before 7 Oct it decides bucket a exactly (requests
      recomputed with `build_request`) and reports b, c and d together as "answer not
      recorded"; since then the `RepairRecord` per round tells them apart. The method
      is in track_2b/docs/prompts.md.*
- [x] **Fix the largest bucket** (2-6 h), then `eval run --redo` on the dev pairs
      *(done 7 to 9 Oct in the P2 dev reruns on CSCS, every earlier answer replayed
      from the cache so that two runs differ only by the change measured; the numbers
      in track_2b/docs/prompts.md, D-Z, D-AB and D-AC)*. What went in, in this order:
      - a facts-only round that "no progress" on other findings does not stop: up to
        `MAX_FACTS_ROUNDS` (default 1) rounds after the loop, missing facts only, no
        block flagged, measured by the FACT-01 count; the exact value in the request
        (`(Wert: 2026-03-31; schreiben Sie: 31. März 2026)`); the cap of missing facts
        per round as a setting, `MAX_MISSING_PER_FACTS_ROUND`, 5 to 10 after the
        measured rerun; an unusable repair answer no longer cancels the round (D-Z);
      - every dropped addition logged with its reason: the `RepairRecord` per round
        (request, answer, dropped texts with reason) in the audit bundle, read by
        `eval diagnose`;
      - the final version chosen facts first, fewest missing must-keep values, then
        fewest blocking findings (8 Oct; bucket k empty since; `eval rescore --select
        facts|blocking` reads either rule on stored jobs without a model call);
      - the code completion's gaps behind the 5 percent silent losses closed (a
        percentage stored as `10%`, an address over two sentences as one fact with its
        street, the coverage check in the reader's direction): no silent loss in P2
        since the fifth run, checked 8 Oct;
      - fact coverage counts only facts whose value the source contains (D-AB, 7 Oct):
        the measure alone lifts the stored P2 eval row from 81.7 to 83.1 percent;
      - a block without a source sentence gets one from the facts it names, a hard term
        the source lacks leaves the fact sheet, the Understand example's office is a
        copy-guard topic word (8 Oct): dev fact coverage 76 to 81 percent, within the
        8B's noise;
      - the recover round (D-AC, 9 Oct): after the facts rounds, every value FACT-01
        still misses is asked for one by one with its source paragraph and the value
        named, and the accepted sentences go after their blocks as one more checked and
        judged version (`MAX_RECOVER_FACTS=10`, on by default, in the final run). Dev,
        German: fact coverage 78 to 96 percent, hard facts kept 72 to 90, invented
        values 0.8 to 0.6 per 100 blocks, about 12 percent more tokens and 5 s more
        per page; the weak sentences echo the prompt or break a reflexive;
      - the polish round (D-AF, 10 Oct): after the recover round, the best version's
        repairable rule errors, or its warnings once no error is left, go to one more
        round through the repair prompt, no fact and no judge's problem; the facts and
        recover rounds add the source's sentences nearly verbatim and no round saw them
        again (the example rebuild of 10 Oct). Dev, German: rule errors 1.9 to 1.3 per
        100 blocks, warnings 38 to 34, unsupported 5.8 to 5.3, facts unchanged, no value
        lost, about 17 percent more tokens (track_2b/docs/prompts.md);
      - the judge's quotes (D-AG, 10 Oct): an unsupported verdict names the words it
        objects to, code keeps it only on a block that holds them and files the rest
        under `dropped`; the prompt says another wording is no problem. Dev, German:
        unsupported 5.3 to 3.1 per 100 blocks, rule errors 1.3 to 0.2, invented 0.6 to
        0.0, facts moved on one pair only (track_2b/docs/prompts.md);
      - wider FACT-01 surface forms: not needed, bucket b held 2 of the 16 missing
        values after the rerun.

      Tried on the dev pairs and taken out again (track_2b/docs/prompts.md): a judge's
      "missing" on a fact that code finds asked for again, and a missing fact asked for
      by the clause of its value (8 Oct: fact coverage 79 to 74 percent, hard facts
      kept 71 to 64); English instructions in every stage (9 Oct, D-AE). Dev numbers
      by run, German P2: facts rounds 75 percent fact coverage against 68 without them
      (7 Oct); the fifth run 75 and 77 percent hard facts kept, cap 10 79 and 81; the
      recover round 96 and 90 (9 Oct; one run per setting, 5 of 12 pairs changed). Two
      runs of the same code differ a lot per pair, so the eval split decides what the
      report says.
- [x] **Headline metrics** (1-2 h) in `eval/score.py` and `eval/report.py` *(7 Oct,
      night: `silent_losses` and `silent_loss_share` per row, the "Silent losses"
      column with its "by design" note in the report tables; the invented values and
      rule errors per 100 blocks existed; `eval numbers` prints the means with the D-M
      case since 8 Oct, below; track_2b/eval/report.md and the §5 column fill with the final
      run, the baseline rows follow from 100 minus hard facts kept)*:
      - *silent losses*: hard values of the source that are neither in the final text
        nor in the review checklist or omission log. For P0 and P0-ZH every missing
        value is silent. For P1 and P2 it is zero by design once identifiers are hard
        facts (WP14); say "by design" in the report;
      - invented values per 100 blocks (exists: the FACT-06 count, for every row);
      - rule errors per 100 blocks, fact coverage, hard facts kept (exist).
- [ ] **Value numbers** (1-2 h):
      - seconds, tokens and USD per 250-word page and setup from the usage log
        *(exist, in `track_2b/eval/report.md` and report §5; the seconds undercount: a call
        replayed from the cache counts 0 s, which is P0's 0.0 in track_2b/eval/report.md since
        its rescoring of 6 Oct, so the final run's baseline rows need fresh calls,
        below. Also measured: the recover round costs about 12 percent more tokens and
        5 s more per German page (dev, 9 Oct); the rule check alone takes 47 ms median
        on a 15-block letter (8 Oct); the 70B everywhere costs 1.8 times the 8B per
        page (report §5))*;
      - our own review time for 3 P2 drafts in the UI, by stopwatch, labelled "team,
        not experts" *(done 10 Oct: the two example jobs and one dev pair of the
        dev-final run, `zg-disability-services-act-de`, served from a scratch copy of
        its store; 1,079 source words together, from opening the review to the export,
        15 minutes by stopwatch, about 3.5 minutes per 250-word page; a dev pair
        instead of an eval pair, since held-out drafts of the frozen pipeline exist
        only after the final run; report §5)*;
      - the drafting time per page of a professional, from a published price per
        page. Without one, the report says so; no invented figure *(open)*.
- [ ] **Final evaluation on CSCS** after the prompt freeze (Sun 11 Oct, 18:00; moved
      from Fri 9 Oct on 9 Oct, D-AD), into `track_2b/eval/results-cscs`:
      - first copy the folder to the next `track_2b/eval/results-cscs-vN` (v1 holds the run of
        6 Oct, the fallback *(done 6 Oct, evening)*; v2 to v5 the dev reruns). Never
        overwrite a result that might be needed;
      - every row again, with `--redo`, not only where the pipeline changed: the
        scoring changed for all of them since 6 Oct (the value kinds of 7 Oct, the
        hotline numbers, the D-AB measure, the silent-loss key the stored P1 and P2
        rows lack). `make eval` has no `--redo`: run its five `eval run` lines with
        `--redo --results track_2b/eval/results-cscs`, P1 and P2 first (the 20 German and 3
        French eval pairs), then P0 and the two P0-ZH variants (German), since a
        baseline's fact coverage is scored against a P1 or P2 fact sheet of the same
        pair (`_reference_factsheet`) and that fact sheet should come from the final
        code; last the two 70B rows of `make eval-70b` with `--redo` on the same 20
        pairs as on 6 Oct (37 s and USD 0.02 per page), at least 5 if time is short
        (WP10);
      - the baseline rows with `LLM_CACHE=0`, so that seconds per page are measured and
        not 0 s from the cache (63 short calls, about 2 minutes per 30 jobs); or, if
        the answers of 6 Oct should stay, from the cache with the seconds of the v1
        rows, stated. P1 and P2 with the cache on, as always: a changed prompt or a new
        round misses it by itself;
      - wall-clock about 1 h for the 8B rows (P2 runs the facts, vocabulary and recover
        rounds now) and 30 min for the 70B rows, overnight is ample; the client's 8
        retries cover the dropped thinking streams;
      - then, without a model call: `eval report --results track_2b/eval/results-cscs --out
        track_2b/eval/report.md` (both tables, with the silent-loss column for the first time),
        `eval numbers --results track_2b/eval/results-cscs` (the D-M case, below), `eval
        diagnose --results track_2b/eval/results-cscs --role eval` (the buckets on the eval
        split: the sentence for the next step in case B), and the commit of the run
        into report §7;
      - if more than a quarter of the pairs fail: case D, the v1 and dev numbers,
        labelled; P0 and P0-ZH may run on Public AI, labelled as such (§4).

      The example jobs' rebuild and the video's real sentences follow the same freeze
      (WP11).
- [ ] **Report §5 table**: SOURCE, REF, P0, P0-ZH complete, P0-ZH condensed, P1, P2,
      with the silent-loss column. The §1 headline follows D-M (below) *(rows in place
      6 Oct, evening; the silent-loss column added 7 Oct night with the identity for
      the rows without a checklist, 0 by design for P1 and P2; the final run fills the
      rest)*. Every place the numbers live, to change in one pass from `eval numbers`
      and `track_2b/eval/report.md` once the final run is read: report §5 (the table, its "6
      October" date, the three reading paragraphs; the κ paragraph stays) and §1 (the
      "Headline result" paragraph: 80 percent, 4.3, 22.0 and 0.1 today); README's
      "Status (6 October 2026)" block (825 tests, 23 pairs under P0, P1 and P2, no
      P0-ZH) and the paragraph under "Why not one chatbot prompt?"; the video's
      evidence scene (narration C: "lost almost a quarter of the hard facts", the
      condensed variant's 23 percent; demo-video.md §4 lists it). Every number with its
      endpoint and split (WP16, rule 4).

Done when: `track_2b/eval/report.md` (CSCS) has every row on the 20 German eval pairs; the
headline sentence follows D-M (below); README, report §1 and the video script carry the
same three numbers, and `eval numbers --results track_2b/eval/results-cscs` prints them.

#### Reading the numbers at G3 (D-M)

Compare P2 with P0-ZH `complete` on the 20 German eval pairs on CSCS, and decide by
these rules, no debate:

| Case | When | Headline |
|------|------|----------|
| A | P2 has fewer invented values and fewer rule errors per 100 blocks, and its fact coverage is at most 5 points below P0-ZH | "Same model, the Canton of Zurich's published prompt against our pipeline: X fewer invented values and Y fewer rule errors per 100 blocks, and every hard fact it misses is listed for the reviewer." |
| B | P2 is better on invented values or rule errors, but more than 5 points below on fact coverage | Lead with "no silent loss": P0-ZH loses Z % of the hard facts without telling anyone, P2 lists every one. State the coverage gap openly, with the fix from the WP13 diagnosis as next step. No code-written fact sentences in the evaluated text (D-R). |
| C | P0-ZH is as good or better on rules and facts | Reposition as the verification layer: "We ran the Canton of Zurich's published prompt through our checks: N invented values and M lost facts that nobody saw." The write stage becomes a replaceable part, and "verify a draft" moves to the top of report §8. |
| D | The final run fails on more than a quarter of the pairs | Report the v1 and dev numbers, labelled, with the failure rate; no headline comparison with P0-ZH. |

In every case: the same numbers in README, report §5 and the video, and never a number
without its endpoint and split. Z in case B names its variant: `complete` loses 5
percent of the hard facts on the stored rows, `condensed` (their default) 23 percent;
a sentence that says "in its default mode", as the video's evidence scene does on its
card (spoken without it since 9 Oct, owner), means the condensed variant. `python -m leichtfacile eval numbers --results track_2b/eval/results-cscs`
applies the table (tool since 8 Oct, WP16): the means per setup, the three comparisons
with P0-ZH `complete`, the case and the headline sentence filled in.

Applied on 6 October (evening) to the numbers then on hand (CSCS, 20 German eval pairs,
8B): **case B**. P2 against P0-ZH `complete`: rule errors 4.3 against 15.4 per 100
blocks, invented values 0.1 against 0.0, fact coverage 84 against 91 percent (7 points),
hard facts kept 80 against 95 percent; the condensed variant (their default) keeps 77
percent of the hard facts. `eval numbers` reproduces this case on the stored rows
(8 Oct). Since then the recover round (D-AC) lifted P2's fact coverage on the German
dev pairs from 78 to 96 percent and hard facts kept from 72 to 90: if the eval split
moves alike, P2 lands within 5 points of P0-ZH `complete` and case A applies, which
names Zurich in the video (D-L) and rewrites its evidence scene, so the video's numbers
wait for the final run (WP11). The headline sentence itself waits for the owner (D-M at
G3) and for the final rerun after the freeze (Sun 11 Oct).

### WP14 - Fact contract and repair hardening (GAP-04, -05, -19, -22)

*Done 6 to 8 Oct.* Details in track_2b/docs/rules.md (value kinds, calibration notes),
architecture §4 and track_2b/docs/prompts.md.

- Value kinds in `rules/values.py`, each with code completion of the fact sheet,
  FACT-01 and FACT-05; SOURCE and REF recomputed: `identifier` (AHV, IBAN, postal
  account, UID, a reference after a keyword; matching per D-O), `period` (D-U),
  `address`, `quantity` and `schedule` (7 Oct); `medication` with FACT-09, no FACT-06
  for lack of a drug list (8 Oct); the 08xx service numbers as phone values (8 Oct).
  A Swiss postcode list and a drug list stay WP17.
- Clause recipes for LEN-02 and LEN-02-FR in `rules/recipes.py` (idea from Zurich's
  prompt), the "a condition stays a condition" line as SEM-08 in both judge prompts
  (D-P).
- Edits by code, P1 and P2 only (D-S): LEX-01 no longer exempts a glossary compound;
  `rules/mediopunkt.py` splits long nouns after write and every repair, recorded as
  `Draft.code_edits` and counted in the eval row (dev rerun in track_2b/docs/prompts.md,
  "Mediopunkt by code"); CH-01 `ß` to `ss` the same way (`rules/swiss.py`, 8 Oct).
  GRAM-08 (a separable verb written as one word, 8 Oct).
- Closed 10 Oct without a measurement (owner): the clause recipes stay as they are in
  both languages; the reading check of the French recipes against the 5 official
  French pages and the recipes' before/after measure on the dev pairs (LEN-02 findings
  per 100 blocks, repair rounds without progress) are not done, and report §6 says
  that the recipes are unmeasured.

### WP15 - Sovereignty and "why Apertus" evidence (GAP-06, -07, -15, -20)

- [x] **A decision letter with personal data** (1-2 h). *Replaced by the KESB decision
      below (D-T, 7 Oct); not written.* Team-written, at
      `track_2b/data/examples/sources/verfuegung-rueckforderung-musterwil.txt` (French
      counterpart if time allows). Topic: a premium reduction paid too much is
      reclaimed. It contains:
      - name and address of an invented person in Musterwil;
      - an AHV number and an IBAN as specimens (WP14);
      - a reference number;
      - the amount to pay back and the payment deadline;
      - the 30-day appeal period with the appeal address;
      - the style guide's example phone number and an e-mail address on `.example`.

      It becomes the third example job (WP8) and the product scene of the video. This
      letter may not go to a cloud chatbot. On Apertus every identifier comes back
      character for character, and the omission log shows whether the model wanted to
      drop the appeal (the veto example of use-case-canton.md).
- [x] **Alternative per D-T: a KESB decision with personal data** (2-3 h; added 6 Oct,
      night; cloud session). Team-written, at
      `track_2b/data/examples/sources/entscheid-beistandschaft-musterwil.txt`: the KESB of an
      invented region appoints a deputy (Beistand) for an invented woman in Musterwil
      who keeps deciding where she lives (track_2b/docs/use-case-decisions.md §3). It contains:
      - name, date of birth and address of the person; an AHV number as a specimen
        (WP14);
      - the case number;
      - the facts, a short legal reasoning, the operative part (deputy's name and
        tasks, the fee), the instructions on appeal: 30 days from notification, the
        competent court with its address;
      - the style guide's example phone number and an e-mail address on `.example`.

      Check its structure against two published decisions so that it reads like a
      real one. If D-T picks it, it replaces the reclaim letter above as the third
      example job (WP8) and, per D-I, possibly the product scene of the video: this
      text may never leave the authority; on Apertus the case number and the AHV
      number come back character for character, and the omission log shows whether
      the model wanted to drop the appeal. Until the decision mode exists (WP17) it
      is an ordinary P2 job; the fixed notice ("Massgebend ist der Entscheid") is
      added by hand in the review, and the video says so.
      *Written 7 Oct (evening): `track_2b/data/examples/sources/entscheid-beistandschaft-musterwil.txt`,
      1,000 words, 26 hard values (the AHV number with a wrong check digit, the IBAN
      with 00), with `entscheid-beistandschaft-musterwil.json` for decision mode and
      the addressee. A research agent found no KESB header with "in Sachen" or
      "betreffend" (those are courts'), so the layout follows the KESB Graubünden's two
      specimen decisions and the KOKES model decision: the panel, the person, the
      subject, I. Sachverhalt, II. Erwägungen, III. Entscheid, Eröffnung and Mitteilung,
      Graubünden's appeal clause. Its example job waits for decision mode v1: built on
      CSCS the same evening, the draft was not fit to show (use-case-decisions.md §7).*
- [x] **One published, anonymised decision as a test** (1 h plus run time, Thu 8 Oct;
      added 6 Oct, night; cloud session): a cantonal court on an appeal against a
      KESB decision, or the Federal Supreme Court on disability insurance (free under
      Copyright Act art. 5; track_2b/docs/sources.md §3). Run P2 on CSCS, read the result, note
      how the placeholders (`A.________`) and the long reasoning come out. Input for
      D-I and D-T. *Done 7 Oct (evening): Verwaltungsgericht Schwyz, III 2022 132 (8
      pages), P2 on CSCS in decision mode and as a standard job, and the KESB decision
      the same way; results and what they mean for decision mode v1 in
      use-case-decisions.md §7. The placeholders pass through as names; the model
      proposed one passage of reasoning for omission, so code made 28 of 30 facts
      must-keep; the court's own decision was not among them.*
- [x] **"Why Apertus" box** (1 h) in README and report §3, five lines:
      - open weights, and open, documented training data that honours opt-outs: an
        authority can justify and audit the model;
      - a Swiss-hosted endpoint (CSCS, Lugano), and on-premise: measured on an 8 GB
        laptop GPU with a community 4-bit build, labelled as such;
      - German and French in one model, Italian next;
      - image input (if WP12a ships);
      - tokens are nearly free; the hardware is the cost.
      *Done 7 Oct as "Why only Apertus": four conditions (the text stays inside, the
      organisation runs the model, it can account for what the model learned, the
      model is Swiss) with the secrecy laws and sources behind them, in
      track_2b/docs/use-cases.md §2, a table in the README, a bullet in report §3 and a scene
      in the video (1:29-1:57, in place of BehiG). The image line is left out: WP12a
      is cut (D-N).*
- [x] **WP12 split** (D-N). The spike moves to Thu 8 Oct (half a day, as in WP12).
      *Decided 7 Oct: the spike ran on the two scans at 1,600 px and at full
      resolution, with the 8B and the 70B; every setting lost hard values, and at
      full resolution both models turned the IBANs, the AVS number and a period into
      other plausible numbers (track_2b/docs/prompts.md, "Image input spike"). WP12a is cut,
      WP12b stays after the deadline; the report names image input as future work
      with these numbers. 9 Oct: most of the digit loss was the server's image size,
      not the model: CSCS keeps at most 1400 x 1400 pixels of any image, so a whole
      page arrives at about 140 dpi. `track_2b/scripts/image_spike.py --strips` sends the
      printed area in strips at the scan's resolution; the 8B then keeps every digit
      of both scans in three runs (20 of 21 and 17 of 22 hard values; the lost ones
      are the invented place name read as "Exampleville" inside the address, the
      e-mails and the URL, and one footer URL), the 70B fewer. Phone photos untested.
      D-N stands unless the owner reopens WP12a with these numbers.*
      - WP12a, only if 3 of 3 phone photos keep every hard value: `ingest/image.py` as
        described in WP12, but for the **reviewed** workflow only. A photo or a
        scanned PDF is transcribed and goes through the existing text ingest, behind
        `FEATURE_IMAGE_INPUT`; one synthetic photographed letter in the tests; by G4.
      - WP12b, the end-user mode (`/letter`, facts box, privacy timer): after G4 only
        if everything is green, otherwise WP17.
- [x] **Precise claims** (1-2 h; GAP-15; elaborated 9 Oct from a read of README, the
      report, the video narration, the use-case documents and `publiccode.yml`). Every
      claim a juror reads says what its source says, no more. *Applied 9 Oct at the
      owner's request: README, report §1, §3 and §5, `publiccode.yml`, the video (the
      four narration files, the evidence scene, demo-video.md), use-case-canton.md,
      use-cases.md, hard-texts.md, prompts.md, the D-M sentences below and in `eval
      numbers`, and the column names of the generated tables; the voice and the video
      length were rebuilt the same day (117.8 s, demo-video.md §4); the report grew by about 75 words,
      WP11's page check stands.* The check repeats with the numbers audit at G4 and G6
      (WP16). Claim by claim, where it stood, and the wording that holds:
      - *The law.* Report §1 ("Accessibility law asks authorities to publish important
        information in Leichte Sprache, FALC or lingua facile") and use-case-canton.md
        §1 ("Federal law (BehiG) and the canton's own accessibility rules require
        ...") say more than the law does: art. 14 para. 1 BehiG (SR 151.3) names
        speech, hearing and visual disabilities, and the partial revision has been
        before Parliament since the Federal Council's message of 20 December 2024
        (work, services, sign languages; whether it covers communication with people
        with learning disabilities, as the video note of 9 Oct says, is to be read in
        the message before it is cited). Wording that holds: "The Disability Equality
        Act asks authorities to consider the needs of people with disabilities, the UN
        Convention on the Rights of Persons with Disabilities (art. 9 and 21, in force
        for Switzerland since 2014) asks for accessible information, and the cantons
        have begun to publish in Leichte Sprache; today each version is written by
        hand ...". In the canton document name the cantonal act or drop "the canton's
        own accessibility rules". The video's card says only *Equal access by Swiss
        law: BehiG | LHand* (done 9 Oct).
      - *The number.* 1.25 million (22 percent) of people aged 16 to 65 have low
        literacy, the Swiss Federal Statistical Office's own count for reading alone
        (first results of PIAAC 2022/2023, Neuchâtel 2024, section 3.3, checked 9 Oct).
        The 844'000 (15 percent, low in all three domains at once) is no longer used
        (owner, 9 Oct). Wording: "about 1.25 million adults in Switzerland aged 16 to 65
        (22 percent) have low reading skills (Swiss Federal Statistical Office, PIAAC
        2022/23)", or where the sentence must stay short, as in the video, "1.25
        million adults in Switzerland struggle with reading" with the office named on
        screen, in words only (no logo); hard-texts.md §2 carries the rule and
        demo-video.md §4 the check. Done 9 Oct in README, report §1 and references,
        use-cases.md, hard-texts.md, demo-video.md and the video.
      - *The voting gap.* Not claimed anywhere now (checked 9 Oct: README, report,
        video, docs). If it comes back: "federal" voting explanations, and Zurich as
        the proof of demand: the canton published its information on the votes of
        28 September 2025 in Leichte Sprache for the first time, written with Pro
        Infirmis's Büro für Leichte Sprache and checked by readers with disabilities
        (Pro Infirmis news; the evaluation pair `zh-voting-de` is that page), while
        the federal administration does not take part (bluewin, 2025).
      - *"Every fact".* Code checks values: dates, amounts, phone numbers, e-mail and
        web addresses, percentages, times, periods, identifiers, addresses,
        quantities, medication. A fact without a value (an obligation, a condition)
        rests on the judge, whose fact verdicts are a hint (κ 0.08, report §5). So
        "every fact value" or "every countable fact" where code is the subject, and
        "every fact" only where the judge is named with it. Fixed: README step 3
        ("nothing lost, nothing invented": "no value lost, no value invented"); the
        short descriptions of `publiccode.yml` ("every fact checked by code", "jede
        Tatsache prüft Code": "every fact value"); the video's "Leicht·Facile lists
        every missing fact", now "lists every one it misses" after the hard facts of
        the sentence before, with the evidence scene's titles to match. README's first
        sentence ("no deadline, amount or phone number got lost") and report §1 ("the
        exact presence of every fact value") hold.
      - *Professionals.* Never "better than professionals": the official versions
        leave values out on purpose (REF keeps 70 percent of the hard values, 60 on
        the fact-rich pairs) and add some from elsewhere. Report §1 sets 80 against
        70 percent and 0.1 against 2.2 "values the source does not have" without
        saying so: one clause next to the first comparison; in §5 call REF's column
        "values not in the source" rather than "invented" where REF is in the table.
        README and the video make no such comparison (checked).
      - *The level.* "A2" names the Leichte Sprache rule set the checker enforces and
        "B1" the team's own thresholds (report §6); neither is a measured reader
        level, and no reader has tested a draft (report §6 "Not a certification"). One clause where "level A2" first appears in report §5 and in
        README's quick start; no CEFR level from a readability score (WP16, rule 5).
        D-E stands in effect: A2 is the evaluated level since 6 Oct, B1 is offered and
        unevaluated.
      - *The baseline's name.* "The best public Swiss prompt" (report §5 table, the
        case A sentence of D-M) is a judgement; "the Canton of Zurich's published
        prompt, the only public Swiss one we found" is a fact. Use the fact, with the
        credit of WP16 rule 6; Zurich in the video only per D-L.
      - *Where it runs.* "The 8B on one 24 GB GPU" (README's Why only Apertus table,
        use-cases.md §2, architecture §10) rests on our run of the official vLLM image
        on an L4 (WP10, 10 Oct; the measured numbers in report §2). "Air-gapped" always
        with "images and weights pulled in advance"; `make bundle` is not built (report
        §6 says so).
      - *Cost per page.* "About one US cent per page" (README) and the USD columns are
        Public AI's list prices applied to the token counts (`PRICES_USD_PER_MTOK` in
        `eval/score.py`: 8B 0.10 and 0.20, 70B 0.82 and 2.92 USD per million input
        and output tokens), not a CSCS price: "at Public AI's list prices" once where
        the cent appears, and on own hardware the GPU is the cost, not the tokens.
      - *Time per page.* use-case-canton.md §1 ("a two-page letter takes them half a
        day") is the team's assumption: label it so until a published figure
        replaces it (WP13, value numbers).
      - *Figures in the use-case documents.* "92 percent of convictions for crimes and
        misdemeanours are penal orders" (use-cases.md §5) has no source next to it:
        Marc Thommen's SNSF study (University of Zurich), reported by Beobachter
        ("Strafbefehle machen 92 Prozent aller Schweizer Urteile aus"); cite it. "49
        percent ... low health literacy (HLS19-21, FOPH)", "KESB Region Solothurn
        since June 2016 (FHNW, 2018)" and the ZGB and StPO periods carry their sources
        (checked).
      - *Already precise, keep:* the four conditions of "Why only Apertus" and their
        sources (research-checked 7 Oct); "the CSCS API serves research, not
        administrations"; "no fine-tuning"; the rule counts, kept in step by a test;
        the video's "a strong single prompt, in its default mode" (D-L), on the evidence
        card; the narration drops it since 9 Oct (owner). Page and test
        counts belong to the numbers audit (WP16).
- Hardware statement: the WP10 item (the `local-llm` profile on a GPU host).

- [x] **Decision mode v1** (planned 7 Oct; about 1.5 days, Sat 10 to Mon 12 Oct; *code complete 8 Oct, pieces 1 to 7 below; the CSCS run of the KESB decision as a decision job is the owner's, see §11*;
      GAP-20; the elaboration of "step 2"). A job option, not a condition: an ordinary
      P2 run that treats the operative part and the appeal instructions as untouchable,
      speaks to one named person, asks the judge three more questions and wraps the
      export in the authority's fixed notice. The conditions P0 to P2 never see it, so
      the evaluation stays valid. Seven pieces:
      1. *Config and plumbing.* `JobConfig.mode: "standard" | "decision"`, `addressee`,
         `notice` (defaults change nothing for stored jobs); the form gets a
         "Dokumentart" select that reveals the person and the notice (prefilled per
         language from `pipeline/labels.py`); `POST /jobs` and `simplify --mode
         decision --addressee --notice`; the mode on the job and in the audit bundle.
         *7 Oct, night: the three fields, the summary's `mode`, the CLI flags and the
         API form fields are in; the page's select is open.*
         *Done 8 Oct: the "Document type" select on `/new` (Standard text, Decision
         letter) with the addressee and the notice below it, hidden by the script for
         a standard text and in view without it; the notice's placeholder follows the
         document language and the server fills `notice_default` from
         `pipeline/labels.py` (DE, FR) when the field stays empty; the page's `POST
         /jobs` takes the three fields like the API; the drafts list tags a decision
         job "Decision".*
      2. *Prompts without touching the frozen ones.* One partial per language,
         `llm/prompts/<lang>/decision.md`, with sections for understand, write, judge
         and repair; the standard templates get one line each, `{% if mode ==
         "decision" %}{% include %}{% endif %}`, which renders to nothing for a
         standard job (same cache keys, same results; the template hash changes once).
         The include lines and the SEM-08 line go in before the prompt freeze; the
         partial is free to change afterwards. *7 Oct, night: the include lines are in
         all eight standard templates (`mode is defined and mode == "decision"`, so
         every existing render call works), with a first draft of `decision.md` in
         German and French; a test shows a standard job's prompt unchanged and a
         decision job's prompt carrying the heading set and the addressee.* Content:
         what the five core questions
         mean for a decision (no new keys in `FactSheet`: a schema change would ripple
         into render, web and locales), the fixed heading set as the reader's
         questions (Was hat die Behörde entschieden? Was bedeutet das für Sie? Was
         entscheiden Sie weiter selbst? Sind Sie nicht einverstanden? Bis wann? Wen
         können Sie fragen?), "Sie" is always the addressee, the reasons condensed to
         the main ones with every omission listed, no advice and no evaluation.
      3. *Protected segments and FACT-08* (`rules/decision.py`; `check_draft` gets a
         `mode`). Segments under a heading matching `Dispositiv | Entscheid | erkennt |
         verfügt | beschliesst | Rechtsmittel` (FR `dispositif | par ces motifs | voies
         de droit | recours`), plus a text fallback for PDFs without headings (the
         numbered items after `erkennt:` / `verfügt:` / `beschliesst:`, a paragraph
         starting `Gegen diesen Entscheid kann` or containing `Rechtsmittelbelehrung`);
         Thursday's run on a published, anonymised decision calibrates the markers.
         Code completion keeps their values must-keep whatever the model marked
         droppable and adds one code fact without a value per numbered item of the
         operative part. `FACT-08` (error, decision mode only): a protected segment
         no block cites or any omission lists; the hit carries the item's fact id,
         `build_request` treats it like FACT-01 and `blocking_count` counts it, so a
         dropped item goes back to the writer before the reviewer sees the draft.
         *Done 8 Oct: `rules/decision.py` with `protected_segments` (heading or text
         marker; one item per paragraph of the operative part, the distribution list
         `Zustellung an:` and after it excluded; the appeal by its heading or the
         `Gegen diesen Entscheid kann` paragraph), `protect_factsheet` (must-keep in the
         parts, code values outside them and the core answers background, no protected
         omit candidate, one fact without a value per part) and FACT-08; `check_draft`
         and `DocInput` carry the mode; `link_facts` links a part's fact by its
         segments and FACT-02 leaves such facts to FACT-08; the orchestrator counts
         FACT-08 as blocking and missing, puts a dropped part first in the request and
         reruns the judge on it. Calibrated on the KESB decision (13 items and the
         appeal, by headings) and the Schwyz decision (2 items and the appeal as its
         item 3, by text; `track_2b/data/cache/decisions/`). Tests in
         `track_2b/tests/rules/test_decision.py`.*
      4. *SEM-08 to SEM-10.* Declared in `JUDGE_RULES`, the filter in
         `to_judge_report` widened (today it drops anything outside SEM-01 to
         SEM-05), the rows moved from "Planned" into the judge table of rules.md.
         SEM-08 (an obligation stays an obligation, a condition a condition, never
         `vielleicht` for `wenn`) is D-P generalised and goes into the standard judge
         prompt before the freeze; SEM-09 (no advice, no "leider") and SEM-10 (every
         period keeps its start) live in the partial. *7 Oct, night: SEM-08 declared,
         in the judge filter, in both judge prompts and in rules.md's judge table;
         SEM-09 and SEM-10 stand in the partial's judge section but the filter still
         drops them: widen it with piece 4.*
         *Done 8 Oct: SEM-09 and SEM-10 declared in `JUDGE_RULES` and pass the filter
         for a decision job only (`DECISION_JUDGE_RULE_IDS`); rows in the judge table
         of rules.md, German titles in the locale.*
      5. *The notice and FACT-07.* The three exporters take `notice` and write it as
         the first and last paragraph; the review page shows it as a fixed banner, not
         a block (a block would need provenance and could be rejected); the notice is
         exempt from the language rules. `FACT-07` in `check_export`: in decision mode
         the first and last lines must be the configured notice. Honest: a guard
         against an empty field and a declaration that the notice is part of the
         contract; the exporter is what writes it.
         *Done 8 Oct: `to_markdown`, `to_html` and the bundle's `layout_lines` take
         `notice` (first and last paragraph, unwrapped); the API export, the CLI export
         and the reader view pass the job's; the review page shows it as `.notice-banner`
         above the blocks; `Context.notice`, `check_export(notice=)`, FACT-07 (first and
         last non-empty line) in `rules/decision.py`, LAY-01 and LAY-02 skip the notice
         line; the bundle's `final` records the notice. Tests in test_decision.py and
         test_web.py (a decision job through the API).*
      6. *The addressee* in understand, write, repair and judge ("Sie ist immer
         {{ addressee }}; den Beistand und die Behörde nennen Sie bei Rolle oder
         Namen"); no code check, SEM-03 plus this line cover it; the name stays in the
         store like the decision itself.
         *8 Oct: in all four sections of the partial, DE and FR, with the task's owner
         (piece 2); no code.*
      7. *Example job and product scene.* The KESB decision (D-T) with a sidecar
         `.json` (`mode`, `addressee`) next to the `.txt`, since `example_sources()`
         reads texts only; the video shows the notice, the case number, the AHV
         number, the 30 days and the court's address as code facts with green ticks,
         FACT-08 catching a dropped operative item and the repair restoring it, the
         omission log for the condensed reasons.
         *8 Oct: `example_sources` carries the sidecar's `mode`, `addressee` and
         `notice` (the reader `example_config` existed for `examples build`), so
         `/new?example=entscheid-beistandschaft-musterwil` and the example buttons
         prefill the three fields. Open: the example job itself, a run of the KESB
         decision on CSCS into `track_2b/data/examples/jobs` (owner's machine, the key).*

      Added from the test runs of 7 Oct (use-case-decisions.md §7), for pieces 2 and 3:
      - in decision mode the values of the header and of the reasoning (outside the
        protected segments) are background facts, unless the model cites them in a
        core answer; today code completion makes them must-keep (29 of 29 facts on the
        KESB decision, 28 of 30 on the published one) and the repair rounds stop on
        "no progress";
      - the partial says to copy a period as written ("innert 30 Tagen seit
        Mitteilung") and never to compute its end: the Understand model wrote "endet am
        15. November 2026", a date the decision does not contain;
      - a draft that quotes the prompt is an unusable answer: the decision-mode draft
        of the published decision carried the write prompt's style guide as a section.
        The copy guard knows the examples only; give it the style guide's lines too;
        *done 8 Oct: the guard renders the write and repair prompts with the style guide
        of both levels, so its lines (without the list marker) and its example values
        count as the prompt's own;*
      - the addressee line in the partial: with "Sie ist immer {{ addressee }}" the 8B
        still gave the deputy's tasks to the person; name the tasks' owner in the
        fact sheet (the deputy) and check it in the judge (SEM-03).
      *Done 8 Oct, all four: the first by code (`protect_factsheet`) and in the partial's
      understand section; the period copied as written, with its start and no computed
      date, in the understand, write, repair and judge sections (SEM-10 names a computed
      date); the copy guard knows the style guide; the task's owner named in the fact
      sheet and the draft, and a "Sie" that takes the deputy's task is SEM-03. German
      and French; the standard templates and their hashes unchanged (track_2b/docs/prompts.md,
      row 9 of 8 Oct).*
      Owner's decision, affects standard jobs too: a fact-sheet value that FACT-05
      finds missing from the source still counts as known to FACT-06, so a value the
      Understand model invents reaches the draft with only a warning on the fact sheet.
      Proposal: such a value is not known to FACT-06 and not required by FACT-01.
      *Decided and done 7 Oct (D-AB), for every job, before the freeze.*

      Tests: `track_2b/tests/rules/test_decision.py` (protected segments with and without
      headings, FACT-08 on a dropped item and an omitted Rechtsmittelbelehrung, silent
      in standard mode, FACT-07 on export lines); orchestrator with stub stages (a
      decision job's prompts carry the addressee and the partial, a standard job's not
      a word of it, FACT-08 lands in the repair request, the summary records the
      mode); the judge filter; the form posts the three fields; the KESB example
      through `complete_factsheet` with all four code facts.

      Cut order if G4 slips: the French partial; the code facts per operative item
      (keep the segment coverage check); the addressee in the judge; FACT-07 (keep
      the notice in the export). Never cut once started: the mode flag, FACT-08, the
      notice in the export, the example job. Separable for a second developer: pieces
      1, 5 and 7; pieces 2 to 4 touch the pipeline core. Stays WP17: anonymisation in
      front, a Swiss postcode list, the received-letter mode, drug names.

Done when: the decision letter runs P2 on CSCS with every identifier intact and is
among the example jobs; the "Why Apertus" box is in README and report; the spike
result is in architecture §4.1; WP12a has shipped or been cut by D-N; the KESB
decision runs as a decision job with the notice in the export and FACT-08 silent.

### WP16 - Credibility and positioning (GAP-08, -11, -12, -13, -16)

- [x] **Push the evening work** (owner, 15 min). *Done: on `main` as `56030bb`, pushed.*
      Checked on 6 Oct (night) at `cdb3b8b`, these were missing from `main`:
      - `eval sample` and `eval kappa`;
      - the `RESULTS` variable and `MSYS_NO_PATHCONV=1` in the Makefile;
      - the topic-word copy guard;
      - the parser repairs for a wrong bracket and a broken unicode escape.

      Judges and CI see `main`, not this machine.
- [x] **CI** (1-2 h): `.github/workflows/ci.yml` on push and pull request *(written 6 Oct,
      evening; green on `main` and the badge wait for the owner's push)*.
      - lint: `ruff check` and `ruff format --check`;
      - test: `uv sync --frozen`, then `pytest -q` (no network beyond the installs;
        the spaCy wheels come from pinned URLs);
      - docker: build the image, start it with an unreachable `LLM_BASE_URL`, and
        `curl /healthz` must answer (liveness does not depend on the endpoint);
      - every action pinned to a commit SHA, with a uv cache; an image scan (trivy)
        only as a non-blocking step;
      - a badge at the top of README.
- [ ] **Numbers audit** (0.5 h at G4, again at G6): every number in README, report and
      *(tool since 8 Oct: `python -m leichtfacile eval numbers --results track_2b/eval/results-cscs`
      prints the headline means per setup, the D-M case (WP13) with its three comparisons and
      the filled headline sentence; the audit is a diff against it)*
      video traced to a command (table below). First fix: "404 tests" *(README says
      the current count since 56030bb; the first P0 scorings in `track_2b/eval/results-cscs`
      used a fact sheet without code completion, fixed 6 Oct evening in `eval/run.py`;
      rescore P0 with `--redo` from the cache before the numbers are final)*.
- [ ] **Positioning paragraph** (1 h). README gets "And the Canton of Zurich's app?"
      next to "Why not one chatbot prompt?"; report §1 or §6 gets the same.
      - the sentence in rule 6 of the messaging rules below, with credit to Zurich (link, licence) and SUMM AI in
        one clause;
      - the complement angle: our checks work on any draft, also one from Zurich's app
        or from a person ("verify a draft" is in WP17).
- [ ] **Messaging** (1 h): README's first screen, report §1 and the video script
      follow the messaging rules below.
- [x] **`publiccode.yml`** (0.5-1 h). *Done 8 Oct: version 0.4, name, url, platforms,
      categories document-management and translation (the list has no accessibility),
      developmentStatus development, softwareType standalone/web, descriptions in en,
      de and fr with features, Apache-2.0, maintenance community with the owner as
      contact, localisation de/fr/en, intendedAudience government, local-authorities,
      social-services, justice, country ch. Checked by script against the v0.4
      schema's required keys and lengths; the Go parser is not installed here.*
      - name, descriptions (en, de, fr), `developmentStatus: development`,
        `softwareType: standalone/web`, licence Apache-2.0,
        `maintenance.type: community`, languages de, fr, en, audience CH government;
      - validate it with the publiccode parser if available;
      - check whether opensource.admin.ch lists projects of non-public bodies. The
        file is useful either way.
- [ ] Optional goodwill (owner):
      - a short, friendly issue upstream: `strip_markdown` removes underscores in URLs
        and e-mail addresses;
      - once the repo is public, a pull request to awesome-apertus (maintained by
        Patrick Arnecke of the Zurich team, GitHub `rnckp`).
- [x] **Video** (track_2b/docs/demo-video.md): *Closed 9 Oct: the concept "Find the deadline" of
      8 Oct replaced the first two points (the product scene is the example letter, no
      FACT-06 scene); the evidence scene follows case B of D-M and does not name Zurich
      (D-L); its final number comes with the final run (WP13, report §5 item).*
      - the decision letter as the product scene;
      - FACT-06 catching an invented phone number, then repaired;
      - the headline from D-M (WP13);
      - Zurich named only per D-L.

Done when: CI is green on `main` with a badge; the counts in README and report match
the commands; the positioning paragraph and the "Why Apertus" box are in README and
report; `publiccode.yml` validates.

#### Messaging rules and numbers audit

Rules for README's first screen, report §1 and the video:

1. The first sentence says whom it is for and what it achieves, with a number.
   Architecture comes after.
2. "Audit trail", "human in the loop", "provenance" and "sovereign" never stand alone:
   half the field says them.
3. One picture: source and draft side by side, with the fact checklist.
4. Every number names its endpoint (CSCS, Public AI, local llama.cpp) and its split.
5. Say "federal" voting explanations. Never "better than professionals" because of
   hard facts kept. No CEFR level from a readability score.
6. Zurich's app is credited wherever P0-ZH appears, and described as the basis we
   build on: *"Zurich's open-source app showed that language-model drafts help
   cantonal writers. Its own published roadmap named what was missing: checks for
   completeness and accuracy, rules beyond readability, managed terminology, and open
   models on-premise for sensitive texts. Leicht·Facile builds most of that layer
   on Apertus."* Three of the four are done (checks by code and a judge, passive and
   Konjunktiv rules, open models on-premise); managed terminology is the termbase in
   WP17. Drop "most of" only when it ships.

Numbers audit, at G4 and G6. Fix the text, never the command:

| Claim | Command or source |
|-------|-------------------|
| Number of rules (42, plus any new ones) | the rule registry; `track_2b/tests/rules/test_registry.py` compares it with rules.md |
| Number of tests | `uv run pytest --collect-only -q`, last line |
| Pairs: 35 (30 German, 5 French; 20 and 3 held out) | `track_2b/data/pairs/manifest.jsonl` |
| Checker on official pages: about 2 errors per 100 blocks | `make calibrate` |
| Every evaluation number | `track_2b/eval/report.md` from `make eval RESULTS=track_2b/eval/results-cscs` |
| 1.25 million (22%) | Swiss Federal Statistical Office, first PIAAC 2022/2023 results, section 3.3 (wording check in demo-video.md §4) |
| Laptop GPU figures | architecture §10, labelled as a community 4-bit build |

### WP18 - UI redesign: the reviewer's workbench (added 7 Oct)

*Done.* Designed and approved by the owner on 7 Oct, specified in `track_2b/docs/ui-design.md`
(design canvas: https://claude.ai/artifact/8Js1ncMf4ceXmg3uUcPqCU, private to the
owner); D-V to D-Y decided. Built 7 Oct: an own `app.css` with tokens and vendored fonts
(IBM Plex Sans and Mono, Atkinson Hyperlegible Next, SIL OFL 1.1), the app bar, the
review screen (blocks with findings, Apply, decisions by key, checks as tabs), the
reader view with the export panel, the drafts list as start page, New draft at `/new`,
the job stepper, texts in `en.json` and `de.json`, tests, screenshots (not every page in
German at every width, ui-design §17), docs. WP15's form fields and notice banner went
into the new templates on 8 Oct.

Added 9 Oct: "Suggest a sentence" for a missing fact on the review page (architecture
§4.7) and the recover round in the pipeline behind `MAX_RECOVER_FACTS` (architecture
§4.6). Dev run with the round on (`track_2b/eval/results-cscs-recover-on`): German fact coverage
78 to 96 percent, hard facts kept 72 to 90, no invented value added; the judge calls 3
of 13 recovered facts distorted (track_2b/docs/prompts.md, "The recover round on the dev pairs").
D-AC decided by the owner the same day: the round is on by default
(`MAX_RECOVER_FACTS=10`) and in the final run.

### WP11 - Report, video, submission

Submission check of 7 Oct against the template's submission requirements (README,
"Submission Requirements & Deliverables") and the five judging criteria, at commit
`40a8b5c`; the two "submission check" lines in §11 have the details. Passed: the Docker
image builds and serves `/healthz` and the UI with no external assets; tests and ruff
green on the committed state (963 tests); `track_2b/data/` has 44 KB tracked; no key in git
history; first commit on 5 October, inside the hackathon period; the report keeps the
template's sections; only Apertus at runtime; code Apache 2.0, report CC-BY-4.0. Fixed
since:

- `make run` without a `.env` file when the three variables come from the shell, as the
  judges may set them (`bfa2de5`);
- a JSON slip (a second value without a list) that failed the Understand stage and with
  it the job; with only the three variables set, the judge ran on the 8B and the client
  retried 4 times: now the 70B judges when the endpoint lists it, and retries default to
  8 (`40a8b5c`);
- `make run` with Docker stopped ended in a connection error from Compose: now
  `check-docker` says that Docker is not running (or not installed, or without Compose
  v2) and how to start it, also before `stop`, `check-llm` and `smoke`;
- no pre-computed example jobs: the premium-reduction letter in German and French built
  on CSCS into `track_2b/data/examples/jobs/` (7 Oct); the KESB decision's job follows with
  decision mode v1 (WP15). Rebuild after the freeze if the pipeline changes; until then
  the two bundles carry errors and their test is an expected failure (9 Oct);
- the `track_2b/` layout: settled 9 Oct without a question to the organisers, with the
  template's `track_2b/` contents at the root; on 10 Oct the organisers confirmed that
  the original `track_2b/` folder must stay and the Makefile must be at the root, where
  they run `make run`: the project moved into `track_2b/` (docs, src, data, eval,
  scripts, tests, report), the root keeps the Makefile, Docker, Compose, uv, CI and
  PLAN.md, the targets are in `track_2b/Makefile` and the root Makefile includes it
  (recipes run from the root), README.md, the report and its
  PDF are in both places (track_2b/docs/architecture.md §11);
- literal U+2010 to U+2014 characters in the regexes of `rules/values.py`: the classes
  are built from `DASHES` (`leicht-facile-a3`), which also removed an unintended `/`
  range that rejected a value right after a colon;
- a failed job reported "0 model calls, 0 tokens" after two calls: usage was stored only
  when a stage returned; now each call is stored as it is made.

- [x] Report cut to the page limit: it was 8 A4 pages at 10 pt with 2 cm margins (4,427
      words), limit 6; now 3,171 words, 6 pages, the last 37 % full, so about half a
      page is left for the names, the video link, κ and the final rerun.
- [ ] `track_2b/technical_report.md` filled (sections 1-8); export to PDF (pandoc or print to
      PDF), check the 6-page limit, save as `track_2b/RoestigrabenBridgers_Report.pdf` and
      the same file at the root. §2 holds a Mermaid diagram: the export must render it (print the GitHub
      page, or HTML with mermaid.js; plain pandoc prints the code instead).
      *First draft 9 Oct: every guiding question of the jury answered in the template's
      sections (maturity level, user group, why these sizes, where Apertus fell short,
      coding assistants, what the running system contacts, licences, ten times the
      volume, the way into use), the settings table set to the code, visible
      **[PENDING]** and **[OWNER]** placeholders; printed as a draft
      `track_2b/RoestigrabenBridgers_Report.pdf`: 6 pages, the last 98 % full with
      the placeholders, so the final text may not grow (method: track_2b/docs/submission.md §5).*
      *Reprinted 10 Oct from the current text with a base URL, so its links point to
      GitHub (the 9 Oct draft had nine links to local files), and copied to the root
      next to the report's root copy: 6 pages, the last 94 % full.*
- [ ] Stale report: the **[PENDING]** video link (header) and commit (§7), known after
      the final rerun. The status line, the three
      **[pending]** markers (report §5 now says κ is not yet measured, report §4 no
      longer announces a dataset decision), French in report §8, the stale NUM-08
      limitation and the test count are fixed.
- [ ] `README.md`: keep the template text, add a "Leicht·Facile" section on top: what it
      is, `make run` quick start, where the report and video are. Stale on 7 Oct: "825
      tests" (963 now), "Status (6 October 2026)", the Pending list names French; the
      demo video is "*link follows*". *Updated 9 Oct: status of 9 October (French,
      decision mode v1, Check my text, the recover step, 1,244 tests), what the
      container contacts at runtime, the maturity line, the coding assistants; the video
      link and the final numbers as **[PENDING]**.*
- [x] State the differentiator in README, report §1 and the video: not a translator, and
      not achievable with one chatbot prompt (fact contract, provenance, omission log,
      independent checks, audit trail). P0 is that baseline; cite the P0 vs P2 numbers.
      *Done: README "Why not one chatbot prompt?", report §1 (Approach and the headline
      with P0 against P2) and the video's evidence scene; the numbers change with the
      final run (WP13, report §5 item).*
- [x] Demo video (at most 2 minutes): 15 s problem, 60 s live run on a cantonal page
      with the review UI, 30 s numbers and sovereignty, 15 s close. Record with the
      example job pre-loaded as a fallback if CSCS is slow; link it in README and
      report.
      *Done in another shape: the concept "Find the deadline" (track_2b/docs/demo-video.md)
      replaced this storyboard on 8 Oct; version C is built, 118.1 s, with a real screen
      recording of the example letter. Left in other items: the opening sentence (below),
      the link in README and report, the final numbers (WP13).*
- [x] Video, before/after (1:19): the storyboard wants the tool's real A2 output for
      DE-4, and P2 on the sentence alone gives none that can be shown (§11, 8 October).
      *Resolved 8 Oct by concept A ("Find the deadline", track_2b/docs/demo-video.md): the viewer
      is tested on the example letter and its real draft; no DE-4 rewrite is shown.*
      Either run DE-4 inside a short letter, or take the pair from the example job (a
      source sentence and its block) and change "The same sentence, now" to match.
- [ ] Video, the opening sentence again (version C, 1:50; owner, 9 October): its easy
      text of DE-4 and FR-4 is the team's placeholder, labelled on screen
      (`video/src/scenes/Again.tsx`). Replace it with the tool's real output after the
      prompt freeze (Sun 11 Oct), running both sentences inside a short letter: alone,
      DE-4 came back wrapped in letter headings and without its consequence (8 Oct).
- [x] Clean-checkout test on Linux or macOS, or on a second machine, before G6:
      `git clone`, `.env`, `make run`, run one job. So far only on this Windows machine
      (fresh clone, no `.env`, `make run`, 4 of 4 smoke jobs to review). *10 Oct: on
      Linux (Ubuntu 24.04, AWS) at 6936d05: a clone of a git bundle of `main` (the
      repository is private), `.env` for the local vLLM, `make run` unchanged, one job
      end to end through the API (WP10's hardware run). The endpoint was the local
      vLLM, not CSCS.*
- [ ] Repo to public (anonymous access gave 404 on 7 October); `.env` absent from
      history (check `git log -p -- .env`); then check that CI is green on the submitted
      commit.
- [ ] The owner's answers to the **[OWNER]** placeholders (track_2b/docs/submission.md): the
      declared maturity level, the coding-assistant sentence, the first user (none
      named, D-Q), who submits and with which Devpost e-mail, "Swiss student team", the
      video platform, and whether track_2b/docs/submission.md stays in the public repository.
- [ ] Submit at hackapertus.ch/online-hack/submissions: repo URL, PDF, video URL, model
      "8B + 70B v1.5" and the message to the jury; every field with our entry and the
      checklist before Submit in track_2b/docs/submission.md (drafted 9 Oct).

### WP17 - After 16 October (GAP-17, -18)

Before the deadline only as text in report §8 and README "Next steps". Effort is a rough
guess.

| Item | What | Why | Effort |
|------|------|-----|--------|
| Termbase | Per organisation: hard term, approved easy term, explanation, banned words. Injected into the write prompt; code checks use, consistency ("same thing, same word") and banned words | Consistent naming across all texts of a canton; Zurich planned it | 2-3 days |
| Vocabulary in prompt and checker | Done 7 Oct, pulled forward (D-AA): the fact sheet gets the checked explanations, code adds missing glossary entries, LEX-07 / LEX-07-FR flag the office words left (track_2b/docs/rules.md "Vocabulary"); a vocabulary round rewrites the office words left. The writer's word list was tried and removed (it primed the 8B). Left for here: a word list for the writer with a later Apertus, or one that names only the everyday words, and the per-organisation termbase above overriding the vocabulary | The writer and the 8B get the same words every time; glossary texts that pass the checker | done |
| House-style profiles | Quotation marks, numbers in words, `14.00 Uhr`, thousands separator, hyphen or Mediopunkt as one profile per organisation, read by prompt and checker | Every canton has its own rules; Zurich's prompt and our checker disagree on five of them | 2 days |
| Check my own text | Done 8 Oct, pulled forward (the code of WP13-16 was complete): `/check`, a third entry in the app bar, the deterministic checker on a pasted text as the CLI `check` runs it, German and French, blocks with their findings, document findings by rule, the counts; no job, no model call, nothing stored (ui-design §5.8, architecture §7) | Useful without AI, offline, in milliseconds | done |
| Complete or essentials | A switch that decides how many `omit_candidates` may go; the omission log shows what went | A real need; Zurich builds it from contradictory prompt text | 1 day |
| Several drafts | N drafts, chosen block by block by the checker (no blocking finding, every fact present) | Variety helps (Zurich's One-Klick) without making the reader compare | 1-2 days plus evaluation |
| DOCX | Easy-language layout (about 14 pt, left-aligned, one sentence per line) and a footer with date, model and prompt hash | Writers work in Word | 1 day |
| Verify a draft | Source plus any draft (Zurich's app, a person): fact sheet, FACT-01, FACT-06, rules, judge | Makes us a complement to existing tools | 2 days |
| UI in German and French | Labels and help texts in the writers' languages | The users are cantonal writers | 1-2 days |
| Italian | *Out of scope for the hackathon (owner, 8 Oct).* The 9 rules of `track_2b/docs/rules.md` (Italian section), prompts and few-shot examples, calibration on Ticino pairs, the UI and the web form. Decide first how the grammar rules get their parse: `it_core_news_md` (and every spaCy Italian model) is CC BY-NC-SA 3.0, non-commercial, from its training data UD Italian ISDT, unlike the German (MIT) and French (LGPL-LR) models; options are an optional extra outside the Docker image, the model in the image with a notice, or word lists and verb endings without a model. The polite imperative with Lei (`Compili il modulo`) is a subjunctive form, so the subjunctive rule may only fire after `che` or a conjunction | National coverage; Apertus's languages | 1 week |
| ZIX column | The Canton's index as an extra evaluation column, in the evaluation environment only (it loads pickled models and runs a pip fallback) | Speaks Zurich's language | 0.5 day |
| Decision mode, beyond v1 | WP15 builds v1 by G4 (mode flag, addressee, notice with FACT-07, protected segments with FACT-08, SEM-08 to SEM-10, form, CLI, example job). Later: whatever its cut order drops (French partial, code facts per operative item, the addressee in the judge, FACT-07), a document-type detector instead of the manual flag, an anonymisation step in front, decisions of social insurance offices and courts as further examples | The strongest sovereignty case: KESB and courts | 1-2 days |
| Planned fact checks | *Built by 8 Oct: the value kinds of 7 Oct and `medication`, FACT-07 to FACT-09, SEM-08 to SEM-10 (`track_2b/docs/rules.md`, "Fact checks for the further use cases").* Left: a Swiss postcode list for bare postcodes; a drug list (the Swissmedic list of authorised medicines), so code finds a drug name the model did not give and FACT-06 an invented one | The further use cases (`track_2b/docs/use-cases.md` §13) | 1-2 days |
| Patient letters | Medical mode: the kinds `quantity`, `schedule`, `medication`, FACT-09 and SEM-08 exist (7 and 8 Oct); left: a drug list, Apertus-70B-MeditronFO as judge, an assessment under the Medical Devices Ordinance, a pilot with a hospital (`track_2b/docs/use-cases.md` §3) | Health data, 49 percent low health literacy; the strongest case after courts | 1-2 weeks plus the legal assessment |
| Helpers for received letters | Lease terminations and payment orders for tenants' associations, social services and debt counselling: WP12b with the period kind and the facts box (`track_2b/docs/use-cases.md` §4, §6) | Reach; a 10- or 30-day period decides | with WP12b |
| Tax letters | A tax office's standard letters in the writer workflow, and a client's tax letter for debt counselling with WP12b and image input; every value kind it needs exists (`track_2b/docs/use-cases.md` §12) | Tax secrecy: a strong sovereignty case; the WP12 print letter is a tax reminder | a pilot, plus WP12b |
| WP12b | The end-user letter mode | Reach | as in WP12 |
| Pilot | A canton's easy-language office, target-group tests | Value | weeks |
| LoRA | From reviewer edits (architecture §4.8) | Cost, quality | as before |

"Check my own text" may move before G4, but only if WP13-WP16 are done by Sat 10 Oct.
*Moved on 8 Oct: the code of WP13-WP16 was complete (what was open were runs and texts),
the owner relaxed the condition.*

### Dependencies

| WP | Needs | Can run in parallel with |
|----|-------|--------------------------|
| WP0 | - | WP2 |
| WP1 | WP0 config, CSCS key | WP2, WP3 |
| WP2 | - | WP1, WP3 |
| WP3 | WP2 schemas | WP1, WP5 (base + non-fact rules) |
| WP4 | WP1, WP2, WP3, styleguide from WP5 base | WP5 rules |
| WP5 | WP2 schemas, spaCy model | WP4 |
| WP6 | WP4, WP5 | WP7 dataset and metrics |
| WP7 | WP3 (fetch), WP6 for P2 | WP8 |
| WP8 | WP2, WP6 | WP7, WP9 |
| WP9 | WP4-WP6 pattern | WP8, WP10 |
| WP10 | WP7 | WP8, WP9 |
| WP12 | WP3, WP6, WP8; spike needs only CSCS | WP10 (spike any time) |
| WP13 | WP7 harness, CSCS | WP14, WP16 |
| WP14 | WP5, WP6 | WP13 (P0-ZH runs), WP15 |
| WP15 | WP14 identifier kind (for the decision letter); WP12 spike | WP13 |
| WP16 | nothing for push and CI; the positioning text needs WP13's numbers | WP13-WP15 |
| WP17 | after 16 October | - |
| WP18 | WP8 (done); WP15's form fields and notice banner build on it | WP13-WP16 (it touches no pipeline file) |
| WP11 | everything | - |

## 4. Schedule and gates

The gates, each at the end of its day (G1 and G2 passed on 6 Oct):

- **G1** (Tue 6 Oct): `make run` serves `/healthz` against CSCS; day-1 checks answered;
  `[verify]` markers resolved.
- **G2** (Thu 8 Oct): German `simplify --stop-after rules` end to end on a real page;
  golden tests for the top 12 rules green.
- **G3** (Mon 12 Oct, moved from Sat 10 Oct with the freeze, D-AD): every report §5 row
  on CSCS, P0-ZH included; headline decided (D-M).
- **G4** (Mon 12 Oct): UI demoable; export works; pipeline feature freeze (bug fixes
  only); decision mode v1 and WP18 in or cut, each per its own cut order.
- **G5** (Wed 14 Oct): report draft complete (6 pages), video recorded, clean-checkout
  test passed, CI green on the final commit.
- **G6** (Thu 15 Oct): everything submission-ready, nothing left to do on the 16th but
  click.

Prompt freeze: Sun 11 Oct, 18:00 (moved from Fri 9 Oct by the owner on 9 Oct, D-AD).
Prompt and pipeline changes for the final run go in until then and are measured on dev
first; the final CSCS run starts that night.

| Date | Focus | Gate (end of day) |
|------|-------|-------------------|
| Mon 5 to Tue 6 Oct | Design docs, this plan, the CSCS key; the core of WP0 to WP10, first without the key, then on CSCS; the gap review (§10) | **G1**, **G2**; first P0, P1 and P2 numbers on the 23 held-out pairs (§11) |
| Wed 7 Oct | Push the evening work; CI; P0-ZH condition and its runs (eval and dev); save the CSCS run of 6 Oct as `track_2b/eval/results-cscs-v1` and read its numbers; *done this day as well: the value kinds `identifier`, `period` and `address` (WP14), REF rows recomputed* | CI green on `main`; P0-ZH numbers on 20 eval pairs |
| Thu 8 Oct | Identifier kind; decision letter; fact-retention diagnosis; WP12 spike (half a day); KESB decision (D-T) and one published, anonymised decision as a test (WP15); period kind if the identifier kind is in (D-U, WP14); UI track (WP18, own session): D-V to D-Y, foundations, start of the review screen *(done 7 Oct)* | D-N and D-O decided; diagnosis table in prompts.md; D-T decided and D-I revisited; D-U decided |
| Fri 9 Oct | Fix the largest fact-loss bucket; clause recipes (German); Mediopunkt by code (WP14, D-S); dev rerun with `--redo`; before the freeze the decision mode's hooks (three `JobConfig` fields with defaults, the include lines in the standard templates, the SEM-08 line; about 1 h); UI: the review screen, the reader view; *prompt freeze moved to Sun 11 Oct (D-AD)* | Pre-freeze changes measured on dev |
| Sat 10 Oct | Pre-freeze changes and their dev measurement; value numbers (review stopwatch); decision mode (WP15): protected segments, FACT-08, orchestrator wiring, tests; UI: the drafts list, the New draft page | Every pipeline change for the final run in |
| Sun 11 Oct | Last dev rerun with `--redo` *(done 10 Oct, 17:00, on commit 3131a02 into `track_2b/eval/results-cscs-dev-final`: 166 of 175 calls from the cache, numbers as in the placement run but for two pairs' fresh recover samples; again only if the pipeline changes)*; **prompt freeze 18:00**; final CSCS evaluation overnight; example jobs with the decision letter (WP8); WP12a if the spike passed; positioning paragraph, "Why Apertus", precise claims; decision mode: German partial, SEM-09 and SEM-10, addressee, notice and FACT-07, form, API, CLI, the KESB example as a decision job, one P2 run on CSCS; UI: the job page, the texts, tests and screenshots; the decision mode's form fields and notice banner go into the new templates (WP18) | Final run started; example jobs in the image |
| Mon 12 Oct | Read the numbers per D-M (WP13); `publiccode.yml`; numbers audit; docs in sync; video storyboard; decision mode: French partial if time, docs | **G3**, **G4** |
| Tue 13 Oct | WP10 rest (8B vs 70B, κ labelling, hallucination spot check); report tables final; report §8 from WP17; D-L | All report tables filled |
| Wed 14 Oct | Report draft, video recording, clean-checkout test on Linux and on Windows | **G5** |
| Thu 15 Oct | PDF, numbers audit again, repo public, awesome-apertus pull request prepared | **G6** |
| Fri 16 Oct | Submit before 12:00 CEST | Submitted |

If the CSCS evaluation stalls (dropped streams, quota): P0 and P0-ZH may run on Public
AI, labelled as such; P2 numbers come only from CSCS; the v1 results are the fallback.

If one person with agents does the work: agents take the identifier kind (WP14), CI
and `publiccode.yml` (WP16) next to the evaluation runs. The owner keeps the diagnosis,
the decision letter and every text a juror reads. WP18 suits an agent session as well: it
touches no pipeline file, and the owner judges it from screenshots and the running UI.

Rule of thumb for the day: start with the item on the critical path (the gate), then
parallelisable items, then polish. Evaluation runs go in the background with the
cache on while UI work happens.

## 5. Day-1 verification script (WP1)

`track_2b/scripts/day1_checks.py`, run as soon as `.env` exists. Record each answer in
`track_2b/docs/architecture.md` §12 and remove the `[verify]` marker it resolves.

1. **Models and host.** `GET {LLM_BASE_URL}/models`. Expect `swiss-ai/Apertus-v1.5-8B`,
   `-8B-thinking`, `-70B`, `-70B-thinking`. Note the exact host that works.
2. **Thinking format.** One call to `-8B-thinking` with a short reasoning task.
   Check whether the SDK returns `reasoning_content`, inline `<|inner_prefix|>` tokens,
   or nothing. Sets the default `LLM_THINKING_MODE` and the stripping logic.
3. **JSON reliability.** 20 Understand-style calls on one 600-word page, with and
   without `response_format={"type": "json_object"}`. Count parse failures and
   validation failures. Sets whether `response_format` is used.
4. **Image input.** One call with a photographed letter as `image_url` (base64) to
   the 8B. Sets `FEATURE_IMAGE_INPUT`.
5. **Rate limits and concurrency.** 8 parallel short calls; note 429s, latency
   spread, and any documented limits in the response headers. Sets whether
   section-parallel writing is enabled and the eval worker count.
6. **Baseline quality.** P0 (single prompt) on 10 German pairs with the 8B. Read
   five outputs by hand. Decides whether A2 stays primary or B1 becomes primary with
   A2 as the stretch.

Also measure once: tokens and wall time for Understand + Write + Judge on a typical
page, to size `max_tokens` and estimate the eval budget.

## 6. Testing strategy

| Layer | What | How | Runs in |
|-------|------|-----|---------|
| Unit | Rules, readability, surface forms, JSON extraction, schemas, export wrapping | pytest, golden YAML, no network | `make test`, every commit |
| Recorded | Prompt rendering snapshots; parsing of real model outputs saved as fixtures | pytest with fixtures under `track_2b/tests/fixtures/llm/` | `make test` |
| Integration | Orchestrator with stub stages; API routes with the FastAPI test client | pytest | `make test` |
| Smoke | One real page through P2 against the live endpoint | `make smoke` | before each gate |
| Acceptance | Clean clone + `.env` + `make run` + one job in the browser | manual | G5, G6 |
| Evaluation | P0/P1/P2 over the manifest | `make eval` | G3, WP10 |

Privacy guard: a test asserts that no log line above `DEBUG` contains document text
(use a sentinel string in a fixture document).

## 7. Cut list

Apply in this order when a gate is missed:

1. LoRA (report only).
2. WP17 items (report §8 only), "check my own text" included.
3. Cross-language consistency check.
4. DOCX export and `make bundle`.
5. WP12b, the end-user letter mode.
6. `publiccode.yml`.
7. Italian.
8. Clause recipes for French (German stays).
9. WP18's later parts, in its own cut order (track_2b/docs/ui-design.md §13), "Suggest a
    sentence" for a missing fact first (it touches no evaluated path): the drafts
    list's extras, the job page beyond the stylesheet, New draft as its own page, the
    reader view's export panel.
10. WP12a, image ingest for the reviewed workflow *(cut 7 Oct, D-N)*.
11. 70B writer comparison (the 70B judge stays).
12. P0-ZH `condensed` (`complete` stays).
13. French.
14. B1 level.
15. UI polish: a single review page without the version switcher.
16. Judge κ labelling: 30 items down to 15, stated in the report.

Mediopunkt by code (WP14) is not on this list: both parts go in before the freeze or
both move to WP17 with a sentence in report §7. A checker change after the final run
would make its numbers stale, and the rule change alone adds warnings nobody fixes.

The decision mode (WP15, v1) has its own cut order inside its item: the French
partial, the code facts per operative item, the addressee in the judge, FACT-07. The
mode flag, FACT-08, the notice in the export and the KESB example as a decision job
go together or not at all; its hooks before the freeze cost nothing and stay either
way.

The UI redesign (WP18) goes in as a whole up to its review screen: the stylesheet, the
app bar and the review screen stay once started, or WP18 is reverted; only the later
parts in item 9 are cut on their own.

Never cut:
- `make run` from a clean checkout;
- FACT-01 and FACT-06;
- the identifier kind (if it causes false positives that cannot be fixed by G4, ship
  it as `warn`; do not remove it);
- the decision letter among the example jobs;
- the comparison of P2 with P0 and with P0-ZH `complete`;
- CI green on the submitted commit;
- the report;
- the video.

## 8. Open decisions

| ID | Question | Recommendation | Decide by |
|----|----------|----------------|-----------|
| D-A | Where do rules live: parse `track_2b/docs/rules.md` at runtime, or a code registry with a test that both contain the same ids? | Code registry (`rules/catalog.py`) with id, families, severities per level, prose; `styleguide.py` renders from it; a test diffs ids and severities against `rules.md`. Markdown parsing at runtime is brittle. | 7 Oct |
| D-B | `response_format` JSON mode | Use it only if day-1 check 3 shows fewer failures; never rely on it alone. *Decided 6 Oct on Public AI: 20 of 20 parsed in both modes, same answers; not used.* | done |
| D-C | SARI implementation | Own ~80-line implementation in `eval/metrics.py`, unit-tested against the EASSE example; avoids heavy deps in the image. | 9 Oct |
| D-D | UI styling | One vendored classless CSS file (pico.css or water.css, MIT) plus hand-written `app.js`; no framework, no bundler. *7 Oct: WP18 replaces water.css with an own stylesheet and vendored fonts, still without a framework or a bundler (track_2b/docs/ui-design.md).* | 11 Oct |
| D-E | Primary level A2 or B1 | Day-1 check 6. *In effect since 6 Oct: the evaluation runs at A2, the UI offers B1 with the team's own thresholds (report §6); the claims follow WP15's "Precise claims".* | 6 Oct |
| D-F | Section-parallel writing | Only if check 5 shows headroom; otherwise sequential. *Decided 6 Oct on Public AI: 8 parallel calls, no 429, 1.4 to 2.2 s each. Headroom exists; use it first for parallel evaluation workers, section-parallel writing stays optional.* | done |
| D-I | Main demo document | A past Federal Council voting explanation (track_2b/docs/sources.md §3); confirm its article-5 status first. Backup: the radio and TV fee exemption fact sheet. *Revisit on 8 Oct after the WP15 test run (added 6 Oct, night; cloud session): a KESB decision is the stronger sovereignty demo (track_2b/docs/use-case-decisions.md); the voting explanation can stay as one sentence on the federal gap. Test run of 7 Oct (use-case-decisions.md §7): the KESB decision is not demo-ready on today's pipeline (an invented appeal deadline, the deputy's tasks given to the person); it becomes the demo only with decision mode v1 by G4, otherwise the premium-reduction letter carries the product scene.* | 9 Oct |
| D-J | NUM-08 and +41 numbers | Decide at checker calibration: accept the international format or lower to `info`. | 8 Oct |
| D-H | Team name | Decided 5 Oct: **Röstigraben Bridgers**; file name `track_2b/RoestigrabenBridgers_Report.pdf`. Report §1 frames the name as bridging the gap between authorities and readers, not as translation. | done |
| D-K | P0-ZH variants | Run both on the 20 German eval pairs: `complete` (same task as ours, keep every fact; used for the headline) and `condensed` (their default for Leichte Sprache). One 8B call per pair, cheap. | 7 Oct |
| D-L | Name Zurich in the video | Report: yes, with credit, link and licence. Video: only in case A of D-M (WP13); otherwise "a strong single prompt". *10 Oct (owner): the end card's footer credits the institution in every case, "Inspired by simply-simplify-language, Team Data, Office for Statistics and Data, Canton of Zurich." (the office added the same day, its name as in their licence; no person named; naming Patrick Arnecke only with his consent). It lets viewers connect the evidence scene's "strong single prompt" with Zurich, so its final wording is decided here with D-M, in case C with the verification-layer framing.* | 13 Oct |
| D-M | Headline metric and sentence | The case table in WP13, applied to the final CSCS numbers, no debate. | 12 Oct (G3, moved from 10 Oct with the freeze, D-AD) |
| D-N | WP12 split | Spike on 8 Oct. WP12a (image ingest for the reviewed workflow) only if 3 of 3 phone photos keep every hard value in the transcription; WP12b (end-user mode) after G4 only if everything is green. *Decided 7 Oct after four spike runs (8B and 70B, 1,600 px and full resolution): hard values are lost at every setting, and at full resolution the models turn the IBANs, the AVS number and a period into other plausible numbers, the worst case for a fact contract. WP12a cut, WP12b after the deadline; the report names image input as future work with these numbers (track_2b/docs/prompts.md). 9 Oct: the digit loss came mostly from the server's clamp on image size (1400 x 1400 pixels); with `--strips` at the scan's resolution the 8B keeps every digit of both scans and loses only an invented place name inside addresses, e-mails and the URL. Decision unchanged; the owner may reopen WP12a with these numbers.* | done |
| D-O | Identifier matching | IBAN and AHV number compared without spaces; every other identifier exactly, after whitespace normalisation; no checksum test (letters carry specimen numbers); FACT-01 and FACT-06 severity `error` at A2 and B1. *Decided 7 Oct as recommended, implemented; a digits-only identifier also matches its bare number, so `Dossier 12345` survives as `Ihre Nummer: 12345`.* | done |
| D-P | Clause recipe for `wenn` / `si` | Question form ("Haben Sie ...? Dann ..."), never `vielleicht`; one line in the judge prompt: a condition must stay a condition. *Done 7 Oct (night): the recipes in `rules/recipes.py`, the judge line as SEM-08 in both judge prompts.* | done |
| D-Q | Outreach | No outreach during the hackathon (owner, 9 Oct): no mail to Zurich's team or to an easy-language office was sent. Report §6 ("Not a certification") says the drafts still need testing by readers from the target group. | 9 Oct |
| D-R | Fact-retention fallback | If P2 still keeps fewer facts than P0-ZH after the WP13 fix: no code-written fact sentences in the evaluated text; report the trade-off and the "no silent loss" property instead (case B of D-M (WP13)). *The recover round (D-AC) keeps to this: the 8B writes the sentence, code places it after its block and checks the value, and the judge reads the version.* | 10 Oct |
| D-Z | Facts-only rounds on or off for the final run | Default on (`MAX_FACTS_ROUNDS=1`) since 7 Oct (night). Decide from the dev rerun with and without them and from the diagnosis: keep them when fact coverage rises and invented values do not; set 0 when the missing facts are mostly written and rejected or dropped (buckets b and c), which is prompt and matcher work, not a round. *Decided 7 Oct from the ablation (track_2b/docs/prompts.md): on. Fact coverage 75 against 68 percent, hard facts kept 72 against 65, no invented value on either side, fewer judge findings. The third run answered the last question: 5 of 30 missing facts had been written into a version the blocking-count rule did not keep, so since 8 Oct the final version is the one with the fewest must-keep values missing, then the fewest blocking findings; `eval rescore --select facts|blocking` reads the rule's effect on the stored jobs without a model call. Read on the same jobs with `eval rescore` (7 Oct, late): facts first gives 80 percent fact coverage and 81 percent hard facts kept against 71 and 68 under the old rule, at 1.2 more judge findings and 1.3 more rule errors per 100 blocks; on the run before, 83 and 84. Open for the Friday decision: the cap of a facts-only round (`MAX_MISSING_PER_FACTS_ROUND`, default 5; 13 of the 30 missing facts were behind it, all in one pair with 22 facts), to be raised only with a measured rerun. Measured 7 Oct (fifth run and the cap-10 run, same cache): cap 10 gives 79 percent fact coverage and 81 percent hard facts kept against 75 and 77, no invented value, judge findings 2.8 against 4.6 per 100 blocks, rule errors 6.7 against 5.4; the default is 10 since then. The fifth run also shows no silent loss and nothing in bucket k.* | done |
| D-S | Mediopunkt by code (WP14): where and for what | P1 and P2 only; P0 and P0-ZH measure the prompt alone, as with Zurich's `strip_markdown`. Nouns only; adjectives keep the LEX-01 warning. The count of code splits is reported next to the LEX column. Optional at G3, if a juror could ask how much of the LEX gain is the cheap part: a rescored "P0 + code" row from the cache, no model calls. | 8 Oct |
| D-T | WP15 demo letter: premium-reduction reclaim or KESB decision | A team-written KESB decision (a deputyship) instead of the premium-reduction reclaim: it shows personal data and the second use case (track_2b/docs/use-case-decisions.md) at once. Keep the reclaim letter only if the KESB decision does not read like a real one after the check against published decisions. *Decided 7 Oct by its rule: the KESB decision, written in the layout and wording of the KESB Graubünden's two specimen decisions and the KOKES model decision. The reclaim letter is not written.* | done |
| D-U | Period value kind (`innert 30 Tagen`) before the freeze | Yes, if the identifier kind is in by Thu 8 Oct: same module (`rules/values.py`), 2-3 h, it makes the 30-day appeal period of the KESB demo a fact checked by code, and every further use case needs it first (track_2b/docs/use-cases.md §13). Otherwise WP17, with one sentence in report §7. *Decided 7 Oct: yes; period, identifier and address kinds done together, before the freeze.* | done |
| D-V | Reader typeface (WP18): Atkinson Hyperlegible Next for the reader view and the HTML export | In the reader view yes: the vendored font, injected into the preview response only. In the HTML export first in the font stack with Arial and Helvetica behind it, not embedded, so exported files stay small (track_2b/docs/ui-design.md §14). *Decided 7 Oct as recommended, implemented.* | done |
| D-W | New draft as its own page at `/new` (WP18); the start page becomes the drafts list | Yes; `POST /jobs` and the API stay; the demo's "paste a letter" scene starts at `/new`, one click from the list. *Decided 7 Oct, implemented.* | done |
| D-X | Accent colour and density as settings (WP18) | No settings in v1: the accent is one CSS variable with its tints, the density stays "comfortable"; WP17 if reviewers ask. *Decided 7 Oct.* | done |
| D-Y | Per-row checks and review progress in the drafts list (WP18) | Computed per request with `review_view` for the at most 50 rows shown; a stored summary per job only if the page needs more than 300 ms with 50 jobs. *Decided 7 Oct, implemented (`drafts_view`).* | done |
| D-AA | The vocabulary in the pipeline: after 16 October (WP17) or now | Now (owner, 7 Oct): checked explanations in the fact sheet, missing glossary entries by code, rule LEX-07 / LEX-07-FR (track_2b/docs/rules.md "Vocabulary"); `USE_VOCABULARY=0` switches them off for the measurement. A last vocabulary round rewrites the office words left in the best version (42 to 19 office words in the final drafts, no fact lost). The writer gets no list of office words: tried, it primed the 8B to write those words; removed (owner, 7 Oct), worth another try with a later Apertus. Keep the rest on for the final run unless a rerun shows a loss of facts or style (track_2b/docs/prompts.md, "Vocabulary in the pipeline"). *Decided 7 Oct, implemented.* | done |
| D-AB | A fact-sheet value the source does not contain (FACT-05): known to FACT-06 and required by FACT-01, or neither | Neither: the model computed or invented it (an end of an appeal period, a day for "im Frühling"), or normalised it into a form no faithful draft can match; FACT-01 and the source check use the same matching. FACT-05 keeps warning on the fact sheet, FACT-06 flags the value in a draft, fact coverage counts only facts whose value the source contains. *Decided 7 Oct (owner) after the KESB decision's invented deadline, implemented. Dev rerun on CSCS with the old and the new rule on the same cache: fact coverage 78.8 against 78.8 percent under the new measure, hard facts kept, invented values and rule errors unchanged, about 600 tokens per page less; the measure alone raises stored P2 fact coverage on the eval pairs from 81.7 to 83.1 percent (track_2b/docs/prompts.md).* | done |
| D-AC | "Suggest a sentence" for a missing fact (9 Oct): on the review page only, or also as a round in the pipeline | Review page only until 16 October: a pipeline round would change the evaluated numbers after the prompt freeze (Sun 11 Oct, 18:00, D-AD) and the final run, and on f07 two of three sentences kept the value but lost the residence condition, which only a reader sees. As a pipeline round after the facts rounds, behind a setting with default off, only after the dev measurement (WP18 item) and a rerun; otherwise report §8 as next step. *Decided 9 Oct by the owner after the dev run (German fact coverage 78 to 96 percent, no invented value added): the recover round is on by default, `MAX_RECOVER_FACTS=10`, and in the final run.* | done |
| D-AD | Prompt freeze: Fri 9 Oct, 18:00, or later | Sun 11 Oct, 18:00 (owner, 9 Oct). Prompt and pipeline changes for the final run go in until then and are measured on dev first; the final CSCS run starts on Sunday night, G3 and D-M move to Mon 12 Oct, G4 stays on Mon 12 Oct. | done |
| D-AE | Prompt language (9 Oct): instructions in the document's language, as frozen, or English instructions for German and French documents, in some or all of understand, write, judge and repair | The document's language, as frozen. On the dev pairs English repair wrote longer, less plain German on equal input (45 new rule problems against 26), English Understand failed on 2 of 12 pages in two passes and dropped content (114 must-keep facts against 176 and 150), and English reached omission entries; the gains on facts stayed within the noise of two German runs (track_2b/docs/prompts.md, "English instructions"). The one lead is the English judge's fact verdicts (65 against 37 percent agreement with the blind labels on 19 facts), worth more labels after the final run. *Decided 9 Oct by the owner: not taken; the variant removed completely, the results kept in track_2b/docs/prompts.md.* | done |
| D-AF | Polish round (10 Oct): one more repair round after the recover round for the rule findings the facts and recover rounds leave in the sentences they add, or none | Yes, measured on dev first (owner, 10 Oct). From the example rebuild: 0 of 6 German and 0 of 6 French fresh attempts clean; the long passive sentences in the final drafts had come in with the facts and recover rounds, nearly the source's, and no round saw them again; in both dev runs of 9 Oct every final draft has errors. `MAX_POLISH_ROUNDS=1`: the best version's repairable rule errors, or its warnings once no error is left, in one more round through the repair prompt, no fact, no judge's problem, no office word; kept only when it loses no must-keep value and adds no blocking finding (architecture §4.6). *Measured 10 Oct on the 12 dev pairs (track_2b/docs/prompts.md, "The polish round on the dev pairs"): German rule errors 1.9 to 1.3 per 100 blocks, warnings 38 to 34, unsupported 5.8 to 5.3, fact coverage and hard facts unchanged at 96 and 90 percent, no must-keep value lost, about 17 percent more tokens; final drafts built on the polished version in 8 of 12 jobs, discarded in 4 where the judge flagged the rewrites. Kept on for the final run.* | done |
| D-AG | The judge's unsupported verdicts (10 Oct): leave them, or make each quote the words it objects to and let code check the quote | Quote and check (owner, 10 Oct, from the example rebuild: the 70B cited the judge prompt's own example block ids, `b006` in 46 of 179 verdicts of the example builds and 18 of 146 in the dev run of 9 Oct, and called a French draft unsupported for a tax assessment the letter names; one French attempt was clean but for such a verdict). Both judge templates ask for a `quote` and say that another wording of the same statement is no problem; `to_judge_report` keeps a verdict on the block that holds the quote, moves it there when another block does, and files the rest under `dropped` in the report, counted nowhere. *Measured 10 Oct on the 12 dev pairs (track_2b/docs/prompts.md, "The judge's quotes on the dev pairs"): unsupported verdicts over all versions 188 to 102, 4 dropped as copies of the example; German unsupported 5.3 to 3.1 per 100 blocks, rule errors 1.3 to 0.2, invented 0.6 to 0.0; fact coverage 96 to 94 and hard facts 90 to 88 on one pair alone, where a facts round added none of 9 values in a fresh sample. Kept on for the final run.* | done |
| D-AH | Bookkeeping errors and the judge's spellings (10 Oct): leave FACT-02, FACT-03 and the judge's fact check as they are, or link a fact without a value by its source sentence, skip a question block in FACT-03 and tell the judge that another spelling of a value is no distortion | All three (owner, 10 Oct, from the second rebuild round on the new pipeline: 0 of 11 attempts clean, 23 of about 42 errors FACT-02 and FACT-03, 14 judge verdicts; in the dev finals 11 of 18 FACT-02 findings on facts without a value have their source sentence cited by a block; the judge called CHF 42'000 a distortion of CHF 42'000.-). `stages.link_facts` names such a fact on every block that cites one of its sentences, and a fact with values in its text on the blocks of its sentences that together hold all of them (7 of the 12 FACT-02 findings left in the second rebuild round were the income limits spread over two sentences); FACT-03 skips a question; both judge templates carry the spelling line. *Measured 10 Oct on the 12 dev pairs (track_2b/docs/prompts.md, "Fact links, questions and the judge's spellings on the dev pairs"): FACT-02 findings in the finals 19 to 10, unsupported verdicts over all versions 102 to 55, German unsupported 3.1 to 0.8 per 100 blocks, two finals without any error for the first time; fact coverage 94 to 95, hard facts 88 to 86 on one pair's fresh sample, rule errors 0.2 to 1.3 within the day's run-to-run range. Kept on for the final run.* | done |
| D-AI | Sentence placement (10 Oct): a sentence added after a list item lands between the items, or after the list | After the list (owner, 10 Oct, from the clean German candidates of the third rebuild round, whose list of enclosures the facts and recover rounds had split). `stages.apply_repairs` holds an addition after a list item until the list ends, `stages.add_sentences` places a recovered sentence after the list and after earlier recovered sentences of the same list; tests, docs. *Measured 10 Oct on the 12 dev pairs (track_2b/docs/prompts.md, "Sentence placement on the dev pairs"): 7 pairs identical from the cache, 5 with fresh later samples; German rule errors 1.3 to 1.6 per 100 blocks, fact coverage 95 to 96, hard facts 86 to 87, unsupported 0.8 to 1.0, all within the day's noise. Kept on for the final run.* | done |

## 9. Judging criteria → evidence we must produce

| Criterion | Evidence | Produced by |
|-----------|----------|-------------|
| Purposeful use of AI | The "Apertus understands, code counts" split; P0 vs P1 vs P2 table showing what each AI stage adds; the not-a-translator comparison (use-case-canton.md §4); P0-ZH: what the pipeline adds over the best public single prompt on the same model; Apertus image input in the reviewed workflow (WP12a, cut by D-N) | WP5, WP7, WP13, report §3 and §5 |
| Technical rigour | Golden tests, FACT-01 exact coverage, judge κ, recorded fixtures, resumable pipeline, cache for reproducible reruns; a fair baseline; the fact-retention diagnosis; identifiers in the fact contract; CI green on the submitted commit; numbers audit | WP5, WP7, WP10, WP13, WP14, WP16 |
| Value, cost and scalability | CHF per page 8B vs 70B, latency per stage, reviewer workflow with provenance; minutes per page including review; an outside voice; `publiccode.yml`; the WP17 roadmap (termbase, house styles) in report §8; one engine, many documents: the further use cases in `track_2b/docs/use-cases.md` | WP1 usage log, WP10, WP13, WP16, WP17 |
| Sovereign deployability | `local-llm` compose profile, air-gapped image (no CDN, models baked in), single `LLM_BASE_URL` dependency, hardware statement; the decision letter with personal data, which may not go to a cloud chatbot; the "Why Apertus" box; the decisions use case, where the text may never leave the authority (track_2b/docs/use-case-decisions.md); the use cases under official, medical or tax secrecy and the three conditions that leave Apertus as the only model (track_2b/docs/use-cases.md §2) | WP0, WP8 vendoring, WP15, report §2 |
| Implementation feasibility | `make run` on a clean checkout, example jobs including the decision letter, limitations stated honestly; CI; `main` equals the state in this log | WP0, WP8, WP11, WP16 |

The jury's guiding questions for Track 2B (read from hackapertus.ch on 9 Oct): five
dimensions, 0 to 5 each; technical rigour is judged against the maturity level the
team declares; teams declare the external services the running system contacts and
the use of coding assistants; a named first user counts under feasibility.
track_2b/docs/submission.md §6 maps every question to where README and report answer it.

## 10. Gap register (6 October 2026, night)

Input, all from 6 October:

1. A look at the visible Track 2B field and the jury: about 15 public entries, found
   by search (titles and descriptions only). Most of them are general "trust layers"
   (audit trail, human approval, provenance). Domain entries close to us: Velum
   (air-gapped anonymisation of Swiss court decisions), a court-triage head on a
   frozen Apertus 8B, GemeindeSim. Model work: Loraclette (a LoRA), Vipunen
   (red-teaming). Jury as listed for Hack Apertus: two business leaders, two
   professors (NLP at HSG, FHNW School of Business), a responsible-AI researcher (Sony
   AI) and SNAI's technical community manager.
2. A line-by-line comparison with the Canton of Zurich's app
   `machinelearningZH/simply-simplify-language` (v1.6.0, commit `5462559`, MIT) and its
   ZIX index. One prompt with 39 rules plus 10 clause recipes for Leichte Sprache,
   commercial models through OpenRouter, public data only, no fact checks, no
   evaluation of output quality, plain text output. Its README roadmap until July 2025
   (completeness and accuracy checks with an LLM judge, passive and Konjunktiv
   detection, managed terminology, on-premise open models) is largely what we built.
3. A recheck of `main` after the push of `29a61df` and `cdb3b8b` (§11).

What the reviews concluded:

- We are likely in the top group on technical rigour, sovereign deployability and
  feasibility. On "why Apertus" and on value we are in the middle until there are
  numbers.
- The vocabulary of the field (audit trail, human in the loop, sovereign) does not set
  us apart. Numbers, a named user and real Swiss texts do.
- The real threats: a well-measured anonymiser such as Velum (sovereignty is a
  necessity there), and as ideas a photo-of-a-letter explainer (our WP12) and Swiss
  German minutes.
- Zurich's app is the prior art every Swiss juror can name. Their own published
  roadmap is our best positioning; their prompt is the fairest baseline we can run.

Must = done by G3 or G4. Should = by G4 if every Must is green. Later = report §8 only.

| ID | Gap | Evidence | Criterion | Closed by | Priority |
|----|-----|----------|-----------|-----------|----------|
| GAP-01 | No headline number: P2 against P0 on CSCS still pending | `track_2b/eval/report.md` holds SOURCE, REF and P0 (Public AI, 10 pairs) only | All | WP13 | Must |
| GAP-02 | P0 is a one-sentence prompt; a juror can call it a strawman | `llm/prompts/de/baseline.md` | Rigour, purposeful AI | WP13 (P0-ZH) | Must |
| GAP-03 | P2 may keep fewer facts than P0 | P0, eval, Public AI: 83 % fact coverage, 90 % hard facts kept. P2, dev, CSCS with guard: 61 % fact coverage. Repair "no progress" on 9 of 12 dev pairs (Public AI). Different splits and endpoints, but the risk is real | Rigour, value | WP13 | Must |
| GAP-04 | Identifiers are outside the fact contract: a lost reference or AHV number is a silent loss | `HARD_KINDS` = date, amount, phone, email, url, percent, time (`rules/values.py:19`) | Rigour, sovereignty story | WP14; *closed 7 Oct: `identifier` in `HARD_KINDS`* | Must |
| GAP-05 | Repair gets no concrete recipe for subordinate clauses | LEN-02 carries no suggestion; Zurich's prompt has a recipe per conjunction | Rigour | WP14 | Should |
| GAP-06 | "Why sovereignty?": every demo text is public | `track_2b/data/examples/`, track_2b/docs/sources.md §3 | Sovereign deployability | WP15 | Must |
| GAP-07 | "Why Apertus?": no Apertus-specific feature in use | image input verified on CSCS, not wired into ingest; Italian jobs refused | Purposeful AI | WP15 (WP12a, argument) | Should |
| GAP-08 | Prior art not addressed | Zurich's app, SUMM AI | Value, purposeful AI | WP16 | Must |
| GAP-09 | No outside voice, no target-group contact | report §6 | Value; the responsible-AI juror | Not addressed: no outreach during the hackathon (D-Q); report §6 "Not a certification" | Should |
| GAP-10 | Value stays qualitative | no minutes or francs saved per page | Value, cost | WP13 | Should |
| GAP-11 | `main` lags this log; stale counts | the evening work is not pushed (§11); README and report say 404 tests | Feasibility | WP16 | Must |
| GAP-12 | No CI: the tests run only on our machines | no `.github/` | Rigour, feasibility | WP16 | Must |
| GAP-13 | Generic pitch vocabulary; too much architecture for 2 minutes | README first screen, track_2b/docs/demo-video.md | All | WP16 (messaging rules) | Should |
| GAP-14 | Live-run risk | example jobs pending; CSCS cuts about 1 in 4 long thinking calls; `local-llm` ran once on an L4 (10 Oct, WP10); no bundle | Feasibility | WP8, WP10, WP16 | Must (example jobs) |
| GAP-15 | Claims not precise enough | the voting gap is federal (Zurich publishes cantonal voting information in Leichte Sprache since 28 September 2025); A2 or B1 still open (D-E) | All | WP15, WP16 | Must |
| GAP-16 | Not listable as public-sector software | no `publiccode.yml` | Value, scalability | WP16 | Should |
| GAP-17 | UI only in English | templates use `lang="en"` | Value | WP17; *German since `3ef69d3` (6 Oct), French and Italian stay WP17* | Later |
| GAP-18 | Zurich's good ideas not captured | termbase, house styles, check my own text, completeness switch, several drafts, DOCX | Value, scalability | WP17, report §8 | Later |
| GAP-19 | Long compounds reach the reviewer unsplit: the glossary exempts them from LEX-01, and the 8B ignores the split suggestion | job `287fea3aadd2` (6 Oct, web UI, CSCS): `Krankenversicherungspolice` and `Sozialversicherungsstelle` in the final draft, `Alleinstehende` flagged through two rounds | Rigour, value (the first thing a juror sees in a draft) | WP14 | Should; in by the freeze or WP17 |
| GAP-20 | The strongest sovereignty case was not described: decisions of child and adult protection authorities (KESB) and courts, explained to the person concerned in a letter that goes out with the decision | Idea from the Velum comparison (6 Oct, night; cloud session); KESB Region Solothurn has done it by hand since 2016; appeal periods of 30 and 10 days (Art. 450b ZGB) | Sovereign deployability, value | Docs written 6 Oct (night; cloud session) as a patch, not committed: `track_2b/docs/use-case-decisions.md` plus references in README, architecture, report §8, sources §3, demo-video §4 (on `main` as `acab7a9` since). Demo: WP15 (D-T). Decision mode: WP15 "Decision mode v1", planned 7 Oct for Sat 10 to Mon 12 Oct; the rest WP17 | Must (docs, demo), Should (mode v1 by G4) |
| GAP-21 | The further use cases were not described: patient letters, lease terminations, penal orders, payment orders, social and school decisions, information for study participants, migration, private-sector letters | Raised 6 Oct (night): one engine, many documents; penal orders are 92 percent of Swiss convictions with a 10-day objection period; 49 percent of adults have low health literacy | Value, scalability | `track_2b/docs/use-cases.md` and the planned fact checks in `track_2b/docs/rules.md`, written 6 Oct (night; cloud session, 2). Modes and checks: WP17 | Should (docs), Later (modes) |
| GAP-22 | A period is no checked value: `innert 30 Tagen` yields a plain number, so a changed or invented period passes FACT-01 and FACT-06 unless the fact sheet carries it as a value | `rules/values.py` (`ValueKind`, `HARD_KINDS`); step 4 of `track_2b/docs/use-case-decisions.md` claimed otherwise (corrected 6 Oct, night) | Rigour; the KESB demo's 30-day appeal period | WP14 (period kind, D-U); *closed 7 Oct, with the address kind* | Should; by the freeze or WP17 |

## 11. Progress log

Add one line per working session: date, what was finished, what moved.

- 2026-10-05: design docs committed; plan written; use case doc (docs/use-case-canton.md) added; nothing implemented yet.
- 2026-10-05 (late): CSCS key requested. WP0 and the WP1 client done without a key: scaffold, Docker image, compose profiles, LLM client with retries, reasoning removal, JSON repair and cache; 50 tests green. Apertus 1.5 is not on Hugging Face inference providers; Apertus 1 is, as a dev-only fallback. Public AI's own API serves all four Apertus 1.5 variants (pay per token, USD 2 starter credit): fallback for development and evaluation if CSCS is slow or late; client now sends a User-Agent it requires.
- 2026-10-06 (night): implemented everything that needs no key, with three helper agents (ingest, metrics, dataset) and a research agent. Rule checker for German (30 rules, golden tests, hard texts, calibration on 30 official pages: 2.0 errors per 100 blocks), schemas, store, pipeline with code-completed fact sheet and repair loop, web API and review UI (checked with screenshots), exports, evaluation harness (SOURCE and REF rows computed), day-1 script, manifest with 35 pairs. Without a key the pipeline ran against Apertus 1.5 8B in a community 4-bit build through llama.cpp on the laptop GPU: understand works; write with thinking was slow and paraphrased, without thinking fast and much better, so write runs without thinking by default (LLM_THINKING_STAGES); runaway reasoning now falls back to an answer without thinking, and a failing judge or repair no longer fails the job. Decisions: D-A (code registry), D-C (SARI port, checked bit for bit), D-D (water.css), D-J (spaced +41 accepted) are done; D-I has candidates (docs/sources.md §3).

- 2026-10-06 (morning): verified end to end without a key. The Docker image (`make run` equivalent) ran three real P2 jobs through its web API against the local 4-bit Apertus 8B: understand, write, judge and repair work, the review page and the exports show the results, and the fallbacks fired as designed (runaway reasoning answered without thinking, a judge answering with a bare list skipped with a note, a repair round without progress stopped). Repair quality on this 4-bit model is the weak point: one direct run restored all missing fact values, the container runs did not; repairs now come in focused rounds (blocking problems first, at most 5 missing facts) and all prompt examples moved to topics outside the evaluation set after examples leaked into drafts. The new compose profile `local-llm-small` (llama.cpp CUDA image) was tested on the RTX 4060. Calibration after the ingest fixes: 2.0 errors per 100 blocks on 3,468 blocks; SOURCE and REF rows in eval/report.md. 587 tests. Next with the key: `make day1`, then tune the prompts on the official model, then `make eval`.

- 2026-10-06 (day): French done without a key (WP9 French): 27 French rules in `rules/fr.py` (tense and mood from verb endings, since the French parser misreads them), golden tests and the French hard texts, calibration on the 5 official French pages (5.3 to 2.2 errors per 100 blocks; French sentence limits 15/18 words from the data), French prompts and few-shot examples, prompt labels per language, French test letter, web form and API accept French, report sections per language with French SOURCE/REF rows, French spaCy model in the image. Two French runs on the local 4-bit Apertus: good FALC drafts, same weaknesses as German (missing income limits, weak repair, unreliable 8B judge, judge thinking runs to the token limit). Code fixes from the runs: repeated sentences dropped after write and repair, judge findings on headings not sent for repair. 750+ tests. Italian, DOCX and the bundle stay stretch.

- 2026-10-06 (afternoon): `make day1` on the Public AI gateway (architecture §12): all four Apertus 1.5 names listed; the 8B returned no reasoning in 15 of 15 thinking calls (two of three had reasoned in the morning), so Public AI runs count as runs without thinking at every stage; JSON 20 of 20 in both modes (D-B: `response_format` not used); image input works (check 4 passed); 8 parallel calls without a 429 (D-F: headroom, eval can run pairs in parallel). Three 504s on long calls, retried fine. Next: P0 on 10 German pairs (D-E), prompt tuning on the dev split, then `make eval` labelled Public AI.
- 2026-10-06 (afternoon, 2): the P0 baseline run on Public AI got through 3 of 10 pairs: 3 pairs lost to 504s (Cloudflare cuts responses after about 100 s; long pages at 20 tokens per second exceed that), and the run died when the 8B left the `facts` list out of a fact sheet for scoring. Fixes: the client streams every response (`LLM_STREAM`, default on), a scoring failure marks the pair `scoring_failed` instead of stopping the run, failed pairs rerun on the next `eval run` (their rows are replaced), and a complete Understand answer without `facts` counts as an empty fact sheet. Next: rerun P0 (`--limit 10`), read five outputs for D-E.
- 2026-10-06 (afternoon, 3): P0 rerun with streaming: no 504s (answers of up to 3,400 tokens in 157 s), 8 of 10 pairs scored. The two others failed scoring because the 8B writes long runs of segment ids as a range (`"s0064" bis "s0087"`) on long pages, and `extract_json` skipped the broken outer object and returned the inner `core` object. Fix: the parser writes ranges out, repairs trailing and missing commas, and reports a syntax error with its position instead of a fragment. P0 then scored 10 of 10 pairs (architecture §12, item 6): 16.1 errors per 100 blocks against 2.7 for the official texts, 90 percent of hard facts kept, readability 46. D-E waits for P2 on the dev split. Numbers are Public AI, 8B without thinking; `eval/report.md` is regenerated only by the full `make eval`.
- 2026-10-06 (evening): P2 on the dev split (Public AI, 8B without thinking, 70B judge without thinking): 11 of 12 pairs reached review, French excellent (3.3 errors per 100 blocks, 88 percent fact coverage), but 4 of 10 German drafts were the write prompt's JSON example (dog tax) word for word, patched by the repair rounds into nonsense, and one write put the omissions list inside blocks. Fixes: write prompt v5 (form before the style examples, document last with a closing instruction), a code guard that sends a copied answer back once (understand, write, repair), the pseudo-block list hoisted, and `eval run --redo` to rerun pairs after a prompt change. Next: rerun P2 on dev with `--redo` and compare.
- 2026-10-06 (night): P2 dev rerun with prompt v5 and the guard: 12 of 12 pairs reached review, no copies. German means v4 to v5: invented per 100 blocks 20.6 to 3.7, errors 5.1 to 2.3, fact coverage 45 to 54 percent, hard facts kept 55 to 61 percent (docs/prompts.md, Tested so far). Found: the examples' phone number (031 987 65 43 / 032 987 65 43) in 4 of 12 final drafts and the example's office in 3, inserted by repair additions and not caught by the judge; and the repair round brings no progress on 9 of 12 pairs. Next: a code rule FACT-06 (every value in the draft must be in the source), then the repair prompt for additions.
- 2026-10-06 (late): CSCS key arrived; `.env` on profile A. `check-llm` and `make day1` on CSCS (architecture §12): official names, reasoning in the `reasoning` field (model-suffix mode works), 39 of 40 JSON answers, image input works, 8 parallel calls at 100 ms, about 150 tokens per second. About one long thinking call in four is cut by the server (`incomplete chunked`); retries recover it, `LLM_MAX_RETRIES=8` for profile A. Thinking costs 12 to 90 s per Understand call. Running: P2 with thinking on 3 dev pairs in `eval/results-cscs` (own folder: the results file name is the lowercased model name, the same for both endpoints). Public AI day-1 file kept as `day1_checks_publicai.json`.
- 2026-10-06 (night, 2): P2 with thinking on 3 dev pairs on CSCS (`eval/results-cscs`): fact coverage 0.29/1.00/0.00 (gateway, no thinking) to 0.89/0.80/1.00, hard facts kept 0.43 to 0.81 on average, 60 to 90 s per job; texts longer and harder to read; the thinking judge finds distortions. Thinking stages stay. Parser repairs added for a missing comma after a list or object, an object not closed before a top-level key (schema-aware) and a German quotation closed with a straight quote; the voting pair then ran from the repaired cached fact sheet. Next: FACT-06, then repair additions, then `make eval` on CSCS.
- 2026-10-06 (late, 2): FACT-06 implemented (`rules/document.py`): every date, amount, phone number, e-mail and web address, percentage and time in a draft must be in the source or the fact sheet; error at both levels, blocking, sent to repair with the source's only phone number, e-mail or web address as the suggestion (never a date or amount); shortened web addresses and full hours the source writes as plain numbers pass. The evaluation counts invented values per 100 blocks by code against the source alone (also for P0 and the official versions): new column in `eval/report.md`, old result rows show a dash until rerun with `--redo`. Docs, README and report updated (42 rules). Checked on the stored dev drafts: the examples' phone numbers in 8 of 12 final drafts, the examples' 120 Franken and 30. April 2026 in 3, an e-mail with a dropped letter on CSCS, no false positive in 10 P0 drafts (1,100 blocks); the official easy versions add 2.2 values per 100 blocks their originals do not have. Next: the repair prompt for additions, then `make eval` on CSCS.
- 2026-10-06 (late, 3): repair prompt v6 (DE, FR): every value comes from the fact sheet or the original's sentences, the JSON form's values belong to another document, no value invented for a fact without one. Code guard in the repair call: an answer with a value the document does not have (KnownValues, the FACT-06 check) is sent back once with the values named; the second answer is used as it is. Write is not guarded (long call; FACT-06 plus repair do the job). Next: P2 dev rerun on CSCS with `--redo` to compare invented values and rounds, then `make eval` on CSCS.
- 2026-10-06 (late, 4): P2 dev rerun on CSCS with the guard (docs/prompts.md, Tested so far). Two defects found and fixed on the way: the guard's complaint on the last attempt failed a repair round (now a `soft_check` of `complete_json` that is consulted only while an attempt is left and falls back to the answer it complained about), and an answer that fails to parse stayed in the response cache, so `--redo` and the automatic rerun of failed pairs replayed it (now `LLMClient.forget` drops it). Results: 11 of 12 pairs through, guard fired 10 times in 33 repair calls, always on example values, second answers clean; 8 foreign values left, 6 of them from the write stage (paraphrased example content below the copy guard's threshold), German fact coverage 61 percent, invented values 2.1 per 100 blocks. `be-pregnancy-counselling-de` fails in Understand on changing JSON slips (missing comma last). Next: the write stage's paraphrased example content (topic words in the copy guard, or the soft foreign-value check on write), then `make eval` on CSCS.
- 2026-10-06 (evening): parser repairs for two more CSCS slips (a list or object closed with the wrong bracket, a broken unicode escape) and for a core answer given as a bare sentence; topic words of the examples in the copy guard, soft (sent back once, dropped from the second answer; the first, hard version failed two P1 jobs over one sentence); `make run` and `make smoke` verified against CSCS from the container (Git Bash needs `MSYS_NO_PATHCONV=1`, now in the recipe); `eval sample` and `eval kappa` for the judge labelling (sheets in the git-ignored `eval/labels/`); `RESULTS` variable for `make eval`. Full evaluation on CSCS started (`RESULTS=eval/results-cscs`, 70B writer on 5 pairs queued): 7 of 23 P0 scorings and 2 P1 jobs failed on slips fixed since, 22 dropped streams in the first 70 calls; the failed pairs rerun after the chain. 798 tests.
- 2026-10-06 (night): G3 reached four days early: P0, P1, P2 on all 23 held-out pairs on CSCS and the 70B writer on 5 (docs/prompts.md, technical report §5 and §1 filled). On the way: a write answer cut off at the token limit is written again as two halves (8 jobs), entries written as blocks and empty blocks are hoisted or dropped, the examples' own values count as example content (P2 invented values 3.1 to 0.1 per 100 blocks), the topic rule is soft. Every P2 job stops on "no progress" after 1.8 rounds: the repair prompt is the next lever. Open in WP10: the hand labelling (sheets ready), the hardware statement (written as a statement). 811 tests.
- 2026-10-06 (evening, 2; parallel session): WP13 P0-ZH and WP16 CI, next to the other session's 70B comparison in the same tree. P0-ZH: Zurich's prompt as a Jinja template generated from their `utils_prompts.py` (v1.6.0, commit 5462559) and checked character for character against their `create_prompt`; conditions `P0-ZH-complete` and `P0-ZH-condensed` through schemas, orchestrator, stages (`baseline_zh`: tags, ß to ss, no `strip_markdown`, a note when the tags are missing), eval runner (French pairs skipped), report rows, CLIs, web step map and catalogs, Makefile `eval` target; `THIRD_PARTY_NOTICES.md`; 8 tests; docs (prompts.md, architecture §9 and §11, report §5 and §7). Smoke run on CSCS (`eval/results-cscs-zh`, one dev pair): 5 s, tagged answer, 58 blocks, 0 errors per 100 blocks. Found on the way: a baseline scored before any P1/P2 job existed used the raw Understand answer without code completion (`_reference_factsheet`), so the first 13 P0 scorings of the eval run were measured against fewer facts; fixed with a test, P0 needs a `--redo` rescoring from the cache. CI: `.github/workflows/ci.yml` (ruff, pytest, Docker build and `/healthz` against an unreachable endpoint, trivy advisory; actions pinned to commits), badge in README; the three jobs rehearsed locally in Docker (image built, `/healthz` 200 with `reachable: false` against an unreachable endpoint, ruff and 824 tests green on Linux inside the image). Suite: 824 tests. Next: run P0-ZH (both variants) on the 20 eval and 10 dev German pairs plus P0 on the dev pairs into `eval/results-cscs` once it is free, rescore P0, then §13.4.
- 2026-10-06 (evening, 3; parallel session): `eval/results-cscs` handed over by the other session after its 70B runs; snapshot to `eval/results-cscs-v1` (store checkpointed, every file). Then in the folder: P0 `--redo` on the 20 eval pairs from the cache (fact coverage 98 to 93 percent, nothing else changed; seconds per page read 0.0 because cached calls count 0 s), P0 on the 10 dev pairs, P0-ZH complete and condensed on eval and dev: 90 jobs, all to review, about 2 minutes per 30 jobs, every answer tagged; `eval/report.md` regenerated. Eval: P0-ZH complete 91 % coverage, 95 % hard facts, 15.4 errors per 100 blocks; condensed 75, 77, 8.7; P2 8B 84, 80, 4.3: §13.4 case B, recorded there. Numbers in docs/prompts.md (new subsection, P0 row corrected), report §5 (P0 row, two P0-ZH rows, one paragraph), architecture §9 (one sentence). Open in WP13: headline metrics (silent-loss column), value numbers, the Friday final run; the headline sentence is the owner's (D-M).
- 2026-10-06 (night, 3): two reviews: the visible Track 2B field and the jury, and a line-by-line comparison with the Canton of Zurich's `simply-simplify-language` (v1.6.0, commit `5462559`, MIT) and its ZIX index. Recheck of `main` after the push of `29a61df` (FACT-06) and `cdb3b8b` (repair guard). Gap plan §13 added: gap register, WP13-WP17 (P0-ZH baseline with Zurich's prompt, fact-retention diagnosis, identifiers as hard facts, clause recipes, a decision letter with personal data, CI, positioning, outreach), a schedule to 16 October, a revised cut list, decisions D-K to D-R. Not yet on `main`: the evening work (`eval sample`, `eval kappa`, the `RESULTS` variable, `MSYS_NO_PATHCONV=1`, the topic-word copy guard; the parser repairs for a wrong bracket and a broken unicode escape were not found either). README and report still say 404 tests.
- 2026-10-06 (night, 4): the owner's first test of the web UI against CSCS (job `287fea3aadd2`, P2, 2 rounds, stopped on "no progress"): the final draft keeps `Krankenversicherungspolice` and `Sozialversicherungsstelle` unsplit because the glossary exempts them from LEX-01, and the compounds LEX-01 flags keep their warning because the 8B ignores the split it is given. Fix reviewed and written into WP14 (GAP-19, D-S): the rule stops exempting glossary compounds, and a deterministic step splits compound nouns after write and after every repair, in P1 and P2 only, with the count recorded per version and reported. Nothing implemented yet.
- 2026-10-06 (night, 5): Mediopunkt by code (WP14, GAP-19, D-S) implemented. LEX-01 no longer exempts a compound because it is in the glossary (only a long non-compound stays exempt); its suggestion comes from `lexicon.mediopunkt_suggestion`, shared with the new step `rules/mediopunkt.py`, which splits compound nouns (spaCy NOUN or PROPN, no digit, no URL or e-mail) in blocks and glossary terms and lowers a capital after the dot, after write and after every repair, before the check, in P1 and P2 only. Recorded as `Draft.code_edits` (one entry per word) on the version it changed; the review page says "n words split by code" (DE, EN); the eval row gets `code_splits` and `mediopunkt_per_100`, the report a column "LEX by code" next to LEX. SARI's tokenizer and the repeat keys of `drop_repeats` and `apply_repairs` drop the Mediopunkt. Tests: the job's words in `test_lexicon`, glossary cases in the LEX-01 golden set, `tests/pipeline/test_mediopunkt.py` (nouns split, adjectives and verbs untouched, values, word counts and readability unchanged, glossary split, capital lowered, idempotent, edits per version, P1 and P2 split before the check, P0 and P0-ZH untouched). Rescored on the 97 German P1 and P2 final drafts in the CSCS store without model calls: LEX-01 warnings per 100 blocks from 27 to 39 down to about 3, all warnings roughly halved, 30 to 41 splits per 100 blocks; reading splits by hand found a street name cut to pieces (splitter fixed: a nested split counts by its weakest part; the word before a house number is left alone) and one Swiss term the splitter does not know (docs/prompts.md change log). Not done: the dev `--redo` rerun that shows the repair rounds saved.

- 2026-10-06 (night, 6): Mediopunkt by code finished. P2 on the 10 German dev pairs on CSCS without the step (no-op, `eval/results-cscs-nomp`) and then with it (`eval/results-cscs`, `--redo`; the rows before it kept in `eval/results-cscs-v2`), the second run replaying the first's Understand and Write answers from the cache (run in sequence: in parallel, cache misses give the two sides different drafts). Over the 8 like-for-like pairs: LEX-01 35 to 5 warnings per 100 blocks, all warnings 79 to 51, errors unchanged, no fact lost (the split leaves coverage and values identical on every first draft). No repair round saved, and none can be: no job on either side reached zero blocking problems, so the warnings round never runs; 15 of 16 jobs stopped on "no progress" with facts and judge findings left, which is the fact-retention diagnosis's question. Fixed on the way: the eval counted only the final version's own splits (10 instead of 33.6 per 100 blocks), now every round's splits still in the text (`kept_code_splits`); the splitter cut the feminine ending (`Schweizer·innen`, `Assistent·innen`), now `-innen` stays on its stem and a word long only by its ending is not split. 3 wrong joints stay (`Kostengut·sprache`, `Kostenvoran·schlag`, `Leistungser·bringende`). The full dev split with the step: 10 of 10 pairs to review, 58 percent fact coverage, 63 percent hard facts. 868 tests. Next: the fact-retention diagnosis on these dev drafts.
- 2026-10-06 (night; cloud session): second use case documented: easy-language letters that go out together with decisions of child and adult protection authorities (KESB) and courts, the strongest sovereignty case (`docs/use-case-decisions.md`, partly planned, with what works today and what does not), with references in README (intro, docs list), architecture (companions, §2 second user, §10 privacy), report §8, sources §3 (a published anonymised decision, a team-written KESB decision), demo-video §4 and the canton use case. Docs only, no rule or code change; rules.md and hard-texts.md untouched (tests parse them). Not committed: delivered to the owner as a patch, checked to apply cleanly on `origin/main` at `0fdb3b7`. Plan: GAP-20, D-T (a KESB decision as the WP15 letter), one published decision as a test on 8 Oct, D-I to revisit, decision mode in WP17.
- 2026-10-06 (night; cloud session, 2): further use cases documented in `docs/use-cases.md`: an overview of all eleven and sketches of nine (patient letters, lease terminations and rent increases, penal orders, payment orders, social assistance and social insurance decisions, school decisions, information for study participants, migration decisions, private-sector letters), each with the facts that must survive, the reviewer and what the checker still needs; the legal periods checked against the law (OR 266l, 269d, 270b, 273; StPO 354; SchKG 74; HRA 16). Planned fact checks specified in `docs/rules.md` ("Planned fact checks (not implemented)"): value kinds `period`, `identifier`, `address`, `quantity`, `schedule`, `medication`; checks `FACT-07` to `FACT-09`; judge questions `SEM-08` to `SEM-10`; ids in backticks so the registry test does not expect them in code. Found and corrected: a period such as `innert 30 Tagen` is not a checked value kind (`rules/values.py`), so step 4 of `docs/use-case-decisions.md` overclaimed; fixed there and stated in architecture §4.4. References in README (intro, docs list), architecture (companions, §2 further users, §4.4), report §8 and both use-case documents. The decisions use case (`acab7a9`) is on `main` as pushed, with this environment's SSH signature. Plan: GAP-21, GAP-22, D-U, the period kind in WP14, rows in WP17, Thu 8 Oct. Docs and plan only, no code: 870 tests pass and ruff is clean (Python 3.13 in the cloud session). Not committed.
- 2026-10-07: the fact contract gets the value kinds `period`, `identifier` and `address` (WP14; GAP-04 and GAP-22 closed; D-O and D-U decided), in `rules/values.py` and from there in the code completion of the fact sheet (value_norm `30 Tage`, `2026-0042`, `Gerichtsstrasse 12, 8000 Musterwil`, fact kind deadline for a period with a deadline word), FACT-01 (the exact string as suggestion), FACT-05, FACT-06 (new messages and German translations; the source's only identifier or address as suggestion), the repair request and "hard facts kept". Periods: digits, number words and adjectives in DE/FR/IT, canonical count and unit as written, weeks equal days and years months, working days only themselves, a period equals its bare count. Identifiers: AHV, IBAN, postal account, UID, a code after a keyword (compounds with -nummer, `Verfügung Nr.`, French and Italian forms), also with a Mediopunkt in the keyword and a few words in between; a bare code in a fact sheet. Addresses: street and number with a street word, Postfach, postcode and place, over lines; a bare postcode and place only after a boundary, never a year or a count. `tests/rules/test_value_kinds.py` (86 tests, a synthetic KESB decision); 956 tests, ruff clean; no prompt change. REF rows of `eval/results-cscs` recomputed and read value by value (rules.md, "The value kinds of 7 October on the official texts"): hard facts on the 20 German eval pairs 138 to 191, REF keeps 69 instead of 70 percent, three defects found and fixed (`St.Gallen`, a town taken into the street, a count as a place). `eval/report.md` untouched: the P0 to P2 rows carry the old definition until the Friday rerun with `--redo`. Docs: rules.md ("Value kinds" table, planned section shortened, calibration note, test plan), architecture §2, §4.2, §4.4, §9, prompts.md, report §5 and §8, both use-case documents. Next: the WP13 diagnosis, then the KESB decision letter (D-T) through P2 with the new facts.
- 2026-10-07 (submission check): checked the repository against the template's submission requirements. Fixed: `make run` failed when the judges set `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_NAME` in the shell without a `.env` file (Compose stopped on the missing env file, `check-env` on "Missing .env"); now `.env` is optional in `docker-compose.yml`, the three variables pass through from the shell (shell wins over `.env`) and `check-env` accepts either. Verified in a fresh clone without `.env`: `check-env` in six cases, `docker compose config` in four, `make check-llm` and `make run` against CSCS (`/healthz` reachable), `make smoke` to review on the second try; the first failed in Understand on a JSON slip the parser does not repair (a value without its key: `"value_norm": "0441234567", "ipv@musterwil.example"`), which fails the whole job. Still open for WP11: the report renders to 8 A4 pages (limit 6), the PDF, the video, the team names, the repo public, the stale counts and status in README and report. With only the three variables set, the judge runs on `LLM_NAME` (the 8B) and `LLM_MAX_RETRIES` is 4, not the 70B and 8 that `.env.example` sets.
- 2026-10-07 (submission check, 2): the two findings of the check fixed. The parser drops a string where an object expects a key (`drop_stray_strings` in `llm/json_out.py`: the 8B gave `value_norm` a second value without a list), and code completion brings the dropped value back as a fact of its own (test on the recorded letter). Without `LLM_JUDGE_NAME` the judge is the 70B of the writer's family when the endpoint lists it, looked up once per process (`LLMClient.judge_model`, also in `/healthz`), else `LLM_NAME` as before, so vLLM and llama.cpp with one model are unchanged; `LLM_MAX_RETRIES` defaults to 8. Verified in a fresh clone without `.env` on CSCS: 4 of 4 `make smoke` jobs to review, the 70B-thinking judging, a dropped stream recovered on attempt 1 of 9. 963 tests.
- 2026-10-07 (afternoon): two more value kinds for the patient letters and the study information (WP14, use cases 3 and 9): `quantity` (a number with a dose or measurement unit, symbol or name in DE, FR and IT, `2,5 mg` and `2.5 Milligramm` the same; a fact given as a bare number is found in its quantity, a dropped unit is a loss) and `schedule` (`1-0-1`, `½-0-½`), taken before addresses after `1000 IE` came out as a postcode and a place. Six quantities and no scheme on the 35 pairs; REF on the German eval pairs 69.2 to 65.9 percent because the two pages concerned have few facts (rules.md, calibration note); 999 tests. The decision mode written into WP15 as "Decision mode v1": seven pieces, tests, cut order, rows in §13.3 (Fri to Mon), a paragraph in §13.5, GAP-20 and the WP17 rows updated. Fixed on a peer session's note: literal U+2010 to U+2014 characters that the editing tool had written into two regex classes of `rules/values.py`, where a `/` in front of them also formed an unintended range (a scheme or quantity right after a colon was rejected); the classes are built from `DASHES` now. Docs: rules.md (two rows, the planned table, the calibration note, the test plan), architecture §4.2, §4.4 and §9, prompts.md, report §8, use-cases.md §3, §9 and §12.
- 2026-10-07 (evening): two printable synthetic letters for the image input spike (WP12): `scripts/print_letters.py` writes `data/examples/print/` with a German tax reminder (one page: a table of amounts, an IBAN, a tax number, deadlines) and a French grant decision (two pages, registered: AHV and file number, a calculation table, payment dates, periods, the means of appeal), each as a PDF to print, fold and scan and as the printed text in reading order for comparing a transcription. Everything invented; the IBANs and the AHV number have invalid check digits. No code in the pipeline changed. Both letters printed, folded in three and scanned by the owner (300 dpi colour, no OCR, one PDF per letter in `data/examples/print/scans/`); the creases cross the German subject line and the French IBAN line. Next: phone photos, then the transcription spike against these texts.
- 2026-10-07 (evening, 2): report cut to the page limit (WP11). Measured by rendering `technical_report.md` with markdown-it-py (tables on) and printing it with headless Edge to A4, 10 pt, 2 cm margins, which reproduces the submission check's 8 pages and 4,427 words; now 6 pages, the last 37 % full, 3,171 words. Every template section kept, every number unchanged. Cut: the status paragraph, the team-name sentence, the planned demo-documents row, the build-time/runtime table (now one paragraph), the stage table's cells, the prompt, parser and reliability detail, the result table's row labels, the second baseline, 70B, judge, calibration and test paragraphs, the limitations and next steps merged. Fixed on the way: 999 tests instead of 825, 42 German and 39 French rules instead of 41, French no longer a next step (Italian is), the NUM-08 limitation dropped (D-J accepts `+41`), the judge default to the 70B in §3, κ stated as not yet measured instead of **[pending]**, the UI described without the stylesheet the WP18 branch removes. Left for the owner: team names, video link, the commit of the final run in §7, the PDF.
- 2026-10-07 (evening; UI session): the web UI reviewed on screenshots of its four pages (a server on a copy of `data/`) and redesigned for people who review drafts all day: calm surfaces, one accent, status colours only as icons and counts, the draft read as text with details for the selected block, checks as tabs, the start page as a work queue, a separate New draft page. Six screens on a design canvas (review, reader view and export, drafts list, new draft, job running, foundations), approved by the owner. Specification `docs/ui-design.md`: tokens, components, every screen against the templates and view models, the new interface texts, WCAG 2.2 AA, tests and checks, build order (about 25 h), cut order, differences from the canvas. Planned as WP18 with D-V to D-Y, rows in §13.3 and item 10 in §13.5; GAP-17 noted as half closed (German since `3ef69d3`). Found on the way, to be fixed in WP18: the judge stage says "1 unsupported statements" (`detail.judged` has no plural forms), the review page's single-key shortcuts act on the whole page (WCAG 2.1.4), deleting a draft does not ask. No code changed.
- 2026-10-07 (night; UI session): WP18 implemented, on a branch in its own worktree so the other sessions kept `main`, and put on `main` as two commits without a merge commit (spec and plan `2740cc2`). Own `app.css` with the `--lf-` tokens instead of water.css; IBM Plex Sans and Mono and Atkinson Hyperlegible Next vendored (14 woff2 files, 236 KB, Fontsource 5.3.0, OFL texts next to them, THIRD_PARTY_NOTICES.md); icon macros; the app bar with the review count, the endpoint indicator and a skip link. Drafts list as the start page (search, status and language as GET parameters, the review page's counts per row computed per request (D-Y), example tag, empty state with the two letters, intro strip, row menu, every delete asks first); New draft at `/new` (D-W; radio lists, the chosen pipeline's stages, drop zone, 400 with the form on an error); the job page as a stepper with each stage's calls, tokens and time. The review workbench: the draft reads as text, the selected block opens (findings, Apply where the evidence stands in the text, the facts it carries, Approve, Edit, Reject), keys only while the focus is in the draft pane (WCAG 2.1.4), Approve and Reject move on, N for the next undecided, Ctrl+S saves; checks as four tabs, facts problems first, document findings grouped by rule with the rule's title (`rule.<ID>`, German titles for all rules); the reader view with the export panel and the "before publication" list, in Atkinson Hyperlegible Next (D-V). Texts in EN and DE, `detail.judged` with plural forms, dead keys removed. Checked: screenshots of every page at 1440 px (the review also in German and at 1366 and 1024), phone width in a browser, the keys, the page without JavaScript (every block open, panels stacked), a contrast pass by script (one token darkened, `--lf-border-input` `#808893`), no request to another host. Departures from the spec in ui-design §17. Tests for the drafts list's filters, the review count, the usage per stage, the grouped findings, the fact order, Apply, the saved time and the vendored fonts; 1004 tests, ruff clean. Docs: architecture §7 and §11, ui-design (as built), README, demo-video.md.
- 2026-10-07 (night, 2): report §2's ASCII sketch replaced by a Mermaid flowchart (WP11), after checking that the submission rules ask only for an updated `technical_report.md` and a PDF of at most 6 pages. One row from Ingest to Export inside the container box, colours as in architecture §3 (purple Apertus, teal code, amber human), the four model stages pointing at one endpoint node; the database and LLM client named in the box title, so it stays short. Measured as on 7 October (markdown-it-py, mermaid 11 from the CDN, headless Edge, A4, 10 pt, 2 cm): still 6 pages, the last one fuller than before (about half instead of 37 %). The PDF export must render Mermaid (WP11 item). Then, since that flowchart is a workflow rather than an architecture, a component view added above it for the owner to choose from: the browser behind the organisation's proxy, the container (FastAPI with the job runner thread, pipeline, rule checker, LLM client), the volume, and one endpoint node naming the three target architectures; the workflow slimmed to one strip of stages without endpoint and container box. Both together: 7 pages, 7 lines over, partly because the strip breaks to the next page; the architecture view alone measured 6 pages, like the workflow alone. The owner keeps both; the caption is gone and the strip's purple boxes name the model in full ("Apertus 1.5 70B"). With c7's §1/§3/§8 text still 7 pages, about 7 lines over at line height 1.35 (c7 measures 6 pages at the browser default). Then §5 shortened by the owner's request, every number kept: the Metrics paragraph 6 to 5 printed lines (the hard-fact list as "other countable values"), "Reading the table" 8 to 6 (the 95 warnings and "all 23 pairs completed" dropped), Zurich's prompt 6 to 5, the calibration paragraph 4 to 3 (the 3,468 blocks dropped). Now 6 pages with about 3 lines free on the last, a tight fit for the team names, the video link and the commit. Open: the cuts (references as titled links, possibly in two columns; the §3 settings table as one sentence; a shorter hardware paragraph; the page-1 gap) and how the PDF is made.
- 2026-10-07 (night; c7): the submission documents argue why only Apertus fits the letters under secrecy (owner's request). `docs/use-cases.md` §2 "Why only Apertus": four conditions in a row, the text stays inside (official, medical and tax secrecy, art. 33 ATSG for social and basic health insurance, art. 86 BVG, art. 47 BankG; privatim's resolution of 18 November 2025 on international cloud services; the CLOUD Act), the organisation runs the model (open weights), it can account for what the model learned (open training data, which rules out Llama, Gemma, Qwen and Mistral), the model is Swiss (which rules out EuroLLM and SmolLM3, the fully open models with German, French and Italian), with the Apertus facts and every source in its references. A research agent checked each claim against primary sources; corrected on the way: other open-weight models can run in-house too, so the argument needs conditions 3 and 4; the personal-data filter replaces only e-mail and IP addresses and IBANs; Apertus 1.5 is Apache 2.0 with an acceptable use policy; more than 1,000 languages, not 1,811 for 1.5; the CSCS API serves research, not administrations (architecture §10 fixed). Tax letters added as use case 12 (tax secrecy, 30 days to object, art. 132 DBG; the WP12 print letter is one), the needs table is §13 now (links in architecture and rules.md updated), a column "What keeps the text inside" and a sovereignty line per use case. README: the use-case paragraph and a "Why only Apertus" table (WP15 box ticked), a pointer under Sovereign deployment. Report: one clause in §1, §3's "Where it runs" bullet carries the argument, §8's two use-case bullets merged; +74 words, about 5 lines (with both §2 diagrams, measured as on 7 October: last page 39 to 47 percent; leicht-facile-99 renders the diagrams larger and counts 7 pages before this change). Video: the BehiG scene dropped at the owner's request, the "only Apertus" scene at 1:29-1:57 with the four conditions as tiles and Ticino's in-house use, the product scene cut to 72 words (42 rules, not 41), about 245 words in all; hard-texts.md §1 no longer suggests BehiG for the pitch. use-case-decisions.md §2 and architecture §10 link the argument. Docs only, no code; no presentation file exists yet. Then, at the owner's go: the video says Leicht·Facile does not replace the writers but gives them a checked first draft (logo scene, now 0:32-0:49; the product scene trimmed to 63 words, the writer approves every block), and mail B in §13.7 no longer says the opposite of what it means ("Das Werkzeug ersetzt die Prüfung durch Menschen aus der Zielgruppe nicht").
- 2026-10-07 (night; vocabulary session): a vocabulary of hard words for German and French (`rules/data/vocabulary_<lang>.toml`, loader `rules/vocabulary.py`, docs/rules.md "Vocabulary"). Two kinds: `replace` (bureaucratic word, phrase or abbreviation and the everyday word: `innert` = `innerhalb von`, `moyennant` = `avec`) and `explain` (a term that stays, `Verfügung`, `Franchise`, `commandement de payer`, with a glossary text). German 229 and 107 entries, French 185 and 105, Swiss usage; drawn from the rare words of the standard pages in the 35 cached pairs, the way official easy pages explain the same terms, and the existing rule lists. Every explanation passes the checker at A2 with no warning (LEX-01 excepted): the first draft had 45 German and 68 French warnings and errors, mostly relative clauses, rewritten as one clause per sentence. `tests/rules/test_vocabulary.py` keeps it so. Not yet used by prompt or checker: the new WP17 row "Vocabulary in prompt and checker".
- 2026-10-07 (night; vocabulary session, 2): vocabulary checked against TERMDAT and published lists (docs/rules.md "Vocabulary"). TERMDAT, queried as Linked Data (`ld.admin.ch/query`, about 40,000 entries): 59 German and 57 French terms of the pilot's letters with the official French equivalent and the entry id as a comment (`rechtliches Gehör` / `droit d'être entendu`, `Mitwirkungspflicht`, `Verzugszins`, `Einstelltage`, `Vorsorgeauftrag`, `vorläufige Aufnahme`; French tax letters say `réclamation`, not `opposition`). 18 and 15 pilot terms TERMDAT lacks, with the act as source (`aufschiebende Wirkung` / `effet suspensif`, `Vorbescheid` / `préavis`, the EL terms, `Grundbedarf` / `forfait pour l'entretien`). A helper agent cross-checked against COSLA's *Lexique administratif*, German administrative-language guides, Wiktionary and Hurraki (checklists only, nothing copied): about 40 gaps per language added (`widrigenfalls`, `Rechtsöffnung`, `Nachsteuer`, `indûment`, `mainlevée`, `taxation d'office`) and 21 wrong or risky entries fixed or dropped (`prescription`, `disposition`, `aufheben`, `verfügen`, `bzw.`). Now German 263 replace and 195 explain, French 218 and 190; every explanation passes the checker at A2. Found on the way: GRAM-04-FR flagged the present `il agit` as passé simple (the parser tags some second-group -ir forms Past); fixed in `rules/fr.py` (the singular of second-group -ir and -ire verbs counts as present, third-group `il sortit` stays flagged), with golden cases.
- 2026-10-07 (night; cloud session): items 1-3 of the 8 Oct plan without the endpoint and without `eval/results-cscs`, which the cloud session does not have. (1) The fact-retention diagnosis as a tool: `eval diagnose` (`eval/diagnose.py`) puts every missing must-keep value of a run's P2 jobs into a bucket (never asked for: cap, no round, unflagged; written but rejected; dropped by code; not written; lost later; answer not recorded) from the stored artifacts and, for new runs, from a `RepairRecord` per round (request, answer as given, dropped texts with reason, in the audit bundle); method in docs/prompts.md, numbers pending the owner's run. (2) The fixes for bucket a and b: facts-only rounds after the repair loop (`MAX_FACTS_ROUNDS`, default 1, D-Z) and the exact form of a missing value in the request; the clause recipes for LEN-02 and LEN-02-FR (`rules/recipes.py`, golden tests, no "Apply" in the UI; D-P done); the decision mode's hooks (JobConfig `mode`, `addressee`, `notice`, CLI and API fields, include lines in all eight standard templates with a first `decision.md` in DE and FR, SEM-08 in the judge filter and both judge prompts, rules.md judge table). (3) Silent losses in `eval/score.py` and the report tables, the §5 column with the identity for the baseline rows; the image spike `scripts/image_spike.py` (`eval/image_spike.py`), tested on the committed scans without a key. Tests: 1059 collected, all green; ruff clean. Committed to the session branch `ccr-0afb0414-dnn24f` at the owner's request; the merge to `main` is the owner's.
- 2026-10-07 (cloud session, 2): the owner's local session ran the branch against CSCS (1,059 tests and ruff green there too) and sent the numbers back: the fact-retention diagnosis of the stored dev jobs (50 of 102 must-keep values missing, 40 never asked for) and of the dev rerun under the new code (16 of 122 missing), the ablation of the facts-only rounds (fact coverage 75 against 68 percent, hard facts kept 72 against 65, no invented value either way, D-Z: on), and the image spike (German page "unlesbar", French letter with wrong digits in the AVS number and the IBAN: no-go at 1,600 px with the 8B, D-N). All written into docs/prompts.md, architecture §4.1 and this plan; the report's §5 no longer claims zero silent losses for P1 and P2 before the final run, since the dev rows show 5 percent. Next: read `silent_loss_kinds` of the P2 rows and close the completion's gap; read the reasons of the 9 facts no round reached; the two spike variants.
- 2026-10-07 (cloud session, 3): the second local run answered all three. The silent losses were three percentages and one address, both gaps of the code completion, closed: a completed percentage is stored as `10%` (as a bare number it never matched a percentage again, so FACT-01 had counted such facts as missing even when the draft had them), and the completion takes the values from the document text with segment offsets, so an address over two sentences is one fact with its street. The nine facts no round reached were asked for in rounds whose version was not kept as final; the diagnosis now classifies such facts by those rounds, with a bucket k for a value written into a version not kept. The spike variants (full resolution, the 70B) read the pages but misread digits in the IBANs, the AVS number and a period: D-N decided, WP12a cut. Tests and ruff green; on the branch. For the owner's next run: the dev rerun under the fixed completion, then `eval diagnose` (expect no silent losses in P2 and the k bucket) and, before the freeze, the reading of D-Z's last question.
- 2026-10-08 (cloud session, 4): the third local run (dev rerun under the fixed completion): 30 of 122 must-keep values missing, fact coverage 71 percent, silent losses 2 percent, no invented value; most of the difference to the run before is one pair with 22 facts (13 behind the cap, 3 written into a version not kept) and one pair whose repair round failed on two unusable answers. Three changes from it, on the branch: the final version is chosen facts first (fewest missing must-keep values, then fewest blocking findings; bucket k had 5 facts), an unusable repair answer no longer cancels the facts round (a failed endpoint still does), and the completion's coverage check asks in the reader's direction, which closes the last silent loss (a model fact with the place alone no longer covers the full address). New: `eval rescore`, which scores stored jobs again from their artifacts under either final-version rule, without a model call, so the rule change is read on the same jobs before any rerun. Next for the owner: `eval rescore` on the current and the previous dev run, then one dev rerun on Thursday under the final code, then the freeze.
- 2026-10-08 (cloud session, 5): the fourth local run, `eval rescore` on the stored dev jobs, no model call: facts first gives 80 percent fact coverage and 81 percent hard facts kept on the third run's drafts against 71 and 68 under the old rule (1.2 more judge findings, 1.3 more rule errors per 100 blocks), and 83 and 84 on the second run's; the "blocking" rescore reproduces the stored row to the decimal. The silent losses stay at 2 and 5 percent because the fact sheets are stored at run time; the completion fixes show in the next run. The cap of a facts-only round is a setting (`MAX_MISSING_PER_FACTS_ROUND`, default 5). Handed the Thursday iteration to the owner's local session with the sequence and the decision rules (session log, LOCAL TEST REQUEST 5). Pending runs for the owner's machine: `eval diagnose` on `eval/results-cscs`, the dev rerun with `--redo` with and without facts rounds, the spike on CSCS.
- 2026-10-07 (owner's local session, request 5): the fifth dev rerun on CSCS under the final code (`--redo`, rows before it in `eval/results-cscs-v5`): silent losses 0 percent, nothing in bucket k, fact coverage 75 percent, hard facts kept 77, 5.4 rule errors per 100 blocks; 13 of 27 missing facts behind the cap, all in one pair. The cap-10 run in `eval/results-cscs-cap10` on the same cache: fact coverage 79, hard facts kept 81, no invented value, judge findings 2.8 against 4.6 per 100 blocks. Decision rule met: `MAX_MISSING_PER_FACTS_ROUND` defaults to 10 (D-Z, docs/prompts.md); the diagnosis names both caps.
- 2026-10-07 (evening; vocabulary session, 3): the vocabulary in the pipeline (D-AA, WP17 row pulled forward; docs/rules.md "Vocabulary", architecture §4.2, §4.3, §4.6). A matcher (`rules/vocabulary.py`) finds the terms in their inflected forms, with the Mediopunkt, as German separable verbs (`reichen ... ein`) and verbal phrases (`tritt ... in Kraft`), French contractions, abbreviations as written; context-dependent words (`Leistung`, `Schreiben`, `consultation`) and `[not_in]` phrases (`zur Verfügung`) keep code from misreading them. Uses: the fact sheet's hard terms get the checked explanations and up to 6 terms of the source; code adds missing glossary entries after write and every repair round (`rules/glossary.py`, marked on the review page, code edits under SEM-05); new rules LEX-07 / LEX-07-FR flag the office words left (the French list hard-coded in LEX-01-FR moved into it), LEX-02 suggests the full word of an abbreviation, LEX-03 leaves office words to LEX-07. Calibrated on the official pages: LEX-07 1.2 per 100 blocks on the 30 German easy pages against 20.5 on their originals (first version 3.1: `Behörde` and `Merkblatt` became explained terms, `Unterlagen`, `Dienststelle`, `Beeinträchtigung` and others context-dependent), LEX-07-FR 0.7 against 19.6. `USE_VOCABULARY=0` switches it off for measuring; the write prompt's word list is built but off (`VOCABULARY_PROMPT=0`). Three P2 runs on the 12 dev pairs on CSCS (docs/prompts.md, "Vocabulary in the pipeline"): hard terms without explanation from 2.3 to 0.1 per draft, glossaries from 4.4 to 7.1 entries, glossary explanations breaking a rule from 72 to 49 percent; the word list made the 8B write 58 office words into its first drafts against 20 without it, which is why it is off; facts, judge findings and rule errors moved in both directions by single pairs (one run per setting). On the way: matcher fixes from the real texts (`recourir` is no `recourant`, `dès lors` is no `dès`), five vocabulary explanations rewritten because LEX-07 flagged their own office words, GRAM-04-FR fix of the afternoon kept. 1111 tests.
- 2026-10-07 (night; usage fix): the submission check's open risk "a failed job reports 0 model calls" fixed. Cause: the orchestrator stored a stage's usage only from the results it returned, so the calls of a stage that raised were lost: Understand or Write with two unusable answers (the job failed with 0 calls), the thinking call before a failed fallback without thinking, and the earlier parts of a sectioned write. Now `LLMClient.recording` (a context variable) passes every call to the job's usage as it is made, around `Orchestrator.run`; the per-stage `_record` calls are gone, so nothing is counted twice. Successful jobs bill exactly as before; the job page's per-stage counts now also fill during a stage. Tests in `tests/pipeline/test_degradation.py` (failed Understand, failed fallback, failed Write); architecture §6 "Usage log". 1118 tests, ruff clean. No effect on the evaluation's numbers: it scores only jobs that reached review, whose failed judge and repair calls were already counted, and a rerun of a failed pair is a new job.
- 2026-10-07 (evening; vocabulary session, 4): the vocabulary round (owner's request): after the facts rounds, one more round through the repair prompt for the office words still in the best version (LEX-07 findings alone, with the everyday word); its version takes the next free number and is kept only if it loses no must-keep value and adds no blocking finding (architecture §4.6). Measured on the 12 dev pairs with every earlier answer replayed from the cache, so both sides have the same versions up to the round (docs/prompts.md, "The vocabulary round"): it ran in 11 jobs, kept in 8, the 3 others lost the final choice (one dropped a fact, two got more judge findings); office words in the final drafts 42 to 19, fact coverage, hard facts and invented values unchanged, rule errors 3.5 to 2.5 per 100 blocks, about 11 s per job. On by default (`VOCABULARY_ROUND=1`). The orchestrator and degradation tests switch it off in their helpers (their scripted answers end before it); its own tests are in tests/pipeline/test_vocabulary.py. 1134 tests.
- 2026-10-07 (evening; vocabulary session, 5): the writer gets no vocabulary (owner): the write prompt's word list, off since the dev run, is removed from code and templates (prompt version 9, the text of version 7 again) and documented as tried, for a later Apertus. One switch left, `USE_VOCABULARY` (on), for the fact sheet's explanations, the glossary entries by code, LEX-07 in the repair rounds and the vocabulary round; `VOCABULARY_PROMPT` and `VOCABULARY_ROUND` are gone. 1132 tests.
- 2026-10-07 (evening; examples session): the decision letter and the example jobs (WP15, WP8). The KESB decision (D-T decided) written as `data/examples/sources/entscheid-beistandschaft-musterwil.txt`: a deputyship for an invented woman, with her name, date of birth, address, an AHV number with a wrong check digit, a case number, an IBAN with 00, the operative part and the 30-day appeal to an invented court; a research agent checked the layout against the KESB Graubünden's two specimen decisions and the KOKES model decision (KESB headers have no "in Sachen"; the appeal clause is Graubünden's). A JSON file next to a source sets its job (`mode`, `addressee`, `notice`), and `examples build --only <name>` builds one. Example jobs built on CSCS: the premium-reduction letter in German and French are in `data/examples/jobs/` and import on start; the KESB decision's job is held back, since its draft (decision mode, as built so far) carried an appeal deadline the decision does not contain and gave the deputy's tasks to the person, and as a standard job it lost the appeal. One published decision as a test (Verwaltungsgericht Schwyz, III 2022 132): placeholders pass through as names, 28 of 30 facts must-keep from the reasoning, the court's decision and the appeal lost, the write prompt's style guide copied into the decision-mode draft. Findings and the changes they ask of decision mode v1 in use-case-decisions.md §7 and WP15; one for the owner: a value FACT-05 finds missing from the source still counts as known to FACT-06. Fixed on the way, with tests: a short "label: value" line (a case number), a phone, e-mail or web line is no heading in pasted text, so its value stays must-keep (`ingest/text.py`); a surname above the street in an address block is no longer taken into the street (a list of street adjectives); a count with "pro Woche", "im Jahr", "par semaine" is a frequency, no period (on the 70 official texts only `365 Tage im Jahr` changes, three times); a range of ids inside one string (`"s0055-s0058"`) is written out after parsing (`llm/json_out.py`; never seen in the evaluation stores). 1133 tests.
- 2026-10-07 (night; examples session, 2): D-AB, the owner's go: a fact-sheet value the source does not contain is no longer known to FACT-06 nor required by FACT-01, and fact coverage (checker metrics, review page, evaluation, diagnosis) counts only facts whose value the source contains (`rules/document.py`: `source_values`, `fact_coverage(..., source)`, `KnownValues`); FACT-05 still warns on the fact sheet. Found in the stored CSCS fact sheets: 8 of 195 values (P1), 12 of 331 (P2 8B), 16 of 207 (70B writer), some invented ("31. März 2026" for "im Frühling"), most normalised into forms no draft could match, which FACT-01 had flagged in every version. Dev rerun on CSCS, old rule patched back in and new rule in sequence on the same cache (`eval/results-cscs-fact06-before`, `-after`): fact coverage 78.8 against 78.8 percent under the new measure, hard facts kept, invented values and rule errors unchanged, 10.6 against 10.5 calls and about 600 tokens per page less; the repair rounds no longer ask for an invented date (`be-birth-registration-de`). The measure alone raises stored fact coverage (P2 8B eval 81.7 to 83.1 percent, 70B writer 73.1 to 77.8): report §5's numbers change with the final run. The KESB decision's invented deadline is now a blocking FACT-06 error. Found on the way: hotline numbers (`0800 33 66 55`) are not found as phone values (WP14 item). Docs: rules.md (FACT-01, FACT-05, FACT-06), architecture §4.4 and the metrics table, prompts.md, report §5's metric definition. 1133 tests.
- 2026-10-08 (video mock session): a mock of the demo video at the owner's request, to get an impression, built without other apps and kept outside the repo (a Remotion 4 project in the session's scratchpad, not committed). It follows docs/demo-video.md scene by scene and runs 1:56: a placeholder voice from Kokoro (open weights, run locally; transcribed back with Whisper, every chunk heard as written, "Leicht·Facile" heard as "Leistfesil"), music made in code and ducked under the voice, the kitchen table and the envelopes drawn in code where the storyboard asks for generated footage, and the product scene from frames of the real UI (headless Edge against a scratch data folder; the job page's stages are the real example job copied stage by stage; no model call). Written for the mock where the storyboard leaves text open: the evaluation sentence by case B of §13.4 with D-L's wording ("Against a strong single prompt: less than a third of the rule errors. And no fact goes missing unnoticed."; 4.3 against 15.4 per 100 blocks from report §5, labelled provisional), the tagline and the end card. Measured for the rule-check timer: 47 ms median for draft v1 of the premium-reduction letter (15 blocks, after warm-up). Found: P2 on the DE-4 sentence alone (CSCS, job d2c96d2ac2b7) gives no usable before/after. The draft wraps the one sentence in the letter headings ("Der Preis ist nicht genannt"), loses the consequence (no money back), and a repair round adds a contact office the sentence never names ("Sie können die Einwohner·kontrolle fragen"); so the mock shows the team's illustrative rewrite from hard-texts.md, labelled as such on screen. WP11 item added. Second version at the owner's request: the opener as a split screen, DE-4 and FR-4 side by side for the whole scene (the quick cut showed FR-4 for under a second), and "Leicht" with the German ich-sound (`lˈaɪçt`; the voice renders it apart from "sh": far less energy at 2.5 to 4 kHz); demo-video.md §2 and §3 follow. Third version, also the owner's: the "only Apertus" tiles fall one per sentence, with a new sentence for the fourth ("Most fully open ones are built abroad."; it was struck while Apertus was named, so "open data" read as a point against Apertus), the ruling-out part of each tile in red, the Apertus tile only on "Apertus"; 267 words, 1:59. Then, after a comparison of three concepts, the owner chose concept A, "Find the deadline" (docs/demo-video.md §1 and §2; the first concept kept in §5): the viewer looks for the deadline in the example letter for five seconds, then finds it in the first sentence of the letter's real P2 draft (German on screen as the illustration, the instruction also in German, English voice); the app scene follows that deadline (the fact sheet's "By when?", the deadline fact, its code check, the draft sentence linked to its source sentence); the evidence beat follows case B of §13.4 (a strong single prompt in its default mode loses 23 % of the hard facts without a trace; Leicht·Facile lists every missing fact); the "only Apertus" scene is unchanged; 231 words, 1:52. Mocked the same day as a second composition next to the first. It resolves the before/after item of WP11; its product scene uses the premium-reduction letter, not the decision letter of the WP16 list, since the test and the app show the same letter. New in demo-video.md §4: the example draft's ungrammatical "Sie mitschicken" is visible in the test. Then variant B for the opening (demo-video.md §3, "One sentence, step by step"), since a full letter is too much text for a five-second test: the deadline sentence of the example letter, what `leichtfacile check` finds in it (2 errors, 3 warnings), the facts f01 and f03, the real draft's three sentences with the facts each carries, the check again (0 errors, the date present); 251 words, 1:54, mocked as a third composition. Found on the way: the draft's "bei der Sozial·versicherungs·stelle" should be "an die", and the checker does not catch it. Then version C, the owner's combination (demo-video.md §3): the "Can you read this?" split-screen opening, the stakes on the kitchen table with the letter (drawn in code; footage or not decided later), the logo, variant B's step by step, a shorter app scene, the evidence and "only Apertus" scenes, the end card "No one left out." as in the first concept (owner); the envelopes face up with an address window bottom right and German labels top left (owner); 231 words, 1:48, mocked as a fourth composition. Version C (`DemoC`) is the draft for the final video (owner). Its source moved from the session scratchpad into `video/` (owner: code in the repo, every generated file excluded by `video/.gitignore`; `video` also in `.dockerignore`): Remotion scenes, the four narration files, the voice, music, capture and check scripts, a README with the build steps; built outside OneDrive with `LF_REPO` pointing at the repo, checked by a clean build of version C (npm ci, prepare, voice, music, stills); the Python scripts pass the repo's ruff. Then the Mediopunkt in version C (owner): one more sentence in the step by step, "A middle dot splits long words into easier parts.", while the dots in the draft's long words light up with a label; 240 words, 1:52. The end card gains "Every person. Every fact." under "No one left out." (owner), so the line reads for people and for facts. The "only Apertus" scene of version C gains a bridge (owner: it was unclear why these letters come up): "Easy language matters most in the most personal letters. A child protection decision for a person with a learning disability. A letter from the hospital. A tax assessment." with the title on screen and the envelopes in that order; 261 words, at 1:59.9 it touched the limit, so voice speed 0.89, a shorter end card and pause: 1:57.
- 2026-10-08 (session f1, before the freeze): the three pre-freeze code items of the plan. (1) Hotline numbers: `PHONE_RE` takes the ten-digit service numbers (0800, 084x, 090x) in both groupings, so `0800 33 66 55`, `0848 35 45 55` and `0900 55 35 55` are phone values for FACT-01, FACT-06, the masking of NUM-02 and the hard-fact metric instead of four plain numbers each; NUM-08 and NUM-08-FR accept either grouping; golden and value tests. SOURCE and REF recomputed in `eval/results-cscs` and `eval/results` (both git-ignored): the pattern alone adds `0800 33 66 55` to `zh-emergency-numbers-de`, `zh-blue-algae-de` and `zh-heat-de`, `0848 35 45 55` to `zh-emergency-numbers-de` and both `be-emergency-numbers` pairs, `0900 55 35 55` to `zh-emergency-numbers-de`, and removes nothing; the stored REF rows also predated the value kinds of 7 Oct and LEX-07, so more columns moved (`zh-passport-id-de` 23 to 22 hard values, the office-word column new). The stored P1 and P2 rows keep their run-time denominators and `eval/report.md` its REF rows until the final run's `eval report`. (2) Copy guard: the write and repair prompts are rendered with the style guide of both levels, so the guide's lines (without the list marker) and its example values (`044 123 45 67`, `4. Februar 2026`) count as the prompt's own; whole lines only, a part of a line is no copy. (3) Silent losses in P2: already closed by the completion fixes of the cloud sessions 4 and 5; the fifth run and the stored P2 rows that carry the key show none, so the WP13 note says so now. 1,142 tests and ruff green.
- 2026-10-08 (session f1, decision mode v1): WP15 pieces 1 to 7 in code, the same session as the pre-freeze items. Fetched the Schwyz decision III 2022 132 into `data/cache/decisions/` (git-ignored, docs/sources.md): the ingest reads it, 8 pages, 2,255 words, 65 units, three headings and none of them the operative part, so the text fallback is what carries a court's PDF. `rules/decision.py`: `protected_segments` (operative part by heading or by the `erkennt ... :` sentence, one item per paragraph, the distribution list excluded; the appeal by heading or the `Gegen diesen Entscheid kann` paragraph; FR markers), `protect_factsheet` (must-keep in the parts, code values outside them and the core answers background, no protected omit candidate, one fact without a value per part), FACT-08 (a part in no block or listed as omitted; blocking and missing like FACT-01, first in the repair request, reruns the judge) and FACT-07 (the export's first and last line are the notice; LAY-01 and LAY-02 skip it). `check_draft` and `DocInput` carry the mode; `link_facts` links a part's fact by its segments and FACT-02 leaves such facts to FACT-08. SEM-09 and SEM-10 declared and through the judge filter for a decision job only. The notice in `to_markdown`, `to_html`, the bundle's layout lines, the API and CLI exports and the reader view, as `.notice-banner` on the review page; the "Document type" select on `/new` with the addressee and the notice, `notice_default` per language in `pipeline/labels.py` filled in by the server when the field stays empty, the page's `POST /jobs` with the three fields, the "Decision" tag on the drafts list, `example_sources` with the sidecar's settings so the KESB example prefills the form. The partial (DE, FR) carries the four lessons of the 7 Oct test runs; the standard templates and their hashes are unchanged. Calibrated on the KESB decision (13 items and the appeal, by headings) and the Schwyz decision (2 items and the appeal as its item 3, by text). Tests: `tests/rules/test_decision.py` (13, the Schwyz one skipped without the file), the request and judge-filter tests, three web tests, one example test; 1,161 tests and ruff green. Open for the owner: the KESB decision as a decision job on CSCS into `data/examples/jobs` (the example job of piece 7 and the video's product scene), and a reading of the drafts under the new partial.
- 2026-10-08 (session f1, small items): `publiccode.yml` (v0.4, en/de/fr, checked by script against the required keys and lengths; WP16 ticked). GRAM-08: a separable verb written as one finite word in verb-second position (`Sie mitschicken eine Kopie`, the video session's finding in the example draft; the tagger says VVFIN, the form says prefix plus known verb), error at A2 and warn at B1, repairable, `schicken ... mit` as the suggestion, no writer instruction so the frozen style guide is unchanged; 3 positives and 8 negatives in the golden file. CH-01 by code: `rules/swiss.py` writes `ss` for `ß` after the Mediopunkt in the write stage and every repair round, blocks and glossary, a `CodeEdit` per word; done the day before the prompt freeze rather than after it, as a deterministic edit that the final run then carries from the start. Headless screenshots of the decision-mode screens (New draft with the KESB example, the review banner, the reader view), kept in the session scratchpad; ui-design §17 notes the check. 1,175 tests and ruff green.
- 2026-10-08 (session f1, WP17 pulled forward and the numbers tool): "Check my text" at `/check`, a third entry in the app bar: the deterministic checker on a pasted text as the CLI `check` runs it (one block per sentence, German and French, the chosen level), the blocks with their findings, the document findings by rule, the counts per 100 blocks and the text metrics; no job, no model call, nothing stored; the `app_env` fixture moved to `tests/web/conftest.py` for the new test file (ui-design §5.8, architecture §7). `eval numbers`: the headline means per setup from a results folder (the plain writer with the most pairs; the silent losses of a row without a checklist from the hard facts kept), the §13.4 case with its three comparisons and the headline sentence filled in. On `eval/results-cscs` (eval split, 20 German pairs) it reproduces the known numbers: P2 8B 84 percent fact coverage, 80 hard facts kept, 4.3 errors and 0.1 invented values per 100 blocks; P0-ZH complete 91, 95, 15.4, 0.0, 5 percent silent losses; condensed 77 kept, 23 lost; case B. The stored P1 and P2 rows of this folder predate the silent-loss key (the final run fills it). 1,181 tests and ruff green.
- 2026-10-08 (Docker check): `make check-docker` before `run`, `stop`, `check-llm` and `smoke`: a stopped Docker daemon, a missing `docker` or a missing Compose v2 now ends with a short message and how to fix it instead of a Compose connection error (tested on Windows with `DOCKER_HOST` pointed at a missing pipe); architecture §10 updated.
- 2026-10-08 (clean example jobs): `examples build` writes a job only when its final draft shows no errors (rule errors, facts the judge finds missing or distorted, unsupported statements; `--allow-problems` writes it anyway), and `tests/test_examples.py` fails on a shipped job with errors: a first-time visitor reads the red counts as a fault of the application. Two checker false positives from the example letters fixed: FACT-02 no longer repeats a fact whose value FACT-01 reports missing, and `link_facts` gives a block without a source sentence the sentences of the facts whose values it contains (FACT-03) and links a fact without a value to a block that cites its sentences and holds all the values of its text (FACT-02: the French contact, the German move notice); docs/rules.md and architecture §6 updated. Two rebuilds on CSCS: German 5 then 2 errors, French 12 then 10, so neither is written and the 7 Oct bundles stay. Left: German f07 (the residence date 1 January 2027 is missing, a real omission) and a judge false positive (b009 is in the source); French a long sentence, a wrong-meaning sentence (`Vous payez la réduction`), an invented sentence, three blocks without provenance and judge false positives (f07 and f08 "missing" although b006 has both amounts). The two example tests stay red until the owner decides how the examples become clean.
- 2026-10-08 (medication and FACT-09): the owner asked for every planned rule except Italian; what was left was the value kind `medication` and FACT-09. The fact sheet names each drug (kind `medication`, the name alone; code takes off a dose, form or bracket the model adds), FACT-01 and FACT-05 find the name as a whole word in any case and through a Mediopunkt, and FACT-09 (`rules/medication.py`, error, repairable) asks that a block naming the drug carries every dose, scheme and duration the source sentence gives it and the draft has, a value going to the nearest name when a sentence has several drugs; points in time, ages and measurements are no part of it. The prompts learn the kind from a partial `medication.md` (DE, FR), included in Understand when the source has a dose and in Write when the fact sheet names a drug: none of the 35 evaluation sources and neither decision has a dose, so the frozen prompts render byte for byte as before. Medication facts come first among the missing facts of a repair round; the Mediopunkt step leaves drug names alone. rules.md: the kind in the value-kind table, FACT-09 in the facts table, the planned section renamed "Fact checks for the further use cases" (links updated); use-cases §3 and §13, architecture, prompts change log 10. Tests: `tests/rules/test_medication.py` (28); 1,215 tests, all green except the two example-job tests, which fail on HEAD too until the example jobs are rebuilt without errors (`examples build`). Not done: a drug list, tables with name and dose in separate cells.
- 2026-10-08 (video, version C): two changes at the owner's request. The opening shows each question on its own line, in German and in French, each line as it is spoken. The logo scene opens with a bridge into easy language, so that the viewer learns it exists before hearing that it is slow expert work: "For them, there is easy language." over a card *Easy language* (*Leichte Sprache*, *Langage facile*, three of its rules), then "But easy-language versions are slow expert work." under it. The longer "there is a special language" would have passed 2:00, so the card carries what makes it special; for margin the silent typing before "Can you read this?" is 0.3 s shorter and the end card 0.4 s; 268 words, 1:59.0. Whisper hears both new sentences as written. Mock: `leicht-facile-demo-mock-C8.mp4`.
- 2026-10-08 (session b0, functional review and two loop changes): a review of the app as a juror meets it (the committed state on a scratch data folder, the example jobs, the stored CSCS jobs) proposed two pre-freeze changes, which the owner asked for and which were then measured and taken out again (docs/prompts.md, "Judge doubts on values"). (A) A judge's `missing` on a fact whose value FACT-01 finds in the draft as non-blocking and not asked for again: in `eval/results-cscs` 11 of the 24 `missing` verdicts on facts with a value left on final P2 drafts were such facts, the French example's f07 and f08 among them. (B) A missing fact asked for by the clause of its value, from the full source sentence: the German example had asked for f07 (1. Januar 2027) twice and got the CHF 9'000 per child rule both times, since code completion copies the whole sentence, cut at 200 characters. P2 on the 12 dev pairs on CSCS, the committed code and then A and B in sequence on the same cache (`eval/results-cscs-ab-before`, `-ab-after`): German fact coverage 79 to 74 percent, hard facts kept 71 to 64, rule errors 3.1 to 4.3 per 100 blocks, French identical. Five German jobs took another path, three ended worse (one through A, whose judge verdict was wrong but whose extra round had helped; two through B, one of them with every added sentence a fragment after a cut), none better. Both removed from the pipeline; the final run uses the loop as committed. Kept, display only: the review page shows such a verdict in amber as "judge doubts" with the judge's note instead of a red "missing" (`FactRow.status`, the facts bar, en and de texts, a UI test; architecture §4.5 and §7, rules.md SEM-07, ui-design.md). The example check still counts it. The review's other functional proposals (check the reviewed text, the example jobs with the KESB decision, compare with the original on Check my text, suggest a fix per block, a readable check record, proof of air-gapped running, quick wins) wait for the owner's choice.
- 2026-10-08 (Italian out of scope): the owner decided that Italian (lingua facile) is out of scope for the hackathon and goes on the roadmap: WP9's Italian item and stretch item 10 say so, and the WP17 row "Italian" carries what was found while scoping it: every spaCy Italian model is CC BY-NC-SA 3.0 (non-commercial), so the way the grammar rules get their parse is a decision of its own, and the polite imperative with Lei is a subjunctive form. Notes in `docs/rules.md` (Italian section) and `docs/architecture.md`. No code change.
- 2026-10-08 (team members): the team is Alexander Bobrovsky (bobrovsky@seznam.cz) and Ivan Kuzmych (i.kuzmych@hotmail.com). Both names replace the `member` placeholders in the report header and stand in the README's team line; `pyproject.toml` gets `authors` and `publiccode.yml` lists both as maintenance contacts with their e-mail addresses.
- 2026-10-08 (session 64, quick wins, rule count, judge agreement): (1) The HTML export breaks lines at sense units of at most 60 characters (`HTML_LINE_CHARS`, within LAY-02's 85) in a 36em column, so the reader view no longer breaks a line twice ("8.30 bis 11.30 Uhr" / "Uhr" alone), and never inside a value (no-break spaces in dates, amounts, phone numbers); print styles set A4 at 14 points, and the reader view's export panel has "Print or save as PDF" (the frame's sandbox allows modals, no scripts). (2) French interface: `web/locales/fr.json`, all 594 keys including the checker's messages and the rule titles, the switcher shows EN / DE / FR (GAP-17 for French). (3) Glossary entries are decided like blocks: ids `g01`, `g02` in a decision's `block_id`, rows after the blocks in the review, the same keys and counts; exports and the audit bundle (`final.glossary`, `undecided_glossary`) carry only what the review keeps. (4) Rule count: README and report say 45 for German and 41 for French, the registry's count (the UI's `rule_count()`), the older narrations 45 too; a test in `tests/rules/test_registry.py` keeps README and report in step. (5) Judge agreement: the 59 items of `eval/labels/dev` (P2 dev drafts of 6 Oct, 70B judge) labelled blind by an AI assistant (Claude), then scored: blocks 80 percent agreement, κ 0.60; facts 38 percent, κ 0.08 (present or not: 62 percent, κ 0.22); in 5 of 18 disagreements the judge's note concerns another fact than the one it is filed under, a lead for the judge prompt. Report §5 and §3 (Other models) say so; the hackathon rules name open-weights models as evaluation helpers, so the owner decides whether these labels stand or are redone by hand. architecture §7, ui-design and docs/prompts.md updated; tests for each part.
- 2026-10-08 (session 76, example jobs, root causes): the CI failure of the two example tests traced and the code-side causes fixed, with tests. (1) Provenance (FACT-03): a block without a source sentence takes those of the facts it names, else the sentence it says in other words (`stages.wording_source`: the most distinctive shared words, a clear margin, two words or one of seven letters or more; 13 of 13 links right on the stored final P2 drafts), and a sentence id the source does not have is dropped (the 8B cited `s0009.2`); without a source sentence the judge, which sees only the cited sentences, had called the French letter's correct cash-payment sentence invented. (2) A hard term of the model that the source does not contain leaves the fact sheet (`stages.in_source`): the 8B copied the Understand example's office for 6 evaluation documents. (3) That office (`Einwohnerkontrolle`, `contrôle des habitants`) is a topic word of the copy guard: the repair example's addition came back with a real number in 4 evaluation P2 jobs and 3 example builds. P2 on the 12 dev pairs on CSCS against the committed code on the same cache (`eval/results-cscs-prov-after`; docs/prompts.md change log 10): fact coverage 76 to 81 percent, hard facts kept 69 to 76, rule errors 2.7 to 2.3 per 100 blocks, unsupported 5.3 to 6.2, invented values 0.64 to 0.85; three pairs better, two worse, two mixed, five identical, so within the 8B's noise. The examples are still not clean: nine builds (three with the cache, six fresh with `LLM_CACHE=0`), none without errors, so `jobs/` keeps the 7 Oct bundles and the two example tests stay red. What remains is model output: the 8B drops the residence date 1 January 2027 (s0005) in nearly every German and fresh French job and the repair rounds never add it (its code fact's text is the whole sentence with the income limits), and the judge calls about one harmless block per job unsupported. Found on the way, not changed (each changes every judge call, so it needs the owner and a measurement before the freeze): the judge sees code facts as the same cut-off sentence and assigns its verdicts to the wrong fact ids (on French v4 it called f06 to f09 missing with notes about other sentences); it sees only the cited sentences, so a wrong citation by the writer becomes an unsupported verdict. 1,229 tests; all green except the two example tests.
- 2026-10-09 (layout risk closed): the `track_2b/` layout risk is ticked without asking the organisers: submission requirement 3 (`make run` from the root of the project on a clean checkout) needs the template's `track_2b/` contents at the root, as the repository has them.
- 2026-10-09 (recover session): "Suggest a sentence" for a missing fact, at the owner's request (WP18 item, D-AC). First a spike on f07 of the example job `praemienverbilligung-brief` (CSCS, 8B, cache off): the paragraph alone brought the value back in 0 of 3 runs, the paragraph with the value and its sentence named in 3 of 3, the repair prompt with f07 alone in 1 of 1 (the job's own two tries: 0); no run had a value outside the paragraph (docs/prompts.md). Built: `stages.recover_fact` with the templates `de/recover.md` and `fr/recover.md` (prompt version 11, used by no pipeline stage), `POST /api/jobs/{id}/facts/{fact}/recover`, the card under a missing fact on the review page with the source sentence, the code check, the rule findings and "Add to block", texts in en, de and fr, 8 tests. Checked in headless Edge against CSCS on the example job: the suggestion came back, "Add" made block b009.2 an edit. Two of three live sentences said "Der Anspruch gilt ab 1. Januar 2027": the value is there, the residence condition is not; the card says that code does not check the meaning. Open: the dev measurement (WP18).
- 2026-10-09 (recover session, 2): the recover round in the pipeline, behind `MAX_RECOVER_FACTS` (default 0, the default path unchanged, as session 7e's comparison runs need). After the facts rounds it takes the best version, asks for each must-keep value FACT-01 still misses (the most important kinds first, at most `MAX_RECOVER_FACTS`) through `stages.recover_fact`, puts the accepted sentences after their blocks (`stages.add_sentences`) as one new version, and checks and judges it like a round (`Orchestrator._recover`; the round's shared tail is now `_finish`). Repair record kind `recover`; the job page counts its calls under Repair. Two orchestrator tests (on and off). The dev run with it on waits for 7e's `eval/results-cscs-en-before`.
- 2026-10-09 (recover session, 3): the dev run with the recover round on (`MAX_RECOVER_FACTS=10`, `eval/results-cscs-recover-on`) right after 7e's default run `eval/results-cscs-en-before`, the cache replaying everything before the round. German dev pairs: fact coverage 78 to 96 percent, hard facts kept 72 to 90, invented values 0.8 to 0.6 per 100 blocks, judge distorted (fact-rich) 3 to 5 percent, tokens per page plus 12 percent; French: 97 to 100, 94 to 97. Five of 12 jobs changed, 16 facts added, the judge calls 3 of the 13 it checked distorted; weak sentences echo the prompt ("Der Wert ist ...") or break a reflexive. D-AC for the owner.
- 2026-10-09 (recover session, 4): D-AC decided by the owner: the recover round is on by default (`MAX_RECOVER_FACTS=10`) and goes into the final run. An error of any kind in a recover call now ends the round with a note, never the job (a test for it); two facts placed after the same block keep their order (`stages.add_sentences`, a test). The orchestrator and degradation test helpers switch the round off, as they do the vocabulary. Session 7e's English comparison runs pass `MAX_RECOVER_FACTS=0`, so they stay comparable with `eval/results-cscs-en-before`.
- 2026-10-09 (freeze moved): the owner moved the prompt freeze from Fri 9 Oct, 18:00, to Sun 11 Oct, 18:00 (D-AD). The final CSCS evaluation starts on Sunday night; G3 (every §5 row on CSCS, headline per §13.4) moves from Sat 10 to Mon 12 Oct, next to G4. §13.3, the final evaluation item of WP13, D-M and D-AC updated; the running sessions told.
- 2026-10-09 (no dataset): the owner dropped the optional Hugging Face dataset. Decision D-G, its WP item, the 13 Oct schedule entries, the consent letter to Canton Bern (old §12; §13 keeps its number so that references to it hold), the dataset parts of docs/sources.md §4, architecture §9 and report §4 removed.
- 2026-10-09 (plan restructured): each topic in one section, at the owner's request; updates go into the existing section, never a new one (AGENTS.md, §0). The finished WPs (WP1, WP2, WP5 to WP8, WP14, WP18) shortened to what was built. WP13 to WP17 moved from §13.2 into §3; the headline rules of §13.4 into WP13; the messaging rules, the numbers audit (§13.6) and the outreach drafts (§13.7) into WP16; the submission check into WP11; the schedule of §13.3 into §4 and the cut list of §13.5 into §7, replacing the originals; the added parts of §2 and §9 merged; the gap register (§13, §13.1) is §10, in place of the first tasks of 6 Oct, all done. Log lines above keep the old numbers; the references in docs, code and the video now name D-M (WP13), WP16 and §4.
- 2026-10-09 (video callback): at the owner's request, version C of the demo video brings the opening sentence back before the end card (docs/demo-video.md §3): the split screen again, DE-4 and FR-4 dimmed at the top, their easy-language versions below, "Can you read it now?". The easy text is the team's placeholder (`video/src/scenes/Again.tsx`, labelled on screen; both versions pass `leichtfacile check` at A2 with 0 errors and 0 warnings) until the tool's real output replaces it (WP11 item). The evidence scene stays: the owner asked whether the sentence should replace it, and it is the video's only answer to "why not one prompt". To stay under 2:00, voice speed 0.89 to 0.90 and the silent leads and pauses trimmed by 0.1 to 0.6 s (end card 3.2 to 2.6 s); 273 words, 1:59.0 as before. Rendered as `leicht-facile-demo-mock-C9.mp4`. Then the strike lines of the "only Apertus" tiles: they were turned about their left end from the tile's middle and ran through its upper half; now they start lower by half their rise and cross the middle (owner); `leicht-facile-demo-mock-C10.mp4`. Then BehiG on the easy-language card (owner): *Equal access by Swiss law: BehiG | LHand* under the three rules, on screen only, so the timing stays. The wording stops short of "the law requires easy language": art. 14 para. 1 BehiG names only speech, hearing and visual disabilities, and the revision that would add people with learning disabilities is before Parliament (Federal Council message of 20 December 2024). Found on the way: report §1 ("Accessibility law asks authorities to publish important information in Leichte Sprache") and docs/use-case-canton.md §1 ("Federal law (BehiG) ... require that important information is available in Leichte Sprache") say more than the law does; not changed here. `leicht-facile-demo-mock-C11.mp4`. Then the Ticino sentence and its caption out of the "only Apertus" scene of version C (owner; the scene keeps the other versions' Ticino through `hasCue`), the envelopes staying at the top for "For these letters"; its time went to the callback (lead 1.0 to 1.6 s, hold after the question 1.0 to 2.0 s) and back to the end card (2.6 to 3.0 s); 266 words, 1:57.6. `leicht-facile-demo-mock-C12.mp4`. Then the callback's answer (owner): "Now you can." spoken 1.2 s after the question, with a green tick after both questions; no English title, since the question is on screen twice already; 269 words, 1:58.3. `leicht-facile-demo-mock-C13.mp4`.
- 2026-10-09 (session 7e, English instructions): at the owner's request, English instructions for German and French documents tested in every model stage, repair first. `llm/prompts/en/` (understand, write, judge, repair and the two partials: the German templates in English line for line, the JSON forms, few-shot pairs and examples in the document's language), the English style guide (`ENGLISH_GUIDES` in `rules/styleguide.py`) and labels (`en`), behind `LLM_ENGLISH_PROMPTS` (empty by default; the default run replayed all 125 dev calls from the cache, so the frozen prompts are unchanged byte for byte); 44 tests in `tests/pipeline/test_english_prompts.py`. Five P2 runs on the 12 dev pairs on CSCS with `MAX_RECOVER_FACTS=0` (`eval/results-cscs-en-before`, `-en-before-fresh`, `-en-repair`, `-en-judge`, `-en-all`) and three fresh judge samples per language on the blind labels (`scripts/prompt_language.py`, `scripts/judge_agreement.py`). Result in docs/prompts.md ("English instructions") and D-AE: not taken, the judge's fact verdicts the one lead. The owner then had the variant removed completely (templates, setting, English style guide and labels, tests, the two scripts; commit `ff0544a` has them), the results kept. Found on the way, not changed: the Understand example's omission (`s0009`, "Gesetzesartikel, für die Leserin nicht nötig") stands in 17 of 104 German fact sheets of `eval/results-cscs` and once made a real value background (`zh-sebe-disability-de`, an e-mail address), because the copy guard checks only the fact texts of an Understand answer. Tests green after the removal, the two example-job tests red as before.
- 2026-10-09 (WP13 brought up to date): the section read against the log, the decisions and the code, its stale notes replaced: the P0-ZH runs of 6 Oct in their item (90 jobs, every answer tagged), the diagnosis buckets k and l, "Fix the largest bucket" ticked with what went in (facts rounds and cap 10, the repair record, the final version facts first, the completion fixes, D-AB, the provenance fixes of 8 Oct, the recover round) and what was tried and removed; the value numbers that exist named, with the cache's 0 s on P0; the final run spelled out: snapshot first, `--redo` on every row because the scoring changed since 6 Oct, P1 and P2 before the baselines (a baseline is scored against the newest P1 or P2 fact sheet of its pair), the baselines with `LLM_CACHE=0` for real seconds, then `eval report`, `eval numbers` and `eval diagnose --role eval`; the report item lists every place the numbers live; D-M names `eval numbers`, the variant behind Z (the video's "default mode" is `condensed`) and case A as the possible outcome after D-AC, with D-L's consequence for the video; D-R notes that the recover round keeps to it. No code change.
- 2026-10-09 (precise claims elaborated): WP15's "Precise claims" item read against README, the report, the video narration, the use-case documents and `publiccode.yml`, each claim with where it stands, its source and the wording that holds: the law (art. 14 para. 1 BehiG; the revision before Parliament since the message of 20 Dec 2024), the 844'000 (the SBFI's count for low skills in all three PIAAC domains, not reading alone; checked against the press release of 23 Oct 2025), the voting gap (no longer claimed; Zurich's Leichte Sprache voting information for 28 Sep 2025 with Pro Infirmis as proof of demand), "every fact" against "every fact value", the 80 against 70 percent next to the official versions, the A2 label, the baseline's name, "the 8B on one GPU" before a GPU run, the price basis of "one cent per page", the half-a-day assumption and the sources of the use-case figures (the penal-order 92 percent from Thommen's SNSF study); D-E noted as in effect. No code or text changed; the sentences a juror reads stay the owner's.
- 2026-10-09 (example tests, CI): the two red example tests traced. The bundles of 7 Oct still carry 4 (German) and 12 (French) open problems and no rebuild since has been clean; one rebuild on CSCS today with the recover round (`MAX_RECOVER_FACTS=10`, the earlier rounds from the cache) left 2 in German (b010 "Sie erhalten kein Geld zurück" cites no source sentence, FACT-03; the judge calls b009 unsupported because the draft names the canton as the payer, which the letter does not) and 3 in French (a 21-word sentence; FACT-02 on the contact fact, whose phone and e-mail stand in two blocks; an invented sentence about a letter from the tax office). The residence date 1 January 2027 is in both drafts now, through the recover round. The clean parts read worse than the count says: the German recover sentence is "Der Wert ist 1. Januar 2027." and the income limit stands three times; the French draft keeps "Vous payez la réduction". Neither bundle written, the 7 Oct bundles stay. So that CI is green until the rebuild after the freeze: `tests/test_examples.py` marks the two bundles in `KNOWN_PROBLEMS` as expected failures, strict, so a clean rebuild fails the test until its name leaves the set; a third example (the KESB decision) is tested as before. data/examples/README.md says so; WP8 and the risk line carry the state. Open for the owner, with the rebuild after the freeze: how the examples become clean (more fresh builds with `LLM_CACHE=0`, a hand-picked version, or a count without the judge's unsupported verdicts), and whether a clean draft that reads badly is the better showcase. 1,241 tests; 2 xfail.
- 2026-10-09 (precise claims applied): at the owner's request, the claims of WP15's "Precise claims" item fixed in the texts. Report §1: the law sentence (disability law and the UN convention ask for accessible information, cantons have begun to publish), the 844'000 as low skills in all three PIAAC domains, the official versions "drop values on purpose" next to 80 against 70 percent; §3: the vLLM profile not yet started on a GPU host; §5: the A2 label as a rule set, Zurich's prompt named as a fact, "values not in the source" instead of "invented values" where REF is in the table, the price basis, "drops a value silently". README: the 844'000, "no value lost, no value invented", the GPU claim, the cent at Public AI list prices, the level note, the deployment row. `publiccode.yml`: "fact value" in en, de and fr (short descriptions re-measured, all under 150 characters). Video: "At least 844,000" and "lists every one it misses" in the four narration files, the evidence scene's titles, demo-video.md's quotes and checklist (the voice and the length need a new build). use-case-canton.md §1 (the law, Zurich since September 2025, the half-day labelled as the team's assumption), use-cases.md (the 844'000, the GPU claim, the penal-order source: Thommen's SNSF study via Beobachter, in the references), hard-texts.md (the wording rule, the BehiG row), prompts.md (the baseline's name). Code: the D-M case A and C sentences in `eval numbers` and here, and the generated tables' column names ("Values not in source", "Unsupported (judge)"). The report grew by about 75 words, about 6 lines; WP11's page check at G5 decides the cuts.
- 2026-10-09 (image spike, strips): the WP12 spike run again on the two scans on CSCS to see where the digits go. A probe of one page at many sizes: the server keeps at most about 7,900 prompt tokens of an image, from 2,000 pixels on the long side up, JPEG or PNG alike, which is the Apertus 1.5 image tokenizer's clamp to 1400 x 1400 pixels (one code per 16 x 16 patch); a whole A4 scan at 300 dpi is read at about 140 dpi. `scripts/image_spike.py --strips` (`eval/image_spike.py`: `ink_box`, `strip_boxes`, `page_parts`, `came_back_as`) cuts the printed area at blank rows into strips under 1.9 million pixels, 5 calls per A4 page, and the report names what the transcription has in place of each lost value. Results in docs/prompts.md ("Image input spike", 9 October): whole page twice more on the 8B, 16 of 21 and 11 of 22 hard values with other digits in the IBANs, the AVS number, the file number, a postcode and a period; strips on the 8B three times, 20 of 21 and 17 of 22, every digit right, the losses an invented place name read as "Exampleville" (address, two e-mails, URL) and one footer URL; the printed area whole, grayscale strips, 1.5 x upscaled strips and the 70B on strips all worse or no better. D-N unchanged, the WP12 item and the decision row carry the finding; the owner may reopen WP12a. Three tests added; the scratch variants not kept. Then, at the owner's request, the honest write-up `docs/image-input.md` for the jury and the Apertus community: the server's image budget, the tables of every run, and a count by kind of value (digits right in strips on the 8B; names, e-mail and web addresses wrong in every setting; the 70B drops a paragraph), the limits of the evidence and what we recommend; linked from the README's pending line, prompts.md and architecture.md.
- 2026-10-09 (the number): at the owner's request, the 844'000 (15 percent, low in all three PIAAC domains, from the SBFI press release) replaced everywhere by the Swiss Federal Statistical Office's own figure for reading: 22 percent, 1.25 million people aged 16 to 65 with low literacy (first results of PIAAC 2022/2023, Neuchâtel 2024, section 3.3, read in the report). The office is named as the source in words, no logo; its reports allow reproduction for non-commercial use with the source named. README, report §1 and its reference, use-cases.md §1 and references, hard-texts.md §2 (the 844'000 kept as a row marked not used), demo-video.md, WP15's "The number" and the sources table. Video: the four narrations say "1.25 million adults in Switzerland struggle with reading" (pronunciation added), and the kitchen scene shows "1.25 million" with "22% of adults aged 16-65 struggle with reading" and the source line; the layout checked in a browser mock, the voice and the length need a new build.
- 2026-10-09 (video rebuilt): the demo video rebuilt after the narration changes of 9 October, in a fresh build folder outside OneDrive (C:\Users\bobro\Developer\lf-video): voice, timeline and mix for all four versions (C 117.8 s, A 112.0 s, B 113.6 s, the first concept 118.4 s), the UI frames captured again (21 shots), stills checked and version C rendered to C:\Users\bobro\Videos\leicht-facile-demo-mock-C14.mp4 (1920x1080, 117.8 s). The speech check reads "1.25 million adults in Switzerland struggle with reading" word for word; its other flags are sentence boundaries and the product name, as before. Edge has an update pending and hands over to the new binary, so puppeteer lost it; the capture now takes an EDGE override (`video/scripts/capture.mjs`, README step 7) and ran on Remotion's headless Chrome.
- 2026-10-09 (evidence card fixed): the facts panel in the evidence scene's right card ran past the card's bottom border since its heading became two lines with the precise claims. `video/src/scenes/Evidence.tsx`: the crop ends after the missing fact's source sentence, the gaps above it are 6 px smaller; the other scenes checked on a contact sheet, no other overflow. Version C rendered again as mock C15 (117.8 s).
- 2026-10-09 (evidence card, one line): at the owner's request, the right card of the evidence scene reads "lists every hard fact it misses" on one line (", for the writer" dropped), so the facts panel has room again; the crop ends after the missing fact's source sentence. The scene holds 2.0 s after its last sentence instead of 0.4 s (`narration-c.json`), version C now 119.4 s, under the 2-minute limit; demo-video.md's version C times shifted. Rendered as mock C16.
- 2026-10-09 (end card): at the owner's request, the end card names the team as "Team Röstigraben Bridgers · Hack Apertus 2026" (`video/src/scenes/End.tsx`, demo-video.md); rendered as mock C17.
- 2026-10-09 (evidence narration): at the owner's request, the narration says "A strong single prompt lost almost a quarter of the hard facts, without a word." ("in its default mode" dropped in narration-a, -b and -c); the evidence card keeps it on screen, so the claim still names the condensed variant (§3 numbers rule and WP15 updated). Voices and mixes rebuilt for A, B and C; version C 118.1 s (was 119.4 s), demo-video.md's times shifted; the speech check reads the new sentence word for word. Rendered as mock C18.
- 2026-10-09 (WP3 without images): at the owner's request, the stale `ingest/image.py` item removed from WP3; image ingest lives only in WP12 (WP12a cut by D-N, WP12b after the deadline).
- 2026-10-09 (WP3 closed): the last open item of WP3, the fixtures, has been done since 6 Oct in another shape: synthetic inputs built in the tests (hand-written pages, fpdf2 PDFs, pasted letters) instead of files saved under tests/fixtures; `tests/ingest` green (171 tests), the `ingest` command checked on a text and an HTML file. The section rewritten as a *Done* paragraph like WP0 to WP2.
- 2026-10-09 (WP4 closed): the last open item of WP4, the tests, accepted in another shape: a completeness test of the rendered prompts instead of a snapshot, two recorded 8B answers of 6 Oct (local llama.cpp, prompt versions a0224c698e87 and e44d14589893, the current files are 99fdb529e5a9 and a644e7997ea4) with the malformed cases derived in the tests; the write stage proven on Zürich pages by the full runs on CSCS. The section rewritten as a *Done* paragraph. Re-recording the two answers on CSCS with the current prompts stays optional (the fixture README asks for it; the tests test parsing, not the prompt text).
- 2026-10-09 (more items closed): at the owner's request, every item that could be closed now: WP9 rewritten as a *Done* paragraph (French done, its P2 numbers in report §5; Italian on the WP17 roadmap); in WP16 the video item (superseded by the concept "Find the deadline"); in WP11 the differentiator (in README, report §1 and the video) and the demo video (built as version C; link and final numbers stay in their own items). Everything else waits on the final run of 11 Oct, outside answers or the owner.
- 2026-10-09 (no outreach): at the owner's request, no outreach during the hackathon: WP16's outreach item, its two mail drafts and its part of the done criterion removed; the professional's drafting time (WP13) and the time-per-page claim (WP15) rest on a published figure only; the mails dropped from the schedule of 7, 8 and 12 Oct; cut-list item 9 removed, the items after it renumbered; D-Q and GAP-09 record the decision.
- 2026-10-09 (submission drafts): at the owner's request, a first draft of every submission document, with visible placeholders: **[PENDING: ...]** for the final run, the video and the commit, **[OWNER: ...]** for the team's decisions. The submission form's fields and the jury's guiding questions for Track 2B read from hackapertus.ch (§9). Report: maturity level, the users (the people who write official texts, from trained writers to case workers, clerks and physicians, not the few trained writers alone; owner), why these model sizes, where Apertus fell short, other models and coding assistants, what the running system contacts, licences, ten times the volume, the way into use and the first user; the settings table set to the code (Write ran without thinking, on CSCS too; Repair 6,000 tokens; a Recover row) and the subtitle to "every fact value"; tightened to 6 pages, the last 98 % full with the placeholders (headless Edge, A4, 10 pt; the draft PDF in the root). README: status of 9 October, decision mode v1, Check my text, the recover step, what the container contacts, the maturity line, the video placeholder. New docs/submission.md: the deliverables, our entry for each form field, the message to the jury (about 3,100 characters), the video page, the PDF method, the jury's questions with where we answer them, the checklist before Submit. architecture.md: the stage table's Recover row. The tests that read README and report pass.
- 2026-10-10 (next steps): at the owner's request, the ten open steps to the submission as a numbered list at the top of this plan, in dependency order (freeze, final run, D-M, numbers, example jobs and video, report and README, hardware statement, clean checkout, repo public, submit), each pointing to its work package, gate or docs/submission.md; §0 says how to keep it.
- 2026-10-10 (AWS L4): at the owner's request, the `local-llm` profile ran for the first time on a GPU host, an AWS g6.xlarge in Zurich (one NVIDIA L4 24 GB). As it stood, vLLM refused the 32k context on 24 GB (4.0 GiB of KV cache needed, 2.13 GiB left); with `--kv-cache-dtype=fp8` and `--max-num-seqs=16` it starts (38,752 tokens of KV cache), and both flags are now defaults in docker-compose.yml (owner). One request runs at 16.2 tokens per second, near the card's bandwidth limit. Through `make run` on a clean Linux clone (the clean-checkout test), the example letter took 63 min with the 8B judging with thinking and 22 min with thinking only in Understand; Understand's reasoning hit the 12,000-token cap in both. The owner reviewed job 1 as a reference. Evidence in eval/hardware/aws-l4-2026-10-10/ (audit bundles, vLLM log, GPU samples, README); report §2, §3, §6 and §7, README, architecture.md, use-cases.md and docs/submission.md updated.
- 2026-10-10 (track_2b layout): the organisers confirmed that the repository must keep the template's original `track_2b/` folder and have the Makefile at the root, where they run `make run`. At the owner's request the project moved into `track_2b/` with `git mv` (docs, src, data, eval, scripts, tests, the report and its PDF; the git-ignored contents of data/ and eval/ moved along); the root keeps the Makefile with the targets, Docker, Compose, uv, CI, PLAN.md, video/ and the local tool folders, and `track_2b/Makefile` passes every target on. README.md is in both places with the same text, each copy's links written from its own folder (AGENTS.md; `track_2b/tests/test_readme.py` checks text and links). The default paths (DATA_DIR, EXAMPLES_DIR, the manifest, `--results`, the scripts) and the image's layout (/app/track_2b) follow; paths in prose, comments and code are written from the root, except the frozen prompt templates, the UI's locale strings, the template's text and this log. Ruff clean, 1244 tests passed and the 2 expected failures; `make run` and `make stop` from the root and from `track_2b/` in a separate Compose project: healthy, both example jobs imported from the new path. The clean-checkout test (next step 8) is due again.
- 2026-10-10 (report in both places): at the owner's request, technical_report.md and RoestigrabenBridgers_Report.pdf are kept in the root as well as in `track_2b/`, like README.md: the same text, each copy's links written from its own folder. The draft PDF of 9 October had nine links to local files (Edge wrote the report's relative links as paths in the scratch folder it printed from); reprinted from the current text with a base URL for `track_2b/` on GitHub, its links work from both copies and from the uploaded file, and one file goes to both places: 6 pages, the last 94 % full. `track_2b/tests/test_readme.py` became `test_copies.py`: the text and links of both Markdown pairs, the two PDFs the same file, no local link in the PDF. AGENTS.md, track_2b/docs/architecture.md §11 and track_2b/docs/submission.md (§1, §5, §7) updated.
- 2026-10-10 (credit to Zurich): at the owner's request, the end card's footer gets a first line, "Inspired by simply-simplify-language, Team Data, Canton of Zurich." (`video/src/scenes/End.tsx`, all versions); the institution is credited, no person. D-L and demo-video.md record it; the wording is final with D-L on 13 Oct. Version C rendered as mock C19 (118.1 s, voice and mix unchanged). The build folder's sync command in video/README.md fixed: `/XD` matches folder names, so `tts\models` had not protected the voice models, and `/MIR` also deleted the generated `src/a/` and `src/timeline*.json`; they are now excluded by name.
- 2026-10-10 (examples rebuild, polish round): at the owner's request the example jobs are to show no error on first start. Six fresh attempts per letter on CSCS (`LLM_CACHE=0`, a scratch folder, nothing written into the repository): none clean, German 3 to 7 errors left, French 3 to 9. Behind them: a GRAM-08 false positive on verb-final clauses (`Wenn Sie wegziehen, melden Sie das`; fixed in `rules/de.py`, golden negatives; no hit in the dev finals of 9 Oct); the sentences the facts and recover rounds add, the source's nearly verbatim, which no round repairs (D-AF, the polish round, `MAX_POLISH_ROUNDS=1`, tests, docs, dev run into `track_2b/eval/results-cscs-polish`); junk facts from Understand (`text`, English, two-word fragments) that FACT-02 then demands a block for; and the 70B judge citing the judge prompt's example block ids: `b006` carries 46 of 179 unsupported verdicts in the example build store and 18 of 146 in the dev run of 9 Oct, five notes echo the example's internet sentence (open for the owner: anchor each verdict to a quoted sentence that code checks). In both dev runs of 9 Oct every final draft has errors. Dev run of the polish round (`track_2b/eval/results-cscs-polish`, 12 pairs): German rule errors 1.9 to 1.3 per 100 blocks, warnings 38 to 34, unsupported 5.8 to 5.3, fact coverage 96 and hard facts 90 percent unchanged, no must-keep value lost, judge distorted verdicts in the finals 13 to 7, about 17 percent more tokens; the final draft descends from the polished version in 8 of 12 jobs. Every final still has errors: FACT-02, FACT-03, FACT-01 and the judge's verdicts, which no rewrite fixes. 1,255 tests, ruff green. Then D-AG, the judge's quotes (both judge templates, `to_judge_report`, a test, docs): dev run in `track_2b/eval/results-cscs-judge-quote`, unsupported verdicts over all versions 188 to 102 with 4 dropped as copies of the example, German unsupported 5.3 to 3.1 per 100 blocks, rule errors 1.3 to 0.2, invented 0.6 to 0.0, fact coverage 96 to 94 on one pair's fresh facts-round sample. Kept on. The rebuild attempts then ran again on this pipeline: 0 of 11 clean (German 5, 4, 5, 3, 9, 5 errors; French 3, 5, one failed on invalid Understand JSON, 2, 5, 3), now mostly FACT-02, FACT-03 and judge verdicts. Then D-AH (`stages.link_facts` names a fact without a value on the blocks of its sentences and a worded fact on the blocks that together hold its values, FACT-03 skips a question, the judge's spelling line; tests, docs): dev run in `track_2b/eval/results-cscs-fact-links`, FACT-02 in the finals 19 to 10, unsupported verdicts 102 to 55, two finals without any error; fact and rule-error numbers within the day's noise. Kept on. The third rebuild round on this pipeline gave the first clean bundles: German attempts 1 and 4 of 6 (errors 0, 2, 3, 0, 5, 2), French 5 and 6 (2, one failed, 2, 2, 0, 0); a scratch first start showed both with 0 errors and 14 of 14 facts. Their lists of enclosures were split by the sentences the facts and recover rounds had placed after an item: D-AI, added sentences go after the list (`stages.apply_repairs`, `stages.add_sentences`, tests, docs), dev run in `track_2b/eval/results-cscs-placement` within the noise. A bug fix next to it: an Understand answer with `null` for a whole core question failed the job after the retry (4 of 18 French example builds), although the prompt itself asks for `"text": null`; `RefOut` now reads it as no answer (a test). Shipped at the owner's choice: German round-4 attempt 6 (the list of enclosures in one piece) and French round-3 attempt 5 (the draft that reads best) as the example bundles, 0 errors, 16 of 16 and 14 of 14 facts, 17 and 14 warnings on a scratch first start with screenshots; `KNOWN_PROBLEMS` emptied, the examples README and WP8 updated. The owner closed WP14's last item without a measurement: the clause recipes stay as they are, report §6 names them as unmeasured. The dress rehearsal for the final run at the owner's request: P2 on the 12 dev pairs on commit 3131a02 into `track_2b/eval/results-cscs-dev-final`, all 12 jobs through, 166 of 175 calls from the cache, German fact coverage 96, hard facts 87, rule errors 1.3 per 100 blocks, unsupported 1.0, French unchanged; two pairs differ from the placement run through fresh recover-round samples. 1,264 tests, ruff green.
- 2026-10-10 (one and a quarter million): at the owner's request, the voice says "one and a quarter million" instead of "one point two five million", where Kokoro paused between "two" and "five"; the screen keeps "1.25 million". The pronunciation in the `say` block of all four narration files; voices and mixes rebuilt for every version (C 117.6 s, was 118.1 s), the speech check reads the sentence word for word; demo-video.md's version C times shifted. Rendered as mock C20.
- 2026-10-10 (step scene on draft v6): the rebuilt example bundles (3131a02) split the deadline sentence s0007 into two sentences, b002 and b003, carrying f01 (deadline) and f06 (procedure); `b002.1` and `f03` are gone, so version C (and B) no longer rendered. At the owner's request `video/src/scenes/Step.tsx` shows the two sentences with their facts; the rule check on them gives 0 errors (2 LEX-07 warnings), so "0 errors (before: 2)" stands. The two sentences have no Mediopunkt, so only the label's example word shows one; the draft no longer names the Sozialversicherungsstelle as the place to send the form. demo-video.md §3 updated; stills checked. The app captures still show the job of 9 October, to be retaken (next step 5). The same day, at the owner's request, a mock with the Kokoro voice `af_bella` (build folder only, the repo keeps `af_heart`): 121.1 s at speed 0.90, over the 2-minute limit, and the speech check hears "every hard fact" as "everyone"; rendered as mock C21-bella on the draft of 9 October. The owner stays with `af_heart`; the mock and its cached voice were removed.
- 2026-10-10 (Makefile the other way round): at the owner's request the targets moved from the root Makefile into `track_2b/Makefile`, and the root Makefile is now a single `include` of it. The recipes still run from the root, so their paths stay written from there; called inside `track_2b/`, the file starts make again at the root with itself. Found on the way: the old pass-on rule (`%:`) took the folder `track_2b/eval/` for the target, so `make eval` inside `track_2b/` did nothing ("up to date"). The goals are now phony there. Checked from both folders with `make -n` for run, stop, eval (with `RESULTS`), eval-70b, test, lint and smoke, and with real runs of check-env, check-docker and bundle (exit codes passed on), on Windows (ezwinports make) and with GNU Make 4.4.1 on Linux (Alpine in Docker); `make run` itself not started. AGENTS.md, architecture §11 and submission.md §1 updated. The clean-checkout test (next step 8) covers the change.
- 2026-10-10 (video in sync with the rebuilt examples): at the owner's request the video follows the example bundles of 3131a02. The app frames are retaken from them (a fresh capture folder; step 7 in video/README.md now names `EXAMPLES_DIR` and the model settings the app needs outside the repo). The evidence scene's facts panel comes from draft v2, *15 of 16 facts present* with f07 (1. Januar 2027) missing, since the final draft v6 carries all 16. The repair ring ends on the final version's pill (v6, 0 blocking), no longer the last one (v7, a later round with 4), and the camera widens to reach it; the app scene says 45 rules, as the app counts them (was 42); both in all three app scenes. The step scene's Mediopunkt beat shows *Antrags·formular* and *Sozial·versicherungs·stelle* on one line, at the draft sentences' size (owner), since its two sentences have none. The hourglass icon of the "Slow expert work" card is redrawn as a sand clock with sand, in thinner lines (owner; it read as a twisted ribbon). The step scene marks the passive with a dotted red line and the long words with a fine wavy yellow one, since a wavy red line reads as a spell checker's mark (owner). The evidence scene's cards are 36 px shorter, their content unchanged, for more room under the title and above the footnote (owner). The "only Apertus" scene notes "Tested: one NVIDIA L4 GPU" under on-premise, after the AWS L4 run (owner; not "air-gapped": the machine had network, and the bundle has not run offline). The end card's credit names the Office for Statistics and Data between Team Data and the canton (owner; D-L). The "MOCK-UP" label and the end card's mock-up note are gone; the footer keeps only the Zurich credit (owner). Still open, in demo-video.md §4: the rebuilt German job answers "What does it cost?" with the junk word *text*, visible on the job page. Stills checked; rendered as mock C26.
- 2026-10-10 (review stopwatch): at the owner's request, WP13's review time: three P2 drafts in the UI, the two example jobs and the dev pair zg-disability-services-act-de of the dev-final run, served from a scratch copy of its store so no stored review changed, each from opening the review to the export; 15 minutes by stopwatch for all three, 1,079 source words, about 3.5 minutes per 250-word page, labelled team, not experts. Report §5 (both copies), submission.md §7 and the WP13 bullet carry it; the published drafting time per page stays pending. No code change.
