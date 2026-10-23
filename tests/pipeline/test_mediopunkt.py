"""The Mediopunkt written by code (rules/mediopunkt.py): what it splits, what it must
never touch, and where in the pipeline it runs."""

from __future__ import annotations

import pytest

from leichtfacile.eval.score import kept_code_splits
from leichtfacile.rules import check_draft
from leichtfacile.rules.mediopunkt import GLOSSARY, apply_mediopunkt
from leichtfacile.rules.readability import readability, words
from leichtfacile.rules.values import extract_values
from leichtfacile.schemas import Block, Draft, GlossaryEntry, RuleFindings
from leichtfacile.store import Store
from tests.conftest import chat_response
from tests.pipeline import fixtures as fx
from tests.pipeline.test_baseline_zh import ZH_ANSWER
from tests.pipeline.test_orchestrator import new_job, orchestrator

SENTENCES = [
    ("heading", "Was ist die Krankenversicherungspolice?"),
    ("sentence", "Die Sozialversicherungsstelle prüft die zivilrechtlichen Fragen."),
    ("sentence", "Alleinstehende haben eine Einkommensgrenze von 1'500 Franken."),
    ("sentence", "Sie sind anspruchsberechtigt bis 31. März 2026, 17.30 Uhr."),
    ("list_item", "Rufen Sie an: 044 123 45 67, oder schreiben Sie an info@zh.ch."),
    ("sentence", "Mehr auf www.zh.ch/praemienverbilligung, der Rabatt ist 10 %."),
    ("sentence", "Die Prämien·Verbilligung hilft Ihnen."),
    ("sentence", "Die Organisationen geben Informationen."),
]


def draft(level: str = "A2", lang: str = "de", **extra) -> Draft:
    return Draft(
        doc_id="d",
        lang=lang,
        level=level,
        blocks=[
            Block(id=f"b{i:03d}", kind=kind, text=text)
            for i, (kind, text) in enumerate(SENTENCES, 1)
        ],
        glossary=[
            GlossaryEntry(term="Krankenversicherungspolice", explanation="Ein Papier."),
            GlossaryEntry(term="die Prämien·verbilligung", explanation="Geld vom Kanton."),
        ],
        **extra,
    )


def test_nouns_are_split_and_adjectives_participles_and_verbs_are_not() -> None:
    out, edits = apply_mediopunkt(draft())
    texts = [b.text for b in out.blocks]
    assert texts[0] == "Was ist die Kranken·versicherungs·police?"
    assert texts[1] == "Die Sozial·versicherungs·stelle prüft die zivilrechtlichen Fragen."
    assert texts[2] == "Allein·stehende haben eine Einkommens·grenze von 1'500 Franken."
    assert "anspruchsberechtigt" in texts[3]  # a verb: another word is the fix, not a dot
    assert texts[7] == "Die Organisationen geben Informationen."  # long, but no compounds
    assert {(e.block_id, e.before, e.after) for e in edits} >= {
        ("b001", "Krankenversicherungspolice", "Kranken·versicherungs·police"),
        ("b002", "Sozialversicherungsstelle", "Sozial·versicherungs·stelle"),
        ("b003", "Alleinstehende", "Allein·stehende"),
        ("b003", "Einkommens·grenze".replace("·", ""), "Einkommens·grenze"),
    }
    assert all(e.rule_id == "LEX-01" for e in edits)
    assert out.code_edits == edits


def test_a_capital_after_the_dot_is_lowered() -> None:
    out, edits = apply_mediopunkt(draft())
    assert out.blocks[6].text == "Die Prämien·verbilligung hilft Ihnen."
    assert ("b007", "Prämien·Verbilligung", "Prämien·verbilligung") in {
        (e.block_id, e.before, e.after) for e in edits
    }


def test_glossary_terms_are_split_too() -> None:
    out, edits = apply_mediopunkt(draft())
    assert [g.term for g in out.glossary] == [
        "Kranken·versicherungs·police",
        "die Prämien·verbilligung",
    ]
    glossary_edits = [e for e in edits if e.block_id == "glossary"]
    assert [(e.before, e.after) for e in glossary_edits] == [
        ("Krankenversicherungspolice", "Kranken·versicherungs·police")
    ]


def _values(text: str) -> list[tuple[str, str, str]]:
    return [(v.kind, v.canonical, v.text) for v in extract_values(text, "de")]


def test_values_word_counts_and_readability_do_not_change() -> None:
    before = draft()
    after, _ = apply_mediopunkt(before)
    for old, new in zip(before.blocks, after.blocks, strict=True):
        assert _values(new.text) == _values(old.text)  # positions move, nothing else
        assert len(words(new.text)) == len(words(old.text))
    sentences_before = [b.text for b in before.blocks if b.kind != "heading"]
    sentences_after = [b.text for b in after.blocks if b.kind != "heading"]
    assert readability(sentences_after, "de") == readability(sentences_before, "de")
    metrics_before = check_draft(before).metrics
    metrics_after = check_draft(after).metrics
    assert metrics_after.words == metrics_before.words
    assert metrics_after.readability == metrics_before.readability


def test_lex_01_is_silent_on_the_split_words_and_the_step_is_idempotent() -> None:
    once, edits = apply_mediopunkt(draft())
    flagged = {f.evidence for f in check_draft(once).findings if f.rule_id == "LEX-01"}
    assert flagged == {"zivilrechtlichen", "anspruchsberechtigt", "Organisationen"}
    twice, again = apply_mediopunkt(once)
    assert again == []
    assert twice == once  # text, glossary and the recorded edits are unchanged
    assert len(edits) == 6


def test_b1_has_a_higher_limit() -> None:
    out, _ = apply_mediopunkt(draft(level="B1"))  # 16 letters: Einkommensgrenze fits
    assert out.blocks[2].text == "Alleinstehende haben eine Einkommensgrenze von 1'500 Franken."
    assert out.blocks[1].text.startswith("Die Sozial·versicherungs·stelle prüft")
    assert out.blocks[0].text == "Was ist die Kranken·versicherungs·police?"


def test_a_street_with_its_house_number_stays_as_written() -> None:
    # Seen on a CSCS draft: the splitter does not know street names and cut one into
    # Ostermundi·gens·trasse. An address is a value; it stays as written.
    out, edits = apply_mediopunkt(
        Draft(
            doc_id="d",
            lang="de",
            level="A2",
            blocks=[
                Block(id="b001", kind="sentence", text="Adresse: Ostermundigenstrasse 99B, Bern."),
                Block(id="b002", kind="sentence", text="Das Amt ist an der Ostermundigenstrasse."),
            ],
        )
    )
    assert out.blocks[0].text == "Adresse: Ostermundigenstrasse 99B, Bern."
    assert out.blocks[1].text == "Das Amt ist an der Ostermundigen·strasse."  # the known name
    assert [e.block_id for e in edits] == ["b002"]


def test_a_french_draft_is_untouched() -> None:
    fr = Draft(
        doc_id="d",
        lang="fr",
        level="A2",
        blocks=[Block(id="b001", kind="sentence", text="La Krankenversicherungspolice arrive.")],
    )
    out, edits = apply_mediopunkt(fr)
    assert out == fr and edits == []


@pytest.fixture
def store(tmp_path) -> Store:
    s = Store(tmp_path / "test.sqlite")
    yield s
    s.close()


LONG_BLOCK = {
    "kind": "sentence",
    "text": "Die Krankenversicherungspolice kommt per Post.",
    "segment_ids": ["s0002"],
}
LONG_TERM = {"term": "Krankenversicherungspolice", "explanation": "Ein Papier der Kasse."}
WRITE_LONG = {
    **fx.WRITE,
    "blocks": [*fx.WRITE["blocks"], LONG_BLOCK],
    "glossary": [*fx.WRITE["glossary"], LONG_TERM],
}
REPAIR_LONG = {
    **fx.REPAIR,
    "repairs": [
        {"id": "b002", "texts": ["Schicken Sie das Gesuch an die Sozialversicherungsstelle.",
                                 "Das Gesuch muss bis 31. März 2026 dort sein."]},
        *fx.REPAIR["repairs"][1:],
    ],
}  # fmt: skip


def test_p1_splits_after_write_before_the_check(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(WRITE_LONG)))
    job_id = new_job(store, condition="P1")
    orchestrator(store, endpoint, sleeps).run(job_id)
    assert store.get_job(job_id).status == "needs_review", store.get_job(job_id).error
    v1 = store.get_artifact(job_id, "draft", Draft, version=1)
    assert v1.blocks[-1].text == "Die Kranken·versicherungs·police kommt per Post."
    assert "Kranken·versicherungs·police" in [g.term for g in v1.glossary]
    # the splits; the glossary entries code adds from the vocabulary are rule SEM-05's
    assert [(e.block_id, e.after) for e in v1.code_edits if e.rule_id == "LEX-01"] == [
        ("b006", "Kranken·versicherungs·police"),
        ("glossary", "Kranken·versicherungs·police"),
    ]
    rules = store.get_artifact(job_id, "rules", RuleFindings, version=1)
    assert not [f for f in rules.findings if f.rule_id == "LEX-01" and f.block_id == "b006"]


def test_p2_splits_every_repaired_version_and_records_per_version(store, endpoint, sleeps):
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(WRITE_LONG)),
        chat_response(fx.as_json(fx.JUDGE_FIRST)),
        chat_response(fx.as_json(REPAIR_LONG)),
        chat_response(fx.as_json(fx.JUDGE_SECOND)),
    )
    job_id = new_job(store, condition="P2")
    orchestrator(store, endpoint, sleeps).run(job_id)
    assert store.get_job(job_id).status == "needs_review", store.get_job(job_id).error
    v1 = store.get_artifact(job_id, "draft", Draft, version=1)
    v2 = store.get_artifact(job_id, "draft", Draft, version=2)
    assert v2.by_id()["b002"].text == "Schicken Sie das Gesuch an die Sozial·versicherungs·stelle."
    assert v2.by_id()["b006"].text == "Die Kranken·versicherungs·police kommt per Post."
    splits = [[e.before for e in v.code_edits if e.rule_id == "LEX-01"] for v in (v1, v2)]
    assert splits[0] == ["Krankenversicherungspolice"] * 2
    assert splits[1] == ["Sozialversicherungsstelle"]  # this version only
    # The repair prompt saw the split text: no LEX-01 line for the block code had fixed.
    repair_prompt = endpoint.chat_bodies()[3]["messages"][-1]["content"]
    assert "Krankenversicherungspolice" not in repair_prompt


def test_the_baselines_keep_the_prompts_text_as_written(store, endpoint, sleeps) -> None:
    endpoint.push(
        chat_response(fx.BASELINE_TEXT.replace("Kranken·kasse", "Krankenversicherungspolice"))
    )
    p0 = new_job(store, condition="P0")
    orchestrator(store, endpoint, sleeps).run(p0)
    draft_p0 = store.get_artifact(p0, "draft", Draft)
    assert "Krankenversicherungspolice" in draft_p0.text() and draft_p0.code_edits == []

    endpoint.push(chat_response(ZH_ANSWER.replace("Kranken·kasse", "Krankenversicherungspolice")))
    zh = new_job(store, condition="P0-ZH-complete")
    orchestrator(store, endpoint, sleeps).run(zh)
    draft_zh = store.get_artifact(zh, "draft", Draft)
    assert "Krankenversicherungspolice" in draft_zh.text() and draft_zh.code_edits == []
    for job_id in (p0, zh):
        rules = store.get_artifact(job_id, "rules", RuleFindings, version=1)
        assert "LEX-01" in {f.rule_id for f in rules.findings}  # the rule still reports it


def test_the_eval_counts_splits_of_earlier_rounds_that_the_final_version_keeps() -> None:
    first, edits = apply_mediopunkt(draft())
    # A repair rewrites one block without the split word and keeps the others as given;
    # its own version records no edit.
    blocks = [*first.blocks]
    blocks[0] = blocks[0].model_copy(update={"text": "Was ist das Papier?"})
    final = first.model_copy(update={"version": 2, "blocks": blocks, "code_edits": []})
    assert kept_code_splits(final, final.code_edits) == 0
    kept = kept_code_splits(final, edits)
    assert kept == len({(e.block_id, e.after) for e in edits}) - 1  # the police block is gone
    glossary = [e for e in edits if e.block_id == GLOSSARY]
    assert glossary and kept_code_splits(final, glossary) == len(glossary)
