"""The pure half of the rounds (pipeline/versions.py): ids, lists, repeat keys, and what
the lenient answer models make of an answer's loose spellings."""

from __future__ import annotations

from leichtfacile.pipeline.models import AdditionItem, RecoverOut, RepairOut, SemanticOut
from leichtfacile.pipeline.stages import to_judge_report
from leichtfacile.pipeline.versions import (
    RepairRequest,
    add_sentences,
    apply_repairs,
    child_id,
    in_list,
    list_end,
    sentence_key,
    sentences_of,
    wording_key,
)
from leichtfacile.schemas import Block, Draft, Fact, FactSheet
from tests.pipeline import fixtures as fx


def _draft(*blocks: Block) -> Draft:
    return Draft(doc_id="d", lang="de", level="A2", blocks=list(blocks))


def test_child_ids_take_the_first_free_number_under_the_block() -> None:
    taken = {"b005", "b005.1", "b005.3"}
    assert child_id("b005", taken) == "b005.2"
    assert child_id("b005", taken) == "b005.4" and "b005.4" in taken
    assert child_id("b005.1", taken) == "b005.1.1"


def test_a_sentence_after_a_list_item_belongs_to_the_list() -> None:
    blocks = [
        Block(id="b001", kind="sentence", text="Sie brauchen:"),
        Block(id="b002", kind="list_item", text="den Pass"),
        Block(id="b002.1", kind="sentence", text="Der Pass muss gültig sein."),
        Block(id="b003", kind="list_item", text="ein Foto"),
        Block(id="b004", kind="sentence", text="Schicken Sie alles bis 31. März 2026."),
    ]
    by_id = {b.id: b for b in blocks}
    assert [in_list(b, by_id) for b in blocks] == [False, True, True, True, False]
    assert list_end(blocks, 1) == 4 and list_end(blocks, 4) == 4


def test_the_two_keys_differ_only_in_the_final_colon() -> None:
    assert sentence_key("Sie brauchen:") == sentence_key("Sie brauchen.") == "sie brauchen"
    assert wording_key("Sie brauchen:") == "sie brauchen:" != wording_key("Sie brauchen.")
    assert wording_key("Kranken·kasse  zahlt!") == "krankenkasse zahlt"


def test_added_sentences_go_after_the_block_its_children_and_its_list() -> None:
    draft = _draft(
        Block(id="b001", kind="list_item", text="den Pass"),
        Block(id="b001.1", kind="sentence", text="Der Pass muss gültig sein."),
        Block(id="b002", kind="list_item", text="ein Foto"),
        Block(id="b003", kind="sentence", text="Danke."),
    )
    fact = Fact(id="f01", kind="deadline", text="bis 31. März 2026", value_norm="2026-03-31")
    out = add_sentences(draft, "b001", ["Schicken Sie alles bis 31. März 2026."], fact)
    assert [b.id for b in out.blocks] == ["b001", "b001.1", "b002", "b001.2", "b003"]
    assert out.blocks[3].fact_ids == ["f01"] and out.blocks[3].kind == "sentence"


def test_a_block_the_answer_repairs_twice_keeps_both_repairs() -> None:
    """The second item used to replace the first (audit of 6 November 2026)."""
    draft = _draft(
        Block(id="b001", kind="sentence", text="Das Gesuch muss eingereicht werden."),
        Block(id="b002", kind="sentence", text="Danke."),
    )
    out = RepairOut.model_validate(
        {
            "repairs": [
                {"id": "b001", "texts": ["Schicken Sie das Gesuch."]},
                {"id": "b001", "texts": ["Die Frist ist der 31. März 2026."]},
            ]
        }
    )
    fs = FactSheet(doc_id="d")
    new = apply_repairs(draft, out, RepairRequest({"b001": ["x"]}, []), fs)
    assert [(b.id, b.text) for b in new.blocks] == [
        ("b001", "Schicken Sie das Gesuch."),
        ("b001.1", "Die Frist ist der 31. März 2026."),
        ("b002", "Danke."),
    ]


def test_sentences_of_joins_fragments_and_splits_several() -> None:
    texts = [
        "Wenn du nicht entschuldigt fehlst",
        "werden die Absenzen vermerkt.",
        "Ruf an. Sag Bescheid.",
    ]
    assert sentences_of(texts, "de") == [
        "Wenn du nicht entschuldigt fehlst werden die Absenzen vermerkt.",
        "Ruf an.",
        "Sag Bescheid.",
    ]


def test_the_answer_models_read_loose_spellings_and_keep_foreign_rule_ids() -> None:
    assert RecoverOut.model_validate({"after": "b5", "texts": ["Ein Satz."]}).after == "b005"
    assert RecoverOut.model_validate({"texts": ["Ein Satz."]}).after is None
    add = AdditionItem.model_validate({"texts": ["Ein Satz."], "segment_ids": "s0001 s0002"})
    assert add.segment_ids == ["s0001", "s0002"]
    add = AdditionItem.model_validate({"texts": ["Ein Satz."], "fact_ids": "f1, f02"})
    assert add.fact_ids == ["f01", "f02"]
    rid = lambda v: SemanticOut.model_validate({"block_id": "b001", "rule_id": v}).rule_id  # noqa: E731
    assert rid("SEM-3") == rid("sem 03") == rid("3") == "SEM-03"
    assert rid("SEM-03 Pronomen") == "SEM-03"
    assert rid("LEX-01") == "LEX-01" and rid("b004") == "b004"


def test_a_foreign_rule_id_is_dropped_from_the_judge_report() -> None:
    """`LEX-01` and `b004` used to become SEM-01 and SEM-04 (audit of 6 November 2026)."""
    draft = _draft(Block(id="b001", kind="sentence", text="Ein Satz."))
    fs = FactSheet(doc_id="d")
    out = fx.JUDGE_FIRST | {
        "fact_checks": [],
        "semantic_findings": [
            {"block_id": "b001", "rule_id": "LEX-01", "note": "x"},
            {"block_id": "b001", "rule_id": "b004", "note": "y"},
            {"block_id": "b001", "rule_id": "SEM-03", "note": "wer?"},
        ],
    }
    from leichtfacile.pipeline.models import JudgeOut

    report = to_judge_report(JudgeOut.model_validate(out), draft, fs, "m")
    assert [s.rule_id for s in report.semantic_findings] == ["SEM-03"]
