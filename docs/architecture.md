# Leicht·Facile - design and architecture

Status: design 5 October 2026; implemented 5-6 October 2026 except what needs the CSCS endpoint (§12). Hack Apertus online hackathon, Track 2B.
Companion documents: [rules.md](rules.md) (the rule catalogue the code checker implements), [use-case-canton.md](use-case-canton.md) (a walkthrough from the point of view of a cantonal administration), [use-case-decisions.md](use-case-decisions.md) (letters that accompany decisions of child and adult protection authorities and courts, partly planned), [use-cases.md](use-cases.md) (all use cases at a glance, the further ones sketched), [sources.md](sources.md) (reference pairs, demo documents and their licences) and [hard-texts.md](hard-texts.md) (hard words and sentences for tests and the presentation).
Items marked **[verify]** are assumptions to confirm against the live endpoint on day 1 (see §12).

## 1. What it is

Leicht·Facile drafts easy-language versions of Swiss official texts - letters, forms,
web pages, decisions - in German (Leichte Sprache / Einfache Sprache), French (FALC)
and Italian (lingua facile), using Apertus 1.5. It is a **drafting assistant for the
professionals who write easy language today**, not a replacement for them or for the
review by readers from the target group.

The design rests on one rule:

> Apertus does everything that needs language understanding. Plain code does
> everything that can be counted.

That split is the answer to the "purposeful use of AI" criterion, and it stops the
model from grading its own homework on things a script can check exactly.

Leicht·Facile is not a translator, and the job cannot be done with one chatbot
prompt. "Rewrite this in Leichte Sprache" yields text with no fact contract, no
provenance, no omission log and no independent check; that is the P0 baseline in §9.
The pipeline exists to add exactly those four things, plus a review workflow and an
audit trail. [use-case-canton.md §4](use-case-canton.md) lays out the comparison
from the administration's point of view.

### Goals

1. Produce a draft that keeps every fact that matters (deadlines, amounts, obligations,
   contacts) and says nothing the source does not say.
2. Follow the published rules for easy language (sentence length, no passive, digits,
   Swiss spelling, …) and prove it with numbers, not demos.
3. Give the human reviewer provenance for every sentence and a checklist of facts, so
   review is faster than writing from scratch.
4. Run entirely on infrastructure the organisation controls: one container plus an
   OpenAI-compatible Apertus endpoint, no other network dependency.

### Non-goals (for the hackathon)

- Certifying texts as "Leichte Sprache". Only a target-group review can do that.
- Translation between languages. Each language version is simplified from the
  original in that language.
- Speech output. Apertus reads images and audio but only writes text; a TTS engine
  would be a separate component.

## 2. Users and workflow

Primary user: a communications officer or an easy-language writer in a canton,
municipality, or an organisation such as Pro Infirmis' Büro für Leichte Sprache.

1. Upload a document (PDF, HTML URL, pasted text, or a photo of a letter) and choose
   language and level (A2 = Leichte Sprache, B1 = Einfache Sprache).
2. Wait 1-3 minutes while the pipeline runs. Progress is visible per stage.
3. Review: source and draft side by side, every draft sentence linked to the source
   sentences it came from, a fact checklist with pass/fail per fact, the list of
   rule findings, and the model's change notes ("left out: appeal procedure, because …").
4. Approve or edit each block, then export (Markdown, HTML, JSON with provenance).
5. Optionally, send the approved text to a target-group test. That step is outside
   the tool but the export is formatted for it (one sentence per line, ≤ 85 characters).

Second user, partly planned ([use-case-decisions.md](use-case-decisions.md)): the case
worker of a child and adult protection authority (KESB), or a court clerk, who drafted
a decision and reviews an easy-language letter that goes out together with it. The
workflow is the same. The review is mandatory, and the decision stays the only legally
binding text. The appeal period, the case number, the AHV number and the court's
postal address are exact facts since 7 October 2026 (§4.4). Not built yet: a field for
the person the letter speaks to; a document type "decision" whose operative part and
appeal instructions are must-keep facts; a fixed notice in the export that the
decision prevails; judge checks for neutrality and advice.

Further users, sketched in [use-cases.md](use-cases.md): physicians (patient letters),
public prosecutors' and debt collection offices, social services, schools, study teams,
and helpers such as tenants' associations and debt counselling services, who explain
letters someone else wrote (the received-letter mode planned in PLAN.md, WP12b). The
fact checks they need are in
[rules.md](rules.md#fact-checks-for-the-further-use-cases).

## 3. Architecture overview

```mermaid
flowchart TB
    subgraph client["Browser"]
        UI["Review UI<br/>(server-rendered HTML + small JS)"]
    end

    subgraph app["leicht-facile container (FastAPI, Python 3.14)"]
        API["HTTP API"]
        Q["Job runner<br/>(single worker thread)"]
        ING["Ingest<br/>PDF · HTML · text · image"]
        UND["Understand → FactSheet"]
        WRI["Plan & write → Draft"]
        RUL["Rule checker<br/>(spaCy + regex, deterministic)"]
        JUD["Meaning judge → JudgeReport"]
        REP["Repair loop<br/>(flagged blocks only, ≤ 3 rounds)"]
        EXP["Export<br/>MD · HTML · JSON"]
        DB[("SQLite + JSON artifacts<br/>(mounted volume)")]
        LLM["LLM client<br/>(OpenAI-compatible, retries, cache, usage log)"]
    end

    subgraph model["Apertus endpoint (any one of)"]
        CSCS["CSCS inference API<br/>(hackathon)"]
        VLLM["Local vLLM<br/>(on-prem / air-gapped)"]
        SC["Swiss sovereign cloud<br/>(Swisscom, Infomaniak)"]
    end

    UI <--> API
    API --> Q
    Q --> ING --> UND --> WRI --> RUL --> REP
    WRI --> JUD --> REP
    REP -->|no errors or 3 rounds| EXP
    UND & WRI & JUD & REP --> LLM
    LLM --> CSCS
    LLM -.-> VLLM
    LLM -.-> SC
    Q <--> DB
    API <--> DB

    classDef ai fill:#e9e1f7,stroke:#6b4fbb,color:#1b1030
    classDef code fill:#dff3f0,stroke:#1f8a7a,color:#0d2b27
    class UND,WRI,JUD,REP ai
    class ING,RUL,EXP code
```

Purple stages call Apertus. Teal stages are deterministic code. Everything runs in one
container; the only outbound connection is `LLM_BASE_URL`.

### Key decisions

| # | Decision | Why |
|---|----------|-----|
| D1 | One Python service (FastAPI) serves both the API and a server-rendered review UI. No Node build step. | One container, one `make run`, nothing to break on the judges' machine. The UI is a review tool, not a product front-end. |
| D2 | All model access goes through one OpenAI-compatible client configured by `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_NAME`. | The hackathon endpoint, local vLLM and Swiss cloud providers all speak the same protocol. "Sovereign deployment" becomes a change of one variable. |
| D3 | The pipeline is a sequence of explicit stages with typed, persisted artifacts (pydantic models stored as JSON). | Every intermediate result is visible in the UI, re-runnable in isolation, and usable for evaluation and ablations. |
| D4 | Countable rules live in code (spaCy morphology + regex). Apertus only judges what needs meaning. | Exact, free, reproducible; removes self-grading bias on the easy half of the rules. |
| D5 | Writer and judge are separate model instances; by default 8B writes, 70B (thinking) judges. `LLM_UNDERSTAND_NAME` can give the Understand stage a third model (the hybrid: the 70B reads, the 8B writes). | A different, stronger model judging reduces bias and gives an 8B-vs-70B cost story. All three are a config switch; §9 compares the tiers. |
| D6 | Each language is simplified from its own original. | Simplifying a translation compounds errors; three fact sheets also allow a cross-language consistency check. |
| D7 | Storage is SQLite plus JSON files on a mounted volume. | Zero operations, works air-gapped, trivially backed up. |
| D8 | The evaluation harness is a first-class module with a fixed dataset manifest and three conditions (baseline, pipeline without repair, full pipeline). | "Technical rigour" is judged on the comparison, not the demo. |

## 4. The pipeline

Each stage takes typed artifacts and produces typed artifacts (schemas in §5). The job
runner executes stages in order and persists each result before starting the next, so
a failure resumes from the last good stage.

### 4.1 Ingest (code)

| Input | Method | Output |
|-------|--------|--------|
| HTML URL | `httpx` fetch; content hidden in tabs and accordions is revealed and `tel:`/`mailto:` links unwrapped; then `trafilatura` main-content extraction (XML output) keeping headings, lists and tables; a rescue pass puts back contact blocks whose phone number or e-mail address the extraction dropped, at their place in the page | `SourceDocument` |
| PDF with text layer | `pdfplumber`, page by page; words are assigned to columns when a page has a gutter (a glossary side column is read after the main text); headings by font size and bold; repeated headers, footers and page numbers removed; hyphenated line ends joined; a paragraph running over a page break is merged | `SourceDocument` |
| PDF without text layer, photo | Not supported yet: a clear error. Planned: rendered to PNG and passed to Apertus as image input in the Understand step (Apertus 1.5 is multimodal). Day-1 check 4 passed on the Public AI gateway on 6 October 2026: the 8B read a rendered letter and answered with its deadline, so image input works through an OpenAI-compatible Apertus endpoint (vLLM at Juelich); the same on CSCS the same day. The go/no-go spike of PLAN.md WP12 is `scripts/image_spike.py` (`eval/image_spike.py`): every page of the scanned letters in `data/examples/print/scans/` goes to the model at a long side of 1600 px with a "transcribe word for word" prompt, and the transcription is measured against the printed text by character error rate and hard values found. On CSCS (7 October 2026) the 8B at 1,600 px declined the German page and read the French letter with wrong digits; at full resolution the 8B and the 70B read both letters but turned the IBANs, the AVS number and a 78-day period into other plausible numbers (docs/prompts.md, "Image input spike"). A no-go for a mode that feeds the fact contract (decision D-N): image input stays future work. | - |
| Pasted text, `.txt`, `.md` | Paragraphs at blank lines, Markdown headings, bullet and numbered lists, short stand-alone lines as headings | `SourceDocument` |

All text is normalised first: Unicode NFC, soft hyphens and zero-width characters
removed, the dot-like characters PDFs deliver in compounds (`Merk•blatt`) turned into
the Mediopunkt, typographic apostrophes in numbers (`1’500`) into `'`.

Segmentation: paragraphs → sentences with spaCy's rule-based sentencizer for the
document language, plus a merge step for German abbreviations and ordinal dates
(`31. März`, `Art. 5 Abs. 2`, `z. B.`). Each segment gets a stable id (`s0001`, …), a
kind (`heading`, `paragraph`, `list_item`, `table_cell`), its heading path, the index
of its paragraph (`para`) and, for headings, the level. The language is detected from
stopword frequencies for German, French and Italian, which needs no extra model for
three languages; the user can override it.

Chunking is not needed for understanding - Apertus 1.5 has a 262,144-token context -
but documents over 3,000 words are **written** section by section (sharing one fact
sheet), to keep output quality.

### 4.2 Understand (Apertus)

One call over the whole document. Output: the `FactSheet` - the most important
artifact, because every later step is checked against it.

- Document type and audience.
- The reader's core questions: What is this? What must I do? By when? What does it
  cost? Whom do I contact? Each answer cites segment ids; `null` if the source does
  not answer it (the writer must then not invent one).
- `facts[]`: every fact that must survive, typed (`deadline`, `amount`, `obligation`,
  `right`, `condition`, `contact`, `procedure`, `definition`, `other`), with a
  normalised value where applicable (ISO date, decimal CHF, digits-only phone; a
  period in words, an identifier or a postal address as written), the segment ids it
  comes from, and `must_keep` true/false.
- `hard_terms[]`: difficult words with a plain explanation, for the glossary.
- `omit_candidates[]`: passages the model considers droppable, with reasons - the
  reviewer sees these.

Model: `LLM_NAME` (8B), thinking on, temperature 0.1. `LLM_UNDERSTAND_NAME` gives this
stage another model while the writer stays the 8B: on CSCS the 70B found more facts
with a third of the 8B's reasoning, but the 8B writer then kept fewer of them
(docs/prompts.md). Output is JSON; see §6 for how JSON is enforced.

**Code completes the fact sheet.** After the call, code adds a fact for every date,
amount, phone number, e-mail address, web address, percentage, time, period (`innert
30 Tagen`), identifier (case number, AHV number, IBAN), postal address, quantity
(`2,5 mg`) and dosing scheme (`1-0-1`) in the source that no fact carries (`origin:
code`; the value kinds are listed in [rules.md](rules.md#facts-the-most-important-family)). The values are taken from the document text
with the segments' character offsets, as the evaluation's "hard facts kept" takes
them, so an address over two sentences is one fact citing both (since 7 October 2026;
sentence by sentence before, which completed such an address without its street). A
percentage is stored as `10%`, the form the prompt asks for; as a bare number it
parsed as a plain number and never matched again. Values in passages the model marked as
droppable become background facts; all others must be kept. The first local test run
showed why: the model listed 3 facts for a letter with 11 checkable values.

**The vocabulary completes the hard terms.** The project's vocabulary of hard words
(`rules/data/vocabulary_<lang>.toml`, `rules/vocabulary.py`; [rules.md](rules.md),
"Vocabulary") explains about 200 terms per language in checked easy language. A hard
term the model listed gets the vocabulary's explanation when the vocabulary has the
term (`origin: vocabulary`): the 8B's own were often hard or wrong (Franchise and
Selbstbehalt explained alike, the Urne as the place of the vote; CSCS dev run of
7 October 2026). Terms of the source the model did not list are added, the rarest
first, up to 6 and 12 hard terms in all. Context-dependent words (Leistung, Wartezeit)
are never added by code. Since 7 October 2026; `USE_VOCABULARY=0` switches this and the
other uses below off, only to measure them.

### 4.3 Plan and write (Apertus)

Easy language is not a sentence-by-sentence translation, so the prompt asks for a
plan first: order content by what matters to the reader, use questions as headings,
one idea per sentence, then write. Inputs:

1. The style guide for language and level (generated from [rules.md](rules.md), so
   prompt and checker never disagree).
2. Two short example pairs (standard → easy) written by the team, to anchor Swiss
   conventions: `ss` not `ß`, the Mediopunkt (`Kranken·kasse`), `1'200 Franken`, dates
   and times. Cantonal pages may not be reproduced in a public repository
   ([sources.md](sources.md) §4), so they are not used as examples.
3. The source segments with ids.
4. The fact sheet.

The writer gets no list of the source's office words with their everyday word: tried on
7 October 2026, such a list made the 8B write more of them into its first drafts, not
fewer (docs/prompts.md, "Vocabulary in the pipeline"), and was removed. A later Apertus
may take it better, or a list that names only the everyday words. The office words are
handled after writing instead: rule LEX-07 (§4.4) and the vocabulary round (§4.6).

Output: `Draft` - blocks (`heading` | `sentence` | `list_item`), each with the
`fact_ids` it conveys and the `segment_ids` it was derived from (this is the
provenance the UI shows), plus `omissions[]` with reasons and a `glossary[]`.

Model: `LLM_NAME` (8B), temperature 0.3, thinking off by default. In the first local
tests, writing with thinking took 24 minutes and produced a paraphrase of the original,
while writing without thinking took 28 seconds and produced easy language (question
headings, `Sie`, no passive); `LLM_THINKING_STAGES` switches thinking per stage, and
the day-1 checks on the CSCS endpoint decide the final setting.

An answer cut off at `max_tokens` is never used (its last objects are incomplete);
the part of the document it was for is written again as two halves, down to six
sentences. Code assigns the block ids (`b001`, …), drops fact ids that do not exist, and links a
block to every fact whose exact value it contains, so fact bookkeeping does not depend
on the model. A block that cites no source sentence takes the sentences of those facts,
and a fact without a value whose text holds values (a contact with its phone number and
e-mail) is linked to a block that cites one of its sentences and contains all of them. A sentence that repeats an earlier one is dropped and its references go
to the first, and a heading left without content goes too: small models repeat a fact
under every heading it answers (the deadline under "What must you do?" and again under
"By when?").

Code then completes the glossary (`rules/glossary.py`): a hard term of the vocabulary
that a block uses and the glossary does not explain gets the vocabulary's entry, at most
6 per version and up to 10 entries in all, the rarest first. The writer is asked to take
the explanations from the fact sheet but leaves many out: on the dev run of 7 October the
fact sheet of `sg-el-costs-de` listed Franchise, Selbstbehalt and Spitex, and the final
glossary had none of them. The entries are marked (`origin: vocabulary`, a muted note on
the review page) and recorded as code edits under rule SEM-05, the judge's question
for a hard word without explanation.

Then code writes the Mediopunkt (`rules/mediopunkt.py`): every compound noun with a part
longer than the level's limit is split (`Kranken·versicherungs·police`), in the blocks
and in the glossary terms, and a capital after an existing dot is lowered. Nouns only;
adjectives and verbs keep their LEX-01 warning, because their fix is another word. Words
with a digit, web and e-mail addresses and the word in front of a number (a street with
its house number) are never touched, so no value changes; the feminine ending `-innen`
stays on its stem (`Sozial·arbeiterinnen`, never `Schweizer·innen`); and the split is the one
LEX-01 proposes, so the rule is silent on the result. The edits are
recorded on the draft version (`code_edits`), shown on the review page and reported in
the evaluation. The same step runs after every repair round, before the check: the 8B
does not apply the split it is given in a repair, and a warning alone costs a polish
round. P1 and P2 only; the baselines measure the prompt alone ([rules.md](rules.md),
"Edits made by code"). Since 8 October 2026 the same step writes `ss` for `ß`
(`rules/swiss.py`, CH-01, one edit per word, blocks and glossary): the 8B writes `ß`
now and then, and a repair round is a poor use of a model call for one character.

### 4.4 Rule check (code)

Runs on every block, in milliseconds, no model. Produces `RuleFindings`: per-block
findings with a rule id, severity (`error` | `warn` | `info`), evidence and, where
possible, a suggestion; plus document metrics (words per sentence, readability
score, share of passive sentences, …). The full catalogue is in
[rules.md](rules.md). Highlights:

- sentence length and clause count (spaCy dependency parse);
- passive, genitive, Konjunktiv, Präteritum, nominalisations (spaCy morphology);
- numbers as digits, Swiss formats for dates, times, amounts, phone numbers;
- `ß`, `« »`, `%`, `&`, brackets, semicolons, abbreviations not on the allowlist;
- long compounds without Mediopunkt;
- office words with an everyday equivalent from the vocabulary (LEX-07, LEX-07-FR:
  `innert`, `reichen ... ein`, `moyennant`; a warning at A2, a note at B1), with the
  everyday word as the suggestion; abbreviations get their full word the same way (LEX-02);
- **fact coverage**: every `must_keep` fact with a normalised value must appear in the
  draft in some accepted surface form (`4. Februar 2020`, `4.2.2020`, …). This is an
  exact check and the single most important automatic test;
- readability: Amstad (German Flesch) for DE, Kandel-Moles for FR, Gulpease for IT;
- the fact sheet itself: a value the model wrote into the fact sheet must appear in the
  source sentences it cites (FACT-05);
- the draft's values: every date, amount, phone number, e-mail and web address,
  percentage, time, period, identifier and postal address in the draft must occur in
  the source (FACT-06, the mirror of fact coverage). A value the model invented or
  copied from the prompt's examples is an error and goes to repair; for a phone
  number, e-mail, web address, identifier or address the source's only one is
  suggested, if it has exactly one. On the 12 dev pairs of 6 October the rule found
  the examples' phone numbers in 8 final drafts, the examples' amount and date in 3,
  and an e-mail address with a dropped letter; the P0 drafts had none. A value of the
  fact sheet counts as known only if the source contains it: since 7 October 2026 a
  value the Understand model computed or invented (an end of an appeal period, a
  day for "im Frühling") is flagged in the draft and no longer required by FACT-01,
  instead of reaching the reader with a FACT-05 warning on the fact sheet alone.
- the value kinds of 7 October: a period (`innert 30 Tagen`, `zwei Wochen`, `30-tägige
  Frist`; `2 Wochen` equals `14 Tage`, working days equal nothing else), an identifier
  (AHV number, IBAN, postal account, UID, a reference after `Referenz`, `Dossier`,
  `Geschäftsnummer`, `Verfügung Nr.` and the like, compared without spaces) and a
  postal address (street and number, Postfach, postcode and place; an address that
  lost its street is a loss, a street the source lacks an invention), a quantity
  (`2,5 mg`, `2 Tabletten`, `38,5 Grad`; the name equals the symbol) and a dosing
  scheme (`1-0-1`) are hard facts like a date: code completion, FACT-01, FACT-05,
  FACT-06 and "hard facts kept" treat them the same way
  ([rules.md](rules.md#facts-the-most-important-family), "Value kinds"). Every further
  use case turns on one of them
  ([use-cases.md §13](use-cases.md#13-what-the-further-use-cases-need)).
- the checks for the further use cases, all built by 8 October 2026: the fixed notice
  (FACT-07) and the operative part and appeal instructions (FACT-08) of the decision
  mode, the judge's SEM-08 to SEM-10, and for patient letters a medication by its name
  (the value kind `medication`, which the fact sheet gives: code finds no drug name)
  kept in one block with its dose, scheme and duration (FACT-09, `rules/medication.py`)
  ([rules.md](rules.md#fact-checks-for-the-further-use-cases)).

Each rule is registered in code once (`rules/base.py`), with its id, severity per level
and the instruction for the writer prompt; the style guide is rendered from that
registry, and a test keeps the registry and [rules.md](rules.md) in sync. German has
31 rules of its own (`rules/de.py`) and French 28 (`rules/fr.py`, ids ending in `-FR`),
both calibrated on the official easy-language pages; 12 rules for facts, layout and
readability apply to every language. Italian texts get only those until their rule set
ships.

### 4.5 Meaning check (Apertus as judge)

A second model call with the fact sheet and the draft (source available on request
via the segment ids). It answers only what code cannot:

1. For each fact: `present` | `missing` | `distorted`, with the block ids and a note.
2. Which draft blocks state something the source does not support (hallucinations).
3. Semantic rule violations: metaphors and idioms, abstract nouns, pronouns whose
   reference is unclear, implied knowledge the reader may not have, and a changed
   obligation, possibility or condition (SEM-08, since 7 October 2026: `müssen` must
   not become `können`, and a `wenn` never `vielleicht`).

Model: `LLM_JUDGE_NAME` (default `swiss-ai/Apertus-v1.5-70B-thinking`), temperature
0. The judge never rewrites; it only reports. Its reliability is measured, not
assumed (§9).

### 4.6 Repair (Apertus)

Only flagged blocks are sent back, each with its findings (rule and judge, with the
checker's suggestion where there is one) and the facts it must keep. The model returns
one to three sentences per flagged block and new sentences for missing facts, each
placed after a named block. A round first asks only for what blocks the draft (rule
errors, missing fact values, the judge's problems), with at most 5 missing facts at a
time, the most important kinds first; the warnings get one round once nothing blocking
is left. Code drops a repaired or added sentence that repeats one already in the draft,
also when an addition lands before the block it repeats. The judge's meaning findings
on headings are not sent for repair: a small model turns the question heading into a
statement. A repair answer with a value that neither the source nor the fact sheet
contains (the check of FACT-06) is sent back once with the values named; the second
answer is used as it is, and FACT-06 flags what remains. A missing fact is listed with
the fact sheet's value and, when that differs, the exact form the draft should write
(`2026-03-31; schreiben Sie: 31. März 2026`). A finding of LEN-02 carries the rewrite
recipe for its conjunction as the suggestion (docs/rules.md). Every round is recorded
(`RepairRecord`, §5): the blocks and facts asked for, the model's answer as given, and
every answered sentence code left out with its reason (a repeat, example content, a
block the round had not flagged); `eval diagnose` reads these records.
Then:

- code completes the glossary and writes the Mediopunkt into the new version as after
  the write stage (§4.3), so that the check, the judge, the reviewer and the exports see
  the same text;
- rule checks rerun on the new version;
- the judge reruns only if a fact or an invented statement was involved; otherwise its
  findings for the blocks the repair did not touch are carried over;
- the loop stops when no blocking finding remains (rule errors, missing fact values,
  facts the judge found missing or distorted, invented statements), when a round brings
  no progress, when only warnings are left after the first round, or after
  `MAX_REPAIR_ROUNDS` (3).

When the loop has stopped and must-keep values are still missing (FACT-01), up to
`MAX_FACTS_ROUNDS` (1) more rounds ask for the missing facts alone, no block flagged,
up to `MAX_MISSING_PER_FACTS_ROUND` (10) of them at a time; a repair round asks for at
most 5 next to its flagged blocks.
They are measured by the FACT-01 count, not by the whole: the loop above stops on "no
progress" when a round adds facts and the judge finds as many new problems, which on
the dev pairs left values missing in nearly every job (docs/prompts.md). A facts round
goes on while it adds a fact and stops when none is missing, when it adds none, or at
the limit; none runs without repair rounds or after a round the endpoint failed (after
an answer the code could not use, it still runs: a smaller prompt, a new try). Since
7 October 2026 (PLAN.md WP13).

**The vocabulary round** (since 7 October 2026, part of the vocabulary): after the facts
rounds, the office words still in the best version (LEX-07, LEX-07-FR) go to one more
round through the repair prompt: the flagged sentences alone, each with its everyday
word as the suggestion, no fact and no judge's problem. Before it, office words reach a
round only as warnings, in the polish round that many jobs never get to, so the repair
rounds stay on what blocks a draft. The round starts from the best version, so its new
version takes the next free number and names that version as its parent. The choice
below keeps it only when it loses no must-keep value and adds no blocking finding; at a
tie the later version wins, so a round that only replaces office words is kept. Not with
`USE_VOCABULARY=0`, not without repair rounds, not after a round the endpoint failed. On
the 12 dev pairs (docs/prompts.md, "The vocabulary round") it ran in 11 jobs and was
kept in 8: office words in the final drafts from 42 to 19, no fact lost, about 11 s more
per job.

The final version is the one with the fewest must-keep values missing (FACT-01), then
the fewest blocking findings, then the latest. Facts come first because a reviewer can
reject an unsupported sentence or mend a long one with a click, but cannot conjure a
missing deadline; until 8 October 2026 the blocking count alone decided, and the dev
rerun of 7 October showed it discarding versions a facts round had just filled, when
the judge flagged the new sentences (docs/prompts.md, bucket k). `eval rescore`
scores stored jobs under either rule without a model call.

Language-rule findings (families LEN, ORD, GRAM, NEG, LEX, NUM, CH), missing fact values
(FACT-01) and values the source does not contain (FACT-06) are repaired; provenance and
bookkeeping findings (FACT-02 to FACT-05) and layout go to the reviewer. All draft versions are kept; the version with the fewest blocking findings
is marked final, and the reviewer can switch to any other version. Model: `LLM_NAME`,
thinking off, temperature 0.2.

**Decision mode** (`JobConfig.mode = "decision"`, with `addressee` and `notice`;
docs/use-case-decisions.md, since 8 October 2026). The same stages, with the decision
partial pulled into every prompt and three additions by code. `rules/decision.py` finds
the operative part and the appeal instructions of the source, by their headings (`III.
Entscheid`, `Rechtsmittelbelehrung`) or, in a PDF without headings, by the sentence that
names the verb of deciding and ends with a colon (`Demnach erkennt das
Verwaltungsgericht:`) followed by the numbered items, and the paragraph that begins
`Gegen diesen Entscheid kann`; the distribution list (`Zustellung an:`) is not part of
it. After the code completion, `protect_factsheet` makes every fact cited from those
parts must-keep whatever the model marked, turns a value code found in the header or
the reasoning into a background fact unless a core answer cites it (the repair rounds
would otherwise chase the dates of the reasoning), strikes the parts from the omit
candidates, and adds one fact without a value per part. FACT-08 (error, decision mode
only) fires when a part is cited by no block or listed as omitted; it carries the part's
fact id, counts as blocking and as missing like FACT-01, and a repair round asks for
the part before any value. The judge is asked SEM-09 (no advice, no evaluation) and
SEM-10 (every period with its start) through the partial; its answers to them pass
the filter for a decision job only. The notice (`JobConfig.notice`) is written by the
Markdown and HTML exporters and by the bundle's layout lines as the first and the last
paragraph, word for word and exempt from the layout rules; the review page shows it as
a banner above the blocks, not as a block, so it has no decision and no provenance;
FACT-07 on the export's lines catches an export without it and a review edit that
removed or changed it.

### 4.7 Review (human) and export (code)

The reviewer sees the final draft with provenance, findings and the fact checklist,
and records a decision per block: `approved`, `edited` (with the new text), or
`rejected`. Export formats:

- Markdown and HTML with one sentence per line, lines ≤ 85 characters, headings and
  lists preserved;
- JSON bundle: source, fact sheet, final draft, findings, decisions - the audit trail;
- DOCX (`python-docx`) if time allows, since writers work in Word.

### 4.8 Learning from edits (stretch)

Approved drafts form an SFT set; reviewer edits form preference pairs (model text vs.
edited text). With the official Apertus fine-tuning recipes, a LoRA on the 8B model
could be trained from them - in effect distilling the 70B judge's standard into the
8B writer. Only attempted if compute is available (Phoeniqs applications closed on
4 October; Hugging Face credits or a Kaggle notebook remain).

### Where Apertus is used - summary

| Stage | Role of Apertus | Model (default) | Thinking | Temp. | Output |
|-------|-----------------|-----------------|----------|-------|--------|
| Ingest (scans only) | Read a photographed or scanned letter (image input) | 8B | off | 0.0 | segments |
| Understand | Extract facts, core answers, hard terms | 8B (`LLM_UNDERSTAND_NAME` overrides) | on | 0.1 | `FactSheet` JSON |
| Plan & write | Reorder, simplify, explain, record omissions | 8B | off (configurable) | 0.3 | `Draft` JSON |
| Meaning check | Judge fact fidelity, hallucinations, semantic rules | 70B-thinking | on | 0.0 | `JudgeReport` JSON |
| Repair | Rewrite flagged blocks | 8B | off | 0.2 | blocks |
| Cross-language check (stretch) | Compare DE/FR/IT fact sheets | 70B | on | 0.0 | diff report |
| Learning (stretch) | LoRA fine-tune of 8B on approved drafts | 8B | - | - | adapter |

The rule checker, ingestion, fact coverage, readability and export use no model.

## 5. Data model

All artifacts are pydantic models (`src/leichtfacile/schemas.py`) serialised as JSON.
The model answers in its own, leniently parsed shapes (`pipeline/models.py`), which
code turns into these artifacts.

```text
SourceDocument
  id, lang (de|fr|it), title, source {type, uri, fetched_at, license_note}
  segments[]: {id, kind, text, heading_path[], heading_level?, para, page?}

FactSheet
  doc_id, doc_type, audience
  core: {what, must_do, deadline, cost, contact}  each {text|null, segment_ids[]}
  facts[]: {id, kind, text, value_norm?, segment_ids[], must_keep, origin (model|code)}
  hard_terms[]: {term, explanation, segment_ids[], origin (model|vocabulary)}
  omit_candidates[]: {segment_ids[], reason}

Draft  (one per version)
  doc_id, lang, level (A2|B1), version, parent_version?, origin (write|repair|baseline|review)
  blocks[]: {id, kind (heading|sentence|list_item), text, fact_ids[], segment_ids[]}
  omissions[]: {what, why, segment_ids[]}
  glossary[]: {term, explanation, origin (model|vocabulary)}
  code_edits[]: {block_id, rule_id, before, after}   made by code on this version:
                Mediopunkt splits (LEX-01), glossary entries (SEM-05)

RuleFindings  (one per draft version)
  draft_version, level
  findings[]: {block_id?, rule_id, severity, message, message_key?, message_params, evidence, suggestion?, fact_id?, segment_ids[]}
  metrics: {blocks, sentences, words, avg_words, max_words, pct_passive, pct_genitive,
            pct_subordinate, readability, readability_formula, facts_total, facts_found,
            fact_coverage}

JudgeReport  (one per judged draft version)
  draft_version, model
  fact_checks[]: {fact_id, status (present|missing|distorted), block_ids[], note}
  unsupported[]: {block_id, note}
  semantic_findings[]: {block_id, rule_id (SEM-01..05, SEM-08), note}

RepairRecord  (one per repair round, under the version it produced)
  draft_version, parent_version, kind (repair|facts|vocabulary)
  requested_blocks[], requested_facts[]
  repairs[]: {block_id, texts[]}            the answer as given
  additions[]: {after?, texts[], fact_ids[]}
  dropped[]: {text, reason (repeat|example|not_flagged), block_id?, fact_ids[]}

ReviewState
  draft_version, completed
  decisions[]: {block_id, decision (approved|edited|rejected), text?, comment?, at}

PipelineSummary
  condition, mode, final_version, rounds, facts_rounds, stop_reason, writer_model,
  understand_model? (only when another model read the source), judge_model?,
  prompt_versions {stage: hash}, blocking_findings[] (per draft version),
  vocabulary? (hash of the vocabulary file the job used), vocabulary_rounds (0|1)

Job
  id, status (queued|running|needs_review|done|failed), stage, title, created_at, updated_at
  config: {lang, level, condition (P0|P1|P2), writer_model, understand_model,
           judge_model, use_judge, max_repair_rounds, max_facts_rounds,
           mode (standard|decision), addressee?, notice?}
  usage[]: {stage, model, tokens_in, tokens_out, latency_ms, cached}
  error?
```

Storage: one SQLite database (`DATA_DIR/leichtfacile.sqlite`) with the tables `jobs`,
`artifacts` (job, name, version, JSON) and `llm_calls`; the response cache is a second
file (`llm_cache.sqlite`). Standard library only, no ORM.

## 6. The LLM client

`leichtfacile/llm/client.py` wraps the `openai` Python SDK:

- **Configuration** from the template's variables: `LLM_BASE_URL`, `LLM_API_KEY`,
  `LLM_NAME`; plus `LLM_JUDGE_NAME` (default: the 70B of the writer's family when the
  endpoint lists it, looked up once per process, else `LLM_NAME`), `LLM_UNDERSTAND_NAME`
  (default `LLM_NAME`) and `LLM_THINKING_MODE` = `model-suffix` (CSCS exposes thinking as separate
  `…-thinking` model names; the suffix is `LLM_THINKING_SUFFIX`) | `chat-template`
  (local vLLM: `extra_body={"chat_template_kwargs": {"enable_thinking": true}}`) |
  `off`. Optional: `LLM_TIMEOUT_S`, `LLM_MAX_RETRIES`, `LLM_CACHE`, and
  `LLM_EXTRA_BODY` (JSON fields sent with every request, for gateway switches).
- **Endpoint profiles** (documented in `.env.example`):
  1. CSCS inference API, the hackathon default;
  2. local vLLM from the `local-llm` compose profile, for on-premise and air-gapped
     deployments;
  3. the Public AI gateway (`https://api.publicai.co/v1`), for development and
     evaluation with public documents. It lists `swiss-ai/apertus-v1.5-8b` and
     `-70b`, each with a `-thinking` variant, at USD 0.10/0.20 per million
     input/output tokens for the 8B and 0.82/2.92 for the 70B, with USD 2 of starter
     credit. It is run by Metagov Inc., a US nonprofit, under Massachusetts law, and
     routes requests to compute partners. It requires a `User-Agent` header, which
     the client always sends. Not a sovereign deployment: never used for documents
     with personal data. The routing checked on 6 October 2026 (from the gateway's
     response headers) decides the profile's settings: the 8B goes to Juelich's
     Blablador (vLLM) and thinks through the chat template, but only in about two
     of three identical calls, so comparisons of thinking against no thinking are
     left to the CSCS endpoint; the 70B goes to
     Infomaniak (`Apertus-v1.5-70B`) and ignores the thinking switch; the
     `-thinking` names are not used, because `apertus-v1.5-8b-thinking` serves the
     older Apertus 1 8B through Featherless. The gateway's response cache ignores
     the thinking switch, so the profile turns it off per request
     (`LLM_EXTRA_BODY={"cache": {"no-cache": true}}`). Results from this profile are
     labelled Public AI, never CSCS;
  4. the Hugging Face inference router, for development only. It serves only the
     older Apertus 1 models (`swiss-ai/Apertus-8B-Instruct-2509` through Public AI,
     `…-70B-Instruct-2509` through Featherless). No Hugging Face provider serves
     Apertus 1.5, so its results are never reported as Apertus 1.5 numbers.

  All facts on third-party endpoints were checked on 5 October 2026.
- **Thinking per stage.** `LLM_THINKING_STAGES` (default `understand,judge`) names
  the stages that use the thinking model. When the reasoning of a thinking call runs
  out of tokens before the answer, the stage is answered once more without thinking;
  both calls are counted in the usage log.
- **Graceful degradation.** A failing judge or repair round does not fail the job:
  the reviewer gets the best draft so far with its rule and fact checks, and the job
  summary names the step that failed.
- **Reasoning removal.** A thinking model's reasoning is taken from the separate
  `reasoning_content` field when the server provides one (vLLM with
  `--reasoning-parser apertus`), and otherwise cut from the text, whether wrapped in
  `<|inner_prefix|> … <|inner_suffix|>` or `<think> … </think>`. Output cut off by
  `max_tokens` while still reasoning is flagged as truncated.
- **Structured output.** Neither the CSCS docs nor the vLLM guide document
  `response_format`, so JSON is enforced the robust way: the schema is in the
  prompt, the response is stripped of any leaked reasoning tokens
  (`<|inner_prefix|> … <|inner_suffix|>`) and code fences, parsed (the slips of a
  small model are repaired in code: a run of ids written as a range, a trailing or a
  missing comma, a list or object closed with the wrong bracket, a unicode escape
  with too few digits, a second value without a list where a key belongs, which is
  dropped because code completion restores any value it carried) and validated with pydantic. On failure the validation error, or the
  syntax error with its position, is fed back once for a repair. An answer that copies
  the prompt's own example or its style guide (4 of 12 dev drafts on the Public AI 8B
  were the JSON form itself, 6 October 2026; a decision-mode draft carried the style
  guide as a section, 7 October) is recognised by code and sent back once in the same
  way.
  The Public AI gateway (vLLM) accepts `response_format={"type":"json_object"}`,
  but it made no difference in the day-1 check (§12), so it is not used.
- **Streaming.** Every response is streamed (`LLM_STREAM`, on by default): the
  endpoint sends the answer as it is generated and the client assembles it, with the
  token counts from the last chunk (`stream_options.include_usage`). Without it, a
  proxy in front of the endpoint can cut a long answer: Cloudflare in front of the
  Public AI gateway does so after about 100 seconds, which lost 3 of 6 evaluation
  pairs to 504 errors on 6 October 2026. A stream that breaks is retried like any
  other failure. `LLM_STREAM=0` is for a server that cannot stream.
- **Reliability.** Retries on 429, 5xx, connection errors and broken streams with
  exponential backoff and jitter, honouring `Retry-After`; other 4xx errors are not
  retried. Per-call timeout, and `max_tokens` sized generously for thinking models
  (reasoning can be several times longer than the visible answer).
- **Usage log.** Every call records model, tokens in/out, latency and stage; jobs
  show totals, and the evaluation reports cost per page using a configurable
  CHF-per-million-tokens table. A job's calls are stored as they are made
  (`LLMClient.recording` around the job's run), so a stage that fails after some
  calls, and the job it fails, still show them.
- **Cache.** Responses are cached by hash of (model, messages, parameters) in SQLite
  when `LLM_CACHE=1`. It speeds up development and makes evaluation reruns cheap. The
  repository ships with an empty cache: the live run must work from the endpoint.
  An answer that cannot be used (no valid JSON, a copy of the example) is dropped
  from the cache again, so a rerun of a failed pair asks the model.
- **Control tokens.** Servers that print special tokens (llama.cpp with `-sp`, which
  is needed to see the reasoning markers) also print `<|assistant_end|>`; every
  `<|...|>` token is removed from answers.
- **Tool calling is not used.** The thinking variants are served with tool use
  disabled, and the pipeline has no need for it.
- **A local endpoint for development without a key.** llama.cpp's `llama-server`
  speaks the same protocol. With the community conversion
  `Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF` (text only, 4-bit, unofficial) and
  `LLM_THINKING_MODE=chat-template` it serves Apertus v1.5 8B on an 8 GB laptop GPU;
  see §10. Results from it are never reported as CSCS numbers.

Privacy: document text is never written to logs above `DEBUG`.

## 7. Web application

### API

| Method & path | Purpose |
|---------------|---------|
| `POST /api/jobs` | Create a job from a file upload, a URL or pasted text (multipart form); options `lang`, `level`, `condition`, `writer_model`, `understand_model`, `judge_model`, `title`, and for the decision mode (docs/use-case-decisions.md) `mode`, `addressee`, `notice` |
| `GET /api/jobs` | The latest jobs |
| `GET /api/jobs/{id}` | Status, current stage, usage totals and per call, artifact versions, links |
| `GET /api/jobs/{id}/artifacts/{name}?version=` | `source`, `factsheet`, `draft`, `rules`, `judge`, `repair`, `review`, `summary` |
| `POST /api/jobs/{id}/review` | Block decisions for one draft version, and whether the review is complete |
| `GET` or `POST /api/jobs/{id}/export?format=md\|html\|json` | Download: Markdown, HTML, or the JSON audit bundle |
| `POST /api/jobs/{id}/rerun?from=understand\|write\|judge` | Delete the artifacts from that stage on and run again |
| `DELETE /api/jobs/{id}` | Remove a job and its artifacts |
| `GET /healthz` | Liveness; also checks the LLM endpoint's `/v1/models` |

Jobs execute on a single worker thread with a queue; the UI polls status. That is
enough for a reviewer's workload and avoids a message broker. Jobs that were queued or
running when the service stopped are queued again on start.

### Review UI

A workbench for people who review drafts for hours every day, designed in WP18
([ui-design.md](ui-design.md) has the full specification: tokens, components,
screens, texts, accessibility). Server-rendered Jinja2 pages, one `app.css`, one
`app.js`, no framework, no build step, no CDN. Calm on purpose: white and grey
surfaces, one institutional blue for actions, selection and focus; red, amber and
green only for status, always with a shape and a word or number. Apertus, code and
the reviewer are told apart by a grey tag with a word and an icon. Every page can be
read without JavaScript; `app.js` adds polling, selection, the keys and saving.

- **App bar** on every page: the wordmark, **Drafts** with a count of the drafts that
  need review, **New draft**, the endpoint indicator (the configured model; the dot
  turns green, amber or red from `/healthz`, kept 5 minutes in `sessionStorage`), the
  EN / DE switch and the API link. A "Skip to content" link comes first.
- **Drafts** (`/`): the work queue as a table. Title (an "Example" tag replaces the
  `Example: ` prefix) and where the text came from, language and level, pipeline,
  status (the stage and time while running, the error when failed), the checks of the
  latest draft (errors, warnings, facts present), the review progress, the creation
  time, and a row menu (open, reader view, exports, delete, which asks first). Search,
  status filter with counts and language filter are GET parameters, so they work
  without JavaScript; at most 50 rows, newest first, with the counts computed per
  request from `review_view` (D-Y). An intro strip explains the four steps and can be
  hidden. Without jobs, the empty state offers the team-written example texts.
- **New draft** (`/new`, D-W): the source as pasted text, web address or file (drop
  zone), with the team-written example texts as one-click fills
  (`/new?example=<id>` fills the text without JavaScript, and the decision mode's
  settings from the JSON file next to an example); language, level and
  pipeline as radio lists, the chosen pipeline's stages shown under it; the document
  type (standard text or decision letter), which reveals the addressee and the
  authority's notice, prefilled per document language from `pipeline/labels.py`
  (without JavaScript the two fields stay in view, and an empty notice gets the
  language's default on the server); title, optional model overrides. `POST /jobs`
  answers 400 with the form and the error.
- **Check my text** (`/check`, since 8 October 2026): the deterministic checker on a
  text the writer pasted, as the CLI `check` runs it (one block per sentence, the rules
  of the document's language at the chosen level, German and French), in
  milliseconds, without a model call and without a job: the page answers with the
  blocks and their findings, the document findings by rule, and the counts (errors,
  warnings and notes per 100 blocks, sentences, words per sentence, readability,
  passive, genitive and subordinate-clause shares). Nothing is stored. Facts and
  meaning need the pipeline, which the page says.
- **Job running** (`/jobs/{id}` while queued or running): the stages of the chosen
  condition as a stepper (done, running, waiting, skipped, failed), each with its
  detail line ("14 facts, 14 must survive") and its model usage ("1 call · 2,813
  tokens · 47 s"; Check: "41 rules · no model call"); next to it the results as soon
  as they exist: the fact sheet with the core questions and the facts that must
  survive, then the latest draft with a severity mark on blocks that have findings.
  The page polls `/jobs/{id}/progress` every two seconds and reloads when the job
  reaches review or fails; a failed job shows the error and "Run again".
- **Review** (`/jobs/{id}` once a draft exists): a header with the view switch
  (Review, Reader view), the export menu, the save state ("Saved 10:42") and "Save
  review" (also Ctrl+S); a strip with language, level, pipeline, the draft versions as
  pills with the blocking problems left after each, the repair rounds and the counts.
  On a window at least 1101 px wide and 600 px high the page fits the window and only
  the three panes scroll; smaller windows stack them. The panes:
  1. **Source** - the sentences in order. Selecting a block marks the sentences it came
     from. Sentences left out keep their text, muted, with a "Left out" tag and the
     reason; sentences neither used nor explained carry an amber bar and a "Not
     explained" tag (FACT-04).
  2. **Draft** - the blocks read as text, with an id gutter, a severity column and a
     decision icon. The selected block opens: its findings (rule id, Code or Judge tag,
     message, suggestion; "Apply" replaces the evidence with the suggestion where the
     evidence stands in the text, such as LEX-01's Mediopunkt split), the facts it
     carries, and Approve / Edit / Reject. Filters (all, with findings, undecided),
     "Approve all undecided", the decided count and "Review complete" in the footer.
     Keys, only while the focus is in this pane (WCAG 2.1.4): J and K or the arrows
     move, A, E and R decide, N jumps to the next undecided block; Approve and Reject
     move on to it. Unsaved decisions warn before leaving. Without JavaScript every
     block is open.
  3. **Checks** - four tabs (stacked without JavaScript): **Facts**, problems first,
     with the expected value, the status from code and judge and the judge's note;
     selecting a fact marks the blocks that carry it. **Findings**, the document's
     findings grouped by rule with the rule's title; a FACT-04 line marks its source
     sentences, a FACT-01 line selects its fact. **Questions**, the five core questions.
     **More**, omissions with reasons, glossary, measures, and the run (models, usage,
     notes, rerun and delete).
- **Reader view**: replaces the panes with the HTML export of the decisions on screen,
  unsaved ones included (`POST /jobs/{id}/preview` renders it and stores nothing; `GET
  /jobs/{id}/preview` shows the saved review and is the fallback without JavaScript),
  next to an export panel: the format (Markdown, HTML, audit bundle), the download of
  the saved review, and a "Before publication" list (blocks decided, blocking problems
  in this version, review complete). The keys are off while it is shown.

Type: IBM Plex Sans and Mono for the interface; the reader view uses Atkinson
Hyperlegible Next (D-V), injected into the preview response only. The HTML export
names it first and falls back to Arial and Helvetica, without embedding it. All three
families are vendored as woff2 under `web/static/fonts/` (SIL OFL 1.1, licences next
to the files, THIRD_PARTY_NOTICES.md), so nothing is fetched from another host.

**Interface languages.** The UI speaks English and German; the interface language is
the reviewer's and independent of the document's, so a German-speaking reviewer can
check a French draft. Every text lives in one flat JSON catalog per language,
`web/locales/<code>.json` (keys such as `review.approve`, `{name}` placeholders,
`.one` / `.other` variants for counts, `_name` for the switcher); `web/i18n.py` loads
them and provides `t(key, ...)` to the templates and view models. The texts `app.js`
needs (keys under `js.`) are embedded in each page as JSON, and the script picks
plural forms and relative times with `Intl`. The language is the choice from the EN /
DE switcher in the header (`/ui/{code}`, stored in a cookie for a year), else
`UI_LANG`, else the browser's `Accept-Language`, else English. Adding French or
Italian means adding `fr.json` or `it.json`: the switcher, the language choice and the
tests pick it up, and a test fails until the catalog has every English key with the
same placeholders. The rule checker's findings follow the switch too: a check reports
the key of its message and the values for its placeholders (`rules/messages.py` holds
the English templates; `message_key` and `message_params` travel with the Finding),
the English catalog takes the templates over as `finding.<key>`, and the other
catalogs translate them. A finding from an artifact written before the keys existed
gets key and values read back off its English text with the rule's templates, and
keeps the stored text when none fits. The rules' titles, which head the grouped
findings, join the English catalog the same way as `rule.<ID>` (the base id without
`-DE` or `-FR`). Model output (the judge's notes) is not translated: it stays in the
language it was produced in.

### CLI

| Command | Purpose |
|---------|---------|
| `python -m leichtfacile serve` | The web application |
| `python -m leichtfacile check-llm [--thinking]` | List the endpoint's models and make one call |
| `python -m leichtfacile ingest <file\|url> [--section]` | Print the segments |
| `python -m leichtfacile check <file\|url> [--level]` | Rule checker on an existing easy-language text |
| `python -m leichtfacile simplify <file\|url> [--condition] [--no-judge] [--no-repair] [--stop-after] [--mode decision --addressee --notice]` | The pipeline without the web app; all artifacts and exports go to `--out` |
| `python -m leichtfacile eval fetch\|calibrate\|reference\|run\|report\|sample\|kappa\|diagnose\|rescore` | The evaluation harness (§9); `diagnose` says why must-keep facts are missing from the final drafts of a run; `rescore` scores stored jobs again from their artifacts, without a model call, under either rule for the final version (`--select facts\|blocking`) |
| `python -m leichtfacile examples build` | Build the example jobs shown on first start |

## 8. Languages and levels

| | German | French | Italian |
|---|--------|--------|---------|
| Easy level (A2) | Leichte Sprache | FALC (facile à lire et à comprendre) | lingua facile |
| Plain level (B1) | Einfache Sprache | langage clair / simplifié | linguaggio semplice |
| Rule source | Canton Zürich rules; EBGB (federal) guide; Inclusion Europe "Informationen für alle" | Inclusion Europe "L'information pour tous"; cantonal FALC pages (FR, VD, GE) | Inclusion Europe "Informazioni per tutti"; Canton Ticino pages |
| spaCy model | `de_core_news_md` | `fr_core_news_md` | `it_core_news_md` |
| Readability | Amstad: `180 - ASL - 58.5·ASW` | Kandel-Moles (French Flesch) | Gulpease: `89 + (300·sentences - 10·letters) / words` |
| Swiss conventions | `ss` for `ß`, `500'000`, `9.00 Uhr`, `044 123 45 67`, Helvetisms | `CHF`, `1 500 francs`, Swiss terms (`septante`, `nonante`) | `fr.` / `CHF`, Ticino terms |

Thresholds differ per level (A2 ≤ 12 words per sentence, B1 ≤ 15 by our choice -
there is no official B1 rule set); both are configuration in `rules.md`. French gets
15 and 18 words: it needs about a quarter more words than German for the same content,
as the calibration on the official pages shows (`rules/base.py`, `LANG_PARAMS`).

| Status | German | French | Italian |
|---|--------|--------|---------|
| Checker rules | 30 + 11 shared | 27 + 11 shared | 11 shared |
| Prompts and few-shot examples | yes | yes | no; jobs are refused |
| Calibration on official pages | 30 pages, 2.0 errors / 100 blocks | 5 pages, 2.2 errors / 100 blocks | - |

German came first in the build order. French followed on 6 October 2026, before the
CSCS key arrived: rules, prompts, examples and the web form. Italian stays a stretch
goal. Syllables for readability come from `pyphen` with the `de_CH`, `fr`, `it`
dictionaries.

## 9. Evaluation

### Dataset

`data/pairs/manifest.jsonl`: one row per document pair - `id`, `publisher`, `canton`,
`lang`, `level`, `role`, `topic`, `url_standard`, `url_easy`, `section_standard` and
`section_easy` (a heading when only one section of a page corresponds), approximate
word counts, `facts_estimate`, `licence_note` and `notes`. It holds 35 verified pairs:
30 German (20 `eval`, 10 `dev`) from Zürich, Bern, St. Gallen, Luzern, Basel-Stadt,
Graubünden, Zug and three federal offices, and 5 French (3 `eval`, 2 `dev`). `dev`
pairs are for prompt development and checker calibration; `eval` pairs are held out
for the final numbers. `python -m leichtfacile eval fetch` (or
`scripts/fetch_pairs.py`) downloads and caches the texts under `data/cache/pairs/`
(git-ignored). The publishers do not allow reproduction, so the manifest and the
fetch command are the dataset.

These reference pairs measure the pipeline; they are not the demo. The demo uses
documents that have no easy-language version yet, such as the Federal Council's
explanations for a past vote. Pairs used as few-shot examples in the prompts are
excluded from evaluation. The shortlist, the demo candidates and the licence terms of
each publisher are in [sources.md](sources.md).

For additional German training or calibration data, DEplain (professionally written
plain-German parallel corpus) is a candidate; its licence must be checked before any
use beyond evaluation.

### Conditions

The codes are P0 to P2, P as in pipeline: next to the levels A2 and B1, the letter C
would read as a CEFR level. They were C0 to C2 until 6 October 2026; stored jobs,
result rows and command lines with the old names still work (`canonical_condition`
in schemas.py maps them). On screen the code carries a short label, "P2: full".

| Code | Condition | Purpose |
|------|-----------|---------|
| P0 | Single prompt: "rewrite this in Leichte Sprache" | Baseline; what a naive user gets |
| P0-ZH | Single prompt: the Canton of Zurich's Leichte Sprache prompt, verbatim (`simply-simplify-language` v1.6.0, MIT, THIRD_PARTY_NOTICES.md), as `complete` (keep everything) and `condensed` (essentials only, their default); German only | Baseline; the best public Swiss prompt on the same model |
| P1 | Understand → write → rule check, no judge, no repair | Value of the fact sheet and structure |
| P2 | Full pipeline with judge and repair | Value of checking and repairing |

P1 and P2 include the one edit code makes to the text, the Mediopunkt in long compound
nouns (§4.3); the baselines do not, as Zurich's own Markdown stripping stays out of
P0-ZH. The report shows the compounds split by code per 100 blocks next to the LEX
family, so the deterministic share of the LEX improvement is visible.

Each run with the 8B writer; P2 also with the 70B writer (every stage on the 70B) and
with the 70B for the Understand stage only (`--understand`, the hybrid); `make eval-70b`
runs both. The judge is always the 70B-thinking model, so P1 and P2 are judged by the
same instrument; in the 70B-writer run it grades its own model's drafts, which the
report notes. Result (6 October 2026, 23 pairs): the 70B everywhere writes cleaner
easy language (1.4 against 4.3 errors per 100 blocks) but keeps fewer facts (78
against 84 percent coverage) at 1.8 times the price per page; the hybrid keeps the
fewest (66 percent). The 8B writer stays the default; docs/prompts.md has the tables.

P0-ZH runs with the settings of P0 (no thinking, temperature 0.3, 6000 tokens) and
with the post-processing of Zurich's app: the text between the `<leichtesprache>` tags
is taken and ß becomes ss. Their Markdown stripping is not applied, because it deletes
the underscores of web and e-mail addresses. An answer without the tags is used whole
and noted in the job summary. The prompt file is a Jinja template whose licence note
is a comment; docs/prompts.md has the details. On the 20 German eval pairs (CSCS, 6
October 2026) the complete variant kept 95 percent of the hard facts (fact coverage
91 percent) with 15.4 rule errors per 100 blocks, the condensed variant 77 percent at
8.7 errors; P2 on the 8B kept 80 percent (84) with 4.3 errors.

### Metrics

| Metric | How | Why it matters |
|--------|-----|----------------|
| Fact coverage | Share of `must_keep` facts with a normalised value found in the output (exact, code); since 7 October 2026 only values the source contains count (FACT-05) | Did anything important get lost? |
| Fact status (judge) | Share present / missing / distorted per the judge | Semantic version of the above |
| Invented statements | Unsupported blocks per 100 blocks (judge; human-labelled on a subset) | Hallucination rate |
| Invented values | Dates, amounts, phone numbers, e-mail and web addresses, percentages, times, periods, identifiers, postal addresses, quantities and dosing schemes in the output that the source does not contain, per 100 blocks (exact, code, the FACT-06 check against the source alone) | A hallucination count that needs no model, also for P0 and the official versions |
| Rule violations | Errors and warnings per 100 blocks, by rule family | Compliance with the published rules |
| Compounds split by code | Words that got their Mediopunkt from code in the final version, after the write stage or in any repair round, per 100 blocks (P1 and P2) | The cheap, deterministic part of the LEX gain, kept apart from the model's |
| Readability | Amstad / Kandel-Moles / Gulpease: source vs. output vs. official easy version | Did it actually get easier? |
| SARI | Against the official easy-language reference | Standard simplification metric |
| Judge reliability | Agreement (Cohen's κ) between the judge and 30 hand-labelled outputs; `eval sample` writes the sheets (facts stratified by the judge's verdict, blocks half flagged and half passed, verdicts in a separate key file), `eval kappa` scores a filled sheet | Is the judge trustworthy? |
| Cost and speed | Tokens, latency and estimated cost per page (250 words), 8B vs. 70B; cost in USD at Public AI list prices as an order of magnitude | Value, cost & scalability |
| Hard facts kept | Share of the source's dates, amounts, phone numbers, e-mail addresses, web addresses, percentages, times, periods, identifiers, postal addresses, quantities and dosing schemes found in the output (exact, code, no model; the last five since 7 October 2026, which raised the count on the 20 German eval pairs from 138 to 195) | A fact measure that does not depend on any model, comparable with the official version |
| Silent losses | Share of the source's hard values that the output lost without a trace: not in the text, and nowhere a reviewer would see them. A single prompt and the official version have no fact checklist and no omission log, so every value they lose is silent (the share is 100 minus hard facts kept); for P1 and P2 a lost value is told when the fact sheet carries it (the review checklist lists every fact with its status) or when its source sentence is a listed omission, so their share is zero by design, and a value above zero names one the code completion missed (`eval.score.silent_losses`, since 7 October 2026; the first dev run showed 5 percent and led to two fixes of the completion, percentages and addresses over two sentences) | The property the headline rests on in case B of PLAN.md §13.4: nothing is lost in silence |

Two rows need no model and frame the conditions: SOURCE (the standard-language
original, checked as if it were a draft) and REF (the official easy-language version).
Every output is scored the same way: language rules recomputed on the final text, fact
coverage against one fact sheet per pair, readability, document-level SARI (a port of
the original `SARI.py`, checked bit for bit; its tokenizer drops the Mediopunkt, so
`Kranken·kasse` is the source's `Krankenkasse` and a split by code is not a deleted and
an added word), judge statistics where a judge ran.
Outputs land in `eval/results/*.jsonl` (git-ignored, they contain rewrites of
protected pages); `python -m leichtfacile eval report` renders the tables for the
technical report from aggregates only, and `eval numbers` prints the headline means
(P2 against the Zurich prompt in its complete mode, the plain writer with the most
pairs per setup) and the case of PLAN.md §13.4 they fall into, with the headline
sentence filled in, so that README, report and video carry the same numbers. If the dataset is published, it follows
the Hugging Face `HackApertus/online_hack_template` layout: test cases, model
responses, and metadata with per-instance licensing.

## 10. Deployment and sovereignty

### `make run`

`make run` → `docker compose up --build`. The Makefile first checks that
`LLM_BASE_URL`, `LLM_API_KEY` and `LLM_NAME` are set, each in the shell or in `.env`,
and prints a short help text otherwise. The `.env` file is optional: Compose reads it
when it exists and passes the three variables through from the shell, where a value
in the shell wins over `.env`. It then checks that Docker is installed, that the
daemon answers and that Compose v2 is there, and otherwise says which one is missing
and how to start Docker (`check-docker`, also before `stop`, `check-llm` and `smoke`). Next to Compose it starts `scripts/open_browser.sh`, which polls
`/healthz` from the host and opens http://localhost:8000 in the default browser
(Windows, macOS, Linux desktops, WSL); without a desktop it prints the address, and
`OPEN_BROWSER=0` turns it off. The helper is stopped with Compose. The image is built from `python:3.14-slim` (the project supports
Python 3.12 and later) and installs the locked dependencies from `uv.lock` with `uv`
at **build** time, including the spaCy models as pinned wheel URLs. German and French
are in the image; the Italian model is added when Italian ships. The
vendored UI assets are copied in the same way. At **runtime** the container needs
exactly one outbound connection: `LLM_BASE_URL`. It runs as a non-root user, keeps
its data in the named volume `appdata` (mounted at `/data`), and has a Docker health
check on `/healthz`. The app listens on `:8000`, with pre-computed example jobs
so the UI is not empty before the first live run (clearly labelled as examples): the
premium-reduction letter in German and in French; the KESB decision with personal data
follows once decision mode v1 is in (PLAN.md WP15). The example jobs are audit bundles in
`data/examples/jobs/`, built from the team's sample documents with `python -m
leichtfacile examples build` (`--only <name>` for one) once an endpoint is available,
and imported into the store on start. A source's job settings, such as the decision
mode and the addressee, come from a JSON file next to it (data/examples/README.md).

`make check-llm` lists the endpoint's models and makes one short call from inside the
container; it is the first thing to run once a key is set.

### The three target architectures

| Architecture | How Leicht·Facile meets it |
|--------------|----------------------------|
| a) On-premise | `docker compose --profile local-llm up`: adds a `vllm` service from the official image `ghcr.io/swiss-ai/vllm_apertus_1.5_release:latest-amd64` serving `swiss-ai/Apertus-v1.5-8B` on one GPU, with the Apertus reasoning parser and `--max-model-len 32768`; the app points at `http://vllm:8000/v1` with `LLM_THINKING_MODE=chat-template`, so one server provides both modes. The 70B judge is optional and can be the 8B in a pinch. **[verify]** on a GPU host: the compose file validates, but the service has not been started yet. |
| b) Air-gapped | Same as (a) with images and weights pulled in advance; spaCy models and UI assets are inside the image; no telemetry, no CDN, no package installs at runtime. A `make bundle` target saves the images to a tarball. |
| c) Sovereign Swiss cloud | Set `LLM_BASE_URL` to a Swiss-operated Apertus endpoint (Swisscom AI Platform, Infomaniak; both list Apertus 1.5 70B). The hackathon demo itself runs against the CSCS inference API in Lugano, which serves research, not administrations. |

Hardware for (a)/(b), to be measured and stated precisely in the report: the 8B
model in bf16 needs roughly 16 GB for the weights plus KV cache, so a 24 GB GPU with
a reduced `--max-model-len` is realistic; the FP8 build (`onprem-ai/Apertus-v1.5-8B-FP8`,
keeps image input) is 11.42 GB against 18.44 GB for the full multimodal checkpoint.

A smaller on-premise option was tested on 5-6 October 2026: llama.cpp (`llama-server`,
Vulkan build b9637) with the community 4-bit text-only conversion
`Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF` (5.06 GB) on a laptop GPU (RTX 4060, 8 GB),
16k context with an 8-bit KV cache. It generated about 37 tokens per second at short
context and about 17 near 16k; Understand took about 1.5 minutes and Write, with
thinking, about 12 minutes for a 400-word letter. It runs the whole pipeline
including thinking mode (`LLM_THINKING_MODE=chat-template`, `llama-server -sp`), but
it has no image input and is an unofficial conversion, so it serves development and
small offices, not the evaluation. `docker compose --profile local-llm-small up` adds
this server as a `llamacpp` service (official `ghcr.io/ggml-org/llama.cpp:server-cuda`
image, weights downloaded on first start); it is served under the alias
`apertus-v1.5-8b-q4-llamacpp`, so its results can never be mistaken for the official
model. Tested on 6 October 2026 with that image (llama.cpp b11429, CUDA) on the same
laptop: the model starts in 6 seconds from the named volume and takes 5.9 GB of GPU
memory. Mounting the model file from a Windows folder instead stalls the start for
many minutes (memory-mapped reads through Docker Desktop's file sharing); the named
volume avoids that. The 70B is served with tensor parallelism over four
GPUs in the official guide; FP8/NVFP4 builds reduce that. The business argument of
the stretch goal (§4.8) is precisely that a fine-tuned 8B makes the 70B unnecessary
at runtime.

### Security and privacy

- Documents contain personal data. In production the model endpoint is inside the
  organisation, so content never leaves. The hackathon demo uses public documents only.
  Decisions of child and adult protection authorities and courts are the most
  sensitive case: before anonymisation they name a person and describe their health,
  family and finances ([use-case-decisions.md](use-case-decisions.md) §2). Why such
  texts leave Apertus as the only model that fits: [use-cases.md §2](use-cases.md#why-only-apertus).
- No authentication in the prototype; it is meant to run behind the organisation's
  reverse proxy. Noted as a limitation.
- Jobs and artifacts live on the mounted volume and can be deleted via the API.
- The server fetches the URLs users submit, so a URL that resolves to a private,
  loopback or link-local address is refused (server-side request forgery);
  `ALLOW_PRIVATE_URLS=1` lifts this for an intranet that needs internal pages.
- No document text in logs above `DEBUG`; the LLM cache can be disabled.

## 11. Repository layout

```text
.github/workflows/ci.yml  CI: ruff, pytest, Docker image built and started against an unreachable endpoint
Makefile                  run · stop · check-llm · test · lint · smoke · calibrate · day1 · eval
docker-compose.yml        app (+ profile local-llm: vllm)
Dockerfile
pyproject.toml, uv.lock   dependencies (uv), Python 3.12+; .python-version pins 3.14
.env.example              endpoint profiles: CSCS, local vLLM, Public AI, Hugging Face, llama.cpp
README.md                 project overview, quick start, status; Track 2B challenge text (template)
technical_report.md       the report (PDF: RoestigrabenBridgers_Report.pdf)
THIRD_PARTY_NOTICES.md    the Canton of Zurich's prompt (MIT) used as baseline P0-ZH; the fonts (OFL)
docs/
  architecture.md         this document
  ui-design.md            the web UI's specification (WP18)
  rules.md                rule catalogue → implemented by src/leichtfacile/rules
  prompts.md              prompt design notes and change log
  sources.md, use-case-canton.md, hard-texts.md
src/leichtfacile/
  __main__.py, cli.py     serve, check-llm, ingest, check, simplify, eval, examples
  config.py               env → settings (pydantic-settings)
  schemas.py              artifacts (§5)
  store.py                SQLite access
  examples.py             example jobs: import on start, build
  llm/                    client.py, json_out.py, reasoning.py, cache.py
  llm/prompts/<lang>/     understand.md, write.md, judge.md, repair.md, baseline.md, examples/;
                          decision.md (the decision mode's partial, included by the four
                          standard templates when mode is "decision");
                          de/baseline_zh.md (Zurich's prompt, verbatim)
  ingest/                 html.py, pdf.py, text.py, segment.py, normalize.py, detect.py, errors.py
  pipeline/               models.py, prompts.py, render.py, stages.py, orchestrator.py, runner.py
  rules/                  base.py, messages.py, de.py, fr.py, document.py, layout.py, values.py,
                          lexicon.py, readability.py, styleguide.py, checker.py, nlp.py,
                          vocabulary.py, data/ (vocabulary_de.toml, vocabulary_fr.toml),
                          recipes.py (clause recipes), mediopunkt.py,
                          glossary.py (glossary entries from the vocabulary)
  web/                    app.py, api.py, pages.py, jobs.py, views.py, i18n.py, templates/,
                          static/ (app.css, app.js, fonts/), locales/ (en.json, de.json)
  export/                 markdown.py, html.py, bundle.py
  eval/                   dataset.py, calibrate.py, score.py, run.py, report.py, metrics.py,
                          labels.py, diagnose.py (why facts go missing), image_spike.py,
                          day1.py, cli.py
scripts/                  fetch_pairs.py, day1_checks.py, print_letters.py, image_spike.py
data/
  pairs/manifest.jsonl    URLs + licence notes (committed)
  examples/               team-written sample documents, printable letters; example job bundles
  cache/                  fetched texts, LLM cache (git-ignored)
eval/results/             evaluation outputs (git-ignored)
tests/                    rules (golden sentences, hard texts), ingest, pipeline (fake endpoint),
                          eval, web
```

`data/` stays well under the 100 MB limit because texts and caches are not committed.

## 12. Day-1 verification checklist

Assumptions to confirm against the live endpoint, in this order. Run on the Public AI
gateway on 6 October 2026 and, when the key arrived the same day, on CSCS (both
results below). `make day1`
(`scripts/day1_checks.py`) runs checks 1-5 and writes `eval/results/day1_checks.json`;
check 6 is `python -m leichtfacile eval run --condition P0 --limit 10`. Checks 2 and 3
were rehearsed against the local llama.cpp endpoint (§10): thinking switches per request
through `chat_template_kwargs`, the reasoning arrives inline between `<|inner_prefix|>`
and `<|inner_suffix|>` and is stripped, and the answer ends with a control token that the
client removes.

1. `GET {LLM_BASE_URL}/v1/models` lists `swiss-ai/Apertus-v1.5-8B`, `…-8B-thinking`,
   `…-70B`, `…-70B-thinking`; the base URL host issued for the hackathon
   (`api.inference.cscs.ch` per the CSCS docs; some public projects use
   `api.swissai.svc.cscs.ch`).
2. How thinking output is returned by the `-thinking` models: a separate
   `reasoning_content` field, or inline tokens that must be stripped.
3. JSON reliability: 20 Understand calls on one document, count parse failures with
   and without `response_format`.
4. Image input through the API (a photographed letter); if unsupported, scans become
   a local-vLLM-only feature.
5. Rate limits and concurrency (the docs do not state them) - determines whether
   section-parallel writing is worth it.
6. Baseline quality: P0 on 10 German pairs. This decides whether the A2 level is
   realistic for the 8B model or whether B1 becomes the primary target with A2 as the
   stretch.

### Results on the Public AI gateway, 6 October 2026

`make day1` with profile C (§6): the 8B `swiss-ai/apertus-v1.5-8b`, served by vLLM
at Juelich. The CSCS key had not arrived. Full output in
`eval/results/day1_checks.json`.

1. **Models.** All four Apertus 1.5 names are listed, in lowercase
   (`swiss-ai/apertus-v1.5-8b`, `-8b-thinking`, `-70b`, `-70b-thinking`), next to the
   Apertus 1 names (`apertus-8b-instruct`, `-70b-instruct`) and three unrelated
   models. The `-thinking` names are not used on this gateway (§6). The host and the
   capitalised names: see CSCS below.
2. **Thinking.** The 8B answered the arithmetic question without any reasoning (4
   output tokens). Fourteen further calls on the same day with `enable_thinking`
   through the chat template, short and long prompts, with and without JSON mode,
   returned no reasoning either, after three calls in the morning had reasoned in two
   cases. On this gateway thinking is unreliable to absent for the 8B and off for the
   70B, so Public AI runs are, in effect, runs without thinking at every stage and are
   labelled that way. The reasoning format of the `-thinking` models: see CSCS below.
3. **JSON.** 20 of 20 Understand answers on the sample letter parsed and validated
   without `response_format`, and 20 of 20 with `{"type": "json_object"}`; nothing
   truncated. JSON mode is accepted by the vLLM backend and changes neither the
   backend nor the answer: a side-by-side pair gave the same fact sheet with 995
   against 1,102 output tokens in 47 against 52 seconds. Decision D-B: `response_format`
   is not used; the example in the prompt, lenient parsing and one repair round are
   enough. The medians of the two runs (46 against 9 seconds) differ because the
   backend's speed varied with load during the run, from about 20 to about 120 output
   tokens per second. Three of the twenty long calls got a 504 from the gateway and
   succeeded on the retry after 30 seconds. The P0 baseline run later lost 3 of 6
   pairs to the same 504 after five attempts each: Cloudflare in front of the gateway
   cuts any response that takes longer than about 100 seconds, which a long page at
   20 tokens per second exceeds. The client now streams every response (§6), so the
   limit no longer applies.
4. **Image input.** Works: the 8B read a rendered letter (PNG as base64 `image_url`)
   and answered "Man muss bis zum 31. März 2026 handeln." The same on CSCS, below.
5. **Parallel calls.** 8 short calls at once: all succeeded, no 429, 1.4 to 2.2
   seconds each, no rate-limit headers. Decision D-F: there is headroom; the
   evaluation can run several pairs at once, section-parallel writing stays optional.
6. **Baseline.** P0 (one prompt, 8B without thinking) on the first 10 held-out German
   pairs, 6 October 2026: 16.1 errors and 85 warnings per 100 blocks against 2.7 and
   27 for the official easy-language versions and 31.3 and 146 for the sources; 7.1
   words per sentence (official: 6.1); readability 46 (official: 62, sources: 36);
   90 percent of the hard facts kept (the official versions keep 70). The findings
   are mostly sentence length (LEN 33 per 100 blocks) and vocabulary (LEX 47:
   abbreviations, long compounds without Mediopunkt). One prompt does not reach A2;
   decision D-E (A2 or B1 as the primary level) waits for P2 on the dev split.

One cost figure from the gateway's headers: an Understand call on the 400-word sample
letter (1,829 tokens in, about 1,000 out) costs USD 0.0004 on the 8B.

### Results on CSCS, 6 October 2026

`make day1` with profile A, the hackathon key, the same afternoon. Full output in
`eval/results/day1_checks_cscs.json` (the Public AI run is kept as
`day1_checks_publicai.json`).

1. **Models and host.** `https://api.inference.cscs.ch/v1` lists `swiss-ai/Apertus-v1.5-8B`,
   `-8B-thinking`, `-70B` and `-70B-thinking` in that spelling, next to the Apertus 1
   models (`Apertus-8B-Instruct-2509`, `-70B-`) and six models of other makers. A short
   call answers in about 100 milliseconds.
2. **Thinking.** `LLM_THINKING_MODE=model-suffix` works as designed: the `-thinking`
   models reason, and the reasoning arrives in the `reasoning` field of every streamed
   chunk (the newer vLLM name; the client reads `reasoning_content` too), never inline.
   The budget is the price: for the 400-word sample letter the 8B wrote 3,000 to 17,000
   characters of reasoning per Understand call, 1,800 to 7,000 output tokens in total,
   in 12 to 90 seconds at about 150 tokens per second; without thinking the same
   call is about 1,000 tokens and 10 seconds.
3. **JSON.** 19 of 20 Understand answers with thinking parsed and validated without
   `response_format` (the twentieth call failed on the connection, below) and 20 of 20
   with `{"type": "json_object"}`; medians 36 and 38 seconds. Decision D-B stands:
   `response_format` is not used.
4. **Image input.** Works on CSCS too: the 8B read the rendered letter and answered
   "bis zum 31. März 2026".
5. **Parallel calls.** 8 short calls at once, all in 98 to 104 milliseconds, no 429.
   Decision D-F stands.
6. **Connection drops.** About one in four long thinking calls ends with the server
   closing the stream (`peer closed connection without sending complete message body`,
   `incomplete chunked`), after seconds to a minute of generation; 10 of the 40 calls of
   check 3 needed retries and one failed after five attempts. The rate is the same for
   sequential and for eight parallel calls, so it is not our load. The client retries
   such drops; `LLM_MAX_RETRIES` defaults to 8, which makes a hard failure rare, at the
   price of repeated generation time.
7. **Baseline.** P0 on the eval pairs runs on CSCS with `make eval`; the Public AI
   baseline above was the first reading.

## 13. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| The 8B model cannot reach A2 quality | Fact sheet, examples and repair loop are designed to compensate; if it still fails, B1 becomes the primary level and the A2 gap is reported as a finding with numbers. |
| JSON output unstable | Schema in prompt, lenient parse, pydantic validation, one error-feedback retry; measured in day-1 check 3. |
| Model judging itself is biased | Everything countable is in code; the judge is a different, larger model; judge agreement with human labels is reported. |
| CSCS endpoint rate-limited or down | Backoff and cache; single-worker queue; evaluation runs overnight. |
| Image input not available on the hackathon endpoint | Feature flagged; demo uses text and HTML; scans shown with local vLLM only if time allows. |
| Scope creep across three languages | German end-to-end with numbers first (by 10 October); FR/IT only afterwards. |
| No compute for the LoRA | Stretch goal; the pipeline's value does not depend on it. The data it would need (approved drafts, edits) is collected regardless. |
| Over-promising to public-sector judges | Positioned as a drafting assistant for professionals; target-group review stays mandatory; limitations stated in the report. |

## 14. Milestones

| Dates | Deliverable |
|-------|-------------|
| Oct 5-6 | Repo, Docker, `make run` with a health check; LLM client; day-1 checks; P0 baseline on 10 German pairs |
| Oct 7-8 | Understand, write, rule checker (DE), repair loop; artifacts visible via API |
| Oct 9-10 | Judge; evaluation harness; first P0 / P1 / P2 numbers; dataset manifest at 20+ pairs |
| Oct 11-12 | Review UI; export; French and Italian rules and prompts |
| Oct 13 | 8B vs. 70B comparison; judge reliability labelling (30 items); LoRA only if compute exists |
| Oct 14-15 | Technical report (≤ 6 pages), demo video (≤ 2 min), clean-checkout test of `make run`, repo set to public |
| Oct 16, morning | Submit on hackapertus.ch/online-hack/submissions (deadline 12:00 CEST) |

## References

- Apertus v1.5 model card - context length, multimodal input, thinking mode:
  https://huggingface.co/swiss-ai/Apertus-v1.5-8B
- vLLM serving guide and official images: https://apertus-ai.org/docs/guides/vllm/
- CSCS LLM inference API (OpenAI-compatible, model names): https://docs.cscs.ch/services/inference/api/
- Canton Zürich, rules for Leichte Sprache:
  https://www.zh.ch/de/webangebote-entwickeln-und-gestalten/inhalt/barrierefreiheit/regeln-fuer-leichte-sprache.html
- EBGB (Swiss federal bureau for equality of people with disabilities), Leitfaden Leichte Sprache:
  https://www.ebgb.admin.ch/dam/de/sd-web/ZHKNDzIYahOc/Leitfaden%20Leichte%20Sprache.pdf
- Apertus fine-tuning recipes, quantised builds and community tooling: https://github.com/rnckp/awesome-apertus
- Hack Apertus Track 2B rules and deliverables: https://hackapertus.notion.site/track-2-b-own-project
