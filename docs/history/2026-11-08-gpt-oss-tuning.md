# gpt-oss tuning and the round defaults, 8 November 2026

A record, not a description of the current version. The Apertus 1.5 8B was unavailable
on the Public AI gateway again, no CSCS key was at hand and neither Apertus size thinks
on the gateway, so the question was which other model with a thinking mode comes close,
and whether gpt-oss, which did well on 25 October, can do better. It led to the preset
`huggingface-gpt-oss-120b-groq`, to plain hyphens in model answers and to
`pipeline.facts_rounds = 0` (CHANGELOG.md, [Unreleased]).

Every run is the full pipeline (P2) over the 23 pairs of the `eval` split that
[model-comparison.md](../model-comparison.md) compares (20 Swiss German, 3 French), with
the response cache on, scored with the rules of the day. gpt-oss ran on the Hugging Face
Inference Providers router with the suffix `:groq` (Groq's hardware), `reasoning_effort`
low unless noted. Groq's own free tier refuses the pipeline's requests (8,000 tokens per
minute); through the router there was no rate limiting. The results folders are under
`eval/` (git-ignored). Model spend for the day: about USD 4.

## gpt-oss variants

German, 20 pairs (French, 3 pairs, in the last column):

| Setup | Folder | Hard facts kept | Errors / 100 blocks | Warnings / 100 blocks | Readability | USD / page | s / page | French: facts kept |
|---|---|---|---|---|---|---|---|---|
| 25 October run, scored with today's rules | `results-hf-gpt-oss` (rescored in a copy) | 94 % | 1.7 | 30.9 | 46 | 0.0051 | 11.5 | 83 % |
| 20B writes, 120B judges (as on 25 October) | `results-hf-gpt-oss-base` | 94 % | 1.6 | 46.4 | 44 | 0.0068 | 12.8 | 73 % (2 pairs) |
| the same, the judge at medium effort | `results-hf-gpt-oss-judge-medium` | 94 % | 2.4 | 49.9 | 46 | 0.0109 | 22.7 | 82 % |
| 120B at every stage | `results-hf-gpt-oss-120b` | 96 % | 0.8 | 34.6 | 44 | 0.0073 | 16.5 | 90 % |
| 120B, the model's own temperature (1.0) | `results-hf-gpt-oss-120b-temp1` | 93 % | 0.2 | 33.7 | 44 | 0.0069 | 15.6 | 91 % |

- **The 20B gives up on a long document.** `ge-prosecutor-election-fr` (38 must-keep
  facts) failed at Write on 25 October and again here: the answer was "I'm sorry, but I
  can't provide that." with the reasoning "Must include all must_keep facts. [...] Hard.
  Probably too large." (and on the retry "maybe too long. Probably skip."). Not a safety
  refusal; the 120B writes the document.
- **The judge at medium effort** (a second provider entry in the checkout's settings, so
  that only the 120B got medium) asked for more repairs, which added text and findings:
  more errors and warnings, 60 % more cost and time, no fact more.
- **The model's own temperature** (OpenAI advises 1.0 for gpt-oss; the stages send 0.1
  to 0.3) traded facts for errors: one emergency-numbers letter kept 5 of 14 numbers
  instead of 10 (7 values lost, 3 gained of 248, none silently). More variance, no clear
  gain.
- **The 120B at every stage, effort low** won and became the preset. Run again on the
  code with plain hyphens (below), `results-hf-gpt-oss-120b-groq`: German 97 % of the
  hard facts kept, 0.5 errors, 29.1 warnings, readability 47, values not in the source
  0.0, USD 0.0081 and 14.3 s a page; French 90 %, 0.6 errors. Its `[[run]]` is in
  model-comparison.md.

## Hyphens in model answers

gpt-oss writes the non-breaking hyphen U+2011 for a plain one: the 120B 101 times in 19
of the 23 final drafts, once inside an e-mail address (`info-sebe@sa.zh.ch` with U+2011 for its
hyphen, in zh-sebe-disability-de), where the value reader then saw `sebe@sa.zh.ch`, a value not in
the source, and a reader who copies or clicks it gets a wrong address. Apertus, Haiku
and GPT-5.6 Luna wrote 0 to 3. Since then the JSON reader turns U+2010 and U+2011 in
every answer into a plain hyphen (`llm/json_out.py`); in the rerun the value not in the
source was gone (0.1 to 0.0 per 100 blocks).

## Readability and word choice

Readability stayed at 44 to 47 with both gpt-oss sizes, against 57 for the Apertus 70B
on Public AI, at the same sentence length. The gap is word length: syllables per word in
the final German drafts were 2.19 (20B), 2.18 (120B), 2.09 (Apertus 8B on CSCS), 2.00
(Apertus 70B), 1.99 (Haiku), 1.96 (Sonnet), and 17 % of the 20B's words had four
syllables or more, against 11 % for the 70B; gpt-oss also addresses the reader less
("Sie" and "Ihr" 4.1 to 5.8 % of the words, the 70B 6.5 %). The style guide already
asks for simple, familiar words; no setting of gpt-oss changed it.

The long words left in the final drafts are mostly the same for all five models looked
at (gpt-oss 20B and 120B, Apertus 70B, Haiku, Sonnet), ranked by the runs and pairs that
use them and leaving out the vocabulary lists and each draft's glossary: Informationen,
Telefonnummer, Behinderung, Unterstützung, Erwachsene, telefonisch, beantragen,
regelmässig, unterstützen, kantonale, Beratungsstelle, Privatpersonen. Candidates for
the vocabulary lists, none added (the lists are curated, and "erhalten" stands among the
context words on purpose):

| Candidate | Everyday word | Uses in 5 runs | File |
|---|---|---|---|
| Unterstützung | Hilfe | 59 | vocabulary_de.toml, replace.nouns |
| unterstützen | helfen | 13 | vocabulary_de.toml, replace.verbs |
| telefonisch | am Telefon | 20 | vocabulary_de.toml, replace.adverbs |
| kantonal | vom Kanton | 12 | vocabulary_de-CH.toml, replace.adverbs |
| benötigen | brauchen | 4 (gpt-oss-120b) | vocabulary_de.toml, replace.verbs |

## What the rounds do since 25 October

The 20B's first drafts score the same on both days with today's rules (errors 12.2 and
12.7, warnings 53.6 and 52.4 per 100 blocks), but the rounds of 8 November cut warnings
less (52.4 to 37.4 in the final drafts, against 53.6 to 26.1) and add 30 % more text
(5,203 words against 4,000). By kept round (the chain from the first draft to the final
version), German, 20 pairs:

| Run | Repair rounds: blocking fixed, words added, warnings added | Facts rounds kept: missing fixed, words added | Recover rounds kept: missing fixed, words added |
|---|---|---|---|
| gpt-oss-20b | 299, +1,365, +106 | 5: 23, +366 | 0 |
| gpt-oss-120b | 198, +1,088, +74 | 4: 9, +248 | 1: 1, +6 |
| Apertus 70B (Public AI, 3 November) | 52, +503, +35 | 11: 4, +76 | 9: 28, +358 |

Most of the growth comes from repairing gpt-oss's short first drafts (31 % of the
source's length, the 70B 39 %): missing values (FACT-01) and grammar. The list items of
FACT-10 are the larger share of the blocking findings in every model's drafts, and the
rounds add few of them:

| Blocking findings, German | First drafts | Final drafts | FACT-10, first to final |
|---|---|---|---|
| gpt-oss-20b | 284 | 144 | 165 to 126 |
| gpt-oss-120b | 235 | 157 | 171 to 150 |
| Apertus 70B (Public AI) | 223 | 164 | 124 to 116 |

They lie mostly in four documents with long lists (the accessibility statement 66 and
46 items, the municipalities letter 38 and 27, the SEBE letter 15 and 23, the outpatient
services 8 and 11). gpt-oss lists them as omissions (`FACT-10.omitted`), the 70B leaves
them out without a note. In those four pairs the repair and facts rounds added 14 items
for 562 words (120B) and none for 113 words (70B).

## The round options

The options were measured by running each model once with the defaults (A) and then
with one option changed; Understand, the first Write and every round before the change
came from A's cache, so the runs differ only from the changed round on. German, 20
pairs:

| Model | Run | Hard facts kept | Errors / 100 blocks | Warnings / 100 blocks | Readability | Tokens / page |
|---|---|---|---|---|---|---|
| gpt-oss-120b | A: defaults (`results-hf-gpt-oss-120b-groq`) | 97 % | 0.5 | 29.1 | 47 | 26,702 |
| | B: `facts_rounds = 0` | 97 % | 0.4 | 27.8 | 46 | 24,775 |
| | C: `polish_rounds = 2` | 97 % | 0.1 | 23.4 | 47 | 30,793 |
| | D: both | 97 % | 0.3 | 26.9 | 46 | 28,947 |
| Apertus 70B, Public AI | A (`results-rounds-apertus-70b-a`) | 94 % | 2.0 | 23.4 | 57 | 28,597 |
| | B | 94 % | 1.8 | 23.4 | 58 | 26,202 |
| | C | 94 % | 1.5 | 23.5 | 57 | 32,223 |
| | D | 94 % | 1.3 | 23.6 | 58 | 29,815 |
| Claude Haiku 5.5 | A (`results-rounds-haiku-a`) | 91 % | 1.5 | 32.2 | 57 | 57,005 |
| | D | 91 % | 1.7 | 31.5 | 57 | 63,542 |

French (3 pairs): the facts kept unchanged in every run (gpt-oss 90 %, Apertus 91 %,
Haiku 80 %); errors gpt-oss 0.6 (A) and 0.0 (B, C, D), Apertus 3.2 (A, B) and 1.6 (C, D),
Haiku 0.0 (A, D).

- **The facts round** kept no fact more with any of the three models and cost 7 to 8 %
  of the tokens: off by default since this record (`pipeline.facts_rounds = 0`); the
  recover round after it adds the missing values one by one, as before.
- **A second polish round** lowered the errors with gpt-oss and the Apertus 70B (and the
  warnings with gpt-oss) at 13 to 15 % more tokens, but brought nothing with Haiku
  (measured with the facts round off): the default stays one; `[pipeline]
  polish_rounds = 2` is the option for the Apertus 70B and gpt-oss.

## gpt-oss-120b on OVHcloud

The same 23 pairs with the suffix `:ovhcloud` (OVHcloud AI Endpoints, which its
documentation places in Gravelines, France, under EU data protection rules; no official
statement was found that every request stays there), on the code before the plain
hyphens and with the facts round on, so it compares with `results-hf-gpt-oss-120b`
(Groq, the same code):

| German, 20 pairs | Groq | OVHcloud |
|---|---|---|
| Hard facts kept | 96 % | 92 % |
| Errors / 100 blocks | 0.8 | 1.6 |
| Warnings / 100 blocks | 34.6 | 26.4 |
| Readability | 44 | 46 |
| Values not in the source / 100 blocks | 0.1 | 0.3 |
| USD / page | 0.0073 | 0.0054 |
| Seconds / page | 16.5 | 155 |

French (3 pairs): 90 % of the hard facts kept on both, no rule error. The OVHcloud run
lost 6 values and gained 1 against the Groq run, in three pairs, none silently; 3 of
the 6 in zh-emergency-numbers-de, which also lost 5 between two Groq runs (the
temperature variant above), so the difference is within what runs of one setup vary
by. Its three values not in the source are e-mail addresses with a non-breaking hyphen
(`fiera-opferberatung.ch`, `kokon-zh.ch`, `castagna-zh.ch` in zh-victim-counselling-de,
written with U+2011), which the plain hyphens now fix. A call took 29 s on average
(Groq 3.8 s), 133 minutes of model time against 16, and the whole run about 5 hours on
a laptop that ran other evaluations beside it. The router's prices for OVHcloud (USD 0.09 and
0.47 per million tokens) are in the Hugging Face provider's table for
`openai/gpt-oss-120b:ovhcloud`; no preset uses it.
