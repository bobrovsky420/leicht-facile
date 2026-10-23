"""The spaCy models the rule checker parses German and French with.

They are not on PyPI, so the package cannot depend on them. In a checkout `uv sync`
installs them as packages (the `models` dependency group in pyproject.toml). Otherwise
`leichtfacile models`, which `leichtfacile setup` offers, downloads the pinned files
from spaCy's releases on GitHub, checks their SHA-256 and unpacks the model folder into
DATA_DIR/models/: no pip needed, which `uv tool` environments lack. Offline, the same
files are carried over and unpacked with `leichtfacile models --from <folder>`.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from leichtfacile.config import paths


@dataclass(frozen=True)
class SpacyModel:
    name: str
    version: str
    sha256: str
    size: int  # bytes, for the message before the download

    @property
    def folder(self) -> str:
        """The model folder inside the wheel, and its name under DATA_DIR/models."""
        return f"{self.name}-{self.version}"

    @property
    def wheel(self) -> str:
        return f"{self.folder}-py3-none-any.whl"

    @property
    def url(self) -> str:
        return f"https://github.com/explosion/spacy-models/releases/download/{self.folder}/{self.wheel}"


# The versions and hashes uv.lock records for the `models` group.
MODELS: dict[str, SpacyModel] = {
    "de": SpacyModel(
        "de_core_news_md",
        "3.8.0",
        "b903f59220f1e76dd672acdaa7fa454d6703fe056c5ccd6457820e70874116d0",
        44_398_316,
    ),
    "fr": SpacyModel(
        "fr_core_news_md",
        "3.8.0",
        "8a70d090a54ef77525c3ffa6a6195b9d365f2cf369ae1cd84ede93f3d709079e",
        45_836_173,
    ),
}


class ModelMissing(RuntimeError):
    def __init__(self, lang: str) -> None:
        model = MODELS[lang]
        super().__init__(
            f"the spaCy model {model.name} for {lang} is not installed: run `leichtfacile models`"
        )


def models_dir() -> Path:
    return paths().data_dir / "models"


def locate(lang: str, folder: Path | None = None) -> str | Path | None:
    """What `spacy.load` takes for `lang`: the installed package's name, else the
    unpacked model folder, else None."""
    import spacy

    model = MODELS[lang]
    if spacy.util.is_package(model.name):
        return model.name
    path = (folder or models_dir()) / model.folder
    return path if (path / "config.cfg").is_file() else None


def missing(folder: Path | None = None) -> list[str]:
    """The languages whose model is neither installed nor unpacked."""
    return [lang for lang in MODELS if locate(lang, folder) is None]


def fetch(url: str, dest: Path) -> None:
    """Download `url` to `dest` (GitHub answers with a redirect)."""
    import httpx

    with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
        response.raise_for_status()
        with dest.open("wb") as f:
            for chunk in response.iter_bytes(1 << 20):
                f.write(chunk)


def install(
    langs: Iterable[str],
    *,
    folder: Path | None = None,
    source: Path | None = None,
    download: Callable[[str, Path], None] = fetch,
    say: Callable[[str], None] = print,
) -> list[Path]:
    """Download (or take from the folder `source`) each language's wheel, check its
    SHA-256 and unpack its model folder into `folder` (DATA_DIR/models). Raises
    ValueError on a wrong checksum or a wheel that is not the model's; a model already
    unpacked is replaced only once the new one is complete."""
    langs = list(langs)
    if not langs:
        return []
    target_dir = folder or models_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for lang in langs:
        model = MODELS[lang]
        with tempfile.TemporaryDirectory(dir=target_dir) as tmp:
            wheel = Path(tmp) / model.wheel
            if source is not None:
                shutil.copyfile(source / model.wheel, wheel)
            else:
                say(f"Downloading {model.name} {model.version} ({model.size / 1e6:.0f} MB)...")
                download(model.url, wheel)
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            if digest != model.sha256:
                raise ValueError(f"{model.wheel}: SHA-256 {digest}, expected {model.sha256}")
            unpacked = Path(tmp) / "unpacked"
            _unpack(wheel, model, unpacked)
            target = target_dir / model.folder
            if target.exists():
                shutil.rmtree(target)
            (unpacked / model.folder).rename(target)
        say(f"{model.name} {model.version}: {target}")
        done.append(target)
    return done


def _unpack(wheel: Path, model: SpacyModel, dest: Path) -> None:
    """The members under `<name>/<name>-<version>/` of the wheel, into `dest/<folder>`."""
    prefix = PurePosixPath(model.name, model.folder)
    with zipfile.ZipFile(wheel) as archive:
        members = [
            m for m in archive.infolist() if PurePosixPath(m.filename).is_relative_to(prefix)
        ]
        for member in members:
            relative = PurePosixPath(member.filename).relative_to(model.name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"{model.wheel}: unsafe path {member.filename}")
            out = dest.joinpath(*relative.parts)
            if member.is_dir():
                out.mkdir(parents=True, exist_ok=True)
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, out.open("wb") as f:
                shutil.copyfileobj(src, f)
    if not (dest / model.folder / "config.cfg").is_file():
        raise ValueError(f"{model.wheel}: no model folder {model.folder} with a config.cfg")
