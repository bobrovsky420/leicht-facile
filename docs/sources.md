# Sources: reference pairs and demo documents

Status: research, 5 October 2026. Companion to [architecture.md](architecture.md)
(§9 evaluation) and [rules.md](rules.md). Facts about third-party pages were checked on
5 October 2026 and can change; re-check before quoting them.

## 1. Two kinds of sources

| Kind | What it is | Used for |
|------|------------|----------|
| **Reference pairs** | A standard-language text for which the publisher also offers an official, professionally written easy-language version | Evaluation (SARI, readability, fact coverage against a human reference) and checker calibration |
| **Demo documents** | Texts with no easy-language version yet | Demos: the tool fills a real gap instead of redoing work that already exists |

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
  (`llm/prompts/<key>/examples/`, one folder per variety) are written by the team, so no
  pair is used as an
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

`data/pairs/manifest.jsonl` holds 73 pairs, each URL checked on 5 October 2026 (HTTP
200, no redirect, real content; the Italian rows on 28 October 2026): 30 German (20
`eval`, 10 `dev`), 5 French (3 `eval`, 2 `dev`) and 14 Italian (9 `eval`, 5 `dev`)
from Switzerland, plus 12 German from Germany (`"region": "DE"`, 8 `eval`, 4 `dev`)
and 12 German from Austria (`"region": "AT"`, 8 `eval`, 4 `dev`), checked on
29 October 2026. Rows without `region` are Swiss. The German and Austrian publishers are
listed under [Germany](#germany) and [Austria](#austria) below.
Swiss publishers: Zürich 13, Bern 8 (6 German, 2 French), Ticino 8 (Italian), St. Gallen 3,
Luzern 2, Basel-Stadt, Graubünden and Zug 1 each, the federal offices BAG (1 German, 4
Italian), BWL (German and French) and EBGB (German and Italian, the Italian standard
being the Federal Council's press release on admin.ch), eHealth Suisse (Italian, with
the Confederation and the cantons), and Geneva and Neuchâtel (French). Each row carries
approximate word counts and a rough count of checkable facts in the standard text.

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
| Ticino (Italian) | 24 pages in lingua facile of the Divisione dell'azione sociale e delle famiglie (DASF), listed on its [introduzione](https://www4.ti.ch/dss/dasf/lingua-facile/introduzione); written with Pro Infirmis and checked by a reader group | Each easy page links its standard page under `/dss/dasf/temi/...` ("Consulta la pagina completa"); some easy pages combine two to eight standard pages, so pair those by section | Social topics (families, disability, elderly, social assistance, victim support). FAQ-style standard pages with contact boxes that the ingest keeps; amounts written `700 fr.`, phones with `+41`. `www4.ti.ch` stalls intermittently (a fetch times out after 30 s, the retry succeeds). Eight pairs in the manifest. The federal Italian pool is the [CCLF list](https://www.edi.admin.ch/it/informazioni-in-lingua-facile-cclf) (14 texts) plus the 14 BAG texts under [Informazioni in lingua facile](https://www.bag.admin.ch/it/informazioni-in-lingua-facile); the standard counterparts are chosen by hand, and BWL and MeteoSvizzera have no usable Italian standard page. |

### Germany

Twelve pairs, checked on 29 October 2026, all in Leichte Sprache and recorded as A2 like
the Swiss rows; no German page claims a CEFR level. `canton` holds the state or city
(`Bund` for federal publishers).

| Id | Publisher | Topic | Why |
|----|-----------|-------|-----|
| `ba-insolvency-pay-de` | Bundesagentur für Arbeit | Insolvenzgeld | Section-by-section match; a 2-month deadline and a dated example |
| `ba-short-time-work-de` (dev) | Bundesagentur für Arbeit | Kurzarbeitergeld | Good match, but the ingest drops some of the easy page's lists |
| `drv-contribution-refund-de` | Deutsche Rentenversicherung Bund | Beitragserstattung | The easy page names the brochure (PDF, 2,420 words) as its standard; about 25 facts |
| `bmbfsfj-parental-allowance-de` | BMBFSFJ, with familienportal.de | Elterngeld | Easy text by capito Berlin, checked by 4 readers; the amounts are on the standard only |
| `koeln-parental-allowance-de` | Stadt Köln | Elterngeld | Mirror pages with income limits and the same contact block |
| `koeln-housing-benefit-de` | Stadt Köln | Wohngeld | Mirror pages |
| `koeln-identity-card-de` | Stadt Köln | Personalausweis | Mirror pages; fees 27,60 and 46 Euro on both |
| `koeln-residence-registration-de` (dev) | Stadt Köln | Anmeldung des Wohnsitzes | Mirror pages, few facts |
| `muenchen-city-pass-de` | Landeshauptstadt München | München-Pass | Inclusion Europe rules and a reader group; income limits on the standard only |
| `muenchen-certificate-of-conduct-de` | Landeshauptstadt München | Führungszeugnis | Same structure; the ingest drops the standard's cost block |
| `stmb-housing-benefit-de` (dev) | Bayern, Staatsministerium für Wohnen, Bau und Verkehr | Wohngeld | Close match, few facts |
| `nuernberg-housing-benefit-de` (dev) | Stadt Nürnberg | Wohngeld | The one Mediopunkt page; about 1,000 words of generic help |

Rejected: DRV Grundrente and Reha-Zuzahlung (easy sections of 240 and 130 words, the
second with an outdated threshold), BA Grundsicherungsgeld and "arbeitslos werden" (no
single standard page), the Familienportal Elterngeld hub (the ingest returns only the
cookie notice), the Bundeswahlleiterin (partial overlap), Hamburg (easy pages of 200-250
words, one machine-translated and unchecked), DGUV (30-300 words), service.berlin.de
`de_plain` (not Leichte Sprache), BMG, BMAS and Sachsen (no parallel topic pages), and
the Baden-Württemberg Sozialministerium (easy URL 404).

| Pool | Size | How to pair | Notes |
|------|------|-------------|-------|
| Köln | 17 easy categories in the [overview](https://www.stadt-koeln.de/service/leichte-sprache/), for example 10 articles under "Anmelden und Ummelden" | Each standard service page links its easy version (`/service/leichte-sprache/<slug>`) | Fees, opening hours, phones; pairing can be automatic. Four pairs in the manifest. |
| München | 34 easy service pages in the [list](https://stadt.muenchen.de/leichte-sprache/dienst-leistungen.html) | The easy page links the standard `/service/info/.../n0/` page, sometimes through a 301 | Inclusion Europe rules plus a reader group; the ingest drops the standard pages' "Dauer und Kosten" block. Two pairs. |
| Bundesagentur für Arbeit | 4 topic pages | By hand | Two pairs. |
| Deutsche Rentenversicherung | 7 areas and 3 easy brochures | By hand; some sections link a "Seite in schwerer Sprache" | Long easy pages over several topics; some easy figures are outdated. One pair. |
| Bayern, Nürnberg, Hannover | StMB Wohngeld; StMAS PDFs on einfach-finden.bayern.de; Nürnberg and Hannover not counted | By hand; Nürnberg's standard page links the easy one | The Bayern UVG PDFs have no standard text of similar length. Nürnberg and Hannover use a Mediopunkt. Two pairs. |
| Hamburg | 13 categories; many items link an "Originaltext" | The Originaltext link | 200-250 words per page; some pages say a computer translated them and nobody checked them, so they are not references. |

Terms (none uses an open licence, so every row is manifest only):
[arbeitsagentur.de](https://www.arbeitsagentur.de/impressum) free to read, reproduction
needs the BA's prior permission;
[deutsche-rentenversicherung.de](https://www.deutsche-rentenversicherung.de/DRV/DE/Service/Footer/Impressum/impressum_node.html)
any use needs prior written consent;
[bmbfsfj.bund.de](https://www.bmbfsfj.bund.de/bmbfsfj/impressum-99480) and
[familienportal.de](https://familienportal.de/familienportal/meta/impressum) the
ministry's written consent;
[stadt-koeln.de](https://www.stadt-koeln.de/service/kontakt/impressum/hinweise-zum-urheberrecht)
prior written permission, no commercial use;
[stadt.muenchen.de](https://stadt.muenchen.de/infos/impressum.html) and
[stmb.bayern.de](https://www.stmb.bayern.de/hil/impressum/index.php) private use under
§ 53 UrhG, other publication needs consent;
[nuernberg.de](https://www.nuernberg.de/internet/sozialamt_nbg/impressum.html) no reuse
clause.

#### What the German pages write

- **Compounds:** the hyphen with a capital second part on almost every page
  ("Insolvenz-Geld", "Personal-Ausweis", "Sozial-Bürger-Haus"); the DRV sometimes writes
  lower case after the hyphen ("Renten-auskunft"). Nürnberg uses the Mediopunkt U+00B7
  with lower case after it and keeps the hyphen where standard spelling has one
  ("Wohn·geld-Plus"), the combination DIN SPEC 33429:2025 (5.2.9) allows; Hannover uses
  U+2219 ("Wohn∙geld"), which the ingest turns into U+00B7.
- **Money:** "Euro" written out, thousands with a dot: "1.700 Euro" (BA), "27,60 Euro"
  (Köln). The euro sign appears only on a standard page.
- **Times:** "8 bis 12:30 Uhr" (Köln), "8:00 Uhr bis 18:00 Uhr" (Bundeswahlleiterin), "von
  8 Uhr morgens bis 16 Uhr nachmittags" and "8.30 Uhr" (München): no common style.
- **Dates and ordinals:** "13. März", "1. April 2025"; digit ordinals on easy pages
  ("65. Geburtstag", numbered headings in Köln).
- **Phones:** "0800 1000 4800" (DRV), "0221 / 221-30700" (Köln, slash and hyphen), digit
  pairs with the area code set apart, "0 89" (München).
- **Address and quotes:** Sie everywhere; „ “ only around form names (BA).
- **Level and checking:** no CEFR level anywhere. München shows the Inclusion Europe logo
  and names a reader group; Familienportal names capito Berlin and 4 readers.

### Austria

Twelve pairs, checked on 29 October 2026, from two publishers: Land Tirol (8) and the
federal Sozialministerium (4, short `bmasgpk`). Both easy sections claim A2: Tirol through
a capito certificate for its Leicht Lesen pages
([A2, 19 April 2016, 9 testers](https://www.tirol.gv.at/fileadmin/buergerservice/leicht-lesen/Produkt-Zertifikat_A2__Phase_1_Land_Tirol.pdf)),
the Sozialministerium through capito Wien ("Sprachstufe A2"). Single pages carry no level.

| Id | Publisher | Topic | Why |
|----|-----------|-------|-----|
| `tirol-multiple-birth-grant-de` | Land Tirol | Mehrlingsgeburtenzuschuss | Same order on both; 660, 990 and 330 Euro, a first-year deadline |
| `tirol-school-costs-grant-de` | Land Tirol | Schulkostenbeihilfe | 200 and 150 Euro, an application window; the easy page adds the history |
| `tirol-training-grant-de` | Land Tirol | Ausbildungsbeihilfe | Percentages, caps of 350, 300 and 150 Euro, a 2-month deadline on both |
| `tirol-rent-subsidy-de` | Land Tirol | Mietzins- und Annuitätenbeihilfe | 80 and 20 percent, residence periods, numbered steps on both |
| `tirol-apprentice-grant-de` | Land Tirol | Ausbildungsbeihilfe für Lehrlinge | 200 Euro a month; deadlines in words on the standard, in digits on the easy page |
| `bmasgpk-old-age-pension-de` | Sozialministerium | Alterspension | The standard's table of women's retirement ages against its end points; about 30 facts |
| `bmasgpk-child-raising-periods-de` | Sozialministerium | Kindererziehungszeiten und Pensionssplitting | 48 and 60 months, 50 percent, 14 years, the 10th birthday |
| `bmasgpk-invalidity-pension-de` | Sozialministerium | Invaliditätspension | Dates and periods on the standard, simplified on the easy page |
| `tirol-education-allowance-de` (dev) | Land Tirol | Bildungsgeld update | The easy page predates the 2025 rules; percentages as fractions |
| `tirol-child-benefit-plus-de` (dev) | Land Tirol | Kindergeld Plus | Short easy text that keeps standard phrasing |
| `tirol-patient-advocacy-de` (dev) | Land Tirol | Patientenvertretung | Office hours and phones, few other facts |
| `bmasgpk-mpox-de` (dev) | Sozialministerium | Mpox | A 1,150-word A2 text from 2022 against a standard updated in 2025; some periods differ |

Rejected: Tirol Familien-Pass (the standard is a 70-word hub against 2,350 easy words),
Wohnbeihilfe (easy 155 words without the amounts) and Hilfswerk (easy 178 words);
Kinderbetreuungszuschuss (easy 211 words) and Schulveranstaltungen (391 and 249 words)
are reserves. Sozialministerium Hinterbliebenenpensionen (standard 184 words, one number)
and Gefährliche Produkte melden (no numbers). Sozialministeriumservice Schlichtung (no
numeric facts, compounds left whole, no level stated). The parliament's B1 news
(summaries of about 120 words, not rewrites). The PVA's "leicht erklärt" pages (plain
overviews without a level or a standard twin).

| Pool | Size | How to pair | Notes |
|------|------|-------------|-------|
| Tirol | At least 42 topic pages in 8 of the 17 categories of the [overview](https://www.tirol.gv.at/leicht-lesen) | Each easy page links its standard page ("Diese Seite in schwerer Sprache anzeigen"; 21 of 24 checked), so pairing can be automatic | Funding programmes with amounts, deadlines and phones. Standard pages open with an "Einfach zusammengefasst" box; some easy pages are short or keep standard phrasing. Eight pairs. |
| Sozialministerium | 22 Leichter-Lesen pages in the [overview](https://www.sozialministerium.gv.at/Services/Leichter-Lesen.html): 8 on social insurance, 5 on health, 3 on consumer protection, 6 about the ministry | The easy pages do not link their standard page; titles and navigation match, so pair by title | Pensions are fact-rich; some easy texts are older than their standard. Four pairs. |
| Parliament | News in Einfache Sprache (B1, by capito) listed on the [Einfache Sprache page](https://www.parlament.gv.at/services/barrierefreiheit/einfache-sprache); an A2 dictionary of political terms | Each news item links its Parlamentskorrespondenz item | About 120 words per item, a summary rather than a rewrite, few checkable facts. The one Austrian B1 source; none in the manifest. |
| Land Oberösterreich | Decisions under the Oö. Chancengleichheitsgesetz in Einfache Sprache (B1) since 2014, Leichte Sprache on request ([page](https://www.land-oberoesterreich.gv.at/557458.htm)); two easy brochures on that law from 2014 | No public standard counterpart | The decisions are not published; the brochures are old. None in the manifest. |
| Others | Sozialministeriumservice: a Leichter-Lesen list loaded by script, most `.LL.html` paths 404; migration.gv.at: two intro pages; wien.gv.at: `/leicht-lesen/` returns HTTP 500; AMS, ÖGK and BMI: none found | | Thin. The Austrian pool rests on Tirol and the Sozialministerium. |

Terms: [tirol.gv.at](https://www.tirol.gv.at/impressum/) all rights reserved by the Land
Tirol, use beyond personal information needs a request under the Tiroler
Informationsweiterverwendungsgesetz;
[sozialministerium.gv.at](https://www.sozialministerium.gv.at/Ministerium/Kontakt/Impressum.html)
rights reserved, non-commercial reprint allowed with the source named;
[parlament.gv.at](https://www.parlament.gv.at/services/hilfe/nutzungsbedingungen)
editorial texts free for political reporting, political education and private
non-commercial use;
[land-oberoesterreich.gv.at](https://www.land-oberoesterreich.gv.at/nutzungsbedingungen.htm)
free reuse with the source named ("Quelle: Land Oberösterreich"). The rows stay manifest
only, like the Swiss ones.

#### What the Austrian pages write

- **Compounds:** the hyphen with a capital second part on every Austrian easy page read;
  no Mediopunkt anywhere. Tirol: "Schul-Pflicht", "Haushalts-Bestätigung". capito Wien
  for the Sozialministerium often splits only at the main joint:
  "Mindest-Versicherungsdauer", "Regel-Pensionsalter". Land Oberösterreich states the
  hyphen as its rule.
- **Money:** the euro sign first with the Austrian dash survives in easy texts, "€ 330,-",
  "€ 200,- pro Monat" (Tirol), next to "660,00 Euro", "200 Euro" and "1.000 Euro" on other
  pages of the same site; standard pages write "€ 550,--" and "€ 2.750,-". Sozialministerium:
  "2.468,01 Euro", "€ 6.930". No "EUR".
- **Big numbers:** the thousands dot.
- **Times:** "von 8.00 Uhr bis 12.00 Uhr" (Tirol easy page) against "7:30 - 18:00 Uhr" on
  another Tirol standard page; most easy pages carry no times.
- **Dates:** "1. Jänner 2024", "31. Dezember 1963", but also numeric dates on easy pages
  ("01.01.2022", "1.1.1955").
- **Phones:** international with spaces, "+43 512 508 7831" (Tirol); Land Oberösterreich
  "(+43 732) 77 20-0". No slash seen on easy pages.
- **Ordinals:** digit ordinals on easy pages ("2. Lehrjahr", "10. Geburtstag") and
  numbered steps ("1. Ansuchen einreichen").
- **Address and quotes:** Sie on every easy page; „ “ on Tirol and Sozialministerium
  pages, ASCII quotes in the parliament's B1 news.
- **Words:** Jänner, Meldezettel, Obsorge, Kinderbeihilfe and Ansuchen on easy pages.

## 3. Demo documents (no easy-language version)

| Candidate | Why it is strong | Caveats |
|-----------|------------------|---------|
| **Explanations of the Federal Council for a past federal vote** (main demo). Candidates: the premium relief initiative of 9 June 2024 (premiums capped at 10 percent of income; same vocabulary as the Zürich and BAG pairs), or subletting in tenancy law of 24 November 2024 (letter-like rules, shortest text). Avoid the 13th AHV pension (3 March 2024): its financing is on the ballot of 29 November 2026 | They go to every voter. A motion to require easy language failed in the National Council ([Année politique](https://anneepolitique.swiss/fr/prozesse/60222-leichte-sprache-in-den-abstimmungserlauterungen.pdf)), so the gap is documented. Article 11 of the federal act on political rights requires them to be brief, factual and to include the views of significant minorities. That gives the judge a meaning check code cannot do: are the arguments of both sides kept, and is the draft still neutral? | Use a vote that is already over, so the demo never looks like campaigning. Copyright status to confirm (§4). |
| **Fact sheet of the Federal Office of Communications on exemptions from the radio and TV fee** ([PDF](https://www.Bakom.admin.ch/dam/bakom/de/dokumente/Elektronische%20Medien/empfangsgeb%C3%BChren/faktenblatt-4-befreiung.pdf.download.pdf/FB4%20Befreiungen%20und%20Opting%20out.pdf)) | Short, letter-like, full of conditions and deadlines: exemption on request, at most five years back and not before 2019. It reaches exactly the readers easy language is for: recipients of supplementary benefits and deafblind people. | Reuse terms of admin.ch apply (§4): show it in the demo, do not commit the text without clarification. |
| **A blank decision or ordinance from a canton without an easy-language section** | Letters and decisions are the core use case. Decisions and ordinances are free of copyright (§4). | Only blank templates or published ordinances, never a real decision with personal data. To be selected. |
| **A published, anonymised decision**: a cantonal court on an appeal against a KESB decision, or the Federal Supreme Court on disability insurance | The second use case ([use-case-decisions.md](use-case-decisions.md)): long legal reasoning, an operative part and appeal instructions with exact periods. Decisions of authorities are free of copyright (§4), so the text and our output may be committed and shown. | Published decisions replace names with placeholders (`A.________`); in practice the letter for the person concerned is made from the decision before anonymisation, inside the authority. Selected 7 October 2026 as a test: Verwaltungsgericht des Kantons Schwyz, III 2022 132 of 17 October 2022 (an appeal against a KESB deputyship, dismissed; 8 pages, 2,347 words, [PDF](https://entscheidsuche.ch/docs/SZ_Verwaltungsgericht/SZ_VG_001_III-2022-132_2022-10-17.pdf)); not committed; fetched when needed into `data/cache/decisions/` (git-ignored; 8 October 2026: the PDF and the text the ingest extracts from it, 8 pages, 2,255 words, 65 units; the ingest finds three headings only, so the operative part `Demnach erkennt das Verwaltungsgericht:` and the appeal instructions are plain units, the case for FACT-08's text fallback). Result in [use-case-decisions.md](use-case-decisions.md) §7. |
| **A KESB decision written by the team**: a deputyship for an invented person | Shows what may never leave the authority: name, address, case number, an AHV number, the 30-day appeal period. Team-written, so free to commit and show. | Specimen identifiers only (for example with a wrong check digit), never a number that could belong to a real person. Written 7 October 2026: `src/leichtfacile/letters/entscheid-beistandschaft-musterwil.txt`, its layout and wording checked against the two specimen decisions in the KESB Graubünden's guide to deputyships and the KOKES model decision (data/examples/README.md). |

### Private institutions

Insurers, pension funds and utilities are a real market: their terms and letters are
among the least readable texts people receive. They are not used as demo sources:
their texts are protected by copyright, and publishing a rewrite of a real insurer's
documents needs that insurer's consent. The insurance topic is covered in the
evaluation by the BAG pair above.

## 4. Licensing

| Source | Terms | Consequence |
|--------|-------|-------------|
| Swiss Copyright Act, [article 5](https://www.droit-bilingue.ch/en-de/2/23/231.1-5-8.html) | Laws, ordinances, other official enactments, and decisions, minutes and reports of authorities are not protected | Such texts can be committed and shown freely |
| [zh.ch](https://www.zh.ch/de/nutzungshinweise.html) | Viewing, download and printing for personal use only; any further use needs consent | Manifest and fetch script only; no texts in the repository |
| [be.ch](https://www.be.ch/de/tools/rechtliches.html) | Written consent required in advance for any reproduction | Same as Zürich |
| [admin.ch](https://www.admin.ch/de/rechtliches) | Rights reserved by the federal authorities | Web pages and fact sheets: manifest only unless article 5 clearly applies |
| [sg.ch](https://www.sg.ch/content/dam/sgch/kanton-stgallen/personalhandbuch/Legal_Disclaimer.pdf) | Reuse with full attribution for private use; other use needs written permission | Same as Zürich |
| [ti.ch](https://www4.ti.ch/tich/informazioni-legali/) | All content is the property of the cantonal administration; use, reproduction and distribution for non-commercial purposes only with written permission, requested in advance, and with the source named; photos carry fees | Same as Zürich |
| [ahv-iv.ch](https://www.ahv-iv.ch/de/Merkblätter) | Even partial reprints need written consent of the Informationsstelle AHV/IV | Not used |
| Federal voting explanations | Three layers (research of 5 October 2026, not legal advice). The bill text is an enactment (article 5 para. 1a): free. The Federal Council's own parts ("In Kürze", "Im Detail", the Federal Council's arguments) are very likely a report of an authority (para. 1c): legally required, a government act, published to reach everybody. The committees' argument pages (about 2,500 characters each) are written by the committees: treat them as third-party text. Infographics and photos may be protected separately. The admin.ch notice asks for consent for any reproduction, but a website notice cannot create copyright in a text article 5 excludes; the booklets themselves carry no reuse note. | Federal Council parts and bill text can be used in demos and as fixtures, with the source named. Committee pages: short quotes only, unless the committee consents. No images. A written confirmation from the Federal Chancellery is optional and need not be awaited. |

None of the sources above uses an open licence such as CC BY.

### Development and evaluation: no consent needed

Developing, testing and evaluating against these pages needs no consent from the
publishers, as long as neither the texts nor our rewrites of them are published.
Our reading of the Copyright Act (not legal advice):

- The repository contains only URLs. Linking to a public page is not reproduction.
- The application fetches a page when a user submits it. The copy on that machine is
  temporary and technically required (article 24a).
- Evaluation runs on locally cached copies (`data/cache/`, git-ignored) for scientific
  research, with lawful access to the pages (article 24d).

### Where consent would be needed

Anything public needs either consent or an article-5 text:

| Artifact | Rule |
|----------|------|
| Screenshots and screen recordings | Article-5 texts as the main material. Protected pages only as short excerpts that illustrate how the tool works (quotation right, article 25). |
| Example letters in `src/leichtfacile/letters/` and `data/examples/print/` | Article-5 texts or synthetic letters written by the team, since the repository is public. |
| Test fixtures in `tests/fixtures/` | Article-5 texts or synthetic letters, including recorded model outputs. |
| Evaluation tables in `docs/evaluation.md` | Metrics and tables freely; short quoted excerpts with the source named. |

A practical risk comes with live fetching: a page can change, move or go offline after
a run. The application reports a failed fetch clearly, and the article-5 example letters
serve as the fallback.

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
