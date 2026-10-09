# Demo video: script and storyboard

Status: initial draft, 6 October 2026; on 7 October 2026 the "only Apertus" scene
added and the BehiG scene dropped for it. On 8 October 2026 the owner chose concept A,
"Find the deadline", after mocks of both concepts; the first concept, "Can you read
this?", is kept in §5 for reference. Companion to [hard-texts.md](hard-texts.md) (hook
sentences, the number) and [use-cases.md](use-cases.md) (the letters that may not leave
the authority, and why that leaves Apertus).

Submission limit: at most 2 minutes. Target: 1:50.

Source of the mocks and of the final render: [video/](../video/README.md) (Remotion
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
  (`data/examples/sources/praemienverbilligung-brief.txt`) and the easy-language text
  the first blocks of its real P2 draft (`data/examples/jobs/`, before review), word for
  word and labelled as such. This replaces the illustrative DE-4 rewrite of the first
  concept, for which P2 gave no usable output (PLAN.md §11, 8 October).
- The deadline runs through the video: the test, the fact sheet's "By when?", the
  deadline fact and its code check, the draft sentence linked to its source sentence,
  the end card ("The deadline. In the first sentence.").
- Key message: the 844,000 people must not be excluded from the letters that decide
  their money, deadlines and rights (spoken at 0:18-0:33, written on the end card).
  Same wording as in [hard-texts.md](hard-texts.md) §2, the README and the report.
- Evidence by case B of decision D-M (PLAN.md, WP13): no fact lost without a trace. A strong single
  prompt in its default mode loses hard facts and nothing tells the writer; Leicht·Facile
  lists every missing fact. The numbers come from the final run; Zurich is not named
  (D-L).
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
| 0:18-0:33 | The kitchen table in evening light (generated footage, or drawn as in the mock): **844,000** with "PIAAC 2023"; the letter's money, deadline and rights marked; the letter pushed away on "shut out"; a card *Slow expert work*. | "844,000 adults in Switzerland struggle with reading. Letters like this decide their money, their deadlines, their rights. No one should be shut out. But easy-language versions are slow expert work." |
| 0:33-0:40 | Logo, *easy-language drafts of official texts*, *with Apertus, the Swiss open model*; then *The writers stay in charge* and *A checked first draft*. | "Leicht·Facile drafts them with Apertus, the Swiss open model. The writers get a checked first draft." |
| 0:40-1:09 | **Real screen recording**, sped up, of the same letter: pasted, level A2. The fact sheet's five questions, *By when?* ringed, then the deadline fact with its value 2027-03-31. The draft. The rule check with a millisecond timer (47 ms on draft v1 of this letter). The facts tab with the deadline present. Judge and repair: the version pills from v1 (10 blocking) to the final version (2). The deadline sentence selected, its source sentence lit; approve with the keys; reader view and export. | "Apertus reads the letter the way you just tried to, and writes down every answer: what to do, by when, what it costs, whom to ask. Then it writes the draft. Code checks every date, amount and phone number, and 45 easy-language rules, in milliseconds. A larger Apertus model judges the meaning; only flagged sentences are repaired. Every sentence links to its source. The writer approves each one." |
| 1:09-1:19 | *No fact lost without a trace.* Left: the share of hard facts a strong single prompt in its default mode loses with nothing telling the writer (23 % in report §5, 6 October). Right: Leicht·Facile with the real facts tab, *13 of 14 facts present*, the missing fact first. Footnote: endpoint, model, split, date. | "A strong single prompt, in its default mode, lost almost a quarter of the hard facts, without a word. Leicht·Facile lists every missing fact." |
| 1:19-1:49 | The "only Apertus" scene of §5, unchanged: the envelopes, the four tiles struck one per sentence, Apertus, the icons, Ticino, CSCS. | As in §5, 1:29-1:57. |
| 1:49-1:52 | End card: *"The deadline. In the first sentence."* above *"No one left out."*, team name (Röstigraben Bridgers), repo URL, "Voice and imagery AI-generated". | (music only) |

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
| 0:07-0:13 | Apertus: the facts that must survive, marked in the sentence and set as chips: f01 deadline 2027-03-31, f03 obligation. | "Apertus first takes out what must survive: the deadline, and what you must do." |
| 0:13-0:17 | The sentence moves up; the real draft's three sentences (b002, b002.1, b003) appear one by one, each with the facts the job records for it. | "Then it writes short sentences. Who does what. One thing each." |
| 0:17-0:21 | The check again: 0 errors (before: 2); the date lights up in the first sentence, the deadline chip gets a tick. | "Code checks that the date is still there, exactly." |

The second sentence, *"Sie schicken das Formular bei der Sozial·versicherungs·stelle"*, should
say "an die"; the checker does not catch it. Either the review step fixes it on screen
or the example job is rebuilt after a prompt fix.

### Version C: "Can you read this?" opening with variant B's composition (mocked 8 October)

The owner's combination: the split-screen opening of §5 for the first seconds, then
variant B's step by step and the rest of §2. The stakes play on the kitchen table with
the letter, drawn in code for now; the owner decides later whether generated footage
replaces it. The app scene is shorter, since the step by step already shows facts and
checks. On 9 October the opening sentence came back before the end card, now in easy
language, so that the opening question gets its answer (owner); the easy text there is
the team's placeholder until the real output is in (§4). The same day the Ticino
sentence left the "only Apertus" scene, and its time went to that easy text (owner),
which now ends with the answer "Now you can." (owner). 269 words, 1:58 (voice speed 0.90; the silent leads and pauses trimmed by 0.1 to
0.6 s).

| Time | Picture | Narration (English) |
|------|---------|---------------------|
| 0:00-0:07 | The split screen of §5: DE-4 and FR-4 type themselves with their questions, one question per line, each line as it is spoken (owner, 8 October); the negations light up. | "Can you read this? Did you understand it right away?" |
| 0:07-0:19 | The kitchen table with the letter (drawn, or generated footage later); **844,000** with PIAAC 2023; then the letter's money, deadline and rights marked, each labelled. | "If you hesitated, you are not alone. 844,000 adults in Switzerland struggle with reading. Letters like these decide their money, their deadlines, their rights." |
| 0:19-0:31 | A bridge into easy language (owner, 8 October: the viewer must first learn that it exists): a card *Easy language*, with *Leichte Sprache* and *Langage facile* as the illustration and three of its rules, *Short sentences*, *Everyday words*, *One idea at a time*; under the rules *Equal access by Swiss law: BehiG | LHand* (owner, 9 October; on screen only, not spoken: art. 14 para. 1 BehiG, SR 151.3, names only speech, hearing and visual disabilities, and the revision before Parliament since the message of 20 December 2024 would add communication that people with learning disabilities understand, so the card does not say that the law requires easy language); below it the card *Slow expert work*; then the logo, *with Apertus, the Swiss open model*, *The writers stay in charge*, *A checked first draft*. | "For them, there is easy language. But easy-language versions are slow expert work. Leicht·Facile drafts them with Apertus, the Swiss open model, and gives the writers a checked first draft." |
| 0:31-0:55 | Variant B's step by step on the real sentence s0007; after the three new sentences the Mediopunkt in *Antrags·formular* and *Sozial·versicherungs·stelle* lights up, labelled "Mediopunkt: long words in readable parts" (owner, 8 October). | "Here is how, on one sentence from a real letter." Then as in variant B, with "A middle dot splits long words into easier parts." before the check. |
| 0:55-1:08 | Real app, short: the letter pasted, the pipeline, judge and repair (the version pills from 10 to 2 blocking), the deadline sentence linked to its source, approval, reader view and export. | "The same for the whole letter. A larger Apertus model judges the meaning; only flagged sentences are repaired. Every sentence links to its source, and the writer approves each one." |
| 1:08-1:17 | The evidence scene of §2. | As in §2. |
| 1:17-1:50 | The "only Apertus" scene of §5, opened by a bridge (owner, 8 October): the title *Easy language matters most in the most personal letters.* over the table, then the envelopes in the order they are named, the KESB decision first. | "Easy language matters most in the most personal letters. A child protection decision for a person with a learning disability. A letter from the hospital. A tax assessment. Under secrecy, they may not go to a foreign cloud." Then as in §5, without the Ticino sentence and its caption (owner, 9 October); the envelopes stay at the top for "For these letters, it is the only option." |
| 1:50-1:55 | The split screen of the opening again (owner, 9 October): DE-4 and FR-4 small and dimmed at the top, their negations still marked; below each its easy-language version line by line, labelled *Leichte Sprache* and *Langage facile*; under it *"Können Sie es jetzt lesen?"* and *"Pouvez-vous le lire maintenant ?"* as it is spoken. For now the team's text, labelled on screen as a placeholder: *"Das ist wichtig: / Melden Sie Ihre Kosten rechtzeitig. / Sonst bekommen Sie kein Geld zurück."* and *"C'est important : / Annoncez vos frais à temps. / Sinon, vous ne recevez pas d'argent."* (both pass `leichtfacile check` at A2 without errors or warnings). On the answer a green tick after each question (owner, 9 October: spoken, not a title; the question is already on screen twice). | "Can you read it now?" (1.2 s to try) "Now you can." |
| 1:55-1:58 | End card: *"No one left out."*, below it *"Every person. Every fact."* (both readings of the line: the people, and the facts of the evidence scene), team, repo (owner, 8 October). | (music only) |

## 4. Before recording

- [ ] The easy text of DE-4 and FR-4 at 1:50 (version C) is the team's placeholder:
      replace it with the tool's real output after the prompt freeze (Sun 11 October),
      in `video/src/scenes/Again.tsx`, and drop the placeholder note. Run the sentences
      inside a short letter: alone, DE-4 came back wrapped in letter headings and
      without its consequence (PLAN.md §11, 8 October).
- [ ] CSCS runs done: the silent-loss share of the strong single prompt for 1:09 from
      the final run, and a real example job for the screen recording.
- [ ] 844,000 wording re-checked against the SBFI press release
      ([hard-texts.md](hard-texts.md) §2).
- [ ] The "only Apertus" scene (1:19-1:49) re-checked against its sources in
      [use-cases.md §2](use-cases.md#why-only-apertus): the privatim resolution, the
      Apertus v1.5 model card (open training data, languages) and the CSCS article on
      the Ticino service.
- [x] Product scene: the premium-reduction letter, since the test and the screen
      recording use the same letter (concept A, 8 October).
- [x] Before/after: replaced by the second test, which shows the example job's real
      draft (concept A, 8 October).
- [ ] The draft's fourth sentence, *"Sie mitschicken eine Kopie der Steuer·veranlagung
      …"*, is ungrammatical and visible in the second test and in the review: rebuild
      the example job after a prompt fix, or show the reviewed text, labelled as
      reviewed.
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
| 0:12-0:32 | AI-generated footage: hands holding an official letter at a kitchen table, evening light. The number fades in: **844,000**, with "PIAAC 2023" small underneath. On "No one should be shut out", the letter is pushed back across the table, unread. | "If you hesitated, you are not alone. 844,000 adults in Switzerland struggle with reading. Letters like this decide their money, their deadlines, their rights. No one should be shut out of them. But easy-language versions are slow expert work, and a chatbot checks nothing." |
| 0:32-0:49 | Logo, the Apertus name, and the tagline set as text. | "Leicht·Facile drafts easy-language versions of official texts with Apertus, the Swiss open model. It does not replace the writers. It gives them a checked first draft. Apertus does what needs language understanding. Plain code checks everything that can be counted." |
| 0:49-1:19 | **Real screen recording**, sped up 2-4x, with zooms on key spots: New draft, paste a letter, choose A2. The running job: the stages tick off, the fact sheet appears with the values as chips. Rule check with a millisecond timer. Judge findings turning from red to green (the version pills: blocking problems per version). The review workbench: select a block and its source sentences light up; approve with the keys. Reader view, then export. | "Apertus turns a letter into a fact sheet: every deadline, amount and phone number. Then it writes a draft. Every sentence links back to its source; every omission is explained. Code checks 45 Swiss easy-language rules, and every date and amount. A larger Apertus model judges the meaning. Only flagged sentences are repaired. The writer approves every block, with a full audit trail." |
| 1:19-1:29 | DE-4 source on the left, **the tool's real A2 output** on the right. Then one evaluation number, P2 against P0. | "The same sentence, now. Short. Clear. The answer comes first. [One sentence with the evaluation result against a single prompt.]" |
| 1:29-1:57 | The kitchen table again. Four window envelopes slide in, face up as Swiss authorities send them (address window bottom right, blank address lines); the edit labels each top left in German and adds a small lock: *Patientenbrief*, *KESB-Entscheid*, *Strafbefehl*, *Steuerveranlagung* (German labels and the window: owner, 8 October). Four tiles follow, their text set in the edit: *Foreign cloud*, *Closed model*, *Open weights, secret training data*, *Open data, built abroad*, each struck through on its own sentence, the part that rules it out turning red (*secret training data*, *built abroad*); only when all four are struck, on "Apertus", a fifth, *Apertus: open data, built in Switzerland, in-house*, with a tick. (The fourth tile has its own sentence since 8 October: in the mock it was struck while Apertus was named, and "open data" read as a point against Apertus.) Under it the three icons on-premise, air-gapped, Swiss cloud; on "Ticino" a caption *Canton of Ticino: Apertus in-house for sensitive documents* (text only, no coat of arms); at the end a small label "This demo: CSCS, Lugano". | "Patient letters, child protection decisions, tax letters: under secrecy, they may not go to a foreign cloud. Closed models stay with their makers. Most open models keep their training data closed. Most fully open ones are built abroad. Apertus is open down to its data, built and trained in Switzerland, and runs in-house. Ticino already runs it for sensitive documents. For these letters, it is the only option." |
| 1:57-2:00 | End card: *"No one left out."*, team name (Röstigraben Bridgers), repo URL, "Voice and imagery AI-generated". | (music only) |
