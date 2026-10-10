# Submission

Status: first draft, 9 October 2026. Everything the hackathon asks for by Fri 16 October,
12:00 CEST, in one place: the deliverables, our entry for each field of the submission
form, the message to the jury, the video page, and the jury's questions with where our
documents answer them. A working document for the team. **[OWNER: delete it, or keep
it, before the repository goes public.]**

Placeholders, here and in README.md and track_2b/technical_report.md: **[PENDING: ...]** waits for
a scheduled step (the final CSCS run after the prompt freeze on Sun 11 October, the
video upload, the submitted commit); **[OWNER: ...]** needs a decision or a fact from
the team. `grep -n "\[PENDING\|\[OWNER" README.md track_2b/technical_report.md track_2b/docs/submission.md`
lists them all; none may be left in README.md and track_2b/technical_report.md when we submit.

## 1. Deliverables

| Deliverable | Where | State |
|-------------|-------|-------|
| Git repo (URL), public | https://github.com/bobrovsky420/leicht-facile | Private today (anonymous access gave 404 on 7 October). **[PENDING: public before submitting; `.env` absent from history; CI green on the submitted commit]** |
| Technical report (PDF, at most 6 pages) | `track_2b/RoestigrabenBridgers_Report.pdf`, printed from `track_2b/technical_report.md`; the same file at the root, next to the root copy of the report | Draft reprinted 10 October from the current text, links absolute: 6 pages, the last 94 % full, placeholders included (method in §5). **[PENDING: export again after the final numbers; check the 6 pages]** |
| Demo video (URL), at most 2 minutes | Version C, 118.1 s ([demo-video.md](demo-video.md)) | **[PENDING: final render with the final numbers and the opening sentence's real output; upload; URL]** |
| Dataset (URL), optional | none | Dropped by the owner on 9 October (PLAN.md D-G) |
| `make run` from the root on a clean checkout | Makefile (at the root; `track_2b/Makefile` passes every target on), docker-compose.yml | Passed on Windows (fresh clone, no `.env`) and on Linux (Ubuntu 24.04 on AWS, 10 October, commit 6936d05: `make run` unchanged, one job end to end against the local vLLM profile; [track_2b/eval/hardware/](../eval/hardware/aws-l4-2026-10-10/)). After the move into `track_2b/` (10 October, working tree on Windows): `make run` and `make stop` from the root and from `track_2b/`, healthy, both example jobs imported. **[PENDING: a fresh clone of the commit with the move, PLAN.md next step 8]** |

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
| Demo video (URL), required for Track 2B | **[PENDING: video URL]** |
| Your message (optional, at most 5,000 characters) | §3 |
| Terms and Conditions * | Accept. Section 6, "What you build is open source": code Apache 2.0, report CC-BY-4.0 |

Judging starts on 16 October at 18:00; each challenge goes to two or three jurors, and
the winners are announced on 23 October at 12:00.

## 3. Message to the jury

For the form's "Your message" field, as plain text (about 3,100 characters with the
placeholders; at most 5,000):

```text
Leicht·Facile drafts easy-language versions of Swiss official texts and letters (German Leichte Sprache, French FALC) with Apertus 1.5, for readers such as the 1.25 million adults in Switzerland with low reading skills. It is built for the people who write official texts: trained easy-language writers, who today write each version by hand and check every deadline, amount and phone number against the original, and the case workers, clerks and physicians who write decisions and letters themselves.

How it works. Apertus does what needs language understanding: the 8B reads the document into a fact sheet, writes a draft with a source for every sentence, repairs only the sentences a check flagged and asks once more for each value still missing; the 70B judges meaning. Plain code does what can be counted: 45 rules for German and 41 for French from the published Swiss guidelines, and an exact check that every fact value of the original (dates, amounts, phone numbers, periods, reference numbers) is in the draft and that the draft adds none. A person reviews source and draft side by side and exports the text with an audit trail.

Maturity we declare: a deployable prototype for German and French drafts of public texts and letters; a proof of concept for court and KESB decisions (decision mode v1); image input explored, not built. [OWNER: confirm]

Try it. Set LLM_BASE_URL, LLM_API_KEY and LLM_NAME (the CSCS values work as they are), then run make run. The drafts list opens with two pre-computed example letters (German and French), so the review page can be seen without a model call. "Check my text" runs the rule checker on any pasted text, without a model.

What the running system contacts: only the Apertus endpoint in LLM_BASE_URL (the document text, inside prompts) and, when a user enters a URL, that page's server. No telemetry, no CDN, no login provider; on-premise or air-gapped, no data leaves the organisation. Why Apertus is the only model that fits letters under official, medical or tax secrecy: README, "Why only Apertus".

Results. [PENDING: the headline sentence after the final CSCS run (D-M), with endpoint and split.]

Where Apertus fell short, and what we did about it: the 8B drops facts while writing and ignores word-level instructions, so code completes the fact sheet and checks every value; the 70B judge's fact verdicts agree with blind labels hardly better than chance (kappa 0.08), so every fact number in the report comes from code; on scanned letters both models change digits on a whole page and names in every setting, so image input is not built (track_2b/docs/image-input.md has every run).

Use of AI in development: the code, tests and documents were written with AI coding assistants (Claude Code, Anthropic), directed and reviewed by the team [OWNER: confirm]. Claude also labelled the 59 items of the judge agreement. No other model runs in the product.

Where to start: README.md, track_2b/technical_report.md (as PDF: track_2b/RoestigrabenBridgers_Report.pdf), track_2b/eval/report.md, track_2b/docs/use-case-canton.md. Submitted commit: [PENDING: hash].
```

## 4. The video page

- **Platform and visibility:** **[OWNER: for example YouTube, unlisted; it must play
  without a login]**
- **Length:** at most 2:00; version C is 118.1 s ([demo-video.md](demo-video.md)).
- **Title:** Leicht·Facile: easy-language drafts of Swiss official letters with Apertus
- **Description:**

```text
Hack Apertus 2026, Track 2B. Team Röstigraben Bridgers (Alexander Bobrovsky, Ivan Kuzmych).

1.25 million adults in Switzerland struggle with reading (Swiss Federal Statistical Office, PIAAC 2022/23). Leicht·Facile drafts easy-language versions of official letters with Apertus 1.5 and checks with code that no deadline, amount or phone number gets lost. A person reviews every draft before it goes out.

Code, report and how to run it: https://github.com/bobrovsky420/leicht-facile

Voice and imagery AI-generated; the voice is Kokoro (open weights, run locally). [OWNER: confirm the credits for the final cut]
```

## 5. The report PDF

The draft PDF was printed like the page check of 7 October: `track_2b/technical_report.md`
rendered with markdown-it-py (tables on), with `<base
href="https://github.com/bobrovsky420/leicht-facile/blob/main/track_2b/">` in the page's
head, the Mermaid diagrams drawn by mermaid 11
from jsDelivr, printed by headless Edge (`--print-to-pdf --no-pdf-header-footer
--virtual-time-budget=15000`) on A4 with 2 cm margins, Arial 10 pt, line height 1.35,
tables 8.5 pt, headings kept with the text that follows. Plain pandoc would print the
Mermaid code instead of the diagrams. The base URL matters: the browser writes every
link of the PDF as an absolute address, and without it the report's relative links
became paths on the printing machine (the draft of 9 October had nine such
`file:///C:/Users/...` links). With it they point to the repository on GitHub, which
works from both copies and from the file uploaded with the form. The one PDF is copied
to `track_2b/` and to the root; `track_2b/tests/test_copies.py` checks that the two are
the same file and that no link is a local path. With the placeholders in, the draft of
10 October fills 6 pages, the last to 94 % (the line of its last word): the final text
may not grow. **[OWNER: the export method for the final PDF; the page count depends on
it.]**

## 6. The jury's questions

The jury scores Track 2B on five dimensions, 0 to 5 each (25 points), and gives each
dimension guiding questions (hackapertus.ch, jury briefing, read 9 October). Technical
rigour is judged against the maturity level the team declares. Where our documents
answer each question:

| Dimension | Question | Where we answer it | State |
|-----------|----------|--------------------|-------|
| Purposeful use of AI | Is Apertus suited to the task, and is that choice reasoned? | Report §1 and §3 ("why only Apertus"); README, "Why only Apertus"; [use-cases.md](use-cases.md) §2 | Answered |
| | Is the model size justified, 8B where sufficient, 70B where needed? | Report §3 "Why these sizes"; §5 table (70B everywhere, hybrid) | Answered; numbers wait for the final run |
| | Is every other model right-sized? | Report §3 "Other models and coding assistants": none at runtime; spaCy and wordfreq | Answered |
| | Does it say where Apertus fell short? | Report §3 "Where Apertus fell short"; §5 judge reliability; [image-input.md](image-input.md) | Answered |
| Technical rigour | Does it run reproducibly from the documented command? | `make run`; report §7 | Clean checkout passed on Windows and Linux. **[PENDING: CI green on the submitted commit]** |
| | Is the claim backed by evaluation, not a single demo? | Report §5: 20 held-out pairs, two baselines, the official versions | **[PENDING: final run]** |
| | Where optimisation was applied (quantisation, batching, caching), is its effect shown? | Report §3 and §5: the 4-bit build only for development, never mixed; the response cache makes reruns exact and seconds undercount; Write without thinking (24 min against 28 s, 4-bit) | Partly: the cache's and the 4-bit build's effect on quality is not measured, nor the vLLM profile's FP8 KV cache (its memory effect is, report §2) |
| | Are limitations and the use of coding assistants declared? | Report §6; report §3 "Other models and coding assistants"; README team line | **[OWNER: confirm the wording]** |
| | (Maturity level declared) | Report header; README; message §3 | **[OWNER: confirm]** |
| Value, cost and scalability | Is the problem evidenced, or only asserted? | Report §1 (FSO PIAAC, disability law, cantons publishing); [use-case-canton.md](use-case-canton.md) §1 | Answered |
| | Does it name a specific user group? | Report §1: the people who write official texts (trained writers, case workers, clerks, physicians); their readers in §1's first sentence | Answered |
| | Is the running cost proportionate to the benefit per use? | Report §5 "Cost, and ten times the volume" | **[PENDING: review time by stopwatch; a published drafting time, or none found]** |
| | What happens to cost and speed at ten times the volume? | Report §5 "Cost, and ten times the volume" | Answered; more workers neither built nor measured |
| Sovereign deployability | Can it be self-hosted on realistic hardware? | Report §2 target architecture and hardware | Answered: the vLLM profile ran on one NVIDIA L4 24 GB (`track_2b/eval/hardware/`) |
| | Does runtime data leave the user's environment? | Report §2 "What the running system contacts" | Answered |
| | Are weights, licences and dependencies free of blocking terms? | Report §2 licences | Answered |
| | Is it independent of any single commercial provider? | Report §2 (any OpenAI-compatible server) | Answered |
| Implementation feasibility | Does use require a realistic change of work? | [use-case-canton.md](use-case-canton.md) §5; report §8 "Into use" (DOCX missing) | Partly |
| | How far from real use: what must still be built, obtained or approved? | Report §8 "Into use" | Answered |
| | Is there a named first user or group? | Report §8 | **[OWNER: none named yet]** |
| | Do others have the same need? | Report §8; [use-cases.md](use-cases.md) | Answered |

## 7. Before we press Submit

- [ ] Final CSCS run read (PLAN.md WP13, D-M); its numbers in one pass in report §1,
      §5 and §6, README and the video (`eval numbers`, `track_2b/eval/report.md`).
- [ ] No **[PENDING]** or **[OWNER]** left in README.md and track_2b/technical_report.md.
- [ ] Tests and ruff green; CI green on the submitted commit.
- [ ] Report exported to PDF (§5), at most 6 pages, saved as
      `track_2b/RoestigrabenBridgers_Report.pdf` and the same file at the root, committed.
- [ ] Video rendered, uploaded, URL in README, report and form.
- [ ] Repository public; `git log -p -- .env` empty.
- [x] Clean-checkout test on Linux or macOS: clone, `.env`, `make run`, one job
      (Linux, 10 October, commit 6936d05).
- [ ] Form filled and submitted by one of us, by Thu 15 October (G6); deadline Fri 16
      October, 12:00 CEST, no extension.
