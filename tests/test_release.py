"""The version lives in pyproject.toml, the package's __version__ and publiccode.yml, and
docs/quickstart.md names the release wheel of that version in its install
commands (AGENTS.md); the README links there instead of naming the wheel. A version bump
that misses one of them fails here, before the tag (.github/workflows/release.yml runs
this file too)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from leichtfacile import __version__

ROOT = Path(__file__).resolve().parents[1]
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
    text = (ROOT / "docs/quickstart.md").read_text(encoding="utf-8")
    urls = re.findall(r"https://github\.com/bobrovsky420/\S+?\.whl", text)
    assert urls and set(urls) == {WHEEL_URL}


def test_no_dependency_is_given_by_url() -> None:
    """PyPI refuses a package whose dependencies name a URL: the spaCy models come from
    PyPI as leichtfacile-model-de and -fr (scripts/model_packages.py)."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert not [d for d in project["dependencies"] if "@" in d or "://" in d]


def test_the_model_packages_are_pinned_and_loaded() -> None:
    """`dependencies` pins leichtfacile-model-<lang> at the version its table
    [tool.leichtfacile.spacy-models.<lang>] builds, and the checker parses with that
    model; Italian, without a model package, gets a blank pipeline."""
    from leichtfacile.rules import nlp

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    models = pyproject["tool"]["leichtfacile"]["spacy-models"]
    deps = pyproject["project"]["dependencies"]
    pins = dict(d.split("==") for d in deps if d.startswith("leichtfacile-model-"))
    assert pins == {f"leichtfacile-model-{lang}": m["version"] for lang, m in models.items()}
    for lang, model in models.items():
        meta = nlp.pipeline(lang).meta
        assert f"{meta['lang']}_{meta['name']}" == model["name"]
        assert meta["version"] == model["version"]
        assert nlp.has_parser(nlp.pipeline(lang))
    assert nlp.pipeline("it").pipe_names == ["sentencizer"]


def test_the_readme_on_pypi_has_no_relative_link() -> None:
    """pypi.org shows the README without the repository: the build hook's substitutions
    (pyproject.toml) make every image and link absolute."""
    hook = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"][
        "metadata"
    ]["hooks"]["fancy-pypi-readme"]
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for sub in hook["substitutions"]:
        text = re.sub(sub["pattern"], sub["replacement"], text)
    assert re.findall(r"\]\((?!https://)[^)]*\)", text) == []
    assert (
        "](https://raw.githubusercontent.com/bobrovsky420/leicht-facile/main/docs/images/" in text
    )
