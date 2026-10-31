"""The sender and the form of address (src/leichtfacile/senders/senders.toml): the data
matches the schema and the rules, the prompts take the phrases and the note, the style
guide and the checker follow the form."""

from __future__ import annotations

from leichtfacile.pipeline.prompts import render
from leichtfacile.pipeline.stages import mode_context
from leichtfacile.rules import check_draft, style_guide
from leichtfacile.rules.base import RULES
from leichtfacile.schemas import ADDRESS_FORMS, LANGS, SENDERS, Block, Draft
from leichtfacile.senders import address_form, address_forms, sender, senders

SMALL = {"style_guide": "", "examples": "", "section": "", "factsheet": "", "source": "[s0001] x"}


def test_the_file_names_every_sender_and_form_of_the_schema_in_every_language() -> None:
    assert tuple(senders()) == SENDERS and tuple(address_forms()) == ADDRESS_FORMS
    for profile in senders().values():
        assert set(profile.phrases) == set(LANGS)
        for phrases in profile.phrases.values():
            assert set(phrases) == {"writes", "document", "judged"}
    for form in address_forms().values():
        assert set(form.forms) == set(LANGS)
        for lang in LANGS:
            assert form.pronoun(lang) and form.guide(lang)


def test_the_formal_form_is_the_rules_own() -> None:
    """The formal lines equal LEX-06's guides and the rule tables' pronouns, so the
    default renders the style guide and the hints as before the option existed."""
    formal = address_form("formal")
    for lang, pronoun in (("de", "Sie"), ("fr", "vous"), ("it", "Lei")):
        assert formal.guide(lang) == RULES["LEX-06"].guide_for(lang, "A2")
        assert formal.pronoun(lang) == pronoun
        assert formal.note(lang) == ""
        assert style_guide(lang, "A2", "formal") == style_guide(lang, "A2")


def test_the_prompts_take_the_senders_phrases_with_the_varietys_facts() -> None:
    assert sender("school").for_prompt("de-CH", {"country_in": "in der Schweiz"}) == {
        "writes": "Texte einer Schule",
        "document": "ein Dokument einer Schule in der Schweiz",
        "judged": "einem Dokument einer Schule",
    }
    for key, start in (
        ("de-CH", "Du schreibst Texte einer Schule in Leichter Sprache"),
        ("de-DE", "Du schreibst Texte einer Schule in Leichter Sprache"),
        ("fr-CH", "Tu écris des textes d'une école en FALC"),
        ("it-CH", "Tu scrivi testi di una scuola in lingua facile"),
    ):
        level = {"de": "Leichter Sprache", "fr": "FALC", "it": "lingua facile"}[key[:2]]
        text = render(key, "write", **mode_context("write", sender="school"), level_name=level,
                      level="A2", medication=False, **SMALL)  # fmt: skip
        assert text.startswith(start), key
    understand = render("de-AT", "understand", **mode_context("understand", sender="organisation"),
                        level_name="Leichter Sprache", medication=False,
                        source="[s0001] x")  # fmt: skip
    assert "ein Dokument einer Organisation in Österreich" in understand
    judge = render("fr-CH", "judge", **mode_context("judge", sender="school"),
                   level_name="FALC", factsheet="", source="", draft="", glossary="")  # fmt: skip
    assert "une version simple d'un document d'une école." in judge


def test_the_form_of_address_adds_its_note_and_turns_the_style_guides_line() -> None:
    formal = render("de-CH", "write", **mode_context("write"), level_name="Leichter Sprache",
                    level="A2", medication=False, **SMALL)  # fmt: skip
    informal = render("de-CH", "write", **mode_context("write", address="informal"),
                      level_name="Leichter Sprache", level="A2", medication=False,
                      **SMALL)  # fmt: skip
    note = address_form("informal").note("de")
    assert note not in formal and note in informal
    assert "mit du an, nicht mit Sie" in note
    guide = style_guide("de", "A2", "plural")
    assert "Sprich die Leserinnen und Leser direkt mit ihr an, nicht mit Sie." in guide
    assert "mit Sie an." not in guide
    assert style_guide("it", "B1", "informal").count("con tu, non con Lei") == 1


def test_the_checker_names_the_forms_pronoun_in_its_hint() -> None:
    def hint(address: str) -> str:
        text = "Der Antragsteller wartet. Wir schicken dir Post."
        draft = Draft(doc_id="d", lang="de", level="A2", address=address,  # type: ignore[arg-type]
                      blocks=[Block(id="b001", kind="sentence", text=text)])  # fmt: skip
        (finding,) = [f for f in check_draft(draft).findings if f.rule_id == "LEX-06"]
        return finding.params["address"]

    assert hint("formal") == "Sie" and hint("informal") == "du" and hint("plural") == "ihr"
