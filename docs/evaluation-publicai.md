# Evaluation tables

Written by `python -m leichtfacile eval report` from `eval/results-publicai`; do not edit
by hand.

## German (Germany)

Pairs: 8 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Silent losses | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 8 | - | 100 % | 0 % | 42.9 | 198.4 | 11.5 | 39 | - | - | 0.0 | - | - | - |
| Official easy-language version | 8 | - | 47 % | 53 % | 3.5 | 28.0 | 7.0 | 59 | - | - | 4.8 | - | - | - |
| P0 baseline: one prompt (swiss-ai/apertus-v1.5-70b) | 8 | 74 % | 74 % | 26 % | 23.6 | 127.6 | 8.6 | 53 | 40.7 | - | 0.9 | 784 | 0.0012 | 5.2 |
| P1 no judge: fact sheet + draft + rule check (swiss-ai/apertus-v1.5-70b) | 8 | 61 % | 60 % | 0 % | 5.2 | 39.8 | 7.5 | 56 | 39.7 | - | 0.8 | 3866 | 0.0051 | 12.4 |
| P2 full: pipeline with judge and repair (swiss-ai/apertus-v1.5-70b) | 8 | 95 % | 87 % | 0 % | 4.1 | 37.8 | 7.6 | 59 | 40.8 | 0.2 | 0.2 | 17420 | 0.0190 | 26.1 |

Silent losses: the share of the source's hard values that the text lost without a trace. A single prompt and the official version have no fact checklist and no omission log, so every value they lose is silent; for P1 and P2 every hard value is a fact in the review checklist or lies in a listed omission, so their share is zero by design, and a value above zero names one the code completion missed.

Rule findings (errors and warnings) per 100 blocks, by family. "LEX by code" is the compounds split by code in the final version, per 100 blocks (P1 and P2 only; the baselines and the reference measure the text as written):

| Setup | LEN | ORD | GRAM | NEG | LEX | LEX by code | NUM | REG |
|---|---|---|---|---|---|---|---|---|
| SOURCE | 64.9 | 0.0 | 49.3 | 0.1 | 120.1 | - | 5.7 | 0.0 |
| REF | 18.4 | 0.0 | 5.0 | 0.0 | 6.9 | - | 0.5 | 0.0 |
| P0 (swiss-ai/apertus-v1.5-70b) | 50.3 | 0.0 | 26.7 | 0.0 | 67.4 | 0.0 | 5.2 | 0.0 |
| P1 (swiss-ai/apertus-v1.5-70b) | 13.0 | 0.0 | 15.0 | 0.0 | 9.1 | 38.4 | 4.9 | 0.3 |
| P2 (swiss-ai/apertus-v1.5-70b) | 12.0 | 0.0 | 15.9 | 0.0 | 5.8 | 34.0 | 5.9 | 0.5 |

Fact-rich subset (7 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 7 | 100 % | - | - |
| REF | 7 | 39 % | - | - |
| P0 (swiss-ai/apertus-v1.5-70b) | 7 | 70 % | 71 % | - |
| P1 (swiss-ai/apertus-v1.5-70b) | 7 | 54 % | 55 % | - |
| P2 (swiss-ai/apertus-v1.5-70b) | 7 | 86 % | 95 % | 2 % |

## German (Austria)

Pairs: 8 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Silent losses | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 8 | - | 100 % | 0 % | 40.3 | 180.8 | 9.9 | 32 | - | - | 0.0 | - | - | - |
| Official easy-language version | 8 | - | 65 % | 35 % | 12.4 | 74.4 | 8.2 | 51 | - | - | 3.5 | - | - | - |
| P0 baseline: one prompt (swiss-ai/apertus-v1.5-70b) | 8 | 69 % | 71 % | 29 % | 24.2 | 99.0 | 8.3 | 57 | 44.1 | - | 1.0 | 929 | 0.0015 | 7.3 |
| P1 no judge: fact sheet + draft + rule check (swiss-ai/apertus-v1.5-70b) | 8 | 68 % | 67 % | 0 % | 7.6 | 41.7 | 7.6 | 61 | 41.7 | - | 2.2 | 7535 | 0.0106 | 27.6 |
| P2 full: pipeline with judge and repair (swiss-ai/apertus-v1.5-70b) | 8 | 96 % | 96 % | 0 % | 4.7 | 42.2 | 7.5 | 61 | 43.2 | 1.8 | 0.4 | 38273 | 0.0428 | 72.4 |

Silent losses: the share of the source's hard values that the text lost without a trace. A single prompt and the official version have no fact checklist and no omission log, so every value they lose is silent; for P1 and P2 every hard value is a fact in the review checklist or lies in a listed omission, so their share is zero by design, and a value above zero names one the code completion missed.

Rule findings (errors and warnings) per 100 blocks, by family. "LEX by code" is the compounds split by code in the final version, per 100 blocks (P1 and P2 only; the baselines and the reference measure the text as written):

| Setup | LEN | ORD | GRAM | NEG | LEX | LEX by code | NUM | REG |
|---|---|---|---|---|---|---|---|---|
| SOURCE | 41.4 | 0.0 | 57.8 | 0.0 | 111.0 | - | 8.9 | 0.0 |
| REF | 32.5 | 0.0 | 21.5 | 0.0 | 30.2 | - | 0.9 | 0.0 |
| P0 (swiss-ai/apertus-v1.5-70b) | 41.4 | 0.0 | 30.6 | 0.0 | 43.9 | 0.0 | 4.9 | 0.0 |
| P1 (swiss-ai/apertus-v1.5-70b) | 18.4 | 0.0 | 13.6 | 0.0 | 10.1 | 27.0 | 3.8 | 0.0 |
| P2 (swiss-ai/apertus-v1.5-70b) | 15.1 | 0.0 | 13.7 | 0.0 | 11.2 | 26.4 | 4.2 | 0.0 |

Fact-rich subset (8 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 8 | 100 % | - | - |
| REF | 8 | 65 % | - | - |
| P0 (swiss-ai/apertus-v1.5-70b) | 8 | 71 % | 69 % | - |
| P1 (swiss-ai/apertus-v1.5-70b) | 8 | 67 % | 68 % | - |
| P2 (swiss-ai/apertus-v1.5-70b) | 8 | 96 % | 96 % | 5 % |

## Italian

Pairs: 9 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Silent losses | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 9 | - | 100 % | 0 % | 40.1 | 110.6 | 16.6 | 50 | - | - | 0.0 | - | - | - |
| Official easy-language version | 9 | - | 31 % | 69 % | 13.1 | 42.4 | 9.2 | 73 | - | - | 2.5 | - | - | - |
| P0 baseline: one prompt (swiss-ai/apertus-v1.5-70b) | 9 | 56 % | 49 % | 51 % | 18.3 | 67.6 | 11.7 | 63 | 44.3 | - | 0.2 | 750 | 0.0012 | 3.1 |
| P1 no judge: fact sheet + draft + rule check (swiss-ai/apertus-v1.5-70b) | 9 | 89 % | 73 % | 0 % | 2.7 | 36.2 | 7.6 | 79 | 43.2 | - | 0.0 | 4158 | 0.0057 | 15.1 |
| P2 full: pipeline with judge and repair (swiss-ai/apertus-v1.5-70b) | 9 | 100 % | 82 % | 0 % | 0.5 | 35.3 | 7.8 | 78 | 43.3 | 2.0 | 0.0 | 17505 | 0.0195 | 23.4 |

Silent losses: the share of the source's hard values that the text lost without a trace. A single prompt and the official version have no fact checklist and no omission log, so every value they lose is silent; for P1 and P2 every hard value is a fact in the review checklist or lies in a listed omission, so their share is zero by design, and a value above zero names one the code completion missed.

Rule findings (errors and warnings) per 100 blocks, by family. "LEX by code" is the compounds split by code in the final version, per 100 blocks (P1 and P2 only; the baselines and the reference measure the text as written):

| Setup | LEN | ORD | GRAM | NEG | LEX | LEX by code | NUM | REG |
|---|---|---|---|---|---|---|---|---|
| SOURCE | 53.4 | 0.0 | 28.4 | 0.3 | 64.0 | - | 4.7 | 0.0 |
| REF | 30.4 | 0.0 | 5.8 | 0.0 | 16.7 | - | 2.7 | 0.0 |
| P0 (swiss-ai/apertus-v1.5-70b) | 39.9 | 0.0 | 10.5 | 0.0 | 30.7 | 0.0 | 4.9 | 0.0 |
| P1 (swiss-ai/apertus-v1.5-70b) | 13.5 | 0.0 | 3.5 | 0.2 | 15.2 | 0.0 | 6.4 | 0.0 |
| P2 (swiss-ai/apertus-v1.5-70b) | 13.8 | 0.0 | 3.0 | 0.2 | 14.5 | 0.0 | 4.3 | 0.0 |

Fact-rich subset (9 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 9 | 100 % | - | - |
| REF | 9 | 31 % | - | - |
| P0 (swiss-ai/apertus-v1.5-70b) | 9 | 49 % | 56 % | - |
| P1 (swiss-ai/apertus-v1.5-70b) | 9 | 73 % | 89 % | - |
| P2 (swiss-ai/apertus-v1.5-70b) | 9 | 82 % | 100 % | 5 % |
