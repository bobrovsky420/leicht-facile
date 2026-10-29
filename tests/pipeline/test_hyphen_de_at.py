"""The compound mark of Germany and Austria (docs/rules.md LEX-01, docs/architecture.md
§4.3): code writes the hyphen with a capital where Switzerland gets the Mediopunkt, the
rule proposes it, the prompts show it, and the values and the copy guard read it."""

from __future__ import annotations

from leichtfacile.pipeline.prompts import render
from leichtfacile.pipeline.stages import _example_key, mode_context, topic_sentences
from leichtfacile.rules import check_draft, style_guide
from leichtfacile.rules.mediopunkt import apply_mediopunkt
from leichtfacile.rules.values import extract_values
from leichtfacile.schemas import Block, Draft, GlossaryEntry


def draft(region: str, *texts: str) -> Draft:
    return Draft(
        doc_id="d",
        lang="de",
        region=region,
        level="A2",
        blocks=[Block(id=f"b{i:03d}", kind="sentence", text=t) for i, t in enumerate(texts, 1)],
        glossary=[GlossaryEntry(term="Krankenversicherungspolice", explanation="Ein Vertrag.")],
    )


def test_code_writes_the_hyphen_with_a_capital_in_germany_and_austria() -> None:
    german = draft("DE", "Die Krankenversicherungspolice kommt.", "Die Kranken·kasse zahlt.")
    out, edits = apply_mediopunkt(german)
    assert [b.text for b in out.blocks] == [
        "Die Kranken-Versicherungs-Police kommt.", "Die Kranken-Kasse zahlt.",
    ]  # fmt: skip
    assert out.glossary[0].term == "Kranken-Versicherungs-Police"
    assert [(e.before, e.after) for e in edits] == [
        ("Krankenversicherungspolice", "Kranken-Versicherungs-Police"),
        ("Kranken·kasse", "Kranken-Kasse"),
        ("Krankenversicherungspolice", "Kranken-Versicherungs-Police"),
    ]
    assert apply_mediopunkt(out) == (out, [])  # idempotent
    # capito's style, one joint split: the long part gets its second hyphen.
    austria = draft("AT", "Die Mindest-Versicherungsdauer gilt.")
    assert apply_mediopunkt(austria)[0].blocks[0].text == "Die Mindest-Versicherungs-Dauer gilt."
    # Switzerland as before.
    swiss = draft("CH", "Die Krankenversicherungspolice kommt.")
    assert apply_mediopunkt(swiss)[0].blocks[0].text == "Die Kranken·versicherungs·police kommt."


def test_lex_01_proposes_the_hyphen_and_flags_a_mediopunkt_in_germany() -> None:
    found = {
        (f.key, f.suggestion)
        for f in check_draft(
            draft("DE", "Die Krankenversicherungspolice kommt.", "Die Kranken·kasse zahlt.")
        ).findings
        if f.rule_id == "LEX-01"
    }
    assert ("LEX-01.hyphen", "Kranken-Versicherungs-Police") in found
    assert ("LEX-01.mark", "Kranken-Kasse") in found
    hyphenated = check_draft(draft("DE", "Die Kranken-Versicherungs-Police kommt.")).findings
    assert all(f.rule_id != "LEX-01" for f in hyphenated)  # every part within the limit
    swiss = {f.key for f in check_draft(draft("CH", "Die Kranken·kasse zahlt.")).findings}
    assert "LEX-01.mark" not in swiss and "LEX-01.hyphen" not in swiss


def test_the_german_prompts_show_the_hyphen_and_the_standard_spelling() -> None:
    common = dict(level_name="Leichter Sprache", level="A2", source="", factsheet="", section="",
                  medication=False, examples="Park·karte", **mode_context("write"))  # fmt: skip
    germany = render("de-DE", "write", style_guide=style_guide("de-DE", "A2"), **common)
    assert "Hunde-Steuer" in germany and "Bürger-Amt" in germany and "Park-Karte" in germany
    assert "Binde-Strich" in germany and "·" not in germany
    assert "Jeder Block außer Überschriften" in germany
    swiss = render("de", "write", style_guide=style_guide("de", "A2"), **common)
    assert "Hunde·steuer" in swiss and "Jeder Block ausser Überschriften" in swiss


def test_the_values_and_the_copy_guard_read_the_hyphenated_compounds() -> None:
    assert ("identifier", "K-4711") in {
        (v.kind, v.canonical) for v in extract_values("Geschäfts-Nummer: K-4711", "de-DE")
    }
    assert _example_key("Die Hunde-Steuer kostet 120 Euro.") == "die hundesteuer kostet 120 euro"
    assert topic_sentences(["Sie melden den Hund beim Bürger-Amt an."], "de-DE", "Ein Brief.") == [
        "Sie melden den Hund beim Bürger-Amt an."
    ]
    assert topic_sentences(["Sie zahlen bis Freitag."], "de-DE", "Ein Brief.") == []
