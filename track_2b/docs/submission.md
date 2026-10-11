# Submission

Status: first draft, 9 October 2026. Everything the hackathon asks for by Fri 16 October,
12:00 CEST, in one place: the deliverables, our entry for each field of the submission
form, the message to the jury, the video page, and the jury's questions with where our
documents answer them. A working document for the team. **[OWNER: delete it, or keep
it, before the repository goes public.]**

Placeholders, here and in README.md and track_2b/technical_report.md: **[PENDING: ...]** waits for
a scheduled step (the final CSCS run after the prompt freeze of 10 October, the
video upload, the submitted commit); **[OWNER: ...]** needs a decision or a fact from
the team. `grep -n "\[PENDING\|\[OWNER" README.md track_2b/technical_report.md track_2b/docs/submission.md`
lists them all; none may be left in README.md and track_2b/technical_report.md when we submit.

## 1. Deliverables

| Deliverable | Where | State |
|-------------|-------|-------|
| Git repo (URL), public | https://github.com/bobrovsky420/leicht-facile | Private today (anonymous access gave 404 on 7 October). **[PENDING: public before submitting; `.env` absent from history; CI green on the submitted commit]** |
| Technical report (PDF, at most 6 pages without the references) | `track_2b/RoestigrabenBridgers_Report.pdf`, printed from `track_2b/technical_report.md` with `make pdf`; both only in `track_2b/` since 11 October (owner) | Printed 11 October from the final numbers (method and limit in §5): 6 pages, the references on the sixth below the licence note, links absolute, no placeholder left. Printed again on 11 October with the video link of C38. **[PENDING: print again after any later change to the report]** |
| Demo video (URL), at most 2 minutes | Version C, 118.7 s ([demo-video.md](demo-video.md)), render C38 (11 October, the final numbers), uploaded 11 October: https://youtu.be/3UVbaXQ8I6o (before: a temporary upload of mock C26) | Linked in both READMEs, the report and its PDF (printed again 11 October). A later render needs a new upload and the link replaced everywhere: YouTube cannot swap the video behind an existing link. |
| Dataset (URL), optional | none | Dropped by the owner on 9 October (PLAN.md D-G) |
| `make run` from the root on a clean checkout | Makefile (at the root; it includes `track_2b/Makefile` with the targets), docker-compose.yml | Passed on Windows (fresh clone, no `.env`) and on Linux (Ubuntu 24.04 on AWS, 10 October, commit 6936d05: `make run` unchanged, one job end to end against the local vLLM profile; [track_2b/eval/hardware/](../eval/hardware/aws-l4-2026-10-10/)). After the move into `track_2b/` (10 October, working tree on Windows): `make run` and `make stop` from the root and from `track_2b/`, healthy, both example jobs imported. **[PENDING: a fresh clone of the commit with the move, PLAN.md next step 8]** |

## 2. The submission form

hackapertus.ch/online-hack/submissions, track "Track 2B - Own Project". One submission
per project: only one of us submits. The fields as the form defines them (read from the
site on 9 October; * = required):

| Field | Our entry |
|-------|-----------|
| First name * | **[OWNER: the team member who submits]** |
| Last name * | **[OWNER]** |
| Email (used for Devpost sign-up) * | **[OWNER: the address used for the Devpost sign-up]** |
| GitHub username * | `bobrovsky420` **[OWNER: or the submitter's own]** |
| Hugging Face username | empty (no dataset) |
| Team name * | Röstigraben Bridgers |
| Team members * (comma-separated names) | Alexander Bobrovsky, Ivan Kuzmych |
| Project name * | Leicht·Facile |
| Swiss student team * (Yes / No) | **[OWNER]** |
| Model * (8B v1.5, 70B v1.5, or 8B + 70B v1.5) | 8B + 70B v1.5 |
| Technical report (PDF, max. 6 pages) * | `track_2b/RoestigrabenBridgers_Report.pdf` |
| Dataset (URL) | empty |
| Git repo (URL) * | https://github.com/bobrovsky420/leicht-facile |
| Demo video (URL), required for Track 2B | https://youtu.be/3UVbaXQ8I6o (render C38) |
| Your message (optional, at most 5,000 characters) | §3 |
| Terms and Conditions * | Accept. Section 6, "What you build is open source": code Apache 2.0, report CC-BY-4.0 |

Judging starts on 16 October at 18:00; each challenge goes to two or three jurors, and
the winners are announced on 23 October at 12:00.

## 3. Message to the jury

For the form's "Your message" field, as plain text (about 3,700 characters with the
placeholders; at most 5,000):

```text
Leicht·Facile drafts easy-language versions of Swiss official texts and letters (German Leichte Sprache, French FALC) with Apertus 1.5, for readers such as the 1.25 million adults in Switzerland with low reading skills. It is built for the people who write official texts: trained easy-language writers, who today write each version by hand and check every deadline, amount and phone number against the original, and the case workers, clerks and physicians who write decisions and letters themselves.

How it works. Apertus does what needs language understanding: the 8B reads the document into a fact sheet, writes a draft with a source for every sentence, repairs only the sentences a check flagged and asks once more for each value still missing; the 70B judges meaning. Plain code does what can be counted: 45 rules for German and 41 for French from the published Swiss guidelines, and an exact check that every fact value of the original (dates, amounts, phone numbers, periods, reference numbers) is in the draft and that the draft adds none. A person reviews source and draft side by side and exports the text with an audit trail.

Maturity we declare: a deployable prototype for German and French drafts of public texts and letters; a proof of concept for court and KESB decisions (decision mode v1); image input explored, not built.

Try it. Set LLM_BASE_URL, LLM_API_KEY and LLM_NAME (the CSCS values work as they are), then run make run. The drafts list opens with two pre-computed example letters (German and French), so the review page can be seen without a model call. "Try a prepared letter" sends the German or the French letter through the whole pipeline with one click: Apertus's answers to these two were recorded on CSCS, so the run takes seconds instead of minutes, and the page says so; any other text goes to Apertus live. "Check my text" runs the rule checker on any pasted text, without a model.

What the running system contacts: only the Apertus endpoint in LLM_BASE_URL (the document text, inside prompts) and, when a user enters a URL, that page's server. No telemetry, no CDN, no login provider; on-premise or air-gapped, no data leaves the organisation. Why Apertus is the only model that fits letters under official, medical or tax secrecy: README, "Why only Apertus".

Results. Same model, a strong single prompt (a published Leichte Sprache prompt from a Swiss public administration) against our pipeline, on 20 held-out German pairs on the CSCS endpoint (final run, 11 October 2026): the pipeline finds 100 percent of the must-keep facts against 83, loses none without a trace against 15 percent, and has 4.2 against 15.0 rule errors per 100 blocks; invented values are rare on both sides (0.1 against 0.0).

Where Apertus fell short, and what we did about it: the 8B drops facts while writing and ignores word-level instructions, so code completes the fact sheet and checks every value; the 70B judge's fact verdicts agree with blind labels hardly better than chance (kappa 0.08), so every fact number in the report comes from code; on scanned letters both models change digits on a whole page and names in every setting, so image input is not built (track_2b/docs/image-input.md has every run).

Use of AI in development: the code, tests and documents were written with AI coding assistants (Claude Code, Anthropic), directed and reviewed by the team. Claude also labelled the 59 items of the judge agreement. No other model runs in the product.

Where to start: README.md, track_2b/technical_report.md (as PDF: track_2b/RoestigrabenBridgers_Report.pdf), track_2b/eval/report.md, track_2b/docs/use-case-canton.md. Submitted commit: [PENDING: hash].
```

## 4. The video page

- **Platform and visibility:** **[OWNER: for example YouTube, unlisted; it must play
  without a login]**
- **Length:** at most 2:00; version C is 118.7 s ([demo-video.md](demo-video.md)).
- **Chapters:** the timestamps in the description, from the scene starts of C38
  (`src/timeline-c.json` in the build folder), each rounded down to the second. YouTube
  needs 0:00 first, at least 3 chapters and 10 s each, so the hook (7 s) joins the
  stakes, and the callback and the end card (8.5 s) join "Why only Apertus". Compute
  them again after a new voice.
- **Title:** Leicht·Facile: easy-language drafts of Swiss official letters with Apertus
- **Description:**

```text
Hack Apertus 2026, Track 2B. Team Röstigraben Bridgers (Alexander Bobrovsky, Ivan Kuzmych).

1.25 million adults in Switzerland struggle with reading (Swiss Federal Statistical Office, PIAAC 2022/23). Leicht·Facile drafts easy-language versions of official letters with Apertus 1.5 and checks with code that no deadline, amount or phone number gets lost. A person reviews every draft before it goes out.

Code, report and how to run it: https://github.com/bobrovsky420/leicht-facile

0:00 Can you read this?
0:18 Easy language, drafted with Apertus
0:30 One sentence, step by step
0:54 The whole letter, checked and approved
1:06 Evidence: no hard fact lost without a trace
1:17 Why only Apertus

Voice AI-generated: Kokoro (open weights, run locally). Pictures drawn in code or captured from the app.
```

## 5. The report PDF

`make pdf` prints the report with an own renderer, `track_2b/scripts/report_pdf.py`
(11 October; the owner's answer to the open question of the export method). The PDF is
prepared in advance and uploaded with the form, so it is laid out for reading, not a
plain print of the Markdown; its text is that of `track_2b/technical_report.md`, read
with markdown-it-py, so every change of the report reaches it with the next print.

- **Layout** (`track_2b/scripts/report/`: page template, stylesheet, drawings): A4 in
  two columns in the web UI's fonts and colours (track_2b/docs/ui-design.md §3), IBM
  Plex Sans 9.1 pt, the summary a size larger as the abstract; running header, footer
  and page numbers. Each chapter title spans the page, ruled above and below, and the
  chapter starts at the top of a new pair of columns (owner, 11 October). Wide tables
  and the diagrams span both columns; a paragraph that introduces a wide table becomes
  its caption; a title stays with the diagram, caption or table that follows it. After
  printing, the renderer looks for a chapter title with no text under it on its page
  (Chromium does not keep a full-width title with the columns below it) and prints
  again with that chapter on a new page (owner, 11 October).
  The summary starts its right column with the deployment paragraph ("One container
  plus an ...", `NEW_COLUMN` in the renderer; owner, 11 October).
  Ragged right and no hyphenation (owner, 11 October): no word is broken at a line
  end, not even at a hyphen of its own.
- **First page:** a title block made from the list under the report's title, and four
  key figures read from the results table in §5, P2 (ours) against P0-ZH complete:
  fact coverage, hard facts kept, silent losses and rule errors, the headline's figures
  (D-M). A changed cell changes them with the next print.
- **Diagrams:** the two Mermaid diagrams of report §2 are drawn as SVG for the PDF, in
  the colours of Apertus, code and the human. `track_2b/tests/test_report_pdf.py`
  checks that the drawings carry every label of the diagrams; a changed diagram must
  be drawn again.
- **Links:** every relative link becomes a link to the repository on GitHub
  (`blob/main/...`), which works from both copies and from the file uploaded with the
  form. Printed as they are, the browser would write them as paths on the printing
  machine (the draft of 9 October had nine `file:///C:/Users/...` links).
- **Printing:** headless Edge or Chrome (`--print-to-pdf`; `CHROME_PATH` names another
  Chromium), a tagged PDF with bookmarks from the headings. The renderer adds the
  document information (title, authors, subject), writes
  `track_2b/RoestigrabenBridgers_Report.pdf` and prints the pages and how full the last
  one is, with and without the references.
- **Foot table:** the target-architecture table (a, b, c) spans the page at the foot of
  the page its subsection starts on (owner, 11 October). The renderer prints the report
  with the table moved down its subsection block by block and keeps the last place
  where it still starts on that page; a sentence ending in a colon stays with the block
  it introduces. Space above the table and its column widths are set so that it fits
  the foot of page 2 with today's text.
- **Limit:** at most 6 pages without the references (the organisers in the hackathon
  chat, 11 October, 13:43: "It's w/o references"; they add it to the guide). The
  renderer finds where the references start by the bookmark of their heading, counts
  the pages before them (the licence note counts) and fails above 6.
  `track_2b/tests/test_report_pdf.py` checks the same on the committed PDF, and that it
  came from the renderer; `track_2b/tests/test_copies.py` that no link is a local path.

Printed 11 October from the final numbers: 6 pages, the last 92 % full. Without the
references also 6, the sixth 75 % full, so the text may grow by about a quarter of a
page; the references then move to a seventh page, which the limit does not count. The
full-width blocks, not the text size, set the page breaks.

## 6. The jury's questions

The jury scores Track 2B on five dimensions, 0 to 5 each (25 points), and gives each
dimension guiding questions (hackapertus.ch, jury briefing, read 9 October). Technical
rigour is judged against the maturity level the team declares. Where our documents
answer each question:

| Dimension | Question | Where we answer it | State |
|-----------|----------|--------------------|-------|
| Purposeful use of AI | Is Apertus suited to the task, and is that choice reasoned? | Report §1 and §3 ("why only Apertus"); README, "Why only Apertus"; [use-cases.md](use-cases.md) §2 | Answered |
| | Is the model size justified, 8B where sufficient, 70B where needed? | Report §3 "Why these sizes"; §5 table (70B everywhere, hybrid) | Answered with the final run of 11 October (report §3 and §5) |
| | Is every other model right-sized? | Report §3 "Other models and coding assistants": none at runtime; spaCy and wordfreq | Answered |
| | Does it say where Apertus fell short? | Report §3 "Where Apertus fell short"; §5 judge reliability; [image-input.md](image-input.md) | Answered |
| Technical rigour | Does it run reproducibly from the documented command? | `make run`; report §7 | Clean checkout passed on Windows and Linux. **[PENDING: CI green on the submitted commit]** |
| | Is the claim backed by evaluation, not a single demo? | Report §5: 20 held-out pairs, two baselines, the official versions | Answered with the final run of 11 October 2026: every row on the 20 German and 3 French held-out pairs, the 70B everywhere on 19 German (report §5) |
| | Where optimisation was applied (quantisation, batching, caching), is its effect shown? | Report §3 and §5: the 4-bit build only for development, never mixed; the response cache makes reruns exact and seconds undercount; Write without thinking (24 min against 28 s, 4-bit) | Partly: the cache's and the 4-bit build's effect on quality is not measured, nor the vLLM profile's FP8 KV cache (its memory effect is, report §2) |
| | Are limitations and the use of coding assistants declared? | Report §6; report §3 "Other models and coding assistants"; README team line | Answered |
| | (Maturity level declared) | Report header; README; message §3 | Confirmed by the owner, 11 October |
| Value, cost and scalability | Is the problem evidenced, or only asserted? | Report §1 (FSO PIAAC, disability law, cantons publishing); [use-case-canton.md](use-case-canton.md) §1 | Answered |
| | Does it name a specific user group? | Report §1: the people who write official texts (trained writers, case workers, clerks, physicians); their readers in §1's first sentence | Answered |
| | Is the running cost proportionate to the benefit per use? | Report §5 "Cost and scale" | Review time measured 10 Oct: about 3.5 minutes per 250-word page (team, not experts; report §5). No published drafting time per page to compare with. |
| | What happens to cost and speed at ten times the volume? | Report §5 "Cost and scale" | Answered; more workers neither built nor measured |
| Sovereign deployability | Can it be self-hosted on realistic hardware? | Report §2 target architecture and hardware | Answered: the vLLM profile ran on one NVIDIA L4 24 GB (`track_2b/eval/hardware/`) |
| | Does runtime data leave the user's environment? | Report §2 "What the running system contacts" | Answered |
| | Are weights, licences and dependencies free of blocking terms? | Report §2 "Licences and providers" | Answered |
| | Is it independent of any single commercial provider? | Report §2 "Licences and providers" (any OpenAI-compatible server) | Answered |
| Implementation feasibility | Does use require a realistic change of work? | [use-case-canton.md](use-case-canton.md) §5; report §8 "Into use"; report §2: the reviewed draft also exports to Word, where the writers work (since 11 October) | Answered |
| | How far from real use: what must still be built, obtained or approved? | Report §8 "Into use" | Answered |
| | Is there a named first user or group? | Nowhere: the report names none | Not answered; the placeholder dropped from report §8 (owner, 11 October) |
| | Do others have the same need? | Report §8; [use-cases.md](use-cases.md) | Answered |

## 7. Before we press Submit

- [ ] Final CSCS run read (PLAN.md WP13, D-M); its numbers in one pass in report §1,
      §5 and §6, README and the video (`eval numbers`, `track_2b/eval/report.md`).
- [ ] No **[PENDING]** or **[OWNER]** left in README.md and track_2b/technical_report.md.
- [ ] Tests and ruff green; CI green on the submitted commit.
- [ ] The prepared letters still replay on the submitted commit (`test_examples.py`
      replays each recording without an endpoint); after any prompt change, record
      them again with `python -m leichtfacile examples record` (track_2b/data/examples/README.md).
- [ ] Report printed with `make pdf` (§5) after its last change, at most 6 pages before
      the references, saved as `track_2b/RoestigrabenBridgers_Report.pdf`, committed.
- [ ] Video rendered, uploaded, URL in README, report and form.
- [ ] Repository public; `git log -p -- .env` empty.
- [x] Clean-checkout test on Linux or macOS: clone, `.env`, `make run`, one job
      (Linux, 10 October, commit 6936d05).
- [ ] Form filled and submitted by one of us, by Thu 15 October (G6); deadline Fri 16
      October, 12:00 CEST, no extension.
