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
  written), postal address, quantity (`2,5 mg`, as `2.5 mg`) and dosing scheme
  (`1-0-1`) (docs/rules.md, "Value kinds"). Values in passages the
  model marked as droppable become background facts; all others must be kept. The first
  local run showed why: the model listed 3 facts for a letter with 11 checkable values.
  The prompts do not mention the new kinds (no prompt change before the freeze); what
  the model writes as a value for them (`30 Tage`, `2026-0042`) is parsed as text.
  Drug names are the exception (8 October 2026): code cannot find them, so for a source
  with a dose or a dosing scheme the partial `medication.md` asks Understand for one
  fact of kind `medication` per drug, the name alone as the value, and Write for one
  list item per medication (docs/rules.md FACT-09). A document without a dose gets the
  standard prompt word for word.
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
  into a page about EL costs with only 2 of 12 sentences verbatim. The examples' office
  counts as a topic too (`Einwohnerkontrolle`, `contrôle des habitants`, since
  8 October 2026): the repair example's addition "Rufen Sie die Einwohner·kontrolle
  an: 031 987 65 43." came back with a number of the document in 4 P2 jobs of the
  CSCS evaluation and 3 example builds, in documents that never name the office.
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
- **The exact form of a missing value** (7 October 2026). The list of missing facts
  in a repair request names the fact sheet's value and, when the draft should write
  it differently, the exact form: `(Wert: 2026-03-31; schreiben Sie: 31. März 2026)`,
  `(valeur : 0221234567 ; écrivez : 022 123 45 67)`. Dates, amounts, phone numbers,
  percentages, times, periods, identifiers and addresses get it; web and e-mail
  addresses are given as written. The repair prompt's text did not change; the
  rendered requests did, so the repair calls of a `--redo` run are fresh.
- **Clause recipes.** A LEN-02 or LEN-02-FR finding carries the rewrite recipe for its
  conjunction as the suggestion (docs/rules.md, `rules/recipes.py`), so the repair
  line reads "Vorschlag: Machen Sie eine Frage und eine Antwort mit Dann ..." for a
  `wenn` clause. The idea is Zurich's, the wording ours.
- **Facts-only rounds** (7 October 2026, PLAN.md WP13). The repair loop stops when a
  round brings no progress on the whole; on the dev pairs that left must-keep values
  missing in 15 of 16 jobs, because a round that adds facts also gets new judge
  findings. After the loop, up to `MAX_FACTS_ROUNDS` (default 1) rounds ask for the
  missing facts alone, with no block flagged, and are measured by the FACT-01 count:
  they go on while a round adds a fact. The judge reruns as in any round with facts
  involved. A facts round asks for up to `MAX_MISSING_PER_FACTS_ROUND` (10) missing
  facts, a repair round for 5 next to its flagged blocks; the cap was raised from 5 on
  the measured dev rerun of 7 October ("Fact-retention diagnosis" below). The final
  version is the one with the fewest must-keep values missing, then the fewest blocking
  findings. Set `MAX_FACTS_ROUNDS=0` to measure the pipeline without them.
- **Repair records.** Every round stores what it asked for, the answer as given and
  every answered sentence code left out with its reason (a repeat, example content, a
  block the round had not flagged), under the version it produced. `eval diagnose`
  reads them to tell a fact the model never wrote from one it wrote in a form FACT-01
  rejects or one code dropped (below, "Fact-retention diagnosis").
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

### Fact-retention diagnosis (WP13): the method, numbers pending (7 October 2026, night)

Why does P2 keep fewer facts than Zurich's complete prompt (84 against 91 percent fact
coverage on the eval split)? `python -m leichtfacile eval diagnose --results
eval/results-cscs --role dev` answers it without a model call, from the stored
artifacts of the P2 jobs: every must-keep fact with a value that FACT-01 does not find
in the final version goes into one bucket.

| Bucket | Meaning | How the tool decides |
|---|---|---|
| a | never asked for in any round | the requests of each round, from the repair record or recomputed with `build_request` from the stored findings; the reason apart: behind the cap of missing facts per round (5 in a repair round, `MAX_MISSING_PER_FACTS_ROUND` in a facts round), no round ran at all (the loop stopped or failed before one), or never flagged by FACT-01 when the job ran |
| b | asked for and written, but in a form FACT-01 rejects | the record's answer carries the fact's digits or words, but no value the matcher accepts |
| c | asked for and written, then dropped by code | the answered sentence is in the record's dropped list (a repeat, example content, a block the round had not flagged) |
| d | asked for, and the model did not write it | no answered sentence for the fact, nothing loose either |
| k | asked for and written into a version that was not kept as final | the value is in a later version than the final one; the final version is the one with the fewest blocking findings, so a round's gains are lost when the judge flags its new sentences (a fact asked for in such a round and not written is b, c or d, with the reason saying which version is final) |
| l | present in an earlier version, lost in a later rewrite | the value is in a version before the final one and gone after a round, by the model's rewrite or by code |
| x | asked for, answer not recorded | jobs run before the repair record existed (every run before 7 October 2026, night): b, c and d cannot be told apart for them |
| e | background facts whose value is not in the final text | listed for reading, not counted: whether the reader needed a fact Understand or code completion marked droppable is a reading decision |

Run on the owner's machine on 7 October 2026 against `eval/results-cscs` (CSCS, 8B
writer, 70B judge), first on the stored dev jobs of 6 October, then after the dev rerun
with `--redo` under the code of 7 October (facts-only rounds, the exact form in the
request, the repair record). The first run's rows are kept in `eval/results-cscs-v3`.

| Bucket | Stored run of 6 Oct (12 jobs) | Rerun of 7 Oct (12 jobs) |
|---|---|---|
| Checkable must-keep facts | 102 | 122 |
| Missing in the final versions | 50 (51 % found) | 16 (87 % found) |
| a: never asked for, behind the cap of 5 per round | 10 | 2 |
| a: never asked for, no repair round reached the final version | 30 | 9 |
| a: never asked for, never flagged by FACT-01 | 0 | 0 |
| b: written in a form FACT-01 rejects | 0 | 2 |
| c: written, then dropped by code | 0 | 1 |
| d: asked for, not written | 0 | 1 |
| l: present once, lost in a later rewrite | 0 | 0 |
| x: asked for, answer not recorded | 10 | 1 |
| e: background facts whose value is not in the text (for reading) | 7 | 8 |
| Facts without a value the judge calls missing or distorted | 23 | 6 |
| Jobs with a record for every round into the final version | 3 of 12 | 11 of 12 |

Reading it: four of five lost facts in the stored run were never asked for, most of
them because no round that led to the final version asked for anything (the loop had
stopped on "no progress" or a later version was not kept), the rest behind the cap.
That is the bucket the facts-only rounds address, and the rerun shows it: 16 missing
instead of 50, on more checkable facts (122 instead of 102, because the rerun's fact
sheets were completed by the code of 7 October, which knows periods, identifiers and
addresses; the Understand answers came from the cache). What is left is small and
spread: 9 facts in jobs where no round reached the final version (the next reading
decision: whether the final-version choice by blocking count throws a facts round's
version away when the judge flags its new sentences), 2 behind the cap, 2 written in a
form the matcher rejects, 1 dropped by code, 1 not written. The two French pairs were
not rerun.

The ablation on the 10 German dev pairs, the same cached Understand and Write answers
on both sides (`eval/results-cscs` with the facts rounds, `eval/results-cscs-nofacts`
with `MAX_FACTS_ROUNDS=0`, run in sequence):

| Setup | Fact coverage | Hard facts kept | Silent losses | Invented values / 100 | Judge: unsupported / 100 | Errors / 100 | Tokens / page | USD / page |
|---|---|---|---|---|---|---|---|---|
| P2, facts rounds on (default) | 75 % | 72 % | 5 % | 0.0 | 3.6 | 7.3 | 22,570 | 0.0121 |
| P2, facts rounds off | 68 % | 65 % | 5 % | 0.0 | 4.3 | 8.2 | 19,197 | 0.0097 |
| P0 (stored rows of 6 Oct) | 74 % | 83 % | - | 0.0 | - | 26.1 | 936 | 0.0001 |
| Official easy-language version | - | 37 % | 63 % | 3.5 | - | 1.6 | - | - |

The facts rounds add 7 points of fact coverage and 7 points of hard facts kept (on the
9 fact-rich pairs 80 against 72 percent kept, 83 against 76 coverage) at about 3,400
more tokens per page, with no invented value on either side and fewer judge findings
and rule errors: the round's additions are clean. They stay on for the final run
(decision D-Z). The "seconds per page" of the ablation's second side read 0.1 only
because nearly every call came from the cache. Two things the run flagged: the P2 rows
show 5 percent silent losses, where the report's note promises zero by design, so the
code completion misses some hard value (the row's `silent_loss_kinds` names the kinds;
to be read next); and two Write calls were cut off at 8,000 tokens on pages of 95 and
88 sentences and written as halves, as designed.

The second reading, the same day, with the kinds and the reason strings of the local
file: the silent losses were three percentages and one address, and both were gaps of
the code completion, now closed. A completed percentage was stored as the bare number
(`4.5`), which parses back as a plain number and never matched the percentage in a
draft again, so FACT-01 counted it as missing even when the draft had `4,5 Prozent`;
it is stored as `4.5%` now, the form the Understand prompt asks for. An address over
two source sentences (`Gerichtsstrasse 12` and `8000 Musterwil` on separate lines) was
completed from the second sentence alone, without its street; the completion now takes
the values from the document text as the evaluation does, with segment offsets, so the
fact cites both sentences and FACT-01 asks for the street. The nine facts in jobs
where no round led to the final version were all asked for in a round whose version
was not kept: six in a facts round that brought no progress, three in a repair round,
with v1 final in each case. The diagnosis now reads such facts off the later rounds
(bucket k when the value is in a version not kept, else b, c or d with the reason
naming the final version), so the next run shows whether the model did not write them
or the final-version choice threw them away.

The third run, the same day, under the fixed completion (`--redo` again; the rows
before it are kept in `eval/results-cscs-v4`): 30 of 122 must-keep values missing (75
percent found), fact coverage 71 percent, hard facts kept 68, silent losses 2 percent,
invented values 0.0, 7.5 rule errors per 100 blocks. The buckets: 13 behind the cap,
2 written in a rejected form, 1 dropped by code, 4 not written, **5 written into a
version that was not kept as final**, 1 lost in a rewrite, 4 not recorded. Three
readings:

- *Run-to-run noise is large on single pairs.* One pair (`sg-el-costs-de`, 22
  checkable facts) accounts for most of the difference to the run before: 18 missing
  against 2, with v3 of 4 final instead of v5 of 5; 13 of its facts were behind the
  cap, 3 were written by the facts round into a v4 the final-version rule did not
  keep. Another pair lost its repair round to two unusable answers and, by the rule of
  the day, its facts round with it. The judge and repair calls are fresh on every
  `--redo` while Understand and Write replay from the cache, so two runs differ by
  the loop alone.
- *The final-version rule discarded facts.* The 5 facts of bucket k were in the draft
  the facts round produced; the version with the fewest blocking findings won because
  the judge flagged the new sentences or they carried a rule error. Since 8 October the
  final version is the one with the fewest must-keep values missing, then the fewest
  blocking findings (`version_key` in the orchestrator), and `eval rescore --select
  facts|blocking` scores the stored jobs under either rule without a model call, so
  the rule's effect is read on the same jobs. An answer the code could not use no
  longer cancels the facts round; only a failed endpoint does.
- *The last silent loss is a completion asymmetry, closed.* One address: the model's
  fact carried the place alone, which counted as covering the full address, while the
  reader who searches the fact sheet for the full address does not find it. Coverage
  is now asked in the reader's direction, so the full value gets its own fact next to
  the model's partial one (the same for a bare number against a quantity).

The rule change, read on the same jobs with `eval rescore` (no model call), German dev
pairs, P2:

| Jobs | Final version by | Fact coverage | Hard facts kept | Silent losses | Invented values / 100 | Judge: unsupported / 100 | Errors / 100 |
|---|---|---|---|---|---|---|---|
| Third run | blocking findings (the rule until 7 Oct) | 71 % | 68 % | 2 % | 0.0 | 4.9 | 7.5 |
| Third run | missing facts first (since 8 Oct) | 80 % | 81 % | 2 % | 0.0 | 6.1 | 8.8 |
| Second run | missing facts first | 83 % | 84 % | 5 % | 0.0 | 5.2 | 7.1 |

The "blocking" rescore reproduces the third run's row to the decimal, which also
checks the rescoring itself. Facts first gains 9 points of fact coverage and 13 of
hard facts kept on the same drafts, for 1.2 more judge findings and 1.3 more rule
errors per 100 blocks: the sentences a facts round adds are the ones the judge then
flags. The silent losses do not move with the rule, as they should not: they are a
property of the fact sheet stored when the job ran, and the completion fixes show
only in the next run. The cap of a facts-only round is a setting now
(`MAX_MISSING_PER_FACTS_ROUND`, default 5): the one experiment left for the dev split
before the freeze.

The fifth run, the same day, under the final code (facts first, the fixed completion;
`--redo`, the rows before it kept in `eval/results-cscs-v5`), then the cap experiment
in a fresh folder `eval/results-cscs-cap10` with `MAX_MISSING_PER_FACTS_ROUND=10`, run
after it on the same cache, so both replay the same Understand and Write answers and
the cap-10 run made only 4 fresh calls. German dev pairs, P2:

| Run | Fact coverage | Hard facts kept | Silent losses | Invented values / 100 | Judge: unsupported / 100 | Errors / 100 | Tokens / page | USD / page |
|---|---|---|---|---|---|---|---|---|
| Fifth run, cap 5 | 75 % | 77 % | 0 % | 0.0 | 4.6 | 5.4 | 21,786 | 0.0117 |
| Cap 10 | 79 % | 81 % | 0 % | 0.0 | 2.8 | 6.7 | 21,697 | 0.0117 |

| Bucket | Fifth run, cap 5 (12 jobs) | Cap 10 (10 German jobs) |
|---|---|---|
| Checkable must-keep facts | 123 | 110 |
| Missing in the final versions | 27 (78 % found) | 15 (86 % found) |
| a: never asked for, behind the cap | 13 | 7 |
| a: no round ran, or never flagged by FACT-01 | 0 | 0 |
| b: written in a form FACT-01 rejects | 1 | 1 |
| c: written, then dropped by code | 2 | 5 |
| d: asked for, not written | 7 | 2 |
| k: written into a version not kept as final | 0 | 0 |
| l: present once, lost in a later rewrite | 0 | 0 |
| x: asked for, answer not recorded (the two French jobs, not rerun) | 4 | 0 |
| e: background facts whose value is not in the text (for reading) | 9 | 9 |
| Facts without a value the judge calls missing or distorted | 9 | 6 |

The fifth run closes the two open points: no silent loss (the completion fixes hold)
and no fact written into a version that was not kept (the facts-first rule holds).
What is left is mostly the cap, 13 of 27 missing facts, all in `sg-el-costs-de` (22
checkable facts). With cap 10 that pair goes from 15 missing facts to 7, and the means
over the ten pairs move by 4 points of fact coverage and 4 of hard facts kept, with no
invented value and fewer judge findings (2.8 against 4.6 per 100 blocks), at 1.3 more
rule errors per 100 blocks. That passes the decision rule set before the run (coverage
up by 3 points or more, invented values not up, judge findings up by less than 2), so
the default is 10 since this run (decision D-Z). The gain comes from one pair; the
other nine keep the same number of missing facts. The 4 fresh calls were the facts
round and its judge in `sg-el-costs-de` and in `zg-disability-services-act-de`; the
second asked for the same 4 facts under both caps, so its fresh answer is a cache miss,
not the cap: the same 4 facts stay missing, read as dropped by code (c) in the cap-10
run and as not written (d) in the fifth.

### Image input spike (CSCS, 8B, 7 October 2026): no-go at this setting

`scripts/image_spike.py` on the two scanned letters of `data/examples/print/scans/`,
long side 1,600 pixels, the 8B without thinking, temperature 0 (PLAN.md WP12, D-N):

| Capture | Pages | Character error rate | Hard values found | Seconds |
|---|---|---|---|---|
| steuermahnung-brief_scan (German, 1 page) | 1 | 0.996 | 0 of 21 | 0.9 |
| bourse-etudes-decision_scan (French, 2 pages) | 2 | 0.057 | 14 of 22 | 8.0 |

The German page came back as `unlesbar` in four tokens: the model declined the page
rather than misreading it, so every value of the tax reminder is lost (the IBAN, the
amount, six dates, four times, two phone numbers, the percentage, the period, the
address). The French letter was read, with 5.7 percent of the characters wrong, and the
digits are where the errors sit: the AVS number `756.4719.2083.50` came back as
`763.4713.2063.50`, the IBAN with wrong digits, the postcode 1999 as 1399, one payment
date, the phone number, the e-mail and the web address are lost. The go/no-go rule of
the plan says stop: an image ingest at this setting would feed the fact contract wrong
numbers that look right.

The two variants, the same day, at full resolution (2,480 pixels):

| Model | Capture | Character error rate | Hard values found | Seconds per page |
|---|---|---|---|---|
| 8B | steuermahnung-brief_scan | 0.060 | 15 of 21 | 5.3 |
| 8B | bourse-etudes-decision_scan | 0.044 | 12 of 22 | 5.3, 3.2 |
| 70B | steuermahnung-brief_scan | 0.118 | 17 of 21 | 12.6 |
| 70B | bourse-etudes-decision_scan | 0.041 | 13 of 22 | 12.1, 7.6 |

At full size the 8B reads the German page it had declined at 1,600 pixels, and both
models read most of the text; what they get wrong are digits, and they get them wrong
in ways that look right. The German IBAN `CH00 0839 4100 2786 5310 4` came back as
`CH00 0839 4100 2756 3510 4` from the 8B and `CH00 0999 4100 2736 5510 4` from the
70B; the French IBAN with two digits swapped on both; the AVS number
`756.4719.2083.50` as `756.4716.2088.50` from the 70B; the 78-day period as `76 Tage`
from both; an amount, an address, e-mail addresses and a payment date are lost as
well. The 70B finds a few more values, has the higher character error rate on the
German page and takes 2 to 2.5 times as long. Decision D-N: a transcription that
turns an IBAN into another plausible IBAN cannot feed a fact contract whose point is
that such numbers survive exactly; image input stays future work, named in the report
with these numbers (WP12a and WP12b cut).

### Vocabulary in the pipeline: P2 on the dev pairs on CSCS (7 October 2026)

Three runs of P2 on the 12 dev pairs (10 German, 2 French) with the settings of the day
(8B writer, 70B judge, thinking for Understand and Judge, 3 repair rounds, 1 facts round
of up to 10 facts): without the vocabulary (`USE_VOCABULARY=0`), with all of it
including the word list in the write prompt (a setting of that day, removed since),
and with all of it
but the word list, the default since. The Understand prompt did not change, so the three
runs got the same Understand answers from the response cache; their fact sheets differ
only by what code added. Write, judge and repair calls are fresh, one run per setting.
One job failed on the side without the vocabulary (`sg-el-costs-de`: the 8B copied the
prompt's JSON example twice) and was run again. The run with the list started before two
fixes of the matcher (the lemma of a noun no longer stands for a verb: `recourir` is no
`recourant`; `dès lors` is no `dès`); all rows were scored again with the final code
(`eval rescore`), so one checker measures all three. Results in
`eval/results-cscs-vocab-off`, `-on` and `-nolist`, each with its `-rescored-facts`.

| Mean of the 12 pairs | without | with the list | default (no list) |
|---|---|---|---|
| Hard terms used without a glossary entry, per draft | 2.3 | 1.0 | 0.1 |
| Glossary entries per draft (added by code) | 4.4 (0) | 7.4 (1.9) | 7.1 (1.6) |
| Glossary entries whose explanation breaks a rule | 38 of 53 (72%) | 40 of 89 (45%) | 42 of 85 (49%) |
| Fact sheet hard terms with the vocabulary's explanation | 0 of 82 | 45 of 114 | 45 of 114 |
| Office words in the first drafts (sum) | 33 | 58 | 20 |
| Office words in the final drafts (sum) | 46 | 37 | 42 |
| Office words per 100 blocks, final drafts (median) | 7.1 | 4.2 | 7.0 |
| Fact coverage | 0.74 | 0.74 | 0.76 |
| Hard facts kept | 0.79 | 0.81 | 0.72 |
| Invented values per draft | 0.08 | 0.25 | 0.17 |
| Rule errors per 100 blocks | 4.1 | 5.9 | 3.5 |
| Rule warnings per 100 blocks | 58.9 | 60.5 | 51.7 |
| Readability (Amstad, Kandel-Moles) | 54.6 | 56.0 | 54.1 |
| Judge: facts missing, distorted | 7.3%, 3.8% | 3.4%, 3.8% | 6.0%, 6.2% |
| Judge: unsupported statements per 100 blocks | 3.3 | 2.7 | 5.1 |
| Repair rounds | 2.1 | 1.9 | 1.9 |

- What code does with the vocabulary works as built, in both runs: the hard terms a
  draft uses without an explanation fall from 2.3 to 1.0 and 0.1 per draft, the
  glossary grows from 4.4 to about 7 entries, 45 of the 114 hard terms carry the checked
  explanation, and the share of glossary explanations that break the rules falls from
  72 to 45 and 49 percent.
- The word list primes the 8B. With it, the first drafts have 58 office words; without
  it 20, and 33 without any vocabulary. Words the writer without the vocabulary never
  used turn up from the list: `grundsätzlich`, `Wohnsitz`, `falls`, `zugestellt`,
  `elterliche Sorge`. The polish round with LEX-07 removes most of them again, so the
  final drafts end in the same range (37, 42 and 46 office words). The list was
  therefore removed again (version 9): about the same final drafts without the detour.
  Worth another try with a later Apertus; not tried yet: a list that names only the
  everyday words.
- Facts, invented values, the judge's findings and the rule errors move in both
  directions, by single pairs: in the default run the 8B wrote a first draft of 7 blocks
  for `sg-el-costs-de` (20 facts missing; the repair and facts rounds refilled it with
  near-copies of the source, hence 74 office words per 100 blocks) and one of 29 blocks
  for `be-tax-extension-fr` (14 facts missing, never recovered); in the run with the
  list a repair answer for `sg-el-costs-de` was broken JSON. One run per setting cannot
  separate effects of this size from that variance; a second run of each, or the 23
  eval pairs, would.

### The vocabulary round: P2 on the dev pairs on CSCS (7 October 2026)

The default of the section above (vocabulary on, no word list) once more, with the
vocabulary round on. The round comes after everything else, so the
run replayed every earlier answer from the response cache: all 12 jobs have the same draft
versions as the run without the round, and the comparison shows what the round alone
does. Results in `eval/results-cscs-vocab-round-v2` (and `-rescored-facts`).

| Mean of the 12 pairs | without the round | with the round |
|---|---|---|
| Office words in the final drafts (sum) | 42 | 19 |
| Office words per 100 blocks | 11.7 | 4.7 |
| Fact coverage | 0.757 | 0.757 |
| Hard facts kept | 0.718 | 0.718 |
| Invented values per draft | 0.17 | 0.17 |
| Rule errors per 100 blocks | 3.5 | 2.5 |
| Rule warnings per 100 blocks | 51.7 | 41.7 |
| Readability | 54.1 | 54.6 |
| Judge: facts missing, distorted | 6.0%, 6.2% | 5.5%, 4.1% |
| Judge: unsupported statements per 100 blocks | 5.1 | 4.8 |

- The round ran in 11 of the 12 jobs (`zh-shelters-de` had no office word left) and its
  version was kept in 8. The other 3 lost the final choice: in `zh-blue-algae-de` the
  rewrite dropped a must-keep value, in `be-tax-extension-fr` and
  `zg-disability-services-act-de` the judge, run again, found more problems. So no fact
  was lost: fact coverage, hard facts and invented values are the same to the last digit.
- In the kept versions the office words fell from 34 to 9; `sg-el-costs-de`, the draft
  the facts rounds had refilled with near-copies of the source, went from 20 to 3 and
  from 6 rule errors to 3.
- The judge's figures move with its reruns: a version whose base had judge findings is
  judged again (the existing rule after a repair round), with the judge's own variance.
  That a rewritten sentence loses its unsupported finding without a new judgment cannot
  happen: carry-over only meets versions without one.
- Cost: 12 rewrite calls of the 8B (1.4 s each) and 10 judge reruns of the 70B (11 s
  each), about 11 s per job. Part of the vocabulary since this run (`USE_VOCABULARY`).

### Fact-sheet values the source lacks: P2 on the dev pairs on CSCS (7 October 2026)

A value the Understand model computes or invents (an end of an appeal period, a day for
"im Frühling") used to count as known: FACT-01 asked for it and FACT-06 accepted it in
the draft, with only a FACT-05 warning on the fact sheet. On the team's KESB decision
this let "Die Beschwerdefrist endet am 15. November 2026" reach the draft
(use-case-decisions.md §7). Since this run such a value is neither required (FACT-01)
nor accepted (FACT-06), and fact coverage counts only facts whose value the source
contains. FACT-01 and the source check use the same matching, so a fact the source check
rejects could never be satisfied by a faithful draft either.

How often, in the stored fact sheets of `eval/results-cscs`: 8 of 195 values (P1, 23
pairs), 12 of 331 (P2 8B, 35 pairs), 16 of 207 (70B writer), almost all must-keep. Some
are inventions ("31. März 2026" for "im Frühling", "1. Januar 2021" for "ab 2021", "30.
Juni 2025" for "ab Mitte 2025", "1. Januar 2026" for "innerhalb von drei Tagen nach der
Geburt"); most are normalisations no draft can match ("9" as an amount for "9 Liter",
"041 43 259 51 00" for "+41 43 259 51 00", "10" for "10 Prozent"), which FACT-01 had
flagged as missing in every version. A gap of its own: `0800 33 66 55` and `0848 35 45
55` are not found as phone numbers at all (the pattern knows three-digit area codes), so
hotline numbers are checked neither by FACT-01 nor by FACT-06. The measure alone, on the stored final drafts:
fact coverage of P2 8B on the eval pairs 81.7 to 83.1 percent, of the 70B writer 73.1 to
77.8, of P1 71.1 to 72.4.

The pipeline effect, P2 on the 12 dev pairs, the old rule (patched back in by a scratch
script) and the new one in sequence on the same cache, both scored with the new measure.
Results in `eval/results-cscs-fact06-before` and `-after`.

| Mean of the 12 pairs | old rule | new rule |
|---|---|---|
| Fact coverage (new measure) | 0.788 | 0.788 |
| Hard facts kept | 0.718 | 0.718 |
| Invented values per 100 blocks | 0.47 | 0.47 |
| Rule errors per 100 blocks | 2.54 | 2.51 |
| Model calls per job | 10.6 | 10.5 |
| Tokens per page | 25,205 | 24,587 |

- Four dev pairs have a fact-sheet value the source lacks; none of them reached a final
  draft on either side. Under the old rule the repair rounds asked for them: in
  `be-birth-registration-de` the repair round and the facts round both asked for "1.
  Januar 2026", which the model did not write; under the new rule the job ends a version
  earlier.
- No fact lost and no value invented by the change; the facts no draft could match leave
  the measure, which is why fact coverage reads higher than in earlier runs.
- On the KESB decision's stored draft the new rule turns the invented deadline into a
  FACT-06 error, which blocks and goes to repair instead of reaching the reader.

### Judge doubts on values: two loop changes tried on the dev pairs on CSCS (8 October 2026), not taken

Two changes to the repair loop, found in a review of the example jobs (PLAN.md §11,
8 October), were built, measured and taken out again before the freeze. Neither touched
a template.

- **A: a judge's "missing" on a value code found as a doubt.** A judge verdict
  `missing` counts as blocking and sends the fact back to every repair and facts round,
  also when FACT-01 finds the fact's value in the draft. In `eval/results-cscs` (all
  stored P2 jobs), 11 of the 24 `missing` verdicts on facts with a value that the judge
  left on final drafts were such facts; in the French example job, f07 and f08 showed as
  red "Missing" next to a block with CHF 42'000 and CHF 61'000. The change: such a
  verdict blocks nothing and no round asks for the fact again.
- **B: a missing fact asked for by its clause.** Code completion gives a fact the whole
  source sentence as its text, cut at 200 characters. In the German example job, f07
  (the residence date 1. Januar 2027) shares its sentence with the income limits; asked
  for f07 in two rounds, the 8B wrote the CHF 9'000 per child rule both times and never
  the date. The change: the repair request lists such a fact with the clauses around its
  value that hold no other value ("Anspruchsberechtigt sind Personen, die am 1. Januar
  2027 ihren zivilrechtlichen Wohnsitz in der Gemeinde Musterwil haben …"), taken from
  the full source sentence. On the stored fact sheets it cut 19 of 419 distinct facts
  with a value.

The measurement: P2 on the 12 dev pairs, the committed code (`cd92aec`, run from a copy)
and then the code with A and B, in sequence on the same cache, so the second run
replayed every request that did not change. Results in `eval/results-cscs-ab-before`
and `eval/results-cscs-ab-after`. German, 10 pairs:

| Mean of the 10 pairs | before | with A and B |
|---|---|---|
| Fact coverage | 79 % | 74 % |
| Hard facts kept | 71 % | 64 % |
| Silent losses | 0 % | 0 % |
| Invented values / 100 | 0.77 | 0.77 |
| Judge: unsupported / 100 | 5.8 | 6.1 |
| Rule errors / 100 | 3.1 | 4.3 |
| Must-keep values missing (sum) | 29 | 38 |
| Model calls per job | 10.6 | 10.4 |

The two French pairs and five German pairs came out identical, every draft version the
same: no request of theirs changed. Two German pairs (`be-birth-registration-de`,
`ebgb-inclusion-initiative-de`) got a changed first repair request through B, the full
source sentence instead of the 200-character copy without any cut, and ended with
different drafts but the same fact numbers. The other three ended worse, each after one
fresh 8B answer:

- `zh-blue-algae-de` (A): the second repair round no longer asked for f05, which the
  judge called missing although "Rufen Sie 0800 33 66 55 an." stood in the draft; the
  judge was wrong. Asked again in the run before, the 8B had rewritten the contact
  sentences with their names, and that path kept two more hard values.
- `sg-el-costs-de` (B): one fact of the second repair round was cut to its clause, and
  every sentence the 8B added in that round came out as a fragment ("Bei Personen in
  einer Einrichtung für Menschen mit einer Behinderung."): it took up the style of the
  excerpt. 8 must-keep values were still missing at the end, against none.
- `lu-cost-approval-de` (B): the first repair request changed without any cut, since a
  code fact's text became the full source sentence instead of the 200-character copy;
  the fresh answer ended with one fact less.

Five changed pairs are too few to separate the changes from the noise of the 8B's
answers, but three ended worse and none better, so neither change went into the
pipeline before the final run. The review page keeps the display part of A,
which changes no number: such a verdict shows in amber as "judge doubts" with the
judge's note instead of a red "missing" (`FactRow.status` in `web/views.py`), since code
finds the value and in every case checked (the French example's f07 and f08, f05 above)
the judge had overlooked it. The pipeline still counts it as blocking and asks for the
fact again.

### Judge agreement with blind labels (8 October 2026)

The labelling sheets of `eval/labels/dev` (`eval sample` on the P2 dev drafts of 6
October, CSCS, judge `Apertus-v1.5-70B-thinking`; 30 facts and 30 blocks, drawn evenly
over the judge's verdicts) were labelled by an AI assistant (Claude) that saw the sheet
only, never the key, and then scored with `eval kappa`:

| Items | Labelled | Agreement | Cohen's κ |
|---|---|---|---|
| Blocks: supported or unsupported | 30 | 80 % | 0.60 |
| Facts: present, missing or distorted | 29 | 38 % | 0.08 |
| Facts: present or not | 29 | 62 % | 0.22 |

One fact item stayed unlabelled: its fact-sheet entry reads "Keine spezifische
Definition im Dokument." with no value and no source. Readings:

- The block verdicts (SEM-06) are usable as a pointer: 12 of 15 flagged blocks were
  unsupported (mostly the prompt-example leaks of that day: dog tax, parking card),
  3 of 15 passed blocks were not ("Montag bis Freitag" added to opening hours, two
  dog-tax sentences from the examples); the 3 flagged blocks the labels pass are close
  paraphrases ("Einige Blaualgen bilden giftige Stoffe.").
- The fact verdicts are not. Seven times the judge said "distorted" where the draft
  lacks the fact; in 5 of the 18 disagreements its note describes another fact than
  the one it is filed under (a note about "CHF 40 pour 8 mois" under the fact
  "Nouvelle date limite: 15 novembre", one about "Uferbereich" under an opening time).
  The judge receives the facts as a numbered list; filing notes under the wrong id
  points at the response format, not at the reading. A candidate for the judge prompt
  after the deadline: one fact per check with its text repeated in the answer.
- This is why fact coverage, hard facts kept and silent losses are measured by code,
  and why the review page shows a judge verdict that code contradicts as a doubt.

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
| 7 | 2026-10-07 | Judge prompt (German and French): one more rule, SEM-08, an obligation, a possibility or a condition that changed (`müssen` to `können`, a `wenn` written as `vielleicht`); the judge filter accepts it (decision D-P, PLAN.md WP15 piece 4). All four standard templates in both languages get one line, `{% if mode is defined and mode == "decision" %}{% include "<lang>/decision.md" %}{% endif %}`, which renders to nothing for a standard job (same prompt text, same cache key; the template hash changes once) and pulls in the stage's section of the new partial `decision.md` for a job in the decision mode (docs/use-case-decisions.md; first draft, free to change after the freeze). |
| 7 | 2026-10-07 | No further template change. Code: the missing-fact lines of a repair request name the exact form of the value next to the fact sheet's; LEN-02 findings carry a rewrite recipe per conjunction as the suggestion; facts-only rounds after the repair loop (`MAX_FACTS_ROUNDS`, default 1); a record per repair round of the request, the answer and what code dropped; `eval diagnose` for the fact-retention diagnosis; silent losses in the evaluation; the image input spike script. Dev rerun on CSCS the same day ("Fact-retention diagnosis" above): missing must-keep values from 50 of 102 to 16 of 122, fact coverage 75 against 68 percent without the facts rounds, no invented value on either side. |
| 7 | 2026-10-08 | No template change. Code, from the second and third dev runs: the code completion takes the values from the document text with segment offsets and stores a percentage as `10%`; a value counts as covered only when a reader who searches the fact sheet for it finds it; the final version is the one with the fewest must-keep values missing, then the fewest blocking findings; an unusable repair answer no longer cancels the facts round; `eval rescore` scores stored jobs under either rule without a model call. |
| 8 | 2026-10-07 | Write prompt (German and French): after the fact sheet, the office words of the document part with their everyday word, from the vocabulary (`Diese Wörter aus dem Dokument sind schwer. Schreiben Sie stattdessen das einfache Wort:`, `Ces mots du document sont difficiles. Écrivez plutôt le mot simple :`, at most 15). The block renders to nothing when the part has no office word or with `USE_VOCABULARY=0`: the prompt is then the same text as before. The generated style guide gets a LEX-07 line in German (`Nehmen Sie Alltags·wörter statt Amts·wörtern ...`), and in French the administrative words move from the LEX-01-FR line to a LEX-07-FR line. Code: the fact sheet's hard terms get the vocabulary's checked explanations and up to 6 terms of the source; code adds missing glossary entries from the vocabulary after the write stage and every repair round; LEX-07 and LEX-07-FR findings go to the polish round (docs/rules.md "Vocabulary"). Dev run on CSCS with and without: "Vocabulary in the pipeline" above; after it the word list is off by default (`VOCABULARY_PROMPT=0`), because it primed the 8B to write the listed office words. |
| 8 | 2026-10-07 | No template change. Code: the vocabulary round, a last round through the repair prompt for the office words still in the best version (LEX-07 findings alone, each sentence with its everyday word); its version takes the next free number and is kept only if it loses no must-keep value and adds no blocking finding. Measured with every earlier answer replayed from the cache ("The vocabulary round" above): office words in the final drafts 42 to 19, no fact lost, about 11 s per job; on by default (`VOCABULARY_ROUND=1`). |
| 9 | 2026-10-07 | Write prompt (German and French): the word list of version 8 removed; the template is the text of version 7 again, so the rendered prompt is the same as before the vocabulary. The writer gets no vocabulary of office words (it primed the 8B); the office words are handled after writing, by LEX-07 and the vocabulary round. One switch, `USE_VOCABULARY`, for the vocabulary's other uses, the vocabulary round included. |
| 9 | 2026-10-08 | No template change. Code: the copy guard renders the write and repair prompts with the style guide of both levels, so the guide's lines (without their list marker) and its example values (`044 123 45 67`, `4. Februar 2026`) count as the prompt's own text; a decision-mode draft on the 8B had carried the style guide as a section of the draft (7 October). The value kind `phone` takes the ten-digit service numbers in both groupings (`0800 33 66 55`, `0848 35 45 55`), which were four plain numbers before, so FACT-01, FACT-06 and the hard-fact metric see the emergency pages' hotlines; SOURCE and REF recomputed. |
| 9 | 2026-10-08 | Decision partial only (`decision.md`, German and French; no standard template and no hash changes), from the test runs of 7 October (use-case-decisions.md §7): the values of the header and the reasoning are background unless a core answer cites them; a period is copied as written, with its start, and never computed to an end date (the Understand model had written "endet am 15. November 2026"); a task stays with its owner in the fact sheet and the draft ("Die Beiständin bezahlt Ihre Rechnungen", not "Sie bezahlen"), and the judge reports a "Sie" that takes the deputy's task as SEM-03 and a computed date as SEM-10. Code the same day: `rules/decision.py` (protected parts, FACT-07, FACT-08), the judge filter for SEM-09 and SEM-10 in decision mode, the notice in the exports, the form fields. |
| 10 | 2026-10-08 | Understand and write prompts (German and French): one more include line each, `{% if medication is defined and medication %}{% include "<lang>/medication.md" %}{% endif %}`, and the new partial `medication.md`. Code switches it on for Understand when the source has a dose or a dosing scheme (`rules/medication.py`, `has_doses`) and for Write when the fact sheet names a medication; it asks for one fact of kind `medication` per drug with the name alone as the value, and for one list item per medication with name, dose, scheme and duration. No evaluation source has a dose (checked on the 35 standard texts and the decision), so every evaluation prompt renders byte for byte as before; the template hash changes once. Code the same day: the value kind `medication` (rules/values.py), FACT-09 (a medication in one block with its dose, scheme and duration; repairable on the block that names it), medication facts first among the missing facts of a repair round, and the Mediopunkt step leaves the names alone (docs/rules.md). |
| 10 | 2026-10-08 | No template change and no pipeline change. Tried on the dev pairs and not taken ("Judge doubts on values" above): a judge's `missing` on a fact whose value FACT-01 finds as non-blocking, and a missing fact asked for by the clause of its value; with both, five of ten German jobs took another path, three ended worse and none better. Kept: the review page shows such a verdict in amber as "judge doubts". |
| 10 | 2026-10-08 | No template change. Code, from the example jobs: a block without a source sentence takes those of the facts it names, else the one it says in other words (`stages.wording_source`), and a sentence id the source does not have is dropped (FACT-03, and the judge sees the sentence); a hard term of the model that the source does not contain leaves the fact sheet (`stages.in_source`; the Understand example's office for 6 documents); the examples' office (`Einwohnerkontrolle`, `contrôle des habitants`) is a topic word of the copy guard. P2 on the 12 dev pairs on CSCS, the committed code (`eval/results-cscs-ab-before`) against these changes on the same cache (`eval/results-cscs-prov-after`): five pairs identical; fact coverage 76 to 81 percent, hard facts kept 69 to 76, must-keep values missing 43 to 33 in all, rule errors 2.7 to 2.3 per 100 blocks, unsupported 5.3 to 6.2, invented values 0.64 to 0.85. Of the seven changed pairs three ended better (be-tax-extension-fr, fact coverage 13 to 94 percent after the copied term "case number" left its fact sheet), two worse (sg-el-costs-de lost three values after the copy guard sent back an Understand answer with the office; bwl-emergency-supplies-fr gained an invented period), two mixed: too few pairs to separate the changes from the 8B's noise. |
