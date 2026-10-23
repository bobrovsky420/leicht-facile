# Use case: decisions of child and adult protection authorities and courts

Status: scenario, 6 October 2026. Partly planned: §7 lists what works today and what is
not built yet. Companion to [use-case-canton.md](use-case-canton.md), the first use
case (texts a cantonal administration publishes), and to
[architecture.md](architecture.md), which describes the mechanics referenced here.

## 1. Who and why

A child and adult protection authority (KESB) or a court whose decisions reach people
with intellectual disabilities, dementia or a psychiatric illness, children, and people
still learning German or French. Their decisions are among the most complex texts an
authority writes: facts, legal reasoning, the operative part (Dispositiv) and the
instructions on how to appeal. They are also among the most important texts the people
concerned ever receive, because they decide about their money, their home and their
right to decide for themselves.

Three reasons to act:

- **The law asks for it.** Since the 2013 revision, adult protection law requires
  authorities to preserve and promote the self-determination of the person concerned
  as far as possible (Art. 388 para. 2 ZGB). The UN Convention on the Rights of Persons
  with Disabilities asks for access to justice, including procedural accommodation
  (Art. 13); the UN committee reviewed Switzerland on this in its 2022 concluding
  observations.
- **It has been done by hand.** KESB Region Solothurn has offered documents from the
  adult protection procedure in easy language since June 2016, including decisions and
  accompanying letters (project "Einfach leicht verständlich", described by FHNW
  researchers in 2018).
- **Time is short.** The appeal period runs from notification: 30 days for most
  decisions of the KESB, 10 days for involuntary placement in an institution (Art. 450b
  ZGB). An easy-language explanation written by hand a week later can come too late to
  be of use.

What the authority wants is an **accompanying letter in easy language**, handed over
together with the decision: what was decided, what it means for the person, what they
can do and by when, and whom they can ask. The decision itself stays the only legally
binding text.

## 2. Why this use case needs sovereignty most

Before anonymisation, a decision names the person and describes their health, family
and finances. Such a text may not go to a chatbot on a foreign cloud. Leicht·Facile
is a Python package installed inside the network, and for decisions it is pointed at a
model endpoint that the authority or the canton controls: on its own servers,
air-gapped, or on a Swiss cloud under the canton's contract
([architecture.md §10](architecture.md#10-deployment-and-sovereignty)).
Nothing else leaves the network. Official secrecy binds the authority, which must also
be able to account for the model it uses and depend on no foreign supplier for it:
that makes Apertus the model that fits best, and the one recommended for decisions
([use-cases.md §2](use-cases.md#why-apertus-fits-best)).

The audit bundle stays in the case file. It shows which sentence of the decision each
easy-language sentence rests on and who approved it, so the authority can show exactly
what it told the person.

## 3. A typical case: a deputyship

The KESB decides to appoint a deputy (Beistand) for a woman with a mild intellectual
disability. The deputy will manage her money and deal with the bank and the social
insurance offices; she keeps deciding where she lives and how she spends her days. The
decision runs to eight pages.

### Step 1: submit the decision

The case worker who drafted the decision submits it as a PDF or as text and chooses the
level A2 (Leichte Sprache). *Planned:* a field that names the person the letter speaks
to, so that "Sie" in the letter is always her and never the deputy or the authority.

### Step 2: Apertus extracts what must not be lost

The fact sheet lists every item of the operative part, the deputy's name and contact,
the tasks the deputy takes over, what she keeps deciding herself, the fee, and the
appeal: the period of 30 days from notification, the competent court and its address,
the form of the appeal. Facts the decision does not state are marked as absent, so the
letter cannot invent them. Code adds every date, amount, phone number, e-mail and web
address the model missed, and, since 7 October 2026, the period of 30 days, the case
number, identifiers such as the AHV number, and the court's postal address, as facts
that must come back character for character
([rules.md](rules.md#facts-the-most-important-family), "Value kinds").

### Step 3: Apertus writes the letter

The letter follows the reader's questions, for example: "Was hat die KESB entschieden?",
"Was bedeutet das für Sie?", "Was entscheiden Sie weiter selbst?", "Sind Sie nicht
einverstanden?", "Bis wann?", "Wen können Sie fragen?". The legal reasoning is
condensed to the main reasons; everything left out is listed with a reason, for the
case worker to veto.

### Step 4: code checks rules and facts

The same deterministic checks as in the first use case: the easy-language rules, every
must-keep fact with its exact value (FACT-01), and no value the decision does not
contain (FACT-06). A deadline date that moved, a period of 30 days that became 20 or
"einen Monat", a case number with two digits swapped, the court's address without its
street, or a phone number taken from somewhere else, is caught exactly; "zwei Wochen"
for "14 Tage" is not a finding, the periods are equal.

### Step 5: a second, larger Apertus model judges meaning

The judge reports distorted facts, invented statements and unclear references, as in
the first use case. *Planned for decisions:* the letter must stay neutral (no
evaluation of the decision, no "leider"), give no advice beyond what the decision says,
and keep every condition a condition.

### Step 6: flagged sentences are repaired

Only the flagged sentences go back to the model, as in the first use case.

### Step 7: the case worker reviews

The person who drafted the decision knows every fact of the case. What they may not
know are the easy-language rules, and the findings list shows where those are broken.
They approve, edit or reject each block. This review is mandatory for decisions, never
optional.

### Step 8: the letter goes out with the decision

*Planned:* the export carries a fixed notice at the top and the bottom, written by the
authority and not by the model: "Diese Erklärung hilft Ihnen, den Entscheid zu
verstehen. Massgebend ist der Entscheid." (French: "Cette explication vous aide à
comprendre la décision. Seule la décision fait foi."). The pipeline takes minutes, so
the letter can go out together with the decision, while the whole appeal period is
still ahead.

## 4. Other decisions that fit

- KESB: child protection measures, custody, involuntary placement (10-day appeal
  period), deputyships.
- Decisions of social insurance offices (disability insurance, supplementary benefits)
  and court judgments on appeals against them.
- Juvenile and family proceedings involving children.
- For the public: leading decisions of the Federal Supreme Court and cantonal courts as
  easy-language summaries, made from the anonymised, published decision. Leicht·Facile
  does not anonymise; that is a separate step before it.

Penal orders, payment orders, social assistance, school and migration decisions, and
use cases beyond decisions, are sketched in [use-cases.md](use-cases.md).

## 5. Why not a chatbot

| What the authority needs | One chatbot prompt | Leicht·Facile |
|--------------------------|--------------------|---------------|
| The decision never leaves the authority | Runs on a foreign cloud | Runs on infrastructure the authority controls |
| Appeal period, amounts, case number, contacts and the appeal address exactly right | The model is asked to be careful; nobody checks | Checked by code (FACT-01), character for character |
| Nothing invented about a person's case | No check | Values checked by code (FACT-06); statements checked by the judge |
| A neutral letter without advice | No check | Planned judge checks |
| Proof of what the person was told | A chat transcript | The audit bundle in the case file |

## 6. Limits

- The letter is not the decision and has no legal force; the decision prevails. The
  authority stays responsible, and a person who knows the case reviews every letter.
- It gives no legal advice and does not assess the chances of an appeal.
- It does not anonymise, and it does not replace an oral explanation or a review by
  readers from the target group.
- AI in the justice system is sensitive. In the EU, AI that helps a judicial authority
  research and interpret facts and law counts as high-risk (AI Act, Annex III, point 8).
  An explanatory letter that a person reviews and the authority signs is a different
  use, but every court and authority has to assess it under its own rules.
- No professional easy-language versions of decisions are known to us as references.
  Quality would be measured with the rule checker, the fact checks, the judge and
  expert review, on published and anonymised decisions (free to use under article 5
  of the Copyright Act, [sources.md §4](sources.md#4-licensing)) or on decisions the
  team writes.

## 7. What works today and what is planned

Works today, unchanged from the first use case: PDF and text ingest, the fact sheet
with the reader's core questions, code completion of dates, amounts, phone numbers,
e-mail and web addresses, percentages and times, the rule checker with FACT-01 and
FACT-06, the judge, repair, the review UI, the exports with the audit bundle, and the
deployment options. Since 7 October 2026, for this use case: periods such as
30 days, identifiers (case and reference numbers, AHV number, IBAN) and postal
addresses are facts that must come back exactly (`period`, `identifier`, `address`),
found by code, checked by FACT-01 and FACT-06, with the exact string as the repair
suggestion.

Since 8 October 2026, the decision mode (a job option, `mode: decision`, with the person
the letter speaks to and the authority's notice): code finds the operative
part and the appeal instructions (`rules/decision.py`), by their headings or, in a PDF
without headings, by the sentence `Demnach erkennt das Verwaltungsgericht:` and the
paragraph `Gegen diesen Entscheid kann ...`; their values are must-keep whatever the
model marked, the values of the header and the reasoning are background unless a core
answer cites them, and each part gets a fact of its own. FACT-08 blocks a draft that
cites a part in no block or lists it as omitted, and the repair round asks for the
part first. The judge answers SEM-09 (no advice, no evaluation) and SEM-10 (every
period with its start) for a decision; SEM-08 is in the standard judge prompt since
7 October. The authority's notice is the first and the last paragraph of every export
and a banner above the blocks on the review page, not a block; FACT-07 on the export's
lines catches an export without it and a review edit that changed it.

Planned, not built:

- a document-type detector instead of the manual mode;
- a mode that condenses long legal reasoning, with every omission listed.

The checks are specified in
[rules.md](rules.md#fact-checks-for-the-further-use-cases).

### Tested on 7 October 2026

Two decisions went through P2 on CSCS (8B writer, 70B judge), each once with the
decision-mode prompts that exist so far (the partial and the addressee, without
protected segments) and once as a standard job:

- **The team's KESB decision** (`src/leichtfacile/letters/entscheid-beistandschaft-musterwil.txt`,
  1,000 words, 26 hard values). Every identifier, address and the 30 days that the draft
  carried came back exactly. But in decision mode the Understand model computed an end
  of the appeal period ("Die Beschwerdefrist endet am 15. November 2026") that the
  decision does not state; FACT-05 warned about the fact sheet, while FACT-06 let the
  date through because the fact sheet carried it. "Sie" became Lea Muster where the
  deputy was meant (the inventory and the report), and the withdrawn suspensive effect
  and the case number were missing. As a standard job the appeal (30 days, the court)
  was missing altogether. 29 of 29 and 20 of 27 facts were must-keep, the sender's
  address and the dates of the reasoning included, so both jobs stopped on "no
  progress".
- **A published decision** (Verwaltungsgericht Schwyz, III 2022 132, 8 pages, an appeal
  against a deputyship). The placeholders (`A.________`) pass through unchanged and
  read as names. The model proposed only one passage of the reasoning for omission, so
  the code completion made 28 of 30 facts must-keep, among them birth dates, an
  inheritance and a loan; the court's own decision (the appeal dismissed) was not one
  of them. In decision mode the draft presented the KESB's measure as the court's
  decision, gave the deputy's duties to the person concerned, left out the appeal to
  the Federal Supreme Court, and copied the write prompt's style guide into the draft
  as a section of its own. The operative part starts with "Demnach erkennt das
  Verwaltungsgericht:" and holds the appeal instructions as its item 3 ("Gegen diesen
  Entscheid kann innert 30 Tagen seit Zustellung ..."): the markers FACT-08 needs.

What it means for decision mode v1: the operative part and the appeal
instructions must be found by code and protected (FACT-08), not left to the model; the
values of the header and the reasoning must be background facts in decision mode, or
the repair rounds chase dates nobody needs; the prompts must say to copy a period as
written and never compute its end; and a draft must not quote the prompt. The
published decision stays a test input. The demo uses the team's decision, which reads
like a real one and carries the personal data a published one has removed.

## References

- Swiss Civil Code (ZGB), Art. 388 and Art. 450b:
  https://www.fedlex.admin.ch/eli/cc/24/233_245_233/de
- Antener, G., Girard, S., Lichtenauer, A. (2018): Empowerment durch Leichte Sprache.
  Das Projekt «Einfach leicht verständlich». Schweizerische Zeitschrift für
  Heilpädagogik 24 (7-8):
  https://irf.fhnw.ch/entities/publication/62297a1f-6275-4d53-912a-5b7018a044a9/full
- UN Committee on the Rights of Persons with Disabilities, concluding observations on
  the initial report of Switzerland (2022): https://digitallibrary.un.org/record/3970220
- Regulation (EU) 2024/1689 (AI Act), Annex III:
  https://eur-lex.europa.eu/eli/reg/2024/1689/oj
