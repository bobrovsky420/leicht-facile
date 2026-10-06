# Leicht·Facile

Leicht·Facile drafts easy-language versions of Swiss official texts (Leichte Sprache,
Einfache Sprache; French and Italian follow) with Apertus, and proves with code that
no deadline, amount or phone number got lost. It is a drafting assistant for the
professionals who write easy language, not a replacement for them or for the review
by readers from the target group.

About 844'000 adults in Switzerland have low reading skills (PIAAC 2023). None of them
should be excluded from the official letters that decide their money, deadlines and
rights.

**Hack Apertus 2026, Track 2B (own project).** Team Röstigraben Bridgers.
Technical report: [technical_report.md](technical_report.md) (PDF:
`RoestigrabenBridgers_Report.pdf`). Demo video: *link follows*.

> Apertus does everything that needs language understanding. Plain code does
> everything that can be counted.

1. **Understand** (Apertus): the document becomes a fact sheet: the reader's core
   questions, every fact with its exact value, hard words, passages that can go.
   Code adds every date, amount and contact the model missed.
2. **Write** (Apertus): a draft in easy language, every sentence linked to the source
   sentences it comes from, every omission explained.
3. **Check** (code): 41 deterministic rules from the published Swiss guidelines
   (sentence length, passive, genitive, numbers, Swiss spelling, Mediopunkt, ...) and
   an exact check of every fact value, in milliseconds, without a model.
4. **Judge** (a second, larger Apertus model): meaning only: distorted facts, invented
   statements, metaphors, unclear references.
5. **Repair** (Apertus): only the flagged sentences, until no blocking finding is left
   (at most 3 rounds).
6. **Review** (human): source and draft side by side, provenance, fact checklist,
   approve, edit or reject each block, export with an audit trail.

### Why not one chatbot prompt?

"Rewrite this in Leichte Sprache" gives a text with no fact contract, no provenance,
no omission log and no independent check, and the chatbots people reach for run on
foreign clouds. Leicht·Facile adds exactly those four things, a review workflow and
an audit trail, and runs on infrastructure the organisation controls. The evaluation
measures the difference: the single prompt is the baseline condition C0, the full
pipeline is C2 ([docs/use-case-canton.md](docs/use-case-canton.md) §4).

## Quick start

Requirements: Docker with Compose, `make`, and an API key for an Apertus endpoint
(the hackathon's CSCS key by default).

```bash
cp .env.example .env      # set LLM_BASE_URL, LLM_API_KEY, LLM_NAME (CSCS by default)
make run                  # builds and starts the container
# open http://localhost:8000
```

The container needs one outbound connection: the Apertus endpoint in `LLM_BASE_URL`.
`.env.example` lists the profiles: CSCS, a local vLLM (`docker compose --profile
local-llm up`), a local llama.cpp server for small GPUs, and two development gateways.
Without `make`: `docker compose up --build`.

In the browser, paste a text, upload a PDF or enter a URL (or click one of the two
example letters), choose language and level (A2 Leichte Sprache or B1 Einfache
Sprache), and follow the stages to the review page.

Other targets: `make check-llm` (one call to the endpoint), `make test`, `make lint`,
`make smoke` (one document through the pipeline), `make calibrate` (rule checker on
official easy-language pages, no model needed), `make day1` (endpoint checks),
`make eval` (conditions C0, C1, C2 on the reference pairs).

## Sovereign deployment

| Target architecture | How |
|---------------------|-----|
| a) On-premise | `docker compose --profile local-llm up` adds a vLLM server with Apertus 1.5 8B on one GPU (official image); set `LLM_BASE_URL=http://vllm:8000/v1` |
| b) Air-gapped | As (a), with images and weights pulled in advance. Python packages, the spaCy model and the UI assets are inside the image: no CDN, no telemetry, no installs at runtime |
| c) Sovereign Swiss cloud | Point `LLM_BASE_URL` at a Swiss-operated Apertus endpoint; the hackathon demo runs against CSCS in Lugano |

Documents and review records stay in a SQLite database on a volume the organisation
controls.

## Status (6 October 2026)

Done:

- German pipeline end to end: ingest (text, HTML, PDF with text layer), Understand,
  Write, rule check, judge, repair, review UI, export (Markdown, HTML, JSON audit
  bundle), web API and CLI.
- German rule checker: 41 deterministic rules with golden tests; 7 meaning rules for
  the judge. French and Italian texts get the language-independent rules (facts,
  layout, readability).
- Evaluation harness: 35 reference pairs (30 German, 5 French), conditions C0, C1 and
  C2, SARI, readability, fact coverage, cost and latency.
- 404 tests, no network needed. The whole pipeline ran on a laptop GPU with a local
  4-bit Apertus 1.5 8B (llama.cpp).

Pending: the runs against the CSCS endpoint (endpoint checks, evaluation numbers,
example jobs), the French and Italian rule sets and prompts, image input for scanned
letters, and the air-gapped bundle (`make bundle`).

## Documentation

- [technical_report.md](technical_report.md): the technical report (PDF: `RoestigrabenBridgers_Report.pdf`)
- [docs/architecture.md](docs/architecture.md): design and architecture
- [docs/rules.md](docs/rules.md): the rule catalogue the checker implements
- [docs/prompts.md](docs/prompts.md): prompt design and change log
- [docs/sources.md](docs/sources.md): reference pairs, demo documents, licences
- [docs/use-case-canton.md](docs/use-case-canton.md): a walkthrough for a cantonal administration
- [docs/hard-texts.md](docs/hard-texts.md): hard words and sentences for tests and the presentation
- [docs/demo-video.md](docs/demo-video.md): script and storyboard for the demo video

## Licence

Code: Apache License 2.0, see [LICENSE](LICENSE). Texts from cantonal and federal web
pages are not part of the repository; the evaluation fetches them from their URLs
([docs/sources.md](docs/sources.md) §4).

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
