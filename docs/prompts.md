# Prompts: design notes and change log

Status: version 1, 5-6 October 2026, written and tested without the CSCS endpoint (see
"Tested so far"). Companion to [architecture.md](architecture.md) §4 and §6.

The templates live in `src/leichtfacile/llm/prompts/<lang>/` as Jinja2 files:
`understand.md`, `write.md`, `judge.md`, `repair.md`, `baseline.md`, plus few-shot
examples in `examples/`; German also has `baseline_zh.md`, the Canton of Zurich's prompt
for the second baseline (below). Every rendered prompt is identified by a short hash of its
template file; the hash is stored in each job's summary and audit bundle, so a result
can always be traced to the exact prompt that produced it.

## Design choices

| Choice | Why |
|--------|-----|
| Instructions in the language of the document | The model reads and writes German for German documents and French for French ones; instructions in the same language avoid another language leaking into fact texts, omission reasons and glossary entries that the reviewers read. The French templates (`prompts/fr/`) follow the German ones line by line, with French JSON examples and two French few-shot pairs on the same topics. The few words code adds around the items (fact sheet headings, "Vorschlag:" or "Suggestion :", the problem lines of a repair round) come from one table per language (`pipeline/labels.py`). Italian has no templates yet. |
| A concrete JSON example in each prompt instead of the JSON schema | Small models copy a filled example more reliably than they follow a schema, and the example is a fraction of the tokens. The pydantic models still validate every answer; the validation error goes back to the model once (`llm/json_out.py`). |
| Lenient parsing of the answer (`pipeline/models.py`) | An 8B model gets details wrong that do not matter: `s4` instead of `s0004`, `Deadline` instead of `deadline`, a string where a list was asked for. These are normalised; only real problems (no blocks, an empty text) count as invalid. A complete answer without the `facts` list, seen on a page with nothing countable, is read as a fact sheet with no model facts; code completion adds the countable values. On long pages the 8B abbreviates a run of ids as a range (`"s0064" bis "s0087"`), which is not JSON: the parser writes the range out, repairs trailing and missing commas, closes an object the model forgot to close before a top-level key (the schema's fields say where) and turns the straight quote that ends a German quotation inside a string into the closing German one; an answer that is still broken is reported with the position of the error, never replaced by an object from inside it. |
| The style guide is generated from the rule registry (`rules/styleguide.py`) | The writer is asked for exactly what the checker checks, with the thresholds of the chosen level. The guide changes when a rule changes; no second copy can drift. |
| Few-shot examples written by the team, on topics outside the evaluation set | The cantonal pages may not be reproduced in a public repository (docs/sources.md §4). Two short synthetic pairs show the style: a decision on a resident parking permit and a dog-tax letter. The JSON examples in the prompts use the dog tax too. In local runs, details of examples on nearby topics leaked into drafts ("Steueramt", "Gemeinde" for the Sozialversicherungsstelle); examples on distant topics make such a leak obvious and keep the evaluation clean. A test checks that the examples break no `error` rule. On the Public AI 8B without thinking, 4 of 12 dev drafts were the write prompt's JSON example itself, word for word (6 October); the form now comes before the style examples and the document last, and code recognises an answer that copies the examples (below). |
| Sentence ids in the source (`[s0004]`) and block ids in drafts (`[b007]`) | Provenance and fact references are by id; the model cites, code verifies that the ids exist (FACT-03, FACT-05). |
| Plan first, then write | Easy language reorders content by what the reader needs; the write prompt asks for the reader's questions as headings before the text. The thinking models do the planning in their reasoning. |
| The judge reports, it never rewrites | Its answer is a list of findings with fact and block ids; repairs go back to the writer. This keeps the judge an independent instrument for the evaluation. |
| Repair sees only the flagged blocks, their problems and the facts they must keep | Smaller prompt, and the rest of the draft cannot be damaged. The rule findings come with the checker's suggestion ("Vorschlag: 31. März 2026"), which is usually right. |
| The baseline prompt (P0) is one sentence | It is what a user types into a chatbot: "Schreiben Sie diesen Text in Leichter Sprache:", in French "Écrivez ce texte en FALC :". |
| The second baseline (P0-ZH) is the Canton of Zurich's prompt, verbatim | A juror can call a one-sentence baseline a strawman; the best public Swiss prompt on the same model is the fair comparison. `prompts/de/baseline_zh.md` holds the system message, the user template, the rule list and the two completeness lines of `simply-simplify-language` v1.6.0 (Canton of Zurich, MIT, THIRD_PARTY_NOTICES.md) without a change; the licence note is a Jinja comment and never reaches the model. Two variants: `complete` (keep every fact, our task) and `condensed` (essentials only, their default for Leichte Sprache). Settings as P0: no thinking, temperature 0.3, 6000 tokens. Post-processing as in their app: the text between the `<leichtesprache>` tags, ß written as ss. Their `strip_markdown` is not applied: it deletes every underscore and would break web and e-mail addresses, so applying it would measure their regex, not their prompt. An answer without the tags is used whole and noted in the job summary. German only: their app has no French prompt. |

## Stage settings

| Stage | Thinking (default) | Temperature | max_tokens without / with thinking |
|-------|--------------------|-------------|------------------------------------|
| understand | on | 0.1 | 6000 / 12000 |
| write | off | 0.3 | 8000 / 16000 |
| judge | on | 0.0 | 6000 / 12000 |
| repair | off | 0.2 | 6000 / 12000 |
| baseline (P0, P0-ZH) | off | 0.3 | 6000 / 12000 |

`LLM_THINKING_STAGES` overrides the first column. Thinking models need a generous
`max_tokens`: the reasoning can be several times longer than the answer. When the
reasoning runs out of tokens before the answer, the stage is answered once more without
thinking.

## Code around the prompts

- **Fact sheet completion.** After Understand, code adds a fact for every date, amount,
  phone number, e-mail address, web address, percentage and time in the source that no
  fact carries (`origin: code`), and since 7 October 2026 for every period (`innert 30
  Tagen`, as the value `30 Tage`), identifier (case number, AHV number, IBAN, as
  written) and postal address (docs/rules.md, "Value kinds"). Values in passages the
  model marked as droppable become background facts; all others must be kept. The first
  local run showed why: the model listed 3 facts for a letter with 11 checkable values.
  The prompts do not mention the new kinds (no prompt change before the freeze); what
  the model writes as a value for them (`30 Tage`, `2026-0042`) is parsed as text.
  Numbers measured before 7 October use the narrower hard-fact definition; the final
  run recomputes every row.
- **Fact linking.** A block that contains a fact's exact value is linked to that fact by
  code, so FACT-02 does not depend on the model's bookkeeping.
- **Copied examples.** An answer whose sentences are mostly from the prompt's own
  examples (the JSON form, the few-shot pairs: two or more, and more than half of
  them) is not a draft of the document. Code
  recognises it (`stages.example_keys`: the sentences of the rendered prompt without
  its document, normalised) and sends it back once with a message in the document's
  language; a second copy fails the stage. Understand, write and repair are checked.
  A sentence about the examples' topics (a dog, a parking permit), or with one of the
  examples' values (their phone numbers, dates, amounts and hours, read from the
  rendered prompts), in a document that has none is example content too, so
  paraphrases are caught: the answer is sent back
  once, and the sentences a second answer still has are dropped in code, since one
  such sentence is not worth a failed stage. On CSCS the 8B wrote dog-tax sentences
  into a page about EL costs with only 2 of 12 sentences verbatim.
- **Values not in the document.** A repair answer with a date, amount, phone number,
  e-mail address, web address, percentage or time that neither the source nor the
  fact sheet contains (the check of rule FACT-06) is sent back once with the values
  named, in the document's language. The second answer is used as it is, and when it
  is not valid JSON the first one is: the guard never fails a round. What remains is
  FACT-06's finding and the next round's problem. The write stage is not
  checked this way: a second write call is long, and FACT-06 plus a repair round do
  the same job.
- **Response cache.** An answer that cannot be used (no valid JSON, a copy of the
  example) is dropped from the response cache, so a rerun of a failed pair asks the
  model again instead of replaying the same unusable answer; the evaluation reruns
  failed pairs with the cache on.
- **Control tokens.** Servers that print special tokens (llama.cpp with `-sp`) also
  print `<|assistant_end|>`; the client strips every `<|...|>` token from answers.

## Tested so far

No CSCS key yet. The prompts were tested against Apertus v1.5 8B through llama.cpp on a
laptop GPU (RTX 4060, 8 GB): the community text-only conversion
`Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF` (4-bit, unofficial, derived from
`andreasmartin/apertus-v1.5-8b-text`). Numbers from this setup are labelled as such and
never mixed with CSCS results.

First full run, on the team's sample letter (`data/examples/sources/`), 6 October 2026:

| Stage | Thinking | Output tokens | Time | Result |
|-------|----------|---------------|------|--------|
| understand | on | 3,291 | 90 s | Good fact sheet: core questions, 9 facts, a hard term, an omission; one invented segment id (caught by FACT-05). Code completion added 8 facts with exact values. |
| write | on | 12,408, then 11,451 | 24 min | The first answer hit `max_tokens` while still reasoning; the JSON repair round succeeded. The draft paraphrased the original: 50 percent passive, Amstad readability 45. |
| judge | on | 12,000 twice | 23 min | Both answers hit `max_tokens` while still reasoning: no JSON, the job failed. |
| write (repeat) | off | 754 | 28 s | Easy language: question headings, `Sie`, lists, 7.2 words per sentence, no passive. Dropped the income limits, which FACT-01 flags for repair. |

Consequences, all in the code now: writing without thinking by default, thinking per
stage configurable, a fallback without thinking when the reasoning runs out of tokens,
and jobs that survive a failing judge or repair round.

Second full run, thinking for understand only (judge on the same local 8B, without
thinking), 6 minutes in total:

| Draft | Blocks | Facts found by code | Passive | Words per sentence |
|-------|--------|---------------------|---------|--------------------|
| v1 (write) | 10 | 4 of 10 | 0 % | 8.8 |
| v2 (repair 1) | 15 | 6 of 10 | 0 % | 8.2 |
| v3 (repair 2) | 19 | 10 of 10 | 0 % | 9.4 |

The repair loop did what it is for: the writer had left out who is entitled and the
income limits; FACT-01 named the missing values, and two repair rounds put them back.
Runs through the web API of the container (the same image `make run` starts) were less
lucky: given eight flagged blocks and ten missing facts at once, the 4-bit model
rewrote the blocks without adding the facts, and the loop stopped after one round
without progress, leaving the missing facts as FACT-01 errors for the reviewer. Hence
version 3: blocking problems first, missing facts in small batches. The length of the
reasoning also varies a lot on this model: understand took 3,300 to 3,800 tokens in
most runs and more than 9,000 in one, where the fallback without thinking applies.
Prompt tuning continues on the official model at CSCS.
Two flaws remained for the reviewer: a sentence repeated by a repair (now filtered by
code) and an office name taken from a few-shot example (now prevented in the prompt;
the 8B judge did not catch it).

French, same setup, on the team's French letter
(`data/examples/sources/reduction-primes-lettre.txt`), 6 October 2026. Two runs: one
with the default thinking stages (understand and judge), one with thinking for
understand only.

| Draft | Facts found by code | Rule errors | Passive | Words per sentence |
|-------|---------------------|-------------|---------|--------------------|
| v1 (write), default run | 6 of 10 | 17 | 12.5 % | 9.5 |
| v3 (repair 2), default run | 10 of 10 | 11 | 5.3 % | 11.6 |
| v1 (write), understand only | 6 of 10 | 11 | 11.8 % | 8.7 |
| v3 (repair 2), understand only | 6 of 10 | 9 | 5.0 % | 8.9 |

The French prompts work on this model: the draft has question headings, talks to the
reader with `vous`, and keeps the deadline, phone number, e-mail and web address
exact; the writer left out the income limits, as in German. In the default run the
second repair round put them back by pasting the original 40-word legal sentence, which
LEN-01-FR flags as an error, so it stays visible. In the other run the second round
made no progress and the loop stopped. The judge with thinking ran to the 12,000-token
limit on three of four calls (10 to 15 minutes each) and answered through the fallback;
without thinking it called every fact present, although code found 4 missing, and
flagged most blocks for SEM-04. Code changes from these runs: a written sentence that
repeats an earlier one is dropped (the deadline came twice, under "Que devez-vous
faire ?" and "Jusqu'à quand ?"), an addition that repeats a later repaired block is
dropped, and the judge's findings on headings are not sent for repair (a repair had
turned the question heading into a statement).

### On the Public AI gateway (official Apertus 1.5 8B, no thinking)

P2 on the 12 dev pairs (10 German, 2 French), 6 October 2026, 70B judge without
thinking (the gateway ignores the switch). With prompt version 4, four of the ten
German drafts were the write prompt's JSON example word for word; the repair rounds
then patched dog-tax sentences with corrections. Version 5 of the write prompt and the
code guard against copied examples removed that. Means over the German pairs, version
4 against 5: invented blocks per 100 from 20.6 to 3.7, rule errors per 100 blocks from
5.1 to 2.3 (official texts: 1.6), warnings from 77 to 56 (official: 28), fact coverage
from 45 to 54 percent, hard facts kept from 55 to 61 percent (the official versions
keep 43), readability 55 (official: 64), about USD 0.006 and 60 seconds per page. All
12 pairs reached review; French: fact coverage 100 percent, no rule errors, readability
80 (official: 82).

Two weaknesses remain and decide the next prompt work. First, fact coverage: on the
fact-rich pages the writer leaves out half of the countable values, and the repair
round that should add them ends with "no progress" on 9 of 12 pairs. Second, values
from the examples leak into real drafts through the repair additions: the example's
phone number `031 987 65 43` (French: `032 987 65 43`) stood in 4 of the 12 final
drafts, the example's office in 3, in sentences the guard does not recognise because
they are rewritten ("Rufen Sie die DISG an: 031 987 65 43."). The judge did not flag
them. Since then rule FACT-06 (the mirror of FACT-01) flags every date, amount, phone
number, e-mail and web address, percentage and time (since 7 October also every
period, identifier and postal address) that is not in the source as an error and sends
the block to repair (with the source's only phone number, e-mail, web address,
identifier or address as the suggestion); the evaluation counts such values per 100
blocks by code, for every condition. On the stored dev drafts the rule found the examples' phone
numbers in 8 of 12 final drafts, the examples' `120 Franken` and `30. April 2026` in
3, and one e-mail address with a dropped letter (`gwaesserschutz@`), which the judge
had passed.

### On CSCS (official Apertus 1.5 8B and 70B, thinking for Understand and Judge)

The hackathon key arrived on 6 October 2026. The same three dev pairs as above, P2 with
the default thinking stages (`Apertus-v1.5-8B-thinking` for Understand, `-70B-thinking`
for the judge), against the gateway run without thinking:

| Pair | Fact coverage | Hard facts kept | Errors / 100 | Readability | Judge: present |
|------|---------------|-----------------|--------------|-------------|----------------|
| zh-blue-algae-de | 0.29 to 0.89 | 0.29 to 0.71 | 0.0 to 2.4 | 70 to 63 | 1.00 to 0.78 |
| zh-voting-de | 1.00 to 1.00 | 1.00 to 1.00 | 10.7 to 19.0 | 57 to 59 | 1.00 to 0.56 |
| lu-cost-approval-de | 0.00 to 1.00 | 0.00 to 0.71 | 0.0 to 0.0 | 70 to 37 | 0.30 to 0.71 |

Thinking earns its time where it matters: the fact sheets are better (the model finds
the values itself, so fewer facts come from code completion) and the drafts keep them:
fact coverage 0.43 to 0.96 and hard facts kept 0.43 to 0.81 on average. The price is
style: the drafts are longer and harder to read (readability 66 to 53, rule errors 3.6
to 7.1 and warnings 55 to 89 per 100 blocks), so the repair rounds have more to do. The
thinking judge reports distortions the no-thinking judge did not (7 to 22 percent of
the facts) and more unsupported blocks. A P2 job takes 45 to 90 seconds on CSCS, less
than the gateway needed without thinking. The thinking stages stay as they are for the
evaluation; the style gap is the repair loop's job. Two slips of the thinking 8B on long fact sheets showed up here:
a missing comma after a list and an object never closed before the next top-level key;
both are repaired in code now (`llm/json_out.py`).

### Repair guard: P2 on the dev pairs on CSCS (6 October 2026, late)

The 12 dev pairs again, P2 with thinking for Understand and the judge, repair prompt
version 6 and the guard against values the document does not contain; the LLM cache
was on, so the pairs already run on CSCS reused their fact sheets, drafts and judge
reports and only the repair rounds ran fresh.

- 11 of 12 pairs reached review. `be-pregnancy-counselling-de` failed three times in
  Understand on three different JSON slips of the thinking 8B (no JSON object at all,
  five validation errors, a missing comma), a fresh answer each time once unusable
  answers left the cache; it is the next candidate for the parser repairs.
- The guard fired 10 times in 33 repair calls, every time on values from the prompt's
  examples (`031 987 65 43`, `032 987 65 43`, `120`, `30. April 2026`, `8 h 00`,
  `11 h 30`) or on a value the model computed (`360`). Whenever the first answer was
  sent back, the second one was clean. One repair addition still carried an example
  value into a final draft: its first answer was invalid JSON and the second, with the
  value, was used (the guard never fails a round).
- 8 foreign values remain in 3 of the 11 final drafts: 6 come from the write stage,
  which the guard does not check (`sg-el-costs-de`: dog-tax sentences in paraphrase,
  only 2 of 12 sentences verbatim and so below the copy guard's threshold;
  `bwl-emergency-supplies-fr`: the example's contact block), 2 from the fallback above.
- German means over the 9 completed pairs: fact coverage 61 percent, hard facts kept
  61 percent, invented values 2.1 per 100 blocks (all in `sg-el-costs-de`), rule errors
  2.8 per 100 blocks, 1.9 repair rounds, 82 seconds per job. The judge's numbers are
  not comparable with the gateway run: the thinking judge reports 10.7 unsupported
  blocks per 100 against 3.7 without thinking.

The remaining leak is the write stage's paraphrased example content. Two candidate
fixes: the copy guard also counts sentences with the examples' topic words (`Hund`,
`Hunde·steuer`, `Impfausweis`, `contrôle des habitants`) that the source does not
contain, or the write stage gets the same soft check for foreign values at the price of
a second write call when it fires.

### Full evaluation on CSCS (6 October 2026)

`make eval RESULTS=eval/results-cscs`: P0, P1 and P2 on the 23 held-out pairs (20
German, 3 French), thinking for Understand and the judge, then P2 with the 70B writer
on the first 5 German pairs. 23 of 23 pairs completed under every condition after the
reruns of failed pairs (the harness reruns them with the cache on, and unusable answers
no longer stay cached). The first pass had failed 7 P0 scorings, 9 P1 and 6 P2 jobs,
every one on an answer shape the code now handles: core answers written as bare
sentences, an omission or glossary entry written as a block of that kind, an empty
block, a list closed with a brace, and 8 write answers cut off at the token limit on
pages of 65 to 185 sentences, which are now written again as two halves. The server cut
31 of about 350 streams; the client retried them all.

German means over 20 pairs, 8B writer:

| Setup | Fact coverage | Hard facts kept | Invented values / 100 | Judge: unsupported / 100 | Errors / 100 | Readability | SARI |
|-------|---------------|-----------------|-----------------------|--------------------------|--------------|-------------|------|
| REF | - | 70 % | 2.2 | - | 2.7 | 62 | - |
| P0 | 93 % | 100 % | 0.0 | - | 22.0 | 50 | 44.5 |
| P1 | 72 % | 69 % | 3.2 | - | 9.9 | 50 | 38.8 |
| P2 | 84 % | 80 % | 0.1 | 6.9 | 4.3 | 51 | 40.6 |
| P2, 70B writer (5 pairs) | 68 % | 71 % | 0.7 | 6.0 | 2.0 | 58 | 42.2 |

P0's fact coverage read 98 percent in this run's first scoring: the 13 pairs scored
before any P1 or P2 job existed were measured against a fact sheet without code
completion (fewer facts). The scoring now completes that sheet as the pipeline does,
and the rescoring from the cache against the stored P2 sheets (6 October, evening)
gives 93 percent; no other P0 number changed.

What the run says about the prompts and guards: the P1 drafts carried 3.2 invented
values per 100 blocks, nearly all the examples' phone number, date and hours in
sentences without a topic word; the example-value rule (above) brought P2 down to 0.1,
two office hours on one page. The judge flags 6.9 unsupported blocks per 100 in P2
(9 percent distorted facts on the fact-rich pairs), which is what the hand labelling
(`eval sample`) has to check. Every P2 job stopped with "a repair round brought no
progress" after 1.8 rounds on average: the repair prompt is the next lever for fact
coverage. The 70B writes cleaner (2.0 errors, readability 58) but keeps fewer facts.

### The three model tiers on the eval split (CSCS, 6 October 2026)

P2 on the 23 held-out pairs (20 German, 3 French) in three settings: the 8B writer
(the default: the 8B for Understand, Write and Repair), every stage on the 70B
(`--writer swiss-ai/Apertus-v1.5-70B`) and the hybrid with the 70B for Understand
only (`--understand swiss-ai/Apertus-v1.5-70B`, in production `LLM_UNDERSTAND_NAME`).
The judge is the 70B-thinking in all three. The hybrid's fact sheets came from the
cache of the 70B run, so the hybrid and the 70B run score against the same sheets.
German means over the 20 pairs (`make eval-70b` reproduces the two extra runs):

| Setup | Fact coverage | Hard facts kept | Errors / 100 | Warnings / 100 | Readability | Unsupported / 100 | Invented values / 100 | Words | USD / page |
|-------|---------------|-----------------|--------------|----------------|-------------|-------------------|-----------------------|-------|------------|
| 8B writer (default) | 84 % | 80 % | 4.3 | 58 | 51 | 6.9 | 0.1 | 245 | 0.0105 |
| 70B everywhere | 78 % | 75 % | 1.4 | 41 | 58 | 4.7 | 0.3 | 209 | 0.0191 |
| Hybrid: 70B reads, 8B writes | 66 % | 65 % | 2.1 | 50 | 54 | 6.2 | 0.6 | 203 | 0.0103 |

- **The 70B writes cleaner easy language and keeps fewer facts.** A third of the rule
  errors, fewer warnings, readability 58 against 51 (the official versions: 62), and
  the judge reports fewer unsupported blocks and fewer distorted facts (2.6 against 8.6
  percent), though in that run the judge grades its own model's drafts. Fact coverage
  78 against 84 percent, hard facts kept 75 against 80 (on the 14 fact-rich pairs 66
  against 73), and shorter texts (209 against 245 words). The first 5 pairs had
  suggested the opposite on facts (68 against 57 percent coverage); the full set turned
  it around, so the 5-pair numbers in earlier notes are superseded.
- **Price and speed.** USD 0.019 against 0.011 per page at Public AI list prices, 1.8
  times rather than the 3 times the token prices suggest, because the 70B needs fewer
  tokens: it reasons a third as much in Understand (1,400 against 4,200 output tokens
  per job) and its repair rounds are shorter. It generates at about 68 tokens per
  second against 155 for the 8B, but the Understand call takes 19 s against 92 s and
  the Write call 27 s against 10 s; summed over the mean fresh call times per stage, a
  P2 job is about 85 s on the 70B and about 150 s on the 8B, because the 8B-thinking's
  reasoning in Understand dominates. The seconds per page in eval/report.md undercount
  all runs, because cached calls count as 0 s (the 8B run reused 76 percent of its
  Understand calls from the cache, the hybrid all of them).
- **The hybrid is the worst of the three on facts** (66 percent coverage, 65 percent of
  the hard facts) although it scores against the same, richer fact sheets as the 70B
  run (7.2 checkable facts per pair against 6.2 in the 8B's own sheets), and hard facts
  kept, which needs no fact sheet, drops too. The 8B writer handles the 70B's fact
  sheets worse than its own: four German drafts collapsed to under 50 words
  (`zh-municipalities-de` 38, `be-education-de` 25, `bs-tax-deductions-de` 30,
  `zh-political-rights-de` 44) and others ballooned (`zh-accessibility-statement-de`
  991 words against 345; the French `ne-disability-petitions-fr` 2,520 against 659, with
  24 rule errors per 100 blocks over the 3 French pairs). Its call times (Write 22 s,
  Repair 15 s) were slower than in the 8B run; the endpoint was shared with other runs
  at the time, so they are not compared. The setting stays available but is not
  recommended; the next prompt work for it would be to shorten the fact texts the
  write prompt shows, which the 70B writes longer.
- **French (3 pairs).** The 70B keeps fewer facts (56 against 73 percent coverage) and
  writes much shorter texts (154 against 400 words) at readability 83 (official: 85);
  the hybrid keeps the most hard facts (78 percent) but at 1,160 words a page.

Decision: the default stays the 8B writer with the 70B judge. `LLM_NAME` set to the
70B is the quality tier for style at about twice the price and, on-premise, four GPUs
instead of one; the hybrid is documented as tested and not better.

### Zurich's prompt as the second baseline (CSCS, 6 October 2026)

P0-ZH (`baseline_zh.md`, both variants) and P0 on the 20 German eval pairs and the 10
German dev pairs, 8B without thinking, scored against the same fact sheets as P1 and P2
(the stored P2 job of each pair). All 90 jobs reached review in about two minutes per
30 jobs; every answer carried the `<leichtesprache>` tags. Means over pairs:

| Split | Setup | Fact coverage | Hard facts kept | Errors / 100 | Warnings / 100 | Words / sentence | Readability | SARI | Invented values / 100 | Tokens / page |
|---|---|---|---|---|---|---|---|---|---|---|
| eval (20) | P0 | 93 % | 100 % | 22.0 | 95.0 | 7.7 | 50 | 44.5 | 0.0 | 982 |
| eval (20) | P0-ZH complete | 91 % | 95 % | 15.4 | 85.6 | 6.8 | 47 | 43.2 | 0.0 | 2374 |
| eval (20) | P0-ZH condensed | 75 % | 77 % | 8.7 | 74.7 | 6.1 | 48 | 41.7 | 0.0 | 2199 |
| eval (20) | P2, 8B | 84 % | 80 % | 4.3 | 58.4 | 6.8 | 51 | 40.6 | 0.1 | 21711 |
| dev (10) | P0 | 74 % | 83 % | 26.1 | 108.0 | 8.3 | 49 | 42.0 | 0.0 | 936 |
| dev (10) | P0-ZH complete | 75 % | 87 % | 26.2 | 114.0 | 8.3 | 43 | 39.8 | 0.0 | 1979 |
| dev (10) | P0-ZH condensed | 74 % | 81 % | 13.0 | 94.4 | 6.6 | 47 | 41.2 | 0.1 | 1861 |
| dev (9 of 10) | P2, 8B, run of 6 Oct afternoon | 61 % | 61 % | 2.8 | 57.3 | 6.8 | 52 | 40.5 | 2.1 | 18235 |

- **Zurich's complete prompt beats our one-sentence P0 on every quality column** and
  keeps slightly fewer facts (95 against 100 percent of the hard facts): it is the
  fairer baseline, and the strawman objection to P0 is answered.
- **Against P2 on the eval split:** P2 has a quarter of the rule errors (4.3 against
  15.4), fewer warnings, the same sentence length and better readability; the complete
  prompt keeps more facts (91 against 84 percent coverage, 95 against 80 percent of the
  hard facts; on the 14 fact-rich pairs 93 against 73, the official versions 60). By
  the rules of PLAN.md §13.4 this is case B: lead with "no silent loss" and state the
  coverage gap openly; the fact-retention diagnosis (WP13) is the next step.
- **The condensed variant, their default for Leichte Sprache, drops a quarter of the
  hard facts** (77 percent kept, 69 on the fact-rich pairs) and nobody is told. That is
  the silent loss in numbers.
- **Neither baseline invents values** on these pages (0.0 per 100 blocks). The invented
  values of P1 and P2 were mostly values from our own prompt examples (above), which the
  code guards now catch.
- **Cost.** The Zurich prompt costs 2.4 times the tokens of P0 (its rules are about
  1,900 input tokens per call) and still a hundredth of P2.
- **Dev split.** The dev pages are harder (the official versions keep 43 percent of
  the hard facts); the single prompts keep 81 to 87 percent. The stored P2 dev rows are
  from the run of 6 October afternoon, before the FACT-06 and example-value guards (9 of
  10 pairs), and are rerun with `--redo` after the Friday prompt work.

The headline sentence that follows from case B is the owner's decision (D-M, G3).

### Mediopunkt by code: P2 on the dev pairs on CSCS (6 October 2026, night)

The 10 German dev pairs under P2 twice, once without the step (`apply_mediopunkt`
replaced by a no-op, results in `eval/results-cscs-nomp`) and once with it
(`eval/results-cscs`, `--redo`; the rows before it are kept in `eval/results-cscs-v2`).
The second run started after the first had finished, so both replayed the same
Understand and Write answers from the LLM cache and started from the same write answer;
the judge and repair calls ran fresh on both sides (the judge sees the split text).
All 10 pairs reached review on both sides, `be-pregnancy-counselling-de` included.

Two pairs are left out of the comparison. `zh-oral-health-de`: its cached Understand
answer failed to parse in the first run and was dropped from the cache, as designed, so
the second run started from a different fact sheet. `sg-el-costs-de`: its write answer
has 3 blocks; with the step, the judge flagged 39 problems after the first repair round
instead of 24, the loop stopped and kept the 3-block version (judge noise and the
choice of the best version, not the split). With it, the rule errors would read 8.5
against 3.3 per 100 blocks, all of it from that one pair.

Means over the other 8 pairs, final version:

| | Without the step | With the step |
|---|---|---|
| LEX-01 warnings / 100 blocks | 34.7 | 4.8 |
| All warnings / 100 blocks | 78.8 | 51.0 |
| Rule errors / 100 blocks | 4.3 | 3.7 |
| Words split by code / 100 blocks | 0 | 33.6 |
| Repair rounds | 1.75 | 2.0 |
| Rounds with only warnings left | 0 | 0 |
| Fact coverage | 69 % | 73 % |
| Hard facts kept | 68 % | 79 % |
| Readability | 48.2 | 48.4 |

- **The step does what it should.** LEX-01 falls from 35 to 5 warnings per 100 blocks,
  the same as the rescoring of the stored drafts (change log, below). The 11 warnings
  left in the 10 final drafts are there by design: adjectives (`selbstbestimmtes`, `handschriftlich`,
  `Weiterführende`), street names in front of a house number and the truncated
  `Familienplanungs-`. The errors are the same rules on both sides (LEN-01, GRAM-01).
- **It saves no repair round, and cannot on these pages.** No job on either side ever
  reached zero blocking problems, so the round that sends the warnings (LEX-01 among
  them) never ran; 15 of 16 jobs stopped on "no progress" with missing or distorted
  facts and judge findings left. The rounds are bounded by the facts, not by the style.
- **It costs no facts.** The first write answer of each pair, split and unsplit, gives
  the same fact coverage and the same values (kind, canonical form, text) on all 10
  pairs. The differences in the table come from the fresh judge and repair calls, the
  run-to-run noise of the loop; they are no effect of the step.
- **Seconds per job** read 22 against 38 only because the first run replayed 14 judge
  calls from the cache and the second 4.
- **The 53 distinct words split by code, read by hand:** 48 right, 5 wrong joints.
  `Assistent·innen` and `Schweizer·innen` split off the feminine ending, which reads as
  gender typography; fixed: the splitter treats `-innen` as an ending when the rest is
  a word, splits only that stem (`Sozial·arbeiterinnen`) and leaves `Schweizerinnen`
  alone, while `Dach·rinnen` stays a compound; a word long only by its ending
  (`Steuerberaterinnen`) is not split, because the short stem invites wrong joints
  (`Schrei·berinnen`). `Kostengut·sprache` (known, above),
  `Kostenvoran·schlag` and `Leistungser·bringende` stay: `Voranschlag` and
  `erbringende` are too rare in the word list to count as parts. The stored drafts
  keep the old splits; the final run uses the fixed splitter.
- **The evaluation's count was too low.** Each version records only the edits made on
  it, and a repair round keeps the dot it is given, so counting the final version's
  edits gave 10 words per 100 blocks instead of 33.6. The evaluation now counts the
  edits of every version up to the final one whose word the final version still has
  (`eval.score.kept_code_splits`).

The full dev split under P2 with the step (10 of 10 pairs): fact coverage 58 percent,
hard facts kept 63 percent, 3.0 rule errors and 47.5 warnings per 100 blocks, no
invented values.

## Change log

| Version | Date | Change |
|---------|------|--------|
| 1 | 2026-10-05 | First German templates for understand, write, judge, repair and baseline; two synthetic examples. |
| 1 | 2026-10-06 | No template change. Stage settings: write without thinking by default (see "Tested so far"). |
| 2 | 2026-10-06 | The examples name no office ("das Amt" instead of "Steuer·amt"), and the write prompt says that names of offices, addresses and numbers come only from the document: in a local run the writer called the Sozialversicherungsstelle "Steueramt", the office of the tax example. Code no longer lets a repair repeat a sentence that is already in the draft. |
| 3 | 2026-10-06 | All examples (few-shot pairs and the JSON examples of every prompt) moved to topics that are not in the evaluation set: a resident parking permit and a dog tax. The repair prompt makes adding the missing facts the first task, each with its value and fact id. Code: a repair round first asks only for the blocking problems (rule errors, missing facts, the judge's problems), at most 5 missing facts at a time, the most important kinds first; the warnings get one round once nothing blocking is left. |
| 4 | 2026-10-06 | French templates for all five stages, with French JSON examples and two French few-shot pairs on the same topics as the German ones. The words code writes around the items come from a table per language (`pipeline/labels.py`). No change to the German templates. |
| 5 | 2026-10-06 | Write prompt (German and French): the JSON form moved before the style examples, its intro says the values come from another document; the document comes last, followed by the instruction to write about it. Reason: on the Public AI 8B without thinking, 4 of 12 dev drafts were the JSON form itself. Code: an answer that copies the examples is sent back once; the omissions or glossary list written as a pseudo-block inside blocks is hoisted. No change to the other templates. |
| 6 | 2026-10-06 | Repair prompt (German and French): every value in the answer comes from the fact sheet or the original's sentences, the values of the JSON form belong to another document, and no value is invented for a fact without one. Code: a repair answer with a value that neither the source nor the fact sheet contains is sent back once with the values named (the check of rule FACT-06); the second answer is used as it is. Reason: the examples' phone number stood in 8 of 12 dev drafts, put there by repair additions. No change to the other templates. |
| 6 | 2026-10-06 | No template change. Code: a sentence with a topic word of the examples (`Hund`, `Parkkarte`, `Impfausweis`, `chien`, `carte de stationnement`, ...) that the source does not contain, or with one of the examples' own values, is sent back once and dropped from the second answer; two more JSON repairs (a list or object closed with the wrong bracket, a unicode escape with too few digits), both seen on the CSCS 8B; a core answer written as a bare sentence instead of an object is read as its text; an empty block `{}` is dropped; a write answer cut off at the token limit is written again as two halves (8 jobs failed this way in the first evaluation run on CSCS); an omission or glossary entry written as a block of that kind is hoisted into its list (the 70B writer). |
| 6 | 2026-10-06 | No change to our templates. New German template `baseline_zh.md`: the Canton of Zurich's Leichte Sprache prompt, verbatim, as the second baseline P0-ZH in two variants (`complete`, `condensed`); its rendering was checked character for character against their own prompt assembly (`create_prompt` in `app_core.py`). |
| 6 | 2026-10-06 | No template change. Code: the Mediopunkt is written by code after the write stage and after every repair round, in P1 and P2 (`rules/mediopunkt.py`, docs/rules.md "Edits made by code"), and LEX-01 no longer exempts a compound because it is in the glossary. Reason: in the owner's first CSCS job through the web UI the 8B kept `Krankenversicherungspolice` and `Sozialversicherungsstelle` unsplit through two repair rounds. The repair prompt therefore no longer carries LEX-01 lines for compound nouns. Rescored without model calls on the final drafts already in the CSCS store (97 German P1 and P2 jobs, 3453 blocks): LEX-01 warnings per 100 blocks fall from 39.1 to 3.0 (P1, 8B), 31.9 to 3.1 (P2, 8B) and 27.0 to 2.2 (P2, 70B), all warnings per 100 blocks from 77.9 to 42.0, 66.7 to 38.0 and 53.8 to 29.3; 30 to 41 words per 100 blocks get the dot, 157 of the 1177 in glossary terms. Reading splits by hand found two wrong joints in the first 25: `Ostermundi·gens·trasse`, fixed in the splitter (a nested split now counts by its weakest part, giving `Ostermundigen·strasse`) and by leaving the word in front of a house number alone; and `Kostengut·sprache` for `Kosten·gutsprache`, which stays, because the splitter does not know the Swiss term. The next 25 had none. What the step saves in repair rounds shows only in the next `--redo` rerun on CSCS, which is still open. |
| 6 | 2026-10-06 | No template change. Code: the compound splitter treats the feminine ending `-innen` as an ending (`Sozial·arbeiterinnen`, never `Schweizer·innen`), and the evaluation counts the splits of earlier rounds that the final version keeps. The dev rerun on CSCS with and without the step is in "Mediopunkt by code" above: LEX-01 from 35 to 5 warnings per 100 blocks, no repair round saved, no fact lost. |
