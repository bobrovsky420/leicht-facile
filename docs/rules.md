# Rule catalogue

The specification for `src/leichtfacile/rules/`. Every rule here is deterministic
(spaCy morphology, dependency parse, or regex) and has a golden test with at least
two sentences that trigger it and one that must not (`tests/rules/golden_de.yaml`,
`golden_fr.yaml`);
the hard texts of [hard-texts.md](hard-texts.md) are a second acceptance test. Each
rule is registered once in code with its id, severity per level and its instruction
for the writer prompt; the style guide in the writer prompt is rendered from that
registry, and a test fails when the registry and this file list different rule ids,
so prompt, checker and catalogue cannot drift apart.

Rules the checker cannot decide - metaphors, abstract nouns, unclear references,
missing background knowledge - are listed at the end and delegated to the judge.

Severity: `error` blocks approval and triggers repair; `warn` triggers repair but
does not block; `info` is reported only.

## Thresholds per level

| Parameter | A2 (Leichte Sprache / FALC / lingua facile) | B1 (Einfache Sprache / langage clair) |
|-----------|---------------------------------------------|-----------------------|
| Max words per sentence | 12 (optimum 8); French 15 (optimum 10) | 15; French 18 |
| Clauses per sentence | 1 | 2 |
| Passive | error | warn |
| Genitive | warn | info |
| Max word length without Mediopunkt (DE) | 13 letters | 16 letters |
| Max word length (FR, a note only) | 12 letters | 12 letters |
| Max characters per line (export) | 85 | 85 |
| Readability target (DE, Amstad) | ≥ 70 | ≥ 60 |

The A2 values follow the Canton Zürich rules; the B1 values are our own, since no
official Swiss rule set for Einfache Sprache exists yet. French needs about a quarter
more words than German for the same content (articles, prepositions); the French
sentence limits follow from the calibration on the official French pages (below).

## German (DE-CH)

### Sentence structure

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| LEN-01 | At most N words per sentence (N from level) | token count excluding punctuation; a run of numbers (`044 123 45 67`) counts as one word | warn up to 3 words over, error beyond |
| LEN-02 | One clause per sentence; no subordinate clauses | per colon-separated part: subordinating conjunctions (`KOUS`: `dass`, `weil`, `wenn`, ...; `KOUI`: `um ... zu`), relative clauses (`rc`), dependent zu-infinitive clauses, finite verbs with their own subject (coordinated verbs sharing a subject and infinitives mis-tagged as finite do not count). The limit is 1 clause (A2) or 2 (B1). The suggestion is the rewrite recipe for the conjunction found (`rules/recipes.py`, since 7 October 2026): `weil`, `da` two sentences with `Deshalb`; `damit`, `um ... zu` the aim first, then `Deshalb`; `obwohl`, `auch wenn` `Trotzdem`; `wenn`, `falls`, `sofern` a question and an answer with `Dann`, never `vielleicht` (decision D-P); `als`, `nachdem`, `bevor`, `sobald`, `während` two sentences in the order of time with `Dann`; `indem`, `sodass` two sentences; a relative clause two sentences with the noun repeated; `ob` a direct question; `dass` the colon form; several main clauses one sentence per statement. The idea of a recipe per conjunction comes from the Canton of Zurich's prompt (THIRD_PARTY_NOTICES.md), the wording is ours; the repair round gets it as "Vorschlag", the review page shows it as advice and never offers it as a replacement | warn for one clause too many, error for two or more |
| LEN-03 | Enumerations of three or more items become a list | a coordination chain (`cj`/`cd`) of three or more nouns, verbs or adjectives | warn |
| ORD-01 | Subject - verb - object order | subject (`sb`) appears after the finite verb in a main clause that is not a question | info |

### Grammar

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| GRAM-01 | No passive | `werden` (aux) + past participle (`VVPP`), also with modals (`muss eingereicht werden`) and `worden`; `sein` + `zu` + infinitive (`ist einzureichen`), also behind coordinated participles (`ist ausgefüllt und unterzeichnet ... einzureichen`) | error (A2) / warn (B1) |
| GRAM-02 | No genitive; use `von` + dative | noun or proper noun with morph `Case=Gen`, excluding fixed phrases (`Anfang des Jahres`, `Ende des Monats`, `eines Tages`) | warn (A2) / info (B1) |
| GRAM-03 | No Konjunktiv | finite verb with morph `Mood=Sub`, or a form that is always Konjunktiv II (`wäre`, `hätte`, `würde`, `könnte`, `müsste`, `dürfte`); a sentence-initial `Sollten Sie ...` heading a fronted clause (a condition without `wenn`). `möchte` is allowed | warn |
| GRAM-04 | Perfekt instead of Präteritum for full verbs | full verb with `Tense=Past`, excluding `sein`, `haben` and modals | warn |
| GRAM-05 | No nominalisations | a noun, or any part of a compound, ending in `-ung`, `-heit`, `-keit`, `-nis`, `-tum` that is not an everyday word (Zipf frequency below 4.0 for the part and the whole word, stop list: `Wohnung`, `Rechnung`, `Versicherung`, ...) and not in the glossary; substantivised infinitives (`das Einreichen`). Warning in nominal style (with a light verb such as `erfolgen` or `vornehmen`, after `zur`/`bei der`, or with a genitive or `von` attribute), otherwise a note | warn / info |
| GRAM-06 | Pronouns only with an unambiguous reference | 3rd-person pronoun (`er`, `ihn`, `ihm`, lowercase `sie`, demonstrative `dieser`/`diese`) with no noun of matching gender and number in the same or the previous block, or with several; an object `sie` matches feminine singular and plural nouns; a capital `Sie` is taken as the reader | info (judge confirms: SEM-03) |
| GRAM-07 | No indirect speech | Konjunktiv I in the 3rd person (`er sei`), or `laut` / `gemäss` / `zufolge` + statement | info |
| GRAM-08 | Separable verbs split in a main clause: `Sie schicken ... mit`, never `Sie mitschicken` | a finite verb (`VVFIN`) in verb-second position, after a first constituent without a verb and before further words, whose form is a separable prefix (`ab`, `an`, `auf`, `aus`, `bei`, `ein`, `mit`, `nach`, `vor`, `zu`, `zurück`, `zusammen`, ...; never the two-way prefixes `über`, `unter`, `um`, `durch`, `wieder`) plus a known verb infinitive (`mitschicken`, `einreichen`, `mitteilen`); the suggestion names the split (`schicken ... mit`). `anerkennen` is allowed as one word (Swiss usage). An infinitive at the end of a phrase (`Kopie mitschicken`) or under a modal is not flagged. Found 8 October 2026 in an example draft (`Sie mitschicken eine Kopie`); no writer instruction, so the style guide and the prompts stay as frozen | error (A2) / warn (B1) |

### Negation

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| NEG-01 | No double negation | two of `nicht`, `kein-`, `nie`, `niemand`, `nichts`, `ohne`, `weder`, or an adjective with the `un-` prefix whose stem is a word (`unmöglich`), in one clause part (parts are separated by commas, colons and `und`/`oder`/`aber`/`sondern`) | error |
| NEG-02 | Prefer positive formulation | one negation in a sentence | info |

### Words

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| LEX-01 | Long compounds get a Mediopunkt (`Sorge·recht`), lowercase after the dot | word or part longer than N letters (level) with no `·`, in the glossary or not (an entry explains the word, it does not make it shorter); the suggestion comes from a compound splitter built on word frequencies (`Prämien·verbilligung`) and is written into the draft by code in P1 and P2 (nouns only, see "Edits made by code" below); a long word that is no compound is a note, none if it is in the glossary; an uppercase letter after the dot is flagged | warn |
| LEX-02 | No abbreviations except common ones | a list of dotted abbreviations (`z. B.`, `bzw.`, `ggf.`, `ca.`, `Art. 5`, ...), abbreviated weekday ranges (`Mo-Fr`), capital clusters and mixed-case law abbreviations (`KVG`, `BehiG`); allowlist: `WC`, `SBB`, `PDF`, `AHV`, `IV`, `CHF`, `SMS`, `TV`; an abbreviation explained in the text (`(EL)` after the full term) or in the glossary is only `info`; the suggestion is the full word from the vocabulary (`z. B.`: `zum Beispiel`, `EL`: `Ergänzungsleistungen`) | warn |
| LEX-03 | No foreign words, anglicisms, jargon | content word with a Zipf frequency below 2.5 (wordfreq, German), unless it is a compound of common words, in the glossary, or an office word LEX-07 names the everyday word for | info |
| LEX-04 | Rare punctuation | `;`, `(` `)`, `[` `]`, `{` `}`, `&`, `/` between words (URLs and e-mail addresses excluded); `%` is NUM-06, quotation marks are CH-02 | warn |
| LEX-05 | Gender-fair, concrete forms | asterisk, colon, underscore and Binnen-I forms (`Mitarbeiter*innen`, `MitarbeiterInnen`), participle nouns (`Mitarbeitende`, `Studierende`). Generic masculine plurals are not detected | info |
| LEX-06 | Direct address with `Sie` | role nouns for the reader (`Antragsteller`, `Gesuchsteller`, `Versicherte`, `Steuerpflichtige`, `Bezüger`, `die betroffene Person`, ...) | info |
| LEX-07 | Everyday words instead of office words | a `replace` word of the vocabulary ("Vocabulary" below: `innert`, `gemäss`, `einreichen` also as `reichen ... ein`, `in Kraft treten` also as `tritt ... in Kraft`), with its everyday word as the suggestion; not the context-dependent words, not abbreviations (LEX-02), not the role nouns (LEX-06) | warn / info |

### Numbers, dates, times, amounts

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| NUM-01 | Numbers as digits, except `ein`/`eine` | cardinal number words (`zwei` ... `zwölf`, `zwanzig` ... `neunzig`, `hundert`, `tausend`) and ordinals from `zweite` on; `erste` and nouns such as `Dritte` (third parties) are not flagged | warn |
| NUM-02 | Thousands separator for numbers of 4+ digits (`500'000`) | 5+ digits without `'`; 4 digits only next to a currency (years, postal codes and form numbers have 4 digits); phone numbers, dates, IBANs and numbers after `Nr.`, `Formular`, `Merkblatt`, `Art.`, ... are skipped | warn |
| NUM-03 | Date format `4. Februar 2020` | numeric dates `04.02.2020`, `4.2.20`, `31.3.`, ISO and slash dates; the suggestion is the written-out date | warn |
| NUM-04 | Time format `9 Uhr` or `9.30 Uhr`, ranges with `bis` | colon times (`09:00`), `9h`, ranges with a dash (`9-12 Uhr`); full hours (`17 Uhr`) and `8.30 bis 11.30 Uhr` are fine | warn |
| NUM-05 | Durations in words and digits: `1 Stunde und 30 Minuten` | `1.5 h`, `1½ Stunden`, `90 min` | info |
| NUM-06 | Percent written out | `%` → `Prozent` | warn |
| NUM-07 | Amounts as `500 Franken` or `CHF 500`, no decimals when zero | `CHF 500.00`, `Fr. 500.-`, `500.00 CHF` | info |
| NUM-08 | Phone numbers spaced: `044 123 45 67` | `0041`, `044/123 45 67`, unspaced or oddly spaced digits; the spaced international format `+41 44 123 45 67` is accepted (decision D-J, calibration), and a service number in either usual grouping (`0800 123 456`, `0848 35 45 55`) | warn |

### Swiss spelling

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| CH-01 | `ss`, never `ß` | `ß` anywhere; since 8 October 2026 code writes `ss` into the blocks and the glossary after the write stage and every repair round, like the Mediopunkt (`rules/swiss.py`, a `CodeEdit` per word, P1 and P2 only), so the rule fires on texts checked as they are | error |
| CH-02 | No `« »` or `„ “`; use `"` sparingly or none | guillemets, low quotes | info |
| CH-03 | Helvetisms where the official text uses them | German-German variants on a small map (`Fahrrad`→`Velo`, `parken`→`parkieren`, `Bürgersteig`→`Trottoir`, `Krankenhaus`→`Spital`) | info |

### Facts (the most important family)

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| FACT-01 | Every `must_keep` fact with a normalised value appears in the draft | for each fact: render accepted surface forms of `value_norm` (dates in the required format and common variants, amounts with and without separators, phone digits with any spacing, URLs and e-mail case-insensitive, periods in any inflection or as number words with `2 Wochen` equal to `14 Tage`, identifiers without spaces, addresses by postcode and place plus the street and Postfach the fact has; see "Value kinds" below) and search the draft text; the suggestion is the exact string. A fact whose value the source does not contain anywhere (FACT-05) is not required: the model computed or invented it, and FACT-06 forbids it in the draft (since 7 October 2026; before, FACT-01 asked for such a value and FACT-06 accepted it) | error |
| FACT-02 | Every `must_keep` fact is referenced by at least one block | `fact_ids` across blocks ⊇ must-keep ids; a fact whose value FACT-01 reports missing is FACT-01's finding only (one missing fact, one error; since 8 October 2026). The pipeline completes the links the writer leaves out (`stages.link_facts`): a block that contains a fact's value names that fact, and a fact without a value whose text holds values (a contact with its phone number and e-mail) is named by a block that cites one of its sentences and contains all of those values | error |
| FACT-03 | No block without provenance | every non-heading block has ≥ 1 `segment_id` that exists in the source; the pipeline drops an id the source does not have (the 8B cited a block id, `s0009.2`) and gives a block that cites none the source sentences of the facts whose values it contains, else of the facts it names, else the source sentence it says in other words: the one it shares the most distinctive words with, by a clear margin, with two shared words or one of seven letters or more (`stages.link_facts`, `wording_source`, since 8 October 2026) | error |
| FACT-04 | Omissions are explained | every source segment not referenced by any block is either listed in `omissions[]` or in the fact sheet's `omit_candidates[]` | warn |
| FACT-05 | Fact sheet values appear in the source | for each fact with a normalised value: the value is found in the cited source segments; a value found elsewhere in the source, or nowhere, means the fact sheet itself may be wrong (checked on the fact sheet, before writing). A value found nowhere in the source is no longer required by FACT-01 nor accepted by FACT-06 | warn |
| FACT-06 | Every value in the draft appears in the source | the mirror of FACT-01: for each date, amount, phone number, e-mail address, web address, percentage, time, period, identifier and postal address found in a draft block, the value (in any accepted surface form) is found in the source text or is a normalised fact-sheet value that the source contains in another form (a period as its bare count); a fact-sheet value the source does not contain at all, such as an end of a period the model computed (`endet am 15. November 2026` for `innert 30 Tagen seit Mitteilung`), is foreign like any other; a shortened web address that is a prefix of a source address passes, as does a full hour the source writes as a plain number (`8-12 Uhr`) and a period the source writes as a plain number; plain numbers are not checked (`zwei Wochen` may become `14 Tage`: the periods are equal); for a phone number, e-mail, web address, identifier or postal address the suggestion names the source's only one, if it has exactly one (never for dates, amounts and periods: the only date in a document may be a law's) | error |
| FACT-07 | The fixed notice is present | decision mode only, on the export's lines (`check_export`, since 8 October 2026): the first and the last non-empty line are the notice the authority set for the job (`JobConfig.notice`, for example "Massgebend ist der Entscheid."), word for word; the exporters write it as the first and last paragraph and the review page shows it as a banner, not a block, so the check catches an export made without it and a review edit that removes or changes it. The notice is exempt from LAY-01 and LAY-02 | error |
| FACT-08 | Nothing from the operative part or the appeal instructions is dropped | decision mode only (`rules/decision.py`, since 8 October 2026): the operative part is found by its heading (`III. Entscheid`, `Dispositiv`) or, without one, by the sentence that names the verb of deciding and ends with a colon (`Demnach erkennt das Verwaltungsgericht:`) followed by numbered items; the appeal instructions by their heading (`Rechtsmittelbelehrung`) or by the paragraph that begins `Gegen diesen Entscheid kann` (French: `Dispositif`, `Par ces motifs`, `voies de droit`, `peut faire l'objet d'un recours`). Every item of the operative part (one per paragraph; the distribution list `Zustellung an:` and what follows it are none) and the instructions must be cited by a block and may not be listed as omitted. The hit carries the part's fact id: `protect_factsheet` adds one fact without a value per part, so a repair round asks for a dropped part like a missing value, and it blocks like FACT-01. Silent in standard mode and when the document has neither part | error |
| FACT-09 | A medication stays in one block with its dose, scheme and duration | patient letters (`rules/medication.py`, since 8 October 2026), so a reader cannot pair a dose with the wrong drug: for each must-keep fact of kind `medication` and each source sentence that names it, the values that belong to it there are its doses (`quantity` in a dose unit: `mg`, `µg`, `g`, `ml`, `IE`, `Tropfen`, `Tablette`, `Kapsel`, `Hub`, `mg/kg`; not a measurement such as `38,5 Grad`), its dosing schemes and its durations (a `period` in days, weeks or months, not after `nach`, `in`, `innert`, `ab`, `bis`, `vor`, `seit`, `après`, `dans`, `dès`, ...: those are points in time, conditions or ages; a frequency such as `alle 2 Tage` stays). With several names in one sentence a value belongs to the nearest one. The draft passes when one block that names the medication carries every one of those values the draft has; the finding names the block with the most of them and lists the others. A value or a name the draft lacks is FACT-01's finding, not this one. Repairable: the repair round rewrites the named block. A table that holds the name and the dose in different cells is not checked (the source keeps cells, not rows) | error |

The value kinds (`rules/values.py`). Every kind feeds the code completion of the fact
sheet, FACT-01, FACT-05, FACT-06 and "hard facts kept" in the evaluation. Plain
numbers are extracted but not checked. The kinds `period`, `identifier` and `address`
were added on 7 October 2026 for the decisions use case and the further use cases
([use-cases.md §13](use-cases.md#13-what-the-further-use-cases-need)); the model is
not told about them, code finds them in the source and parses what the model writes
as a value. The kind `medication` (8 October 2026) is the exception: code cannot find a
drug name, so the model names the medications. It is asked to only for a source with
a dose or a dosing scheme, through the partial `medication.md` (docs/prompts.md); every
other document gets the standard prompt word for word.

| Kind | Found as | Canonical form and matching |
|------|----------|-----------------------------|
| `date` | `31. März 2026`, `31.3.2026`, `2026-03-31`, `31. März`, `31. Jan. 2026` | ISO date; a date without a year matches the same day and month |
| `amount` | `CHF 1'500.-`, `1 500 Franken`, `Fr. 20.50`, `20.-` | decimal number; an amount matches a plain number with the same value |
| `phone` | `044 123 45 67`, `+41 44 123 45 67`, `0041 44 123 45 67`, `0800 123 456`, `0848 35 45 55` (the ten-digit service numbers 0800, 084x and 090x in either grouping; since 8 October 2026, before that the emergency pages' hotlines came out as four plain numbers) | digits only |
| `email`, `url` | as written, with or without `https://` and `www.` | lowercase; a shortened web address that is a prefix of a source address passes FACT-06 |
| `percent` | `10 %`, `10 Prozent`, `10 pour cent` | the number; a fact sheet carries it as `10%` (the prompt's form, and the code completion's since 7 October 2026: a bare number would parse as a plain number and match no percentage) |
| `time` | `9.00 Uhr`, `09:00`, `9 Uhr`, `9 h 00`, `8.30 bis 11.30 Uhr` | HH:MM |
| `period` | a count in digits or as a number word with days, working days, weeks, months or years in any inflection, also as an adjective: `innert 30 Tagen`, `dreissig Tage`, `30-tägige Frist`, `zwei Wochen`, `ein Jahr`, `5 Arbeitstage`; French `jours`, `jours ouvrables`, `semaines`, `mois`, `ans`; Italian `giorni`, `settimane`, `mesi`, `anni`; ages (`ab 18 Jahren`) are periods too; not an ordinal (`am 3. Tag`), not a unit without a count (`pro Tag`) and not a frequency (`an vier Tagen pro Woche`, `365 Tage im Jahr`, `2 jours par semaine`) | count and unit as written (`30d`, `2w`, `1y`, `5wd`); weeks match days (`2 Wochen` equals `14 Tage`) and years match months, working days match only working days; a period also matches its bare count (`Kinder bis 16 Jahre` survives as `Kinder unter 16`, and a fact the model gave as `30` is found in `30 Tage`) |
| `identifier` | AHV number (`756.1234.5678.97`, spaced or as 13 digits); IBAN and QR-IBAN (`CH`, two check digits and 17 characters, any spacing); postal account (`80-151-4`); UID (`CHE-123.456.789`); a code with a digit after a keyword: `Referenz`, `Dossier`, `Aktenzeichen`, compounds with `-nummer` (`Geschäftsnummer`, `Kundennummer`, `Versichertennummer`, `Policennummer`), `Verfügung Nr.`, `Fall Nr.`; French `référence`, `dossier`, `n° de client`; Italian `riferimento`, `incarto`; a keyword split by code (`Geschäfts·nummer`) and a few small words in between (`Die Nummer von Ihrem Dossier ist 2026-0042`) are allowed; a fact-sheet value that is a bare code (`2026-0042`, `K-4711`) is an identifier too | IBAN and AHV number without spaces, everything else exactly after whitespace normalisation, no checksum test (letters carry specimen numbers; decision D-O); a digits-only identifier also matches the number without its keyword (`Dossier 12345` survives as `Ihre Nummer: 12345`); a form number (`Formular 5100`), a count after a common word (`in diesem Fall 300 Franken`) and a one- or two-digit number after a bare keyword are no identifiers |
| `quantity` | a number with a unit of a dose or a measurement: `mg`, `µg`, `g`, `kg`, `ml`, `dl`, `l`, `IE`, `Tropfen`, `Tablette`, `Kapsel`, `Hub`, `°C`, `Grad`, `mmHg`, `mmol/l`, `mg/dl`, `mg/kg`, as symbol or name in German, French or Italian (`2,5 mg`, `2.5 Milligramm`, `2 Tabletten`, `1½ Tabletten`, `über 38,5 Grad`, `9 Liter`); not a length, a weight of goods or money | number with a decimal point and the unit's symbol (`2.5 mg`, `1.5 Tablette`, `38.5 °C`); a match needs the same number and symbol; a fact given as a bare number is found in the quantity (`2` in `2 Tabletten`), a quantity whose unit the draft dropped is not |
| `schedule` | a dosing scheme of three or four parts (`1-0-1`, `1-0-0-1`, `½-0-½`, `1,5-0-1`), never a page range (`3-5`) or a date with dashes | the parts with decimal points, joined by hyphens (`0.5-0-0.5`); exactly, part by part |
| `medication` | not extracted by code (there is no drug list); the fact sheet gives the name as `value_norm` for a fact of kind `medication`, and code takes off what the model adds to it: a dose, a scheme, a strength without unit, a form (`Tabletten`, `Tropfen`, `comprimés`) and a part in brackets (`Dafalgan 500 mg Tabletten (Paracetamol)` is `Dafalgan`) | the name in lowercase; found in a text as a whole word or words, case-insensitive, with a Mediopunkt allowed between any letters (`Panto·prazol`), never inside a longer word (`Pantoprazolum`). It feeds FACT-01, FACT-05 and FACT-09, not FACT-06 (a draft's names are not extracted, so an invented drug is the judge's SEM-06) and not "hard facts kept" in the evaluation. The Mediopunkt step leaves the names as written |
| `address` | street and house number (a street word at the end: `-strasse`, `-str.`, `-weg`, `-gasse`, `-platz`, `-quai`, ...; French and Italian `Rue`, `Avenue`, `Chemin`, `Route`, `Place`, `Via`, `Piazza`, ...; an adjective of place or kind in front such as `Untere Zollgasse` or `Alte Landstrasse`, never the town or office in front of the street nor the surname above it in an address block), `Postfach` / `Case postale` with or without a number, and a four-digit postcode followed by a place name (`Gerichtsstrasse 12, Postfach, 8000 Musterwil`, also over several lines and with `CH-`); a postcode and place alone count only after a line start, a comma or a colon and before a boundary, never in 1900-2099 without a street or `CH-` (a year and a noun), never a count (`1500 Personen`, `6000 Stimmberechtigte`) or a caption | `street number\|Postfach\|postcode place` with `str.` written out and the Mediopunkt removed; postcode and place must agree (case-insensitive), the street and the Postfach only when the fact has them: an address without its street is a loss (FACT-01), a street the source lacks an invention (FACT-06) |

### Layout (checked on export)

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| LAY-01 | One sentence per line | a line with more than one sentence terminator | warn |
| LAY-02 | Lines ≤ 85 characters | length check; break at clause boundaries | warn |
| LAY-03 | Headings carry the reader's questions | the draft has ≥ 1 heading per ~6 blocks; headings ≤ 8 words | info |

### Readability (reported)

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| READ-01 | Amstad index ≥ target for the level | `180 - ASL - 58.5·ASW`; syllables via `pyphen` (`de_CH`) | warn below target, otherwise info |
| READ-02 | Average sentence length and maximum sentence length | reported in the document metrics, no finding | info |
| READ-03 | Share of sentences with passive, genitive, subordinate clause | reported in the document metrics, no finding | info |

## French (FR-CH, FALC)

The same families as German, checked on the parse of `fr_core_news_md` in
`rules/fr.py`; every French rule id ends in `-FR`. The parser's tense and mood features
are not reliable for French verbs (it reads `recevrez` as a present and `recevez` as a
future), so the future, the conditional and the passé simple are recognised from the
verb's ending and its lemma (`recev-r-ez`, `pour-r-iez`), and the subjunctive from the
conjunctions and verbs that require it.

Not carried over from German: the genitive (GRAM-02; French has no genitive case, and
`de` is the recommended form), the Mediopunkt (LEX-01; French has no long compounds),
`ß` and quotation marks (CH-01, CH-02; guillemets are standard French), the
Helvetisms map (CH-03, replaced by the Swiss numerals) and the word order rule
(ORD-01): French statements keep subject, verb, object, inversion is rare, and the
parser cannot tell an inverted subject from an object.

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| LEN-01-FR | At most N words per sentence (N from level, French limits) | words without punctuation; an elided word counts with the next one (`l'argent`), a hyphenated pronoun with its verb (`appelez-nous`), a run of numbers as one word | warn up to 3 words over, error beyond |
| LEN-02-FR | One clause per sentence; no subordinate clauses | per colon-separated part: the main predicate, coordinated predicates with their own subject, finite subordinate clauses (`advcl`, `ccomp`, `acl:relcl`: `parce que`, `que`, `si`, `quand`, `qui`, `dont`, `où`) and adverbial infinitives (`pour`, `afin de`, `sans`, `avant de`, `après`); `est-ce que` only marks a question. The suggestion is the rewrite recipe for the opener (`rules/recipes.py`, since 7 October 2026): `parce que`, `puisque`, `comme` two sentences with `C'est pourquoi`; `pour que`, `afin que`, `pour`, `afin de` the aim first, then `Pour cela`; `bien que`, `même si` `Mais`; `si` a question and an answer with `Alors`, never `peut-être`; `lorsque`, `quand`, `dès que`, `avant de`, `après` two sentences in the order of time with `Ensuite`; `qui`, `dont`, `où` two sentences with the noun repeated; `que` the noun repeated or a colon after a verb; anything else two short sentences. The recipes are still to be read against the 5 official French pages (PLAN.md WP14) | warn for one clause too many, error for two or more |
| LEN-03-FR | Enumerations of three or more items become a list | a coordination chain (`conj`) of three or more nouns, verbs or adjectives, or noun phrases separated by commas and a final `et` or `ou` | warn |
| GRAM-01-FR | No passive | `être` (`aux:pass`) + past participle. With an agent `par`, in a compound tense (`a été envoyé`), after a modal verb or `aller` (`doit être envoyé`) or in the future (`sera envoyé`) it is a passive; a plain present (`est envoyé`) may describe a state and is a warning (A2) or a note (B1); stative participles in the plain present (`fermé`, `ouvert`, `assuré`, `inscrit`, `interdit`, ...) are not flagged | error (A2) / warn (B1) |
| GRAM-03-FR | No subjunctive or conditional | a conditional ending on the future stem (`pourriez`, `faudrait`, `aimerions`); a subjunctive after a conjunction (`pour que`, `afin que`, `bien que`, `avant que`, `sans que`, `à condition que`, `à ce que`, ...) or a governing verb or adjective (`il faut que`, `il est important que`), or a form that is always subjunctive (`puisse`, `fasse`, `soit`) | warn |
| GRAM-04-FR | Present and passé composé; no passé simple, no futur simple where `aller` + infinitive works | a future ending on the future stem (`recevrez`, `sera`, `enverrons`; the suggestion is `allez recevoir`); a passé simple: a finite past tense with a passé simple ending, a subject and no auxiliary; the singular of second-group -ir verbs and of -ire verbs (`il agit`, `je finis`, `il dit`) is the same in the present and counts as present | warn |
| GRAM-05-FR | No nominalisations | a noun ending in `-tion`, `-sion`, `-ment`, `-age`, `-ance`, `-ence`, `-ité`, `-ure`, `-isme` that is not an everyday word (Zipf frequency below 4.0; stop list: `votation`, `ambulance`, ...) and not in the glossary. Warning in nominal style (with a light verb such as `effectuer`, `procéder` or `intervenir`, after `lors de`, `en vue de` or `dans le cadre de`, or with a `de` attribute: `le versement de la prestation`), otherwise a note | warn / info |
| GRAM-06-FR | Pronouns only with an unambiguous reference | `il`, `elle`, `ils`, `elles`, the object `le` or `la`, `celui-ci` ... with no noun of matching gender and number in the same or the previous block, or with several; the impersonal `il` (`il faut`) is skipped | info (judge confirms: SEM-03) |
| GRAM-07-FR | No reported speech | `selon`, `d'après` | info |
| GRAM-08-FR | No impersonal `il convient de`, `il y a lieu de` | phrase list: `il convient`, `il y a lieu`, `il incombe`, `il appartient`, `il importe`, `il est loisible`, `opportun`, `souhaitable`, `recommandé`, `requis`; `il est nécessaire`, `obligatoire`, `possible`, `important`, `interdit` ... + `de` or `que` is a note | warn |
| NEG-01-FR | No double negation | per clause part (commas, colons, `et`, `ou`, `mais`, `car` and the opener of a subordinate clause separate parts): the words that form one negation with `ne` (`pas`, `jamais`, `rien`, `plus`, `personne`, `aucun`, `ni`, ...) count as one negation together; `sans` (when `ne` is present), `non` (not in `non plus`) and an adjective with a negative prefix (`impossible`, `inutile`, `illégal`, ...) each add one; two negations in one part | error |
| NEG-02-FR | Prefer positive formulation | one negation in a sentence | info |
| LEX-01-FR | No long words | a word or part (at hyphens and apostrophes) longer than 12 letters, not in the glossary; the administrative words it also flagged until 7 October 2026 are LEX-07-FR's now | info |
| LEX-02-FR | No abbreviations except common ones | dotted abbreviations (`p. ex.`, `etc.`, `cf.`, `env.`, `c.-à-d.`, `art. 5`, `al. 2`, `no 3`, `tél.`, `Mme`, ...), abbreviated weekday ranges (`lu-ve`) and months, capital clusters and mixed-case law abbreviations (`LAVS`, `LAMal`); allowlist: `CHF`, `AVS`, `AI`, `CFF`, `PDF`, `WC`, `SMS`, `TV`, `ID`, `OK`; known words in an all-capital heading are no abbreviations; an abbreviation explained in the text or the glossary is only `info`; the suggestion is the full word from the vocabulary (`p. ex.`: `par exemple`) | warn |
| LEX-03-FR | No foreign words, anglicisms, jargon | a content word with a Zipf frequency below 2.5 (wordfreq, French), unless it is a hyphenated word of common parts (`pare-brise`), in the glossary, or an office word LEX-07-FR names the everyday word for | info |
| LEX-04-FR | Rare punctuation | `;`, `(` `)`, `[` `]`, `{` `}`, `&`, `/` between words (URLs and e-mail addresses excluded) | warn |
| LEX-05-FR | Inclusive forms without typographic devices | `·e·s`, `.e.s` and `(e)s` forms (`employé·e·s`, `citoyen(ne)`) | info |
| LEX-06-FR | Direct address with `vous` | role nouns for the reader with an article (`le requérant`, `l'assuré`, `les bénéficiaires`, `le contribuable`, `la personne concernée`, ...) | info |
| LEX-07-FR | Everyday words instead of office words | a `replace` word of the vocabulary (`émolument`, `moyennant`, `le cas échéant`, `s'acquitter de` also as `vous vous acquittez de`, `dans le cadre de` also as `dans le cadre du`), with its everyday word as the suggestion; not the context-dependent words, not abbreviations (LEX-02-FR), not the role nouns (LEX-06-FR) | warn / info |
| NUM-01-FR | Numbers as digits, except `un`/`une` | cardinal number words (`deux` ... `seize`, `vingt` ... `nonante`, `cent`, `mille`, also hyphenated) and ordinals from `deuxième` on; `premier`, the adjective `neuf` and `pour cent` are not flagged | warn |
| NUM-02-FR | Thousands separator with a space: `1 500` | 5+ digits without a separator; 4 digits only next to a currency; phone numbers, dates, IBANs, postal codes and numbers after `no`, `art.`, `formulaire`, ... are skipped; `1'500` is accepted | warn |
| NUM-03-FR | Date `4 février 2020` | numeric dates (`31.03.2026`, ISO and slash dates), also a day and month without year after `au`, `le`, `du`, `dès` (`au 15.09`); the suggestion is the written-out date (`1er mars 2026`) | warn |
| NUM-04-FR | Time `9 h 00`, ranges `de 9 h 00 à 12 h 00` | colon times (`09:00`), dot times (`9.30 h`), ranges with a dash (`8h-12h`); `9h` and `16h30` without spaces are a note, as the Geneva pages write them | warn |
| NUM-05-FR | Durations in words and digits: `1 heure et 30 minutes` | `1,5 h`, `1½ heure`, `90 min` | info |
| NUM-06-FR | Percent written out | `%` → `pour cent` | warn |
| NUM-07-FR | Amounts `500 francs` or `CHF 500` | `CHF 500.00`, `500.-`, `500,00 CHF`, `500 CHF` | info |
| NUM-08-FR | Phone numbers spaced: `022 123 45 67` | as NUM-08, including the accepted `+41 22 123 45 67` | warn |
| CH-03-FR | Swiss numerals `septante`, `huitante` or `octante`, `nonante` when numbers are written out | `soixante-dix` to `soixante-dix-neuf`, `quatre-vingt-dix` to `quatre-vingt-dix-neuf` | info |

Readability: Kandel-Moles (French adaptation of Flesch), syllables via `pyphen`
(`fr`); reported, with no target yet. Rule source for the writer prompt: Inclusion
Europe, "L'information pour tous", plus the cantonal FALC pages used as examples.

## Italian (IT-CH, lingua facile)

Out of scope for the hackathon and on the roadmap (PLAN.md, WP17): the rules below are
specified, not built, and the registry test leaves the ids ending in `-IT` out. An
Italian text gets the language-independent rules (facts, layout, readability). Two
findings from scoping them on 8 October 2026: every spaCy Italian model is licensed
CC BY-NC-SA 3.0 (non-commercial, from its training data UD Italian ISDT), unlike the
German (MIT) and French (LGPL-LR) models, so how the grammar rules get their parse is
a decision of its own; and the polite imperative with Lei (`Compili il modulo`) is a
subjunctive form, so GRAM-03-IT may only fire on a subjunctive after `che` or a
conjunction.

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| GRAM-01-IT | No passive, including `si` passivante | `essere`/`venire` + participle; `si` + 3rd person with patient subject | error (A2) / warn (B1) |
| GRAM-03-IT | No subjunctive or conditional | `Mood=Sub`, `Mood=Cnd` | warn |
| GRAM-04-IT | Present and passato prossimo; no passato remoto | `Tense=Past` finite forms | warn |
| GRAM-09-IT | No gerund clauses | `VerbForm=Ger` heading a clause | warn |
| LEX-01-IT | No long words; no bureaucratic vocabulary (`burocratese`) | word longer than 13 letters; a stop list (`ai sensi di`, `di cui sopra`, `in ottemperanza`, `istanza`) | warn |
| NUM-02-IT | Thousands separator `1'500` (Swiss) | `\d{4,}` unspaced, or `1.500` (Italian style) | warn |
| NUM-03-IT | Date `4 febbraio 2020` | numeric dates | warn |
| NUM-04-IT | Time `ore 9.00` or `9.00`, ranges `dalle 9.00 alle 12.00` | `09:00`, `9h` | warn |
| NUM-07-IT | Amounts `500 franchi` or `CHF 500` | `fr. 500.-`, `500,00` | info |

Readability: Gulpease, which needs letters, words and sentences only (no syllables).
Rule source: Inclusion Europe, "Informazioni per tutti"; Canton Ticino pages as
examples.

## Delegated to the judge (all languages)

These are reported by the meaning check with the same rule-id scheme so the UI can
show them next to the code findings:

| ID | Question the judge answers |
|----|----------------------------|
| SEM-01 | Does the block use a metaphor, idiom or figurative expression? |
| SEM-02 | Does it rely on an abstract noun where a concrete action or person would do? |
| SEM-03 | Does a pronoun or demonstrative have an unclear reference? |
| SEM-04 | Does it assume knowledge the reader may not have (a procedure, an institution, a legal term) without explaining it? |
| SEM-05 | Is a difficult word used without an explanation, where the glossary has none? |
| SEM-06 | Does the block state something the source does not support? (hallucination) |
| SEM-07 | For each fact: present, missing, or distorted? A `missing` on a fact whose value FACT-01 finds in the draft shows on the review page in amber as "judge doubts" (since 8 October 2026); the pipeline still counts it as blocking |
| SEM-08 | Is every obligation still an obligation, every possibility a possibility and every condition a condition (`müssen`, `sollen`, `können`; never `vielleicht` for `wenn`, decision D-P)? In the German and French judge prompts since 7 October 2026 |
| SEM-09 | Does the block add advice or an evaluation the source does not contain ("leider", "Sie sollten Beschwerde erheben")? Decision mode only, asked in the partial's judge section (8 October 2026) |
| SEM-10 | Does every period keep its start ("seit Mitteilung", "ab Zustellung")? A period without its start misleads. Decision mode only (8 October 2026) |

## Vocabulary

`rules/data/vocabulary_de.toml` and `vocabulary_fr.toml` collect hard words of Swiss
administrative letters, read by `rules/vocabulary.py`. Two kinds:

- `replace`: a bureaucratic word, phrase or abbreviation and the everyday word to use
  instead (`innert` = `innerhalb von`, `moyennant` = `avec`, `z. B.` = `zum
  Beispiel`). A suggestion, not a blind substitution: case and word order may change.
  Groups: connectors, adverbs, verbs, nouns, abbreviations.
- `explain`: a term that has to stay, because the reader meets it again on forms and
  letters (`Verfügung`, `Franchise`, `commandement de payer`), with a glossary
  explanation. Groups: law, debt, insurance, health, social, tax, residence, vote.
  The false friends of `docs/hard-texts.md` §3 are in it.
- `context` (a group of either kind): words with a second, everyday sense
  (`Schreiben` a letter or to write, `Leistung` in a school report, `consultation` at
  the doctor's). The writer gets the replace words as a hint; code never flags or adds
  them on its own.
- `[not_in]`: phrases in which a term does not count (`zur Verfügung` is no decision).

Size on 7 October: German 260 replace (13 of them context-dependent) and 197 explain
(7), French 225 (24) and 190 (10). Sources:

- the hard words of the standard pages in the pairs (`data/pairs/`), the explanations
  official easy pages give for the same terms, and the rule lists above (LEX-01-FR,
  LEX-02);
- TERMDAT, the federal terminology database, queried as Linked Data (SPARQL endpoint
  `https://ld.admin.ch/query`, graph `https://lindas.admin.ch/fch/termdat`, about
  40,000 entries in DE, FR, IT, RM, EN): the terms of the pilot's letters (decisions
  and appeals, social insurance, unemployment, IV, KESB, debt collection, tax,
  residence, grants) with the official French equivalent. The entry is named in a
  trailing comment (`# TERMDAT 47696`); only the term names are taken, every
  explanation is our own. Terms TERMDAT lacks (`aufschiebende Wirkung`, `Vorbescheid`,
  the EL terms) name the act that defines them (`# IVG Art. 57a`);
- a cross-check against published lists, used as checklists only, never copied: COSLA's
  *Lexique administratif* (Le Robert 2004, about 4,300 entries; before the check we
  covered about 60 percent of its entries relevant to Swiss letters), the German guides
  of the Bundesverwaltungsamt (2002), Bavaria (2022) and Berlin, the senses Wiktionary
  labels Amtssprache, and Hurraki (CC BY-SA). It found gaps (`widrigenfalls`, `Rechtsöffnung`,
  `indûment`, `mainlevée`, `taxation d'office`) and wrong replacements, now fixed:
  `prescription` is a time limit in debt letters, not a rule; `disposition` broke
  `à votre disposition`; `aufheben` in a decision means annul; `bzw.` and `resp.` mean
  "respectively" in Swiss letters, so the advice is two sentences, not `oder`.

`tests/rules/test_vocabulary.py` checks the lists: no term twice, no en or em dash, no
sharp s in German, and every explanation, one block per sentence, passes the checker
at A2 with no warning (LEX-01 excepted, since code adds the Mediopunkt), LEX-07
included, so the explanations use no office word themselves.

**Matching** (`rules/vocabulary.py`): a word matches as written, by its lemma or with a
usual ending (`Verfügungen`, `versées`), with its Mediopunkt (`Prämien·verbilligung`),
as part of a hyphenated word (`Rente` in `IV-Rente`), as a German separable verb
(`reichen ... ein` for `einreichen`) and as a German verbal phrase whose verb stands
elsewhere in the sentence (`tritt ... in Kraft`); French contracted and elided forms
count (`dans le cadre du`), and a French verb is listed without its pronoun
(`vous vous acquittez de`). Abbreviations and acronyms match as written, so the French
`ai` is never the `AI`. Of overlapping matches the longest wins (`opposition à la
poursuite` over `opposition`).

**Use in the pipeline** (since 7 October 2026; `USE_VOCABULARY=0` switches it off, only
to measure it; docs/architecture.md §4.2, §4.3, §4.6):

1. the fact sheet: a hard term the model listed gets the vocabulary's explanation, and
   up to 6 hard terms of the source are added, the rarest first (12 in all);
2. not the writer: a list of the source's office words in the write prompt made the 8B
   write those words more often (docs/prompts.md, "Vocabulary in the pipeline"), so the
   writer gets none; a later Apertus may take it better;
3. code adds the vocabulary's entry for a hard term a draft uses without one, after the
   write stage and every repair round: at most 6 per version, 10 entries in all, the
   rarest first, marked on the review page (`rules/glossary.py`). "Hard" means an
   abbreviation, a phrase or a word below Zipf 5.2: `loi` and `demande` stay out,
   `Verfügung` and `décision` stay in;
4. the checker: LEX-07 and LEX-07-FR flag the office words left in a draft, with the
   everyday word as the suggestion; LEX-02 and LEX-02-FR suggest the full word of an
   abbreviation; LEX-03 leaves the office words to LEX-07. Without the vocabulary their
   findings are computed but not sent to repair;
5. the vocabulary round: a last repair round for the
   office words still in the best version, the flagged sentences alone with their
   everyday word; its version is kept only if it loses no fact and adds no blocking
   finding (docs/architecture.md §4.6). On the dev pairs it took the office words in the
   final drafts from 42 to 19 without losing a fact.

**Calibration** (7 October 2026): LEX-07 fires 1.2 times per 100 blocks on the 30
official German easy-language pages and 20.5 times on their standard originals;
LEX-07-FR 0.7 and 19.6 on the 5 French pairs. The first version fired 3.1 times on the
easy German pages. The words the official writers keep on purpose became explain
entries (`Behörde`, `Merkblatt`) or context-dependent (`Unterlagen`, `obligatorisch`,
`Dienststelle` in names of offices, `Beeinträchtigung` as the respectful word,
`inklusive` meaning inclusion, `site internet`), and a word inside a hyphenated name
(`Abklärungs-Stelle`) is no longer flagged. What still fires on the easy pages are
office words (`genehmigt`, `einreichen`, `Anliegen`).

## Fact checks for the further use cases

Specified on 6 October 2026 as planned checks for the decisions use case
([use-case-decisions.md](use-case-decisions.md)) and the further use cases
([use-cases.md](use-cases.md)), and all built since: the value kinds `period`,
`identifier`, `address`, `quantity` and `schedule` (7 October 2026), SEM-08 (7 October
2026), FACT-07, FACT-08, SEM-09 and SEM-10 (8 October 2026), and the value kind
`medication` with FACT-09 (8 October 2026). Their rows are in the tables above. A
check planned later gets a row here with its id in backticks, because the registry
test reads the rule tables and expects every bare id there to be registered in code;
when it is built, the row moves into its family's table, with tests, and loses the
backticks. Still open for patient letters (use-cases.md §3): a drug list, so that code
can find a medication the model did not name, and a medical judge model.

## Calibration on official easy-language texts

### German

Run on 6 October 2026 with `python -m leichtfacile eval calibrate --role all --lang de`:
the 30 official German easy-language pages of the manifest, 3,468 blocks, level A2.

| Run | Errors / 100 blocks | Warnings / 100 blocks | Info / 100 blocks |
|-----|---------------------|-----------------------|-------------------|
| First version of the checker | 12.6 | 33.3 | 31.5 |
| After calibration | 2.0 | 25.3 | 40.9 |

The remaining errors are mostly genuine deviations of the professional texts: passive
(GRAM-01, 1.3 per 100 blocks, for example "wurde vom Bund entwickelt"), sentences of
16 words or more (LEN-01, 0.6) and nested clauses (LEN-02, 0.2).

What the calibration changed, and why:

- LEN-01 and LEN-02 are graded. Professional texts often run a few words over the
  limit and use a simple `wenn` clause; that is a warning. Far over the limit, or
  nested clauses, is an error.
- LEN-02 no longer counts a colon construction (`Das bedeutet: ...`), coordinated
  verbs sharing one subject (`plant und macht`), infinitives the tagger mistook for
  finite verbs, or stand-alone phrases such as `Gut zu wissen:` as extra clauses.
- NEG-01 counts negations per clause part: `kein Licht und keinen Strom` and negations
  in two separate clauses are no double negation.
- GRAM-05 warns only in nominal style (light verb, `zur`/`bei der`, genitive or `von`
  attribute); an abstract noun on its own is a note. Everyday words with a nominal
  suffix (`Behinderung`, `Unter·stützung`) are not flagged.
- LEX-01 warns for compounds that can take a Mediopunkt, in the glossary or not: an
  entry explains the word but does not make it shorter. A long word that is no
  compound (`Organisationen`) gets a note, and none when it is in the glossary.

Edits made by code (6 October 2026): the Mediopunkt is the one rule whose fix the
pipeline writes itself. The 8B writer does not apply the split a repair round gives it,
and it puts long compounds in the glossary, which used to exempt them (job
`287fea3aadd2` on CSCS kept `Krankenversicherungspolice` and `Sozialversicherungsstelle`
through two rounds). So after the write stage and after every repair round, before the
check, `rules/mediopunkt.py` splits every compound noun with a part longer than the
level's limit, in the blocks and in the glossary terms, and lowers a capital after an
existing dot. Nouns only (spaCy NOUN or PROPN): for an adjective, a participle or a verb
(`zivilrechtlichen`, `anspruchsberechtigt`) the fix is another word, so they keep the
warning. Words with a digit, web and e-mail addresses are never touched, so no value of
the fact contract changes, and neither is a word in front of a number (a street with its house number: the splitter does not know street names). The feminine ending `-innen` is an ending, not a part: the splitter splits the stem and keeps the ending on it (`Sozial·arbeiterinnen`), so `Schweizerinnen` stays as it is instead of `Schweizer·innen`, which reads as gender typography, and a word that is long only by its ending (`Steuerberaterinnen`) is not split. Word and syllable counts do not change (one word in 1196 splits on the CSCS drafts, Audio·deskription, lost a syllable in the hyphenation patterns); the readability index moves by up to 0.6 points in a few drafts only because spaCy's parser places a sentence boundary differently once a token changes.
The split is the one LEX-01 proposes, so rule and step agree and the rule is silent on
the result. Every change is recorded on the draft version (`code_edits`: block, word
before and after), shown on the review page and reported in the evaluation next to the
LEX family as "LEX by code". The step runs in P1 and P2 only; the baselines measure
the prompt alone, and the CLI `check` checks a text as it is.

Edits made by code (7 October 2026): the glossary entries of the vocabulary. A hard term
of the vocabulary that a block uses without a glossary entry gets the vocabulary's
entry, before the Mediopunkt step (so a long term gets its dot too): at most 6 per
version, 10 entries in all, the rarest first, never a context-dependent word
(`rules/glossary.py`, "Vocabulary" above). Each one is a code edit under SEM-05 (block
`glossary`, the term as `after`) and marked `origin: vocabulary`; the review page shows
it as "from the vocabulary", and the evaluation counts them (`code_glossary`) apart from
the Mediopunkt splits.
- NUM-04 accepts full hours (`17 Uhr`) and `8.30 bis 11.30 Uhr`, as the Bern and
  Zürich pages write them.
- NUM-08 accepts the spaced international format (`+41 44 123 45 67`), which the
  Zürich pages use throughout (decision D-J).
- CH-02 (quotation marks) and GRAM-06 (pronoun reference) are notes: Zürich uses
  guillemets to introduce terms, and the pronoun heuristic is too rough for a warning;
  the judge checks references (SEM-03).
- LEX-02 skips words in capitals for emphasis (`JA`, `NEIN`) and allows `ID`.

The official texts score 2.7 errors per 100 blocks in the evaluation's REF row because
that row scores the held-out `eval` pairs only and recomputes everything per page.

### French

Run on 6 October 2026 with `python -m leichtfacile eval calibrate --role all --lang fr`:
the 5 official French easy-language pages of the manifest, 544 blocks, level A2.

| Run | Errors / 100 blocks | Warnings / 100 blocks | Info / 100 blocks |
|-----|---------------------|-----------------------|-------------------|
| First version of the checker | 5.3 | 27.6 | 21.9 |
| After calibration | 2.2 | 20.0 | 23.5 |

The remaining errors are genuine deviations: passives (GRAM-01-FR, 1.1 per 100 blocks,
for example "ont été relus par des relecteurs"), sentences of more than 18 words
(LEN-01-FR, 0.9; two of them are lines where the page joins a label and a phone
number) and one nested clause. The 9.6 warnings per 100 blocks of LEN-02-FR are mostly
relative clauses with `qui` and `pour` + infinitive, which the professional French
texts use freely; for A2 they stay warnings.

What the calibration changed, and why:

- The sentence limits. French needs about a quarter more words than German for the
  same content: on the official pages the mean sentence has 7.3 words in French and
  5.9 in German, and 95 percent of the sentences have at most 15 words in French and
  11 in German. With the German limit of 12, LEN-01-FR caused 21 of the 29 errors.
  The French limits are 15 words (A2) and 18 (B1).
- `est-ce que` marks a question, not a subordinate clause; the parser reads it as a
  relative clause.
- NEG-01-FR also separates clause parts at the opener of a subordinate clause: "Je ne
  dois pas écrire ... si ce n'est pas demandé" has two negations in two clauses.
- GRAM-04-FR: a passé simple needs a subject and no auxiliary. The parser tags the
  participles in "un acte interdit par la loi" and "il est interdit" as finite verbs.
- GRAM-01-FR: `interdit`, `permis`, `autorisé` and `obligé` after `être` describe a
  state, like `fermé` and `assuré`.
- LEX-02-FR: known words in an all-capital heading ("ÉLECTION DU PROCUREUR GÉNÉRAL")
  are no abbreviations.
- GRAM-05-FR: `votation` is everyday Swiss French, `ambulance` a concrete thing.
- NUM-04-FR: `8h` and `16h30`, as the Geneva pages write them, are a note.

### The value kinds of 7 October on the official texts

The kinds `period`, `identifier` and `address` change what counts as a hard fact, so
the check for false positives is the REF row of the evaluation (the official
easy-language version scored against its original), recomputed with `eval reference`
on 7 October 2026 and read value by value:

| Rows | Hard facts in the source | Kept by the official version | Values the official version adds, per 100 blocks |
|------|--------------------------|------------------------------|--------------------------------------------------|
| 20 German eval pairs | 138 to 191 | 70.3 to 69.2 percent | 2.15 to 2.66 |
| 3 French eval pairs | 40 to 46 | 59.5 to 53.2 percent | 0.51 to 0.76 |
| 10 German dev pairs | 94 to 119 | 42.7 to 36.7 percent | 3.21 to 3.54 |

Over the 35 pairs the new kinds add 90 values to the sources (periods and addresses
mostly, one business number), the official versions leave 51 of them out and add 17 of
their own: the same picture as for dates and amounts. Reading the values found three
defects, fixed the same day: `9001 St.Gallen` (no space after `St.` on the sg pages)
gave the place `St`; a town or office in front of the street was taken into it (`Biel
Bahnhofsplatz 2D`), so a draft's `Bahnhofsplatz 2D, 2502 Biel` would have counted as a
lost street; and a count or a caption after a four-digit number became a place (`6000
Stimmberechtigte`, `Case postale 1555 Photos`). What stays, by design: ages are periods
(a page that portrays nine people with their ages gets nine must-keep facts unless the
model marks the passages droppable), a postcode and place in running text (`in 8000
Zürich`) is not found, and Neuchâtel (2000) or Sion (1950) need their street or `CH-`.
The calibration of the rules above is unchanged: no FACT rule runs on a text without its
source.

The kinds `quantity` and `schedule`, added the same day for patient letters, hardly
touch the cantonal pages: six quantities in the 35 sources (temperatures and litres of
water on two pages), no dosing scheme. The official versions keep one of the five on
the eval pairs and add one (`3 Liter pro Person` for `9 Liter`), which moves the
German eval mean from 69.2 to 65.9 percent because both pages have few hard facts (the
count 191 to 195). `1000 IE` was read as a postcode and a place until quantities were
taken before addresses; a known unit is never a place.

## Test plan for the checker

- `tests/rules/golden_<lang>.yaml`: for every rule, 2-5 positive and 2-5 negative
  sentences, including sentences from real cantonal easy-language pages that must
  pass with no `error`.
- `tests/rules/test_value_kinds.py`: the kinds `period`, `identifier`, `address`,
  `quantity` and `schedule`, what is and is not one of them, how they match (`2 Wochen`
  and `14 Tage`, working days, an address with and without its street, `2,5 mg` and
  `2.5 Milligramm`), and FACT-01, FACT-06 and the code completion on a synthetic
  decision of a child and adult protection authority and on a line of a discharge
  letter.
- The official easy-language pages in the evaluation set serve as a sanity check: the
  checker's error rate on professionally written Leichte Sprache should be near zero;
  any error it raises there is either a genuine deviation or a false positive to fix.
- Readability implementations are tested against published example values for each
  formula.
- `tests/rules/test_facts.py`: the fact rules on a synthetic letter, including a phone
  number from the prompt's examples that FACT-06 must flag and the accepted surface
  forms (numeric date, `CHF 20.-`, `+41`, a shortened web address) it must not.
