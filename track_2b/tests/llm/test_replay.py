"""The recorded runs of the prepared letters (llm/replay.py): what a recording keeps,
when the client answers from it, and the files it is stored in."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel

from leichtfacile.llm.cache import ResponseCache
from leichtfacile.llm.json_out import complete_json
from leichtfacile.llm.replay import (
    Recorder,
    Recording,
    Replay,
    read_recording,
    replay_settings,
    write_recording,
)
from tests.conftest import chat_response, make_settings

MESSAGES = [{"role": "user", "content": "Lies den Brief."}]


class Answer(BaseModel):
    deadline: str


def recording_of(answers: list[dict], letter: str = "brief", **settings) -> Recording:
    return Recording(
        letter=letter,
        recorded_at=datetime(2026, 10, 11, 14, 0, tzinfo=UTC),
        version="test",
        endpoint="https://api.inference.cscs.ch",
        settings=replay_settings(make_settings(**settings)),
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
    recorder = record(make_client, endpoint)
    answers = recorder.answers
    assert [a["text"] for a in answers] == [
        "Die Frist ist der 31. März.",
        '{"deadline": "31.03.2027"}',
    ]
    assert {a["stage"] for a in answers} == {"understand"}
    assert all(a["model"] == make_settings().llm_name for a in answers)


def test_a_replay_takes_the_recorded_path_without_the_endpoint(make_client, endpoint) -> None:
    recorder = record(make_client, endpoint)
    sent = len(endpoint.chat_bodies())
    replay = Replay([(recording_of(recorder.answers), recorder.answers)])
    client = make_client(replay=replay)
    with client.replaying():
        out, results = complete_json(client, MESSAGES, Answer, stage="understand")
    assert out.deadline == "31.03.2027"
    assert [r.usage.cached for r in results] == [True, True]
    assert len(endpoint.chat_bodies()) == sent  # nothing went to the endpoint


def test_outside_replaying_the_endpoint_answers(make_client, endpoint) -> None:
    recorder = record(make_client, endpoint)
    replay = Replay([(recording_of(recorder.answers), recorder.answers)])
    client = make_client(replay=replay)
    endpoint.push(chat_response('{"deadline": "30.04.2027"}'))
    out, results = complete_json(client, MESSAGES, Answer, stage="understand")
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


def test_forgetting_leaves_the_recording_as_it_is(make_client, endpoint, tmp_path) -> None:
    recorder = record(make_client, endpoint)
    replay = Replay([(recording_of(recorder.answers), recorder.answers)])
    cache = ResponseCache(tmp_path / "cache.sqlite")
    client = make_client(cache=cache, replay=replay)
    client.forget_keys([a["key"] for a in recorder.answers])  # a replayed job is deleted
    with client.replaying():
        out, _ = complete_json(client, MESSAGES, Answer, stage="understand")
    assert out.deadline == "31.03.2027"
    cache.close()


def test_a_recording_is_read_back_from_its_file(make_client, endpoint, tmp_path) -> None:
    recorder = record(make_client, endpoint)
    folder = tmp_path / "replay"
    write_recording(folder / "brief.json", recording_of(recorder.answers), recorder.answers)
    recording, answers = read_recording(folder / "brief.json")
    assert recording == recording_of(recorder.answers)
    assert answers == recorder.answers
    replay = Replay.load(folder)
    assert len(replay) == 2
    assert replay.recording("brief") == recording
    assert replay.recording_for(["unknown", answers[1]["key"]]) == recording
    assert replay.get(answers[1]["key"])["text"] == '{"deadline": "31.03.2027"}'


def test_a_broken_recording_is_left_out(tmp_path: Path, caplog) -> None:
    folder = tmp_path / "replay"
    folder.mkdir()
    (folder / "brief.json").write_text("{", encoding="utf-8")
    assert len(Replay.load(folder)) == 0
    assert "brief.json" in caplog.text
    assert len(Replay.load(tmp_path / "missing")) == 0


@pytest.mark.parametrize(
    ("changed", "applies"),
    [
        ({}, True),
        ({"llm_name": "swiss-ai/Apertus-v1.5-70B"}, False),
        ({"llm_judge_name": "swiss-ai/Apertus-v1.5-8B"}, False),
        ({"llm_thinking_mode": "chat-template"}, False),
        ({"max_repair_rounds": 5}, False),
        ({"llm_max_retries": 2, "llm_cache": True}, True),  # no prompt depends on these
    ],
)
def test_a_recording_applies_to_the_settings_it_was_made_with(changed, applies) -> None:
    recording = recording_of([])
    assert recording.applies(make_settings(**changed)) is applies


def test_the_default_judge_is_the_70b_of_the_writers_family() -> None:
    assert replay_settings(make_settings())["judge"] == "swiss-ai/Apertus-v1.5-70B"
    assert replay_settings(make_settings(), judge="other")["judge"] == "other"
