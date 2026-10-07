# Leicht·Facile - implementation plan

Working document, kept in the repository since 6 October 2026 (AGENTS.md says when to update it).
Written 5 October 2026, evening; gap plan (§13) added 6 October 2026, night.
Deadline: **16 October 2026, 12:00 CEST**, no extension.

Source of truth for *what* we build: [docs/architecture.md](docs/architecture.md) and
[docs/rules.md](docs/rules.md). This file is about *in which order*, *by when*, and
*what gets cut*. When the two disagree, fix the docs, not this plan - AGENTS.md requires
the docs to stay in sync with the code.

## 0. How to use this plan

- Work packages (WP) are listed in build order in §3. Each has a "done when" line;
  do not start the next WP's main work before the current one's "done when" holds,
  except where the dependency table says they are independent.
- §4 maps WPs to dates with six hard gates. Missing a gate triggers the cut list in §7,
  no debate.
- §5 is the day-1 verification script. It decides several open design choices (§8).
- §13 (added 6 Oct, night) turns the competition review and the comparison with the
  Canton of Zurich's app into a gap register, work packages WP13-WP17, a schedule to
  16 October and a revised cut list. From 7 October, §13.3 replaces the dates in §4
  (the gates keep their names) and §13.5 replaces the cut list in §7.
- Tick boxes as you go; keep this file honest so an agent picking up mid-way can see
  the real state.

## 1. Ground rules and constraints

From the template and the hackathon rules (verified 2026-10-05):

- `make run` must start the whole thing in Docker from a clean checkout. Env vars:
  `LLM_NAME`, `LLM_BASE_URL`, `LLM_API_KEY`. Judges will try this; it is the single
  most important deliverable after the report.
- `data/` stays under 100 MB. Texts and caches are git-ignored; only the manifest,
  examples, and clearly redistributable texts are committed.
- Repo must be public before submission. Report PDF max 6 pages, named
  `TeamName_Report.pdf`, in the repo root. Demo video max 2 minutes.
- Only Apertus models at runtime. Other open models may help with evaluation only, and
  their role must be described in the report. (Plan: none; the judge is Apertus 70B.)
- Repository conventions (AGENTS.md): never commit or push; plain hyphens only, no
  en/em dashes anywhere; the template's `track_2b/` contents are the repo root.

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

### Should ship (clear value, cut first when late)

6. Level B1 (Einfache Sprache) as a second threshold set - cheap once A2 works.
7. French (FALC) prompts, rules, 5+ pairs.
8. 8B vs 70B writer comparison on a subset; judge reliability (Cohen's κ on 30
   hand-labelled items).
9. Pre-computed example jobs so the UI is not empty on first start.

### Stretch (only if everything above is green by 13 October)

10. Italian (lingua facile).
11. Image input (photographed letters) through the API, as an end-user mode without
    expert review (WP12).
12. DOCX export; `make bundle` for the air-gapped tarball.
13. Cross-language fact-sheet consistency check.
14. LoRA from approved drafts (needs compute we do not have; most likely report-only).

### Added 6 October (night): closing the gaps (§13)

- Must ship: the P0-ZH baseline with Zurich's prompt, the fact-retention fix and the
  headline metrics (WP13); identifiers as hard facts (WP14); a decision letter with
  personal data as an example job (WP15); the pushed state, CI and correct counts, the
  positioning paragraph (WP16).
- Should ship: clause recipes for repair (WP14); WP12a, image ingest for the reviewed
  workflow, moves up from stretch item 11 (WP15); value numbers (WP13); outreach and
  `publiccode.yml` (WP16).
- After the deadline: WP12b, the end-user letter mode; the WP17 roadmap (report §8
  only).
- Documented 6 Oct (night; cloud session, 2): the further use cases
  (`docs/use-cases.md`) and the planned fact checks they need (`docs/rules.md`,
  "Planned fact checks"). Only the period value kind is a candidate before the freeze
  (WP14, D-U); everything else is WP17. *Done 7 Oct: the value kinds `period`,
  `identifier` and `address` (WP14), a day before their slot; the decision mode and
  the rest stay WP17.*

## 3. Work packages

Package root: `src/leichtfacile/` (layout per architecture §11). Every WP ends with:
tests green, `ruff` clean, docs updated where behaviour changed, one proposed
commit message per logical chunk.

### WP0 - Scaffold and `make run`

Goal: a container that builds from a clean checkout, serves `/healthz`, and can
reach the LLM endpoint.

- [x] `pyproject.toml` (uv, hatchling, Python 3.12+), `uv.lock`, `.python-version`
      (3.14). Runtime deps so far: fastapi, uvicorn, pydantic, pydantic-settings,
      openai, httpx, spacy; dev: pytest, ruff. Each later WP adds its own deps
      (jinja2, python-multipart, pyphen, trafilatura, pdfplumber, lingua, pyyaml).
      The Docker build uses `uv sync --frozen` directly, so no `requirements.txt`.
- [x] spaCy `de_core_news_md` 3.8.0 as a pinned wheel URL, installed at image build
      time (fr/it added in WP9).
- [x] `src/leichtfacile/{__init__,__main__,cli,config}.py`. `config.py` reads the
      `LLM_*` variables, `MAX_REPAIR_ROUNDS`, `DATA_DIR`, `LOG_LEVEL`.
- [x] `web/app.py` with `GET /` (placeholder page) and `GET /healthz` (lists the
      endpoint's models, reports errors without failing liveness, never shows the key).
- [x] `Dockerfile` (python:3.14-slim, uv 0.12.18, non-root user, Docker health check,
      `CMD uvicorn`). Image builds; container verified against an unreachable endpoint.
- [x] `docker-compose.yml`: `app` with `env_file: .env`, named volume `appdata:/data`
      (avoids host permission problems), port 8000; profile `local-llm` with `vllm`
      (`latest-amd64`, reasoning parser, 32k context). Both profiles validate.
- [x] `Makefile`: `run` (with `.env` check), `stop`, `check-llm`, `test`, `lint`,
      `format`, `smoke` (= `check-llm` for now), `eval` and `bundle` stubs.
- [x] `.env.example` with three profiles (CSCS, local vLLM, Hugging Face dev-only),
      `.dockerignore`, `tests/conftest.py`, `tests/test_healthz.py`.
- [x] `.gitignore`: `data/cache/`, `data/*.sqlite`, `data/*.db`, `eval/results/`,
      `out/`, tool caches.
- [x] Run `make run` itself once *(6 Oct: `docker compose up --build` on the Windows
      host served `/healthz` against CSCS after 10 s, both models listed)*. A Linux or
      macOS run is still worth doing before G6.
- [ ] Start the `local-llm` profile once on a GPU host, if one is reachable.

Done when: `rm -rf` a fresh clone, copy `.env`, `make run`, and
`curl localhost:8000/healthz` returns the model list from CSCS. **Waiting for the key.**

### WP1 - LLM client and day-1 verification

Goal: one robust way to call Apertus; the six assumptions in architecture §12 answered.

- [x] `llm/client.py`: `complete(messages, *, model, thinking, temperature,
      max_tokens, stage, response_format)` returning `LLMResult` (text, reasoning,
      finish reason, usage). Retries on 429/5xx/connection errors with backoff,
      jitter and `Retry-After`; 4xx not retried; usage sink callback.
- [x] Thinking modes `model-suffix`, `chat-template`, `off`. Reasoning from the
      `reasoning_content` field or inline `<|inner_prefix|>` / `<think>` tokens;
      truncation while reasoning is flagged.
- [x] `llm/json_out.py`: `extract_json`, `schema_instruction`, `complete_json` with
      one error-feedback repair. `response_format` is a parameter of `complete`.
- [x] `llm/cache.py`: SQLite cache keyed by sha256 of (model, messages, params),
      enabled by `LLM_CACHE=1`, stored in `DATA_DIR`.
- [x] Tests against a fake OpenAI-compatible endpoint (httpx mock transport, real
      SDK path): 50 tests, ruff clean.
- [x] `python -m leichtfacile check-llm` (and `make check-llm`): lists models, one
      short call, prints reasoning format, tokens and latency. Covers day-1 checks 1-2.
- [x] `scripts/day1_checks.py` for checks 3-6 *(run on the Public AI gateway on 6 Oct, results in architecture §12; CSCS still pending)* (JSON reliability, image input, rate
      limits, P0 baseline); results into `docs/architecture.md` §12, every `[verify]`
      resolved.
- [x] Usage records persisted to the `llm_calls` table (needs the WP2 store).

Done when: the day-1 checks print answers to all six questions and the `[verify]`
markers in the architecture doc are gone.

### WP2 - Schemas, store, orchestrator skeleton

- [x] `schemas.py`: *(plus PipelineSummary and Fact.origin; prompts show a filled JSON example instead of `model_json_schema()`, see docs/prompts.md)* `SourceDocument`, `Segment`, `FactSheet`, `Fact`, `Draft`,
      `Block`, `RuleFindings`, `Finding`, `Metrics`, `JudgeReport`, `ReviewState`,
      `Job`, `Usage` as pydantic v2 models, exactly as architecture §5. Each
      model-facing schema gets `model_json_schema()` rendered into the prompt.
- [x] `store.py`: *(the response cache stays a separate file)* SQLite (stdlib `sqlite3`, WAL mode), tables `jobs`, `artifacts`
      (job_id, name, version, json, created_at), `llm_calls`, `llm_cache`. Thin
      functions, no ORM. Migrations = `CREATE TABLE IF NOT EXISTS`.
- [x] `pipeline/orchestrator.py`: ordered stage list, each stage `(inputs) ->
      artifact`, persisted before the next starts; `run(job_id, from_stage=None)`
      resumes from the last good stage; status and stage written to the job row;
      exceptions recorded in `job.error`.
- [x] Single worker thread with a `queue.Queue`, started by the web app and by the
      CLI (`cli.py simplify` runs the orchestrator inline).
- [x] Tests: round-trip every schema through JSON; store CRUD; orchestrator resume
      after a failing stub stage.

Done when: a job with stub stages runs, persists artifacts, fails, and resumes.

### WP3 - Ingest and segmentation

- [x] `ingest/text.py` (paragraph split) *(ingest agent)*, `ingest/html.py` (trafilatura with
      `include_links=False`, keep headings and lists; fallback to simple
      heuristics only if trafilatura returns empty), `ingest/pdf.py` (pdfplumber,
      per-page text, heading heuristic by font size, page numbers on segments).
- [x] `ingest/segment.py`: *(ingest agent)* paragraphs → sentences via spaCy sentencizer for the
      language; stable ids `s0001…`; kinds `heading | paragraph | list_item |
      table_cell`; heading path.
- [x] `ingest/detect.py`: *(stopword frequencies instead of lingua: three languages need no extra model)* lingua, restricted to de/fr/it, user override wins.
- [ ] `ingest/image.py` *(moved to WP12)*: feature-flagged (`FEATURE_IMAGE_INPUT`), implemented only
      if day-1 check 4 passes; otherwise raises a clear "not supported on this
      endpoint" error. *(Check 4 passed on Public AI on 6 Oct: the 8B read a rendered
      letter. Possible now; still cut-list item 4, after the numbers.)*
- [ ] Fixtures (article-5 or synthetic texts only, see docs/sources.md §4): one HTML
      page saved locally, one short PDF with text layer,
      one pasted text. Tests assert segment counts, kinds, and id stability.

Done when: `python -m leichtfacile ingest <file|url>` prints a `SourceDocument` for
all three input types.

### WP4 - Understand and Write (German)

- [x] `llm/prompts/de/understand.md` and `write.md` *(prompt hash instead of a version header)* as Jinja2 templates with
      placeholders for style guide, examples, segments, fact sheet. Version header
      in each file; `docs/prompts.md` logs changes and why.
- [x] `rules/styleguide.py`: renders the writer style guide from the rule registry
      (see decision D-A in §8) for a given language and level.
- [x] `llm/prompts/de/examples/`: *(two synthetic pairs written by the team: Zürich and Bern pages may not be reproduced in a public repo)* 2-3 standard → easy pairs from Canton Zürich or
      Bern pages, short (under 150 words each), with the source URL and licence note.
- [x] `pipeline/understand.py`: *(in pipeline/stages.py; unknown ids are kept and reported by FACT-05)* one call over the whole document, `FactSheet` out,
      model = writer model with thinking, temperature 0.1. Post-check: every cited
      `segment_id` exists; unknown ids dropped with a warning.
- [x] `pipeline/write.py`: *(in pipeline/stages.py)* plan-then-write prompt, `Draft` out, temperature 0.3.
      Documents over ~3,000 words: split by top-level heading, one call per section
      sharing the fact sheet, blocks re-numbered globally. Post-check: ids unique,
      `segment_ids` exist, `fact_ids` exist.
- [x] Normalisation helpers for `value_norm`: *(rules/values.py; plus code completion of the fact sheet)* ISO dates, decimal CHF, digits-only
      phone, lowercase URL/e-mail. Done in code after the model returns, not trusted
      from the model.
- [ ] Tests: prompt rendering snapshot; parsing of 3 recorded real outputs on
      article-5 or synthetic inputs (saved
      under `tests/fixtures/llm/`), including one deliberately malformed.

Done when: `python -m leichtfacile simplify sample.html --lang de --level A2 --stop-after write`
produces a readable draft with provenance on a real Zürich page.

### WP5 - Rule checker (German)

- [x] `rules/base.py`: `Rule` (id, family, severity per level, `check(doc_ctx,
      block) -> list[Finding]`), registry, runner producing `RuleFindings` and
      `Metrics`. spaCy `Doc` built once per block, shared across rules.
- [x] `rules/de.py`: implement in this order (value per effort): LEN-01, CH-01,
      GRAM-01, NUM-01, NUM-03, NUM-04, NUM-06, NUM-08, LEX-04, LEX-02, NEG-01,
      GRAM-02, GRAM-03, GRAM-04, GRAM-05, LEN-02, LEX-01, NUM-02, NUM-07, CH-02,
      then the `info` rules (ORD-01, GRAM-06, GRAM-07, NEG-02, LEX-03, LEX-05,
      LEX-06, CH-03, NUM-05, LAY-03).
- [x] `rules/facts.py`: *(rules/values.py + rules/document.py; plus FACT-05)* FACT-01 surface-form generator (dates in `4. Februar 2020`,
      `4.2.2020`, `04.02.2020`; amounts with `'`, space, none, with/without `.00`,
      `CHF`/`Fr.`/`Franken`; phones with any whitespace; URLs/e-mails
      case-insensitive), FACT-02, FACT-03, FACT-04.
- [x] `rules/readability.py`: Amstad (DE), Kandel-Moles (FR), Gulpease (IT), with
      `pyphen` syllables; unit tests against published example values.
- [x] `tests/rules/golden_de.yaml`: *(official sentences are not committed (copyright); the calibration on the cached pages and docs/hard-texts.md replace them)* per rule 2-5 positive and 2-5 negative
      sentences, plus 20 sentences lifted from official Leichte Sprache pages that
      must produce zero `error`.
- [x] Sanity run on the official easy-language pages *(2.0 errors per 100 blocks on 30 pages, 3450 blocks, after calibration; see docs/rules.md)* from the dataset: error rate
      per 100 blocks recorded in `docs/rules.md` as the false-positive baseline.

Done when: golden tests pass; official pages produce under 2 errors per 100 blocks;
`rules.md` and the registry contain the same rule ids (enforced by a test).

### WP6 - Judge, repair, full CLI

- [x] `llm/prompts/de/judge.md`: fact sheet + draft in, `JudgeReport` out; SEM-01..07
      ids; "report only, never rewrite". Model = `LLM_JUDGE_NAME`, thinking, temp 0.
- [x] `pipeline/judge.py` with post-checks *(in pipeline/stages.py)* (fact ids and block ids exist).
- [x] `llm/prompts/de/repair.md` and `pipeline/repair.py`: *(in pipeline/stages.py)* flagged blocks only, each
      with its findings and required facts; replacement blocks keep ids; rule check
      reruns on changed blocks; judge reruns only when a fact/hallucination finding
      was involved; stop at zero `error` or `MAX_REPAIR_ROUNDS`. All draft versions
      persisted (`draft@v1…`).
- [x] `cli.py simplify <input> --lang --level --out --writer --judge --no-judge
      --no-repair --stop-after <stage>` writing all artifacts as JSON into `--out`.
- [x] `make smoke`: runs `simplify` on the bundled sample against the live endpoint,
      asserts the job reaches `needs_review` *(6 Oct: reached review on CSCS, 7 calls,
      26k tokens; Git Bash needs `MSYS_NO_PATHCONV=1`, now in the recipe)*.

Done when: one German page runs P2 end to end from the CLI in under 5 minutes and
the repair rounds visibly reduce `error` findings.

### WP7 - Dataset and evaluation harness

- [x] Start from the shortlist and pools in `docs/sources.md`; *(roles dev and eval)* manifest rows carry
      `role` (`eval` or `example`) and a rough fact count.
- [x] `data/pairs/manifest.jsonl`: *(35 pairs: 30 German, 5 French)* target 20+ pairs. Sources: zh.ch (Leichte
      Sprache section), be.ch, sg.ch, fr.ch (DE and FR), ti.ch (IT), admin.ch
      (EBGB). Fields: id, canton, lang, level, url_standard, url_easy, licence_note,
      fetched_at. Licence note per row; texts committed only when clearly permitted.
- [x] `scripts/fetch_pairs.py` *(all 70 texts fetched)* → `data/cache/pairs/<id>.{standard,easy}.json` via
      the ingest module.
- [x] `eval/conditions.py`: *(the conditions are job configs of the orchestrator)* P0 (single prompt baseline), P1 (understand + write +
      rules), P2 (full). Writer/judge models as parameters.
- [x] `eval/metrics.py`: *(plus eval/score.py; CHF replaced by USD at Public AI list prices)* fact coverage (FACT-01 pass rate), judge fact status,
      unsupported blocks per 100, rule errors/warnings per 100 blocks by family,
      readability (source / output / official easy version), SARI (own
      implementation, tested against the EASSE reference example), tokens, latency,
      CHF per page from a configurable price table.
- [x] `eval/run.py`: runs a condition over the manifest with the LLM cache on,
      resumable, writes `eval/results/<condition>_<writer>.jsonl`.
- [x] `eval/report.py`: Markdown tables for the technical report; `make eval`.
- [x] First numbers: P0 on 10 German pairs (day-1 check 6), then P1 and P2 *(6 Oct:
      all three conditions on the 23 held-out pairs on CSCS, docs/prompts.md)*.

Done when: the P0/P1/P2 table exists for at least 15 German pairs and is pasted into
`technical_report.md` §5 as a draft.

### WP8 - Review UI and export

- [x] `web/routes/`: *(web/api.py and web/pages.py)* the API table from architecture §7 (`POST /api/jobs`,
      `GET /api/jobs/{id}`, artifacts, review, export, rerun, delete).
- [x] `web/templates/`: *(review.html also handles the progress state through job.html)* `index.html` (job list + new job form: upload, URL, pasted
      text, language, level, models), `job.html` (progress per stage, polling),
      `review.html` (three panes: source, draft, side panel with fact checklist,
      findings, omissions, glossary, version switcher).
- [x] `web/static/`: *(water.css 2.1.1)* one vendored classless CSS file and one `app.js` (no CDN, no
      build step). Highlight linked segments on block select; approve / edit /
      reject per block; save to `ReviewState`.
- [x] `export/markdown.py`, `export/html.py` (one sentence per line, 85-char wrap at
      clause boundaries, LAY-01/02 check on output), `export/bundle.py` (JSON audit
      trail). DOCX only in stretch.
- [ ] `data/examples/`: two pre-computed jobs on article-5 or synthetic texts (one
      web page, one PDF letter), never a protected page (docs/sources.md §4),
      loaded into the store on first start and labelled "example".

Done when: a judge can open `localhost:8000`, submit a URL, watch the stages, open
the review, click through provenance, and download Markdown - without reading docs.

### WP9 - French and Italian

- [x] French: `prompts/fr/*`, 2 example pairs, `rules/fr.py` (the FR table in
      rules.md), golden tests, 5+ pairs in the manifest, Kandel-Moles verified.
      *(done 6 Oct without the key: 27 rules, calibrated on the 5 official pages to
      2.2 errors per 100 blocks, French limits 15/18 words; French syllables 93 percent
      exact; French letter in data/examples; web form and API accept French. The P2
      numbers on the French pairs need the key.)*
- [ ] Italian (stretch): same shape; Gulpease; Ticino pairs.
- [x] spaCy model `fr_core_news_md` in the image *(image 1.97 to 2.19 GB)*;
      `it_core_news_md` only when Italian ships.

Done when: P2 runs on the French pairs and the French numbers are in the report.

### WP10 - Comparisons and reliability

- [x] P2 with the 70B writer on 5-10 pairs; 8B vs 70B table (quality, tokens, CHF,
      latency) *(6 Oct: 5 pairs, technical report §5)*.
- [ ] Judge reliability: 30 (fact, draft) items labelled by hand; Cohen's κ *(tooling
      done 6 Oct: `eval sample --results eval/results-cscs` writes
      `eval/labels/judge_facts.jsonl` without the verdicts plus a key file,
      `eval kappa <sheet>` scores the filled sheet; the labelling itself is open)*.
- [ ] Hallucination spot check: 30 blocks flagged/unflagged by the judge, labelled
      by hand *(same tooling: `eval/labels/judge_blocks.jsonl`, 15 flagged and 15
      passed; labelling open)*.
- [ ] Hardware statement for the on-prem profile: run the `local-llm` compose
      profile if a GPU is reachable; otherwise cite the official vLLM guide numbers
      and say so *(no GPU host reachable on 6 Oct; the `local-llm-small` llama.cpp
      profile ran on the RTX 4060; the report will cite the vLLM guide and say so)*.

Done when: the report's §5 has every table filled with real numbers.

### WP12 - Letter photo for end users (no expert review)

*Split on 6 Oct (night), decision D-N: the spike and `ingest/image.py` for the
reviewed workflow become WP12a (part of WP15, by G4); the end-user mode is WP12b
(after G4 only if everything is green; cut list §13.5, item 5).*

Goal: a person who received an official letter photographs it with their phone and
gets, directly and without a reviewer in between, an easy-language explanation: what
the letter is about, what they must do, by when, how much, whom to ask. Everything
the reviewer does in the main workflow has to be done by code or said honestly on
the page. Built after WP10 in build order; scope status in §2 (stretch item 11).

- [ ] Go/no-go spike first (half a day at most): 3 synthetic letters, printed and
      photographed with a phone (good light, poor light, skewed), sent to the 8B on
      CSCS with a "transcribe word for word, do not summarise" prompt. Day-1 check 4
      only read a rendered PNG; a real photo is the open question. Measure the
      character error rate against the source text and whether every date, amount
      and phone number survives. Stop here if hard values are lost.
- [ ] `ingest/image.py` (was the WP3 item): JPEG/PNG, up to 3 photos per letter
      (pages in order), EXIF rotation, long side scaled to about 1600 px (Pillow);
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
      `data/examples/`), each as clean text and as phone photos. Report: character
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

### WP13-WP17 - Closing the gaps (added 6 October, night)

Defined in §13.2: WP13 fair baselines and the headline, WP14 fact contract and repair
hardening, WP15 sovereignty and "why Apertus" evidence (includes the WP12 split), WP16
credibility and positioning, WP17 after 16 October. Build order: WP16's push and CI
first, then WP13, WP14 and WP15 next to the evaluation runs; all of them before WP11.

### WP11 - Report, video, submission

- [ ] `technical_report.md` filled (sections 1-8); export to PDF (pandoc or print to
      PDF), check 6-page limit, save as `RoestigrabenBridgers_Report.pdf` in the root.
- [ ] `README.md`: keep the template text, add a "Leicht·Facile" section on top:
      what it is, `make run` quick start, where the report and video are.
- [ ] State the differentiator in README, report §1 and the video: not a translator, and
      not achievable with one chatbot prompt (fact contract, provenance, omission log,
      independent checks, audit trail). P0 is that baseline; cite the P0 vs P2 numbers.
- [ ] Demo video (under 2 min): 15 s problem, 60 s live run on a cantonal page with
      the review UI, 30 s numbers and sovereignty, 15 s close. Record with the
      example job pre-loaded as a fallback if CSCS is slow.
- [ ] Clean-checkout test on a different machine or a fresh clone directory:
      `git clone`, `.env`, `make run`, run one job.
- [ ] Repo to public; `.env` absent from history (check `git log -p -- .env`).
- [ ] Optional HF dataset in the `HackApertus/online_hack_template` layout, only if
      the manifest licensing is clean (decision by 13 October).
- [ ] Submit at hackapertus.ch/online-hack/submissions: repo URL, PDF, video URL,
      dataset URL if any.

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
| WP11 | everything | - |

## 4. Schedule and gates

*From 7 October the schedule in §13.3 applies. The gates keep their names and dates;
they gain the gap items. The table below stays as the original plan.*

| Date | Focus | Gate (end of day) |
|------|-------|-------------------|
| Mon 5 Oct | Design docs (done), this plan, get CSCS key | - |
| Tue 6 Oct | WP0, WP1, start WP2 | **G1**: `make run` serves `/healthz` against CSCS; day-1 checks answered; `[verify]` markers resolved |
| Wed 7 Oct | WP2, WP3, WP4 prompts | Ingest works for text/HTML/PDF; first Understand output on a real page |
| Thu 8 Oct | WP4 finish, WP5 core rules | **G2**: German `simplify --stop-after rules` end to end on a real page, golden tests for the top 12 rules green |
| Fri 9 Oct | WP5 rest, WP6 judge + repair, manifest to 15 pairs | Full P2 run from the CLI on one page |
| Sat 10 Oct | WP7 harness, P0/P1/P2 runs (overnight if needed) | **G3**: P0/P1/P2 numbers on 15+ German pairs. If missed: cut Italian now, French becomes stretch |
| Sun 11 Oct | WP8 API + review UI | Review page shows provenance, findings, fact checklist |
| Mon 12 Oct | WP8 export + examples, WP9 French | **G4**: UI demoable; export works; pipeline feature freeze (bug fixes only) |
| Tue 13 Oct | WP10 comparisons, labelling, κ; Italian only if G3 and G4 were on time | All report tables filled; decide on HF dataset |
| Wed 14 Oct | WP11 report draft, README, video script and recording | **G5**: report draft complete (6 pages), video recorded, clean-checkout test passed |
| Thu 15 Oct | Buffer: fixes from the clean-checkout test, report polish, PDF export, repo public | **G6**: everything submission-ready, nothing left to do on the 16th but click |
| Fri 16 Oct | Submit before 12:00 CEST | Submitted, confirmation saved |

Rule of thumb for the day: start with the item on the critical path (the gate), then
parallelisable items, then polish. Evaluation runs go in the background with the
cache on while UI work happens.

## 5. Day-1 verification script (WP1)

`scripts/day1_checks.py`, run as soon as `.env` exists. Record each answer in
`docs/architecture.md` §12 and remove the `[verify]` marker it resolves.

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
| Recorded | Prompt rendering snapshots; parsing of real model outputs saved as fixtures | pytest with fixtures under `tests/fixtures/llm/` | `make test` |
| Integration | Orchestrator with stub stages; API routes with the FastAPI test client | pytest | `make test` |
| Smoke | One real page through P2 against the live endpoint | `make smoke` | before each gate |
| Acceptance | Clean clone + `.env` + `make run` + one job in the browser | manual | G5, G6 |
| Evaluation | P0/P1/P2 over the manifest | `make eval` | G3, WP10 |

Privacy guard: a test asserts that no log line above `DEBUG` contains document text
(use a sentinel string in a fixture document).

## 7. Cut list (apply in this order when a gate is missed)

*Revised 6 October (night): from 7 October the cut list in §13.5 applies.*

1. LoRA (already report-only).
2. Cross-language consistency check.
3. DOCX export and `make bundle`.
4. Image input (WP12; if the spike passed but time is short, keep the transcription
   and the facts box, drop the explanation).
5. Italian.
6. 70B writer comparison (keep the 70B judge).
7. French.
8. B1 level (keep one level; which one is decided by day-1 check 6).
9. UI polish: keep a single review page without the version switcher.
10. Judge κ labelling: reduce from 30 to 15 items, state it in the report.

Never cut: `make run` from a clean checkout, FACT-01 coverage, the P0 vs P2
comparison, the report, the video.

## 8. Open decisions

| ID | Question | Recommendation | Decide by |
|----|----------|----------------|-----------|
| D-A | Where do rules live: parse `docs/rules.md` at runtime, or a code registry with a test that both contain the same ids? | Code registry (`rules/catalog.py`) with id, families, severities per level, prose; `styleguide.py` renders from it; a test diffs ids and severities against `rules.md`. Markdown parsing at runtime is brittle. | 7 Oct |
| D-B | `response_format` JSON mode | Use it only if day-1 check 3 shows fewer failures; never rely on it alone. *Decided 6 Oct on Public AI: 20 of 20 parsed in both modes, same answers; not used.* | done |
| D-C | SARI implementation | Own ~80-line implementation in `eval/metrics.py`, unit-tested against the EASSE example; avoids heavy deps in the image. | 9 Oct |
| D-D | UI styling | One vendored classless CSS file (pico.css or water.css, MIT) plus hand-written `app.js`; no framework, no bundler. | 11 Oct |
| D-E | Primary level A2 or B1 | Day-1 check 6. | 6 Oct |
| D-F | Section-parallel writing | Only if check 5 shows headroom; otherwise sequential. *Decided 6 Oct on Public AI: 8 parallel calls, no 429, 1.4 to 2.2 s each. Headroom exists; use it first for parallel evaluation workers, section-parallel writing stays optional.* | done |
| D-G | Publish an HF dataset | Development and evaluation need no consent (docs/sources.md §4). Publishing protected texts or our rewrites of them does. Default: manifest, metrics, and article-5 texts with outputs; ask Bern only if a Swiss reference set should be public. | 13 Oct |
| D-I | Main demo document | A past Federal Council voting explanation (docs/sources.md §3); confirm its article-5 status first. Backup: the radio and TV fee exemption fact sheet. *Revisit on 8 Oct after the WP15 test run (added 6 Oct, night; cloud session): a KESB decision is the stronger sovereignty demo (docs/use-case-decisions.md); the voting explanation can stay as one sentence on the federal gap.* | 9 Oct |
| D-J | NUM-08 and +41 numbers | Decide at checker calibration: accept the international format or lower to `info`. | 8 Oct |
| D-H | Team name | Decided 5 Oct: **Röstigraben Bridgers**; file name `RoestigrabenBridgers_Report.pdf`. Report §1 frames the name as bridging the gap between authorities and readers, not as translation. | done |
| D-K | P0-ZH variants | Run both on the 20 German eval pairs: `complete` (same task as ours, keep every fact; used for the headline) and `condensed` (their default for Leichte Sprache). One 8B call per pair, cheap. | 7 Oct |
| D-L | Name Zurich in the video | Report: yes, with credit, link and licence. Video: only in case A of §13.4; otherwise "a strong single prompt". | 13 Oct |
| D-M | Headline metric and sentence | The rules of §13.4, applied to the final CSCS numbers, no debate. | 10 Oct (G3) |
| D-N | WP12 split | Spike on 8 Oct. WP12a (image ingest for the reviewed workflow) only if 3 of 3 phone photos keep every hard value in the transcription; WP12b (end-user mode) after G4 only if everything is green. | 8 Oct |
| D-O | Identifier matching | IBAN and AHV number compared without spaces; every other identifier exactly, after whitespace normalisation; no checksum test (letters carry specimen numbers); FACT-01 and FACT-06 severity `error` at A2 and B1. *Decided 7 Oct as recommended, implemented; a digits-only identifier also matches its bare number, so `Dossier 12345` survives as `Ihre Nummer: 12345`.* | done |
| D-P | Clause recipe for `wenn` / `si` | Question form ("Haben Sie ...? Dann ..."), never `vielleicht`; one line in the judge prompt: a condition must stay a condition. | 9 Oct |
| D-Q | Outreach | Mail A to Zurich's Team Data, mail B to one easy-language office (§13.7). Only synthetic letters and their outputs leave the team. Answers by 12 Oct; no second round. | 7 Oct |
| D-R | Fact-retention fallback | If P2 still keeps fewer facts than P0-ZH after the WP13 fix: no code-written fact sentences in the evaluated text; report the trade-off and the "no silent loss" property instead (case B of §13.4). | 10 Oct |
| D-S | Mediopunkt by code (WP14): where and for what | P1 and P2 only; P0 and P0-ZH measure the prompt alone, as with Zurich's `strip_markdown`. Nouns only; adjectives keep the LEX-01 warning. The count of code splits is reported next to the LEX column. Optional at G3, if a juror could ask how much of the LEX gain is the cheap part: a rescored "P0 + code" row from the cache, no model calls. | 8 Oct |
| D-T | WP15 demo letter: premium-reduction reclaim or KESB decision | A team-written KESB decision (a deputyship) instead of the premium-reduction reclaim: it shows personal data and the second use case (docs/use-case-decisions.md) at once. Keep the reclaim letter only if the KESB decision does not read like a real one after the check against published decisions. | 8 Oct |
| D-U | Period value kind (`innert 30 Tagen`) before the freeze | Yes, if the identifier kind is in by Thu 8 Oct: same module (`rules/values.py`), 2-3 h, it makes the 30-day appeal period of the KESB demo a fact checked by code, and every further use case needs it first (docs/use-cases.md §12). Otherwise WP17, with one sentence in report §7. *Decided 7 Oct: yes; period, identifier and address kinds done together, before the freeze.* | done |

## 9. Judging criteria → evidence we must produce

| Criterion | Evidence | Produced by | Added by §13 (6 Oct, night) |
|-----------|----------|-------------|------------------------------|
| Purposeful use of AI | The "Apertus understands, code counts" split; P0 vs P1 vs P2 table showing what each AI stage adds; the not-a-translator comparison (use-case-canton.md §4) | WP5, WP7, report §3 and §5 | P0-ZH: what the pipeline adds over the best public single prompt on the same model; Apertus image input in the reviewed workflow (WP12a) |
| Technical rigour | Golden tests, FACT-01 exact coverage, judge κ, recorded fixtures, resumable pipeline, cache for reproducible reruns | WP5, WP7, WP10 | A fair baseline; the fact-retention diagnosis; identifiers in the fact contract; CI green on the submitted commit; numbers audit |
| Value, cost and scalability | CHF per page 8B vs 70B, latency per stage, reviewer workflow with provenance | WP1 usage log, WP10 | Minutes per page including review; an outside voice; `publiccode.yml`; the WP17 roadmap (termbase, house styles) in report §8; one engine, many documents: the further use cases in `docs/use-cases.md` |
| Sovereign deployability | `local-llm` compose profile, air-gapped image (no CDN, models baked in), single `LLM_BASE_URL` dependency, hardware statement | WP0, WP8 vendoring, report §2 | The decision letter with personal data, which may not go to a cloud chatbot; the "Why Apertus" box; the decisions use case, where the text may never leave the authority (docs/use-case-decisions.md) |
| Implementation feasibility | `make run` on a clean checkout, example jobs, limitations stated honestly | WP0, WP8, WP11 | Example jobs including the decision letter; CI; `main` equals the state in this log |

## 10. First tasks for 6 October (in order)

1. Request the CSCS key; put it in `.env`.
2. `uv python install 3.12`, create `pyproject.toml`, `uv sync`, spaCy DE model.
3. `config.py`, `web/app.py` with `/healthz`, Dockerfile, compose, Makefile → `make run`.
4. `llm/client.py` + `json_out.py` + tests.
5. `scripts/day1_checks.py`, run checks 1-5, paste results into architecture §12.
6. Fetch 10 German pairs (manual list in the manifest), run check 6 (P0 baseline).
7. Update `docs/architecture.md` for every resolved `[verify]`; propose commit messages.

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

## 12. Draft: consent request to Canton Bern (D-G)

Only needed if the Hugging Face dataset should contain the Bern texts. Not sent.

```text
Betreff: Anfrage zur Veröffentlichung von Texten in Leichter Sprache in einem Forschungs-Datensatz (Hack Apertus)

Sehr geehrte Damen und Herren

Wir nehmen als Team Röstigraben Bridgers am Hackathon Hack Apertus teil (Track 2B).
Unser Projekt Leicht·Facile entwirft mit dem Schweizer Sprachmodell Apertus Fassungen
amtlicher Texte in Leichter Sprache. Ein Prüfprogramm kontrolliert danach jede Frist,
jeden Betrag und jede Telefonnummer, und eine Fachperson prüft den Entwurf, bevor er
veröffentlicht wird.

Für die Auswertung vergleichen wir unsere Entwürfe mit Seiten in Leichter Sprache, die
Fachleute geschrieben haben. Dazu gehören diese Seiten des Kantons Bern, jeweils mit
der Seite in Standardsprache:

- Steuererklärung, Frist verlängern (Deutsch und Französisch):
  https://www.sv.fin.be.ch/de/start/leichte-sprache/steuern.html
  https://www.sv.fin.be.ch/fr/start/leichte-sprache/steuern.html
- Notrufnummern (Deutsch und Französisch):
  https://www.police.be.ch/de/start/leichte-sprache/notfall.html
  https://www.police.be.ch/fr/start/leichte-sprache/notfall.html
- Sozialhilfe: https://www.gsi.be.ch/de/start/leichte-sprache/soziales/sozialhilfe/sozial-hilfe.html
- Geburt melden: https://www.zivilstand.sid.be.ch/de/start/leichte-sprache/geburt.html
- Namensänderung: https://www.zivilstand.sid.be.ch/de/start/leichte-sprache/namensaenderung.html
- Abstimmung zur Berner Bildungsinitiative (PDF in Leichter Sprache vom 28. August 2026)

Bis jetzt verwenden wir die Texte nur intern. Öffentlich zeigen wir nur die Links und
Kennzahlen. Gemäss Ihren rechtlichen Hinweisen fragen wir deshalb um Ihre Zustimmung:
Dürfen wir die Texte dieser Seiten zusammen mit unseren Entwürfen in einem öffentlichen
Datensatz auf Hugging Face veröffentlichen, mit Quellenangabe und unter der Lizenz
CDLA-Permissive-2.0? Der Datensatz dient der Forschung zur Leichten Sprache und ist
für Behörden frei nutzbar.

Eine Antwort bis am 12. Oktober 2026 würde uns sehr helfen. Wir senden Ihnen den
Datensatz gerne vorher zur Durchsicht. Wenn Sie nur einem Teil der Seiten zustimmen,
hilft uns das auch.

Freundliche Grüsse

[Name]
Team Röstigraben Bridgers, Hack Apertus 2026
[E-Mail]
```

## 13. Closing the gaps (added 6 October 2026, night)

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

### 13.1 Gap register

Must = done by G3 or G4. Should = by G4 if every Must is green. Later = report §8 only.

| ID | Gap | Evidence | Criterion | Closed by | Priority |
|----|-----|----------|-----------|-----------|----------|
| GAP-01 | No headline number: P2 against P0 on CSCS still pending | `eval/report.md` holds SOURCE, REF and P0 (Public AI, 10 pairs) only | All | WP13 | Must |
| GAP-02 | P0 is a one-sentence prompt; a juror can call it a strawman | `llm/prompts/de/baseline.md` | Rigour, purposeful AI | WP13 (P0-ZH) | Must |
| GAP-03 | P2 may keep fewer facts than P0 | P0, eval, Public AI: 83 % fact coverage, 90 % hard facts kept. P2, dev, CSCS with guard: 61 % fact coverage. Repair "no progress" on 9 of 12 dev pairs (Public AI). Different splits and endpoints, but the risk is real | Rigour, value | WP13 | Must |
| GAP-04 | Identifiers are outside the fact contract: a lost reference or AHV number is a silent loss | `HARD_KINDS` = date, amount, phone, email, url, percent, time (`rules/values.py:19`) | Rigour, sovereignty story | WP14; *closed 7 Oct: `identifier` in `HARD_KINDS`* | Must |
| GAP-05 | Repair gets no concrete recipe for subordinate clauses | LEN-02 carries no suggestion; Zurich's prompt has a recipe per conjunction | Rigour | WP14 | Should |
| GAP-06 | "Why sovereignty?": every demo text is public | `data/examples/`, docs/sources.md §3 | Sovereign deployability | WP15 | Must |
| GAP-07 | "Why Apertus?": no Apertus-specific feature in use | image input verified on CSCS, not wired into ingest; Italian jobs refused | Purposeful AI | WP15 (WP12a, argument) | Should |
| GAP-08 | Prior art not addressed | Zurich's app, SUMM AI | Value, purposeful AI | WP16 | Must |
| GAP-09 | No outside voice, no target-group contact | report §6 | Value; the responsible-AI juror | WP16 (outreach) | Should |
| GAP-10 | Value stays qualitative | no minutes or francs saved per page | Value, cost | WP13 | Should |
| GAP-11 | `main` lags this log; stale counts | the evening work is not pushed (§11); README and report say 404 tests | Feasibility | WP16 | Must |
| GAP-12 | No CI: the tests run only on our machines | no `.github/` | Rigour, feasibility | WP16 | Must |
| GAP-13 | Generic pitch vocabulary; too much architecture for 2 minutes | README first screen, docs/demo-video.md | All | WP16 (§13.6) | Should |
| GAP-14 | Live-run risk | example jobs pending; CSCS cuts about 1 in 4 long thinking calls; `local-llm` never started on a GPU; no bundle | Feasibility | WP8, WP10, WP16 | Must (example jobs) |
| GAP-15 | Claims not precise enough | the voting gap is federal (Zurich publishes cantonal voting information in Leichte Sprache since 28 September 2025); A2 or B1 still open (D-E) | All | WP15, WP16 | Must |
| GAP-16 | Not listable as public-sector software | no `publiccode.yml` | Value, scalability | WP16 | Should |
| GAP-17 | UI only in English | templates use `lang="en"` | Value | WP17 | Later |
| GAP-18 | Zurich's good ideas not captured | termbase, house styles, check my own text, completeness switch, several drafts, DOCX | Value, scalability | WP17, report §8 | Later |
| GAP-19 | Long compounds reach the reviewer unsplit: the glossary exempts them from LEX-01, and the 8B ignores the split suggestion | job `287fea3aadd2` (6 Oct, web UI, CSCS): `Krankenversicherungspolice` and `Sozialversicherungsstelle` in the final draft, `Alleinstehende` flagged through two rounds | Rigour, value (the first thing a juror sees in a draft) | WP14 | Should; in by the freeze or WP17 |
| GAP-20 | The strongest sovereignty case was not described: decisions of child and adult protection authorities (KESB) and courts, explained to the person concerned in a letter that goes out with the decision | Idea from the Velum comparison (6 Oct, night; cloud session); KESB Region Solothurn has done it by hand since 2016; appeal periods of 30 and 10 days (Art. 450b ZGB) | Sovereign deployability, value | Docs written 6 Oct (night; cloud session) as a patch, not committed: `docs/use-case-decisions.md` plus references in README, architecture, report §8, sources §3, demo-video §4 (on `main` as `acab7a9` since). Demo: WP15 (D-T). Decision mode: WP17 | Must (docs, demo), Later (mode) |
| GAP-21 | The further use cases were not described: patient letters, lease terminations, penal orders, payment orders, social and school decisions, information for study participants, migration, private-sector letters | Raised 6 Oct (night): one engine, many documents; penal orders are 92 percent of Swiss convictions with a 10-day objection period; 49 percent of adults have low health literacy | Value, scalability | `docs/use-cases.md` and the planned fact checks in `docs/rules.md`, written 6 Oct (night; cloud session, 2). Modes and checks: WP17 | Should (docs), Later (modes) |
| GAP-22 | A period is no checked value: `innert 30 Tagen` yields a plain number, so a changed or invented period passes FACT-01 and FACT-06 unless the fact sheet carries it as a value | `rules/values.py` (`ValueKind`, `HARD_KINDS`); step 4 of `docs/use-case-decisions.md` claimed otherwise (corrected 6 Oct, night) | Rigour; the KESB demo's 30-day appeal period | WP14 (period kind, D-U); *closed 7 Oct, with the address kind* | Should; by the freeze or WP17 |

### 13.2 Work packages

Each WP follows the §3 conventions: tests green, ruff clean, docs in sync, one proposed
commit message per logical chunk (the owner commits). Effort is in focused hours;
model run time is not counted.

#### WP13 - Fair baselines and the headline (GAP-01, -02, -03, -10)

Goal: by G3, one table that answers "what does the pipeline add over the best single
prompt, on the same model?", with numbers a juror can trust.

- [x] **P0-ZH condition** (3-4 h). Zurich's Leichte Sprache prompt as a single-prompt
      baseline *(implemented 6 Oct, evening: conditions `P0-ZH-complete` and
      `P0-ZH-condensed`, template verified verbatim, smoke run on CSCS; the eval and
      dev runs wait for `eval/results-cscs` to be free)*:
      - `llm/prompts/de/baseline_zh.md`: their system message and user template of
        v1.6.0 with `RULES_LS`, verbatim. The MIT notice and the source commit go in a
        Jinja comment, so they never reach the model. Add `THIRD_PARTY_NOTICES.md`.
      - Two variants (D-K): `complete` (`REWRITE_COMPLETE`, our task: keep every fact)
        and `condensed` (`REWRITE_CONDENSED`, their default for Leichte Sprache).
      - Same settings as P0: 8B, thinking off, temperature 0.3, 6000 tokens. Take the
        text between the `<leichtesprache>` tags; use the whole answer when the tags
        are missing, and count how often.
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
      evening; rows in `eval/results-cscs`, numbers in docs/prompts.md)*.
- [ ] **Fact-retention diagnosis** (2-3 h, no model calls). On the stored P2 dev drafts
      (`eval/results-cscs`), classify every must-keep fact missing from the final
      version:
      - a) never requested in a repair round: more than 5 missing facts, or the loop
        stopped on "no progress";
      - b) requested, but the value came back in a surface form FACT-01 does not
        accept;
      - c) requested and added, then dropped by code (repeat filter, copy guard,
        FACT-06 guard);
      - d) requested, but the model did not write it;
      - e) marked droppable by Understand or by code completion although the reader
        needs it.

      Result: a table in docs/prompts.md ("Tested so far").
- [ ] **Fix the largest bucket** (2-6 h), then `eval run --redo` on the dev pairs.
      Candidates:
      - a facts-only repair round that "no progress" on other findings does not stop;
      - the exact value in the repair request ("Schreiben Sie genau: 31. März 2026");
      - wider FACT-01 surface forms where the value stays unambiguous;
      - every dropped addition logged with its reason.
- [ ] **Headline metrics** (1-2 h) in `eval/score.py` and `eval/report.py`:
      - *silent losses*: hard values of the source that are neither in the final text
        nor in the review checklist or omission log. For P0 and P0-ZH every missing
        value is silent. For P1 and P2 it is zero by design once identifiers are hard
        facts (WP14); say "by design" in the report;
      - invented values per 100 blocks (exists: the FACT-06 count, for every row);
      - rule errors per 100 blocks, fact coverage, hard facts kept (exist).
- [ ] **Value numbers** (1-2 h):
      - seconds and tokens per page from the usage log (exists);
      - our own review time for 3 P2 drafts in the UI, by stopwatch, labelled "team,
        not experts";
      - the drafting time per page of a professional, from the outreach answers
        (§13.7) or a published price per page. Without either, the report says so;
        no invented figure.
- [ ] **Final evaluation on CSCS** after the prompt freeze (Fri 9 Oct, 18:00):
      - P0, P0-ZH (both variants), P1 and P2 on the 20 German eval pairs;
      - P0, P1 and P2 on the 3 French eval pairs;
      - the 70B writer on 5 pairs (WP10);
      - `--redo` only where the pipeline changed;
      - first save the run started on 6 Oct as `eval/results-cscs-v1`, the fallback
        *(done 6 Oct, evening, after the other session's 70B runs)*.
        Never overwrite a result that might be needed.
- [ ] **Report §5 table**: SOURCE, REF, P0, P0-ZH complete, P0-ZH condensed, P1, P2,
      with the silent-loss column. The §1 headline follows §13.4 *(rows in place 6 Oct,
      evening; the silent-loss column waits for the headline metrics above)*.

Done when: `eval/report.md` (CSCS) has every row on the 20 German eval pairs; the
headline sentence follows §13.4; README, report §1 and the video script carry the same
three numbers.

#### WP14 - Fact contract and repair hardening (GAP-04, -05, -19, -22)

- [x] **Identifier kind** (4-6 h; *done 7 Oct as specified, plus a reference code
      given bare in the fact sheet (`2026-0042`) counts as an identifier, a keyword
      split by code (`Geschäfts·nummer`) is allowed, and a digits-only identifier also
      matches its bare number; §11*). New value kind `identifier` in `rules/values.py`,
      part of `HARD_KINDS`:
      - patterns:
        - AHV number `756.dddd.dddd.dd`;
        - IBAN and QR-IBAN: `CH`, two check digits and 17 characters, any spacing;
        - postal account `dd-d{1,6}-d`;
        - UID `CHE-ddd.ddd.ddd`;
        - a reference after a keyword. German: Referenz, Ref., Geschäftsnummer,
          Dossier, Fall, Kundennummer, Versichertennummer, Policennummer,
          Verfügung Nr. French: référence, réf., dossier, n° AVS, numéro de client,
          police;
      - matching per D-O: IBAN and AHV without spaces, everything else exactly after
        whitespace normalisation, no checksum test;
      - wired into:
        - code completion of the fact sheet (`origin: code`, must keep);
        - FACT-01 (missing: error);
        - FACT-06 (an identifier not in the source counts as an invented value);
        - the repair suggestion (the exact string);
        - "hard facts kept" in the evaluation;
      - no clash with existing kinds: phone numbers, dates, amounts, postal codes and
        form numbers (`Formular 5100`) stay what they are (tests);
      - recompute the SOURCE and REF rows (`eval reference`): the hard-fact definition
        changes for every row;
      - tests with specimen values only: the IBAN from IBAN documentation, or one with
        a wrong check digit; an AHV number with a wrong check digit. Never a random
        valid number;
      - docs: rules.md (FACT-01, FACT-06, value kinds), architecture §4.2 and §4.4,
        prompts.md (code completion), report §5 (definition of hard facts).
- [x] **Period kind** (2-3 h; D-U; GAP-22; added 6 Oct, night; cloud session, 2;
      *done 7 Oct: the canonical form keeps count and unit as written and the match
      converts, so FACT-01 names the source's own form; adjective forms (`30-tägige`)
      and ages count; a period also matches its bare count*). The
      value kind `period` as specified in `docs/rules.md` ("Planned fact checks"):
      - a number in digits or as a number word (reuse NUM-01's table) with `Tag`,
        `Arbeitstag`, `Werktag`, `Woche`, `Monat`, `Jahr` in any inflection; French
        `jour`, `jour ouvrable`, `semaine`, `mois`, `an`, `année`;
      - canonical: days for days and weeks (`2 Wochen` = `14 Tage`, which FACT-06
        already allows for plain numbers), months for months and years, working days
        on their own;
      - part of `HARD_KINDS`: code completion of the fact sheet, FACT-01, FACT-05,
        FACT-06 and "hard facts kept"; recompute SOURCE and REF (`eval reference`);
      - golden tests: `innert 30 Tagen` against `innert 20 Tagen` (FACT-01 error),
        `zwei Wochen` against `14 Tage` (no finding), `5 Arbeitstage` against
        `5 Tage` (error), an invented `10 Tage` (FACT-06 error), ages (`ab 65 Jahren`)
        kept as facts;
      - docs: move the `period` row from the planned section of rules.md into the FACT
        family, drop "planned" from step 4 of `docs/use-case-decisions.md` and from
        architecture §4.4.
- [x] **Address kind** (2-3 h; *added and done 7 Oct, in the same pass: it serves 6 of
      the 11 use cases (docs/use-cases.md §12) and the KESB demo's appeal address*).
      The value kind `address` as specified in `docs/rules.md`: street and number,
      Postfach, postcode and place, over several lines too; a postcode and place
      alone only after a boundary, never a year or a count; the street and the
      Postfach must come back when the fact has them; checked on the 35 pairs value
      by value (rules.md, "The value kinds of 7 October on the official texts").
      Not done: a Swiss postcode list (would make a bare postcode and place exact;
      WP17).
- [ ] **Clause recipes** (3-4 h German, 2 h more for French). LEN-02 and LEN-02-FR put
      a rewrite recipe for the conjunction they found into `suggestion`, which repair
      already receives (idea from Zurich's prompt, credited in rules.md; our own
      wording).
      - German:
        - `weil`, `da`: two sentences, the second starting with `Deshalb`;
        - `damit`, `um ... zu`: the aim first, then `Deshalb`;
        - `obwohl`, `auch wenn`: `Trotzdem`;
        - `wenn`, `falls`: question form `Haben Sie ...? Dann ...` (D-P, never
          `vielleicht`);
        - `als`, `nachdem`, `bevor`, `sobald`: two sentences in time order with
          `Dann`;
        - `indem`, `sodass`, `welcher`: two sentences;
        - `ob`: a direct question;
        - `dass`: a colon form (`Das bedeutet: ...`), which LEN-02 already accepts.
      - French:
        - `parce que`, `car`: `C'est pourquoi`;
        - `bien que`: `Mais`;
        - `si`: question form;
        - `pour que`, `afin que`: the aim first;
        - `lorsque`, `quand`: `Ensuite`.

        Check every French recipe against the 5 official French pages before it ships.
      - Judge prompt (DE, FR): one line saying a condition must stay a condition;
        `vielleicht` turns it into a possibility, which is a distortion.
      - Golden tests: each conjunction yields its recipe.
      - Measure on the dev pairs, before and after: LEN-02 findings per 100 blocks in
        the final version, and repair rounds without progress.

- [x] **Mediopunkt by code** (GAP-19, D-S; implemented 6 Oct, night, 5: rule, step,
      record, UI, eval column, tests, docs; dev rerun with and without the step done
      6 Oct, night, 6: docs/prompts.md "Mediopunkt by code"). Found on 6 Oct in the web UI (job `287fea3aadd2`, P2 on CSCS): the final
      draft kept `Krankenversicherungspolice` and `Sozialversicherungsstelle` unsplit
      because the writer had put them in the glossary and LEX-01 skips glossary words;
      the compounds LEX-01 did flag (`Alleinstehende`, `Einkommensgrenze`) kept their
      warning through two repair rounds because the 8B does not apply the split it is
      given. Two parts that fix different halves, detection and resolution, and only
      work together: the rule alone adds warnings the model ignores, the step alone
      leaves the glossary loophole open.
      1. *LEX-01 no longer exempts a compound because it is in the glossary.* The
         exemption stays for the non-compound branch (a long word that cannot be split
         and is explained needs no note) and for LEX-03 and GRAM-05. `_glossary_key`
         already strips the Mediopunkt, so an explained `Kranken·versicherungs·police`
         still counts as explained once it is split.
      2. *A deterministic step `rules/mediopunkt.py`* that applies the split:
         - `apply_mediopunkt(draft, level) -> tuple[Draft, list[CodeEdit]]`. Every
           block and every glossary term: a token that spaCy tags NOUN or PROPN, has
           no digit, is no URL or e-mail, and has a part longer than the level's
           `max_word_letters` gets `with_mediopunkt(part, limit)`; a capital after an
           existing dot is lowered the same way. Adjectives, participles and verbs
           (`zivilrechtlichen`, `anspruchsberechtigt`) are left to the rule: the easy
           language fix for them is another word, not `zivil·rechtlichen`. The
           suggestion comes from one helper shared with LEX-01
           (`mediopunkt_suggestion(token, limit)`), so rule and step cannot disagree.
           Idempotent: after the split every part is at most `limit` letters, LEX-01
           is silent, a second run changes nothing. Checked on the job's words: the
           splitter gives `Kranken·versicherungs·police`,
           `Sozial·versicherungs·stelle`, `Antrags·formular`, `Steuer·veranlagung`,
           `Allein·stehende`, `Einkommens·grenze` and refuses `Organisationen` and
           `Informationen`.
         - Where: `_run_pipeline`, right after `link_facts`, after write and after
           every repair, before `_check`. Before the check, not after the last round:
           warnings alone cost a polish round once nothing blocking is left, and the
           judge, the reviewer and the exports must see the same text. P1 and P2
           only, never P0 or P0-ZH (D-S): a baseline measures the prompt alone, the
           reason Zurich's `strip_markdown` stays out of P0-ZH. The CLI `check` is
           untouched: it checks a text as it is.
         - Record: `Draft.code_edits: list[CodeEdit]` (`block_id` or `"glossary"`,
           `rule_id` "LEX-01", `before`, `after`) on the version it changed; the
           audit bundle carries it with the draft; the version panel of the review
           page says "n words split by code" (DE and EN catalogs); the eval row gets
           `mediopunkt_per_100` from the final version, shown next to the LEX family
           column, so the deterministic share of the LEX improvement is visible.
         - What must not change, each as a test: `extract_values(before) ==
           extract_values(after)` (no date, amount, phone, address or identifier can
           be touched); `word_count`, `metrics.words` and the readability score
           (`readability._WORD_RE` keeps `X·Y` one word); `drop_repeats` keys.
           `eval/metrics.tokenize` keeps `·` inside the token, so a split word no
           longer equals its unsplit form in the source for SARI: strip `·` in
           `tokenize` (typography is not content; the REF rows are recomputed in the
           final run anyway) and say so in the SARI note of architecture §9.
         - Tests: the words above as cases in `tests/rules/test_lexicon.py`; LEX-01
           golden cases: a glossary compound is flagged, a glossary non-compound is
           silent; new `tests/pipeline/test_mediopunkt.py`: nouns split, adjectives
           untouched, values unchanged, glossary term split, capital after the dot
           lowered, idempotent, `code_edits` recorded; orchestrator test with stub
           stages: P0 and P0-ZH drafts untouched, P1 and P2 split before the check.
         - Docs: rules.md (LEX-01 row, a paragraph "edits made by code" in the
           calibration notes), architecture §4 (write and repair) and §9 (P1 and P2
           only, the count is reported), prompts.md "Tested so far" after the dev
           `--redo` rerun, report §5 one sentence.
         - Measure on the dev pairs, before and after: LEX-01 findings per 100 blocks
           in the final version, polish rounds saved, and 10 code splits read by hand
           for wrong joints.
         - Not now: a hyphen instead of the Mediopunkt as a house style (WP17,
           house-style profiles); French (no compounds, LEX-01-FR stays a note); the
           same mechanism for CH-01 `ß` to `ss` (the code exists in `zh_answer_text`;
           a candidate for the next deterministic edit, not before the freeze).

Done when: an identifier dropped or changed in a draft is a blocking FACT-01 or FACT-06
error with the exact string as suggestion; SOURCE and REF are recomputed; LEN-02
findings carry recipes; a long compound noun leaves a P1 or P2 job with its
Mediopunkt, glossary or not, and the count of code splits is in the bundle and the
eval row; the dev rerun shows the effect, whatever it is, in docs/prompts.md.

#### WP15 - Sovereignty and "why Apertus" evidence (GAP-06, -07, -15, -20)

- [ ] **A decision letter with personal data** (1-2 h). Team-written, at
      `data/examples/sources/verfuegung-rueckforderung-musterwil.txt` (French
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
- [ ] **Alternative per D-T: a KESB decision with personal data** (2-3 h; added 6 Oct,
      night; cloud session). Team-written, at
      `data/examples/sources/entscheid-beistandschaft-musterwil.txt`: the KESB of an
      invented region appoints a deputy (Beistand) for an invented woman in Musterwil
      who keeps deciding where she lives (docs/use-case-decisions.md §3). It contains:
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
- [ ] **One published, anonymised decision as a test** (1 h plus run time, Thu 8 Oct;
      added 6 Oct, night; cloud session): a cantonal court on an appeal against a
      KESB decision, or the Federal Supreme Court on disability insurance (free under
      Copyright Act art. 5; docs/sources.md §3). Run P2 on CSCS, read the result, note
      how the placeholders (`A.________`) and the long reasoning come out. Input for
      D-I and D-T.
- [ ] **"Why Apertus" box** (1 h) in README and report §3, five lines:
      - open weights, and open, documented training data that honours opt-outs: an
        authority can justify and audit the model;
      - a Swiss-hosted endpoint (CSCS, Lugano), and on-premise: measured on an 8 GB
        laptop GPU with a community 4-bit build, labelled as such;
      - German and French in one model, Italian next;
      - image input (if WP12a ships);
      - tokens are nearly free; the hardware is the cost.
- [ ] **WP12 split** (D-N). The spike moves to Thu 8 Oct (half a day, as in WP12).
      - WP12a, only if 3 of 3 phone photos keep every hard value: `ingest/image.py` as
        described in WP12, but for the **reviewed** workflow only. A photo or a
        scanned PDF is transcribed and goes through the existing text ingest, behind
        `FEATURE_IMAGE_INPUT`; one synthetic photographed letter in the tests; by G4.
      - WP12b, the end-user mode (`/letter`, facts box, privacy timer): after G4 only
        if everything is green, otherwise WP17.
- [ ] **Precise claims** (0.5 h):
      - write "federal voting explanations" wherever the voting gap is claimed. Zurich
        publishes cantonal voting information in Leichte Sprache since 28 September
        2025, written with Pro Infirmis and checked by test readers: cite it as proof
        of demand;
      - A2 or B1 per D-E after G3;
      - never read "hard facts kept" as "better than professionals": they leave facts
        out on purpose.
- [ ] Hardware statement (existing WP10 item): the vLLM profile on a GPU host if one is
      reachable; otherwise cite the guide and say so.

Done when: the decision letter runs P2 on CSCS with every identifier intact and is
among the example jobs; the "Why Apertus" box is in README and report; the spike
result is in architecture §4.1; WP12a has shipped or been cut by D-N.

#### WP16 - Credibility and positioning (GAP-08, -09, -11, -12, -13, -16)

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
      video traced to a command (table in §13.6). First fix: "404 tests" *(README says
      the current count since 56030bb; the first P0 scorings in `eval/results-cscs`
      used a fact sheet without code completion, fixed 6 Oct evening in `eval/run.py`;
      rescore P0 with `--redo` from the cache before the numbers are final)*.
- [ ] **Positioning paragraph** (1 h). README gets "And the Canton of Zurich's app?"
      next to "Why not one chatbot prompt?"; report §1 or §6 gets the same.
      - the sentence from §13.6, with credit to Zurich (link, licence) and SUMM AI in
        one clause;
      - the complement angle: our checks work on any draft, also one from Zurich's app
        or from a person ("verify a draft" is in WP17).
- [ ] **Messaging** (1 h): README's first screen, report §1 and the video script
      follow §13.6.
- [ ] **`publiccode.yml`** (0.5-1 h).
      - name, descriptions (en, de, fr), `developmentStatus: development`,
        `softwareType: standalone/web`, licence Apache-2.0,
        `maintenance.type: community`, languages de, fr, en, audience CH government;
      - validate it with the publiccode parser if available;
      - check whether opensource.admin.ch lists projects of non-public bodies. The
        file is useful either way.
- [ ] **Outreach** (1 h, D-Q): mail A on Wed 7 Oct, mail B on Thu 8 Oct, with the three
      example drafts (§13.7). Answers by Mon 12 Oct go into report §6 (quote) and the
      value numbers. Without an answer the report says the drafts have not yet been
      reviewed by experts or the target group.
- [ ] Optional goodwill (owner):
      - a short, friendly issue upstream: `strip_markdown` removes underscores in URLs
        and e-mail addresses;
      - once the repo is public, a pull request to awesome-apertus (maintained by
        Patrick Arnecke of the Zurich team, GitHub `rnckp`).
- [ ] **Video** (docs/demo-video.md):
      - the decision letter as the product scene;
      - FACT-06 catching an invented phone number, then repaired;
      - the headline from §13.4;
      - Zurich named only per D-L.

Done when: CI is green on `main` with a badge; the counts in README and report match
the commands; the positioning paragraph and the "Why Apertus" box are in README and
report; the outreach is sent and its outcome recorded; `publiccode.yml` validates.

#### WP17 - After 16 October (GAP-17, -18)

Before the deadline only as text in report §8 and README "Next steps". Effort is a rough
guess.

| Item | What | Why | Effort |
|------|------|-----|--------|
| Termbase | Per organisation: hard term, approved easy term, explanation, banned words. Injected into the write prompt; code checks use, consistency ("same thing, same word") and banned words | Consistent naming across all texts of a canton; Zurich planned it | 2-3 days |
| House-style profiles | Quotation marks, numbers in words, `14.00 Uhr`, thousands separator, hyphen or Mediopunkt as one profile per organisation, read by prompt and checker | Every canton has its own rules; Zurich's prompt and our checker disagree on five of them | 2 days |
| Check my own text | A web page for the deterministic checker on a text the writer wrote (the CLI `check` exists) | Useful without AI, offline, in milliseconds | 0.5-1 day |
| Complete or essentials | A switch that decides how many `omit_candidates` may go; the omission log shows what went | A real need; Zurich builds it from contradictory prompt text | 1 day |
| Several drafts | N drafts, chosen block by block by the checker (no blocking finding, every fact present) | Variety helps (Zurich's One-Klick) without making the reader compare | 1-2 days plus evaluation |
| DOCX | Easy-language layout (about 14 pt, left-aligned, one sentence per line) and a footer with date, model and prompt hash | Writers work in Word | 1 day |
| Verify a draft | Source plus any draft (Zurich's app, a person): fact sheet, FACT-01, FACT-06, rules, judge | Makes us a complement to existing tools | 2 days |
| UI in German and French | Labels and help texts in the writers' languages | The users are cantonal writers | 1-2 days |
| Italian | Rules, prompts, calibration on Ticino pairs | National coverage; Apertus's languages | 1 week |
| ZIX column | The Canton's index as an extra evaluation column, in the evaluation environment only (it loads pickled models and runs a pip fallback) | Speaks Zurich's language | 0.5 day |
| Decision mode | For letters that go out with decisions (docs/use-case-decisions.md §7): a field for the person the letter speaks to, core questions for decisions, the operative part and the appeal instructions as must-keep facts, postal addresses as a value kind, the fixed notice in the export, judge checks for neutrality, advice and conditions | The strongest sovereignty case: KESB and courts | 2-3 days |
| Planned fact checks | The rest of `docs/rules.md` "Planned fact checks": value kinds `quantity`, `schedule`, `medication` (`period`, `identifier` and `address` exist since 7 Oct), a Swiss postcode list for bare postcodes; checks `FACT-07` (fixed notice), `FACT-08` (operative part and appeal instructions kept), `FACT-09` (a medication in one block); judge questions `SEM-08` (modality, conditions), `SEM-09` (no advice, no evaluation), `SEM-10` (every period keeps its start) | The further use cases (`docs/use-cases.md` §12) | 3-4 days |
| Patient letters | Medical mode: the kinds `quantity`, `schedule`, `medication`, `FACT-09`, `SEM-08`, Apertus-70B-MeditronFO as judge, an assessment under the Medical Devices Ordinance, a pilot with a hospital (`docs/use-cases.md` §3) | Health data, 49 percent low health literacy; the strongest case after courts | 1-2 weeks plus the legal assessment |
| Helpers for received letters | Lease terminations and payment orders for tenants' associations, social services and debt counselling: WP12b with the period kind and the facts box (`docs/use-cases.md` §4, §6) | Reach; a 10- or 30-day period decides | with WP12b |
| WP12b | The end-user letter mode | Reach | as in WP12 |
| Pilot | A canton's easy-language office, target-group tests | Value | weeks |
| LoRA | From reviewer edits (architecture §4.8) | Cost, quality | as before |

"Check my own text" may move before G4, but only if WP13-WP16 are done by Sat 10 Oct.

### 13.3 Schedule from 7 October

The gates keep their names and dates from §4 and gain the items below (G1 and G2 were
passed on 6 Oct).

| Date | Focus | Gate (end of day) |
|------|-------|-------------------|
| Wed 7 Oct | Push the evening work; CI; P0-ZH condition and its runs (eval and dev); mail A; save the CSCS run of 6 Oct as `eval/results-cscs-v1` and read its numbers; *done this day as well: the value kinds `identifier`, `period` and `address` (WP14), REF rows recomputed* | CI green on `main`; P0-ZH numbers on 20 eval pairs |
| Thu 8 Oct | Identifier kind; decision letter; fact-retention diagnosis; WP12 spike (half a day); mail B with three drafts; KESB decision (D-T) and one published, anonymised decision as a test (WP15); period kind if the identifier kind is in (D-U, WP14) | D-N and D-O decided; diagnosis table in prompts.md; D-T decided and D-I revisited; D-U decided |
| Fri 9 Oct | Fix the largest fact-loss bucket; clause recipes (German); Mediopunkt by code (WP14, D-S); dev rerun with `--redo`; **prompt freeze 18:00**; final CSCS evaluation overnight | Final run started |
| Sat 10 Oct | Read the numbers per §13.4; value numbers (review stopwatch) | **G3**: every §5 row on CSCS, P0-ZH included; headline decided (D-M) |
| Sun 11 Oct | Example jobs with the decision letter (WP8); WP12a if the spike passed; positioning paragraph, "Why Apertus", precise claims | Example jobs in the image |
| Mon 12 Oct | `publiccode.yml`; numbers audit; docs in sync; outreach answers in; video storyboard | **G4**: feature freeze, as before |
| Tue 13 Oct | WP10 rest (8B vs 70B, κ labelling, hallucination spot check); report tables final; report §8 from WP17; D-G, D-L | All report tables filled |
| Wed 14 Oct | Report draft, video recording, clean-checkout test on Linux and on Windows | **G5** as before, plus CI green on the final commit |
| Thu 15 Oct | PDF, numbers audit again, repo public, awesome-apertus pull request prepared | **G6**, as before |
| Fri 16 Oct | Submit before 12:00 CEST | Submitted |

If the CSCS evaluation stalls (dropped streams, quota): P0 and P0-ZH may run on Public
AI, labelled as such; P2 numbers come only from CSCS; the v1 results are the fallback.

If one person with agents does the work: agents take the identifier kind (WP14), CI
and `publiccode.yml` (WP16) next to the evaluation runs. The owner keeps the diagnosis,
the decision letter and every text a juror reads.

### 13.4 Reading the numbers at G3 (D-M)

Compare P2 with P0-ZH `complete` on the 20 German eval pairs on CSCS, and decide by
these rules, no debate:

| Case | When | Headline |
|------|------|----------|
| A | P2 has fewer invented values and fewer rule errors per 100 blocks, and its fact coverage is at most 5 points below P0-ZH | "Same model, the best public Swiss prompt against our pipeline: X fewer invented values and Y fewer rule errors per 100 blocks, and every missing fact is listed for the reviewer." |
| B | P2 is better on invented values or rule errors, but more than 5 points below on fact coverage | Lead with "no silent loss": P0-ZH loses Z % of the hard facts without telling anyone, P2 lists every one. State the coverage gap openly, with the fix from the WP13 diagnosis as next step. No code-written fact sentences in the evaluated text (D-R). |
| C | P0-ZH is as good or better on rules and facts | Reposition as the verification layer: "We ran the best single prompt through our checks: N invented values and M lost facts that nobody saw." The write stage becomes a replaceable part, and "verify a draft" moves to the top of report §8. |
| D | The final run fails on more than a quarter of the pairs | Report the v1 and dev numbers, labelled, with the failure rate; no headline comparison with P0-ZH. |

In every case: the same numbers in README, report §5 and the video, and never a number
without its endpoint and split.

Applied on 6 October (evening) to the numbers then on hand (CSCS, 20 German eval pairs,
8B): **case B**. P2 against P0-ZH `complete`: rule errors 4.3 against 15.4 per 100
blocks, invented values 0.1 against 0.0, fact coverage 84 against 91 percent (7 points),
hard facts kept 80 against 95 percent; the condensed variant (their default) keeps 77
percent of the hard facts. The headline sentence itself waits for the owner (D-M at G3)
and for the Friday rerun.

### 13.5 Cut list, revised (replaces §7 from 7 October)

Apply in this order when a gate is missed:

1. LoRA (report only).
2. WP17 items (report §8 only), "check my own text" included.
3. Cross-language consistency check.
4. DOCX export and `make bundle`.
5. WP12b, the end-user letter mode.
6. `publiccode.yml`.
7. Italian.
8. Clause recipes for French (German stays).
9. Outreach follow-ups (mails already sent stay sent; no second round).
10. WP12a, image ingest for the reviewed workflow.
11. 70B writer comparison (the 70B judge stays).
12. P0-ZH `condensed` (`complete` stays).
13. French.
14. B1 level.
15. UI polish: a single review page without the version switcher.
16. Judge κ labelling: 30 items down to 15, stated in the report.

Mediopunkt by code (WP14) is not on this list: both parts go in before the freeze or
both move to WP17 with a sentence in report §7. A checker change after the final run
would make its numbers stale, and the rule change alone adds warnings nobody fixes.

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

### 13.6 Messaging and numbers audit

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
| Number of rules (42, plus any new ones) | the rule registry; `tests/rules/test_registry.py` compares it with rules.md |
| Number of tests | `uv run pytest --collect-only -q`, last line |
| Pairs: 35 (30 German, 5 French; 20 and 3 held out) | `data/pairs/manifest.jsonl` |
| Checker on official pages: about 2 errors per 100 blocks | `make calibrate` |
| Every evaluation number | `eval/report.md` from `make eval RESULTS=eval/results-cscs` |
| 844'000 | SBFI press release of 23 October 2025 (wording check in demo-video.md §4) |
| Laptop GPU figures | architecture §10, labelled as a community 4-bit build |

### 13.7 Outreach drafts (D-Q)

Only synthetic letters and their outputs leave the team; never a rewrite of a protected
page. Fill in the placeholders; send A on Wed 7 Oct, B on Thu 8 Oct.

**A. Team Data, Office for Statistics and Data, Canton of Zurich**

```text
An: datashop@statistik.zh.ch
Betreff: «Sprache vereinfachen» als Vergleich im Hackathon Hack Apertus: kurze Rückmeldung möglich?

Guten Tag

Wir sind das Team Röstigraben Bridgers und nehmen am Hackathon Hack Apertus teil
(Track 2B, Abgabe am 16. Oktober 2026). Unser Projekt Leicht·Facile entwirft mit dem
Schweizer Sprachmodell Apertus Texte in Leichter Sprache. Danach prüft Programmcode
jede Frist, jeden Betrag und jede Telefonnummer gegen das Original, und eine
Fachperson entscheidet über jeden Abschnitt. Alles läuft auf Infrastruktur, welche
die Verwaltung selbst kontrolliert.

Ihre App «Sprache vereinfachen» ist für uns die beste öffentliche Grundlage in der
Schweiz. Wir verwenden deshalb Ihren Prompt für Leichte Sprache (Version 1.6.0,
MIT-Lizenz, mit Quellenangabe) in unserer Auswertung als Vergleich: dasselbe Modell,
einmal mit Ihrem Prompt, einmal mit unserem Ablauf. Die Zahlen senden wir Ihnen gerne.

Zwei Fragen:

1. Verwenden Ihre Mitarbeitenden für Leichte Sprache meistens «Text verdichten» oder
   die vollständige Fassung? Wir möchten Ihren Prompt fair einsetzen.
2. Dürfen wir eine kurze Einschätzung von Ihnen (zwei bis drei Sätze) in unserem
   Bericht zitieren? Eine Antwort bis am 12. Oktober 2026 würde uns sehr helfen.

Beim Vergleich ist uns aufgefallen, dass die Funktion strip_markdown alle Unterstriche
entfernt, auch in Web-Adressen wie .../praemienverbilligung_krankenversicherung.html
und in E-Mail-Adressen. Gerne erfassen wir dazu ein Issue auf GitHub.

Freundliche Grüsse

[Name]
Team Röstigraben Bridgers, Hack Apertus 2026
[E-Mail]
[Link zum Repository, sobald es öffentlich ist]
```

**B. An easy-language office** (Büro für Leichte Sprache of Pro Infirmis, or a
cantonal office in St. Gallen or Bern; St. Gallen is a main partner of the hackathon)

```text
An: [Fachstelle]
Betreff: 20 Minuten Fachblick auf drei Entwürfe in Leichter Sprache? (Hackathon-Projekt)

Guten Tag

Wir sind das Team Röstigraben Bridgers und nehmen am Hackathon Hack Apertus teil.
Unser Projekt Leicht·Facile ist ein Hilfsmittel für Fachleute wie Sie: Das Schweizer
Sprachmodell Apertus schreibt einen Entwurf in Leichter Sprache. Programmcode prüft
jede Frist, jeden Betrag und jede Telefonnummer gegen das Original. Eine Fachperson
entscheidet über jeden Abschnitt. Die Prüfung durch Menschen aus der Zielgruppe
ersetzt das Werkzeug nicht.

Wir möchten wissen, ob unsere Entwürfe Fachleuten Arbeit abnehmen. Hätten Sie etwa
20 Minuten Zeit für drei kurze Entwürfe? Die Ausgangstexte sind von uns erfundene
Briefe ohne echte Personendaten. Wir senden Ihnen Original und Entwurf als PDF.

Unsere drei Fragen:

1. Wie lange brauchen Sie für eine solche Seite, wenn Sie sie selbst schreiben?
2. Was müssten Sie an unseren Entwürfen ändern, bevor Sie sie prüfen lassen würden?
3. Dürfen wir Ihre Einschätzung in unserem Bericht zitieren, mit Ihrem Namen oder
   ohne?

Eine Antwort bis am 12. Oktober 2026 würde uns sehr helfen. Auch eine kurze Antwort
hilft uns.

Freundliche Grüsse

[Name]
Team Röstigraben Bridgers, Hack Apertus 2026
[E-Mail]
```
