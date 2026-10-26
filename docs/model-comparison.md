# Model comparison

Every evaluation run of the full pipeline (P2) side by side: the published runs with
Apertus 1.5 on the CSCS inference API, and the runs on other endpoints and models that
followed. All of them use the same held-out pairs (the `eval` split: 20 German and 3
French texts of Swiss administrations with their official easy-language versions), the
same rule checker and the same scoring as [evaluation.md](evaluation.md); only the model,
the endpoint and the thinking mode change. `uv run leichtfacile eval compare` writes the
tables from the results folders named below (git-ignored, like all of `eval/`); the runs
block and the prose are written by hand, the tables are not.

## How to read the tables

- The columns that code measures compare across runs: fact coverage, hard facts kept,
  silent losses, values not in the source, rule errors and warnings, words per sentence,
  readability (Amstad for German, Kandel-Moles for French), SARI, tokens and USD per page
  (a page is 250 words of the source).
- The judge columns (unsupported statements, distorted facts) do not: every run has its
  own judge, and a model judging its own drafts flags differently from a larger model
  judging another's.
- USD per page follows the prices in the providers' models tables of
  `src/leichtfacile/presets.toml` (`input_usd`, `output_usd`): Apertus at
  Public AI's prices (the CSCS endpoint itself charged nothing), gpt-oss at Groq's. A
  model on one's own hardware has no price per token (a dash); the laptop run below cost
  some CHF 0.15 of electricity for its 23 pairs.
- Seconds per page are the model time of that day on that endpoint: a research cluster,
  a US cloud and a laptop with a throttled GPU are not the same kind of number.
- The Apertus runs are the project's reference results. Every other run is an experiment
  on another endpoint, never an Apertus or CSCS number, and the texts of those runs left
  Switzerland (the "The text goes to" column).
- Each run carries the scores of its day: the Apertus rows those of 12 October 2026, the
  later runs those of the current rules. The reference rows (the originals and the
  official versions) come from the first run's folder; a later folder scores the French
  official versions at 56 % instead of 54 %, the size of that drift. `eval rescore
  --in-place` brings a folder to the current rules without calling a model.

## Adding a run

Run the condition into a results folder of its own (`eval reference --role all --results
eval/results-<name>` once, then `eval run --cache --condition P2 --results
eval/results-<name> --preset <name>`), add a `[[run]]` table to the block below (`file`
is the `P2_<writer>.jsonl` the run wrote; `date`, `endpoint`, `writer`, `judge`,
`thinking`, `text`, `prices` and `notes` fill the runs table), and run
`uv run leichtfacile eval compare`. A model without a price in `presets.toml` shows no
USD per page until it has one and the folder is scored again (`eval rescore --in-place`).

<!-- runs:start -->
```toml
[[run]]
label = "Apertus 1.5 8B, the 70B judges (CSCS)"
results = "eval/results-cscs"
file = "P2_swiss-ai-apertus-v1-5-8b.jsonl"
date = 2026-10-12
endpoint = "CSCS inference API, Lugano"
writer = "swiss-ai/Apertus-v1.5-8B"
judge = "swiss-ai/Apertus-v1.5-70B"
thinking = "Understand and Judge (model-suffix)"
text = "Switzerland (CSCS)"
prices = "Public AI list prices; CSCS charged nothing"
notes = "the published run, docs/evaluation.md"

[[run]]
label = "Apertus 1.5 70B everywhere (CSCS)"
results = "eval/results-cscs"
file = "P2_swiss-ai-apertus-v1-5-70b.jsonl"
date = 2026-10-12
endpoint = "CSCS inference API, Lugano"
writer = "swiss-ai/Apertus-v1.5-70B"
judge = "swiss-ai/Apertus-v1.5-70B (itself)"
thinking = "Understand and Judge (model-suffix)"
text = "Switzerland (CSCS)"
prices = "Public AI list prices; CSCS charged nothing"
notes = "the quality tier; one German pair without a result"

[[run]]
label = "Apertus 1.5 8B writes, the 70B reads and judges (CSCS)"
results = "eval/results-cscs"
file = "P2_swiss-ai-apertus-v1-5-8b_understand-swiss-ai-apertus-v1-5-70b.jsonl"
date = 2026-10-12
endpoint = "CSCS inference API, Lugano"
writer = "swiss-ai/Apertus-v1.5-8B"
judge = "swiss-ai/Apertus-v1.5-70B"
thinking = "Understand and Judge (model-suffix)"
text = "Switzerland (CSCS)"
prices = "Public AI list prices; CSCS charged nothing"
notes = "the hybrid: the 70B writes the fact sheet (docs/prompts.md)"

[[run]]
label = "Qwen 3.5 9B on Ollama, no thinking, judges itself (laptop)"
results = "eval/results-ollama-qwen3.5-9b"
file = "P2_qwen3-5-9b.jsonl"
date = 2026-10-24
endpoint = "Ollama 0.40 in WSL on a laptop (RTX 4060, 8 GB)"
writer = "qwen3.5:9b (Q4_K_M)"
judge = "qwen3.5:9b (itself)"
thinking = "none: with thinking on, Understand and Judge ran to 12,000 tokens"
text = "nowhere: the laptop"
prices = "own hardware; about CHF 0.15 of electricity for the run"
notes = "19 % of the model on the CPU; the GPU throttled for hours (1.2 to 1.8 tokens/s)"

[[run]]
label = "gpt-oss-20b writes, gpt-oss-120b judges, effort low (Groq via Hugging Face)"
results = "eval/results-hf-gpt-oss"
file = "P2_openai-gpt-oss-20b-groq.jsonl"
date = 2026-10-25
endpoint = "Groq (region yul) through the Hugging Face Inference Providers router"
writer = "openai/gpt-oss-20b"
judge = "openai/gpt-oss-120b"
thinking = "gpt-oss always reasons; reasoning_effort low on every call"
text = "Canada or the United States (Groq)"
prices = "Groq list prices, billed through Hugging Face"
notes = "Groq's free tier refused the pipeline's requests (8,000 tokens per minute); one French pair passed on its third run"
[[run]]
label = "gpt-5.4-nano, no thinking, judges itself (OpenAI)"
results = "eval/results-openai-gpt-5.4-nano"
file = "P2_gpt-5-4-nano.jsonl"
date = 2026-10-25
endpoint = "OpenAI API"
writer = "gpt-5.4-nano"
judge = "gpt-5.4-nano (itself)"
thinking = "reasoning_effort none on every call"
text = "United States (OpenAI)"
prices = "OpenAI list prices"
notes = "the smallest current OpenAI model; max_completion_tokens, no temperature; on the long documents its Understand answer passed the 6,000-token budget, so those pairs ran with the 12,000 budget of the thinking stages (the model still reasons only when asked)"

[[run]]
label = "gpt-5.6-luna, no thinking, judges itself (OpenAI)"
results = "eval/results-openai-gpt-5.6-luna"
file = "P2_gpt-5-6-luna.jsonl"
date = 2026-10-25
endpoint = "OpenAI API"
writer = "gpt-5.6-luna"
judge = "gpt-5.6-luna (itself)"
thinking = "reasoning_effort none on every call"
text = "United States (OpenAI)"
prices = "OpenAI list prices"
notes = "the newest cheap OpenAI model; on the long documents its Understand answer passed the 6,000-token budget, so those pairs ran with the 12,000 budget of the thinking stages (the model still reasons only when asked)"
[[run]]
label = "Claude Haiku 5.5, no thinking, judges itself (Anthropic)"
results = "eval/results-anthropic-claude-haiku-5.5"
file = "P2_claude-haiku-5-5.jsonl"
date = 2026-10-25
endpoint = "Anthropic's OpenAI-compatible endpoint"
writer = "claude-haiku-5-5"
judge = "claude-haiku-5-5 (itself)"
thinking = "off, through the native thinking field (the endpoint ignores reasoning_effort; thinking tokens count in max_tokens and are not reported)"
text = "United States (Anthropic)"
prices = "Anthropic list prices"
notes = "no temperature (refused by the 5.5 models); the smallest current Claude; with adaptive thinking on, Understand ran to 12,000 and Write to 8,000 tokens"
[[run]]
label = "Claude Sonnet 5.5, no thinking, judges itself (Anthropic)"
results = "eval/results-anthropic-claude-sonnet-5.5"
file = "P2_claude-sonnet-5-5.jsonl"
date = 2026-10-25
endpoint = "Anthropic's OpenAI-compatible endpoint"
writer = "claude-sonnet-5-5"
judge = "claude-sonnet-5-5 (itself)"
thinking = "off, through the native thinking field: `between_tools`, the only value Sonnet 5.5 accepts there (the endpoint refuses `adaptive`, Sonnet `disabled`); with no tools in the pipeline it does not think"
text = "United States (Anthropic)"
prices = "Anthropic list prices"
notes = "no temperature; nine Write answers passed 8,000 tokens and were written in halves, the longest Understand answer reached 10,800; 275 calls, USD 14.7 paid"
[[run]]
label = "Claude Haiku 5.5 writes, Sonnet 5.5 judges, no thinking (Anthropic)"
results = "eval/results-anthropic-haiku-sonnet-judge"
file = "P2_claude-haiku-5-5.jsonl"
date = 2026-10-25
endpoint = "Anthropic's OpenAI-compatible endpoint"
writer = "claude-haiku-5-5"
judge = "claude-sonnet-5-5"
thinking = "off on both, through the native thinking field set per model (the provider's models tables): `disabled` for Haiku, `between_tools` for Sonnet"
text = "United States (Anthropic)"
prices = "Anthropic list prices"
notes = "the writer's Understand and first Write calls are those of the Haiku run and came from the response cache, so the drafts differ from that run only through the judge and the repairs it asked for; cached calls count their tokens but no time, so the seconds per page leave out Understand and the first Write; USD 4.4 paid"
```
<!-- runs:end -->

<!-- tables:start -->
| Run | Date | Endpoint | Writer | Judge | Thinking | The text goes to | Prices | Notes | Results |
|---|---|---|---|---|---|---|---|---|---|
| Apertus 1.5 8B, the 70B judges (CSCS) | 2026-10-12 | CSCS inference API, Lugano | swiss-ai/Apertus-v1.5-8B | swiss-ai/Apertus-v1.5-70B | Understand and Judge (model-suffix) | Switzerland (CSCS) | Public AI list prices; CSCS charged nothing | the published run, docs/evaluation.md | `eval/results-cscs/P2_swiss-ai-apertus-v1-5-8b.jsonl` |
| Apertus 1.5 70B everywhere (CSCS) | 2026-10-12 | CSCS inference API, Lugano | swiss-ai/Apertus-v1.5-70B | swiss-ai/Apertus-v1.5-70B (itself) | Understand and Judge (model-suffix) | Switzerland (CSCS) | Public AI list prices; CSCS charged nothing | the quality tier; one German pair without a result | `eval/results-cscs/P2_swiss-ai-apertus-v1-5-70b.jsonl` |
| Apertus 1.5 8B writes, the 70B reads and judges (CSCS) | 2026-10-12 | CSCS inference API, Lugano | swiss-ai/Apertus-v1.5-8B | swiss-ai/Apertus-v1.5-70B | Understand and Judge (model-suffix) | Switzerland (CSCS) | Public AI list prices; CSCS charged nothing | the hybrid: the 70B writes the fact sheet (docs/prompts.md) | `eval/results-cscs/P2_swiss-ai-apertus-v1-5-8b_understand-swiss-ai-apertus-v1-5-70b.jsonl` |
| Qwen 3.5 9B on Ollama, no thinking, judges itself (laptop) | 2026-10-24 | Ollama 0.40 in WSL on a laptop (RTX 4060, 8 GB) | qwen3.5:9b (Q4_K_M) | qwen3.5:9b (itself) | none: with thinking on, Understand and Judge ran to 12,000 tokens | nowhere: the laptop | own hardware; about CHF 0.15 of electricity for the run | 19 % of the model on the CPU; the GPU throttled for hours (1.2 to 1.8 tokens/s) | `eval/results-ollama-qwen3.5-9b/P2_qwen3-5-9b.jsonl` |
| gpt-oss-20b writes, gpt-oss-120b judges, effort low (Groq via Hugging Face) | 2026-10-25 | Groq (region yul) through the Hugging Face Inference Providers router | openai/gpt-oss-20b | openai/gpt-oss-120b | gpt-oss always reasons; reasoning_effort low on every call | Canada or the United States (Groq) | Groq list prices, billed through Hugging Face | Groq's free tier refused the pipeline's requests (8,000 tokens per minute); one French pair passed on its third run | `eval/results-hf-gpt-oss/P2_openai-gpt-oss-20b-groq.jsonl` |
| gpt-5.4-nano, no thinking, judges itself (OpenAI) | 2026-10-25 | OpenAI API | gpt-5.4-nano | gpt-5.4-nano (itself) | reasoning_effort none on every call | United States (OpenAI) | OpenAI list prices | the smallest current OpenAI model; max_completion_tokens, no temperature; on the long documents its Understand answer passed the 6,000-token budget, so those pairs ran with the 12,000 budget of the thinking stages (the model still reasons only when asked) | `eval/results-openai-gpt-5.4-nano/P2_gpt-5-4-nano.jsonl` |
| gpt-5.6-luna, no thinking, judges itself (OpenAI) | 2026-10-25 | OpenAI API | gpt-5.6-luna | gpt-5.6-luna (itself) | reasoning_effort none on every call | United States (OpenAI) | OpenAI list prices | the newest cheap OpenAI model; on the long documents its Understand answer passed the 6,000-token budget, so those pairs ran with the 12,000 budget of the thinking stages (the model still reasons only when asked) | `eval/results-openai-gpt-5.6-luna/P2_gpt-5-6-luna.jsonl` |
| Claude Haiku 5.5, no thinking, judges itself (Anthropic) | 2026-10-25 | Anthropic's OpenAI-compatible endpoint | claude-haiku-5-5 | claude-haiku-5-5 (itself) | off, through the native thinking field (the endpoint ignores reasoning_effort; thinking tokens count in max_tokens and are not reported) | United States (Anthropic) | Anthropic list prices | no temperature (refused by the 5.5 models); the smallest current Claude; with adaptive thinking on, Understand ran to 12,000 and Write to 8,000 tokens | `eval/results-anthropic-claude-haiku-5.5/P2_claude-haiku-5-5.jsonl` |
| Claude Sonnet 5.5, no thinking, judges itself (Anthropic) | 2026-10-25 | Anthropic's OpenAI-compatible endpoint | claude-sonnet-5-5 | claude-sonnet-5-5 (itself) | off, through the native thinking field: `between_tools`, the only value Sonnet 5.5 accepts there (the endpoint refuses `adaptive`, Sonnet `disabled`); with no tools in the pipeline it does not think | United States (Anthropic) | Anthropic list prices | no temperature; nine Write answers passed 8,000 tokens and were written in halves, the longest Understand answer reached 10,800; 275 calls, USD 14.7 paid | `eval/results-anthropic-claude-sonnet-5.5/P2_claude-sonnet-5-5.jsonl` |
| Claude Haiku 5.5 writes, Sonnet 5.5 judges, no thinking (Anthropic) | 2026-10-25 | Anthropic's OpenAI-compatible endpoint | claude-haiku-5-5 | claude-sonnet-5-5 | off on both, through the native thinking field set per model (the provider's models tables): `disabled` for Haiku, `between_tools` for Sonnet | United States (Anthropic) | Anthropic list prices | the writer's Understand and first Write calls are those of the Haiku run and came from the response cache, so the drafts differ from that run only through the judge and the repairs it asked for; cached calls count their tokens but no time, so the seconds per page leave out Understand and the first Write; USD 4.4 paid | `eval/results-anthropic-haiku-sonnet-judge/P2_claude-haiku-5-5.jsonl` |

## German

Pairs: 20 (eval split). Means over pairs; a dash means not applicable.

| Run | Pairs | Fact coverage | Hard facts kept | Silent losses | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 20 | - | 100 % | 0 % | 31.3 | 164.5 | 9.8 | 36 | - | - | 0.0 | - | - | - |
| Official easy-language version | 20 | - | 67 % | 33 % | 2.7 | 27.7 | 6.1 | 62 | - | - | 2.8 | - | - | - |
| Apertus 1.5 8B, the 70B judges (CSCS) | 20 | 100 % | 97 % | 0 % | 3.7 | 41.5 | 7.0 | 52 | 42.2 | 2.7 | 0.0 | 33392 | 0.0159 | 59.6 |
| Apertus 1.5 70B everywhere (CSCS) | 19 | 100 % | 96 % | 0 % | 0.5 | 22.2 | 6.5 | 57 | 42.9 | 1.0 | 0.0 | 22295 | 0.0250 | 60.0 |
| Apertus 1.5 8B writes, the 70B reads and judges (CSCS) | 20 | 99 % | 94 % | 0 % | 3.0 | 37.6 | 6.8 | 53 | 42.3 | 1.4 | 0.0 | 24307 | 0.0145 | 31.8 |
| Qwen 3.5 9B on Ollama, no thinking, judges itself (laptop) | 20 | 99 % | 87 % | 1 % | 0.3 | 27.9 | 6.7 | 55 | 41.3 | 4.7 | 0.0 | 28876 | - | 587.5 |
| gpt-oss-20b writes, gpt-oss-120b judges, effort low (Groq via Hugging Face) | 20 | 100 % | 94 % | 0 % | 1.7 | 31.9 | 6.9 | 46 | 40.8 | 0.7 | 0.0 | 20197 | 0.0051 | 11.5 |
| gpt-5.4-nano, no thinking, judges itself (OpenAI) | 20 | 99 % | 93 % | 0 % | 0.7 | 34.3 | 7.3 | 48 | 41.6 | 2.1 | 0.0 | 38935 | 0.0185 | 86.6 |
| gpt-5.6-luna, no thinking, judges itself (OpenAI) | 20 | 100 % | 90 % | 1 % | 0.4 | 21.0 | 6.7 | 44 | 44.4 | 3.1 | 0.0 | 38070 | 0.0167 | 84.0 |
| Claude Haiku 5.5, no thinking, judges itself (Anthropic) | 20 | 100 % | 92 % | 0 % | 0.9 | 29.9 | 6.9 | 57 | 44.1 | 8.6 | 0.3 | 46648 | 0.0085 | 33.3 |
| Claude Sonnet 5.5, no thinking, judges itself (Anthropic) | 20 | 100 % | 91 % | 0 % | 0.0 | 17.5 | 6.5 | 59 | 47.4 | 2.2 | 0.0 | 68069 | 0.2386 | 73.3 |
| Claude Haiku 5.5 writes, Sonnet 5.5 judges, no thinking (Anthropic) | 20 | 100 % | 93 % | 0 % | 1.0 | 33.5 | 7.1 | 56 | 44.7 | 5.6 | 0.2 | 46667 | 0.0765 | 28.8 |

Silent losses: the share of the source's hard values that the text lost without a trace. A single prompt and the official version have no fact checklist and no omission log, so every value they lose is silent; for P1 and P2 every hard value is a fact in the review checklist or lies in a listed omission, so their share is zero by design, and a value above zero names one the code completion missed.

Rule findings (errors and warnings) per 100 blocks, by family. "LEX by code" is the compounds split by code in the final version, per 100 blocks (P1 and P2 only; the baselines and the reference measure the text as written):

| Run | LEN | ORD | GRAM | NEG | LEX | LEX by code | NUM | CH |
|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 49.9 | 0.0 | 39.7 | 0.3 | 99.9 | - | 2.8 | 0.0 |
| Official easy-language version | 10.1 | 0.0 | 6.0 | 0.0 | 12.9 | - | 0.2 | 0.0 |
| Apertus 1.5 8B, the 70B judges (CSCS) | 17.6 | 0.0 | 9.6 | 0.0 | 11.9 | 34.1 | 3.2 | 0.0 |
| Apertus 1.5 70B everywhere (CSCS) | 7.0 | 0.0 | 4.4 | 0.0 | 7.3 | 29.2 | 1.3 | 0.0 |
| Apertus 1.5 8B writes, the 70B reads and judges (CSCS) | 16.3 | 0.0 | 9.2 | 0.0 | 9.1 | 32.3 | 3.4 | 0.0 |
| Qwen 3.5 9B on Ollama, no thinking, judges itself (laptop) | 7.0 | 0.0 | 7.3 | 0.0 | 8.2 | 28.2 | 1.9 | 0.0 |
| gpt-oss-20b writes, gpt-oss-120b judges, effort low (Groq via Hugging Face) | 10.1 | 0.0 | 7.2 | 0.0 | 8.7 | 43.6 | 1.4 | 0.0 |
| gpt-5.4-nano, no thinking, judges itself (OpenAI) | 9.8 | 0.0 | 7.4 | 0.0 | 13.4 | 47.2 | 2.6 | 0.0 |
| gpt-5.6-luna, no thinking, judges itself (OpenAI) | 4.2 | 0.0 | 5.4 | 0.0 | 9.3 | 19.9 | 0.5 | 0.0 |
| Claude Haiku 5.5, no thinking, judges itself (Anthropic) | 11.7 | 0.0 | 4.3 | 0.2 | 7.8 | 15.6 | 4.1 | 0.0 |
| Claude Sonnet 5.5, no thinking, judges itself (Anthropic) | 8.0 | 0.0 | 2.2 | 0.0 | 5.5 | 2.6 | 0.4 | 0.0 |
| Claude Haiku 5.5 writes, Sonnet 5.5 judges, no thinking (Anthropic) | 12.8 | 0.0 | 4.6 | 0.1 | 9.1 | 16.5 | 4.1 | 0.0 |

Fact-rich subset (17 pairs with at least 3 hard facts):

| Run | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| Original (standard language) | 17 | 100 % | - | - |
| Official easy-language version | 17 | 61 % | - | - |
| Apertus 1.5 8B, the 70B judges (CSCS) | 17 | 97 % | 99 % | 6 % |
| Apertus 1.5 70B everywhere (CSCS) | 16 | 96 % | 100 % | 3 % |
| Apertus 1.5 8B writes, the 70B reads and judges (CSCS) | 17 | 96 % | 99 % | 4 % |
| Qwen 3.5 9B on Ollama, no thinking, judges itself (laptop) | 17 | 84 % | 98 % | 5 % |
| gpt-oss-20b writes, gpt-oss-120b judges, effort low (Groq via Hugging Face) | 17 | 93 % | 100 % | 1 % |
| gpt-5.4-nano, no thinking, judges itself (OpenAI) | 17 | 92 % | 99 % | 8 % |
| gpt-5.6-luna, no thinking, judges itself (OpenAI) | 17 | 88 % | 100 % | 3 % |
| Claude Haiku 5.5, no thinking, judges itself (Anthropic) | 17 | 90 % | 100 % | 4 % |
| Claude Sonnet 5.5, no thinking, judges itself (Anthropic) | 17 | 89 % | 100 % | 1 % |
| Claude Haiku 5.5 writes, Sonnet 5.5 judges, no thinking (Anthropic) | 17 | 91 % | 100 % | 2 % |

Failed runs (not in the means): Apertus 1.5 70B everywhere (CSCS): zh-sebe-disability-de.

## French

Pairs: 3 (eval split). Means over pairs; a dash means not applicable.

| Run | Pairs | Fact coverage | Hard facts kept | Silent losses | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 3 | - | 100 % | 0 % | 36.4 | 85.8 | 10.1 | 59 | - | - | 0.0 | - | - | - |
| Official easy-language version | 3 | - | 54 % | 46 % | 2.9 | 21.7 | 6.6 | 85 | - | - | 0.8 | - | - | - |
| Apertus 1.5 8B, the 70B judges (CSCS) | 3 | 100 % | 72 % | 0 % | 3.5 | 25.8 | 8.2 | 70 | 40.2 | 8.4 | 0.0 | 23493 | 0.0156 | 43.5 |
| Apertus 1.5 70B everywhere (CSCS) | 3 | 100 % | 89 % | 0 % | 3.4 | 17.4 | 7.7 | 80 | 47.3 | 0.5 | 0.0 | 14704 | 0.0177 | 39.2 |
| Apertus 1.5 8B writes, the 70B reads and judges (CSCS) | 3 | 95 % | 87 % | 0 % | 8.8 | 45.5 | 8.7 | 73 | 42.4 | 13.6 | 0.0 | 26369 | 0.0157 | 38.9 |
| Qwen 3.5 9B on Ollama, no thinking, judges itself (laptop) | 3 | 100 % | 72 % | 0 % | 0.0 | 12.5 | 8.2 | 81 | 44.4 | 5.7 | 0.0 | 19084 | - | 236.7 |
| gpt-oss-20b writes, gpt-oss-120b judges, effort low (Groq via Hugging Face) | 3 | 100 % | 83 % | 0 % | 0.0 | 46.3 | 10.2 | 70 | 42.8 | 2.5 | 0.0 | 24993 | 0.0070 | 15.5 |
| gpt-5.4-nano, no thinking, judges itself (OpenAI) | 3 | 100 % | 93 % | 0 % | 0.4 | 40.4 | 9.2 | 71 | 44.4 | 2.7 | 0.0 | 27641 | 0.0128 | 40.2 |
| gpt-5.6-luna, no thinking, judges itself (OpenAI) | 3 | 100 % | 80 % | 0 % | 0.5 | 22.8 | 7.7 | 74 | 48.5 | 1.2 | 0.0 | 17570 | 0.0073 | 36.1 |
| Claude Haiku 5.5, no thinking, judges itself (Anthropic) | 3 | 100 % | 83 % | 0 % | 0.9 | 21.3 | 7.6 | 80 | 46.6 | 7.7 | 0.0 | 35250 | 0.0063 | 23.9 |
| Claude Sonnet 5.5, no thinking, judges itself (Anthropic) | 3 | 100 % | 91 % | 0 % | 0.4 | 10.9 | 7.2 | 79 | 50.6 | 3.1 | 0.0 | 32037 | 0.1187 | 41.9 |
| Claude Haiku 5.5 writes, Sonnet 5.5 judges, no thinking (Anthropic) | 3 | 100 % | 87 % | 0 % | 1.2 | 29.3 | 8.1 | 77 | 47.2 | 7.7 | 0.0 | 28761 | 0.0526 | 19.6 |

Silent losses: the share of the source's hard values that the text lost without a trace. A single prompt and the official version have no fact checklist and no omission log, so every value they lose is silent; for P1 and P2 every hard value is a fact in the review checklist or lies in a listed omission, so their share is zero by design, and a value above zero names one the code completion missed.

Rule findings (errors and warnings) per 100 blocks, by family. "LEX by code" is the compounds split by code in the final version, per 100 blocks (P1 and P2 only; the baselines and the reference measure the text as written):

| Run | LEN | ORD | GRAM | NEG | LEX | LEX by code | NUM | CH |
|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 53.7 | 0.0 | 24.5 | 0.0 | 39.5 | - | 4.5 | 0.0 |
| Official easy-language version | 17.0 | 0.0 | 4.0 | 0.0 | 3.1 | - | 0.5 | 0.0 |
| Apertus 1.5 8B, the 70B judges (CSCS) | 14.4 | 0.0 | 4.7 | 0.0 | 7.5 | 0.0 | 2.7 | 0.0 |
| Apertus 1.5 70B everywhere (CSCS) | 6.0 | 0.0 | 4.6 | 0.0 | 8.4 | 0.0 | 1.7 | 0.0 |
| Apertus 1.5 8B writes, the 70B reads and judges (CSCS) | 17.0 | 0.0 | 7.8 | 0.0 | 22.4 | 0.0 | 7.2 | 0.0 |
| Qwen 3.5 9B on Ollama, no thinking, judges itself (laptop) | 1.0 | 0.0 | 3.1 | 0.0 | 6.9 | 0.0 | 1.6 | 0.0 |
| gpt-oss-20b writes, gpt-oss-120b judges, effort low (Groq via Hugging Face) | 17.9 | 0.0 | 12.3 | 0.0 | 12.1 | 0.0 | 4.0 | 0.0 |
| gpt-5.4-nano, no thinking, judges itself (OpenAI) | 15.6 | 0.0 | 15.9 | 0.0 | 8.2 | 0.0 | 1.1 | 0.0 |
| gpt-5.6-luna, no thinking, judges itself (OpenAI) | 9.8 | 0.0 | 5.5 | 0.0 | 5.5 | 0.0 | 2.5 | 0.0 |
| Claude Haiku 5.5, no thinking, judges itself (Anthropic) | 8.5 | 0.0 | 6.5 | 0.0 | 4.0 | 0.0 | 3.3 | 0.0 |
| Claude Sonnet 5.5, no thinking, judges itself (Anthropic) | 5.3 | 0.0 | 3.2 | 0.0 | 2.8 | 0.0 | 0.0 | 0.0 |
| Claude Haiku 5.5 writes, Sonnet 5.5 judges, no thinking (Anthropic) | 12.5 | 0.0 | 8.8 | 0.0 | 5.8 | 0.0 | 3.4 | 0.0 |

Fact-rich subset (3 pairs with at least 3 hard facts):

| Run | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| Original (standard language) | 3 | 100 % | - | - |
| Official easy-language version | 3 | 54 % | - | - |
| Apertus 1.5 8B, the 70B judges (CSCS) | 3 | 72 % | 100 % | 5 % |
| Apertus 1.5 70B everywhere (CSCS) | 3 | 89 % | 100 % | 0 % |
| Apertus 1.5 8B writes, the 70B reads and judges (CSCS) | 3 | 87 % | 95 % | 8 % |
| Qwen 3.5 9B on Ollama, no thinking, judges itself (laptop) | 3 | 72 % | 100 % | 2 % |
| gpt-oss-20b writes, gpt-oss-120b judges, effort low (Groq via Hugging Face) | 3 | 83 % | 100 % | 0 % |
| gpt-5.4-nano, no thinking, judges itself (OpenAI) | 3 | 93 % | 100 % | 2 % |
| gpt-5.6-luna, no thinking, judges itself (OpenAI) | 3 | 80 % | 100 % | 1 % |
| Claude Haiku 5.5, no thinking, judges itself (Anthropic) | 3 | 83 % | 100 % | 2 % |
| Claude Sonnet 5.5, no thinking, judges itself (Anthropic) | 3 | 91 % | 100 % | 1 % |
| Claude Haiku 5.5 writes, Sonnet 5.5 judges, no thinking (Anthropic) | 3 | 87 % | 100 % | 2 % |
<!-- tables:end -->

## Reading, 25 October 2026

- **Facts.** The Apertus runs keep 96 to 97 % of the hard values in German, gpt-oss 94 %,
  gpt-5.4-nano and Haiku with Sonnet judging 93 %, Haiku alone 92 %, Sonnet 91 %,
  gpt-5.6-luna 90 %, Qwen 87 %; Qwen and luna each lost one value in two hundred silently.
  The Haiku drafts are the only ones that carry values not in the source (0.3 per 100
  blocks with Haiku judging, 0.2 with Sonnet judging); Sonnet's own drafts carry none, as
  everybody else's. In French (3 pairs) nano and Sonnet lead (93 and 91 %), the 70B 89 %,
  Haiku with Sonnet judging 87 %, gpt-oss and Haiku 83 %, luna 80 %, the 8B and Qwen 72 %.
- **Rules.** Sonnet writes no rule error at all in German and the fewest warnings (17.5
  per 100 blocks); the 70B, Qwen, luna, nano and the two Haiku runs write 0.3 to 1.0
  errors, gpt-oss 1.7, the 8B 3.7. Sonnet also leaves the fewest compounds for code to
  split (2.6 per 100 blocks); Haiku 15.6, gpt-oss and nano the most.
- **Readability.** Sonnet reads easiest (59 in German), the 70B and Claude Haiku 57, Haiku
  with Sonnet judging 56, Qwen 55, the 8B 52, nano 48, gpt-oss 46, luna 44: the OpenAI
  models and gpt-oss write short sentences with long words. Sonnet scores highest on SARI
  (47), the closeness to the official versions; Haiku and luna follow (44 to 45).
- **The judge alone.** The run with Haiku writing and Sonnet judging reused Haiku's
  Understand and first Write answers, so the differences to the Haiku run come only from
  the judge and the repairs it asked for: unsupported statements fall from 8.6 to 5.6 per
  100 blocks (Sonnet flags fewer of Haiku's sentences than Haiku itself), hard facts rise
  from 92 to 93 % in German and from 83 to 87 % in French, SARI from 44.1 to 44.7, while
  the repairs add a few warnings (29.9 to 33.5) and the price per page grows ninefold
  (USD 0.009 to 0.077): the judge's calls carry most of the tokens of a run.
- **Speed and price.** gpt-oss on Groq: 11.5 s and USD 0.005 per page; Claude Haiku: 33 s
  and USD 0.009 (47k tokens per page); CSCS: about 60 s and USD 0.016 (8B) or 0.025 (70B)
  at Public AI's prices; the OpenAI small models: 85 s and USD 0.017 to 0.019 per page
  (38k tokens per page); Sonnet everywhere: 73 s and USD 0.24 per page (68k tokens per
  page, the most: longer factsheets and drafts, larger judge prompts), 28 times Haiku and
  about ten times the 70B; the laptop: 588 s and no token price. The seconds per page of
  the Haiku-writes-Sonnet-judges run (29) leave out Understand and the first Write, which
  came from the cache.
- **Output budgets.** The OpenAI small models answered Understand with 6 to 9 thousand
  tokens on the long documents, past the 6,000-token budget of a stage without thinking;
  those pairs ran with the thinking budget of 12,000 (the models reason only when asked, so
  nothing else changed). Claude Haiku's Write passed 8,000 tokens on three long documents
  and Sonnet's on nine; those drafts were written in two halves, as the pipeline does.
  Sonnet's longest Understand answer reached 10,800 tokens, under the 12,000 budget.
- **Thinking.** Only Apertus on CSCS thought where the pipeline asks for it. Qwen 3.5 9B
  and gpt-oss-20b at Groq's default effort ran their reasoning to the budget's end, so Qwen
  ran without thinking and gpt-oss at the lowest effort; the OpenAI models ran with
  `reasoning_effort: none`; the Claude models with thinking switched off through the
  native field, since Anthropic's OpenAI-compatible endpoint ignores `reasoning_effort`
  and counts thinking tokens in the output budget (with thinking on, Haiku's Understand
  ran to 12,000 tokens). Each Claude model accepts a different value there: `disabled` on
  Haiku 5.5, `between_tools` on Sonnet 5.5 (the endpoint refuses `adaptive`), so the mixed
  run set the field per model.
