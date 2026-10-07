# Demo video: script and storyboard

Status: initial draft, 6 October 2026; on 7 October 2026 the "only Apertus" scene
(1:29-1:57) added and the BehiG scene dropped for it. Companion to
[hard-texts.md](hard-texts.md) (hook sentences, the number) and
[use-cases.md](use-cases.md) (the letters that may not leave the authority, and why
that leaves Apertus).

Submission limit: at most 2 minutes. Target: 1:50.

## 1. Concept: "Can you read this?"

Start with the viewer's own moment of not understanding, then show the tool solving
that same sentence. The video itself follows easy-language rules: short sentences,
one idea per shot, English captions burned in.

- Main language: English (narration, captions, titles). German and French appear on
  screen only as illustrations.
- Fully AI-generated: voice, music, background footage, titles. The product scenes are
  real screen recordings (see §3).
- Key message: the 844,000 people must not be excluded from the letters that decide
  their money, deadlines and rights (spoken at 0:12-0:32, written on the end card).
  Same wording as in [hard-texts.md](hard-texts.md) §2, the README and the report.
- Second message: patient letters, child protection decisions and tax letters are
  under secrecy and may not go to a foreign cloud, and for them Apertus is the only
  model that fits (1:29-1:57). The argument and its sources are in
  [use-cases.md §2](use-cases.md#why-only-apertus); the README and report §3 say the
  same.
- Third message: Leicht·Facile does not replace the writers; it gives them a checked
  first draft (0:32-0:49), and the writer approves every block (end of the product
  scene).
- Narration: about 250 words, about 1:47 at a calm pace (140 words per minute). Every
  scene is timed to its narration: if the evaluation sentence at 1:19 runs longer than
  20 words, take the time from the product scene.

## 2. Storyboard

| Time | Picture | Narration (English) |
|------|---------|---------------------|
| 0:00-0:12 | Black screen. DE-4 types itself in full screen: *"Es ist nicht unwesentlich, dass Kosten, die nicht fristgerecht geltend gemacht werden, nicht vergütet werden können."* Below it: *"Können Sie das lesen? Haben Sie es sofort verstanden?"* Quick cut to FR-4 with *"Pouvez-vous lire ceci ? L'avez-vous compris tout de suite ?"* | "Can you read this? Did you understand it right away? Only one question matters here: do I get my money back, or not?" |
| 0:12-0:32 | AI-generated footage: hands holding an official letter at a kitchen table, evening light. The number fades in: **844,000**, with "PIAAC 2023" small underneath. On "No one should be shut out", the letter is pushed back across the table, unread. | "If you hesitated, you are not alone. 844,000 adults in Switzerland struggle with reading. Letters like this decide their money, their deadlines, their rights. No one should be shut out of them. But easy-language versions are slow expert work, and a chatbot checks nothing." |
| 0:32-0:49 | Logo, the Apertus name, and the tagline set as text. | "Leicht·Facile drafts easy-language versions of official texts with Apertus, the Swiss open model. It does not replace the writers. It gives them a checked first draft. Apertus does what needs language understanding. Plain code checks everything that can be counted." |
| 0:49-1:19 | **Real screen recording**, sped up 2-4x, with zooms on key spots: New draft, paste a letter, choose A2. The running job: the stages tick off, the fact sheet appears with the values as chips. Rule check with a millisecond timer. Judge findings turning from red to green (the version pills: blocking problems per version). The review workbench: select a block and its source sentences light up; approve with the keys. Reader view, then export. | "Apertus turns a letter into a fact sheet: every deadline, amount and phone number. Then it writes a draft. Every sentence links back to its source; every omission is explained. Code checks 42 Swiss easy-language rules, and every date and amount. A larger Apertus model judges the meaning. Only flagged sentences are repaired. The writer approves every block, with a full audit trail." |
| 1:19-1:29 | DE-4 source on the left, **the tool's real A2 output** on the right. Then one evaluation number, P2 against P0. | "The same sentence, now. Short. Clear. The answer comes first. [One sentence with the evaluation result against a single prompt.]" |
| 1:29-1:57 | The kitchen table again. Four blank envelopes slide in; the edit labels each and adds a small lock: *Patient letter*, *KESB decision*, *Penal order*, *Tax assessment*. Four tiles follow, their text set in the edit: *Foreign cloud*, *Closed model*, *Open weights, secret training data*, *Open data, built abroad*, each struck through as the narration reaches it, then a fifth, *Apertus: open data, built in Switzerland, in-house*, with a tick. Under it the three icons on-premise, air-gapped, Swiss cloud; on "Ticino" a caption *Canton of Ticino: Apertus in-house for sensitive documents* (text only, no coat of arms); at the end a small label "This demo: CSCS, Lugano". | "Patient letters, child protection decisions, tax letters: under secrecy, they may not go to a foreign cloud. Closed models stay with their makers. Most open models keep their training data closed. Apertus is open down to its data, built and trained in Switzerland, and runs in-house. Ticino already runs it for sensitive documents. For these letters, it is the only option." |
| 1:57-2:00 | End card: *"No one left out."*, team name (Röstigraben Bridgers), repo URL, "Voice and imagery AI-generated". | (music only) |

## 3. Production notes

- **Record the product, do not generate it.** The UI scenes (0:49-1:19) and the
  before/after (1:19-1:29) are real recordings of the tool, as
  [hard-texts.md](hard-texts.md) §1 requires for the comparison. Generated screens of
  the app would misrepresent the prototype.
- **No readable text in generated footage.** Video generators garble writing. Generate
  the kitchen-table letter blank and add the DE-4 text in the edit. Use a made-up
  sender such as "Gemeinde Musterwil", never a real authority's letterhead or logo.
  The same for the envelopes at 1:29: blank in the footage, labelled in the edit.
- **Categories, not competitors.** The struck-through tiles at 1:29 name kinds of
  models, never a product, a company or a logo. Every claim in that scene has its
  source in [use-cases.md §2](use-cases.md#why-only-apertus); "only option" is meant
  for letters under secrecy, not for public web pages, and the scene says so.
- **Pronunciation:** set a text-to-speech alias for "Leicht·Facile" (roughly "LYSHT
  fa-SEEL") and test it first. The same for "Apertus" and "CSCS" (spelled out C-S-C-S).
- **Voice:** one calm, warm voice, a bit slower than normal (about 140 words per
  minute), with pauses after the questions in the first scene. Quiet music.
- **Captions:** English, burned in. German and French only in the picture, not in the
  captions.

## 4. Before recording

- [ ] CSCS runs done: the evaluation number for 1:19 and a real example job for the
      screen recording.
- [ ] 844,000 wording re-checked against the SBFI press release
      ([hard-texts.md](hard-texts.md) §2).
- [ ] The "only Apertus" scene (1:29-1:57) re-checked against its sources in
      [use-cases.md §2](use-cases.md#why-only-apertus): the privatim resolution, the
      Apertus v1.5 model card (open training data, languages) and the CSCS article on
      the Ticino service.
- [ ] French: show it beyond the opening only if the French rules and prompts work by
      recording day.
- [ ] Product scene (0:49-1:19): the premium-reduction letter or a KESB decision
      written by the team ([use-case-decisions.md](use-case-decisions.md)); decide
      after a test run on 8 October.
- [ ] Recording finished by 14 October; two days for edits before the deadline
      (16 October 2026, 12:00 CEST).
