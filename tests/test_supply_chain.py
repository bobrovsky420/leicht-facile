"""The supply-chain measures stay in step (docs/architecture.md §10, "Supply chain"): the
release cooldown and its dated exceptions, which expire; Dependabot's three ecosystems
under the same window; every action pinned to a commit and the one download pinned by
its checksum; the security policy with its contact; and the scanners' configuration."""

from __future__ import annotations

import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_new_releases_wait_a_week_and_dated_exceptions_expire() -> None:
    """[tool.uv] exclude-newer keeps a release out until it is a week old. The project's
    own language packages are exempt for good (pinned to an exact version, published right
    before the pin); any other exception carries the date after which the window admits
    the release by itself, and this test asks for its removal from that day on."""
    uv = tomllib.loads(_read("pyproject.toml"))["tool"]["uv"]
    assert uv["exclude-newer"] == "7 days"
    own = {"leichtfacile-model-de", "leichtfacile-model-fr", "leichtfacile-model-it"}
    for package, until in uv["exclude-newer-package"].items():
        if package in own:
            assert until is False, package
            continue
        assert isinstance(until, str), f"{package}: an exception names a date or is dropped"
        expiry = datetime.fromisoformat(until)  # uv reads the date as text
        assert expiry.tzinfo is not None, f"{package}: the date needs its time zone (Z)"
        assert datetime.now(UTC) < expiry, (
            f"the cooldown exception for {package} expired on {expiry:%d %B %Y}: remove it "
            "from exclude-newer-package in pyproject.toml and run `uv lock`"
        )


def test_dependabot_covers_the_lockfile_the_actions_and_the_images_under_the_same_window() -> None:
    config = yaml.safe_load(_read(".github/dependabot.yml"))
    updates = {u["package-ecosystem"]: u for u in config["updates"]}
    assert set(updates) == {"uv", "github-actions", "docker"}
    for ecosystem, update in updates.items():
        assert update["schedule"]["interval"] == "weekly", ecosystem
        assert update["cooldown"]["default-days"] == 7, ecosystem


def test_every_action_is_pinned_to_a_commit_and_the_download_by_its_checksum() -> None:
    for path in WORKFLOWS:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "uses:" in line and not line.lstrip().startswith("#"):
                assert re.search(r"uses: [\w./-]+@[0-9a-f]{40} # v\d", line), (path.name, line)
    ci = _read(".github/workflows/ci.yml")
    assert re.search(r"GITLEAKS_VERSION: \d+\.\d+\.\d+$", ci, re.MULTILINE)
    assert re.search(r"GITLEAKS_SHA256: [0-9a-f]{64}$", ci, re.MULTILINE)
    assert "sha256sum --check" in ci
    assert "fetch-depth: 0" in ci, "the secret scan reads the whole history"
    assert "scan-type: fs" in ci, "the lockfile scan"


def test_the_security_policy_names_the_contact_and_the_scanners_are_configured() -> None:
    policy = _read("SECURITY.md")
    assert "hello@leichtfacile.ch" in policy
    assert "https://github.com/bobrovsky420/leicht-facile/security/advisories/new" in policy
    gitleaks = tomllib.loads(_read(".gitleaks.toml"))
    assert gitleaks["extend"]["useDefault"] is True
    assert all(a["regexTarget"] == "line" for a in gitleaks["allowlists"])
    hook = ROOT / "scripts" / "hooks" / "pre-commit"
    assert hook.stat().st_mode & 0o111, "the hook is executable"
    assert "gitleaks git --pre-commit --staged" in hook.read_text(encoding="utf-8")


def test_the_release_attests_its_artifacts_and_ships_their_bills_of_materials() -> None:
    """release.yml attests the wheel and the image with GitHub's provenance action, checks
    that PyPI holds the wheel's own attestation, and attaches a CycloneDX bill of materials
    for each, attested too; SECURITY.md tells a reader how to verify a download."""
    release = _read(".github/workflows/release.yml")
    assert release.count("uses: actions/attest-build-provenance@") == 2, "the wheel and the image"
    assert release.count("uses: actions/attest-sbom@") == 2, "one bill of materials each"
    assert release.count("attestations: write") == 2, "both jobs may write attestations"
    assert release.count("format: cyclonedx") == 2
    assert "https://pypi.org/integrity/leichtfacile/" in release
    assert "push-to-registry: true" in release, "the image's attestations live in ghcr.io too"
    assert "gh release upload" in release, "the image's bill of materials joins the release"
    policy = _read("SECURITY.md")
    assert "gh attestation verify" in policy
    assert "pypi-attestations verify pypi" in policy
