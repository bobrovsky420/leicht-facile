# Demo video: script and storyboard

Status: initial draft, 6 October 2026. Companion to [hard-texts.md](hard-texts.md)
(hook sentences, the number, BehiG).

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
  their money, deadlines and rights (spoken at 0:12-0:34, written on the end card).
  Same wording as in [hard-texts.md](hard-texts.md) §2, the README and the report.
- Narration: about 250 words, about 1:47 at a calm pace (140 words per minute).

## 2. Storyboard

| Time | Picture | Narration (English) |
|------|---------|---------------------|
| 0:00-0:12 | Black screen. DE-4 types itself in full screen: *"Es ist nicht unwesentlich, dass Kosten, die nicht fristgerecht geltend gemacht werden, nicht vergütet werden können."* Below it: *"Können Sie das lesen? Haben Sie es sofort verstanden?"* Quick cut to FR-4 with *"Pouvez-vous lire ceci ? L'avez-vous compris tout de suite ?"* | "Can you read this? Did you understand it right away? Only one question matters here: do I get my money back, or not?" |
| 0:12-0:34 | AI-generated footage: hands holding an official letter at a kitchen table, evening light. The number fades in: **844,000**, with "PIAAC 2023" small underneath. On "No one should be shut out", the letter is pushed back across the table, unread. | "If you hesitated, you are not alone. 844,000 adults in Switzerland struggle with reading. Letters like this decide their money, their deadlines, their rights. No one should be shut out of them. But easy-language versions are slow expert work, and chatbots run on foreign clouds, with no checks." |
| 0:34-0:46 | Logo, the Apertus name, and the tagline set as text. | "Leicht·Facile drafts easy-language versions of official texts with Apertus, the Swiss open model. Apertus does what needs language understanding. Plain code checks everything that can be counted." |
| 0:46-1:30 | **Real screen recording**, sped up 2-4x, with zooms on key spots: paste a letter, choose A2. Fact sheet with the values highlighted. Draft with links back to the source sentences. Rule check with a millisecond timer. Judge findings turning from red to green. Review page side by side. Approve, then export. | "Paste a letter, upload a PDF, or enter a URL. First, Apertus turns it into a fact sheet: every deadline, amount and phone number, with its exact value. Then it writes a draft. Every sentence links back to its source. Every omission is explained. Code checks 41 rules from the Swiss guidelines in milliseconds, and confirms that no fact got lost. A larger Apertus model judges the meaning. Only the flagged sentences get repaired. Finally, a human expert reviews, approves and exports, with a full audit trail." |
| 1:30-1:40 | DE-4 source on the left, **the tool's real A2 output** on the right. Then one evaluation number, P2 against P0. | "The same sentence, now. Short. Clear. The answer comes first. [One sentence with the evaluation result against a single prompt.]" |
| 1:40-1:48 | Three icons: on-premise, air-gapped, Swiss cloud. A "CSCS Lugano" label. | "It runs on-premise, air-gapped, or in a Swiss sovereign cloud. This demo runs on CSCS in Lugano." |
| 1:48-1:57 | *"Behindertengleichstellungsgesetz (BehiG)"* fills the screen. The rule badges LEX-01, LEX-02 and GRAM-05 pop up in red. Then the easy version. | "Even the Swiss law on equal rights for people with disabilities breaks its own rules. Even the law needs Leicht·Facile." |
| 1:57-2:00 | End card: *"No one left out."*, team name (Röstigraben Bridgers), repo URL, "Voice and imagery AI-generated". | (music only) |

## 3. Production notes

- **Record the product, do not generate it.** The UI scenes (0:46-1:30) and the
  before/after (1:30-1:40) are real recordings of the tool, as
  [hard-texts.md](hard-texts.md) §1 requires for the comparison. Generated screens of
  the app would misrepresent the prototype.
- **No readable text in generated footage.** Video generators garble writing. Generate
  the kitchen-table letter blank and add the DE-4 text in the edit. Use a made-up
  sender such as "Gemeinde Musterwil", never a real authority's letterhead or logo.
- **Pronunciation:** set a text-to-speech alias for "Leicht·Facile" (roughly "LYSHT
  fa-SEEL") and test it first. The same for "Apertus" and "CSCS" (spelled out C-S-C-S).
- **Voice:** one calm, warm voice, a bit slower than normal (about 140 words per
  minute), with pauses after the questions in the first scene. Quiet music.
- **Captions:** English, burned in. German and French only in the picture, not in the
  captions.

## 4. Before recording

- [ ] CSCS runs done: the evaluation number for 1:30 and a real example job for the
      screen recording.
- [ ] BehiG easy version produced by the actual tool, not the hand-written one in
      [hard-texts.md](hard-texts.md) §1.
- [ ] 844,000 wording re-checked against the SBFI press release
      ([hard-texts.md](hard-texts.md) §2).
- [ ] French: show it beyond the opening only if the French rules and prompts work by
      recording day.
- [ ] Recording finished by 14 October; two days for edits before the deadline
      (16 October 2026, 12:00 CEST).
