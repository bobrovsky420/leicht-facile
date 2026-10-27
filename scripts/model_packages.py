"""Build the packages leichtfacile-model-de and leichtfacile-model-fr: spaCy's models for
German and French, their files unchanged, under names the app can depend on. spaCy
publishes its models on GitHub only, and PyPI refuses dependencies given by URL.

The models are the tables [tool.leichtfacile.spacy-models.<lang>] in pyproject.toml.
Each package is spaCy's wheel, checked against its SHA-256, with the package folder
renamed to leichtfacile_model_<lang> and metadata of its own; the same input gives the
same bytes, so a wheel already on PyPI is recognised and skipped.
.github/workflows/models.yml builds and publishes them. Standard library only: it runs
without the project's environment, which depends on these packages.

    uv run --no-project python scripts/model_packages.py [--lang de] [--out dist/models]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import tempfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
RELEASES = "https://github.com/explosion/spacy-models/releases/download"
LICENSE_FILES = ("LICENSE", "LICENSES_SOURCES")
EPOCH = (1980, 1, 1, 0, 0, 0)  # every member's time stamp: the same bytes on every build
WHEEL = (
    "Wheel-Version: 1.0\nGenerator: scripts/model_packages.py\nRoot-Is-Purelib: true\n"
    "Tag: py3-none-any\n"
)

DESCRIPTION = """\
# leichtfacile-model-{lang}

spaCy's model `{name}` {version}, its files unchanged, under a name that
[Leicht·Facile]({homepage}) can depend on: spaCy publishes its models on GitHub only,
and PyPI refuses dependencies given by URL. This is not a release by Explosion, the
model's author.

- Built from {url} (SHA-256 `{sha256}`) by `scripts/model_packages.py`.
- License: {license}; the licenses of the training data are in `LICENSES_SOURCES`.
- Loaded with `spacy.load("leichtfacile_model_{lang}")`.

spaCy's model card follows.

{card}"""


def main() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    models = pyproject["tool"]["leichtfacile"]["spacy-models"]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lang", choices=list(models), help="only this language's package")
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "models")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for lang, model in models.items():
        if args.lang and lang != args.lang:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / f"{model['name']}-{model['version']}-py3-none-any.whl"
            download(spacy_url(model), source)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if digest != model["sha256"]:
                raise SystemExit(f"{source.name}: SHA-256 {digest}, expected {model['sha256']}")
            wheel = build(lang, model, pyproject["project"], source, args.out)
        print(f"{wheel} ({wheel.stat().st_size / 1e6:.0f} MB)")


def spacy_url(model: dict) -> str:
    folder = f"{model['name']}-{model['version']}"
    return f"{RELEASES}/{folder}/{folder}-py3-none-any.whl"


def download(url: str, dest: Path) -> None:
    print(f"Downloading {url} ...")
    with urllib.request.urlopen(url, timeout=60) as response, dest.open("wb") as f:
        shutil.copyfileobj(response, f, 1 << 20)


def build(lang: str, model: dict, project: dict, source: Path, out: Path) -> Path:
    """spaCy's wheel `source` as the wheel of leichtfacile-model-<lang> in `out`: the
    members of its package folder under the new name, byte for byte, and a new dist-info
    (METADATA, the license files, entry_points.txt, WHEEL, RECORD)."""
    name, version = model["name"], model["version"]
    package = f"leichtfacile_model_{lang}"
    dist_info = f"{package}-{version}.dist-info"
    wheel = out / f"{package}-{version}-py3-none-any.whl"
    record: list[str] = []
    with zipfile.ZipFile(source) as spacy, zipfile.ZipFile(wheel, "w") as target:

        def add(path: str, data: bytes) -> None:
            info = zipfile.ZipInfo(path, EPOCH)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, data)
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
            record.append(f"{path},sha256={digest.decode()},{len(data)}")

        for member in spacy.infolist():
            parts = PurePosixPath(member.filename).parts
            if parts[0] == name and not member.is_dir():  # spaCy's dist-info is replaced
                add(PurePosixPath(package, *parts[1:]).as_posix(), spacy.read(member))
        folder = f"{name}/{name}-{version}"
        meta = json.loads(spacy.read(f"{name}/meta.json"))
        card = spacy.read(f"{folder}/README.md").decode("utf-8")
        add(f"{dist_info}/METADATA", metadata(lang, model, meta, project, card).encode("utf-8"))
        for license_file in LICENSE_FILES:
            add(f"{dist_info}/licenses/{license_file}", spacy.read(f"{folder}/{license_file}"))
        add(f"{dist_info}/entry_points.txt", f"[spacy_models]\n{package} = {package}\n".encode())
        add(f"{dist_info}/WHEEL", WHEEL.encode())
        # RECORD lists itself without a hash
        add(f"{dist_info}/RECORD", "\n".join([*record, f"{dist_info}/RECORD,,", ""]).encode())
    return wheel


def metadata(lang: str, model: dict, meta: dict, project: dict, card: str) -> str:
    """Core metadata 2.4: the model's author as author, this project's authors as the
    maintainers, the model's spaCy range as the one requirement."""
    name, version = model["name"], model["version"]
    homepage = project["urls"]["Homepage"]
    maintainers = ", ".join(f"{a['name']} <{a['email']}>" for a in project["authors"])
    headers = [
        "Metadata-Version: 2.4",
        f"Name: leichtfacile-model-{lang}",
        f"Version: {version}",
        f"Summary: spaCy's {name} {version}, unchanged, as a dependency of leichtfacile",
        f"Author: {meta['author']}",
        f"Maintainer-email: {maintainers}",
        f"License-Expression: {model['license']}",
        *(f"License-File: {f}" for f in LICENSE_FILES),
        f"Project-URL: Homepage, {homepage}",
        f"Project-URL: Model, https://spacy.io/models/{lang}#{name}",
        f"Project-URL: Source, {spacy_url(model)}",
        f"Requires-Dist: spacy{meta['spacy_version']}",
        "Description-Content-Type: text/markdown",
    ]
    description = DESCRIPTION.format(
        lang=lang, name=name, version=version, homepage=homepage, url=spacy_url(model),
        sha256=model["sha256"], license=meta["license"], card=card.strip(),
    )  # fmt: skip
    return "\n".join(headers) + "\n\n" + description + "\n"


if __name__ == "__main__":
    main()
