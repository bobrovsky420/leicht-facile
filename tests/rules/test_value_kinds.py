"""The value kinds period, identifier and postal address (rules.md, "Facts"): how they
are found, how they match, and what FACT-01, FACT-06 and the code completion of the
fact sheet do with them, on a synthetic decision of a child and adult protection
authority."""

from __future__ import annotations

import pytest

from leichtfacile.pipeline.stages import complete_factsheet, link_facts
from leichtfacile.rules import check_draft
from leichtfacile.rules.values import (
    Value,
    extract_values,
    format_address,
    format_identifier,
    format_period,
    hard_values,
    matches,
    parse_value_norm,
)
from leichtfacile.schemas import Block, Draft, Fact, FactSheet, Segment, SourceDocument, SourceInfo


def keys(text: str, lang: str = "de") -> list[tuple[str, str]]:
    return [(v.kind, v.canonical) for v in extract_values(text, lang)]


# -- extraction ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("innert 30 Tagen seit Zustellung", ("period", "30d")),
        ("Sie haben dreissig Tage Zeit.", ("period", "30d")),
        ("einundzwanzig Tage", ("period", "21d")),
        ("eine 30-tägige Frist", ("period", "30d")),
        ("innert zwei Wochen", ("period", "2w")),
        ("ein Jahr gültig", ("period", "1y")),
        ("einjährige Frist", ("period", "1y")),
        ("innert 5 Arbeitstagen", ("period", "5wd")),
        ("5 Werktage", ("period", "5wd")),
        ("innert 10 Kalendertagen", ("period", "10d")),
        ("Kinder bis 16 Jahren", ("period", "16y")),
        ("nach 6 Monaten", ("period", "6m")),
        ("AHV-Nummer 756.1234.5678.97", ("identifier", "756.1234.5678.97")),
        ("756 1234 5678 97", ("identifier", "756.1234.5678.97")),
        ("7561234567897", ("identifier", "756.1234.5678.97")),
        ("IBAN CH93 0076 2011 6238 5295 7", ("identifier", "CH9300762011623852957")),
        ("CH9300762011623852957", ("identifier", "CH9300762011623852957")),
        ("Postkonto 80-151-4", ("identifier", "80-151-4")),
        ("UID CHE-123.456.789 MWST", ("identifier", "CHE-123.456.789")),
        ("Referenz 2026-0042", ("identifier", "2026-0042")),
        ("Referenz 2026" + chr(0x2011) + "0042", ("identifier", "2026-0042")),  # a hyphen
        ("Dossier-Nr. 12345", ("identifier", "12345")),
        ("Geschäftsnummer: K-4711", ("identifier", "K-4711")),
        ("Geschäfts·nummer: K-4711", ("identifier", "K-4711")),
        ("Die Nummer von Ihrem Dossier ist 2026-0042.", ("identifier", "2026-0042")),
        ("Verfügung Nr. 12 vom 31.3.2026", ("identifier", "12")),
        ("Gerichtsstrasse 12, 8000 Musterwil", ("address", "Gerichtsstrasse 12||8000 Musterwil")),
        ("Gerichts·strasse 12, 8000 Musterwil", ("address", "Gerichtsstrasse 12||8000 Musterwil")),
        ("Bahnhofstr. 3a\n8001 Zürich", ("address", "Bahnhofstrasse 3a||8001 Zürich")),
        ("Postfach 1234, 8000 Musterwil", ("address", "|Postfach 1234|8000 Musterwil")),
        ("Bezirksgericht, 8000 Musterwil", ("address", "||8000 Musterwil")),
        ("Adresse: CH-2000 Neuchâtel", ("address", "||2000 Neuchâtel")),
        ("Untere Zollgasse 7, Postfach, 3000 Bern 7",
         ("address", "Untere Zollgasse 7|Postfach|3000 Bern")),
        ("8000 Zürich Telefon 044 123 45 67", ("address", "||8000 Zürich")),
    ],
)  # fmt: skip
def test_german_values(text: str, expected: tuple[str, str]) -> None:
    assert expected in keys(text)


@pytest.mark.parametrize(
    ("lang", "text", "expected"),
    [
        ("fr", "dans les trente jours", ("period", "30d")),
        ("fr", "un délai de 10 jours ouvrables", ("period", "10wd")),
        ("fr", "quatre-vingt-onze jours", ("period", "91d")),
        ("fr", "vingt et un jours", ("period", "21d")),
        ("fr", "deux semaines", ("period", "2w")),
        ("fr", "un an", ("period", "1y")),
        ("fr", "N° de dossier 2026-0042", ("identifier", "2026-0042")),
        ("fr", "Référence : AB-123", ("identifier", "AB-123")),
        ("fr", "Rue de la Gare 5, Case postale 123, 1200 Genève",
         ("address", "Rue de la Gare 5|Case postale 123|1200 Genève")),
        ("it", "entro 30 giorni", ("period", "30d")),
        ("it", "due settimane", ("period", "2w")),
        ("it", "Via Cantonale 3, 6900 Lugano", ("address", "Via Cantonale 3||6900 Lugano")),
    ],
)  # fmt: skip
def test_french_and_italian_values(lang: str, text: str, expected: tuple[str, str]) -> None:
    assert expected in keys(text, lang)


@pytest.mark.parametrize(
    ("text", "absent"),
    [
        ("Formular 5100 einreichen", "identifier"),  # a form number stays a number
        ("In diesem Fall 300 Franken", "identifier"),  # an amount after a common word
        ("Ihr Dossier 30 Tage", "identifier"),  # a period after a keyword
        ("Am 3. Tag", "period"),  # an ordinal
        ("Pro Tag 20 Franken, am Montag, im Jahr 2026", "period"),  # no count in front
        ("Kosten: 1000 Franken", "address"),  # a four-digit amount and a noun
        ("Es gibt 1500 Plätze", "address"),  # a count in the middle of a sentence
        ("Budget 2026 Zürich", "address"),  # a year followed by a capitalised word
        ("Telefon 044 123 45 67", "identifier"),
        ("Frist 31.03.2026", "identifier"),
    ],
)
def test_what_is_not_a_value_of_the_new_kinds(text: str, absent: str) -> None:
    assert absent not in {kind for kind, _ in keys(text)}


def test_counts_of_periods_and_codes_are_not_plain_numbers_too() -> None:
    assert keys("innert 30 Tagen, Referenz 2026-0042, 8000 Musterwil") == [
        ("period", "30d"),
        ("identifier", "2026-0042"),
        ("address", "||8000 Musterwil"),
    ]  # in text order, and no number among them


def test_value_text_is_the_code_and_the_address_as_written() -> None:
    (ref,) = extract_values("Ihre Geschäfts·nummer lautet 2026-0042.")
    assert (ref.text, ref.start, ref.end) == ("2026-0042", 29, 38)
    (addr,) = extract_values("Gerichts·strasse 12, 8000 Musterwil.")
    assert addr.text == "Gerichts·strasse 12, 8000 Musterwil"


def test_a_mediopunkt_from_code_leaves_the_values_unchanged() -> None:
    before = (
        "Die Geschäftsnummer ist 2026-0042. Schreiben Sie an: Gerichtsstrasse 12, 8000 Musterwil."
    )
    after = before.replace("Geschäftsnummer", "Geschäfts·nummer").replace(
        "Gerichtsstrasse", "Gerichts·strasse"
    )
    assert keys(before) == keys(after)


# -- normalised fact values and matching ---------------------------------------------


@pytest.mark.parametrize(
    ("value_norm", "kind", "expected"),
    [
        ("30 Tage", "deadline", ("period", "30d")),
        ("innert 30 Tagen", "deadline", ("period", "30d")),
        ("2026-0042", "other", ("identifier", "2026-0042")),  # a bare code
        ("K-4711", "other", ("identifier", "K-4711")),
        ("Geschäftsnummer 2026-0042", "other", ("identifier", "2026-0042")),
        ("756.1234.5678.97", "other", ("identifier", "756.1234.5678.97")),
        ("CH93 0076 2011 6238 5295 7", "other", ("identifier", "CH9300762011623852957")),
        ("8000 Musterwil", "contact", ("address", "||8000 Musterwil")),
        ("Gerichtsstrasse 12, 8000 Musterwil", "contact",
         ("address", "Gerichtsstrasse 12||8000 Musterwil")),
        ("12345", "other", ("number", "12345")),  # digits alone stay a number
        ("1.5", "other", ("number", "1.5")),
        ("zh.ch/ipv2", "contact", ("url", "zh.ch/ipv2")),
    ],
)  # fmt: skip
def test_parse_value_norm(value_norm: str, kind: str, expected: tuple[str, str]) -> None:
    value = parse_value_norm(value_norm, kind)
    assert value is not None and value.key == expected


def v(text: str, lang: str = "de") -> Value:
    value = parse_value_norm(text, "other", lang)
    assert value is not None
    return value


def test_periods_match_by_length_and_working_days_only_themselves() -> None:
    assert matches(v("2 Wochen"), v("14 Tage"))
    assert matches(v("1 Jahr"), v("12 Monate"))
    assert matches(v("30 Tage"), v("30 Tagen"))
    assert matches(v("30 Tage"), v("trente jours", "fr"))
    assert not matches(v("30 Tage"), v("20 Tage"))
    assert not matches(v("5 Arbeitstage"), v("5 Tage"))
    assert not matches(v("1 Monat"), v("30 Tage"))


def test_a_period_and_its_count_match_each_other() -> None:
    assert matches(v("16 Jahre"), v("16"))  # "Kinder unter 16" keeps the fact
    assert matches(v("30"), v("30 Tage"))
    assert not matches(v("16 Jahre"), v("12"))
    assert not matches(Value("amount", "30"), v("30 Tage"))  # a fee is no period


def test_identifiers_match_exactly_without_spaces() -> None:
    assert matches(v("756 1234 5678 97"), v("756.1234.5678.97"))
    assert matches(v("CH9300762011623852957"), v("CH93 0076 2011 6238 5295 7"))
    assert not matches(v("Referenz 2026-0042"), v("Referenz 2026-0024"))
    assert matches(v("Dossier-Nr. 12345"), v("12345"))  # the number without its keyword


def test_addresses_match_on_postcode_and_place_and_on_the_street_the_fact_has() -> None:
    full, short = v("Gerichtsstrasse 12, 8000 Musterwil"), v("8000 Musterwil")
    assert matches(short, full)  # the draft may add the street
    assert not matches(full, short)  # but not drop it
    assert matches(full, v("Gerichts·strasse 12, 8000 Musterwil"))
    assert not matches(full, v("Gerichtsstrasse 14, 8000 Musterwil"))
    assert not matches(short, v("8001 Musterwil"))
    assert matches(v("Postfach, 8000 Musterwil"), v("Postfach 1234, 8000 Musterwil"))
    assert not matches(v("Postfach 1234, 8000 Musterwil"), v("Postfach, 8000 Musterwil"))


def test_hard_values_count_the_new_kinds() -> None:
    text = "Referenz 2026-0042: innert 30 Tagen an Gerichtsstrasse 12, 8000 Musterwil"
    assert hard_values(text) == {
        ("identifier", "2026-0042"),
        ("period", "30d"),
        ("address", "Gerichtsstrasse 12||8000 Musterwil"),
    }


def test_formatting() -> None:
    assert format_period("30d") == "30 Tage"
    assert format_period("1y") == "1 Jahr"
    assert format_period("2w") == "2 Wochen"
    assert format_period("5wd", "fr") == "5 jours ouvrables"
    assert format_period("1m", "it") == "1 mese"
    assert format_identifier("CH9300762011623852957") == "CH93 0076 2011 6238 5295 7"
    assert format_identifier("2026-0042") == "2026-0042"
    assert format_address("Gerichtsstrasse 12|Postfach|8000 Musterwil") == (
        "Gerichtsstrasse 12, Postfach, 8000 Musterwil"
    )
    assert format_address("||8000 Musterwil") == "8000 Musterwil"


# -- the fact rules and the code completion on a decision ----------------------------

SOURCE = SourceDocument(
    id="decision",
    lang="de",
    title="Entscheid",
    source=SourceInfo(type="text"),
    segments=[
        Segment(id="s0001", kind="heading", text="Entscheid der KESB Musterwil", heading_level=1),
        Segment(id="s0002", kind="paragraph", para=1,
                text="Geschäftsnummer 2026-0042, AHV-Nummer 756.1234.5678.97."),
        Segment(id="s0003", kind="paragraph", para=2,
                text="Die KESB errichtet für die betroffene Person eine Beistandschaft."),
        Segment(id="s0004", kind="paragraph", para=3,
                text="Gegen diesen Entscheid kann innert 30 Tagen seit Zustellung Beschwerde "
                "erhoben werden."),
        Segment(id="s0005", kind="paragraph", para=3,
                text="Die Beschwerde ist zu richten an: Bezirksgericht Musterwil, "
                "Gerichtsstrasse 12, 8000 Musterwil."),
        Segment(id="s0006", kind="paragraph", para=4,
                text="Die Beistandschaft wird nach 2 Jahren überprüft."),
    ],
)  # fmt: skip
MODEL_FACTS = FactSheet(
    doc_id="decision",
    facts=[
        Fact(id="f01", kind="other", text="Es gibt eine Beistandschaft.", segment_ids=["s0003"])
    ],
)
FACTS = complete_factsheet(MODEL_FACTS, SOURCE)


def test_code_completion_adds_the_new_kinds_as_must_keep_facts() -> None:
    added = {f.value_norm: f for f in FACTS.facts if f.origin == "code"}
    assert set(added) == {
        "2026-0042",
        "756.1234.5678.97",
        "30 Tage",
        "Gerichtsstrasse 12, 8000 Musterwil",
        "2 Jahre",
    }
    assert added["30 Tage"].kind == "deadline"  # "innert" marks the deadline
    assert added["2 Jahre"].kind == "other"
    assert added["Gerichtsstrasse 12, 8000 Musterwil"].kind == "contact"
    assert added["2026-0042"].kind == "other"
    assert all(f.must_keep for f in added.values())
    assert [f.id for f in FACTS.facts] == ["f01", "f02", "f03", "f04", "f05", "f06"]


# The easy-language sentences and the source sentence each one rests on; extra
# sentences of a test cite the appeal instructions.
GOOD = (
    ("Die KESB gibt Ihnen einen Beistand.", "s0003"),
    ("Ihre Nummer bei der KESB: Geschäfts·nummer 2026-0042.", "s0002"),
    ("Ihre AHV-Nummer ist 756.1234.5678.97.", "s0002"),
    ("Sie haben 30 Tage Zeit für eine Beschwerde.", "s0004"),
    ("Schreiben Sie an: Bezirksgericht Musterwil, Gerichts·strasse 12, 8000 Musterwil.", "s0005"),
    ("Nach 24 Monaten prüft die KESB den Beistand.", "s0006"),
)


def draft(*items: tuple[str, str] | str) -> Draft:
    blocks = [
        Block(
            id=f"b{i:03d}",
            kind="sentence",
            text=item if isinstance(item, str) else item[0],
            segment_ids=["s0004"] if isinstance(item, str) else [item[1]],
        )
        for i, item in enumerate(items, 1)
    ]
    blocks[0] = blocks[0].model_copy(update={"fact_ids": ["f01"]})
    return link_facts(Draft(doc_id="decision", lang="de", level="A2", blocks=blocks), FACTS)


def fact_rule_ids(d: Draft) -> list[str]:
    findings = check_draft(d, source=SOURCE, factsheet=FACTS).findings
    return [f.rule_id for f in findings if f.rule_id.startswith("FACT")]


def test_a_draft_that_keeps_every_value_in_another_form_passes() -> None:
    d = draft(*GOOD)
    assert fact_rule_ids(d) == []
    assert check_draft(d, source=SOURCE, factsheet=FACTS).metrics.fact_coverage == 1.0
    by_block = {b.id: b.fact_ids for b in d.blocks}
    assert by_block["b004"] == ["f04"] and by_block["b005"] == ["f05"]  # linked by value


ADDRESS = "Gerichtsstrasse 12, 8000 Musterwil"


@pytest.mark.parametrize(
    ("index", "text", "expected"),
    [
        (3, "Sie haben 20 Tage Zeit für eine Beschwerde.", "30 Tage"),
        (3, "Sie haben einen Monat Zeit für eine Beschwerde.", "30 Tage"),
        (2, "Ihre AHV-Nummer steht im Entscheid.", "756.1234.5678.97"),
        (1, "Ihre Nummer bei der KESB: Geschäfts·nummer 2026-0024.", "2026-0042"),
        (4, "Schreiben Sie an das Bezirksgericht, 8000 Musterwil.", ADDRESS),
    ],
)
def test_a_changed_or_dropped_value_is_a_fact_01_error_with_the_exact_string(
    index: int, text: str, expected: str
) -> None:
    items = list(GOOD)
    items[index] = (text, GOOD[index][1])
    findings = [
        f
        for f in check_draft(draft(*items), source=SOURCE, factsheet=FACTS).findings
        if f.rule_id == "FACT-01"
    ]
    assert len(findings) == 1
    assert findings[0].severity == "error" and findings[0].suggestion == expected
    assert expected in findings[0].message


def test_an_invented_period_number_or_address_is_a_fact_06_error() -> None:
    d = draft(
        *GOOD,
        "Sie haben 10 Tage Zeit für Fragen.",
        "Ihre Referenz ist 2026-0024.",
        "Oder an: Bahnhofstrasse 1, 8001 Zürich.",
    )
    findings = {
        f.message_key: f
        for f in check_draft(d, source=SOURCE, factsheet=FACTS).findings
        if f.rule_id == "FACT-06"
    }
    assert set(findings) == {"FACT-06.period", "FACT-06.identifier", "FACT-06.address"}
    assert all(f.severity == "error" for f in findings.values())
    assert findings["FACT-06.period"].evidence == "10 Tage"
    assert findings["FACT-06.period"].suggestion is None  # never the only period
    assert findings["FACT-06.identifier"].suggestion is None  # the source has two
    assert findings["FACT-06.address"].suggestion == ADDRESS
    assert "Bahnhofstrasse 1, 8001 Zürich" in findings["FACT-06.address"].message


def test_the_sample_letter_carries_its_periods_once() -> None:
    letter = (
        "Änderungen sind innert 30 Tagen schriftlich zu melden. Gegen die Verfügung kann "
        "innert 30 Tagen seit Zustellung Einsprache erhoben werden."
    )
    assert hard_values(letter) == {("period", "30d")}


# -- quantities and dosing schemes (patient letters) ---------------------------------


@pytest.mark.parametrize(
    ("lang", "text", "expected"),
    [
        ("de", "Nehmen Sie 2,5 mg am Morgen.", ("quantity", "2.5 mg")),
        ("de", "2.5 Milligramm", ("quantity", "2.5 mg")),
        ("de", "1 Tablette", ("quantity", "1 Tablette")),
        ("de", "2 Tabletten", ("quantity", "2 Tablette")),
        ("de", "1½ Tabletten", ("quantity", "1.5 Tablette")),
        ("de", "½ Tablette", ("quantity", "0.5 Tablette")),
        ("de", "20 Tropfen", ("quantity", "20 Tropfen")),
        ("de", "2 Hübe", ("quantity", "2 Hub")),
        ("de", "über 38,5 Grad", ("quantity", "38.5 °C")),
        ("de", "38.5 °C", ("quantity", "38.5 °C")),
        ("de", "500 mg/dl", ("quantity", "500 mg/dl")),
        ("de", "1000 IE", ("quantity", "1000 IE")),
        ("de", "9 Liter Wasser", ("quantity", "9 l")),
        ("de", "Morgens 1-0-1.", ("schedule", "1-0-1")),
        ("de", "1-0-0-1", ("schedule", "1-0-0-1")),
        ("de", "½-0-½", ("schedule", "0.5-0-0.5")),
        ("de", "1,5-0-1", ("schedule", "1.5-0-1")),
        ("de", "1 - 0 - 1", ("schedule", "1-0-1")),
        ("fr", "2 comprimés", ("quantity", "2 Tablette")),
        ("fr", "5 gouttes", ("quantity", "5 Tropfen")),
        ("fr", "2,5 mg", ("quantity", "2.5 mg")),
        ("it", "2 compresse", ("quantity", "2 Tablette")),
        ("it", "10 gocce", ("quantity", "10 Tropfen")),
    ],
)
def test_quantities_and_schedules(lang: str, text: str, expected: tuple[str, str]) -> None:
    assert expected in keys(text, lang)


@pytest.mark.parametrize(
    ("text", "absent"),
    [
        ("Art. 5 gilt", "quantity"),
        ("2 ganze Tage", "quantity"),
        ("am 3. Grad", "quantity"),
        ("50 Prozent", "quantity"),
        ("CHF 500", "quantity"),
        ("Seite 3-5", "schedule"),
        ("8-12 Uhr", "schedule"),
        ("Tel. 044 123 45 67", "schedule"),
        ("Konto 80-151-4", "schedule"),
        ("31-12-2026", "schedule"),
    ],
)
def test_what_is_not_a_quantity_or_a_schedule(text: str, absent: str) -> None:
    assert absent not in {kind for kind, _ in keys(text)}


def test_quantities_match_by_number_and_symbol() -> None:
    assert matches(v("2,5 mg"), v("2.5 Milligramm"))
    assert not matches(v("2.5 mg"), v("2.5 g"))
    assert not matches(v("2 Tabletten"), v("3 Tabletten"))
    assert matches(v("2"), v("2 Tabletten"))  # a fact "2" written with its unit
    assert not matches(v("2 Tabletten"), v("2"))  # the unit dropped is a loss
    assert matches(v("1-0-1"), v("1 - 0 - 1"))
    assert matches(v("½-0-½"), v("0.5-0-0.5"))
    assert not matches(v("1-0-1"), v("1-0-0-1"))


def test_parse_quantity_and_schedule_value_norms() -> None:
    assert parse_value_norm("2,5 mg", "other").key == ("quantity", "2.5 mg")
    assert parse_value_norm("1-0-1", "other").key == ("schedule", "1-0-1")
    assert parse_value_norm("2 Tabletten", "obligation").key == ("quantity", "2 Tablette")


def test_an_invented_dose_or_scheme_is_a_fact_06_error() -> None:
    source = SourceDocument(
        id="patient",
        lang="de",
        source=SourceInfo(type="text"),
        segments=[
            Segment(id="s0001", kind="paragraph", para=1,
                    text="Nehmen Sie 2,5 mg Bisoprolol morgens, Schema 1-0-0, für 3 Monate."),
        ],
    )  # fmt: skip
    facts = complete_factsheet(FactSheet(doc_id="patient", facts=[]), source)
    assert {f.value_norm for f in facts.facts} == {"2.5 mg", "1-0-0", "3 Monate"}
    d = Draft(doc_id="patient", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Nehmen Sie 5 mg am Morgen, Schema 1-0-1.",
              segment_ids=["s0001"]),
    ])  # fmt: skip
    found = {
        f.message_key for f in check_draft(d, source=source, factsheet=facts).findings
        if f.rule_id == "FACT-06"
    }  # fmt: skip
    assert found == {"FACT-06.quantity", "FACT-06.schedule"}
