# Model scorecard: every tested model, task by task

Status: 11 November 2026. Every model that ran the full Leicht·Facile pipeline on the
evaluation pairs, compared task by task, with the best and the worst run of each task
marked. It draws on the published runs of [model-comparison.md](model-comparison.md),
which has the full generated tables, the stored evaluation jobs under `eval/`
(git-ignored), and the project's records of the same weeks
([prompts.md](prompts.md), [history/](history/)). The Apertus models get a document of
their own, [apertus-gaps.md](apertus-gaps.md); this one treats every model alike.

**The setup.** Every run is the full pipeline (P2: Understand, Write, rule checks by
code, a judge, repair, recover and polish rounds) on the same held-out pairs: 20 German
and 3 French pages of Swiss administrations, each with its official easy-language
version. Only the model, the endpoint and the thinking mode change. Hard facts kept,
fact coverage, silent losses, values not in the source and the rule findings are
measured by code; the judge's own columns are left out, because each run had its own
judge.

**How to read the marks.** In each column the best value among the model runs is
marked ▲ and set in **bold**, the worst ▼ in *italics*. ▲ means best and ▼ worst
whether the best is the highest number (facts kept, readability) or the lowest
(errors, price, seconds). The rows of the original and the official easy-language
version are references and never marked. Values are compared as shown,
so equal rounded values tie; a mark goes to at most three tied runs, and where more
runs share the best or the worst value, none is marked. A mark shows the extreme, not
a significant difference: two runs of the same setup kept 100 and 82 of 140 hard facts
on the dev pairs, the same gpt-oss-120b kept 97 % on Groq and 92 % on OVHcloud, and two
runs of Mistral Small 4 without thinking kept 89 and 85 % of the German hard facts.
The French columns rest on 3 pairs and show a direction at most.

## 1. The runs

| Run | Model and maker | Open | Where the text went | Thinking | Date |
|---|---|---|---|---|---|
| Apertus 8B, 70B judges (CSCS) | Apertus 1.5 8B, judged by the 70B (Swiss AI Initiative: EPFL, ETH Zurich, CSCS) | weights and training data | Switzerland (CSCS, Lugano) | in Understand and Judge | 12 Oct 2026 |
| Apertus 8B writes, 70B reads and judges (CSCS) | Apertus 1.5 8B and 70B | weights and training data | Switzerland (CSCS) | in Understand and Judge | 12 Oct |
| Apertus 70B (CSCS) | Apertus 1.5 70B | weights and training data | Switzerland (CSCS) | in Understand and Judge | 12 Oct |
| Apertus 70B, no thinking (Public AI) | Apertus 1.5 70B | weights and training data | the Public AI gateway (USA) and a compute partner of its choice | none (the gateway ignores the switch) | 3 Nov |
| Qwen 3.5 9B (laptop) | Qwen 3.5 9B, 4-bit (Alibaba) | weights | nowhere: a laptop with an RTX 4060 | none | 24 Oct |
| gpt-oss-20b, 120b judges (Groq) | gpt-oss-20b, judged by gpt-oss-120b (OpenAI) | weights | Canada or the USA (Groq, through Hugging Face) | always, effort low | 25 Oct |
| gpt-oss-120b (Groq) | gpt-oss-120b (OpenAI) | weights | Canada or the USA (Groq) | always, effort low | 8 Nov |
| gpt-oss-120b (OVHcloud) | gpt-oss-120b (OpenAI) | weights | France (OVHcloud, through Hugging Face) | always, effort low | 8 Nov |
| Mistral Small 4 | Mistral Small 4 (Mistral AI) | weights | the EU (Mistral AI) | none | 11 Nov |
| Mistral Small 4, thinking | Mistral Small 4 (Mistral AI) | weights | the EU (Mistral AI) | in Understand and Judge (effort high) | 11 Nov |
| GPT-5.4-nano | GPT-5.4-nano (OpenAI) | no | USA (OpenAI) | none | 25 Oct |
| GPT-5.6-luna | GPT-5.6-luna (OpenAI) | no | USA (OpenAI) | none | 25 Oct |
| Claude Haiku 5.5 | Claude Haiku 5.5 (Anthropic) | no | USA (Anthropic) | none | 25 Oct |
| Haiku writes, Sonnet judges | Claude Haiku 5.5, judged by Sonnet 5.5 | no | USA (Anthropic) | none | 25 Oct |
| Claude Sonnet 5.5 | Claude Sonnet 5.5 (Anthropic) | no | USA (Anthropic) | none | 25 Oct |
| Claude Opus 5.5 | Claude Opus 5.5 (Anthropic) | no | USA (Anthropic) | always (cannot be switched off) | 27 Oct |

Each model judges its own drafts unless the run says otherwise. The Apertus 70B on CSCS
has 19 German pairs: the endpoint cut its answer on one long page in every attempt.

## 2. Best and worst at a glance

German unless the task says French; the numbers are those of §3.

| Task | Best | Worst |
|---|---|---|
| Hard facts kept in the final draft | Apertus 8B, 70B judges; gpt-oss-120b on Groq (97 %) | Mistral Small 4 (85 %) |
| Pairs with every hard fact kept (of 20) | Apertus 8B, 70B judges (17) | Qwen 3.5 9B and Mistral Small 4 (10) |
| Hard facts kept in the first draft | Claude Haiku and Sonnet, Mistral Small 4 with thinking (84 %) | Apertus 8B (61 %) |
| Must-keep facts found in the first draft | Mistral Small 4 (94 %) | Apertus 8B (61 %) |
| Hard facts kept, French | GPT-5.4-nano (93 %) | Apertus 8B and Qwen 3.5 9B (72 %) |
| Values not in the source | most runs (0.0 per 100 blocks) | Claude Haiku and gpt-oss-120b on OVHcloud (0.3) |
| Silent losses | most runs (0 %) | Qwen 3.5 9B and GPT-5.6-luna (1 %) |
| Rule errors in the final draft | Claude Sonnet and Opus (0.0 per 100 blocks) | Apertus 8B (3.7) |
| Rule errors, French | five runs at 0.0 (Qwen, gpt-oss-20b, gpt-oss-120b on OVHcloud, Mistral Small 4, Opus) | Apertus 8B writes, 70B reads (8.8); of the single models Apertus 8B (3.5) |
| Rule errors in the first draft | Claude Opus (0.0) | gpt-oss-20b (14.2) |
| Warnings | Claude Opus (7.6) | Apertus 8B (41.5) |
| Passive sentences | Claude Sonnet and Opus (0.0 %) | Apertus 8B (2.6 %) |
| Long compounds left for code to mark | Claude Opus (1.7 per 100 blocks) | GPT-5.4-nano (47.2) |
| Readability (Amstad) | Claude Sonnet and Opus (59) | GPT-5.6-luna (44) |
| Readability, French (Kandel-Moles) | Qwen 3.5 9B (81) | Apertus 8B and gpt-oss-20b (70) |
| Words per sentence | Apertus 70B on Public AI (6.3) | GPT-5.4-nano (7.3) |
| Closeness to the official version (SARI) | Claude Opus (48.1) | gpt-oss-20b (40.8) |
| The longest page (15 values) | six runs with 12 of 15 | Apertus 8B (4 of 15) |
| The page with the most values (33) | every run but two (33 of 33) | Qwen 3.5 9B (22 of 33) |
| The passport page (22 values) | gpt-oss-20b, gpt-oss-120b on OVHcloud (22 of 22) | GPT-5.4-nano and Mistral Small 4 (15 of 22) |
| Repair rounds per pair | Claude Opus (1.3) | Claude Sonnet (2.1) |
| Model calls per pair | gpt-oss-20b (9.1) | Apertus 8B (13.7) |
| Tokens per page | gpt-oss-20b (20,197) | Claude Sonnet (68,069) |
| Price per page | gpt-oss-20b on Groq (USD 0.005) | Claude Opus (USD 0.50) |
| Seconds per page | gpt-oss-20b on Groq (11.5) | Qwen on the laptop (588); of the cloud endpoints gpt-oss-120b on OVHcloud (155) |
| Thinking that can be set to a little | gpt-oss and the OpenAI models (an effort level) | Apertus, Qwen on Ollama, Mistral Small 4 (on or off), Claude Opus (always on) |

In short: Claude Opus and Sonnet write the cleanest and most readable text and Opus
needs the fewest rounds, at 30 to 100 times the price of the gpt-oss runs; gpt-oss is
the cheapest and fastest, with the longest words; Apertus with its judge keeps the
most facts in the end from the weakest first drafts and with the most rule findings;
Qwen on a laptop keeps few facts and nothing leaves the machine; Mistral Small 4 is
cheap without thinking but keeps the fewest facts in the end, and thinking in two
stages brings it to 92 % at 2.5 times the price.

## 3. Task by task

### 3.1 Keeping the facts

The share of the source's hard values (dates, amounts, deadlines, phone numbers,
addresses and other exact values) that the final draft carries, found by code;
"must-keep facts found" is measured against each run's own fact sheet, "silent losses"
are values lost without being listed for the reviewer. German:

| Run | Pairs | Hard facts kept | Fact-rich pairs: hard facts kept | Pairs with every hard fact kept | Must-keep facts found | Silent losses | Values not in source / 100 blocks |
|---|---|---|---|---|---|---|---|
| Original (standard language) | 20 | 100 % | 100 % | - | - | 0 % | 0.0 |
| Official easy-language version | 20 | 67 % | 61 % | - | - | 33 % | 2.8 |
| Apertus 8B, 70B judges (CSCS) | 20 | **97 % ▲** | **97 % ▲** | **17 ▲** | 100 % | 0 % | 0.0 |
| Apertus 8B writes, 70B reads and judges (CSCS) | 20 | 94 % | 96 % | 14 | 99 % | 0 % | 0.0 |
| Apertus 70B (CSCS) | 19 | 96 % | 96 % | 16 | 100 % | 0 % | 0.0 |
| Apertus 70B, no thinking (Public AI) | 20 | 94 % | 93 % | 15 | 99 % | 0 % | 0.0 |
| Qwen 3.5 9B (laptop) | 20 | 87 % | *84 % ▼* | *10 ▼* | 99 % | *1 % ▼* | 0.0 |
| gpt-oss-20b, 120b judges (Groq) | 20 | 94 % | 93 % | 16 | 100 % | 0 % | 0.0 |
| gpt-oss-120b (Groq) | 20 | **97 % ▲** | 96 % | 15 | 100 % | 0 % | 0.0 |
| gpt-oss-120b (OVHcloud) | 20 | 92 % | 91 % | 14 | 100 % | 0 % | *0.3 ▼* |
| Mistral Small 4 | 20 | *85 % ▼* | 88 % | *10 ▼* | 100 % | 0 % | 0.0 |
| Mistral Small 4, thinking | 20 | 92 % | 91 % | 13 | 100 % | 0 % | 0.0 |
| GPT-5.4-nano | 20 | 93 % | 92 % | 15 | 99 % | 0 % | 0.0 |
| GPT-5.6-luna | 20 | 90 % | 88 % | 11 | 100 % | *1 % ▼* | 0.0 |
| Claude Haiku 5.5 | 20 | 92 % | 90 % | 12 | 100 % | 0 % | *0.3 ▼* |
| Haiku writes, Sonnet judges | 20 | 93 % | 91 % | 13 | 100 % | 0 % | 0.2 |
| Claude Sonnet 5.5 | 20 | 91 % | 89 % | 11 | 100 % | 0 % | 0.0 |
| Claude Opus 5.5 | 20 | 91 % | 89 % | 13 | 99 % | 0 % | 0.0 |

French:

| Run | Pairs | Hard facts kept | Pairs with every hard fact kept | Must-keep facts found | Silent losses | Values not in source / 100 blocks |
|---|---|---|---|---|---|---|
| Original (standard language) | 3 | 100 % | - | - | 0 % | 0.0 |
| Official easy-language version | 3 | 56 % | - | - | 44 % | 0.8 |
| Apertus 8B, 70B judges (CSCS) | 3 | *72 % ▼* | 1 | 100 % | 0 % | 0.0 |
| Apertus 8B writes, 70B reads and judges (CSCS) | 3 | 87 % | 1 | *95 % ▼* | 0 % | 0.0 |
| Apertus 70B (CSCS) | 3 | 89 % | 1 | 100 % | 0 % | 0.0 |
| Apertus 70B, no thinking (Public AI) | 3 | 91 % | 1 | 100 % | 0 % | 0.0 |
| Qwen 3.5 9B (laptop) | 3 | *72 % ▼* | 1 | 100 % | 0 % | 0.0 |
| gpt-oss-20b, 120b judges (Groq) | 3 | 83 % | 1 | 100 % | 0 % | 0.0 |
| gpt-oss-120b (Groq) | 3 | 90 % | 1 | 100 % | 0 % | 0.0 |
| gpt-oss-120b (OVHcloud) | 3 | 90 % | 1 | 100 % | 0 % | 0.0 |
| Mistral Small 4 | 3 | 77 % | *0 ▼* | 97 % | 0 % | 0.0 |
| Mistral Small 4, thinking | 3 | 91 % | 1 | 100 % | 0 % | 0.0 |
| GPT-5.4-nano | 3 | **93 % ▲** | **2 ▲** | 100 % | 0 % | 0.0 |
| GPT-5.6-luna | 3 | 80 % | 1 | 100 % | 0 % | 0.0 |
| Claude Haiku 5.5 | 3 | 83 % | *0 ▼* | 100 % | 0 % | 0.0 |
| Haiku writes, Sonnet judges | 3 | 87 % | *0 ▼* | 100 % | 0 % | 0.0 |
| Claude Sonnet 5.5 | 3 | 91 % | 1 | 100 % | 0 % | 0.0 |
| Claude Opus 5.5 | 3 | 83 % | 1 | 100 % | 0 % | 0.0 |

- Every pipeline run keeps far more than the official easy-language versions (67 % in
  German, 56 % in French), and none loses a value without a trace beyond 1 %: that is
  the pipeline's design, for every model.
- Between the models the spread is 12 points in German: the Apertus 8B with its 70B
  judge and gpt-oss-120b on Groq lead with 97 %, Mistral Small 4 without thinking
  trails with 85 % and Qwen 3.5 9B with 87 %; the Claude models end at 91 to 93 %, the
  OpenAI small models at 90 to 93 %, Mistral Small 4 with thinking at 92 %.
- Values that are not in the source appear only in drafts of Claude Haiku (0.3 per 100
  blocks, 0.2 with Sonnet judging) and of gpt-oss-120b on OVHcloud, whose three were
  e-mail addresses written with a non-breaking hyphen (fixed in code since).

### 3.2 The first draft

The first draft is one Write call on the model's own fact sheet, before any judge or
repair round: it shows more of the model and less of the pipeline. Scored on 10 and 11
November 2026 with the rules of that day from the stored jobs (scored the same way, the
final drafts reproduce §3.1 within 2 points); the run with Sonnet judging shares
Haiku's first drafts and is left out. German:

| Run | Words | Hard facts kept | Must-keep facts found | Errors / 100 blocks | Warnings / 100 blocks | Readability | Values not in source / 100 blocks |
|---|---|---|---|---|---|---|---|
| Apertus 8B, 70B judges (CSCS) | 268 | *61 % ▼* | *61 % ▼* | 9.6 | 45.7 | 49 | 0.14 |
| Apertus 8B writes, 70B reads and judges (CSCS) | 250 | 71 % | 73 % | 8.0 | 41.4 | 51 | 0.12 |
| Apertus 70B (CSCS) | 145 | 69 % | 72 % | 3.7 | 23.6 | 57 | 0.00 |
| Apertus 70B, no thinking (Public AI) | 191 | 71 % | 78 % | 3.2 | 24.7 | 56 | 0.16 |
| Qwen 3.5 9B (laptop) | 143 | 68 % | 79 % | 4.5 | 30.9 | 53 | 0.38 |
| gpt-oss-20b, 120b judges (Groq) | 135 | 81 % | 87 % | *14.2 ▼* | *57.4 ▼* | *42 ▼* | *0.50 ▼* |
| gpt-oss-120b (Groq) | 143 | 81 % | 84 % | 7.2 | 45.1 | 46 | 0.00 |
| gpt-oss-120b (OVHcloud) | 126 | 75 % | 83 % | 9.0 | 49.6 | 44 | 0.43 |
| Mistral Small 4 | 302 | 80 % | **94 % ▲** | 4.3 | 27.7 | 55 | 0.15 |
| Mistral Small 4, thinking | 294 | **84 % ▲** | 92 % | 4.4 | 31.0 | 52 | 0.09 |
| GPT-5.4-nano | 454 | 79 % | 86 % | 2.1 | 33.2 | 48 | 0.00 |
| GPT-5.6-luna | 380 | 82 % | 93 % | 1.2 | 19.6 | 45 | 0.14 |
| Claude Haiku 5.5 | 239 | **84 % ▲** | 91 % | 4.7 | 33.4 | 55 | 0.33 |
| Claude Sonnet 5.5 | 414 | **84 % ▲** | 91 % | 0.3 | 14.8 | **61 ▲** | 0.09 |
| Claude Opus 5.5 | 441 | 80 % | 88 % | **0.0 ▲** | **9.6 ▲** | 59 | 0.00 |

French:

| Run | Words | Hard facts kept | Must-keep facts found | Errors / 100 blocks | Warnings / 100 blocks | Readability | Values not in source / 100 blocks |
|---|---|---|---|---|---|---|---|
| Apertus 8B, 70B judges (CSCS) | 490 | 63 % | 72 % | 6.3 | 30.1 | 67 | 0.00 |
| Apertus 8B writes, 70B reads and judges (CSCS) | 220 | 49 % | *48 % ▼* | 5.9 | 17.6 | *47 ▼* | 0.00 |
| Apertus 70B (CSCS) | 212 | 51 % | 52 % | 2.1 | 8.9 | **81 ▲** | 0.00 |
| Apertus 70B, no thinking (Public AI) | 159 | 47 % | 50 % | 0.9 | 13.3 | 73 | 0.00 |
| Qwen 3.5 9B (laptop) | 178 | *46 % ▼* | 55 % | 1.4 | 9.9 | 80 | 0.00 |
| gpt-oss-20b, 120b judges (Groq) | 210 | 49 % | 51 % | *18.3 ▼* | 45.6 | 68 | 0.00 |
| gpt-oss-120b (Groq) | 265 | 80 % | 88 % | 14.1 | *61.6 ▼* | 75 | 0.00 |
| gpt-oss-120b (OVHcloud) | 236 | 63 % | 72 % | 10.4 | 33.3 | 72 | *0.88 ▼* |
| Mistral Small 4 | 221 | 52 % | 63 % | 8.0 | 46.8 | 74 | 0.00 |
| Mistral Small 4, thinking | 380 | 66 % | 69 % | 6.3 | 32.3 | 76 | 0.00 |
| GPT-5.4-nano | 394 | 78 % | 78 % | **0.8 ▲** | 26.0 | 72 | 0.00 |
| GPT-5.6-luna | 544 | 70 % | 87 % | 2.8 | 15.2 | 75 | 0.00 |
| Claude Haiku 5.5 | 335 | 58 % | 64 % | 2.4 | 31.4 | 77 | 0.00 |
| Claude Sonnet 5.5 | 819 | **89 % ▲** | **97 % ▲** | 2.1 | 11.9 | 78 | 0.00 |
| Claude Opus 5.5 | 723 | 80 % | **97 % ▲** | 1.7 | **5.3 ▲** | 78 | 0.00 |

- The Claude and OpenAI models, gpt-oss on Groq and Mistral Small 4 keep 79 to 84 % of
  the hard facts in the first draft, gpt-oss-120b on OVHcloud 75 %; the Apertus runs 61
  to 71 % and Qwen 68 %. The rounds then close most of the gap: at the end (§3.1) the
  Apertus 8B run is ahead of every Claude run.
- Mistral Small 4's first drafts find the most must-keep facts (94 % without thinking)
  but gain the least in the rounds: 80 % of the hard facts in the first draft, 85 % in
  the end. Its run of 10 November had 86 % in the first drafts, so two runs of one
  setup differ by 6 points before any round.
- Claude Opus writes a first draft without a rule error and Sonnet nearly so;
  gpt-oss-20b writes the most errors and warnings in its first drafts (14.2 errors),
  followed by the Apertus 8B (9.6) and gpt-oss-120b (7.2 and 9.0), and gpt-oss's first
  drafts read hardest (42 to 46).
- The OpenAI models and Claude Sonnet and Opus write long first drafts (380 to 454
  words), the Apertus 70B, Qwen and gpt-oss short ones (126 to 191 words).

### 3.3 Following the rules

Rule findings of the final drafts per 100 blocks, by the project's checker
([rules.md](rules.md)): errors and warnings, the main families, the long compounds
code had to mark after the model ("compounds left to code") and the share of
sentences in the passive. German:

| Run | Errors / 100 blocks | Warnings / 100 blocks | Sentence length (LEN) | Grammar (GRAM) | Words (LEX) | Numbers (NUM) | Compounds left to code | Sentences in the passive |
|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 31.3 | 164.5 | 49.9 | 39.7 | 99.9 | 2.8 | - | - |
| Official easy-language version | 2.7 | 27.7 | 10.1 | 6.0 | 12.9 | 0.2 | - | - |
| Apertus 8B, 70B judges (CSCS) | *3.7 ▼* | *41.5 ▼* | *17.6 ▼* | *9.6 ▼* | 11.9 | 3.2 | 34.1 | *2.6 % ▼* |
| Apertus 8B writes, 70B reads and judges (CSCS) | 3.0 | 37.6 | 16.3 | 9.2 | 9.1 | 3.4 | 32.3 | 1.9 % |
| Apertus 70B (CSCS) | 0.5 | 22.2 | 7.0 | 4.4 | 7.3 | 1.3 | 29.2 | 0.4 % |
| Apertus 70B, no thinking (Public AI) | 2.4 | 23.4 | 10.0 | 6.3 | 5.6 | 1.6 | 29.4 | 1.7 % |
| Qwen 3.5 9B (laptop) | 0.3 | 27.9 | 7.0 | 7.3 | 8.2 | 1.9 | 28.2 | 0.4 % |
| gpt-oss-20b, 120b judges (Groq) | 1.7 | 31.9 | 10.1 | 7.2 | 8.7 | 1.4 | 43.6 | 1.3 % |
| gpt-oss-120b (Groq) | 0.5 | 29.1 | 10.9 | 5.4 | 6.8 | 1.0 | 45.4 | 0.4 % |
| gpt-oss-120b (OVHcloud) | 1.6 | 26.4 | 6.2 | 8.7 | 7.1 | 1.8 | 40.0 | 1.6 % |
| Mistral Small 4 | 0.8 | 28.1 | 11.9 | 4.9 | 8.0 | 1.5 | 30.9 | 0.7 % |
| Mistral Small 4, thinking | 1.2 | 24.4 | 10.0 | 7.1 | 5.7 | 0.8 | 23.0 | 0.9 % |
| GPT-5.4-nano | 0.7 | 34.3 | 9.8 | 7.4 | *13.4 ▼* | 2.6 | *47.2 ▼* | 0.6 % |
| GPT-5.6-luna | 0.4 | 21.0 | 4.2 | 5.4 | 9.3 | 0.5 | 19.9 | 0.4 % |
| Claude Haiku 5.5 | 0.9 | 29.9 | 11.7 | 4.3 | 7.8 | *4.1 ▼* | 15.6 | 0.7 % |
| Haiku writes, Sonnet judges | 1.0 | 33.5 | 12.8 | 4.6 | 9.1 | *4.1 ▼* | 16.5 | 0.6 % |
| Claude Sonnet 5.5 | **0.0 ▲** | 17.5 | 8.0 | 2.2 | 5.5 | **0.4 ▲** | 2.6 | **0.0 % ▲** |
| Claude Opus 5.5 | **0.0 ▲** | **7.6 ▲** | **1.1 ▲** | **1.0 ▲** | **3.7 ▲** | **0.4 ▲** | **1.7 ▲** | **0.0 % ▲** |

French:

| Run | Errors / 100 blocks | Warnings / 100 blocks | Sentence length (LEN) | Grammar (GRAM) | Words (LEX) | Numbers (NUM) | Compounds left to code | Sentences in the passive |
|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 36.4 | 85.8 | 53.7 | 24.5 | 39.5 | 4.5 | - | - |
| Official easy-language version | 2.9 | 21.7 | 17.0 | 4.0 | 3.1 | 0.5 | - | - |
| Apertus 8B, 70B judges (CSCS) | 3.5 | 25.8 | 14.4 | 4.7 | 7.5 | 2.7 | 0.0 | 1.0 % |
| Apertus 8B writes, 70B reads and judges (CSCS) | *8.8 ▼* | 45.5 | 17.0 | 7.8 | 22.4 | 7.2 | 0.0 | 4.9 % |
| Apertus 70B (CSCS) | 3.4 | 17.4 | 6.0 | 4.6 | 8.4 | 1.7 | 0.0 | 3.8 % |
| Apertus 70B, no thinking (Public AI) | 3.3 | 19.0 | 6.8 | 6.6 | 6.4 | 2.5 | 0.0 | 5.6 % |
| Qwen 3.5 9B (laptop) | 0.0 | 12.5 | 1.0 | 3.1 | 6.9 | 1.6 | 0.0 | 1.6 % |
| gpt-oss-20b, 120b judges (Groq) | 0.0 | 46.3 | *17.9 ▼* | 12.3 | 12.1 | 4.0 | 0.0 | 5.5 % |
| gpt-oss-120b (Groq) | 0.6 | *55.0 ▼* | 15.5 | 9.1 | *22.6 ▼* | *8.5 ▼* | 0.0 | 0.7 % |
| gpt-oss-120b (OVHcloud) | 0.0 | 26.7 | 8.8 | 6.7 | 6.1 | 5.2 | 0.0 | 2.1 % |
| Mistral Small 4 | 0.0 | 23.6 | 7.0 | 7.5 | 6.3 | 2.8 | 0.0 | 2.1 % |
| Mistral Small 4, thinking | 1.6 | 28.1 | 11.7 | 7.0 | 9.4 | 1.5 | 0.0 | 2.7 % |
| GPT-5.4-nano | 0.4 | 40.4 | 15.6 | *15.9 ▼* | 8.2 | 1.1 | 0.0 | *8.0 % ▼* |
| GPT-5.6-luna | 0.5 | 22.8 | 9.8 | 5.5 | 5.5 | 2.5 | 0.0 | 2.8 % |
| Claude Haiku 5.5 | 0.9 | 21.3 | 8.5 | 6.5 | 4.0 | 3.3 | 0.0 | 4.3 % |
| Haiku writes, Sonnet judges | 1.2 | 29.3 | 12.5 | 8.8 | 5.8 | 3.4 | 0.0 | 5.6 % |
| Claude Sonnet 5.5 | 0.4 | 10.9 | 5.3 | 3.2 | 2.8 | **0.0 ▲** | 0.0 | 1.7 % |
| Claude Opus 5.5 | 0.0 | **0.0 ▲** | **0.0 ▲** | **0.0 ▲** | **0.0 ▲** | **0.0 ▲** | 0.0 | **0.0 % ▲** |

- Claude Opus has the fewest findings in every family in both languages; Sonnet has no
  error and the second fewest warnings in German. The Apertus 8B leaves the most errors,
  warnings, long sentences, grammar findings and passives in German.
- In French the Apertus runs end with 3.3 to 3.5 errors per 100 blocks (the hybrid
  8.8), every other run with 0.0 to 1.6; gpt-oss-120b leaves the most warnings, word
  findings and number findings there.
- Long compounds: Opus and Sonnet split them themselves (1.7 and 2.6 per 100 blocks
  left), the Claude Haiku and GPT-5.6-luna runs half way (16 to 20), Mistral Small 4
  leaves 23 and 31, the Apertus runs and Qwen about 30, gpt-oss and GPT-5.4-nano 40 to
  47.

### 3.4 Readability and closeness to the official versions

Readability by Amstad (German) and Kandel-Moles (French), higher is easier; words per
sentence; SARI, the closeness of the edits to the official easy-language version; and
the length of the draft as a share of the source. German:

| Run | Readability | Words / sentence | SARI | Length, % of the source |
|---|---|---|---|---|
| Original (standard language) | 36 | 9.8 | - | - |
| Official easy-language version | 62 | 6.1 | - | - |
| Apertus 8B, 70B judges (CSCS) | 52 | 7.0 | 42.2 | 53 |
| Apertus 8B writes, 70B reads and judges (CSCS) | 53 | 6.8 | 42.3 | 49 |
| Apertus 70B (CSCS) | 57 | 6.5 | 42.9 | 39 |
| Apertus 70B, no thinking (Public AI) | 57 | **6.3 ▲** | 43.6 | 39 |
| Qwen 3.5 9B (laptop) | 55 | 6.7 | 41.3 | 39 |
| gpt-oss-20b, 120b judges (Groq) | 46 | 6.9 | *40.8 ▼* | 31 |
| gpt-oss-120b (Groq) | 47 | 7.2 | 42.0 | 35 |
| gpt-oss-120b (OVHcloud) | 46 | 6.6 | 41.9 | 37 |
| Mistral Small 4 | 53 | 7.0 | 44.5 | 59 |
| Mistral Small 4, thinking | 54 | 6.8 | 45.0 | 59 |
| GPT-5.4-nano | 48 | *7.3 ▼* | 41.6 | 98 |
| GPT-5.6-luna | *44 ▼* | 6.7 | 44.4 | 81 |
| Claude Haiku 5.5 | 57 | 6.9 | 44.1 | 61 |
| Haiku writes, Sonnet judges | 56 | 7.1 | 44.7 | 59 |
| Claude Sonnet 5.5 | **59 ▲** | 6.5 | 47.4 | 96 |
| Claude Opus 5.5 | **59 ▲** | 6.4 | **48.1 ▲** | 93 |

French:

| Run | Readability | Words / sentence | SARI | Length, % of the source |
|---|---|---|---|---|
| Original (standard language) | 59 | 10.1 | - | - |
| Official easy-language version | 85 | 6.6 | - | - |
| Apertus 8B, 70B judges (CSCS) | *70 ▼* | 8.2 | *40.2 ▼* | 47 |
| Apertus 8B writes, 70B reads and judges (CSCS) | 73 | 8.7 | 42.4 | 31 |
| Apertus 70B (CSCS) | 80 | 7.7 | 47.3 | 34 |
| Apertus 70B, no thinking (Public AI) | 76 | **6.7 ▲** | 46.3 | 23 |
| Qwen 3.5 9B (laptop) | **81 ▲** | 8.2 | 44.4 | 33 |
| gpt-oss-20b, 120b judges (Groq) | *70 ▼* | 10.2 | 42.8 | 46 |
| gpt-oss-120b (Groq) | 75 | *10.5 ▼* | 45.1 | 37 |
| gpt-oss-120b (OVHcloud) | 73 | 7.7 | 44.6 | 29 |
| Mistral Small 4 | 75 | 7.5 | 47.7 | 29 |
| Mistral Small 4, thinking | 79 | 8.8 | 47.5 | 44 |
| GPT-5.4-nano | 71 | 9.2 | 44.4 | 57 |
| GPT-5.6-luna | 74 | 7.7 | 48.5 | 43 |
| Claude Haiku 5.5 | 80 | 7.6 | 46.6 | 44 |
| Haiku writes, Sonnet judges | 77 | 8.1 | 47.2 | 53 |
| Claude Sonnet 5.5 | 79 | 7.2 | **50.6 ▲** | 59 |
| Claude Opus 5.5 | 80 | 7.3 | 49.6 | 56 |

- Claude Sonnet and Opus read easiest and come closest to the official versions; the
  Apertus 70B and Claude Haiku follow (56 to 57), then Qwen, Mistral Small 4 and the
  Apertus 8B (52 to 55), ahead of the OpenAI small models and gpt-oss (44 to 48).
- Short sentences do not make easy text by themselves: the OpenAI models and gpt-oss
  write sentences about as short as the others' with longer words. Syllables per word
  in the final German drafts, measured on 8 November 2026: gpt-oss-20b 2.19,
  gpt-oss-120b 2.18, Apertus 8B 2.09, Apertus 70B 2.00, Claude Haiku 1.99, Claude
  Sonnet 1.96
  ([history/2026-11-08-gpt-oss-tuning.md](history/2026-11-08-gpt-oss-tuning.md)).
- Length: the OpenAI models, Sonnet and Opus write drafts of 81 to 98 % of the source's
  length in German, the Apertus 70B, Qwen and gpt-oss of 31 to 39 %.

### 3.5 Long pages

Four eval pages with much text or many values, final drafts: hard facts kept, and the
draft's length in words (the page with the most values, 33, is in the bullets below). The sources have 1,782, 4,165 (the longest of
the set), 1,989 and 1,429 words.

| Run | Political rights, German (9 values): kept | words | Disability petitions, French (15 values): kept | words | Prosecutor election, French (18 values): kept | words | Passport and ID, German (22 values): kept | words |
|---|---|---|---|---|---|---|---|---|
| Apertus 8B, 70B judges (CSCS) | 9 | 295 | *4 ▼* | 117 | 16 | 1,181 | 20 | 589 |
| Apertus 8B writes, 70B reads and judges (CSCS) | *7 ▼* | 93 | 10 | 200 | 17 | 645 | 21 | 348 |
| Apertus 70B (CSCS) | 9 | 178 | 11 | 455 | 17 | 513 | 21 | 487 |
| Apertus 70B, no thinking (Public AI) | 9 | 229 | 12 | 343 | 17 | 318 | 18 | 357 |
| Qwen 3.5 9B (laptop) | 9 | 269 | 5 | 351 | 15 | 321 | 20 | 382 |
| gpt-oss-20b, 120b judges (Groq) | 9 | 153 | 8 | 427 | 17 | 457 | **22 ▲** | 282 |
| gpt-oss-120b (Groq) | 9 | 459 | 12 | 370 | 16 | 491 | 21 | 501 |
| gpt-oss-120b (OVHcloud) | 9 | 135 | 12 | 454 | 16 | 502 | **22 ▲** | 253 |
| Mistral Small 4 | 8 | 559 | 9 | 462 | *14 ▼* | 608 | *15 ▼* | 900 |
| Mistral Small 4, thinking | 9 | 678 | 12 | 656 | 17 | 773 | 20 | 675 |
| GPT-5.4-nano | 9 | 1,295 | 12 | 1,042 | **18 ▲** | 777 | *15 ▼* | 634 |
| GPT-5.6-luna | 9 | 1,237 | 7 | 1,086 | 17 | 773 | 19 | 1,133 |
| Claude Haiku 5.5 | 9 | 424 | 9 | 476 | 17 | 837 | 20 | 650 |
| Haiku writes, Sonnet judges | 9 | 350 | 11 | 718 | 17 | 773 | 20 | 805 |
| Claude Sonnet 5.5 | 9 | 1,173 | 12 | 1,580 | 17 | 1,063 | 20 | 1,114 |
| Claude Opus 5.5 | 9 | 1,503 | 8 | 1,153 | 17 | 880 | 16 | 932 |

- The longest page splits the field: six runs keep 12 of its 15 values, the Apertus 8B
  keeps 4 in a 117-word draft, Qwen 5, GPT-5.6-luna 7. In the first drafts most runs
  kept few of its values (the Apertus 70B none, Qwen and gpt-oss-20b one, Sonnet 12);
  the rounds brought most of them back.
- The page with 22 values is the reverse: gpt-oss keeps 21 and 22 of them, GPT-5.4-nano
  and Mistral Small 4 without thinking 15, Claude Opus 16.
- The page with the most values, victim counselling in German (33 values in 364 words,
  most of them contact details), keeps all of them in every run but two: Qwen 3.5 9B kept 22, and Mistral Small 4
  without thinking 25 (its first draft lost 8 and the rounds did not bring them back;
  with thinking it kept 33).
- On the political-rights and petitions pages the OpenAI models, Sonnet and Opus write
  1,000 to 1,600 words, every other run 93 to 718.
- gpt-oss-20b answered the French election page at Write with "I'm sorry, but I can't
  provide that." on two days (its reasoning: "Hard. Probably too large."); the pair
  passed on a later attempt, and gpt-oss-120b writes it.

### 3.6 Effort, price and speed

Repair rounds and model calls per pair, tokens per page (a page is 250 words of the
source), and the price and model time per page. Prices are the providers' list prices
(Apertus at Public AI's; CSCS itself charged nothing), and the seconds are each
endpoint's on its day: a research cluster, US clouds and a throttled laptop. German:

| Run | Repair rounds | Model calls / pair | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|
| Apertus 8B, 70B judges (CSCS) | 1.8 | *13.7 ▼* | 33,392 | 0.0159 | 59.6 |
| Apertus 8B writes, 70B reads and judges (CSCS) | 1.7 | 12.6 | 24,307 | 0.0145 | 31.8 |
| Apertus 70B (CSCS) | 1.4 | 10.9 | 22,295 | 0.0250 | 60.0 |
| Apertus 70B, no thinking (Public AI) | 1.7 | 13.5 | 28,528 | 0.0324 | 39.6 |
| Qwen 3.5 9B (laptop) | 1.7 | 11.9 | 28,876 | - | *587.5 ▼* |
| gpt-oss-20b, 120b judges (Groq) | 2.0 | **9.1 ▲** | **20,197 ▲** | **0.0051 ▲** | **11.5 ▲** |
| gpt-oss-120b (Groq) | 1.9 | 11.4 | 26,702 | 0.0081 | 14.3 |
| gpt-oss-120b (OVHcloud) | 2.0 | 11.9 | 29,288 | 0.0054 | 155.3 |
| Mistral Small 4 | 1.8 | 9.9 | 29,284 | 0.0071 | 30.2 |
| Mistral Small 4, thinking | 1.7 | 9.6 | 47,315 | 0.0178 | 122.2 |
| GPT-5.4-nano | 1.9 | 11.4 | 38,935 | 0.0185 | 86.6 |
| GPT-5.6-luna | 1.9 | 12.0 | 38,070 | 0.0167 | 84.0 |
| Claude Haiku 5.5 | 1.4 | 10.7 | 46,648 | 0.0085 | 33.3 |
| Haiku writes, Sonnet judges | 1.9 | 10.9 | 46,667 | 0.0765 | 28.8 |
| Claude Sonnet 5.5 | *2.1 ▼* | 12.0 | *68,069 ▼* | 0.239 | 73.3 |
| Claude Opus 5.5 | **1.3 ▲** | 10.6 | 58,324 | *0.498 ▼* | 128.2 |

French:

| Run | Repair rounds | Model calls / pair | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|
| Apertus 8B, 70B judges (CSCS) | **1.3 ▲** | 14.3 | 23,493 | 0.0156 | 43.5 |
| Apertus 8B writes, 70B reads and judges (CSCS) | **1.3 ▲** | *20.3 ▼* | 26,369 | 0.0157 | 38.9 |
| Apertus 70B (CSCS) | 2.0 | 15.0 | **14,704 ▲** | 0.0177 | 39.2 |
| Apertus 70B, no thinking (Public AI) | 2.3 | 14.0 | 20,806 | 0.0246 | 36.7 |
| Qwen 3.5 9B (laptop) | **1.3 ▲** | 13.7 | 19,084 | - | *236.7 ▼* |
| gpt-oss-20b, 120b judges (Groq) | *3.0 ▼* | 13.0 | 24,993 | 0.0070 | 15.5 |
| gpt-oss-120b (Groq) | 2.0 | 12.3 | 16,023 | 0.0050 | **8.1 ▲** |
| gpt-oss-120b (OVHcloud) | 2.3 | 13.0 | 19,427 | **0.0037 ▲** | 100.8 |
| Mistral Small 4 | 2.0 | 11.7 | 18,887 | 0.0046 | 18.7 |
| Mistral Small 4, thinking | 1.7 | **9.7 ▲** | 23,701 | 0.0086 | 56.7 |
| GPT-5.4-nano | 2.3 | 13.3 | 27,641 | 0.0128 | 40.2 |
| GPT-5.6-luna | 2.3 | 11.0 | 17,570 | 0.0073 | 36.1 |
| Claude Haiku 5.5 | 2.0 | 12.3 | 35,250 | 0.0063 | 23.9 |
| Haiku writes, Sonnet judges | 2.0 | 11.0 | 28,761 | 0.0526 | 19.6 |
| Claude Sonnet 5.5 | 2.0 | 11.7 | 32,037 | 0.119 | 41.9 |
| Claude Opus 5.5 | 2.3 | 10.3 | *39,165 ▼* | *0.320 ▼* | 81.1 |

- Two rows undercount their seconds: the hybrid took its Understand answers and the run
  with Sonnet judging its Understand and first Write answers from the response cache.
- gpt-oss on Groq is the cheapest and fastest by far; on OVHcloud the same model is ten
  times slower. Claude Sonnet uses the most tokens (long fact sheets and drafts, large
  judge prompts), Claude Opus costs the most (its thinking counts as output).
- The judge's calls carry most of a run's tokens: with Sonnet judging Haiku's drafts the
  price per page rose ninefold (USD 0.009 to 0.077) for one point of hard facts.
- Thinking in Understand and Judge costs Mistral Small 4 2.5 times the price and 4
  times the time in German (USD 0.007 to 0.018, 30 to 122 s a page): its reasoning
  counts as output.

### 3.7 Running the model

What each model and endpoint needed from the client, and what went wrong while the runs
were made.

| Model, endpoint | Thinking control | What the client needed | Output budgets | Problems seen |
|---|---|---|---|---|
| Apertus 1.5, CSCS | `-thinking` model names; reasoning in its own field | nothing special | reasoning without a budget (3,000 to 17,000 characters for one letter); 8 Write answers on long pages cut at 8,000 tokens, written in halves since | about one long thinking stream in four closed midway; one 70B answer cut in all 35 attempts; one stream stalled overnight |
| Apertus 1.5, Public AI | none: the switch is ignored by both sizes | the gateway's cache turned off per request, a User-Agent, streaming (a proxy cuts answers after about 100 s) | none seen | the 8B refused or failing on 11 of 34 days; the backend partner changes without notice |
| Qwen 3.5 9B, Ollama | on or off (`reasoning_effort` none) | a larger context than Ollama's default 4,096 | with thinking, Understand and Judge ran to the 12,000-token budget (one call 43 minutes) | the laptop's GPU throttled for hours (1.2 to 1.8 tokens per second); 19 % of the model on the CPU |
| gpt-oss, Groq via Hugging Face | `reasoning_effort` low | the router (Groq's free tier refused the pipeline's requests at 8,000 tokens per minute) | one Understand ran to 12,000 tokens even at low effort | non-breaking hyphens in its answers (101 in 23 drafts, once inside an e-mail address), plain hyphens in code since |
| Mistral Small 4, Mistral AI | `reasoning_effort` none or high, nothing between | reading an answer sent as a list of thinking and text chunks, as it is when the model thinks | with thinking the judge reasoned past 12,000 tokens, so every call had 12,000 more | repair answers with one block's texts empty failed the round in 5 of 20 German jobs (the empty item is dropped since); two streams with thinking stalled (one call 50 minutes, one job past its two hours); the judge with thinking listed fewer than half of the facts in 38 of 100 answers |
| GPT-5.4-nano, GPT-5.6-luna, OpenAI | `reasoning_effort` none | `max_completion_tokens` instead of `max_tokens`, no temperature | Understand answers of 6,000 to 9,000 tokens on long pages, run with the 12,000 budget | none |
| Claude Haiku, Sonnet, OpenAI-compatible endpoint | a native field per model (`disabled` for Haiku, `between_tools` for Sonnet); `reasoning_effort` is ignored | no temperature, an `anthropic-version` header | Write passed 8,000 tokens on 3 pages (Haiku) and 9 (Sonnet), written in halves | none |
| Claude Opus | cannot be switched off | 12,000 more output tokens on every call | Understand reached 18,000 tokens, 4 Write answers passed 20,000; one pair failed on the first budget | none |

## 4. Model profiles

- **Apertus 1.5 8B with the 70B judging (CSCS).** Ends with the most hard facts (97 %,
  every one on 17 of 20 pages) from the weakest first drafts (61 %): the rounds do most
  of the work, with the most calls per pair. Leaves the most rule errors, warnings and
  passives in German, and keeps with Qwen the fewest facts in French (72 %) at the lowest
  French SARI (40.2). Open weights and training data; runs on one 24 GB GPU.
- **Apertus 1.5 70B.** The cleaner Apertus: with thinking on CSCS 0.5 errors per 100
  blocks and readability 57, without thinking on Public AI 2.4 and 57; on Public AI the
  shortest sentences of all runs, on CSCS the fewest tokens in French. Short drafts (39 %
  of the source) and first drafts that keep 69 to 71 % of the facts; in French its
  repair rounds raise the errors (from 0.9 and 2.1 in the first drafts to 3.3 and 3.4).
- **Qwen 3.5 9B on a laptop.** The fewest facts in the end (87 %, every one on 10 of 20
  pages) and one value in a hundred lost silently, but few rule errors (0.3) and readable
  text (55, in French the best with 81). The slowest by far on a throttled 8 GB laptop
  GPU, and the only run whose text never left the machine.
- **gpt-oss-20b, 120b judging.** The cheapest, fastest and leanest run (USD 0.005, 11.5
  s, 20,000 tokens and 9 calls a page). Its first drafts keep many facts (81 %) but carry
  the most rule errors (14.2) and read hardest (42); the final drafts keep 94 % at the
  lowest SARI. Refused to write the French election page on two days.
- **gpt-oss-120b.** Ties for the most facts (97 %) with 0.5 errors, at USD 0.008 and 14 s
  a page on Groq; keeps 21 of the 22-value page (22 on OVHcloud). Writes long words
  (readability 47), leaves many compounds to code, and in French the most warnings and
  the longest sentences. The same model on OVHcloud kept 92 % at ten times the time.
- **Mistral Small 4.** Open weights (Apache 2.0), the text stays in the EU. Without
  thinking cheap and quick (USD 0.007 and 30 s a page), with first drafts that find the
  most must-keep facts (94 %), but the fewest hard facts in the end (85 %, 89 % in its
  run of the day before) and 25 of the 33 values of the victim-counselling page.
  Thinking in Understand and Judge brings it to 92 % at 2.5 times the price and four
  times the time, with the fewest calls per French pair; that judge often lists only
  the facts it finds a problem with.
- **GPT-5.4-nano.** The most facts in French (93 %, 3 pairs) and all 18 of the election
  page, but 15 of 22 on the page with the most values. The longest German sentences (7.3
  words), the most long compounds and word findings, and drafts almost as long as the
  source.
- **GPT-5.6-luna.** First drafts that find the most must-keep facts (93 %), final drafts
  that keep 90 % of the hard facts, one silent loss in a hundred, and the hardest German
  to read (44).
- **Claude Haiku 5.5.** The best first drafts on facts (84 %, with Sonnet), 92 % in the
  end, cheap (USD 0.009). The only Claude drafts with values not in the source (0.3 per
  100 blocks) and the most number findings. With Sonnet judging: one point more of the
  facts at nine times the price.
- **Claude Sonnet 5.5.** No rule error and no passive in German, readability 59, first
  drafts that read best of all (61); 91 % of the hard facts in the end. The most tokens
  (68,000 a page) and the most repair rounds, USD 0.24 a page.
- **Claude Opus 5.5.** The cleanest text by every rule family in both languages, and in
  German the highest SARI and the fewest repair rounds; 91 % of the hard facts, 16 of 22
  on the page with the most values. The most expensive (USD 0.50 a page) and slower than
  every cloud run but the one on OVHcloud (128 s); its thinking cannot be switched off.

## 5. Tested on one model only

These results have no counterpart from another model and are not compared here:

- Image input (scanned letters): Apertus 1.5 8B and 70B on CSCS
  ([image-input.md](image-input.md)).
- Italian and the German of Germany and Austria: Apertus 1.5 70B on Public AI
  ([evaluation-publicai.md](evaluation-publicai.md)).
- The school letters and the forms of address: Apertus 1.5 70B on Public AI
  ([use-case-schools.md](use-case-schools.md)).
- The judge against blind labels: the Apertus 70B only ([prompts.md](prompts.md),
  "Judge agreement with blind labels").
- One NVIDIA L4 on premises: Apertus 1.5 8B
  ([hardware/aws-l4-2026-10-10/](hardware/aws-l4-2026-10-10/README.md)).
- The gpt-oss variants (the 20B writing, a judge at medium effort, the model's own
  temperature) and the round options measured on gpt-oss-120b, the Apertus 70B and
  Claude Haiku
  ([history/2026-11-08-gpt-oss-tuning.md](history/2026-11-08-gpt-oss-tuning.md)).

## 6. Limits

- **The pipeline was built on Apertus.** Prompts, guards and repairs were developed
  against the Apertus 8B from 5 October 2026; the other models ran on the same code
  unchanged. That favours Apertus on the final numbers; the first drafts (§3.2) show
  more of each model.
- **Small samples, one run per setup:** 20 German and 3 French pairs; see the noise
  under "How to read the marks". Mistral Small 4 ran each setup twice; the tables show
  the second run, of 11 November, after a fix to the repair answers.
- **Thinking differs between runs** (§1): Apertus on CSCS and one Mistral Small 4 run
  thought in two stages, gpt-oss and Opus on every call, the others not at all.
- **Different days and rules.** The tables of §3 are the published numbers: the Apertus
  rows on CSCS carry the rules of 12 October 2026, the later runs those of their day;
  the first drafts are scored with the rules of 10 and 11 November.
- **Our own instruments.** The rule checker and the fact matcher are the project's,
  calibrated on the official easy-language versions; the judge's columns are not
  compared.
- **Endpoints and prices** are the providers' of the day; a model on other hardware or
  another provider can be faster, slower or cheaper.
