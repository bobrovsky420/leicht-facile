# Evaluation tables

Written by `python -m leichtfacile eval report` from `eval/results-publicai`; do not edit
by hand.

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
