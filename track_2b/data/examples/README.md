# Example documents

Texts in `sources/` are written by the team for testing and demonstration. They imitate
the style of Swiss official letters but describe no real authority: the municipalities
Musterwil and Exempleville are invented, the web and e-mail addresses use the reserved
`.example` domain, and 044 123 45 67 and 022 123 45 67 are example numbers in the style
of Swiss style guides.

| File | Content | Use |
|------|---------|-----|
| `sources/praemienverbilligung-brief.txt` | Letter about health insurance premium reduction: income limits, a deadline, documents to enclose, objection period, contact | Smoke test (`make smoke`), day-1 check 3, example job, prepared letter (recorded run) |
| `sources/reduction-primes-lettre.txt` | The same letter in French (réduction individuelle des primes) | French test runs, French example job, prepared letter (recorded run) |
| `sources/entscheid-beistandschaft-musterwil.txt` | A decision of an invented KESB: a deputyship (Vertretungsbeistandschaft mit Vermögensverwaltung) for an invented woman with a mild intellectual disability, who keeps deciding where she lives. Personal data (name, date of birth, address, AHV number), a case number, an IBAN, the operative part with dates and amounts, and the 30-day appeal period with the court's address | Example job in decision mode once decision mode v1 is in (PLAN.md WP15), the video's product scene (track_2b/docs/use-case-decisions.md); an example text in the New draft form, no recorded run (below) |

A JSON file next to a source holds that example's job settings, any `JobConfig` field:
`sources/entscheid-beistandschaft-musterwil.json` runs the KESB decision in decision mode
(`mode`), speaking to Lea Muster (`addressee`), with the KESB's fixed notice (`notice`).
Sources without one run as standard P2 jobs at level A2.

The KESB decision follows the layout of real ones: the header with the panel, the
person and the subject, then I. Sachverhalt, II. Erwägungen, III. Entscheid and the
Rechtsmittelbelehrung, as in the two specimen decisions in the annex of the KESB
Graubünden's guide to deputyships (*Leitfaden Mandatsführung und Vermögensverwaltung*)
and the KOKES model decision; the operative items and the appeal clause use their
wording. The AHV number has a wrong check digit and the IBAN the check digits 00, so
neither can belong to anyone. The people, the street, the bank and the doctor are
invented.

## Example jobs

`jobs/` holds the pre-computed example jobs, one audit bundle per source, imported into
the store on the first start so the UI is not empty: for now the premium-reduction
letter in German and in French. The KESB decision's job follows with decision mode v1:
built on 7 October 2026 with today's pipeline, its draft carried an appeal deadline the
decision does not contain and gave the deputy's tasks to Lea Muster (PLAN.md WP15). The
jobs are built with the endpoint and the settings of `.env`:

```
uv run python -m leichtfacile examples build                # every source
uv run python -m leichtfacile examples build --only entscheid-beistandschaft-musterwil
```

The build runs each source through P2 in its own store (`track_2b/data/examples-build.sqlite`)
and writes `jobs/<source>.json`; a job that fails writes nothing. Neither does a job
whose final draft still shows errors (rule findings of severity error, facts the judge
finds missing or distorted, unsupported statements): someone opening the application
for the first time reads a red error count as a fault of the application. The bundle
already in `jobs/` then stays; `--allow-problems` writes the job anyway, and
`track_2b/tests/test_examples.py` fails on a shipped job with errors (its `KNOWN_PROBLEMS`
set marks shipped bundles with errors as expected failures; it is empty). The shipped
bundles are of 10 October 2026, built on that day's pipeline (the polish round, the
judge's quotes and spelling line, the fact links, sentences placed after a list;
PLAN.md D-AF to D-AI) in five rounds of six fresh attempts per letter with the response
cache off. The bundles of 7 October had carried 4 and 12 errors and no rebuild before
10 October had been clean; of the 60 attempts of 10 October, 5 came out without an
error, and the shipped ones are the German draft whose list of enclosures stands in
one piece and the French draft that reads best. Both show 0 errors, every fact
present and 17 and 14 warnings on first start: the warnings are the reviewer's work
list, not faults.

## Recorded runs (prepared letters)

`replay/` holds one recorded run per prepared letter, so that a first visitor can send
a letter through the pipeline without pasting one and without waiting minutes for the
endpoint (since 11 October 2026; `llm/replay.py`, track_2b/docs/architecture.md §6).
The drafts list's card "Try a prepared letter" offers every letter recorded here with
a Run button, which sends it as the New draft form would. The job's first run then
takes Apertus's answers from the recording, in about 3 seconds instead of a minute
or more, and the job and review pages say so, with the date and the recorded run's
duration. Only a byte-identical prompt replays: change the text, a setting or a
model, or run a step again, and Apertus answers live. The button Run without cache
next to Run (since 13 October 2026) sends the unchanged letter to Apertus live as
well, past the recording and the response cache. The same letter's example job
(above) is a different run, so its draft differs.

A recording holds the answers in call order (stage, model, tokens, latency and the
answer's text), keyed by the hash of the prompt as in the response cache, without the
prompts and without the reasoning; and the settings the prompts depend on (models,
thinking switch, rounds), the date, the endpoint and the result. It is made with the
endpoint and the settings of `.env`:

```
uv run python -m leichtfacile examples record                    # every source
uv run python -m leichtfacile examples record --only reduction-primes-lettre --attempts 18
```

The command sends each source through the pipeline as its Run button does, with a
recorder as the response cache that keeps every answer, also those the pipeline threw
away and asked again for, so the replay takes the same path. It runs `--parallel` (3)
attempts at a time until a batch has a clean one (no error by the example jobs'
measure, above), at most `--attempts` (6), and writes the clean run with the fewest
warnings; a letter without a clean run keeps its file (`--allow-problems` writes the
run with the fewest errors). Every attempt stays in
`track_2b/data/examples-record.sqlite`. `track_2b/tests/test_examples.py` replays each
recording without an endpoint and fails when a prompt has changed since: the letter
would then run live, so record it again.

Recorded on 11 October 2026 on CSCS (the 8B reads, writes and repairs, the 70B
judges; the default settings):

| Letter | Attempts | Recorded run | Final draft |
|--------|----------|--------------|-------------|
| `praemienverbilligung-brief` | 3, all clean | 7 calls, 70 s of model time | v4: 0 errors, 11 warnings, 12 of 12 facts |
| `reduction-primes-lettre` | 6, one clean | 11 calls, 52 s | v6: 0 errors, 7 warnings, 12 of 12 facts |
| `entscheid-beistandschaft-musterwil` | 18, none clean | not recorded | 5 to 19 errors per run (overlong sentences, provenance, items of the operative part not carried over, FACT-08); every fact kept in the best runs. It stays an example text in the New draft form, off the card (owner's decision, 11 October 2026) |

## Printed letters (image input)

`print/` holds two more letters, made for the image input spike (PLAN.md WP12): each as a
PDF to print and as the printed text in reading order (`.txt`: blocks separated by a
blank line, table cells by a tab), the reference a transcription is compared with.
`uv run python track_2b/scripts/print_letters.py` writes all four files again, byte for byte the
same. Everything in them is invented as above, and so are the people and the streets;
the IBANs carry the check digits 00 and the AHV number a wrong check digit, so none of
them can belong to anyone.

| File | Content | What it tests |
|------|---------|---------------|
| `print/steuermahnung-brief.pdf` | German, 1 page: first reminder for unpaid taxes | A table of amounts with a negative line and a bold total, an IBAN, a tax number, dates and a payment deadline, a percentage, office hours, a drawn signature |
| `print/bourse-etudes-decision.pdf` | French, 2 pages: registered decision granting a study grant | A reference block with an AHV and a file number, a calculation table, two payment dates, periods of 14 and 30 days, a running header on page 2, the means of appeal in small print, two signatures |

Print at 100 % (not "fit to page") and fold in three along the marks on the left edge,
as for a window envelope. Scan to JPEG or PNG, or to a PDF without OCR: a scanner's
searchable PDF carries its own text layer, which the PDF ingest would read instead of
Apertus.

Scans and photos go to `print/scans/`, named `<letter>_<capture>` with the letter's
file name in front, so a test pairs each with its `.txt`. A scan is the scanner's PDF
with all pages of the letter in order; photos are JPEGs, one per page, with `_p<page>`
(`steuermahnung-brief_photo-dim_p1.jpg`). A page scanned at 300 dpi is 0.5 to 0.8 MB;
`track_2b/data/` must stay under 100 MB for the submission.

| File | Capture |
|------|---------|
| `print/scans/steuermahnung-brief_scan.pdf` | 7 October 2026: printed, folded in three, flatbed scan at 300 dpi in colour (Canon), 1 page. One crease runs along the top of the subject line, one through the last line of the paragraph on instalments |
| `print/scans/bourse-etudes-decision_scan.pdf` | The same, 2 pages in one file. On page 1 a crease runs through the IBAN line (`CH00 0571 2009 4417 6382 9`); page 2 is slightly skewed |

Each page of these PDFs is one JPEG (2480 x 3507 pixels) and the PDFs have no text
layer, so the PDF ingest refuses them as scans. A test takes the page JPEGs out
unchanged (pdfplumber: `page.images[0]["stream"].get_rawdata()`), without rendering
or re-encoding.

Texts from cantonal or federal web pages are not stored here: their publishers do not
allow reproduction (track_2b/docs/sources.md §4). The evaluation fetches them into the
git-ignored `track_2b/data/cache/` instead.
