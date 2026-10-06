"""SARI, Cohen's kappa and the surface measures (eval/metrics.py)."""

from __future__ import annotations

import pytest

from leichtfacile.eval.metrics import (
    cohen_kappa,
    compression_ratio,
    novel_token_share,
    sari_document,
    sari_sentence,
    tokenize,
)

# -- SARI ----------------------------------------------------------------------------

# The example of Xu et al. (2016), as in main() of the reference SARI.py. The expected
# values are what that code prints (commit 0210f15, run with Python 3.14); the copy of
# the paper in the same repository gives them rounded to 0.2683, 0.5890 and 0.5072.
# (The ACL Anthology version of the paper prints 0.2683, 0.7594 and 0.5890.)
SOURCE = "About 95 species are currently accepted ."
REFERENCES = [
    "About 95 species are currently known .",
    "About 95 species are now accepted .",
    "95 species are now accepted .",
]


@pytest.mark.parametrize(
    ("prediction", "reference_code", "paper"),
    [
        ("About 95 you now get in .", 0.2682782411698074, 0.2683),
        ("About 95 species are now agreed .", 0.5889995423074248, 0.5890),
        ("About 95 species are currently agreed .", 0.5071608864657479, 0.5072),
    ],
)
def test_sari_reproduces_the_reference_code(prediction, reference_code, paper):
    score = sari_sentence(SOURCE, prediction, REFERENCES)
    assert score / 100 == pytest.approx(reference_code, abs=1e-12)
    assert round(score / 100, 4) == paper


def test_sari_keeps_the_keep_recall_of_the_reference_code():
    # The example of issue #6 in the reference repository: its keep recall is 1/2 in
    # the code and 1/3 by equation 5 of the paper. Value from the reference code.
    assert sari_sentence("a b", "b", ["a b", "a"]) == pytest.approx(100 / 12, abs=1e-12)


def test_sari_of_an_unchanged_output():
    # 0/0 counts as 0, so nothing deleted and nothing added scores 0 for both: 100/3.
    assert sari_sentence("a b c d", "a b c d", ["a b c d"]) == pytest.approx(100 / 3)
    # Three tokens have no 4-grams, so keep loses a quarter as well (reference code).
    assert sari_sentence("a b c", "a b c", ["a b c"]) == pytest.approx(25.0)


def test_sari_ignores_case_and_attached_punctuation():
    raw = sari_sentence(
        "Die Frist endet am 31. März.",
        "Die Frist ist am 31. März vorbei.",
        ["Die Frist ist am 31. März zu Ende."],
    )
    tokenized = sari_sentence(
        "die frist endet am 31 . märz .",
        "die frist ist am 31 . märz vorbei .",
        ["die frist ist am 31 . märz zu ende ."],
    )
    assert raw == tokenized


def test_sari_needs_a_reference():
    with pytest.raises(ValueError):
        sari_sentence("a b", "a", [])


def test_sari_document_scores_the_whole_document():
    source = "Die Prämienverbilligung wird jährlich überprüft.\nSie müssen keinen Antrag stellen."
    prediction = "Sie bekommen Geld für die Kranken·kasse.\nSie müssen keinen Antrag stellen."
    reference = (
        "Sie bekommen Geld für die Kranken·kasse.\n"
        "Das Amt prüft das jedes Jahr.\n"
        "Sie müssen nichts tun."
    )
    score = sari_document(source, prediction, [reference])
    # The reference code on the tokens of the three documents joined by spaces.
    assert score / 100 == pytest.approx(0.6214646464646464, abs=1e-12)
    # Line breaks are spaces: n-grams run across sentence boundaries.
    flat = [t.replace("\n", " ") for t in (source, prediction, reference)]
    assert score == sari_sentence(flat[0], flat[1], [flat[2]])


# -- tokens --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "lang", "tokens"),
    [
        (
            "Am 4.2.2020 zahlt die Gemeinde 1'500 Franken, d.h. CHF 1500.-.",
            "de",
            ["am", "4.2.2020", "zahlt", "die", "gemeinde", "1'500", "franken", ","]
            + ["d", ".", "h", ".", "chf", "1500", ".", "-", "."],
        ),
        (
            "Das Sorge·recht per E-Mail: geht's?",
            "de",
            ["das", "sorge·recht", "per", "e-mail", ":", "geht's", "?"],
        ),
        (
            "L\u2019information de l'État coûte 1'500 francs.",
            "fr",
            ["l'", "information", "de", "l'", "état", "coûte", "1'500", "francs", "."],
        ),
        (
            "Dell'anno 2026, alle 9.00.",
            "it",
            ["dell'", "anno", "2026", ",", "alle", "9.00", "."],
        ),
        ("Sorge\u00adrecht\n  neue Zeile", "de", ["sorgerecht", "neue", "zeile"]),
    ],
)
def test_tokenize(text, lang, tokens):
    assert tokenize(text, lang) == tokens


# -- Cohen's kappa -------------------------------------------------------------------


def _labels(table: dict[tuple[str, str], int]) -> tuple[list[str], list[str]]:
    """The two raters' labels from a contingency table {(label a, label b): count}."""
    a: list[str] = []
    b: list[str] = []
    for (label_a, label_b), count in table.items():
        a += [label_a] * count
        b += [label_b] * count
    return a, b


def test_kappa_textbook_example():
    # Wikipedia, "Cohen's kappa", simple example: 50 grant proposals, two readers.
    # p_o = 35/50 = 0.7, p_e = 0.5 * 0.6 + 0.5 * 0.4 = 0.5, kappa = 0.2 / 0.5 = 0.4.
    a, b = _labels({("yes", "yes"): 20, ("yes", "no"): 5, ("no", "yes"): 10, ("no", "no"): 15})
    assert cohen_kappa(a, b) == pytest.approx(0.4, abs=1e-12)


@pytest.mark.parametrize(
    ("table", "exact", "published"),
    [
        (
            {("yes", "yes"): 45, ("yes", "no"): 15, ("no", "yes"): 25, ("no", "no"): 15},
            3 / 23,
            0.1304,
        ),
        (
            {("yes", "yes"): 25, ("yes", "no"): 35, ("no", "yes"): 5, ("no", "no"): 35},
            7 / 27,
            0.2593,
        ),
    ],
)
def test_kappa_same_agreement_different_chance(table, exact, published):
    # Wikipedia, "Same percentages but different numbers": p_o is 0.6 in both tables,
    # p_e is 0.54 and 0.46.
    a, b = _labels(table)
    assert cohen_kappa(a, b) == pytest.approx(exact, abs=1e-12)
    assert round(cohen_kappa(a, b), 4) == published


def test_kappa_three_categories():
    # p_o = 3/4; p_e = (2 * 1 + 1 * 2 + 1 * 1) / 16 = 5/16; kappa = (12 - 5) / (16 - 5)
    assert cohen_kappa(["x", "x", "y", "z"], ["x", "y", "y", "z"]) == pytest.approx(7 / 11)


def test_kappa_degenerate_cases():
    assert cohen_kappa(["a", "b", "c"], ["a", "b", "c"]) == 1.0
    # One category for every item from both raters: 0/0, defined as 1.0.
    assert cohen_kappa(["present"] * 5, ["present"] * 5) == 1.0
    # One rater always says the same: agreement is exactly what chance gives.
    assert cohen_kappa(["ok"] * 4, ["ok", "ok", "ok", "bad"]) == 0.0
    # Systematic disagreement.
    assert cohen_kappa(["a", "b"], ["b", "a"]) == -1.0


def test_kappa_rejects_bad_input():
    with pytest.raises(ValueError):
        cohen_kappa(["a"], ["a", "b"])
    with pytest.raises(ValueError):
        cohen_kappa([], [])


# -- surface measures ----------------------------------------------------------------


def test_compression_ratio():
    assert compression_ratio(200, 150) == 0.75
    assert compression_ratio(100, 120) == 1.2
    assert compression_ratio(10, 0) == 0.0
    with pytest.raises(ValueError):
        compression_ratio(0, 10)
    with pytest.raises(ValueError):
        compression_ratio(10, -1)


def test_novel_token_share():
    source = tokenize("Die Frist endet am 31. März.")
    output = tokenize("Die Frist ist am 31. März vorbei.")
    # 9 output tokens, of which "ist" and "vorbei" are not in the source.
    assert novel_token_share(source, output) == pytest.approx(2 / 9)
    # Repetitions count, tokens are compared as given, an empty output has none.
    assert novel_token_share(["a"], ["b", "b", "a", "a"]) == 0.5
    assert novel_token_share(["Frist"], ["frist"]) == 1.0
    assert novel_token_share(["a"], []) == 0.0
