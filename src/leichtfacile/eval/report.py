"""Markdown tables for the technical report, from the JSONL results in eval/results/.

Only aggregate numbers leave this module: no text from the protected reference pages
and no model rewrite of them, so the tables can be committed and published.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from leichtfacile.eval.score import LANGUAGE_FAMILIES

ORDER = {"SOURCE": 0, "REF": 1, "C0": 2, "C1": 3, "C2": 4}
LANGUAGES = {"de": "German", "fr": "French", "it": "Italian"}
LABELS = {
    "SOURCE": "Original (standard language)",
    "REF": "Official easy-language version",
    "C0": "C0: one prompt",
    "C1": "C1: fact sheet + draft + rule check",
    "C2": "C2: full pipeline with judge and repair",
}


def load_rows(results_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(results_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _mean(rows: list[dict], key: str) -> float | None:
    values = [r[key] for r in rows if r.get(key) is not None]
    return mean(values) if values else None


def _fmt(value: float | None, digits: int = 1, pct: bool = False) -> str:
    if value is None:
        return "-"
    return f"{100 * value:.0f} %" if pct else f"{value:.{digits}f}"


def _groups(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("status") not in (None, "needs_review", "done"):
            continue
        key = (
            r["setup"]
            if r["setup"] in ("SOURCE", "REF")
            else f"{r['setup']} ({r.get('writer', '?')})"
        )
        groups[key].append(r)
    return sorted(groups.items(), key=lambda kv: (ORDER.get(kv[0].split(" ")[0], 9), kv[0]))


def render_report(results_dir: Path, *, role: str | None = "eval", lang: str | None = None) -> str:
    """The tables, one section per language when the results cover several: numbers of
    different languages are not comparable (other rules, other readability formula)."""
    rows = [r for r in load_rows(results_dir) if role in (None, "all") or r.get("role") == role]
    if lang:
        rows = [r for r in rows if r.get("lang", "de") == lang]
    if not rows:
        return "No results yet. Run `python -m leichtfacile eval reference` and `eval run` first."
    langs = sorted({r.get("lang", "de") for r in rows}, key=lambda c: (c not in LANGUAGES, c))
    if len(langs) == 1:
        return _render_rows(rows, role)
    sections = []
    for code in langs:
        part = [r for r in rows if r.get("lang", "de") == code]
        sections.append(f"## {LANGUAGES.get(code, code)}\n\n" + _render_rows(part, role))
    return "\n\n".join(sections)


def _render_rows(rows: list[dict[str, Any]], role: str | None) -> str:
    failed = [r for r in rows if r.get("status") not in (None, "needs_review", "done")]
    groups = _groups(rows)
    out = [
        f"Pairs: {len({r['pair_id'] for r in rows})} ({role or 'all'} split). "
        "Means over pairs; a dash means not applicable.",
        "",
        "| Setup | Pairs | Fact coverage | Hard facts kept | Errors / 100 blocks "
        "| Warnings / 100 blocks | Words / sentence | Readability | SARI "
        "| Invented / 100 blocks | Tokens / page | USD / page "
        "| Seconds / page |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, group in groups:
        label = LABELS.get(name.split(" ")[0], name)
        if " (" in name:
            label += " " + name[name.index("(") :]
        out.append(
            f"| {label} | {len(group)} | {_fmt(_mean(group, 'fact_coverage'), pct=True)} "
            f"| {_fmt(_mean(group, 'hard_fact_recall'), pct=True)} "
            f"| {_fmt(_mean(group, 'errors_per_100'))} | {_fmt(_mean(group, 'warnings_per_100'))} "
            f"| {_fmt(_mean(group, 'avg_words'))} | {_fmt(_mean(group, 'readability'), 0)} "
            f"| {_fmt(_mean(group, 'sari'))} | {_fmt(_mean(group, 'unsupported_per_100'))} "
            f"| {_fmt(_mean(group, 'tokens_per_page'), 0)} "
            f"| {_fmt(_mean(group, 'usd_per_page'), 4)} "
            f"| {_fmt(_mean(group, 'latency_s_per_page'))} |"
        )
    out += ["", "Rule findings (errors and warnings) per 100 blocks, by family:", ""]
    out.append("| Setup | " + " | ".join(LANGUAGE_FAMILIES) + " |")
    out.append("|---|" + "---|" * len(LANGUAGE_FAMILIES))
    for name, group in groups:
        cells = []
        for family in LANGUAGE_FAMILIES:
            values = [r.get("by_family_per_100", {}).get(family, 0.0) for r in group]
            cells.append(_fmt(mean(values)) if values else "-")
        out.append(f"| {name} | " + " | ".join(cells) + " |")
    rich = [r for r in rows if (r.get("hard_facts_total") or 0) >= 3]
    if rich:
        out += [
            "",
            f"Fact-rich subset ({len({r['pair_id'] for r in rich})} pairs "
            "with at least 3 hard facts):",
            "",
        ]
        out += [
            "| Setup | Pairs | Hard facts kept | Fact coverage | Judge: distorted |",
            "|---|---|---|---|---|",
        ]
        for name, group in _groups(rich):
            out.append(
                f"| {name} | {len(group)} | {_fmt(_mean(group, 'hard_fact_recall'), pct=True)} "
                f"| {_fmt(_mean(group, 'fact_coverage'), pct=True)} "
                f"| {_fmt(_mean(group, 'judge_distorted'), pct=True)} |"
            )
    if failed:
        out += [
            "",
            f"Failed runs: {len(failed)} ({', '.join(sorted({r['pair_id'] for r in failed}))}).",
        ]
    return "\n".join(out)
