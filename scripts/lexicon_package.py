"""Build the package leichtfacile-model-it: an Italian spaCy pipeline, the blank
Italian tokenizer and sentencizer with the Morph-it! lexicon as its tagger
(scripts/morphit.py), under a name the app can depend on, like the spaCy models of
scripts/model_packages.py. Every spaCy Italian model is licensed CC BY-NC-SA, so the
Italian checker tags with Morph-it! (Eros Zanchetta and Marco Baroni, University of
Bologna, version 0.4.8, CC BY-SA 2.0 and LGPL) instead and does without a parser.

The lexicon comes from the archive the table [tool.leichtfacile.lexicon-models.it] in
pyproject.toml names (the Language Bank of Finland's HFST build, which carries the
original text file and its readme; the authors' site refuses downloads by scripts),
checked against the archive's SHA-256 and the lexicon's own. The licence texts go into
the wheel. The same input gives the same bytes, so a wheel already on PyPI is
recognised and skipped by the publish step of .github/workflows/models.yml.

    uv run python scripts/lexicon_package.py [--out dist/models]

Needs spaCy and srsly, which the project's environment has (or `uv run --no-project
--with "spacy>=3.8.16,<3.9"`); the package itself is not needed to build it.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import sys
import tempfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
EPOCH = (1980, 1, 1, 0, 0, 0)  # every member's time stamp: the same bytes on every build
WHEEL = (
    "Wheel-Version: 1.0\nGenerator: scripts/lexicon_package.py\nRoot-Is-Purelib: true\n"
    "Tag: py3-none-any\n"
)
INIT = '''"""{description}"""

from pathlib import Path

from spacy.util import get_model_meta, load_model_from_init_py

from . import morphit  # noqa: F401  (registers the factory "morphit")

__version__ = get_model_meta(Path(__file__).parent)["version"]


def load(**overrides):
    return load_model_from_init_py(__file__, **overrides)
'''
DESCRIPTION = """\
# leichtfacile-model-{lang}

An Italian spaCy pipeline for [Leicht·Facile]({homepage}): the blank Italian
tokenizer and sentencizer with the Morph-it! lexicon as its tagger. The component
`morphit` sets the lemma, the part of speech and the morphology of every token from the
lexicon and keeps every reading of an ambiguous form in `token._.readings`; there is
no parser. Every spaCy Italian model is licensed for non-commercial use only, which is
why this pipeline exists.

- Lexicon: Morph-it! {source_version} by Eros Zanchetta and Marco Baroni, University of
  Bologna (http://sslmit.unibo.it/morphit), taken from {url} (SHA-256 `{sha256}`),
  licensed under the Creative Commons Attribution ShareAlike 2.0 License and the GNU
  Lesser General Public License; its readme and the LGPL text are in this package.
- Built by `scripts/lexicon_package.py` of Leicht·Facile; the component's code is in
  `morphit.py` of this package.
- Loaded with `spacy.load("leichtfacile_model_{lang}")`.
"""


def main() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lexicons = pyproject["tool"]["leichtfacile"]["lexicon-models"]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "models")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for lang, model in lexicons.items():
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "source.zip"
            download(model["url"], archive)
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            if digest != model["sha256"]:
                raise SystemExit(f"{model['url']}: SHA-256 {digest}, expected {model['sha256']}")
            files = extract(archive, model, Path(tmp))
            wheel = build(lang, model, pyproject["project"], files, Path(tmp), args.out)
        print(f"{wheel} ({wheel.stat().st_size / 1e6:.0f} MB)")


def download(url: str, dest: Path) -> None:
    print(f"Downloading {url} ...")
    request = urllib.request.Request(url, headers={"User-Agent": "leichtfacile-build"})
    with urllib.request.urlopen(request, timeout=120) as response, dest.open("wb") as f:
        shutil.copyfileobj(response, f, 1 << 20)


def extract(archive: Path, model: dict, tmp: Path) -> dict[str, Path]:
    """The lexicon, its readme and the LGPL text out of the archive, the lexicon
    checked against its SHA-256."""
    out = {}
    with zipfile.ZipFile(archive) as zf:
        for key in ("lexicon", "readme", "lgpl"):
            member = model[key]
            target = tmp / PurePosixPath(member).name
            target.write_bytes(zf.read(member))
            out[key] = target
    digest = hashlib.sha256(out["lexicon"].read_bytes()).hexdigest()
    if digest != model["lexicon_sha256"]:
        expected = model["lexicon_sha256"]
        raise SystemExit(f"{model['lexicon']}: SHA-256 {digest}, expected {expected}")
    return out


def build(
    lang: str, model: dict, project: dict, files: dict[str, Path], tmp: Path, out: Path
) -> Path:
    """The pipeline on disk, then the wheel: the package folder with `__init__.py`, the
    component's code, `meta.json` and the pipeline data, and a dist-info (METADATA, the
    licence files, entry_points.txt, WHEEL, RECORD)."""
    import spacy

    sys.path.insert(0, str(HERE))
    import morphit  # noqa: PLC0415  (scripts/morphit.py, bundled below)

    name, version = model["name"], model["version"]
    package = f"leichtfacile_model_{lang}"
    data_dir = f"{lang}_{name}-{version}"
    nlp = spacy.blank(lang)
    nlp.add_pipe("sentencizer")
    component: morphit.MorphitLexicon = nlp.add_pipe(morphit.COMPONENT)
    component.load_tsv(files["lexicon"])
    print(f"{len(component)} forms")
    description = (
        f"Italian: tokenizer, sentencizer and the Morph-it! {model['source_version']} lexicon as "
        "the tagger (lemma, part of speech, morphology, every reading); no parser"
    )
    nlp.meta.update(
        {
            "name": name,
            "version": version,
            "description": description,
            "author": "Leicht·Facile; lexicon by Eros Zanchetta and Marco Baroni",
            "email": project["authors"][0]["email"],
            "url": project["urls"]["Homepage"],
            "license": model["license"],
            "sources": [
                {
                    "name": f"Morph-it! {model['source_version']}",
                    "url": "http://sslmit.unibo.it/morphit",
                    "license": model["license"],
                    "author": "Eros Zanchetta and Marco Baroni",
                }
            ],
        }
    )
    pipeline_dir = tmp / data_dir
    nlp.to_disk(pipeline_dir)
    meta = json.loads((pipeline_dir / "meta.json").read_text(encoding="utf-8"))

    dist_info = f"{package}-{version}.dist-info"
    wheel = out / f"{package}-{version}-py3-none-any.whl"
    record: list[str] = []
    with zipfile.ZipFile(wheel, "w") as target:

        def add(path: str, data: bytes) -> None:
            info = zipfile.ZipInfo(path, EPOCH)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, data)
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
            record.append(f"{path},sha256={digest.decode()},{len(data)}")

        description = DESCRIPTION.format(
            lang=lang, homepage=project["urls"]["Homepage"], url=model["url"],
            sha256=model["sha256"], source_version=model["source_version"],
        )  # fmt: skip
        add(f"{package}/__init__.py", INIT.format(description=meta["description"]).encode())
        add(f"{package}/morphit.py", (HERE / "morphit.py").read_bytes())
        add(f"{package}/meta.json", (pipeline_dir / "meta.json").read_bytes())
        for file in sorted(p for p in pipeline_dir.rglob("*") if p.is_file()):
            relative = file.relative_to(tmp).as_posix()
            add(f"{package}/{relative}", file.read_bytes())
        add(f"{dist_info}/METADATA", metadata(lang, model, meta, project, description).encode())
        for key in ("readme", "lgpl"):
            add(f"{dist_info}/licenses/{files[key].name}", files[key].read_bytes())
        add(f"{dist_info}/entry_points.txt", f"[spacy_models]\n{package} = {package}\n".encode())
        add(f"{dist_info}/WHEEL", WHEEL.encode())
        add(f"{dist_info}/RECORD", "\n".join([*record, f"{dist_info}/RECORD,,", ""]).encode())
    return wheel


def metadata(lang: str, model: dict, meta: dict, project: dict, description: str) -> str:
    """Core metadata 2.4: the lexicon's authors as the author, this project's authors as
    the maintainers, the pipeline's spaCy range as the one requirement."""
    maintainers = ", ".join(f"{a['name']} <{a['email']}>" for a in project["authors"])
    headers = [
        "Metadata-Version: 2.4",
        f"Name: leichtfacile-model-{lang}",
        f"Version: {model['version']}",
        f"Summary: Italian spaCy pipeline with the Morph-it! {model['source_version']} lexicon as "
        "its tagger, a dependency of leichtfacile",
        "Author: Eros Zanchetta and Marco Baroni (Morph-it!); Leicht·Facile (the pipeline)",
        f"Maintainer-email: {maintainers}",
        f"License-Expression: {model['license']}",
        "License-File: readme-morph-it.txt",
        "License-File: lgpl.txt",
        f"Project-URL: Homepage, {project['urls']['Homepage']}",
        "Project-URL: Lexicon, http://sslmit.unibo.it/morphit",
        f"Project-URL: Source, {model['url']}",
        f"Requires-Dist: spacy{meta['spacy_version']}",
        "Description-Content-Type: text/markdown",
    ]
    return "\n".join(headers) + "\n\n" + description + "\n"


if __name__ == "__main__":
    main()
