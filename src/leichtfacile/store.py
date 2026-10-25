"""SQLite storage for jobs, artifacts and model calls (docs/architecture.md §5).

One database file in data.dir. Artifacts are pydantic models stored as JSON text, with
a version per name (draft 1, draft 2, ...). The standard library is enough: the schema
is small and there are a few worker threads plus the web handlers.

The jobs table is also the work queue: a worker claims the oldest queued job with one
guarded UPDATE (`claim_next_queued`), and every change of status that must not race
with the workers goes through `transition`, which names the statuses it may start from.

The schema is versioned with `PRAGMA user_version`: the base tables, then one group per
later change (`_MIGRATIONS`), of statements or of rewrites of the stored JSON; a database
made by an older version gets the groups it lacks on open, so the models in schemas.py
read one shape and carry no fallbacks for old data.

The connections are a small pool (`POOL_SIZE`): an operation takes one and gives it
back, so the web handlers read while a worker writes (WAL: readers never wait for a
writer) and two writers wait for each other within `BUSY_TIMEOUT_S` instead of
failing (audit B4). A write transaction begins with `BEGIN IMMEDIATE`, which takes the
write lock up front, so a writer waits its turn before its first statement rather
than failing midway.
"""

from __future__ import annotations

import json
import queue
import re
import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from leichtfacile.llm.client import Usage
from leichtfacile.schemas import (
    Job,
    JobConfig,
    JobCounts,
    UsageRecord,
    canonical_condition,
    utcnow,
)

T = TypeVar("T", bound=BaseModel)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    stage TEXT,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    config TEXT NOT NULL,
    error TEXT
);
CREATE TABLE IF NOT EXISTS artifacts (
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (job_id, name, version)
);
CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    model TEXT NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    cached INTEGER NOT NULL DEFAULT 0,
    at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS llm_calls_job ON llm_calls(job_id);
"""
Migration = str | Callable[[sqlite3.Connection], None]  # a statement, or a rewrite


def _rewrite_json(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    transform: Callable[[dict[str, Any]], dict[str, Any]],
    where: str = "",
) -> None:
    """Apply `transform` to the JSON document in `column` of every row of `table` (those
    matching `where`) and write back the documents it changed."""
    rows = conn.execute(f"SELECT rowid, {column} FROM {table} {where}").fetchall()
    for row in rows:
        # Parsed twice: a transform that changes a nested value in place must still
        # compare as a change.
        data = json.loads(row[column])
        changed = transform(json.loads(row[column]))
        if changed != data:
            conn.execute(
                f"UPDATE {table} SET {column} = ? WHERE rowid = ?",
                (json.dumps(changed, ensure_ascii=False), row["rowid"]),
            )


def _early_job_config(config: dict[str, Any]) -> dict[str, Any]:
    config.pop("live", None)  # a run without recorded answers; went on 23 October 2026
    if "condition" in config:
        config["condition"] = canonical_condition(config["condition"])
    return config


def _early_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if "condition" in summary:
        summary["condition"] = canonical_condition(summary["condition"])
    return summary


def _early_review(review: dict[str, Any]) -> dict[str, Any]:
    # Before 11 October 2026 a review carried no `saved_at`: its latest decision stands in.
    stamps = [d.get("at") for d in review.get("decisions") or [] if d.get("at")]
    if not review.get("saved_at") and stamps:
        review["saved_at"] = max(stamps)
    return review


def _rewrite_early_october(conn: sqlite3.Connection) -> None:
    """What the first weeks stored differently: the conditions C0 to C2 (P0 to P2 since
    6 October 2026), the retired `live` field and a review without its stamp."""
    _rewrite_json(conn, "jobs", "config", _early_job_config)
    _rewrite_json(conn, "artifacts", "data", _early_summary, "WHERE name = 'summary'")
    _rewrite_json(conn, "artifacts", "data", _early_review, "WHERE name = 'review'")


# The stop reasons as the summaries stored them until 25 October 2026, and their codes.
_OLD_STOP_REASONS = {
    "baseline": "baseline",
    "P1": "p1",
    "no problems left": "no_problems",
    "only warnings left": "no_blocking",
    "no blocking problems left": "no_blocking",
    "a repair round failed": "round_failed",
    "a repair round brought no progress": "no_progress",
    "no missing facts left": "no_missing_facts",
    "a facts round failed": "facts_round_failed",
    "a facts round brought no progress": "facts_no_progress",
}


def _stop_code(text: str) -> str:
    if text in _OLD_STOP_REASONS:
        return _OLD_STOP_REASONS[text]
    if text.startswith("stopped after"):
        return "max_facts_rounds" if "facts" in text else "max_rounds"
    return "no_problems"


def _round_limits(config: dict[str, Any]) -> dict[str, Any]:
    """A job's two round limits become its pipeline options (schemas.PipelineOptions);
    the options the job had no field for take their defaults."""
    if "max_repair_rounds" in config or "max_facts_rounds" in config:
        config["pipeline"] = {
            "repair_rounds": config.pop("max_repair_rounds", 3),
            "facts_rounds": config.pop("max_facts_rounds", 1),
        }
    return config


def _rewrite_round_records(conn: sqlite3.Connection) -> None:
    """25 October 2026: the summary's four round counters become one record per round,
    rebuilt from the job's repair records (from its draft versions for the jobs of the
    first days, which have none), and its stop reason becomes a code."""
    _rewrite_json(conn, "jobs", "config", _round_limits)
    summaries = conn.execute(
        "SELECT rowid, job_id, data FROM artifacts WHERE name = 'summary'"
    ).fetchall()
    for row in summaries:
        data = json.loads(row["data"])
        if not isinstance(data.get("rounds"), int):
            continue  # stored with records already
        records = conn.execute(
            "SELECT version, data FROM artifacts WHERE job_id = ? AND name = 'repair' "
            "ORDER BY version",
            (row["job_id"],),
        ).fetchall()
        rounds: list[dict[str, Any]] = []
        if records:
            counts: dict[str, int] = {}
            for record in records:
                kind = json.loads(record["data"]).get("kind", "repair")
                counts[kind] = counts.get(kind, 0) + 1
                parent = json.loads(record["data"]).get("parent_version", record["version"] - 1)
                rounds.append(
                    {
                        "kind": kind,
                        "number": counts[kind],
                        "parent_version": parent,
                        "version": record["version"],
                    }
                )
        else:
            versions = conn.execute(
                "SELECT version FROM artifacts WHERE job_id = ? AND name = 'draft' AND version > 1 "
                "ORDER BY version",
                (row["job_id"],),
            ).fetchall()
            rounds = [
                {"kind": "repair", "number": n, "parent_version": v["version"] - 1,
                 "version": v["version"]}
                for n, v in enumerate(versions, 1)
            ]  # fmt: skip
        data["rounds"] = rounds
        for key in ("facts_rounds", "vocabulary_rounds", "polish_rounds"):
            data.pop(key, None)
        data["stop_reason"] = _stop_code(str(data.get("stop_reason", "")))
        conn.execute(
            "UPDATE artifacts SET data = ? WHERE rowid = ?",
            (json.dumps(data, ensure_ascii=False), row["rowid"]),
        )


def _finding_keys(rules: dict[str, Any]) -> dict[str, Any]:
    """25 October 2026: a finding carries its message as key and values only. One stored
    with the English text alone (before 12 October) keeps that text as the value of the
    `legacy` template."""
    findings = []
    for finding in rules.get("findings") or []:
        if "key" in finding:
            findings.append(finding)
            continue
        text = finding.pop("message", "")
        key = finding.pop("message_key", None)
        params = finding.pop("message_params", None) or {}
        if not key:
            key, params = "legacy", {"text": text}
        findings.append({**finding, "key": key, "params": params})
    return {**rules, "findings": findings}


def _rewrite_finding_keys(conn: sqlite3.Connection) -> None:
    _rewrite_json(conn, "artifacts", "data", _finding_keys, "WHERE name = 'rules'")


# 25 October 2026: a rule has one id whatever the language (rules/catalog.py). The
# French ids lost their -FR suffix, GRAM-08-FR became GRAM-09, four French keys became
# sub-keys of the shared template, and the templates whose text differed between the
# languages took the difference as a value.
_FR_KEYS = {
    "LEX-01-FR": "LEX-01.no_compound",
    "LEX-05-FR": "LEX-05.inclusive",
    "GRAM-04-FR": "GRAM-04.future",
}
_TOOK_VALUES: dict[str, dict[str, dict[str, str]]] = {  # key -> language -> the values
    "GRAM-03": {"de": {"mood": "Konjunktiv"}, "fr": {"mood": "Subjonctif"}},
    "LEX-02.weekdays": {
        "de": {"expected": "Montag bis Freitag"},
        "fr": {"expected": "du lundi au vendredi"},
    },
    "LEX-04.slash": {
        "de": {"first": "und", "second": "oder"},
        "fr": {"first": "et", "second": "ou"},
    },
    "LEX-06": {"de": {"address": "Sie"}, "fr": {"address": "vous"}},
    "LEX-06.no_address": {"de": {"address": "Sie"}, "fr": {"address": "vous"}},
    "NUM-06": {"de": {"expected": "Prozent"}, "fr": {"expected": "pour cent"}},
}
_TOOK_SUGGESTION = {"NUM-02", "NUM-04.range"}  # expected: what the check suggested


def _neutral_finding(finding: dict[str, Any]) -> dict[str, Any]:
    rule_id, key = str(finding.get("rule_id", "")), str(finding.get("key", ""))
    lang = "fr" if rule_id.endswith("-FR") else "de"
    if rule_id.endswith("-FR"):
        rule_id = "GRAM-09" if rule_id == "GRAM-08-FR" else rule_id[:-3]
    if key in _FR_KEYS:
        key = _FR_KEYS[key]
    else:
        key = re.sub(r"^GRAM-08-FR", "GRAM-09", key)
        key = re.sub(r"^([A-Z]+-\d{2})-FR", r"\1", key)
    params = dict(finding.get("params") or {})
    for name, value in _TOOK_VALUES.get(key, {}).get(lang, {}).items():
        params.setdefault(name, value)
    if key in _TOOK_SUGGESTION and "expected" not in params and finding.get("suggestion"):
        params["expected"] = finding["suggestion"]
    return {**finding, "rule_id": rule_id, "key": key, "params": params}


def _neutral_rule_ids(rules: dict[str, Any]) -> dict[str, Any]:
    return {**rules, "findings": [_neutral_finding(f) for f in rules.get("findings") or []]}


def _rewrite_rule_ids(conn: sqlite3.Connection) -> None:
    _rewrite_json(conn, "artifacts", "data", _neutral_rule_ids, "WHERE name = 'rules'")


# One group per schema version after the base; `PRAGMA user_version` counts the groups
# applied. Never change a group once it has shipped: add the next one.
_MIGRATIONS: tuple[tuple[Migration, ...], ...] = (
    (  # 1 (11 October 2026): the counts for the drafts list on the job row, the cache
        # key of every model call so that a job's cache rows go with it, an index for
        # the queue and the list filters
        "ALTER TABLE jobs ADD COLUMN counts TEXT",
        "ALTER TABLE llm_calls ADD COLUMN cache_key TEXT",
        "CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status, updated_at)",
    ),
    (_rewrite_early_october,),  # 2 (25 October 2026): old names and fields rewritten
    (_rewrite_round_records,),  # 3 (25 October 2026): one record per round, stop codes
    (_rewrite_finding_keys,),  # 4 (25 October 2026): findings as key and values
    (_rewrite_rule_ids,),  # 5 (25 October 2026): one rule id whatever the language
)
SCHEMA_VERSION = len(_MIGRATIONS)
# Connections kept open at most: the workers and a few web handlers at a time.
POOL_SIZE = 8
BUSY_TIMEOUT_S = 5.0  # how long a writer waits for another writer's transaction
# The statuses a job can be in while no worker holds it. Only these may be deleted,
# rerun or queued again; a running job is stopped first (`JobRunner.cancel`).
IDLE_STATUSES: tuple[str, ...] = ("queued", "needs_review", "done", "failed")


class Store:
    def __init__(self, path: Path, pool_size: int = POOL_SIZE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._idle: queue.LifoQueue[sqlite3.Connection] = queue.LifoQueue()
        self._size = max(1, pool_size)
        self._open = 0  # connections made, idle or in use
        self._open_lock = threading.Lock()
        self._closed = False
        with self._tx() as conn:
            conn.executescript(_SCHEMA)
            _migrate(conn)

    def _connect(self) -> sqlite3.Connection:
        # Explicit transactions (`_tx`); a connection moves between threads (the pool);
        # WAL so that readers never wait for the writer; the busy timeout for writers.
        conn = sqlite3.connect(
            self.path, check_same_thread=False, autocommit=True, timeout=BUSY_TIMEOUT_S
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _take(self) -> sqlite3.Connection:
        """An idle connection, a new one while the pool is under its size, else the
        next one given back."""
        try:
            return self._idle.get_nowait()
        except queue.Empty:
            pass
        with self._open_lock:
            if self._closed:
                raise sqlite3.ProgrammingError("Cannot operate on a closed database.")
            grow = self._open < self._size
            if grow:
                self._open += 1
        if not grow:
            try:
                return self._idle.get(timeout=30.0)
            except queue.Empty:
                raise sqlite3.OperationalError("no database connection became free") from None
        try:
            return self._connect()
        except Exception:
            with self._open_lock:
                self._open -= 1
            raise

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """A connection for one operation, back in the pool afterwards."""
        conn = self._take()
        try:
            yield conn
        finally:
            self._idle.put(conn)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """One write transaction, committed at the end, rolled back on an exception."""
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    def close(self) -> None:
        """Close every connection, each once the operation using it has given it back."""
        with self._open_lock:
            if self._closed:
                return
            self._closed = True
            count = self._open
        for _ in range(count):
            self._idle.get().close()

    @property
    def connections(self) -> int:
        """Connections open now, idle or in use (at most the pool's size)."""
        with self._open_lock:
            return self._open

    @property
    def schema_version(self) -> int:
        with self._connection() as conn:
            return int(conn.execute("PRAGMA user_version").fetchone()[0])

    # -- jobs -----------------------------------------------------------------------

    def create_job(
        self,
        config: JobConfig,
        title: str | None = None,
        job_id: str | None = None,
        counts: JobCounts | None = None,
    ) -> Job:
        job = Job(id=job_id or uuid.uuid4().hex[:12], title=title, config=config, counts=counts)
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO jobs (id, status, stage, title, created_at, updated_at, config, "
                "counts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job.id,
                    job.status,
                    job.stage,
                    job.title,
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                    job.config.model_dump_json(),
                    counts.model_dump_json() if counts else None,
                ),
            )
        return job

    def get_job(self, job_id: str) -> Job | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            calls = conn.execute(
                "SELECT stage, model, tokens_in, tokens_out, latency_ms, cached "
                "FROM llm_calls WHERE job_id = ? ORDER BY id",
                (job_id,),
            ).fetchall()
        return _job(row, [UsageRecord(**dict(c)) for c in calls])

    def list_jobs(
        self, limit: int = 50, *, status: str | None = None, lang: str | None = None
    ) -> list[Job]:
        """The newest jobs first, filtered in SQL by status and document language."""
        where, params = _filters(status, lang)
        with self._connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs{where} ORDER BY created_at DESC LIMIT ?", (*params, limit)
            ).fetchall()
        return [_job(r, []) for r in rows]

    def count_jobs(self, status: str | None = None) -> int:
        """How many jobs there are, or how many have this status."""
        where, params = _filters(status, None)
        with self._connection() as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM jobs{where}", params).fetchone()
        return int(row[0])

    def status_counts(self, lang: str | None = None) -> dict[str, int]:
        """How many jobs have each status, for the filter tabs of the drafts list."""
        where, params = _filters(None, lang)
        with self._connection() as conn:
            rows = conn.execute(
                f"SELECT status, COUNT(*) AS n FROM jobs{where} GROUP BY status", params
            ).fetchall()
        return {r["status"]: int(r["n"]) for r in rows}

    def langs(self) -> list[str]:
        """The document languages of the stored jobs, sorted."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT json_extract(config, '$.lang') AS lang FROM jobs "
                "WHERE lang IS NOT NULL ORDER BY lang"
            ).fetchall()
        return [r["lang"] for r in rows]

    def update_job(self, job_id: str, **fields: object) -> None:
        with self._tx() as conn:
            conn.execute(*_update(job_id, fields))

    def transition(
        self, job_id: str, status: str, *, only_from: tuple[str, ...], **fields: object
    ) -> bool:
        """Set the status, and `fields` with it, only while the job has one of the
        `only_from` statuses: one guarded UPDATE, so a worker that takes the job in the
        same moment cannot be overtaken. False when the job has another status or
        does not exist."""
        sql, params = _update(job_id, {"status": status, **fields})
        marks = ", ".join("?" for _ in only_from)
        with self._tx() as conn:
            cur = conn.execute(f"{sql} AND status IN ({marks})", (*params, *only_from))
        return cur.rowcount > 0

    def claim_next_queued(self) -> str | None:
        """Take the job that has waited longest for a worker: its status becomes
        `running` in the same transaction, so two workers never take the same job."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT id FROM jobs WHERE status = 'queued' ORDER BY updated_at, created_at "
                "LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            sql, params = _update(row["id"], {"status": "running"})
            cur = conn.execute(f"{sql} AND status = 'queued'", params)
            return row["id"] if cur.rowcount else None

    def requeue(self, job_id: str, *, delete: Sequence[str], trim: Sequence[str] = ()) -> bool:
        """Queue the job again for a rerun: without the artifacts named in `delete` and
        without the versions above 1 of those in `trim`, in one transaction, and only
        while no worker holds it (`IDLE_STATUSES`). False when it is running or does
        not exist; nothing is deleted then."""
        sql, params = _update(job_id, {"status": "queued", "stage": None, "error": None})
        marks = ", ".join("?" for _ in IDLE_STATUSES)
        with self._tx() as conn:
            cur = conn.execute(f"{sql} AND status IN ({marks})", (*params, *IDLE_STATUSES))
            if not cur.rowcount:
                return False
            conn.executemany(
                "DELETE FROM artifacts WHERE job_id = ? AND name = ? AND version > 1",
                [(job_id, n) for n in trim],
            )
            conn.executemany(
                "DELETE FROM artifacts WHERE job_id = ? AND name = ?",
                [(job_id, n) for n in delete],
            )
        return True

    def requeue_running(self) -> list[str]:
        """Jobs left `running` by a process that stopped: queued again, for the start."""
        with self._tx() as conn:
            ids = [
                r["id"]
                for r in conn.execute("SELECT id FROM jobs WHERE status = 'running'").fetchall()
            ]
            for job_id in ids:
                conn.execute(*_update(job_id, {"status": "queued"}))
        return ids

    def delete_job(self, job_id: str) -> bool:
        """Remove the job with its artifacts and calls, unless a worker is running it.
        False when nothing was deleted; `get_job` tells the two reasons apart."""
        with self._tx() as conn:
            cur = conn.execute("DELETE FROM jobs WHERE id = ? AND status != 'running'", (job_id,))
        return cur.rowcount > 0

    def jobs_older_than(self, cutoff: datetime) -> list[Job]:
        """Jobs last changed before `cutoff` that no worker holds, for the purge."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE updated_at < ? AND status != 'running' "
                "ORDER BY updated_at",
                (cutoff.isoformat(),),
            ).fetchall()
        return [_job(r, []) for r in rows]

    # -- artifacts --------------------------------------------------------------------

    def put_artifact(self, job_id: str, name: str, model: BaseModel, version: int = 0) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO artifacts (job_id, name, version, data, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (job_id, name, version, model.model_dump_json(), utcnow().isoformat()),
            )

    def get_artifact(
        self, job_id: str, name: str, cls: type[T], version: int | None = None
    ) -> T | None:
        with self._connection() as conn:
            if version is None:
                row = conn.execute(
                    "SELECT data FROM artifacts WHERE job_id = ? AND name = ? "
                    "ORDER BY version DESC LIMIT 1",
                    (job_id, name),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT data FROM artifacts WHERE job_id = ? AND name = ? AND version = ?",
                    (job_id, name, version),
                ).fetchone()
        return cls.model_validate_json(row["data"]) if row else None

    def get_artifact_json(self, job_id: str, name: str, version: int | None = None) -> dict | None:
        with self._connection() as conn:
            sql = "SELECT data FROM artifacts WHERE job_id = ? AND name = ?"
            params: tuple = (job_id, name)
            if version is not None:
                sql += " AND version = ?"
                params = (*params, version)
            row = conn.execute(sql + " ORDER BY version DESC LIMIT 1", params).fetchone()
        return json.loads(row["data"]) if row else None

    def versions(self, job_id: str, name: str) -> list[int]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT version FROM artifacts WHERE job_id = ? AND name = ? ORDER BY version",
                (job_id, name),
            ).fetchall()
        return [r["version"] for r in rows]

    def artifact_names(self, job_id: str) -> dict[str, list[int]]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT name, version FROM artifacts WHERE job_id = ? ORDER BY name, version",
                (job_id,),
            ).fetchall()
        out: dict[str, list[int]] = {}
        for r in rows:
            out.setdefault(r["name"], []).append(r["version"])
        return out

    # -- usage ------------------------------------------------------------------------

    def add_usage(self, job_id: str, usage: Usage) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO llm_calls (job_id, stage, model, tokens_in, tokens_out, "
                "latency_ms, cached, at, cache_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    usage.stage,
                    usage.model,
                    usage.tokens_in,
                    usage.tokens_out,
                    usage.latency_ms,
                    int(usage.cached),
                    utcnow().isoformat(),
                    usage.cache_key,
                ),
            )

    def usage_totals(self) -> list[dict]:
        """Calls, tokens and latency per stage, model and cache hit, summed over every
        stored job, for `/metrics` (web/observability.py)."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT stage, model, cached, COUNT(*) AS calls, SUM(tokens_in) AS tokens_in, "
                "SUM(tokens_out) AS tokens_out, SUM(latency_ms) AS latency_ms FROM llm_calls "
                "GROUP BY stage, model, cached ORDER BY stage, model, cached"
            ).fetchall()
        return [dict(r) for r in rows]

    def cache_keys(self, job_id: str) -> list[str]:
        """The response-cache keys of the job's model calls, so that a deleted job
        takes its cached prompts and answers with it (llm/cache.py)."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT cache_key FROM llm_calls WHERE job_id = ? "
                "AND cache_key IS NOT NULL",
                (job_id,),
            ).fetchall()
        return [r["cache_key"] for r in rows]


def _migrate(conn: sqlite3.Connection) -> None:
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    for number, group in enumerate(_MIGRATIONS, 1):
        if number > version:
            for step in group:
                if callable(step):
                    step(conn)
                else:
                    conn.execute(step)
    if version < SCHEMA_VERSION:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _update(job_id: str, fields: dict[str, object]) -> tuple[str, tuple]:
    """The UPDATE for `fields` (an allowlist of columns), `updated_at` set with them."""
    allowed = {"status", "stage", "title", "error", "config", "counts"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"cannot update {unknown}")
    values = dict(fields)
    for name in ("config", "counts"):
        if isinstance(values.get(name), BaseModel):
            values[name] = values[name].model_dump_json()  # type: ignore[union-attr]
    values["updated_at"] = utcnow().isoformat()
    assignments = ", ".join(f"{k} = ?" for k in values)
    return f"UPDATE jobs SET {assignments} WHERE id = ?", (*values.values(), job_id)


def _filters(status: str | None, lang: str | None) -> tuple[str, tuple]:
    clauses, params = [], []
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if lang:
        clauses.append("json_extract(config, '$.lang') = ?")
        params.append(lang)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), tuple(params)


def _job(row: sqlite3.Row, usage: list[UsageRecord]) -> Job:
    counts = row["counts"]
    return Job(
        id=row["id"],
        status=row["status"],
        stage=row["stage"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        config=JobConfig.model_validate_json(row["config"]),
        usage=usage,
        error=row["error"],
        counts=JobCounts.model_validate_json(counts) if counts else None,
    )
