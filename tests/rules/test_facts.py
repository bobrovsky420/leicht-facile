"""Fact rules FACT-01 to FACT-06 on a small synthetic letter."""

from __future__ import annotations

from leichtfacile.rules import check_draft
from leichtfacile.rules.messages import render_finding
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
    assert "31. März 2026" in render_finding(errors[0])
    assert result.metrics.fact_coverage == round(2 / 3, 3)


def test_a_question_block_needs_no_provenance() -> None:
    """A question states nothing (10 October 2026): the writer's question to the reader
    typed as a sentence block is not FACT-03's business; a statement without a source
    sentence still is."""
    question = Block(id="b003", kind="sentence", text="Was kostet das?")
    orphan = Block(id="b005", kind="sentence", text="Das Amt prüft alles.")
    result = check_draft(draft(GOOD[0], GOOD[1], question, GOOD[3], orphan), source=SOURCE,
                         factsheet=FACTS)  # fmt: skip
    flagged = [f.block_id for f in result.findings if f.rule_id == "FACT-03"]
    assert flagged == ["b005"]


def test_unreferenced_fact_and_missing_provenance() -> None:
    orphan = Block(id="b003", kind="sentence", text="Das kostet 20 Franken.")
    result = check_draft(draft(GOOD[0], GOOD[1], orphan, GOOD[3]), source=SOURCE, factsheet=FACTS)
    ids = rule_ids(result)
    assert "FACT-02" in ids  # f02 is in the text but no block claims it
    assert "FACT-03" in ids  # b003 names no source sentence
    assert "FACT-01" not in ids  # the value itself is there
    assert any(f.block_id == "b003" for f in result.findings if f.rule_id == "FACT-03")


def test_a_missing_value_is_one_finding() -> None:
    # The fee is gone, block and link: FACT-01 says so, FACT-02 does not say it again.
    result = check_draft(draft(GOOD[0], GOOD[1], GOOD[3]), source=SOURCE, factsheet=FACTS)
    facts = [(f.rule_id, f.fact_id) for f in result.findings if f.rule_id in ("FACT-01", "FACT-02")]
    assert facts == [("FACT-01", "f02")]


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
    messages = [render_finding(f) for f in result.findings if f.rule_id == "FACT-05"]
    assert any("f05" in m and "not in the source" in m for m in messages)
    assert any("f06" in m and "unknown source sentences" in m for m in messages)


def test_value_not_in_the_source_is_an_error_with_the_source_value_suggested() -> None:
    leaked = Block(
        id="b005",
        kind="sentence",
        text="Rufen Sie die DISG an: 031 987 65 43.",
        segment_ids=["s0004"],
    )  # the phone number of the prompt's examples
    result = check_draft(draft(*GOOD, leaked), source=SOURCE, factsheet=FACTS)
    (finding,) = [f for f in result.findings if f.rule_id == "FACT-06"]
    assert finding.block_id == "b005" and finding.severity == "error"
    assert "phone number 031 987 65 43 is not in the source" in render_finding(finding)
    assert finding.evidence == "031 987 65 43"
    assert finding.suggestion == "044 123 45 67"  # the source's only phone number


def test_values_the_source_has_in_another_form_are_not_foreign() -> None:
    hours = Segment(
        id="s0006",
        kind="paragraph",
        para=4,
        text="Schalter: 8-12 Uhr. Mehr unter https://www.zh.ch/de/soziales.html, "
        "Mail an info@zh.ch.",
    )
    source = SOURCE.model_copy(update={"segments": [*SOURCE.segments, hours]})
    blocks = [
        Block(
            id="b001",
            kind="sentence",
            text="Schicken Sie das Gesuch bis 31.3.2026.",
            segment_ids=["s0002"],
        ),
        Block(id="b002", kind="sentence", text="Das kostet CHF 20.-.", segment_ids=["s0003"]),
        Block(
            id="b003",
            kind="sentence",
            text="Rufen Sie an: +41 44 123 45 67.",
            segment_ids=["s0004"],
        ),
        Block(
            id="b004",
            kind="sentence",
            text="Der Schalter ist von 8 Uhr bis 12 Uhr offen.",
            segment_ids=["s0006"],
        ),
        Block(
            id="b005",
            kind="sentence",
            text="Mehr Infos: www.zh.ch oder info@zh.ch.",
            segment_ids=["s0006"],
        ),
    ]
    result = check_draft(draft(*blocks), source=source, factsheet=FACTS)
    assert "FACT-06" not in rule_ids(result)


def test_a_fact_sheet_value_the_source_lacks_is_fact_05_and_fact_06_not_fact_01() -> None:
    """A value the model computed or invented (an end of a period, a sum) is not known:
    FACT-05 warns on the fact sheet, FACT-06 flags it in the draft, and FACT-01 does not
    ask for it when the draft leaves it out."""
    wrong = FACTS.model_copy(update={"facts": [
        *FACTS.facts,
        Fact(id="f05", kind="deadline", text="Frist 30. April", value_norm="2026-04-30",
             segment_ids=["s0002"]),
    ]})  # fmt: skip
    block = Block(
        id="b005",
        kind="sentence",
        text="Die Frist ist der 30. April 2026.",
        fact_ids=["f05"],
        segment_ids=["s0002"],
    )
    ids = rule_ids(check_draft(draft(*GOOD, block), source=SOURCE, factsheet=wrong))
    assert "FACT-05" in ids and "FACT-06" in ids
    without = check_draft(draft(*GOOD), source=SOURCE, factsheet=wrong)
    assert not [f for f in without.findings if f.rule_id == "FACT-01" and f.fact_id == "f05"]
    assert (
        without.metrics.facts_total
        == check_draft(draft(*GOOD), source=SOURCE, factsheet=FACTS).metrics.facts_total
    )


def test_foreign_values_without_a_fact_sheet_suggest_contacts_only() -> None:
    from leichtfacile.rules.document import foreign_values

    two_dates = SOURCE.model_copy(update={"segments": [
        *SOURCE.segments,
        Segment(id="s0006", kind="paragraph", para=4, text="Die Verfügung folgt am 15. Mai 2026."),
    ]})  # fmt: skip
    invented = Draft(doc_id="letter", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Sie bekommen bis 30. Juni 2026 einen Brief."),
        Block(id="b002", kind="sentence", text="Das Amt hat 3 Schalter."),
    ])  # fmt: skip
    found = foreign_values(invented, two_dates, None, "de")
    assert [(f.block_id, f.value.kind, f.value.canonical) for f in found] == [
        ("b001", "date", "2026-06-30")
    ]  # a plain number is never foreign
    assert found[0].suggestion is None  # never a date: the source's only date may be a law's


def test_a_leaflet_number_and_an_address_the_pattern_missed_are_not_foreign() -> None:
    """The final run of 11 October 2026 flagged `Merkblatt 2.06.` (2 June for the date
    pattern, the source's plain number 2.06) and `3003 Bern` after `Schweiz - ` as
    invented; since 13 October the words of the source decide. An address or a date the
    source has nowhere stays foreign."""
    from leichtfacile.rules.document import foreign_values

    source = SOURCE.model_copy(update={"segments": [
        *SOURCE.segments,
        Segment(id="s0006", kind="paragraph", para=4,
                text="Mehr steht im Merkblatt 2.06 (Hausdienstarbeit)."),
        Segment(id="s0007", kind="paragraph", para=5,
                text="Bundesamt für Gesundheit Schwarzenburgstrasse 157 Schweiz - 3003 Bern"),
    ]})  # fmt: skip
    draft_ = Draft(doc_id="letter", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Lesen Sie das Merkblatt 2.06."),
        Block(id="b002", kind="sentence",
              text="Das Amt ist in Bern, Schwarzenburgstrasse 157, 3003 Bern."),
        Block(id="b003", kind="sentence", text="Lesen Sie das Merkblatt 2.07."),
        Block(id="b004", kind="sentence", text="Schreiben Sie an: 3000 Bern."),
    ])  # fmt: skip
    found = foreign_values(draft_, source, None, "de")
    assert [(f.block_id, f.value.kind, f.value.text) for f in found] == [
        ("b003", "date", "2.07."),
        ("b004", "address", "3000 Bern"),
    ]
