"""The recorded runs of the sample letters (llm/replay.py): what a recording keeps, when
the client answers from it, and the files it is stored in."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from leichtfacile.llm.cache import ResponseCache
from leichtfacile.llm.json_out import complete_json
from leichtfacile.llm.replay import Recorder, Recording, Replay, read_recording, write_recording
from tests.conftest import MODEL, chat_response

MESSAGES = [{"role": "user", "content": "Lies den Brief."}]


class Answer(BaseModel):
    deadline: str


def recording_of(answers: list[dict], letter: str = "brief") -> Recording:
    return Recording(
        letter=letter,
        preset="test",
        models={"writer": MODEL, "judge": MODEL},
        recorded_at=datetime(2026, 11, 8, 14, 0, tzinfo=UTC),
        version="test",
        endpoint="http://llm.test",
        seconds=42.0,
        calls=len(answers),
        result={"errors": 0, "warnings": 3},
    )


def record(make_client, endpoint) -> Recorder:
    """A run whose first answer is thrown away: no JSON, so the model is asked again."""
    endpoint.push(chat_response("Die Frist ist der 31. März."))
    endpoint.push(chat_response('{"deadline": "31.03.2027"}'))
    recorder = Recorder()
    client = make_client(cache=recorder, usage_sink=recorder.observe)
    out, results = complete_json(client, MESSAGES, Answer, stage="understand")
    assert out.deadline == "31.03.2027" and len(results) == 2
    return recorder


def test_the_recorder_keeps_the_answer_the_run_threw_away(make_client, endpoint) -> None:
    answers = record(make_client, endpoint).answers
    assert [a["text"] for a in answers] == [
        "Die Frist ist der 31. März.",
        '{"deadline": "31.03.2027"}',
    ]
    assert {a["stage"] for a in answers} == {"understand"}
    assert {a["model"] for a in answers} == {MODEL}


def test_a_replay_takes_the_recorded_path_without_the_endpoint(make_client, endpoint) -> None:
    recorder = record(make_client, endpoint)
    sent = len(endpoint.chat_bodies())
    client = make_client(replay=Replay([(recording_of(recorder.answers), recorder.answers)]))
    with client.replaying():
        out, results = complete_json(client, MESSAGES, Answer, stage="understand")
    assert out.deadline == "31.03.2027"
    assert [r.usage.cached for r in results] == [True, True]
    assert [r.usage.latency_ms for r in results] == [0, 0]
    assert len(endpoint.chat_bodies()) == sent  # nothing went to the endpoint


def test_outside_replaying_the_endpoint_answers(make_client, endpoint) -> None:
    recorder = record(make_client, endpoint)
    client = make_client(replay=Replay([(recording_of(recorder.answers), recorder.answers)]))
    endpoint.push(chat_response('{"deadline": "30.04.2027"}'))
    out, results = complete_json(client, MESSAGES, Answer, stage="understand")
    assert out.deadline == "30.04.2027"
    assert not results[0].usage.cached


def test_another_prompt_goes_to_the_endpoint(make_client, endpoint) -> None:
    recorder = record(make_client, endpoint)
    client = make_client(replay=Replay([(recording_of(recorder.answers), recorder.answers)]))
    endpoint.push(chat_response('{"deadline": "30.04.2027"}'))
    edited = [{"role": "user", "content": "Lies den Brief, bitte."}]
    with client.replaying():
        out, results = complete_json(client, edited, Answer, stage="understand")
    assert out.deadline == "30.04.2027"
    assert not results[0].usage.cached


def test_a_recorded_answer_comes_before_the_response_cache(make_client, endpoint, tmp_path) -> None:
    recorder = record(make_client, endpoint)
    cache = ResponseCache(tmp_path / "cache.sqlite")
    for answer in recorder.answers:  # the cache holds another answer to the same prompts
        cache.put(answer["key"], answer["model"], {
            "text": '{"deadline": "01.01.2030"}', "reasoning": None, "finish_reason": "stop",
            "tokens_in": 1, "tokens_out": 1})  # fmt: skip
    replay = Replay([(recording_of(recorder.answers), recorder.answers)])
    client = make_client(cache=cache, replay=replay)
    with client.replaying():
        out, _ = complete_json(client, MESSAGES, Answer, stage="understand")
    assert out.deadline == "31.03.2027"
    cache.close()


def test_a_deleted_job_leaves_the_recording_as_it_is(make_client, endpoint, tmp_path) -> None:
    recorder = record(make_client, endpoint)
    replay = Replay([(recording_of(recorder.answers), recorder.answers)])
    cache = ResponseCache(tmp_path / "cache.sqlite")
    client = make_client(cache=cache, replay=replay)
    cache.delete_many(a["key"] for a in recorder.answers)  # as Store.delete_job does
    with client.replaying():
        out, _ = complete_json(client, MESSAGES, Answer, stage="understand")
    assert out.deadline == "31.03.2027"
    cache.close()


def test_a_recording_is_read_back_from_its_file(make_client, endpoint, tmp_path) -> None:
    recorder = record(make_client, endpoint)
    folder = tmp_path / "recordings"
    path = write_recording(folder, recording_of(recorder.answers), recorder.answers)
    assert path == folder / "test" / "brief.json"
    recording, answers = read_recording(path)
    assert recording == recording_of(recorder.answers)
    assert answers == recorder.answers
    replay = Replay.load(folder)
    assert len(replay) == 2
    assert replay.recording_for(["unknown", answers[1]["key"]]) == recording
    assert replay.recording_for(["unknown"]) is None
    assert replay.get(answers[1]["key"])["text"] == '{"deadline": "31.03.2027"}'


def test_a_broken_recording_is_left_out(tmp_path: Path, caplog) -> None:
    folder = tmp_path / "recordings" / "test"
    folder.mkdir(parents=True)
    (folder / "brief.json").write_text("{", encoding="utf-8")
    assert len(Replay.load(tmp_path / "recordings")) == 0
    assert "brief.json" in caplog.text
    assert len(Replay.load(tmp_path / "missing")) == 0
