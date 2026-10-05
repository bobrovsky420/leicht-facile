# Rule catalogue

The specification for `src/leichtfacile/rules/`. Every rule here is deterministic
(spaCy morphology, dependency parse, or regex) and has a golden test with at least
one sentence that triggers it and one that must not. The style guide inserted into
the writer prompt is **generated from this file**, so prompt and checker cannot drift
apart.

Rules the checker cannot decide - metaphors, abstract nouns, unclear references,
missing background knowledge - are listed at the end and delegated to the judge.

Severity: `error` blocks approval and triggers repair; `warn` triggers repair but
does not block; `info` is reported only.

## Thresholds per level

| Parameter | A2 (Leichte Sprache / FALC / lingua facile) | B1 (Einfache Sprache) |
|-----------|---------------------------------------------|-----------------------|
| Max words per sentence | 12 (optimum 8) | 15 |
| Clauses per sentence | 1 | 2 |
| Passive | error | warn |
| Genitive | warn | info |
| Max word length without Mediopunkt (DE) | 13 letters | 16 letters |
| Max characters per line (export) | 85 | 85 |
| Readability target (DE, Amstad) | ≥ 70 | ≥ 60 |

The A2 values follow the Canton Zürich rules; the B1 values are our own, since no
official Swiss rule set for Einfache Sprache exists yet.

## German (DE-CH)

### Sentence structure

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| LEN-01 | At most N words per sentence (N from level) | token count excluding punctuation | error |
| LEN-02 | One clause per sentence; no subordinate clauses | spaCy: tokens with dep `cp` / `mo` headed by a subordinating conjunction (`dass`, `weil`, `obwohl`, `wenn`, `damit`, `nachdem`, …), or more than one finite verb | warn (A2: error) |
| LEN-03 | Enumerations of three or more items become a list | ≥ 3 comma- or `und`-separated noun phrases in one sentence | warn |
| ORD-01 | Subject - verb - object order | subject (`sb`) appears after the finite verb in a main clause that is not a question | info |

### Grammar

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| GRAM-01 | No passive | `werden` (aux) + past participle (`VVPP`); also `sein` + `zu` + infinitive (`ist einzureichen`) | error (A2) / warn (B1) |
| GRAM-02 | No genitive; use `von` + dative | determiner or noun with morph `Case=Gen`, excluding an allowlist of fixed phrases (`Anfang des Jahres`, `Ende des Monats`) | warn |
| GRAM-03 | No Konjunktiv | verb with morph `Mood=Sub` | warn |
| GRAM-04 | Perfekt instead of Präteritum for full verbs | full verb with `Tense=Past`, excluding `sein`, `haben` and modals | warn |
| GRAM-05 | No nominalisations | nouns ending in `-ung`, `-heit`, `-keit`, `-nis`, `-tum`, substantivised infinitives (`das Einreichen`) - excluding the glossary and a stop list (`Wohnung`, `Zeitung`, `Rechnung`) | warn |
| GRAM-06 | Pronouns only with an unambiguous reference | 3rd-person pronoun (`er`, `sie`, `es`, `dieser`, `diese`) with no noun of matching gender/number in the same or the previous block | warn (judge confirms) |
| GRAM-07 | No indirect speech | `Konjunktiv I` reporting pattern or `laut` / `gemäss` + statement | info |

### Negation

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| NEG-01 | No double negation | two of `nicht`, `kein-`, `nie`, `niemand`, `nichts`, `ohne`, `un-` prefix in one sentence | error |
| NEG-02 | Prefer positive formulation | one negation in a sentence | info |

### Words

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| LEX-01 | Long compounds get a Mediopunkt (`Sorge·recht`), lowercase after the dot | word longer than N letters (level) with no `·`, not in glossary; suggestion from a compound splitter | warn |
| LEX-02 | No abbreviations except common ones | regex for abbreviations (`z.B.`, `bzw.`, `ggf.`, `Art.`, `Abs.`, capital clusters); allowlist: `WC`, `SBB`, `PDF`, `AHV`, `IV`, `CHF`, `Fr.`, `Uhr`; a term introduced in full earlier in the text is exempt | warn |
| LEX-03 | No foreign words, anglicisms, jargon | token not in the top-10k German lemma list and not in the glossary; tuned to be conservative | info |
| LEX-04 | Rare punctuation | `;`, `(` `)`, `[` `]`, `{` `}`, `« »`, `&`, `%`, `/` between words | warn |
| LEX-05 | Gender-fair, concrete forms | generic masculine plural for persons (`die Mitarbeiter`), `-ende` forms, asterisk/colon/underscore forms (`Mitarbeiter*innen`) | info |
| LEX-06 | Direct address with `Sie` | third-person references to the reader (`der Antragsteller muss`) in a text that addresses the reader elsewhere | info |

### Numbers, dates, times, amounts

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| NUM-01 | Numbers as digits, except `ein`/`eine` | number words (`zwei` … `zwölf`, `hundert`, `tausend`, ordinals) | warn |
| NUM-02 | Thousands separator for numbers of 4+ digits (`500'000`) | `\d{4,}` without `'` or thin space | warn |
| NUM-03 | Date format `4. Februar 2020` | numeric dates `04.02.2020`, `4.2.20`, ISO dates | warn |
| NUM-04 | Time format `9.00 Uhr`, ranges `9.00 Uhr bis 12.00 Uhr` | `9 Uhr`, `09:00`, `9h`, `9-12 Uhr` | warn |
| NUM-05 | Durations in words and digits: `1 Stunde und 30 Minuten` | `1.5 h`, `1½ Stunden`, `90 min` | info |
| NUM-06 | Percent written out | `%` → `Prozent` | warn |
| NUM-07 | Amounts as `500 Franken` or `CHF 500`, no decimals when zero | `CHF 500.00`, `Fr. 500.-`, `500.00 CHF` | info |
| NUM-08 | Phone numbers spaced, no country code: `044 123 45 67` | `+41 44 …`, `0041`, `044/123 45 67`, unspaced digits | warn |

### Swiss spelling

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| CH-01 | `ss`, never `ß` | `ß` anywhere | error |
| CH-02 | No `« »` or `„ “`; use `"` sparingly or none | guillemets, low quotes | warn |
| CH-03 | Helvetisms where the official text uses them | German-German variants on a small map (`Fahrrad`→`Velo`, `parken`→`parkieren`, `Bürgersteig`→`Trottoir`, `Krankenhaus`→`Spital`) | info |

### Facts (the most important family)

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| FACT-01 | Every `must_keep` fact with a normalised value appears in the draft | for each fact: render accepted surface forms of `value_norm` (dates in the required format and common variants, amounts with and without separators, phone digits with any spacing, URLs and e-mail case-insensitive) and search the draft text | error |
| FACT-02 | Every `must_keep` fact is referenced by at least one block | `fact_ids` across blocks ⊇ must-keep ids | error |
| FACT-03 | No block without provenance | every non-heading block has ≥ 1 `segment_id` that exists in the source | error |
| FACT-04 | Omissions are explained | every source segment not referenced by any block is either listed in `omissions[]` or in the fact sheet's `omit_candidates[]` | warn |

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
| READ-02 | Average sentence length and maximum sentence length | reported per document | info |
| READ-03 | Share of sentences with passive, genitive, subordinate clause | reported per document | info |

## French (FR-CH, FALC)

Same families; the German-specific rules (`ß`, Mediopunkt, Perfekt/Präteritum,
Helvetisms map) are replaced by:

| ID | Rule | Detection | Severity |
|----|------|-----------|----------|
| GRAM-01-FR | No passive | `être` + past participle with morph `Voice=Pass` or agent `par` | error (A2) / warn (B1) |
| GRAM-03-FR | No subjunctive or conditional | `Mood=Sub`, `Mood=Cnd` | warn |
| GRAM-04-FR | Present and passé composé; no passé simple, no futur simple where `aller` + infinitive works | `Tense=Past` with `VerbForm=Fin` (passé simple), `Tense=Fut` | warn |
| GRAM-08-FR | No impersonal `il convient de`, `il y a lieu de` | phrase list | warn |
| LEX-01-FR | No long words; prefer the everyday synonym | word longer than 12 letters not in glossary | info |
| NUM-02-FR | Thousands separator with a space: `1 500` | `\d{4,}` unspaced | warn |
| NUM-03-FR | Date `4 février 2020` | numeric dates | warn |
| NUM-04-FR | Time `9 h 00`, ranges `de 9 h 00 à 12 h 00` | `09:00`, `9h` without space | warn |
| NUM-07-FR | Amounts `500 francs` or `CHF 500` | `500.-`, `500,00 CHF` | info |
| CH-03-FR | Swiss numerals `septante`, `huitante`/`octante` (Vaud/Fribourg), `nonante` when numbers are written out | `soixante-dix`, `quatre-vingt-dix` | info |
| LEX-05-FR | Inclusive forms without typographic devices | `·e·s`, `(e)s`, `.e.s` forms | info |

Readability: Kandel-Moles (French adaptation of Flesch), syllables via `pyphen`
(`fr`). Rule source for the writer prompt: Inclusion Europe, "L'information pour
tous", plus the cantonal FALC pages used as examples.

## Italian (IT-CH, lingua facile)

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
| SEM-07 | For each fact: present, missing, or distorted? |

## Test plan for the checker

- `tests/rules/golden_<lang>.yaml`: for every rule, 2-5 positive and 2-5 negative
  sentences, including sentences from real cantonal easy-language pages that must
  pass with no `error`.
- The official easy-language pages in the evaluation set serve as a sanity check: the
  checker's error rate on professionally written Leichte Sprache should be near zero;
  any error it raises there is either a genuine deviation or a false positive to fix.
- Readability implementations are tested against published example values for each
  formula.
