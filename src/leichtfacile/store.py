"""SQLite storage for jobs, artifacts and model calls (docs/architecture.md §5).

One database file in DATA_DIR. Artifacts are pydantic models stored as JSON text, with
a version per name (draft 1, draft 2, ...). The standard library is enough: the schema
is small and there is one writer thread plus the web handlers.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from leichtfacile.llm.client import Usage
from leichtfacile.schemas import Job, JobConfig, UsageRecord, utcnow

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


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._tx() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(_SCHEMA)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- jobs -----------------------------------------------------------------------

    def create_job(
        self, config: JobConfig, title: str | None = None, job_id: str | None = None
    ) -> Job:
        job = Job(id=job_id or uuid.uuid4().hex[:12], title=title, config=config)
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO jobs (id, status, stage, title, created_at, updated_at, config) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    job.id,
                    job.status,
                    job.stage,
                    job.title,
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                    job.config.model_dump_json(),
                ),
            )
        return job

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            calls = self._conn.execute(
                "SELECT stage, model, tokens_in, tokens_out, latency_ms, cached "
                "FROM llm_calls WHERE job_id = ? ORDER BY id",
                (job_id,),
            ).fetchall()
        return _job(row, [UsageRecord(**dict(c)) for c in calls])

    def list_jobs(self, limit: int = 50) -> list[Job]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_job(r, []) for r in rows]

    def count_jobs(self, status: str | None = None) -> int:
        """How many jobs there are, or how many have this status."""
        with self._lock:
            if status is None:
                row = self._conn.execute("SELECT COUNT(*) FROM jobs").fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM jobs WHERE status = ?", (status,)
                ).fetchone()
        return int(row[0])

    def update_job(self, job_id: str, **fields: object) -> None:
        allowed = {"status", "stage", "title", "error", "config"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"cannot update {unknown}")
        if "config" in fields and isinstance(fields["config"], BaseModel):
            fields["config"] = fields["config"].model_dump_json()
        fields["updated_at"] = utcnow().isoformat()
        assignments = ", ".join(f"{k} = ?" for k in fields)
        with self._tx() as conn:
            conn.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", (*fields.values(), job_id))

    def delete_job(self, job_id: str) -> bool:
        with self._tx() as conn:
            cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return cur.rowcount > 0

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
        with self._lock:
            if version is None:
                row = self._conn.execute(
                    "SELECT data FROM artifacts WHERE job_id = ? AND name = ? "
                    "ORDER BY version DESC LIMIT 1",
                    (job_id, name),
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT data FROM artifacts WHERE job_id = ? AND name = ? AND version = ?",
                    (job_id, name, version),
                ).fetchone()
        return cls.model_validate_json(row["data"]) if row else None

    def get_artifact_json(self, job_id: str, name: str, version: int | None = None) -> dict | None:
        with self._lock:
            sql = "SELECT data FROM artifacts WHERE job_id = ? AND name = ?"
            params: tuple = (job_id, name)
            if version is not None:
                sql += " AND version = ?"
                params = (*params, version)
            row = self._conn.execute(sql + " ORDER BY version DESC LIMIT 1", params).fetchone()
        return json.loads(row["data"]) if row else None

    def versions(self, job_id: str, name: str) -> list[int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT version FROM artifacts WHERE job_id = ? AND name = ? ORDER BY version",
                (job_id, name),
            ).fetchall()
        return [r["version"] for r in rows]

    def artifact_names(self, job_id: str) -> dict[str, list[int]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT name, version FROM artifacts WHERE job_id = ? ORDER BY name, version",
                (job_id,),
            ).fetchall()
        out: dict[str, list[int]] = {}
        for r in rows:
            out.setdefault(r["name"], []).append(r["version"])
        return out

    def delete_artifacts_version(self, job_id: str, name: str, version: int) -> None:
        with self._tx() as conn:
            conn.execute(
                "DELETE FROM artifacts WHERE job_id = ? AND name = ? AND version = ?",
                (job_id, name, version),
            )

    def delete_artifacts(self, job_id: str, names: list[str]) -> None:
        with self._tx() as conn:
            conn.executemany(
                "DELETE FROM artifacts WHERE job_id = ? AND name = ?",
                [(job_id, n) for n in names],
            )

    # -- usage ------------------------------------------------------------------------

    def add_usage(self, job_id: str, usage: Usage) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO llm_calls (job_id, stage, model, tokens_in, tokens_out, "
                "latency_ms, cached, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    usage.stage,
                    usage.model,
                    usage.tokens_in,
                    usage.tokens_out,
                    usage.latency_ms,
                    int(usage.cached),
                    utcnow().isoformat(),
                ),
            )


def _job(row: sqlite3.Row, usage: list[UsageRecord]) -> Job:
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
    )
