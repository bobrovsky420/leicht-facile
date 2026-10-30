"""The one reader of the result rows (eval/results.py): the status and role filters,
the old condition names, the mean, and the silent losses of a row without a checklist."""

from __future__ import annotations

import json
from pathlib import Path

from leichtfacile.eval.results import (
    completed,
    completed_rows,
    group_key,
    languages,
    load_rows,
    mean,
    value,
    variety_of,
)


def _write(folder: Path, name: str, rows: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_rows_get_the_current_condition_names_and_the_filters_agree(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "P2_m.jsonl",
        [
            {"setup": "C2", "pair_id": "a", "role": "eval", "status": "needs_review"},
            {"pair_id": "b", "role": "eval", "status": "failed"},  # a failed run: no setup
            {"setup": "C2", "pair_id": "c", "role": "dev", "status": "done", "lang": "fr"},
        ],
    )
    _write(tmp_path, "REF.jsonl", [{"setup": "REF", "pair_id": "a", "role": "eval"}])
    rows = load_rows(tmp_path)
    assert [r["setup"] for r in rows] == ["P2", "P2", "P2", "REF"]
    assert [r["pair_id"] for r in completed(rows)] == ["a", "c", "a"]  # no status is usable
    assert [r["pair_id"] for r in completed(rows, "eval")] == ["a", "a"]
    assert [r["pair_id"] for r in completed(rows, "all")] == ["a", "c", "a"]
    assert [r["pair_id"] for r in completed_rows(tmp_path, "P2", "dev")] == ["c"]
    assert languages(rows) == ["de", "fr"]
    assert load_rows(tmp_path / "nowhere") == []


def test_the_rows_of_germany_and_austria_group_as_varieties_of_their_own() -> None:
    rows = [
        {"lang": "de"},  # a row from before the region: Swiss
        {"lang": "de", "region": "CH"},
        {"lang": "de", "region": "AT"},
        {"lang": "de", "region": "DE"},
        {"lang": "fr", "region": "CH"},
    ]
    assert [variety_of(r) for r in rows] == ["de", "de", "de-AT", "de-DE", "fr"]
    assert languages(rows) == ["de", "de-DE", "de-AT", "fr"]


def test_the_mean_skips_missing_values_and_derives_silent_losses_without_a_checklist() -> None:
    rows = [
        {"setup": "P0", "hard_fact_recall": 0.75, "errors_per_100": 2.0},
        {"setup": "P0", "hard_fact_recall": 0.25, "silent_loss_share": 0.5, "errors_per_100": None},
        {"setup": "P0"},
    ]
    assert mean(rows, "errors_per_100") == 2.0
    assert mean(rows, "nothing") is None
    # the first row has no share: it follows from the hard facts kept; the third has neither
    assert value(rows[0], "silent_loss_share") == 0.25
    assert value(rows[2], "silent_loss_share") is None
    assert mean(rows, "silent_loss_share") == 0.375
    # a pipeline row without the share stays without it: its losses are told, not silent
    assert value({"setup": "P2", "hard_fact_recall": 0.5}, "silent_loss_share") is None
    assert group_key({"writer": "8B", "understand": "70B"}) == "8B, understand 70B"
    assert group_key({}) == "?"
