"""The version lives in pyproject.toml, the package's __version__ and publiccode.yml, and
both README copies and track_2b/docs/quickstart.md name the release wheel of that version
in their install commands (AGENTS.md). A version bump that misses one of them fails here,
before the tag (.github/workflows/release.yml runs this file too)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from leichtfacile import __version__

ROOT = Path(__file__).resolve().parents[2]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
WHEEL_URL = (
    "https://github.com/bobrovsky420/leicht-facile/releases/download/"
    f"v{VERSION}/leichtfacile-{VERSION}-py3-none-any.whl"
)


def test_the_package_has_the_project_version() -> None:
    assert __version__ == VERSION


def test_publiccode_has_the_project_version() -> None:
    text = (ROOT / "publiccode.yml").read_text(encoding="utf-8")
    assert re.search(r'^softwareVersion: "([^"]+)"$', text, re.MULTILINE)[1] == VERSION


@pytest.mark.parametrize("doc", ["README.md", "track_2b/README.md", "track_2b/docs/quickstart.md"])
def test_the_install_commands_name_the_wheel_of_this_version(doc: str) -> None:
    text = (ROOT / doc).read_text(encoding="utf-8")
    urls = re.findall(r"https://github\.com/\S+?\.whl", text)
    assert urls and set(urls) == {WHEEL_URL}
