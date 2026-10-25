"""The life of a job around the pipeline (docs/architecture.md §5 and §10):

- the counts the drafts list shows, written to the job row when the job is created,
  when the pipeline ends and when a review is saved, so the list opens no artifact;
- deletion, which takes the job's rows in the response cache with it;
- the retention purge (`data.retention_days`);
- the log filter that keeps a model's words out of the logs when an exception text
  carries them.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from leichtfacile.review import load_review, review_counts
from leichtfacile.schemas import Job, JobCounts, SourceDocument
from leichtfacile.store import Store

if TYPE_CHECKING:
    from leichtfacile.llm.client import LLMClient

log = logging.getLogger(__name__)


# -- counts ------------------------------------------------------------------------------


def source_counts(source: SourceDocument, counts: JobCounts | None = None) -> JobCounts:
    """`counts` with where the document came from, for the drafts list's second line."""
    info = source.source
    return (counts or JobCounts()).model_copy(
        update={
            "source_type": info.type,
            "source_uri": info.uri,
            "source_chars": len(source.text()) if info.type == "text" else None,
        }
    )


def job_counts(store: Store, job: Job) -> JobCounts:
    """Every count for the job as it stands: the source line, the final version's
    findings and facts, the review's progress. `review.py` is the one place that knows
    how findings and facts are counted (the review page reads it too), so the counts
    are computed once per job instead of once per row of the list (audit B3)."""
    counts = job.counts or JobCounts()
    if counts.source_type is None:
        source = store.get_artifact(job.id, "source", SourceDocument)
        if source is not None:
            counts = source_counts(source, counts)
    data = load_review(store, job)
    if data is None:
        return counts.model_copy(update={"has_draft": False})
    return counts.model_copy(update={"has_draft": True, **review_counts(data)})


# -- deletion and retention ------------------------------------------------------------


def remove_job(store: Store, llm: LLMClient, job_id: str) -> bool:
    """Delete the job with its artifacts and calls, and its prompts and answers from the
    response cache (`llm.cache`), which carry the document. False when the job does
    not exist or a worker is running it."""
    keys = store.cache_keys(job_id)
    if not store.delete_job(job_id):
        return False
    if keys:
        llm.forget_keys(keys)
    return True


def purge_expired(
    store: Store, llm: LLMClient, days: int, *, now: datetime | None = None
) -> list[str]:
    """Delete every job not changed for `days` days (`data.retention_days`), with its
    artifacts, calls and cache rows; running jobs stay. 0 days
    keeps everything. The ids deleted."""
    if days <= 0:
        return []
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    deleted = [job.id for job in store.jobs_older_than(cutoff) if remove_job(store, llm, job.id)]
    if deleted:
        log.info("retention: %d jobs older than %d days deleted", len(deleted), days)
    return deleted


# -- logs ------------------------------------------------------------------------------

# pydantic writes the offending value into its messages: `input_value='...', input_type=str`.
_INPUT_VALUE = re.compile(r"input_value=.*?(?=, input_type=|\]|$)", re.DOTALL)


def redact(text: str) -> str:
    return _INPUT_VALUE.sub("input_value=<redacted>", text)


class RedactingFilter(logging.Filter):
    """Keeps `input_value=...` excerpts out of a record's message and its formatted
    exception. The code that builds error texts leaves them out itself
    (`llm/json_out.redacted_error`); this is the net under it."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # a broken format string is the logger's problem, not ours
            return True
        clean = redact(message)
        if clean != message:
            record.msg, record.args = clean, ()
        if record.exc_info and not record.exc_text:
            text = logging.Formatter().formatException(record.exc_info)
            if redact(text) != text:
                record.exc_text = redact(text)  # the formatter uses it as it stands
        return True


def redact_logs() -> None:
    """Put the filter on every handler that is attached now: the root logger's (the
    CLI's `basicConfig`, a test's capture) and the last resort for records nobody
    handles. Safe to call more than once."""
    handlers = [*logging.getLogger().handlers, logging.lastResort]
    for handler in handlers:
        if handler is not None and not any(isinstance(f, RedactingFilter) for f in handler.filters):
            handler.addFilter(RedactingFilter())
