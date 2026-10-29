"""The values in the German of Germany and Austria (docs/rules.md, "Value kinds"): the
thousands dot and the decimal comma, the euro, the phone shapes, five-digit postcodes,
German and Austrian IBANs, the file numbers of a Bescheid, Jänner; and what the Swiss
varieties still read as before."""

from __future__ import annotations

import pytest

from leichtfacile.pipeline.stages import complete_factsheet, link_facts
from leichtfacile.rules import check_draft
from leichtfacile.rules.document import display_value
from leichtfacile.rules.values import (
    Value,
    extract_values,
    format_date,
    format_identifier,
    format_phone,
    format_thousands,
    parse_value_norm,
)
from leichtfacile.schemas import Block, Draft, Fact, FactSheet, Segment, SourceDocument, SourceInfo


def keys(text: str, lang: str) -> list[tuple[str, str]]:
    return [(v.kind, v.canonical) for v in extract_values(text, lang)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Die Gebühr beträgt 1.500,00 €.", ("amount", "1500")),
        ("Sie bekommen 1.500 Euro im Monat.", ("amount", "1500")),
        ("EUR 1.234,56", ("amount", "1234.56")),
        ("20,50 Euro", ("amount", "20.5")),
        ("€ 330,- pro Monat", ("amount", "330")),  # the Austrian pages' style
        ("€ 1.500,--", ("amount", "1500")),
        ("1,5 Mio. Euro", ("amount", "1500000")),
        ("rund 20.000 Menschen", ("number", "20000")),
        ("Version 2.5", ("number", "2.5")),
        ("1.500.000 Einwohner", ("number", "1500000")),
        ("Telefon 0221 / 221-30700", ("phone", "022122130700")),
        ("Telefon: 0 55 44 33 22 11", ("phone", "05544332211")),  # Netzwerk, rule Z8
        ("(05544) 332211", ("phone", "05544332211")),
        ("+49 30 1234567", ("phone", "0301234567")),
        ("0800 1234567", ("phone", "08001234567")),
        ("Tel. 01 53115-0", ("phone", "01531150")),  # Vienna
        ("+43 1 711 00-0", ("phone", "01711000")),
        ("+43 512 508 7831", ("phone", "05125087831")),
        ("Musterstraße 1, 50667 Köln", ("address", "Musterstraße 1||50667 Köln")),
        ("Rathausstraße 1, 1010 Wien", ("address", "Rathausstraße 1||1010 Wien")),
        ("Hauptstraße 5/2/7, 1020 Wien", ("address", "Hauptstraße 5/2/7||1020 Wien")),
        ("Kurfürstendamm 12, 10719 Berlin", ("address", "Kurfürstendamm 12||10719 Berlin")),
        ("Musterstr. 1, 50667 Köln", ("address", "Musterstraße 1||50667 Köln")),
        ("D-10115 Berlin", ("address", "||10115 Berlin")),
        ("Anschrift: 01067 Dresden", ("address", "||01067 Dresden")),
        ("am 1. Jänner 2027", ("date", "2027-01-01")),
        ("bis 15. Feber 2027", ("date", "2027-02-15")),
        ("Kassenzeichen 123456789", ("identifier", "123456789")),
        ("GZ 2026-0042", ("identifier", "2026-0042")),
        ("Geschäftszahl: ABC-123/2026", ("identifier", "ABC-123/2026")),
        ("Steuer-ID 12 345 678 901", ("identifier", "12345678901")),
        ("SVNR 1234 010180", ("identifier", "1234010180")),
        ("Rentenversicherungsnummer 65 170839 J 003", ("identifier", "65170839J003")),
        ("IBAN DE89 3704 0044 0532 0130 00", ("identifier", "DE89370400440532013000")),
        ("AT61 1904 3002 3457 3201", ("identifier", "AT611904300234573201")),
        ("binnen vier Wochen nach Zustellung", ("period", "4w")),
        ("innerhalb eines Monats nach Bekanntgabe", ("period", "1m")),
    ],
)
def test_german_and_austrian_values(text: str, expected: tuple[str, str]) -> None:
    assert expected in keys(text, "de-DE"), keys(text, "de-DE")
    assert expected in keys(text, "de-AT"), keys(text, "de-AT")


def test_the_swiss_varieties_read_as_before() -> None:
    # The dot is no thousands separator in Switzerland, and five digits are a count.
    assert keys("1.500 Franken", "de") == [("number", "1")]  # as before: no dot thousands
    assert keys("Mit 30000 Stimmen.", "de") == [("number", "30000")]
    assert keys("Fr. 1'500.50", "de") == [("amount", "1500.5")]
    # What a Swiss letter may cite is still found: a German address with its country
    # letter, a German IBAN, an Austrian month.
    assert ("address", "||10115 Berlin") in keys("D-10115 Berlin", "de")
    assert ("identifier", "DE89370400440532013000") in keys("DE89 3704 0044 0532 0130 00", "de")
    assert ("date", "2027-01-01") in keys("am 1. Jänner 2027", "de")
    # A German phone shape is read in the German varieties only.
    assert ("phone", "022122130700") not in keys("Telefon 0221 / 221-30700", "de")


def test_formatting_in_the_german_varieties() -> None:
    assert format_thousands("1500", "de-DE") == "1.500"
    assert format_thousands("1500.5", "de-AT") == "1.500,5"
    assert format_thousands("1500", "de") == "1'500" and format_thousands("1500", "fr") == "1 500"
    assert format_date("2027-01-01", "de-AT") == "1. Jänner 2027"
    assert format_date("2027-01-01", "de-DE") == "1. Januar 2027"
    assert format_date("2027-01-01", "de") == "1. Januar 2027"
    assert format_phone("05544332211", "de-DE") == "0 55 44 33 22 11"
    assert format_phone("0301234567", "de-DE") == "0 30 12 34 567"
    assert format_phone("0441234567") == "044 123 45 67"
    assert format_identifier("DE89370400440532013000") == "DE89 3704 0044 0532 0130 00"
    assert format_identifier("AT611904300234573201") == "AT61 1904 3002 3457 3201"
    assert display_value(Value("amount", "1500"), "de-DE") == "1.500 Euro"
    assert display_value(Value("amount", "1500"), "de") == "1'500 Franken"
    assert display_value(Value("date", "2027-01-01"), "de-AT") == "1. Jänner 2027"
    assert display_value(Value("phone", "05544332211"), "de-AT") == "0 55 44 33 22 11"


@pytest.mark.parametrize(
    ("value_norm", "kind", "expected"),
    [
        ("1.500", "amount", ("amount", "1500")),  # the German model writes the dot
        ("1500.50", "amount", ("amount", "1500.5")),  # the prompt's decimal point
        ("1.500,00", "amount", ("amount", "1500")),
        ("+49 30 1234567", "contact", ("phone", "0301234567")),
        ("4930 1234567", "contact", ("phone", "0301234567")),
        ("Musterstraße 1, 50667 Köln", "contact", ("address", "Musterstraße 1||50667 Köln")),
    ],
)
def test_parse_value_norm_in_the_german_variety(value_norm, kind, expected) -> None:
    value = parse_value_norm(value_norm, kind, "de-DE")
    assert value is not None and (value.kind, value.canonical) == expected


# -- the fact rules and the code completion on a synthetic German Bescheid ----------

BESCHEID = SourceDocument(
    id="bescheid",
    lang="de",
    region="DE",
    title="Bescheid",
    source=SourceInfo(type="text"),
    segments=[
        Segment(id="s0001", kind="heading", text="Bescheid über Wohngeld", heading_level=1),
        Segment(id="s0002", kind="paragraph", para=1,
                text="Kassenzeichen 12345/2026, Steuer-ID 12 345 678 901."),
        Segment(id="s0003", kind="paragraph", para=2,
                text="Sie erhalten ab 1. Januar 2027 Wohngeld von 1.500,00 € im Monat."),
        Segment(id="s0004", kind="paragraph", para=3,
                text="Gegen diesen Bescheid können Sie innerhalb eines Monats nach Bekanntgabe "
                "Widerspruch erheben."),
        Segment(id="s0005", kind="paragraph", para=3,
                text="Der Widerspruch ist zu richten an: Stadt Köln, Amt für Wohnungswesen, "
                "Musterstraße 1, 50667 Köln."),
        Segment(id="s0006", kind="paragraph", para=4, text="Telefon 0221 / 221-30700."),
    ],
)  # fmt: skip
MODEL_FACTS = FactSheet(
    doc_id="bescheid",
    facts=[Fact(id="f01", kind="right", text="Sie bekommen Wohngeld.", segment_ids=["s0003"])],
)
FACTS = complete_factsheet(MODEL_FACTS, BESCHEID)


def test_code_completion_reads_the_german_values() -> None:
    added = {f.value_norm for f in FACTS.facts if f.origin == "code"}
    assert added == {
        "12345/2026", "12345678901", "2027-01-01", "1500", "1 Monat",
        "Musterstraße 1, 50667 Köln", "022122130700",
    }  # fmt: skip
    assert all(f.must_keep for f in FACTS.facts if f.origin == "code")


def german_draft(*items: tuple[str, str]) -> Draft:
    blocks = [
        Block(id=f"b{i:03d}", kind="sentence", text=text, segment_ids=segments.split())
        for i, (text, segments) in enumerate(items, 1)
    ]
    blocks[0] = blocks[0].model_copy(update={"fact_ids": ["f01"]})
    return link_facts(
        Draft(doc_id="bescheid", lang="de", region="DE", level="A2", blocks=blocks), FACTS
    )


def fact_rule_ids(d: Draft) -> list[str]:
    findings = check_draft(d, source=BESCHEID, factsheet=FACTS).findings
    return sorted({f.rule_id for f in findings if f.rule_id.startswith("FACT")})


def test_a_german_draft_that_keeps_every_value_passes_the_fact_rules() -> None:
    d = german_draft(
        ("Sie bekommen Wohngeld: 1.500 Euro im Monat.", "s0001 s0003"),
        ("Das gilt ab 1. Januar 2027.", "s0003"),
        ("Ihr Kassenzeichen ist 12345/2026.", "s0002"),
        ("Ihre Steuer-ID ist 12345678901.", "s0002"),
        ("Sie haben 1 Monat Zeit für den Widerspruch.", "s0004"),
        ("Schreiben Sie an: Amt für Wohnungswesen, Musterstraße 1, 50667 Köln.", "s0005"),
        ("Rufen Sie an: 0221 221 30700.", "s0006"),
    )
    assert fact_rule_ids(d) == []


def test_a_changed_amount_and_an_invented_phone_number_are_found_in_the_german_draft() -> None:
    d = german_draft(
        ("Sie bekommen Wohngeld: 1.400 Euro im Monat.", "s0001 s0003"),
        ("Das gilt ab 1. Januar 2027.", "s0003"),
        ("Ihr Kassenzeichen ist 12345/2026.", "s0002"),
        ("Ihre Steuer-ID ist 12345678901.", "s0002"),
        ("Sie haben 1 Monat Zeit für den Widerspruch.", "s0004"),
        ("Schreiben Sie an: Amt für Wohnungswesen, Musterstraße 1, 50667 Köln.", "s0005"),
        ("Rufen Sie an: 0 30 99 99 99 9.", "s0006"),
    )
    assert fact_rule_ids(d) == ["FACT-01", "FACT-06"]
    findings = check_draft(d, source=BESCHEID, factsheet=FACTS).findings
    missing = next(f for f in findings if f.rule_id == "FACT-01")
    assert missing.suggestion == "1.500 Euro"  # the German form of the missing value
