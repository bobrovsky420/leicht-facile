"""Judge the labelled drafts again and score the new verdicts against the blind labels
(docs/prompts.md, "Judge agreement with blind labels" and "English instructions").

Usage: uv run python scripts/judge_agreement.py --name de-current
           [--labels eval/labels/dev] [--store eval/results-cscs-v1]

Reads the endpoint from .env or the shell; with LLM_ENGLISH_PROMPTS=judge the judge has
the English instructions. For each labelled job it loads the source, the fact sheet and
the final draft from a copy of the store (the store itself is never written), calls the
judge once, writes the verdicts as key files next to the sheets
(`judge_facts.<name>.key.jsonl`, `judge_blocks.<name>.key.jsonl`) and prints the
agreement with the labels, scored as `eval kappa` scores the original key. A fact the
new answer does not check has no verdict and is left out, and the count says so.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from leichtfacile.config import get_settings
from leichtfacile.eval.labels import kappa_report, render_kappa
from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline import stages
from leichtfacile.schemas import Draft, FactSheet, PipelineSummary, SourceDocument
from leichtfacile.store import Store


def _load(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True, help="names the key files, e.g. en or de")
    parser.add_argument("--labels", type=Path, default=Path("eval/labels/dev"))
    parser.add_argument("--store", type=Path, default=Path("eval/results-cscs-v1"))
    args = parser.parse_args()

    sheets = {kind: args.labels / f"judge_{kind}.jsonl" for kind in ("facts", "blocks")}
    items = {kind: _load(path) for kind, path in sheets.items()}
    jobs = sorted({i["job_id"] for rows in items.values() for i in rows})
    settings = get_settings()
    llm = LLMClient(settings)
    english = stages.english_for(llm, "judge")
    reports = {}
    with tempfile.TemporaryDirectory() as tmp:
        for part in args.store.glob("store.sqlite*"):
            shutil.copy(part, Path(tmp) / part.name)
        store = Store(Path(tmp) / "store.sqlite")
        for job_id in jobs:
            summary = store.get_artifact(job_id, "summary", PipelineSummary)
            source = store.get_artifact(job_id, "source", SourceDocument)
            factsheet = store.get_artifact(job_id, "factsheet", FactSheet)
            draft = store.get_artifact(job_id, "draft", Draft, version=summary.final_version)
            text = "\n".join(f"[{b.id}] {b.text}" for b in draft.blocks)
            sheet_drafts = {i["draft"] for i in items["facts"] if i["job_id"] == job_id}
            if sheet_drafts and sheet_drafts != {text}:
                raise SystemExit(f"{job_id}: the stored final draft is not the labelled one")
            report, _ = stages.judge(llm, source, factsheet, draft, model=llm.judge_model())
            reports[job_id] = report
            print(f"{job_id}: judged ({'English' if english else 'document language'})")
        store.close()

    for kind, rows in items.items():
        keys = []
        for row in rows:
            report = reports[row["job_id"]]
            if kind == "facts":
                check = next((c for c in report.fact_checks if c.fact_id == row["fact_id"]), None)
                if check is None:
                    continue
                keys.append({"item_id": row["item_id"], "judge": check.status, "note": check.note})
            else:
                notes = {u.block_id: u.note for u in report.unsupported}
                verdict = "unsupported" if row["block_id"] in notes else "supported"
                keys.append(
                    {"item_id": row["item_id"], "judge": verdict, "note": notes.get(row["block_id"], "")}
                )
        key = args.labels / f"judge_{kind}.{args.name}.key.jsonl"
        key.write_text("".join(json.dumps(k, ensure_ascii=False) + "\n" for k in keys), "utf-8")
        print(f"\n{kind} ({args.name}), key {key}:")
        print(render_kappa(kappa_report(sheets[kind], key)))
        if kind == "facts":
            print("Present or not:", _present_or_not(sheets[kind], key))


def _present_or_not(sheet: Path, key: Path) -> str:
    """The fact verdicts as two classes, present against missing or distorted."""
    labels = {r["item_id"]: r.get("label") for r in _load(sheet)}
    pairs = [
        (k["judge"] == "present", labels[k["item_id"]] == "present")
        for k in _load(key)
        if labels.get(k["item_id"])
    ]
    if not pairs:
        return "-"
    from leichtfacile.eval.metrics import cohen_kappa

    agree = sum(1 for a, b in pairs if a == b) / len(pairs)
    kappa = cohen_kappa([str(a) for a, _ in pairs], [str(b) for _, b in pairs])
    return f"agreement {100 * agree:.0f} %, Cohen's kappa {kappa:.2f} ({len(pairs)} items)"


if __name__ == "__main__":
    main()
