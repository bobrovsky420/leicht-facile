"""The checks of the German of Germany and Austria that the golden sentences cannot
show: the spelling written by code, the style guide in the variety's spelling, the
findings' suggestions, the decision mode on a Bescheid, and the pairs by region."""

# ruff: noqa: E501  (the Bescheid fixtures keep their sentences on one line each)

from __future__ import annotations

from leichtfacile.eval.dataset import Pair, select
from leichtfacile.ingest import ingest_text
from leichtfacile.rules import check_draft, style_guide
from leichtfacile.rules.decision import protected_segments
from leichtfacile.rules.swiss import apply_spelling
from leichtfacile.schemas import Block, Draft, GlossaryEntry


def draft(region: str, *texts: str) -> Draft:
    return Draft(
        doc_id="d",
        lang="de",
        region=region,
        level="A2",
        blocks=[Block(id=f"b{i:03d}", kind="sentence", text=t) for i, t in enumerate(texts, 1)],
        glossary=[
            GlossaryEntry(term="Massnahme", explanation="Etwas, das die Behörde beschliesst.")
        ],
    )


def findings(d: Draft) -> list[tuple[str, str | None, str | None]]:
    return [(f.rule_id, f.key, f.suggestion) for f in check_draft(d).findings]


# -- the spelling written by code --------------------------------------------------


def test_code_writes_the_sharp_s_in_germany_and_austria_and_ss_in_switzerland() -> None:
    german = draft("DE", "Die Strasse ist gesperrt, ausserdem regnet es.", "Die Masse bleibt.")
    out, edits = apply_spelling(german)
    assert [b.text for b in out.blocks] == [
        "Die Straße ist gesperrt, außerdem regnet es.", "Die Masse bleibt.",
    ]  # fmt: skip
    assert out.glossary[0].term == "Maßnahme" and "beschließt" in out.glossary[0].explanation
    assert [(e.rule_id, e.before, e.after) for e in edits][:2] == [
        ("REG-01", "Strasse", "Straße"), ("REG-01", "ausserdem", "außerdem"),
    ]  # fmt: skip
    assert out.code_edits == edits
    # Austria the same; Switzerland the other way round; the second pass changes nothing.
    assert (
        apply_spelling(german.model_copy(update={"region": "AT"}))[0]
        .blocks[0]
        .text.startswith("Die Straße")
    )
    swiss = draft("CH", "Die Straße ist gesperrt.")
    assert apply_spelling(swiss)[0].blocks[0].text == "Die Strasse ist gesperrt."
    assert apply_spelling(out) == (out, [])


# -- the style guide and the checks ------------------------------------------------


def test_the_style_guide_speaks_the_variety() -> None:
    germany = style_guide("de-DE", "A2")
    assert "Große Zahlen schreibst du mit Punkt: 1.500 Euro" in germany
    assert "9 Uhr oder 9:30 Uhr" in germany and "ß, wo es hingehört" in germany
    assert "Grosse" not in germany and "Franken" not in germany and "Velo" not in germany
    austria = style_guide("de-AT", "A2")
    assert "4. Jänner 2026" in austria and "9 Uhr oder 9.30 Uhr" in austria
    assert "ÖBB" in austria and "Gehsteig" in austria
    assert "1'500 Franken" in style_guide("de", "A2")  # Switzerland as before


def test_the_findings_of_germany_and_austria_carry_the_varietys_suggestions() -> None:
    german = draft(
        "DE",
        "Sie fahren mit dem Velo ins Spital.",
        "Rufen Sie 0301234567 an.",
        "Das kostet 1500 Euro, also EUR 1.500,00.",
        "Sie anerkennen die Rechnung.",
    )
    found = findings(german)
    assert ("REG-03", "REG-03.germany", "Fahrrad") in found
    assert ("REG-03", "REG-03.germany", "Krankenhaus") in found
    assert ("NUM-08", "NUM-08.grouped", "0 30 12 34 567") in found
    assert ("NUM-02", "NUM-02", "1.500") in found
    assert ("NUM-07", "NUM-07", "1.500 Euro") in found
    assert any(rule == "GRAM-08" for rule, _, _ in found)
    assert all(rule != "REG-01" for rule, _, _ in found)  # no Swiss ss in the text
    austria = findings(draft("AT", "Sie gehen im Januar ins Spital."))
    assert ("REG-03", "REG-03.austria", "Jänner") in austria
    assert all(key != "REG-03.austria" or sug != "Krankenhaus" for _, key, sug in austria)
    swiss = findings(draft("CH", "Sie anerkennen die Rechnung.", "Sie fahren mit dem Velo."))
    assert all(rule not in ("GRAM-08", "REG-03") for rule, _, _ in swiss)


# -- the decision mode on a Bescheid --------------------------------------------------

BESCHEID_DE = """Stadt Musterstadt
Amt für Wohnungswesen

Bescheid über Wohngeld

Sehr geehrte Frau Muster,

auf Ihren Antrag vom 3. Februar 2026 bewilligen wir Ihnen Wohngeld von 180,00 Euro im Monat.

Das Wohngeld wird vom 1. März 2026 bis zum 28. Februar 2027 gezahlt.

## Begründung

Sie haben einen Anspruch nach § 1 des Wohngeldgesetzes. Ihr Einkommen liegt unter der Grenze.

## Rechtsbehelfsbelehrung

Gegen diesen Bescheid können Sie innerhalb eines Monats nach Bekanntgabe Widerspruch erheben. Der Widerspruch ist bei der Stadt Musterstadt, Rathausplatz 1, 50667 Musterstadt, einzulegen.

Mit freundlichen Grüßen
"""

BESCHEID_AT = """Bezirkshauptmannschaft Musterbezirk

Bescheid

## Spruch

Ihrem Ansuchen vom 3. Jänner 2026 auf Wohnbeihilfe wird stattgegeben. Die Wohnbeihilfe beträgt € 240,- monatlich ab 1. Februar 2026.

## Begründung

Die Voraussetzungen nach § 5 des Wohnbauförderungsgesetzes sind erfüllt.

## Rechtsmittelbelehrung

Gegen diesen Bescheid kann binnen vier Wochen nach Zustellung Beschwerde an das Landesverwaltungsgericht erhoben werden. Die Beschwerde ist bei der Bezirkshauptmannschaft einzubringen.

Für den Bezirkshauptmann
"""


def test_a_german_bescheid_is_protected_from_the_salutation_to_the_reasons() -> None:
    doc = ingest_text(BESCHEID_DE, lang="de").model_copy(update={"region": "DE"})
    found = protected_segments(doc)
    assert found.found_by == "reasons"
    assert [p.text for p in found.items] == [
        "auf Ihren Antrag vom 3. Februar 2026 bewilligen wir Ihnen Wohngeld von 180,00 Euro im "
        "Monat.",
        "Das Wohngeld wird vom 1. März 2026 bis zum 28. Februar 2027 gezahlt.",
    ]
    assert found.appeal is not None
    assert "innerhalb eines Monats nach Bekanntgabe Widerspruch" in found.appeal.text
    assert "Rathausplatz 1" in found.appeal.text and "Grüßen" not in found.appeal.text
    assert not any("Wohngeldgesetzes" in p.text for p in found.parts())  # the reasons are free


def test_an_austrian_bescheid_is_protected_by_its_spruch() -> None:
    doc = ingest_text(BESCHEID_AT, lang="de").model_copy(update={"region": "AT"})
    found = protected_segments(doc)
    assert found.found_by == "heading"
    assert len(found.items) == 1 and "stattgegeben" in found.items[0].text
    assert "€ 240,-" in found.items[0].text
    assert found.appeal is not None
    assert "binnen vier Wochen nach Zustellung Beschwerde" in found.appeal.text
    assert "Bezirkshauptmann" not in found.appeal.text.split("einzubringen.")[-1]


def test_the_swiss_variety_reads_a_german_bescheid_as_an_ordinary_letter() -> None:
    doc = ingest_text(BESCHEID_DE, lang="de")  # region CH: no Begründung fallback
    assert protected_segments(doc).items == ()


# -- the evaluation's pairs by region --------------------------------------------------


def test_pairs_are_selected_by_region() -> None:
    pairs = [
        Pair(id="zh-a-de", lang="de", url_standard="u", url_easy="e"),
        Pair(id="koeln-b-de", lang="de", region="DE", url_standard="u", url_easy="e"),
        Pair(id="tirol-c-de", lang="de", region="AT", url_standard="u", url_easy="e"),
    ]
    assert [p.id for p in select(pairs, region="DE")] == ["koeln-b-de"]
    assert [p.id for p in select(pairs, region="CH")] == ["zh-a-de"]
    assert len(select(pairs)) == 3 and len(select(pairs, region="all")) == 3
