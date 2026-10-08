# Use cases

Status: overview, 6 October 2026; why only Apertus fits (§2) and tax letters (§12)
added 7 October 2026. The first two use cases are described step by step
in their own documents, [use-case-canton.md](use-case-canton.md) and
[use-case-decisions.md](use-case-decisions.md). The others are sketched here: what the
document is, which facts must survive, who reviews, and what the checker still needs.
The value kinds `period`, `identifier` and `address` they share exist since 7 October
2026 ([rules.md](rules.md#facts-the-most-important-family), "Value kinds"); the
checks built for them since are listed in
[rules.md](rules.md#fact-checks-for-the-further-use-cases). Companion to
[architecture.md](architecture.md).

## 1. Overview

| # | Use case | Document | Period or date the reader must not miss | Natural reviewer | What keeps the text inside | Status |
|---|----------|----------|-----------------------------------------|------------------|----------------------------|--------|
| 1 | Cantonal administration | Letters, forms, web pages | Dates such as a 31 March deadline | Easy-language writer | Nothing for a web page; official secrecy for a letter to a named person | Built ([use-case-canton.md](use-case-canton.md)) |
| 2 | Child and adult protection, courts | Decisions | 30 days to appeal, 10 days for involuntary placement | Case worker, court clerk | Official secrecy; health, family and finances | Partly planned ([use-case-decisions.md](use-case-decisions.md)) |
| 3 | Hospitals and doctors | Discharge letter, report with recommendations | Follow-up dates, how long to take a drug | The physician who signs | Medical secrecy; health data | Planned (§3) |
| 4 | Housing | Termination of a lease, rent increase | 30 days to contest | Tenants' association, social service, conciliation authority | The adviser's client data | Planned (§4) |
| 5 | Criminal justice | Penal order (Strafbefehl) | 10 days to object | Public prosecutor's office | Official secrecy; criminal proceedings | Planned (§5) |
| 6 | Debt collection | Payment order (Zahlungsbefehl) | 10 days to object | Debt collection office, debt counselling | Official secrecy; the adviser's client data | Planned (§6) |
| 7 | Social assistance and social insurance | Decisions, conditions, sanctions | Appeal periods, duties to report | Case worker | Social insurance confidentiality; social assistance | Close to 1 and 2 (§7) |
| 8 | Schools | Placement and special-education decisions | Appeal periods under cantonal law | School administration | Official secrecy; children's health | Planned (§8) |
| 9 | Research | Information for study participants | None; rights and risks must survive | Study team, ethics committee | Nothing for the information sheet itself | Planned (§9) |
| 10 | Migration | Permit and asylum decisions | Appeal periods, some in working days | Migration office | Official secrecy; asylum proceedings | Partial fit (§10) |
| 11 | Private sector | Letters of insurers, pension funds, utilities | Payment and cancellation dates | The company's writers | Customer data; health insurers' and pension funds' duty of confidentiality | As use case 1 (§11) |
| 12 | Tax administration | Assessments, reminders, payment plans | 30 days to object, payment dates | The tax office's writers, debt counselling | Tax secrecy | Close to 1 (§12) |

The column "What keeps the text inside" names the secrecy or the kind of data that rules
out a foreign cloud; [§2](#why-only-apertus) gives the legal basis and why that leaves
Apertus as the only model.

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
  the Federal Act on Data Protection (FADP, art. 5 lit. c) and the cantonal data
  protection laws, and most of the texts are under a secrecy obligation as well. That
  makes a deployment on infrastructure the organisation controls a requirement rather
  than an option, and leaves Apertus as the only model that fits
  ([below](#why-only-apertus)).

The tool is used in one of two ways:

- **Writer workflow**, as built: the author's side drafts, a professional reviews, the
  text goes out with an audit trail (use cases 1-3, 5, 7-9, 11, 12).
- **Received letters**, planned (PLAN.md, WP12b): a helper or the reader uploads a
  letter someone else wrote. Nobody on the author's side reviews it, so code builds a
  box with every deadline, amount and contact in the letter's own wording, a fixed
  notice says that only the letter counts, and the explanation gives no advice (use
  cases 4, 6 and 12, and any letter a reader brings).

### Why only Apertus

For a public web page, any good model would do. For almost every use case above, the
text names a person, and four conditions follow one after the other.

1. **The text stays inside the organisation.** Every authority is bound by official
   secrecy (art. 320 StGB), doctors by professional secrecy (art. 321 StGB), tax
   offices by tax secrecy (art. 110 DBG), social insurances, basic health insurers
   among them (art. 1 KVG), by their duty of confidentiality (art. 33 ATSG), pension
   funds by art. 86 BVG, banks by art. 47 BankG. Data on health, social assistance and
   administrative or criminal proceedings are particularly sensitive (FADP art. 5 lit.
   c, and likewise the cantonal data protection laws). In November 2025 the cantonal
   data protection commissioners (privatim) resolved that public bodies may hand such
   data to international cloud services such as Microsoft 365 only if they encrypt it
   themselves and the provider has no key; US providers can be compelled to hand over
   data even from Swiss data centres (CLOUD Act). A model has to read the text in
   clear, so a model service can never meet that condition: chatbots and model APIs
   on foreign clouds are out. (The last step is our reasoning; privatim does not mention
   language models.)
2. **The organisation runs the model itself**, on its own servers, air-gapped, or at a
   Swiss operator under its contract. That needs open weights; closed models stay in
   their makers' hands, including the on-premise offers some vendors make.
3. **The organisation can account for what the model learned.** An authority that
   sends a text a model helped to write must be able to say what that model was
   trained on and how the data was collected. Llama, Gemma, Qwen and Mistral publish
   their weights but not their training data.
4. **The model is Swiss.** The organisation depends on no foreign supplier for the
   model, its documentation or its development, which is what the Federal Council
   means by digital sovereignty: the capacity to act in the digital space and to
   monitor it (report of 26 November 2025). The few fully open models with German,
   French and Italian, EuroLLM and SmolLM3 among them, are built and trained abroad.

Apertus meets all four. Its weights, the scripts that rebuild its training data and
its training code are published. Website opt-outs in force in January 2025 were
applied to older crawls as well, and e-mail addresses, IP addresses and IBANs were
replaced in the data. It was built by EPFL, ETH Zurich and CSCS with due
consideration to Swiss data protection and copyright law, trained on the Alps
supercomputer in Lugano on more than 1,000 languages, with dedicated Swiss German and
Romansh data, and released under Apache 2.0 with an acceptable use policy. Swisscom
and Infomaniak serve Apertus 1.5 70B in Switzerland; the 8B runs on one GPU in the
organisation's own building
([architecture.md §10](architecture.md#10-deployment-and-sovereignty)). The Canton of
Ticino already runs Apertus in-house to translate sensitive government documents. The
hackathon demo runs on the CSCS inference API, which serves research, not
administrations.

For the use cases that name a person, Apertus is therefore not one option among
several: it is the only model that meets all four conditions. Conditions 1 to 3 follow
from the law and from accountability; condition 4 is the sovereignty choice. An
authority that drops it is left with a short list of foreign, fully open models; one
that also drops condition 3 has many open-weight models to choose from, but cannot say
what they learned.

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
  (`über 38,5 Grad`) are checked facts; the judge looks for invented statements and
  asks SEM-08 (an instruction stays an instruction, a recommendation a
  recommendation). Since 8 October 2026 the drug names too: for a source with a dose
  the fact sheet names each medication (the value kind `medication`), FACT-01 asks for
  every name, and FACT-09 keeps each medication in one block with its dose, scheme and
  duration, so a reader cannot pair a dose with the wrong drug. The write prompt asks
  for one list item per medication.
- **Needs.** A drug list (for instance the Swissmedic list of authorised medicines),
  so that code finds a medication the model did not name and FACT-06 a name the
  draft invented; a medical judge model.
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
- **Sovereignty.** The letter names the tenant, the flat and the rent. A social
  service that uploads it is bound by official secrecy, a counsellor by the duty to
  keep a client's affairs confidential.
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
- **Sovereignty.** The debt collection office is bound by official secrecy; a debt
  counselling service keeps its clients' debts confidential.
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
- **Sovereignty.** Special-education measures rest on a child's health and
  development; the school administration is bound by official secrecy.
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
- **Sovereignty.** Permit and asylum decisions describe a person's family, health and
  reasons for flight; the migration office is bound by official secrecy.
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
- **Sovereignty.** Basic health insurers are bound by the duty of confidentiality of
  art. 33 ATSG, pension funds by art. 86 BVG, banks by banking secrecy (art. 47
  BankG).
- **Limits.** Not used for demos or evaluation: the texts are protected by copyright
  ([sources.md §3](sources.md#3-demo-documents-no-easy-language-version)).

## 12. Tax letters

- **Document.** Assessments (Veranlagungsverfügung), reminders to file the return,
  payment reminders and payment plans of cantonal and municipal tax offices.
- **Why.** A return not filed after a reminder is assessed at the office's discretion,
  an assessment can be contested only within 30 days of notification (art. 132 DBG for
  the direct federal tax; cantonal laws likewise), and a late payment costs interest.
  Every household gets these letters, including every reader easy language is for.
- **Facts that must survive exactly.** Tax amounts and instalments, due dates, the
  interest rate, the tax number and the payment reference, the IBAN, the 30-day period
  and its start, the office's address and phone number.
- **Reviewer.** The tax office's writers, for its standard letters (the workflow of use
  case 1); a debt counselling service for a letter a client brings.
- **Sovereignty.** Tax secrecy (art. 110 DBG, and the cantonal tax laws) binds everyone
  who works on an assessment. A household's income, wealth and debts may not go to a
  foreign cloud.
- **Works today.** Amounts, dates, percentages, periods, the tax number, the IBAN and
  the office's address are checked facts. The printable letter for the image input
  test is a tax reminder of this kind (`data/examples/print/`).
- **Needs.** Nothing new for the writer workflow; the received-letter mode and image
  input (PLAN.md, WP12) for a letter a client brings on paper.
- **Limits.** No tax advice: whether an assessment is right is a question for the tax
  office or an adviser, not for the letter.

## 13. What the further use cases need

| Need | Use cases | Specified in |
|------|-----------|--------------|
| Periods as a checked value kind | 2, 4-8, 10, 12 | Built 7 October 2026: [rules.md](rules.md#facts-the-most-important-family), `period` |
| Identifiers (case and reference numbers, AHV number, IBAN, tax number) | 2, 5-7, 12 | Built 7 October 2026: rules.md, `identifier` |
| Postal addresses (where to appeal or object) | 2, 4-6, 8, 10, 12 | Built 7 October 2026: rules.md, `address` |
| Doses, dosing schemes, drug names | 3, 9 | `quantity` and `schedule` built 7 October 2026, `medication` and FACT-09 8 October 2026 (rules.md, Facts); a drug list open |
| The decision mode: addressed person, fixed notice, operative part and appeal instructions kept | 2, 5-8, 10 | [use-case-decisions.md §7](use-case-decisions.md#7-what-works-today-and-what-is-planned); rules.md: `FACT-07`, `FACT-08` |
| The received-letter mode | 4, 6, 12 | PLAN.md WP12b |
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
- Swiss Criminal Code (StGB, SR 311.0), art. 320, 321; Federal Act on Direct Federal
  Taxation (DBG, SR 642.11), art. 110, 132; ATSG (SR 830.1), art. 33; KVG (SR 832.10),
  art. 1; BVG (SR 831.40), art. 86; Banking Act (BankG, SR 952.0), art. 47:
  https://www.fedlex.admin.ch
- privatim, resolution on outsourcing data processing to international cloud services
  (18 November 2025):
  https://www.privatim.ch/wp-content/uploads/2025/11/20251124_privatim_Resolution-Hyperscaler_DE.pdf
- Federal Office of Justice, report on the US CLOUD Act (17 September 2021):
  https://www.newsd.admin.ch/newsd/message/attachments/92795.pdf
- Federal Council, digital sovereignty (26 November 2025):
  https://www.admin.ch/en/newnsb/2VPWG78YrVs4eAVeiklQx
- Apertus 1.5 model card: https://huggingface.co/swiss-ai/Apertus-v1.5-8B; Apertus
  technical report (arXiv 2509.14233): https://arxiv.org/abs/2509.14233; acceptable use
  policy: https://github.com/swiss-ai/apertus-legal/tree/main/apertus_1.5
- ETH Zurich, press release on Apertus (2 September 2025):
  https://ethz.ch/en/news-and-events/eth-news/news/2025/09/press-release-apertus-a-fully-open-transparent-multilingual-language-model.html
- CSCS, Apertus 1.5 (24 July 2026), with the Ticino translation service:
  https://www.cscs.ch/science/computer-science-hpc/2026/apertus-15-building-the-next-generation-of-open-ai-infrastructure
- Fully open models built abroad: EuroLLM-22B (arXiv 2602.05879), SmolLM3
  (https://huggingface.co/HuggingFaceTB/SmolLM3-3B)
