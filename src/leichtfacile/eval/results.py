"""The result rows of the evaluation, read in one place.

A results folder (`eval/results*/`, git-ignored) holds one JSONL row per pair and
condition (`eval run`) and `REF.jsonl` with the originals (`SOURCE`) and the official
easy-language versions (`REF`). Every command that reads the rows goes through this
module, so that `eval report`, `eval compare`, `eval numbers`, `eval rescore`, `eval
sample` and `eval diagnose` agree on each of them: which rows count (a job that reached
the review, or a reference row without a status), the role filter, the condition names
rows carried before 6 October 2026 (C0 to C2), the mean of a measure, and the silent
losses of a row without a fact checklist, which follow from the hard facts kept.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean as exact_mean
from typing import Any

from leichtfacile.schemas import BASELINE_CONDITIONS, canonical_condition

Row = dict[str, Any]

# A usable row: a reference row (no status) or a job that reached the review.
OK = (None, "needs_review", "done")
ORDER = {
    "SOURCE": 0,
    "REF": 1,
    "P0": 2,
    "P0-ZH-complete": 3,
    "P0-ZH-condensed": 4,
    "P1": 5,
    "P2": 6,
}
LANGUAGES = {"de": "German", "fr": "French", "it": "Italian"}
LABELS = {
    "SOURCE": "Original (standard language)",
    "REF": "Official easy-language version",
    "P0": "P0 baseline: one prompt",
    "P0-ZH-complete": "P0-ZH complete: Zurich's prompt, keep everything",
    "P0-ZH-condensed": "P0-ZH default: Zurich's prompt, essentials only",
    "P1": "P1 no judge: fact sheet + draft + rule check",
    "P2": "P2 full: pipeline with judge and repair",
}
# Rows without a fact checklist: every hard value they lose is a silent loss, so the
# share follows from the hard facts kept when a row stored before the key has none.
NO_CHECKLIST = frozenset({"SOURCE", "REF", *BASELINE_CONDITIONS})


def read_jsonl(path: Path) -> list[Row]:
    """The rows of one file; none when it does not exist."""
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def load_rows(results_dir: Path, pattern: str = "*.jsonl") -> list[Row]:
    """The rows of a results folder, with the current condition names. A row of a failed
    run written before 25 October 2026 has no setup: it is the file's (`P2_<writer>.jsonl`)."""
    rows = []
    for path in sorted(results_dir.glob(pattern)):
        for row in read_jsonl(path):
            row.setdefault("setup", path.stem.split("_")[0])
            row["setup"] = canonical_condition(row["setup"])
            rows.append(row)
    return rows


def for_role(rows: list[Row], role: str | None) -> list[Row]:
    """The rows of one split; None or "all" keeps every row."""
    if role in (None, "all"):
        return list(rows)
    return [r for r in rows if r.get("role") == role]


def completed(rows: list[Row], role: str | None = None) -> list[Row]:
    """The usable rows of a split: a failed run or a failed scoring is left out."""
    return [r for r in for_role(rows, role) if r.get("status") in OK]


def completed_rows(results_dir: Path, condition: str, role: str | None) -> list[Row]:
    """The rows of a condition's completed jobs (every writer setup), for a role."""
    return completed(load_rows(results_dir, f"{condition}_*.jsonl"), role)


def group_key(row: Row) -> str:
    """The models of a row: the writer, and the reader when another model read the
    source (the hybrid)."""
    key = row.get("writer", "?")
    if row.get("understand"):
        key += f", understand {row['understand']}"
    return key


def value(row: Row, key: str) -> float | None:
    """A measure of a row; the silent-loss share of a row without a fact checklist
    follows from the hard facts kept when the row does not carry it."""
    found = row.get(key)
    if found is None and key == "silent_loss_share" and row.get("setup") in NO_CHECKLIST:
        kept = row.get("hard_fact_recall")
        return None if kept is None else 1 - kept
    return found


def mean(rows: list[Row], key: str) -> float | None:
    """The mean of a measure over the rows that have it; None when none has."""
    values = [v for r in rows if (v := value(r, key)) is not None]
    return exact_mean(values) if values else None  # exact, so the printed digits are stable


def fmt(found: float | None, digits: int = 1, pct: bool = False) -> str:
    if found is None:
        return "-"
    return f"{100 * found:.0f} %" if pct else f"{found:.{digits}f}"


def languages(rows: list[Row]) -> list[str]:
    """The languages of the rows, the known ones first in their order."""
    return sorted({r.get("lang", "de") for r in rows}, key=lambda c: (c not in LANGUAGES, c))
