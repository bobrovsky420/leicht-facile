"""Hard words for easy language, per language: an everyday word to use instead, or a
plain explanation for the glossary when the term has to stay.

The lists are rules/data/vocabulary_{lang}.toml; their header says how to edit them.
They are the seed of the termbase (PLAN.md, WP17): hard term, easy term, explanation.

`find_terms` finds the entries in a parsed text. A word matches in its inflected forms
(the lemma, or the term with a usual ending: Verfügungen, versées), with its Mediopunkt
(Prämien·verbilligung), as a German separable verb (reichen ... ein for einreichen) and
as a German verbal phrase whose verb stands elsewhere in the sentence (tritt ... in
Kraft). Abbreviations and acronyms match as written, case and dots included, so the
French "ai" is never the AI. A phrase of the [not_in] table hides a term inside it
(zur Verfügung stehen is no decision), and of overlapping matches the longest wins
(opposition à la poursuite over opposition).

The pipeline uses the lists in four places (docs/architecture.md §4): the fact sheet
gets the checked explanations, the write prompt lists the hard words of the source with
their everyday word, code adds missing glossary entries (rules/glossary.py), and rule
LEX-07 / LEX-07-FR flags the office words left in a draft.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import cached_property, lru_cache
from importlib import resources
from typing import TYPE_CHECKING, Literal

from leichtfacile.rules.lexicon import MEDIOPUNKT, zipf
from leichtfacile.rules.nlp import pipeline

if TYPE_CHECKING:
    from spacy.tokens import Doc, Span, Token

Kind = Literal["replace", "explain"]
KINDS: tuple[Kind, ...] = ("replace", "explain")
CONTEXT = "context"  # the group of words with a second, everyday sense
OFFICE_RULES = ("LEX-07", "LEX-07-FR")  # the rules that flag the office words
ABBREVIATIONS = "abbreviations"
# An explanation is added by code only for a term an everyday reader may not know: an
# abbreviation, a phrase, or a word below the everyday words loi (5.4) and demande (5.5)
# on the Zipf scale. Verfügung (5.0, from zur Verfügung) and décision (5.0) stay in; a
# cap takes the rarest terms first (rules/glossary.py).
HARD_ZIPF = 5.2
# Endings an inflected form may add to the term as written (Fristen, versées).
_ENDINGS = {
    "de": ("e", "en", "n", "s", "es", "er", "ern", "em"),
    "fr": ("e", "s", "es", "x"),
}
_MIN_STEM = 4  # shorter words match only as written or by their lemma
# French function words in their contracted and elided forms: dans le cadre du.
_FUNCTION_FORMS = {
    "fr": {
        "de": {"d'", "du", "des"},
        "à": {"au", "aux"},
        "le": {"la", "les", "l'"},
        "la": {"le", "les", "l'"},
    },
}
_REFLEXIVE = ("s'", "se ")  # French verbs listed with their pronoun: s'acquitter de
_GERMAN_INFINITIVE = re.compile(r"[a-zäöü]+(?:en|ern|eln)")


@dataclass(frozen=True)
class VocabularyEntry:
    term: str
    kind: Kind
    group: str  # connectors, verbs, law, insurance, context, ... (the TOML table)
    easy: str | None = None  # kind "replace": the everyday word
    explanation: str | None = None  # kind "explain": the glossary text
    not_in: tuple[str, ...] = ()  # phrases in which the term does not count

    @property
    def context(self) -> bool:
        """A word with a second, everyday sense: a hint for the writer, never used by
        code on its own."""
        return self.group == CONTEXT

    @property
    def abbreviation(self) -> bool:
        return self.group == ABBREVIATIONS or _is_acronym(self.term)


@dataclass(frozen=True)
class Match:
    entry: VocabularyEntry
    text: str  # the words as they stand in the text (separate parts joined by " ... ")
    start: int  # character offsets in the text that was searched
    end: int
    # The character ranges of the matched words: one, or two for a separated verb
    # (reichen ... ein), so that the words in between can match on their own.
    ranges: tuple[tuple[int, int], ...] = ()
    partial: bool = False  # only a part of a hyphenated word: Rente in IV-Rente

    @property
    def parts(self) -> tuple[tuple[int, int], ...]:
        return self.ranges or ((self.start, self.end),)


def vocabulary_path(lang: str):
    return resources.files("leichtfacile.rules") / "data" / f"vocabulary_{lang}.toml"


def has_vocabulary(lang: str) -> bool:
    return vocabulary_path(lang).is_file()


@lru_cache
def load_vocabulary(lang: str) -> tuple[VocabularyEntry, ...]:
    if not has_vocabulary(lang):
        return ()
    data = tomllib.loads(vocabulary_path(lang).read_text(encoding="utf-8"))
    unknown = set(data) - {*KINDS, "not_in"}
    if unknown:
        raise ValueError(f"vocabulary_{lang}.toml: unknown tables {sorted(unknown)}")
    not_in = {term: tuple(phrases) for term, phrases in data.get("not_in", {}).items()}
    entries = []
    for kind in KINDS:
        for group, terms in data.get(kind, {}).items():
            for term, text in terms.items():
                extra = {"easy": text} if kind == "replace" else {"explanation": text}
                entries.append(
                    VocabularyEntry(term, kind, group, not_in=not_in.get(term, ()), **extra)
                )
    orphans = set(not_in) - {e.term for e in entries}
    if orphans:
        raise ValueError(f"vocabulary_{lang}.toml: [not_in] names unknown terms {sorted(orphans)}")
    return tuple(entries)


def is_hard(entry: VocabularyEntry, lang: str) -> bool:
    """Whether code may explain the term on its own: an abbreviation, a phrase, or a
    word rarer than everyday words."""
    if entry.abbreviation or " " in entry.term or "-" in entry.term:
        return True
    return zipf(entry.term.lower(), lang) < HARD_ZIPF


def rarity(entry: VocabularyEntry, lang: str) -> float:
    """How common the term is, for "the rarest first": abbreviations and phrases count
    as rare (0), a word by its Zipf frequency."""
    if entry.abbreviation or " " in entry.term or "-" in entry.term:
        return 0.0
    return zipf(entry.term.lower(), lang)


@lru_cache
def vocabulary_version(lang: str) -> str | None:
    """A short hash of the vocabulary file, recorded with every job that used it."""
    if not has_vocabulary(lang):
        return None
    return hashlib.sha256(vocabulary_path(lang).read_bytes()).hexdigest()[:12]


_ARTICLE = re.compile(r"^(?:der|die|das|den|dem|des|le|la|les|l')\s*", re.IGNORECASE)


def explained_term(term: str, lang: str) -> VocabularyEntry | None:
    """The explain entry a hard term or glossary term names as a whole: Franchise,
    die Prämien·verbilligung, Invalidenversicherung (IV) through its IV. None for any
    other term and for the context-dependent entries."""
    if not has_vocabulary(lang):
        return None
    main = re.sub(r"\s*\([^)]*\)", "", term).strip()
    for text in (main, *re.findall(r"\(([^)]*)\)", term)):
        text = _ARTICLE.sub("", text.strip())
        if not text:
            continue
        for m in matcher(lang).find_text(text):
            entry = m.entry
            whole = m.start == 0 and m.end == len(text) and not m.partial
            if whole and entry.kind == "explain" and not entry.context:
                return entry
    return None


def prompt_words(
    lang: str,
    texts: Iterable[str],
    *,
    exclude: re.Pattern[str] | None = None,
    limit: int = 15,
) -> list[VocabularyEntry]:
    """The replace entries in the texts, in text order, for the write prompt's list of
    hard words with their everyday word: the context-dependent ones too (the writer sees
    the sentence), not a part of a hyphenated name, not what `exclude` matches (the
    role nouns: LEX-06 asks for Sie, not for an easier noun)."""
    if not has_vocabulary(lang):
        return []
    seen: dict[str, VocabularyEntry] = {}
    for matches in matcher(lang).find_texts(texts):
        for m in matches:
            entry = m.entry
            if entry.kind != "replace" or not entry.easy or m.partial:
                continue
            if exclude is not None and exclude.search(m.text):
                continue
            seen.setdefault(entry.term, entry)
    return list(seen.values())[:limit]


def easy_for(lang: str, abbreviation: str) -> str | None:
    """The full word for an abbreviation of the vocabulary (z. B. -> zum Beispiel)."""
    return _abbreviations(lang).get(_squeeze(abbreviation))


# -- matching -------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pattern:
    entry: VocabularyEntry
    words: tuple[frozenset[str], ...]  # the accepted forms of each word, normalised
    verbal: bool  # German: the last word is a verb that may stand anywhere in the sentence


class VocabularyMatcher:
    """The entries of one language, ready to be found in parsed text."""

    def __init__(self, lang: str) -> None:
        self.lang = lang
        self.entries = load_vocabulary(lang)

    @cached_property
    def _nlp(self):
        return pipeline(self.lang)

    @cached_property
    def _patterns(self) -> dict[str, list[_Pattern]]:
        """Word patterns by every accepted form of their first word."""
        words = [e for e in self.entries if not e.abbreviation]
        terms = [_without_reflexive(e.term) if self.lang == "fr" else e.term for e in words]
        index: dict[str, list[_Pattern]] = defaultdict(list)
        for entry, doc in zip(words, self._nlp.pipe(terms), strict=True):
            tokens = [t for t in doc if not t.is_space]
            forms = [self._accepted(t) for t in tokens]
            verbal = (
                self.lang == "de"
                and len(tokens) >= 2
                and bool(_GERMAN_INFINITIVE.fullmatch(tokens[-1].text))
            )
            pattern = _Pattern(entry, tuple(forms), verbal)
            for form in forms[0]:
                index[form].append(pattern)
        return index

    @cached_property
    def _regexes(self) -> list[tuple[VocabularyEntry, re.Pattern[str]]]:
        """Abbreviations and acronyms: as written, with an optional space after a dot."""
        out = []
        for entry in self.entries:
            if not entry.abbreviation:
                continue
            parts = entry.term.replace(". ", ".").split(".")
            body = r"\.\s?".join(re.escape(part) for part in parts)
            out.append((entry, re.compile(rf"(?<![\w.]){body}(?!\w)")))
        return out

    def _accepted(self, token: Token) -> frozenset[str]:
        """The forms a word of a term accepts: as written, and its lemma when that is
        the same word without its ending (prestations: prestation). Not a lemma of
        another word class: recourant (the appellant) is lemmatised as recourir, which
        would make every recourir an appellant."""
        word = _norm(token.text)
        forms = {word}
        lemma = _norm(token.lemma_)
        if lemma.isalpha() and len(lemma) >= _MIN_STEM and word.startswith(lemma):
            forms.add(lemma)
        return frozenset(forms)

    def _forms(self, token: Token) -> set[str]:
        """What a token of the text can stand for: as written, its lemma, its stem
        without a usual ending, the parts of a hyphenated word, a separable verb with its
        particle, and the base form of a contracted French function word."""
        surface = _norm(token.text)
        forms = self._word_forms(surface) | {_norm(token.lemma_)}
        if "-" in surface:
            for part in surface.split("-"):
                if len(part) >= _MIN_STEM:
                    forms |= self._word_forms(part)
        if self.lang == "de" and token.pos_ in ("VERB", "AUX"):
            for child in token.children:
                if child.dep_ == "svp":  # reichen ... ein
                    forms.add(_norm(child.text) + _norm(token.lemma_))
        for base, contracted in _FUNCTION_FORMS.get(self.lang, {}).items():
            if surface in contracted:
                forms.add(base)
        return forms

    def _word_forms(self, word: str) -> set[str]:
        """A normalised word and its stems without a usual ending (Fristen: frist)."""
        forms = {word}
        for ending in _ENDINGS.get(self.lang, ()):
            if word.endswith(ending) and len(word) - len(ending) >= _MIN_STEM:
                forms.add(word[: -len(ending)])
        return forms

    def find(self, doc: Doc | Span) -> list[Match]:
        """The entries in a parsed text, in text order, the longest of overlapping
        matches only. Offsets are relative to the start of `doc`."""
        offset = doc.start_char if hasattr(doc, "start_char") and doc.start_char else 0
        text = doc.text
        found: list[Match] = []
        sentences = list(doc.sents) if _has_sents(doc) else [doc]
        for sent in sentences:
            forms = [self._forms(t) for t in sent]
            for i, token_forms in enumerate(forms):
                candidates = {id(p): p for f in token_forms for p in self._patterns.get(f, ())}
                for pattern in candidates.values():
                    match = self._match_at(pattern, sent, forms, i, offset)
                    if match is not None:
                        found.append(match)
        for entry, regex in self._regexes:
            for m in regex.finditer(text):
                found.append(Match(entry, m.group(0), m.start(), m.end(), ((m.start(), m.end()),)))
        found = [m for m in found if not _hidden(m, text)]
        return _longest(found)

    def find_text(self, text: str) -> list[Match]:
        return self.find(self._nlp(text))

    def find_texts(self, texts: Iterable[str]) -> Iterator[list[Match]]:
        for doc in self._nlp.pipe(texts):
            yield self.find(doc)

    def _hyphen_part(self, token: Token, accepted: frozenset[str]) -> tuple[str, int, int] | None:
        """The part of a hyphenated word that matched, when the whole word did not:
        (text, start, end)."""
        surface = _norm(token.text)
        if "-" not in token.text or (self._word_forms(surface) | {_norm(token.lemma_)}) & accepted:
            return None
        position = token.idx
        for part in token.text.split("-"):
            if self._word_forms(_norm(part)) & accepted:
                return part, position, position + len(part)
            position += len(part) + 1
        return None

    def _match_at(
        self, pattern: _Pattern, sent: Span, forms: list[set[str]], i: int, offset: int
    ) -> Match | None:
        words = pattern.words[:-1] if pattern.verbal else pattern.words
        if i + len(words) > len(forms):
            return None
        if any(not (w & forms[i + k]) for k, w in enumerate(words)):
            return None
        first, last = sent[i], sent[i + len(words) - 1]
        parts = [sent[i : i + len(words)].text]
        start, end = first.idx, last.idx + len(last.text)
        partial = False
        if len(words) == 1 and not pattern.verbal:  # Rente in IV-Rente: only the part
            part = self._hyphen_part(first, words[0])
            if part is not None:
                parts, start, end = [part[0]], part[1], part[2]
                partial = True
        ranges = [(start, end)]
        particle = _separated_particle(first, words[0]) if len(words) == 1 else None
        if particle is not None:  # reichen ... ein
            parts.append(particle.text)
            ranges.append((particle.idx, particle.idx + len(particle.text)))
        if pattern.verbal:  # the verb anywhere else in the sentence: tritt ... in Kraft
            verb = next(
                (
                    sent[k]
                    for k in range(len(forms))
                    if not i <= k < i + len(words) and pattern.words[-1] & forms[k]
                ),
                None,
            )
            if verb is None:
                return None
            parts = [verb.text, *parts] if verb.idx < start else [*parts, verb.text]
            ranges.append((verb.idx, verb.idx + len(verb.text)))
        ranges = sorted((a - offset, b - offset) for a, b in ranges)
        start, end = ranges[0][0], max(b for _, b in ranges)
        return Match(pattern.entry, " ... ".join(parts), start, end, tuple(ranges), partial)


@lru_cache
def matcher(lang: str) -> VocabularyMatcher:
    return VocabularyMatcher(lang)


def find_terms(lang: str, doc: Doc | Span) -> list[Match]:
    """The vocabulary entries in a parsed text (see the module docstring)."""
    return matcher(lang).find(doc) if has_vocabulary(lang) else []


def office_words(
    matches: Iterable[Match], *, exclude: re.Pattern[str] | None = None
) -> Iterator[Match]:
    """The office words among the matches, for rules LEX-07 and LEX-07-FR: replace
    entries with an everyday word; not the context-dependent ones, not abbreviations
    (LEX-02), not a part of a hyphenated word (Abklärungs-Stelle, often a name) and not
    what `exclude` matches (the role nouns of LEX-06)."""
    for m in matches:
        entry = m.entry
        if entry.kind != "replace" or entry.context or entry.abbreviation or not entry.easy:
            continue
        if m.partial:
            continue
        if exclude is not None and exclude.search(m.text):
            continue
        yield m


def covered_offsets(matches: Iterable[Match], base: int = 0) -> set[int]:
    """The character offsets the matches cover, shifted by `base`."""
    return {base + x for m in matches for a, b in m.parts for x in range(a, b)}


# -- helpers --------------------------------------------------------------------------


def _norm(text: str) -> str:
    return text.replace(MEDIOPUNKT, "").lower()


def _squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _is_acronym(term: str) -> bool:
    """KVG, EL, LAMal, BehiG: no space, at least two capitals, nothing but letters."""
    return " " not in term and term.isalpha() and sum(c.isupper() for c in term) >= 2


def _without_reflexive(term: str) -> str:
    for pronoun in _REFLEXIVE:
        if term.startswith(pronoun):
            return term[len(pronoun) :]
    return term


def _separated_particle(token: Token, accepted: frozenset[str]) -> Token | None:
    """The particle of a German separable verb when only verb and particle together
    are the term: ein in "reichen das Gesuch ein" for einreichen."""
    if {_norm(token.text), _norm(token.lemma_)} & accepted:
        return None
    for child in token.children:
        if child.dep_ == "svp" and _norm(child.text) + _norm(token.lemma_) in accepted:
            return child
    return None


def _has_sents(doc: Doc | Span) -> bool:
    if hasattr(doc, "has_annotation"):  # a Doc
        return doc.has_annotation("SENT_START")
    return False  # a Span is taken as one sentence


def _hidden(match: Match, text: str) -> bool:
    """Whether the match stands inside a [not_in] phrase of its term."""
    lowered = text.lower()
    start, end = match.parts[0]
    for phrase in match.entry.not_in:
        for m in re.finditer(re.escape(phrase.lower()), lowered):
            if m.start() <= start and end <= m.end():
                return True
    return False


def _longest(matches: list[Match]) -> list[Match]:
    """Of overlapping matches the one with the most matched characters; the words
    between the parts of a separated verb do not count as covered."""
    kept: list[Match] = []

    def size(m: Match) -> int:
        return sum(b - a for a, b in m.parts)

    for m in sorted(matches, key=lambda m: (-size(m), m.start)):
        if any(a < d and c < b for k in kept for a, b in m.parts for c, d in k.parts):
            continue
        kept.append(m)
    return sorted(kept, key=lambda m: m.start)


@lru_cache
def _abbreviations(lang: str) -> dict[str, str]:
    return {
        _squeeze(e.term): e.easy
        for e in load_vocabulary(lang)
        if e.kind == "replace" and e.abbreviation and e.easy
    }
