# Rules for AI agents in this repository

These rules come from the repository owner. They apply to every AI coding agent
working here and can only be relaxed by an explicit instruction from the owner.

## Git

- Never run `git commit` or `git push`. The owner commits.
- After every bigger change, end the reply with a proposed one-line commit message.
- Never add a `Co-Authored-By` line or any other attribution trailer to a proposed
  commit message.

## Typography

- Never use an en dash (U+2013) or an em dash (U+2014) unless the owner explicitly
  asks for it. Use a plain hyphen (-) instead: in prose, in ranges (`5-6`, `20-40`),
  in docs, in code comments and in commit messages.
- Exception: en dashes may be used in presentations, but only when the owner has
  explicitly allowed it for that presentation.

## Project

- Hack Apertus, Track 2B. The organisers require the template's `track_2b/` folder and
  a Makefile at the repository root, where they run `make run`. `track_2b/` holds the
  project (Makefile, README, technical report and its PDF, `data/`, `docs/`, `eval/`,
  `scripts/`, `src/`, `tests/`); the root holds the build and tooling files (Makefile,
  Docker, Compose, `pyproject.toml`, CI), PLAN.md, `video/` and the local untracked
  folders (`.venv/`, `.vscode/`, caches, `.env`). The root Makefile has the targets;
  `track_2b/Makefile` passes every target on to it.
- Write paths from the repository root (`track_2b/docs/rules.md`) in prose, comments
  and code. Markdown link targets are relative to the file that contains them.
- `README.md` exists twice, in the root and in `track_2b/`. Both copies have the same
  text; only relative link targets differ, each written from its own file's folder.
  Change both in the same edit. `track_2b/tests/test_readme.py` checks it.
- Design lives in `track_2b/docs/architecture.md`, the rule specification in
  `track_2b/docs/rules.md`. Keep both in sync with the code.
- The plan (order, dates, gates, cuts) lives in `PLAN.md`. Update it when something is
  implemented (tick its box, add a line to §11 Progress log) and when something new is
  planned (add the item to its work package, the schedule or the open decisions).
- Update `PLAN.md` in place, in the section where the topic lives (PLAN.md §0 lists
  them). Never append a new section, an "Added on ..." block or a revised copy of an
  existing section.
