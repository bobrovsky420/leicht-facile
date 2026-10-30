# Example documents

The example documents live in two folders. The example letters the app offers are part
of the package, in [`src/leichtfacile/letters/`](../../src/leichtfacile/letters/), so an
installed wheel brings them along. This folder, `data/examples/`, holds the printed
letters of the image input spike in `data/examples/print/` (below).

## Example letters (`src/leichtfacile/letters/`)

The letters in `src/leichtfacile/letters/` are written by the team for testing and
demonstration. They imitate the style of Swiss official letters but describe no real
authority: the municipalities Musterwil, Exempleville and Esempiopoli are invented, and
so are their schools and the camp villages Musterberg, Montexemple and Montesempio; the
web and e-mail addresses use the reserved `.example` domain, and 044 123 45 67,
022 123 45 67 and 091 123 45 67 (the schools' numbers end in 70, the camp phone is
079 123 45 67) are example numbers in the style of Swiss style guides. The New draft
form offers each one as a one-click fill (`/new?example=<file name>`), and so does the
drafts list while it is empty.

| File | Content | Use |
|------|---------|-----|
| `praemienverbilligung-brief.txt` | Letter about health insurance premium reduction: income limits, a deadline, documents to enclose, objection period, contact | The smoke run (`uv run leichtfacile simplify src/leichtfacile/letters/praemienverbilligung-brief.txt --out out/smoke`), tests, an example text in the New draft form |
| `reduction-primes-lettre.txt` | The same letter in French (réduction individuelle des primes) | French test runs, an example text in the New draft form |
| `riduzione-premi-lettera.txt` | The same letter in Italian (riduzione individuale dei premi), from the invented municipality of Esempiopoli | Italian test runs, an example text in the New draft form |
| `entscheid-beistandschaft-musterwil.txt` | A decision of an invented KESB: a deputyship (Vertretungsbeistandschaft mit Vermögensverwaltung) for an invented woman with a mild intellectual disability, who keeps deciding where she lives. Personal data (name, date of birth, address, AHV number), a case number, an IBAN, the operative part with dates and amounts, and the 30-day appeal period with the court's address | Decision mode (docs/use-case-decisions.md), tests, an example text in the New draft form |
| `wohngeld-bescheid.txt` | Germany (29 October 2026): a Wohngeld-Bescheid of the invented Stadt Musterstadt (postcode 12345), the decision before the heading Begründung (286,00 Euro a month from 1 September 2026 to 31 August 2027, 572,00 Euro of back pay, August refused), the duties to report changes, a Rechtsbehelfsbelehrung "innerhalb eines Monats nach Bekanntgabe"; the IBAN has invalid check digits | Decision mode in an installation in Germany (`texts.region = "DE"`), tests, an example text in the New draft form there |
| `familienbeihilfe-bescheid.txt` | Austria (29 October 2026): a Bescheid of the invented Finanzamt Musterhausen (postcode 9999) with the headings Spruch, Begründung and Rechtsmittelbelehrung: € 1.500,- to repay by 18. Jänner 2027, because the son's income exceeded the limit (§ 5 FLAG), an RSb mark, the address Gartengasse 3/2/5, the Beschwerde "binnen eines Monats nach Zustellung" (the BAO's period, § 245) | Decision mode in an installation in Austria (`texts.region = "AT"`), tests, an example text in the New draft form there |
| `klassenlager-elternbrief.txt` | School letter to parents (30 October 2026): the Klassenlager of the invented Primarschule Musterwil, 7 to 11 June 2027 at the Lagerhaus Sonnenhalde, 7999 Musterberg: a compulsory school event, dispensation only on a written request by 30 April, departure and return times, the parents' share of the food costs (CHF 16.- a day, CHF 80.-, due within 30 days, waived on request), the reply slip (Talon) due 23 April with allergies and medication, a packing list of seven items, the camp phone, the information evening of 20 April at 19.30, the secretariat's hours and contact | Letters of a sender that is no authority (docs/use-cases.md §8), tests, an example text in the New draft form |
| `camp-de-classe-lettre-parents.txt` | The same letter in French: the camp de classe of the Établissement primaire d'Exempleville at the chalet Le Soleil, 1899 Montexemple, with the coupon-réponse | As above |
| `settimana-verde-lettera-genitori.txt` | The same letter in Italian: the settimana verde of the Scuola elementare di Esempiopoli at the Casa alpina Il Sole, 6799 Montesempio, with the tagliando; the parents are addressed with voi, as Ticino does | As above |
| `schnupperwoche-schuelerbrief.txt` | School letter to students, in the du form (30 October 2026): the Schnupperwoche of the invented Sekundarschule Musterwil, 15 to 19 March 2027: the student finds a trial apprenticeship, the employer's confirmation is due 19 February, who to tell by 5 February without a place, the BIZ's address (Bahnhofstrasse 10, 9999 Musterwil) and hours, the employer's working hours, a sick call by 7.30, a medical certificate after 2 days, travel costs up to CHF 30.- a week, insurance, the report due within two weeks (2 April), contacts | As above |
| `semaine-de-stage-lettre-eleves.txt` | The same letter in French, in the tu form: the semaine de stage of the Établissement secondaire d'Exempleville (10e année), the office d'orientation at Rue de la Gare 10, 1999 Exempleville | As above |
| `settimana-di-stage-lettera-allievi.txt` | The same letter in Italian, in the tu form: the settimana di stage of the Scuola media di Esempiopoli (quarta media), the Ufficio dell'orientamento at Via della Stazione 10, 6899 Esempiopoli | As above |

A JSON file next to a letter holds that example's job settings, any `JobConfig` field:
`entscheid-beistandschaft-musterwil.json` runs the KESB decision in decision mode
(`mode`), speaking to Lea Muster (`addressee`), with the KESB's fixed notice (`notice`).
Letters without one run as standard P2 jobs at level A2. Since 29 October 2026 every
JSON names the letter's `region` (CH, DE or AT): an installation offers the letters of
its region and the French and Italian ones (docs/architecture.md §7).

The six school letters are the first examples of a sender that is no authority. They
run as standard jobs. The camp letter follows the usual shape of a Swiss Elternbrief: a
compulsory school event, the parents' share limited to the food costs (as the Federal
Supreme Court ruled in 2017), the Talon to sign and return, the packing list. The
Schnupperwoche letter speaks to the student in the du form, as Swiss lower secondary
schools do, and the French and Italian versions in the tu form. The prompts still call
the source an official document and the German and French rules expect Sie and vous
(docs/use-cases.md §8).

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
