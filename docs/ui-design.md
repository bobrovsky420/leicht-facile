# Web UI design: the reviewer's workbench

Specification of the redesigned web UI, planned as WP18 (PLAN.md). Designed and
approved by the owner on 7 October 2026; **not implemented yet**. Until it is,
[architecture.md](architecture.md) §7 describes the UI as it is; when WP18 lands,
§7 is rewritten from this file.

The visual reference is a design canvas with six screens (review, reader view and
export, drafts list, new draft, job running, foundations), clickable in its Play
mode: https://claude.ai/artifact/8Js1ncMf4ceXmg3uUcPqCU (private to the owner's
account; shared from its Share menu). Where this file and the canvas differ, this
file wins; §15 lists the differences.

## 1. Why a redesign

Found in a walk through the four pages on 7 October 2026 (screenshots of the start
page, the progress page, the review page and the reader view on a copy of `data/`):

- The start page is a landing page: a hero, four colour-coded cards and a large
  form. Someone who uses the tool every day scrolls past the explanation to reach
  the drafts, which sit under the form.
- The review page spends about 200 px of a 900 px window on its title, two rows of
  coloured pills and the version row before the panes start.
- Colour has stopped carrying meaning: a purple primary button and purple Apertus
  pills, teal code pills, yellow dashed outlines around every unexplained source
  sentence, coloured left borders on blocks and facts. When everything is coloured,
  nothing stands out.
- Blocks are cards with three decision buttons always visible and their findings
  folded away, so the draft does not read as a text and the eye skips controls on
  every line.
- The checks pane stacks seven collapsible cards inside a framed pane; facts that
  share one long source sentence repeat it in full (f06 to f08, f10 to f13 on the
  premium-reduction letter).
- Smaller things: the delete buttons act without asking; the keys j, k, a, e and r
  act on the whole page (WCAG 2.1.4); the progress page repeats the stages in a
  separate usage table.

The goal: a quiet, dense workbench for people in an administration who review
drafts for hours every day.

## 2. Principles and constraints

- **Calm.** White and grey surfaces separated by 1 px lines. One accent, an
  institutional blue, for actions, selection and focus. Red, amber and green only
  for status (findings, facts, decisions, job state), and then as small icons and
  counts with a word, never as large fills.
- **Dense but readable.** 14 px interface text and 32 px controls; the text under
  review stays large (16 px draft, 15 px source). On the review page every pixel of
  height that is not needed goes to the panes.
- **Text before chrome.** The draft reads as a document; details open for the
  selected block only.
- **Keyboard first** on the review page; with the mouse, a block takes at most two
  clicks (select, decide).
- **Same architecture.** Server-rendered Jinja2, one `app.css`, one `app.js`, no
  framework, no build step, no CDN: the fonts are vendored, the image works
  air-gapped. Pages keep working without JavaScript where they do today (§6).
- **Same data.** The view models in `views.py` gain a few fields; the API, the
  schemas, the stored artifacts and the pipeline do not change. The only new route
  is `GET /new`.
- **English and German** interface as today; every new text in both catalogs.
- **WCAG 2.2 AA** (§9).

## 3. Tokens

CSS custom properties on `:root` in `app.css`, prefixed `--lf-`.

### 3.1 Colour

| Token | Value | Use |
|-------|-------|-----|
| `--lf-ink` | `#1A1E23` | Text, headings, icons |
| `--lf-text-2` | `#49515C` | Labels, descriptions (8.0:1 on white) |
| `--lf-muted` | `#646C78` | IDs, captions, counts (5.3:1 on white, 5.0:1 on `--lf-sunken`) |
| `--lf-border-input` | `#8A929D` | Outline of text fields, selects and the selected segment (3.2:1, WCAG 1.4.11) |
| `--lf-border-strong` | `#BCC3CC` | Outline of buttons (their label identifies them) |
| `--lf-border` | `#D7DBE0` | Edges of panes, cards and the app bar |
| `--lf-hairline` | `#E6E9ED` | Strip borders, chip borders, list frames |
| `--lf-divider` | `#EDEFF2` | Rows inside panes and tables |
| `--lf-track` | `#EEF0F3` | Track of a segmented control on white |
| `--lf-track-sunken` | `#EAEDF0` | The same on `--lf-sunken` |
| `--lf-app` | `#F1F3F5` | Page background behind the surfaces |
| `--lf-sunken` | `#F7F8FA` | Pane headers, table heads, footers, row hover |
| `--lf-hover` | `#F1F3F6` | Hover of buttons and menu items |
| `--lf-surface` | `#FFFFFF` | Panes, cards, fields |
| `--lf-accent` | `#1F4E8A` | Primary buttons, links, selection bar, focus ring, the running state (8.3:1 against white, both ways) |
| `--lf-accent-hover` | `#163B6A` | Hover of primary buttons and links |
| `--lf-accent-weak` | `#E9EDF3` | Selected block, linked source sentence, pressed Edit, current version |
| `--lf-accent-tint` | `#F2F4F8` | Checked option of a radio list, the running stage |
| `--lf-accent-faint` | `#F4F6F9` | Blocks that carry the selected fact |
| `--lf-accent-line` | `#A5B8D0` | Border of pressed Edit and of the current version pill |
| `--lf-error` | `#B42318` | Error icons and counts, missing and distorted facts, pressed Reject, danger buttons (6.6:1) |
| `--lf-error-weak` | `#FDEEEC` | Pressed Reject |
| `--lf-error-line` | `#F1B8B2` | Border of pressed Reject and of danger buttons |
| `--lf-warn` | `#B26B00` | Warning icons, the "Needs review" dot (graphics only, 4.2:1) |
| `--lf-warn-text` | `#8A5300` | Warning counts, the "Not explained" tag (6.3:1) |
| `--lf-warn-weak` | `#FFF4E0` | Fill of the "Not explained" tag |
| `--lf-warn-bar` | `#D99A2B` | Bar of a source sentence nobody explained |
| `--lf-ok` | `#1E6B3A` | Present facts, approved blocks, done jobs and stages (6.5:1) |
| `--lf-ok-weak` | `#E8F3EC` | Pressed Approve |
| `--lf-ok-line` | `#9CCBAE` | Border of pressed Approve |
| `--lf-keycap` | `#C9CED6` | Border of keycaps |

The four accent tints are the accent mixed with white (90, 94, 95 and 60 percent).
An installation that changes `--lf-accent` recomputes them (D-X).

Rules:

- Status colour appears only together with a shape (circle, triangle, check, cross)
  and a word or a number.
- No coloured left borders as decoration. A 3 px inset bar marks two things only:
  the selection (accent) and a source sentence nobody explained (amber).
- Apertus, code and the reviewer are told apart by a word and an icon in a grey tag,
  no longer by purple and teal.

### 3.2 Type

| Role | Font | Size / line | Weight |
|------|------|-------------|--------|
| Page title (Drafts, New draft) | IBM Plex Sans | 20/28 | 600 |
| Screen title (the document on the job and review pages) | IBM Plex Sans | 18/24 | 600 |
| Card heading | IBM Plex Sans | 15/22 | 600 |
| Pane heading; table head | IBM Plex Sans | 13/18; 12/16 | 600 |
| Interface text | IBM Plex Sans | 14/20 | 400 |
| Field label | IBM Plex Sans | 12/16 | 500 |
| Caption, count | IBM Plex Sans | 12/16 | 400 |
| Draft block (review) | IBM Plex Sans | 16/24; headings 17/24 | 400; 600 |
| Source sentence (review) | IBM Plex Sans | 15/23; headings 15/22 | 400; 600 |
| IDs (`s0010`, `b008`, `f07`) | IBM Plex Mono | 11/16 | 400 |
| Rule ids; values | IBM Plex Mono | 11/16; 11-12/18 | 600; 400 |
| Reader page | Atkinson Hyperlegible Next (D-V) | 20/32; h1 29/36; h2 23/30 | 400; 700 |

Font stacks: `"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif`;
`"IBM Plex Mono", ui-monospace, Consolas, monospace`; `"Atkinson Hyperlegible Next",
Arial, Helvetica, sans-serif`. Counts and table numbers use
`font-variant-numeric: tabular-nums`.

### 3.3 Spacing, shape, sizes

- Spacing steps: 4, 8, 12, 16, 20, 24, 32 px. Gutters: 20 px in the app bar and the
  page headers, 24 px around page content, 16 px inside panes and cards.
- Radius: 4 chips, tags and keycaps; 6 buttons and fields; 7 and 5 the segmented
  track and its items; 8 cards, menus and radio lists; 11 status badges.
- Heights: app bar 48; summary strip 40; pane header 40; buttons 32 (36 for the one
  primary action of a page, 26 to 30 inside panes); fields 34; table rows at least 52.
- Lines: 1 px everywhere. The only shadow is the menus' (`0 8px 24px
  rgba(16, 24, 40, 0.12)`).
- Focus: `outline: 2px solid var(--lf-accent); outline-offset: 2px` on everything
  focusable, never removed; rows show it inset.
- Motion: only the running stage's spinner, none under `prefers-reduced-motion`.

### 3.4 Fonts to vendor

Into `src/leichtfacile/web/static/fonts/`, as woff2, subsets `latin` and
`latin-ext` (German, French and Italian letters, the Mediopunkt):

| Family | Weights | Licence | Source |
|--------|---------|---------|--------|
| IBM Plex Sans | 400, 500, 600 | SIL OFL 1.1 | Fontsource `@fontsource/ibm-plex-sans`, or IBM's `IBM/plex` releases |
| IBM Plex Mono | 400, 600 | SIL OFL 1.1 | Fontsource `@fontsource/ibm-plex-mono`, or `IBM/plex` |
| Atkinson Hyperlegible Next | 400, 700 | SIL OFL 1.1 | Fontsource `@fontsource/atkinson-hyperlegible-next`, or `googlefonts/atkinson-hyperlegible-next` |

About 14 files of 15 to 30 KB each (an estimate; check when downloading). One
`@font-face` per file with `font-display: swap` and the subset's `unicode-range`.
The licence text of each family goes next to the files (`OFL-IBM-Plex.txt`,
`OFL-Atkinson-Hyperlegible-Next.txt`), and `THIRD_PARTY_NOTICES.md` gains a section
per family with the version used. The download needs the owner's go, with file
names, source and size stated first.

## 4. Components

| Component | Class | Anatomy and states |
|-----------|-------|--------------------|
| App bar | `.appbar` | 48 px, white, bottom border; wordmark, main nav, endpoint indicator, language switch, API link (§5.1) |
| Page header | `.pagehead` | Breadcrumb link (12 px), title, status badge; actions on the right; wraps on narrow windows |
| Summary strip | `.strip` | 40 px band in `--lf-sunken` under a page header, 13 px text, wraps |
| Button | `.btn`, `.btn-primary`, `.btn-quiet`, `.btn-danger`, `.btn-sm` | 32 px. Primary: accent fill, white text. Default: white, `--lf-border-strong`. Quiet: no border, `--lf-text-2`. Danger: white, `--lf-error-line` border, error text. Disabled: 50 percent opacity and `aria-disabled` |
| Segmented control | `.seg`, `.seg-item` | Track `--lf-track` (`--lf-track-sunken` in pane headers). Selected item: white, 1 px `--lf-border-input` outline, weight 600, `aria-pressed` or `aria-current` |
| Tabs | `.tabs` | `role=tablist`, 40 px; selected tab: 2 px accent underline and weight 600 |
| Status badge | `.badge` | 22 px pill, white, 1 px border, 8 px dot: queued hollow grey, running accent, needs review amber, done green, failed red |
| Tag | `.tag` | 18 px, `--lf-hover` fill, 11 px 500, optional 12 px icon: Apertus and Judge (chip), Code (brackets), You (person); "Left out" grey; "Not explained" in `--lf-warn-weak` with `--lf-warn-text` |
| Value chip | `.chip` | Mono 11 to 12 px, `--lf-sunken` fill, hairline border |
| Keycap | `kbd` | Mono 11 px, 1 px `--lf-keycap` border with a 2 px bottom |
| Severity icon | macro `sev(kind)` | Error: red circle with "!"; warning: amber triangle with "!"; note: grey ring with "i"; present: green circle with a check; distorted: red triangle |
| Decision icon | macro `decision(kind)` | Undecided: hollow grey ring; approved: green circle with a check; edited: accent circle with a pencil; rejected: red circle with a cross |
| Field | `.field` | Label above (12/16 500), 34 px control with `--lf-border-input`, hint below (12/16 muted), error below in `--lf-error` with an icon |
| Radio list | `.optlist` | Framed list, one option per row (title 600, description 13/18); the checked row in `--lf-accent-tint` |
| Menu | `details.menu` | Summary styled as a button; panel white, radius 8, shadow; closes on Esc and on a click outside (JS) |
| Pane | `.pane` | Flush column with a 40 px sunken header and its own scroll area; 1 px border between panes |
| Source row | `.seg` | 60 px mono gutter with the id; states: linked, left out, not explained, heading (§5.5) |
| Block row | `.block` | Id gutter, severity column, text, decision column; selected: accent-weak fill and accent bar, details open (§5.5) |
| Fact row | `.fact` | A button: status icon, id, value chip, status word, text clamped to two lines, the judge's note |
| Stepper | `.steps` | Vertical list; icon column with a connector line; title, who tag, state word, description, detail, usage (§5.4) |
| Meter | `.meter` | 4 px track in `--lf-hairline`, accent fill, green when complete |
| Empty state | `.empty` | Centred text with the next action as a button |

Icons are inline SVG from one macro file, `templates/_icons.html`, drawn on a 16 px
grid with `currentColor` strokes where they follow the text colour. Icon-only
buttons carry an `aria-label`; decorative icons `aria-hidden="true"`.

## 5. Screens

### 5.1 Every page: the app bar (`base.html`)

- Left: the wordmark `Leicht·Facile` (16 px 600, the Mediopunkt in the accent),
  a link to `/`. Main nav: **Drafts** (`/`) with a count badge of the jobs in
  `needs_review` (`aria-label` "3 drafts need review") and **New draft** (`/new`).
  The current section has a 2 px accent underline and `aria-current`.
- Right: the endpoint indicator, a dot, "Endpoint" and the configured model name
  (`settings.llm_name`, mono 12). The dot is grey until `app.js` has the `/healthz`
  answer: green when the endpoint is reachable and the model listed, amber when it
  is reachable without the model, red when it is unreachable. The full sentence
  (the existing `js.endpoint.*` texts) goes into the indicator's `title` and
  `aria-label`. `app.js` keeps the answer for 5 minutes in `sessionStorage`, so
  moving between pages does not call the endpoint's model list each time.
- The language switch (EN | DE, as today) and the API link.
- First focusable element: a "Skip to content" link.
- The tagline leaves the header (it opens the empty state, §5.2); the footer leaves
  every page (the disclaimer moves under the drafts list and into the reader view's
  export panel).
- Server side: `_render` adds `review_count` for the badge
  (`Store.count_jobs("needs_review")`, one count query).

### 5.2 Drafts (`/`, `index.html`)

The work queue. It replaces the hero, the four cards and the form; the form moves to
`/new` (D-W).

Layout, at most 1440 px wide with 24 px gutters:

1. Page header: h1 "Drafts", the line "10 drafts. 3 need your review." and the
   primary link button "New draft".
2. Intro strip "How it works" on one line, four numbered steps: Apertus reads the
   text and writes the draft; code checks 41 rules (`rule_count()`) and every value;
   a second model judges and flagged blocks are repaired; you review every block and
   export. A close button hides it, and `localStorage` remembers that per browser.
   Without JavaScript the strip stays and the button is not shown.
3. One white card: a toolbar (search field, status filter as a segmented control
   with counts, language select), the table, a footer line ("10 drafts",
   "Newest first").
4. Under the card: the version and the disclaimer (`site.footer`).

Filters are GET parameters, so they work without JavaScript and survive a reload:
`/?status=needs_review&q=prämien&lang=de`. Status: all (default), `needs_review`,
`running`, `queued`, `done`, `failed`, each with its count. Search: a
case-insensitive substring of the shown title. Language: the document's language
(the source's `lang`, else `config.lang`). `pages.index` lists
`store.list_jobs(200)`, filters in Python and shows at most 50 rows, newest first.

The table is a real `<table>`; column widths at 1440 px:

| Column | Content | From |
|--------|---------|------|
| Document (flexible, at least 280) | Title as a link to `/jobs/{id}`, one line with an ellipsis. Second line, 12 px muted: the source, "Pasted text · 1,960 characters", "Web page · zh.ch", "PDF · antrag.pdf", "Photo". An "Example" tag for example jobs, whose title is shown without the `Example: ` prefix | `Job.title`, `SourceDocument.source` (`type`, `uri`), `EXAMPLE_PREFIX` |
| Language (130) | "German · A2" | the source's `lang` or `config.lang`, `config.level` |
| Pipeline (120) | "P2: full" | `condition.short.*` |
| Status (180) | The badge. Second line: running: the stage and the time so far ("Judge, 1 min 04 s"); queued: "Waiting for the worker"; failed: the first 60 characters of the error, in red | `Job.status`, `Job.stage`, `Job.error` |
| Checks (200) | Error icon and count, warning icon and count, "Facts 9/14"; "Not yet" before the first draft | the review page's numbers (`ReviewView.counts`, `fact_counts`) |
| Review (150) | A 56 px meter and "4 of 21", with ", complete" once the review is complete; "Not yet" | decisions on the final version, its blocks, `ReviewState.completed` |
| Created (150) | "Today", "Yesterday" or "05.10.2026", the time below; the full UTC time in `title` | `Job.created_at`; `app.js` makes the day relative, as today |
| Actions (40) | Row menu (`details.menu`): Open, Reader view, Export Markdown, HTML or audit bundle, Delete (asks first) | existing routes |

Rows highlight on hover; the title is the link, the rest of the row has no click
handler.

Empty states:

- No jobs at all: "No drafts yet", the tagline, one sentence on what to paste, the
  two example letters as buttons that open `/new?example=<id>` with the text filled
  in, and "New draft". This is what judges see until example jobs ship (PLAN.md,
  submission check, risks).
- Nothing matches the filters: "No drafts match. Clear the search or pick another
  status." with a "Clear filters" link to `/`.

View model: `drafts_view(store, jobs, t) -> list[DraftRow]` in `views.py` (D-Y). For
jobs in `needs_review` or `done` it calls `review_view` and keeps the counts; the
others get status and note only. `DraftRow`: `job`, `title`, `is_example`,
`source_line`, `language`, `status_note`, `errors`, `warnings`, `facts_present`,
`facts_total`, `decided`, `blocks`, `complete`, `created_day`, `created_time`.

### 5.3 New draft (`/new`, `new.html`)

- `GET /new` renders the form; `?example=<id>` fills the text area with that
  example. `POST /jobs` stays as it is; on a `SubmissionError` it renders `new.html`
  with status 400, the error above the form and the fields kept (today it renders
  the start page).
- Layout: breadcrumb "Drafts", h1 "New draft", two cards side by side, the source
  flexible and the settings 400 px; stacked under 1000 px.
- **Source card**, header "Source document" with the three source tabs as a
  segmented control (`role=tablist`; the existing tab logic in `app.js`; without
  JavaScript all three panels show, as today):
  - Paste text: label, text area (15/23, at least 420 px high, resizable), under it
    "1,960 of 200,000 characters" (`MAX_TEXT_CHARS`) and a language note: "Detected:
    German" only after an example was loaded (the server detects the language);
    otherwise "The language is detected when the draft is created". Then a row "Try
    an example" with the two examples as link buttons, and "Clear".
  - Web address: label, URL field, the existing hint plus "Only public pages are
    fetched; addresses in private networks are refused" (what `error.private_url`
    enforces).
  - Upload a file: a drop zone with "Drop a file here", "or", and a label styled as
    a button ("Choose a file") for the visually hidden file input; the existing hint
    ("PDF with a text layer, HTML or plain text, up to 15 MB"). After a choice, the
    file name and size show. Dropping needs JavaScript; the label works without it.
- **Settings card**:
  - Language of the document: select (Detect, German, French, "Italian (follows)"
    disabled), as today.
  - Level: radio list, "A2 · Leichte Sprache, FALC" ("Easy language: short
    sentences, one statement each, hard words explained.") and "B1 · Einfache
    Sprache, langage clair" ("Plain language for readers with some reading
    practice."). Field name `level`, unchanged.
  - Pipeline: radio list, "P2 full" with a "Default" tag ("Fact sheet, draft, rule
    check, judge, repair"), "P1 no judge" ("Fact sheet, draft, rule check"), "P0
    baseline" ("One prompt, for comparison"). Field name `condition`, unchanged.
    Under it the stages the choice runs, as small chips with Apertus, code or you
    (from `STEPS_BY_CONDITION`). All three sequences are rendered and CSS shows the
    checked one's (`:has()`), so it works without JavaScript.
  - Title (optional).
  - Models, a closed `<details>`: Writer, Reader (fact sheet), Judge, with the
    configured names as placeholders and the existing hint.
  - The decision mode's fields (§5.7).
  - Footer: "Create draft" (submit, 36 px, full width) and "Cancel" (link to `/`);
    under them the endpoint status, the same answer as in the app bar.

### 5.4 Job running (`job.html`, `_progress.html`)

- Page header: breadcrumb, title, status badge (Queued, Running or Failed). On the
  right "Running for 2 min 01 s · 8,188 tokens" with "The page updates by itself"
  under it (`role=status`), and "Delete draft" (danger, asks first). Summary strip:
  language, level, pipeline; the writer and judge model names (`JobConfig`, else the
  settings).
- Left, the card "Pipeline" (380 px) with "Stage 4 of 6" in its header. One row per
  stage:
  - the state icon: done, a green check; running, an accent spinner; waiting, a grey
    ring; skipped, a dashed ring; failed, a red "!";
  - a connector line to the next stage, green after a done stage;
  - title, who tag (Apertus, Code, You), the state word on the right, the
    description, the detail line (`Step.detail`, as today);
  - new: a usage line, "1 call · 2,813 tokens · 47 s" from the stage's
    `StageUsage`, and "41 rules · no model call" for Check.

  The running stage has `--lf-accent-tint` and `aria-current="step"`. The separate
  usage table goes.
- Right, "Results so far" with "Shown as each stage finishes. The review opens by
  itself when the pipeline is done." Two cards side by side:
  - Fact sheet (Apertus tag, "14 facts"): the five core questions, label above
    answer; then "Facts that must survive", one line each: id, kind (`kind.*`), the
    fact's text with an ellipsis, the normalised value as a chip; the background line
    as today.
  - Draft v{n} (tags Apertus and "Checked by code", "10 errors · 9 warnings"): the
    blocks as text, headings in bold, a severity icon in a gutter for blocks with
    findings; under it "Findings about the whole document, such as missing facts,
    are not marked on a block."
- Failed: an alert on top of the results column (red icon, "The job failed:
  {error}", the existing hint, "Run again from the start"); the failed stage shows
  the error in its detail line, mono 12.
- Polling as today: `app.js` swaps the `_progress.html` fragment every 2 s and
  reloads when the status leaves queued and running. The fragment's root carries
  `data-elapsed` and `data-tokens`; `app.js` copies them into the page header after
  each swap.
- View model: `Step` gains `usage: StageUsage | None`, matched by stage key (Read is
  `understand`); `progress_view` already sums the usage per stage.

### 5.5 Review (`review.html`)

The screen people use all day. At 1101 × 600 px and more the page fits the window
and only the panes scroll, as today.

**Page header, row 1:** breadcrumb "Drafts", the title (one line, ellipsis), the
status badge ("Needs review" or "Done"). On the right:

- the view switch "Review | Reader view" (segmented; links as today, `app.js`
  switches in place);
- the "Export" menu (Markdown, HTML, audit bundle; links as today);
- the save state (`role=status`): "Saved 10:42" from the newest `Decision.at` of the
  stored review, "No decisions saved yet", "Unsaved changes" with an amber dot,
  "Saving...", "Not saved: {detail}";
- "Save review" (primary, `type=submit form="review-form"`: it sits in the header
  and submits the form; Ctrl+S does the same).

**Row 2, the summary strip:** "German · A2: Leichte Sprache, FALC · P2: full";
"Version" with one pill per draft version ("v1 · final · 10 blocking", "v2 · 11
blocking"; the current one in `--lf-accent-weak`; links `?version=`); the repair
rounds and the stop reason; the code-split line when there are splits; on the right
the error icon and count, the warning icon and count, "Facts 9 of 14 present", and
"19,369 tokens · 2 min 22 s model time" in muted text.

**Three panes,** flush, with 1 px borders between them and no gaps or rounded
frames: Source (flex 1), Draft (flex 1.35), Checks (400 px).

**Source pane.**

- Header: "Source", "19 sentences".
- Legend line: "Source of the selected block" (accent-weak swatch with the bar),
  "Not explained 5" (amber bar), "Left out 5" (grey tag).
- Rows: the id in a 60 px mono gutter, then the sentence; headings in bold; extra
  space before a new paragraph. States:
  - linked (the selected block's sources, set by `app.js`): `--lf-accent-weak` and
    the 3 px accent bar;
  - left out: the text in `--lf-muted`, under it the grey "Left out" tag and the
    reason. The reason is shown, no longer only a tooltip, and the text is not struck
    through: the reviewer has to read what was dropped;
  - not explained (FACT-04): the 3 px amber bar and an amber "Not explained" tag,
    instead of the dashed outline.
- `lang` is the document's language.

```html
<p class="seg {{ state }}" id="seg-{{ seg.id }}" data-seg="{{ seg.id }}">
  <span class="sid">{{ seg.id }}</span>
  <span class="seg-text">{{ seg.text }}</span>
  {% if state == "omitted" %}<span class="seg-note"><span class="tag">{{ t('review.tag.left_out') }}</span> {{ reason }}</span>{% endif %}
  {% if state == "unused" %}<span class="seg-note"><span class="tag tag-warn">{{ t('review.tag.unused') }}</span></span>{% endif %}
</p>
```

**Draft pane.**

- Header: "Draft v1", "21 blocks", and the filter control "All 21 | With findings 5 |
  Undecided 17" (`aria-pressed`, the existing `data-filter` buttons).
- One row per block, reading as text: the id gutter (mono 11); a 34 px severity
  column with the worst finding's icon and the count of errors and warnings (a grey
  note icon when there are notes only); the text (16/24, headings 17/24 600, list
  items with a bullet); a 40 px decision column with the decision icon, a hollow ring
  until decided. Rejected blocks: text muted and struck through. Edited blocks show
  the edited text.
- Selecting a block (click, Enter, J or K) gives it the accent-weak fill and the
  accent bar, highlights its sentences in the source pane and scrolls them into view,
  and opens the row:
  - for an edited block, the text area "Edited text", with the original text struck
    through above it;
  - the findings, one per line: severity icon, rule id (mono 600), a tag "Code" or
    "Judge", the message. A suggestion line gets an "Apply" button when the finding
    has `evidence` and a `suggestion` and the evidence occurs in the block text
    (LEX-01's Mediopunkt split today): Apply sets "edited" with the evidence replaced
    by the suggestion;
  - "Carries" with a chip per fact the block carries: the id and the value, else the
    fact's first words;
  - the decision: the three radio inputs styled as buttons with their keys, Approve A,
    Edit E, Reject R; pressed in green, accent and red. "Next undecided N" on the
    right.
- Approve and Reject move the selection to the next undecided block, wrapping to the
  top; Edit keeps it and focuses the text area; choosing the pressed decision again
  clears it.
- Without JavaScript every row is open, as today; the radios are plain radios.
- Footer, sticky: "4 of 21 decided" with a meter, "Approve all undecided", and the
  "Review complete" checkbox.
- The block texts carry the document's `lang`.

```html
<article class="block{% if row.worst %} sev-{{ row.worst }}{% endif %}{% if row.decision %} decided{% endif %}"
         id="blk-{{ b.id }}" data-block="{{ b.id }}" data-segments="{{ b.segment_ids | join(' ') }}"
         data-facts="{{ b.fact_ids | join(' ') }}" tabindex="0">
  <span class="bid">{{ b.id }}</span>
  <span class="block-sev">{{ sev(row.worst) }}<span class="n">{{ counted }}</span></span>
  <div class="block-main">
    <p class="block-text" lang="{{ v.draft.lang }}">{{ b.text }}</p>
    <div class="block-details">
      {# edited text, findings with Apply, "Carries", the decision radios d-{{ b.id }}
         and the text area t-{{ b.id }}, Next undecided #}
    </div>
  </div>
  <span class="block-state">{{ decision(row.decision.decision if row.decision else none) }}</span>
</article>
```

**Checks pane.** Tabs "Facts 9/14 | Findings 14 | Questions 5 | More"
(`role=tablist`, arrow keys move between tabs, `aria-controls`). Without JavaScript
the four panels stack with their headings.

- **Facts:** a summary ("9 of 14 facts present", "facts that must survive"), a
  stacked bar (present green, distorted red, missing red at 55 percent), the counts
  in words, the existing hint. Then the facts, problems first: missing, distorted,
  unchecked, present, then the background facts (`must_keep` false) marked
  "Background only". Each fact is a button: status icon, id, the expected value as a
  chip (`FactRow.expected`), the status word, the text clamped to two lines (the full
  text in `title`), the judge's note with a "Judge" tag. Selecting a fact marks the
  blocks that carry it (`--lf-accent-faint` and the bar) and scrolls to the first.
- **Findings:** the document findings grouped by rule (on the premium-reduction
  letter: FACT-01 4, FACT-02 5, FACT-04 3, FACT-05 1, READ-01 1): the group's worst
  severity icon, the rule id, the rule's title (`RuleSpec.title`, translated, §8), the
  count; under it one line per finding with its reference (fact id or sentence range)
  and the message. A FACT-04 line highlights its sentences in the source; a FACT-01
  or FACT-02 line selects its fact.
- **Questions:** the five core questions, the label (12 px muted) above the answer;
  an answer with sentence ids highlights them, as today.
- **More:** "Left out, with reasons" (what, why, sentence ids; a click highlights
  them), "Glossary", "Measures" (a two-column list with tabular numbers), "Run"
  (writer, reader and judge models, the notes, "Run again from" with its button, and
  "Delete draft", danger, asks first).

View model (`views.py`): `Issue` gains `evidence`, `fact_id` and `segment_ids` (from
the `Finding`; empty for the judge's issues); `ReviewView` gains `facts_sorted` (the
order above), `finding_groups` (`FindingGroup(rule_id, title, worst, issues)`),
`omitted_count`, `unused_count`, `saved_at` (the newest `Decision.at`, or None) and
the current version's blocking count for the reader view's list.

### 5.6 Reader view and export (`review.html`)

`GET /jobs/{id}/preview` stays the fallback without JavaScript.

- The view switch replaces the three panes with two columns, the page and the export
  panel. The page header and the strip stay; the strip's right side says "The text as
  a reader gets it, with your decisions: rejected blocks left out, edits in place."
- **The page:** the existing iframe with the HTML export of the decisions on screen
  (`POST /jobs/{id}/preview`, unsaved ones included), centred on `--lf-app` in a
  white frame at most 760 px wide; the iframe grows to its content, as today, and the
  column scrolls.
- **The export panel** (360 px, white):
  - "Export", "Draft v1 with the saved review."
  - "Format" as a radio list: Markdown `.md` ("Plain text with headings, one sentence
    per line. For a content management system."), HTML `.html` ("A web page in the
    reader layout, ready to print or to publish."), audit bundle `.json` ("Source,
    fact sheet, every draft version, the findings and your decisions.").
  - "Download .html" (primary, full width): the existing export URL with the chosen
    format and version.
  - "Exports use the last saved review. Decisions you have not saved are left out."
    With unsaved decisions on screen, the existing `js.reader_unsaved` text instead.
  - "Before publication", three lines from the review state: "{decided} of {total}
    blocks decided" (undecided blocks stay in, as drafted), "{n} blocking problems in
    v{version}" (the version pill's number), "Review marked complete" or "Review not
    marked complete"; then the disclaimer (`site.footer`).
- The page's typeface: D-V.

### 5.7 Hooks for the decision mode (WP15)

- New draft: after Pipeline, "Document type" (Standard text, Decision letter);
  choosing a decision letter reveals "Addressee" and "Notice", the notice prefilled
  per language from `pipeline/labels.py` (WP15 piece 1; field names from WP15).
- Review: the notice as a fixed banner under the summary strip (`--lf-sunken`, a grey
  "Fixed notice" tag, the text), not a block (WP15 piece 5). The reader view shows it
  where the export writes it.
- Drafts list: a "Decision" tag next to the title, like "Example".
- WP18 is planned first; WP15 then adds its fields to `new.html` and the banner to
  `review.html`.

## 6. Behaviour (`app.js`)

Kept: the source tabs, filling an example, the endpoint check, relative times, the
progress polling, provenance highlighting, decisions, filters, the warning about
unsaved decisions, saving through the API, the reader view in place.

New or changed:

1. The endpoint indicator on every page, its answer cached for 5 minutes in
   `sessionStorage`; the New draft page reads the same answer.
2. Drafts: hiding the intro strip (`localStorage`), submitting the language select
   on change.
3. New draft: the character count, the language note after an example, the file
   name and size after a choice, dropping a file on the drop zone.
4. Job running: copying `data-elapsed` and `data-tokens` into the page header after
   each swap.
5. Review:
   - one selected block at a time; its row opens (`.is-open`), the others close (the
     page carries the `js` class);
   - shortcuts only while the focus is in the draft pane (WCAG 2.1.4): J and K, or
     the arrow keys, move; A, E and R decide; N jumps to the next undecided block.
     Ctrl+S (Cmd+S) saves from anywhere on the page; Esc closes an open menu;
   - Approve and Reject move on to the next undecided block;
   - Apply for a suggestion;
   - the decision column follows the radios;
   - the save state's text and dot, "Saved HH:MM" after a save;
   - the checks tabs, with arrow keys;
   - reader view: the format choice builds the download link; the "Before
     publication" lines follow the decisions on screen.
6. Everything destructive asks first: `data-confirm` on the delete forms, one handler
   (`js.confirm_delete`).

## 7. Server side

- `pages.py`: `GET /` with the parameters `status`, `q` and `lang` (§5.2); `GET /new`
  with `example` (§5.3); `POST /jobs` renders `new.html` on an error; `_render` adds
  `review_count`.
- `views.py`: `DraftRow` and `drafts_view` (§5.2); `Step.usage` (§5.4); the new
  `Issue` fields, `facts_sorted`, `finding_groups`, the counts and `saved_at` (§5.5).
- `store.py`: `count_jobs(status)`, one SQL count.
- `i18n.py`: the rules' titles join the English catalog as `rule.<ID>` (the base id
  without `-DE` or `-FR`), like `finding.<key>`; the other catalogs translate them.
- `export/html.py`: only as D-V decides.
- No change to the API, the schemas, the store layout or the pipeline.

## 8. Interface texts

Every new text in `en.json` and `de.json`; the catalog test fails otherwise. German
in Swiss spelling (ss), plain hyphens only. Fix on the way: `detail.judged` says "1
unsupported statements"; it gets `.one` and `.other` forms.

New keys with their English text (German written during WP18):

```text
site.skip                 Skip to content
site.endpoint             Endpoint
nav.review_count.one      {n} draft needs review
nav.review_count.other    {n} drafts need review

drafts.count.one          {n} draft.
drafts.count.other        {n} drafts.
drafts.to_review.one      {n} needs your review.
drafts.to_review.other    {n} need your review.
drafts.how.title          How it works
drafts.how.read           Apertus reads the text and writes the draft
drafts.how.check          Code checks {count} rules and every value
drafts.how.judge          A second model judges, flagged blocks are repaired
drafts.how.review         You review every block and export
drafts.how.hide           Hide how it works
drafts.search             Search by title
drafts.search_label       Search drafts by title
drafts.filter             Filter by status
drafts.filter.all         All
drafts.lang.all           All
drafts.col.checks         Checks
drafts.col.review         Review
drafts.col.actions        Actions
drafts.source.text        Pasted text · {chars} characters
drafts.source.html        Web page · {host}
drafts.source.pdf         PDF · {name}
drafts.source.image       Photo
drafts.example            Example
drafts.not_yet            Not yet
drafts.facts              Facts {present}/{total}
drafts.reviewed           {decided} of {total}
drafts.reviewed_complete  {decided} of {total}, complete
drafts.today              Today
drafts.yesterday          Yesterday
drafts.running            {stage}, {time}
drafts.actions_for        More actions for {title}
drafts.open               Open
drafts.delete             Delete
drafts.empty.title        No drafts yet
drafts.empty.text         Paste an official text, give a web address or upload a PDF. Or start with an example letter:
drafts.no_match           No drafts match. Clear the search or pick another status.
drafts.clear              Clear filters
drafts.shown              {shown} of {total} drafts
drafts.newest_first       Newest first

new.source                Source document
new.chars                 {n} of {max} characters
new.lang_auto             The language is detected when the draft is created
new.lang_detected         Detected: {lang}
new.clear                 Clear
new.drop                  Drop a file here
new.or                    or
new.choose                Choose a file
new.private_note          Only public pages are fetched; addresses in private networks are refused.
new.settings              Settings
new.doc_lang              Language of the document
new.level.A2.desc         Easy language: short sentences, one statement each, hard words explained.
new.level.B1.desc         Plain language for readers with some reading practice.
new.condition.P2.title    P2 full
new.condition.P2.desc     Fact sheet, draft, rule check, judge, repair
new.condition.P1.title    P1 no judge
new.condition.P1.desc     Fact sheet, draft, rule check
new.condition.P0.title    P0 baseline
new.condition.P0.desc     One prompt, for comparison
new.default               Default
new.stages                Stages that run
new.models_defaults       configured defaults
new.create                Create draft
new.cancel                Cancel

progress.pipeline         Pipeline
progress.stage_of         Stage {i} of {n}
progress.state.done       Done
progress.state.running    Running
progress.state.pending    Waiting
progress.state.skipped    Skipped
progress.state.failed     Failed
progress.usage.one        {n} call · {tokens} tokens · {time}
progress.usage.other      {n} calls · {tokens} tokens · {time}
progress.no_model         {rules} rules · no model call
progress.results          Results so far
progress.results_hint     Shown as each stage finishes. The review opens by itself when the pipeline is done.
progress.running_for      Running for {time} · {tokens} tokens
progress.updates          The page updates by itself
progress.writer           Writer
progress.judge            Judge
progress.doc_findings     Findings about the whole document, such as missing facts, are not marked on a block.

review.saved_at           Saved {time}
review.never_saved        No decisions saved yet
review.blocking_n         {n} blocking
review.sentences.one      {n} sentence
review.sentences.other    {n} sentences
review.blocks.one         {n} block
review.blocks.other       {n} blocks
review.legend.unused_n    Not explained {n}
review.legend.omitted_n   Left out {n}
review.tag.left_out       Left out
review.tag.unused         Not explained
review.tag.code           Code
review.tag.judge          Judge
review.carries            Carries
review.apply              Apply
review.next_undecided     Next undecided
review.edited_text        Edited text
review.no_match           No blocks match this filter.
review.decision.undecided Undecided
review.decision.approved  Approved
review.decision.edited    Edited
review.decision.rejected  Rejected
review.tab.facts          Facts
review.tab.findings       Findings
review.tab.questions      Questions
review.tab.more           More
review.facts_must         facts that must survive
review.facts_counts       {present} present · {distorted} distorted · {missing} missing
review.findings_hint      Findings about the whole document. Findings on single blocks show in the draft.
review.core_hint          The five core questions, answered from the fact sheet.

reader.export_hint        Draft v{version} with the saved review.
reader.format             Format
reader.md.desc            Plain text with headings, one sentence per line. For a content management system.
reader.html.desc          A web page in the reader layout, ready to print or to publish.
reader.json.desc          Source, fact sheet, every draft version, the findings and your decisions.
reader.download           Download {ext}
reader.saved_only         Exports use the last saved review. Decisions you have not saved are left out.
reader.before             Before publication
reader.decided            {decided} of {total} blocks decided
reader.decided_hint       Undecided blocks stay in, as drafted.
reader.blocking.one       {n} blocking problem in v{version}
reader.blocking.other     {n} blocking problems in v{version}
reader.complete           Review marked complete
reader.not_complete       Review not marked complete
reader.complete_hint      Mark it complete in the review once every block is decided.

js.unsaved                Unsaved changes
js.saved_at               Saved {time}
js.confirm_delete         Delete this draft and everything it produced? This cannot be undone.

rule.<ID>                 the rule's title from RuleSpec.title, merged like finding.<key>
```

Existing keys used again: `site.tagline` (empty state), `site.footer`, `site.drafts`,
`site.new`, `jobs.document`, `jobs.status`, `jobs.created`, `index.lang`,
`index.level`, `index.condition`, `index.tab.*`, `index.text.*`, `index.url.*`,
`index.file.label`, `index.examples`, `index.models*`, `review.facts_present`,
`review.reader.hint`, `review.export*`, `status.*`, `condition.short.*`, `level.*`,
`who.*`, `step.*`, `detail.*`, `fact.*`, `kind.*`, `core.*`, `js.endpoint.*`,
`js.reader_unsaved`.

Probably unused afterwards (remove once `grep` confirms): `index.title`,
`index.lede`, `index.how.*`, `index.new`, `index.condition.P0` to `P2`,
`index.submit`, `index.endpoint`, `jobs.none`, `usage.*`, `review.keys`,
`review.legend.omitted`, `review.legend.unused`, `review.omitted_title`,
`review.unused_title`, `progress.findings`.

## 9. Accessibility (WCAG 2.2 AA)

- Landmarks: `header`, `nav`, `main`, `aside`; the skip link; one `h1` per page and
  headings in order.
- Only real controls: `a`, `button`, `input`, `select`, `textarea`. A block row is an
  `article` with `tabindex="0"`; Enter selects it. Filters use `aria-pressed`, the
  view switch `aria-current`, the tabs the WAI-ARIA tabs pattern.
- Focus visible everywhere (2 px accent ring); sticky headers and footers do not
  cover the focused element (`scroll-margin`).
- Colour is never the only signal: every status has a shape and a word or a number;
  icon-only controls have an `aria-label`.
- Contrast: text at least 4.5:1, large text 3:1, field outlines, the selected
  segment and the selection bar at least 3:1 against their background (§3.1).
- Targets at least 24 × 24 px (2.5.8); icon buttons are 28 to 32 px.
- Single-key shortcuts act only while the focus is in the draft pane (2.1.4).
- Reflow: at 320 px wide and at 200 percent zoom nothing is cut off; the drafts table
  scrolls inside its card, as data tables may.
- Language: the document's title, sentences, blocks, facts and glossary carry the
  document's `lang`; the interface carries the interface language.
- Live regions: the save state, the elapsed time while a job runs, the endpoint
  status (`role=status`, polite); the stepper itself is not live.
- Motion: the spinner stops under `prefers-reduced-motion`.
- The reader iframe has a `title`; unsaved decisions warn before leaving, as today;
  every delete asks first.

## 10. Responsive behaviour

- At 1101 × 600 px and more the review page fits the window; below, the panes stack
  in the order Source, Draft, Checks and the page scrolls (the breakpoint of today's
  `app.css`).
- The app bar and every toolbar wrap; the summary strip wraps.
- Drafts: the table keeps its columns and scrolls sideways inside the card under
  1170 px.
- New draft and Job running: the two columns stack under 1000 px.
- The reader view's export panel moves under the page under 1000 px.

## 11. Files

| File | Change |
|------|--------|
| `web/templates/base.html` | Rewritten: app bar, skip link, no footer |
| `web/templates/_icons.html` | New: icon macros |
| `web/templates/index.html` | Rewritten: the drafts list |
| `web/templates/new.html` | New: the form, moved from `index.html` |
| `web/templates/job.html`, `_progress.html` | Rewritten: header, stepper with usage, result cards |
| `web/templates/review.html` | Rewritten: header, strip, panes, checks tabs, reader view with export panel |
| `web/static/water.css` | Deleted |
| `web/static/app.css` | Rewritten: tokens, `@font-face`, components, screens |
| `web/static/fonts/` | New: woff2 files and licence texts |
| `web/static/app.js` | Extended (§6) |
| `web/pages.py`, `web/views.py`, `web/i18n.py`, `store.py` | §7 |
| `export/html.py` | Only per D-V |
| `web/locales/en.json`, `de.json` | §8 |
| `tests/web/test_ui.py`, `test_web.py`, `test_i18n.py` | §12 |
| `docs/architecture.md` §7, `README.md`, `docs/demo-video.md`, `THIRD_PARTY_NOTICES.md`, `PLAN.md` | Updated when WP18 lands |

Hooks that `app.js` and the tests rely on keep their names: the classes `block`,
`seg`, `fact`, `step-<state>`, `version current`; the attributes `data-filter`,
`data-block`, `data-segments`, `data-facts`, `data-fact`, `data-version`; the ids
`review-form`, `reader-pane`, `reader-frame`, `example-texts`, `endpoint-status`.

## 12. Tests and checks

To update:

- `test_ui.py`: the start-page test splits into one for the drafts list (examples in
  the empty state, the intro strip with the rule count, the model name in the app
  bar) and one for `/new` ("Try an example", `id="example-texts"`); the progress
  tests keep `step-<state>`; the review test keeps `version current`, `data-filter`,
  "Reader view" and "0 of N decided".
- `test_web.py`: the form round trip now starts at `/new`; a rejected submission
  answers 400 with `new.html`.
- `test_i18n.py`: `rule.<ID>` for every rule id among the keys built from data.

To add:

- the drafts list: filters by status, search and language; counts; an example job
  without the prefix and with its tag; the empty state links to `/new?example=`;
- `/new?example=<id>` fills the text area;
- the review count in the app bar;
- progress steps carry their usage;
- the review view: document findings grouped by rule with titles, facts sorted with
  problems first, Apply offered only when the evidence is in the block text,
  `saved_at` from the stored decisions;
- no template refers to anything outside `/static` (no `http` in a `src` or
  `href` of a stylesheet, script or font).

Checks before WP18 counts as done:

- Screenshots with a headless browser (`msedge --headless=new --screenshot=<file>
  --window-size=<w>,<h> <url>` against `python -m leichtfacile serve` on a copy of
  `data/`, with `LLM_BASE_URL` pointing at an unreachable port so no model is
  called), in English and German, at 1440 × 900,
  1280 × 800, 1024 × 768 and 390 × 844: the empty list, the list with jobs, New draft
  with an example, a queued, a running and a failed job, a review with a selected
  block in each checks tab, the reader view.
- Without JavaScript (Edge with `--blink-settings=scriptEnabled=false`): the list and
  its filters, submitting a new draft, a readable review page with every row open.
- Keyboard only: review five blocks with the keys alone; the tab order; the focus
  ring; the shortcuts silent outside the draft pane.
- Contrast of every token pair in §3.1, by script or by hand.
- `make run` from a clean checkout serves the UI without a request to another host.

## 13. Build order, effort, cut order

| Step | What | Hours |
|------|------|-------|
| 0 | D-V to D-Y decided; the owner's go for the font download | 0.5 |
| 1 | Foundations: `app.css` with tokens and components, water.css removed, fonts and licence texts, `_icons.html`, the app bar | 3 |
| 2 | Review screen: template, view model fields, `app.js` behaviour | 7 |
| 3 | Reader view with the export panel; D-V | 1.5 |
| 4 | Drafts list: parameters, `drafts_view`, table, empty states, intro strip, row menu, delete confirmation | 3.5 |
| 5 | New draft at `/new`: radio lists, stages, drop zone, error path | 2 |
| 6 | Job running: stepper with usage, result cards, failed state | 2 |
| 7 | Texts: every new key in EN and DE, rule titles, dead keys removed | 2 |
| 8 | Tests, screenshots, keyboard, no-JavaScript and contrast passes, fixes | 3 |
| 9 | Docs: architecture §7, README, demo-video.md, THIRD_PARTY_NOTICES.md, PLAN.md | 1 |
| | Total | about 25 |

The review screen comes first: it is the video's main scene. The redesign touches no
pipeline file, so it runs next to the prompt freeze and the final evaluation without
disturbing them (PLAN.md §13.3 has the days).

Cut order if G4 comes close:

1. The drafts list's extras: the language filter, the row menu, the Checks and
   Review columns.
2. The job page beyond the stylesheet: today's markup on the new tokens.
3. New draft as its own page: the form stays above the list, restyled.
4. The reader view's export panel: the iframe and the Export menu stay.

Never cut once started: the stylesheet, the app bar and the review screen. If the
review screen cannot be finished by G4, WP18 is reverted as a whole rather than
shipping a half-styled review page.

## 14. Open decisions

| ID | Question | Recommendation |
|----|----------|----------------|
| D-V | Atkinson Hyperlegible Next for the reader view and the HTML export? | Yes in the reader view: the vendored font, injected only into the preview response. In the HTML export the stack names it first and falls back to Arial and Helvetica as today, without embedding the font, so exported files stay small. |
| D-W | New draft as its own page at `/new`, the start page becomes the drafts list? | Yes. `POST /jobs` and the API stay; the demo's "paste a letter" scene starts at `/new`, one click from the list. |
| D-X | The accent colour and the density as settings? | No settings in v1: the accent is one CSS variable with its four tints, which an installation can override; the density stays "comfortable". Both go to WP17 if reviewers ask. |
| D-Y | How the drafts list gets its per-row checks and review progress | Computed per request with `review_view` for the at most 50 rows shown; a stored summary per job only if the page needs more than 300 ms with 50 jobs. |

## 15. Differences from the canvas

- Fields and the selected segment are outlined in `--lf-border-input` (`#8A929D`)
  for WCAG 1.4.11; the canvas draws `#BCC3CC`.
- The drafts list is a real `<table>`; the canvas lays it out as a grid of `div`s.
- Only the rows "Individuelle Prämienverbilligung 2027" and "Réduction individuelle
  des primes 2027" of the canvas's drafts list are real jobs; the others are sample
  rows built from the evaluation topics, with made-up counts.
- The job page's time and tokens in the header come from the polled fragment
  (`data-elapsed`, `data-tokens`).
- "Save review" in the header submits the review form through `form="review-form"`.
- The shortcuts act only while the focus is in the draft pane; the canvas binds them
  to the selected block.
- The canvas's accent and density controls are design levers, not product settings
  (D-X).

## 16. Not in this package

- French and Italian interface catalogs (GAP-17, WP17).
- Settings for the accent or the density (D-X).
- Autosave, and saving decisions without JavaScript (reading the review works without
  it; saving needs it today and still will).
- User accounts, roles, assigning drafts to reviewers.
- Pagination beyond 50 rows; sorting by other columns.
- A print stylesheet for the review page.
