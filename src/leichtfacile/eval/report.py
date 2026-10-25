"""Markdown tables from result rows: docs/evaluation.md (`eval report`, one results
folder, one group per setup and model) and the language sections of
docs/model-comparison.md (`eval compare`, one group per run; eval/compare.py).

Only aggregate numbers leave this module: no text from the protected reference pages
and no model rewrite of them, so the tables can be committed and published.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import mean as exact_mean

from leichtfacile.eval.results import (
    LABELS,
    LANGUAGES,
    OK,
    ORDER,
    Row,
    completed,
    fmt,
    for_role,
    group_key,
    languages,
    load_rows,
    mean,
)
from leichtfacile.eval.score import LANGUAGE_FAMILIES

RICH_FACTS = 3  # the fact-rich subset: pairs with at least this many hard facts


@dataclass(frozen=True)
class Group:
    """One row of the tables: a setup and its models, or a run of the comparison."""

    label: str  # the first table's row label
    short: str  # the label of the tables after it
    rows: list[Row]  # every row of the group, the failed ones included


def groups_of(rows: list[Row]) -> list[Group]:
    """One folder's rows as groups: the originals, the official versions, then each
    setup with its models, in the order of the setups."""
    groups: dict[str, list[Row]] = {}
    for r in rows:
        reference = r["setup"] in ("SOURCE", "REF")
        key = r["setup"] if reference else f"{r['setup']} ({group_key(r)})"
        groups.setdefault(key, []).append(r)
    out = []
    order = lambda kv: (ORDER.get(kv[0].split(" ")[0], 9), kv[0])  # noqa: E731
    for key, found in sorted(groups.items(), key=order):
        label = LABELS.get(key.split(" ")[0], key)
        if " (" in key:
            label += " " + key[key.index("(") :]
        out.append(Group(label, key, found))
    return out


def render_report(results_dir: Path, *, role: str | None = "eval", lang: str | None = None) -> str:
    """The tables, one section per language when the results cover several: numbers of
    different languages are not comparable (other rules, other readability formula)."""
    rows = for_role(load_rows(results_dir), role)
    if lang:
        rows = [r for r in rows if r.get("lang", "de") == lang]
    if not rows:
        return "No results yet. Run `python -m leichtfacile eval reference` and `eval run` first."
    langs = languages(rows)
    if len(langs) == 1:
        return render_tables(groups_of(rows), role=role or "all")
    sections = []
    for code in langs:
        part = [r for r in rows if r.get("lang", "de") == code]
        tables = render_tables(groups_of(part), role=role or "all")
        sections.append(f"## {LANGUAGES.get(code, code)}\n\n{tables}")
    return "\n\n".join(sections)


def render_tables(groups: list[Group], *, role: str, column: str = "Setup") -> str:
    """The tables of one language: the measures per group, the rule findings by
    family, the fact-rich subset, and the failed runs, which are in no mean. `column`
    heads the groups' column."""
    rows = [r for g in groups for r in g.rows]
    ok = [(g, completed(g.rows)) for g in groups]
    out = [
        f"Pairs: {len({r['pair_id'] for r in rows})} ({role} split). "
        "Means over pairs; a dash means not applicable.",
        "",
        f"| {column} | Pairs | Fact coverage | Hard facts kept | Silent losses "
        "| Errors / 100 blocks | Warnings / 100 blocks | Words / sentence | Readability "
        "| SARI | Unsupported / 100 blocks (judge) | Values not in source / 100 blocks "
        "| Tokens / page "
        "| USD / page | Seconds / page |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    out += [_metrics_row(g.label, found) for g, found in ok]
    out += [
        "",
        "Silent losses: the share of the source's hard values that the text lost without a "
        "trace. A single prompt and the official version have no fact checklist and no "
        "omission log, so every value they lose is silent; for P1 and P2 every hard value "
        "is a fact in the review checklist or lies in a listed omission, so their share is "
        "zero by design, and a value above zero names one the code completion missed.",
        "",
        'Rule findings (errors and warnings) per 100 blocks, by family. "LEX by code" is '
        "the compounds split by code in the final version, per 100 blocks (P1 and P2 only; "
        "the baselines and the reference measure the text as written):",
        "",
    ]
    columns = [*LANGUAGE_FAMILIES]
    columns.insert(columns.index("LEX") + 1, "LEX by code")
    out.append(f"| {column} | " + " | ".join(columns) + " |")
    out.append("|---|" + "---|" * len(columns))
    for g, found in ok:
        cells = []
        for family in columns:
            if family == "LEX by code":
                splits = [r for r in found if "mediopunkt_per_100" in r]
                cells.append(fmt(mean(splits, "mediopunkt_per_100")))
                continue
            values = [r.get("by_family_per_100", {}).get(family, 0.0) for r in found]
            cells.append(fmt(exact_mean(values)) if values else "-")
        out.append(f"| {g.short} | " + " | ".join(cells) + " |")
    rich = [
        (g, [r for r in found if (r.get("hard_facts_total") or 0) >= RICH_FACTS]) for g, found in ok
    ]
    rich = [(g, found) for g, found in rich if found]
    if rich:
        pairs = {r["pair_id"] for _, found in rich for r in found}
        out += [
            "",
            f"Fact-rich subset ({len(pairs)} pairs with at least {RICH_FACTS} hard facts):",
            "",
            f"| {column} | Pairs | Hard facts kept | Fact coverage | Judge: distorted |",
            "|---|---|---|---|---|",
        ]
        for g, found in rich:
            out.append(
                f"| {g.short} | {len(found)} | {fmt(mean(found, 'hard_fact_recall'), pct=True)} "
                f"| {fmt(mean(found, 'fact_coverage'), pct=True)} "
                f"| {fmt(mean(found, 'judge_distorted'), pct=True)} |"
            )
    failed = []
    for g in groups:
        pairs = sorted({r["pair_id"] for r in g.rows if r.get("status") not in OK})
        if pairs:
            failed.append(f"{g.short}: {', '.join(pairs)}")
    if failed:
        out += ["", "Failed runs (not in the means): " + "; ".join(failed) + "."]
    return "\n".join(out)


def _metrics_row(label: str, rows: list[Row]) -> str:
    return (
        f"| {label} | {len(rows)} | {fmt(mean(rows, 'fact_coverage'), pct=True)} "
        f"| {fmt(mean(rows, 'hard_fact_recall'), pct=True)} "
        f"| {fmt(mean(rows, 'silent_loss_share'), pct=True)} "
        f"| {fmt(mean(rows, 'errors_per_100'))} | {fmt(mean(rows, 'warnings_per_100'))} "
        f"| {fmt(mean(rows, 'avg_words'))} | {fmt(mean(rows, 'readability'), 0)} "
        f"| {fmt(mean(rows, 'sari'))} | {fmt(mean(rows, 'unsupported_per_100'))} "
        f"| {fmt(mean(rows, 'invented_values_per_100'))} "
        f"| {fmt(mean(rows, 'tokens_per_page'), 0)} "
        f"| {fmt(mean(rows, 'usd_per_page'), 4)} "
        f"| {fmt(mean(rows, 'latency_s_per_page'))} |"
    )
