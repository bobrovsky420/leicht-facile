"""Patient letters: the value kind `medication` (rules/values.py) and FACT-09, a
medication in one block with its dose, scheme and duration (rules/medication.py)."""

from __future__ import annotations

import pytest

from leichtfacile.pipeline.models import FactOut
from leichtfacile.pipeline.orchestrator import repairable
from leichtfacile.pipeline.prompts import level_name, render
from leichtfacile.pipeline.stages import complete_factsheet, mode_context
from leichtfacile.rules import check_draft
from leichtfacile.rules.medication import (
    has_doses,
    medication_names,
    medication_values,
    names_medication,
)
from leichtfacile.rules.mediopunkt import apply_mediopunkt
from leichtfacile.rules.values import find_medication, medication_name, parse_value_norm
from leichtfacile.schemas import (
    Block,
    Draft,
    Fact,
    FactSheet,
    Finding,
    Segment,
    SourceDocument,
    SourceInfo,
)


def source(*texts: str, lang: str = "de") -> SourceDocument:
    return SourceDocument(
        id="patient",
        lang=lang,
        source=SourceInfo(type="text"),
        segments=[
            Segment(id=f"s{i:04d}", kind="paragraph", text=text, para=i)
            for i, text in enumerate(texts, 1)
        ],
    )


def medications(*names: str) -> FactSheet:
    return FactSheet(
        doc_id="patient",
        facts=[
            Fact(id=f"f{i:02d}", kind="medication", text=name, value_norm=name,
                 segment_ids=["s0001"])
            for i, name in enumerate(names, 1)
        ],
    )  # fmt: skip


def draft(*texts: str) -> Draft:
    return Draft(
        doc_id="patient",
        lang="de",
        level="A2",
        blocks=[
            Block(id=f"b{i:03d}", kind="list_item", text=text, segment_ids=["s0001"])
            for i, text in enumerate(texts, 1)
        ],
    )


def findings(result, rule_id: str) -> list:
    return [f for f in result.findings if f.rule_id == rule_id]


# -- the value kind -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value_norm", "name"),
    [
        ("Dafalgan", "Dafalgan"),
        ("Dafalgan 500 mg Tabletten (Paracetamol)", "Dafalgan"),
        ("Co-Amoxi 1 g 1-0-1", "Co-Amoxi"),
        ("Dafalgan 500", "Dafalgan"),
        ("Pantozol 40 mg Filmtabletten", "Pantozol"),
        ("Insulin Lantus 10 IE", "Insulin Lantus"),
        ("Vitamin D3 1000 IE", "Vitamin D3"),
        ("Dafalgan comprimés 1 g", "Dafalgan"),
        ("500 mg", None),
    ],
)
def test_the_name_without_dose_scheme_and_form(value_norm: str, name: str | None) -> None:
    assert medication_name(value_norm) == name


def test_a_medication_fact_parses_as_its_name() -> None:
    value = parse_value_norm("Dafalgan 500 mg", "medication")
    assert value is not None and value.key == ("medication", "dafalgan")
    assert value.text == "Dafalgan"
    assert parse_value_norm("500 mg", "medication") is None
    # The same value under another kind is the dose.
    assert parse_value_norm("Dafalgan 500 mg", "other").key == ("quantity", "500 mg")


def test_a_name_is_found_in_any_case_with_a_mediopunkt_as_a_whole_word() -> None:
    target = parse_value_norm("Pantoprazol", "medication")
    assert [v.text for v in find_medication(target, "Nehmen Sie Panto·prazol. PANTOPRAZOL")] == [
        "Panto·prazol",
        "PANTOPRAZOL",
    ]
    assert find_medication(target, "Pantoprazolum 40 mg") == []
    two_words = parse_value_norm("Insulin Lantus", "medication")
    assert find_medication(two_words, "Spritzen Sie Insulin  Lantus am Abend.")


def test_the_fact_kind_and_its_aliases() -> None:
    assert FactOut(kind="medication", text="Dafalgan").kind == "medication"
    assert FactOut(kind="Medikament", text="Dafalgan").kind == "medication"
    assert FactOut(kind="médicament", text="Dafalgan").kind == "medication"


SOURCE = source(
    "Nehmen Sie Dafalgan 500 mg 1-0-1 während 5 Tagen.",
    "Nehmen Sie 1 Tablette Ponstan 0-0-1.",
    "Kommen Sie nach 2 Wochen zur Kontrolle.",
)
FACTS = medications("Dafalgan", "Ponstan")
GOOD = draft(
    "Dafalgan 500 mg: 1-0-1, 5 Tage lang.",
    "Ponstan: 1 Tablette, 0-0-1.",
    "Kommen Sie nach 2 Wochen zur Kontrolle.",
)


def test_a_dropped_medication_is_a_fact_01_error() -> None:
    result = check_draft(
        draft("Nehmen Sie 500 mg: 1-0-1, 5 Tage lang.", "Ponstan: 1 Tablette, 0-0-1."),
        source=SOURCE,
        factsheet=FACTS,
    )
    missing = findings(result, "FACT-01")
    assert [(f.fact_id, f.suggestion) for f in missing] == [("f01", "Dafalgan")]
    assert result.metrics.facts_total == 2 and result.metrics.facts_found == 1


def test_a_medication_the_source_lacks_is_fact_05_and_not_required() -> None:
    facts = medications("Dafalgan", "Aspirin")
    result = check_draft(GOOD, source=SOURCE, factsheet=facts)
    assert findings(result, "FACT-01") == []
    assert [f.fact_id for f in findings(result, "FACT-05")] == ["f02"]
    assert result.metrics.facts_total == 1


# -- FACT-09 --------------------------------------------------------------------------


def test_a_medication_with_its_values_in_one_block_passes() -> None:
    result = check_draft(GOOD, source=SOURCE, factsheet=FACTS)
    assert findings(result, "FACT-09") == [] and findings(result, "FACT-01") == []
    assert result.metrics.facts_found == 2


def test_a_dose_and_scheme_apart_from_the_name_are_an_error() -> None:
    result = check_draft(
        draft(
            "Sie nehmen Dafalgan.",
            "Sie nehmen 500 mg.",
            "Am Morgen und am Abend: 1-0-1.",
            "Das machen Sie 5 Tage lang.",
            "Ponstan: 1 Tablette, 0-0-1.",
        ),
        source=SOURCE,
        factsheet=FACTS,
    )
    (found,) = findings(result, "FACT-09")
    assert found.severity == "error"
    assert (found.block_id, found.fact_id, found.segment_ids) == ("b001", "f01", ["s0001"])
    assert found.message_params == {"name": "Dafalgan", "values": "500 mg, 1-0-1, 5 Tage"}
    assert repairable(found)


def test_the_block_with_most_values_is_named_and_only_the_rest_reported() -> None:
    result = check_draft(
        draft(
            "Dafalgan 500 mg: 1-0-1.", "Das machen Sie 5 Tage lang.", "Ponstan: 1 Tablette, 0-0-1."
        ),
        source=SOURCE,
        factsheet=FACTS,
    )
    (found,) = findings(result, "FACT-09")
    assert found.block_id == "b001" and found.message_params["values"] == "5 Tage"


def test_a_value_or_a_name_the_draft_lacks_is_not_fact_09() -> None:
    # The duration is nowhere: FACT-01's finding when it is a fact, never FACT-09's.
    lacks_value = draft("Dafalgan 500 mg: 1-0-1.", "Ponstan: 1 Tablette, 0-0-1.")
    assert findings(check_draft(lacks_value, source=SOURCE, factsheet=FACTS), "FACT-09") == []
    lacks_name = draft("Nehmen Sie 500 mg: 1-0-1, 5 Tage lang.", "Ponstan: 1 Tablette, 0-0-1.")
    assert findings(check_draft(lacks_name, source=SOURCE, factsheet=FACTS), "FACT-09") == []


def test_values_belong_to_the_nearest_name() -> None:
    src = source("Nehmen Sie 2 Tabletten Dafalgan 500 mg 1-0-1 und 1 Tablette Ponstan 0-0-1.")
    owned = {
        m.fact_id: [v.canonical for v in m.values] for m in medication_values(src, FACTS, "de")
    }
    assert owned == {"f01": ["2 Tablette", "500 mg", "1-0-1"], "f02": ["1 Tablette", "0-0-1"]}


def test_measurements_points_in_time_and_ages_do_not_belong_to_a_medication() -> None:
    src = source(
        "Bei Fieber über 38,5 Grad nehmen Sie Dafalgan 500 mg, nach 3 Tagen nicht mehr.",
        "Kinder ab 12 Jahren nehmen Ponstan 250 mg alle 2 Tage.",
    )
    owned = {
        m.fact_id: [v.canonical for v in m.values] for m in medication_values(src, FACTS, "de")
    }
    # A frequency (`alle 2 Tage`) is part of the scheme.
    assert owned == {"f01": ["500 mg"], "f02": ["250 mg", "2d"]}


def test_each_source_sentence_is_kept_together_on_its_own() -> None:
    src = source(
        "Nehmen Sie Dafalgan 500 mg 1-0-1.",
        "Ab dem 4. Tag nehmen Sie Dafalgan 0-0-1.",
    )
    facts = medications("Dafalgan")
    ok = draft("Dafalgan 500 mg: 1-0-1.", "Ab dem 4. Tag: Dafalgan 0-0-1.")
    assert findings(check_draft(ok, source=src, factsheet=facts), "FACT-09") == []


def test_french_doses_and_durations() -> None:
    src = source(
        "Prenez Dafalgan 1 g 1-0-1 pendant 5 jours, puis revenez dans 2 semaines.", lang="fr"
    )
    owned = [
        v.canonical for m in medication_values(src, medications("Dafalgan"), "fr") for v in m.values
    ]
    assert owned == ["1 g", "1-0-1", "5d"]


def test_a_finding_on_another_rule_is_not_made_repairable() -> None:
    other = Finding(block_id="b001", rule_id="FACT-02", severity="error", message="x")
    assert not repairable(other)


# -- the prompts ----------------------------------------------------------------------


def test_doses_switch_on_the_medication_partial() -> None:
    assert has_doses(SOURCE)
    assert has_doses(source("Nehmen Sie 20 Tropfen am Abend."))
    assert not has_doses(source("Trinken Sie 2 Liter Wasser bei über 30 Grad."))
    assert not has_doses(source("Die Gebühr beträgt 20 Franken."))
    assert names_medication(FACTS)
    assert not names_medication(FactSheet(doc_id="patient"))


@pytest.mark.parametrize("lang", ["de", "fr"])
def test_the_partial_renders_only_when_switched_on(lang: str) -> None:
    def understand(**extra: object) -> str:
        return render(
            lang,
            "understand",
            **mode_context("understand"),
            **extra,
            level_name=level_name(lang, "A2"),
            source="[s0001] x",
        )

    assert understand() == understand(medication=False)
    assert '"medication"' not in understand()
    assert '"medication"' in understand(medication=True)


def test_code_completion_keeps_doses_next_to_a_medication_fact() -> None:
    facts = complete_factsheet(medications("Dafalgan"), SOURCE)
    assert {f.value_norm for f in facts.facts} >= {"Dafalgan", "500 mg", "1-0-1", "5 Tage"}


def test_the_mediopunkt_step_leaves_medication_names_as_written() -> None:
    facts = medications("Metoclopramidtropfen")
    assert medication_names(facts) == ["Metoclopramidtropfen"]
    text = draft("Nehmen Sie die Metoclopramidtropfen am Morgen.")
    split, edits = apply_mediopunkt(text)
    assert [e.after for e in edits] == ["Metoclopramid·tropfen"]
    kept, none = apply_mediopunkt(text, keep=medication_names(facts))
    assert none == [] and kept.blocks[0].text == text.blocks[0].text
