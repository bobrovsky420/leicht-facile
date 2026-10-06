# Sources: reference pairs and demo documents

Status: research, 5 October 2026. Companion to [architecture.md](architecture.md)
(§9 evaluation) and [rules.md](rules.md). Facts about third-party pages were checked on
5 October 2026 and can change; re-check before quoting them in the report or video.

## 1. Two kinds of sources

| Kind | What it is | Used for |
|------|------------|----------|
| **Reference pairs** | A standard-language text for which the publisher also offers an official, professionally written easy-language version | Evaluation (SARI, readability, fact coverage against a human reference) and checker calibration |
| **Demo documents** | Texts with no easy-language version yet | The live demo and the video: the tool fills a real gap instead of redoing work that already exists |

Reference pairs are not the same as the golden tests in [rules.md](rules.md). Golden
tests are single sentences for individual checker rules; reference pairs are whole
documents.

Rules for using reference pairs:

- **Evaluation:** our draft is scored against the official easy version (SARI,
  readability, fact coverage). Conditions P0, P1 and P2 run on the same pairs.
- **Checker calibration:** official easy-language pages are written by professionals,
  so the checker should raise almost no `error` findings on them. Every error is either
  a genuine deviation or a false positive to fix. The rate is recorded in
  [rules.md](rules.md) as the false-positive baseline.
- **No leakage:** the few-shot examples in the writer prompt
  (`llm/prompts/<lang>/examples/`) are written by the team, so no pair is used as an
  example. The manifest splits the pairs into `dev` (prompt development and checker
  calibration) and `eval` (held out for the final numbers).

## 2. Reference pairs

### Shortlist

| Id (proposed) | Publisher | Topic | Standard version | Easy version | Notes |
|---------------|-----------|-------|------------------|--------------|-------|
| `be-tax-extension-de` | Canton Bern, tax administration | Extending the tax-return deadline | [Frist als Privatperson verlängern](https://www.sv.fin.be.ch/de/start/themen/frist-verlaengern/fristverlaengerung-privatpersonen.html), about 1,200 words | [Steuern in Leichter Sprache](https://www.sv.fin.be.ch/de/start/leichte-sprache/steuern.html), several tabs | Dense, checkable facts: extension to 15 July, 15 September or 15 November for CHF 20, 40 or 60 (cheaper online), late fee CHF 60, phone number, office hours. The easy page covers all of taxes; the comparison uses the section on extensions. |
| `be-tax-extension-fr` | Canton Bern, tax administration | Same topic in French | French counterpart of the standard page | [Impôts en langage facile](https://www.sv.fin.be.ch/fr/start/leichte-sprache/steuern.html), about 3,500 words | Same fees as the German pages. One topic in two languages from one publisher: the cheapest way to show French. |
| `sg-el-costs-de` | St. Gallen social insurance office (SVA) | Refund of illness and disability costs for recipients of supplementary benefits | [Merkblatt 5100](https://www.svasg.ch/de/online-schalter/pdf/form_5100.pdf), PDF, 2 pages, about 1,100 words | [Merkblatt 5100 in Leichter Sprache](https://www.svasg.ch/online-schalter/pdf/form_5100_leichte-sprache.pdf), PDF, 17 pages, about 2,200 words | The PDF pair. About 15 CHF amounts, a 15-month deadline, phone numbers. The easy version links back to the standard one. |
| `zh-premium-reduction-de` | Canton Zürich, health directorate | Health insurance premium reduction | [Prämienverbilligung](https://www.zh.ch/de/gesundheit/praemienverbilligung_krankenversicherung.html), about 2,000-2,500 words | [Prämien·verbilligung in Leichter Sprache](https://www.zh.ch/de-ls/gesundheit/praemienverbilligung_krankenversicherung.html), about 1,100 words | The scenario of [use-case-canton.md](use-case-canton.md). Deadline 31 March of the following year, phone numbers, e-mail addresses, address. |
| `bag-health-insurance-de` | Federal Office of Public Health (BAG) | Mandatory health insurance | Standard BAG pages on health insurance (to be selected) | [Die Kranken·versicherung in Leichter Sprache](https://www.bag.admin.ch/de/die-kranken-versicherung-in-leichter-sprache), about 800 words | Written by the Kompetenzzentrum Leichte Sprache. Facts: cancellation by 30 November, franchise examples, 10 percent copay, priminfo.ch. Covers the insurance topic without a private insurer's text. The page links no single standard counterpart. |

### The manifest

`data/pairs/manifest.jsonl` holds 35 pairs, each URL checked on 5 October 2026 (HTTP
200, no redirect, real content): 30 German (20 `eval`, 10 `dev`) and 5 French (3
`eval`, 2 `dev`). Publishers: Zürich 13, Bern 8 (6 German, 2 French), St. Gallen 3,
Luzern 2, Basel-Stadt, Graubünden and Zug 1 each, the federal offices BAG, BWL (German
and French) and EBGB, and Geneva and Neuchâtel (French). Each row carries approximate
word counts and a rough count of checkable facts in the standard text.

Corrections to the shortlist above, from building the manifest:

- `be-tax-extension-de`: the standard page has about 420 words, not 1,200, and no
  phone number or office hours; those are on the easy page's "Hilfe" tab. The Bern
  easy pages put all sub-headings at the same level, so the easy section is the whole
  "Steuer-Erklärung" tab (about 700 words), not only the part on extensions.
- `be-tax-extension-fr`: the French easy tax page has about 2,400 words, not 3,500.
- `zh-premium-reduction-de`: about 900 and 420 words, not 2,000-2,500 and 1,100. The
  31 March deadline and the phone numbers are on the easy page only.
- `bag-health-insurance-de`: the easy page has about 500-580 words, not 800; the
  standard counterpart is chosen by hand (premiums and cost sharing) and matches only
  in part.

### Pools for the rest of the set

| Pool | Size | How to pair | Notes |
|------|------|-------------|-------|
| Zürich | About 27 easy-language pages, listed in the [overview](https://www.zh.ch/de-ls/inhalte-in-leichter-sprache.html) | The easy path `/de-ls/...` mirrors the standard path `/de/...` | Health, disability, elections, victim support, passports. Pairing can be largely automatic. |
| Bern | About 60 topics in the [A-Z list](https://www.be.ch/de/start/leichte-sprache/inhalte.html?tab=abisz), spread over department subdomains | Each easy page has a "Zur Standardsprache" link, often only to the department's start page; pair by hand | Many pages are short (150-200 words) and carry no facts, for example marriage. Prefer pages with deadlines, amounts and contacts. Many pages also exist in French. |
| St. Gallen | A [list of documents](https://www.sg.ch/gesundheit-soziales/soziales-in-leichter-sprache/behinderung-in-leichter-sprache/teilhabe-und-barrierefreiheit-in-leichter-sprache/informationen-in-leichter-sprache.html), mostly reports | Pair by title | Reports are long and fact-poor; the SVA sheet above is the best item. |
| Vaud (French) | The FALC adaptation of the welcome brochure, published 12 February 2026 | Standard version on Issuu, FALC version on [vaud-bienvenue.ch](https://www.vaud-bienvenue.ch/brochures) | The standard brochure has 110 pages: use selected chapters only. |
| Ticino (Italian) | Voting and election information in lingua facile; no paired page identified yet | - | Italian stays a stretch goal. |

## 3. Demo documents (no easy-language version)

| Candidate | Why it is strong | Caveats |
|-----------|------------------|---------|
| **Explanations of the Federal Council for a past federal vote** (main demo). Candidates: the premium relief initiative of 9 June 2024 (premiums capped at 10 percent of income; same vocabulary as the Zürich and BAG pairs), or subletting in tenancy law of 24 November 2024 (letter-like rules, shortest text). Avoid the 13th AHV pension (3 March 2024): its financing is on the ballot of 29 November 2026 | They go to every voter. A motion to require easy language failed in the National Council ([Année politique](https://anneepolitique.swiss/fr/prozesse/60222-leichte-sprache-in-den-abstimmungserlauterungen.pdf)), so the gap is documented. Article 11 of the federal act on political rights requires them to be brief, factual and to include the views of significant minorities. That gives the judge a meaning check code cannot do: are the arguments of both sides kept, and is the draft still neutral? | Use a vote that is already over, so the demo never looks like campaigning. Copyright status to confirm (§4). |
| **Fact sheet of the Federal Office of Communications on exemptions from the radio and TV fee** ([PDF](https://www.Bakom.admin.ch/dam/bakom/de/dokumente/Elektronische%20Medien/empfangsgeb%C3%BChren/faktenblatt-4-befreiung.pdf.download.pdf/FB4%20Befreiungen%20und%20Opting%20out.pdf)) | Short, letter-like, full of conditions and deadlines: exemption on request, at most five years back and not before 2019. It reaches exactly the readers easy language is for: recipients of supplementary benefits and deafblind people. | Reuse terms of admin.ch apply (§4): show it in the demo, do not commit the text without clarification. |
| **A blank decision or ordinance from a canton without an easy-language section** | Letters and decisions are the core use case. Decisions and ordinances are free of copyright (§4). | Only blank templates or published ordinances, never a real decision with personal data. To be selected. |
| **A published, anonymised decision**: a cantonal court on an appeal against a KESB decision, or the Federal Supreme Court on disability insurance | The second use case ([use-case-decisions.md](use-case-decisions.md)): long legal reasoning, an operative part and appeal instructions with exact periods. Decisions of authorities are free of copyright (§4), so the text and our output may be committed and shown. | Published decisions replace names with placeholders (`A.________`); in practice the letter for the person concerned is made from the decision before anonymisation, inside the authority. To be selected. |
| **A KESB decision written by the team**: a deputyship for an invented person | Shows what may never leave the authority: name, address, case number, an AHV number, the 30-day appeal period. Team-written, so free to commit and show. | Specimen identifiers only (for example with a wrong check digit), never a number that could belong to a real person. Check its structure against published decisions so that it reads like a real one. |

### Private institutions

Insurers, pension funds and utilities are a real market: their terms and letters are
among the least readable texts people receive. They are not used as demo sources:

- their texts are protected by copyright, and rewriting a real insurer's documents in a
  public video needs that insurer's consent;
- a private company's document weakens the sovereignty story the judges score.

They appear in the technical report as a market (value and next steps). The insurance
topic is covered in the evaluation by the BAG pair above.

## 4. Licensing

| Source | Terms | Consequence |
|--------|-------|-------------|
| Swiss Copyright Act, [article 5](https://www.droit-bilingue.ch/en-de/2/23/231.1-5-8.html) | Laws, ordinances, other official enactments, and decisions, minutes and reports of authorities are not protected | Such texts can be committed, published in a dataset and shown freely |
| [zh.ch](https://www.zh.ch/de/nutzungshinweise.html) | Viewing, download and printing for personal use only; any further use needs consent | Manifest and fetch script only; no texts in the repository or dataset |
| [be.ch](https://www.be.ch/de/tools/rechtliches.html) | Written consent required in advance for any reproduction | Same as Zürich. Bern is a hackathon partner: ask for consent if we want to publish the dataset. |
| [admin.ch](https://www.admin.ch/de/rechtliches) | Rights reserved by the federal authorities | Web pages and fact sheets: manifest only unless article 5 clearly applies |
| [sg.ch](https://www.sg.ch/content/dam/sgch/kanton-stgallen/personalhandbuch/Legal_Disclaimer.pdf) | Reuse with full attribution for private use; other use needs written permission | Same as Zürich |
| [ahv-iv.ch](https://www.ahv-iv.ch/de/Merkblätter) | Even partial reprints need written consent of the Informationsstelle AHV/IV | Not used |
| Federal voting explanations | Three layers (research of 5 October 2026, not legal advice). The bill text is an enactment (article 5 para. 1a): free. The Federal Council's own parts ("In Kürze", "Im Detail", the Federal Council's arguments) are very likely a report of an authority (para. 1c): legally required, a government act, published to reach everybody. The committees' argument pages (about 2,500 characters each) are written by the committees: treat them as third-party text. Infographics and photos may be protected separately. The admin.ch notice asks for consent for any reproduction, but a website notice cannot create copyright in a text article 5 excludes; the booklets themselves carry no reuse note. | Federal Council parts and bill text can be used in the video, as fixtures and in a dataset, with the source named. Committee pages: short quotes only, unless the committee consents. No images. A written confirmation from the Federal Chancellery is optional and need not be awaited. |

None of the sources above uses an open licence such as CC BY.

### Development and evaluation: no consent needed

Developing, testing and evaluating against these pages needs no consent from the
publishers, as long as neither the texts nor our rewrites of them are published.
Our reading of the Copyright Act (not legal advice):

- The repository contains only URLs. Linking to a public page is not reproduction.
- The application fetches a page when a user, including a judge, submits it. The copy
  on that machine is temporary and technically required (article 24a).
- Evaluation runs on locally cached copies (`data/cache/`, git-ignored) for scientific
  research, with lawful access to the pages (article 24d).
- Showing a draft to the jury on their own machine is not publication.

### Where consent would be needed

Anything public needs either consent or an article-5 text:

| Artifact | Rule |
|----------|------|
| Demo video | Article-5 texts as the main material. Protected pages only as short excerpts that illustrate how the tool works (quotation right, article 25). |
| Example jobs in `data/examples/` | Article-5 texts or synthetic letters written by the team, since the repository is public. |
| Test fixtures in `tests/fixtures/` | Article-5 texts or synthetic letters, including recorded model outputs. |
| Technical report | Metrics and tables freely; short quoted excerpts with the source named. |
| Hugging Face dataset (plan decision D-G) | Manifest, metrics, and article-5 texts with our outputs on them. Our rewrites of protected pages are adaptations and stay out unless the publisher consents. |

A practical risk comes with live fetching: judging happens after the deadline, and
pages can change, move or go offline. The application reports a failed fetch clearly,
and the article-5 example jobs serve as the fallback.

### Hugging Face dataset (optional, decision D-G)

What the hackathon asks for (template `HackApertus/online_hack_template` and the terms
and conditions §6, checked on 5 October 2026):

- Three components: test cases, the model's response to each case, and a metadata file
  with the licence of every single item. File names and formats are free; three JSONL
  files joined on `id` work.
- The dataset is licensed under CDLA-Permissive-2.0, irrevocably from submission, and
  must be public (the template is gated: remove the gate).
- Only data the team created or has the right to publish. Data from human subjects
  would need a consent form; ours has none, and no personal data.
- The card has many sections (curation, sources, consent, personal data, risks); a
  card with placeholders scores zero in the Track 1B rubric, so every section must be
  filled.

What ours would contain: the manifest (URLs and metrics only for protected pages), the
team-written texts and article-5 texts with our outputs on them, and per item the
licence basis (`team-written`, `URG art. 5`, or `URL only`).

## 5. Findings that affect the design

- **Phone numbers and times on official pages.** The Zürich easy-language pages
  write phone numbers with `+41` (`+41 44 448 53 75`); the Bern easy pages write them
  nationally (`031 633 60 01`). Times appear as `von 8 Uhr bis 12 Uhr` (Bern) and
  `08.00 bis 11.45` (Zürich). Rules NUM-04 and NUM-08 are calibrated against these
  pages; the result is in [rules.md](rules.md).
- **Contact cards on cantonal pages.** zh.ch, sg.ch and zg.ch put phone numbers,
  e-mail addresses and opening hours into contact cards, and the Bern police pages put
  the emergency numbers into a table. Main-content extraction must keep them, or the
  fact measures on those pairs are wrong.
- **Voting booklets.** The booklets use margin headings that plain text extraction
  interleaves with the body text, and some bill-text pages extract badly. Crop the
  margin column, and take bill texts from Fedlex instead.
- **Two-column PDFs.** Both St. Gallen PDFs use two columns; the easy version puts the
  glossary in a side column. Plain text extraction interleaves the columns line by
  line. PDF ingest assigns the words to columns by the gutter and reads the main
  column first, then the glossary column.
- **Separator characters in compounds.** The St. Gallen easy-language PDF separates
  compounds with a special character (`Merk·blatt`, `Ergänzungs·leistungen`) that may
  come out as a different code point after extraction. Ingest normalises it to the
  Mediopunkt so that LEX-01 and the readability counts work.
- **Fact density varies a lot.** Many easy-language pages contain no deadlines or
  amounts. Fact coverage is only meaningful on pages that have such facts; the
  manifest records a rough fact count per pair so the evaluation can report coverage
  on the fact-rich subset separately.
- **Time-sensitive facts.** The Bern standard page carried a notice on 5 October 2026
  that the filing deadline moves to 30 November 2026 because of system maintenance.
  Such notices may be missing from the easy version. Fetched texts are stored with
  `fetched_at`, and the evaluation uses the cached copy, not the live page.
