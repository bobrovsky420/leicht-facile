"""The `morphit` pipeline component: lemma, part of speech and morphology from the
Morph-it! lexicon (Eros Zanchetta and Marco Baroni, University of Bologna, version
0.4.8), the tagger of the Italian checker. scripts/lexicon_package.py bundles this
file into the package leichtfacile_model_it, whose `__init__` imports it, so the
factory is registered when the package is loaded; the app never imports it itself.

Morph-it! lists every inflected form with its lemma and a tag such as
`VER:ind+pres+3+s`, `NOUN-M:s`, `ADJ:pos+f+p` or `PRO-PERS-CLI-3-F-S`. A form can have
several readings: `compili` is an indicative and three subjunctives, `la` an article
and a pronoun, `franchi` a noun, an adjective and a verb. The component keeps every
reading in `token._.readings`, a tuple of (lemma, tag), so a rule can require a form
whose readings agree, and sets one reading as `lemma_`, `tag_` (the Morph-it! tag),
`pos_` (Universal Dependencies) and `morph` (UD features), chosen by a few context
rules: after an article, a determiner or a number a noun or adjective reading wins;
a closed-class reading (preposition, conjunction, article, pronoun) wins over an
open-class one (secondo is a preposition before it is a verb); an article wins over a
clitic pronoun before a noun; after a finite auxiliary a participle or infinitive wins;
essere, avere, venire and stare are AUX before a participle, an infinitive or a gerund
and VERB otherwise; among finite verb readings the indicative wins over the imperative,
the subjunctive and the conditional. A word the lexicon lacks keeps empty attributes
and no readings; numbers and punctuation get NUM and PUNCT.
"""

from __future__ import annotations

import re
import struct
from collections.abc import Iterable
from pathlib import Path

import srsly
from spacy.language import Language
from spacy.tokens import Doc, Token

COMPONENT = "morphit"
LEXICON_FILE = "lexicon.msgpack"
_PAIR = struct.Struct("<II")

if not Token.has_extension("readings"):
    Token.set_extension("readings", default=())

# The first part of a Morph-it! tag to the UD part of speech.
_POS = {
    "VER": "VERB", "MOD": "VERB", "ASP": "VERB", "CAU": "VERB", "AUX": "AUX",
    "NOUN": "NOUN", "NPR": "PROPN", "ADJ": "ADJ", "ADV": "ADV", "ART": "DET",
    "ARTPRE": "ADP", "DET": "DET", "PRO": "PRON", "PRE": "ADP", "CON": "CCONJ",
    "INT": "INTJ", "ABL": "X", "SMI": "SYM", "SYM": "SYM", "PON": "PUNCT",
    "SENT": "PUNCT", "WH": "PRON", "NE": "PRON", "CE": "PRON", "CI": "PRON",
    "SI": "PRON", "TALE": "DET",
}  # fmt: skip
_VERB_TAGS = frozenset({"VER", "MOD", "ASP", "CAU", "AUX"})
_CLOSED_TAGS = frozenset(
    {"PRE", "CON", "ART", "ARTPRE", "DET", "PRO", "WH", "NE", "CE", "CI", "SI", "TALE", "INT"}
)
# Conjunctions that open a subordinate clause (the rest of CON are coordinating).
_SUBORDINATING = frozenset(
    {"che", "se", "perché", "poiché", "siccome", "affinché", "benché", "sebbene", "qualora",
     "purché", "quando", "mentre", "finché", "nonostante", "malgrado", "dopoché", "giacché",
     "quantunque", "ancorché", "laddove", "ove", "onde", "come", "quanto", "appena"}
)  # fmt: skip
_MOOD = {"ind": "Ind", "sub": "Sub", "cond": "Cnd", "impr": "Imp"}
_TENSE = {"pres": "Pres", "impf": "Imp", "past": "Past", "fut": "Fut"}
_NUMBER = {"s": "Sing", "p": "Plur", "S": "Sing", "P": "Plur"}
_GENDER = {"m": "Masc", "f": "Fem", "M": "Masc", "F": "Fem"}
_DEGREE = {"pos": "Pos", "comp": "Cmp", "sup": "Sup"}
_MOOD_RANK = {"ind": 0, "impr": 1, "sub": 2, "cond": 3, "inf": 4, "ger": 5, "part": 6}
_AUX_LEMMAS = frozenset({"essere", "avere", "venire", "stare"})
# The words lo and gli take as an article: s plus consonant, z, gn, ps, pn, x, y, i
# plus vowel; l' takes a vowel (and a mute h).
_LO_ARTICLE_RE = re.compile(r"^(?:s[^aeiouàèéìòù\W\d_]|z|gn|ps|pn|x|y|i[aeiou])", re.IGNORECASE)
_VOWEL_RE = re.compile(r"^[aeiouàèéìòùh]", re.IGNORECASE)
_DETERMINERS = frozenset(
    {"il", "lo", "la", "i", "gli", "le", "l'", "un", "uno", "una", "un'", "questo", "questa",
     "questi", "queste", "quel", "quello", "quella", "quei", "quegli", "quelle", "mio", "mia",
     "tuo", "tua", "suo", "sua", "suoi", "sue", "nostro", "nostra", "vostro", "vostra", "ogni",
     "del", "dello", "della", "dell'", "dei", "degli", "delle", "al", "allo", "alla", "all'",
     "ai", "agli", "alle", "nel", "nella", "nello", "nei", "negli", "nelle"}
)  # fmt: skip
_SKIPPED = frozenset(
    {"non", "già", "ancora", "anche", "sempre", "mai", "più", "appena", "subito", "solo",
     "soltanto", "stato", "stata", "stati", "state", "lo", "la", "li", "le", "gli", "ne",
     "ci", "vi", "mi", "ti", "si"}
)  # fmt: skip


def coarse(tag: str) -> str:
    """`VER` of `VER:ind+pres+3+s`, `PRO` of `PRO-PERS-CLI-3-F-S`, `NOUN` of `NOUN-M:s`."""
    return tag.split(":", 1)[0].split("-", 1)[0]


def is_verb_tag(tag: str) -> bool:
    return coarse(tag) in _VERB_TAGS


def verb_form(tag: str) -> str:
    """`ind`, `sub`, `cond`, `impr`, `inf`, `ger` or `part` of a verb tag, else ""."""
    if not is_verb_tag(tag) or ":" not in tag:
        return ""
    return tag.split(":", 1)[1].split("+", 1)[0]


def pos_of(tag: str, text: str = "") -> str:
    head, _, _ = tag.partition(":")
    parts = head.split("-")
    if "NUM" in parts:
        return "NUM"
    if parts[0] == "CON":
        return "SCONJ" if text.lower() in _SUBORDINATING else "CCONJ"
    return _POS.get(parts[0], "X")


def morph_of(tag: str) -> str:
    """The UD features of a Morph-it! tag as `Mood=Ind|Number=Sing|...`."""
    head, _, feats = tag.partition(":")
    parts = head.split("-")
    values = feats.split("+") if feats else []
    out: dict[str, str] = {}
    if parts[0] in _VERB_TAGS and values:
        form, rest = values[0], values[1:]
        if form in _MOOD:
            out["VerbForm"] = "Fin"
            out["Mood"] = _MOOD[form]
        elif form == "inf":
            out["VerbForm"] = "Inf"
        elif form == "ger":
            out["VerbForm"] = "Ger"
        elif form == "part":
            out["VerbForm"] = "Part"
        if rest and rest[0] in _TENSE:
            out["Tense"] = _TENSE[rest[0]]
            rest = rest[1:]
        if form in _MOOD:
            if rest and rest[0] in ("1", "2", "3"):
                out["Person"] = rest[0]
                rest = rest[1:]
            if rest and rest[0] in _NUMBER:
                out["Number"] = _NUMBER[rest[0]]
                rest = rest[1:]
        elif form == "part":
            if rest and rest[0] in _NUMBER:
                out["Number"] = _NUMBER[rest[0]]
                rest = rest[1:]
            if rest and rest[0] in _GENDER:
                out["Gender"] = _GENDER[rest[0]]
                rest = rest[1:]
        if rest:
            out["Clitic"] = "Yes"
    elif parts[0] == "ADJ" and values:
        if values[0] in _DEGREE:
            out["Degree"] = _DEGREE[values[0]]
        for v in values[1:]:
            if v in _GENDER:
                out["Gender"] = _GENDER[v]
            elif v in _NUMBER:
                out["Number"] = _NUMBER[v]
    else:
        for part in parts[1:]:
            if part in ("1", "2", "3"):
                out["Person"] = part
            elif part in _GENDER:
                out["Gender"] = _GENDER[part]
            elif part in _NUMBER:
                out["Number"] = _NUMBER[part]
            elif part == "CLI":
                out["Clitic"] = "Yes"
        for v in values:
            if v in _GENDER:
                out["Gender"] = _GENDER[v]
            elif v in _NUMBER:
                out["Number"] = _NUMBER[v]
    return "|".join(f"{k}={v}" for k, v in sorted(out.items()))


class MorphitLexicon:
    """The component: the lexicon as `form -> packed (lemma index, tag index) pairs`,
    with the lemmas and tags in two lists, read from `lexicon.msgpack`."""

    def __init__(self, nlp: Language, name: str = COMPONENT) -> None:
        self.name = name
        self._lemmas: list[str] = []
        self._tags: list[str] = []
        self._forms: dict[str, bytes] = {}

    # -- the lexicon -----------------------------------------------------------------

    def load_tsv(self, path: Path | str) -> None:
        """Read Morph-it!'s text file: form, lemma, tag, tab-separated, UTF-8."""
        lemma_index: dict[str, int] = {}
        tag_index: dict[str, int] = {}
        pairs: dict[str, list[int]] = {}
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) != 3 or not parts[0]:
                continue
            form, lemma, tag = parts
            li = lemma_index.setdefault(lemma, len(lemma_index))
            ti = tag_index.setdefault(tag, len(tag_index))
            pairs.setdefault(form, []).extend((li, ti))
        self._lemmas = list(lemma_index)
        self._tags = list(tag_index)
        self._forms = {
            form: struct.pack(f"<{len(flat)}I", *flat) for form, flat in sorted(pairs.items())
        }

    def __len__(self) -> int:
        return len(self._forms)

    def readings(self, text: str) -> tuple[tuple[str, str], ...]:
        """Every reading of a form as (lemma, tag): as written, else in lower case."""
        key = text.replace("’", "'")
        packed = self._forms.get(key)
        if packed is None and key != key.lower():
            packed = self._forms.get(key.lower())
        if packed is None:
            return ()
        return tuple((self._lemmas[li], self._tags[ti]) for li, ti in _PAIR.iter_unpack(packed))

    # -- the pipeline component -----------------------------------------------------

    def __call__(self, doc: Doc) -> Doc:
        for i, token in enumerate(doc):
            rs = self.readings(token.text)
            token._.readings = rs
            if not rs:
                if token.is_punct:
                    token.pos_ = "PUNCT"
                elif token.like_num:
                    token.pos_ = "NUM"
                continue
            lemma, tag = self._choose(rs, doc, i)
            token.lemma_ = lemma
            token.tag_ = tag
            token.pos_ = self._pos(lemma, tag, doc, i)
            token.set_morph(morph_of(tag) or None)
        return doc

    def _choose(self, rs: tuple[tuple[str, str], ...], doc: Doc, i: int) -> tuple[str, str]:
        if len(rs) == 1:
            return rs[0]
        prev = doc[i - 1] if i > 0 else None
        groups = {coarse(tag) for _, tag in rs}
        if prev is not None and (
            prev.tag_.startswith(("ART", "DET")) or prev.pos_ == "NUM" or prev.like_num
        ):
            for wanted in ("NOUN", "ADJ", "NPR"):
                if wanted in groups:
                    return next(r for r in rs if coarse(r[1]) == wanted)
        if prev is not None and prev.pos_ == "AUX":
            after_aux = [r for r in rs if verb_form(r[1]) in ("part", "inf", "ger")]
            if after_aux:
                return after_aux[0]
        if "ART" in groups and "PRO" in groups:
            wanted = "ART" if self._article(doc, i) else "PRO"
            return next(r for r in rs if coarse(r[1]) == wanted)
        return min(rs, key=_rank)

    def _article(self, doc: Doc, i: int) -> bool:
        """Whether the article reading of la, le, lo, gli or l' fits: the next word
        takes that form of the article (lo only before s plus consonant, z, gn, ps, x
        and y, l' only before a vowel, la never before one) and reads as a noun, not as
        a verb with its object ("lo invii", "Le invii il modulo")."""
        nxt = doc[i + 1] if i + 1 < len(doc) else None
        if nxt is None or nxt.is_punct:
            return False
        form = doc[i].text.lower().replace("’", "'")
        text = nxt.text
        if form == "lo" and not _LO_ARTICLE_RE.match(text):
            return False
        if form == "l'" and not _VOWEL_RE.match(text):
            return False
        if form == "la" and _VOWEL_RE.match(text):
            return False
        if form == "gli" and not (_VOWEL_RE.match(text) or _LO_ARTICLE_RE.match(text)):
            return False
        next_groups = {coarse(tag) for _, tag in self.readings(text)}
        if not next_groups:
            return True  # a word the lexicon lacks is a noun more often than not
        verbal = bool(next_groups & _VERB_TAGS)
        nominal = bool(next_groups & {"NOUN", "ADJ", "NPR"})
        if verbal and nominal and i + 2 < len(doc):
            after = doc[i + 2].text.lower().replace("’", "'")
            if after in _DETERMINERS:
                return False  # "lo invii il modulo": a verb with its object
        return nominal

    def _pos(self, lemma: str, tag: str, doc: Doc, i: int) -> str:
        pos = pos_of(tag, doc[i].text)
        if lemma in _AUX_LEMMAS and pos in ("AUX", "VERB"):
            for nxt in doc[i + 1 : i + 5]:
                if nxt.is_punct:
                    break
                if nxt.text.lower() in _SKIPPED:
                    continue
                forms = {verb_form(tag) for _, tag in self.readings(nxt.text)}
                return "AUX" if forms & {"part", "inf", "ger"} else "VERB"
            return "VERB"
        return pos

    # -- serialisation ----------------------------------------------------------------

    def _data(self) -> dict:
        return {"lemmas": self._lemmas, "tags": self._tags, "forms": self._forms}

    def _load(self, data: dict) -> None:
        self._lemmas, self._tags, self._forms = data["lemmas"], data["tags"], data["forms"]

    def to_disk(self, path: Path | str, *, exclude: Iterable[str] = ()) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        srsly.write_msgpack(path / LEXICON_FILE, self._data())

    def from_disk(self, path: Path | str, *, exclude: Iterable[str] = ()) -> MorphitLexicon:
        self._load(srsly.read_msgpack(Path(path) / LEXICON_FILE))
        return self

    def to_bytes(self, *, exclude: Iterable[str] = ()) -> bytes:
        return srsly.msgpack_dumps(self._data())

    def from_bytes(self, data: bytes, *, exclude: Iterable[str] = ()) -> MorphitLexicon:
        self._load(srsly.msgpack_loads(data))
        return self


def _rank(reading: tuple[str, str]) -> tuple[int, int]:
    """Closed-class readings first, then verbs (indicative before the other moods),
    nouns, adjectives, proper nouns, the rest."""
    tag = reading[1]
    head = coarse(tag)
    if head in _CLOSED_TAGS:
        return (0, 0)
    if head in _VERB_TAGS:
        return (1, _MOOD_RANK.get(verb_form(tag), 9))
    return ({"NOUN": 2, "ADJ": 3, "NPR": 4}.get(head, 5), 0)


@Language.factory(COMPONENT)
def create_morphit(nlp: Language, name: str) -> MorphitLexicon:
    return MorphitLexicon(nlp, name)
