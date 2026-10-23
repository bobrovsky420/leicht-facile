"""The spaCy models: where they are found, the download with its checksum, the offline
folder, and what the checker and the command line do without them."""

from __future__ import annotations

import dataclasses
import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from leichtfacile import spacy_models
from leichtfacile.cli import main, models_or_exit
from leichtfacile.rules import nlp


def model_wheel(name: str, folder: str, *, extra: dict[str, str] | None = None) -> bytes:
    """A wheel shaped like spaCy's: the package, the model folder inside it, dist-info."""
    files = {
        f"{name}/__init__.py": "",
        f"{name}/meta.json": "{}",
        f"{name}/{folder}/config.cfg": "[nlp]\n",
        f"{name}/{folder}/tokenizer": "bytes",
        f"{folder}.dist-info/METADATA": "Name: x\n",
        **(extra or {}),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


@pytest.fixture
def german(monkeypatch):
    """The German model as a small fake wheel with its checksum, and spaCy reporting no
    installed package, so the unpacked folder decides."""
    model = spacy_models.MODELS["de"]
    data = model_wheel(model.name, model.folder)
    fake = dataclasses.replace(model, sha256=hashlib.sha256(data).hexdigest(), size=len(data))
    monkeypatch.setitem(spacy_models.MODELS, "de", fake)
    monkeypatch.setattr("spacy.util.is_package", lambda name: False)
    return fake, data


def test_a_download_is_checked_and_unpacked_to_the_model_folder(tmp_path, german) -> None:
    model, data = german
    fetched: list[str] = []

    def download(url: str, dest: Path) -> None:
        fetched.append(url)
        dest.write_bytes(data)

    assert spacy_models.locate("de", tmp_path) is None
    spacy_models.install(["de"], folder=tmp_path, download=download, say=lambda line: None)
    assert fetched == [model.url] and model.url.endswith("/de_core_news_md-3.8.0-py3-none-any.whl")
    assert spacy_models.locate("de", tmp_path) == tmp_path / model.folder
    assert sorted(p.name for p in (tmp_path / model.folder).iterdir()) == [
        "config.cfg",
        "tokenizer",
    ]
    assert sorted(p.name for p in tmp_path.iterdir()) == [model.folder]  # nothing else left


def test_a_wrong_checksum_installs_nothing(tmp_path, german) -> None:
    def tampered(url: str, dest: Path) -> None:
        dest.write_bytes(german[1] + b"x")

    with pytest.raises(ValueError, match="SHA-256"):
        spacy_models.install(["de"], folder=tmp_path, download=tampered, say=lambda line: None)
    assert spacy_models.locate("de", tmp_path) is None


def test_a_path_out_of_the_model_folder_is_refused(tmp_path, monkeypatch) -> None:
    model = spacy_models.MODELS["de"]
    evil = f"{model.name}/{model.folder}/../../escaped.txt"
    data = model_wheel(model.name, model.folder, extra={evil: "x"})
    fake = dataclasses.replace(model, sha256=hashlib.sha256(data).hexdigest())
    monkeypatch.setitem(spacy_models.MODELS, "de", fake)
    with pytest.raises(ValueError, match="unsafe path"):
        spacy_models.install(["de"], folder=tmp_path / "models",
                             download=lambda url, dest: dest.write_bytes(data),
                             say=lambda line: None)  # fmt: skip
    assert not list(tmp_path.rglob("escaped.txt"))


def test_offline_the_wheel_comes_from_a_folder(tmp_path, german) -> None:
    model, data = german
    (tmp_path / "wheelhouse").mkdir()
    (tmp_path / "wheelhouse" / model.wheel).write_bytes(data)

    def no_network(url: str, dest: Path) -> None:
        pytest.fail("downloaded")

    spacy_models.install(["de"], folder=tmp_path / "models", source=tmp_path / "wheelhouse",
                         download=no_network, say=lambda line: None)  # fmt: skip
    assert spacy_models.locate("de", tmp_path / "models") == tmp_path / "models" / model.folder


def test_an_installed_package_wins_over_the_folder(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("spacy.util.is_package", lambda name: name == "de_core_news_md")
    assert spacy_models.locate("de", tmp_path) == "de_core_news_md"


def test_the_checker_stops_without_the_german_model(monkeypatch) -> None:
    monkeypatch.setattr(spacy_models, "locate", lambda lang, folder=None: None)
    nlp.pipeline.cache_clear()
    try:
        with pytest.raises(spacy_models.ModelMissing, match="leichtfacile models"):
            nlp.pipeline("de")
        assert nlp.pipeline("it").has_pipe("sentencizer")  # Italian: blank by design
    finally:
        nlp.pipeline.cache_clear()


def test_the_command_line_names_the_missing_models(monkeypatch, capsys) -> None:
    monkeypatch.setattr(spacy_models, "missing", lambda folder=None: ["fr"])
    with pytest.raises(SystemExit) as stop:
        models_or_exit()
    assert stop.value.code == 2
    assert "fr_core_news_md" in capsys.readouterr().err


def test_models_reports_what_is_already_there(monkeypatch, capsys) -> None:
    monkeypatch.setattr(spacy_models, "missing", lambda folder=None: [])
    monkeypatch.setattr(spacy_models, "locate", lambda lang, folder=None: f"{lang}-package")
    assert main(["models"]) == 0
    out = capsys.readouterr().out
    assert "de_core_news_md: de-package (already there)" in out and "fr_core_news_md" in out
