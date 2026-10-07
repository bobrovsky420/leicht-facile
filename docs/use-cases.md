# Use cases

Status: overview, 6 October 2026. The first two use cases are described step by step
in their own documents, [use-case-canton.md](use-case-canton.md) and
[use-case-decisions.md](use-case-decisions.md). The others are sketched here: what the
document is, which facts must survive, who reviews, and what the checker still needs.
The value kinds `period`, `identifier` and `address` they share exist since 7 October
2026 ([rules.md](rules.md#facts-the-most-important-family), "Value kinds"); the
remaining checks are specified in
[rules.md](rules.md#planned-fact-checks-not-implemented). Companion to
[architecture.md](architecture.md).

## 1. Overview

| # | Use case | Document | Period or date the reader must not miss | Natural reviewer | Status |
|---|----------|----------|-----------------------------------------|------------------|--------|
| 1 | Cantonal administration | Letters, forms, web pages | Dates such as a 31 March deadline | Easy-language writer | Built ([use-case-canton.md](use-case-canton.md)) |
| 2 | Child and adult protection, courts | Decisions | 30 days to appeal, 10 days for involuntary placement | Case worker, court clerk | Partly planned ([use-case-decisions.md](use-case-decisions.md)) |
| 3 | Hospitals and doctors | Discharge letter, report with recommendations | Follow-up dates, how long to take a drug | The physician who signs | Planned (§3) |
| 4 | Housing | Termination of a lease, rent increase | 30 days to contest | Tenants' association, social service, conciliation authority | Planned (§4) |
| 5 | Criminal justice | Penal order (Strafbefehl) | 10 days to object | Public prosecutor's office | Planned (§5) |
| 6 | Debt collection | Payment order (Zahlungsbefehl) | 10 days to object | Debt collection office, debt counselling | Planned (§6) |
| 7 | Social assistance and social insurance | Decisions, conditions, sanctions | Appeal periods, duties to report | Case worker | Close to 1 and 2 (§7) |
| 8 | Schools | Placement and special-education decisions | Appeal periods under cantonal law | School administration | Planned (§8) |
| 9 | Research | Information for study participants | None; rights and risks must survive | Study team, ethics committee | Planned (§9) |
| 10 | Migration | Permit and asylum decisions | Appeal periods, some in working days | Migration office | Partial fit (§10) |
| 11 | Private sector | Letters of insurers, pension funds, utilities | Payment and cancellation dates | The company's writers | As use case 1 (§11) |

## 2. What they share

- The text decides about someone's money, home, health or freedom.
- It carries exact values: dates, amounts, contacts and, above all, a period such as
  "innert 10 Tagen", whose loss costs a right.
- Many of its readers cannot read it: about 844'000 adults in Switzerland have low
  reading skills (PIAAC 2023), and 49 percent of adults have low health literacy
  (HLS19-21).
- Someone can review an easy version before it is used.
- Most of them contain personal data. Data on health, on administrative and criminal
  proceedings and sanctions, and on social assistance are particularly sensitive under
  the Federal Act on Data Protection (FADP, art. 5 lit. c), which makes a deployment on
  the organisation's own infrastructure a requirement rather than an option.

The tool is used in one of two ways:

- **Writer workflow**, as built: the author's side drafts, a professional reviews, the
  text goes out with an audit trail (use cases 1-3, 5, 7-9, 11).
- **Received letters**, planned (PLAN.md, WP12b): a helper or the reader uploads a
  letter someone else wrote. Nobody on the author's side reviews it, so code builds a
  box with every deadline, amount and contact in the letter's own wording, a fixed
  notice says that only the letter counts, and the explanation gives no advice (use
  cases 4 and 6, and any letter a reader brings).

## 3. Patient letters

- **Document.** Discharge letters and reports with recommendations are written for the
  family doctor. The patient receives the same text, or nothing.
- **Why.** 49 percent of adults in Switzerland have low health literacy (HLS19-21,
  Federal Office of Public Health). In Germany, "Was hab' ich?" tested automatically
  created patient letters after hospital stays at the Dresden heart centre
  (2019-2020): patients understood their illness and treatment better, and the Federal
  Joint Committee (G-BA) recommended such letters for routine care.
- **Facts that must survive exactly.** Drug names, doses (`5 mg`), dosing schemes
  (`1-0-1`), how long to take a drug, follow-up dates, warning signs with their
  thresholds ("über 38,5 Grad"), phone numbers.
- **Reviewer.** The physician who signs the discharge letter, before the patient
  leaves.
- **Sovereignty.** Health data are particularly sensitive; the letter stays on the
  hospital's infrastructure. A medical Apertus model exists for the judge:
  Apertus-70B-MeditronFO (EPFL).
- **Works today.** Dates, phone numbers, periods (how long to take a drug, when to
  come back), doses (`5 mg`, `2 Tabletten`), dosing schemes (`1-0-1`) and thresholds
  (`über 38,5 Grad`) are checked facts; the judge looks for invented statements.
- **Needs.** The value kind `medication` (drug names, which need a drug list); the
  check `FACT-09` (a drug's name, dose and scheme in one block); the judge question
  `SEM-08` (an instruction stays an instruction, a recommendation a recommendation); a
  medical judge model.
- **Limits.** A wrong dose is harm, not just a wrong fact: the physician's review is
  mandatory, and the letter gives no advice beyond the report. Whether such software
  is a medical device (Swiss Medical Devices Ordinance, aligned with the EU MDR) must
  be assessed. A tool that rewrites a text the physician signs is closer to
  communication than to diagnosis, but that is a legal assessment still to be made.

## 4. Termination of a lease and rent increases

- **Document.** A landlord terminates a lease on a form approved by the canton, which
  states how the tenant can contest the termination or ask for an extension (art. 266l
  para. 2 OR). A rent increase also needs an official form (art. 269d OR).
- **Why.** The tenant has 30 days from receipt to contest a termination at the
  conciliation authority, and for a lease of unlimited duration also 30 days to ask
  for an extension (art. 273 OR); a rent increase can be contested within 30 days as
  well (art. 270b OR). After that the right is lost.
- **Facts that must survive exactly.** The date the lease ends, the 30-day period and
  its start (receipt), the conciliation authority and its address, the rent amounts.
- **Reviewer.** Rarely the private landlord. More likely: tenants' associations,
  social services and counsellors, the conciliation authority itself, and public or
  cooperative landlords who want their tenants to understand.
- **Mode.** Mostly a received letter (the helper uploads it), or the writer workflow
  at a cooperative or a city's housing department.
- **Works today.** The 30-day period, the date the lease ends, the conciliation
  authority's address and the rent amounts are checked facts.
- **Needs.** The received-letter mode; the judge question `SEM-10` (every period
  keeps its start).
- **Limits.** No legal advice: whether to contest is a question for the tenants'
  association, not for the letter.

## 5. Penal orders

- **Document.** A penal order (Strafbefehl) is a conviction by the public prosecutor
  without a court hearing. 92 percent of convictions for crimes and misdemeanours in
  Switzerland are penal orders.
- **Why.** The person has 10 days to object (art. 354 para. 1 StPO); without an
  objection the order becomes a final judgment. Researchers ask whether people who do
  not object agree with the order, or did not understand it for linguistic or
  cognitive reasons.
- **Facts that must survive exactly.** The sanction (days-fines and their amount, a
  fine, the costs), the 10-day period and its start (notification), where and how to
  object, the case number.
- **Reviewer.** The public prosecutor's office that issued the order, which sends the
  easy-language letter with it, as in use case 2.
- **Sovereignty.** Data on criminal proceedings and sanctions are particularly
  sensitive.
- **Works today.** The sanction's amounts, the 10-day period, the case number and the
  address to object to are checked facts.
- **Needs.** The decision mode of use case 2; the judge questions `SEM-09` (neutral,
  no advice) and `SEM-10`.
- **Limits.** As for all decisions: the order prevails, and whether to object is legal
  advice the letter does not give.

## 6. Debt collection payment orders

- **Document.** A payment order (Zahlungsbefehl) from the debt collection office
  demands payment of a claim.
- **Why.** The debtor has 10 days from notification to object (Rechtsvorschlag, art. 74
  SchKG), orally or in writing; otherwise the creditor can continue the collection.
  Debt hits many of the readers easy language is for.
- **Facts that must survive exactly.** The creditor, the claimed amount with interest
  and costs, the 10-day period and its start, how and where to object, the case
  number.
- **Reviewer.** The debt collection office, which can hand out an easy-language sheet
  with the case's values; or a debt counselling service for an order a client brings.
- **Works today.** The claimed amount, the 10-day period, the case number and the
  office's address are checked facts.
- **Needs.** The decision mode or the received-letter mode.
- **Limits.** The payment order does not say whether the claim is justified, and
  neither may the letter.

## 7. Social assistance and social insurance decisions

- **Document.** Decisions of social services and social insurances (disability
  insurance, supplementary benefits, unemployment insurance): benefits, conditions,
  duties to report changes, sanctions.
- **Why.** A missed duty to report can cost benefits; a missed appeal period, the
  decision itself. Many readers belong to the target group.
- **Facts that must survive exactly.** Amounts, start and end dates, duties with their
  deadlines, the objection or appeal period, contacts, the case number.
- **Reviewer.** The case worker who wrote the decision: the workflows of use cases 1
  and 2 apply directly.
- **Sovereignty.** Data on social assistance are particularly sensitive.
- **Works today.** Amounts, dates, periods and the case number are checked facts.
- **Needs.** The decision mode.

## 8. School and special-education decisions

- **Document.** Decisions on school placement, special-education measures and
  disciplinary measures.
- **Why.** They reach parents with low reading skills or still learning German or
  French, and they set appeal periods under cantonal law.
- **Facts that must survive exactly.** The measure and its start, the school and
  contacts, the appeal period and the appeal authority.
- **Reviewer.** The school administration or the school psychology service.
- **Works today.** The start of the measure, the appeal period and the appeal
  authority's address are checked facts.
- **Needs.** The decision mode.

## 9. Information for study participants

- **Document.** Participant information and consent forms for research with people,
  usually written from the templates of swissethics.
- **Why.** The Human Research Act requires that participants be informed orally and in
  writing, in an understandable form (art. 16 para. 2 HRA). People with low reading
  skills or an intellectual disability should be able to take part too.
- **Facts that must survive exactly.** The right to withdraw at any time without giving
  reasons, risks and burdens, the number and length of visits, compensation,
  insurance, contacts.
- **Reviewer.** The study team; the ethics committee approves the final text.
- **Works today.** The number and length of visits (periods), doses and quantities,
  compensation and contacts are checked facts.
- **Needs.** The judge question `SEM-08` (a right stays a right, a risk is not
  softened).
- **Limits.** The easy version supplements the approved information and needs the
  ethics committee's approval like any other document for participants.

## 10. Migration decisions (partial fit)

- **Document.** Decisions on residence permits, integration agreements and asylum.
- **Why.** High stakes and appeal periods, some counted in working days.
- **Facts that must survive exactly.** Periods (with working days kept apart from
  days), the authority and its address, the case number, conditions.
- **Partial fit.** Many readers need their own language, not easier German or French,
  and Leicht·Facile does not translate ([architecture.md §1](architecture.md#1-what-it-is),
  non-goals). An easy version still helps readers who know some German or French, and
  interpreters can work from it.
- **Works today.** Periods are checked facts, and working days never pass as days.
- **Needs.** The decision mode.

## 11. Letters of insurers, pension funds and utilities

- **Document.** Terms, premium and benefit letters, pension certificates, bills.
- **Fit.** The workflow of use case 1, run by the company's own writers; customer data
  stay on the company's infrastructure.
- **Limits.** Not used for demos or evaluation: the texts are protected by copyright
  ([sources.md §3](sources.md#3-demo-documents-no-easy-language-version)).

## 12. What the further use cases need

| Need | Use cases | Specified in |
|------|-----------|--------------|
| Periods as a checked value kind | 2, 4-8, 10 | Built 7 October 2026: [rules.md](rules.md#facts-the-most-important-family), `period` |
| Identifiers (case and reference numbers, AHV number, IBAN) | 2, 5-7 | Built 7 October 2026: rules.md, `identifier` |
| Postal addresses (where to appeal or object) | 2, 4-6, 8, 10 | Built 7 October 2026: rules.md, `address` |
| Doses, dosing schemes, drug names | 3, 9 | `quantity` and `schedule` built 7 October 2026 (rules.md, Facts); `medication` and `FACT-09` planned |
| The decision mode: addressed person, fixed notice, operative part and appeal instructions kept | 2, 5-8, 10 | [use-case-decisions.md §7](use-case-decisions.md#7-what-works-today-and-what-is-planned); rules.md: `FACT-07`, `FACT-08` |
| The received-letter mode | 4, 6 | PLAN.md WP12b |
| Obligations, conditions and the start of periods kept; no advice | all | rules.md: `SEM-08`, `SEM-09`, `SEM-10` |
| A medical judge model | 3 | Apertus-70B-MeditronFO |

## References

- Federal Office of Public Health: health literacy survey Switzerland 2019-21
  (HLS19-21-CH, with Careum).
- "Was hab' ich?": patient letters after hospital stays (PASTA, Dresden heart centre,
  2019-2020); Deutsches Ärzteblatt, "Leicht verständliche Patientenbriefe verbessern
  die Gesundheitskompetenz":
  https://www.aerzteblatt.de/nachrichten/132399/Leicht-verstaendliche-Patientenbriefe-verbessern-die-Gesundheitskompetenz
- Beobachter, "Strafbefehle machen 92 Prozent aller Schweizer Urteile aus":
  https://www.beobachter.ch/gesetze-recht/strafbefehle-machen-92-aller-schweizer-urteile-aus-staatsanwalte-verhangen-immer-mehr-freiheitsstrafen-553045
- Swiss Code of Obligations (OR, SR 220), art. 266l, 269d, 270b, 273; Criminal Procedure
  Code (StPO, SR 312.0), art. 354; Debt Enforcement and Bankruptcy Act (SchKG, SR
  281.1), art. 74; Human Research Act (HRA, SR 810.30), art. 16; Federal Act on Data
  Protection (FADP, SR 235.1), art. 5: https://www.fedlex.admin.ch
- EPFL LiGHT, MeditronFO models: https://huggingface.co/collections/EPFLiGHT/meditronfo
