"""The version lives in pyproject.toml and publiccode.yml (AGENTS.md); the package reads
its __version__ from the installed package, and the documents name no version in their
commands: they install the newest release (`uvx leichtfacile`, `:latest`), and only the
quickstart's one command for a particular release names one, a past release as the
example. A version bump that misses one fails here, before the tag
(.github/workflows/release.yml runs this file too). The samples package (samples/) has a
version of its own, which the app's range admits."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from leichtfacile import __version__

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
# An exact version of the app in a command: a pinned uvx or pip install, an image tag, the
# compose variable, a release wheel.
PINNED = re.compile(
    r"leichtfacile(?:@|==|:|-)\d+\.\d+\.\d+|LEICHTFACILE_VERSION=\d|releases/download/v\d"
)


def test_the_package_has_the_project_version() -> None:
    assert __version__ == VERSION


def test_the_app_admits_the_major_version_of_the_samples_package() -> None:
    """The samples package has a version of its own (samples/pyproject.toml): the app
    depends on every release of one major version from the one it needs on, so new
    letters and recorded runs reach the installations without a release of the app."""
    samples = tomllib.loads((ROOT / "samples/pyproject.toml").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    major, minor, _ = (int(part) for part in samples["project"]["version"].split("."))
    (pin,) = [d for d in project["dependencies"] if d.startswith("leichtfacile-samples")]
    found = re.fullmatch(r"leichtfacile-samples>=(\d+)\.(\d+),<(\d+)", pin)
    assert found, pin
    lowest, highest = (int(found[1]), int(found[2])), int(found[3])
    assert lowest <= (major, minor) and highest == lowest[0] + 1 == major + 1
    assert samples["project"]["license"] == project["license"]
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert (ROOT / "samples/LICENSE").read_text(encoding="utf-8") == license_text


def test_publiccode_has_the_project_version() -> None:
    text = (ROOT / "publiccode.yml").read_text(encoding="utf-8")
    assert re.search(r'^softwareVersion: "([^"]+)"$', text, re.MULTILINE)[1] == VERSION


def test_the_documents_name_no_version_in_their_commands() -> None:
    """The commands install the newest release, so a release changes no document but the
    changelog; one advanced command in the quickstart installs a particular release, with
    a release that has its section in CHANGELOG.md as the example."""
    found = {
        path.relative_to(ROOT).as_posix(): PINNED.findall(path.read_text(encoding="utf-8"))
        for path in [ROOT / "README.md", ROOT / "SECURITY.md", *sorted(ROOT.glob("docs/*.md"))]
    }
    (example,) = found.pop("docs/quickstart.md")
    assert not any(found.values()), found
    assert example.startswith("leichtfacile==")
    released = example.removeprefix("leichtfacile==")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = rf"^## \[{re.escape(released)}\] - \d{{4}}-\d\d-\d\d$"
    assert re.search(section, changelog, re.MULTILINE), released
    for name in ("README.md", "docs/quickstart.md"):
        assert "<version>" not in (ROOT / name).read_text(encoding="utf-8"), name


def test_the_project_address_agrees() -> None:
    """https://leichtfacile.ch (the site, in the leicht-facile-web repository) is the
    project's address on PyPI, in
    publiccode.yml, in the web fetcher's User-Agent and in the header that names the app to
    OpenRouter."""
    from leichtfacile.ingest.fetch import USER_AGENT

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    home = project["urls"]["Homepage"]
    publiccode = (ROOT / "publiccode.yml").read_text(encoding="utf-8")
    presets = (ROOT / "src/leichtfacile/presets/presets.toml").read_text(encoding="utf-8")
    openrouter = tomllib.loads(presets)["providers"]["openrouter"]["headers"]
    assert home == "https://leichtfacile.ch"
    assert re.search(r'^landingURL: "([^"]+)"$', publiccode, re.MULTILINE)[1] == home
    assert USER_AGENT.endswith(f"(+{home})")
    assert openrouter["HTTP-Referer"] == home


def test_no_dependency_is_given_by_url() -> None:
    """PyPI refuses a package whose dependencies name a URL: the spaCy models come from
    PyPI as leichtfacile-model-de and -fr (scripts/model_packages.py)."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert not [d for d in project["dependencies"] if "@" in d or "://" in d]


def test_the_model_packages_are_pinned_and_loaded() -> None:
    """`dependencies` pins leichtfacile-model-<lang> at the version its table builds
    ([tool.leichtfacile.spacy-models.<lang>] for the spaCy models German and French,
    [tool.leichtfacile.lexicon-models.it] for the Italian lexicon pipeline), the checker
    parses with the spaCy models and tags with the lexicon component."""
    from leichtfacile.rules import nlp

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    models = pyproject["tool"]["leichtfacile"]["spacy-models"]
    lexicons = pyproject["tool"]["leichtfacile"]["lexicon-models"]
    deps = pyproject["project"]["dependencies"]
    pins = dict(d.split("==") for d in deps if d.startswith("leichtfacile-model-"))
    expected = {f"leichtfacile-model-{lang}": m["version"] for lang, m in models.items()}
    expected |= {f"leichtfacile-model-{lang}": m["version"] for lang, m in lexicons.items()}
    assert pins == expected
    for lang, model in models.items():
        meta = nlp.pipeline(lang).meta
        assert f"{meta['lang']}_{meta['name']}" == model["name"]
        assert meta["version"] == model["version"]
        assert nlp.has_parser(nlp.pipeline(lang))
    for lang, model in lexicons.items():
        pipe = nlp.pipeline(lang)
        assert pipe.meta["name"] == model["name"] and pipe.meta["version"] == model["version"]
        assert nlp.LEXICON_COMPONENT in pipe.pipe_names
        assert nlp.has_analysis(pipe) and not nlp.has_parser(pipe)


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
    assert re.findall(r'(?:src|srcset)="(?!https://)[^"]*"', text) == []
    assert (
        "](https://raw.githubusercontent.com/bobrovsky420/leicht-facile/main/docs/images/" in text
    )
