# Hard texts: examples for tests, glossary and presentation

Status: collection, 5 October 2026. Companion to [rules.md](rules.md) (rule IDs) and
[sources.md](sources.md) (licensing).

All words and sentences below are **written by the team** in the style of Swiss
official letters. None is copied from a real page, so they can be used in the public
repository (`tests/fixtures/`, glossary seeds) and on slides without consent.

## 1. Presentation hook

Idea: open the pitch with one real-sounding official sentence, full screen, and ask
the audience to read it.

Language: the pitch, the slides and the demo video are in English (narration, slide
text, captions). German and French appear on screen only as illustrations: the hard
sentences, the tool output and the two hook questions below.

1. Slide: one sentence from §4, nothing else.
   *"Können Sie das lesen? Haben Sie es sofort verstanden?"* /
   *"Pouvez-vous lire ceci ? L'avez-vous compris tout de suite ?"*
2. Slide: *"You are not alone."* plus the number from §2.
3. Slide: the same content as Leicht·Facile output (A2), side by side with the source.

Best candidates for slide 1:

- **DE-4** (triple negation): ask the audience "Bekomme ich das Geld oder nicht?"
  Even expert readers hesitate.
- **FR-4** (`ne` without `pas`, conditional passé): weak readers miss the negation and
  understand the opposite.
- **DE-3** / **FR-3**: short, but every key word is a false friend (Verfügung,
  Eröffnung, notification).

A light moment for the pitch, after the number or before the demo:

- **Behindertengleichstellungsgesetz (BehiG)**: the law that requires accessible
  information has a 32-letter name and an abbreviation, and fails its own rules
  (LEX-01, LEX-02, GRAM-05). Its full title is a genitive chain: *Bundesgesetz über
  die Beseitigung von Benachteiligungen von Menschen mit Behinderungen*. The French
  side is no better: *Loi fédérale sur l'élimination des inégalités frappant les
  personnes handicapées (LHand)*. Punchline: "Even the law needs Leicht·Facile."
  Easy version: *Gesetz für gleiche Rechte von Menschen mit Behinderungen*.

The judges are expert readers. The point is not that they fail, but that they need a
second look; the target group often never gets past the first.

Slide 3 must show real tool output, not the illustrative rewrites in §4.

## 2. The number

| Figure | Source | Use |
|--------|--------|-----|
| **844'000** people aged 16-65 (15%) with low skills in reading, numeracy and adaptive problem solving | PIAAC 2023 (OECD), [SBFI press release, 23 October 2025](https://www.sbfi.admin.ch/de/newnsb/JrHo0f0D4ssv3Nu8Ee678) | Preferred: newest official figure |
| About **800'000** adults (about 1 in 6) who cannot read and write well enough for everyday tasks (Illettrismus) | ALL survey 2003, widely quoted, for example by [SRF](https://www.srf.ch/news/schweiz/funktionaler-analphabetismus-es-ist-nie-zu-spaet-wenn-erwachsene-lesen-lernen) and [swissinfo](https://www.swissinfo.ch/ger/wenn-mann-oder-frau--buchstaeblich--ueberfordert-ist/43497674) | Only as the rounded, familiar number |

Suggested wording: *"About 844,000 adults in Switzerland struggle with reading.
Source: PIAAC 2023."* As an on-screen illustration: *"Rund 840'000 Erwachsene in der
Schweiz haben Mühe mit Lesen."* / *"Environ 840 000 adultes en Suisse ont de la peine
à lire."*

Key message, the same in every deliverable (video, pitch, README, report): these
people must not be excluded. Official letters decide their money, their deadlines and
their rights, and they have the same right to understand them. Short form for slides
and the end card: *"No one left out."* Never stop at the number alone: say what it
means for the people behind it.

Caveats for the slide:

- The PIAAC figure counts people aged 16-65 only. People over 65 are not included.
- The target group of easy language is wider: people with intellectual disabilities,
  people learning German or French, people with dementia, prelingually deaf people.
  The number is therefore a conservative lower bound for "people who need easy
  language", not the same thing.
- Re-check the press release wording before the final recording: it does not give a
  separate number for reading alone.

## 3. Words

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
| Behindertengleichstellungsgesetz (BehiG) | 32 letters plus an abbreviation; the name of the law that requires easy access fails the easy-language rules itself | LEX-01, LEX-02, GRAM-05 |
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
| ayant droit, requérant·e | Legal role words, inclusive typography | LEX-05-FR |
| émolument, moyennant, nonobstant | Old bureaucratic vocabulary | LEX-01-FR |
| le cas échéant, dûment, en vertu de | Fixed administrative phrases | LEX-01-FR |

## 4. Sentences

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
| FR-1 | Le droit à la réduction individuelle des primes est reconnu aux personnes dont le revenu déterminant n'excède pas les limites fixées par le Conseil d'État. | Passive, `dont`, negation, jargon | GRAM-01-FR, SEM-04 |
| FR-2 | La demande doit être déposée, dûment remplie et signée, au plus tard le 31.03.2027, faute de quoi le droit s'éteint. | Passive, inserted phrase, numeric date, `faute de quoi` | GRAM-01-FR, NUM-03-FR |
| FR-3 | La présente décision peut faire l'objet d'une réclamation écrite et motivée dans les 30 jours dès sa notification. | Nominal style, Swiss `dès`, false friend | SEM-02, SEM-05 |
| FR-4 | Il convient de relever que les frais qui n'auraient pas été annoncés dans les délais ne pourront être remboursés. | Impersonal start, conditional passé, `ne` without `pas` | GRAM-08-FR, GRAM-03-FR |
| FR-5 | Si vous deviez ne pas être en mesure de vous acquitter du montant dû, nous vous saurions gré de bien vouloir prendre contact avec nos services. | Courtesy formulas hide the instruction ("call us") | GRAM-03-FR, SEM-01 |
| FR-6 | Le/la requérant·e transmet les pièces justificatives à l'office compétent, lequel les examine et, le cas échéant, les fait suivre. | Inclusive typography, `lequel`, unclear `les` | LEX-05-FR, SEM-03 |
| FR-7 | Le délai est prolongé au 15.09 moyennant un émolument de Fr. 40.-. | Passive, date without year, amount format, rare words | NUM-03-FR, NUM-07-FR, LEX-01-FR |

Illustrative FALC rewrite of FR-4:

> Vous avez des frais ?
> Annoncez les frais à temps.
> Sinon, vous ne recevez pas d'argent.

## 5. Other uses

- **Golden tests:** most sentences trigger one or more checker rules and can become
  positive cases in `tests/rules/`.
- **Glossary seeds:** the false friends in §3 need glossary entries, since no
  countable rule catches them.
- **Judge tests:** DE-3, DE-4, FR-3 and FR-4 are good probes for SEM-05 and SEM-07
  (does the draft keep the meaning, or flip a negation?).
