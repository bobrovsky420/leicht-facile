"""Hand-labelling sheets for the judge (docs/architecture.md §9) and the agreement
between the judge and the labels.

`sample_items` draws (fact, draft) items, stratified by the judge's verdict, and blocks
the judge flagged as unsupported or passed, from the final drafts of one condition.
The sheets carry everything a labeller needs and no verdict, so the labeller is not
primed; the verdicts go to a key file next to each sheet. `kappa_report` joins a filled
sheet with its key and reports Cohen's kappa and the confusion counts.

The sheets quote the reference pages, so they stay local (`eval/labels/` is
git-ignored); only the agreement numbers are published.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from leichtfacile.eval.metrics import cohen_kappa
from leichtfacile.schemas import Draft, FactSheet, JudgeReport, PipelineSummary, SourceDocument
from leichtfacile.store import Store

FACT_LABELS = ("present", "missing", "distorted")
BLOCK_LABELS = ("supported", "unsupported")
SHEETS = {"fact": "judge_facts", "block": "judge_blocks"}

Item = tuple[dict[str, Any], dict[str, Any]]  # the sheet row and its key row


def _rows(results_dir: Path, condition: str, role: str | None) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(results_dir.glob(f"{condition}_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("status") not in (None, "needs_review", "done"):
                continue
            if role in (None, "all") or row.get("role") == role:
                rows.append(row)
    return rows


def _final(store: Store, job_id: str):
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    if summary is None:
        return None
    version = summary.final_version
    parts = (
        store.get_artifact(job_id, "source", SourceDocument),
        store.get_artifact(job_id, "factsheet", FactSheet),
        store.get_artifact(job_id, "draft", Draft, version=version),
        store.get_artifact(job_id, "judge", JudgeReport, version=version),
    )
    return None if any(p is None for p in parts) else parts


def _take(rng: random.Random, pools: dict[str, list[Item]], total: int) -> list[Item]:
    """Up to `total` items, as evenly over the pools as their sizes allow."""
    for pool in pools.values():
        rng.shuffle(pool)
    out: list[Item] = []
    while len(out) < total and any(pools.values()):
        for pool in pools.values():
            if pool and len(out) < total:
                out.append(pool.pop())
    return out


def sample_items(
    results_dir: Path,
    *,
    condition: str = "C2",
    role: str | None = "eval",
    facts: int = 30,
    blocks: int = 30,
    seed: int = 1,
) -> tuple[list[Item], list[Item]]:
    """Fact items stratified by the judge's status and block items half flagged,
    half passed, from the final drafts of the condition's completed jobs."""
    rng = random.Random(seed)
    fact_pools: dict[str, list[Item]] = {s: [] for s in FACT_LABELS}
    block_pools: dict[str, list[Item]] = {s: [] for s in BLOCK_LABELS}
    store = Store(results_dir / "store.sqlite")
    try:
        for row in _rows(results_dir, condition, role):
            loaded = _final(store, row["job_id"])
            if loaded is None:
                continue
            source, factsheet, draft, judge = loaded
            by_fact = {f.id: f for f in factsheet.facts}
            by_seg = source.by_id()
            draft_text = "\n".join(f"[{b.id}] {b.text}" for b in draft.blocks)
            source_text = "\n".join(f"[{s.id}] {s.text}" for s in source.segments)
            base = {"pair_id": row["pair_id"], "job_id": row["job_id"]}
            for check in judge.fact_checks:
                fact = by_fact.get(check.fact_id)
                if fact is None:
                    continue
                item_id = f"{row['job_id']}:{check.fact_id}"
                sheet = {
                    "item_id": item_id,
                    "kind": "fact",
                    **base,
                    "fact_id": fact.id,
                    "fact": fact.text,
                    "value": fact.value_norm,
                    "source": " ".join(by_seg[s].text for s in fact.segment_ids if s in by_seg),
                    "draft": draft_text,
                    "label": "",  # one of FACT_LABELS
                }
                key = {"item_id": item_id, "judge": check.status, "note": check.note}
                fact_pools[check.status].append((sheet, key))
            flagged = {u.block_id: u.note for u in judge.unsupported}
            for block in draft.blocks:
                if block.kind == "heading":
                    continue
                item_id = f"{row['job_id']}:{block.id}"
                verdict = "unsupported" if block.id in flagged else "supported"
                sheet = {
                    "item_id": item_id,
                    "kind": "block",
                    **base,
                    "block_id": block.id,
                    "text": block.text,
                    "cited": " ".join(by_seg[s].text for s in block.segment_ids if s in by_seg),
                    "source": source_text,
                    "label": "",  # one of BLOCK_LABELS
                }
                key = {"item_id": item_id, "judge": verdict, "note": flagged.get(block.id, "")}
                block_pools[verdict].append((sheet, key))
    finally:
        store.close()
    return _take(rng, fact_pools, facts), _take(rng, block_pools, blocks)


def write_sheets(out_dir: Path, fact_items: list[Item], block_items: list[Item]) -> list[Path]:
    """One sheet and one key file per kind; returns the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for kind, items in (("fact", fact_items), ("block", block_items)):
        for suffix, index in ((".jsonl", 0), (".key.jsonl", 1)):
            path = out_dir / f"{SHEETS[kind]}{suffix}"
            lines = [json.dumps(item[index], ensure_ascii=False) for item in items]
            path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            paths.append(path)
    return paths


def key_path(sheet: Path) -> Path:
    return sheet.with_name(sheet.name.removesuffix(".jsonl") + ".key.jsonl")


def _load(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def kappa_report(sheet: Path, key: Path | None = None) -> dict[str, Any]:
    """Agreement between the judge (key) and the labels filled into the sheet."""
    rows = _load(sheet)
    verdicts = {k["item_id"]: k["judge"] for k in _load(key or key_path(sheet))}
    kind = rows[0]["kind"] if rows else "fact"
    allowed = FACT_LABELS if kind == "fact" else BLOCK_LABELS
    judge: list[str] = []
    human: list[str] = []
    unknown: list[str] = []
    for row in rows:
        label = (row.get("label") or "").strip().lower()
        if not label:
            continue
        if label not in allowed or row["item_id"] not in verdicts:
            unknown.append(row["item_id"])
            continue
        judge.append(verdicts[row["item_id"]])
        human.append(label)
    report: dict[str, Any] = {
        "kind": kind,
        "items": len(rows),
        "labelled": len(judge),
        "unknown_labels": unknown,
        "labels": list(allowed),
    }
    if judge:
        agree = sum(1 for a, b in zip(judge, human, strict=True) if a == b)
        report["agreement"] = round(agree / len(judge), 3)
        report["kappa"] = round(cohen_kappa(judge, human), 3)
        report["confusion"] = {
            f"{j} -> {h}": n
            for (j, h), n in sorted(Counter(zip(judge, human, strict=True)).items())
        }
    return report


def render_kappa(report: dict[str, Any]) -> str:
    noun = "facts" if report["kind"] == "fact" else "blocks"
    lines = [f"{report['labelled']} of {report['items']} {noun} labelled."]
    if report["unknown_labels"]:
        lines.append(
            f"Ignored {len(report['unknown_labels'])} items with a label outside "
            f"{', '.join(report['labels'])} or without a key."
        )
    if "kappa" in report:
        lines.append(
            f"Agreement {100 * report['agreement']:.0f} %, Cohen's kappa {report['kappa']:.2f}."
        )
        lines.append(
            "Judge -> label: " + ", ".join(f"{k} {n}" for k, n in report["confusion"].items())
        )
    return "\n".join(lines)
