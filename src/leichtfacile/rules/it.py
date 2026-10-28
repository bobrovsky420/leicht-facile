"""Italian rules (docs/rules.md, "Italian (IT-CH, lingua facile)").

Sentence-scope checks read what the lexicon component of leichtfacile_model_it sets on
every token from Morph-it! (rules/nlp.py): the lemma, the part of speech, the
morphological features (mood, tense, verb form, person, number, gender) and, in
`token._.readings`, every reading of an ambiguous form. There is no dependency parse:
clauses are counted from the finite verbs and the words that open subordinate clauses,
as the German module counts them from its parse, and a passive is an auxiliary
followed by a participle. Block-scope checks are regular expressions over the block
text. Messages are the English templates of rules/messages.py; the `guide` texts are
Italian, because they go into the writer prompt, which addresses the model with tu.
The reader of the easy-language text is addressed with Lei (docs/rules.md); voi is
accepted as direct address too.

This module holds the Italian words and patterns of the checks the languages share
(rules/shared.py) and the sentence analysis the document metrics read. The Italian
checks of their own follow (docs/rules.md, "Italian").
"""

from __future__ import annotations

import re

from spacy.tokens import Span, Token

from leichtfacile.rules.values import DASHES

IT = "it"
SENTENCE_KINDS = ("sentence", "list_item")
APOSTROPHES = "'" + chr(0x2019)
_APOS = "['" + chr(0x2019) + "]"
_GROUP_SEPARATORS = " '" + chr(0x2019) + chr(0xA0) + chr(0x202F) + chr(0x2009)
_LETTER = "A-Za-zÀ-ÖØ-öø-ÿ"
_DEGREE, _ORDINAL_O, _HALF = chr(0xB0), chr(0xBA), chr(0xBD)


def _norm(text: str) -> str:
    """Lowercase, with the typographic apostrophe as a plain one."""
    return text.lower().replace(chr(0x2019), "'")


# -- sentence analysis ------------------------------------------------------------


def words(sent: Span) -> list[Token]:
    return [t for t in sent if not (t.is_punct or t.is_space)]


def _elided(t: Token) -> bool:
    """l', dell', un', quest', c': an elided word that is read with the next one."""
    return len(t.text) <= 8 and t.text[-1] in APOSTROPHES and t.text[:-1].isalpha()


def word_count(sent: Span) -> int:
    """Words in a sentence. An elided article, preposition or pronoun counts with the
    next word (l'ufficio, dell'anno), and a run of numbers (091 123 45 67) as one word."""
    count = 0
    previous_num = previous_elided = False
    for t in words(sent):
        is_num = t.text[:1].isdigit()
        if not (previous_elided or (is_num and previous_num)):
            count += 1
        previous_num, previous_elided = is_num, _elided(t)
    return count


def readings(t: Token) -> tuple[tuple[str, str], ...]:
    """Every reading of the token in the lexicon as (lemma, Morph-it! tag); empty for a
    word the lexicon lacks or a pipeline without the component."""
    return getattr(t._, "readings", None) or ()


def is_finite(t: Token) -> bool:
    return t.pos_ in ("VERB", "AUX") and "Fin" in t.morph.get("VerbForm")


def is_participle(t: Token) -> bool:
    return t.pos_ in ("VERB", "AUX") and "Part" in t.morph.get("VerbForm")


def is_infinitive(t: Token) -> bool:
    return t.pos_ in ("VERB", "AUX") and "Inf" in t.morph.get("VerbForm")


AUX_LEMMAS = frozenset({"essere", "avere", "venire", "andare", "stare"})
MODAL_LEMMAS = frozenset({"dovere", "potere", "volere", "sapere"})
# Words that may stand between an auxiliary and its participle or infinitive: "non è
# stato inviato", "ha già pagato", "deve ancora pagare".
_BETWEEN = frozenset(
    {"non", "già", "ancora", "anche", "sempre", "mai", "più", "appena", "subito", "solo",
     "soltanto", "stato", "stata", "stati", "state", "lo", "la", "li", "le", "gli", "ne",
     "ci", "vi", "mi", "ti", "si"}
)  # fmt: skip
# Verbs whose compound past takes essere: "è arrivato", "sono partiti" are no passive.
ESSERE_INTRANSITIVES = frozenset(
    {"andare", "venire", "arrivare", "partire", "uscire", "entrare", "tornare", "ritornare",
     "rimanere", "restare", "nascere", "morire", "diventare", "stare", "essere", "cadere",
     "salire", "scendere", "succedere", "accadere", "avvenire", "piacere", "sembrare",
     "parere", "riuscire", "durare", "costare", "mancare", "bastare", "esistere",
     "scadere", "giungere", "sorgere", "crescere", "passare", "intervenire"}
)  # fmt: skip
# Participles that after essere usually describe a state, not an action: "l'ufficio è
# chiuso", "Lei è assicurato". Without an agent or a compound tense they are no passive.
STATIVE_PARTICIPLES = frozenset(
    {"chiudere", "aprire", "situare", "nascere", "sposare", "separare", "divorziare",
     "assicurare", "iscrivere", "interessare", "domiciliare", "obbligare", "autorizzare",
     "vietare", "permettere", "tenere", "abituare", "preoccupare", "stancare", "convincere",
     "indicare", "contenere", "comporre", "collegare", "limitare", "riservare", "esentare",
     "coinvolgere", "impegnare", "occupare", "attrezzare"}
)  # fmt: skip
AGENT_RE = re.compile(r"^(?:da|dal|dallo|dalla|dall'|dai|dagli|dalle)$")
COORDINATORS = frozenset({"e", "ed", "o", "od", "oppure", "ma", "né", "nemmeno", "neppure"})


def _content_after(tokens: list[Token], k: int, limit: int = 4) -> Token | None:
    """The next token after `tokens[k]` that is not a word of _BETWEEN or an adverb."""
    for t in tokens[k + 1 : k + 1 + limit]:
        if t.is_punct:
            return None
        if _norm(t.text) in _BETWEEN or t.pos_ == "ADV":
            continue
        return t
    return None


def _shares_subject(tokens: list[Token], k: int) -> bool:
    """ "paga e firma": a finite verb right after a coordinator, with nothing but
    adverbs and clitics in between, continues the statement of the verb before."""
    j = k - 1
    while j >= 0 and (_norm(tokens[j].text) in _BETWEEN or tokens[j].pos_ == "ADV"):
        j -= 1
    return j >= 0 and _norm(tokens[j].text) in COORDINATORS


def finite_verbs(sent: Span) -> list[Token]:
    """Finite verbs that open a clause of their own: not the auxiliary of a compound
    tense (ha scritto, è stato inviato), not a modal before its infinitive (deve
    pagare), not a coordinated verb that shares its subject (paga e firma)."""
    tokens = list(sent)
    out = []
    for k, t in enumerate(tokens):
        if not is_finite(t):
            continue
        if t.lemma_ in AUX_LEMMAS | MODAL_LEMMAS:
            following = _content_after(tokens, k)
            if following is not None and (is_participle(following) or is_infinitive(following)):
                continue
        if _shares_subject(tokens, k):
            continue
        out.append(t)
    return out


def clause_parts(sent: Span) -> list[Span]:
    """Parts of a sentence separated by a colon; each part is read as a statement of
    its own ("Ecco i numeri: 117 per la polizia.")."""
    parts = []
    start = sent.start
    for t in sent:
        if t.text == ":" and t.i > start:
            parts.append(sent.doc[start : t.i])
            start = t.i + 1
    if start < sent.end:
        parts.append(sent.doc[start : sent.end])
    parts = [p for p in parts if any(not (t.is_punct or t.is_space) for t in p)]
    return parts or [sent]


# Words that open a subordinate clause with a finite verb; the longest match wins.
CONJUNCTIONS = (
    "a condizione che", "a patto che", "nel caso in cui", "nel caso che", "in modo che",
    "una volta che", "dato che", "visto che", "in quanto", "dopo che", "prima che",
    "anche se", "non appena", "da quando", "fino a quando", "perché", "poiché", "siccome",
    "affinché", "benché", "sebbene", "nonostante", "malgrado", "qualora", "purché",
    "quando", "mentre", "finché", "appena", "se", "che",
)  # fmt: skip
RELATIVES = ("il quale", "la quale", "i quali", "le quali", "chi", "cui", "dove")
# Prepositions that open an adverbial infinitive clause: "per pagare", "prima di
# partire", "senza pagare", "al fine di ottenere".
INFINITIVE_OPENERS = (
    "al fine di", "allo scopo di", "prima di", "invece di", "oltre a", "senza", "per", "dopo",
)  # fmt: skip
_NOT_SUBORDINATING_AFTER = frozenset(
    {"è che", "non è che", "altro che", "più che", "meno che", "così che"}
)
_SE_PRONOUN_NEXT = frozenset({"ne", "lo", "la", "li", "le", "stesso", "stessa", "stessi", "stesse"})


def _phrase(tokens: list[Token], k: int, n: int) -> str:
    return " ".join(_norm(t.text) for t in tokens[k : k + n])


def _finite_follows(tokens: list[Token], k: int) -> bool:
    for t in tokens[k + 1 :]:
        if t.text in (":", ";"):
            return False
        if is_finite(t):
            return True
    return False


def _infinitive_follows(tokens: list[Token], k: int, limit: int = 4) -> bool:
    for t in tokens[k + 1 : k + 1 + limit]:
        if is_infinitive(t):
            return True
        if t.is_punct or t.pos_ in ("NOUN", "PROPN", "VERB", "AUX"):
            return False
    return False


def _opener_at(tokens: list[Token], k: int) -> tuple[str, str, int] | None:
    """The opener starting at token k as (text, kind, length in tokens), or None."""
    for phrase in CONJUNCTIONS:
        n = phrase.count(" ") + 1
        if _phrase(tokens, k, n) != phrase:
            continue
        word = phrase
        if word == "se" and k + 1 < len(tokens) and _norm(tokens[k + 1].text) in _SE_PRONOUN_NEXT:
            return None  # "se ne", "se stesso": a pronoun
        if word == "che" and k >= 1 and _phrase(tokens, k - 1, 2) in _NOT_SUBORDINATING_AFTER:
            return None
        if word == "che" and k >= 2 and _phrase(tokens, k - 2, 3) in _NOT_SUBORDINATING_AFTER:
            return None
        if word == "perché" and k == 0 and tokens[-1].text == "?":
            return None  # a question
        if not _finite_follows(tokens, k + n - 1):
            return None
        return phrase, "conjunction", n
    for phrase in RELATIVES:
        n = phrase.count(" ") + 1
        if _phrase(tokens, k, n) == phrase and _finite_follows(tokens, k + n - 1):
            return phrase, "relative", n
    for phrase in INFINITIVE_OPENERS:
        n = phrase.count(" ") + 1
        if _phrase(tokens, k, n) == phrase and _infinitive_follows(tokens, k + n - 1):
            return phrase, "infinitive", n
    return None


def openers(sent: Span) -> list[tuple[int, str, str]]:
    """The openers of the subordinate clauses of a sentence as (token index, text,
    kind), in order; kind is conjunction, relative or infinitive."""
    tokens = list(sent)
    found = []
    k = 0
    while k < len(tokens):
        opener = _opener_at(tokens, k)
        if opener is None:
            k += 1
            continue
        text, kind, n = opener
        found.append((tokens[k].i, text, kind))
        k += n
    return found


def subordinators(sent: Span) -> list[str]:
    """Openers of the subordinate clauses of a sentence, in order."""
    return [text for _, text, _ in openers(sent)]


def clause_count(sent: Span) -> int:
    subs = openers(sent)
    infinitives = [o for o in subs if o[2] == "infinitive"]
    by_verbs = len(finite_verbs(sent)) + len(infinitives)
    return max(1, by_verbs, 1 + len(subs))


def passive_constructions(sent: Span) -> list[tuple[str, bool]]:
    """Passive constructions as (evidence, strong): essere, venire or andare followed by
    the participle of another verb. Strong: with an agent (da ...), in a compound tense
    (è stato inviato), after a modal (deve essere inviato), with venire or andare
    (viene inviato, va compilato) or in the future (sarà inviato). A plain present with
    essere (è inviato) may describe a state; it is weak, and the participles of
    STATIVE_PARTICIPLES are left out. The compound past of an intransitive verb (è
    arrivato) and a reflexive (si è iscritto) are no passive."""
    tokens = list(sent)
    found = []
    for k, t in enumerate(tokens):
        if t.lemma_ not in ("essere", "venire", "andare") or t.pos_ not in ("AUX", "VERB"):
            continue
        if is_participle(t):
            continue  # "stata" in "è stata inviata": the chain starts at "è"
        if k >= 1 and _norm(tokens[k - 1].text) == "si":
            continue  # reflexive or impersonal si
        participle = _content_after(tokens, k)
        if participle is None or not is_participle(participle):
            continue
        if participle.lemma_ in ESSERE_INTRANSITIVES or participle.lemma_ == "avere":
            continue
        p = participle.i - sent.start
        between = [_norm(x.text) for x in tokens[k + 1 : p]]
        compound = any(x in ("stato", "stata", "stati", "state") for x in between)
        after = tokens[p + 1 : p + 5]
        agent = any(AGENT_RE.match(_norm(x.text)) for x in after)
        strong = (
            agent
            or compound
            or t.lemma_ in ("venire", "andare")
            or is_infinitive(t)  # deve essere inviato
            or "Fut" in t.morph.get("Tense")
        )
        if not strong and participle.lemma_ in STATIVE_PARTICIPLES:
            continue
        found.append((_span_text(sent, t, participle), strong))
    return found


def genitives(sent: Span) -> list[tuple[Token, str]]:
    """Italian has no genitive case; di phrases are the usual form."""
    return []


def _span_text(sent: Span, a: Token, b: Token) -> str:
    first, last = sorted((a, b), key=lambda t: t.i)
    if last.i - first.i <= 4:
        return sent.doc[first.i : last.i + 1].text
    return f"{first.text} ... {last.text}"


# -- the Italian words and patterns of the shared checks (rules/shared.py) ----------

SLASH_RE = re.compile(r"(?<=[" + _LETTER + r"])\s?/\s?(?=[" + _LETTER + r"])")

_ROLE_NOUNS = (
    r"(?:richiedent[ei]|istant[ei]|assicurat[oaie]|beneficiari[oae]?|contribuent[ei]|"
    r"interessat[oaie]|amministrat[oaie]|titolar[ei]|avent[ei]\s+diritto|stipulant[ei]|"
    r"utent[ei]|person[ae]\s+assicurat[ae]|person[ae]\s+interessat[ae]|cittadin[oaie])"
)
ROLE_NOUN_RE = re.compile(
    r"\b(?:il|lo|la|l"
    + _APOS
    + r"|i|gli|le|del|dello|della|dell"
    + _APOS
    + r"|dei|degli|delle|al|allo|alla|all"
    + _APOS
    + r"|ai|agli|alle|ogni|ciascun[oa]?|tutt[ie]\s+(?:i|le|gli))\s?"
    + _ROLE_NOUNS
    + r"\b",
    re.IGNORECASE,
)
ROLE_NOUN_WORD_RE = re.compile(r"\b" + _ROLE_NOUNS + r"\b", re.IGNORECASE)  # LEX-07

IDENTIFIER_BEFORE_RE = re.compile(
    r"(?:n" + _DEGREE + r"|n" + _ORDINAL_O + r"|n\.|no\.?|numero|modulo|formulario|art\.?|"
    r"articolo|cpv\.?|capoverso|lett\.?|lettera|cifra|casella\s+postale|CP|NPA|"
    r"codice\s+postale|ufficio|sala|linea|bus|tram|conto|IBAN|incarto|riferimento|rif\.?|"
    r"pratica|CH-)\s?$",
    re.IGNORECASE,
)
CURRENCY_NEAR_RE = re.compile(r"CHF|[Ff]r\.|franchi|franco|centesim[oi]", re.IGNORECASE)

# "entro il 15.09", "dal 1.3": a day and a month without a year or a final dot. The
# word before tells it from a decimal number.
DATE_SHORT_RE = re.compile(
    r"(?<![\w.])(?:entro\s+il|il|dal|al|fino\s+al|dall" + _APOS + r"|all" + _APOS + r")"
    r"\s(\d{1,2})\.(\d{1,2})(?![\d.,])",
    re.IGNORECASE,
)

DURATION_RE = re.compile(
    r"\d+[.,]\d\s?(?:h|ore)\b|\d*" + _HALF + r"\s?(?:h|ore)\b|\b\d+\s?min\b\.?"
)

_AMOUNT = r"\d{1,3}(?:[" + _GROUP_SEPARATORS + r"]\d{3})+|\d+"
AMOUNT_STYLE_RE = re.compile(
    r"(?:CHF|[Ff]r\.)\s?(" + _AMOUNT + r")[.,](?:00|[" + DASHES + r"]{1,2})"
    r"|(" + _AMOUNT + r")[.,](?:00|[" + DASHES + r"]{1,2})\s?(?:CHF|[Ff]r\.|franchi)"
    r"|(" + _AMOUNT + r")(?:[.,]\d{2})?\s?CHF\b"
)
