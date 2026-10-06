## German

Pairs: 20 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Invented / 100 blocks | Invented values / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 20 | - | 100 % | 31.3 | 145.6 | 9.8 | 36 | - | - | 0.0 | - | - | - |
| Official easy-language version | 20 | - | 70 % | 2.7 | 26.7 | 6.1 | 62 | - | - | 2.2 | - | - | - |
| C0: one prompt (swiss-ai/Apertus-v1.5-8B) | 20 | 98 % | 100 % | 22.0 | 95.0 | 7.7 | 50 | 44.5 | - | 0.0 | 982 | 0.0001 | 2.0 |
| C1: fact sheet + draft + rule check (swiss-ai/Apertus-v1.5-8B) | 20 | 72 % | 69 % | 9.9 | 58.5 | 7.3 | 50 | 38.8 | - | 3.2 | 8537 | 0.0012 | 10.9 |
| C2: full pipeline with judge and repair (swiss-ai/Apertus-v1.5-70B) | 5 | 68 % | 71 % | 2.0 | 41.5 | 6.9 | 58 | 42.2 | 6.0 | 0.7 | 11672 | 0.0141 | 19.6 |
| C2: full pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B) | 20 | 84 % | 80 % | 4.3 | 58.4 | 6.8 | 51 | 40.6 | 6.9 | 0.1 | 21711 | 0.0105 | 23.3 |

Rule findings (errors and warnings) per 100 blocks, by family:

| Setup | LEN | ORD | GRAM | NEG | LEX | NUM | CH |
|---|---|---|---|---|---|---|---|
| SOURCE | 49.9 | 0.0 | 39.7 | 0.3 | 80.9 | 2.8 | 0.0 |
| REF | 10.1 | 0.0 | 5.9 | 0.0 | 11.9 | 0.2 | 0.0 |
| C0 (swiss-ai/Apertus-v1.5-8B) | 43.8 | 0.0 | 21.6 | 0.1 | 45.2 | 3.5 | 0.5 |
| C1 (swiss-ai/Apertus-v1.5-8B) | 21.3 | 0.0 | 13.7 | 0.1 | 27.2 | 1.8 | 0.0 |
| C2 (swiss-ai/Apertus-v1.5-70B) | 14.8 | 0.0 | 5.4 | 0.0 | 20.2 | 1.0 | 0.0 |
| C2 (swiss-ai/Apertus-v1.5-8B) | 17.3 | 0.0 | 12.3 | 0.1 | 27.1 | 1.9 | 0.0 |

Fact-rich subset (14 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 14 | 100 % | - | - |
| REF | 14 | 60 % | - | - |
| C0 (swiss-ai/Apertus-v1.5-8B) | 14 | 99 % | 97 % | - |
| C1 (swiss-ai/Apertus-v1.5-8B) | 14 | 65 % | 67 % | - |
| C2 (swiss-ai/Apertus-v1.5-70B) | 4 | 64 % | 60 % | 1 % |
| C2 (swiss-ai/Apertus-v1.5-8B) | 14 | 73 % | 77 % | 9 % |

## French

Pairs: 3 (eval split). Means over pairs; a dash means not applicable.

| Setup | Pairs | Fact coverage | Hard facts kept | Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability | SARI | Invented / 100 blocks | Invented values / 100 blocks | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Original (standard language) | 3 | - | 100 % | 36.4 | 69.9 | 10.1 | 59 | - | - | 0.0 | - | - | - |
| Official easy-language version | 3 | - | 60 % | 2.9 | 21.2 | 6.6 | 85 | - | - | 0.5 | - | - | - |
| C0: one prompt (swiss-ai/Apertus-v1.5-8B) | 3 | 59 % | 72 % | 10.5 | 26.0 | 5.8 | 53 | 36.7 | - | 0.0 | 980 | 0.0001 | 0.0 |
| C1: fact sheet + draft + rule check (swiss-ai/Apertus-v1.5-8B) | 3 | 73 % | 54 % | 5.1 | 21.2 | 8.7 | 75 | 44.2 | - | 0.0 | 6019 | 0.0008 | 1.2 |
| C2: full pipeline with judge and repair (swiss-ai/Apertus-v1.5-8B) | 3 | 73 % | 54 % | 4.6 | 22.7 | 8.8 | 75 | 44.4 | 2.5 | 0.0 | 12147 | 0.0048 | 122.4 |

Rule findings (errors and warnings) per 100 blocks, by family:

| Setup | LEN | ORD | GRAM | NEG | LEX | NUM | CH |
|---|---|---|---|---|---|---|---|
| SOURCE | 53.7 | 0.0 | 24.9 | 0.0 | 23.2 | 4.5 | 0.0 |
| REF | 17.0 | 0.0 | 4.0 | 0.0 | 2.6 | 0.5 | 0.0 |
| C0 (swiss-ai/Apertus-v1.5-8B) | 19.1 | 0.0 | 2.2 | 0.0 | 13.8 | 1.3 | 0.0 |
| C1 (swiss-ai/Apertus-v1.5-8B) | 15.2 | 0.0 | 4.6 | 0.0 | 3.4 | 3.2 | 0.0 |
| C2 (swiss-ai/Apertus-v1.5-8B) | 16.7 | 0.0 | 4.4 | 0.0 | 3.3 | 3.0 | 0.0 |

Fact-rich subset (3 pairs with at least 3 hard facts):

| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |
|---|---|---|---|---|
| SOURCE | 3 | 100 % | - | - |
| REF | 3 | 60 % | - | - |
| C0 (swiss-ai/Apertus-v1.5-8B) | 3 | 72 % | 59 % | - |
| C1 (swiss-ai/Apertus-v1.5-8B) | 3 | 54 % | 73 % | - |
| C2 (swiss-ai/Apertus-v1.5-8B) | 3 | 54 % | 73 % | 0 % |
