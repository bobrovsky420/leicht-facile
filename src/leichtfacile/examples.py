"""Example jobs: pre-computed audit bundles in data/examples/jobs/, loaded into the store
on first start so the UI is not empty, and built from data/examples/sources/ with
`python -m leichtfacile examples build` (needs a model endpoint).

Only team-written or article-5 texts are used as sources (docs/sources.md §4).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from leichtfacile.schemas import (
    Draft,
    FactSheet,
    JobConfig,
    JudgeReport,
    PipelineSummary,
    RepairRecord,
    ReviewState,
    RuleFindings,
    SourceDocument,
    UsageRecord,
)
from leichtfacile.store import Store

log = logging.getLogger(__name__)
EXAMPLE_PREFIX = "Example: "


def examples_dir() -> Path:
    return Path(os.environ.get("EXAMPLES_DIR", "data/examples"))


def example_sources(folder: Path | None = None) -> list[dict[str, str]]:
    """The team-written example texts offered on the start page: id, title and text,
    plus the job settings of the decision mode (`mode`, `addressee`, `notice`) from the
    JSON file next to a source, when it has one (`example_config`)."""
    folder = (folder or examples_dir()) / "sources"
    out = []
    for path in sorted(folder.glob("*.txt")) + sorted(folder.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = lines[0].lstrip("#").strip() if lines else path.stem
        settings = example_config(path)
        fields = {k: settings[k] for k in ("mode", "addressee", "notice") if settings.get(k)}
        out.append({"id": path.stem, "title": title, "text": text, **fields})
    return out


def import_bundle(store: Store, bundle: dict[str, Any], *, job_id: str | None = None) -> str | None:
    """Recreate a job from its audit bundle. Returns the job id, or None if it exists."""
    job_data = bundle["job"]
    job_id = job_id or job_data["id"]
    if store.get_job(job_id) is not None:
        return None
    config = JobConfig.model_validate(job_data["config"])
    title = job_data.get("title") or job_id
    if not title.startswith(EXAMPLE_PREFIX):
        title = EXAMPLE_PREFIX + title
    store.create_job(config, title=title, job_id=job_id)  # the bundle's id keeps links stable
    store.put_artifact(job_id, "source", SourceDocument.model_validate(bundle["source"]))
    if bundle.get("factsheet"):
        store.put_artifact(job_id, "factsheet", FactSheet.model_validate(bundle["factsheet"]))
    for draft in bundle.get("drafts") or []:
        d = Draft.model_validate(draft)
        store.put_artifact(job_id, "draft", d, d.version)
    for rules in bundle.get("rule_findings") or []:
        r = RuleFindings.model_validate(rules)
        store.put_artifact(job_id, "rules", r, r.draft_version)
    for judge in bundle.get("judge_reports") or []:
        j = JudgeReport.model_validate(judge)
        store.put_artifact(job_id, "judge", j, j.draft_version)
    for record in bundle.get("repair_records") or []:
        rec = RepairRecord.model_validate(record)
        store.put_artifact(job_id, "repair", rec, rec.draft_version)
    if bundle.get("summary"):
        store.put_artifact(job_id, "summary", PipelineSummary.model_validate(bundle["summary"]))
    if bundle.get("review"):
        store.put_artifact(job_id, "review", ReviewState.model_validate(bundle["review"]))
    for usage in job_data.get("usage") or []:
        from leichtfacile.llm.client import Usage

        u = UsageRecord.model_validate(usage)
        store.add_usage(
            job_id, Usage(u.stage, u.model, u.tokens_in, u.tokens_out, u.latency_ms, u.cached)
        )
    store.update_job(job_id, status="needs_review", stage="review")
    return job_id


def load_examples(store: Store, folder: Path | None = None) -> list[str]:
    folder = (folder or examples_dir()) / "jobs"
    loaded = []
    for path in sorted(folder.glob("*.json")):
        try:
            job_id = import_bundle(store, json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:  # a broken example must not stop the service
            log.warning("example %s not loaded: %s", path.name, exc)
            continue
        if job_id:
            loaded.append(job_id)
    if loaded:
        log.info("loaded %d example jobs", len(loaded))
    return loaded


def example_config(path: Path) -> dict[str, Any]:
    """Job settings for one example source from the JSON file next to it, if any:
    `entscheid.txt` with `entscheid.json` holding `{"mode": "decision", "addressee": ...}`.
    Only JobConfig fields are allowed."""
    sidecar = path.with_suffix(".json")
    if not sidecar.is_file():
        return {}
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    unknown = set(data) - set(JobConfig.model_fields)
    if unknown:
        raise ValueError(f"{sidecar.name}: not job settings: {', '.join(sorted(unknown))}")
    return data


def build_examples(
    level: str = "A2",
    condition: str = "P2",
    folder: Path | None = None,
    only: list[str] | None = None,
) -> list[Path]:
    """Run the pipeline on every example source (or the ones named in `only`, by file
    name without suffix) and write the bundles (needs the endpoint)."""
    from leichtfacile.config import get_settings
    from leichtfacile.export.bundle import build_bundle
    from leichtfacile.ingest import ingest_file
    from leichtfacile.llm.client import LLMClient
    from leichtfacile.pipeline.orchestrator import Orchestrator

    folder = folder or examples_dir()
    settings = get_settings()
    store = Store(settings.data_dir / "examples-build.sqlite")
    orchestrator = Orchestrator(store, LLMClient.from_settings(settings), settings)
    out_dir = folder / "jobs"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for path in sorted((folder / "sources").glob("*")):
        if path.suffix.lower() not in (".txt", ".md", ".html", ".htm", ".pdf"):
            continue
        if only and path.stem not in only:
            continue
        # The language is detected: the sources include a German and a French letter.
        source = ingest_file(path, doc_id=f"example-{path.stem}",
                             license_note="written by the team; free to use")  # fmt: skip
        settings_for = {"lang": source.lang, "level": level, "condition": condition,
                        "max_repair_rounds": settings.max_repair_rounds,
                        "max_facts_rounds": settings.max_facts_rounds}  # fmt: skip
        config = JobConfig.model_validate(settings_for | example_config(path))
        job = store.create_job(config, title=source.title or path.stem)
        store.put_artifact(job.id, "source", source)
        orchestrator.run(job.id)
        job = store.get_job(job.id)
        if job.status != "needs_review":
            log.error("example %s failed: %s", path.name, job.error)
            continue
        bundle = build_bundle(store, job)
        bundle["job"]["id"] = f"example-{path.stem}"
        target = out_dir / f"{path.stem}.json"
        target.write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
        written.append(target)
    return written
