"""Example jobs: pre-computed audit bundles in track_2b/data/examples/jobs/, loaded into the store
on first start so the UI is not empty, and built from track_2b/data/examples/sources/ with
`python -m leichtfacile examples build` (needs a model endpoint).

The same sources are the prepared letters a visitor runs with one click; their recorded
runs in track_2b/data/examples/replay/ are made with `examples record` (llm/replay.py).

Only team-written or article-5 texts are used as sources (track_2b/docs/sources.md §4).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from leichtfacile import __version__
from leichtfacile.config import Paths
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

if TYPE_CHECKING:
    from leichtfacile.config import Settings
    from leichtfacile.llm.replay import Recording

log = logging.getLogger(__name__)
EXAMPLE_PREFIX = "Example: "


def examples_dir() -> Path:
    """EXAMPLES_DIR from the environment or .env, without the model settings (no key
    is needed to read the examples). The web app passes `Settings.examples_dir`."""
    return Paths().examples_dir


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
    from leichtfacile.lifecycle import job_counts  # lifecycle imports this module

    counts = job_counts(store, store.get_job(job_id))  # type: ignore[arg-type]
    store.update_job(job_id, status="needs_review", stage="review", counts=counts)
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


def open_problems(rules: RuleFindings | None, judge: JudgeReport | None) -> int:
    """What the UI shows as errors on a draft: rule findings of severity error, facts
    the judge finds missing or distorted, and statements it finds unsupported. A fact
    the judge finds missing although code finds its value counts too, though the review
    page shows it in amber ("judge doubts"): an example should have neither."""
    count = sum(1 for f in rules.findings if f.severity == "error") if rules else 0
    if judge:
        count += sum(1 for c in judge.fact_checks if c.status != "present")
        count += len(judge.unsupported)
    return count


def build_examples(
    level: str = "A2",
    condition: str = "P2",
    folder: Path | None = None,
    only: list[str] | None = None,
    allow_problems: bool = False,
) -> list[Path]:
    """Run the pipeline on every example source (or the ones named in `only`, by file
    name without suffix) and write the bundles (needs the endpoint). A first-time
    visitor reads a red error count as a fault of the application, so a job whose final
    draft still has errors is not written unless `allow_problems` is set; the bundle
    already in jobs/ stays."""
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
        summary = store.get_artifact(job.id, "summary", PipelineSummary)
        final = summary.final_version if summary else None
        left = open_problems(
            store.get_artifact(job.id, "rules", RuleFindings, version=final),
            store.get_artifact(job.id, "judge", JudgeReport, version=final),
        )
        if left and not allow_problems:
            log.error("example %s not written: %d errors left in draft v%s", path.name, left, final)
            continue
        bundle = build_bundle(store, job)
        bundle["job"]["id"] = f"example-{path.stem}"
        target = out_dir / f"{path.stem}.json"
        target.write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
        written.append(target)
    return written


def record_examples(
    folder: Path | None = None,
    only: list[str] | None = None,
    attempts: int = 6,
    parallel: int = 3,
    allow_problems: bool = False,
) -> list[Path]:
    """Record a clean run of every prepared letter (or the ones named in `only`) for
    the replay (llm/replay.py; needs the endpoint). A letter runs as its Run button
    sends it, with a `Recorder` as the response cache, `parallel` attempts at a time
    until a batch has a run whose final draft shows no error, at most `attempts` in
    all; the clean run with the fewest warnings is written to replay/<letter>.json. A
    letter without a clean run keeps its file, unless `allow_problems` writes the run
    with the fewest errors. Every attempt stays in `examples-record.sqlite`."""
    from concurrent.futures import ThreadPoolExecutor
    from functools import partial

    from leichtfacile.config import get_settings
    from leichtfacile.llm.replay import FOLDER, write_recording

    folder = folder or examples_dir()
    settings = get_settings()
    store = Store(settings.data_dir / "examples-record.sqlite")
    written = []
    with ThreadPoolExecutor(parallel) as pool:
        for example in example_sources(folder):
            if only and example["id"] not in only:
                continue
            attempt = partial(_record_once, store, settings, example)
            runs: list[_Attempt] = []
            while len(runs) < attempts and not any(r.clean for r in runs):
                batch = range(len(runs) + 1, min(len(runs) + parallel, attempts) + 1)
                runs += pool.map(attempt, batch)
            usable = [r for r in runs if r.clean or (allow_problems and r.recording)]
            if not usable:
                log.error("letter %s not recorded: no clean run in %d", example["id"], len(runs))
                continue
            best = min(usable, key=lambda r: (r.errors, r.warnings))
            target = folder / FOLDER / f"{example['id']}.json"
            write_recording(target, best.recording, best.answers)  # type: ignore[arg-type]
            written.append(target)
    return written


@dataclass
class _Attempt:
    """One run of a letter in `record_examples`: once it reached review, its recording
    with the answers and the counts the drafts list shows."""

    recording: Recording | None = None
    answers: list[dict[str, Any]] = field(default_factory=list)
    errors: int = 0
    warnings: int = 0

    @property
    def clean(self) -> bool:
        return self.recording is not None and self.errors == 0


def _record_once(store: Store, settings: Settings, example: dict[str, str], n: int) -> _Attempt:
    """Run the letter as its Run button sends it (`example_submission`, `create_job`),
    with a `Recorder` as the response cache."""
    from leichtfacile.llm.client import LLMClient
    from leichtfacile.llm.replay import Recorder, Recording, replay_settings
    from leichtfacile.pipeline.orchestrator import Orchestrator
    from leichtfacile.web.jobs import create_job, example_submission

    name = example["id"]
    recorder = Recorder()
    llm = LLMClient(settings, cache=recorder, usage_sink=recorder.observe)
    try:
        job = create_job(store, settings, example_submission(example))
        Orchestrator(store, llm, settings).run(job.id)
    except Exception:  # one attempt failing must not end the others
        log.exception("letter %s, attempt %d failed", name, n)
        return _Attempt()
    job = store.get_job(job.id)
    if job is None or job.status != "needs_review" or job.counts is None:
        log.warning("letter %s, attempt %d: no review: %s", name, n, job.error if job else None)
        return _Attempt()
    summary = store.get_artifact(job.id, "summary", PipelineSummary)
    final = summary.final_version if summary else None
    problems = open_problems(
        store.get_artifact(job.id, "rules", RuleFindings, version=final),
        store.get_artifact(job.id, "judge", JudgeReport, version=final),
    )
    counts = job.counts
    errors = max(problems, counts.errors)  # the build's measure and what the list shows
    seconds = sum(u.latency_ms for u in job.usage) / 1000
    log.info("letter %s, attempt %d: job %s, %d errors, %d warnings, %d calls, %.0f s",
             name, n, job.id, errors, counts.warnings, len(job.usage), seconds)  # fmt: skip
    url = urlsplit(settings.llm_base_url)
    recording = Recording(
        letter=name,
        recorded_at=datetime.now(UTC),
        version=__version__,
        endpoint=f"{url.scheme}://{url.hostname}",
        settings=replay_settings(settings, judge=summary.judge_model if summary else None),
        seconds=seconds,
        calls=len(job.usage),
        result={
            "job": job.id,
            "final_version": final,
            "errors": errors,
            "warnings": counts.warnings,
            "facts_present": counts.facts_present,
            "facts_total": counts.facts_total,
        },
    )
    return _Attempt(recording, recorder.answers, errors, counts.warnings)
