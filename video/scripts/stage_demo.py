"""Stage a copy of the real example job at a given pipeline state, for the screen capture.

The running server's worker does not pick up jobs inserted from outside, so the job page
renders exactly the state set here. Every artifact and model call is copied from the
real example job (P2 on CSCS); only the status, the stage and the start time are set.

    python scripts/stage_demo.py understand|write|check|judge|repair|review

The database is the app's DATA_DIR for the capture (default video/out/capture-data),
set with CAPTURE_DATA.
"""

import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DATA = Path(
    os.environ.get("CAPTURE_DATA", Path(__file__).resolve().parents[1] / "out" / "capture-data")
)
DB = DATA / "leichtfacile.sqlite"
SRC = "example-praemienverbilligung-brief"
JOB = "demo-run"
TITLE = "Individuelle Prämienverbilligung 2027"

# what each state shows: artifacts as (name, max version), model calls by stage
STATES = {
    "understand": dict(art=[("source", 0)], calls=[], elapsed=24),
    "write": dict(art=[("source", 0), ("factsheet", 0)], calls=["understand"], elapsed=203),
    "check": dict(
        art=[("source", 0), ("factsheet", 0), ("draft", 1)],
        calls=["understand", "write"],
        elapsed=210,
    ),
    "judge": dict(
        art=[("source", 0), ("factsheet", 0), ("draft", 1), ("rules", 1)],
        calls=["understand", "write"],
        elapsed=211,
    ),
    "repair": dict(
        art=[
            ("source", 0),
            ("factsheet", 0),
            ("draft", 2),
            ("rules", 2),
            ("judge", 1),
            ("repair", 2),
        ],
        calls=["understand", "write", "judge:1", "repair:1"],
        elapsed=226,
    ),
}


INSERT_JOB = (
    "INSERT INTO jobs (id, status, stage, title, created_at, updated_at, config) "
    "VALUES (?,?,?,?,?,?,?)"
)
COPY_CALLS = (
    "INSERT INTO llm_calls (job_id, stage, model, tokens_in, tokens_out, latency_ms, cached, at) "
    "SELECT ?, stage, model, tokens_in, tokens_out, latency_ms, cached, at FROM llm_calls "
)


def main(state: str) -> None:
    c = sqlite3.connect(DB, timeout=10)
    c.execute("PRAGMA foreign_keys = ON")
    cfg = c.execute("SELECT config FROM jobs WHERE id = ?", (SRC,)).fetchone()[0]
    c.execute("DELETE FROM artifacts WHERE job_id = ?", (JOB,))
    c.execute("DELETE FROM llm_calls WHERE job_id = ?", (JOB,))
    c.execute("DELETE FROM jobs WHERE id = ?", (JOB,))
    now = datetime.now(UTC)
    if state == "review":
        calls = c.execute(
            "SELECT SUM(latency_ms) FROM llm_calls WHERE job_id = ?", (SRC,)
        ).fetchone()[0]
        start = now - timedelta(minutes=12)
        end = start + timedelta(milliseconds=calls + 4000)
        c.execute(
            INSERT_JOB,
            (JOB, "needs_review", "review", TITLE, start.isoformat(), end.isoformat(), cfg),
        )
        c.execute(
            "INSERT INTO artifacts SELECT ?, name, version, data, created_at FROM artifacts "
            "WHERE job_id = ?",
            (JOB, SRC),
        )
        c.execute(
            COPY_CALLS + "WHERE job_id = ? ORDER BY id",
            (JOB, SRC),
        )
    else:
        spec = STATES[state]
        start = now - timedelta(seconds=spec["elapsed"])
        c.execute(
            INSERT_JOB,
            (JOB, "running", state, TITLE, start.isoformat(), now.isoformat(), cfg),
        )
        for name, upto in spec["art"]:
            c.execute(
                "INSERT INTO artifacts SELECT ?, name, version, data, created_at FROM artifacts "
                "WHERE job_id = ? AND name = ? AND version <= ?",
                (JOB, SRC, name, upto),
            )
        for item in spec["calls"]:
            stage, _, n = item.partition(":")
            limit = int(n) if n else -1
            c.execute(
                COPY_CALLS + "WHERE job_id = ? AND stage = ? ORDER BY id LIMIT ?",
                (JOB, SRC, stage, limit),
            )
    c.commit()
    c.close()
    print(f"{JOB}: {state}")


if __name__ == "__main__":
    main(sys.argv[1])
