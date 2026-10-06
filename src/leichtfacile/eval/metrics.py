"""Metrics for the evaluation tables (docs/architecture.md §9).

- SARI against the official easy-language reference, on a 0-100 scale, ported from the
  reference implementation of Xu et al. (2016).
- Cohen's kappa for the agreement between the judge and hand labels.
- Compression ratio and novel-token share, which describe how far an output moves away
  from its source.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence

# -- tokens ----------------------------------------------------------------------------
#
# Words keep internal hyphens and apostrophes (e-mail, geht's), numbers keep their
# separators (4.2.2020, 9.00, 1,5, 1'500), and every other character that is not a space
# is a token of its own. French and Italian split an elided article or preposition from
# the next word (l' information, dell' anno), as the Moses tokenizer does. Typographic
# apostrophes become ASCII ones, soft hyphens are dropped, and so is the Mediopunkt:
# Sorge·recht is the word Sorgerecht of the source, typography is not content. Without
# this, a compound the pipeline splits by code (rules/mediopunkt.py) would count as a
# word deleted and a word added in SARI.
_TOKEN_RE = re.compile(r"\w+(?:(?:[-\u2010\u2011']|(?<=\d)[.,](?=\d))\w+)*|[^\w\s]")
_ELISION_TOKEN_RE = re.compile(
    r"[^\W\d_]+'(?=\w)|\w+(?:(?:[-\u2010\u2011]|(?<=\d)[.,'](?=\d))\w+)*|[^\w\s]"
)
_ELISION_LANGS = ("fr", "it")
_DROPPED = str.maketrans("", "", "\u00ad\u00b7")


def tokenize(text: str, lang: str = "de") -> list[str]:
    """Lowercased tokens with punctuation split off, for SARI and token overlap."""
    text = unicodedata.normalize("NFC", text).translate(_DROPPED).replace("\u2019", "'")
    pattern = _ELISION_TOKEN_RE if lang in _ELISION_LANGS else _TOKEN_RE
    return pattern.findall(text.lower())


# -- SARI ------------------------------------------------------------------------------
#
# W. Xu, C. Napoles, E. Pavlick, Q. Chen and C. Callison-Burch, "Optimizing Statistical
# Machine Translation for Text Simplification", TACL 4 (2016), 401-415. This is a port of
# SARIngram and SARIsent in https://github.com/cocoxu/simplification/blob/master/SARI.py
# (commit 0210f15), quirks included, so that our scores equal the reference code's:
# - keep: F1 of precision and recall; source and output counts are multiplied by the
#   number of references, and recall is averaged per n-gram (issue #6 of the repository
#   calls this a bug; it stays);
# - delete: precision only;
# - add: F1 over n-gram types (sets, not counts);
# - F1 per n-gram order 1 to 4, averaged over the orders, then the mean of keep, delete
#   and add (equation 7 of the paper averages precision and recall before F1, issue #8);
# - 0/0 counts as 0, so an output equal to source and reference scores 33.3, not 100;
# - a text shorter than four tokens has no 4-grams and loses their share (issue #17).
# The copy of the paper in that repository gives 0.2683, 0.5890 and 0.5072 for its three
# example outputs, as the code computes; the ACL Anthology version prints 0.2683, 0.7594
# and 0.5890. Hugging Face evaluate and tensor2tensor change the keep recall and set 0/0
# to 1 (0.2695 for the first example); EASSE adds up counts over a corpus and by default
# uses F1 for deletion. Their numbers are not comparable with ours.
#
# We simplify whole documents, so sari_document scores each document as one unit. D-SARI
# (R. Sun, H. Jin and X. Wan, "Document-Level Text Simplification: Dataset, Criteria and
# Baseline", EMNLP 2021) adds length and sentence-count penalties for that setting; we
# report plain SARI and the compression ratio next to it.


def sari_sentence(
    source: str, prediction: str, references: Sequence[str], *, lang: str = "de"
) -> float:
    """SARI of a prediction, from 0 to 100 (the reference code returns 0 to 1).

    All texts go through `tokenize` (lowercase, punctuation split off); for input that is
    already tokenized, like the examples of the paper, this equals the lowercasing and
    splitting at spaces of the reference code.
    """
    if not references:
        raise ValueError("SARI needs at least one reference")
    refs = [tokenize(r, lang) for r in references]
    return 100 * _sari(tokenize(source, lang), tokenize(prediction, lang), refs)


def sari_document(
    source: str, prediction: str, references: Sequence[str], *, lang: str = "de"
) -> float:
    """SARI of a whole document, from 0 to 100.

    The documents are not aligned sentence by sentence: the tokens of each document form
    one sequence (line breaks are spaces), and n-grams may span a sentence boundary. The
    computation is the same as for one sentence.
    """
    return sari_sentence(source, prediction, references, lang=lang)


def _ngrams(tokens: Sequence[str], n: int) -> list[str]:
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _sari(
    source: Sequence[str], prediction: Sequence[str], references: Sequence[Sequence[str]]
) -> float:
    """SARIsent on token lists, from 0 to 1."""
    numref = len(references)
    keep: list[float] = []
    delete: list[float] = []
    add: list[float] = []
    for n in (1, 2, 3, 4):
        k, d, a = _sari_ngram(
            _ngrams(source, n),
            _ngrams(prediction, n),
            [_ngrams(r, n) for r in references],
            numref,
        )
        keep.append(k)
        delete.append(d)
        add.append(a)
    avg_keep = sum(keep) / 4
    avg_delete = sum(delete) / 4
    avg_add = sum(add) / 4
    return (avg_keep + avg_delete + avg_add) / 3


def _sari_ngram(
    sgrams: list[str], cgrams: list[str], rgramslist: list[list[str]], numref: int
) -> tuple[float, float, float]:
    """SARIngram for one n-gram order: (keep F1, delete precision, add F1).

    s is the source, c the candidate (our prediction), r the references; the names
    follow the reference code so that the two can be compared line by line.
    """
    rgramcounter = Counter(g for rgrams in rgramslist for g in rgrams)
    sgramcounter = Counter(sgrams)
    sgramcounter_rep = Counter({g: count * numref for g, count in sgramcounter.items()})
    cgramcounter = Counter(cgrams)
    cgramcounter_rep = Counter({g: count * numref for g, count in cgramcounter.items()})

    # Keep
    keepgramcounter_rep = sgramcounter_rep & cgramcounter_rep
    keepgramcountergood_rep = keepgramcounter_rep & rgramcounter
    keepgramcounterall_rep = sgramcounter_rep & rgramcounter
    keeptmpscore1 = 0.0
    keeptmpscore2 = 0.0
    for g in keepgramcountergood_rep:
        keeptmpscore1 += keepgramcountergood_rep[g] / keepgramcounter_rep[g]
        keeptmpscore2 += keepgramcountergood_rep[g] / keepgramcounterall_rep[g]
    keep_precision = 0.0
    if keepgramcounter_rep:
        keep_precision = keeptmpscore1 / len(keepgramcounter_rep)
    keep_recall = 0.0
    if keepgramcounterall_rep:
        keep_recall = keeptmpscore2 / len(keepgramcounterall_rep)
    keep = _f1(keep_precision, keep_recall)

    # Delete: precision only (the reference code also computes a recall it never uses)
    delgramcounter_rep = sgramcounter_rep - cgramcounter_rep
    delgramcountergood_rep = delgramcounter_rep - rgramcounter
    deltmpscore1 = 0.0
    for g in delgramcountergood_rep:
        deltmpscore1 += delgramcountergood_rep[g] / delgramcounter_rep[g]
    delete = 0.0
    if delgramcounter_rep:
        delete = deltmpscore1 / len(delgramcounter_rep)

    # Add: n-gram types, not counts
    addgramcounter = set(cgramcounter) - set(sgramcounter)
    addgramcountergood = addgramcounter & set(rgramcounter)
    addgramcounterall = set(rgramcounter) - set(sgramcounter)
    add_precision = 0.0
    if addgramcounter:
        add_precision = len(addgramcountergood) / len(addgramcounter)
    add_recall = 0.0
    if addgramcounterall:
        add_recall = len(addgramcountergood) / len(addgramcounterall)
    add = _f1(add_precision, add_recall)

    return keep, delete, add


def _f1(precision: float, recall: float) -> float:
    if precision > 0 or recall > 0:
        return 2 * precision * recall / (precision + recall)
    return 0.0


# -- judge reliability -----------------------------------------------------------------


def cohen_kappa(labels_a: Sequence[str], labels_b: Sequence[str]) -> float:
    """Cohen's kappa for two raters who labelled the same items with nominal categories.

    kappa = (p_o - p_e) / (1 - p_e), with p_o the observed agreement and p_e the agreement
    expected by chance from each rater's label frequencies (J. Cohen, "A coefficient of
    agreement for nominal scales", Educational and Psychological Measurement 20(1), 1960,
    37-46). 1 is perfect agreement, 0 agreement at chance level, below 0 less than chance.

    If both raters give every item one and the same label, p_e is 1 and kappa is 0/0. We
    return 1.0 then: the raters agree perfectly and there is no disagreement to explain.
    Such a sample says little about the judge, so report the number of items with kappa.
    """
    if len(labels_a) != len(labels_b):
        raise ValueError(f"label lists differ in length: {len(labels_a)} and {len(labels_b)}")
    n = len(labels_a)
    if n == 0:
        raise ValueError("kappa needs at least one labelled item")
    agree = sum(a == b for a, b in zip(labels_a, labels_b, strict=True))
    counts_a = Counter(labels_a)
    counts_b = Counter(labels_b)
    chance = sum(counts_a[label] * counts_b[label] for label in counts_a)
    # In integers until the division: kappa = (n * agree - chance) / (n * n - chance).
    if chance == n * n:
        return 1.0
    return (n * agree - chance) / (n * n - chance)


# -- surface measures ------------------------------------------------------------------


def compression_ratio(source_words: int, output_words: int) -> float:
    """Output length relative to the source, in words: 0.6 means 40 percent shorter.

    Count the words of both texts the same way, for example with
    `leichtfacile.rules.readability.words`.
    """
    if source_words <= 0:
        raise ValueError(f"the source needs at least one word, got {source_words}")
    if output_words < 0:
        raise ValueError(f"negative word count: {output_words}")
    return output_words / source_words


def novel_token_share(source_tokens: Sequence[str], output_tokens: Sequence[str]) -> float:
    """Share of output tokens, repetitions included, that do not occur in the source.

    0 means the output only reuses the source's vocabulary; rewriting in easy language
    replaces words and adds explanations, so the share grows. Tokens are compared as
    given: pass `tokenize` output to ignore case and punctuation. An empty output has no
    novel tokens and gives 0.0.
    """
    if not output_tokens:
        return 0.0
    vocabulary = set(source_tokens)
    return sum(t not in vocabulary for t in output_tokens) / len(output_tokens)
