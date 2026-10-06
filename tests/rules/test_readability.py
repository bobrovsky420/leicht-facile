"""Readability formulas, words and syllables (rules/readability.py)."""

from __future__ import annotations

import pytest

from leichtfacile.rules.readability import (
    amstad,
    count_syllables,
    gulpease,
    kandel_moles,
    readability,
    words,
)

# -- formulas from counts ------------------------------------------------------------


def test_amstad_from_counts():
    # 2 sentences, 10 words, 15 syllables: ASL 5, ASW 1.5; 180 - 5 - 58.5 * 1.5
    assert amstad(2, 10, 15) == 87.25


def test_kandel_moles_from_counts():
    # ASL 5, ASW 1.5: 207 - 1.015 * 5 - 73.6 * 1.5 = 207 - 5.075 - 110.4
    assert kandel_moles(2, 10, 15) == pytest.approx(91.525, abs=1e-12)


def test_gulpease_from_counts():
    # 89 + (300 * 2 - 10 * 50) / 10 and 89 + (300 * 1 - 10 * 120) / 20
    assert gulpease(2, 10, 50) == 99.0
    assert gulpease(1, 20, 120) == 44.0


def test_scores_are_not_clipped():
    assert amstad(1, 1, 1) == 120.5
    assert amstad(1, 40, 120) == -35.5


@pytest.mark.parametrize("formula", [amstad, kandel_moles, gulpease])
@pytest.mark.parametrize(("n_sentences", "n_words"), [(0, 5), (1, 0)])
def test_formulas_need_a_sentence_and_a_word(formula, n_sentences, n_words):
    with pytest.raises(ValueError):
        formula(n_sentences, n_words, 7)


# -- words ---------------------------------------------------------------------------


def test_words_keep_joined_parts_and_drop_numbers():
    text = "Ab 1. Januar 2026 gilt das Sorge·recht (E-Mail, A2, COVID-19) für 1'500 Kinder."
    assert words(text) == [
        "Ab",
        "Januar",
        "gilt",
        "das",
        "Sorge·recht",
        "E-Mail",
        "A2",
        "COVID-19",
        "für",
        "Kinder",
    ]


def test_words_keep_apostrophes_and_drop_soft_hyphens():
    assert words("Geht's? L'information de l\u2019État.") == [
        "Geht's",
        "L'information",
        "de",
        "l\u2019État",
    ]
    assert words("Sorge\u00adrecht") == ["Sorgerecht"]


def test_words_of_numbers_and_punctuation():
    assert words("9.00 - 12.00 Uhr: 1'500.-") == ["Uhr"]
    assert words("2026. -- ?") == []


# -- syllables -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "lang", "expected"),
    [
        ("Sorge·recht", "de", 3),  # parts at the Mediopunkt: Sor-ge, recht
        ("E-Mail", "de", 2),
        ("und", "de", 1),  # the patterns break un-d; a part without a vowel is no syllable
        ("Kind", "de", 1),
        ("Arbeit", "de", 2),  # A-r-beit
        ("über", "de", 2),  # no hyphenation point: the vowel groups count
        ("einen", "de", 2),
        ("Feuer", "de", 2),  # a hyphenation point splits a vowel group: Feu-er
        ("neue", "de", 2),
        ("Theater", "de", 3),
        ("CHF", "de", 1),  # no vowel: one syllable
        ("z", "de", 1),
        ("contre", "fr", 1),  # mute final e
        ("facile", "fr", 2),
        ("avec", "fr", 2),  # no hyphenation point
        ("été", "fr", 2),
        ("chaque", "fr", 1),  # u after q is no vowel
        ("l'information", "fr", 4),
        ("aujourd'hui", "fr", 3),
        ("informazione", "it", 5),
        ("facile", "it", 3),
        ("dell'anno", "it", 3),
    ],
)
def test_count_syllables(word, lang, expected):
    assert count_syllables(word, lang) == expected


def test_count_syllables_of_no_word():
    assert count_syllables("", "de") == 0
    assert count_syllables("-", "de") == 0


# Spoken syllables in standard pronunciation (Duden, Wiktionary) of 43 words from
# official texts, including known hard cases. Measured with pyphen 0.18.1: 40 of 43
# exact (93.0 percent). Wrong: Information (counts 5; the i of -tion is a glide in
# speech), Idee (3; the patterns break I-de-e), Prämie (3; glide). Counting
# hyphenation points + 1 instead gets 27 of 43 (62.8 percent) with left=1 and right=1
# (und: un-d) and 33 of 43 (76.7 percent) with pyphen's default left=2 and right=2
# (Abend: 1). Familie is Fa-mi-lie, 3 syllables, and counts 3.
OFFICIAL_WORDS = [
    ("und", 1),
    ("über", 2),
    ("einen", 2),
    ("oder", 2),
    ("aber", 2),
    ("immer", 2),
    ("die", 1),
    ("Sie", 1),
    ("Haus", 1),
    ("Kind", 1),
    ("Geld", 1),
    ("Brief", 1),
    ("Amt", 1),
    ("Frist", 1),
    ("Arbeit", 2),
    ("Abend", 2),
    ("Wohnung", 2),
    ("Antrag", 2),
    ("Kanton", 2),
    ("neue", 2),
    ("Frauen", 2),
    ("Gemeinde", 3),
    ("Formular", 3),
    ("Behörde", 3),
    ("Adresse", 3),
    ("Telefon", 3),
    ("Polizei", 3),
    ("Aufenthalt", 3),
    ("Familie", 3),
    ("Energie", 3),
    ("bezahlen", 3),
    ("Theater", 3),
    ("Versicherung", 4),
    ("Krankenkasse", 4),
    ("Unterstützung", 4),
    ("Information", 4),
    ("Steuererklärung", 5),
    ("Ergänzungsleistungen", 6),
    ("Arbeitslosenversicherung", 8),
    ("Idee", 2),
    ("Prämie", 2),
    ("Sorge·recht", 3),
    ("E-Mail", 2),
]

# 40 words drawn at random (random.Random(2026).sample) from the 5000 most frequent
# German words in wordfreq 3.1.1 with at least three letters, counted by hand.
# Measured: 40 of 40 exact. Counting hyphenation points + 1 with left=1 and right=1
# gets 33 of 40 (82.5 percent; kur-z-en, f-lü-gel, ta-l).
FREQUENT_WORDS = [
    ("bank", 1),
    ("lächeln", 2),
    ("entsprechen", 3),
    ("faktor", 2),
    ("schüler", 2),
    ("kurzen", 2),
    ("mittlere", 3),
    ("flügel", 2),
    ("angestellten", 4),
    ("seither", 2),
    ("verträge", 3),
    ("down", 1),
    ("krass", 1),
    ("glas", 1),
    ("dass", 1),
    ("titel", 2),
    ("staaten", 2),
    ("schmerzen", 2),
    ("zeiten", 2),
    ("intensiv", 3),
    ("ohne", 2),
    ("streifen", 2),
    ("tausend", 2),
    ("mitten", 2),
    ("konsequenzen", 4),
    ("krankheit", 2),
    ("info", 2),
    ("grossteil", 2),
    ("sitzung", 2),
    ("höchst", 1),
    ("links", 1),
    ("locker", 2),
    ("sinn", 1),
    ("opfern", 2),
    ("tal", 1),
    ("kochen", 2),
    ("solcher", 2),
    ("gebieten", 3),
    ("paul", 1),
    ("helfer", 2),
]


@pytest.mark.parametrize(
    "word_list", [OFFICIAL_WORDS, FREQUENT_WORDS], ids=["official", "frequent"]
)
def test_syllable_accuracy_on_german_words(word_list):
    wrong = [
        (w, n, count_syllables(w, "de")) for w, n in word_list if count_syllables(w, "de") != n
    ]
    accuracy = 1 - len(wrong) / len(word_list)
    assert accuracy >= 0.85, f"accuracy {accuracy:.1%}; (word, expected, counted): {wrong}"


# Spoken syllables in standard French (final mute e not counted) of 45 words from
# official texts and easy-language pages. Measured with pyphen 0.18.1: 42 of 45 exact
# (93.3 percent). Wrong: payer (a y between vowels joins them: counts 1), doivent and
# parlent (the mute ending -ent of the third person plural counts as a syllable; without
# the part of speech it cannot be told from argent or souvent, where it is spoken).
FRENCH_WORDS = [
    ("demande", 2), ("formulaire", 3), ("commune", 2), ("canton", 2), ("lettre", 1),
    ("argent", 2), ("impôt", 2), ("déclaration", 4), ("information", 4), ("personne", 2),
    ("téléphone", 3), ("numéro", 3), ("délai", 2), ("année", 2), ("aide", 1),
    ("assurance", 3), ("maladie", 3), ("famille", 2), ("enfant", 2), ("école", 2),
    ("travail", 2), ("vous", 1), ("avez", 2), ("pouvez", 2), ("recevez", 3),
    ("payer", 2), ("Suisse", 1), ("Genève", 2), ("francs", 1), ("semaine", 2),
    ("question", 2), ("réponse", 2), ("simple", 1), ("important", 3), ("obligatoire", 4),
    ("nécessaire", 3), ("guichet", 2), ("électricité", 5), ("nourriture", 3),
    ("votation", 3), ("procureur", 3), ("élection", 3), ("handicapées", 4), ("doivent", 1),
    ("parlent", 1),
]  # fmt: skip


def test_syllable_accuracy_on_french_words():
    wrong = [
        (w, n, count_syllables(w, "fr")) for w, n in FRENCH_WORDS if count_syllables(w, "fr") != n
    ]
    accuracy = 1 - len(wrong) / len(FRENCH_WORDS)
    assert accuracy >= 0.9, f"accuracy {accuracy:.1%}; (word, expected, counted): {wrong}"
    assert {w for w, _, _ in wrong} == {"payer", "doivent", "parlent"}


def test_unsupported_language():
    with pytest.raises(ValueError):
        count_syllables("house", "en")
    with pytest.raises(ValueError):
        readability(["A house."], "en")


# -- readability of a text -----------------------------------------------------------


def test_readability_of_a_german_text_counted_by_hand():
    sentences = [
        "Sie bekommen einen Brief vom Steuer·amt.",
        "Bitte bezahlen Sie bis zum 30. Juni 2026.",
        "Die Rechnung ist 500 Franken.",
    ]
    # Numbers are not words. Words and syllables, counted by hand:
    # Sie 1, be-kom-men 3, ei-nen 2, Brief 1, vom 1, Steu-er·amt 3: 6 words, 11
    # Bit-te 2, be-zah-len 3, Sie 1, bis 1, zum 1, Ju-ni 2: 6 words, 10
    # Die 1, Rech-nung 2, ist 1, Fran-ken 2: 4 words, 6
    # 3 sentences, 16 words, 27 syllables: 180 - 16/3 - 58.5 * 27/16 = 75.95
    result = readability(sentences, "de")
    assert result.formula == "amstad"
    assert (result.sentences, result.words, result.syllables, result.letters) == (3, 16, 27, 80)
    assert result.score == pytest.approx(180 - 16 / 3 - 58.5 * 27 / 16, abs=1e-12)
    assert round(result.score, 2) == 75.95


def test_readability_of_a_french_text_uses_kandel_moles():
    # Le 1, chat 1, dort 1: 207 - 1.015 * 3 - 73.6 * 1
    result = readability(["Le chat dort."], "fr")
    assert (result.formula, result.sentences, result.words, result.syllables) == (
        "kandel-moles",
        1,
        3,
        3,
    )
    assert result.score == pytest.approx(207 - 1.015 * 3 - 73.6, abs=1e-12)


def test_readability_of_an_italian_text_uses_gulpease():
    # Letters: il 2, gatto 5, dorme 5. 89 + (300 * 1 - 10 * 12) / 3 = 149, above 100.
    result = readability(["Il gatto dorme."], "it")
    assert (result.formula, result.sentences, result.words, result.letters) == (
        "gulpease",
        1,
        3,
        12,
    )
    assert result.score == 149.0


@pytest.mark.parametrize("sentences", [[], [""], ["2026.", "1'500.-"]])
def test_readability_without_words_has_no_score(sentences):
    result = readability(sentences, "de")
    assert result.score is None
    assert (result.sentences, result.words, result.syllables, result.letters) == (0, 0, 0, 0)


def test_sentences_without_words_do_not_count():
    assert readability(["Das ist gut.", "2026."], "de").sentences == 1
