"""Readability indices for German, French and Italian (docs/rules.md, READ-01).

Each index is a pure function of counts, so it can be tested exactly. `readability`
gets the sentences from the caller, splits them into words and counts syllables or
letters. ASL is the average sentence length in words, ASW the average number of
syllables per word. Scores are not clipped: very easy texts can score above 100.

Formulas and the sources their constants were checked against:

- German, Amstad (Flesch adapted for German): 180 - ASL - 58.5 * ASW.
  T. Amstad, "Wie verständlich sind unsere Zeitungen?", dissertation, Universität
  Zürich, 1978; formula as quoted in https://de.wikipedia.org/wiki/Lesbarkeitsindex.
- French, Kandel and Moles: 207 - 1.015 * ASL - 73.6 * ASW.
  L. Kandel and A. Moles, "Application de l'indice de Flesch à la langue française",
  Cahiers d'Études de Radio-Télévision 19 (1958), 253-274; constants as quoted in
  K. Bendová, "Using a parallel corpus to adapt the Flesch Reading Ease formula to
  Czech", Journal of Linguistics 72(2), 2021, 477-487 (doi:10.2478/jazcas-2021-0044).
- Italian, Gulpease: 89 + (300 * sentences - 10 * letters) / words.
  P. Lucisano and M. E. Piemontese, "GULPEASE: una formula per la predizione della
  difficoltà dei testi in lingua italiana", Scuola e città 39(3), 1988, 110-124;
  formula as quoted in https://it.wikipedia.org/wiki/Indice_Gulpease.

Words: a word is a token with at least one letter. A Mediopunkt (Sorge·recht), a
hyphen (E-Mail) or an apostrophe (geht's, l'information) inside a token keeps it one
word. Numbers (2026, 1'500, 9.00) are not words: their written length says nothing
about how long they take to read (2026 has seven spoken syllables), and easy-language
texts write digits on purpose, so counting them would move the score with the number
of numbers. Tokens that mix letters and digits (A2, COVID-19) are words.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from typing import Literal

import pyphen

from leichtfacile.schemas import base_lang
from leichtfacile.varieties import variety

Formula = Literal["amstad", "kandel-moles", "gulpease"]

# The formula is the language's; the hyphenation dictionary for the syllable count is
# the variety's (varieties.toml: de_CH for Swiss German).
FORMULAS: dict[str, Formula] = {"de": "amstad", "fr": "kandel-moles", "it": "gulpease"}

# Characters that join the parts of one word: hyphen, Unicode hyphen, non-breaking
# hyphen, Mediopunkt, apostrophe, typographic apostrophe.
_WORD_RE = re.compile(r"\w+(?:[-\u2010\u2011\u00b7'\u2019]\w+)*")
_PART_SEPARATOR_RE = re.compile(r"[-\u2010\u2011\u00b7]")
_APOSTROPHES_RE = re.compile(r"['\u2019]")
_SOFT_HYPHEN = "\u00ad"
_VOWELS = frozenset("aeiouyàáâäæèéêëìíîïòóôöœùúûüÿ")


@dataclass(frozen=True)
class ReadabilityResult:
    score: float | None  # None when the sentences contain no words
    formula: Formula
    sentences: int  # sentences with at least one word
    words: int
    syllables: int
    letters: int


def amstad(sentences: int, words: int, syllables: int) -> float:
    """German: 180 - ASL - 58.5 * ASW."""
    asl, asw = _averages(sentences, words, syllables)
    return 180 - asl - 58.5 * asw


def kandel_moles(sentences: int, words: int, syllables: int) -> float:
    """French: 207 - 1.015 * ASL - 73.6 * ASW."""
    asl, asw = _averages(sentences, words, syllables)
    return 207 - 1.015 * asl - 73.6 * asw


def gulpease(sentences: int, words: int, letters: int) -> float:
    """Italian: 89 + (300 * sentences - 10 * letters) / words."""
    _check_counts(sentences, words)
    return 89 + (300 * sentences - 10 * letters) / words


def words(text: str) -> list[str]:
    """The words of a text, as written (see the module docstring for what counts)."""
    text = unicodedata.normalize("NFC", text).replace(_SOFT_HYPHEN, "")
    return [t for t in _WORD_RE.findall(text) if any(ch.isalpha() for ch in t)]


def count_syllables(word: str, lang: str) -> int:
    """Syllables of one word, from pyphen's hyphenation patterns and the vowels.

    The word is first split at Mediopunkt and hyphens (Sorge·recht, E-Mail), and
    apostrophes are dropped. In each part, a syllable is a group of adjacent vowels,
    and a hyphenation point inside a group splits it (Feu-er, The-a-ter, neu-e). A part
    without vowels (CHF, km) counts as one syllable.

    The patterns run with left=1 and right=1, so that one-letter syllables at the edges
    are found (A-bend, neu-e). Counting hyphenation points plus one fails in two ways,
    both measured on frequent German words (wordfreq):
    - with left=1 and right=1 the German patterns also break next to single consonants
      (un-d, Kin-d, A-r-beit); 264 of the 1486 most frequent words get such a break.
      Counting vowel groups ignores these breaks.
    - the patterns find no break at all in some frequent words (über, einen; French
      contre, avec, été). Counting vowel groups is the fallback, applied to every word
      rather than to long words only, because the misses are mostly short words.

    French: a final e or es after a consonant is mute (contre: 1, facile: 2). In all
    languages a u after q is not a vowel (chaque, Quelle).

    Known weaknesses: an i before another vowel is a glide in speech but a syllable for
    hyphenation (Information has 4 spoken syllables and counts 5; Prämie 2, counts 3),
    some hyphenation errors remain (Idee counts 3), English words with a silent e get
    one syllable too many (Code, live), and abbreviations are not spelled out (AHV
    counts 1). The measured accuracy is documented in tests/rules/test_readability.py.
    """
    hyphenator = _hyphenator(lang)
    total = 0
    for part in _PART_SEPARATOR_RE.split(unicodedata.normalize("NFC", word)):
        part = _APOSTROPHES_RE.sub("", part).replace(_SOFT_HYPHEN, "").lower()
        if any(ch.isalnum() for ch in part):
            total += max(1, _vowel_groups(part, hyphenator.positions(part), lang))
    return total


def readability(sentences: Iterable[str], lang: str) -> ReadabilityResult:
    """The readability index for the language: Amstad (de), Kandel and Moles (fr) or
    Gulpease (it). Sentences without words (a number alone) are not counted."""
    formula = _formula(lang)
    n_sentences = n_words = n_syllables = n_letters = 0
    for sentence in sentences:
        tokens = words(sentence)
        if not tokens:
            continue
        n_sentences += 1
        n_words += len(tokens)
        n_syllables += sum(count_syllables(t, lang) for t in tokens)
        n_letters += sum(ch.isalpha() for t in tokens for ch in t)
    score: float | None = None
    if n_words:
        if formula == "amstad":
            score = amstad(n_sentences, n_words, n_syllables)
        elif formula == "kandel-moles":
            score = kandel_moles(n_sentences, n_words, n_syllables)
        else:
            score = gulpease(n_sentences, n_words, n_letters)
    return ReadabilityResult(
        score=score,
        formula=formula,
        sentences=n_sentences,
        words=n_words,
        syllables=n_syllables,
        letters=n_letters,
    )


# -- helpers -------------------------------------------------------------------------


def _check_counts(sentences: int, words: int) -> None:
    if sentences <= 0 or words <= 0:
        raise ValueError(f"need at least one sentence and one word, got {sentences} and {words}")


def _averages(sentences: int, words: int, syllables: int) -> tuple[float, float]:
    _check_counts(sentences, words)
    return words / sentences, syllables / words


def _formula(lang: str) -> Formula:
    """`lang`: a language or a variety key (`de-AT`)."""
    try:
        return FORMULAS[base_lang(lang)]
    except KeyError:
        raise ValueError(f"unsupported language {lang!r}; expected de, fr or it") from None


@cache
def _hyphenator(lang: str) -> pyphen.Pyphen:
    _formula(lang)  # validates the language
    return pyphen.Pyphen(lang=variety(lang).hyphenation, left=1, right=1)


def _is_vowel(word: str, i: int) -> bool:
    return word[i] in _VOWELS and not (word[i] == "u" and i > 0 and word[i - 1] == "q")


def _mute_ending(word: str, lang: str) -> int:
    """Where a French mute final e or es starts; len(word) if there is none."""
    if lang == "fr":
        for ending in ("es", "e"):
            start = len(word) - len(ending)
            if (
                start > 1
                and word.endswith(ending)
                and not _is_vowel(word, start - 1)
                and any(_is_vowel(word, i) for i in range(start - 1))
            ):
                return start
    return len(word)


def _vowel_groups(word: str, breaks: list[int], lang: str) -> int:
    """Groups of adjacent vowels; a hyphenation point inside a group splits it."""
    split_at = set(breaks)
    count = 0
    previous = False
    for i in range(_mute_ending(word, lang)):
        vowel = _is_vowel(word, i)
        if vowel and (not previous or i in split_at):
            count += 1
        previous = vowel
    return count
