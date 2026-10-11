from __future__ import annotations

import sqlite3
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from leichtfacile.llm.client import Usage
from leichtfacile.schemas import Block, Draft, JobConfig, JobCounts
from leichtfacile.store import SCHEMA_VERSION, Store


def test_jobs_artifacts_and_usage(tmp_path) -> None:
    store = Store(tmp_path / "s.sqlite")
    job = store.create_job(JobConfig(level="B1"), title="Test")
    assert store.get_job(job.id).config.level == "B1"

    for version in (1, 2):
        draft = Draft(doc_id="d", lang="de", level="A2", version=version,
                      blocks=[Block(id="b001", kind="sentence",
                                    text=f"Version {version}.")])  # fmt: skip
        store.put_artifact(job.id, "draft", draft, version)
    assert store.versions(job.id, "draft") == [1, 2]
    assert store.get_artifact(job.id, "draft", Draft).version == 2
    assert store.get_artifact(job.id, "draft", Draft, version=1).blocks[0].text == "Version 1."
    assert store.get_artifact_json(job.id, "draft")["version"] == 2

    store.add_usage(job.id, Usage("write", "m", 10, 20, 300))
    store.update_job(job.id, status="running", stage="write")
    loaded = store.get_job(job.id)
    assert loaded.status == "running" and loaded.usage[0].tokens_out == 20
    assert [j.id for j in store.list_jobs()] == [job.id]

    assert not store.delete_job(job.id)  # a worker holds it (audit V14)
    store.update_job(job.id, status="done")
    assert store.delete_job(job.id)
    assert store.get_job(job.id) is None
    assert store.versions(job.id, "draft") == []  # artifacts go with the job
    store.close()


def test_an_older_database_gets_the_new_columns_on_open(tmp_path) -> None:
    """The schema is versioned (`PRAGMA user_version`): a database made before the
    counts and the cache keys existed is migrated when it is opened."""
    path = tmp_path / "old.sqlite"
    old = sqlite3.connect(path)
    old.executescript(
        "CREATE TABLE jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, stage TEXT, title TEXT,"
        " created_at TEXT NOT NULL, updated_at TEXT NOT NULL, config TEXT NOT NULL, error TEXT);"
        "CREATE TABLE artifacts (job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,"
        " name TEXT NOT NULL, version INTEGER NOT NULL, data TEXT NOT NULL,"
        " created_at TEXT NOT NULL, PRIMARY KEY (job_id, name, version));"
        "CREATE TABLE llm_calls (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL"
        " REFERENCES jobs(id) ON DELETE CASCADE, stage TEXT NOT NULL, model TEXT NOT NULL,"
        " tokens_in INTEGER NOT NULL, tokens_out INTEGER NOT NULL, latency_ms INTEGER NOT NULL,"
        " cached INTEGER NOT NULL DEFAULT 0, at TEXT NOT NULL);"
        "INSERT INTO jobs VALUES ('old1', 'needs_review', 'review', 'Alt',"
        " '2026-10-01T00:00:00+00:00', '2026-10-01T00:00:00+00:00', '{\"lang\": \"de\"}', NULL);"
    )
    old.commit()
    old.close()

    store = Store(path)
    assert store.schema_version == SCHEMA_VERSION
    job = store.get_job("old1")
    assert job is not None and job.counts is None  # filled in later, on the drafts list
    store.update_job("old1", counts=JobCounts(errors=2, has_draft=True))
    assert store.get_job("old1").counts.errors == 2
    store.add_usage("old1", Usage("write", "m", 1, 2, 3, cache_key="abc"))
    assert store.cache_keys("old1") == ["abc"]
    store.close()
    assert Store(path).schema_version == SCHEMA_VERSION  # opening again changes nothing


def test_the_jobs_table_is_the_queue(tmp_path) -> None:
    store = Store(tmp_path / "q.sqlite")
    first = store.create_job(JobConfig(), title="first")
    second = store.create_job(JobConfig(), title="second")
    assert store.count_jobs("queued") == 2
    assert store.claim_next_queued() == first.id  # the one that waited longest
    assert store.get_job(first.id).status == "running"
    assert store.claim_next_queued() == second.id
    assert store.claim_next_queued() is None

    # Guarded transitions: a running job is neither queued again nor deleted.
    assert not store.transition(first.id, "queued", only_from=("needs_review", "failed"))
    assert not store.requeue(first.id, delete=["draft"])
    assert not store.delete_job(first.id)
    assert store.transition(first.id, "failed", only_from=("running",), error="x")
    assert store.get_job(first.id).error == "x"
    assert store.transition(first.id, "queued", only_from=("failed",), error=None)
    assert store.get_job(first.id).error is None

    # A process that stopped left `second` running: queued again on start.
    assert store.requeue_running() == [second.id]
    assert store.count_jobs("queued") == 2
    store.close()


def test_a_rerun_removes_the_artifacts_in_the_same_step_as_the_requeue(tmp_path) -> None:
    store = Store(tmp_path / "r.sqlite")
    job = store.create_job(JobConfig(), title="t")
    for version in (1, 2):
        draft = Draft(doc_id="d", lang="de", level="A2", version=version,
                      blocks=[Block(id="b001", kind="sentence", text="x")])  # fmt: skip
        store.put_artifact(job.id, "draft", draft, version)
    store.put_artifact(job.id, "draft", draft, 2)
    store.update_job(job.id, status="needs_review", stage="review", error="old")
    assert store.requeue(job.id, delete=["summary"], trim=["draft"])
    loaded = store.get_job(job.id)
    assert loaded.status == "queued" and loaded.stage is None and loaded.error is None
    assert store.versions(job.id, "draft") == [1]
    store.close()


def test_list_filters_counts_and_languages_in_sql(tmp_path) -> None:
    store = Store(tmp_path / "f.sqlite")
    de = store.create_job(JobConfig(lang="de"), title="de")
    fr = store.create_job(JobConfig(lang="fr"), title="fr")
    store.create_job(JobConfig(), title="none")
    store.update_job(fr.id, status="failed")
    assert [j.id for j in store.list_jobs(status="queued", lang="de")] == [de.id]
    assert [j.id for j in store.list_jobs(lang="fr")] == [fr.id]
    assert store.status_counts() == {"queued": 2, "failed": 1}
    assert store.status_counts(lang="fr") == {"failed": 1}
    assert store.langs() == ["de", "fr"]
    old = datetime.now(UTC) - timedelta(days=40)
    with sqlite3.connect(store.path) as db:  # back-dated behind the store's back
        db.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (old.isoformat(), de.id))
    cutoff = datetime.now(UTC) - timedelta(days=30)
    assert [j.id for j in store.jobs_older_than(cutoff)] == [de.id]
    store.close()


def test_readers_never_wait_for_a_writer_and_writers_wait_for_each_other(tmp_path) -> None:
    """Audit B4: a pool of connections in WAL mode. A worker's open write transaction
    holds no reader up; a second writer waits until it is committed."""
    store = Store(tmp_path / "pool.sqlite")
    store.create_job(JobConfig(), title="before")
    entered, release, done = threading.Event(), threading.Event(), threading.Event()

    def long_write() -> None:
        with store._tx() as conn:  # the transaction a worker's write holds open
            conn.execute("UPDATE jobs SET title = 'during'")
            entered.set()
            release.wait(10)

    def second_write() -> None:
        store.create_job(JobConfig(), title="after")
        done.set()

    writer = threading.Thread(target=long_write)
    writer.start()
    assert entered.wait(5)
    started = time.monotonic()
    assert [j.title for j in store.list_jobs()] == ["before"], "a reader sees the committed state"
    assert time.monotonic() - started < 1.0, "and sees it at once"
    other = threading.Thread(target=second_write)
    other.start()
    assert not done.wait(0.3), "the second writer waits for the first"
    release.set()
    writer.join(5)
    assert done.wait(5)
    other.join(5)
    assert sorted(j.title for j in store.list_jobs()) == ["after", "during"]
    store.close()


def test_the_pool_serves_parallel_threads_within_its_size(tmp_path) -> None:
    store = Store(tmp_path / "pool2.sqlite", pool_size=3)
    errors: list[Exception] = []

    def work(n: int) -> None:
        try:
            for i in range(25):
                job = store.create_job(JobConfig(), title=f"{n}-{i}")
                assert store.get_job(job.id) is not None
                store.list_jobs(5)
        except Exception as exc:  # reported by the test, not lost in the thread
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert errors == []
    assert store.count_jobs() == 200
    assert 1 <= store.connections <= 3
    store.close()
    with pytest.raises(sqlite3.ProgrammingError):
        store.count_jobs()
