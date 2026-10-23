"""Parsing and checking real model answers (tests/fixtures/llm/README.md)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leichtfacile.llm.client import LLMClient
from leichtfacile.llm.json_out import (
    JSONExtractionError,
    LLMOutputError,
    complete_json,
    extract_json,
)
from leichtfacile.pipeline.models import UnderstandOut, WriteOut
from leichtfacile.pipeline.stages import complete_factsheet, link_facts, to_factsheet
from leichtfacile.rules import check_draft
from leichtfacile.rules.values import parse_value_norm
from leichtfacile.schemas import Block, Draft, SourceDocument
from tests.conftest import chat_response, make_settings

FIXTURES = Path(__file__).parents[1] / "fixtures" / "llm"


@pytest.fixture(scope="module")
def source() -> SourceDocument:
    return SourceDocument.model_validate_json((FIXTURES / "letter_source.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def factsheet(source):
    raw = (FIXTURES / "letter_understand.txt").read_text(encoding="utf-8")
    out = UnderstandOut.model_validate(extract_json(raw))
    return complete_factsheet(to_factsheet(out, source.id), source)


def test_recorded_understand_answer_parses(factsheet, source) -> None:
    known = source.segment_ids()
    model_facts = [f for f in factsheet.facts if f.origin == "model"]
    assert len(model_facts) == 3
    assert all(set(f.segment_ids) <= known for f in factsheet.facts)
    # Code completes what the model left out: the income limits and the contacts.
    code_values = {
        parse_value_norm(f.value_norm, f.kind).key for f in factsheet.facts if f.origin == "code"
    }
    assert {
        ("amount", "42000"),
        ("amount", "61000"),
        ("email", "ipv@musterwil.example"),
    } <= code_values


def test_a_value_dropped_from_a_broken_answer_comes_back_from_code(source) -> None:
    # CSCS, 7 October 2026: the 8B gave the contact fact the e-mail address as a second
    # value without a list. The parser drops it, code completion adds it as a fact.
    raw = (
        '{"facts": [{"kind": "contact", "text": "Telefon 044 123 45 67 oder E-Mail '
        'ipv@musterwil.example", "value_norm": "0441234567", "ipv@musterwil.example", '
        '"segment_ids": ["s0016"], "must_keep": true}]}'
    )
    out = UnderstandOut.model_validate(extract_json(raw, UnderstandOut.model_fields))
    sheet = complete_factsheet(to_factsheet(out, source.id), source)
    values = {
        (f.origin, parse_value_norm(f.value_norm, f.kind).key) for f in sheet.facts if f.value_norm
    }
    assert ("model", ("phone", "0441234567")) in values
    assert ("code", ("email", "ipv@musterwil.example")) in values


def test_recorded_write_answer_and_the_missing_phone_number(factsheet, source) -> None:
    raw = (FIXTURES / "letter_write.txt").read_text(encoding="utf-8")
    out = WriteOut.model_validate(extract_json(raw))
    assert out.blocks[1].fact_ids == ["f07"]  # "f007" normalised
    draft = Draft(
        doc_id=source.id,
        lang="de",
        level="A2",
        blocks=[
            Block(
                id=f"b{i:03d}",
                kind=b.kind,
                text=b.text,
                fact_ids=b.fact_ids,
                segment_ids=b.segment_ids,
            )
            for i, b in enumerate(out.blocks, 1)
        ],
    )
    draft = link_facts(draft, factsheet)
    result = check_draft(draft, source=source, factsheet=factsheet)
    missing = {f.fact_id for f in result.findings if f.rule_id == "FACT-01"}
    phone = next(f.id for f in factsheet.facts if f.value_norm == "0441234567")
    assert phone in missing  # the writer dropped the phone number; code notices
    assert result.metrics.pct_passive == 0.0


def test_a_cut_off_answer_is_reported_as_broken_not_read_as_a_fragment() -> None:
    raw = (FIXTURES / "letter_understand.txt").read_text(encoding="utf-8")
    half = raw[: len(raw) // 2]
    # The first complete inner object would parse, but it is not the answer: the
    # parser reports the break with its position instead.
    with pytest.raises(JSONExtractionError, match="invalid JSON"):
        extract_json(half)


def test_a_cut_off_answer_is_never_used(endpoint, sleeps) -> None:
    raw = (FIXTURES / "letter_understand.txt").read_text(encoding="utf-8")
    endpoint.push(chat_response(raw[: len(raw) // 2], finish_reason="length"))
    llm = LLMClient(make_settings(llm_max_retries=0), http_client=endpoint.http_client())
    with pytest.raises(LLMOutputError, match="cut off"):
        complete_json(llm, [{"role": "user", "content": "x"}], UnderstandOut)
    assert len(endpoint.chat_bodies()) == 1  # no repair round for a cut-off answer


def test_meta_names_the_prompt_versions() -> None:
    meta = json.loads((FIXTURES / "letter_meta.json").read_text(encoding="utf-8"))
    assert meta["understand"]["thinking"] is True and meta["write"]["thinking"] is False
    assert len(meta["write"]["prompt_version"]) == 12
