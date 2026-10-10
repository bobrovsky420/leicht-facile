# Use case: a cantonal administration

Status: scenario, 5 October 2026. Companion to [architecture.md](architecture.md),
which describes the mechanics behind each step referenced here. A second use case,
letters that accompany decisions of child and adult protection authorities and courts,
is in [use-case-decisions.md](use-case-decisions.md); all use cases at a glance are in
[use-cases.md](use-cases.md).

## 1. Who and why

The communications office of a Swiss canton. Federal disability law (art. 14 BehiG)
and the UN Convention on the Rights of Persons with Disabilities ask authorities for
accessible information, and cantons have begun to publish important information in
Leichte Sprache; Zurich's voting information has been available in Leichte Sprache
since September 2025. Today one or two trained writers produce those versions by hand.
A two-page letter takes them half a day (the team's assumption, until a writer's own
figure replaces it): reading, deciding what to keep, rewriting, checking every number
against the original, and formatting the result.

The office does not want a machine that publishes texts. It wants its writers to
spend their time reviewing instead of drafting, and it wants proof that nothing
important was lost or invented along the way.

## 2. Setup, done once by IT

IT runs one container on the canton's own infrastructure. The container needs exactly
one outbound connection: an Apertus endpoint. That endpoint is either a GPU server the
canton operates with vLLM, or a Swiss-hosted Apertus service. Nothing leaves the
canton's network, there are no accounts with foreign providers, and there is no
telemetry. Documents and review records stay on a volume the canton controls.

See [architecture.md §10](architecture.md#10-deployment-and-sovereignty) for the three
deployment profiles and the hardware involved.

## 3. A typical case: the premium-reduction letter

The social insurance office has a standard letter about Prämienverbilligung (health
insurance premium reduction). Two pages, legal tone. It tells residents how to apply,
what the income limit is, that the deadline is 31 March, and whom to call. The
communications office wants a Leichte Sprache version for the website and as an
enclosure to the letter.

### Step 1: submit the document

The writer pastes the text, uploads the PDF, or enters the URL of the web page. They
choose German and the level: A2 (Leichte Sprache) or B1 (Einfache Sprache).

### Step 2: Apertus reads the letter and writes a fact sheet, not a draft

Before anything is rewritten, the model extracts what must survive: the deadline, the
income limit, the amounts, the phone number, the obligations, the rights, and the
answers to the reader's core questions (What is this? What must I do? By when? What
does it cost? Whom do I ask?). Every fact points back to the sentence in the letter
it came from. Facts the letter does not state are marked as absent, so the writer
cannot invent an answer later.

This fact sheet is the reference for every later check.

### Step 3: Apertus writes the draft against the fact sheet

The model orders the content by what matters to the reader, uses questions as
headings, writes one idea per sentence, explains hard terms in a glossary, and
records what it left out and why. Every draft sentence is linked to the source
sentences it was derived from.

### Step 4: plain code checks the countable rules

No model is involved in this step. The checker verifies sentence length, passive
voice, genitive, Konjunktiv, numbers as digits, `ss` instead of `ß`, Swiss date and
phone formats, and Mediopunkt in long compounds. Above all it verifies that every
must-keep fact appears in the draft with the right value. If the deadline silently
became 30 March, this check catches it exactly, not approximately.

The rule catalogue is in [rules.md](rules.md).

### Step 5: a second, larger Apertus model judges meaning

The judge answers only what code cannot: is a fact distorted, does the draft claim
something the letter never said, is there a metaphor, an unclear "it", or assumed
knowledge the reader may not have. The judge reports; it never rewrites.

### Step 6: flagged sentences are repaired

Only the flagged sentences go back to the model, each with its findings and the
facts it must convey. Up to three rounds. Every round is kept, so the writer can see
what changed and why.

### Step 7: the writer reviews

This is where the tool earns its keep. The writer sees the original and the draft
side by side. Clicking a draft sentence highlights the source sentences it came from.
A checklist shows every fact as present, missing or distorted. The remaining rule
findings are listed with suggestions. The omissions are listed with the model's
reasons, so the writer can veto a decision such as "left out: appeal procedure".
The writer approves, edits or rejects each block.

### Step 8: export

Markdown or HTML formatted for Leichte Sprache (one sentence per line, short lines),
plus a JSON bundle containing the source, the fact sheet, the final draft with
provenance, all findings, and the writer's decisions. That bundle is the audit
trail. If a resident later disputes the easy-language version, the office can show
which source sentence each statement rests on and who approved it.

### Step 9: the target-group test stays with the canton

Certification as Leichte Sprache requires review by readers from the target group.
The tool does not replace that step. It delivers a draft worth testing in minutes
instead of hours, with the fact checking already done, and exports it in the format
the test readers need.

## 4. Why this is not a translator, and why one chatbot cannot do the job

A translator turns sentence A into sentence B. Pasting the letter into a chatbot
with "rewrite this in Leichte Sprache" does exactly that. It is also the baseline
condition P0 in the evaluation. For an administration that has to publish the result
and defend it, that approach falls short in ways no prompt can fix:

| What the office needs | One chatbot prompt | Leicht·Facile |
|-----------------------|--------------------|---------------|
| Certainty that every deadline, amount, obligation and contact survived | The model is asked to be careful; nobody checks | Facts are extracted first into a fact sheet, then verified in the draft by exact code (rule FACT-01) |
| Knowing what was left out and why | Omissions are silent | Every omission is listed with a reason, for the writer to veto |
| Proof of where each sentence comes from | None | Every block links to the source sentences it was derived from |
| Compliance with the published rules | The rules sit in the prompt, so the model grades its own work | Countable rules are checked deterministically; only meaning is judged, and by a different, larger model |
| An audit trail for publication | A chat transcript | A JSON bundle: source, fact sheet, draft, findings, reviewer decisions |
| A review workflow for the writers | Copy and paste | Side-by-side review with provenance, fact checklist and per-block decisions |

Two further differences go beyond text quality. Easy language reorders content by
what the reader needs first and turns headings into questions; that is a planning
task, not a translation. And the chatbots people reach for run on foreign clouds,
which rules them out for letters containing personal data. Leicht·Facile runs on the
canton's own infrastructure against an Apertus endpoint.

The claim is measured, not asserted: the evaluation compares the single-prompt
baseline (P0) with the full pipeline (P2) on the same documents and reports fact
coverage, invented statements and rule violations for both. See
[architecture.md §9](architecture.md#9-evaluation).

## 5. What changes for the office

- Writers stop drafting from scratch and start reviewing, which is faster and is
  where their expertise matters most.
- Fact fidelity is checked mechanically on every document. No manual process
  guarantees that.
- Every published easy-language text carries provenance and a review record.
- Costs are predictable: tokens on hardware the canton controls. The evaluation in
  the technical report shows what the 8B model achieves alone and what the 70B judge
  adds, so the deployment can be sized accordingly.
- French (FALC) and Italian versions follow the same pipeline, each simplified from
  its own original, so the three language versions can be checked against each other
  for consistency.

## 6. What it does not do

- It does not certify texts, does not translate between languages, and does not
  replace the target-group review.
- The prototype has no login. In production it sits behind the organisation's
  reverse proxy like any other internal tool.
- The 8B model may not reach true A2 quality on every document. That is exactly what
  the evaluation measures, and the report states the result rather than claiming
  otherwise.
