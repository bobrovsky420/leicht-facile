from __future__ import annotations

import pytest

from leichtfacile.rules.lexicon import (
    is_common_compound,
    lowercase_after_mediopunkt,
    mediopunkt_suggestion,
    with_mediopunkt,
)


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
        # The words of job 287fea3aadd2 (CSCS, 6 October 2026), docs/rules.md LEX-01
        ("Krankenversicherungspolice", "Kranken·versicherungs·police"),
        ("Sozialversicherungsstelle", "Sozial·versicherungs·stelle"),
        ("Antragsformular", "Antrags·formular"),
        ("Steuerveranlagung", "Steuer·veranlagung"),
        ("Alleinstehende", "Allein·stehende"),
        ("Einkommensgrenze", "Einkommens·grenze"),
        ("Ostermundigenstrasse", "Ostermundigen·strasse"),  # not Ostermundi·gens·trasse
        ("Familiennamensänderung", "Familien·namens·änderung"),
        # -innen is an ending: the stem is split, never the ending (CSCS dev drafts)
        ("Sozialarbeiterinnen", "Sozial·arbeiterinnen"),
        ("Dachrinnen", "Dach·rinnen"),  # no feminine stem: rinnen is the head
    ],
)
def test_compound_split(word: str, expected: str) -> None:
    assert with_mediopunkt(word, 13) == expected


@pytest.mark.parametrize(
    "word",
    [
        "Verantwortlichkeiten",
        "Informationen",
        "Schweizerische",
        "Sistierung",
        "Organisationen",
        "Schweizerinnen",  # not Schweizer·innen or Schweize·rinnen
        "Assistentinnen",
    ],
)
def test_derived_words_are_not_split(word: str) -> None:
    assert with_mediopunkt(word, 13) is None


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("Krankenversicherungspolice", "Kranken·versicherungs·police"),
        ("Prämien·verbilligungsgesuch", "Prämien·verbilligungs·gesuch"),  # a part stays
        ("Kranken·kasse", None),  # no part too long
        ("Organisationen", None),  # too long, no compound
        ("Gesuch", None),
        ("E-Mail-Krankenversicherung", "E-Mail-Kranken·versicherung"),  # hyphens stay
        ("Gemeindeschreiberinnen", "Gemeinde·schreiberinnen"),  # the ending stays on
        ("Steuerberaterinnen", None),  # long only by its ending: no wrong joint
    ],
)
def test_mediopunkt_suggestion(word: str, expected: str | None) -> None:
    assert mediopunkt_suggestion(word, 13) == expected
    if expected:
        assert mediopunkt_suggestion(expected, 13) is None  # a second run changes nothing


def test_lowercase_after_mediopunkt() -> None:
    assert lowercase_after_mediopunkt("Prämien·Verbilligung") == "Prämien·verbilligung"
    assert lowercase_after_mediopunkt("Kranken·Kassen·Karte") == "Kranken·kassen·karte"
    assert lowercase_after_mediopunkt("Prämien·verbilligung") is None
    assert lowercase_after_mediopunkt("Prämienverbilligung") is None


def test_common_compound() -> None:
    assert is_common_compound("Krankenkasse")
    assert not is_common_compound("Sistierung")
