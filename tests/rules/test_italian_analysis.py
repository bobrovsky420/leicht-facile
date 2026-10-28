"""The Italian pipeline (leichtfacile_model_it: the blank tokenizer and sentencizer
with the Morph-it! component) and the sentence analysis of rules/it.py it feeds."""

from __future__ import annotations

import pytest

from leichtfacile.rules import it
from leichtfacile.rules.nlp import LEXICON_COMPONENT, has_analysis, has_parser, pipeline


@pytest.fixture(scope="module")
def nlp():
    return pipeline("it")


def _sent(nlp, text: str):
    return next(nlp(text).sents)


def test_the_pipeline_tags_without_a_parser(nlp) -> None:
    assert LEXICON_COMPONENT in nlp.pipe_names and has_analysis(nlp) and not has_parser(nlp)
    doc = nlp("Il modulo deve essere compilato entro il 31 marzo 2026.")
    tags = {t.text: (t.lemma_, t.pos_) for t in doc}
    assert tags["modulo"] == ("modulo", "NOUN")
    assert tags["deve"] == ("dovere", "VERB")
    assert tags["essere"] == ("essere", "AUX")  # before a participle
    assert tags["compilato"] == ("compilare", "VERB")
    assert "Part" in doc[4].morph.get("VerbForm") and "Past" in doc[4].morph.get("Tense")
    assert doc[7].pos_ == "NUM" and doc[7]._.readings == ()  # 31: not in the lexicon
    assert doc[-1].pos_ == "PUNCT"


def test_ambiguous_forms_keep_every_reading(nlp) -> None:
    doc = nlp("Compili il modulo e lo invii.")
    compili, lo, invii = doc[0], doc[4], doc[5]
    assert {tag for _, tag in compili._.readings} >= {"VER:ind+pres+2+s", "VER:sub+pres+3+s"}
    assert "Fin" in compili.morph.get("VerbForm")
    assert lo.pos_ == "PRON" and invii.pos_ == "VERB"  # a clitic and its verb, no article
    assert nlp("Lei paga 500 franchi.")[3].pos_ == "NOUN"  # franchi: not the verb francare
    assert nlp("La domanda è pronta.")[1].pos_ == "NOUN"  # after the article
    assert nlp("Lei domanda un modulo.")[1].pos_ == "VERB"
    assert nlp("Secondo la legge paga.")[0].pos_ == "ADP"  # secondo: not the verb secondare
    assert nlp("Tu sei malato.")[1].pos_ == "VERB" and nlp("Lei aspetta sei mesi.")[2].pos_ == "NUM"
    assert nlp("Se sei stato nel bosco, controlla la pelle.")[2].pos_ == "VERB"  # the participle
    assert nlp("Ha raggiunto la sua franchigia.")[2].pos_ == "DET"  # la before a possessive
    doc = nlp("Un appartamento senza gradini e ostacoli.")
    assert doc[2].pos_ == "ADP" and doc[3].pos_ == "NOUN" and doc[5].pos_ == "NOUN"
    assert nlp("Sono ostacoli fisici presenti in casa.")[3].pos_ != "VERB"
    doc = nlp("Chieda all'Ufficio rette, anticipi e incassi.")
    assert [t.pos_ for t in doc[3:8]] == ["NOUN", "PUNCT", "NOUN", "CCONJ", "NOUN"]


@pytest.mark.parametrize(
    ("text", "pos"),
    [
        ("Telefoni al numero 117.", "VERB"),  # a polite imperative, not the plural noun
        ("Telefoni per fissare un appuntamento.", "VERB"),
        ("Controlli i documenti.", "VERB"),
        ("Per domande: telefoni all'ufficio.", "VERB"),
        ("Aspetti della vita", "NOUN"),
        ("Contatti per domande", "NOUN"),
        ("Telefoni fissi e cellulari", "NOUN"),
    ],
)
def test_polite_imperatives_at_the_start(nlp, text: str, pos: str) -> None:
    doc = nlp(text)
    token = doc[3] if text.startswith("Per domande") else doc[0]
    assert token.pos_ == pos


def test_word_count_joins_elisions_and_number_runs(nlp) -> None:
    assert it.word_count(_sent(nlp, "L'ufficio dell'anno scorso ha scritto.")) == 5
    assert it.word_count(_sent(nlp, "Telefoni allo 091 123 45 67.")) == 3


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("La domanda è stata inviata dal Comune.", [("è stata inviata", True)]),
        ("Il modulo viene controllato.", [("viene controllato", True)]),
        ("Il modulo deve essere compilato.", [("essere compilato", True)]),
        ("Il modulo è compilato.", [("è compilato", False)]),
        ("L'ufficio è chiuso.", []),
        ("Lei è arrivata ieri.", []),
        ("Lei si è iscritta al corso.", []),
    ],
)
def test_passive_constructions(nlp, text: str, expected: list) -> None:
    assert it.passive_constructions(_sent(nlp, text)) == expected


@pytest.mark.parametrize(
    ("text", "openers", "clauses"),
    [
        ("Lei paga la tassa.", [], 1),
        ("Paga la tassa se ha un cane.", ["se"], 2),
        ("Questo è il modulo che Lei compila.", ["che"], 2),
        ("Telefoni per fissare un appuntamento.", ["per"], 2),
        ("Per ricevere i soldi Lei deve fare una domanda.", ["per"], 2),
        ("Per confrontare i prezzi:", ["per"], 1),
        ("La domanda è stata inviata e il Comune ha risposto.", [], 2),
        ("Bisogna chiedere all'Ufficio rette, anticipi e incassi.", [], 1),
        ("Lei riceve una lettera e paga la fattura.", [], 1),
        ("Lei riceve una lettera e il Comune paga.", [], 2),
        ("Perché paga?", [], 1),
    ],
)
def test_subordinators_and_clause_count(nlp, text: str, openers: list, clauses: int) -> None:
    s = _sent(nlp, text)
    assert it.subordinators(s) == openers
    assert it.clause_count(s) == clauses
