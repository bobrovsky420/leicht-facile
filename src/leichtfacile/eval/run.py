"""Run a condition over the manifest pairs; resumable, one JSONL line per pair.

Results go to eval/results/ (git-ignored: they contain model rewrites of protected
pages). Jobs and artifacts are kept in eval/results/store.sqlite for inspection, and
the LLM cache (LLM_CACHE=1) makes reruns cheap.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from leichtfacile.config import Settings
from leichtfacile.eval.dataset import Pair, load_pair
from leichtfacile.eval.score import score_output, score_reference, score_source
from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline import stages
from leichtfacile.pipeline.orchestrator import Orchestrator
from leichtfacile.schemas import (
    Draft,
    FactSheet,
    JobConfig,
    JudgeReport,
    PipelineSummary,
    SourceDocument,
)
from leichtfacile.store import Store

log = logging.getLogger(__name__)
RESULTS = Path("eval/results")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def results_file(results_dir: Path, condition: str, writer: str) -> Path:
    return results_dir / f"{condition}_{slug(writer)}.jsonl"


def _done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        json.loads(line)["pair_id"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    }


def reference_rows(pairs: list[Pair], results_dir: Path = RESULTS) -> Path:
    """REF and SOURCE rows: no model involved, so they run without a key."""
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / "REF.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for pair in pairs:
            standard, easy = load_pair(pair)
            for row in (score_source(standard), score_reference(standard, easy)):
                row.update(pair_id=pair.id, role=pair.role, lang=pair.lang)
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def run_condition(
    pairs: list[Pair],
    condition: str,
    *,
    settings: Settings,
    llm: LLMClient,
    results_dir: Path = RESULTS,
    writer: str | None = None,
    judge: str | None = None,
    judge_all: bool = False,
) -> Path:
    """Run one condition on every pair that has no result yet."""
    results_dir.mkdir(parents=True, exist_ok=True)
    store = Store(results_dir / "store.sqlite")
    orchestrator = Orchestrator(store, llm, settings)
    writer_name = writer or settings.llm_name
    out = results_file(results_dir, condition, writer_name)
    done = _done(out)
    for pair in pairs:
        if pair.id in done:
            log.info("%s %s: done already", condition, pair.id)
            continue
        standard, easy = load_pair(pair)
        config = JobConfig(
            lang=pair.lang,
            level=pair.level,
            condition=condition,  # type: ignore[arg-type]
            writer_model=writer,
            judge_model=judge,
            max_repair_rounds=settings.max_repair_rounds,
        )
        job = store.create_job(config, title=pair.id)
        store.put_artifact(job.id, "source", standard)
        orchestrator.run(job.id)
        job = store.get_job(job.id)
        row: dict[str, Any] = {
            "pair_id": pair.id,
            "role": pair.role,
            "lang": pair.lang,
            "writer": writer_name,
            "job_id": job.id,
            "status": job.status,
        }
        if job.status not in ("needs_review", "done"):
            row["error"] = job.error
        else:
            summary = store.get_artifact(job.id, "summary", PipelineSummary)
            draft = store.get_artifact(
                job.id, "draft", Draft, version=summary.final_version if summary else None
            )
            factsheet = store.get_artifact(job.id, "factsheet", FactSheet) or _reference_factsheet(
                store, orchestrator, pair, job.id
            )
            judge_report = store.get_artifact(job.id, "judge", JudgeReport, version=draft.version)
            if judge_report is None and judge_all and factsheet is not None:
                judge_report = _score_judge(
                    store, orchestrator, job.id, standard, factsheet, draft, judge
                )
            row.update(score_output(job, draft, standard, easy, factsheet, judge_report))
            if summary:
                row.update(rounds=summary.rounds, stop_reason=summary.stop_reason)
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        log.info("%s %s: %s", condition, pair.id, row.get("status"))
    return out


def _reference_factsheet(
    store: Store, orch: Orchestrator, pair: Pair, job_id: str
) -> FactSheet | None:
    """A fact sheet to score outputs without one (C0): reuse another condition's, or make one.
    Calls made here are scoring calls and are not counted as the condition's cost."""
    for other in store.list_jobs(limit=1000):
        if other.title == pair.id and other.id != job_id:
            fs = store.get_artifact(other.id, "factsheet", FactSheet)
            if fs is not None:
                return fs
    standard = store.get_artifact(job_id, "source", SourceDocument)
    fs, _ = stages.understand(orch.llm, standard, level=pair.level)
    store.put_artifact(job_id, "score_factsheet", fs)
    return fs


def _score_judge(store, orch, job_id, standard, factsheet, draft, judge_model) -> JudgeReport:
    model = judge_model or orch.settings.judge_name
    report, _ = stages.judge(orch.llm, standard, factsheet, draft, model=model)
    store.put_artifact(job_id, "score_judge", report, draft.version)
    return report
