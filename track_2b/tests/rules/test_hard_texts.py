"""The hard texts of track_2b/docs/hard-texts.md trigger the rules the collection lists.

Only the rules code can check are asserted; the SEM rules belong to the judge. Where
the checker reports more than the list, that is fine: these sentences break many rules.
The sentences are written by the team (see track_2b/docs/hard-texts.md).
"""

from __future__ import annotations

import pytest

from leichtfacile.rules import check_draft
from leichtfacile.schemas import Block, Draft

HARD_SENTENCES = {
    "DE-1": (
        "Anspruch auf Prämienverbilligung haben Personen, deren massgebendes Einkommen die "
        "vom Regierungsrat festgelegte Grenze nicht übersteigt.",
        {"LEN-02", "ORD-01", "GRAM-05", "NEG-02"},
    ),
    "DE-2": (
        "Das Gesuch ist vollständig ausgefüllt und unterzeichnet bis spätestens 31.03.2027 "
        "einzureichen, andernfalls verwirkt der Anspruch.",
        {"GRAM-01", "NUM-03", "LEN-02"},
    ),
    "DE-3": (
        "Gegen diese Verfügung kann innert 30 Tagen seit Eröffnung schriftlich Einsprache "
        "erhoben werden.",
        {"GRAM-01"},
    ),
    "DE-4": (
        "Es ist nicht unwesentlich, dass Kosten, die nicht fristgerecht geltend gemacht werden, "
        "nicht vergütet werden können.",
        {"NEG-01", "LEN-02"},
    ),
    "DE-5": (
        "Die Rückerstattung von Krankheits- und Behinderungskosten erfolgt gemäss Art. 14 "
        "Abs. 1 ELG, sofern die Kosten nicht durch Dritte gedeckt sind bzw. wären.",
        {"LEX-02", "GRAM-03"},
    ),
    "DE-6": (
        "Sollten Sie mit der Zahlung in Verzug geraten, behalten wir uns vor, die Betreibung "
        "einzuleiten.",
        {"GRAM-03"},
    ),
    "DE-7": (
        "Der Antragsteller hat die Unterlagen der zuständigen Stelle einzureichen; diese prüft "
        "sie und leitet sie gegebenenfalls weiter.",
        {"LEX-06", "LEX-04", "GRAM-06"},
    ),
    "BehiG": (
        "Das Behindertengleichstellungsgesetz (BehiG) gilt.",
        {"LEX-01", "LEX-02", "GRAM-05"},
    ),
    "Kostengutsprache": ("Die Kostengutsprache kommt bald.", {"LEX-01", "LEX-03"}),
    "Artikel": ("Das steht in Art. 14 Abs. 1 lit. b ELG.", {"LEX-02"}),
    "EL": ("Die Ergänzungsleistungen (EL) helfen.", {"LEX-01", "LEX-02"}),
}


# FR-3 is left out: the collection lists only judge rules for it (SEM-02, SEM-05).
HARD_SENTENCES_FR = {
    "FR-1": (
        "Le droit à la réduction individuelle des primes est reconnu aux personnes dont le "
        "revenu déterminant n'excède pas les limites fixées par le Conseil d'État.",
        {"GRAM-01-FR"},
    ),
    "FR-2": (
        "La demande doit être déposée, dûment remplie et signée, au plus tard le 31.03.2027, "
        "faute de quoi le droit s'éteint.",
        {"GRAM-01-FR", "NUM-03-FR"},
    ),
    "FR-4": (
        "Il convient de relever que les frais qui n'auraient pas été annoncés dans les délais "
        "ne pourront être remboursés.",
        {"GRAM-08-FR", "GRAM-03-FR"},
    ),
    "FR-5": (
        "Si vous deviez ne pas être en mesure de vous acquitter du montant dû, nous vous "
        "saurions gré de bien vouloir prendre contact avec nos services.",
        {"GRAM-03-FR"},
    ),
    "FR-6": (
        "Le/la requérant·e transmet les pièces justificatives à l'office compétent, lequel les "
        "examine et, le cas échéant, les fait suivre.",
        {"LEX-05-FR"},
    ),
    "FR-7": (
        "Le délai est prolongé au 15.09 moyennant un émolument de Fr. 40.-.",
        {"NUM-03-FR", "NUM-07-FR", "LEX-07-FR"},
    ),
}
CASES = [("de", key, *value) for key, value in HARD_SENTENCES.items()]
CASES += [("fr", key, *value) for key, value in HARD_SENTENCES_FR.items()]


@pytest.mark.parametrize(("lang", "key", "text", "expected"), CASES, ids=[c[1] for c in CASES])
def test_hard_sentence_triggers_the_listed_rules(
    lang: str, key: str, text: str, expected: set[str]
) -> None:
    draft = Draft(doc_id="hard", lang=lang, level="A2",
                  blocks=[Block(id="b001", kind="sentence", text=text)])  # fmt: skip
    found = {f.rule_id for f in check_draft(draft).findings}
    assert expected <= found, f"{key}: missing {sorted(expected - found)}"


def test_the_law_that_requires_easy_language_fails_its_own_rules() -> None:
    """The presentation example: BehiG breaks the long-word, abbreviation and nominal rules."""
    draft = Draft(doc_id="hard", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Das Behindertengleichstellungsgesetz (BehiG) gilt.")
    ])  # fmt: skip
    findings = {f.rule_id: f for f in check_draft(draft).findings}
    assert findings["LEX-01"].suggestion == "Behinderten·gleich·stellungs·gesetz"


def test_an_explained_abbreviation_is_only_a_note() -> None:
    text = "Die Ergänzungs·leistungen (EL) helfen Ihnen. Die EL kommen jeden Monat."
    draft = Draft(doc_id="hard", lang="de", level="A2",
                  blocks=[Block(id="b001", kind="sentence", text=text)])  # fmt: skip
    severities = {f.severity for f in check_draft(draft).findings if f.rule_id == "LEX-02"}
    assert severities == {"info"}
