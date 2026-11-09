"""The value grammar (rules/value_grammar.py, rules/data/values_<lang>.toml): a text is
read with its own language's words; and the value index (rules/value_index.py): the
values of a source and a draft extracted once, with the parts that hold them."""

from __future__ import annotations

import pytest

from leichtfacile.rules.value_grammar import PERIOD_UNITS, grammar_for, languages
from leichtfacile.rules.value_index import ValueIndex
from leichtfacile.rules.values import (
    Value,
    extract_values,
    format_date,
    format_thousands,
    number_word,
    parse_value_norm,
)
from leichtfacile.schemas import Block, Segment, SourceDocument, SourceInfo


def keys(text: str, lang: str = "de") -> list[tuple[str, str]]:
    return [(v.kind, v.canonical) for v in extract_values(text, lang)]


def test_every_language_has_a_grammar_with_the_period_units_and_the_months() -> None:
    assert languages() == ("de", "fr", "it")
    for lang in languages():
        g = grammar_for(lang)
        assert set(g.period_names) == set(PERIOD_UNITS)
        assert all(g.period_units[unit] for unit in PERIOD_UNITS)
        assert len(g.month_names) == 12 and set(g.months.values()) == set(range(1, 13))
    assert grammar_for("en").key == "de-CH"  # a language without a grammar reads as German


def test_a_variety_replaces_keys_and_keeps_the_rest() -> None:
    de, at, germany = grammar_for("de"), grammar_for("de-AT"), grammar_for("de-DE")
    assert at.month_names[0] == "Jänner" and de.month_names[0] == "Januar"
    assert at.months == de.months  # Jänner is read in every German variety
    assert germany.dot_decimals and germany.german_phones and germany.five_digit_postcodes
    assert not de.dot_decimals and not de.german_phones and not de.five_digit_postcodes
    assert (de.writes_thousands, germany.writes_thousands, grammar_for("fr").writes_thousands) == (
        "'",
        ".",
        " ",
    )
    assert format_thousands("1500.5", "de-DE") == "1.500,5" and format_date("--01-04", "de-AT") == (
        "4. Jänner"
    )
    assert keys("Bahnhofstr. 3, 8001 Zürich") == [("address", "Bahnhofstrasse 3||8001 Zürich")]
    assert keys("Bahnhofstr. 3, 10115 Berlin", "de-DE") == [
        ("address", "Bahnhofstraße 3||10115 Berlin")
    ]


@pytest.mark.parametrize(
    ("text", "lang", "absent", "present"),
    [
        # A French month is no month in a German text (Mars is a planet there).
        ("le 15 mars 2026", "de", "date", None),
        ("le 15 mars 2026", "fr", None, ("date", "2026-03-15")),
        ("il 15 luglio 2026", "de", "date", None),
        ("il 15 luglio 2026", "it", None, ("date", "2026-07-15")),
        # `2 h` is a duration in German and Italian, a time in French.
        ("Die Fahrt dauert 2 h.", "de", "time", None),
        ("Il viaggio dura 2 h.", "it", "time", None),
        ("ouvert de 9 h 30", "fr", None, ("time", "09:30")),
        ("ouvert dès 9h", "fr", None, ("time", "09:00")),
        # The clock word and the Italian time words are each language's own.
        ("um 9 Uhr", "fr", "time", None),
        ("alle ore 9", "de", "time", None),
        ("alle ore 9", "it", None, ("time", "09:00")),
        # Percent, currency and multiplier words likewise.
        ("10 pour cent", "fr", None, ("percent", "10")),
        ("10 per cento", "it", None, ("percent", "10")),
        ("2 millions de francs", "fr", None, ("amount", "2000000")),
        ("2 milioni di franchi", "it", None, ("amount", "2000000")),
        ("20 Millionen Franken", "de", None, ("amount", "20000000")),
        ("70 Rappen", "de", None, ("amount", "0.7")),
        ("70 centimes", "fr", None, ("amount", "0.7")),
    ],
)
def test_a_text_is_read_with_its_own_languages_words(text, lang, absent, present) -> None:
    found = keys(text, lang)
    if absent:
        assert not [k for k in found if k[0] == absent], found
    if present:
        assert present in found, found


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("entro ventuno giorni", ("period", "21d")),
        ("entro trentatré giorni", ("period", "33d")),
        ("nei prossimi dodici mesi", ("period", "12m")),
        ("per duecento giorni", ("period", "200d")),
    ],
)
def test_italian_number_words_in_compounds_count_as_periods(text, expected) -> None:
    """Before the grammar the German and French compounds were periods and the Italian
    ones nothing (`entro ventuno giorni` gave no value; audit of 6 November 2026)."""
    assert expected in keys(text, "it")


def test_number_words_follow_each_languages_way_of_compounding() -> None:
    assert number_word("einundzwanzig", "de") == 21 and number_word("dreissig", "de") == 30
    assert number_word("vingt-cinq", "fr") == 25 and number_word("quatre-vingt-onze", "fr") == 91
    assert number_word("vingt et un", "fr") == 21
    assert number_word("ventuno", "it") == 21 and number_word("trentotto", "it") == 38
    assert number_word("duecento", "it") == 200 and number_word("duemila", "it") == 2000
    assert number_word("mille", "it") == 1000 and number_word("Tag", "de") is None
    assert number_word("ventuno", "de") is None  # an Italian word is no German number


def _source() -> SourceDocument:
    segments = [
        Segment(id="s0001", kind="heading", text="Frist", para=1, heading_level=1),
        Segment(id="s0002", kind="paragraph", text="Schicken Sie es bis 31. März 2026.", para=2),
        Segment(id="s0003", kind="paragraph", text="Gerichtsstrasse 12", para=3),
        Segment(id="s0004", kind="paragraph", text="8000 Musterwil", para=3),
        Segment(id="s0005", kind="paragraph", text="Sie nehmen Dafalgan 500 mg.", para=4),
    ]  # fmt: skip
    return SourceDocument(
        id="d", lang="de", title="Brief vom 2. Februar 2026", source=SourceInfo(type="text"),
        segments=segments,
    )  # fmt: skip


def test_the_source_index_traces_every_value_to_the_segments_it_spans() -> None:
    index = ValueIndex.of_source(_source())
    by_value = {v.canonical: held for v, held in zip(index.values, index.holders, strict=True)}
    assert by_value["2026-02-02"] == ()  # the title's value belongs to no segment
    assert by_value["2026-03-31"] == ("s0002",)
    # The address over two sentences is one value, held by both.
    assert by_value["Gerichtsstrasse 12||8000 Musterwil"] == ("s0003", "s0004")
    assert [v.canonical for v in index.of_part("s0003")] == ["Gerichtsstrasse 12||8000 Musterwil"]
    assert {v.kind for v in index.hard()} == {"date", "address", "quantity"}

    deadline = parse_value_norm("2026-03-31", "deadline")
    assert index.contains(deadline) and index.holders_of(deadline) == ["s0002"]
    assert index.part_contains(deadline, "s0002") and not index.part_contains(deadline, "s0003")
    assert not index.contains(parse_value_norm("2026-04-30", "deadline"))
    medication = parse_value_norm("Dafalgan 500 mg", "medication")
    assert index.contains(medication) and index.holders_of(medication) == ["s0005"]
    assert index.part_contains(medication, "s0005") and not index.part_contains(medication, "s0002")


def test_the_block_index_reads_each_block_alone_as_the_rules_do() -> None:
    blocks = [
        Block(id="b001", kind="heading", text="Was müssen Sie tun?"),
        Block(id="b002", kind="sentence", text="Schicken Sie das Gesuch bis 31. März 2026."),
        Block(id="b003", kind="sentence", text="Das kostet 20 Franken."),
    ]
    index = ValueIndex.of_blocks(blocks, "de")
    assert index.of_part("b001") == []
    assert index.of_part("b002") == extract_values(blocks[1].text, "de")
    assert [v.canonical for v in index.of_part("b003")] == ["20"]
    assert index.holders == (("b002",), ("b003",))
    amount = Value("amount", "20")
    assert index.holders_of(amount) == ["b003"] and index.contains(amount)
    assert index.text == "\n".join(b.text for b in blocks)
