"""SQLite cache of model responses, keyed by a hash of model, messages and parameters.

Enabled with `llm.cache`. It makes development and evaluation reruns cheap. The
repository never ships a filled cache: a live run must work from the endpoint. In the
service the store owns it (`open_cache`, `Store.delete_job`): a deleted job takes its
rows with it whether or not a preset is ready, and the clients get it from there.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

CACHE_NAME = "llm_cache.sqlite"  # in `data.dir`, next to the store's database

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_cache (
    key TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    response TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def cache_key(model: str, messages: list[dict[str, Any]], params: dict[str, Any]) -> str:
    payload = json.dumps(
        {"model": model, "messages": messages, "params": params},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(_SCHEMA)
            self._conn.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT response FROM llm_cache WHERE key = ?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, model: str, response: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO llm_cache (key, model, response) VALUES (?, ?, ?)",
                (key, model, json.dumps(response, ensure_ascii=False)),
            )
            self._conn.commit()

    def delete(self, key: str) -> None:
        self.delete_many([key])

    def delete_many(self, keys: Iterable[str]) -> None:
        """Delete these rows in one transaction: all of them or, on an error, none."""
        with self._lock:
            try:
                self._conn.executemany(
                    "DELETE FROM llm_cache WHERE key = ?", ((key,) for key in keys)
                )
            except BaseException:
                self._conn.rollback()
                raise
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def open_cache(data_dir: Path, enabled: bool) -> ResponseCache | None:
    """The response cache of a data directory, for the store: when `llm.cache` is on, and
    when it is off but the file is there from a time it was on, since a deleted job must
    take its rows with it either way. None without either."""
    path = data_dir / CACHE_NAME
    return ResponseCache(path) if enabled or path.exists() else None
