"""Recovering one missing fact from its source paragraph (stages.recover_fact)."""

from __future__ import annotations

import pytest

from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline.models import UnderstandOut
from leichtfacile.pipeline.stages import fact_window, recover_fact, to_factsheet
from leichtfacile.schemas import Block, Draft
from tests.conftest import chat_response, make_settings
from tests.pipeline import fixtures as fx


@pytest.fixture
def llm(endpoint) -> LLMClient:
    return LLMClient(make_settings(llm_max_retries=0), http_client=endpoint.http_client())


def factsheet():
    return to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), "doc")


def draft() -> Draft:
    """The letter without its deadline (f01, sentence s0003 in paragraph 1)."""
    return Draft(doc_id="doc", lang="de", level="A2", blocks=[
        Block(id="b001", kind="heading", text="Was müssen Sie tun?"),
        Block(id="b002", kind="sentence", text="Schicken Sie das Gesuch an die Gemeinde.",
              segment_ids=["s0003"]),
        Block(id="b003", kind="sentence", text="Das kostet 20 Franken.", segment_ids=["s0004"]),
        Block(id="b004", kind="sentence", text="Rufen Sie das Sozial·amt an: 044 123 45 67.",
              fact_ids=["f03"], segment_ids=["s0005"]),
    ])  # fmt: skip


def answer(texts: list[str], after: str | None = "b002"):
    return chat_response(fx.as_json({"after": after, "texts": texts}))


def test_the_call_sees_only_the_paragraph_and_the_blocks_at_its_place(llm, endpoint) -> None:
    endpoint.push(answer(["Das Gesuch muss bis 31. März 2026 bei der Gemeinde sein."]))
    rec, results = recover_fact(llm, fx.letter(), factsheet(), draft(), "f01")
    assert len(results) == 1 and rec.rejected is None
    assert rec.texts == ["Das Gesuch muss bis 31. März 2026 bei der Gemeinde sein."]
    assert rec.block_id == "b002" and rec.resolved is True
    prompt = endpoint.chat_bodies()[0]["messages"][0]["content"]
    assert "[s0002]" in prompt and "[s0003]" in prompt  # the fact's paragraph
    assert "Auskunft erteilt" not in prompt and "Gebühr" not in prompt  # other paragraphs
    # No fact sheet: the other facts are not there (the style guide's own examples are).
    assert "Die Gebühr ist 20 Franken" not in prompt and "Telefonnummer 044" not in prompt
    assert "Im Text fehlt dieser Wert: 31. März 2026" in prompt
    assert "Satz [s0003]" in prompt
    assert "[b002] Schicken Sie" in prompt and "[b003]" in prompt and "[b004]" not in prompt


def test_an_answer_without_the_value_is_sent_back_once(llm, endpoint) -> None:
    endpoint.push(
        answer(["Schicken Sie das Gesuch bald."]),
        answer(["Schicken Sie das Gesuch bis 31. März 2026."]),
    )
    rec, results = recover_fact(llm, fx.letter(), factsheet(), draft(), "f01")
    assert len(results) == 2 and rec.texts == ["Schicken Sie das Gesuch bis 31. März 2026."]
    feedback = endpoint.chat_bodies()[1]["messages"][-1]["content"]
    assert "den Wert 31. März 2026 nicht" in feedback
    # Twice without it: no suggestion.
    endpoint.push(answer(["Schicken Sie es bald."]), answer(["Schicken Sie es bald."]))
    rec, results = recover_fact(llm, fx.letter(), factsheet(), draft(), "f01")
    assert len(results) == 2 and rec.rejected == "no_answer" and rec.texts == []


def test_a_sentence_that_repeats_the_draft_is_left_out(llm, endpoint) -> None:
    # The phone number is in another paragraph: as a repeat it neither shows nor counts
    # as a value from outside the paragraph.
    endpoint.push(answer([
        "Das Gesuch muss bis 31. März 2026 bei der Gemeinde sein.",
        "Das Sozial·amt hat die Nummer 044 123 45 67.",
        "Schicken Sie das Gesuch an die Gemeinde.",
    ], after="s0003"))  # fmt: skip
    rec, results = recover_fact(llm, fx.letter(), factsheet(), draft(), "f01")
    assert len(results) == 1 and rec.rejected is None
    assert rec.texts == ["Das Gesuch muss bis 31. März 2026 bei der Gemeinde sein."]
    assert len(rec.dropped) == 2
    assert rec.block_id == "b002"  # the block built from sentence s0003


def test_a_value_from_outside_the_paragraph_rejects_the_suggestion(llm, endpoint) -> None:
    leaked = ["Das Gesuch muss bis 31. März 2026 dort sein.", "Rufen Sie 031 111 22 33 an."]
    endpoint.push(answer(leaked), answer(leaked))
    rec, results = recover_fact(llm, fx.letter(), factsheet(), draft(), "f01")
    assert len(results) == 2
    feedback = endpoint.chat_bodies()[1]["messages"][-1]["content"]
    assert "031 111 22 33" in feedback and "nicht im Absatz" in feedback
    assert rec.rejected == "foreign" and rec.foreign == ["031 111 22 33"] and rec.texts == []


def test_nothing_new_and_no_source(llm, endpoint) -> None:
    d = draft()
    d.blocks[1].text = "Schicken Sie das Gesuch bis 31. März 2026 an die Gemeinde."
    endpoint.push(answer(["Schicken Sie das Gesuch bis 31. März 2026 an die Gemeinde."]))
    rec, _ = recover_fact(llm, fx.letter(), factsheet(), d, "f01")
    assert rec.rejected == "nothing_new" and rec.dropped
    fs = factsheet()
    fs.facts[0].segment_ids = []
    rec, results = recover_fact(llm, fx.letter(), fs, draft(), "f01")
    assert rec.rejected == "no_source" and results == []


def test_the_target_skips_headings_and_falls_back_to_the_paragraphs_block(llm, endpoint) -> None:
    endpoint.push(answer(["Das Gesuch muss bis 31. März 2026 dort sein."], after="b001"))
    rec, _ = recover_fact(llm, fx.letter(), factsheet(), draft(), "f01")
    assert rec.block_id == "b002"  # b001 is a heading
    endpoint.push(answer(["Das Gesuch muss bis 31. März 2026 dort sein."], after="b777"))
    rec, _ = recover_fact(llm, fx.letter(), factsheet(), draft(), "f01")
    assert rec.block_id == "b002"


def test_the_window_without_a_block_from_the_paragraph() -> None:
    d = draft()
    d.blocks[1].segment_ids = []  # no block is built from paragraph 1
    window = fact_window(d, fx.letter(), {"s0002", "s0003"})
    assert [b.id for b in window] == ["b001", "b002"]


def test_sentences_of_two_facts_after_one_block_keep_their_order() -> None:
    from leichtfacile.pipeline.stages import add_sentences

    fs = factsheet()
    d = add_sentences(draft(), "b002", ["Erster Satz."], fs.facts[0])
    d = add_sentences(d, "b002", ["Zweiter Satz.", "Dritter Satz."], fs.facts[1])
    assert [(b.id, b.text) for b in d.blocks[1:6]] == [
        ("b002", "Schicken Sie das Gesuch an die Gemeinde."),
        ("b002.1", "Erster Satz."),
        ("b002.2", "Zweiter Satz."),
        ("b002.3", "Dritter Satz."),
        ("b003", "Das kostet 20 Franken."),
    ]
    assert d.blocks[3].fact_ids == [fs.facts[1].id]
    assert add_sentences(d, "b999", ["Nirgends."], fs.facts[0]) == d
