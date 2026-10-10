## German

Pairs: 20 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Silent losses | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 20 | - | 100 % | 0 % | 31.3 | 164.5 | 9.8 | 36 | - | - | 0.0 | - | - | - |
| Official easy-language version | 20 | - | 67 % | 33 % | 2.7 | 27.7 | 6.1 | 62 | - | - | 2.8 | - | - | - |
| P0 baseline: one prompt (swiss-ai/Apertus-v1.5-8B) | 20 | 88 % | 88 % | 12 % | 22.2 | 103.3 | 7.9 | 50 | 42.6 | - | 0.2 | 944 | 0.0001 | 2.5 |
| P0-ZH complete: Zurich's prompt, keep everything (swiss-ai/Apertus-v1.5-8B) | 20 | 91 % | 93 % | 7 % | 19.5 | 100.3 | 7.5 | 46 | 42.7 | - | 0.2 | 2385 | 0.0003 | 2.4 |
| P0-ZH condensed: Zurich's prompt, essentials only (swiss-ai/Apertus-v1.5-8B) | 20 | 74 % | 75 % | 25 % | 9.6 | 74.2 | 5.9 | 47 | 42.2 | - | 0.0 | 2218 | 0.0002 | 1.6 |
| P1 no judge: fact sheet + draft + rule check (swiss-ai/Apertus-v1.5-8B) | 20 | 53 % | 51 % | 0 % | 7.0 | 40.0 | 7.4 | 50 | 38.7 | - | 0.1 | 8661 | 0.0012 | 6.5 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-70B) | 20 | 97 % | 91 % | 0 % | 1.0 | 20.3 | 6.2 | 59 | 41.7 | 0.5 | 0.0 | 23223 | 0.0260 | 44.5 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B) | 20 | 98 % | 87 % | 0 % | 2.0 | 36.5 | 7.0 | 54 | 41.2 | 1.8 | 0.0 | 32775 | 0.0171 | 33.6 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 20 | 99 % | 94 % | 0 % | 1.8 | 34.3 | 6.7 | 54 | 42.2 | 1.7 | 0.0 | 26775 | 0.0166 | 32.5 |

Silent losses: the share of the source's hard values that the text lost without a trace. A single prompt and the official version have no fact checklist and no omission log, so every value they lose is silent; for P1 and P2 every hard value is a fact in the review checklist or lies in a listed omission, so their share is zero by design, and a value above zero names one the code completion missed.

Rule findings (errors and warnings) per 100 blocks, by family. "LEX by code" is the compounds split by code in the final version, per 100 blocks (P1 and P2 only; the baselines and the reference measure the text as written):

| Setup | LEN | ORD | GRAM | NEG | LEX | LEX by code | NUM | CH |
|---|---|---|---|---|---|---|---|---|
| SOURCE | 49.9 | 0.0 | 39.7 | 0.3 | 99.9 | - | 2.8 | 0.0 |
| REF | 10.1 | 0.0 | 6.0 | 0.0 | 12.9 | - | 0.2 | 0.0 |
| P0 (swiss-ai/Apertus-v1.5-8B) | 44.2 | 0.0 | 21.9 | 0.1 | 52.9 | 0.0 | 3.4 | 0.5 |
| P0-ZH-complete (swiss-ai/Apertus-v1.5-8B) | 38.1 | 0.0 | 22.5 | 0.1 | 52.7 | 0.0 | 3.6 | 0.0 |
| P0-ZH-condensed (swiss-ai/Apertus-v1.5-8B) | 21.7 | 0.0 | 15.1 | 0.0 | 40.4 | 0.0 | 3.1 | 0.0 |
| P1 (swiss-ai/Apertus-v1.5-8B) | 19.9 | 0.0 | 9.3 | 0.0 | 9.9 | 34.9 | 2.9 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-70B) | 5.9 | 0.0 | 5.6 | 0.0 | 5.3 | 24.4 | 1.7 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-8B) | 16.5 | 0.0 | 8.0 | 0.0 | 7.8 | 34.9 | 2.7 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 10.0 | 0.0 | 10.1 | 0.0 | 10.5 | 35.3 | 2.7 | 0.0 |

Fact-rich subset (17 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 17 | 100 % | - | - |
| REF | 17 | 61 % | - | - |
| P0 (swiss-ai/Apertus-v1.5-8B) | 17 | 86 % | 86 % | - |
| P0-ZH-complete (swiss-ai/Apertus-v1.5-8B) | 17 | 91 % | 90 % | - |
| P0-ZH-condensed (swiss-ai/Apertus-v1.5-8B) | 17 | 71 % | 69 % | - |
| P1 (swiss-ai/Apertus-v1.5-8B) | 17 | 48 % | 50 % | - |
| P2 (swiss-ai/Apertus-v1.5-70B) | 17 | 89 % | 97 % | 4 % |
| P2 (swiss-ai/Apertus-v1.5-8B) | 17 | 85 % | 98 % | 1 % |
| P2 (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 17 | 93 % | 99 % | 1 % |

## French

Pairs: 3 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Silent losses | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 3 | - | 100 % | 0 % | 36.4 | 85.8 | 10.1 | 59 | - | - | 0.0 | - | - | - |
| Official easy-language version | 3 | - | 54 % | 46 % | 2.9 | 21.7 | 6.6 | 85 | - | - | 0.8 | - | - | - |
| P0 baseline: one prompt (swiss-ai/Apertus-v1.5-8B) | 3 | 36 % | 51 % | 49 % | 8.7 | 19.8 | 5.4 | 55 | 36.9 | - | 0.4 | 969 | 0.0001 | 2.7 |
| P1 no judge: fact sheet + draft + rule check (swiss-ai/Apertus-v1.5-8B) | 3 | 53 % | 53 % | 0 % | 5.2 | 33.8 | 7.2 | 71 | 43.2 | - | 0.0 | 8201 | 0.0011 | 9.6 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-70B) | 3 | 100 % | 89 % | 0 % | 6.1 | 40.2 | 9.2 | 79 | 45.0 | 0.7 | 0.0 | 20820 | 0.0242 | 39.3 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B) | 3 | 94 % | 70 % | 0 % | 2.1 | 37.8 | 7.5 | 71 | 43.7 | 1.5 | 0.0 | 31205 | 0.0157 | 32.4 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 3 | 100 % | 88 % | 0 % | 17.8 | 40.3 | 10.8 | 78 | 46.4 | 0.7 | 0.0 | 18354 | 0.0127 | 20.7 |

Silent losses: the share of the source's hard values that the text lost without a trace. A single prompt and the official version have no fact checklist and no omission log, so every value they lose is silent; for P1 and P2 every hard value is a fact in the review checklist or lies in a listed omission, so their share is zero by design, and a value above zero names one the code completion missed.

Rule findings (errors and warnings) per 100 blocks, by family. "LEX by code" is the compounds split by code in the final version, per 100 blocks (P1 and P2 only; the baselines and the reference measure the text as written):

| Setup | LEN | ORD | GRAM | NEG | LEX | LEX by code | NUM | CH |
|---|---|---|---|---|---|---|---|---|
| SOURCE | 53.7 | 0.0 | 24.5 | 0.0 | 39.5 | - | 4.5 | 0.0 |
| REF | 17.0 | 0.0 | 4.0 | 0.0 | 3.1 | - | 0.5 | 0.0 |
| P0 (swiss-ai/Apertus-v1.5-8B) | 15.1 | 0.0 | 0.4 | 0.0 | 11.8 | 0.0 | 1.2 | 0.0 |
| P1 (swiss-ai/Apertus-v1.5-8B) | 15.7 | 0.0 | 10.5 | 0.4 | 9.9 | 0.0 | 2.6 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-70B) | 17.6 | 0.0 | 9.5 | 0.0 | 14.2 | 0.0 | 5.0 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-8B) | 17.8 | 0.0 | 8.0 | 0.3 | 10.8 | 0.0 | 2.9 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 25.8 | 0.0 | 12.2 | 0.0 | 10.6 | 0.0 | 9.5 | 0.0 |

Fact-rich subset (3 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 3 | 100 % | - | - |
| REF | 3 | 54 % | - | - |
| P0 (swiss-ai/Apertus-v1.5-8B) | 3 | 51 % | 36 % | - |
| P1 (swiss-ai/Apertus-v1.5-8B) | 3 | 53 % | 53 % | - |
| P2 (swiss-ai/Apertus-v1.5-70B) | 3 | 89 % | 100 % | 0 % |
| P2 (swiss-ai/Apertus-v1.5-8B) | 3 | 70 % | 94 % | 2 % |
| P2 (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 3 | 88 % | 100 % | 0 % |
