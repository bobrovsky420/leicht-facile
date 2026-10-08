"""Swiss spelling written by code (rules/swiss.py): ß to ss in the blocks and the
glossary, recorded as code edits, and where in the pipeline it runs."""

from __future__ import annotations

import pytest

from leichtfacile.eval.score import kept_code_splits
from leichtfacile.rules import check_draft
from leichtfacile.rules.swiss import apply_ss, replace_ss
from leichtfacile.schemas import Block, Draft, GlossaryEntry
from leichtfacile.store import Store
from tests.conftest import chat_response
from tests.pipeline import fixtures as fx
from tests.pipeline.test_orchestrator import new_job, orchestrator


def draft(lang: str = "de") -> Draft:
    return Draft(
        doc_id="d",
        lang=lang,
        level="A2",
        blocks=[
            Block(id="b001", kind="heading", text="Was heißt das?"),
            Block(id="b002", kind="sentence", text="Die Straße ist gesperrt, außerdem regnet es."),
            Block(id="b003", kind="sentence", text="Das kostet 1'500 Franken."),
        ],
        glossary=[GlossaryEntry(term="Maßnahme", explanation="Etwas, das die Behörde beschließt.")],
    )


def test_ss_replaces_sz_in_blocks_and_glossary_and_records_the_edits() -> None:
    out, edits = apply_ss(draft())
    assert [b.text for b in out.blocks] == [
        "Was heisst das?",
        "Die Strasse ist gesperrt, ausserdem regnet es.",
        "Das kostet 1'500 Franken.",
    ]
    assert out.glossary[0].term == "Massnahme"
    assert out.glossary[0].explanation == "Etwas, das die Behörde beschliesst."
    assert [(e.block_id, e.before, e.after) for e in edits] == [
        ("b001", "heißt", "heisst"),
        ("b002", "Straße", "Strasse"),
        ("b002", "außerdem", "ausserdem"),
        ("glossary", "Maßnahme", "Massnahme"),
        ("glossary", "beschließt", "beschliesst"),
    ]
    assert all(e.rule_id == "CH-01" for e in edits) and out.code_edits == edits
    assert [f.rule_id for f in check_draft(out).findings if f.rule_id == "CH-01"] == []
    assert kept_code_splits(out, edits) == 0  # not Mediopunkt splits


def test_ss_is_idempotent_and_leaves_french_and_clean_drafts_alone() -> None:
    once, edits = apply_ss(draft())
    twice, again = apply_ss(once)
    assert twice == once and again == []
    clean = draft().model_copy(update={"blocks": [draft().blocks[2]], "glossary": []})
    assert apply_ss(clean) == (clean, [])
    french = draft(lang="fr")
    assert apply_ss(french) == (french, [])
    assert replace_ss("Grüße aus Zürich") == ("Grüsse aus Zürich", [("Grüße", "Grüsse")])


def test_the_pipeline_writes_ss_after_the_write_stage(store, endpoint, sleeps) -> None:
    write = {**fx.WRITE, "blocks": [dict(b) for b in fx.WRITE["blocks"]]}
    write["blocks"][1] = {**write["blocks"][1], "text": "Die Straße ist gesperrt."}
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(write)))
    job_id = new_job(store, condition="P1")
    orchestrator(store, endpoint, sleeps).run(job_id)
    stored = store.get_artifact(job_id, "draft", Draft, version=1)
    assert stored.blocks[1].text == "Die Strasse ist gesperrt."
    assert [(e.rule_id, e.before, e.after) for e in stored.code_edits if e.rule_id == "CH-01"] == [
        ("CH-01", "Straße", "Strasse")
    ]


@pytest.fixture
def store(tmp_path) -> Store:
    s = Store(tmp_path / "test.sqlite")
    yield s
    s.close()
