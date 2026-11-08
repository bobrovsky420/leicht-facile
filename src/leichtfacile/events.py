"""The event log of a job (docs/architecture.md §5): what happened to it and when.

Every change of a job's state is an event the store appends to `job_events` in the same
transaction as the artifact it belongs to (`Store.record`): `queued` (by whom, or from
which stage on a rerun, or `restart` when the service queued it again), `claimed` (a
worker took it), `stage_started` and `stage_finished` (the stage), `round_finished` (the
round's record), `finished` (the pipeline ended; the stage it ended at), `failed` (the
error), `cancelled` (by whom), `review_saved` (the version, who, whether complete) and
`exported` (the format, the version, who). An event holds no text of the document.

The job row's `status`, `stage` and `error` are projections of the events (`project`):
the store writes them from the event it records, nothing else writes them, and
`updated_at` is the time of the last event. The timeline the audit bundle prints, the
time a job ran, the wall-clock time of its stages (the progress page's estimate) and the
durations `/metrics` reports are read from the same log (`run_seconds`, `stage_seconds`,
`durations`), so they survive a restart and know the queue wait and code time too.
"""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import median

from leichtfacile.schemas import ROUND_KINDS, JobEvent

EVENT_KINDS = (
    "queued",
    "claimed",
    "stage_started",
    "stage_finished",
    "round_finished",
    "finished",
    "failed",
    "cancelled",
    "review_saved",
    "exported",
)
# The error a cancelled job carries (pipeline/orchestrator.py says the same).
CANCELLED = "cancelled"
# The events that end a run: the status they leave the job in.
RUN_ENDS = {"finished": "needs_review", "failed": "failed", "cancelled": "failed"}


def project(status: str | None, kind: str, payload: dict) -> dict[str, object]:
    """The columns of the job row an event sets (`status`, `stage`, `error`), from the
    event and the status the job has (`status`; None for a job being created)."""
    if kind == "queued":
        return {"status": "queued", "stage": None, "error": None}
    if kind == "claimed":
        return {"status": "running", "error": None}
    if kind == "stage_started":
        return {"stage": payload.get("stage")}
    if kind == "finished":
        return {"status": "needs_review", "stage": payload.get("stage", "review"), "error": None}
    if kind == "failed":
        return {"status": "failed", "error": payload.get("error")}
    if kind == "cancelled":
        return {"status": "failed", "error": CANCELLED}
    if kind == "review_saved" and status in ("needs_review", "done"):
        return {"status": "done" if payload.get("completed") else "needs_review"}
    return {}


def step_of(stage: str) -> str:
    """The progress page's step a stage belongs to: its first word, every kind of round
    under `repair` (`repair 2`, `recover`, `polish`)."""
    key = stage.split(" ", maxsplit=1)[0]
    return "repair" if key in ROUND_KINDS else key


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def last_run(events: list[JobEvent]) -> list[JobEvent]:
    """The events of the job's last run: from its last `claimed` on."""
    starts = [i for i, e in enumerate(events) if e.kind == "claimed"]
    return events[starts[-1] :] if starts else []


def run_end(events: list[JobEvent]) -> JobEvent | None:
    """The event that ended the last run (`RUN_ENDS`), None while it runs or never ran."""
    run = last_run(events)
    return next((e for e in reversed(run) if e.kind in RUN_ENDS), None) if run else None


def run_seconds(events: list[JobEvent]) -> float | None:
    """How long the last run took, from the worker taking the job to its end; None for
    a run that has not ended or a job that never ran."""
    run, end = last_run(events), run_end(events)
    if not run or end is None:
        return None
    return max((_aware(end.at) - _aware(run[0].at)).total_seconds(), 0.0)


def stage_seconds(events: list[JobEvent], now: datetime | None = None) -> dict[str, float]:
    """Wall-clock seconds per step (`step_of`) over the last run: every stage from its
    start to its end, the one still running up to `now` when given."""
    seconds: dict[str, float] = {}
    open_stage: tuple[str, datetime] | None = None
    for event in last_run(events):
        if event.kind == "stage_started":
            if open_stage is not None:  # a start without an end: the stage ended here
                _add(seconds, open_stage, _aware(event.at))
            open_stage = (str(event.payload.get("stage", "")), _aware(event.at))
        elif open_stage is not None and (event.kind == "stage_finished" or event.kind in RUN_ENDS):
            _add(seconds, open_stage, _aware(event.at))
            open_stage = None
    if open_stage is not None and now is not None:
        _add(seconds, open_stage, _aware(now))
    return seconds


def _add(seconds: dict[str, float], stage: tuple[str, datetime], end: datetime) -> None:
    key = step_of(stage[0])
    seconds[key] = seconds.get(key, 0.0) + max((end - stage[1]).total_seconds(), 0.0)


def stage_medians(samples: dict[str, list[float]]) -> dict[str, float]:
    return {key: median(values) for key, values in samples.items() if values}


def durations(by_job: dict[str, list[JobEvent]]) -> list[tuple[str, float]]:
    """How long each job's last run took and the status it ended in (`RUN_ENDS`), for
    `/metrics`; jobs still running or never run are left out."""
    out: list[tuple[str, float]] = []
    for events in by_job.values():
        end, seconds = run_end(events), run_seconds(events)
        if end is not None and seconds is not None:
            out.append((RUN_ENDS[end.kind], seconds))
    return out
