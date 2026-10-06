from __future__ import annotations

import pytest

from leichtfacile.ingest.normalize import MEDIOPUNKT, join_lines, normalize_text


def test_nfc():
    assert normalize_text("Pra\u0308mie") == "Prämie"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Prämien\u00adverbilligung", "Prämienverbilligung"),  # soft hyphen
        ("Kranken\u200bkasse", "Krankenkasse"),  # zero-width space
        ("\ufeffMerkblatt", "Merkblatt"),  # byte order mark
        ("Wort\u2060verbindung", "Wortverbindung"),  # word joiner
    ],
)
def test_invisible_characters_are_removed(text, expected):
    assert normalize_text(text) == expected


@pytest.mark.parametrize("space", ["\u00a0", "\u202f", "\u2009", "\u2007", "\u3000", "\t"])
def test_special_spaces_become_plain_spaces(space):
    assert normalize_text(f"Fr.{space}60") == "Fr. 60"
    assert normalize_text(f"1{space}500 francs") == "1 500 francs"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("\ufb01nden", "finden"), ("o\ufb00en", "offen"), ("\ufb02iessend", "fliessend")],
)
def test_ligatures_are_expanded(text, expected):
    assert normalize_text(text) == expected


@pytest.mark.parametrize(
    "dot",
    [
        "\u00b7",  # middle dot
        "\u2022",  # bullet
        "\u2219",  # bullet operator
        "\u22c5",  # dot operator
        "\u2027",  # hyphenation point
        "\u0387",  # greek ano teleia
        "\u30fb",  # katakana middle dot
        "\uff65",  # halfwidth katakana middle dot
        "\u2e31",  # word separator middle dot
        "\uf0b7",  # Symbol-font bullet from PDFs
    ],
)
def test_dot_between_letters_becomes_mediopunkt(dot):
    assert normalize_text(f"Merk{dot}blatt und Ergänzungs{dot}leistungen") == (
        f"Merk{MEDIOPUNKT}blatt und Ergänzungs{MEDIOPUNKT}leistungen"
    )


def test_dots_that_are_not_between_letters_stay():
    assert normalize_text("\u2022 Erster Punkt") == "\u2022 Erster Punkt"
    assert normalize_text("5 \u22c5 3") == "5 \u22c5 3"


@pytest.mark.parametrize("mark", ["\u2019", "\u02bc"])
def test_typographic_apostrophe_in_numbers(mark):
    assert normalize_text(f"Fr. 1{mark}500.-") == "Fr. 1'500.-"
    assert normalize_text(f"l{mark}art. 5") == f"l{mark}art. 5"  # only between digits


def test_non_breaking_hyphen_becomes_hyphen():
    assert normalize_text("E\u2011Mail") == "E-Mail"


def test_dashes_are_not_touched():
    assert normalize_text("Fr. 60.\u2013 bis 8.00\u201312.00 Uhr") == (
        "Fr. 60.\u2013 bis 8.00\u201312.00 Uhr"
    )


def test_whitespace_runs_collapse_but_line_breaks_stay():
    assert normalize_text("  Die  Frist \t endet.  ") == "Die Frist endet."
    assert normalize_text("Satz eins. \n  Satz zwei.") == "Satz eins.\nSatz zwei."
    assert normalize_text("Absatz eins.\n\n\n\nAbsatz zwei.") == "Absatz eins.\n\nAbsatz zwei."
    assert normalize_text("Zeile\r\nZeile\rZeile") == "Zeile\nZeile\nZeile"
    assert normalize_text("A\u2028B\u2029C") == "A\nB\n\nC"


def test_control_characters_are_removed():
    assert normalize_text("Frist\x00 \x07endet\x9c.") == "Frist endet."


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (["Sie bekommen eine Prämien-", "verbilligung."], "Sie bekommen eine Prämienverbilligung."),
        (["Schreiben Sie eine E-", "Mail."], "Schreiben Sie eine E-Mail."),
        (["Die Kranken-", "Kasse zahlt."], "Die Kranken-Kasse zahlt."),
        (["Kranken-", "und Unfallversicherung"], "Kranken- und Unfallversicherung"),
        (
            ["Haftpflicht-", "oder Invaliditätsversicherung"],
            "Haftpflicht- oder Invaliditätsversicherung",
        ),
        (["Prämien\u00ad", "verbilligung"], "Prämienverbilligung"),
        (["Die Gebühr beträgt Fr. 60.-", "pro Jahr."], "Die Gebühr beträgt Fr. 60.- pro Jahr."),
        (["Gültig 2025-", "2026."], "Gültig 2025-2026."),
        (["Das gilt -", "aber nur heute."], "Das gilt - aber nur heute."),
        (["Erste Zeile", "", "  zweite Zeile  "], "Erste Zeile zweite Zeile"),
        ([], ""),
    ],
)
def test_join_lines(lines, expected):
    assert join_lines(lines) == expected
