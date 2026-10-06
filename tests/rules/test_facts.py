"""Fact rules FACT-01 to FACT-05 on a small synthetic letter."""

from __future__ import annotations

from leichtfacile.rules import check_draft
from leichtfacile.schemas import (
    Block,
    Draft,
    Fact,
    FactSheet,
    Omission,
    OmitCandidate,
    Segment,
    SourceDocument,
    SourceInfo,
)

SOURCE = SourceDocument(
    id="letter",
    lang="de",
    title="Prämienverbilligung",
    source=SourceInfo(type="text"),
    segments=[
        Segment(id="s0001", kind="heading", text="Prämienverbilligung 2026", heading_level=1),
        Segment(
            id="s0002",
            kind="paragraph",
            text="Das Gesuch ist bis spätestens 31. März 2026 einzureichen.",
            para=1,
        ),
        Segment(
            id="s0003",
            kind="paragraph",
            text="Für die Bearbeitung wird eine Gebühr von CHF 20.- erhoben.",
            para=1,
        ),
        Segment(id="s0004", kind="paragraph", text="Auskunft: Telefon 044 123 45 67.", para=2),
        Segment(id="s0005", kind="paragraph", text="Rechtsgrundlage ist Art. 5 IPVG.", para=3),
    ],
)

FACTS = FactSheet(
    doc_id="letter",
    facts=[
        Fact(id="f01", kind="deadline", text="Frist 31. März 2026", value_norm="2026-03-31",
             segment_ids=["s0002"]),
        Fact(id="f02", kind="amount", text="Gebühr 20 Franken", value_norm="20",
             segment_ids=["s0003"]),
        Fact(id="f03", kind="contact", text="Telefon 044 123 45 67", value_norm="0441234567",
             segment_ids=["s0004"]),
        Fact(id="f04", kind="obligation", text="Gesuch einreichen", segment_ids=["s0002"]),
    ],
    omit_candidates=[OmitCandidate(segment_ids=["s0005"], reason="Rechtsgrundlage")],
)  # fmt: skip


def draft(*blocks: Block, omissions: list[Omission] | None = None) -> Draft:
    return Draft(doc_id="letter", lang="de", level="A2", blocks=list(blocks),
                 omissions=omissions or [])  # fmt: skip


GOOD = [
    Block(id="b001", kind="heading", text="Was müssen Sie tun?"),
    Block(id="b002", kind="sentence", text="Schicken Sie das Gesuch bis 31. März 2026.",
          fact_ids=["f01", "f04"], segment_ids=["s0002"]),
    Block(id="b003", kind="sentence", text="Das kostet 20 Franken.", fact_ids=["f02"],
          segment_ids=["s0003"]),
    Block(id="b004", kind="sentence", text="Fragen? Rufen Sie 044 123 45 67 an.",
          fact_ids=["f03"], segment_ids=["s0004"]),
]  # fmt: skip


def rule_ids(result) -> list[str]:
    return [f.rule_id for f in result.findings if f.rule_id.startswith("FACT")]


def test_complete_draft_has_no_fact_findings() -> None:
    result = check_draft(draft(*GOOD), source=SOURCE, factsheet=FACTS)
    assert rule_ids(result) == []
    assert result.metrics.facts_total == 3
    assert result.metrics.facts_found == 3
    assert result.metrics.fact_coverage == 1.0


def test_changed_deadline_is_an_error() -> None:
    changed = GOOD[1].model_copy(update={"text": "Schicken Sie das Gesuch bis 30. März 2026."})
    result = check_draft(draft(GOOD[0], changed, *GOOD[2:]), source=SOURCE, factsheet=FACTS)
    errors = [f for f in result.findings if f.rule_id == "FACT-01"]
    assert len(errors) == 1
    assert errors[0].fact_id == "f01" and errors[0].severity == "error"
    assert "31. März 2026" in errors[0].message
    assert result.metrics.fact_coverage == round(2 / 3, 3)


def test_unreferenced_fact_and_missing_provenance() -> None:
    orphan = Block(id="b003", kind="sentence", text="Das kostet 20 Franken.")
    result = check_draft(draft(GOOD[0], GOOD[1], orphan, GOOD[3]), source=SOURCE, factsheet=FACTS)
    ids = rule_ids(result)
    assert "FACT-02" in ids  # f02 is in the text but no block claims it
    assert "FACT-03" in ids  # b003 names no source sentence
    assert "FACT-01" not in ids  # the value itself is there
    assert any(f.block_id == "b003" for f in result.findings if f.rule_id == "FACT-03")


def test_unexplained_omission() -> None:
    result = check_draft(draft(GOOD[0], GOOD[1], GOOD[3]), source=SOURCE, factsheet=FACTS)
    (finding,) = [f for f in result.findings if f.rule_id == "FACT-04"]
    assert finding.segment_ids == ["s0003"]  # s0005 is an omit candidate, s0001 a heading
    explained = draft(
        GOOD[0], GOOD[1], GOOD[3],
        omissions=[Omission(what="Gebühr", why="test", segment_ids=["s0003"])],
    )  # fmt: skip
    assert "FACT-04" not in rule_ids(check_draft(explained, source=SOURCE, factsheet=FACTS))


def test_fact_sheet_value_not_in_source() -> None:
    wrong = FACTS.model_copy(
        update={
            "facts": [
                *FACTS.facts,
                Fact(id="f05", kind="deadline", text="Frist 30. April", value_norm="2026-04-30",
                     segment_ids=["s0002"]),
                Fact(id="f06", kind="amount", text="Gebühr", value_norm="20",
                     segment_ids=["s0009"]),
            ]
        }
    )  # fmt: skip
    result = check_draft(draft(*GOOD), source=SOURCE, factsheet=wrong)
    messages = [f.message for f in result.findings if f.rule_id == "FACT-05"]
    assert any("f05" in m and "not in the source" in m for m in messages)
    assert any("f06" in m and "unknown source sentences" in m for m in messages)
