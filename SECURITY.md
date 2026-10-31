# Security policy

## Reporting a vulnerability

Please report a vulnerability privately, not in a public issue:

- through GitHub's private vulnerability reporting:
  <https://github.com/bobrovsky420/leicht-facile/security/advisories/new>, or
- by e-mail to <hello@leichtfacile.ch>.

Say what you found, how to reproduce it and, if you know, which versions it affects. We
answer within five working days, keep you informed, and aim to publish a fix within 90
days of the report, sooner when the risk asks for it. We name you in the release notes
unless you prefer otherwise.

## What is in scope

- The `leichtfacile` package on PyPI and the wheel of each GitHub release.
- The container image `ghcr.io/bobrovsky420/leichtfacile` and `compose.yaml`.
- The language packages `leichtfacile-model-de`, `-fr` and `-it`, as this repository
  builds them (`scripts/model_packages.py`, `scripts/lexicon_package.py`).
- This repository's workflows.

Out of scope: the text a model writes (a draft is reviewed by a person by design), the
model providers' endpoints and the model servers' images (vLLM, llama.cpp), which belong
to their projects, and findings that need an attacker on the machine the app runs on.

## Supported versions

The latest release, on PyPI and on ghcr.io. `uvx leichtfacile` runs it; the other ways
of installing update by hand ([docs/quickstart.md](docs/quickstart.md#updates)).

## How the repository guards its supply chain

Pinned, hashed dependencies installed frozen; actions pinned to commits; trusted
publishing to PyPI; a one-week cooldown on new releases; weekly dependency updates;
a secret scan of the whole history and a vulnerability scan of the lockfile and the
image on every change; no download at runtime. The details and the repository settings
that go with them: [docs/architecture.md §10](docs/architecture.md#10-deployment-and-sovereignty),
"Supply chain".
