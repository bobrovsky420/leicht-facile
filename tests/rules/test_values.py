from __future__ import annotations

import pytest

from leichtfacile.rules.values import (
    Value,
    extract_values,
    find_value,
    format_date,
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
