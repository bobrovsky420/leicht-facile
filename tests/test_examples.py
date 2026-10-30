"""Example sources and their job settings (data/examples/README.md)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from leichtfacile.config import LETTERS_DIR
from leichtfacile.examples import example_config, example_sources
from leichtfacile.rules.vocabulary import standard_spelling
from leichtfacile.schemas import JobConfig

EXAMPLES = LETTERS_DIR
# The French and Italian letters are Swiss, and offered by every installation.
SWISS_EVERYWHERE = {
    "reduction-primes-lettre",
    "riduzione-premi-lettera",
    "camp-de-classe-lettre-parents",
    "settimana-verde-lettera-genitori",
    "semaine-de-stage-lettre-eleves",
    "settimana-di-stage-lettera-allievi",
}
# The school letters (30 October 2026): a camp letter to parents and a letter about the
# trial-apprenticeship week to students, each in German, French and Italian.
SCHOOL_LETTERS = {
    "klassenlager-elternbrief": ("de", "parents"),
    "camp-de-classe-lettre-parents": ("fr", "parents"),
    "settimana-verde-lettera-genitori": ("it", "parents"),
    "schnupperwoche-schuelerbrief": ("de", "students"),
    "semaine-de-stage-lettre-eleves": ("fr", "students"),
    "settimana-di-stage-lettera-allievi": ("it", "students"),
}
# How each language addresses the reader: parents formally, students in the du form.
FORMAL = {"de": r"\bSie\b", "fr": r"\bvous\b", "it": r"\b[Vv]i\b"}
INFORMAL = {"de": r"\bdu\b", "fr": r"\btu\b", "it": r"\b[Tt]i\b"}


def test_a_source_without_a_settings_file_has_none(tmp_path: Path) -> None:
    (tmp_path / "brief.txt").write_text("Text", encoding="utf-8")
    assert example_config(tmp_path / "brief.txt") == {}


def test_the_settings_file_next_to_a_source_sets_the_job(tmp_path: Path) -> None:
    (tmp_path / "entscheid.txt").write_text("Text", encoding="utf-8")
    settings = {"mode": "decision", "addressee": "Lea Muster"}
    (tmp_path / "entscheid.json").write_text(json.dumps(settings), encoding="utf-8")
    assert example_config(tmp_path / "entscheid.txt") == settings


def test_a_settings_file_with_other_keys_is_refused(tmp_path: Path) -> None:
    (tmp_path / "entscheid.txt").write_text("Text", encoding="utf-8")
    (tmp_path / "entscheid.json").write_text('{"modus": "decision"}', encoding="utf-8")
    with pytest.raises(ValueError, match="modus"):
        example_config(tmp_path / "entscheid.txt")


def test_the_settings_files_are_no_example_texts() -> None:
    ids = [e["id"] for e in example_sources(EXAMPLES)]
    assert "entscheid-beistandschaft-musterwil" in ids
    assert len(ids) == len(set(ids))  # the .json next to the .txt is not listed


def test_the_kesb_decision_runs_in_decision_mode() -> None:
    config = JobConfig.model_validate(
        example_config(EXAMPLES / "entscheid-beistandschaft-musterwil.txt")
    )
    assert config.mode == "decision"
    assert config.addressee == "Lea Muster"
    assert config.notice and "Massgebend ist der Entscheid" in config.notice


def test_example_sources_carry_the_decision_settings() -> None:
    by_id = {e["id"]: e for e in example_sources(EXAMPLES)}
    kesb = by_id["entscheid-beistandschaft-musterwil"]
    assert kesb["mode"] == "decision" and kesb["addressee"] == "Lea Muster"
    assert kesb["notice"].endswith("Massgebend ist der Entscheid.")
    assert "mode" not in by_id["praemienverbilligung-brief"]


def test_every_shipped_letter_names_the_region_it_is_written_for() -> None:
    letters = sorted(EXAMPLES.glob("*.txt"))
    assert len(letters) == 12
    for path in letters:
        settings = example_config(path)
        assert settings.get("region") in ("CH", "DE", "AT"), path.name
        JobConfig.model_validate(settings)  # job settings and nothing else


def test_an_installation_offers_the_letters_of_its_region() -> None:
    def offered(region: str | None) -> set[str]:
        return {e["id"] for e in example_sources(EXAMPLES, region)}

    swiss = {
        "entscheid-beistandschaft-musterwil",
        "praemienverbilligung-brief",
        "klassenlager-elternbrief",
        "schnupperwoche-schuelerbrief",
    }
    assert offered("CH") == swiss | SWISS_EVERYWHERE
    assert offered("DE") == {"wohngeld-bescheid"} | SWISS_EVERYWHERE
    assert offered("AT") == {"familienbeihilfe-bescheid"} | SWISS_EVERYWHERE
    assert offered(None) == offered("CH") | offered("DE") | offered("AT")  # no filter
    langs = {e["id"]: e["lang"] for e in example_sources(EXAMPLES)}
    assert langs["wohngeld-bescheid"] == langs["familienbeihilfe-bescheid"] == "de"
    assert (langs["reduction-primes-lettre"], langs["riduzione-premi-lettera"]) == ("fr", "it")


def test_a_letter_that_names_no_region_is_offered_everywhere(tmp_path: Path) -> None:
    text = (
        "Sie haben am 2. September Wohngeld beantragt. Der Antrag ist abgelehnt, weil Ihr "
        "Einkommen zu hoch ist. Sie können innerhalb eines Monats Widerspruch erheben."
    )
    for name in ("brief", "bescheid"):
        (tmp_path / f"{name}.txt").write_text(text, encoding="utf-8")
    (tmp_path / "bescheid.json").write_text('{"region": "DE"}', encoding="utf-8")
    assert [e["id"] for e in example_sources(tmp_path, "CH")] == ["brief"]
    assert [e["id"] for e in example_sources(tmp_path, "DE")] == ["bescheid", "brief"]
    assert [e["id"] for e in example_sources(tmp_path, "AT")] == ["brief"]


def test_the_bescheide_of_germany_and_austria_run_in_decision_mode() -> None:
    german = JobConfig.model_validate(example_config(EXAMPLES / "wohngeld-bescheid.txt"))
    assert (german.mode, german.region, german.addressee) == ("decision", "DE", "Erika Beispiel")
    assert german.notice == (
        "Diese Erklärung hilft Ihnen, den Bescheid zu verstehen. Maßgebend ist der Bescheid."
    )
    austrian = JobConfig.model_validate(example_config(EXAMPLES / "familienbeihilfe-bescheid.txt"))
    assert (austrian.mode, austrian.region) == ("decision", "AT")
    assert austrian.addressee == "Maria Exempel"
    assert austrian.notice is None  # the variety's notice (varieties.toml) fills it


def test_the_bescheide_follow_their_countrys_conventions() -> None:
    wohngeld = (EXAMPLES / "wohngeld-bescheid.txt").read_text(encoding="utf-8")
    beihilfe = (EXAMPLES / "familienbeihilfe-bescheid.txt").read_text(encoding="utf-8")
    for text in (wohngeld, beihilfe):
        assert "ß" in text and standard_spelling(text) == text  # no Swiss ss
        for swiss in ("Franken", "CHF", "innert", "·", "\u2013", "\u2014"):
            assert swiss not in text
    # Germany: the decision before the reasons, the euro with the thousands dot, a
    # five-digit postcode, the Widerspruch within a month of the Bekanntgabe.
    first, reasons = wohngeld.index("1. Auf Ihren Antrag"), wohngeld.index("## Begründung")
    assert first < reasons < wohngeld.index("## Rechtsbehelfsbelehrung")
    assert "1.540,00 Euro" in wohngeld and "12345 Musterstadt" in wohngeld
    assert "innerhalb eines Monats nach Bekanntgabe Widerspruch" in wohngeld
    # Austria: Spruch, Begründung, Rechtsmittelbelehrung; Jänner, € 1.500,-, four digits.
    spruch, reasons = beihilfe.index("## Spruch"), beihilfe.index("## Begründung")
    assert spruch < reasons < beihilfe.index("## Rechtsmittelbelehrung")
    assert "18. Jänner 2027" in beihilfe and "€ 1.500,-" in beihilfe
    assert "9999 Musterhausen" in beihilfe and "Bundesfinanzgericht" in beihilfe
    assert "binnen eines Monats nach Zustellung" in beihilfe


def test_the_school_letters_are_swiss_and_speak_to_parents_or_students() -> None:
    by_id = {e["id"]: e for e in example_sources(EXAMPLES)}
    for name, (lang, readers) in SCHOOL_LETTERS.items():
        letter = by_id[name]
        assert (letter["lang"], letter["region"]) == (lang, "CH"), name
        assert "mode" not in letter  # a standard job, not a decision
        text = letter["text"]
        assert "CHF" in text and "ß" not in text, name
        spoken, other = (FORMAL, INFORMAL) if readers == "parents" else (INFORMAL, FORMAL)
        assert re.search(spoken[lang], text), name
        assert not re.search(other[lang], text), name
