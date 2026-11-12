# Prompt variants on five models, and what was built instead, 11 November 2026

A record, not a description of the current version. The prompts, guards and rounds were
developed on the Apertus 1.5 8B; nine other models then ran on them unchanged
([model-scorecard.md](../model-scorecard.md)). The question was whether better prompts,
or prompts of their own, would get more out of the other models. They did not: wording
moved the first drafts and not the final ones, and the same sentence moved models in
opposite directions. What the stored runs and the new ones showed instead led to three
changes (CHANGELOG.md, [Unreleased]): the evaluation's reference facts kept, contact
values that are kept whatever the model marks, and the judge's role as a setting of its
model (`judge_role`).

The stored runs are the 13 of [model-comparison.md](../model-comparison.md) that ran one
setup each, read again without a model call (German, the 20 pairs of the `eval` split).
The new runs are on the 30 Swiss German pairs (20 eval, 10 dev) with gpt-oss-120b (Groq
through the Hugging Face router, effort low), Mistral Small 4 (no thinking), Claude
Haiku 5.5 (no thinking) and the Apertus 1.5 70B and 8B (Public AI, no thinking; the 8B
on the 10 dev pairs, its endpoint gave about 20 tokens a second). The repository's
templates stayed as they were: each variant ran on a copy of the templates with its
edit, against two fresh samples of the unchanged ones on the same fact sheets, and a
difference comes with a 90 % bootstrap interval over the pairs; a star marks one that
excludes zero. With six arms and five models some stars are chance. Folder
`eval/prompt-study` (git-ignored), with the scripts and the changed templates in
`scripts/`. Model spend: about USD 9 at list prices.

## Where the lost values stand

Every run finds 99 to 100 % of the facts its own fact sheet says to keep. The hard
values a final draft lacks are mostly values the fact sheet did not ask for: Understand
had listed their passage as droppable, so code made them background facts
(architecture.md §4.2), or had marked its own fact as background.

| Run | Hard values | Kept, first draft | Kept, final draft | Lost: a must-keep fact | Lost: background by Understand | Lost: in a droppable passage | Lost: no fact | Sentences listed as droppable |
|---|---|---|---|---|---|---|---|---|
| Apertus 8B, 70B judges (CSCS) | 199 | 61 % | 97 % | 1 | 0 | 8 | 0 | 7 % |
| Apertus 70B (CSCS, 19 pairs) | 180 | 69 % | 96 % | 1 | 0 | 7 | 0 | 13 % |
| Apertus 70B (Public AI) | 199 | 71 % | 94 % | 4 | 0 | 12 | 1 | 13 % |
| Qwen 3.5 9B | 199 | 68 % | 87 % | 7 | 2 | 26 | 1 | 22 % |
| gpt-oss-20b, 120b judges | 199 | 81 % | 94 % | 0 | 0 | 13 | 0 | 15 % |
| gpt-oss-120b (Groq) | 199 | 81 % | 97 % | 1 | 1 | 6 | 1 | 23 % |
| Mistral Small 4 | 199 | 80 % | 85 % | 0 | 0 | 33 | 1 | 43 % |
| Mistral Small 4, thinking | 199 | 84 % | 92 % | 0 | 1 | 15 | 1 | 29 % |
| GPT-5.4-nano | 199 | 79 % | 93 % | 7 | 2 | 10 | 0 | 22 % |
| GPT-5.6-luna | 199 | 82 % | 90 % | 1 | 3 | 18 | 1 | 23 % |
| Claude Haiku 5.5 | 199 | 84 % | 92 % | 0 | 3 | 16 | 1 | 24 % |
| Claude Sonnet 5.5 | 199 | 84 % | 91 % | 0 | 1 | 17 | 1 | 25 % |
| Claude Opus 5.5 | 199 | 80 % | 91 % | 4 | 6 | 11 | 1 | 25 % |

So the order of the runs in "hard facts kept" is largely the order of how much each
model's Understand lists as droppable. Whether such a drop is a loss, the official
easy-language version of the same page can say: of the 281 values the thirteen fact
sheets left droppable or marked as background, the official versions keep 93 (33 %);
of the 2,274 they asked to keep, 1,571 (69 %). Per run the official versions keep 1 to
7 of the values left out, but 26 of Mistral Small 4's 50 without thinking and 11 of
Qwen's 29. What the others leave out is mostly what a translator leaves out: the date a
law came into force, the dates of PDF documents for professionals, the ages of the
people in example cases, a contact for the press. By kind:

| Kind | Left droppable | of those the official version keeps |
|---|---|---|
| period | 98 | 37 (38 %) |
| date | 65 | 6 (9 %) |
| time | 41 | 16 (39 %) |
| web address | 22 | 9 (41 %) |
| e-mail address | 17 | 11 (65 %) |
| percentage | 12 | 0 |
| postal address | 11 | 8 (73 %) |
| amount | 9 | 2 (22 %) |
| phone number | 5 | 4 (80 %) |
| quantity | 1 | 0 |

Three more readings of the stored runs:

- **The first drafts skip what code added.** Of the must-keep facts with a value, the
  first drafts miss the model's own less often than those code added for a value the
  model had not listed: Apertus 70B on Public AI 3 against 30 %, Qwen 6 against 48 %,
  gpt-oss-120b 5 against 25 %, Mistral Small 4 0 against 9 %, GPT-5.4-nano 12 against
  33 %, Haiku 8 against 22 %, Sonnet 11 against 18 %; the Apertus 8B the other way
  round (54 against 36 %). Sonnet and gpt-oss list part of them as omissions of their
  own, against the fact sheet's must-keep.
- **Judge and repair are three quarters of the tokens** of every model: the judge 37 to
  48 %, the repair rounds 30 to 35 %, Write 12 to 17 %, Understand 7 to 12 %.
- **A strong judge is never done.** Semantic findings per report: Apertus 70B 0.3,
  gpt-oss-120b 2.2, Qwen 4.2, GPT-5.4-nano 5.8, Sonnet 8.0, luna 9.7, Mistral Small 4
  10.1, Haiku 11.3. Of 20 jobs, those that end with nothing blocking: Haiku 0, Sonnet,
  luna and Mistral Small 4 1, nano 2, gpt-oss-120b and Opus 6, the Apertus 70B on CSCS
  9 of 19; in the final drafts of the Claude and OpenAI models 7 to 9 blocking findings a
  pair are left, nearly all the judge's. Haiku and Sonnet on the same 23 first drafts
  of Haiku agree on the facts (93 %, Cohen's kappa 0.83, 543 verdicts) and hardly on
  single blocks: 104 and 37 unsupported blocks, 15 in common; 218 and 158 semantic
  findings, 34 in common.

## A rule against dropping what the reader needs

Three wordings in the German Understand prompt, Understand alone on the 30 pairs. The
share of a page's hard values that the fact sheet keeps as must-keep, mean over pairs,
and the values left droppable with those of them the official versions keep:

| Model | Templates as they are (two samples) | 1: "what the reader needs to act" | 2: "a sentence with a phone number ... never belongs in this list" | 3: "every phone number ... is a fact", "always true" |
|---|---|---|---|---|
| Claude Haiku | 83 %; 67 and 88 left, 24 and 37 kept by the official versions | 89 % (+6); 27 left, 10 | 86 % (+3); 36, 13 | 92 % (+9*); 26, 10 |
| Mistral Small 4 | 82 %; 59 and 48, 21 and 14 | 81 % (0); 54, 20 | 73 % (-9*); 89, 36 | 84 % (+2); 35, 10 |
| gpt-oss-120b | 93 %; 18 and 26, 5 and 5 | 90 % (-3*); 33, 13 | 84 % (-9*); 51, 13 | 89 % (-4); 25, 13 |
| Apertus 70B | 88 %; 31 and 34, 6 and 8 | 88 % (0); 27, 14 | not run | not run |

1. Appended to the item on droppable passages: "Nie weglassen kann man, was die
   Leserin oder der Leser braucht, um zu handeln: Fristen, Beträge, Bedingungen,
   Öffnungszeiten und wie man die zuständige Stelle erreicht (Telefon, E-Mail,
   Adresse)."
2. Appended to the same item: "Ein Satz mit einer Telefonnummer, einer E-Mail-Adresse,
   einer Adresse, einer Öffnungszeit, einer Frist oder einem Betrag gehört nie in diese
   Liste, auch wenn er dir unwichtig scheint."
3. In the item on facts: "Jede Telefonnummer, jede E-Mail-Adresse, jede Adresse, jede
   Öffnungszeit, jede Frist und jeder Betrag ist eine eigene Tatsache.", and at
   `must_keep`: "Kontakte, Öffnungszeiten, Fristen und Beträge sind immer true."

Haiku follows the rule. Mistral Small 4 and gpt-oss do not, and the second wording made
both list more: with the kinds named in that item, gpt-oss gave "Kontakt- und
Bürozeitenangaben, bereits in den wichtigsten Kontakten enthalten" and "Postadresse,
nicht nötig für Leichte Sprache" as reasons, and the share of sentences it listed as
droppable rose from 22 to 28 %. Two samples of the unchanged templates already differ by
3 to 21 values. A rule that has to hold for every model is not a sentence of a prompt.

## The write prompt

Four variants of the German write prompt, first drafts (one Write call) on the same fact
sheets. Hard facts kept, and for the last column the Amstad readability:

| Model (pairs) | Templates as they are (two samples) | keep | plan | exact | struct | words: readability |
|---|---|---|---|---|---|---|
| gpt-oss-120b (30) | 79 % (78, 80) | 86 % (+7*) | 89 % (+10*) | 83 % (+5*) | 78 % (-1) | 44.5 to 44.7 |
| Mistral Small 4 (30) | 82 % (80, 84) | 87 % (+5*) | 84 % (+2) | 81 % (-1) | 82 % (0) | 53.8 to 54.5 |
| Claude Haiku (30) | 82 % (80, 83) | 84 % (+3*) | 79 % (-3) | 82 % (0) | 79 % (-3) | 57.0 to 56.7 |
| Apertus 70B (30) | 70 % (73, 67) | 74 % (+5) | 63 % (-7) | not run | not run | not run |
| Apertus 8B (10 dev pairs) | 70 % (66, 73) | 64 % (-6) | 62 % (-8) | not run | not run | not run |

- **keep**: "Das gilt für jede einzelne: auch für jede Telefonnummer, jede Adresse, jede
  Öffnungszeit und jeden Betrag aus einer Liste oder Tabelle." after the must-keep
  sentence, and at the omissions "Eine Tatsache mit "must_keep" lässt du nie weg, auch
  wenn sie dir unwichtig scheint: Darüber entscheidet später ein Mensch."
- **plan**: keep, and the plan as a field of the answer before the blocks: every
  question of the reader with the ids of the facts that go under it, every must-keep
  fact under exactly one.
- **exact**: the fact sheet in the write prompt names the written form of each value
  (`| Wert: 2026-03-31; schreibe: 31. März 2026`), as the repair request does.
- **struct**: the same words as a system and a user message, the style guide, the
  examples and the fact sheet in tags.
- **words**: one more line of the style guide, "Nimm das kürzere Wort, wenn es das
  Gleiche sagt: Hilfe statt Unterstützung, helfen statt unterstützen, am Telefon statt
  telefonisch, brauchen statt benötigen, Auskunft statt Informationen, fragen statt sich
  erkundigen."

The words arm, which has nothing to do with facts, kept 3 to 5 points more of them on
Mistral Small 4 and Haiku (a star on both): a difference of that size is within what any
change of the prompt does. Above it stand keep and plan on gpt-oss; plan helps gpt-oss,
does nothing for Mistral Small 4 and Haiku and costs the Apertus 70B 7 points (interval
-14 to +1); the Apertus 8B's intervals on 10 pairs span 40 points. The short-word hint
moves no model's readability, and the form of the prompt (struct) moves nothing.

End to end (the full pipeline, both arms fresh), the first-draft gains are gone:

| Model, variant (pairs) | Hard facts kept, templates as they are | variant | Must-keep found | Repair rounds | Tokens / page |
|---|---|---|---|---|---|
| gpt-oss-120b, plan (30) | 95 % | 95 % | 100 and 100 % | 1.8 and 1.9 | 22,283 and 23,079 |
| Mistral Small 4, keep (20 eval) | 90 % | 89 % | 100 and 100 % | 1.6 and 1.6 | 29,214 and 28,573 |
| Claude Haiku, Understand wording 1 and keep (30) | 88 % | 92 % (+5, -1 to +11) | 100 and 100 % | 1.6 and 1.6 | 51,933 and 50,821 |

The first drafts of these arms kept 82 and 86 % (gpt-oss) and 83 and 85 % (Mistral
Small 4): the rounds bring every arm to the same end, in the same number of rounds,
since they run while the judge finds something. Haiku's 5 points come from its fact
sheets, on the dev pages (82 to 94 %; eval 90 to 91 %), where its Understand had left
35 to 40 % of the hard values droppable.

## The judge

With the judge out of the loop (the rounds on the rule findings alone; the final draft
judged once afterwards by the same judge, for the comparison):

| Model (pairs) | Hard facts kept | Must-keep found | Errors / 100 blocks | Warnings / 100 blocks | Unsupported / 100 blocks (the judge on the final draft) | Facts the judge calls missing | Model calls | Tokens / page | USD / page | Seconds / page |
|---|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b, loop (30) | 95 % | 100 % | 0.9 | 37.7 | 1.3 | 10 % | 9.8 | 22,283 | 0.0067 | 15.0 |
| gpt-oss-120b, judge off | 95 % | 100 % | 0.4 | 27.2* | 5.6* | 15 % | 5.5* | 11,950* | 0.0033* | 5.8* |
| Claude Haiku, loop (20 eval) | 90 % | 100 % | 1.0 | 27.0 | 8.3 | 14 % | 9.9 | 51,798 | 0.0094 | 56.5 |
| Claude Haiku, judge off | 90 % | 100 % | 0.3* | 19.6* | 10.9* | 20 %* | 5.7* | 24,064* | 0.0039* | 7.7* |

The facts do not depend on the judge: code checks them. The loop costs half of the
price and more of the time, and its repairs add rule findings. What it buys is the
judge's own count on the final draft: gpt-oss's judge flags little and the loop resolves
most of it (5.6 to 1.3 unsupported blocks per 100), Haiku's flags much and the loop
resolves a quarter (10.9 to 8.3).

A sentence in the judge prompt changes how much a judge flags, not what: with "Ein
echtes Problem ist eines, das der Leserin oder dem Leser etwas Falsches sagt oder sie
oder ihn falsch handeln lässt. Was nur schöner oder noch einfacher sein könnte, meldest
du nicht." Haiku's semantic findings on 20 stored first drafts fell from 195 to 115 and
its unsupported blocks stayed (91 and 88); Sonnet shares 15 % of the semantic findings
before and after.

**The role as built** (`judge_role = "report"`: the rounds on the rule findings, then
one report on the final draft; `leichtfacile eval run --judge-role report`, Claude
Haiku, the 30 pairs, against the loop of the same day, with the contact rule below on
both sides):

| Measure | Loop | Report | Difference (90 % interval) |
|---|---|---|---|
| Hard facts kept | 91 % | 91 % | +1 (0 to +2) |
| Reference facts kept | 92 % | 93 % | +1 (0 to +3) |
| Must-keep found | 98 % | 99 % | +1 (0 to +2) |
| Errors / 100 blocks | 1.1 | 0.7 | -0.4 (-1.1 to +0.4) |
| Warnings / 100 blocks | 29.3 | 24.8 | -4.5* (-8.1 to -1.2) |
| Words | 384 | 350 | -33* (-48 to -18) |
| Unsupported / 100 blocks (the judge on the final draft) | 9.2 | 14.7 | +5.5* (+3.2 to +7.9) |
| Facts the judge calls missing | 13 % | 17 % | +4* (+1 to +8) |
| Model calls | 10.7 | 7.1 | -3.5* (-4.0 to -3.0) |
| Tokens / page | 52,677 | 29,708 | -22,968* |
| USD / page | 0.0096 | 0.0051 | -0.0045* |
| Seconds / page | 49.1 | 9.0 | -40.0* |

**The judge's report against blind labels.** `eval sample` drew 30 fact verdicts and 30
blocks from the final drafts of the report run: ten facts for each verdict, 15 blocks
that the judge lists as unsupported and 15 that it passes, from 18 and 19 of the 30
pages. An AI assistant (Claude, in a session of its own that saw the sheets and never
the key) labelled them, and `eval kappa` scored the sheets:

| Items | Labelled | Agreement | Cohen's κ | The judge's verdicts and their labels |
|---|---|---|---|---|
| Blocks: supported or unsupported | 30 | 63 % | 0.27 | 15 listed: 4 unsupported, 11 supported; 15 passed: 15 supported |
| Facts: present, missing or distorted | 30 | 67 % | 0.50 | 10 missing: 9 missing, 1 present; 10 present: 9 present, 1 distorted; 10 distorted: 2 distorted, 8 present |
| Facts: present or not | 30 | 67 % | 0.38 | |

- **What Haiku's judge calls missing is missing, and what it passes is there.** Its
  other two verdicts mostly are not what they say. 8 of the 10 facts it calls distorted
  the labels find in the draft, in other or fewer words ("dunkel" for "lichtgeschützt",
  a condition without "deutlich günstiger"), and 11 of the 15 listed blocks are covered
  by the source. The 14.7 unsupported blocks per 100 of the report run count the
  judge's doubts; at the labels' rate about 4 per 100 are statements without a source
  (4 of 15: 10 to 51 % at the sample's 90 % interval). Three of the four confirmed
  blocks the labeller called hard to decide, a changed modality each ("können" as an
  instruction, "dürfen" as a certainty, an aim as a fact).
- **The judge lists what it looked at.** In 4 of those 11 blocks its own note clears
  the block ("Entspricht s0070.", "daher kein Problem", "aber gedeckt", "eine
  Auslassung, keine Falschaussage"), and code counts every entry of the list. Of the 232
  entries in the final reports of the report run, 64 (28 %) are of this kind: read one
  by one, found by their phrases, so the share is a floor. The same German phrases in
  the unsupported lists of other final reports, unread: Haiku in the loop of the day
  56 of 154 and with the judge off 37 of 131, Haiku on 25 October 18 of 101, Sonnet 6
  of 48, GPT-5.6-luna 3 of 43, Qwen 3 of 41, and none or one for Opus (3 entries),
  GPT-5.4-nano (33), gpt-oss-120b (22), Mistral Small 4 (107) and the Apertus 70B (26 on
  Public AI, 71 on CSCS). In the loop every such entry is a blocking finding, and the
  rounds go on while one is left. The quote of an entry does not tell them apart: Haiku
  quotes the whole block either way.
- **Where the four confirmed blocks come from.** Two stood in the first draft: "können
  Sie ... kommen" as "gehen Sie" (the shelters), and "dürfen ... beantwortet werden" as
  a certainty (political rights; the rounds reworded it). Two were written by a round
  on a passive finding (GRAM-01). A repair round turned "sollen besser berücksichtigt
  werden" into "Das Amt berücksichtigt die Bedürfnisse ... besser.": an office the
  source does not name, and an aim as a fact. A polish round replaced "Sie sollen nicht
  schlechter behandelt werden." by "Das Amt zahlt das Geld." and "Sie bekommen das
  Geld.": the two example sentences of the hint that the finding carries, word for word
  (`rules/de.py`, `PASSIVE_RECIPE`: "Wer tut es? Nenne die Person oder das Amt: Das Amt
  zahlt das Geld. Oder: Sie bekommen das Geld.").
- **The hints' example sentences in drafts.** A rule finding takes a hint into the
  repair request (the clause recipes of LEN-02, the passive hint of GRAM-01), each with
  example sentences. In the 2,144 P2 jobs of all stored runs no first draft has one of
  these sentences where the source lacks it, and 24 final drafts do; runs that share
  cached answers count more than once. "Verdienen Sie wenig?" and "Das ist wichtig."
  stand in 8 of them each, "Das Amt zahlt das Geld." in 5, "Dann bekommen Sie Geld.",
  "Schicken Sie das Formular." and "Lei guadagna poco?" in 2 each, two more sentences
  in 1. Some fit their page: a page on premium reductions may ask "Verdienen Sie
  wenig?", and "Das ist wichtig." is a stock phrase. These do not: "Verdienen Sie
  wenig? Dann bekommen Sie Geld." on the page about voting, in the report run (a repair
  round wrote it) and in the loop of the same day (the polish round); "Das Amt zahlt
  das Geld." on the page of the racism counselling, in the end-to-end run of the
  Understand wording above (a loop) and with the judge off, and "Das Amt zahlt Ihnen
  das Geld." there in the report run; the two sentences on the disability page above.
  The judge names them in its report (not in the run with the judge off, whose report
  of that page holds three fact verdicts and nothing else), and in both roles they stay
  in the final version: the loop does not keep them out. Not built: a check in code
  that takes a repaired sentence which is a hint's example word for word, in a document
  without it, for example content, the way `pipeline/checks.py` takes the examples'
  topics; or hints without whole example sentences, which is a change of a prompt and
  has to be measured per model.
- **For the choice of the role.** On Haiku the report costs half and keeps the same
  facts. Its judge's list is a list of doubts in either role, a quarter of them cleared
  by their own note and a quarter confirmed by the labels, and part of what the labels
  confirm was written by rounds that run in every role. Not measured: the loop's final
  drafts were not labelled, so whether the loop leaves fewer statements without a source
  than the report is open, and 15 passed blocks do not show what the judge misses (none
  of 15: up to 18 % at the same interval).

## What was built

- **Reference facts kept**, a column of `eval report` and `eval compare` next to the
  hard facts kept: of the source's hard values that the official version keeps, the
  share the text keeps. In German the runs stand at 89 to 100 % (hard facts kept: 85 to
  97 %), each 2 to 6 points above its hard facts kept
  ([model-comparison.md](../model-comparison.md)). The stored rows got it with `eval
  rescore --in-place --only`, their other numbers untouched.
- **Contact values are kept** (`pipeline/facts.py`, `_keep_contacts`): a phone number,
  an e-mail address and a postal address are must-keep whatever the model marked, and
  their sentences leave the omit candidates. On the stored fact sheets of the 23 eval
  pairs the rule changes 1 to 7 pairs a run and makes 1 to 12 facts must-keep (Mistral
  Small 4 without thinking 12, Sonnet 5, the Apertus 8B, nano and luna 4, Haiku and Opus
  3). On the fact sheets of this day it reaches further on the dev pages: Haiku had left
  33 contact values droppable in 7 of the 30 pairs, 20 of them on one page of
  counselling centres, the Apertus 8B 12 and the 70B 6 on one page of shelters, Mistral
  Small 4 10, gpt-oss 1. What it does to the drafts is measured below ("The contact
  rule, measured"): a gain on Haiku, none on the Apertus models, and a change to the
  order in which the rounds ask for missing facts.
- **The judge's role** is a setting of the model that judges (`judge_role`: loop,
  report, off; architecture.md §4.5), the loop by default, and no shipped preset
  changed.

Not built: prompts of a model's own, and switches in the templates for a model. Haiku
with the third Understand wording is the one case that would use one; the contact rule
covers the part of it that the official versions back.

## The contact rule, measured

**Claude Haiku, the judge in the loop, the 7 pages whose fact sheet the rule changes.**
Two samples of each arm on the same fact sheets, fresh from the Write call on (the
second one the evening of the same day, both arms on the code as built, the rule
switched off for one of them):

| Measure | Without the rule | With the rule | Difference (90 % interval over the pages) |
|---|---|---|---|
| Hard facts kept | 70 % | 85 % | +15* (+7 to +24) |
| Reference facts kept (6 pages) | 76 % | 90 % | +14* (+5 to +24) |
| Must-keep found | 100 % | 93 % | -7 (-21 to 0) |
| Errors / 100 blocks | 0.6 | 0.8 | +0.3 (-0.5 to +1.0) |
| Warnings / 100 blocks | 27.5 | 28.9 | +1.4 (-2.7 to +5.6) |
| Readability | 57.1 | 55.2 | -1.9* (-3.3 to -0.6) |
| Words | 450 | 520 | +70* (+23 to +117) |
| Model calls | 11.4 | 13.5 | +2.1* (+0.6 to +3.6) |
| USD / page | 0.0087 | 0.0098 | +0.0010 (-0.0001 to +0.0023) |
| Seconds / page | 28.9 | 33.6 | +4.7* (+1.2 to +8.6) |

The samples one by one: 71 to 85 % and 70 to 86 %. Every page is better with the rule,
the algae page most (4 to 11 of its 16 values) and the page of counselling centres (12
and 13 to 19 of 37); two samples of one arm differ by one value on at most two pages,
and no page loses a value of another kind. Over all 30 pages hard facts kept go from 88
to 91 % (the first sample). On the counselling page 18 of the 37 values stay missing,
every one flagged for the reviewer: a repair round asks for 5 missing facts and the
recover round for 10 (`pipeline.recover_facts`), limits set for a small model.

**Where the rule hurt: the order of the missing facts.** The German pension page
(`drv-contribution-refund-de`) has 45 hard values, 34 of them the addresses, phone
numbers and e-mail addresses of sixteen regional offices; the official version keeps
three periods and no contact value. The Apertus 70B writing and judging on Public AI,
three samples of each arm on one fact sheet:

| | Without the rule | With the rule | With the rule, values asked for before contacts |
|---|---|---|---|
| Must-keep facts, of 59 | 31 | 58 | 58 |
| Hard values kept, of 45 | 16, 15, 26 | 19, 18, 19 | 16, 27, 16 |
| Dates and periods kept, of 8 | 8, 7, 7 | 3, 2, 7 | 8, 8, 8 |
| Values the official version keeps, of 3 | 3, 3, 3 | 1, 1, 2 | 3, 3, 3 |
| Contact values kept, of 34 | 5, 5, 16 | 13, 13, 9 | 5, 16, 5 |
| Must-keep values missing in the final version | 2, 2, 2 | 24, 25, 25 | 27, 17, 27 |

With the rule, 33 to 35 contact facts and five dates and periods were missing after the
first draft. A round asked for missing facts by their kind, a contact before a fact of
the kind `other`, which is what code gives a date or a period it adds: every place of
the recover rounds and every place but one of the repair rounds went to a contact
value, and the periods the page is about were never asked for. Since this measurement a
value of no listed kind is asked for just before the contact values
(`rounds.missing_order`). With that order the three samples keep every date and period
again. On this page the rule then neither helps nor hurts the drafts of the Apertus 70B
(5, 16 and 5 contact values against 5, 5 and 16 without it), and it leaves the reviewer
17 to 27 values flagged as missing, all of them addresses, phone numbers and one e-mail
address of the regional offices, which the official version leaves out. Applied to the
stored Haiku rounds of the table above, the new order changes one request in each
sample: the passport page's first repair round would ask for one or two more values of
the kind `other` in place of contact values.

The official versions keep 58 % of the contact values of their sources (184 of 316 on
the 49 pairs that have any): 65 % on pages with one to three, 78 % with four to nine,
46 % on the nine pages with ten or more, from none of 34 (the pension page) to 12 of 14
(a page of emergency numbers).

The default preset (the Apertus 8B writing, the 70B judging) on the shelters page, with
and without the rule: the draft carries all 12 hard values both times; without the rule
none of them is a fact the draft is held to, with it all 12 are, at one repair round
and 7 calls instead of 5, 241 seconds instead of 178. For the other models the rule
changes few pages (1 of 30 for gpt-oss, 3 of 20 for Mistral Small 4, the shelters page
for both Apertus models) and no run shows what it does to them.

## Limits

- Swiss German only; French and Italian variants were not written. 30 pairs, one day,
  one or two samples an arm (three on the pension page).
- The contact rule's gain is measured on one model (Haiku). The changed order of the
  missing facts is measured on one page of one model, and its effect on Haiku's pages
  is read off the stored rounds, not run.
- The official versions say what human translators kept, not what a reader needs; a
  value they leave out can still matter.
- Each model judged its own drafts, and "unsupported" is that judge's count.
- The blind labels are an AI assistant's, not people's: one labeller, 30 facts and 30
  blocks of one run of one model. The loop's final drafts were not labelled.
- The first-draft comparison of the Apertus 8B has 10 pairs and intervals of 40
  points; the 8B's end-to-end runs and the Understand wordings on it were not run.
- The runs on Mistral Small 4 end to end cover the 20 eval pairs; the judge-off run on
  Haiku the 20 eval pairs, the report run all 30.
