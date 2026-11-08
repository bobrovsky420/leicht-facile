from __future__ import annotations

import sqlite3
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from leichtfacile.llm.cache import ResponseCache
from leichtfacile.llm.client import Usage
from leichtfacile.schemas import (
    Block,
    Draft,
    JobConfig,
    JobCounts,
    PipelineOptions,
    PipelineSummary,
    ReviewState,
    RuleFindings,
)
from leichtfacile.store import SCHEMA_VERSION, SchemaTooNew, Store


def test_jobs_artifacts_and_usage(tmp_path) -> None:
    store = Store(tmp_path / "s.sqlite")
    job = store.create_job(JobConfig(level="B1"), title="Test", created_by="a.muster")
    assert store.get_job(job.id).config.level == "B1"
    assert store.get_job(job.id).created_by == "a.muster"  # who submitted it: the login's user
    assert store.list_jobs()[0].created_by == "a.muster"

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
    mine = store.create_job(JobConfig(), workspace="h1")  # the workspace column, group 7
    assert [j.id for j in store.list_jobs(workspace="h1")] == [mine.id]
    assert store.get_job("old1", workspace="h1") is None  # the old job is in no workspace
    named = store.create_job(JobConfig(), created_by="a.muster")  # created_by, group 8
    assert store.get_job(named.id).created_by == "a.muster"
    assert job.created_by is None  # nobody was recorded before
    store.close()
    assert Store(path).schema_version == SCHEMA_VERSION  # opening again changes nothing


def test_old_names_and_fields_are_rewritten_on_open(tmp_path) -> None:
    """The second migration rewrites what the first weeks stored differently: the
    conditions C0 to C2 (P since 6 October 2026), the retired `live` field (gone since
    23 October) and a review without its stamp (`saved_at` since 11 October). After it
    the models need no fallback for them."""
    path = tmp_path / "s.sqlite"
    store = Store(path)
    job = store.create_job(JobConfig(level="B1"), title="Test")
    decisions = (
        '[{"block_id": "b001", "decision": "approved", "at": "2026-10-05T10:00:00+00:00"},'
        ' {"block_id": "b002", "decision": "rejected", "at": "2026-10-05T11:00:00+00:00"}]'
    )
    summary = (
        '{"condition": "C2", "final_version": 3, "rounds": 1, "facts_rounds": 1, '
        '"vocabulary_rounds": 0, "polish_rounds": 0, "stop_reason": "no missing facts left"}'
    )
    with sqlite3.connect(path) as db:  # as the versions of early October stored them
        db.execute(
            "UPDATE jobs SET config = json_set(config, '$.live', json('false'), "
            "'$.condition', 'C2', '$.max_repair_rounds', 1, '$.max_facts_rounds', 2)"
        )
        db.execute(
            "INSERT INTO artifacts VALUES (?, 'summary', 0, ?, '2026-10-05T12:00:00+00:00')",
            (job.id, summary),
        )
        for version, kind in ((2, "repair"), (3, "facts")):
            db.execute(
                "INSERT INTO artifacts VALUES (?, 'repair', ?, ?, '2026-10-05T12:00:00+00:00')",
                (job.id, version, f'{{"draft_version": {version}, "parent_version": '
                                  f'{version - 1}, "kind": "{kind}"}}'),
            )  # fmt: skip
        db.execute(
            "INSERT INTO artifacts VALUES (?, 'review', 0, ?, '2026-10-05T12:00:00+00:00')",
            (job.id, '{"draft_version": 1, "decisions": ' + decisions + "}"),
        )
        findings = (  # the English text alone; key and values; two French rule ids
            '[{"block_id": "b001", "rule_id": "LEN-01", "severity": "warn", '
            '"message": "The sentence has 14 words; the limit for A2 is 12."}, '
            '{"block_id": "b001", "rule_id": "LEX-01", "severity": "warn", "message": "x", '
            '"message_key": "LEX-01", "message_params": {"found": "Krankenkasse", '
            '"letters": 12, "limit": 13}}, '
            '{"block_id": "b001", "rule_id": "GRAM-08-FR", "severity": "warn", "message": "x", '
            '"message_key": "GRAM-08-FR.soft", "message_params": {"found": "il est possible"}}, '
            '{"block_id": "b001", "rule_id": "LEX-04-FR", "severity": "warn", "message": "x", '
            '"message_key": "LEX-04-FR.slash", "message_params": {}}, '
            '{"block_id": "b002", "rule_id": "LEN-02-FR", "severity": "warn", '
            '"message": "Subordinate clause: 2 clauses in one sentence."}]'
        )
        db.execute(
            "INSERT INTO artifacts VALUES (?, 'rules', 1, ?, '2026-10-05T12:00:00+00:00')",
            (job.id, '{"draft_version": 1, "level": "A2", "findings": ' + findings + "}"),
        )
        db.execute("PRAGMA user_version = 1")
    store.close()

    for _ in range(2):  # opening again changes nothing
        store = Store(path)
        assert store.schema_version == SCHEMA_VERSION
        rounds = PipelineOptions(repair_rounds=1, facts_rounds=2)
        expected = JobConfig(level="B1", condition="P2", pipeline=rounds)
        assert store.get_job(job.id).config == expected
        migrated = store.get_artifact(job.id, "summary", PipelineSummary)
        assert migrated.condition == "P2" and migrated.stop_reason == "no_missing_facts"
        assert [(r.kind, r.number, r.parent_version, r.version) for r in migrated.rounds] == [
            ("repair", 1, 1, 2),
            ("facts", 1, 2, 3),
        ]
        assert migrated.rounds_of("repair") == 1 and migrated.rounds_of("facts") == 1
        review = store.get_artifact(job.id, "review", ReviewState)
        assert review.saved_at == datetime(2026, 10, 5, 11, tzinfo=UTC)
        rules = store.get_artifact(job.id, "rules", RuleFindings, version=1)
        assert [(f.rule_id, f.key, f.params) for f in rules.findings] == [
            ("LEN-01", "legacy", {"text": "The sentence has 14 words; the limit for A2 is 12."}),
            ("LEX-01", "LEX-01", {"found": "Krankenkasse", "letters": 12, "limit": 13}),
            ("GRAM-09", "GRAM-09.soft", {"found": "il est possible"}),
            ("LEX-04", "LEX-04.slash", {"first": "et", "second": "ou"}),
            # a French finding with the English text alone: only its id changes
            ("LEN-02", "legacy", {"text": "Subordinate clause: 2 clauses in one sentence."}),
        ]
        store.close()


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


def test_a_deleted_job_takes_its_cache_rows_and_leaves_those_another_job_uses(tmp_path) -> None:
    """The store owns the response cache, so a deletion needs no model client (audit
    2.1.2: with no preset ready, the rows stayed). A row of the same text's other job
    stays until that job goes too; a running job keeps everything."""
    cache = ResponseCache(tmp_path / "cache.sqlite")
    store = Store(tmp_path / "d.sqlite", cache=cache)
    one, two = store.create_job(JobConfig()), store.create_job(JobConfig())
    store.add_usage(one.id, Usage("understand", "m", 1, 2, 3, cache_key="own"))
    store.add_usage(one.id, Usage("write", "m", 1, 2, 3, cache_key="shared"))
    store.add_usage(two.id, Usage("write", "m", 1, 2, 3, cache_key="shared"))
    for key in ("own", "shared"):
        cache.put(key, "m", {"text": key})
    store.update_job(one.id, status="running")
    assert not store.delete_job(one.id)
    assert cache.get("own") == {"text": "own"}  # a running job keeps its rows
    store.update_job(one.id, status="needs_review")
    assert store.delete_job(one.id)
    assert cache.get("own") is None and cache.get("shared") == {"text": "shared"}
    assert store.delete_job(two.id)
    assert cache.get("shared") is None
    assert not store.delete_job(two.id)  # gone already
    store.close()  # closes the cache with it


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
    assert store.langs() == ["de-CH", "fr-CH"]  # the varieties: a job without a region is Swiss
    austrian = store.create_job(JobConfig(lang="de", region="AT"), title="at")
    assert store.langs() == ["de-CH", "de-AT", "fr-CH"]
    assert [j.id for j in store.list_jobs(lang="de-AT")] == [austrian.id]
    assert [j.id for j in store.list_jobs(lang="de-CH")] == [de.id]
    assert [j.id for j in store.list_jobs(lang="de")] == [austrian.id, de.id]  # the language
    assert store.status_counts(lang="de-CH") == {"queued": 1}
    old = datetime.now(UTC) - timedelta(days=40)
    with sqlite3.connect(store.path) as db:  # back-dated behind the store's back
        db.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (old.isoformat(), de.id))
    cutoff = datetime.now(UTC) - timedelta(days=30)
    assert [j.id for j in store.jobs_older_than(cutoff)] == [de.id]
    store.close()


def test_workspaces_scope_the_reads_and_a_new_link_moves_the_jobs(tmp_path) -> None:
    """A job carries the hash of its workspace (web/workspaces.py): a read with a
    workspace sees that workspace alone, one without sees everything, and a move takes
    every job of a workspace along without touching `updated_at`."""
    store = Store(tmp_path / "w.sqlite")
    mine = store.create_job(JobConfig(lang="de"), title="Meins", workspace="h1")
    theirs = store.create_job(JobConfig(lang="fr"), title="Leur", workspace="h2")
    nobody = store.create_job(JobConfig(lang="it"), title="Nessuno")  # the command line's
    assert store.get_job(mine.id, workspace="h1").id == mine.id
    assert store.get_job(mine.id, workspace="h2") is None
    assert store.get_job(nobody.id, workspace="h1") is None
    assert store.get_job(nobody.id).id == nobody.id
    assert [j.id for j in store.list_jobs(workspace="h1")] == [mine.id]
    assert len(store.list_jobs()) == 3
    assert store.count_jobs(workspace="h2") == 1 and store.count_jobs() == 3
    assert store.count_jobs("queued", workspace="h1") == 1
    assert store.status_counts(workspace="h1") == {"queued": 1}
    assert store.langs(workspace="h2") == ["fr-CH"]
    assert store.langs() == ["de-CH", "fr-CH", "it-CH"]
    before = store.get_job(theirs.id).updated_at
    assert store.move_workspace("h2", "h3") == 1
    assert store.get_job(theirs.id, workspace="h3").updated_at == before
    assert store.list_jobs(workspace="h2") == []
    assert store.move_workspace("h2", "h4") == 0  # nothing left there
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
        except Exception as exc:  # noqa: BLE001  (the test reports it, not the thread)
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


def test_the_swiss_rule_ids_become_the_regions_on_open(tmp_path) -> None:
    """Migration 6 (29 October 2026): CH-01 to CH-03 became REG-01 to REG-03 in the
    stored findings and in the code edits of the drafts."""
    path = tmp_path / "s.sqlite"
    store = Store(path)
    job = store.create_job(JobConfig(), title="Test")
    with sqlite3.connect(path) as db:
        findings = (
            '[{"block_id": "b001", "rule_id": "CH-01", "severity": "error", "key": "CH-01", '
            '"params": {"found": "Strasse"}}, {"block_id": "b001", "rule_id": "CH-02", '
            '"severity": "info", "key": "CH-02", "params": {}}, {"block_id": "b001", '
            '"rule_id": "LEN-01", "severity": "warn", "key": "LEN-01", "params": {}}]'
        )
        db.execute(
            "INSERT INTO artifacts VALUES (?, 'rules', 1, ?, '2026-10-28T12:00:00+00:00')",
            (job.id, '{"draft_version": 1, "level": "A2", "findings": ' + findings + "}"),
        )
        draft = (
            '{"doc_id": "d", "lang": "de", "level": "A2", "blocks": [], "code_edits": '
            '[{"block_id": "b001", "rule_id": "CH-01", "before": "Straße", "after": "Strasse"}, '
            '{"block_id": "b002", "rule_id": "LEX-01", "before": "Krankenkasse", '
            '"after": "Kranken·kasse"}]}'
        )
        db.execute(
            "INSERT INTO artifacts VALUES (?, 'draft', 1, ?, '2026-10-28T12:00:00+00:00')",
            (job.id, draft),
        )
        db.execute("PRAGMA user_version = 5")
    store.close()
    store = Store(path)
    assert store.schema_version == SCHEMA_VERSION
    rules = store.get_artifact(job.id, "rules", RuleFindings)
    assert [(f.rule_id, f.key) for f in rules.findings] == [
        ("REG-01", "REG-01"), ("REG-02", "REG-02"), ("LEN-01", "LEN-01"),
    ]  # fmt: skip
    assert [e.rule_id for e in store.get_artifact(job.id, "draft", Draft).code_edits] == [
        "REG-01", "LEX-01",
    ]  # fmt: skip
    store.close()


def test_an_older_database_is_copied_before_its_migration(tmp_path) -> None:
    """Before the groups it lacks are applied, the database as it was goes to
    backups/<name>-v<version>.sqlite next to it: the copy a downgrade restores. A
    database of the current version is not copied."""
    path = tmp_path / "old.sqlite"
    store = Store(path)
    store.create_job(JobConfig())
    store.close()
    assert not (tmp_path / "backups").exists()
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version = 5")
    Store(path).close()
    copy = tmp_path / "backups" / "old-v5.sqlite"
    assert copy.is_file()
    with sqlite3.connect(copy) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
    assert Store(path).schema_version == SCHEMA_VERSION


def test_a_database_of_a_newer_version_is_refused(tmp_path) -> None:
    path = tmp_path / "new.sqlite"
    Store(path).close()
    with sqlite3.connect(path) as db:
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    with pytest.raises(SchemaTooNew, match="newer version"):
        Store(path)
    assert not (tmp_path / "backups").exists()
