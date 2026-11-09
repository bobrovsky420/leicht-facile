"""Stored jobs replayed on their recorded answers (eval/replay.py): a P2 job run on the
fake endpoint with the response cache on, then run again without any endpoint."""

from __future__ import annotations

import json

import pytest

from leichtfacile.eval.replay import (
    REPORT_NAME,
    canonical,
    differences,
    render_line,
    replay_job,
    replay_jobs,
    select_jobs,
)
from leichtfacile.llm.cache import CACHE_NAME, ResponseCache
from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline.orchestrator import Orchestrator
from leichtfacile.schemas import Draft, JobConfig, PipelineOptions
from leichtfacile.store import Store
from tests.conftest import FakeEndpoint, chat_response, make_settings
from tests.pipeline import fixtures as fx

ANSWERS = (fx.UNDERSTAND, fx.WRITE, fx.JUDGE_FIRST, fx.REPAIR, fx.JUDGE_SECOND)
# The rounds the answers above end with, as in test_orchestrator.py.
ROUNDS = PipelineOptions(vocabulary=False, recover_facts=0, polish_rounds=0)


@pytest.fixture
def recorded(tmp_path):
    """A P2 job run on the fake endpoint with the response cache on: its store, the
    cache with its five answers, the settings it ran with and its id."""
    settings = make_settings(
        llm__models__judge="swiss-ai/Apertus-v1.5-70B", llm__max_retries=0, llm__cache=True
    )
    cache = ResponseCache(settings.data.dir / CACHE_NAME)
    store = Store(tmp_path / "jobs.sqlite", cache=cache)
    endpoint = FakeEndpoint()
    endpoint.push(*(chat_response(fx.as_json(a)) for a in ANSWERS))
    llm = LLMClient(settings, http_client=endpoint.http_client(), cache=cache)
    job = store.create_job(JobConfig(condition="P2", pipeline=ROUNDS), title="Brief")
    store.put_artifact(job.id, "source", fx.letter())
    Orchestrator(store, llm, settings).run(job.id)
    assert store.get_job(job.id).status == "needs_review"
    assert len(store.cache_keys(job.id)) == 5
    yield store, cache, settings, job.id
    store.close()


def test_the_replay_of_unchanged_code_agrees_with_the_stored_artifacts(recorded) -> None:
    store, cache, settings, job_id = recorded
    done = replay_job(store, store.get_job(job_id), cache, settings)

    assert done.status == "needs_review", done.error
    assert done.agrees, done.differences
    assert done.answered == {"key": 5, "order": 0, "none": 0} and done.gone == 0
    assert [v["version"] for v in done.replayed["versions"]] == [1, 2]
    assert done.replayed["summary"]["final_version"] == 2
    assert done.replayed == done.stored
    assert "agrees" in render_line(done) and "5 by key, 0 by order" in render_line(done)


def test_a_changed_prompt_is_answered_by_order(recorded) -> None:
    """Other settings make other cache keys (another model name): every call is answered
    with the next recorded answer of its stage, and the code makes the same of them."""
    store, cache, _, job_id = recorded
    other = make_settings(
        llm__models__writer="another-writer", llm__models__judge="another-judge",
        llm__max_retries=0,
    )  # fmt: skip
    done = replay_job(store, store.get_job(job_id), cache, other)

    assert done.status == "needs_review", done.error
    assert done.answered == {"key": 0, "order": 5, "none": 0}
    assert done.agrees, done.differences


def test_an_answer_gone_from_the_cache_ends_the_round_and_is_reported(recorded) -> None:
    store, cache, settings, job_id = recorded
    cache.delete_many(k for stage, _, k in store.call_keys(job_id) if stage == "repair")
    done = replay_job(store, store.get_job(job_id), cache, settings)

    assert done.status == "needs_review" and done.gone == 1
    assert done.answered == {"key": 3, "order": 0, "none": 1}
    assert "versions: v1, v2 before, v1 after" in done.differences
    assert "final version v2 before, v1 after" in done.differences
    assert any(d.startswith("summary: notes +1") for d in done.differences)
    assert not done.agrees and "1 unanswered, 1 gone from the cache" in render_line(done)


def test_differences_name_facts_blocks_findings_judge_and_summary(recorded) -> None:
    store, _, _, job_id = recorded
    before = canonical(store, job_id)
    after = json.loads(json.dumps(before))  # a deep copy
    after["factsheet"]["facts"].append(
        {"id": "f99", "kind": "deadline", "text": "Eine neue Frist", "value_norm": "2027-01-01",
         "segment_ids": ["s0002"], "must_keep": True, "origin": "code"}
    )  # fmt: skip
    after["factsheet"]["facts"][0]["segment_ids"] = ["s0009"]
    v1, v2 = after["versions"]
    v1["blocks"][0]["text"] = "Ein anderer Satz."
    v2["blocks"][0]["fact_ids"] = ["f99"]
    v2["findings"].append("LEX-01 b001 long_word -")
    fact_id = next(iter(v2["judge"]["fact_checks"]))
    v2["judge"]["fact_checks"][fact_id] = "missing"
    after["summary"]["final_version"] = 1
    lines = differences(before, after)

    assert lines[0].startswith('facts: +1 (f99 deadline "Eine neue Frist")')
    assert lines[1].startswith("facts: 1 with another value, sentence or must-keep")
    assert (
        f"v1: 1 of {len(v1['blocks'])} blocks differ ({len(v1['blocks'])} blocks before)" in lines
    )
    assert "v2: fact links differ on 1 blocks" in lines
    assert "v2: findings +1 (LEX-01 b001 long_word -)" in lines
    assert f"v2: judge fact checks differ on 1 ({fact_id} present to missing)" in lines
    assert lines[-1] == "final version v2 before, v1 after"
    assert differences(before, before) == []


def test_replay_jobs_writes_a_file_per_job_and_compares_with_an_earlier_folder(
    recorded, tmp_path
) -> None:
    store, cache, settings, job_id = recorded
    before = tmp_path / "before"
    replay = replay_jobs(store, cache, before, settings_for=lambda name: settings)
    assert [j.job_id for j in replay.jobs] == [job_id] and replay.agreeing == 1
    written = json.loads((before / f"{job_id}.json").read_text(encoding="utf-8"))
    assert written["answered"] == {"key": 5, "order": 0, "none": 0}
    assert written["replayed"] == written["stored"]
    assert "Agrees with the stored artifacts." in (before / REPORT_NAME).read_text("utf-8")

    # The stored version 2 with another text, as a change of the repair code would leave
    # it; and the earlier replay's file with another final version, as a replay before
    # a change of the code would have written it.
    draft = store.get_artifact(job_id, "draft", Draft, version=2)
    first = draft.blocks[0].model_copy(update={"text": "Ein anderer Satz."})
    store.put_artifact(
        job_id, "draft", draft.model_copy(update={"blocks": [first, *draft.blocks[1:]]}), 2
    )
    written["replayed"]["summary"]["final_version"] = 1
    (before / f"{job_id}.json").write_text(json.dumps(written), encoding="utf-8")

    seen = []
    after = replay_jobs(
        store, cache, tmp_path / "after", settings_for=lambda name: settings, against=before,
        on_job=seen.append,
    )  # fmt: skip
    (job,) = after.jobs
    assert seen == [job] and not job.agrees
    assert job.differences == [
        f"v2: 1 of {len(draft.blocks)} blocks differ ({len(draft.blocks)} blocks before)"
    ]
    assert job.changes == ["final version v1 before, v2 after"]
    report = (tmp_path / "after" / REPORT_NAME).read_text("utf-8")
    assert (
        "1 jobs: 0 agree with the stored artifacts, 1 differ, 0 did not reach the review." in report
    )
    assert (
        "1 jobs compared, 1 changed." in report and "- final version v1 before, v2 after" in report
    )
    assert "1 differences; 1 changes" in render_line(job, before)


def test_select_jobs_takes_reviewed_jobs_with_a_source_and_calls_or_the_ids_named(recorded) -> None:
    store, _, _, job_id = recorded
    failed = store.create_job(JobConfig(condition="P2"), title="failed")
    store.put_artifact(failed.id, "source", fx.letter())
    store.record(failed.id, "failed", {"error": "x"})
    no_calls = store.create_job(JobConfig(condition="P2"), title="never ran")
    store.put_artifact(no_calls.id, "source", fx.letter())
    store.record(no_calls.id, "finished", {"stage": "review"})

    assert [j.id for j in select_jobs(store)] == [job_id]
    assert [j.id for j in select_jobs(store, ids=[job_id[:4]])] == [job_id]
    assert select_jobs(store, ids=[failed.id]) == []  # no recorded call to replay
    assert [j.id for j in select_jobs(store, limit=1)] == [job_id]


def test_the_command_replays_the_store_of_the_data_folder(recorded, tmp_path, monkeypatch, capsys):
    from leichtfacile.cli import main

    store, _, settings, job_id = recorded
    monkeypatch.setenv("LEICHTFACILE_DATA__DIR", str(settings.data.dir))
    out = tmp_path / "out"
    code = main(["eval", "replay", "--store", str(store.path), "--out", str(out)])

    assert code == 0, capsys.readouterr().err
    printed = capsys.readouterr().out
    assert f"{job_id}  Brief" in printed and "needs_review  agrees" in printed
    assert (
        "1 jobs: 1 agree with the stored artifacts, 0 differ, 0 did not reach the review" in printed
    )
    assert (out / f"{job_id}.json").exists() and (out / REPORT_NAME).exists()
    # The configured preset is not the one the job ran on (the test's), so the keys differ
    # and the answers come by order.
    assert json.loads((out / f"{job_id}.json").read_text("utf-8"))["answered"]["order"] == 5

    assert main(["eval", "replay", "--store", str(tmp_path / "none.sqlite")]) == 1
    assert "no job database" in capsys.readouterr().err
