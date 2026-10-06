from __future__ import annotations

import pytest
from pydantic import BaseModel

from leichtfacile.llm.json_out import (
    JSONExtractionError,
    LLMOutputError,
    complete_json,
    extract_json,
    schema_instruction,
)
from tests.conftest import chat_response


class Fact(BaseModel):
    kind: str
    value: str


class FactSheet(BaseModel):
    facts: list[Fact]


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1}',
        '  {"a": 1}  ',
        '```json\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
        'Hier ist das Ergebnis:\n{"a": 1}\nIch hoffe, das hilft.',
        '<|inner_prefix|>Denken {nicht json}<|inner_suffix|>{"a": 1}',
        '<think>{"a": 2}</think>{"a": 1}',
        'Beispiel {kein json} und dann {"a": 1}',
    ],
)
def test_extract_json_object(text):
    assert extract_json(text) == {"a": 1}


def test_extract_json_array():
    assert extract_json("Liste: [1, 2, 3]") == [1, 2, 3]


def test_extract_json_keeps_unicode_and_nested_values():
    text = '{"text": "Sorge·recht bis 31. März", "list": [{"x": "ä"}]}'
    assert extract_json(text) == {"text": "Sorge·recht bis 31. März", "list": [{"x": "ä"}]}


@pytest.mark.parametrize("text", ["", "kein JSON hier", "{kaputt", '<|inner_prefix|>{"a": 1}'])
def test_extract_json_fails_cleanly(text):
    with pytest.raises(JSONExtractionError):
        extract_json(text)


def test_schema_instruction_contains_schema():
    text = schema_instruction(FactSheet)
    assert '"facts"' in text
    assert "JSON" in text


VALID = '{"facts": [{"kind": "deadline", "value": "2027-03-31"}]}'


def test_complete_json_valid_first_time(endpoint, make_client):
    endpoint.push(chat_response(VALID))
    sheet, results = complete_json(make_client(), [{"role": "user", "content": "x"}], FactSheet)
    assert sheet.facts[0].value == "2027-03-31"
    assert len(results) == 1


def test_complete_json_repairs_once(endpoint, make_client):
    endpoint.push(chat_response('{"facts": [{"kind": "deadline"}]}'), chat_response(VALID))
    sheet, results = complete_json(
        make_client(), [{"role": "user", "content": "x"}], FactSheet, stage="understand"
    )
    assert sheet.facts[0].kind == "deadline"
    assert len(results) == 2

    repair = endpoint.chat_bodies()[1]["messages"]
    assert [m["role"] for m in repair] == ["user", "assistant", "user"]
    assert "value" in repair[-1]["content"]  # the validation error names the missing field


def test_complete_json_gives_up_after_repair(endpoint, make_client):
    endpoint.push(chat_response("nichts"), chat_response("immer noch nichts"))
    with pytest.raises(LLMOutputError) as info:
        complete_json(make_client(), [{"role": "user", "content": "x"}], FactSheet)
    assert len(info.value.results) == 2


def test_extract_json_writes_id_ranges_out():
    text = (
        '{"a": ["s0045" ... "s0048"], "b": ["s0064" bis "s0066"], "c": ["f01"-"f03"], '
        '"d": ["s0001" à "s0002"], "e": ["s0010", "s0012" ... "s0013"]}'
    )
    assert extract_json(text) == {
        "a": ["s0045", "s0046", "s0047", "s0048"],
        "b": ["s0064", "s0065", "s0066"],
        "c": ["f01", "f02", "f03"],
        "d": ["s0001", "s0002"],
        "e": ["s0010", "s0012", "s0013"],
    }


def test_extract_json_repairs_commas():
    text = '{"facts": [{"kind": "a"}\n {"kind": "b"},],\n "x": "y"\n "z": 1,}'
    assert extract_json(text) == {"facts": [{"kind": "a"}, {"kind": "b"}], "x": "y", "z": 1}


def test_extract_json_never_returns_a_fragment_of_a_broken_answer():
    text = '{"doc_type": "x", "core": {"what": {"text": "a"}}, "facts": [1 2]}'
    with pytest.raises(JSONExtractionError, match="delimiter.*near"):
        extract_json(text)


def test_complete_json_feeds_the_syntax_error_back(endpoint, make_client):
    broken = '{"facts": [{"kind": "a", "value": "1"} {"kind": "b", "value": "2"}]}'
    endpoint.push(chat_response(broken), chat_response(VALID))
    sheet, results = complete_json(make_client(), [{"role": "user", "content": "x"}], FactSheet)
    assert len(results) == 2 and sheet.facts[0].kind == "deadline"
    feedback = endpoint.chat_bodies()[1]["messages"][-1]["content"]
    assert "delimiter" in feedback and "<<<here>>>" in feedback
