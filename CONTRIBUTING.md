# Contributing to Leicht·Facile

Thank you for helping. This page says how to set up a checkout, what a change needs
before it is merged, and who holds the rights in what you contribute. How to report a
vulnerability is in [SECURITY.md](SECURITY.md), not here.

## Before you start

- Open an issue for a bug or a proposal before a large change, so that nobody works
  twice. A rule finding you disagree with is an issue too: name the rule id, the
  sentence and the source that says otherwise.
- Never paste a confidential letter or a personal detail into an issue or a pull
  request. Use the sample letters of the app or a public web page.

## Setting up

The project is a Python package managed with uv; it needs Python 3.12 or later.

```bash
uv sync --frozen
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

The tests answer model calls from a fake endpoint, so no key and no model are needed,
and the spaCy models come with the dependencies. Running the app and the evaluation is
described in [docs/quickstart.md](docs/quickstart.md).

## House rules

- Python stays within `[tool.ruff]` of `pyproject.toml` (line length 100); both ruff
  commands above pass before you push.
- Plain hyphens only: no en dash or em dash in prose, docs, comments or commit
  messages.
- Paths are written from the repository root (`docs/rules.md`); Markdown link targets
  are relative to the file that contains them.
- Every notable change gets an entry in [CHANGELOG.md](CHANGELOG.md) under
  `## [Unreleased]`, in the same change: a feature, setting, command or rule, a changed
  behaviour or default, a removal, a fix a user would notice. One or two sentences for
  the people who install and run the app, sorted into Added, Changed, Deprecated,
  Removed, Fixed or Security. Refactors, tests, CI and docs get no entry unless they
  change what a user sees.
- [docs/architecture.md](docs/architecture.md) describes the design and
  [docs/rules.md](docs/rules.md) the rules; a change in the code changes them in the
  same pull request.
- A change comes with its tests.

## Pull requests

Branch from `main`, keep the branch rebased, and send one pull request per change; the
maintainers merge by fast-forward, so the history has no merge commits. The pull request
template lists what a review looks for.

## Who holds the rights

Two kinds of people contribute:

- The maintainers, listed in [MAINTAINERS.md](MAINTAINERS.md), keep the rights in what
  they write and publish it under the Apache License 2.0 by committing it. The two
  sections below do not apply to them.
- Everyone else certifies the origin of every commit with a sign-off and assigns the
  rights in the contribution, as the two sections below describe.

### Sign-off

Every commit of yours carries a line `Signed-off-by: Your Name <you@example.org>` with
your real name; `git commit -s` adds it (in VS Code, the setting `git.alwaysSignOff`).
The line certifies the Developer Certificate of Origin in the file [DCO](DCO) and
accepts the section "Rights in your contribution" below. CI checks the line on every
pull request from outside the maintainers and names the commits that lack it; add it
with `git commit --amend -s` for the last commit or `git rebase --signoff origin/main`
for all of them, then push again. Your name and e-mail address in the sign-off are
public and stay in the history.

### Rights in your contribution

This section applies to every contribution by someone not listed in MAINTAINERS.md. By
signing off a commit you accept it, in the version the `main` branch holds on that day,
for the contribution the commit contains. "Contribution" means the code, text, data and
other material you submit to the project; "assignee" means Alexander Bobrovsky, the
project's main copyright owner.

1. **Assignment.** You assign to the assignee the copyright and all related rights in
   your contribution, for every country and for the whole term of protection. Where
   the law that applies to you does not allow this, you grant the assignee instead an
   exclusive, worldwide, perpetual, irrevocable and transferable licence, with the
   right to sublicense, for every known kind of use of the contribution, among them
   its reproduction, modification, distribution in any form, making it available
   online, and its licensing to others under any terms, open-source or not.
2. **Your own use.** The assignee grants you a non-exclusive, worldwide, perpetual,
   irrevocable, royalty-free licence to use your contribution for any purpose, with
   the right to license it to others under any terms.
3. **Moral rights.** As far as the law allows, you will not assert your moral rights in
   the contribution against the assignee, the project or its users. The project keeps
   your name in its history.
4. **Patents.** You grant the assignee and every recipient of the project a licence
   under the patent claims you can license that your contribution, alone or combined
   with the project, would infringe, on the terms of section 3 of the Apache License
   2.0.
5. **What you promise.** The contribution is your own work, or you say in the commit
   message which parts come from elsewhere and under which licence; you are entitled
   to make this assignment and these grants; and if you made the contribution for your
   employer, or another organisation holds rights in it, that organisation has agreed
   to this section or signs the form in [docs/assignment.md](docs/assignment.md)
   instead.
6. **No other terms.** You submit the contribution under this section and the Apache
   License 2.0 and under no other terms. The project distributes it under the Apache
   License 2.0 and may distribute it under other terms as well.
7. **Law.** Swiss law applies to this section, without its conflict-of-law rules; the
   courts at the assignee's domicile have jurisdiction.

### Substantial contributions

For a substantial contribution (a new module, rule, language or letter, or more than
about 100 changed lines) the maintainers ask you to sign the form in
[docs/assignment.md](docs/assignment.md) before they merge it. The same holds, whatever
the size, when an organisation holds the rights in what you submit, for example your
employer: the organisation signs. Send the signed form to <hello@leichtfacile.ch>; it
stays with the maintainers and is not published.

### AI assistance

You may write with an AI assistant. The person who signs off is responsible for the
contribution as if they had written every line: it must work, follow this page, and
contain no code or text whose licence you do not know.

## Releases

Releases are made by the maintainers. A version bump changes in one commit the version
in `pyproject.toml`, `src/leichtfacile/__init__.py` (`__version__`) and
`publiccode.yml` (`softwareVersion`), and the wheel's URL in every install command of
`docs/quickstart.md`; `## [Unreleased]` in CHANGELOG.md becomes the version's section
with its date and compare link. `tests/test_release.py` checks that they agree. The tag
`v<version>` pushed to GitHub makes `.github/workflows/release.yml` build the wheel,
publish the GitHub release and the PyPI package, and push the container image.
