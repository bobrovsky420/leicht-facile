# Apertus 1.5 in Leicht·Facile: where it falls short, with evidence

Status: 10 November 2026. Written for the Apertus development team. It collects every
measurement and observation the project made with Apertus 1.5 8B and 70B between 5
October and 8 November 2026, set against the other models that ran the same pipeline on
the same pages: Qwen 3.5 9B, gpt-oss-20b and -120b, GPT-5.4-nano, GPT-5.6-luna and
Claude Haiku, Sonnet and Opus 5.5. The aim is to show, with numbers and examples, where
Apertus needed the most help and what would help it most. Where Apertus did as well as
or better than the others, this document says so too (§6), and §7 names the limits of
the evidence. Sources are the project's records in this folder
([model-comparison.md](model-comparison.md), [prompts.md](prompts.md),
[evaluation.md](evaluation.md), [evaluation-publicai.md](evaluation-publicai.md),
[image-input.md](image-input.md), [history/](history/),
[hardware/aws-l4-2026-10-10/](hardware/aws-l4-2026-10-10/)), the stored evaluation jobs
under `eval/` (git-ignored), and the project's working notes of the same weeks.

## 1. Summary

Leicht·Facile drafts easy-language versions (Leichte Sprache, FALC, lingua facile) of
official texts and promises that every date, amount, deadline and contact detail
survives exactly, checked by code. With the full pipeline around it, Apertus keeps the
hard facts as well as any model we tried: 97 % of them in German with the 8B writing
and the 70B judging, the best of the fourteen published runs, tied with gpt-oss-120b.
Most of that is the pipeline's doing, though. The pipeline was built on the 8B, and a
good part of its code exists because of what the 8B did. The gaps, most important first:

1. **The first draft keeps the fewest facts and needs the most repair.** Scored with
   the same rules, the first drafts of Apertus keep 61 % (8B) and 69 to 71 % (70B) of
   the source's hard facts in German; those of gpt-oss, the OpenAI and the Claude models
   keep 79 to 84 %, Qwen 3.5 9B 68 % (§3). The judge, repair and recover rounds bring
   the 8B to 97 %. Even after those rounds the 8B's drafts carry the most rule errors
   and warnings of every run in German (3.7 errors and 41.5 warnings per 100 blocks,
   against 0.0 to 1.7 and 7.6 to 34.3 for the eight other models). In French all three
   Apertus runs end with the most errors (3.3 to 3.5 per 100 blocks, every other run 0.0
   to 1.2).
2. **Instruction following in long, structured prompts.** The 8B copies the prompt's
   own examples into real drafts: the JSON form word for word (4 of 12 drafts on one
   day), the examples' phone numbers (8 of 12 final drafts of the same run), the topic
   of a few-shot example (dog-tax sentences in a page about supplementary benefits), and
   once the style guide as a section of the draft. The 70B judge cited the example's
   block id in 46 of 179 verdicts. Asked to fix a flagged sentence, both sizes tend to
   add new sentences instead of changing or removing it.
3. **Reasoning has no budget.** With thinking on, the 8B's reasoning ran from 3,000 to
   17,000 characters for one 400-word letter, and on our own GPU it hit the 12,000-token
   cap in Understand in both jobs, 744 s for that call alone. Apertus thinks fully or
   not at all; gpt-oss and the OpenAI models take an effort level, and gpt-oss ran its
   whole evaluation with a little thinking at effort low. Without thinking, both
   sizes answered a simple time sum wrong in 16 of 16 calls.
4. **Long documents are unstable.** The same 7-page text came out as an 8-block, 43-word
   draft on one day and a 140-block draft with 47 rule errors the next; a French
   4,165-word page came out as 117 words keeping 4 of 15 hard facts, the fewest of all
   runs (Qwen 3.5 9B kept 5, the Apertus 70B 11 and 12, the best runs 12).
5. **The 70B as a fact checker is close to chance.** Against blind labels (made by an AI
   assistant) its fact verdicts reach Cohen's κ 0.08 (block verdicts 0.60), it files
   notes under the wrong fact id, and on six school letters 27 of its 32 "missing"
   verdicts named a fact the draft stated in other words.
6. **Structured output on long inputs.** JSON slips (id ranges written as "s0064 bis
   s0087", unclosed objects, wrong brackets, short unicode escapes, a missing `facts`
   field) made about 1 in 25 Understand answers unusable on the first try; the project
   repairs each kind in code.
7. **Image input loses digits and normalises names.** The server keeps at most about
   1400 x 1400 pixels of an image, so a whole A4 scan turns IBANs and AVS numbers into
   other plausible numbers; in strips the 8B reads every digit, but unfamiliar names
   become familiar ones (`Exempleville` as `Exampleville`, inside e-mail addresses too).
8. **Serving and availability, not the model, cost the most time.** One long thinking
   stream in four was cut by the CSCS endpoint; one 70B answer never got through in 35
   attempts; the Public AI gateway ignores the thinking switch on both sizes, routed the
   `-thinking` names to Apertus 1 or refused them, and refused or timed out the 8B on 11
   of the 34 days from 6 October to 8 November. No 1.5 8B is on the Hugging Face router
   or OpenRouter, and there is no official GGUF.

## 2. What was measured

**The task.** A standard-language page of a Swiss administration goes in; a draft at
level A2 (or B1) comes out for a person to review. The pipeline
([architecture.md](architecture.md) §4): *Understand* writes a fact sheet as JSON
(core questions, facts with values and source sentence ids, droppable passages, hard
terms); code completes it with every date, amount, phone number and other hard value it
finds; *Write* drafts the text as JSON blocks citing facts and sentences; code checks
the rules of [rules.md](rules.md) (sentence length, passives, negation, compounds,
numbers, missing and foreign values); the *Judge* (a model) reports unsupported and
distorted statements; *Repair*, *Recover* and *Polish* rounds fix what is flagged. All
instructions are in the document's language.

**The pairs.** The `eval` split: 20 German and 3 French pages of Swiss cantons and the
federation, each with its official easy-language version; for the 70B on Public AI also
8 pages each of Germany and Austria and 9 Italian ones. Fact coverage, hard facts kept,
silent losses, values not in the source and rule findings are measured by code; the
judge columns are each run's own judge.

**The runs** (full list in [model-comparison.md](model-comparison.md)):

| Run | Date | Endpoint | Thinking |
|---|---|---|---|
| Apertus 1.5 8B writes, 70B judges | 12 Oct | CSCS inference API | Understand and Judge (`-thinking` names) |
| Apertus 1.5 70B everywhere | 12 Oct | CSCS | Understand and Judge |
| Apertus 1.5 70B everywhere | 3 Nov | Public AI gateway | none (the gateway ignores the switch) |
| Qwen 3.5 9B (Q4_K_M) | 24 Oct | Ollama on a laptop | none |
| gpt-oss-20b writes, 120b judges | 25 Oct | Groq via Hugging Face | always, effort low |
| gpt-oss-120b everywhere | 8 Nov | Groq via Hugging Face | always, effort low |
| GPT-5.4-nano, GPT-5.6-luna | 25 Oct | OpenAI | none |
| Claude Haiku 5.5, Sonnet 5.5 | 25 Oct | Anthropic | none |
| Claude Opus 5.5 | 27 Oct | Anthropic | always (cannot be switched off) |

## 3. The results side by side

German, 20 pairs, the final drafts of the full pipeline (P2), as published in
[model-comparison.md](model-comparison.md). "Compounds left to code" counts the long
compounds code had to mark after the model; the judge columns are left out because each
run had its own judge.

| Run | Hard facts kept | Errors / 100 blocks | Warnings / 100 blocks | Readability (Amstad) | Compounds left to code / 100 blocks | Tokens / page | USD / page | s / page |
|---|---|---|---|---|---|---|---|---|
| Apertus 8B, 70B judges (CSCS) | 97 % | 3.7 | 41.5 | 52 | 34.1 | 33,392 | 0.016 | 60 |
| Apertus 70B (CSCS, 19 pairs) | 96 % | 0.5 | 22.2 | 57 | 29.2 | 22,295 | 0.025 | 60 |
| Apertus 70B, no thinking (Public AI) | 94 % | 2.4 | 23.4 | 57 | 29.4 | 28,528 | 0.032 | 40 |
| Qwen 3.5 9B (laptop) | 87 % | 0.3 | 27.9 | 55 | 28.2 | 28,876 | - | 588 |
| gpt-oss-20b, 120b judges | 94 % | 1.7 | 31.9 | 46 | 43.6 | 20,197 | 0.005 | 12 |
| gpt-oss-120b | 97 % | 0.5 | 29.1 | 47 | 45.4 | 26,702 | 0.008 | 14 |
| GPT-5.4-nano | 93 % | 0.7 | 34.3 | 48 | 47.2 | 38,935 | 0.019 | 87 |
| GPT-5.6-luna | 90 % | 0.4 | 21.0 | 44 | 19.9 | 38,070 | 0.017 | 84 |
| Claude Haiku 5.5 | 92 % | 0.9 | 29.9 | 57 | 15.6 | 46,648 | 0.009 | 33 |
| Claude Sonnet 5.5 | 91 % | 0.0 | 17.5 | 59 | 2.6 | 68,069 | 0.239 | 73 |
| Claude Opus 5.5 | 91 % | 0.0 | 7.6 | 59 | 1.7 | 58,324 | 0.498 | 128 |

French, 3 pairs (too few for more than a direction):

| Run | Hard facts kept | Errors / 100 blocks | Warnings / 100 blocks | Readability (Kandel-Moles) |
|---|---|---|---|---|
| Apertus 8B, 70B judges (CSCS) | 72 % | 3.5 | 25.8 | 70 |
| Apertus 70B (CSCS) | 89 % | 3.4 | 17.4 | 80 |
| Apertus 70B, no thinking (Public AI) | 91 % | 3.3 | 19.0 | 76 |
| Qwen 3.5 9B | 72 % | 0.0 | 12.5 | 81 |
| gpt-oss-20b, 120b judges | 83 % | 0.0 | 46.3 | 70 |
| gpt-oss-120b | 90 % | 0.6 | 55.0 | 75 |
| GPT-5.4-nano | 93 % | 0.4 | 40.4 | 71 |
| GPT-5.6-luna | 80 % | 0.5 | 22.8 | 74 |
| Claude Haiku 5.5 | 83 % | 0.9 | 21.3 | 80 |
| Claude Sonnet 5.5 | 91 % | 0.4 | 10.9 | 79 |
| Claude Opus 5.5 | 83 % | 0.0 | 0.0 | 80 |

**The first drafts.** The tables above show what the pipeline makes of each model. The
first draft, one Write call on the model's own fact sheet before any judge or repair
round, shows more of the model itself. Scored for this document on 10 November 2026 with
the rules of that day, from the stored jobs of the same runs (the final drafts, scored
the same way, reproduce the tables above within 2 points). German, 20 pairs (the 70B on
CSCS 19):

| Run | Words | Hard facts kept | Must-keep facts found | Errors / 100 blocks | Warnings / 100 blocks | Readability | Values not in source / 100 blocks |
|---|---|---|---|---|---|---|---|
| Apertus 8B (CSCS) | 268 | 61 % | 61 % | 9.6 | 45.7 | 49 | 0.14 |
| Apertus 70B (CSCS) | 145 | 69 % | 72 % | 3.7 | 23.6 | 57 | 0.00 |
| Apertus 70B, no thinking (Public AI) | 191 | 71 % | 78 % | 3.2 | 24.7 | 56 | 0.16 |
| Qwen 3.5 9B | 143 | 68 % | 79 % | 4.5 | 30.9 | 53 | 0.38 |
| gpt-oss-20b | 135 | 81 % | 87 % | 14.2 | 57.4 | 42 | 0.50 |
| gpt-oss-120b | 143 | 81 % | 84 % | 7.2 | 45.1 | 46 | 0.00 |
| GPT-5.4-nano | 454 | 79 % | 86 % | 2.1 | 33.2 | 48 | 0.00 |
| GPT-5.6-luna | 380 | 82 % | 93 % | 1.2 | 19.6 | 45 | 0.14 |
| Claude Haiku 5.5 | 239 | 84 % | 91 % | 4.7 | 33.4 | 55 | 0.33 |
| Claude Sonnet 5.5 | 414 | 84 % | 91 % | 0.3 | 14.8 | 61 | 0.09 |
| Claude Opus 5.5 | 441 | 80 % | 88 % | 0.0 | 9.6 | 59 | 0.00 |

- The Apertus first drafts keep 8 to 23 points fewer hard facts than gpt-oss, the
  OpenAI and the Claude models; the 70B is at the level of Qwen 3.5 9B. "Hard facts
  kept" needs no fact sheet (it counts the source's dates, amounts, numbers and
  addresses in the draft), so this column compares across runs; "must-keep facts found"
  is measured against each run's own fact sheet.
- It is not only brevity: the 8B writes longer first drafts than the 70B, Qwen and
  gpt-oss and still keeps the fewest facts.
- The 8B's first drafts carry 9.6 rule errors per 100 blocks, the second most after
  gpt-oss-20b (14.2); the 70B's 3.2 to 3.7 are in the range of Qwen and Haiku. The 70B's
  first drafts read as easily as Haiku's (56 to 57), behind only Sonnet and Opus.
- French (3 pairs): the first drafts keep 63 % (8B), 52 % and 47 % (70B) of the hard
  facts, against 46 to 89 % for the others (Qwen 46 %, gpt-oss-20b 49 %, Haiku 58 %,
  Sonnet 89 %). The 70B's French first drafts are clean (0.9 and 2.1 errors per 100
  blocks), and the rounds raise that to 3.3 and 3.4: the sentences added to bring back
  the facts break the rules. For every other model the rounds lower the French errors
  (gpt-oss-120b from 14.1 to 0.6, Sonnet from 2.1 to 0.4).

## 4. The gaps in detail

Each gap names what we saw, the evidence, how the other models did where we know it,
and what the project built around it. "Apertus-specific" means seen with Apertus and
not, or much less, with the other models on the same pipeline; "serving" means the
endpoint, not the weights.

### 4.1 First drafts: facts dropped while writing

- **The rounds do most of the work.** On the 20 German eval pairs (CSCS, 12 October) a
  single Write of the 8B with the completed fact sheet (condition P1) found 61 % of the
  must-keep facts and kept 59 % of the hard facts; the full pipeline (P2) found 100 % and
  kept 97 %. Over three final runs of 10 to 12 October, P1 found 53 %, 74 % and 61 %: the
  first draft varies a lot from run to run, the pipeline's result does not (98.5 %, 100 %,
  99.6 %). The 70B without thinking on Public AI does better on its own (P1: 77 % found,
  70 % kept) but still needs the rounds for its 94 %.
- **Against the other models,** the first drafts of every Apertus run keep the fewest
  hard facts: 61 % (8B) and 69 to 71 % (70B) in German, against 79 to 84 % for gpt-oss,
  GPT-5.4-nano, GPT-5.6-luna and the three Claude models (§3, "The first drafts").
- **Missing values per first draft.** In 31 stored jobs of the 70B on Public AI (the
  seven sample letters, 26 to 31 October), 135 of the 185 error findings of the first
  drafts were missing must-keep values (FACT-01), 4.4 per draft.
- **Examples.** The 8B's first draft of the team's premium-reduction letter dropped every
  CHF amount (42'000, 61'000, 9'000), which the first repair round put back. In an early
  local run the 8B listed 3 facts for a letter with 11 checkable values; code completion
  of the fact sheet exists because of it.
- **What the project built:** code completion of the fact sheet (every hard value of the
  source becomes a fact), facts and recover rounds that ask for each missing value by
  name and in the exact written form ([prompts.md](prompts.md), "Code around the
  prompts"), the final version chosen by the fewest missing values.

### 4.2 Rule compliance and style

- **The 8B writes the most rule errors and warnings** of all runs in German (3.7
  and 41.5 per 100 blocks after every repair round; §3). Its readability (Amstad 52) is
  below the 70B's and Haiku's (57) and the official versions' (62), and above gpt-oss and
  the OpenAI small models (44 to 48), which write short sentences with long words.
- **French is the weakest language for both sizes.** After every round the three Apertus
  runs keep 3.3 to 3.5 rule errors per 100 blocks in French (the hybrid, 70B reads and
  8B writes, 8.8); every other run 0.0 to 1.2. Three pairs only, but the gap is
  consistent across all three Apertus runs, and for the 70B it comes from the rounds:
  its French first drafts have 0.9 and 2.1 errors (§3).
- **Passives carried over from administrative German.** On the pages of Germany and
  Austria the 70B left 4.1 and 4.7 errors per 100 blocks, "almost all GRAM-01 passives
  ('werden nicht erstattet', 'Erstattet werden') and LEN-01" carried over from the
  source; the repair rounds did not remove them ([prompts.md](prompts.md), 30 October).
  Over the rounds of the 31 stored Public AI jobs the passives rose from 15 in the first
  drafts to 22 in the final ones: repairs introduce passives.
- **Compounds.** The 8B kept `Krankenversicherungspolice` and `Sozialversicherungsstelle`
  unsplit through two repair rounds although LEX-01 flagged them; since 6 October code
  marks the compounds itself. Code still marks 29 to 34 compounds per 100 blocks after the
  Apertus runs, about as many as after Qwen and fewer than after gpt-oss and GPT-5.4-nano
  (44 to 47), but 10 to 20 times as many as after Sonnet and Opus (1.7 to 2.6).
- **A word list primes the 8B.** Given the source's office words with their everyday
  replacements in the write prompt, the 8B wrote 58 office words in the first drafts
  against 20 without the list ([prompts.md](prompts.md), "Vocabulary in the pipeline").
  The list was removed; the replacements happen after writing.
- **English instructions made its German worse.** With English instructions for German
  documents, the 8B's repairs fixed fewer rule problems on the same input (15 against 21)
  and made more new ones (45 against 26), and Understand failed on 3 of 12 pages that the
  German prompt handles ([prompts.md](prompts.md), "English instructions").

### 4.3 Instruction following: examples, address, deletions

- **Copying the prompt's examples.** On the Public AI 8B without thinking, 4 of 12 dev
  drafts were the write prompt's JSON form itself, word for word (6 October). The
  examples' phone numbers (`031 987 65 43`, in French `032 987 65 43`) stood in 8 of 12
  final dev drafts, put there by repair additions ("Rufen Sie die DISG an: 031 987 65
  43."). On CSCS the 8B wrote
  dog-tax sentences, the topic of a few-shot pair, into a page about the costs that
  supplementary benefits cover, only 2 of 12 of them verbatim. A French final draft
  carried five sentences with the example's pet microchip ("le numéro de la puce"),
  flagged by the judge in every round and never removed (11 October). A decision-mode
  draft carried the style guide as a section. The repair guard fired 10 times in 33
  repair calls on values of the examples (6 October). The other models ran on the
  same, already guarded prompts, so we cannot say how often they would have copied; we
  did not count the guard's firings for them.
- **Asked to fix, it adds.** In a French election draft, sentences with the microchip
  grew from one block in the first draft to five in the final one: the repair rounds
  rewrote and added instead of deleting (12 October). On six school letters (70B, 31
  October) 54 of the 80 sentences the rounds added restated facts the draft already had,
  35 of them for facts nobody had asked for; the medical certificate rule stood three
  times in the final German draft. Asked to put a missing
  value into the block that already says the thing, the 70B left the block as it was and
  added the value in new sentences beside it.
- **Style taken from the excerpt.** Asked for a fact by the clause around its value, the
  8B wrote every added sentence as a fragment ("Bei Personen in einer Einrichtung für
  Menschen mit einer Behinderung."), taking up the style of the excerpt.
- **Form of address.** Without an explicit instruction, the 70B wrote the same student
  letter in Sie twice and in du once, a French student letter with vous and tu in the
  same section, and an Italian parents' letter mixing Lei, tu and voi. Since the prompt
  names the form, the German letter is right; the Italian one still mixes the forms.
- **Fact ids hung on the wrong blocks.** The 70B hangs a section's fact ids on its
  question heading ("Was müssen Sie tun?" carried three facts) and a requested fact id
  on unrelated sentences (six Italian lines restating a packing list).
- **Lists dropped without a note.** The 70B kept 2 of 7 items of a camp letter's packing
  list in German and none in French; across the 23 eval pairs with lists, 48 items stay
  dropped after every round. gpt-oss lists such items as omissions; the 70B leaves them
  out without a note
  ([history/2026-11-08-gpt-oss-tuning.md](history/2026-11-08-gpt-oss-tuning.md)).
- **What the project built:** a copy guard that sends back an answer with the examples'
  sentences, topic words or values; examples on topics outside the evaluation set; a
  check for values not in the document (FACT-06); filters that drop repeated, already
  conveyed and value-less additions; one fact per list item (FACT-10); the form of
  address as a job option.

### 4.4 Values computed or invented by Understand

- In the stored fact sheets, 8 of 195 values (P1), 12 of 331 (P2, 8B) and 16 of 207 (70B
  writer) were not in the source: inventions such as "31. März 2026" for "im Frühling",
  "1. Januar 2021" for "ab 2021", "1. Januar 2026" for "innerhalb von drei Tagen nach der
  Geburt", and normalisations no draft can match ("9" for "9 Liter").
- On a child-protection decision Understand computed the end of the appeal period, "Die
  Beschwerdefrist endet am 15. November 2026", which the source never states; it reached
  the draft before code rejected such values. One real invention reached a final eval
  draft: "bis 15. Januar" in a tax-extension page whose source names only July,
  September and November.
- The 70B turned an Austrian repayment demand into "verringert die Familien-Beihilfe um
  1.500 Euro", a benefit reduction (29 October).
- **Time arithmetic without thinking.** A short probe asked for 7.15 plus 2 h 50 min
  (10:05). Both sizes on Public AI, without thinking: 16 of 16 answers wrong (9:05,
  9.05, once 00:65; 6 November), and 1 of 2 wrong on 31 October. We did not
  put the same question to the other models, so this is no comparison; it shows why the
  pipeline wanted thinking in Understand and Judge.

### 4.5 Long documents

- **Collapse and balloon.** `zh-political-rights-de` (7.4 pages) came out of the 8B as an
  8-block, 43-word draft on 10 October, as a 140-block draft with 47 rule errors (two
  fifths of the run's errors) on 11 October and as 44 blocks on 12 October, with prompts
  that differed between the runs only by the document fence and the informal address of
  the model. In the hybrid run of 6 October, with the 70B's fact sheets, four 8B drafts
  collapsed to under 50 words (25, 30, 38, 44) and others ballooned (991 words where the
  8B's own run had 345, 2,520 where it had 659).
- **The French petitions page** (`ne-disability-petitions-fr`, 4,165 words): the 8B wrote
  117 words and kept 4 of 15 hard facts, every loss listed for the reviewer, the fewest
  of all runs. On the same page Qwen 3.5 9B kept 5, GPT-5.6-luna 7, gpt-oss-20b and Opus
  8, Haiku 9, the 70B 11 (CSCS) and 12 (Public AI), and gpt-oss-120b, GPT-5.4-nano and
  Sonnet 12 (Sonnet in 1,580 words). The page is hard for every small model: the 70B's
  first drafts kept none of the 15 values, Qwen's and gpt-oss-20b's one.
- **Pages with many values.** On a 2,422-word pension brochure with 45 hard values the
  70B wrote 293 words and kept 17; part of that is the pipeline's cap of missing values
  asked for per round.
- **Not an output limit.** The 70B's longest answers were about 1,900 tokens (Understand)
  and 3,500 (Write) against budgets of 6,000 and 8,000, and every stored repair answer
  ended with `stop`. On CSCS, 8 Write answers of the 8B on pages of 65 to 185 sentences
  did hit the 8,000-token cap in the first evaluation pass; such pages are written in two
  halves since.
- For comparison: gpt-oss-20b refused the longest French page ("I'm sorry, but I can't
  provide that.", its reasoning "Hard. Probably too large."); the larger models wrote it.

### 4.6 Reasoning: runaway length and no budget

- **On CSCS** the 8B-thinking wrote 3,000 to 17,000 characters of reasoning per
  Understand call on a 400-word letter, 1,800 to 7,000 output tokens, 12 to 90 s; without
  thinking the same call is about 1,000 tokens and 10 s. The 70B reasons about a third as
  much (Understand 19 s against 92 s for the 8B).
- **On one NVIDIA L4** (official weights, the swiss-ai vLLM image, 10 October) Understand
  hit the 12,000-token cap in both jobs (744 s each, answered by the fallback without
  thinking), and the 8B judge hit it once; one letter took 63 minutes with thinking in
  Understand and Judge, 22 minutes with thinking in Understand only
  ([hardware/aws-l4-2026-10-10/](hardware/aws-l4-2026-10-10/README.md)).
- **On the community 4-bit GGUF** reasoning ran to 3,000 to 12,000 tokens; the judge with
  thinking ran to the 12,000-token limit in about 10 minutes per call, and Write with
  thinking took 24 minutes and paraphrased the source.
- **Thinking also changed the style.** On three dev pairs, CSCS with thinking against
  the gateway without it, thinking raised fact coverage from 43 to 96 % but lowered
  readability from 66 to 53 and raised rule errors from 3.6 to 7.1 per 100 blocks.
- **The others.** Runaway reasoning is not unique to Apertus: Qwen 3.5 9B and gpt-oss at
  its default effort also ran to the budget's end. The difference is the control:
  gpt-oss and the OpenAI models take an effort level, the Claude models a thinking
  field; Apertus, like Qwen on Ollama, has only on or off (`enable_thinking`, or the
  `-thinking` model names on CSCS). gpt-oss ran its whole evaluation with a little
  thinking at effort low; Apertus could think fully or not at all.
- **What the project built:** thinking per stage, generous output budgets, a fallback
  without thinking when the reasoning runs out of tokens, Write never with thinking.

### 4.7 The 70B as judge

- **Fact verdicts close to chance.** On 30 facts and 30 blocks of the dev drafts, drawn
  evenly over the judge's verdicts and labelled blind by an AI assistant (Claude) that
  never saw the judge's answers: blocks 80 % agreement, κ 0.60; facts (present, missing,
  distorted) 38 %, κ 0.08 ([prompts.md](prompts.md), "Judge agreement with blind
  labels"). Seven times it said "distorted" where the draft lacks the fact; in 5 of 18
  disagreements its note describes another fact than the one it is filed under.
- **Paraphrase counted as missing.** On six school letters 27 of its 32 "missing"
  verdicts named a fact that a block stated in other words ("Papier vom Arzt" for the
  Arztzeugnis), repeated in every version, which drove the restatement loop of §4.3. On
  the eval stores 11 of 24 "missing" verdicts left on final drafts were values code found
  in the draft.
- **Prompt artefacts.** It cited the prompt example's own block id `b006` in 46 of 179
  verdicts (10 October); it called amounts distorted for their punctuation (42'000
  Franken for CHF 42'000.-); it objected to question headings the style rules require and
  to supplies the source does list.
- **Cost.** In the 31 stored Public AI jobs the judge was 55 % of the model time (3.7
  calls of 19.6 s per job), and 95 % of its 3,165 fact verdicts said "present".
- The other models judged their own drafts, so their judge columns do not compare; the
  blind-label check was only made for the Apertus judge. The 8B as judge was never
  measured on the eval pairs.
- **What the project built:** every fact number comes from code; the judge must quote the
  words it objects to, and a verdict whose quote is not in the draft is dropped; a
  "missing" that code contradicts is shown as a doubt.

### 4.8 Structured output

- Slips of the 8B on long fact sheets and drafts, each now repaired in code
  ([architecture.md](architecture.md) §6, "Structured output"): a run of ids written as
  a range (`"s0064" bis "s0087"`), trailing and missing commas, an object not closed
  before the next top-level key, a list or object closed with the wrong bracket, a
  unicode escape with too few digits, a German closing quote as a straight quote, core
  answers as bare sentences, `null` for a whole core question (4 of 18 French example
  builds), omissions written as blocks, an empty block `{}`.
- Even so, about 1 Understand answer in 25 was unusable on the first try (no JSON, no
  `facts` field) and passed on a retry; one dev page failed three times on three
  different slips. With English instructions, Write gave its omissions as an object
  keyed by sentence ids, and Understand copied three facts of the JSON example.
- In the first evaluation pass on CSCS (6 October) 7 P0 scorings, 9 P1 and 6 P2 jobs
  failed on answer shapes the code did not yet handle.
- On the positive side: on a short letter 20 of 20 Understand answers parsed with and
  without `response_format` (6 October), and the 70B on Public AI ran more than 150 jobs
  from 28 to 31 October without a failed stage.

### 4.9 Image input

Measured on CSCS on 7 and 9 October 2026 on two printed and scanned letters
([image-input.md](image-input.md) has every number):

- The server keeps at most about 1400 x 1400 pixels (7,879 prompt tokens), whatever is
  uploaded, so an A4 page at 300 dpi is read at about 140 dpi; the model card does not
  say so. At that size both sizes turn digits into other plausible digits (an IBAN into
  another IBAN, the AVS number `756.4719.2083.50` into `755 4716 2083 50`, 78 days into
  76, the postcode 1999 into 1899), and the whole-page runs of two days gave different
  wrong digits at temperature 0.
- In strips under the limit the 8B read every digit of both letters in three runs out of
  three; the 70B still misread an AVS digit and dropped a whole paragraph without a
  trace.
- Unfamiliar words are normalised in every setting: `Exempleville` as `Exampleville` in
  8 of 10 occurrences, inside e-mail and web addresses too, `Musterwil` as `Mustervil`.
  The 8B declined a readable page as `unlesbar` in four tokens at 1,600 pixels.
- The project keeps image input as future work. No other model was tested on the scans.

### 4.10 Speed, tokens and price

- **Tokens.** The 8B setup needs 33,392 tokens per page, half again as many as the 70B
  everywhere (22,295) and more than gpt-oss (20,197 to 26,702): its drafts need more
  rounds. The Claude and OpenAI models use more (38,000 to 68,000).
- **Speed.** On CSCS the 8B generated about 155 tokens per second and the 70B about 68,
  60 s per page either way; gpt-oss on Groq took 12 to 14 s per page. On one L4 the 8B
  generates 16.2 tokens per second, close to the card's memory bandwidth; a letter takes
  22 to 63 minutes there.
- **Price** at Public AI's list prices (CSCS charged nothing): USD 0.016 per page for the
  8B setup and 0.025 to 0.032 for the 70B, against 0.005 to 0.008 for gpt-oss on Groq,
  0.009 for Haiku, 0.017 to 0.019 for the OpenAI small models, 0.24 for Sonnet and 0.50
  for Opus.

## 5. Serving and availability

None of this is the weights, but it decided more of the project's time than any model
behaviour, and much of it is within reach of the Apertus ecosystem.

**CSCS inference API** (the reference numbers, 6 to 12 October; the project's access
ended on 31 October):

- About one long thinking stream in four was closed by the server midway (`incomplete
  chunked`), at the same rate sequential or eight in parallel; 31 of about 350 streams
  in the first evaluation run.
- The 70B's Write stream for a 7.6-page text was cut in all 35 attempts on 11 October
  and in all 9 on 12 October, so the 70B row has 19 German pairs; the same text went
  through as a short single-prompt answer. One 70B Write call was closed 8 times and
  answered on the 9th (618 s).
- A stream that never ended stalled one French pair overnight: 2 minutes of model time
  logged in 12 hours, until the job's budget stopped it.
- CSCS serves research and grants keys on application, so an adopter cannot reproduce
  the reference numbers.

**Public AI gateway** (the shipped default since 3 November;
[history/](history/)):

- The thinking switch is ignored by both sizes (`chat_template_kwargs.enable_thinking`
  true, false or absent: no reasoning, 4 to 6 output tokens; 16 calls with unique
  prompts on 6 November). The 8B thought in two of three calls on one morning and in none
  of fourteen that afternoon (6 October).
- The 8B's `-thinking` name served the older Apertus 1 8B through Featherless (6
  October); both `-thinking` names then answered 400 (13 and 28 October), then 403 (6
  November).
- The 1.5 8B was refused for our key from 28 October although listed, answered again on
  6 November, and answered 503 and 504 on 7 and 8 November while the 70B answered in
  0.7 s. The shipped
  default, with the 8B writing, failed every job while it was down.
- The 70B went to Infomaniak (Switzerland), Featherless (USA; 8 of 11 calls on 13
  October) and Phoeniqs, changing without notice; the backend shows only in LiteLLM
  headers. The gateway's response cache ignored the thinking switch; Cloudflare in front
  cut non-streamed answers after about 100 s (504); the backend's speed swung between
  about 20 and 120 tokens per second with load.
- Juelich's Blablador page describes `alias-apertus` as Apertus 1; an image test showed
  it serves 1.5 (6 November).

**Distribution and self-hosting:**

- No provider of the Hugging Face router serves the 1.5 8B (25 October, 6 November);
  OpenRouter listed 466 models and none from swiss-ai (26 October); the only Apertus on
  Ollama we found was a community quantization of Apertus 1. Self-service hosted 8B:
  none (Blablador needs an eduGAIN login, Cloudflare an approved form).
- No official GGUF; the 22 community quantizations are unofficial, and the one we used
  is text-only. Transformers and vLLM need the swiss-ai forks or image.
- The official vLLM image has only moving tags (`latest-amd64`) and needs a CUDA 13
  driver. On a 24 GB L4 it does not start with the documented settings: it needs an FP8
  KV cache and at most 16 parallel sequences, and the effect of the FP8 KV cache on
  quality is not documented.
- No draft model for speculative decoding fits the 1.5 tokenizer.

## 6. Where Apertus held up

- **Facts kept with the pipeline.** 97 % of the hard facts in German (8B with the 70B
  judging) and 96 % (70B), the best of all runs with gpt-oss-120b; every other model 87
  to 94 %. No silent loss, and no value that is not in the source, in any Apertus final
  draft; only Claude Haiku's and one gpt-oss run's had such values.
- **Readable wording from the 70B.** Amstad 57 on CSCS and on Public AI, behind only
  Sonnet and Opus (59) and ahead of gpt-oss (46 to 47) and the OpenAI small models (44
  to 48). Its words are shorter than gpt-oss's (2.00 syllables per word against 2.18;
  11 % of its words have four syllables or more, against 17 % for gpt-oss-20b) and close
  to Haiku's (1.99) and Sonnet's (1.96), and it addresses the reader more ("Sie" and
  "Ihr" 6.5 % of the words, gpt-oss 4.1 to 5.8 %).
- **The 70B with thinking writes clean German.** 0.5 rule errors per 100 blocks on CSCS,
  as clean as gpt-oss-120b (0.5).
- **Italian, Germany, Austria.** On the 70B without thinking: Italian 0.5 errors per 100
  blocks and 82 % of the hard facts (the official easy-language pages keep 31 %);
  Germany 87 % and Austria 96 %. The feared Helvetisms did not appear in German and
  Austrian drafts (the regional rules fired 0.5 and 0.0 times per 100 blocks).
- **Native-language instructions work.** German, French and Italian prompts serve the
  model better than English ones (§4.2), as the project chose.
- **Focused tasks.** Asked for one missing value with its source sentence, the 8B wrote it
  3 of 3 times in 0.5 to 3 s; the recover rounds on Public AI fixed 52 missing values and
  made nothing worse.
- **Clean characters.** Almost no non-breaking hyphens (gpt-oss-120b wrote 101 of them,
  once inside an e-mail address) and no leaked template or reasoning markers in 1,424
  stored drafts.
- **Image digits in strips.** The 8B read every digit of two scanned letters (§4.9).
- **It runs where it has to.** The 8B on one 24 GB GPU with the official image, and at 4
  bits on an 8 GB laptop GPU; open weights together with open training data, which no
  other model in the comparison offers.

## 7. Limits of this evidence

- **The pipeline was built on the 8B.** Prompts, guards and repairs were developed against
  Apertus from 5 October; the other models ran on the same code unchanged. That favours
  Apertus on the pipeline's final numbers and hides its raw behaviour; the first-draft
  table in §3 and the P1 numbers in §4.1 show more of it.
- **Small samples, one run per setup.** 20 German and 3 French pairs. Two runs of the same
  pipeline on the same dev pairs kept 100 and 82 of 140 hard facts; the single prompts
  moved by up to 8 points between days on unchanged templates. Differences of a few
  points are within the noise.
- **Thinking differs.** Apertus thought in Understand and Judge on CSCS and nowhere on
  Public AI; Qwen, the OpenAI models, Haiku and Sonnet ran without thinking, gpt-oss and
  Opus with it.
- **Judges differ.** Each model judged its own drafts, except the 8B (judged by the 70B);
  the judge columns are not compared here. The blind labels are an AI assistant's, not
  people's.
- **Scores of different days.** The published Apertus CSCS rows carry the rules of 12
  October, the later runs the rules of their day; the first-draft table scores every run
  with the rules of 10 November.
- **Our own instruments.** The rule checker and the fact matcher are the project's,
  calibrated on the official easy-language versions. A bug of ours split compounds
  wrongly until 6 November (`Sozial·versicherung·samt`); such marks in earlier drafts are
  ours, not the model's.
- **Endpoints and prices** are the providers' of the day; CSCS charged nothing, and the
  prices are Public AI's list prices.
- **Image and arithmetic** were tested on Apertus only.
- The stored jobs behind every number are on the maintainers' machine, git-ignored,
  because they contain rewrites of pages that may not be republished.

## 8. What would help most

In the order of what it would have saved us:

1. **A reasoning budget** (an effort level or a token budget) next to `enable_thinking`,
   and hosting partners that pass the switch through. The pipeline wanted a little
   thinking in Understand and Judge and got either runaway reasoning or none.
2. **Instruction following in long structured prompts in German, French and Italian:**
   use few-shot examples as style only, take every value from the document, keep a named
   form of address, delete a flagged sentence when asked instead of adding new ones.
3. **Plain-language writing,** French and the 8B first: short active sentences, no
   carried-over passives, compounds a reader can parse. The gap to the other models is
   widest in French.
4. **Stable output on long inputs:** no collapse of a 4,165-word page to 117 words, no
   swing between 43 words and 140 blocks for one page, and JSON that stays well-formed
   (no id ranges, closed objects) on fact sheets of 50 items and more; a documented JSON
   mode or guided decoding on the hosted endpoints.
5. **Fact-level verification:** a verdict filed under the fact it is about, paraphrase
   recognised as present, no citation of the prompt's own examples.
6. **Dates and times** computed correctly without thinking, and never computed when the
   source does not state them.
7. **Image input for documents:** the image budget stated in the model card and a larger
   one or tiling for A4 pages, and transcription that keeps unfamiliar names as written.
8. **Serving:** long streams that are not cut on CSCS, a hosted 8B that stays up, the 8B
   on the Hugging Face router and OpenRouter, an official GGUF, pinned image tags, and
   support upstream in transformers and vLLM.
