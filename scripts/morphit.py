"""The `morphit` pipeline component: lemma, part of speech and morphology from the
Morph-it! lexicon (Eros Zanchetta and Marco Baroni, University of Bologna, version
0.4.8), the tagger of the Italian checker. scripts/lexicon_package.py bundles this
file into the package leichtfacile_model_it, whose `__init__` imports it, so the
factory is registered when the package is loaded; the app never imports it itself.

Morph-it! lists every inflected form with its lemma and a tag such as
`VER:ind+pres+3+s`, `NOUN-M:s`, `ADJ:pos+f+p` or `PRO-PERS-CLI-3-F-S`. A form can have
several readings: `compili` is an indicative and three subjunctives, `la` an article
and a pronoun, `legge` the law and reads, `ancora` still and anchors. The component
keeps every reading in `token._.readings`, a tuple of (lemma, tag), so a rule can
require a form whose readings agree, and sets one reading as `lemma_`, `tag_` (the
Morph-it! tag), `pos_` (Universal Dependencies) and `morph` (UD features), chosen by
the context rules of `_choose`, written for official texts: an article wins over a
clitic pronoun before a noun phrase, a possessive and after a preposition; a
closed-class reading wins over an open-class one (dei is the preposition, not the
gods; secondo the preposition before the verb), except that sei is the verb unless an
article, a preposition, a plural noun or punctuation marks the number (alle sei, sei
mesi); an adverb wins over a verb (ancora, ora, meno); a word
whose verb readings are all first person is a noun or an adjective (lavoro, incasso,
preciso); after an article, a determiner, a possessive, a demonstrative, a number, a
preposition, a prenominal adjective or a verb a noun or adjective reading wins over a
finite verb reading (allo stesso ufficio, un nuovo salario, definire compiti), the
adjective when a noun follows; at the start of a sentence a noun reading wins when a
noun phrase follows (Uffici cantonali, Aspetti della vita), unless the word is a polite
imperative before an article, an a-preposition or per with an infinitive (Telefoni al
numero, Compili il modulo); after a noun an adjective that agrees with it
wins (una somma fissa, but il Comune paga), a verb reading that is only second
person loses to the noun (cassa pensioni), and so does a past participle that does
not agree with the noun (Ufficio rette); after a noun and e or o a word without a
third-person indicative reading is a noun too (gradini e ostacoli); after an
auxiliary a past participle, an
infinitive or a gerund wins (è stato, ha pagato, deve essere inviato), not a present
participle (è importante stays an adjective); essere, avere, venire and stare are AUX
before such a form and VERB otherwise; among finite verb readings the indicative wins
over the imperative, the subjunctive and the conditional. A word the lexicon lacks
keeps empty attributes and no readings; numbers and punctuation get NUM and PUNCT.
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
_NOMINAL_TAGS = frozenset({"NOUN", "ADJ", "NPR"})
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
# Tags that open a noun phrase: articles, determiners, possessives, demonstratives and
# indefinites (questa somma, lo stesso ufficio, ogni mese).
_DETERMINER_PREFIXES = ("ART", "DET", "PRO-POSS", "PRO-DEMO", "PRO-INDEF")
_A_PREPOSITIONS = frozenset({"a", "ad", "al", "allo", "alla", "all'", "ai", "agli", "alle"})
_PLAIN_ARTICLES = frozenset({"il", "lo", "la", "i", "gli", "le", "l'", "un", "uno", "una", "un'"})
# The words lo and gli take as an article: s plus consonant, z, gn, ps, pn, x, y, i
# plus vowel; l' takes a vowel (and a mute h).
_LO_ARTICLE_RE = re.compile(r"^(?:s[^aeiouàèéìòù\W\d_]|z|gn|ps|pn|x|y|i[aeiou])", re.IGNORECASE)
_VOWEL_RE = re.compile(r"^[aeiouàèéìòùh]", re.IGNORECASE)
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


def is_finite_tag(tag: str) -> bool:
    return verb_form(tag) in ("ind", "sub", "cond", "impr")


def _third_person(finite: list[str]) -> bool:
    """Whether a third-person indicative reading is among the finite verb tags."""
    return any(verb_form(t) == "ind" and _person(t) == "3" for t in finite)


def _person(tag: str) -> str:
    """The person of a finite verb tag ("1", "2", "3"), else ""."""
    if not is_finite_tag(tag):
        return ""
    parts = tag.split(":", 1)[1].split("+")
    return parts[2] if len(parts) > 2 and parts[2] in ("1", "2", "3") else ""


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


def _features(tag: str) -> tuple[str, str]:
    """(gender, number) of a tag's morphology, "" where it has none."""
    feats = dict(f.split("=") for f in morph_of(tag).split("|") if "=" in f)
    return feats.get("Gender", ""), feats.get("Number", "")


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

    def _groups(self, token: Token | None) -> set[str]:
        return {coarse(tag) for _, tag in self.readings(token.text)} if token is not None else set()

    def _nominal(self, token: Token | None) -> bool:
        """The token can be a noun, an adjective or a name, or is a number."""
        if token is None:
            return False
        return token.like_num or bool(self._groups(token) & _NOMINAL_TAGS)

    def _noun_follows(self, token: Token | None) -> bool:
        """The token reads as a noun phrase's noun and not as a third-person verb: salario
        after "un nuovo", but not paga after "il Comune"."""
        if not self._nominal(token):
            return False
        return not any(_person(tag) == "3" for _, tag in self.readings(token.text))

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
        groups = {coarse(tag) for _, tag in rs}
        if "ART" in groups and "PRO" in groups:
            wanted = "ART" if self._article(doc, i) else "PRO"
            return next(r for r in rs if coarse(r[1]) == wanted)
        if doc[i].text.lower() == "sei" and groups & _VERB_TAGS:
            wanted = ("DET", "PRO") if self._number_sei(doc, i) else tuple(_VERB_TAGS)
            return min((r for r in rs if coarse(r[1]) in wanted), key=_rank)
        if groups & _CLOSED_TAGS:
            return min(rs, key=_rank)  # dei: the preposition, not the gods
        prev = doc[i - 1] if i > 0 and not doc[i - 1].is_punct else None
        prev2 = doc[i - 2] if prev is not None and i > 1 and not doc[i - 2].is_punct else None
        nxt = doc[i + 1] if i + 1 < len(doc) else None
        determiner = prev is not None and (
            prev.tag_.startswith(_DETERMINER_PREFIXES) or prev.pos_ == "NUM" or prev.like_num
        )
        if "ADV" in groups and not determiner:
            return next(r for r in rs if coarse(r[1]) == "ADV")  # ancora, ora, meno
        finite = [tag for _, tag in rs if is_finite_tag(tag)]
        non_finite = [r for r in rs if verb_form(r[1]) in ("inf", "ger") or ":part+past" in r[1]]
        nominal_groups = groups & _NOMINAL_TAGS
        first_person_only = bool(finite) and all(_person(t) == "1" for t in finite)
        if nominal_groups and first_person_only and not non_finite:
            return self._nominal_reading(rs, groups, nxt)  # lavoro, incasso, preciso
        if prev is None:
            # the start of a sentence or of a part: a noun phrase when one follows
            # (Uffici cantonali, Aspetti della vita), unless the word is a polite
            # imperative (Telefoni al numero, Compili il modulo)
            nominal = nxt is not None and (
                nxt.is_punct
                or self._nominal(nxt)
                or bool(self._groups(nxt) & {"PRE", "ARTPRE"})
                or self._coordinated_noun(groups, doc, i)
            )
            if nominal and self._imperative(rs, nxt, doc[i + 2] if i + 2 < len(doc) else None):
                nominal = False
        elif determiner:
            nominal = True
        elif prev.pos_ == "ADP":
            nominal = not non_finite or not any(verb_form(r[1]) == "inf" for r in rs)
        elif prev.pos_ == "ADJ":
            # a prenominal adjective: i piccoli animali, un nuovo salario; after a noun
            # the adjective ends its phrase (il premio mensile costa), unless the word
            # has no third-person indicative reading (ostacoli fisici presenti in casa)
            nominal = (
                prev2 is None or prev2.pos_ not in ("NOUN", "PROPN") or not _third_person(finite)
            )
        elif prev.pos_ in ("VERB", "AUX"):
            # è stato, ha pagato, deve pagare, deve essere inviato: a past participle,
            # an infinitive or a gerund; not the present participle of "è importante",
            # which stays an adjective. Else the object: definire compiti.
            if non_finite:
                return non_finite[0]
            nominal = True
        elif prev.pos_ == "CCONJ" and prev2 is not None and prev2.pos_ in ("NOUN", "PROPN", "ADJ"):
            # gradini e ostacoli: a noun coordinated with a noun, unless the word has a
            # third-person indicative reading (il Comune paga e controlla)
            nominal = not _third_person(finite)
        elif prev.pos_ in ("NOUN", "PROPN"):
            if "ADJ" in groups and self._agrees(rs, prev, prev2):
                return next(r for r in rs if coarse(r[1]) == "ADJ")  # una somma fissa
            # cassa pensioni: without a third-person indicative reading (pensioni is a
            # second person and a subjunctive) the verb loses to the noun; so does a
            # past participle that does not agree with the noun (Ufficio rette)
            participle = any(":part+past" in r[1] for r in rs)
            nominal = "NOUN" in groups and (
                (bool(finite) and not _third_person(finite))
                or (participle and not finite and not self._agrees(rs, prev, prev2, "VER"))
            )
        else:
            nominal = False
        if nominal and nominal_groups:
            return self._nominal_reading(rs, groups, nxt)
        return min(rs, key=_rank)

    def _number_sei(self, doc: Doc, i: int) -> bool:
        """sei is the number after an article, a preposition or a number (alle sei, le
        sei), before a plural noun (sei mesi), a number or punctuation (sono sei.); else
        the verb (sei malato, sei stato nel bosco)."""
        prev = doc[i - 1] if i > 0 else None
        if prev is not None and (prev.pos_ in ("ADP", "DET", "NUM") or prev.like_num):
            return True
        nxt = doc[i + 1] if i + 1 < len(doc) else None
        if nxt is None or nxt.is_punct or nxt.like_num:
            return True
        return any(
            coarse(tag) == "NOUN" and tag.endswith(":p") for _, tag in self.readings(nxt.text)
        )

    def _imperative(self, rs: tuple[tuple[str, str], ...], nxt: Token, after: Token | None) -> bool:
        """A polite imperative at the start of a sentence or a part (Telefoni al numero,
        Controlli i documenti, Telefoni per fissare un appuntamento): a third-person
        present subjunctive reading, and an article, an a-preposition or per with an
        infinitive after it. Before a di-preposition or a noun the word stays a noun
        (Aspetti della vita, Contatti per domande, Telefoni fissi)."""
        if not any(
            verb_form(tag) == "sub" and "+pres+" in tag and _person(tag) == "3" for _, tag in rs
        ):
            return False
        word = nxt.text.replace("’", "'").lower()
        if word in _A_PREPOSITIONS or word in _PLAIN_ARTICLES:
            return True
        if word in ("per", "a", "ad") and after is not None:
            return any(verb_form(tag) == "inf" for _, tag in self.readings(after.text))
        return False

    def _nominal_reading(
        self, rs: tuple[tuple[str, str], ...], groups: set[str], nxt: Token | None
    ) -> tuple[str, str]:
        order = ("NOUN", "ADJ", "NPR")
        if "ADJ" in groups and "NOUN" in groups and self._noun_follows(nxt):
            order = ("ADJ", "NOUN", "NPR")  # a prenominal adjective: un nuovo salario
        for wanted in order:
            if wanted in groups:
                return next(r for r in rs if coarse(r[1]) == wanted)
        return min(rs, key=_rank)

    def _coordinated_noun(self, groups: set[str], doc: Doc, i: int) -> bool:
        """A noun before e or o and another noun (rette, anticipi e incassi); not an
        imperative before an object (Controlli e invii il modulo)."""
        if "NOUN" not in groups or i + 2 >= len(doc):
            return False
        if doc[i + 1].text.lower() not in ("e", "ed", "o", "od", "oppure"):
            return False
        after = doc[i + 3].text.lower().replace("’", "'") if i + 3 < len(doc) else ""
        return "NOUN" in self._groups(doc[i + 2]) and after not in _PLAIN_ARTICLES

    def _agrees(
        self, rs: tuple[tuple[str, str], ...], noun: Token, before: Token | None, head: str = "ADJ"
    ) -> bool:
        """Whether an adjective reading (or, with head VER, a participle) agrees in gender
        and number with the noun before it; a noun of either gender takes the gender of
        its article (il Comune)."""
        gender, number = _features(noun.tag_)
        if before is not None and before.tag_.startswith(("ART", "DET", "PRO-POSS")):
            article_gender, article_number = _features(before.tag_)
            gender, number = article_gender or gender, article_number or number
        if not number:
            return False
        for _, tag in rs:
            if coarse(tag) != head or (head == "VER" and ":part+past" not in tag):
                continue
            adj_gender, adj_number = _features(tag)
            if adj_number == number and (not gender or not adj_gender or adj_gender == gender):
                return True
        return False

    def _article(self, doc: Doc, i: int) -> bool:
        """Whether the article reading of la, le, lo, gli or l' fits: after a preposition
        always; else the next word takes that form of the article (lo only before s plus
        consonant, z, gn, ps, x and y, l' only before a vowel, la never before one) and
        reads as a noun, not as a verb with its object ("lo invii il modulo")."""
        nxt = doc[i + 1] if i + 1 < len(doc) else None
        if nxt is None or nxt.is_punct:
            return False
        if i > 0 and doc[i - 1].pos_ == "ADP":
            return True  # con la disdetta, per la posta
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
        next_groups = self._groups(nxt)
        if not next_groups:
            return True  # a word the lexicon lacks is a noun more often than not
        if any(tag.startswith("PRO-POSS") for _, tag in self.readings(text)):
            return True  # la sua franchigia
        # A verb with its object: "lo invii il modulo". A first-person form ("l'incasso
        # l'ufficio recupera") is no such verb in an official text.
        addressed = any(_person(tag) in ("2", "3") for _, tag in self.readings(text))
        nominal = bool(next_groups & _NOMINAL_TAGS)
        if addressed and nominal and i + 3 < len(doc):
            after = doc[i + 2].text.lower().replace("’", "'")
            if after in _PLAIN_ARTICLES and self._nominal(doc[i + 3]):
                return False
        return nominal

    def _pos(self, lemma: str, tag: str, doc: Doc, i: int) -> str:
        pos = pos_of(tag, doc[i].text)
        if lemma in _AUX_LEMMAS and pos in ("AUX", "VERB"):
            for nxt in doc[i + 1 : i + 5]:
                if nxt.is_punct:
                    break
                if nxt.text.lower() in _SKIPPED:
                    continue
                forms = {
                    verb_form(tag) if ":part+past" not in tag else "part+past"
                    for _, tag in self.readings(nxt.text)
                }
                return "AUX" if forms & {"part+past", "inf", "ger"} else "VERB"
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
    """Articles first, then prepositions, the other closed-class readings, adverbs,
    verbs (indicative before the other moods), nouns, adjectives, proper nouns, the
    rest."""
    tag = reading[1]
    head = coarse(tag)
    if head in ("ART", "ARTPRE"):
        return (0, 0)
    if head == "PRE":
        return (0, 1)  # senza, dopo, tra: the preposition, not the conjunction
    if head in _CLOSED_TAGS:
        return (0, 2)
    if head == "ADV":
        return (0, 3)
    if head in _VERB_TAGS:
        return (1, _MOOD_RANK.get(verb_form(tag), 9))
    return ({"NOUN": 2, "ADJ": 3, "NPR": 4}.get(head, 5), 0)


@Language.factory(COMPONENT)
def create_morphit(nlp: Language, name: str) -> MorphitLexicon:
    return MorphitLexicon(nlp, name)
