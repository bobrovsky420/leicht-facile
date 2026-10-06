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
from leichtfacile.pipeline.prompts import has_prompt
from leichtfacile.schemas import (
    BASELINE_CONDITIONS,
    ZH_CONDITIONS,
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


def results_file(
    results_dir: Path, condition: str, writer: str, understand: str | None = None
) -> Path:
    """One file per condition and model setup; a hybrid (another model for the
    Understand stage) gets its own file."""
    name = f"{condition}_{slug(writer)}"
    if understand and understand != writer:
        name += f"_understand-{slug(understand)}"
    return results_dir / f"{name}.jsonl"


_OK = ("needs_review", "done")


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _done(path: Path) -> set[str]:
    """Pairs with a usable result. Failed runs and failed scorings run again next time."""
    return {r["pair_id"] for r in _rows(path) if r.get("status") in _OK}


def _write_row(path: Path, row: dict[str, Any]) -> None:
    """Add the row, replacing an earlier row of the same pair (a failed run)."""
    rows = [r for r in _rows(path) if r["pair_id"] != row["pair_id"]] + [row]
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


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
    understand: str | None = None,
    judge: str | None = None,
    judge_all: bool = False,
    redo: bool = False,
) -> Path:
    """Run one condition on every pair that has no result yet (all of them with `redo`,
    after a prompt change; the old rows are replaced). `understand` names another model
    for the Understand stage (default: LLM_UNDERSTAND_NAME, else the writer)."""
    results_dir.mkdir(parents=True, exist_ok=True)
    store = Store(results_dir / "store.sqlite")
    orchestrator = Orchestrator(store, llm, settings)
    writer_name = writer or settings.llm_name
    reader_name = understand or settings.llm_understand_name or writer_name
    if condition in BASELINE_CONDITIONS or reader_name == writer_name:
        reader_name = None  # no Understand stage, or the writer reads too
    out = results_file(results_dir, condition, writer_name, reader_name)
    done = set() if redo else _done(out)
    for pair in pairs:
        if pair.id in done:
            log.info("%s %s: done already", condition, pair.id)
            continue
        if condition in ZH_CONDITIONS and not has_prompt(pair.lang, "baseline_zh"):
            log.info("%s %s: no Zurich prompt for '%s', skipped", condition, pair.id, pair.lang)
            continue
        standard, easy = load_pair(pair)
        config = JobConfig(
            lang=pair.lang,
            level=pair.level,
            condition=condition,  # type: ignore[arg-type]
            writer_model=writer,
            understand_model=understand,
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
            **({"understand": reader_name} if reader_name else {}),
            "job_id": job.id,
            "status": job.status,
        }
        if job.status not in _OK:
            row["error"] = job.error
        else:
            try:
                row.update(_score(store, orchestrator, job, pair, standard, easy, judge, judge_all))
            except Exception as exc:  # a scoring call failed: the run goes on, the pair reruns
                log.warning("%s %s: scoring failed: %s", condition, pair.id, exc)
                row["status"] = "scoring_failed"
                row["error"] = f"{type(exc).__name__}: {exc}"[:500]
        _write_row(out, row)
        log.info("%s %s: %s", condition, pair.id, row.get("status"))
    return out


def _score(
    store: Store,
    orchestrator: Orchestrator,
    job: Any,
    pair: Pair,
    standard: SourceDocument,
    easy: SourceDocument,
    judge: str | None,
    judge_all: bool,
) -> dict[str, Any]:
    summary = store.get_artifact(job.id, "summary", PipelineSummary)
    draft = store.get_artifact(
        job.id, "draft", Draft, version=summary.final_version if summary else None
    )
    factsheet = store.get_artifact(job.id, "factsheet", FactSheet) or _reference_factsheet(
        store, orchestrator, pair, job.id
    )
    judge_report = store.get_artifact(job.id, "judge", JudgeReport, version=draft.version)
    if judge_report is None and judge_all and factsheet is not None:
        judge_report = _score_judge(store, orchestrator, job.id, standard, factsheet, draft, judge)
    # every version up to the final one: a split made in an earlier round stays in it
    edits = [
        edit
        for version in store.versions(job.id, "draft")
        if version <= draft.version
        for edit in store.get_artifact(job.id, "draft", Draft, version=version).code_edits
    ]
    row = score_output(job, draft, standard, easy, factsheet, judge_report, edits)
    if summary:
        row.update(rounds=summary.rounds, stop_reason=summary.stop_reason)
    return row


def _reference_factsheet(
    store: Store, orch: Orchestrator, pair: Pair, job_id: str
) -> FactSheet | None:
    """A fact sheet to score outputs without one (P0): reuse another condition's, or make one.
    Calls made here are scoring calls and are not counted as the condition's cost."""
    for other in store.list_jobs(limit=1000):
        if other.title == pair.id and other.id != job_id:
            fs = store.get_artifact(other.id, "factsheet", FactSheet)
            if fs is not None:
                return fs
    standard = store.get_artifact(job_id, "source", SourceDocument)
    fs, _ = stages.understand(
        orch.llm, standard, level=pair.level, model=orch.settings.llm_understand_name
    )
    # Completed by code as in the pipeline, so a baseline scored before any P1 or P2 job
    # exists is held to the same facts as one scored after them.
    fs = stages.complete_factsheet(fs, standard)
    store.put_artifact(job_id, "score_factsheet", fs)
    return fs


def _score_judge(store, orch, job_id, standard, factsheet, draft, judge_model) -> JudgeReport:
    model = judge_model or orch.settings.judge_name
    report, _ = stages.judge(orch.llm, standard, factsheet, draft, model=model)
    store.put_artifact(job_id, "score_judge", report, draft.version)
    return report
