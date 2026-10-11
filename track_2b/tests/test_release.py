"""The version lives in pyproject.toml, the package's __version__ and publiccode.yml, and
track_2b/docs/quickstart.md names the release wheel of that version in its install
commands (AGENTS.md); the READMEs link there instead of naming the wheel. A version bump
that misses one of them fails here, before the tag (.github/workflows/release.yml runs
this file too)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

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


def test_the_install_commands_name_the_wheel_of_this_version() -> None:
    text = (ROOT / "track_2b/docs/quickstart.md").read_text(encoding="utf-8")
    urls = re.findall(r"https://github\.com/\S+?\.whl", text)
    assert urls and set(urls) == {WHEEL_URL}
