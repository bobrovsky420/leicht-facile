"""docs/model-comparison.md: every evaluation run side by side (docs/architecture.md §12).

The document declares its runs in a TOML block between `<!-- runs:start -->` and
`<!-- runs:end -->`, one `[[run]]` per run with its results folder and rows file;
`python -m leichtfacile eval compare` fills the tables between `<!-- tables:start -->` and
`<!-- tables:end -->` from those rows: the runs table, then the tables of `eval report`
(eval/report.py) per language with one group per run, the originals and the official
versions from the first folder that has them. Only aggregates leave this module.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from leichtfacile.eval.report import Group, render_tables
from leichtfacile.eval.results import (
    LABELS,
    LANGUAGES,
    Row,
    for_role,
    languages,
    read_jsonl,
    variety_of,
)

RUNS = ("<!-- runs:start -->", "<!-- runs:end -->")
TABLES = ("<!-- tables:start -->", "<!-- tables:end -->")
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

    def rows(self, root: Path, role: str) -> list[Row]:
        path = root / self.results / self.file
        if not path.is_file():
            raise CompareError(f"{self.label}: no rows at {path}")
        return for_role(read_jsonl(path), role)


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
    tables = render_runs(runs, root=root, role=role)
    start, end = TABLES
    head, _, rest = text.partition(start)
    _, _, tail = rest.partition(end)
    if not head or not rest:
        raise CompareError(f"{doc}: no {start} ... {end} block")
    doc.write_text(f"{head}{start}\n{tables}\n{end}{tail}", encoding="utf-8", newline="\n")
    return len(runs)


def render_runs(runs: list[Run], *, root: Path = Path("."), role: str = "eval") -> str:
    """The runs table, then one section per language with the tables of `eval report`:
    the originals and the official versions first, then one group per run."""
    data = {run.label: run.rows(root, role) for run in runs}
    reference = _reference(runs, root, role)
    out = [_runs_table(runs)]
    for code in languages([r for rows in data.values() for r in rows]):
        groups = []
        for setup in ("SOURCE", "REF"):
            rows = [r for r in reference if r.get("setup") == setup and variety_of(r) == code]
            if rows:
                groups.append(Group(LABELS[setup], LABELS[setup], rows))
        groups += [
            Group(run.label, run.label, [r for r in data[run.label] if variety_of(r) == code])
            for run in runs
        ]
        tables = render_tables(groups, role=role, column="Run")
        out.append(f"## {LANGUAGES.get(code, code)}\n\n{tables}")
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


def _reference(runs: list[Run], root: Path, role: str) -> list[Row]:
    """The originals and the official versions (REF.jsonl), the same in every folder: from
    the first run's folder that has them."""
    for run in runs:
        path = root / run.results / "REF.jsonl"
        if path.is_file():
            return for_role(read_jsonl(path), role)
    return []


def _between(text: str, markers: tuple[str, str]) -> str:
    start, end = markers
    if start not in text or end not in text:
        raise CompareError(f"no {start} ... {end} block in the document")
    return text.split(start, 1)[1].split(end, 1)[0]
