from __future__ import annotations

import pytest

from leichtfacile.rules.lexicon import is_common_compound, with_mediopunkt


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("Prämienverbilligung", "Prämien·verbilligung"),
        ("Ergänzungsleistungen", "Ergänzungs·leistungen"),
        ("Krankenversicherung", "Kranken·versicherung"),
        ("Krankenversicherungsprämie", "Kranken·versicherungs·prämie"),
        ("Wohnsitzbestätigung", "Wohnsitz·bestätigung"),
        ("Steuererklärung", "Steuer·erklärung"),
        ("Sozialversicherungsanstalt", "Sozial·versicherungs·anstalt"),
        ("Bundesverwaltungsgericht", "Bundes·verwaltungs·gericht"),
        ("Fristverlängerungsgesuch", "Frist·verlängerungs·gesuch"),
        ("Aufenthaltsbewilligung", "Aufenthalts·bewilligung"),
    ],
)
def test_compound_split(word: str, expected: str) -> None:
    assert with_mediopunkt(word, 13) == expected


@pytest.mark.parametrize(
    "word", ["Verantwortlichkeiten", "Informationen", "Schweizerische", "Sistierung"]
)
def test_derived_words_are_not_split(word: str) -> None:
    assert with_mediopunkt(word, 13) is None


def test_common_compound() -> None:
    assert is_common_compound("Krankenkasse")
    assert not is_common_compound("Sistierung")
