"""Labelling sheets for the judge and the agreement with the labels (eval/labels.py)."""

from __future__ import annotations

import json

from leichtfacile.eval.labels import (
    kappa_report,
    key_path,
    render_kappa,
    sample_items,
    write_sheets,
)
from leichtfacile.pipeline.models import UnderstandOut
from leichtfacile.pipeline.stages import to_factsheet
from leichtfacile.schemas import (
    Block,
    Draft,
    FactCheck,
    JobConfig,
    JudgeReport,
    PipelineSummary,
    Unsupported,
)
from leichtfacile.store import Store
from tests.pipeline import fixtures as fx


def _results_dir(tmp_path):
    store = Store(tmp_path / "store.sqlite")
    job = store.create_job(JobConfig(condition="P2"), title="syn-letter-de")
    store.put_artifact(job.id, "source", fx.letter())
    store.put_artifact(
        job.id, "factsheet", to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), "doc")
    )
    draft = Draft(doc_id="doc", lang="de", level="A2", blocks=[
        Block(id="b001", kind="heading", text="Was müssen Sie tun?"),
        Block(id="b002", kind="sentence", text="Schicken Sie das Gesuch bis 31. März 2026.",
              fact_ids=["f01"], segment_ids=["s0003"]),
        Block(id="b003", kind="sentence", text="Das kostet 20 Franken.", segment_ids=["s0004"]),
        Block(id="b004", kind="sentence", text="Die Gemeinde schenkt Ihnen einen Hund.",
              segment_ids=["s0002"]),
    ])  # fmt: skip
    store.put_artifact(job.id, "draft", draft, 1)
    judge = JudgeReport(draft_version=1, model="judge", fact_checks=[
        FactCheck(fact_id="f01", status="present", block_ids=["b002"]),
        FactCheck(fact_id="f02", status="distorted", block_ids=["b003"], note="20 statt 25"),
        FactCheck(fact_id="f03", status="missing"),
    ], unsupported=[Unsupported(block_id="b004", note="Kein Hund im Original.")])  # fmt: skip
    store.put_artifact(job.id, "judge", judge, 1)
    store.put_artifact(job.id, "summary", PipelineSummary(
        condition="P2", final_version=1, rounds=0, stop_reason="test", writer_model="w",
        judge_model="judge", prompt_versions={}, blocking_findings=[2], notes=[],
    ))  # fmt: skip
    store.close()
    row = {"pair_id": "syn-letter-de", "job_id": job.id, "role": "eval", "setup": "P2",
           "status": "needs_review"}  # fmt: skip
    (tmp_path / "P2_writer.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    return tmp_path


def test_sheets_hold_the_items_without_the_verdicts(tmp_path) -> None:
    results = _results_dir(tmp_path)
    fact_items, block_items = sample_items(results, facts=30, blocks=30)
    assert sorted(k["judge"] for _, k in fact_items) == ["distorted", "missing", "present"]
    assert sorted(k["judge"] for _, k in block_items) == ["supported", "supported", "unsupported"]
    for sheet, key in fact_items + block_items:
        assert sheet["label"] == "" and "judge" not in sheet and sheet["item_id"] == key["item_id"]
    distorted = next(s for s, k in fact_items if k["judge"] == "distorted")
    assert distorted["value"] == "20" and "[b003] Das kostet 20 Franken." in distorted["draft"]
    flagged = next(s for s, k in block_items if k["judge"] == "unsupported")
    assert flagged["block_id"] == "b004" and "[s0002]" in flagged["source"]

    paths = write_sheets(tmp_path / "labels", fact_items, block_items)
    assert [p.name for p in paths] == [
        "judge_facts.jsonl",
        "judge_facts.key.jsonl",
        "judge_blocks.jsonl",
        "judge_blocks.key.jsonl",
    ]
    assert key_path(paths[0]) == paths[1]
    # Two items of a kind at most when the pools are short.
    fact_items, block_items = sample_items(results, facts=2, blocks=1)
    assert len(fact_items) == 2 and len(block_items) == 1


def test_kappa_from_a_filled_sheet(tmp_path) -> None:
    results = _results_dir(tmp_path)
    fact_items, block_items = sample_items(results)
    sheet, key = write_sheets(tmp_path / "labels", fact_items, block_items)[:2]
    verdicts = {k["item_id"]: k["judge"] for _, k in fact_items}
    rows = [json.loads(line) for line in sheet.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        row["label"] = verdicts[row["item_id"]]  # the labeller agrees with the judge
    rows[0]["label"] = "Present " if rows[0]["label"] == "present" else rows[0]["label"]
    sheet.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    report = kappa_report(sheet)
    assert report["labelled"] == 3 and report["agreement"] == 1.0 and report["kappa"] == 1.0
    assert "Cohen's kappa 1.00" in render_kappa(report)

    rows[1]["label"] = "nonsense"
    rows[2]["label"] = ""
    sheet.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    report = kappa_report(sheet)
    assert report["labelled"] == 1 and len(report["unknown_labels"]) == 1
    assert "Ignored 1 items" in render_kappa(report)
