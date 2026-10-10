"""One worker thread that runs jobs from a queue (track_2b/docs/architecture.md §7).

Enough for a reviewer's workload and no message broker: the web app submits job ids,
the worker runs them one after the other. Jobs that were queued or running when the
service stopped are queued again on start.
"""

from __future__ import annotations

import logging
import queue
import threading

from leichtfacile.pipeline.orchestrator import Orchestrator

log = logging.getLogger(__name__)


class JobRunner:
    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="job-runner", daemon=True)
        self._thread.start()

    def submit(self, job_id: str) -> None:
        self.orchestrator.store.update_job(job_id, status="queued", error=None)
        self._queue.put(job_id)

    def resume_pending(self) -> int:
        pending = [
            j.id
            for j in self.orchestrator.store.list_jobs(limit=500)
            if j.status in ("queued", "running")
        ]
        for job_id in reversed(pending):
            self.submit(job_id)
        return len(pending)

    def stop(self, timeout_s: float = 5.0) -> None:
        if self._thread and self._thread.is_alive():
            self._queue.put(None)
            self._thread.join(timeout_s)

    def wait_idle(self, timeout_s: float = 30.0) -> bool:
        """For tests: wait until the queue is drained."""
        done = threading.Event()

        def waiter() -> None:
            self._queue.join()
            done.set()

        threading.Thread(target=waiter, daemon=True).start()
        return done.wait(timeout_s)

    def _loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                if job_id is None:
                    return
                self.orchestrator.run(job_id)
            except Exception:  # run() records failures itself; this is a last resort
                log.exception("job runner: unexpected error in job %s", job_id)
            finally:
                self._queue.task_done()
