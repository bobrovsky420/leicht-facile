# Example documents

The example documents live in two folders. The example letters the app offers are part
of the package, in [`src/leichtfacile/letters/`](../../src/leichtfacile/letters/), so an
installed wheel brings them along. This folder, `data/examples/`, holds the printed
letters of the image input spike in `data/examples/print/` (below).

## Example letters (`src/leichtfacile/letters/`)

The letters in `src/leichtfacile/letters/` are written by the team for testing and
demonstration. They imitate the style of Swiss official letters but describe no real
authority: the municipalities Musterwil and Exempleville are invented, the web and
e-mail addresses use the reserved `.example` domain, and 044 123 45 67 and
022 123 45 67 are example numbers in the style of Swiss style guides. The New draft
form offers each one as a one-click fill (`/new?example=<file name>`), and so does the
drafts list while it is empty.

| File | Content | Use |
|------|---------|-----|
| `praemienverbilligung-brief.txt` | Letter about health insurance premium reduction: income limits, a deadline, documents to enclose, objection period, contact | The smoke run (`uv run leichtfacile simplify src/leichtfacile/letters/praemienverbilligung-brief.txt --out out/smoke`), tests, an example text in the New draft form |
| `reduction-primes-lettre.txt` | The same letter in French (réduction individuelle des primes) | French test runs, an example text in the New draft form |
| `entscheid-beistandschaft-musterwil.txt` | A decision of an invented KESB: a deputyship (Vertretungsbeistandschaft mit Vermögensverwaltung) for an invented woman with a mild intellectual disability, who keeps deciding where she lives. Personal data (name, date of birth, address, AHV number), a case number, an IBAN, the operative part with dates and amounts, and the 30-day appeal period with the court's address | Decision mode (docs/use-case-decisions.md), tests, an example text in the New draft form |

A JSON file next to a letter holds that example's job settings, any `JobConfig` field:
`entscheid-beistandschaft-musterwil.json` runs the KESB decision in decision mode
(`mode`), speaking to Lea Muster (`addressee`), with the KESB's fixed notice (`notice`).
Letters without one run as standard P2 jobs at level A2.

The KESB decision follows the layout of real ones: the header with the panel, the
person and the subject, then I. Sachverhalt, II. Erwägungen, III. Entscheid and the
Rechtsmittelbelehrung, as in the two specimen decisions in the annex of the KESB
Graubünden's guide to deputyships (*Leitfaden Mandatsführung und Vermögensverwaltung*)
and the KOKES model decision; the operative items and the appeal clause use their
wording. The AHV number has a wrong check digit and the IBAN the check digits 00, so
neither can belong to anyone. The people, the street, the bank and the doctor are
invented.

`data.examples_dir` points the app at another folder of letters instead (`leichtfacile
config set data.examples_dir <folder>`, [configuration.md](../../docs/configuration.md)):
`.txt` or `.md` files, each with an optional `.json` of job settings next to it. The default is the package's folder (`LETTERS_DIR` in
`src/leichtfacile/config.py`).

## Printed letters (image input)

`data/examples/print/` holds two more letters, made for the image input spike ([image-input.md](../../docs/image-input.md)): each as a
PDF to print and as the printed text in reading order (`.txt`: blocks separated by a
blank line, table cells by a tab), the reference a transcription is compared with.
`uv run python scripts/print_letters.py` writes all four files again, byte for byte the
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
(`steuermahnung-brief_photo-dim_p1.jpg`). A page scanned at 300 dpi is 0.5 to 0.8 MB.

| File | Capture |
|------|---------|
| `print/scans/steuermahnung-brief_scan.pdf` | 7 October 2026: printed, folded in three, flatbed scan at 300 dpi in colour (Canon), 1 page. One crease runs along the top of the subject line, one through the last line of the paragraph on instalments |
| `print/scans/bourse-etudes-decision_scan.pdf` | The same, 2 pages in one file. On page 1 a crease runs through the IBAN line (`CH00 0571 2009 4417 6382 9`); page 2 is slightly skewed |

Each page of these PDFs is one JPEG (2480 x 3507 pixels) and the PDFs have no text
layer, so the PDF ingest refuses them as scans. A test takes the page JPEGs out
unchanged (pdfplumber: `page.images[0]["stream"].get_rawdata()`), without rendering
or re-encoding.

Texts from cantonal or federal web pages are stored in neither folder: their
publishers do not allow reproduction (docs/sources.md §4). The evaluation fetches them
into the git-ignored `data/cache/` instead.
