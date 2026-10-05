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
  readability, fact coverage). Conditions C0, C1 and C2 run on the same pairs.
- **Checker calibration:** official easy-language pages are written by professionals,
  so the checker should raise almost no `error` findings on them. Every error is either
  a genuine deviation or a false positive to fix. The rate is recorded in
  [rules.md](rules.md) as the false-positive baseline.
- **No leakage:** a pair used as a few-shot example in the writer prompt
  (`llm/prompts/<lang>/examples/`) is excluded from the evaluation set. The manifest
  marks it with `role: example`.

## 2. Reference pairs

### Shortlist

| Id (proposed) | Publisher | Topic | Standard version | Easy version | Notes |
|---------------|-----------|-------|------------------|--------------|-------|
| `be-tax-extension-de` | Canton Bern, tax administration | Extending the tax-return deadline | [Frist als Privatperson verlängern](https://www.sv.fin.be.ch/de/start/themen/frist-verlaengern/fristverlaengerung-privatpersonen.html), about 1,200 words | [Steuern in Leichter Sprache](https://www.sv.fin.be.ch/de/start/leichte-sprache/steuern.html), several tabs | Dense, checkable facts: extension to 15 July, 15 September or 15 November for CHF 20, 40 or 60 (cheaper online), late fee CHF 60, phone number, office hours. The easy page covers all of taxes; the comparison uses the section on extensions. |
| `be-tax-extension-fr` | Canton Bern, tax administration | Same topic in French | French counterpart of the standard page | [Impôts en langage facile](https://www.sv.fin.be.ch/fr/start/leichte-sprache/steuern.html), about 3,500 words | Same fees as the German pages. One topic in two languages from one publisher: the cheapest way to show French. |
| `sg-el-costs-de` | St. Gallen social insurance office (SVA) | Refund of illness and disability costs for recipients of supplementary benefits | [Merkblatt 5100](https://www.svasg.ch/de/online-schalter/pdf/form_5100.pdf), PDF, 2 pages, about 1,100 words | [Merkblatt 5100 in Leichter Sprache](https://www.svasg.ch/online-schalter/pdf/form_5100_leichte-sprache.pdf), PDF, 17 pages, about 2,200 words | The PDF pair. About 15 CHF amounts, a 15-month deadline, phone numbers. The easy version links back to the standard one. |
| `zh-premium-reduction-de` | Canton Zürich, health directorate | Health insurance premium reduction | [Prämienverbilligung](https://www.zh.ch/de/gesundheit/praemienverbilligung_krankenversicherung.html), about 2,000-2,500 words | [Prämien·verbilligung in Leichter Sprache](https://www.zh.ch/de-ls/gesundheit/praemienverbilligung_krankenversicherung.html), about 1,100 words | The scenario of [use-case-canton.md](use-case-canton.md). Deadline 31 March of the following year, phone numbers, e-mail addresses, address. |
| `bag-health-insurance-de` | Federal Office of Public Health (BAG) | Mandatory health insurance | Standard BAG pages on health insurance (to be selected) | [Die Kranken·versicherung in Leichter Sprache](https://www.bag.admin.ch/de/die-kranken-versicherung-in-leichter-sprache), about 800 words | Written by the Kompetenzzentrum Leichte Sprache. Facts: cancellation by 30 November, franchise examples, 10 percent copay, priminfo.ch. Covers the insurance topic without a private insurer's text. The page links no single standard counterpart. |

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
| **Explanations of the Federal Council for a past federal vote** (main demo) | They go to every voter. A motion to require easy language failed in the National Council ([Année politique](https://anneepolitique.swiss/fr/prozesse/60222-leichte-sprache-in-den-abstimmungserlauterungen.pdf)), so the gap is documented. Article 11 of the federal act on political rights requires them to be brief, factual and to include the views of significant minorities. That gives the judge a meaning check code cannot do: are the arguments of both sides kept, and is the draft still neutral? | Use a vote that is already over, so the demo never looks like campaigning. Copyright status to confirm (§4). |
| **Fact sheet of the Federal Office of Communications on exemptions from the radio and TV fee** ([PDF](https://www.Bakom.admin.ch/dam/bakom/de/dokumente/Elektronische%20Medien/empfangsgeb%C3%BChren/faktenblatt-4-befreiung.pdf.download.pdf/FB4%20Befreiungen%20und%20Opting%20out.pdf)) | Short, letter-like, full of conditions and deadlines: exemption on request, at most five years back and not before 2019. It reaches exactly the readers easy language is for: recipients of supplementary benefits and deafblind people. | Reuse terms of admin.ch apply (§4): show it in the demo, do not commit the text without clarification. |
| **A blank decision or ordinance from a canton without an easy-language section** | Letters and decisions are the core use case. Decisions and ordinances are free of copyright (§4). | Only blank templates or published ordinances, never a real decision with personal data. To be selected. |

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
| [ahv-iv.ch](https://www.ahv-iv.ch/de/Merkblätter) | Even partial reprints need written consent of the Informationsstelle AHV/IV | Not used |
| Federal voting explanations | Plausibly a report of an authority under article 5, not confirmed | Confirm before committing the text or publishing it in a dataset |

Consequence for the optional Hugging Face dataset (plan decision D-G): without consent
from the publishers, the dataset can contain only the manifest, our model outputs and
metrics, plus article-5 texts. The report states this.

## 5. Findings that affect the design

- **Phone numbers with +41 on official pages.** The easy-language pages of Zürich and
  Bern write phone numbers as `+41 44 448 53 75`. Rule NUM-08 in [rules.md](rules.md)
  flags that format as `warn`, so it would fire on professional texts. To decide when
  the checker is calibrated (WP5): accept the international format, or lower NUM-08 to
  `info`. Time formats on the same pages (`08:00-12:00`) should be verified against
  NUM-04 the same way.
- **Two-column PDFs.** Both St. Gallen PDFs use two columns; the easy version puts the
  glossary in a side column. Plain text extraction interleaves the columns line by
  line. PDF ingest needs column-aware extraction (crop by column with pdfplumber
  before extracting).
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
