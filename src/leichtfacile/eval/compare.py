"""docs/model-comparison.md: every evaluation run side by side (docs/architecture.md §12).

The document declares its runs in a TOML block between `<!-- runs:start -->` and
`<!-- runs:end -->`, one `[[run]]` per run with its results folder and rows file;
`python -m leichtfacile eval compare` fills the tables between `<!-- tables:start -->` and
`<!-- tables:end -->` from those rows: means over the pairs of one split, one section per
language, the same columns as docs/evaluation.md. Only aggregates leave this module.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from leichtfacile.eval.report import LABELS, LANGUAGES, _fmt, _mean
from leichtfacile.eval.score import LANGUAGE_FAMILIES

RUNS = ("<!-- runs:start -->", "<!-- runs:end -->")
TABLES = ("<!-- tables:start -->", "<!-- tables:end -->")
OK = (None, "needs_review", "done")
FACTS = (
    ("date", "Date"),
    ("endpoint", "Endpoint"),
    ("writer", "Writer"),
    ("judge", "Judge"),
    ("thinking", "Thinking"),
    ("text", "The text goes to"),
    ("prices", "Prices"),
    ("notes", "Notes"),
)


class CompareError(ValueError):
    """The document or a run it declares cannot be used."""


@dataclass(frozen=True)
class Run:
    label: str
    results: Path  # the results folder, relative to the repository root
    file: str  # the rows of this run in it (P2_<writer>.jsonl)
    facts: dict[str, str]  # what the runs table shows, by the keys of FACTS

    def rows(self, root: Path, role: str) -> list[dict[str, Any]]:
        path = root / self.results / self.file
        if not path.is_file():
            raise CompareError(f"{self.label}: no rows at {path}")
        return [r for r in _read(path) if role == "all" or r.get("role") == role]


def read_runs(text: str) -> list[Run]:
    """The runs the document declares, in its order."""
    block = _between(text, RUNS)
    lines = [line for line in block.splitlines() if not line.startswith("```")]
    try:
        data = tomllib.loads("\n".join(lines))
    except tomllib.TOMLDecodeError as exc:
        raise CompareError(f"the runs block is not valid TOML: {exc}") from None
    runs = []
    for entry in data.get("run", []):
        for key in ("label", "results", "file"):
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise CompareError(f"a run needs {key} (text): {entry}")
        facts = {key: str(entry[key]) for key, _ in FACTS if key in entry}
        runs.append(Run(entry["label"], Path(entry["results"]), entry["file"], facts))
    if not runs:
        raise CompareError("the document declares no [[run]]")
    return runs


def update(doc: Path, *, root: Path = Path("."), role: str = "eval") -> int:
    """Fill the document's tables from its runs; the number of runs."""
    text = doc.read_text(encoding="utf-8")
    runs = read_runs(text)
    tables = render_tables(runs, root=root, role=role)
    start, end = TABLES
    head, _, rest = text.partition(start)
    _, _, tail = rest.partition(end)
    if not head or not rest:
        raise CompareError(f"{doc}: no {start} ... {end} block")
    doc.write_text(f"{head}{start}\n{tables}\n{end}{tail}", encoding="utf-8", newline="\n")
    return len(runs)


def render_tables(runs: list[Run], *, root: Path = Path("."), role: str = "eval") -> str:
    data = {run.label: run.rows(root, role) for run in runs}
    reference = _reference(runs, root, role)
    langs = sorted(
        {r.get("lang", "de") for rows in data.values() for r in rows},
        key=lambda c: (c not in LANGUAGES, c),
    )
    out = [_runs_table(runs)]
    for code in langs:
        section = _language(code, runs, data, reference, role)
        out.append(f"## {LANGUAGES.get(code, code)}\n\n{section}")
    return "\n\n".join(out)


def _runs_table(runs: list[Run]) -> str:
    out = [
        "| Run | " + " | ".join(label for _, label in FACTS) + " | Results |",
        "|---|" + "---|" * (len(FACTS) + 1),
    ]
    for run in runs:
        cells = [run.facts.get(key, "-") for key, _ in FACTS]
        where = f"`{run.results.as_posix()}/{run.file}`"
        out.append(f"| {run.label} | " + " | ".join(cells) + f" | {where} |")
    return "\n".join(out)


def _language(
    code: str,
    runs: list[Run],
    data: dict[str, list[dict[str, Any]]],
    reference: list[dict[str, Any]],
    role: str,
) -> str:
    groups = [
        (run.label, [r for r in data[run.label] if r.get("lang", "de") == code]) for run in runs
    ]
    ok = [(label, [r for r in rows if r.get("status") in OK]) for label, rows in groups]
    pairs = {r["pair_id"] for _, rows in groups for r in rows}
    out = [
        f"Pairs: {len(pairs)} ({role} split). Means over pairs; a dash means not applicable.",
        "",
        "| Run | Pairs | Fact coverage | Hard facts kept | Silent losses "
        "| Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability "
        "| SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks "
        "| Tokens / page | USD / page | Seconds / page |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for setup in ("SOURCE", "REF"):
        rows = [r for r in reference if r.get("setup") == setup and r.get("lang", "de") == code]
        if rows:
            out.append(_metrics_row(LABELS[setup], rows))
    for label, rows in ok:
        out.append(_metrics_row(label, rows))
    columns = [*LANGUAGE_FAMILIES]
    columns.insert(columns.index("LEX") + 1, "LEX by code")
    out += [
        "",
        'Rule findings (errors and warnings) per 100 blocks, by family; "LEX by code" is the '
        "compounds split by code in the final version, per 100 blocks:",
        "",
        "| Run | " + " | ".join(columns) + " |",
        "|---|" + "---|" * len(columns),
    ]
    for label, rows in ok:
        cells = []
        for column in columns:
            if column == "LEX by code":
                splits = [r["mediopunkt_per_100"] for r in rows if "mediopunkt_per_100" in r]
                cells.append(_fmt(mean(splits)) if splits else "-")
            else:
                values = [r.get("by_family_per_100", {}).get(column, 0.0) for r in rows]
                cells.append(_fmt(mean(values)) if values else "-")
        out.append(f"| {label} | " + " | ".join(cells) + " |")
    out += [
        "",
        "Fact-rich subset (pairs with at least 3 hard facts):",
        "",
        "| Run | Pairs | Hard facts kept | Fact coverage | Judge: distorted |",
        "|---|---|---|---|---|",
    ]
    for label, rows in ok:
        rich = [r for r in rows if (r.get("hard_facts_total") or 0) >= 3]
        out.append(
            f"| {label} | {len(rich)} | {_fmt(_mean(rich, 'hard_fact_recall'), pct=True)} "
            f"| {_fmt(_mean(rich, 'fact_coverage'), pct=True)} "
            f"| {_fmt(_mean(rich, 'judge_distorted'), pct=True)} |"
        )
    failed = [
        f"{label}: {', '.join(sorted(r['pair_id'] for r in rows if r.get('status') not in OK))}"
        for label, rows in groups
        if any(r.get("status") not in OK for r in rows)
    ]
    if failed:
        out += ["", "Failed pairs (not in the means): " + "; ".join(failed) + "."]
    return "\n".join(out)


def _metrics_row(label: str, rows: list[dict[str, Any]]) -> str:
    return (
        f"| {label} | {len(rows)} | {_fmt(_mean(rows, 'fact_coverage'), pct=True)} "
        f"| {_fmt(_mean(rows, 'hard_fact_recall'), pct=True)} "
        f"| {_fmt(_mean(rows, 'silent_loss_share'), pct=True)} "
        f"| {_fmt(_mean(rows, 'errors_per_100'))} | {_fmt(_mean(rows, 'warnings_per_100'))} "
        f"| {_fmt(_mean(rows, 'avg_words'))} | {_fmt(_mean(rows, 'readability'), 0)} "
        f"| {_fmt(_mean(rows, 'sari'))} | {_fmt(_mean(rows, 'unsupported_per_100'))} "
        f"| {_fmt(_mean(rows, 'invented_values_per_100'))} "
        f"| {_fmt(_mean(rows, 'tokens_per_page'), 0)} "
        f"| {_fmt(_mean(rows, 'usd_per_page'), 4)} "
        f"| {_fmt(_mean(rows, 'latency_s_per_page'))} |"
    )


def _reference(runs: list[Run], root: Path, role: str) -> list[dict[str, Any]]:
    """The originals and the official versions (REF.jsonl), the same in every folder: from
    the first run's folder that has them."""
    for run in runs:
        path = root / run.results / "REF.jsonl"
        if path.is_file():
            return [r for r in _read(path) if role == "all" or r.get("role") == role]
    return []


def _read(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _between(text: str, markers: tuple[str, str]) -> str:
    start, end = markers
    if start not in text or end not in text:
        raise CompareError(f"no {start} ... {end} block in the document")
    return text.split(start, 1)[1].split(end, 1)[0]
