"""Clause recipes (rules/recipes.py): every conjunction LEN-02 and LEN-02 find gets
the rewrite recipe for its kind as the finding's suggestion, and the review page never
offers a recipe as a replacement."""

from __future__ import annotations

import pytest

from leichtfacile.rules import check_draft
from leichtfacile.rules.recipes import RECIPE_RULES, recipe_de, recipe_fr
from leichtfacile.schemas import Block, Draft

GERMAN = [
    ("Sie bekommen Geld, weil Sie wenig verdienen.", "weil", "Deshalb"),
    ("Da Sie wenig verdienen, bekommen Sie Geld.", "Da", "Deshalb"),
    ("Sie stellen ein Gesuch, damit Sie das Geld bekommen.", "damit", "zuerst das Ziel"),
    ("Um das Geld zu bekommen, müssen Sie ein Gesuch stellen.", "Um", "zuerst das Ziel"),
    ("Sie bekommen Geld, obwohl Sie viel verdienen.", "obwohl", "Trotzdem"),
    ("Sie bekommen Geld, auch wenn Sie viel verdienen.", "wenn", "Trotzdem"),
    ("Wenn Sie wenig verdienen, bekommen Sie Geld.", "Wenn", "Frage und eine Antwort"),
    ("Falls Sie wenig verdienen, bekommen Sie Geld.", "Falls", "Nie vielleicht"),
    ("Nachdem Sie das Gesuch geschickt haben, bekommen Sie einen Brief.", "Nachdem", "Zeit"),
    ("Bevor Sie das Gesuch schicken, lesen Sie das Merkblatt.", "Bevor", "Zeit"),
    ("Sobald das Geld da ist, schreibt Ihnen die Gemeinde.", "Sobald", "Zeit"),
    ("Sie sparen Geld, indem Sie früh zahlen.", "indem", "So sparen Sie Geld"),
    ("Sie zahlen früh, so dass Sie Geld sparen.", "dass", "So sparen Sie Geld"),
    ("Das ist das Formular, das Sie brauchen.", "das", "wiederhole das Nomen"),
    ("Das ist das Formular, welches Sie brauchen.", "welches", "wiederhole das Nomen"),
    ("Die Gemeinde prüft, ob Sie Anspruch haben.", "ob", "direkte Frage"),
    ("Die Gemeinde schreibt, dass Sie Anspruch haben.", "dass", "Doppelpunkt"),
    ("Es ist wichtig, das Formular zu schicken.", "schicken", "Schicken Sie das Formular"),
]


def _finding(lang: str, text: str, rule_id: str):
    draft = Draft(
        doc_id="r", lang=lang, level="A2", blocks=[Block(id="b001", kind="sentence", text=text)]
    )
    (finding,) = [f for f in check_draft(draft).findings if f.rule_id == rule_id]
    return finding


@pytest.mark.parametrize(("text", "opener", "marker"), GERMAN, ids=[g[1] for g in GERMAN])
def test_each_german_conjunction_yields_its_recipe(text: str, opener: str, marker: str) -> None:
    finding = _finding("de", text, "LEN-02")
    assert finding.params["opener"] == opener
    assert finding.suggestion and marker in finding.suggestion


def test_several_main_clauses_get_the_two_sentences_recipe() -> None:
    finding = _finding("de", "Sie gehen zum Amt und Sie zeigen Ihren Ausweis.", "LEN-02")
    assert finding.key == "LEN-02.main"
    assert finding.suggestion == recipe_de(None) == "Mach 2 Sätze: eine Aussage pro Satz."


FRENCH = [
    ("Vous recevez de l'argent parce que vous gagnez peu.", "parce que", "C'est pourquoi"),
    ("Puisque vous gagnez peu, vous recevez de l'argent.", "puisque", "C'est pourquoi"),
    ("Vous recevez de l'argent bien que vous gagniez beaucoup.", "bien que", "Mais"),
    ("Vous recevez de l'argent même si vous gagnez beaucoup.", "si", "Mais"),
    ("Si vous gagnez peu, vous recevez de l'argent.", "si", "Jamais peut-être"),
    ("Nous envoyons une facture pour que vous puissiez payer.", "pour que", "Pour cela"),
    ("Pour recevoir l'argent, vous devez faire une demande.", "pour", "Pour cela"),
    ("Afin de recevoir l'argent, vous devez faire une demande.", "afin de", "Pour cela"),
    ("Lorsque vous recevez la lettre, vous payez la facture.", "lorsque", "Ensuite"),
    ("Quand vous recevez la lettre, vous payez la facture.", "quand", "Ensuite"),
    ("Dès que vous recevez la lettre, vous payez la facture.", "dès que", "Ensuite"),
    ("Avant de payer, lisez la lettre.", "avant de", "Ensuite"),
    ("C'est le formulaire qui est important.", "qui", "répète le nom"),
    ("C'est la personne dont vous avez besoin.", "dont", "répète le nom"),
    ("C'est le bureau où vous allez.", "où", "répète le nom"),
    ("Nous vous informons que votre demande est acceptée.", "que", "deux-points"),
]


@pytest.mark.parametrize(("text", "opener", "marker"), FRENCH, ids=[f[1] for f in FRENCH])
def test_each_french_conjunction_yields_its_recipe(text: str, opener: str, marker: str) -> None:
    finding = _finding("fr", text, "LEN-02")
    assert finding.params["opener"] == opener
    assert finding.suggestion and marker in finding.suggestion


def test_french_main_clauses_and_unknown_openers_get_the_two_sentences_recipe() -> None:
    finding = _finding("fr", "Vous allez au bureau et vous montrez votre passeport.", "LEN-02")
    assert finding.key == "LEN-02.main"
    assert finding.suggestion == recipe_fr(None)
    assert recipe_fr("sans") == recipe_fr(None)


def test_recipes_use_plain_hyphens_and_never_the_word_vielleicht_as_advice() -> None:
    import re

    from leichtfacile.rules import recipes

    for table in (recipes._DE, recipes._FR):
        for text in table.values():
            assert not re.search("[\u2013\u2014]", text)
    assert "vielleicht" not in recipes._DE["condition"].split("Nie")[0]


def test_the_review_page_does_not_offer_a_recipe_as_a_replacement(tmp_path) -> None:
    from leichtfacile.schemas import JobConfig, RuleFindings
    from leichtfacile.store import Store
    from leichtfacile.web.views import review_view

    assert {"LEN-02"} == RECIPE_RULES
    from tests.pipeline import fixtures as fx

    store = Store(tmp_path / "r.sqlite")
    job = store.create_job(JobConfig(condition="P1"), title="t")
    store.put_artifact(job.id, "source", fx.letter())
    text = "Sie bekommen Geld, weil Sie wenig verdienen."
    draft = Draft(doc_id="d", lang="de", level="A2",
                  blocks=[Block(id="b001", kind="sentence", text=text)])  # fmt: skip
    store.put_artifact(job.id, "draft", draft, 1)
    rules = check_draft(draft)
    assert isinstance(rules, RuleFindings)
    store.put_artifact(job.id, "rules", rules, 1)
    view = review_view(store, job)
    (issue,) = [i for i in view.rows[0].issues if i.rule_id == "LEN-02"]
    assert issue.suggestion and "Deshalb" in issue.suggestion
    assert not issue.applicable
    store.close()
