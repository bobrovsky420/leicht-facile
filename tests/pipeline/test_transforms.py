"""Code's steps after a model stage, declared once (pipeline/transforms.py), and the
answers they start from, which are read and never changed (pipeline/models.py: frozen;
pipeline/facts.py and pipeline/versions.py build from copies)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from leichtfacile.pipeline import facts, transforms
from leichtfacile.pipeline.facts import complete_factsheet, factsheet_of, to_factsheet
from leichtfacile.pipeline.models import RepairOut, UnderstandOut, WriteOut
from leichtfacile.pipeline.versions import (
    RepairRequest,
    first_version,
    repair_version,
    without_texts,
)
from leichtfacile.rules.decision import protect_factsheet
from leichtfacile.rules.lists import protect_lists
from leichtfacile.schemas import Block, Draft, FactSheet
from tests.pipeline import fixtures as fx
from tests.rules.test_decision import WITH_HEADINGS
from tests.rules.test_decision import source as decision_source


def _sheet() -> FactSheet:
    return to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), fx.letter().id)


def _draft(*texts: str) -> Draft:
    blocks = [Block(id=f"b{i:03d}", kind="sentence", text=t) for i, t in enumerate(texts, 1)]
    return Draft(doc_id=fx.letter().id, lang="de", level="A2", blocks=blocks)


# -- the declared steps ----------------------------------------------------------------


def test_the_sequences_name_their_steps_in_order() -> None:
    assert [step.__name__ for step in transforms.AFTER_UNDERSTAND] == [
        "hard_values", "decision_parts", "list_items", "vocabulary_terms",
    ]  # fmt: skip
    assert [step.__name__ for step in transforms.AFTER_WRITE] == [
        "fact_links", "glossary", "compound_marks", "spelling",
    ]  # fmt: skip
    assert transforms.AFTER_ROUND == transforms.AFTER_WRITE


def test_the_fact_sheet_is_completed_by_the_steps_in_order() -> None:
    source, fs = fx.letter(), _sheet()
    plain = protect_lists(complete_factsheet(fs, source), source)
    done = transforms.completed(fs, transforms.Context(source))
    assert done == facts.vocabulary_terms(plain, source)
    assert any(t.origin == "vocabulary" for t in done.hard_terms)
    # Without the vocabulary the hard terms stay the model's.
    assert transforms.completed(fs, transforms.Context(source, vocabulary=False)) == plain
    assert all(t.origin == "model" for t in plain.hard_terms)


def test_the_parts_of_a_decision_are_protected_in_decision_mode_only() -> None:
    source = decision_source(WITH_HEADINGS)
    fs = FactSheet(doc_id=source.id)
    standard = transforms.Context(source, vocabulary=False)
    decision = transforms.Context(source, mode="decision", vocabulary=False)
    assert transforms.decision_parts(fs, standard) is fs
    protected = transforms.decision_parts(fs, decision)
    assert protected == protect_factsheet(fs, source) and protected.facts
    # The hard values first, then the decision's parts, then the items of the lists: an
    # item a protected part cites already gets no second fact.
    completed = complete_factsheet(fs, source)
    with_parts = transforms.completed(fs, decision)
    assert with_parts == protect_lists(protect_factsheet(completed, source), source)
    without = transforms.completed(fs, standard)
    assert without == protect_lists(completed, source) and without != with_parts


def test_the_edits_of_a_draft_are_returned_and_stand_on_the_version() -> None:
    source = fx.letter()
    ctx = transforms.Context(source)
    fs = transforms.completed(_sheet(), ctx)
    draft = _draft(
        "Schicken Sie das Gesuch bis 31. März 2026.",
        "Der Selbstbehalt kommt regelmäßig mit der Krankenversicherungspolice.",
    )
    out, edits = transforms.edited(transforms.AFTER_WRITE, draft, fs, ctx)

    assert out.blocks[0].fact_ids == ["f01"] and out.blocks[0].segment_ids == ["s0003"]
    assert out.blocks[1].text == (
        "Der Selbstbehalt kommt regelmässig mit der Kranken·versicherungs·police."
    )
    assert [g.term for g in out.glossary] == ["Gesuch", "Selbstbehalt"]
    assert [(e.rule_id, e.block_id) for e in edits] == [
        ("SEM-05", "glossary"),  # the glossary entries from the vocabulary
        ("SEM-05", "glossary"),
        ("LEX-01", "b002"),  # the compound split
        ("REG-01", "b002"),  # ss for the sharp s
    ]
    assert out.code_edits == edits  # every edit of the steps is on the version
    assert transforms.edited(transforms.AFTER_ROUND, out, fs, ctx) == (out, [])  # idempotent

    plain, fewer = transforms.edited(
        transforms.AFTER_WRITE, draft, fs, transforms.Context(source, vocabulary=False)
    )
    assert plain.glossary == [] and [e.rule_id for e in fewer] == ["LEX-01", "REG-01"]
    assert draft.code_edits == [] and "ß" in draft.blocks[1].text  # the input is as it was


# -- the answers are read, never changed -------------------------------------------------


def test_an_answer_is_frozen() -> None:
    out = RepairOut.model_validate(fx.REPAIR)
    with pytest.raises(ValidationError):
        out.repairs = []
    with pytest.raises(ValidationError):
        out.repairs[0].texts = []
    facts_out = UnderstandOut.model_validate(fx.UNDERSTAND)
    with pytest.raises(ValidationError):
        facts_out.facts = []


def test_the_fact_sheet_of_an_answer_leaves_out_what_is_about_the_examples() -> None:
    terms = [*fx.UNDERSTAND["hard_terms"], {"term": "Einwohnerkontrolle", "explanation": "Amt."}]
    out = UnderstandOut.model_validate(fx.UNDERSTAND | {"hard_terms": terms})
    fs = factsheet_of(out, fx.letter(), topical={out.facts[1].text})
    assert [(f.id, f.kind) for f in fs.facts] == [("f01", "deadline"), ("f02", "contact")]
    assert [t.term for t in fs.hard_terms] == ["Prämienverbilligung"]  # the source's terms only
    assert len(out.facts) == 3 and len(out.hard_terms) == 2  # the answer keeps what it had
    assert factsheet_of(out, fx.letter()).facts[1].kind == "amount"


def test_the_first_version_numbers_the_blocks_across_the_sections() -> None:
    one = WriteOut.model_validate({
        "blocks": [
            {"kind": "heading", "text": "Was ist das?"},
            {"kind": "sentence", "text": "Sie haben wenig Geld.", "fact_ids": ["f01", "f77"]},
            {"kind": "sentence", "text": "Melden Sie den Hund an."},
        ],
        "glossary": [{"term": "Gesuch", "explanation": "Ein Brief an das Amt."}],
    })  # fmt: skip
    two = WriteOut.model_validate({
        "blocks": [
            {"kind": "sentence", "text": "Das kostet 20 Franken."},
            {"kind": "sentence", "text": "Sie haben wenig Geld."},
        ],
        "glossary": [{"term": "gesuch", "explanation": "Noch einmal."}],
        "omissions": [{"what": "Gesetzesartikel", "why": "nicht nötig", "segment_ids": ["s0006"]}],
    })  # fmt: skip
    answers = [(one, {"Melden Sie den Hund an."}), (two, set())]
    draft = first_version(fx.letter(), _sheet(), answers, level="A2")

    assert (draft.version, draft.origin, draft.lang) == (1, "write", "de")
    assert [(b.id, b.text) for b in draft.blocks] == [
        ("b001", "Was ist das?"),
        ("b002", "Sie haben wenig Geld."),  # once: the second section repeats it
        ("b003", "Das kostet 20 Franken."),
    ]
    assert draft.blocks[1].fact_ids == ["f01"]  # f77 is no fact of the sheet
    assert [g.term for g in draft.glossary] == ["Gesuch"]  # a term once
    assert [o.what for o in draft.omissions] == ["Gesetzesartikel"]
    assert len(one.blocks) == 3  # the answer is as the model gave it


def test_a_rounds_version_leaves_the_answer_as_the_model_gave_it() -> None:
    draft = _draft("Das Gesuch muss eingereicht werden.", "Danke.")
    out = RepairOut.model_validate({
        "repairs": [{"id": "b001", "texts": [
            "Schicken Sie das Gesuch", "an die Gemeinde.", "Melden Sie den Hund an.",
        ]}],
        "additions": [{"after": "b002", "texts": ["Das kostet 20 Franken. Rufen Sie an."]}],
    })  # fmt: skip
    before = out.model_dump()
    request = RepairRequest({"b001": ["x"]}, [])
    new, record = repair_version(
        draft, out, request, _sheet(), topical={"Melden Sie den Hund an."}, kind="polish"
    )

    assert out.model_dump() == before  # not a text of the answer changed
    assert (record.kind, record.draft_version, record.parent_version) == ("polish", 2, 1)
    assert record.repairs[0].texts == before["repairs"][0]["texts"]  # what the model answered
    assert [(d.reason, d.block_id, d.text) for d in record.dropped] == [
        ("example", "b001", "Melden Sie den Hund an.")
    ]
    assert [(b.id, b.text) for b in new.blocks] == [
        ("b001", "Schicken Sie das Gesuch an die Gemeinde."),  # the fragments joined
        ("b002", "Danke."),
        ("b002.1", "Das kostet 20 Franken."),  # the two sentences apart
        ("b002.2", "Rufen Sie an."),
    ]
    assert (new.version, new.parent_version, new.origin) == (2, 1, "repair")


def test_an_answer_without_some_texts_is_a_copy() -> None:
    out = RepairOut.model_validate({
        "repairs": [{"id": "b001", "texts": ["A."]}, {"id": "b002", "texts": ["B.", "C."]}],
        "additions": [{"texts": ["A."]}, {"after": "b002", "texts": ["A.", "D."]}],
    })  # fmt: skip
    kept = without_texts(out, {"A."})
    assert [(i.id, i.texts) for i in kept.repairs] == [("b002", ["B.", "C."])]
    assert [(a.after, a.texts) for a in kept.additions] == [("b002", ["D."])]
    assert len(out.repairs) == 2 and out.additions[1].texts == ["A.", "D."]
    assert without_texts(out, set()) is out
