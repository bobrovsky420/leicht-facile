# Maintenance and support policy

For the people who install and run Leicht·Facile and for those who decide whether to:
who maintains it, what we commit to, what stays stable from one release to the next,
what a release may change until version 1.0 and after it, and what 1.0 means. How to
contribute is in [CONTRIBUTING.md](../CONTRIBUTING.md), how a release is made in
[releasing.md](releasing.md), how to report a vulnerability in
[SECURITY.md](../SECURITY.md).

## Who maintains it

The maintainers named in [MAINTAINERS.md](../MAINTAINERS.md), as a community project
(`maintenance.type: community` in [publiccode.yml](../publiccode.yml)), on a best-effort
basis and without a fee. The project's address is <hello@leichtfacile.ch>; bugs and
proposals go to the issues of the repository, vulnerabilities to the private channels
SECURITY.md names.

## What we commit to

- A vulnerability report gets an answer within five working days and a fix within 90
  days, sooner when the risk asks for it (SECURITY.md).
- Any other issue gets an answer within ten working days. Whether and when it is fixed
  depends on the maintainers' time; the answer says what to expect.
- A problem that stops the app from working, or that loses or corrupts a user's data,
  is fixed in a patch release as soon as the fix is ready. Other changes wait for the
  next release; there is no fixed release cadence.
- Supported is the latest release, on PyPI and on ghcr.io, on the Python versions CI
  tests (3.12 to 3.14 today). Updating is described in
  [quickstart.md](quickstart.md#updates); a newer release brings the database up to
  date on its first start.
- A service level with guaranteed times is not part of this policy. An organisation
  that needs one contracts it with a maintainer or with any third party of its choice;
  the licence needs no permission for that.

## What stays stable

The surfaces an organisation builds on. A release that changes one of them says so in
[CHANGELOG.md](../CHANGELOG.md), under the rules of the next two sections.

- **The command line:** the commands of `leichtfacile` (`setup`, `preset`, `config`,
  `serve`, `check-llm`, `ingest`, `check`, `simplify`, `eval`) and their options.
- **The settings:** the sections and keys of the settings file, the
  `LEICHTFACILE_<SECTION>__<KEY>` variables, the keys read from `.env`, and where the
  file lives (`leichtfacile config path`), as [configuration.md](configuration.md)
  describes them.
- **The HTTP API** under `/api/v1` ([architecture.md §7](architecture.md#7-web-application)),
  the probes `/healthz` and `/readyz`, and the names of the metrics of `/metrics`.
- **The exports:** Markdown, HTML, Word, and the audit bundle with its `format` field
  (`leicht-facile/audit-bundle@1`), whose number changes only with an incompatible
  change of the bundle.
- **The rules:** the rule ids of [rules.md](rules.md) and the keys of their findings.
- **The data directory:** its files (`leichtfacile.sqlite`, with the cache on
  `llm_cache.sqlite`) and the database schema, which the app migrates forward by
  itself.
- **The container image:** port 8000, the unprivileged user, the settings through
  environment variables, the health check.
- **The package names:** `leichtfacile` and the language packages
  `leichtfacile-model-de`, `-fr` and `-it`.

Not stable, and changed in any release without notice: the Python modules (the package
is an application, not a library; `import leichtfacile` is no API), the prompts and
their examples, the model presets and their prices (they follow the providers), the
HTML, CSS and wording of the web UI, the texts of messages and findings, and the
evaluation harness's outputs.

## Until 1.0

Versions 0.x. A minor release (0.11 to 0.12) may change a stable surface. When it does:

- the CHANGELOG says so under Changed, Removed or Deprecated, with what an operator
  must do;
- stored data is migrated by the app on its first start, never by hand; the app keeps a
  copy of the database as it was before, and an older release refuses a database a newer
  one has written, so going back means restoring that copy ([quickstart.md](quickstart.md#updates));
- a renamed setting, command or route keeps working under its old name for one more
  minor release, with a warning, unless the CHANGELOG says why it cannot.

A patch release (0.12.1) changes no stable surface.

## From 1.0

Semantic versioning: a major release may change or remove a stable surface, a minor
release adds without breaking, a patch release fixes.

- A surface on its way out is deprecated first: named in the CHANGELOG under
  Deprecated with the release that removes it, and announced by the app where the
  surface can carry it (a warning at startup for a setting or command, response
  headers for an API route). It keeps working for at least two minor releases or six
  months, whichever is longer, before a major release removes it.
- Stored data is migrated forward across a major release too; the audit bundle's
  format number changes only in a major release, and the app keeps reading the
  previous number.
- Supported is the latest minor release of the latest major; after a new major, the
  previous major gets security fixes for six months.

## What 1.0 means

1.0 is declared when:

- the stable surfaces listed above have not changed across two consecutive minor
  releases;
- a second maintainer holds release rights, so no release depends on one person;
- CI runs a type checker and keeps a committed description of the HTTP API equal to
  the code;
- an organisation runs the app in production, or the public demo has run through a
  quarter.

## Licensing

Every release made is under the Apache License 2.0 and stays so: the licence is
irrevocable. The project is published under a licence the Open Source Initiative
approves. Who holds the rights in the code, and how contributions are taken, is in the
README's licence section and in CONTRIBUTING.md.
