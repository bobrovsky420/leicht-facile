## German

Pairs: 20 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Silent losses | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 20 | - | 100 % | 0 % | 31.3 | 164.5 | 9.8 | 36 | - | - | 0.0 | - | - | - |
| Official easy-language version | 20 | - | 67 % | 33 % | 2.7 | 27.7 | 6.1 | 62 | - | - | 2.8 | - | - | - |
| P0 baseline: one prompt (swiss-ai/Apertus-v1.5-8B) | 20 | 92 % | 93 % | 7 % | 19.5 | 95.2 | 7.6 | 52 | 43.0 | - | 0.2 | 982 | 0.0001 | 2.6 |
| P0-ZH complete: Zurich's prompt, keep everything (swiss-ai/Apertus-v1.5-8B) | 20 | 83 % | 85 % | 15 % | 15.0 | 92.4 | 7.0 | 47 | 43.0 | - | 0.0 | 2393 | 0.0003 | 2.4 |
| P0-ZH condensed: Zurich's prompt, essentials only (swiss-ai/Apertus-v1.5-8B) | 20 | 69 % | 67 % | 33 % | 9.0 | 80.0 | 6.1 | 46 | 41.5 | - | 0.2 | 2198 | 0.0002 | 1.4 |
| P1 no judge: fact sheet + draft + rule check (swiss-ai/Apertus-v1.5-8B) | 20 | 74 % | 73 % | 0 % | 8.3 | 50.3 | 7.4 | 51 | 40.6 | - | 1.1 | 9555 | 0.0014 | 0.0 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-70B) | 19 | 99 % | 92 % | 0 % | 0.6 | 26.6 | 6.6 | 56 | 43.8 | 1.1 | 0.0 | 22988 | 0.0262 | 57.5 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B) | 20 | 100 % | 97 % | 0 % | 4.2 | 43.9 | 7.1 | 51 | 41.7 | 1.6 | 0.1 | 28066 | 0.0131 | 63.3 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 20 | 100 % | 95 % | 0 % | 1.9 | 41.4 | 7.1 | 53 | 42.0 | 1.0 | 0.1 | 27885 | 0.0163 | 32.4 |

Silent losses: the share of the source's hard values that the text lost without a trace. A single prompt and the official version have no fact checklist and no omission log, so every value they lose is silent; for P1 and P2 every hard value is a fact in the review checklist or lies in a listed omission, so their share is zero by design, and a value above zero names one the code completion missed.

Rule findings (errors and warnings) per 100 blocks, by family. "LEX by code" is the compounds split by code in the final version, per 100 blocks (P1 and P2 only; the baselines and the reference measure the text as written):

| Setup | LEN | ORD | GRAM | NEG | LEX | LEX by code | NUM | CH |
|---|---|---|---|---|---|---|---|---|
| SOURCE | 49.9 | 0.0 | 39.7 | 0.3 | 99.9 | - | 2.8 | 0.0 |
| REF | 10.1 | 0.0 | 6.0 | 0.0 | 12.9 | - | 0.2 | 0.0 |
| P0 (swiss-ai/Apertus-v1.5-8B) | 43.0 | 0.0 | 19.2 | 0.0 | 46.8 | 0.0 | 3.4 | 0.7 |
| P0-ZH-complete (swiss-ai/Apertus-v1.5-8B) | 30.1 | 0.0 | 17.9 | 0.1 | 52.1 | 0.0 | 3.7 | 0.0 |
| P0-ZH-condensed (swiss-ai/Apertus-v1.5-8B) | 24.7 | 0.0 | 16.4 | 0.1 | 39.9 | 0.0 | 3.1 | 0.0 |
| P1 (swiss-ai/Apertus-v1.5-8B) | 22.1 | 0.0 | 13.3 | 0.0 | 17.3 | 33.4 | 3.0 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-70B) | 10.2 | 0.0 | 5.4 | 0.0 | 6.1 | 30.7 | 1.7 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-8B) | 17.1 | 0.0 | 9.7 | 0.0 | 15.3 | 36.5 | 3.5 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 19.3 | 0.0 | 9.4 | 0.0 | 8.8 | 36.6 | 2.9 | 0.0 |

Fact-rich subset (17 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 17 | 100 % | - | - |
| REF | 17 | 61 % | - | - |
| P0 (swiss-ai/Apertus-v1.5-8B) | 17 | 91 % | 90 % | - |
| P0-ZH-complete (swiss-ai/Apertus-v1.5-8B) | 17 | 82 % | 80 % | - |
| P0-ZH-condensed (swiss-ai/Apertus-v1.5-8B) | 17 | 67 % | 69 % | - |
| P1 (swiss-ai/Apertus-v1.5-8B) | 17 | 68 % | 69 % | - |
| P2 (swiss-ai/Apertus-v1.5-70B) | 16 | 90 % | 99 % | 3 % |
| P2 (swiss-ai/Apertus-v1.5-8B) | 17 | 97 % | 100 % | 2 % |
| P2 (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 17 | 94 % | 100 % | 2 % |

Failed runs: 1 (zh-sebe-disability-de).

## French

Pairs: 3 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Silent losses | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 3 | - | 100 % | 0 % | 36.4 | 85.8 | 10.1 | 59 | - | - | 0.0 | - | - | - |
| Official easy-language version | 3 | - | 54 % | 46 % | 2.9 | 21.7 | 6.6 | 85 | - | - | 0.8 | - | - | - |
| P0 baseline: one prompt (swiss-ai/Apertus-v1.5-8B) | 3 | 61 % | 68 % | 32 % | 10.6 | 27.2 | 5.6 | 54 | 36.8 | - | 0.5 | 950 | 0.0001 | 2.7 |
| P1 no judge: fact sheet + draft + rule check (swiss-ai/Apertus-v1.5-8B) | 3 | 57 % | 53 % | 0 % | 11.3 | 29.4 | 8.5 | 72 | 40.4 | - | 0.0 | 5849 | 0.0008 | 3.2 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-70B) | 3 | 100 % | 91 % | 0 % | 4.6 | 28.1 | 9.2 | 80 | 46.2 | 0.0 | 0.0 | 17621 | 0.0201 | 42.3 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B) | 3 | 100 % | 87 % | 0 % | 4.9 | 34.0 | 8.6 | 74 | 41.6 | 1.5 | 0.0 | 23297 | 0.0113 | 47.2 |
| P2 full: pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 3 | 100 % | 93 % | 0 % | 6.6 | 33.7 | 7.2 | 70 | 41.8 | 0.7 | 0.0 | 25412 | 0.0149 | 28.2 |

Silent losses: the share of the source's hard values that the text lost without a trace. A single prompt and the official version have no fact checklist and no omission log, so every value they lose is silent; for P1 and P2 every hard value is a fact in the review checklist or lies in a listed omission, so their share is zero by design, and a value above zero names one the code completion missed.

Rule findings (errors and warnings) per 100 blocks, by family. "LEX by code" is the compounds split by code in the final version, per 100 blocks (P1 and P2 only; the baselines and the reference measure the text as written):

| Setup | LEN | ORD | GRAM | NEG | LEX | LEX by code | NUM | CH |
|---|---|---|---|---|---|---|---|---|
| SOURCE | 53.7 | 0.0 | 24.5 | 0.0 | 39.5 | - | 4.5 | 0.0 |
| REF | 17.0 | 0.0 | 4.0 | 0.0 | 3.1 | - | 0.5 | 0.0 |
| P0 (swiss-ai/Apertus-v1.5-8B) | 18.1 | 0.0 | 1.8 | 0.0 | 16.6 | 0.0 | 1.3 | 0.0 |
| P1 (swiss-ai/Apertus-v1.5-8B) | 21.1 | 0.0 | 8.9 | 0.0 | 6.1 | 0.0 | 4.7 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-70B) | 16.1 | 0.0 | 6.7 | 0.0 | 8.1 | 0.0 | 1.8 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-8B) | 17.7 | 0.0 | 5.6 | 0.0 | 8.9 | 0.0 | 6.7 | 0.0 |
| P2 (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 14.4 | 0.0 | 7.7 | 0.0 | 12.4 | 0.0 | 5.9 | 0.0 |

Fact-rich subset (3 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 3 | 100 % | - | - |
| REF | 3 | 54 % | - | - |
| P0 (swiss-ai/Apertus-v1.5-8B) | 3 | 68 % | 61 % | - |
| P1 (swiss-ai/Apertus-v1.5-8B) | 3 | 53 % | 57 % | - |
| P2 (swiss-ai/Apertus-v1.5-70B) | 3 | 91 % | 100 % | 0 % |
| P2 (swiss-ai/Apertus-v1.5-8B) | 3 | 87 % | 100 % | 2 % |
| P2 (swiss-ai/Apertus-v1.5-8B, understand swiss-ai/Apertus-v1.5-70B) | 3 | 93 % | 100 % | 0 % |
