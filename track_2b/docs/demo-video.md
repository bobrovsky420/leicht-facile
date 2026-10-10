# Demo video: script and storyboard

Status: initial draft, 6 October 2026; on 7 October 2026 the "only Apertus" scene
added and the BehiG scene dropped for it. On 8 October 2026 the owner chose concept A,
"Find the deadline", after mocks of both concepts; the first concept, "Can you read
this?", is kept in §5 for reference. On 10 October 2026 the final CSCS run gave case A of
decision D-M, so the evidence scene carries the final numbers (§2, §4); the prompt's
source stays on the end card (owner). Companion to [hard-texts.md](hard-texts.md) (hook
sentences, the number) and [use-cases.md](use-cases.md) (the letters that may not leave
the authority, and why that leaves Apertus).

Submission limit: at most 2 minutes. Target: 1:50.

Source of the mocks and of the final render: [video/](../../video/README.md) (Remotion
scenes, narration per version, voice, music and capture scripts; generated files are
not in git). The current draft is version C (§3), composition `DemoC`.

## 1. Concept: "Find the deadline"

The viewer takes a test instead of being told that official letters are hard: find the
deadline in a letter in five seconds, then in its easy-language version, where it is in
the first sentence. The video itself follows easy-language rules: short sentences, one
idea per shot, English captions burned in.

- Main language: English (narration, captions, the instruction). German stays on screen
  as the illustration: the letter, the draft, the app's content and the instruction's
  second line "Finden Sie die Frist." (owner, 8 October: German binds the video to
  Switzerland and Apertus). The test still works without German, since a date is
  recognizable in any language. French is not shown.
- Real material: the letter is the team-written example
  (`track_2b/data/examples/sources/praemienverbilligung-brief.txt`) and the easy-language text
  the first blocks of its real P2 draft (`track_2b/data/examples/jobs/`, before review), word for
  word and labelled as such. This replaces the illustrative DE-4 rewrite of the first
  concept, for which P2 gave no usable output (PLAN.md §11, 8 October).
- The deadline runs through the video: the test, the fact sheet's "By when?", the
  deadline fact and its code check, the draft sentence linked to its source sentence,
  the end card ("The deadline. In the first sentence.").
- Key message: the 1.25 million people must not be excluded from the letters that decide
  their money, deadlines and rights (spoken at 0:18-0:33, written on the end card).
  Same wording as in [hard-texts.md](hard-texts.md) §2, the README and the report.
- Evidence by case A of decision D-M (PLAN.md, WP13; the final run of 10 October 2026):
  same model, a strong one-shot prompt against our pipeline: a tenth of
  the rule errors (2.0 against 19.5 per 100 blocks), no invented value (0.0 against
  0.2), and every hard fact Leicht·Facile misses is listed for the writer, where the
  prompt loses 7 percent of them without a trace (code checks the values; a fact
  without a value rests on the judge). The scene does not name the prompt's source
  (owner, 10 October: next to a project we build on, that would sound arrogant);
  the end card carries the credit to Zurich (D-L).
- Second message: patient letters, child protection decisions and tax letters are
  under secrecy and may not go to a foreign cloud, and for them Apertus is the only
  model that fits (1:19-1:49). The argument and its sources are in
  [use-cases.md §2](use-cases.md#why-only-apertus); the README and report §3 say the
  same.
- Third message: Leicht·Facile does not replace the writers; it gives them a checked
  first draft (0:33-0:40), and the writer approves every sentence (end of the product
  scene).
- Narration: 231 words in the mock of 8 October, 1:52 in all at about 155 words per
  minute while speaking, with two silent countdowns. Every scene is timed to its
  narration.

## 2. Storyboard

| Time | Picture | Narration (English) |
|------|---------|---------------------|
| 0:00-0:12 | Dark screen. The example letter, German, full text, on a white page. On the right *"Find the deadline."*, below it *"Finden Sie die Frist."*, and a five-second countdown ring with soft ticks. Time's up: the page dims except *"bis spätestens 31. März 2027"*, marked in the third paragraph. | "Find the deadline. You have five seconds." (countdown) "Missed it? It was here, in the third paragraph." |
| 0:12-0:18 | The first blocks of the letter's real draft (German, labelled "Draft by Leicht·Facile, before review"), the same countdown. After about a second *"31. März 2027"* lights up in the first sentence; the ring stops, a chime: *"Found in 1 second"*. | "Now the easy-language version." (about a second) "There. In the first sentence." |
| 0:18-0:33 | The kitchen table in evening light (generated footage, or drawn as in the mock): **1.25 million** with "22% of adults aged 16-65" and the source "Swiss Federal Statistical Office, PIAAC 2022/23"; the letter's money, deadline and rights marked; the letter pushed away on "shut out"; a card *Slow expert work*. | "1.25 million adults in Switzerland struggle with reading. Letters like this decide their money, their deadlines, their rights. No one should be shut out. But easy-language versions are slow expert work." |
| 0:33-0:40 | Logo, *easy-language drafts of official texts*, *with Apertus, the Swiss open model*; then *The writers stay in charge* and *A checked first draft*. | "Leicht·Facile drafts them with Apertus, the Swiss open model. The writers get a checked first draft." |
| 0:40-1:09 | **Real screen recording**, sped up, of the same letter: pasted, level A2. The fact sheet's five questions, *By when?* ringed, then the deadline fact with its value 2027-03-31. The draft. The rule check with a millisecond timer (47 ms on draft v1 of this letter). The facts tab with the deadline present. Judge and repair: the version pills from v1 (10 blocking) to the final version (2). The deadline sentence selected, its source sentence lit; approve with the keys; reader view and export. | "Apertus reads the letter the way you just tried to, and writes down every answer: what to do, by when, what it costs, whom to ask. Then it writes the draft. Code checks every date, amount and phone number, and 45 easy-language rules, in milliseconds. A larger Apertus model judges the meaning; only flagged sentences are repaired. Every sentence links to its source. The writer approves each one." |
| 1:09-1:19 | *Same model. A strong one-shot prompt against our pipeline.* Left: *A strong one-shot prompt, asked to keep every fact*, the counter runs to **19.5** *rule errors per 100 blocks; 7 % of the hard facts lost, and nothing tells the writer* (report §5, final run of 10 October). Right: Leicht·Facile, *2.0 rule errors per 100 blocks* and *lists every hard fact it misses* (one line each), with the real facts tab of the example job's draft v2, *15 of 16 facts present*, the missing fact (f07, 1. Januar 2027) first; the final draft v6 carries all 16, so it has none to show, and a later round puts f07 back (10 October). Footnote: Apertus 1.5 8B on CSCS, one-shot prompt asked to keep every fact, 20 German test pairs, final run of 10 October 2026, hard facts defined (shortened in C30 to keep its margins). The prompt's source is not named on the card or in the voice (owner, 10 October); the end card credits it. | "Same model. A strong one-shot prompt against our pipeline: a tenth of the rule errors. And Leicht·Facile lists every hard fact it misses." (20 words, as the case B sentence of 9 October; "one-shot" is the owner's word, 10 October; rendered 10 October, night, as C30) |
| 1:19-1:49 | The "only Apertus" scene of §5, unchanged: the envelopes, the four tiles struck one per sentence, Apertus, the icons, Ticino, CSCS. | As in §5, 1:29-1:57. |
| 1:49-1:52 | End card: *"The deadline. In the first sentence."* above *"No one left out."*, team name (Röstigraben Bridgers), repo URL, "Voice and imagery AI-generated", the credit to Zurich's simply-simplify-language (as in version C). | (music only) |

## 3. Production notes

- **Record the product, do not generate it.** The UI scenes (0:40-1:09) are real
  recordings of the tool, and the test texts (0:00-0:18) are the example letter and its
  real draft, word for word. Generated screens of the app would misrepresent the
  prototype.
- **No readable text in generated footage.** Video generators garble writing. Generate
  the kitchen-table letter blank and add its text in the edit. Use a made-up sender such
  as "Gemeinde Musterwil", never a real authority's letterhead or logo. The same for the
  envelopes at 1:19: blank in the footage, labelled in the edit.
- **Categories, not competitors.** The struck-through tiles name kinds of models, never
  a product, a company or a logo. Every claim in that scene has its source in
  [use-cases.md §2](use-cases.md#why-only-apertus); "only option" is meant for letters
  under secrecy, not for public web pages, and the scene says so.
- **The countdowns:** five seconds for the letter, with soft ticks and a low tone when
  the time is up; the second test stops as soon as the date lights up, with a light
  chime. Keep both short.
- **Pronunciation:** set a text-to-speech alias for "Leicht·Facile" and test it first:
  "Leicht" in High German, with the ich-sound (IPA `ˈlaɪçt`, not "lysht"), then French
  "fa-SEEL" (owner, 8 October). The same for "Apertus" and "CSCS" (spelled out C-S-C-S).
- **Voice:** one calm, warm voice, a bit slower than normal (about 140 to 155 words
  per minute), with pauses after the questions. Quiet music.
- **Captions:** English, burned in. German only in the picture, not in the captions.

### Variant B for 0:00-0:18: "One sentence, step by step" (mocked 8 October)

The owner found the five-second test unfair: a full letter is too much text to scan,
whatever one's reading skill. Variant B shows the simplification itself on one sentence,
the one the deadline comes from (s0007 of the example letter), with real data only. The
rest of the video stays as in §2 (the app scene's first line becomes "Apertus reads the
whole letter like this, …"); 251 words, 1:54.

| Time | Picture | Narration (English) |
|------|---------|---------------------|
| 0:00-0:03 | *"Das Antragsformular ist vollständig ausgefüllt und unterzeichnet bis spätestens 31. März 2027 bei der Sozialversicherungsstelle einzureichen."* types itself, labelled "Original". | "One sentence from an official letter." |
| 0:03-0:07 | What `leichtfacile check` finds, marked on the words: LEN-01 (16 words, at most 12 for A2) and GRAM-01 (passive "ist … einzureichen"), LEN-02 (two clauses), LEX-01 (Antragsformular, Sozialversicherungsstelle): 2 errors, 3 warnings. | "Sixteen words. Nobody acts. The verb comes last." |
| 0:07-0:13 | Apertus: the facts that must survive, marked in the sentence and set as chips: f01 deadline 2027-03-31, f06 procedure. | "Apertus first takes out what must survive: the deadline, and what you must do." |
| 0:13-0:17 | The sentence moves up; the real draft's two sentences (b002, b003) appear one by one, each with the facts the job records for it. | "Then it writes short sentences. Who does what. One thing each." |
| 0:17-0:21 | The check again: 0 errors (before: 2); the date lights up in the first sentence, the deadline chip gets a tick. | "Code checks that the date is still there, exactly." |

Since the example bundles of 10 October (draft v6) the sentence becomes *"Sie reichen den
Antrag bis zum 31. März 2027 ein."* and *"Der Antrag muss vollständig ausgefüllt und
unterzeichnet sein."*: 0 errors, 2 warnings (LEX-07, office words). The draft of 9 October
had three sentences, the second with "bei" for "an die"; the new one no longer names the
Sozialversicherungsstelle as the place to send the form (the job records no fact for it;
the draft names the office later, as a contact).

### Version C: "Can you read this?" opening with variant B's composition (mocked 8 October)

The owner's combination: the split-screen opening of §5 for the first seconds, then
variant B's step by step and the rest of §2. The stakes play on the kitchen table with
the letter, drawn in code for now; the owner decides later whether generated footage
replaces it. The app scene is shorter, since the step by step already shows facts and
checks. On 9 October the opening sentence came back before the end card, now in easy
language, so that the opening question gets its answer (owner); the easy text there is
the team's placeholder until the real output is in (§4). The same day the Ticino
sentence left the "only Apertus" scene, and its time went to that easy text (owner),
which now ends with the answer "Now you can." (owner). 267 words, 1:58 (voice speed 0.90; the silent leads and pauses trimmed by 0.1 to
0.6 s; the evidence scene held 1.6 s longer and "in its default mode" no longer spoken on
9 October; "1.25 million" spoken as "one and a quarter million" on 10 October
(owner: the voice paused inside "one point two five"), 117.6 s in all; the evidence
scene for case A on 10 October, night: 269 words, 119.4 s, rendered as
`leicht-facile-demo-C30.mp4`; C27 the same night still named the prompt's source, C28
said "single prompt", C29's footnote ran edge to edge).

| Time | Picture | Narration (English) |
|------|---------|---------------------|
| 0:00-0:07 | The split screen of §5: DE-4 and FR-4 type themselves with their questions, one question per line, each line as it is spoken (owner, 8 October); the negations light up. | "Can you read this? Did you understand it right away?" |
| 0:07-0:18 | The kitchen table with the letter (drawn, or generated footage later); **1.25 million** with 22% and the source (Swiss Federal Statistical Office, PIAAC 2022/23); then the letter's money, deadline and rights marked, each labelled. | "If you hesitated, you are not alone. 1.25 million adults in Switzerland struggle with reading. Letters like these decide their money, their deadlines, their rights." |
| 0:18-0:31 | A bridge into easy language (owner, 8 October: the viewer must first learn that it exists): a card *Easy language*, with *Leichte Sprache* and *Langage facile* as the illustration and three of its rules, *Short sentences*, *Everyday words*, *One idea at a time*; under the rules *Equal access by Swiss law: BehiG | LHand* (owner, 9 October; on screen only, not spoken: art. 14 para. 1 BehiG, SR 151.3, names only speech, hearing and visual disabilities, and the revision before Parliament since the message of 20 December 2024 would add communication that people with learning disabilities understand, so the card does not say that the law requires easy language); below it the card *Slow expert work*; then the logo, *with Apertus, the Swiss open model*, *The writers stay in charge*, *A checked first draft*. | "For them, there is easy language. But easy-language versions are slow expert work. Leicht·Facile drafts them with Apertus, the Swiss open model, and gives the writers a checked first draft." |
| 0:31-0:54 | Variant B's step by step on the real sentence s0007; after the new sentences the label "Mediopunkt: long words in readable parts, as later in this draft" (owner, 8 October); the Mediopunkte in the draft light up with it, but draft v6 has none in these two sentences, so two example words above the label show it, *Antrags·formular* and *Sozial·versicherungs·stelle*, on one line (owner, 10 October). | "Here is how, on one sentence from a real letter." Then as in variant B, with "A middle dot splits long words into easier parts." before the check. |
| 0:54-1:07 | Real app, short: the letter pasted, the pipeline, judge and repair (the version pills from 4 blocking in v1 to 0 in the final v6; v7, a later round with 4, is left at the edge), the deadline sentence linked to its source, approval, reader view and export. | "The same for the whole letter. A larger Apertus model judges the meaning; only flagged sentences are repaired. Every sentence links to its source, and the writer approves each one." |
| 1:07-1:16 | The evidence scene of §2, held 2 s after its last sentence so the facts panel can be read (owner, 9 October). | As in §2. |
| 1:16-1:49 | The "only Apertus" scene of §5, opened by a bridge (owner, 8 October): the title *Easy language matters most in the most personal letters.* over the table, then the envelopes in the order they are named, the KESB decision first. | "Easy language matters most in the most personal letters. A child protection decision for a person with a learning disability. A letter from the hospital. A tax assessment. Under secrecy, they may not go to a foreign cloud." Then as in §5, without the Ticino sentence and its caption (owner, 9 October); the envelopes stay at the top for "For these letters, it is the only option." |
| 1:49-1:55 | The split screen of the opening again (owner, 9 October): DE-4 and FR-4 small and dimmed at the top, their negations still marked; below each its easy-language version line by line, labelled *Leichte Sprache* and *Langage facile*; under it *"Können Sie es jetzt lesen?"* and *"Pouvez-vous le lire maintenant ?"* as it is spoken. The team's illustrative rewrite, labelled so on screen (10 October: the frozen pipeline's real output for the two sentences inside a short letter was not usable, §4): *"Das ist wichtig: / Melden Sie Ihre Kosten rechtzeitig. / Sonst bekommen Sie kein Geld zurück."* and *"C'est important : / Annoncez vos frais à temps. / Sinon, vous ne recevez pas d'argent."* (both pass `leichtfacile check` at A2 without errors or warnings). On the answer a green tick after each question (owner, 9 October: spoken, not a title; the question is already on screen twice). | "Can you read it now?" (1.2 s to try) "Now you can." |
| 1:55-1:58 | End card: *"No one left out."*, below it *"Every person. Every fact."* (both readings of the line: the people, and the facts of the evidence scene), *Team Röstigraben Bridgers · Hack Apertus 2026* ("Team" added by the owner, 9 October), repo (owner, 8 October); in the small footer, its only line since 10 October (owner), *Inspired by simply-simplify-language, Team Data, Office for Statistics and Data, Canton of Zurich.* (owner, 10 October; the institution, no person named, its name as in their licence (THIRD_PARTY_NOTICES.md) without the department; the wording is final with D-L). | (music only) |

## 4. Before recording

- [x] The easy text of DE-4 and FR-4 at 1:49 (version C) was the team's placeholder:
      replace it with the tool's real output after the prompt freeze (declared 10 October),
      in `video/src/scenes/Again.tsx`, and drop the placeholder note. Run the sentences
      inside a short letter: alone, DE-4 came back wrapped in letter headings and
      without its consequence (PLAN.md §11, 8 October). *Run 10 October, night, each
      inside a short team-written letter (`video/letters/`, the outputs in
      `video/letters/p2-2026-10-10/`, frozen pipeline, CSCS): the German final version
      renders DE-4 as "Das Amt bezahlt keine Kosten, die nicht rechtzeitig verlangen
      werden." (a grammar slip; version 3 had "Das Amt vergütet keine Kosten, die nicht
      fristgerecht geltend gemacht werden.", correct but no easier) and repeats it; the
      French draft keeps the deadline and drops the consequence of FR-4 in every version.
      So the team's rewrite stays, labelled "Illustrative rewrite by the team, not tool
      output", and the note in `Again.tsx` says why; the owner decides whether that
      stands or the scene changes.*
- [x] CSCS runs done (final run, 10 October): case A of D-M, so the evidence scene at
      1:09 carries the final numbers (§2), without naming the prompt's source (owner;
      the end card credits it). Narration
      C (`ev-a`, `ev-b`), the titles, the counter and the footnote in
      `video/src/scenes/Evidence.tsx` (the right card gets a line for 2.0 rule errors,
      the facts panel is narrower to make room) and the bars in `Compare.tsx` (the
      earlier concept) updated the same day and rendered the same night (C27 with
      Zurich named, then C28 to C30 with the abstract wording at the owner's request; about
      119 s): the cards fit (stills at 70 and 73 s); a first voice with "the Canton of"
      in the line had made the mix 120.4 s, over the limit. The real
      example job for the screen recording is done: the bundles rebuilt on 10 October,
      the app frames retaken from them the same day.
- [ ] The rebuilt job's fact sheet answers "What does it cost?" with the junk word
      *text* (`core.cost` in the bundle, no source sentence), visible in the app scene's
      job page (0:54-0:57): rebuild the example once Understand drops such answers, or
      move the camera off it.
- [x] The number re-checked against the Swiss Federal Statistical Office's PIAAC
      report (9 October: 22 percent, 1.25 million people aged 16 to 65, with low
      literacy; the narration says "1.25 million adults ... struggle with reading", the
      screen names the office; [hard-texts.md](hard-texts.md) §2).
- [x] Voice regenerated and the length re-checked after the narration changes of
      9 October (`sk-b` "1.25 million adults ...", `ev-b` "lists every one it misses", two
      words more) and the evidence scene's titles in `video/src/scenes/Evidence.tsx`
      (rebuilt 9 October: version C 117.8 s, mock C14; the speech check reads the new
      sentence word for word).
- [ ] The "only Apertus" scene (1:19-1:49) re-checked against its sources in
      [use-cases.md §2](use-cases.md#why-only-apertus): the privatim resolution, the
      Apertus v1.5 model card (open training data, languages) and the CSCS article on
      the Ticino service.
- [x] Product scene: the premium-reduction letter, since the test and the screen
      recording use the same letter (concept A, 8 October).
- [x] Before/after: replaced by the second test, which shows the example job's real
      draft (concept A, 8 October).
- [x] The draft's fourth sentence, *"Sie mitschicken eine Kopie der Steuer·veranlagung
      …"*, was ungrammatical: the rebuilt job of 10 October writes *"Sie legen eine
      Kopie der Steuer·veranlagung und der Kranken·versicherungs·police bei."*
- [x] The "MOCK-UP" label on every frame and the mock-up note on the end card removed
      (owner, 10 October); the footer keeps only the Zurich credit. The voice stays
      Kokoro `af_heart` (owner, 10 October, after a mock with `af_bella`).
- [ ] Recording finished by 14 October; two days for edits before the deadline
      (16 October 2026, 12:00 CEST).

## 5. Earlier concept: "Can you read this?" (6 to 8 October)

Start with the viewer's own moment of not understanding, then show the tool solving
that same sentence. Mocked on 8 October in three versions; replaced by concept A, whose
opening needs no illustrative rewrite and works without German. Its "only Apertus"
scene (1:29-1:57) is reused there unchanged.

- Main language: English (narration, captions, titles). German and French appear on
  screen only as illustrations.
- Key message spoken at 0:12-0:32 and written on the end card; second message at
  1:29-1:57; third message at 0:32-0:49 and at the end of the product scene.
- Narration: about 250 words planned; the mock counted 267 with its evaluation
  sentence and fit in 1:59 only at about 165 words per minute.

| Time | Picture | Narration (English) |
|------|---------|---------------------|
| 0:00-0:12 | Black screen, split in two: DE-4 on the left (*"Es ist nicht unwesentlich, dass Kosten, die nicht fristgerecht geltend gemacht werden, nicht vergütet werden können."*) and FR-4 on the right type themselves side by side and stay for the whole scene. Under each its question: *"Können Sie das lesen? Haben Sie es sofort verstanden?"* and *"Pouvez-vous lire ceci ? L'avez-vous compris tout de suite ?"* On "do I get my money back, or not?" the negations in both light up. (Split screen instead of a quick cut to FR-4: the owner's decision of 8 October, after the mock showed FR-4 too briefly.) | "Can you read this? Did you understand it right away? Only one question matters here: do I get my money back, or not?" |
| 0:12-0:32 | AI-generated footage: hands holding an official letter at a kitchen table, evening light. The number fades in: **1.25 million**, with "22% of adults aged 16-65" and the source "Swiss Federal Statistical Office, PIAAC 2022/23" small underneath. On "No one should be shut out", the letter is pushed back across the table, unread. | "If you hesitated, you are not alone. 1.25 million adults in Switzerland struggle with reading. Letters like this decide their money, their deadlines, their rights. No one should be shut out of them. But easy-language versions are slow expert work, and a chatbot checks nothing." |
| 0:32-0:49 | Logo, the Apertus name, and the tagline set as text. | "Leicht·Facile drafts easy-language versions of official texts with Apertus, the Swiss open model. It does not replace the writers. It gives them a checked first draft. Apertus does what needs language understanding. Plain code checks everything that can be counted." |
| 0:49-1:19 | **Real screen recording**, sped up 2-4x, with zooms on key spots: New draft, paste a letter, choose A2. The running job: the stages tick off, the fact sheet appears with the values as chips. Rule check with a millisecond timer. Judge findings turning from red to green (the version pills: blocking problems per version). The review workbench: select a block and its source sentences light up; approve with the keys. Reader view, then export. | "Apertus turns a letter into a fact sheet: every deadline, amount and phone number. Then it writes a draft. Every sentence links back to its source; every omission is explained. Code checks 45 Swiss easy-language rules, and every date and amount. A larger Apertus model judges the meaning. Only flagged sentences are repaired. The writer approves every block, with a full audit trail." |
| 1:19-1:29 | DE-4 source on the left, **the tool's real A2 output** on the right. Then one evaluation number, P2 against P0. | "The same sentence, now. Short. Clear. The answer comes first. [One sentence with the evaluation result against a single prompt.]" |
| 1:29-1:57 | The kitchen table again. Four window envelopes slide in, face up as Swiss authorities send them (address window bottom right, blank address lines); the edit labels each top left in German and adds a small lock: *Patientenbrief*, *KESB-Entscheid*, *Strafbefehl*, *Steuerveranlagung* (German labels and the window: owner, 8 October). Four tiles follow, their text set in the edit: *Foreign cloud*, *Closed model*, *Open weights, secret training data*, *Open data, built abroad*, each struck through on its own sentence, the part that rules it out turning red (*secret training data*, *built abroad*); only when all four are struck, on "Apertus", a fifth, *Apertus: open data, built in Switzerland, in-house*, with a tick. (The fourth tile has its own sentence since 8 October: in the mock it was struck while Apertus was named, and "open data" read as a point against Apertus.) Under it the three icons on-premise, air-gapped, Swiss cloud; on "Ticino" a caption *Canton of Ticino: Apertus in-house for sensitive documents* (text only, no coat of arms); at the end a small label "This demo: CSCS, Lugano" under Swiss cloud, and since 10 October "Tested: one NVIDIA L4 GPU" under on-premise (owner; the `local-llm` run on an AWS L4 in Zurich, track_2b/eval/hardware/aws-l4-2026-10-10/; not "air-gapped", that machine had network). | "Patient letters, child protection decisions, tax letters: under secrecy, they may not go to a foreign cloud. Closed models stay with their makers. Most open models keep their training data closed. Most fully open ones are built abroad. Apertus is open down to its data, built and trained in Switzerland, and runs in-house. Ticino already runs it for sensitive documents. For these letters, it is the only option." |
| 1:57-2:00 | End card: *"No one left out."*, team name (Röstigraben Bridgers), repo URL, "Voice and imagery AI-generated", the credit to Zurich's simply-simplify-language (as in version C). | (music only) |
