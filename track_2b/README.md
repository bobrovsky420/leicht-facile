# Leicht·Facile

[![CI](https://github.com/bobrovsky420/leicht-facile/actions/workflows/ci.yml/badge.svg)](https://github.com/bobrovsky420/leicht-facile/actions/workflows/ci.yml)

Leicht·Facile drafts easy-language versions of Swiss official texts (German Leichte
Sprache and Einfache Sprache, French FALC; Italian follows) with Apertus, and proves with code that
no deadline, amount or phone number got lost. It is a drafting assistant for the
people who write official texts, from trained easy-language writers to case workers,
not a replacement for their review or for the test by readers from the target group.

About 1.25 million adults in Switzerland aged 16 to 65 (22 percent) have low reading
skills (Swiss Federal Statistical Office, PIAAC 2022/23). None of them should be excluded from the official
letters that decide their money, deadlines and rights.

Two use cases: a canton's letters and web pages
([track_2b/docs/use-case-canton.md](docs/use-case-canton.md)), and easy-language letters that
accompany decisions of child and adult protection authorities (KESB) and courts, texts
that may never leave the authority (decision mode v1;
[track_2b/docs/use-case-decisions.md](docs/use-case-decisions.md)). Further use cases, from patient letters and lease terminations to
penal orders, payment orders and tax letters, are sketched in
[track_2b/docs/use-cases.md](docs/use-cases.md). Most of them are under official, medical or
tax secrecy and may not go to a chatbot on a foreign cloud: for them, Apertus is the
only model that fits ([why](#why-only-apertus)).

**Hack Apertus 2026, Track 2B (own project).** Team Röstigraben Bridgers: Alexander
Bobrovsky (bobrovsky@seznam.cz) and Ivan Kuzmych (i.kuzmych@hotmail.com).
Technical report: [track_2b/technical_report.md](technical_report.md) (PDF:
`track_2b/RoestigrabenBridgers_Report.pdf`). Demo video: **[PENDING: video URL]**. Maturity: a
deployable prototype for German and French drafts of public texts and letters, a proof
of concept for decisions **[OWNER: confirm]**. Built with AI coding assistants (report §3).

> Apertus does everything that needs language understanding. Plain code does
> everything that can be counted.

1. **Understand** (Apertus): the document becomes a fact sheet: the reader's core
   questions, every fact with its exact value, hard words, passages that can go.
   Code adds every date, amount and contact the model missed.
2. **Write** (Apertus): a draft in easy language, every sentence linked to the source
   sentences it comes from, every omission explained.
3. **Check** (code): 45 deterministic rules from the published Swiss guidelines
   (sentence length, passive, genitive, numbers, Swiss spelling, Mediopunkt, ...) and
   an exact check of every fact value in both directions (no value lost, no value
   invented), in milliseconds, without a model.
4. **Judge** (a second, larger Apertus model): meaning only: distorted facts, invented
   statements, metaphors, unclear references.
5. **Repair** (Apertus): only the flagged sentences, until no blocking finding is left
   (at most 3 rounds); then one sentence for each must-keep value still missing (at
   most 10), checked like the rest.
6. **Review** (human): source and draft side by side, provenance, fact checklist,
   approve, edit or reject each block, export with an audit trail.

### Why not one chatbot prompt?

"Rewrite this in Leichte Sprache" gives a text with no fact contract, no provenance,
no omission log and no independent check, and the chatbots people reach for run on
foreign clouds. Leicht·Facile adds exactly those four things, a review workflow and
an audit trail, and runs on infrastructure the organisation controls. The evaluation
measures the difference: the single prompt is the baseline condition P0, the full
pipeline is P2 (P as in pipeline, not a language level;
[track_2b/docs/use-case-canton.md](docs/use-case-canton.md) §4).

### Why only Apertus

For a public web page, any good model would do. A letter that names a person is under
official secrecy, a patient letter under medical secrecy, a tax letter under tax
secrecy. Four conditions follow, and only Apertus meets all four:

| Condition | Rules out | Apertus |
|-----------|-----------|---------|
| The text stays inside the organisation (secrecy law; the cantonal data protection commissioners' resolution of November 2025) | Chatbots and model APIs on foreign clouds | Runs on-premise or air-gapped: the 8B on one 24 GB GPU with the official vLLM image (run by the team on an NVIDIA L4); Swisscom and Infomaniak serve the 70B in Switzerland |
| The organisation runs the model itself | Closed models | Open weights |
| The organisation can account for what the model learned | Open-weight models that keep their training data secret (Llama, Gemma, Qwen, Mistral) | Open training data and code; website opt-outs honoured, also for older crawls |
| The model is Swiss | Fully open models built and trained abroad (EuroLLM, SmolLM3) | Built by EPFL, ETH Zurich and CSCS, trained in Lugano; German, French and Italian, with Swiss German and Romansh data |

The Canton of Ticino already runs Apertus in-house to translate sensitive government
documents. Tokens are nearly free (about one US cent per page for the full pipeline at
Public AI's list prices, report §5); on own hardware the GPU is the cost. The legal
basis, the sources and the use cases:
[track_2b/docs/use-cases.md §2](docs/use-cases.md#why-only-apertus).

## Quick start

Requirements: Docker with Compose, `make`, and an API key for an Apertus endpoint
(the hackathon's CSCS key by default).

```bash
cp .env.example .env      # set LLM_BASE_URL, LLM_API_KEY, LLM_NAME (CSCS by default)
make run                  # builds and starts the container, opens http://localhost:8000
```

The three variables can also come from the shell, without a `.env` file:

```bash
export LLM_BASE_URL=https://api.inference.cscs.ch/v1 LLM_API_KEY=... LLM_NAME=swiss-ai/Apertus-v1.5-8B
make run
```

For these three, a value in the shell wins over `.env`; every other setting comes from
`.env` or its default.

`make run` opens the web UI in the default browser once the service answers; on a
machine without a desktop it prints the address instead (`make run OPEN_BROWSER=0`
turns the browser off).

The container needs one outbound connection: the Apertus endpoint in `LLM_BASE_URL`.
`.env.example` lists the profiles: CSCS, a local vLLM (`docker compose --profile
local-llm up`), a local llama.cpp server for small GPUs, and two development gateways.
Without `make`: `docker compose up --build`.

Model tiers: by default the 8B reads, writes and repairs, and the 70B judges (when the
endpoint serves it; otherwise `LLM_NAME` judges).
`LLM_NAME=swiss-ai/Apertus-v1.5-70B` runs every stage on the 70B;
`LLM_UNDERSTAND_NAME=swiss-ai/Apertus-v1.5-70B` lets the 70B read (the fact sheet) and
the 8B write. `track_2b/eval/report.md` compares the three.

In the browser (English, German or French), paste a text, upload a PDF or enter a URL
(or click one of the two example letters), choose language and level (A2 Leichte
Sprache or B1 Einfache Sprache; the level names the rule set, not a measured reader
level), and follow the stages to the review page. **Check my text** runs the rule
checker on any text you paste, without a model and without storing it.

Other targets: `make check-llm` (one call to the endpoint), `make test`, `make lint`,
`make smoke` (one document through the pipeline), `make calibrate` (rule checker on
official easy-language pages, no model needed), `make day1` (endpoint checks),
`make eval` (conditions P0, P1, P2 on the reference pairs; `RESULTS=track_2b/eval/results-cscs`
keeps one endpoint's results together). `python -m leichtfacile eval sample` writes the
hand-labelling sheets for the judge and `eval kappa` scores a filled sheet; `eval diagnose`
says why must-keep facts are missing from the final drafts of a run, without a model call.

## Sovereign deployment

| Target architecture | How |
|---------------------|-----|
| a) On-premise | `docker compose --profile local-llm up` adds a vLLM server with Apertus 1.5 8B on one GPU with 24 GB or more (official image; run on an NVIDIA L4: [track_2b/eval/hardware/](eval/hardware/aws-l4-2026-10-10/)); set `LLM_BASE_URL=http://vllm:8000/v1` |
| b) Air-gapped | As (a), with images and weights pulled in advance. Python packages, the spaCy model and the UI assets are inside the image: no CDN, no telemetry, no installs at runtime |
| c) Sovereign Swiss cloud | Point `LLM_BASE_URL` at a Swiss-operated Apertus endpoint; the hackathon demo runs against CSCS in Lugano |

Documents and review records stay in a SQLite database on a volume the organisation
controls. At runtime the container contacts only the Apertus endpoint, and a web
page's server when a user enters a URL: no telemetry, no CDN, no login provider (report
§2). Which texts need this, and why it leaves Apertus as the only model:
[Why only Apertus](#why-only-apertus).

## Status (9 October 2026)

Done:

- German and French pipeline end to end: ingest (text, HTML, PDF with text layer),
  Understand, Write, rule check, judge, repair, recover, polish, review UI in English,
  German
  and French, export (Markdown, HTML, JSON audit bundle), web API and CLI.
- Rule checker: 45 deterministic rules for German and 41 for French, with golden
  tests; 8 meaning rules for the judge (10 in decision mode). Italian texts get the
  language-independent rules (facts, layout, readability).
- Decision mode v1 for letters that accompany decisions of KESB and courts: the
  operative part and the appeal instructions protected, one named addressee, a notice
  at the start and the end that only the decision itself is authoritative
  ([track_2b/docs/use-case-decisions.md](docs/use-case-decisions.md)).
- Check my text: the rule checker on any pasted text, no model, nothing stored.
- Evaluation harness: 35 reference pairs (30 German, 5 French), conditions P0, P0-ZH
  (the Canton of Zurich's published prompt), P1 and P2, SARI, readability, fact
  coverage, silent losses, cost and latency.
- Evaluation on the CSCS endpoint: 23 held-out pairs, results of 6 October in
  `track_2b/eval/report.md` and the technical report. **[PENDING: the final run after the
  prompt freeze (10 October) replaces them.]**
- 1,244 tests **[PENDING: the count on the submitted commit]**, no network needed; CI
  runs them, the linter and a start of the Docker image on every push. The whole
  pipeline ran on a laptop GPU with a local 4-bit Apertus 1.5 8B (llama.cpp), on one
  NVIDIA L4 with the official 8B in vLLM (`make run` on a clean Linux clone,
  [track_2b/eval/hardware/](eval/hardware/aws-l4-2026-10-10/)), and `make run` and `make smoke`
  against CSCS.

Pending: the final evaluation run and the two example jobs rebuilt after it; image
input for scanned letters (not built; what the scans showed:
[track_2b/docs/image-input.md](docs/image-input.md)); the air-gapped bundle (`make bundle`);
Italian (after the hackathon).

## Documentation

- [track_2b/technical_report.md](technical_report.md): the technical report (PDF: `track_2b/RoestigrabenBridgers_Report.pdf`)
- [track_2b/docs/architecture.md](docs/architecture.md): design and architecture
- [track_2b/docs/ui-design.md](docs/ui-design.md): the web UI's specification: tokens, components, screens, accessibility
- [track_2b/docs/rules.md](docs/rules.md): the rule catalogue the checker implements
- [track_2b/docs/prompts.md](docs/prompts.md): prompt design and change log
- [track_2b/docs/sources.md](docs/sources.md): reference pairs, demo documents, licences
- [track_2b/docs/use-case-canton.md](docs/use-case-canton.md): a walkthrough for a cantonal administration
- [track_2b/docs/use-case-decisions.md](docs/use-case-decisions.md): letters that accompany decisions of child and adult protection authorities and courts (partly planned)
- [track_2b/docs/use-cases.md](docs/use-cases.md): all use cases at a glance; the further ones sketched with the checks they need
- [track_2b/docs/image-input.md](docs/image-input.md): what Apertus 1.5 reads from a scanned letter, by kind of value
- [track_2b/docs/hard-texts.md](docs/hard-texts.md): hard words and sentences for tests and the presentation
- [track_2b/docs/demo-video.md](docs/demo-video.md): script and storyboard for the demo video

## Licence

Code: Apache License 2.0, see [LICENSE](../LICENSE). Texts from cantonal and federal web
pages are not part of the repository; the evaluation fetches them from their URLs
([track_2b/docs/sources.md](docs/sources.md) §4).

---

# Track 2 B: Own Project

Bring your own idea and build a working Apertus prototype that tackles a problem you care about — any domain, any use case. The project must be new, started within the hackathon period.

Submissions must use the Apertus model family.
For Track 2 this means that submitted solutions must be built with Apertus. Other open-weights models can be used to support development, e.g. as automatic judges during evaluation. Their role must be clearly described in the submission report.

💬 In case you have questions, join the conversation on [Discord](https://discord.gg/hack-apertus) or send an email to “hello@hackapertus.ch”

---

## 🔧 Resources & Tools

Check our resources & tools page for detailed information:
https://hackapertus.notion.site/resources-tools

| Models           | URL                                      |
|------------------|------------------------------------------|
| Apertus v1.5 8B  | [huggingface.co/swiss-ai/Apertus-v1.5-8B](https://huggingface.co/swiss-ai/Apertus-v1.5-8B)  |
| Apertus v1.5 70B | [huggingface.co/swiss-ai/Apertus-v1.5-70B](https://huggingface.co/swiss-ai/Apertus-v1.5-70B) |


## Target architecture (mandatory)

Whatever you build in Track 2B must be deployable in one of these three architectures:

- **a) On-premise** — on the organisation's own infrastructure, under its own administration.
- **b) Air-gapped** — with no external network connection at runtime.
- **c) Sovereign Swiss cloud** — on a cloud platform operated in Switzerland, under Swiss jurisdiction, with Swiss data residency.

---

## Data

The `data/` directory must not exceed 100 MB.

---

## 📦 Submission Requirements & Deliverables

❗️ Submissions are not handled on Devpost but via this URL only:
http://hackapertus.ch/online-hack/submissions

The submission must: 
1. follow the template repo and include all prerequisite files and definitions
2. follow the specified input/output formats
3. run in a Docker container, launched with `make run` from the root of the project
4. run end-to-end when judges try to run it

### Git repo (URL)
- Create your repo from this template (**Use this template**) and work in the `track_2b/` challenge directory. Delete the other track challenge directories.
- Keep `track_2b/` as it is: don't rename it or move its files.
- Set the repo to PUBLIC (Settings --> Collaborators --> Manage Visibility)
- Submit the URL of YOUR Git repo.

### Technical Report (pdf)
- Update [technical_report.md](technical_report.md) in this repository with all the details for your submission.
- Upload a pdf of your technical report to this directory, named as `TeamName_Report.pdf`.
- Format: pdf, max. 6 pages
- Submit the pdf of the technical report.

### Demo video (URL)
- Max. 2 min demo video of your prototype

### Dataset (URL) - optional, depending on your project
Submitted datasets must comply with our guidelines for responsibly sourced datasets.

- Create a user account on Hugging Face
- Clone our dataset template on Hugging Face: https://huggingface.co/datasets/HackApertus/online_hack_template
- Complete the dataset card with all required information
- Upload your dataset. It should consist of the following components:
    - evaluation dataset (i.e. individual test cases)
    - model response dataset (i.e. the model response to each test case)
    - metadata file (i.e. additional information about each test case; where relevant, this file must contain instance-level licensing information) 
- Make sure your dataset access control is set to PUBLIC
- Provide the URL of _your_ data set


---

## ⚖️ Judging Criteria

1. Purposeful use of AI
2. Technical rigour
3. Value, cost & scalability
4. Sovereign deployability
5. Implementation feasibility

Judges use a Scale 0–5 per dimension.

---

## Support

**Licensing requirements**
Please check our Terms & Conditions (6. What you build is open source):
https://hackapertus.ch/terms-and-conditions

## FAQ
💡 https://hackapertus.ch/faq

## Contact
💬 In case you have questions, join the conversation on Discord or send an email to “hello@hackapertus.ch”
