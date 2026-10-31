from __future__ import annotations

import pytest

from leichtfacile.rules.values import (
    Value,
    extract_values,
    find_value,
    format_date,
    format_phone,
    format_thousands,
    hard_values,
    matches,
    parse_value_norm,
)


def kinds(text: str) -> list[tuple[str, str]]:
    return [(v.kind, v.canonical) for v in extract_values(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Die Frist endet am 31. März 2026.", ("date", "2026-03-31")),
        ("bis 31.03.2026", ("date", "2026-03-31")),
        ("bis 31.3.26", ("date", "2026-03-31")),
        ("am 2026-03-31", ("date", "2026-03-31")),
        ("bis 31.3.", ("date", "--03-31")),
        ("bis 31. Jan. 2026", ("date", "2026-01-31")),
        ("le 1er mars 2026", ("date", "2026-03-01")),
        ("entro il 15 luglio 2026", ("date", "2026-07-15")),
        ("CHF 20.-", ("amount", "20")),
        ("Fr. 1'500.00", ("amount", "1500")),
        ("1\u2019500 Franken", ("amount", "1500")),
        ("1 500 Franken", ("amount", "1500")),
        ("1.50 Franken", ("amount", "1.5")),
        ("044 123 45 67", ("phone", "0441234567")),
        ("+41 44 123 45 67", ("phone", "0441234567")),
        ("0041 44 123 45 67", ("phone", "0441234567")),
        ("044/123 45 67", ("phone", "0441234567")),
        ("0800 123 456", ("phone", "0800123456")),
        ("Opfer·hilfe 0800 33 66 55", ("phone", "0800336655")),
        ("Eltern·notruf 0848 35 45 55", ("phone", "0848354555")),
        ("Tel. 0900 55 35 55 (Fr. 2.-)", ("phone", "0900553555")),
        ("0800336655", ("phone", "0800336655")),
        ("info@zh.ch", ("email", "info@zh.ch")),
        ("https://www.zh.ch/ipv.", ("url", "zh.ch/ipv")),
        ("priminfo.ch", ("url", "priminfo.ch")),
        ("10 %", ("percent", "10")),
        ("10 Prozent", ("percent", "10")),
        ("um 9.00 Uhr", ("time", "09:00")),
        ("um 13:30", ("time", "13:30")),
        ("9 Uhr", ("time", "09:00")),
    ],
)
def test_extract_values(text: str, expected: tuple[str, str]) -> None:
    assert expected in kinds(text)


def test_values_do_not_overlap() -> None:
    found = kinds("Rufen Sie 044 123 45 67 an. Frist: 31.03.2026. Kosten: CHF 1'500.-")
    assert found == [("phone", "0441234567"), ("date", "2026-03-31"), ("amount", "1500")]


def test_a_hotline_is_one_phone_number_not_four_plain_numbers() -> None:
    # The emergency pages write the free and shared-cost numbers in pairs; before 8
    # October 2026 these came out as 0848, 35, 45 and 55, so no fact rule saw them.
    found = kinds("Eltern·notruf: 0848 35 45 55, Tag und Nacht. Opfer·hilfe: 0800 33 66 55.")
    assert found == [("phone", "0848354555"), ("phone", "0800336655")]
    assert hard_values("Rufen Sie 0848 354 555 an.") == {("phone", "0848354555")}


def test_url_drops_sentence_dot() -> None:
    (value,) = [v for v in extract_values("Mehr auf www.zh.ch/ipv.") if v.kind == "url"]
    assert value.text == "www.zh.ch/ipv"


@pytest.mark.parametrize(
    ("value_norm", "kind", "expected"),
    [
        ("2026-03-31", "deadline", ("date", "2026-03-31")),
        ("--03-31", "deadline", ("date", "--03-31")),
        ("09:00", "other", ("time", "09:00")),
        ("0441234567", "contact", ("phone", "0441234567")),
        ("+41 44 123 45 67", "contact", ("phone", "0441234567")),
        ("CHF 1500.00", "amount", ("amount", "1500")),
        ("1500", "amount", ("amount", "1500")),
        ("31. März 2026", "deadline", ("date", "2026-03-31")),
        ("10%", "condition", ("percent", "10")),
        ("info@zh.ch", "contact", ("email", "info@zh.ch")),
    ],
)
def test_parse_value_norm(value_norm: str, kind: str, expected: tuple[str, str]) -> None:
    value = parse_value_norm(value_norm, kind)
    assert value is not None and value.key == expected


@pytest.mark.parametrize("value_norm", [None, "", "  ", "Sie müssen das Formular schicken"])
def test_unparseable_value_norm(value_norm: str | None) -> None:
    assert parse_value_norm(value_norm, "obligation") is None


def test_date_without_year_matches() -> None:
    target = parse_value_norm("2026-03-31", "deadline")
    assert find_value(target, "Schicken Sie den Brief bis 31. März.")
    assert not find_value(target, "Schicken Sie den Brief bis 30. März.")
    assert not find_value(target, "Schicken Sie den Brief bis 31. März 2025.")


def test_amount_and_number_match_each_other() -> None:
    assert matches(Value("amount", "1500"), Value("number", "1500"))
    assert not matches(Value("amount", "1500"), Value("amount", "150"))


def test_hard_values_skip_plain_numbers() -> None:
    keys = hard_values("2 Kinder, Artikel 5, Frist 31.3.2026, CHF 20, Tel. 044 123 45 67")
    assert keys == {("date", "2026-03-31"), ("amount", "20"), ("phone", "0441234567")}


def test_formatting() -> None:
    assert format_date("2026-03-31") == "31. März 2026"
    assert format_date("--03-01", "fr") == "1er mars"
    assert format_date("2026-07-15", "it") == "15 luglio 2026"
    assert format_thousands("1500") == "1'500"
    assert format_thousands("500000") == "500'000"
    assert format_thousands("1500", "fr") == "1 500"
    assert format_phone("0441234567") == "044 123 45 67"
    assert format_phone("0800123456") == "0800 123 456"
    # Regional codes starting with 08 or 09 are no service numbers (Graubünden, Ticino).
    assert format_phone("0812345678") == "081 234 56 78"
    assert format_phone("0912345678") == "091 234 56 78"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("vom 7. bis 11. Juni 2027", [("date", "2027-06-07"), ("date", "2027-06-11")]),
        ("7.-11. Juni", [("date", "--06-07"), ("date", "--06-11")]),
        ("am 15. und 16. März", [("date", "--03-15"), ("date", "--03-16")]),
        ("du 7 au 11 juin 2027", [("date", "2027-06-07"), ("date", "2027-06-11")]),
        ("les 1er et 2 juin", [("date", "--06-01"), ("date", "--06-02")]),
        ("dal 7 all'11 giugno 2027", [("date", "2027-06-07"), ("date", "2027-06-11")]),
        ("dal 7 al 11 giugno", [("date", "--06-07"), ("date", "--06-11")]),
    ],
)
def test_a_range_of_days_in_one_month_gives_both_dates(text: str, expected) -> None:
    assert kinds(text) == expected
    first = parse_value_norm("2027-06-07", "deadline")
    if expected[0][1].endswith("06-07"):
        assert find_value(first, text)  # FACT-01 finds the first day of the range


@pytest.mark.parametrize(
    "text", ["von 8 bis 11 Uhr", "2 bis 3 Wochen", "Kinder von 6 bis 12 Jahren", "Art. 5 und 7"]
)
def test_a_range_without_a_month_is_no_date(text: str) -> None:
    assert not [v for v in extract_values(text) if v.kind == "date"]
