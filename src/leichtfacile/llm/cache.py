"""SQLite cache of model responses, keyed by a hash of model, messages and parameters.

Enabled with `LLM_CACHE=1`. It makes development and evaluation reruns cheap. The
repository never ships a filled cache: a live run must work from the endpoint.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

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

    def close(self) -> None:
        with self._lock:
            self._conn.close()
