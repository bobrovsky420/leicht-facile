"""Worker threads that run the queued jobs (docs/architecture.md §7).

The jobs table is the queue: a worker takes the job that has waited longest with one
guarded UPDATE (`Store.claim_next_queued`), so `jobs.workers` threads share it without a
broker and nothing in memory is lost on a restart. A worker that finds nothing waits
for a nudge from `submit` or one second, whichever comes first, so a job queued by
another process is picked up too; a claim that fails (the database busy past its
timeout) is logged and tried again after five seconds, and the thread lives on. Jobs
left `running` by a process that stopped are queued again on start. A queue limit
refuses submissions when `jobs.queue_limit` jobs wait; `cancel` stops a queued or a
running job. A housekeeping thread deletes the jobs older than `data.retention_days`
once an hour (lifecycle.py). Every step is an event in the job's log (events.py): the
claim, a cancellation with who asked, the restart; `/metrics` reads the jobs' durations
from there (web/observability.py).
"""

from __future__ import annotations

import logging
import threading

from leichtfacile.lifecycle import purge_expired
from leichtfacile.pipeline.orchestrator import Orchestrator
from leichtfacile.store import IDLE_STATUSES

log = logging.getLogger(__name__)
POLL_S = 1.0  # how long an idle worker waits before it looks at the queue again
CLAIM_RETRY_S = 5.0  # how long a worker waits after a claim failed
PURGE_INTERVAL_S = 3600.0


class QueueFull(RuntimeError):
    """`jobs.queue_limit` jobs are waiting already."""


class JobRunner:
    def __init__(
        self,
        orchestrator: Orchestrator,
        *,
        workers: int = 1,
        queue_limit: int = 50,
        retention_days: int = 0,
        purge_interval_s: float = PURGE_INTERVAL_S,
    ) -> None:
        self.orchestrator = orchestrator
        self.store = orchestrator.store
        self.workers = max(1, workers)
        self.queue_limit = queue_limit
        self.retention_days = retention_days
        self.purge_interval_s = purge_interval_s
        self._threads: list[threading.Thread] = []
        # Two conditions on one lock: the workers wait on `_work` for a nudge (something
        # was queued, or stop), `wait_idle` on `_idle` for a worker that went idle. With
        # one condition for both, every idle worker woke the others at once.
        lock = threading.Lock()
        self._work = threading.Condition(lock)
        self._idle = threading.Condition(lock)
        self._stopping = threading.Event()
        self._busy = 0  # workers between taking a job and finishing it

    def start(self) -> None:
        if any(t.is_alive() for t in self._threads):
            return
        self._stopping.clear()
        self._threads = [
            threading.Thread(target=self._worker, name=f"job-runner-{n}", daemon=True)
            for n in range(1, self.workers + 1)
        ]
        if self.retention_days:
            self._threads.append(
                threading.Thread(target=self._housekeeping, name="job-purge", daemon=True)
            )
        for thread in self._threads:
            thread.start()

    def ensure_room(self) -> None:
        """Raise `QueueFull` when the queue holds its limit of waiting jobs."""
        waiting = self.store.count_jobs("queued")
        if waiting >= self.queue_limit:
            raise QueueFull(f"the queue is full: {waiting} jobs are waiting")

    def submit(self, job_id: str) -> bool:
        """Queue the job (again) and wake a worker: a job that waits already is left as
        it is, one that ended gets a `queued` event. False when a worker is running it
        or it does not exist; nothing changes then."""
        job = self.store.get_job(job_id)
        if job is None:
            return False
        queued = job.status == "queued" or self.store.record(
            job_id, "queued", only_from=IDLE_STATUSES
        )
        self._nudge()
        return queued

    def cancel(self, job_id: str, *, by: str | None = None) -> str | None:
        """Stop the job: `stopping` when a worker runs it and will end it at its next
        check, `cancelled` when it was waiting and is taken out of the queue, None when
        it is neither queued nor running. The `cancelled` event names `by`, the user
        who asked (web/security.py)."""
        if self.orchestrator.cancel(job_id, by=by):
            return "stopping"
        payload = {"by": by} if by else {}
        if self.store.record(job_id, "cancelled", payload, only_from=("queued",)):
            return "cancelled"
        return None

    def recover_on_start(self) -> int:
        """Queue the jobs again that a stopped process left running."""
        ids = self.store.requeue_running()
        self._nudge()
        return len(ids)

    def stop(self, timeout_s: float = 5.0) -> None:
        """Stop the threads. A job in a model call is not interrupted: it keeps the
        `running` status and `recover_on_start` queues it again on the next start."""
        self._stopping.set()
        self._nudge()
        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout_s)

    @property
    def busy(self) -> int:
        """Workers between taking a job and finishing it."""
        with self._work:
            return self._busy

    def wait_idle(self, timeout_s: float = 30.0) -> bool:
        """For tests: wait until no job is waiting and no worker is busy."""
        with self._idle:
            return self._idle.wait_for(
                lambda: self._busy == 0 and self.store.count_jobs("queued") == 0, timeout_s
            )

    def purge(self) -> list[str]:
        """Delete the jobs older than the retention; the ids deleted."""
        return purge_expired(self.store, self.retention_days)

    # -- threads ------------------------------------------------------------------------

    def _nudge(self) -> None:
        with self._work:
            self._work.notify_all()

    def _worker(self) -> None:
        while not self._stopping.is_set():
            with self._work:
                self._busy += 1  # before the claim, so `wait_idle` never misses a job
            wait_s = POLL_S
            try:
                job_id = self.store.claim_next_queued()
            except Exception:  # a busy or failing database must not end the thread
                log.exception("job runner: no job could be taken; trying again shortly")
                job_id, wait_s = None, CLAIM_RETRY_S
            if job_id is None:
                with self._work:
                    self._busy -= 1
                    self._idle.notify_all()
                    if not self._stopping.is_set():
                        self._work.wait(wait_s)
                continue
            try:
                self.orchestrator.run(job_id)
            except Exception:  # run() records failures itself; this is a last resort
                log.exception("job runner: unexpected error in job %s", job_id)
            finally:
                with self._work:
                    self._busy -= 1
                    self._idle.notify_all()

    def _housekeeping(self) -> None:
        while True:
            try:
                self.purge()
            except Exception:  # the next hour tries again
                log.exception("retention purge failed")
            if self._stopping.wait(self.purge_interval_s):
                return
