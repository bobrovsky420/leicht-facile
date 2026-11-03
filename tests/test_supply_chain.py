"""The supply-chain measures stay in step (docs/architecture.md §10, "Supply chain"): the
release cooldown and its dated exceptions, which expire; Dependabot's three ecosystems
under the same window; every action pinned to a commit and the one download pinned by
its checksum; the security policy with its contact; and the scanners' configuration."""

from __future__ import annotations

import re
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _git_mode(path: Path) -> str:
    """The mode git records for a tracked file (100755: executable), the same on every
    system: a checkout on Windows has no execute bit, the index has."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--stage", "--", path.relative_to(ROOT).as_posix()],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    assert out, f"{path} is not tracked"
    return out.split()[0]


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
    assert set(updates) == {"uv", "github-actions", "docker", "docker-compose"}
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
    assert _git_mode(hook) == "100755", "the hook is executable (git update-index --chmod=+x)"
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
    # uv publish uploads an attestation but creates none, and only one among the files it
    # is given: the wheel is signed first, the pairing is proved by a dry run, and the
    # upload's glob takes the attestation along (0.10.0 and 0.10.1 reached PyPI without).
    sign = release.index("pypi-attestations sign dist/")
    dry_run = release.index("uv publish -v --dry-run")
    publish = release.index("run: uv publish --trusted-publishing always dist/*\n")
    assert sign < dry_run < publish, "signed, paired, then uploaded"
    assert "Found attestation for distribution" in release
    assert "push-to-registry: true" in release, "the image's attestations live in ghcr.io too"
    assert "gh release upload" in release, "the image's bill of materials joins the release"
    policy = _read("SECURITY.md")
    assert "gh attestation verify" in policy
    assert "pypi-attestations verify pypi" in policy


def test_the_contribution_policy_stays_consistent() -> None:
    """The two tiers of CONTRIBUTING.md hold together: MAINTAINERS.md names every author
    of pyproject.toml with a GitHub login in the form the sign-off job greps, the job
    reads that file, the DCO is the unchanged text of version 1.1, and the assignment
    form exists where CONTRIBUTING.md points."""
    maintainers = _read("MAINTAINERS.md")
    login = r"GitHub login `([A-Za-z0-9-]+)`"
    logins = re.findall(rf"^- .*{login}", maintainers, re.MULTILINE)
    assert logins, "without a login the sign-off check would skip nobody"
    # The prose of the file must not read as a login (the job greps the list items).
    assert re.findall(login, maintainers) == logins
    for author in tomllib.loads(_read("pyproject.toml"))["project"]["authors"]:
        assert author["name"] in maintainers, author
    ci = _read(".github/workflows/ci.yml")
    assert "grep -E '^- ' MAINTAINERS.md | grep -oE 'GitHub login `[A-Za-z0-9-]+`'" in ci
    assert 'test("^Signed-off-by: .+ <.+>$")' in ci
    dco = _read("DCO")
    assert dco.startswith("Developer Certificate of Origin\nVersion 1.1\n")
    assert "changing it is not allowed" in dco
    contributing = _read("CONTRIBUTING.md")
    for needed in ("MAINTAINERS.md", "[DCO](DCO)", "docs/assignment.md", "hello@leichtfacile.ch"):
        assert needed in contributing, needed
    assert (ROOT / "docs" / "assignment.md").is_file()
    assert "hello@leichtfacile.ch" in _read("docs/assignment.md")
