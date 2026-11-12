# leichtfacile-samples

The sample letters of [Leicht·Facile](https://leichtfacile.ch) and the recorded runs its
web app answers them from: data alone, apart from the app's code. The app
(`leichtfacile`) depends on this package and reads it; it is not meant to be used on
its own. In the repository it lives in
[`samples/`](https://github.com/bobrovsky420/leicht-facile/tree/main/samples), a member
of the uv workspace, so a checkout has it installed with `uv sync`.

The package has a version of its own, so new letters and recorded runs reach the
installations without a release of the app: the app depends on every release of one
major version (`leichtfacile-samples>=0.5,<1`). A new letter or recording is a minor
version, a correction a patch; the major version changes when the app needs a change to
read the package (a new field in a letter's `.json`, another format of a recording), and
the app that reads it then names the new major version. The workflow `samples.yml`
publishes it to PyPI, by hand after a change of `samples/` and its version.

## The letters (`leichtfacile_samples/letters/`)

The letters in `leichtfacile_samples/letters/` are written by the team for testing and
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
| `praemienverbilligung-brief.txt` | Letter about health insurance premium reduction: income limits, a deadline, documents to enclose, objection period, contact | The smoke run (`uv run leichtfacile simplify samples/leichtfacile_samples/letters/praemienverbilligung-brief.txt --out out/smoke`), tests, an example text in the New draft form |
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
its region and the French and Italian ones (docs/architecture.md §7). The school
letters' JSON names the school as the sender (`sender`), and the three letters to
students the du form (`address: informal`), the two options of 31 October 2026
(docs/architecture.md §4.3); the New draft form's selects follow the sidecar.

The six school letters are the first examples of a sender that is no authority. They
run as standard jobs. The camp letter follows the usual shape of a Swiss Elternbrief: a
compulsory school event, the parents' share limited to the food costs (as the Federal
Supreme Court ruled in 2017), the Talon to sign and return, the packing list. The
Schnupperwoche letter speaks to the student in the du form, as Swiss lower secondary
schools do, and the French and Italian versions in the tu form (docs/use-cases.md §8).

The KESB decision follows the layout of real ones: the header with the panel, the
person and the subject, then I. Sachverhalt, II. Erwägungen, III. Entscheid and the
Rechtsmittelbelehrung, as in the two specimen decisions in the annex of the KESB
Graubünden's guide to deputyships (*Leitfaden Mandatsführung und Vermögensverwaltung*)
and the KOKES model decision; the operative items and the appeal clause use their
wording. The AHV number has a wrong check digit and the IBAN the check digits 00, so
neither can belong to anyone. The people, the street, the bank and the doctor are
invented.

`data.examples_dir` points the app at another folder of letters instead (`leichtfacile
config set data.examples_dir <folder>`,
[configuration.md](https://github.com/bobrovsky420/leicht-facile/blob/main/docs/configuration.md)):
`.txt` or `.md` files, each with an optional `.json` of job settings next to it. The
default is this package's folder (`LETTERS` in `leichtfacile_samples/__init__.py`).

## The recorded runs (`leichtfacile_samples/recordings/`)

Version 0.6.1 holds the runs of the preset `huggingface-gpt-oss-120b-groq` (gpt-oss-120b
on the Hugging Face router) for 8 of the 12 letters: the premium-reduction letter in
German, French and Italian and five of the six school letters, recorded on 8 November
2026; the German premium-reduction letter, the Schnupperwoche letter and the two Italian
school letters again on 12 November 2026, after a change of the app's prompts had made
them stale. The KESB decision and the Bescheide of Germany and Austria had no clean run in
six attempts, and the French camp letter always one finding left (a link the judge
missed); these four run live. One recorded run per letter and preset,
`recordings/<preset>/<letter>.json`, so that a first visitor sees a sample letter go through the pipeline in seconds instead of
minutes, and at no cost. A recording holds the model's answers in call order, each
keyed by the hash the response cache uses (the model, the messages and the request's
parameters), with its stage, model, token counts and latency; it holds neither the
prompts nor the reasoning. Beside them: the preset, its models, the date, the app's
version, the endpoint's host, the model time of the run and its result (the final
version, its errors, warnings and facts).

The web app answers a job's first run from these answers when a prompt is byte for
byte a recorded one: a sample letter sent unchanged from the New draft form at level A2,
on the preset it was recorded with, in an installation with the default settings. Every
other prompt goes to the model: an edited letter, another level or preset, a step run
again, a changed prompt of a newer version. The job page and the review page say when
a draft's answers were recorded. The command line (the smoke run among it) and the
evaluation never read the recordings. A replayed call counts as cached, with no model
time.

`uv run python scripts/record_samples.py` records them, with the preset's key from the
environment or the repository's `.env` (it reads no other setting of the checkout):
each letter runs as the New draft form sends it, a few attempts at a time until one
reaches review clean (no error, nothing that blocks publication, every fact kept), and
the clean run with the fewest warnings is written. A letter without a clean run keeps
the recording it has. `--check` replays every recording without an endpoint and names
those a changed prompt has made stale; `samples.yml` replays them all on the app of the
commit it publishes from and fails on a stale one (tests/test_samples.py). A recording
made for one version of the app replays on the later ones as long as their prompts stay
the same; after a change of a prompt the letter runs live until it is recorded again.
