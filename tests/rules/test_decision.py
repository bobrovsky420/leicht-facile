"""Decision mode: the protected parts of a decision, the fact sheet built on them and
FACT-08 (rules/decision.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from leichtfacile.ingest import ingest_text
from leichtfacile.rules import check_draft
from leichtfacile.rules.decision import protect_factsheet, protected_segments
from leichtfacile.schemas import (
    Block,
    CoreAnswer,
    CoreQuestions,
    Draft,
    Fact,
    FactSheet,
    Omission,
    OmitCandidate,
    SourceDocument,
)

# A decision with headings, the way an authority writes it.
WITH_HEADINGS = """# Entscheid über eine Beistandschaft

Kindes- und Erwachsenenschutzbehörde Musterwil, Entscheid vom 14. Oktober 2026.

## Erwägungen

1. Lea Muster kann ihre Rechnungen seit dem 3. Juni 2026 nicht mehr bezahlen.

2. Eine Beistandschaft ist deshalb nötig.

## Entscheid

1. Für Lea Muster wird eine Vertretungsbeistandschaft errichtet.

2. Die Gebühr von Fr. 450.00 wird Lea Muster auferlegt.

3. Mitteilung an:
- Lea Muster (Einschreiben)
- Sozialdienst Musterwil

## Rechtsmittelbelehrung

Gegen diesen Entscheid kann innert 30 Tagen seit Mitteilung Beschwerde beim Obergericht,
Gerichtsstrasse 12, 9999 Musterwil, erhoben werden.

Eröffnet am 16. Oktober 2026.
"""

# A court's decision without headings: the operative part opens with a sentence, the
# appeal instructions are one of its numbered items.
WITHOUT_HEADINGS = """Verwaltungsgericht des Kantons Schwyz

Entscheid vom 17. Oktober 2022

Am 3. Juni 2022 hat die KESB eine Beistandschaft errichtet. Dagegen hat der Beschwerdeführer
am 26. August 2022 Beschwerde erhoben.

Demnach erkennt das Verwaltungsgericht:

1. Die Beschwerde wird abgewiesen.

2. Es werden keine Verfahrenskosten erhoben.

3. Gegen diesen Entscheid kann innert 30 Tagen seit Zustellung Beschwerde erhoben werden.

4. Zustellung an:
- den Beschwerdeführer
- die Vorinstanz

Schwyz, 17. Oktober 2022.

Im Namen des Verwaltungsgerichts.
"""


def source(text: str) -> SourceDocument:
    return ingest_text(text, lang="de", doc_id="decision")


def seg(doc: SourceDocument, snippet: str) -> str:
    """The id of the first segment whose text contains the snippet."""
    return next(s.id for s in doc.segments if snippet in s.text)


def test_the_operative_part_and_the_appeal_are_found_by_their_headings() -> None:
    doc = source(WITH_HEADINGS)
    found = protected_segments(doc)
    assert found.found_by == "heading"
    assert [p.text for p in found.items] == [
        "Für Lea Muster wird eine Vertretungsbeistandschaft errichtet.",
        "Die Gebühr von Fr. 450.00 wird Lea Muster auferlegt.",
    ]  # the distribution list is no item
    assert found.appeal is not None
    assert found.appeal.text.startswith("Gegen diesen Entscheid kann innert 30 Tagen seit")
    assert seg(doc, "Eröffnet am") not in found.ids()
    assert seg(doc, "seit dem 3. Juni 2026") not in found.ids()  # the reasoning is free


def test_the_operative_part_and_the_appeal_are_found_by_their_text() -> None:
    doc = source(WITHOUT_HEADINGS)
    found = protected_segments(doc)
    assert found.found_by == "text"
    assert [p.text for p in found.items] == [
        "Die Beschwerde wird abgewiesen.",
        "Es werden keine Verfahrenskosten erhoben.",
    ]
    assert found.appeal is not None
    assert "innert 30 Tagen seit Zustellung" in found.appeal.text
    assert seg(doc, "Zustellung an") not in found.ids()
    assert seg(doc, "Schwyz, 17. Oktober 2022") not in found.ids()
    assert seg(doc, "Beschwerde erhoben") not in found.ids()  # the narrative, no instructions


def test_an_ordinary_letter_protects_nothing() -> None:
    doc = source("# Prämienverbilligung\n\nDas Gesuch ist bis 31. März 2026 einzureichen.\n")
    found = protected_segments(doc)
    assert found.items == () and found.appeal is None and found.found_by == ""


def factsheet(doc: SourceDocument) -> FactSheet:
    reasoning = seg(doc, "seit dem 3. Juni 2026")
    item_1 = seg(doc, "Vertretungsbeistandschaft errichtet")
    item_2 = seg(doc, "Fr. 450.00")
    return FactSheet(
        doc_id="decision",
        core=CoreQuestions(what=CoreAnswer(text="Eine Beistandschaft.", segment_ids=[item_1])),
        facts=[
            # the model's: stays as the model said
            Fact(id="f01", kind="other", text="Beistandschaft nötig",
                 segment_ids=[seg(doc, "deshalb nötig")], must_keep=False),
            # code found the fee in the operative part, the model had marked it droppable
            Fact(id="f02", kind="amount", text="Gebühr Fr. 450.00", value_norm="450",
                 segment_ids=[item_2], must_keep=False, origin="code"),
            # code found a date of the reasoning: background in a decision
            Fact(id="f03", kind="deadline", text="seit dem 3. Juni 2026", value_norm="2026-06-03",
                 segment_ids=[reasoning], must_keep=True, origin="code"),
        ],
        omit_candidates=[
            OmitCandidate(segment_ids=[reasoning, item_1], reason="Begründung"),
            OmitCandidate(segment_ids=[item_2], reason="Gebühr"),
        ],
    )  # fmt: skip


def test_protect_factsheet_keeps_the_parts_and_frees_the_reasoning() -> None:
    doc = source(WITH_HEADINGS)
    fs = protect_factsheet(factsheet(doc), doc)
    keep = {f.id: f.must_keep for f in fs.facts}
    assert keep["f01"] is False  # the model's choice outside the parts stands
    assert keep["f02"] is True  # in the operative part: must-keep whatever the model said
    assert keep["f03"] is False  # a code value of the reasoning, in no core answer
    parts = [f for f in fs.facts if f.origin == "code" and not f.value_norm]
    assert [f.kind for f in parts] == ["other", "other", "deadline"]
    assert all(f.must_keep for f in parts)
    assert parts[0].text == "Für Lea Muster wird eine Vertretungsbeistandschaft errichtet."
    assert parts[2].segment_ids == list(protected_segments(doc).appeal.segment_ids)
    assert [o.segment_ids for o in fs.omit_candidates] == [[seg(doc, "seit dem 3. Juni 2026")]]


def test_protect_factsheet_leaves_an_ordinary_letter_alone() -> None:
    doc = source("# Prämienverbilligung\n\nDas Gesuch ist bis 31. März 2026 einzureichen.\n")
    fact = Fact(id="f01", kind="deadline", text="Frist", value_norm="2026-03-31",
                segment_ids=["s0002"], must_keep=False, origin="code")  # fmt: skip
    fs = FactSheet(doc_id="decision", facts=[fact])
    assert protect_factsheet(fs, doc) == fs


def draft(doc: SourceDocument, *cited: str, omissions: list[Omission] | None = None) -> Draft:
    blocks = [Block(id="b001", kind="heading", text="Was hat die Behörde entschieden?")]
    for i, snippet in enumerate(cited, 2):
        block = Block(
            id=f"b{i:03d}", kind="sentence", text=f"Satz {i}.", segment_ids=[seg(doc, snippet)]
        )
        blocks.append(block)
    return Draft(doc_id="decision", lang="de", level="A2", blocks=blocks, omissions=omissions or [])


def fact_08(result) -> list:
    return [f for f in result.findings if f.rule_id == "FACT-08"]


def test_fact_08_names_a_dropped_item_with_its_fact_id() -> None:
    doc = source(WITH_HEADINGS)
    fs = protect_factsheet(factsheet(doc), doc)
    d = draft(doc, "Vertretungsbeistandschaft errichtet", "innert 30 Tagen")  # item 2 dropped
    (finding,) = fact_08(check_draft(d, source=doc, factsheet=fs, mode="decision"))
    assert finding.severity == "error" and finding.block_id is None
    assert finding.message == (
        "Item 2 of the operative part is in no block: "
        "Die Gebühr von Fr. 450.00 wird Lea Muster auferlegt."
    )
    assert finding.message_key == "FACT-08" and finding.message_params["item"] == 2
    part = next(f for f in fs.facts if f.text.startswith("Die Gebühr von Fr. 450.00"))
    assert finding.fact_id == part.id
    assert finding.segment_ids == [seg(doc, "Fr. 450.00")]


def test_fact_08_flags_an_omitted_appeal_and_is_silent_when_everything_is_cited() -> None:
    doc = source(WITH_HEADINGS)
    fs = protect_factsheet(factsheet(doc), doc)
    appeal = seg(doc, "innert 30 Tagen")
    omitted = draft(
        doc, "Vertretungsbeistandschaft errichtet", "Fr. 450.00",
        omissions=[Omission(what="Rechtsmittel", why="zu lang", segment_ids=[appeal])],
    )  # fmt: skip
    (finding,) = fact_08(check_draft(omitted, source=doc, factsheet=fs, mode="decision"))
    assert finding.message_key == "FACT-08.appeal_omitted"
    assert finding.message.startswith("The appeal instructions are listed as omitted: Gegen diesen")
    complete = draft(doc, "Vertretungsbeistandschaft errichtet", "Fr. 450.00", "innert 30 Tagen")
    assert fact_08(check_draft(complete, source=doc, factsheet=fs, mode="decision")) == []


def test_fact_08_is_silent_in_standard_mode() -> None:
    doc = source(WITH_HEADINGS)
    fs = protect_factsheet(factsheet(doc), doc)
    d = draft(doc, "Vertretungsbeistandschaft errichtet")
    assert fact_08(check_draft(d, source=doc, factsheet=fs)) == []
    assert len(fact_08(check_draft(d, source=doc, factsheet=fs, mode="decision"))) == 2


def test_the_parts_of_a_decision_do_not_trip_fact_02() -> None:
    # The part facts have no value, so blocks are linked to them by the sentences they
    # cite (stages.link_facts); FACT-02 leaves them to FACT-08.
    doc = source(WITH_HEADINGS)
    fs = protect_factsheet(factsheet(doc), doc)
    d = draft(doc, "Vertretungsbeistandschaft errichtet")
    result = check_draft(d, source=doc, factsheet=fs, mode="decision")
    assert [f.fact_id for f in result.findings if f.rule_id == "FACT-02"] == ["f02"]


ROOT = Path(__file__).parents[2]
EXAMPLE = ROOT / "data" / "examples" / "sources" / "entscheid-beistandschaft-musterwil.txt"
PUBLISHED = ROOT / "data" / "cache" / "decisions" / "SZ_VG_001_III-2022-132_2022-10-17.pdf"


def test_the_example_decision_has_its_parts() -> None:
    doc = ingest_text(EXAMPLE.read_text(encoding="utf-8"), lang="de")
    found = protected_segments(doc)
    assert found.found_by == "heading" and len(found.items) == 13
    assert found.items[0].text.startswith("Für Lea Muster wird eine Vertretungsbeistandschaft")
    assert found.items[-1].text.startswith("Die Gebühr von Fr. 450.00")  # no distribution list
    assert found.appeal is not None
    assert "Gerichtsstrasse 12, 9999 Musterwil" in found.appeal.text
    fs = protect_factsheet(FactSheet(doc_id=doc.id), doc)
    assert len(fs.facts) == 14 and all(f.must_keep and not f.value_norm for f in fs.facts)


@pytest.mark.skipif(not PUBLISHED.exists(), reason="fetched when needed (docs/sources.md)")
def test_the_published_decision_has_no_headings_and_is_found_by_its_text() -> None:
    from leichtfacile.ingest import ingest_pdf

    doc = ingest_pdf(PUBLISHED.read_bytes(), lang="de")
    found = protected_segments(doc)
    assert found.found_by == "text"
    assert [p.text for p in found.items] == [
        "1. Die Beschwerde wird im Sinne der Erwägungen abgewiesen.",
        "2. Es werden keine Verfahrenskosten erhoben.",
    ]
    assert found.appeal is not None and "innert 30 Tagen seit Zustellung" in found.appeal.text


# -- the notice: FACT-07 on the export's lines, and the exporters ------------------------

NOTICE = "Diese Erklärung hilft Ihnen, den Entscheid zu verstehen. Massgebend ist der Entscheid."


def test_fact_07_wants_the_notice_first_and_last_and_exempts_it_from_the_layout_rules() -> None:
    from leichtfacile.export import layout_lines
    from leichtfacile.rules import get_checker

    blocks = [
        Block(id="b001", kind="heading", text="Was hat die Behörde entschieden?"),
        Block(id="b002", kind="sentence", text="Sie bekommen eine Beiständin."),
    ]
    checker = get_checker("de")
    lines = layout_lines(blocks, notice=NOTICE)
    assert lines[0] == NOTICE and lines[-1] == NOTICE and len(NOTICE) > 85
    assert checker.check_export(lines, "A2", notice=NOTICE) == []  # no FACT-07, no LAY-01/02
    ids = [f.rule_id for f in checker.check_export(layout_lines(blocks), "A2", notice=NOTICE)]
    assert ids == ["FACT-07", "FACT-07"]
    (last,) = checker.check_export(
        [NOTICE, "", "Sie bekommen eine Beiständin."], "A2", notice=NOTICE
    )
    assert last.message_key == "FACT-07.last" and last.evidence == "Sie bekommen eine Beiständin."
    assert checker.check_export(layout_lines(blocks), "A2") == []  # a standard job: no notice


def test_the_exporters_write_the_notice_as_the_first_and_last_paragraph() -> None:
    from leichtfacile.export.html import to_html
    from leichtfacile.export.markdown import to_markdown
    from leichtfacile.schemas import GlossaryEntry

    d = Draft(
        doc_id="decision", lang="de", level="A2",
        blocks=[Block(id="b001", kind="sentence", text="Sie bekommen eine Beiständin.")],
        glossary=[GlossaryEntry(term="Beiständin", explanation="Eine Person, die hilft.")],
    )  # fmt: skip
    md = to_markdown(d, title="Entscheid", notice=NOTICE)
    paragraphs = [p.strip() for p in md.split("\n\n") if p.strip()]
    assert paragraphs[0] == "# Entscheid" and paragraphs[2] == NOTICE and paragraphs[-1] == NOTICE
    html = to_html(d, notice=NOTICE)
    assert html.count(f'<p class="notice">{NOTICE}</p>') == 2
    assert (
        html.index('<p class="notice">')
        < html.index("Sie bekommen")
        < html.rindex('<p class="notice">')
    )
    assert '<p class="notice">' not in to_html(d) and NOTICE not in to_markdown(d)
