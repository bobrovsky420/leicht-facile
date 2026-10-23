# Evaluation tables

Written by `python -m leichtfacile eval report` from `eval/results-cscs`; do not edit
by hand.

## German

Pairs: 20 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Silent losses | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 20 | - | 100 % | 0 % | 31.3 | 164.5 | 9.8 | 36 | - | - | 0.0 | - | - | - |
| Official easy-language version | 20 | - | 67 % | 33 % | 2.7 | 27.7 | 6.1 | 62 | - | - | 2.8 | - | - | - |
| P0 baseline: one prompt (swiss-ai/Apertus-v1.5-8B) | 20 | 94 % | 95 % | 5 % | 24.9 | 108.6 | 8.0 | 49 | 44.3 | - | 0.2 | 999 | 0.0001 | 2.8 |
| P0-ZH complete: Zurich's prompt, keep everything (swiss-ai/Apertus-v1.5-8B) | 20 | 82 % | 85 % | 15 % | 15.0 | 92.4 | 7.0 | 47 | 43.0 | - | 0.0 | 2393 | 0.0003 | 2.4 |
| P0-ZH default: Zurich's prompt, essentials only (swiss-ai/Apertus-v1.5-8B) | 20 | 65 % | 67 % | 33 % | 9.0 | 80.0 | 6.1 | 46 | 41.5 | - | 0.0 | 2198 | 0.0002 | 1.4 |
| P1 no judge: fact sheet + draft + rule check (swiss-ai/Apertus-v1.5-8B) | 20 | 61 % | 59 % | 1 % | 9.7 | 46.6 | 7.1 | 50 | 39.6 | - | 0.1 | 8900 | 0.0012 | 3.6 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-70B) | 19 | 100 % | 96 % | 0 % | 0.5 | 22.2 | 6.5 | 57 | 42.9 | 1.0 | 0.0 | 22295 | 0.0250 | 60.0 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B) | 20 | 100 % | 97 % | 0 % | 3.7 | 41.5 | 7.0 | 52 | 42.2 | 2.7 | 0.0 | 33392 | 0.0159 | 59.6 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 20 | 99 % | 94 % | 0 % | 3.0 | 37.6 | 6.8 | 53 | 42.3 | 1.4 | 0.0 | 24307 | 0.0145 | 31.8 |

Silent losses: the share of the source's hard values that the text lost without a trace. A single prompt and the official version have no fact checklist and no omission log, so every value they lose is silent; for P1 and P2 every hard value is a fact in the review checklist or lies in a listed omission, so their share is zero by design, and a value above zero names one the code completion missed.

Rule findings (errors and warnings) per 100 blocks, by family. "LEX by code" is the compounds split by code in the final version, per 100 blocks (P1 and P2 only; the baselines and the reference measure the text as written):

| Setup | LEN | ORD | GRAM | NEG | LEX | LEX by code | NUM | CH |
|---|---|---|---|---|---|---|---|---|
| SOURCE | 49.9 | 0.0 | 39.7 | 0.3 | 99.9 | - | 2.8 | 0.0 |
| REF | 10.1 | 0.0 | 6.0 | 0.0 | 12.9 | - | 0.2 | 0.0 |
| P0 (swiss-ai/Apertus-v1.5-8B) | 45.5 | 0.0 | 26.7 | 0.1 | 55.8 | 0.0 | 3.6 | 0.2 |
| P0-ZH-complete (swiss-ai/Apertus-v1.5-8B) | 30.1 | 0.0 | 17.9 | 0.1 | 52.1 | 0.0 | 3.7 | 0.0 |
| P0-ZH-condensed (swiss-ai/Apertus-v1.5-8B) | 24.7 | 0.0 | 16.4 | 0.1 | 39.9 | 0.0 | 3.1 | 0.0 |
| P1 (swiss-ai/Apertus-v1.5-8B) | 23.8 | 0.0 | 11.8 | 0.1 | 14.5 | 34.8 | 2.2 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-70B) | 7.0 | 0.0 | 4.4 | 0.0 | 7.3 | 29.2 | 1.3 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-8B) | 17.6 | 0.0 | 9.6 | 0.0 | 11.9 | 34.1 | 3.2 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 16.3 | 0.0 | 9.2 | 0.0 | 9.1 | 32.3 | 3.4 | 0.0 |

Fact-rich subset (17 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 17 | 100 % | - | - |
| REF | 17 | 61 % | - | - |
| P0 (swiss-ai/Apertus-v1.5-8B) | 17 | 94 % | 93 % | - |
| P0-ZH-complete (swiss-ai/Apertus-v1.5-8B) | 17 | 82 % | 79 % | - |
| P0-ZH-condensed (swiss-ai/Apertus-v1.5-8B) | 17 | 68 % | 65 % | - |
| P1 (swiss-ai/Apertus-v1.5-8B) | 17 | 58 % | 60 % | - |
| P2 (swiss-ai/Apertus-v1.5-70B) | 16 | 96 % | 100 % | 3 % |
| P2 (swiss-ai/Apertus-v1.5-8B) | 17 | 97 % | 99 % | 6 % |
| P2 (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 17 | 96 % | 99 % | 4 % |

Failed runs: 1 (zh-sebe-disability-de).

## French

Pairs: 3 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Silent losses | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 3 | - | 100 % | 0 % | 36.4 | 85.8 | 10.1 | 59 | - | - | 0.0 | - | - | - |
| Official easy-language version | 3 | - | 54 % | 46 % | 2.9 | 21.7 | 6.6 | 85 | - | - | 0.8 | - | - | - |
| P0 baseline: one prompt (swiss-ai/Apertus-v1.5-8B) | 3 | 89 % | 89 % | 11 % | 29.7 | 68.3 | 8.9 | 54 | 36.8 | - | 0.4 | 983 | 0.0001 | 2.9 |
| P1 no judge: fact sheet + draft + rule check (swiss-ai/Apertus-v1.5-8B) | 3 | 72 % | 63 % | 0 % | 6.3 | 30.1 | 8.0 | 67 | 39.7 | - | 0.0 | 5569 | 0.0008 | 4.9 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-70B) | 3 | 100 % | 89 % | 0 % | 3.4 | 17.4 | 7.7 | 80 | 47.3 | 0.5 | 0.0 | 14704 | 0.0177 | 39.2 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B) | 3 | 100 % | 72 % | 0 % | 3.5 | 25.8 | 8.2 | 70 | 40.2 | 8.4 | 0.0 | 23493 | 0.0156 | 43.5 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 3 | 95 % | 87 % | 0 % | 8.8 | 45.5 | 8.7 | 73 | 42.4 | 13.6 | 0.0 | 26369 | 0.0157 | 38.9 |

Silent losses: the share of the source's hard values that the text lost without a trace. A single prompt and the official version have no fact checklist and no omission log, so every value they lose is silent; for P1 and P2 every hard value is a fact in the review checklist or lies in a listed omission, so their share is zero by design, and a value above zero names one the code completion missed.

Rule findings (errors and warnings) per 100 blocks, by family. "LEX by code" is the compounds split by code in the final version, per 100 blocks (P1 and P2 only; the baselines and the reference measure the text as written):

| Setup | LEN | ORD | GRAM | NEG | LEX | LEX by code | NUM | CH |
|---|---|---|---|---|---|---|---|---|
| SOURCE | 53.7 | 0.0 | 24.5 | 0.0 | 39.5 | - | 4.5 | 0.0 |
| REF | 17.0 | 0.0 | 4.0 | 0.0 | 3.1 | - | 0.5 | 0.0 |
| P0 (swiss-ai/Apertus-v1.5-8B) | 43.0 | 0.0 | 20.7 | 0.0 | 30.0 | 0.0 | 4.4 | 0.0 |
| P1 (swiss-ai/Apertus-v1.5-8B) | 14.4 | 0.0 | 7.0 | 0.0 | 11.4 | 0.0 | 3.6 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-70B) | 6.0 | 0.0 | 4.6 | 0.0 | 8.4 | 0.0 | 1.7 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-8B) | 14.4 | 0.0 | 4.7 | 0.0 | 7.5 | 0.0 | 2.7 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 17.0 | 0.0 | 7.8 | 0.0 | 22.4 | 0.0 | 7.2 | 0.0 |

Fact-rich subset (3 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 3 | 100 % | - | - |
| REF | 3 | 54 % | - | - |
| P0 (swiss-ai/Apertus-v1.5-8B) | 3 | 89 % | 89 % | - |
| P1 (swiss-ai/Apertus-v1.5-8B) | 3 | 63 % | 72 % | - |
| P2 (swiss-ai/Apertus-v1.5-70B) | 3 | 89 % | 100 % | 0 % |
| P2 (swiss-ai/Apertus-v1.5-8B) | 3 | 72 % | 100 % | 5 % |
| P2 (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 3 | 87 % | 95 % | 8 % |
