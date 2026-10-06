# Technical report - Leicht·Facile

Easy-language drafts of Swiss official texts with Apertus, with every fact checked by
code.

- **Track:** Track 2B - Own Project
- **Event:** Hack Apertus 2026, online
- **Team:** Röstigraben Bridgers - `member`, `member`, `member`
- **Repository:** https://github.com/bobrovsky420/leicht-facile
- **Demo:** `link to video`

Status of this report: 6 October 2026. Everything that has been designed, decided or
built is described; numbers that need the CSCS endpoint are marked **[pending]** and
are filled in from `make eval`.

## 1. Summary

**Problem.** About 844'000 adults in Switzerland aged 16 to 65 (15%) have low reading
skills (PIAAC 2023). People with intellectual disabilities, people learning a national
language and people with dementia need easy language too. None of them should be
excluded from the official letters that decide their money, deadlines and rights. Federal and cantonal
accessibility law asks authorities to publish important information in Leichte
Sprache, FALC or lingua facile, but each version is written by hand by a small number
of trained writers, and every deadline, amount and phone number must be checked
against the original.

**Approach.** Leicht·Facile is a drafting assistant for those writers. It rests on one
rule: *Apertus does everything that needs language understanding; plain code does
everything that can be counted.* Apertus 1.5 turns the document into a fact sheet,
writes a draft against it with provenance for every sentence, judges meaning with a
second, larger model, and repairs only the flagged sentences. Code checks 41
published easy-language rules and the exact presence of every fact value. A human
reviews source and draft side by side and exports the text with an audit trail. The
whole system is one container plus an OpenAI-compatible Apertus endpoint, so it runs
on-premise, air-gapped or on a Swiss cloud.

**Why not one prompt.** "Rewrite this in Leichte Sprache" gives text with no fact
contract, no provenance, no omission log and no independent check. That prompt is our
baseline condition C0; the full pipeline is C2.

**Headline result.** **[pending]** fact coverage, invented statements and rule
violations of C2 against C0 on the held-out German pairs.

The team name is meant as a bridge between authorities and the people they write to,
not between languages: each language version is simplified from its own original.

## 2. Architecture

```text
Browser (review UI)
   |
leicht-facile container (FastAPI, Python 3.14)
   Ingest (code) -> Understand (Apertus) -> Write (Apertus) -> Rule check (code)
                                                   \-> Judge (Apertus) -> Repair (Apertus)
   -> Review (human) -> Export (code)
   SQLite + JSON artifacts on a mounted volume; one LLM client for all model calls
   |
Apertus endpoint: CSCS API | local vLLM | Swiss sovereign cloud
```

The full diagram is in [docs/architecture.md](docs/architecture.md) §3.

| Stage | Done by | Output |
|-------|---------|--------|
| Ingest | Code: `trafilatura` for HTML, `pdfplumber` for PDFs (column-aware, headers and footers removed), paragraph rules for text; spaCy sentence splitting with a merge step for German abbreviations and dates | `SourceDocument`: segments with stable ids (`s0001`), kind, heading path |
| Understand | Apertus 8B, thinking | `FactSheet`: the reader's core questions (what, what to do, by when, cost, contact), typed facts with normalised values and source ids, hard terms, droppable passages. Code then adds every date, amount, phone number, e-mail, URL, percentage and time the model missed |
| Write | Apertus 8B, thinking | `Draft`: blocks with the fact ids they carry and the source segments they come from, omissions with reasons, glossary. Code links each block to every fact whose exact value it contains |
| Rule check | Code (spaCy morphology and dependency parse, regex, word frequencies) | `RuleFindings` with rule id, severity, evidence and a suggestion; document metrics |
| Judge | Apertus 70B, thinking | `JudgeReport`: each fact present, missing or distorted; unsupported (invented) blocks; semantic findings. The judge never rewrites |
| Repair | Apertus 8B | New text for flagged blocks only, plus sentences for missing facts; up to 3 rounds; every version kept |
| Review and export | Human, then code | Per-block decisions; Markdown and HTML (one sentence per line, at most 85 characters) and a JSON audit bundle |

Key decisions:

- **Countable rules in code, meaning in the model.** Sentence length, passive,
  genitive, Konjunktiv, nominalisations, numbers, Swiss date, time and phone formats,
  `ss` for `ß`, the Mediopunkt in long compounds, and fact coverage are decided by
  code: exact, free, reproducible, and the model does not grade its own homework.
  41 deterministic German rules are registered once in code with their severity per
  level and the instruction for the writer prompt. The writer's style guide is
  rendered from that registry, and a test fails if the registry and the catalogue in
  [docs/rules.md](docs/rules.md) disagree.
- **Fact coverage (rule FACT-01) is the central check.** Every must-keep fact with a
  normalised value must appear in the draft in an accepted surface form
  (`31. März 2026`, `31.3.2026`, ...). A deadline that silently became 30 March is
  caught exactly.
- **Typed, persisted artifacts.** Each stage reads and writes pydantic models stored
  in SQLite. A failed job resumes from the last good stage, every intermediate result
  is visible in the UI, and the evaluation reuses the same artifacts.
- **Writer and judge are different models.** The 70B judge checks the 8B writer.
- **One service.** FastAPI serves the API and a server-rendered review UI (Jinja2, one
  vendored classless stylesheet, a small script); a single worker thread runs the
  jobs. No Node build, no message broker, no CDN.

### Target architecture (mandatory)

Leicht·Facile is deployable in all three architectures. The only runtime dependency
is the Apertus endpoint in `LLM_BASE_URL`; changing the deployment means changing that
variable.

| Architecture | How it is met |
|--------------|---------------|
| a) On-premise | `docker compose --profile local-llm up` adds a vLLM service from the official image `ghcr.io/swiss-ai/vllm_apertus_1.5_release` serving Apertus 1.5 8B on one GPU with the Apertus reasoning parser; the app points at `http://vllm:8000/v1`. A llama.cpp profile serves a 4-bit 8B on an 8 GB laptop GPU for small offices. |
| b) Air-gapped | As (a), with images and weights pulled in advance. Python packages, the spaCy model and UI assets are baked into the image; no telemetry, no CDN, no package installs at runtime. |
| c) Sovereign Swiss cloud | `LLM_BASE_URL` points at a Swiss-operated Apertus endpoint. The hackathon demo runs against the CSCS inference API in Lugano. |

| | Build time | Runtime |
|---|------------|---------|
| Network | PyPI (locked by `uv.lock`), the spaCy model wheel from GitHub, base images from Docker Hub and GHCR | The Apertus endpoint only; a URL the user submits is fetched on request |
| Storage | - | Named volume `appdata`: SQLite database, artifacts, optional response cache |

The container runs as a non-root user with a Docker health check. Document text is
never logged above `DEBUG`. The prototype has no login and is meant to run behind the
organisation's reverse proxy.

Hardware for (a) and (b): the 8B in bf16 needs about 16 GB for the weights plus KV
cache, so a 24 GB GPU with a reduced context is realistic; the FP8 build is 11.4 GB.
**[pending]** a measured run of the vLLM profile on a GPU host. Measured so far: on a
laptop RTX 4060 (8 GB) with llama.cpp and a community 4-bit conversion, about 37
tokens per second at short context and 17 near 16k; Understand took about 1.5 minutes
and Write with thinking about 12 minutes for a 400-word letter.

## 3. Use of Apertus

- **Models:** `swiss-ai/Apertus-v1.5-8B` (writer: Understand, Write, Repair, baseline)
  and `swiss-ai/Apertus-v1.5-70B` (judge), both in thinking mode where noted. Both are
  set by environment variables (`LLM_NAME`, `LLM_JUDGE_NAME`); an 8B-vs-70B writer
  comparison is part of the evaluation.
- **How it is used:** inference, as a structured-output agent pipeline (no tool
  calling: the thinking variants are served with tools disabled, and the pipeline does
  not need them). Fine-tuning is not part of the submission (§8).
- **Where it runs:** the CSCS inference API for the hackathon; the same client works
  unchanged with local vLLM, llama.cpp or a Swiss cloud endpoint.

| Stage | Model | Thinking | Temperature | max_tokens |
|-------|-------|----------|-------------|------------|
| Understand | 8B | on | 0.1 | 12000 |
| Write | 8B | on | 0.3 | 16000 |
| Judge | 70B | on | 0.0 | 12000 |
| Repair | 8B | off | 0.2 | 8000 |
| Baseline C0 | 8B | off | 0.3 | 6000 |

**Prompts** ([docs/prompts.md](docs/prompts.md)). German instructions for German
documents. Each prompt shows one filled JSON example instead of the JSON schema; small
models copy an example more reliably, at a fraction of the tokens. Source sentences
carry ids (`[s0004]`) and draft blocks carry ids (`[b007]`): the model cites, code
verifies that the ids exist. The writer prompt asks for a plan first (the reader's
questions as headings), contains the style guide rendered from the rule registry for
the chosen level, and two short example pairs written by the team (cantonal pages may
not be reproduced, and no evaluation pair leaks into a prompt). The repair prompt
receives only the flagged blocks, their findings with the checker's suggestion, and
the facts they must keep. Every prompt is identified by a hash of its template, stored
with each result.

**Structured output.** The answer is stripped of reasoning (from `reasoning_content`,
or inline `<|inner_prefix|> ... <|inner_suffix|>` or `<think>` tokens), control tokens
and code fences, parsed leniently (an 8B model writes `s4` for `s0004` or a string
where a list was asked for) and validated with pydantic. On failure the validation
error goes back to the model once. Output cut off while still reasoning is reported as
truncated.

**Reliability.** Retries on 429, 5xx and connection errors with exponential backoff,
jitter and `Retry-After`; a response cache keyed by model, messages and parameters
for development and evaluation reruns; every call is logged with stage, model, tokens
and latency, so each job shows its cost.

**Other models.** No other language model is used at runtime or in the evaluation.
The rule checker uses spaCy's `de_core_news_md` (a small statistical parser for
part-of-speech, morphology and dependencies, not a generative model) and the
`wordfreq` word frequency lists. During development without a CSCS key, the prompts
were tested against the same Apertus 1.5 8B through llama.cpp, using the community
conversion `Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF` (4-bit, unofficial). Numbers from
that setup are labelled as such and never mixed with CSCS results.

## 4. Data

| Data | Origin | Licence and handling |
|------|--------|----------------------|
| Reference pairs: 35 documents with an official easy-language version (30 German: 20 `eval`, 10 `dev`; 5 French: 3 `eval`, 2 `dev`) | Cantons Zürich, Bern, St. Gallen, Luzern, Basel-Stadt, Graubünden, Zug, Geneva, Neuchâtel; federal offices BAG, BWL, EBGB | The publishers allow personal use only. The repository holds only the manifest (`data/pairs/manifest.jsonl`: URLs, section, word counts, fact estimate, licence note per pair); `eval fetch` caches the texts locally in a git-ignored folder. Every URL was checked on 5 October 2026 |
| Example documents and few-shot examples | Written by the team; invented municipality, reserved `.example` domains, the style-guide example phone number | Part of the repository, under the project licence |
| Hard texts for tests and the presentation | Written by the team in the style of official letters | Same |
| Demo documents (planned) | Federal Council explanations for a past federal vote, a text with no easy-language version (Swiss Copyright Act art. 5: official reports and enactments are not protected) | Bill text and the Federal Council's parts only; committee texts and images are not used |

`dev` pairs are used for prompt development and checker calibration, `eval` pairs are
held out for the reported numbers. No personal data is used: the reference pairs are
public web pages, all other texts are written by the team. Developing and evaluating
against protected pages needs no consent as long as neither the texts nor our rewrites
of them are published (Copyright Act articles 24a and 24d; our reading, not legal
advice; details in [docs/sources.md](docs/sources.md) §4). An optional Hugging Face
dataset would therefore contain the manifest, metrics, and article-5 texts with our
outputs, with instance-level licence fields. **[pending]** decision on publishing it.

## 5. Evaluation

**Task.** Simplify a standard-language official text to level A2 (Leichte Sprache)
and keep every fact. Each held-out pair is run under three conditions with the 8B
writer:

| Code | Condition | Measures the value of |
|------|-----------|-----------------------|
| C0 | One prompt: "Schreiben Sie diesen Text in Leichter Sprache:" | Baseline: what a user gets from a chatbot |
| C1 | Understand, Write, rule check; no judge, no repair | Fact sheet, planning and provenance |
| C2 | Full pipeline with judge and repair | Checking and repairing |

Two reference rows need no model: SOURCE (the original, scored as if it were a draft)
and REF (the official easy-language version written by professionals).

**Metrics.** All rows are scored the same way, on the final text:

- *Fact coverage*: share of must-keep facts with a normalised value found in the
  output (exact, code), against one fact sheet per pair.
- *Hard facts kept*: share of the source's dates, amounts, phone numbers, e-mail and
  web addresses, percentages and times found in the output (exact, code, no model;
  comparable with REF).
- *Fact status and invented statements*: present, missing or distorted facts, and
  unsupported blocks per 100 blocks, from the 70B judge.
- *Rule violations*: errors and warnings per 100 blocks, by rule family.
- *Readability*: Amstad index (German Flesch) for source, output and REF.
- *SARI* against the official easy version (document level, a port of the original
  `SARI.py`, checked bit for bit).
- *Cost and speed*: tokens, latency and estimated cost per page of 250 words.

**[pending]** results on the 20 held-out German pairs:

| Setup | Fact coverage | Hard facts kept | Invented / 100 blocks | Rule errors / 100 blocks | Amstad | SARI |
|-------|---------------|-----------------|-----------------------|--------------------------|--------|------|
| SOURCE | | | - | | | - |
| REF (official) | | | - | | | |
| C0 baseline | | | | | | |
| C1 | | | | | | |
| C2 (ours) | | | | | | |

**[pending]** 8B vs. 70B writer on a subset: quality, tokens, latency, cost per page.

**Judge reliability.** The judge is measured, not assumed: agreement (Cohen's κ)
between the judge and hand labels on 30 (fact, draft) items. **[pending]**

**Checker calibration.** Official easy-language pages are written by professionals,
so the checker should raise almost no errors on them; each error is a real deviation
or a false positive to fix. **[pending]** errors per 100 blocks on the reference
pages, recorded in [docs/rules.md](docs/rules.md).

**Tests.** 404 automated tests run without network: golden sentences for every rule
(at least two that trigger it, one that must not), the team's hard texts, the client
against a fake OpenAI-compatible endpoint, the orchestrator with recorded model
outputs, the evaluation metrics, and the web API.

## 6. Limitations

- **A2 with an 8B model is not guaranteed.** The fact sheet, examples and repair loop
  are meant to compensate; if they do not, B1 (Einfache Sprache) becomes the primary
  level and the gap is reported with numbers.
- **Not a certification.** Easy-language texts must be tested by readers from the
  target group. The tool prepares that test; it does not replace it.
- **German first.** French and Italian run through the same pipeline but get only the
  language-independent rules (facts, layout, readability) until their rule sets and
  prompts ship. The B1 thresholds are our own choice; no official Swiss B1 rule set
  exists.
- **Judge is a model.** Meaning checks (distortion, invention, metaphors, unclear
  references) depend on the 70B judge; its agreement with hand labels is reported.
- **Fact coverage needs values.** Exact checks cover facts with a normalised value
  (dates, amounts, contacts); obligations and conditions without a value rely on the
  judge. Many easy-language pages carry few such facts, so coverage is reported on the
  fact-rich subset as well.
- **Not yet supported:** scanned PDFs and photos (Apertus 1.5 reads images, but image
  input through the CSCS API is unverified), DOCX export, the air-gapped image bundle.
- **Live pages change.** Evaluation uses cached copies with a fetch date; a page
  submitted live may have moved or changed.
- **Rule NUM-08** (phone numbers without `+41`) is under review: official Zürich pages
  use `+41`.
- **No login** in the prototype.

## 7. Reproducibility

- **Run:** `cp .env.example .env`, set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_NAME`,
  then `make run` and open http://localhost:8000. `make check-llm` makes one call to
  the endpoint; `make smoke` runs a bundled example letter through the full pipeline.
- **Numbers:** `make eval` fetches the pairs, scores the references, runs C0, C1 and
  C2 with the response cache on (an interrupted run resumes), and writes the report
  tables. `make calibrate` runs the checker on the official pages without a model.
- **Environment:** Python 3.14 in `python:3.14-slim`; dependencies locked in
  `uv.lock`; spaCy `de_core_news_md` 3.8.0 pinned by wheel URL; uv 0.12.18.
- **Models and prompts:** model names and stage settings as in §3; each result
  stores the hash of the prompt template that produced it. Sampling temperatures above
  zero are not seeded; reruns reproduce exact outputs through the response cache.
- **Hardware:** the CSCS endpoint for all reported numbers. **[pending]** exact commit
  of the reported run.

## 8. Next steps

- French (FALC) and Italian (lingua facile) rule sets, prompts and evaluation, with a
  consistency check across the three fact sheets of one document.
- Image input for scanned letters and photos.
- Learning from review: approved drafts as training data and reviewer edits as
  preference pairs for a LoRA on the 8B writer with the official Apertus fine-tuning
  recipes, so that a small on-premise model reaches the 70B judge's standard.
- DOCX export (writers work in Word) and an air-gapped image bundle.
- A pilot with a cantonal easy-language office and target-group testing of the
  drafts.
- Beyond the public sector: insurers, pension funds and utilities send some of the
  least readable letters people receive.

## License

Code: Apache License 2.0 ([LICENSE](LICENSE)). This report: Creative Commons
Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

## References

- Apertus v1.5 model card: https://huggingface.co/swiss-ai/Apertus-v1.5-8B
- Apertus vLLM serving guide: https://apertus-ai.org/docs/guides/vllm/
- CSCS LLM inference API: https://docs.cscs.ch/services/inference/api/
- Canton of Zürich, rules for Leichte Sprache:
  https://www.zh.ch/de/webangebote-entwickeln-und-gestalten/inhalt/barrierefreiheit/regeln-fuer-leichte-sprache.html
- EBGB, Leitfaden Leichte Sprache:
  https://www.ebgb.admin.ch/dam/de/sd-web/ZHKNDzIYahOc/Leitfaden%20Leichte%20Sprache.pdf
- Inclusion Europe, "Information for all" (German, French and Italian editions)
- SBFI, PIAAC 2023 results for Switzerland (press release, 23 October 2025):
  https://www.sbfi.admin.ch/de/newnsb/JrHo0f0D4ssv3Nu8Ee678
- Amstad, T. (1978): Wie verständlich sind unsere Zeitungen? (German readability index)
- Xu, W. et al. (2016): Optimizing Statistical Machine Translation for Text
  Simplification. TACL 4 (SARI)
- Swiss Copyright Act (URG), articles 5, 24a, 24d: https://www.fedlex.admin.ch/eli/cc/1993/1798_1798_1798/de
