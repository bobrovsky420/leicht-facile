"""Log output (audit T6): one handler, a text or a JSON line per record, the request id
and the job id on every record, and the redacting filter of lifecycle.py in front.

`request_id` is set by the request middleware (web/observability.py) for the time a
request is handled, `job_id` by the orchestrator for the time a worker runs a job.
Both are context variables, so a line written anywhere in between carries them
without being told. `configure_logging` is called by `create_app` with `LOG_LEVEL`
and `LOG_FORMAT`; the CLI's other commands keep `logging.basicConfig`.

Privacy (track_2b/docs/architecture.md §10) is the business of what is logged, not of
this module: no document text above DEBUG, and the redacting filter as the net.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import IO

from leichtfacile.lifecycle import RedactingFilter, redact_logs

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
job_id: ContextVar[str | None] = ContextVar("job_id", default=None)
HANDLER_NAME = "leichtfacile.log"
# Fields a record may carry in `extra` that the JSON line keeps (the access line's).
EXTRA_FIELDS = ("method", "path", "status", "duration_ms", "client")


class ContextFilter(logging.Filter):
    """Puts the request id and the job id of the moment on the record, so that a
    formatter, or a test's capture, finds them there."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            record.request_id = request_id.get()
        if getattr(record, "job_id", None) is None:
            record.job_id = job_id.get()
        return True


def context_of(record: logging.LogRecord) -> dict[str, object]:
    """The ids and the extra fields the record carries, in a fixed order, None left
    out. The ids come from the record when a `ContextFilter` put them there, else
    from the context variables of the moment."""
    fields: dict[str, object] = {
        "request_id": getattr(record, "request_id", None) or request_id.get(),
        "job_id": getattr(record, "job_id", None) or job_id.get(),
    }
    for name in EXTRA_FIELDS:
        fields[name] = getattr(record, name, None)
    return {k: v for k, v in fields.items() if v is not None}


def _exception_text(formatter: logging.Formatter, record: logging.LogRecord) -> str | None:
    """The traceback as the redacting filter left it (`exc_text`), else formatted."""
    if record.exc_info and not record.exc_text:
        record.exc_text = formatter.formatException(record.exc_info)
    return record.exc_text or None


class TextFormatter(logging.Formatter):
    """`LEVEL logger: message request_id=... job_id=...`, the traceback on the lines
    after. The access line names its method, path and status in the message itself."""

    def __init__(self) -> None:
        super().__init__("%(levelname)s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        line = self.formatMessage(record)
        ids = context_of(record)
        line += "".join(f" {k}={ids[k]}" for k in ("request_id", "job_id") if k in ids)
        exception = _exception_text(self, record)
        return f"{line}\n{exception}" if exception else line


class JsonFormatter(logging.Formatter):
    """One JSON object per line: time (UTC), level, logger, message, then the ids and
    the fields the record carries, and `exception` with the traceback."""

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **context_of(record),
        }
        exception = _exception_text(self, record)
        if exception:
            line["exception"] = exception
        return json.dumps(line, ensure_ascii=False, default=str)


class StderrHandler(logging.StreamHandler):
    """Writes to whatever `sys.stderr` is at the time (a test harness swaps it)."""

    def __init__(self) -> None:
        logging.Handler.__init__(self)

    @property  # type: ignore[override]
    def stream(self) -> IO[str]:
        return sys.stderr

    @stream.setter
    def stream(self, value: IO[str]) -> None:  # StreamHandler's constructor is skipped
        pass


def configure_logging(level: str, fmt: str, stream: IO[str] | None = None) -> logging.Handler:
    """One handler on the root logger with the text or the JSON format, named so that
    a second call (another app in the same process, the tests) replaces it instead of
    doubling the lines; the `leichtfacile` loggers at `level`; the redacting filter on
    this and every other handler. `stream` is for tests; stderr otherwise."""
    root = logging.getLogger()
    for old in [h for h in root.handlers if h.name == HANDLER_NAME]:
        root.removeHandler(old)
    handler: logging.Handler = StderrHandler() if stream is None else logging.StreamHandler(stream)
    handler.name = HANDLER_NAME
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    handler.addFilter(RedactingFilter())
    handler.addFilter(ContextFilter())
    root.addHandler(handler)
    logging.getLogger("leichtfacile").setLevel(level.upper())
    redact_logs()  # the other handlers too: a test's capture, the CLI's basicConfig
    return handler
