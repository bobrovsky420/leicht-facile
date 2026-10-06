## German

Pairs: 20 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Invented / 100 blocks | Invented values / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 20 | - | 100 % | 31.3 | 145.6 | 9.8 | 36 | - | - | 0.0 | - | - | - |
| Official easy-language version | 20 | - | 70 % | 2.7 | 26.7 | 6.1 | 62 | - | - | 2.2 | - | - | - |
| C0: one prompt (swiss-ai/apertus-v1.5-8b) | 10 | 83 % | 90 % | 16.1 | 85.4 | 7.1 | 46 | 43.8 | - | - | 937 | 0.0001 | 13.9 |

Rule findings (errors and warnings) per 100 blocks, by family:

| Setup | LEN | ORD | GRAM | NEG | LEX | NUM | CH |
|---|---|---|---|---|---|---|---|
| SOURCE | 49.9 | 0.0 | 39.7 | 0.3 | 80.9 | 2.8 | 0.0 |
| REF | 10.1 | 0.0 | 5.9 | 0.0 | 11.9 | 0.2 | 0.0 |
| C0 (swiss-ai/apertus-v1.5-8b) | 33.4 | 0.0 | 16.9 | 0.2 | 47.3 | 2.6 | 0.1 |

Fact-rich subset (14 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 14 | 100 % | - | - |
| REF | 14 | 60 % | - | - |
| C0 (swiss-ai/apertus-v1.5-8b) | 9 | 89 % | 80 % | - |

## French

Pairs: 3 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Invented / 100 blocks | Invented values / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 3 | - | 100 % | 36.4 | 69.9 | 10.1 | 59 | - | - | 0.0 | - | - | - |
| Official easy-language version | 3 | - | 60 % | 2.9 | 21.2 | 6.6 | 85 | - | - | 0.5 | - | - | - |

Rule findings (errors and warnings) per 100 blocks, by family:

| Setup | LEN | ORD | GRAM | NEG | LEX | NUM | CH |
|---|---|---|---|---|---|---|---|
| SOURCE | 53.7 | 0.0 | 24.9 | 0.0 | 23.2 | 4.5 | 0.0 |
| REF | 17.0 | 0.0 | 4.0 | 0.0 | 2.6 | 0.5 | 0.0 |

Fact-rich subset (3 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 3 | 100 % | - | - |
| REF | 3 | 60 % | - | - |
