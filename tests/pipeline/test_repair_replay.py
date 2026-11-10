"""Recorded repair rounds replayed through `versions.apply_repairs`
(tests/fixtures/repairs/README.md): the new version and the dropped sentences must be
what the export made of the same round. A change of the function that alters either
fails here; a deliberate change exports the cases again (scripts/repair_fixtures.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leichtfacile.pipeline.models import RepairOut
from leichtfacile.pipeline.versions import RepairRequest, apply_repairs, sentences_of
from leichtfacile.schemas import Draft, DroppedText, FactSheet

FIXTURES = Path(__file__).parents[1] / "fixtures" / "repairs"
CASES = sorted(FIXTURES.glob("*.json"))


def replay(case: dict) -> tuple[Draft, list[DroppedText]]:
    """The round as the pipeline ran it: the parent version, the answer as applied,
    the blocks and the facts asked for, the version number the round produced."""
    draft = Draft.model_validate(case["draft"])
    factsheet = FactSheet.model_validate(case["factsheet"])
    facts = {f.id: f for f in factsheet.facts}
    request = RepairRequest(
        {b: ["replay"] for b in case["requested_blocks"]},
        [facts[i] for i in case["requested_facts"]],
    )
    dropped: list[DroppedText] = []
    new = apply_repairs(
        draft,
        RepairOut.model_validate(case["answer"]),
        request,
        factsheet,
        dropped=dropped,
        version=case["version"],
    )
    return new, dropped


def test_the_cases_are_there() -> None:
    assert len(CASES) >= 10, "export the cases: uv run python scripts/repair_fixtures.py"


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_a_recorded_round_replays_as_exported(path: Path) -> None:
    case = json.loads(path.read_text(encoding="utf-8"))
    assert case["format"] == "repair-replay@1"
    new, dropped = replay(case)
    assert new.model_dump(mode="json") == case["expected"]["draft"]
    assert [d.model_dump(mode="json") for d in dropped] == case["expected"]["dropped"]


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_a_recorded_round_is_a_real_case(path: Path) -> None:
    """What makes the case worth keeping: the answer is applied to the version it was
    written for, every sentence the model gave is in the new version or in the dropped
    list, and every new sentence of the version came from the answer."""
    case = json.loads(path.read_text(encoding="utf-8"))
    new, dropped = replay(case)
    assert new.parent_version == case["draft"]["version"]
    assert new.version == case["version"] > new.parent_version
    lang = case["draft"]["lang"]
    given = {
        t
        for item in [*case["answer"]["repairs"], *case["answer"]["additions"]]
        for t in sentences_of(list(item["texts"]), lang)  # as the function reads them
    }
    before = {b["text"] for b in case["draft"]["blocks"]}
    after = {b.text for b in new.blocks}
    left_out = {d.text for d in dropped}
    assert given <= after | left_out
    assert after - before <= given
