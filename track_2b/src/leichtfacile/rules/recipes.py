"""Rewrite recipes for sentences with a subordinate clause (LEN-02, LEN-02-FR).

The finding's suggestion names the easy-language pattern for the conjunction found, in
the document's language, so that the repair round and the reviewer know what to do
with it: "weil" becomes two sentences with "Deshalb", "wenn" a question with "Dann",
never "vielleicht" (PLAN.md D-P). The idea of a recipe per conjunction comes from the
Canton of Zurich's prompt (THIRD_PARTY_NOTICES.md); the wording is ours. A recipe is
advice, never a replacement text, so the review page does not offer it as "Apply".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.tokens import Token

# Rules whose suggestion is a recipe, not a text that replaces the evidence.
RECIPE_RULES = frozenset({"LEN-02", "LEN-02-FR"})

_DE = {
    "reason": "Machen Sie 2 Sätze: zuerst der Grund, dann die Folge mit Deshalb. "
    "(Sie verdienen wenig. Deshalb bekommen Sie Geld.)",
    "aim": "Machen Sie 2 Sätze: zuerst das Ziel, dann der Weg mit Deshalb. "
    "(Sie wollen das Geld. Deshalb stellen Sie ein Gesuch.)",
    "concession": "Machen Sie 2 Sätze. Der zweite beginnt mit Trotzdem. "
    "(Sie verdienen viel. Trotzdem bekommen Sie Geld.)",
    "condition": "Machen Sie eine Frage und eine Antwort mit Dann. "
    "(Verdienen Sie wenig? Dann bekommen Sie Geld.) "
    "Nie vielleicht: die Bedingung bleibt eine Bedingung.",
    "time": "Machen Sie 2 Sätze in der Reihenfolge der Zeit. Der zweite beginnt mit Dann. "
    "(Zuerst schicken Sie das Gesuch. Dann bekommen Sie einen Brief.)",
    "means": "Machen Sie 2 Sätze. (Sie zahlen früh. So sparen Sie Geld.)",
    "relative": "Machen Sie 2 Sätze und wiederholen Sie das Nomen. "
    "(Das ist das Formular. Das Formular brauchen Sie.)",
    "whether": "Machen Sie eine direkte Frage. (Haben Sie Anspruch? Das prüft die Gemeinde.)",
    "that": "Schreiben Sie mit Doppelpunkt. (Die Gemeinde schreibt: Sie haben Anspruch.)",
    "infinitive": "Machen Sie 2 Sätze. (Schicken Sie das Formular. Das ist wichtig.)",
    "two": "Machen Sie 2 Sätze: eine Aussage pro Satz.",
}
_DE_OPENERS = {
    "weil": "reason", "da": "reason", "denn": "reason", "zumal": "reason",
    "damit": "aim", "um": "aim",
    "obwohl": "concession", "obschon": "concession", "obgleich": "concession",
    "wenngleich": "concession", "wobei": "concession",
    "wenn": "condition", "falls": "condition", "sofern": "condition", "soweit": "condition",
    "als": "time", "nachdem": "time", "bevor": "time", "sobald": "time", "seit": "time",
    "seitdem": "time", "während": "time", "solange": "time", "bis": "time", "ehe": "time",
    "indem": "means", "sodass": "means",
    "ob": "whether",
    "dass": "that",
}  # fmt: skip
# "auch wenn" is a concession, "so dass" a result: the word before the opener decides.
_DE_BEFORE = {
    ("auch", "wenn"): "concession",
    ("selbst", "wenn"): "concession",
    ("so", "dass"): "means",
}


def recipe_de(opener: Token | None) -> str:
    """The recipe for the German opener a LEN-02 finding names (a KOUS or KOUI
    conjunction, a relative pronoun or the verb of a zu-infinitive clause); without an
    opener, the recipe for several main clauses."""
    if opener is None:
        return _DE["two"]
    if opener.tag_ in ("PRELS", "PRELAT"):
        return _DE["relative"]
    if opener.tag_.startswith("V"):
        return _DE["infinitive"]
    word = opener.text.lower()
    before = opener.doc[opener.i - 1].text.lower() if opener.i > opener.sent.start else ""
    kind = _DE_BEFORE.get((before, word)) or _DE_OPENERS.get(word, "two")
    return _DE[kind]


_FR = {
    "reason": "Faites 2 phrases : d'abord la raison, puis la conséquence avec C'est pourquoi. "
    "(Vous gagnez peu. C'est pourquoi vous recevez de l'argent.)",
    "aim": "Faites 2 phrases : d'abord le but, puis le moyen avec Pour cela. "
    "(Vous voulez l'argent. Pour cela, vous faites une demande.)",
    "concession": "Faites 2 phrases. La deuxième commence par Mais. "
    "(Vous gagnez beaucoup. Mais vous recevez de l'argent.)",
    "condition": "Faites une question et une réponse avec Alors. "
    "(Vous gagnez peu ? Alors vous recevez de l'argent.) "
    "Jamais peut-être : la condition reste une condition.",
    "time": "Faites 2 phrases dans l'ordre du temps. La deuxième commence par Ensuite. "
    "(D'abord vous recevez la lettre. Ensuite vous payez.)",
    "relative": "Faites 2 phrases et répétez le nom. "
    "(C'est le formulaire. Vous remplissez le formulaire.)",
    "that": "Faites 2 phrases : répétez le nom (C'est le formulaire. Vous remplissez le "
    "formulaire.), ou écrivez avec deux-points après un verbe (Nous vous informons : votre "
    "demande est acceptée.).",
    "two": "Faites 2 phrases courtes : une information par phrase.",
}
_FR_OPENERS = {
    "parce que": "reason", "puisque": "reason", "comme": "reason", "car": "reason",
    "pour que": "aim", "afin que": "aim", "pour": "aim", "afin de": "aim",
    "bien que": "concession", "quoique": "concession", "même si": "concession",
    "si": "condition", "à condition que": "condition",
    "lorsque": "time", "quand": "time", "dès que": "time", "après": "time",
    "après que": "time", "avant de": "time", "avant que": "time", "pendant que": "time",
    "depuis que": "time", "jusqu'à ce que": "time", "une fois que": "time",
    "qui": "relative", "dont": "relative", "où": "relative", "lequel": "relative",
    "laquelle": "relative", "lesquels": "relative", "lesquelles": "relative",
    "auquel": "relative", "duquel": "relative",
    "que": "that",
}  # fmt: skip


def recipe_fr(opener: str | None, text: str = "") -> str:
    """The recipe for the French opener a LEN-02-FR finding names (`parce que`, `si`,
    `qui`, `pour`); "même si" is read off the sentence, since the parser gives `si`."""
    if opener is None:
        return _FR["two"]
    word = opener.lower().replace("’", "'")
    if word == "si" and "même si" in text.lower():
        return _FR["concession"]
    return _FR[_FR_OPENERS.get(word, "two")]
