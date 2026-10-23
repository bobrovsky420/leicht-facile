"""Example sources and their job settings (data/examples/README.md)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leichtfacile.examples import example_config, example_sources
from leichtfacile.schemas import JobConfig

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "examples"


def test_a_source_without_a_settings_file_has_none(tmp_path: Path) -> None:
    (tmp_path / "brief.txt").write_text("Text", encoding="utf-8")
    assert example_config(tmp_path / "brief.txt") == {}


def test_the_settings_file_next_to_a_source_sets_the_job(tmp_path: Path) -> None:
    (tmp_path / "entscheid.txt").write_text("Text", encoding="utf-8")
    settings = {"mode": "decision", "addressee": "Lea Muster"}
    (tmp_path / "entscheid.json").write_text(json.dumps(settings), encoding="utf-8")
    assert example_config(tmp_path / "entscheid.txt") == settings


def test_a_settings_file_with_other_keys_is_refused(tmp_path: Path) -> None:
    (tmp_path / "entscheid.txt").write_text("Text", encoding="utf-8")
    (tmp_path / "entscheid.json").write_text('{"modus": "decision"}', encoding="utf-8")
    with pytest.raises(ValueError, match="modus"):
        example_config(tmp_path / "entscheid.txt")


def test_the_settings_files_are_no_example_texts() -> None:
    ids = [e["id"] for e in example_sources(EXAMPLES)]
    assert "entscheid-beistandschaft-musterwil" in ids
    assert len(ids) == len(set(ids))  # the .json next to the .txt is not listed


def test_the_kesb_decision_runs_in_decision_mode() -> None:
    config = JobConfig.model_validate(
        example_config(EXAMPLES / "sources" / "entscheid-beistandschaft-musterwil.txt")
    )
    assert config.mode == "decision"
    assert config.addressee == "Lea Muster"
    assert config.notice and "Massgebend ist der Entscheid" in config.notice


def test_example_sources_carry_the_decision_settings() -> None:
    by_id = {e["id"]: e for e in example_sources(EXAMPLES)}
    kesb = by_id["entscheid-beistandschaft-musterwil"]
    assert kesb["mode"] == "decision" and kesb["addressee"] == "Lea Muster"
    assert kesb["notice"].endswith("Massgebend ist der Entscheid.")
    assert "mode" not in by_id["praemienverbilligung-brief"]
