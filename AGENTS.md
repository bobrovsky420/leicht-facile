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

- Hack Apertus, Track 2B. The template's `track_2b/` contents are the repository
  root; do not create a `track_2b/` subfolder.
- Design lives in `docs/architecture.md`, the rule specification in `docs/rules.md`.
  Keep both in sync with the code.
- The plan (order, dates, gates, cuts) lives in `PLAN.md`. Update it when something is
  implemented (tick its box, add a line to §11 Progress log) and when something new is
  planned (add the item to its work package, the schedule or the open decisions).
- Update `PLAN.md` in place, in the section where the topic lives (PLAN.md §0 lists
  them). Never append a new section, an "Added on ..." block or a revised copy of an
  existing section.
