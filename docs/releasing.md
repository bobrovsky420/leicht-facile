# Releasing and maintaining

For the maintainers ([MAINTAINERS.md](../MAINTAINERS.md)): how a release is made, how
the language packages, the pins and the sibling repositories are kept, which settings
of the repository the code relies on, and what to do when a step fails. The house rules
are in [CONTRIBUTING.md](../CONTRIBUTING.md); what a release may change is in
[maintenance.md](maintenance.md).

## Before a release

1. `main` is green on every CI job, and no Dependabot pull request you meant to take
   is still open.
2. If prompts, rules or the default model changed since the last evaluation, rerun it
   ([quickstart.md](quickstart.md#the-evaluation)) and update the tables
   (`evaluation.md`, `evaluation-publicai.md`, `model-comparison.md`).
3. In CHANGELOG.md, `## [Unreleased]` becomes `## [<version>] - <YYYY-MM-DD>`, with its
   link `[<version>]: .../compare/v<previous>...v<version>` at the end of the file; no
   empty `## [Unreleased]` stays behind.
4. The version in two places, in the same commit: `pyproject.toml` and `publiccode.yml`
   (`softwareVersion`). The package reads `__version__` from its metadata, and no
   document names the version: the commands install the newest release, and the
   quickstart's one command for a particular release takes a past release as its
   example (0.13.2), which stays as it is. `uv lock` writes
   the new version into `uv.lock` (CI installs `--frozen`), and
   `uv run pytest -q tests/test_release.py` checks all of it.
5. Commit on `main`, push, and wait for CI.

## The tag and the release workflow

The tag `v<version>` on the commit CI passed (`git tag v<version> <sha>`,
`git push origin v<version>`) starts `.github/workflows/release.yml`:

- the wheel job: the tag matches the version, the release test, the wheel built and
  installed in a clean environment where the checker runs, a bill of materials of the
  locked dependencies, the GitHub release with both files, the PyPI attestation signed
  and paired with the wheel (a dry run proves the pairing before the upload), the upload
  by trusted publishing, the provenance attestations, and a check that pypi.org serves
  the provenance;
- then the image job: the image built and checked, pushed to
  `ghcr.io/bobrovsky420/leichtfacile` as `<version>` and `latest`, attested in the
  registry, and its bill of materials added to the release.

Watch it with `gh run watch <id> --exit-status`. Afterwards: the release page holds the
wheel and two `.cdx.json` files; the wheel's provenance page on pypi.org answers,
`https://pypi.org/integrity/leichtfacile/<version>/leichtfacile-<version>-py3-none-any.whl/provenance`;
`gh attestation verify` passes for the wheel and for
`oci://ghcr.io/bobrovsky420/leichtfacile:<version>` (SECURITY.md, "Verifying a
release"); ghcr.io lists both tags.

When a step fails:

- A version on PyPI can never be uploaded again. A failure after the upload means a
  new patch version; the GitHub release of the failed one stays.
- The attestation steps run after publishing: a failure there turns the job red but
  withholds nothing. Check what is missing and rerun the failed jobs
  (`gh run rerun <id> --failed`).
- The very first push of a new package to ghcr.io can be denied right after the push
  creates it; rerunning the failed job passes. A new package starts private: set its
  visibility by hand once.

After the release: the demo (the `leicht-facile-demo` repository) pins the app's
version in its compose file; update it there and run its smoke test before the
upgrade.

## The language packages

`leichtfacile-model-de` and `-fr` are spaCy's models republished unchanged,
`leichtfacile-model-it` the Italian pipeline with the Morph-it! lexicon
(`scripts/model_packages.py`, `scripts/lexicon_package.py`). A bump is three steps, in
this order, because `uv.lock` and CI resolve from PyPI:

1. the table in `pyproject.toml` (`[tool.leichtfacile.spacy-models.<lang>]` with spaCy's
   name, version, the SHA-256 of its wheel and the licence;
   `[tool.leichtfacile.lexicon-models.it]`), on a branch;
2. `.github/workflows/models.yml` run by hand (Actions, Models, Run workflow): one job
   per language, each in its own GitHub environment (`pypi-model-de`, `-fr`, `-it`),
   since PyPI keeps one pending publisher per repository, workflow and environment; a
   wheel already on PyPI is skipped; the Italian build uses the spaCy version of
   `uv.lock`, named in the workflow;
3. the pin in `dependencies`, then `uv lock`. `tests/test_release.py` ties the pins to
   the tables and checks that the checker loads these pipelines.

The language packages are exempt from the dependency cooldown
(`exclude-newer-package` in `pyproject.toml`), since they are pinned to a version
published right before the pin.

## Dependencies and pins

- Dependabot opens grouped pull requests on Mondays (the Python packages, the actions,
  the Dockerfile's images, the model servers' images of `compose.yaml`), each release
  admitted a week after it is public; CI gates them. `uv lock --upgrade` by hand
  respects the same week (`[tool.uv] exclude-newer`); an exception names the release
  and the date after which the window admits it by itself, and
  `tests/test_supply_chain.py` asks for its removal from that day.
- Every action is pinned to a commit, the comment after the hash names the release
  (the test checks the form). gitleaks is pinned by version and SHA-256 in `ci.yml`.
  The Dockerfile's images and the model servers' images are pinned by digest, with the
  tag in a comment next to the pin: read a digest with
  `docker buildx imagetools inspect <image>:<tag> --format '{{.Manifest.Digest}}'`, or
  without Docker from the registry (a token from
  `https://ghcr.io/token?scope=repository:<name>:pull`, then `HEAD
  /v2/<name>/manifests/<tag>` with the OCI index `Accept` header; the digest is the
  `Docker-Content-Digest` header).
- Python: CI tests every version from `requires-python` on (3.12 to 3.14 today). A new
  minor version joins the matrix once the dependencies support it; one leaves at its
  end of life, with `requires-python` and the classifiers.

## Settings of the repository on GitHub

- The ruleset `main`: deletion and non-fast-forward pushes blocked; every CI job a
  required check, by its name: "Lint (ruff)", "Types (mypy)", "Tests (pytest, Python 3.12)", "Tests
  (pytest, Python 3.13)", "Tests (pytest, Python 3.14)", "The service starts without
  its endpoint", "The container image builds, starts and passes the scan", "No secret
  in the whole history (gitleaks)", "The lockfile has no fixable high or critical
  vulnerability (Trivy)", "Every commit of an outside pull request is signed off
  (DCO)". A new CI job is added to the list by hand (Settings, Rules, Rulesets). The
  administrators may bypass the ruleset, which is how the maintainers push to `main`.
- Secret scanning with push protection, Dependabot alerts and private vulnerability
  reporting switched on.
- The environments `pypi-model-de`, `-fr` and `-it` for the language packages.
- On pypi.org, trusted publishers: `leichtfacile` from `release.yml`, each language
  package from `models.yml` with its environment. No token is stored anywhere.
- The packages on ghcr.io are public.
- Locally, `git config core.hooksPath scripts/hooks` runs ruff and gitleaks on the
  staged changes before each commit.

## The repositories and services

- `leicht-facile` (public): the app, this documentation, the workflows above.
- `leicht-facile-web` (private): the site <https://leichtfacile.ch>, published by
  GitHub Pages from its own workflow, with the custom domain. The user's guide's
  pictures are made here and copied there
  (`scripts/guide_screenshots.py --site ../leicht-facile-web/site`).
- `leicht-facile-demo` (private): the gate in front of the public demo; its image is a
  public package on ghcr.io, built on its own tags; it pins the app's version and runs
  on a server driven through a remote Docker context.
- Services: PyPI (the four packages), ghcr.io, the domain `leichtfacile.ch` (the DNS
  records for GitHub Pages and the Search Console verification record must stay), the
  mailbox <hello@leichtfacile.ch>, and the model provider's account that pays for the
  demo. Credentials and recovery codes live in the maintainers' private note, never in
  a repository.

## Stored data and compatibility

- The database schema is versioned with `PRAGMA user_version` (`src/leichtfacile/
  store.py`): the base tables, then one group per change in `_MIGRATIONS`. Never change
  a group once it has shipped; add the next one. A group that rewrites stored JSON gets
  a test with a row of the old shape, and the rewrite test replays every group.
- The audit bundle's `format` field (`leicht-facile/audit-bundle@<n>`) changes its
  number only for an incompatible change of the bundle (maintenance.md).
- A change to a stable surface follows maintenance.md: the CHANGELOG under Changed,
  Removed or Deprecated says what an operator must do, and the old name keeps working
  for the period the policy names.

## When a maintainer joins or leaves

Update `MAINTAINERS.md`, the contacts of `publiccode.yml` and the authors of
`pyproject.toml`; on GitHub the repository's collaborators and the ruleset's bypass
list; on pypi.org the owners of the four packages; the packages on ghcr.io; the domain
and the mailbox; and the private note.
