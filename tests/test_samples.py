"""The package leichtfacile-samples (samples/README.md): its recorded runs belong to a
letter and a shipped preset, and, before the package is published, each one replays
without an endpoint.

The replay runs each letter through the whole pipeline, so it runs where
LEICHTFACILE_RELEASE_CHECK=1 is set, in .github/workflows/samples.yml before the package
is published, and not in every CI run: a prompt change must not wait for a recording,
but a release of the samples must not ship a stale one. `uv run python
scripts/record_samples.py --check` runs the same check by hand; `record_samples.py`
records them again.
"""

from __future__ import annotations

import os

import pytest
from leichtfacile_samples import RECORDINGS

from leichtfacile import config
from leichtfacile.config import LETTERS_DIR
from leichtfacile.examples import check_recording, example_sources
from leichtfacile.llm.replay import read_recording

PATHS = sorted(RECORDINGS.glob("*/*.json"))
RELEASE = os.environ.get("LEICHTFACILE_RELEASE_CHECK") == "1"


def test_the_letters_ship_in_the_samples_package() -> None:
    assert LETTERS_DIR.parent.name == "leichtfacile_samples"
    assert len(example_sources(LETTERS_DIR)) >= 12


@pytest.mark.parametrize("path", PATHS, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_a_recording_belongs_to_a_letter_and_a_shipped_preset(path) -> None:
    recording, answers = read_recording(path)
    assert recording.path == f"{path.parent.name}/{path.name}"
    assert recording.letter in {e["id"] for e in example_sources(LETTERS_DIR)}
    assert recording.preset in config.PRESETS
    assert answers and recording.calls >= len({a["key"] for a in answers}) > 0
    assert recording.result["errors"] == 0  # a sample shows no red count


@pytest.mark.skipif(not RELEASE, reason="at a release (LEICHTFACILE_RELEASE_CHECK=1)")
@pytest.mark.parametrize("path", PATHS, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_a_recording_replays_without_an_endpoint(path) -> None:
    recording, _ = read_recording(path)
    settings = config.load(strict=False, preset=recording.preset).settings
    assert check_recording(path, settings) is None
