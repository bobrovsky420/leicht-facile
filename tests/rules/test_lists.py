"""Lists of the source stay whole: the facts `protect_lists` adds and FACT-10
(rules/lists.py)."""

from __future__ import annotations

from leichtfacile.ingest import ingest_text
from leichtfacile.pipeline.rounds import build_request, missing_count
from leichtfacile.pipeline.stages import complete_factsheet
from leichtfacile.rules import check_draft
from leichtfacile.rules.lists import list_facts, protect_lists, source_lists
from leichtfacile.rules.messages import render_finding
from leichtfacile.schemas import Block, Draft, FactSheet, Omission, OmitCandidate

CAMP = """# Klassenlager 2027

Das Lager dauert vom 7. bis 11. Juni 2027.

Mitzunehmen sind insbesondere:

- Schlafsack und Kissenbezug
- Hausschuhe und Wanderschuhe
- Taschengeld von höchstens CHF 20.-

Handys bleiben zu Hause.
"""


def camp(omit: list[str] | None = None):
    source = ingest_text(CAMP, lang="de", doc_id="camp")
    sheet = FactSheet(doc_id="camp")
    if omit:
        sheet = sheet.model_copy(
            update={"omit_candidates": [OmitCandidate(segment_ids=omit, reason="nebensächlich")]}
        )
    return source, protect_lists(complete_factsheet(sheet, source), source)


def segment(source, start: str) -> str:
    return next(s.id for s in source.segments if s.text.startswith(start))


def fact_10(draft: Draft, source, fs: FactSheet) -> list:
    rules = check_draft(draft, source=source, factsheet=fs)
    return [f for f in rules.findings if f.rule_id == "FACT-10"]


def test_every_list_item_becomes_a_fact_unless_a_code_fact_cites_it_already() -> None:
    source, fs = camp()
    (items,) = source_lists(source)
    assert [s.text for s in items] == [
        "Schlafsack und Kissenbezug",
        "Hausschuhe und Wanderschuhe",
        "Taschengeld von höchstens CHF 20.-",
    ]
    added = list_facts(fs)
    # The pocket money is a value fact of the code completion already.
    assert [f.text for f in added] == [
        "- Schlafsack und Kissenbezug",
        "- Hausschuhe und Wanderschuhe",
    ]
    assert all(f.must_keep and f.origin == "code" and not f.value_norm for f in added)
    cited = [segment(source, "Schlafsack"), segment(source, "Hausschuhe")]
    assert [f.segment_ids for f in added] == [[cited[0]], [cited[1]]]
    ids = [f.id for f in fs.facts]
    assert len(set(ids)) == len(ids) and ids[-2:] == [f.id for f in added]
    assert protect_lists(fs, source) == fs  # no second fact for a cited item


def test_fact_10_names_a_dropped_item_and_an_omitted_one() -> None:
    source, fs = camp()
    first, second = segment(source, "Schlafsack"), segment(source, "Hausschuhe")
    draft = Draft(doc_id="camp", lang="de", level="A2", blocks=[
        Block(id="b001", kind="list_item", text="Schlafsack und Kissen·bezug",
              segment_ids=[first]),
    ])  # fmt: skip
    (finding,) = fact_10(draft, source, fs)
    assert finding.fact_id == list_facts(fs)[1].id and finding.severity == "error"
    assert "Hausschuhe und Wanderschuhe" in render_finding(finding)
    omitted = draft.model_copy(update={"omissions": [
        Omission(what="Hausschuhe", why="unwichtig", segment_ids=[second]),
    ]})  # fmt: skip
    (finding,) = fact_10(omitted, source, fs)
    assert finding.key == "FACT-10.omitted"
    whole = draft.model_copy(update={"blocks": [
        *draft.blocks,
        Block(id="b002", kind="list_item", text="Haus·schuhe und Wander·schuhe",
              segment_ids=[second]),
    ]})  # fmt: skip
    assert not fact_10(whole, source, fs)


def test_a_dropped_item_is_asked_for_like_a_missing_value() -> None:
    source, fs = camp()
    draft = Draft(doc_id="camp", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Handys bleiben zu Hause.",
              segment_ids=[segment(source, "Handys")]),
    ])  # fmt: skip
    rules = check_draft(draft, source=source, factsheet=fs)
    dropped = [f.fact_id for f in rules.findings if f.rule_id == "FACT-10"]
    assert len(dropped) == 2 and missing_count(rules) >= 2
    asked = [f.id for f in build_request(draft, rules, None, fs).missing]
    assert set(dropped) <= set(asked)


BROCHURE = """# Beitragserstattung

- Wann kann ich mir meine Beiträge erstatten lassen?
- Erstattung nur auf Antrag

## Erstattung nur auf Antrag

Sie erreichen uns so:

- Telefon
- 044 123 45 67
- Unterlagen:
- Pass oder Ausweis
- Pass oder Ausweis
"""


def brochure():
    source = ingest_text(BROCHURE, lang="de", doc_id="brochure")
    return source, protect_lists(complete_factsheet(FactSheet(doc_id="brochure"), source), source)


def test_questions_intro_lines_and_repeated_lines_become_no_fact() -> None:
    source, fs = brochure()
    # The cover's question and its table of contents, the intro "Unterlagen:", the
    # phone number (a value fact of the code completion) and the repeated line.
    assert [f.text for f in list_facts(fs)] == ["- Telefon", "- Pass oder Ausweis"]
    assert list_facts(fs)[1].segment_ids == [segment(source, "Pass")]


def test_an_item_worded_under_a_neighbours_id_counts_as_kept() -> None:
    source, fs = brochure()
    number, intro = segment(source, "044"), segment(source, "Unterlagen")
    draft = Draft(doc_id="brochure", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Telefon: 044 123 45 67",
              segment_ids=[number]),
        Block(id="b002", kind="sentence", text="Sie brauchen einen Pass oder einen Ausweis.",
              segment_ids=[segment(source, "Erstattung nur")]),
    ])  # fmt: skip
    # "Telefon" is worded by the block that cites the number's line; the papers are
    # worded by a block that cites the heading, not the list.
    (finding,) = fact_10(draft, source, fs)
    assert "Pass oder Ausweis" in render_finding(finding)
    cited_list = draft.model_copy(update={"blocks": [
        draft.blocks[0],
        draft.blocks[1].model_copy(update={"segment_ids": [intro]}),
    ]})  # fmt: skip
    assert not fact_10(cited_list, source, fs)


def test_an_item_in_a_droppable_passage_is_background() -> None:
    source, _ = camp()
    second = segment(source, "Hausschuhe")
    _, fs = camp(omit=[second])
    background = next(f for f in list_facts(fs) if f.segment_ids == [second])
    assert not background.must_keep
    draft = Draft(doc_id="camp", lang="de", level="A2", blocks=[
        Block(id="b001", kind="list_item", text="Schlafsack und Kissen·bezug",
              segment_ids=[segment(source, "Schlafsack")]),
    ])  # fmt: skip
    assert not fact_10(draft, source, fs)
