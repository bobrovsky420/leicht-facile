"""The container image (Dockerfile, .dockerignore, compose.yaml, the workflows) stays in
step with the project: the Python of .python-version, the server's default port, the
image's name wherever it is written, the version its tag names in the docs (as
test_release.py keeps the wheel's), and a build context that holds the package alone, so
that a key in a checkout's .env never lands in an image."""

from __future__ import annotations

import re
from pathlib import Path

from leichtfacile.config import Server
from tests.test_release import VERSION

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "ghcr.io/bobrovsky420/leichtfacile"
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_the_image_runs_the_pinned_python_and_a_pinned_uv() -> None:
    python = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    bases = re.findall(r"^FROM python:(\S+)", DOCKERFILE, re.MULTILINE)
    assert len(bases) == 2 and set(bases) == {f"{python}-slim"}, bases
    assert re.search(r"^COPY --from=ghcr\.io/astral-sh/uv:\d+\.\d+\.\d+ ", DOCKERFILE, re.MULTILINE)


def test_the_image_listens_on_the_default_port() -> None:
    port = Server().port
    assert f"\nEXPOSE {port}\n" in DOCKERFILE
    assert f"http://127.0.0.1:{port}/healthz" in DOCKERFILE
    assert f':{port}:{port}"' in _read("compose.yaml")


def test_the_build_context_holds_the_package_alone() -> None:
    """.dockerignore is an allowlist, and the Dockerfile copies from it alone."""
    lines = [line for line in _read(".dockerignore").splitlines() if line and line[0] != "#"]
    assert lines[0] == "*"
    allowed = {line[1:].rstrip("/") for line in lines if line.startswith("!")}
    assert allowed == {"pyproject.toml", "uv.lock", "README.md", "LICENSE", "src"}
    copies = re.findall(r"^COPY (?!--from=)(.+?) \S+$", DOCKERFILE, re.MULTILINE)
    assert copies, "the Dockerfile copies from the build context"
    for sources in copies:
        for source in sources.split():
            assert source.rstrip("/") in allowed, source


def test_the_image_name_and_the_version_agree() -> None:
    """release.yml publishes the image, compose.yaml pulls it, and the docs name it with
    the tag of this version or `latest`."""
    release = _read(".github/workflows/release.yml")
    assert re.search(rf"^\s+IMAGE: {re.escape(IMAGE)}$", release, re.MULTILINE)
    assert f"image: {IMAGE}:${{LEICHTFACILE_VERSION:-latest}}" in _read("compose.yaml")
    for doc in ("README.md", "docs/quickstart.md", "docs/architecture.md"):
        text = _read(doc)
        assert IMAGE in text, doc
        tags = re.findall(re.escape(IMAGE) + r":([\w.-]+)", text)
        assert set(tags) <= {VERSION, "latest"}, (doc, tags)
    assert VERSION in re.findall(re.escape(IMAGE) + r":([\w.-]+)", _read("docs/quickstart.md"))


def test_ci_starts_the_image_as_the_serve_job_does() -> None:
    """The container job runs the image with the same provider and preset variables as
    the native serve job, plus the login the image demands, and scans it."""
    ci = _read(".github/workflows/ci.yml")
    assert ci.count("LEICHTFACILE_PRESETS__CI__MODELS__WRITER: any-model") == 2
    assert "LEICHTFACILE_AUTH__TOKEN: ci-token" in ci
    assert "docker build --tag leichtfacile:ci ." in ci
    assert re.search(r"uses: aquasecurity/trivy-action@[0-9a-f]{40} # v\d", ci)
