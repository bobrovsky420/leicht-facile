"""The vocabulary lists (rules/data/vocabulary_<lang>.toml): well formed, no duplicate
terms, every glossary explanation passes the checker at A2, and the matcher finds the
terms in their inflected, separated and abbreviated forms."""

from __future__ import annotations

import re

import pytest

from leichtfacile.rules import check_draft
from leichtfacile.rules.messages import render_finding
from leichtfacile.rules.vocabulary import easy_for, load_vocabulary, matcher, office_words
from leichtfacile.schemas import Block, Draft, GlossaryEntry

LANGS = ("de", "fr", "it")
# LEX-01 wants a Mediopunkt in long German words; code adds it to drafts at A2 only,
# so the level-neutral list keeps the plain spelling.
SKIP_RULES = {"LEX-01"}
DASHES = {chr(0x2013), chr(0x2014)}  # en and em dash: plain hyphen only
SHARP_S = chr(0xDF)  # Swiss German writes ss


@pytest.mark.parametrize("lang", LANGS)
def test_vocabulary_is_well_formed(lang: str) -> None:
    entries = load_vocabulary(lang)
    replace = [e for e in entries if e.kind == "replace"]
    explain = [e for e in entries if e.kind == "explain"]
    assert len(replace) >= 150 and len(explain) >= 90

    seen: dict[str, str] = {}
    for e in entries:
        key = e.term.casefold()
        assert key not in seen, f"{e.term!r} in {e.group} and {seen[key]}"
        seen[key] = e.group
        text = e.easy if e.kind == "replace" else e.explanation
        assert text and text == text.strip() and e.term == e.term.strip()
        assert not DASHES & set(e.term + text), e.term
        if lang == "de":
            assert SHARP_S not in e.term + text, e.term
        if e.kind == "replace":
            assert e.easy != e.term
        else:
            assert text[-1] in ".?", e.term


@pytest.mark.parametrize("lang", LANGS)
def test_explanations_pass_the_checker(lang: str) -> None:
    explain = [e for e in load_vocabulary(lang) if e.kind == "explain"]
    blocks, owner = [], {}
    for i, e in enumerate(explain):
        for j, sentence in enumerate(re.split(r"(?<=[.?])\s+", e.explanation)):
            block = Block(id=f"b{i:03d}.{j}", kind="sentence", text=sentence)
            blocks.append(block)
            owner[block.id] = e.term
    draft = Draft(
        doc_id="vocabulary",
        lang=lang,
        level="A2",
        blocks=blocks,
        glossary=[GlossaryEntry(term=e.term, explanation=e.explanation) for e in explain],
    )
    findings = [
        f"{owner.get(f.block_id, '-')}: {f.rule_id} {render_finding(f)}"
        for f in check_draft(draft).findings
        if f.severity != "info" and f.rule_id not in SKIP_RULES
    ]
    assert findings == []


def _found(lang: str, text: str) -> list[tuple[str, str]]:
    return [(m.entry.term, m.text) for m in matcher(lang).find_text(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sie reichen das Gesuch innert 30 Tagen ein.",
         [("einreichen", "reichen ... ein"), ("Gesuch", "Gesuch"), ("innert", "innert")]),
        ("Das Formular ist einzureichen.", [("einreichen", "einzureichen")]),
        ("Das Gesetz tritt am 1. Januar in Kraft.",
         [("Gesetz", "Gesetz"), ("in Kraft treten", "tritt ... in Kraft")]),
        ("Sie machen die Kosten geltend.", [("geltend machen", "machen ... geltend")]),
        ("Sie bekommen die Prämien·verbilligung.",
         [("Prämienverbilligung", "Prämien·verbilligung")]),
        ("Die Verfügungen stehen Ihnen zur Verfügung.", [("Verfügung", "Verfügungen")]),
        ("Er bekam eine IV-Rente, z.B. im Mai.",
         [("IV", "IV"), ("Rente", "Rente"), ("z. B.", "z.B.")]),
        ("Die Ergänzungsleistung kommt.", [("Ergänzungsleistungen", "Ergänzungsleistung")]),
    ],
)  # fmt: skip
def test_german_terms_in_their_forms(text: str, expected: list[tuple[str, str]]) -> None:
    assert _found("de", text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Vous vous acquittez de la facture ci-jointe.",
         [("s'acquitter de", "acquittez de"), ("ci-joint", "ci-jointe")]),
        ("Dans le cadre du projet, vous faites valoir vos droits.",
         [("dans le cadre de", "Dans le cadre du"), ("faire valoir", "faites valoir")]),
        ("Les prestations susmentionnées sont versées.",
         [("prestation", "prestations"), ("susmentionné", "susmentionnées"),
          ("verser", "versées")]),
        ("Vous faites opposition à la poursuite.",
         [("opposition à la poursuite", "opposition à la poursuite")]),
        # recourir is no recourant, and dès lors is no dès (not_in)
        ("Il est dès lors important de pouvoir recourir à sa réserve.", []),
        ("J'ai reçu la rente AI, p. ex. en mai.",
         [("rente", "rente"), ("AI", "AI"), ("p. ex.", "p. ex.")]),
    ],
)  # fmt: skip
def test_french_terms_in_their_forms(text: str, expected: list[tuple[str, str]]) -> None:
    assert _found("fr", text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # inflected nouns and adjectives: the ending swapped for the base form's
        ("I premi suddetti sono esigibili.",
         [("premio", "premi"), ("suddetto", "suddetti"), ("esigibile", "esigibili")]),
        ("La prestazione complementare e l'assegno familiare.",
         [("prestazioni complementari", "prestazione complementare"),
          ("assegni familiari", "assegno familiare")]),
        # verb forms, and an articulated preposition for the term's bare one
        ("Ai sensi della legge, l'ufficio provvede al pagamento e ha effettuato il controllo.",
         [("ai sensi di", "Ai sensi della"), ("legge", "legge"),
          ("provvedere", "provvede"), ("effettuare", "effettuato")]),
        # a reflexive verb: listed with its pronoun, which the text puts before the verb
        ("Lei si rivolge all'ufficio e deve annunciarsi all'URC.",
         [("rivolgersi a", "rivolge all'"), ("annunciarsi", "annunciarsi"), ("URC", "URC")]),
        # inoltre is no inoltrare, verso no versare, and in sostanza no sostanza (not_in)
        ("Inoltre, verso sera la decisione è in sostanza chiara.", [("decisione", "decisione")]),
        ("Porti i documenti, p. es. il permesso B, ecc.",
         [("p. es.", "p. es."), ("permesso B", "permesso B"), ("ecc.", "ecc.")]),
    ],
)  # fmt: skip
def test_italian_terms_in_their_forms(text: str, expected: list[tuple[str, str]]) -> None:
    assert _found("it", text) == expected


def test_context_words_are_no_office_words() -> None:
    matches = matcher("de").find_text("Schreiben Sie uns, gemäss dem Gesetz zur Abklärungs-Stelle.")
    assert [m.entry.term for m in matches] == ["Schreiben", "gemäss", "Gesetz", "Abklärung"]
    # Schreiben is context-dependent, Gesetz is explained, Abklärungs-Stelle is a name
    assert [m.entry.term for m in office_words(matches)] == ["gemäss"]


def test_abbreviations_give_their_full_word() -> None:
    assert easy_for("de", "z.B.") == "zum Beispiel"
    assert easy_for("fr", "p. ex.") == "par exemple"
    assert easy_for("de", "CHF") is None
    assert easy_for("it", "ecc.") == "eccetera"
