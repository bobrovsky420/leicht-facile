"""Hard words for easy language, per language and national variety: an everyday word to
use instead, or a plain explanation for the glossary when the term has to stay.

The lists are rules/data/vocabulary_<name>.toml; their header says how to edit them.
They are the seed of the planned termbase: hard term, easy term, explanation. Every
function takes a language or a variety key (schemas.variety: `de` for Swiss German,
`de-DE`, `de-AT`). A key reads its language's file, shared by the varieties, and the
variety's own: `de` reads vocabulary_de.toml and vocabulary_de-CH.toml, `de-AT`
vocabulary_de.toml and vocabulary_de-AT.toml; French and Italian have one file each.
Every German file is written in the Swiss spelling (ss, never sharp s); for Germany and
Austria the loader renders terms and texts in their spelling with the table of
rules/data/spelling_de.toml (`standard_spelling`: Bundesstrasse, Bundesstraße).

`find_terms` finds the entries in a parsed text. A word matches in its inflected forms
(the lemma, the term with a usual ending: Verfügungen, versées, or an Italian form with
its ending swapped: decisioni, notificato), with its Mediopunkt (Prämien·verbilligung),
as a German separable verb (reichen ... ein for einreichen) and as a German verbal
phrase whose verb stands elsewhere in the sentence (tritt ... in Kraft); sharp s and ss
are the same letters (Maßnahme matches Massnahme). Abbreviations and acronyms match as
written, case and dots included, so the French "ai" is never the AI. A phrase of the
[not_in] table hides a term inside it (zur Verfügung stehen is no decision), and of
overlapping matches the longest wins (opposition à la poursuite over opposition).

The pipeline uses the lists in four places (docs/architecture.md §4): the fact sheet
gets the checked explanations, code adds missing glossary entries (rules/glossary.py),
rule LEX-07 flags the office words left in a draft, and the vocabulary round
rewrites them. The writer gets no list of office words: on the CSCS dev run of 7 October
2026 such a list made the 8B write more of them (docs/prompts.md).
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from functools import cached_property, lru_cache
from importlib import resources
from typing import TYPE_CHECKING, Literal

from leichtfacile.rules.lexicon import MEDIOPUNKT, zipf
from leichtfacile.rules.nlp import pipeline
from leichtfacile.schemas import base_lang, canonical_variety

if TYPE_CHECKING:
    from spacy.tokens import Doc, Span, Token

Kind = Literal["replace", "explain"]
KINDS: tuple[Kind, ...] = ("replace", "explain")
CONTEXT = "context"  # the group of words with a second, everyday sense
OFFICE_RULES = ("LEX-07",)  # the rule that flags the office words, in every language
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
# Italian inflects by changing the ending: an inflected form's ending and the endings
# of the base forms it may stand for (decisioni: decisione, premi: premio, rendite:
# rendita, notifica and notificato: notificare, rivolgersi: rivolgere). Verb endings
# only where they name the conjugation, so a bare -o (verso) is never a verb.
_ENDING_SWAPS: dict[str, dict[str, tuple[str, ...]]] = {
    "it": {
        "i": ("o", "e", "a", "io", "are"),
        "e": ("a", "o", "i", "ere", "ire"),
        "a": ("o", "e", "are", "ere"),
        "o": ("i",),
        "chi": ("co", "care"),
        "ghi": ("go",),
        "che": ("ca",),
        "ghe": ("ga",),
        "iamo": ("are", "ere", "ire"),
        "erà": ("are", "ere"),
        "rsi": ("re",),
        **dict.fromkeys(("ano", "ato", "ata", "ati", "ate", "ando"), ("are",)),
        **dict.fromkeys(("uto", "uta", "uti", "ute"), ("ere",)),
        **dict.fromkeys(("ono", "endo"), ("ere", "ire")),
        **dict.fromkeys(("ito", "ita", "iti", "ite", "isce", "isca", "iscono", "irà"), ("ire",)),
    },
}
# Function words in their contracted and elided forms: dans le cadre du, ai sensi della.
_FUNCTION_FORMS = {
    "fr": {
        "de": {"d'", "du", "des"},
        "à": {"au", "aux"},
        "le": {"la", "les", "l'"},
        "la": {"le", "les", "l'"},
    },
    "it": {
        "di": {"d'", "del", "dello", "della", "dell'", "dei", "degli", "delle"},
        "d'": {"di"},
        "a": {"al", "allo", "alla", "all'", "ai", "agli", "alle"},
        "da": {"dal", "dallo", "dalla", "dall'", "dai", "dagli", "dalle"},
        "in": {"nel", "nello", "nella", "nell'", "nei", "negli", "nelle"},
        "su": {"sul", "sullo", "sulla", "sull'", "sui", "sugli", "sulle"},
    },
}
_REFLEXIVE = ("s'", "se ")  # French verbs listed with their pronoun: s'acquitter de
_REFLEXIVE_IT = re.compile(r"^(\w{3,}[aei])rsi\b")  # Italian: the pronoun at the end, rivolgersi a
_GERMAN_INFINITIVE = re.compile(r"[a-zäöüß]+(?:en|ern|eln)")
_DATA = resources.files("leichtfacile.rules") / "data"
# The varieties that write sharp s: their vocabulary is rendered with the table of
# rules/data/spelling_de.toml at load time.
SHARP_S_VARIETIES = frozenset({"de-DE", "de-AT"})
_SPELLING = _DATA / "spelling_de.toml"


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


def _vocabulary_path(name: str):
    return _DATA / f"vocabulary_{name}.toml"


@lru_cache
def vocabulary_files(key: str) -> tuple[str, ...]:
    """The names of the files a language or variety key reads, in this order: the
    language's, shared by its varieties (`de`), and the variety's own (`de-CH`, also for
    the bare `de`; `de-AT`); French and Italian have the first alone."""
    lang = base_lang(key)
    return tuple(
        name for name in (lang, canonical_variety(key)) if _vocabulary_path(name).is_file()
    )


def has_vocabulary(key: str) -> bool:
    return bool(vocabulary_files(key))


@lru_cache
def read_vocabulary(name: str) -> tuple[VocabularyEntry, ...]:
    """One file as written, rules/data/vocabulary_<name>.toml (`de`, `de-CH`, `fr`, ...):
    its entries in file order and in its own spelling. A term's [not_in] phrases stand
    in the term's file."""
    file = f"vocabulary_{name}.toml"
    data = tomllib.loads(_vocabulary_path(name).read_text(encoding="utf-8"))
    unknown = set(data) - {*KINDS, "not_in"}
    if unknown:
        raise ValueError(f"{file}: unknown tables {sorted(unknown)}")
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
        raise ValueError(f"{file}: [not_in] names unknown terms {sorted(orphans)}")
    return tuple(entries)


@lru_cache
def load_vocabulary(key: str) -> tuple[VocabularyEntry, ...]:
    """The entries of a language or variety key: its files in the order of
    `vocabulary_files`, in the spelling of Germany and Austria for their keys."""
    entries = [e for name in vocabulary_files(key) for e in read_vocabulary(name)]
    if key in SHARP_S_VARIETIES:
        entries = [_in_standard_spelling(e) for e in entries]
    return tuple(entries)


def is_hard(entry: VocabularyEntry, key: str) -> bool:
    """Whether code may explain the term on its own: an abbreviation, a phrase, or a
    word rarer than everyday words."""
    if entry.abbreviation or " " in entry.term or "-" in entry.term:
        return True
    return zipf(entry.term.lower(), base_lang(key)) < HARD_ZIPF


def rarity(entry: VocabularyEntry, key: str) -> float:
    """How common the term is, for "the rarest first": abbreviations and phrases count
    as rare (0), a word by its Zipf frequency."""
    if entry.abbreviation or " " in entry.term or "-" in entry.term:
        return 0.0
    return zipf(entry.term.lower(), base_lang(key))


@lru_cache
def vocabulary_version(key: str) -> str | None:
    """A short hash of the files the key reads, in their order and with the spelling
    table last for Germany and Austria, recorded with every job that used them. A key
    of one file (French, Italian) keeps the hash of that file alone."""
    paths = [_vocabulary_path(name) for name in vocabulary_files(key)]
    if not paths:
        return None
    if key in SHARP_S_VARIETIES:
        paths.append(_SPELLING)
    return hashlib.sha256(b"".join(p.read_bytes() for p in paths)).hexdigest()[:12]


# -- spelling -------------------------------------------------------------------------


@lru_cache
def _sharp_s() -> tuple[re.Pattern[str], dict[str, str]]:
    """The stems of rules/data/spelling_de.toml as one pattern, the longest first, so a
    stem written as it is (fussel) wins over a shorter one inside it (fuss)."""
    data = tomllib.loads(_SPELLING.read_text(encoding="utf-8"))
    table = {stem.lower(): standard for stem, standard in data["sharp_s"].items()}
    stems = sorted(table, key=len, reverse=True)
    return re.compile("|".join(re.escape(stem) for stem in stems), re.IGNORECASE), table


def standard_spelling(text: str) -> str:
    """A Swiss text in the spelling of Germany and Austria: sharp s for the ss of the
    stems in rules/data/spelling_de.toml, also inside a word (Bundesstrasse:
    Bundesstraße, gemässe: gemäße), with the case of the first letter kept. The words
    the table leaves out as ambiguous (Masse, Busse) and words in capitals stay."""
    pattern, table = _sharp_s()

    def standard(m: re.Match[str]) -> str:
        found = m.group(0)
        if found.isupper():
            return found
        out = table[found.lower()]
        return out[:1].upper() + out[1:] if found[:1].isupper() else out

    return pattern.sub(standard, text)


def _in_standard_spelling(entry: VocabularyEntry) -> VocabularyEntry:
    def standard(text: str | None) -> str | None:
        return standard_spelling(text) if text else text

    return replace(
        entry,
        term=standard_spelling(entry.term),
        easy=standard(entry.easy),
        explanation=standard(entry.explanation),
        not_in=tuple(standard_spelling(phrase) for phrase in entry.not_in),
    )


# A leading article of a glossary term: a word article needs a space after it (`le` in
# `legge` and `Le` in `Lebensbedarf` are no articles; found 28 October 2026), the
# elided l' none.
_ARTICLE = re.compile(
    r"^(?:(?:der|die|das|den|dem|des|le|la|les|il|lo|i|gli)\s+|l')", re.IGNORECASE
)


# The hyphen as the compound mark of Germany and Austria (Familien-Beihilfe, docs/rules.md
# LEX-01): a small letter, the hyphen, a capital and a small letter; never E-Mail, IV-Rente.
_HYPHEN_MARK_RE = re.compile(r"(?<=[a-zäöüß])-(?=[A-ZÄÖÜ][a-zäöüß])")


def explained_term(term: str, key: str) -> VocabularyEntry | None:
    """The explain entry a hard term or glossary term names as a whole: Franchise,
    die Prämien·verbilligung, Invalidenversicherung (IV) through its IV. None for any
    other term and for the context-dependent entries. The compound mark does not count:
    the matcher drops the Mediopunkt, and a glossary term the model copied from a
    hyphenated draft (Familien-Beihilfe, Austria) is tried without the hyphen too."""
    if not has_vocabulary(key):
        return None
    main = re.sub(r"\s*\([^)]*\)", "", term).strip()
    for text in (main, *re.findall(r"\(([^)]*)\)", term)):
        text = _ARTICLE.sub("", text.strip())
        if not text:
            continue
        for candidate in dict.fromkeys((text, _HYPHEN_MARK_RE.sub("", text))):
            for m in matcher(key).find_text(candidate):
                entry = m.entry
                whole = m.start == 0 and m.end == len(candidate) and not m.partial
                if whole and entry.kind == "explain" and not entry.context:
                    return entry
    return None


def easy_for(key: str, abbreviation: str) -> str | None:
    """The full word for an abbreviation of the vocabulary (z. B. -> zum Beispiel)."""
    return _abbreviations(key).get(_squeeze(abbreviation))


# -- matching -------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pattern:
    entry: VocabularyEntry
    words: tuple[frozenset[str], ...]  # the accepted forms of each word, normalised
    verbal: bool  # German: the last word is a verb that may stand anywhere in the sentence


class VocabularyMatcher:
    """The entries of one language or variety, ready to be found in parsed text."""

    def __init__(self, key: str) -> None:
        self.key = key
        self.lang = base_lang(key)  # the spaCy pipeline and the inflection rules
        self.entries = load_vocabulary(key)

    @cached_property
    def _nlp(self):
        return pipeline(self.lang)

    @cached_property
    def _patterns(self) -> dict[str, list[_Pattern]]:
        """Word patterns by every accepted form of their first word."""
        words = [e for e in self.entries if not e.abbreviation]
        terms = [_without_reflexive(e.term, self.lang) for e in words]
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
        particle, and the base form of a contracted function word (du, della)."""
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
        """A normalised word, its stems without a usual ending (Fristen: frist) and its
        base forms with the ending swapped (decisioni: decisione)."""
        forms = {word}
        for ending in _ENDINGS.get(self.lang, ()):
            if word.endswith(ending) and len(word) - len(ending) >= _MIN_STEM:
                forms.add(word[: -len(ending)])
        for ending, bases in _ENDING_SWAPS.get(self.lang, {}).items():
            if word.endswith(ending) and len(word) - len(ending) >= _MIN_STEM:
                forms.update(word[: -len(ending)] + base for base in bases)
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
def matcher(key: str) -> VocabularyMatcher:
    return VocabularyMatcher(key)


def find_terms(key: str, doc: Doc | Span) -> list[Match]:
    """The vocabulary entries in a parsed text (see the module docstring)."""
    return matcher(key).find(doc) if has_vocabulary(key) else []


def office_words(
    matches: Iterable[Match], *, exclude: re.Pattern[str] | None = None
) -> Iterator[Match]:
    """The office words among the matches, for rule LEX-07: replace
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
    """A word for matching: without its Mediopunkt and case-folded, which also makes
    sharp s ss (Maßnahme: massnahme)."""
    return text.replace(MEDIOPUNKT, "").casefold()


def _squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _is_acronym(term: str) -> bool:
    """KVG, EL, LAMal, BehiG: no space, at least two capitals, nothing but letters."""
    return " " not in term and term.isalpha() and sum(c.isupper() for c in term) >= 2


def _without_reflexive(term: str, lang: str) -> str:
    """The term without its reflexive pronoun, which the text puts elsewhere (vous vous
    acquittez de, Lei si rivolge a): s'acquitter de is listed as acquitter de,
    rivolgersi a as rivolgere a."""
    if lang == "fr":
        for pronoun in _REFLEXIVE:
            if term.startswith(pronoun):
                return term[len(pronoun) :]
    if lang == "it":
        return _REFLEXIVE_IT.sub(r"\1re", term)
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
    start, end = match.parts[0]
    for phrase in match.entry.not_in:
        for m in _phrase_pattern(phrase).finditer(text):
            if m.start() <= start and end <= m.end():
                return True
    return False


@lru_cache(maxsize=1024)
def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """A [not_in] phrase in any case, with ss and sharp s alike (Bescheid weiss)."""
    return re.compile(re.escape(phrase.casefold()).replace("ss", "(?:ss|ß)"), re.IGNORECASE)


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
def _abbreviations(key: str) -> dict[str, str]:
    return {
        _squeeze(e.term): e.easy
        for e in load_vocabulary(key)
        if e.kind == "replace" and e.abbreviation and e.easy
    }
