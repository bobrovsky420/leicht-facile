"""Segmentation: structural units into `Segment`s with stable ids.

The extractors (text, HTML, PDF) produce `Unit`s in document order: headings,
paragraphs, list items and table cells. `build_segments` turns them into segments:
headings stay one segment each, every other unit is split into sentences that share
the unit's `para` index. Ids run "s0001", "s0002", ... in document order, and
`heading_path` lists the enclosing headings by level.

Sentences are split by spaCy's rule-based sentencizer on a blank pipeline for the
language (no model download, fast). Two systematic errors of the blank pipelines are
corrected afterwards:

- False splits after abbreviations the tokenizer does not know ("Art. 5", "Dr. med.",
  French "art. 12 al. 3", "p. ex.", Italian "cpv. 2", "Sig. Rossi") and before a word
  in lower case are merged again.
- An opening quote or bracket after the period stays with the sentence it opens.
- Missed splits in German: the tokenizer keeps a number with a period as one token
  (ordinal numbers), so "Die Frist endet am 31. März 2026. Danach ..." comes out as
  one sentence. A number with a period ends the sentence when the next word starts in
  upper case, is not a month name, and either the number is a year, a date or an
  amount, or the next word is a function word ("Wir", "Die", "Danach"). "am 3. Mai" and
  "die 2. Mahnung" stay together. The same applies after an abbreviation that can end
  a sentence ("usw.", "etc.", "ecc.", "60 Fr.").
"""

from __future__ import annotations

import re
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache

import spacy
from spacy.language import Language

from leichtfacile.ingest.detect import FUNCTION_WORDS
from leichtfacile.ingest.normalize import normalize_text
from leichtfacile.schemas import LANGS, Segment, SegmentKind

DEFAULT_HEADING_LEVEL = 2


@dataclass(frozen=True)
class Unit:
    """One structural unit of a source document."""

    kind: SegmentKind
    text: str
    heading_level: int | None = None  # 1-6 for headings; None means level 2
    page: int | None = None  # PDF page, 1-based


# -- abbreviations -----------------------------------------------------------------
# Lower case, without the final period and without inner spaces ("z. B." is "z.b").

# Never at the end of a sentence: titles and words that always precede something.
_LEADING_WORDS = """
    abt abzgl allg betr bspw bzgl bzw ca d.h dipl dr ev evtl exkl fax frl geb gem ggf hr
    hrn i.d.r inkl insb ing iur jur kath kt lic max med mind phil prof rd ref resp sel
    s.o s.u sog st str tel u.a u.u v.a vgl z.b z.h z.t zb zzgl av bd cf env m me mlle
    mlles mm mme mmes p.ex pr rte ste vve ad.es arch avv cfr dott dott.ssa egr gent geom
    on p.es rag sig sig.na sig.ra sig.ri sigg spett vd
"""
_LEADING = frozenset(_LEADING_WORDS.split()) | {
    "o.\u00e4",
    "u.\u00e4",
    "r\u00f6m",
    "c.-\u00e0-d",
    "c.\u00e0.d",
    "t\u00e9l",
}
# Before a number: "Art. 5", "Abs. 2", "al. 3", "cpv. 2", "n. 12", "S. 4".
_REFERENCE_WORDS = """
    abb abs al anm art bd bst buchst cap ch chap cif cpv fig kap let lett lit n no nr p
    pag pagg par pp rz s tab vol ziff
"""
_REFERENCE = frozenset(_REFERENCE_WORDS.split())
# Can end a sentence: "usw.", "etc.", "ecc.", "Es kostet 60 Fr."
_FINAL_WORDS = """
    etc ecc f ff fr jh jhd min mia mio mrd sek std tsd u.s.w usf usw
"""
_FINAL = frozenset(_FINAL_WORDS.split())

_MONTHS_WORDS = """
    januar februar maerz april mai juni juli august september oktober november dezember
    jan feb febr apr jun jul aug sep sept okt nov dez janvier fevrier mars avril juin
    juillet aout septembre octobre novembre decembre janv avr juil gennaio febbraio
    marzo aprile maggio giugno luglio agosto settembre ottobre dicembre gen mag giu lug
    ago set ott dic
"""
MONTHS = frozenset(_MONTHS_WORDS.split()) | {
    "j\u00e4nner",
    "m\u00e4rz",
    "m\u00e4r",
    "f\u00e9vrier",
    "f\u00e9vr",
    "ao\u00fbt",
    "d\u00e9cembre",
    "d\u00e9c",
}
_EXTRA_STARTERS = {
    lang: frozenset(words.split())
    for lang, words in {
        "de": "bitte danach daher dafür damit dann dazu deshalb trotzdem zudem",
        "fr": "cependant ensuite puis",
        "it": "poi quindi tuttavia",
    }.items()
}

# Opening brackets and quotation marks: ( [ { guillemets, low and high curly quotes.
_OPENING = "([{\u00ab\u2039\u201e\u201c\u201a\u2018\"'"
_ELISION = re.compile(r"^.*['\u2019]")
_STREET = re.compile(r"[^\W\d_]{2,}str$")  # "Bahnhofstr. 5"
_NUMBER_END = re.compile(r"(?:^|[\s(\[/\u00ab\u201e\"'])(\d(?:[\d'\u2019.,]*\d)?)\.$")
_FIRST_WORD = re.compile(rf"[{re.escape(_OPENING)}]*([^\W\d_]+)")
_CANDIDATE = re.compile(r"\.\s+")


@cache
def _pipeline(lang: str) -> Language:
    nlp = spacy.blank(lang)
    nlp.add_pipe("sentencizer")
    return nlp


_NLP_LOCK = threading.Lock()


def split_sentences(text: str, lang: str) -> list[str]:
    """Split one paragraph into sentences (see the module docstring)."""
    if lang not in LANGS:
        raise ValueError(f"unsupported language {lang!r}; expected one of {LANGS}")
    text = text.strip()
    if not text:
        return []
    with _NLP_LOCK:
        doc = _pipeline(lang)(text)
    proposed = {_before_opening(text, s.start_char) for s in doc.sents if s.start_char > 0}
    candidates = {m.end() for m in _CANDIDATE.finditer(text) if m.end() < len(text)}
    starts = []
    for pos in sorted(proposed | candidates):
        left = text[max(0, pos - 80) : pos].rstrip()
        right = text[pos : pos + 80]
        if pos in proposed:
            if not _keeps_together(left, right):
                starts.append(pos)
        elif _missed_boundary(left, right, lang):
            starts.append(pos)
    bounds = [0, *starts, len(text)]
    return [s for a, b in zip(bounds, bounds[1:], strict=False) if (s := text[a:b].strip())]


def _before_opening(text: str, pos: int) -> int:
    """Move a sentence start back over opening quotes and brackets.

    The sentencizer starts a sentence at the first word after the period, so in
    "... Hitze·welle. \u00abHitze·welle\u00bb bedeutet ..." the opening guillemet would end the
    previous sentence. A quote or bracket that follows a space opens the next sentence.
    """
    while pos > 1 and text[pos - 1] in _OPENING and text[pos - 2].isspace():
        pos -= 1
    return pos


def _keeps_together(left: str, right: str) -> bool:
    """True when a boundary proposed by the sentencizer is not a sentence end."""
    if not left.endswith("."):
        return False
    first = right.lstrip(_OPENING)[:1]
    if not first:
        return False
    if first.islower():
        return True
    candidates = _abbreviation_candidates(left)
    if any(c in _LEADING for c in candidates):
        return True
    number_end = _NUMBER_END.search(left) is not None
    if first.isdigit() and (
        number_end
        or any(c in _REFERENCE or c in _FINAL for c in candidates)
        or _STREET.search(candidates[0])
    ):
        return True
    return number_end and _first_word(right) in MONTHS


def _missed_boundary(left: str, right: str, lang: str) -> bool:
    """True when the sentencizer missed a sentence end after a number or abbreviation."""
    match = _FIRST_WORD.match(right)
    if match is None or not match.group(1)[0].isupper():
        return False
    first = match.group(1).lower()
    if first in MONTHS:
        return False
    starters = FUNCTION_WORDS[lang] | _EXTRA_STARTERS.get(lang, frozenset())
    number = _NUMBER_END.search(left)
    if number:
        value = number.group(1)
        if any(c in value for c in ".,'\u2019") or sum(c.isdigit() for c in value) >= 4:
            return True  # a year, a date, an amount or a phone number
        return first in starters  # "67. Wir ..." but not "3. Etage"
    if any(c in _FINAL for c in _abbreviation_candidates(left)):
        # German nouns are capitalised, so only a function word marks a new sentence.
        return lang != "de" or first in starters
    return False


def _abbreviation_candidates(left: str) -> list[str]:
    """The last one, two and three tokens before the final period, normalised."""
    tokens = left[-60:].split()
    out = []
    for n in (1, 2, 3):
        if len(tokens) < n:
            break
        chunk = _ELISION.sub("", "".join(tokens[-n:]).lstrip(_OPENING))
        out.append(chunk[:-1].lower())
    return out


def _first_word(text: str) -> str:
    match = _FIRST_WORD.match(text)
    return match.group(1).lower() if match else ""


# -- segments ----------------------------------------------------------------------


def build_segments(units: Iterable[Unit], lang: str) -> list[Segment]:
    """Turn units into segments with ids, heading paths and paragraph indices."""
    segments: list[Segment] = []
    open_headings: list[tuple[int, str]] = []
    para = 0
    for unit in units:
        text = " ".join(normalize_text(unit.text).split())
        if not text:
            continue
        if unit.kind == "heading":
            level = min(max(unit.heading_level or DEFAULT_HEADING_LEVEL, 1), 6)
            while open_headings and open_headings[-1][0] >= level:
                open_headings.pop()
            segments.append(
                Segment(
                    id=_segment_id(len(segments)),
                    kind="heading",
                    text=text,
                    heading_path=[t for _, t in open_headings],
                    heading_level=level,
                    para=para,
                    page=unit.page,
                )
            )
            open_headings.append((level, text))
        else:
            for sentence in split_sentences(text, lang):
                segments.append(
                    Segment(
                        id=_segment_id(len(segments)),
                        kind=unit.kind,
                        text=sentence,
                        heading_path=[t for _, t in open_headings],
                        para=para,
                        page=unit.page,
                    )
                )
        para += 1
    return segments


def _segment_id(index: int) -> str:
    return f"s{index + 1:04d}"
