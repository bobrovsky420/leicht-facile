# Hard texts: examples for tests and the glossary

Status: collection, 5 October 2026. Companion to [rules.md](rules.md) (rule IDs) and
[sources.md](sources.md) (licensing).

All words and sentences below are **written by the team** in the style of Swiss
official letters. None is copied from a real page, so they can be used in the public
repository (`tests/fixtures/`, glossary seeds) without consent.

## 1. The number

| Figure | Source | Use |
|--------|--------|-----|
| **1.25 million** people aged 16-65 (22%) with low literacy (level 1 or below) | Swiss Federal Statistical Office (FSO), [first results of PIAAC 2022/2023, Neuchâtel 2024](https://www.bfs.admin.ch/asset/fr/33346105), section 3.3 | Used everywhere (owner, 9 October 2026) |
| **844'000** people aged 16-65 (15%) with low skills in all three domains: reading, numeracy and adaptive problem solving | FSO, [Leben mit geringen Lese-, Alltagsmathematik- und Problemlösekompetenzen, Neuchâtel 2025](https://dam-api.bfs.admin.ch/hub/api/dam/assets/36075857/master); [SBFI press release, 23 October 2025](https://www.sbfi.admin.ch/de/newnsb/JrHo0f0D4ssv3Nu8Ee678) | Not used: it is not a count of people who struggle with reading |
| About **800'000** adults (about 1 in 6) who cannot read and write well enough for everyday tasks (Illettrismus) | ALL survey 2003, widely quoted, for example by [SRF](https://www.srf.ch/news/schweiz/funktionaler-analphabetismus-es-ist-nie-zu-spaet-wenn-erwachsene-lesen-lernen) and [swissinfo](https://www.swissinfo.ch/ger/wenn-mann-oder-frau--buchstaeblich--ueberfordert-ist/43497674) | Only as the rounded, familiar number |

Suggested wording: *"1.25 million adults in Switzerland struggle with reading. Source:
Swiss Federal Statistical Office, PIAAC 2022/23."* In full text: "about 1.25 million
adults in Switzerland aged 16 to 65 (22 percent) have low reading skills (Swiss Federal
Statistical Office, PIAAC 2022/23)". It is the office's own figure for literacy alone,
checked in its report on 9 October 2026. Name the office in words only: no logo, no
federal emblem. Its reports allow reproduction for non-commercial use when the source
is named. In German and French: *"1,25 Millionen Erwachsene in der Schweiz
haben Mühe mit Lesen."* / *"1,25 million d'adultes en Suisse ont de la peine à
lire."*

Caveats:

- The PIAAC figure counts people aged 16-65 only. People over 65 are not included.
- The target group of easy language is wider: people with intellectual disabilities,
  people learning German or French, people with dementia, prelingually deaf people.
  The number is therefore a conservative lower bound for "people who need easy
  language", not the same thing.
- The 22 percent include about 3 percent who could not take the test in any test
  language (German, French or Italian); the office assumes they would score low.

## 2. Words

Ordered roughly from "looks easy but is not" to "obviously hard". The false friends
at the top are the most interesting: the code checker cannot see them, only the judge
(SEM-05) or a glossary entry can.

### German

| Word | Why it is hard | Rule |
|------|----------------|------|
| Verfügung | False friend: everyday `zur Verfügung stehen`, here an official decision | SEM-05 |
| Eröffnung (einer Verfügung) | Readers know it as the opening of a shop; here formal delivery | SEM-05 |
| Franchise | Everyday: a chain store; here the insurance deductible | LEX-03 |
| Betreibung, Zahlungsbefehl | Swiss debt-collection terms; `Befehl` sounds like a police order | SEM-04 |
| massgebendes Einkommen | Everyday words for a defined legal amount | SEM-04 |
| Säule 3a | Metaphor plus a code | SEM-01 |
| Prämienverbilligung | Long compound, abstract noun | LEX-01, GRAM-05 |
| Rechtsmittelbelehrung | Legal jargon; `Rechtsmittel` is unknown | LEX-01, SEM-04 |
| Ergänzungsleistungen (EL) | Abstract compound, usually abbreviated | LEX-01, LEX-02 |
| Behindertengleichstellungsgesetz (BehiG) | 32 letters plus an abbreviation; the name of the law on equal access for people with disabilities fails the easy-language rules itself | LEX-01, LEX-02, GRAM-05 |
| Kostengutsprache | Swiss administrative term; `Gutsprache` is unknown | LEX-01, LEX-03 |
| innert, gemäss, ggf., bzw. | Bureaucratic prepositions and abbreviations | LEX-02 |
| Art. 14 Abs. 1 lit. b ELG | A chain of abbreviations | LEX-02 |

### French

| Word | Why it is hard | Rule |
|------|----------------|------|
| prestations complémentaires (PC) | Many readers know `PC` only as a computer | LEX-02, SEM-05 |
| notification | Readers know it from the phone; here formal delivery | SEM-05 |
| franchise, quote-part | Same false friend as in German | LEX-03 |
| poursuite, commandement de payer | Debt-collection terms that sound threatening | SEM-04 |
| permis d'établissement, impôt à la source | Institutions the reader must already know | SEM-04 |
| réduction individuelle des primes (RIP), subside | Abbreviation, rare word | LEX-02 |
| voies de droit, délai de recours | Legal jargon | SEM-04 |
| ayant droit, requérant·e | Legal role words, inclusive typography | LEX-05 |
| émolument, moyennant, nonobstant | Old bureaucratic vocabulary | LEX-07 |
| le cas échéant, dûment, en vertu de | Fixed administrative phrases | LEX-07 |

### Italian

| Word | Why it is hard | Rule |
|------|----------------|------|
| prestazioni complementari (PC) | Readers know `PC` as a computer; the benefit is unknown | LEX-02, SEM-05 |
| notificazione | Readers know the phone's notifications; here formal delivery | SEM-05 |
| franchigia, aliquota percentuale | Same false friend as in German; a technical share | LEX-03, SEM-05 |
| esecuzione, precetto esecutivo | Debt-collection terms that sound like a penalty | SEM-04 |
| permesso di domicilio, imposta alla fonte | Institutions the reader must already know | SEM-04 |
| riduzione individuale dei premi (RIPAM), sussidio | Abbreviation, rare word | LEX-02 |
| rimedi giuridici, termine di ricorso | Legal jargon | SEM-04 |
| avente diritto, richiedente, istante | Legal role words; `istante` is also the instant | LEX-06, SEM-05 |
| emolumento, mediante, nonostante | Old bureaucratic vocabulary | LEX-07 |
| qualora, debitamente, in virtù di | Fixed administrative phrases | LEX-07 |

## 3. Sentences

The rewrites are hand-written illustrations of the target, not tool output.

### German

| ID | Sentence | Why it is hard | Rules |
|----|----------|----------------|-------|
| DE-1 | Anspruch auf Prämienverbilligung haben Personen, deren massgebendes Einkommen die vom Regierungsrat festgelegte Grenze nicht übersteigt. | Relative clause, inverted order, negation, abstract nouns | LEN-02, ORD-01, GRAM-05, NEG-02 |
| DE-2 | Das Gesuch ist vollständig ausgefüllt und unterzeichnet bis spätestens 31.03.2027 einzureichen, andernfalls verwirkt der Anspruch. | Hidden passive, numeric date, jargon `verwirkt`, second clause | GRAM-01, NUM-03, LEN-02 |
| DE-3 | Gegen diese Verfügung kann innert 30 Tagen seit Eröffnung schriftlich Einsprache erhoben werden. | Passive, two false friends, no visible actor | GRAM-01, SEM-05 |
| DE-4 | Es ist nicht unwesentlich, dass Kosten, die nicht fristgerecht geltend gemacht werden, nicht vergütet werden können. | Triple negation, nested clauses; readers often understand the opposite | NEG-01, LEN-02 |
| DE-5 | Die Rückerstattung von Krankheits- und Behinderungskosten erfolgt gemäss Art. 14 Abs. 1 ELG, sofern die Kosten nicht durch Dritte gedeckt sind bzw. wären. | Elliptic compound, abbreviations, Konjunktiv, abstract `Dritte` | LEX-02, GRAM-03, SEM-02 |
| DE-6 | Sollten Sie mit der Zahlung in Verzug geraten, behalten wir uns vor, die Betreibung einzuleiten. | Conditional without `wenn`, idiom, indirect threat | GRAM-03, SEM-01 |
| DE-7 | Der Antragsteller hat die Unterlagen der zuständigen Stelle einzureichen; diese prüft sie und leitet sie gegebenenfalls weiter. | Third person instead of `Sie`, semicolon, unclear pronouns | LEX-06, LEX-04, GRAM-06 |

Illustrative A2 rewrite of DE-4:

> Sie haben Kosten?
> Melden Sie die Kosten rechtzeitig.
> Sonst bekommen Sie kein Geld zurück.

### French

| ID | Sentence | Why it is hard | Rules |
|----|----------|----------------|-------|
| FR-1 | Le droit à la réduction individuelle des primes est reconnu aux personnes dont le revenu déterminant n'excède pas les limites fixées par le Conseil d'État. | Passive, `dont`, negation, jargon | GRAM-01, SEM-04 |
| FR-2 | La demande doit être déposée, dûment remplie et signée, au plus tard le 31.03.2027, faute de quoi le droit s'éteint. | Passive, inserted phrase, numeric date, `faute de quoi` | GRAM-01, NUM-03 |
| FR-3 | La présente décision peut faire l'objet d'une réclamation écrite et motivée dans les 30 jours dès sa notification. | Nominal style, Swiss `dès`, false friend | SEM-02, SEM-05 |
| FR-4 | Il convient de relever que les frais qui n'auraient pas été annoncés dans les délais ne pourront être remboursés. | Impersonal start, conditional passé, `ne` without `pas` | GRAM-09, GRAM-03 |
| FR-5 | Si vous deviez ne pas être en mesure de vous acquitter du montant dû, nous vous saurions gré de bien vouloir prendre contact avec nos services. | Courtesy formulas hide the instruction ("call us") | GRAM-03, SEM-01 |
| FR-6 | Le/la requérant·e transmet les pièces justificatives à l'office compétent, lequel les examine et, le cas échéant, les fait suivre. | Inclusive typography, `lequel`, unclear `les` | LEX-05, SEM-03 |
| FR-7 | Le délai est prolongé au 15.09 moyennant un émolument de Fr. 40.-. | Passive, date without year, amount format, rare words | NUM-03, NUM-07, LEX-07 |

Illustrative FALC rewrite of FR-4:

> Vous avez des frais ?
> Annoncez les frais à temps.
> Sinon, vous ne recevez pas d'argent.

### Italian

| ID | Sentence | Why it is hard | Rules |
|----|----------|----------------|-------|
| IT-1 | Il diritto alla riduzione individuale dei premi è riconosciuto alle persone il cui reddito determinante non supera i limiti fissati dal Consiglio di Stato. | Passive, `il cui`, negation, jargon | GRAM-01, LEN-02, SEM-04 |
| IT-2 | La domanda deve essere inoltrata, debitamente compilata e firmata, entro il 31.03.2027, pena la perdita del diritto. | Passive, inserted phrase, numeric date, `pena` | GRAM-01, NUM-03, LEX-07 |
| IT-3 | Contro la presente decisione può essere presentato reclamo scritto e motivato entro 30 giorni dalla notificazione. | Passive, nominal style, false friend | GRAM-01, SEM-02, SEM-05 |
| IT-4 | Occorre rilevare che le spese non annunciate entro i termini non potranno essere rimborsate. | Impersonal start, two negations, future passive | GRAM-09, NEG-01, GRAM-01 |
| IT-5 | Qualora Lei non fosse in grado di pagare l'importo dovuto, La preghiamo di contattare i nostri uffici. | Subjunctive after `qualora`, courtesy formulas hide the instruction ("call us") | GRAM-03, LEX-07, SEM-01 |
| IT-6 | Il/la richiedente trasmette i documenti giustificativi all'ufficio competente, il quale li esamina e, se del caso, li inoltra. | Slash, third person, `il quale`, unclear `li` | LEX-04, LEX-06, SEM-03 |
| IT-7 | Il termine è prorogato al 15.09 mediante un emolumento di fr. 40.-. | Passive, date without year, amount format, rare words | NUM-03, NUM-07, LEX-07 |

Illustrative lingua facile rewrite of IT-4:

> Lei ha delle spese?
> Annunci le spese in tempo.
> Altrimenti non riceve i soldi.

## 4. Other uses

- **Golden tests:** most sentences trigger one or more checker rules and can become
  positive cases in `tests/rules/`.
- **Glossary seeds:** the false friends in §2 need glossary entries, since no
  countable rule catches them.
- **Judge tests:** DE-3, DE-4, FR-3 and FR-4 are good probes for SEM-05 and SEM-07
  (does the draft keep the meaning, or flip a negation?).
