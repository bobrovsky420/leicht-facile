"""Italian rules (docs/rules.md, "Italian (IT-CH, lingua facile)").

Sentence-scope checks read what the lexicon component of leichtfacile_model_it sets on
every token from Morph-it! (rules/nlp.py): the lemma, the part of speech, the
morphological features (mood, tense, verb form, person, number, gender) and, in
`token._.readings`, every reading of an ambiguous form. There is no dependency parse:
clauses are counted from the finite verbs and the words that open subordinate clauses,
as the German module counts them from its parse, a passive is an auxiliary followed
by a participle, and a mood or tense rule fires only on a form whose readings agree
or on a form after a word that requires that mood. The polite imperative with Lei
(`Compili il modulo`) is a present-subjunctive form, so the subjunctive counts only
after che or a conjunction that requires it; the imperfect subjunctive and the
conditional are never imperatives. Block-scope checks are regular expressions over
the block text. Messages are the English templates of rules/messages.py; the `guide`
texts are Italian, because they go into the writer prompt, which addresses the model
with tu. The reader of the easy-language text is addressed with Lei; voi and tu count
as direct address too.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from spacy.tokens import Span, Token

from leichtfacile.rules.base import BlockInfo, Context, Hit, rule
from leichtfacile.rules.lexicon import is_known, zipf
from leichtfacile.rules.messages import hit
from leichtfacile.rules.recipes import recipe_it
from leichtfacile.rules.values import DASHES, EMAIL_RE, URL_RE, mask, mask_numbers
from leichtfacile.rules.vocabulary import covered_offsets, easy_for, find_terms, office_words

IT = "it"
SENTENCE_KINDS = ("sentence", "list_item")
APOSTROPHES = "'" + chr(0x2019)
_APOS = "['" + chr(0x2019) + "]"
_GROUP_SEPARATORS = " '" + chr(0x2019) + chr(0xA0) + chr(0x202F) + chr(0x2009)
_LETTER = "A-Za-zÀ-ÖØ-öø-ÿ"
_DEGREE, _ORDINAL_O, _HALF = chr(0xB0), chr(0xBA), chr(0xBD)
_VERB_TAGS = frozenset({"VER", "AUX", "MOD", "ASP", "CAU"})


def _norm(text: str) -> str:
    """Lowercase, with the typographic apostrophe as a plain one."""
    return text.lower().replace(chr(0x2019), "'")


# -- the lexicon's readings --------------------------------------------------------


def readings(t: Token) -> tuple[tuple[str, str], ...]:
    """Every reading of the token in the lexicon as (lemma, Morph-it! tag); empty for a
    word the lexicon lacks or a pipeline without the component."""
    return getattr(t._, "readings", None) or ()


def _coarse(tag: str) -> str:
    return tag.split(":", 1)[0].split("-", 1)[0]


def verb_readings(t: Token) -> list[tuple[str, str]]:
    """The verb readings as (form, tense): ("ind", "pres"), ("sub", "impf"), ("cond",
    "pres"), ("part", "past"), ("ger", "pres"), ("inf", "pres")."""
    out = []
    for _, tag in readings(t):
        if _coarse(tag) not in _VERB_TAGS or ":" not in tag:
            continue
        feats = tag.split(":", 1)[1].split("+")
        out.append((feats[0], feats[1] if len(feats) > 1 else ""))
    return out


def only_verb(t: Token) -> bool:
    """Every reading of the form is a verb reading."""
    rs = readings(t)
    return bool(rs) and all(_coarse(tag) in _VERB_TAGS for _, tag in rs)


def _all_forms(t: Token, *wanted: tuple[str, str]) -> bool:
    """The form is a verb whose readings all have one of the (form, tense) pairs."""
    forms = verb_readings(t)
    return only_verb(t) and bool(forms) and all(f in wanted for f in forms)


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


def is_finite(t: Token) -> bool:
    return t.pos_ in ("VERB", "AUX") and "Fin" in t.morph.get("VerbForm")


def is_participle(t: Token) -> bool:
    """A past participle (inviato, stata); a present participle (importante) is an
    adjective for every rule here."""
    return (
        t.pos_ in ("VERB", "AUX")
        and "Part" in t.morph.get("VerbForm")
        and "Past" in t.morph.get("Tense")
    )


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
    """Finite verbs that open a clause of their own. A compound tense or a modal with
    its infinitive counts once, by its finite auxiliary (ha scritto, è stato inviato,
    deve pagare); a coordinated verb that shares its subject (paga e firma) not at all."""
    tokens = list(sent)
    return [t for k, t in enumerate(tokens) if is_finite(t) and not _shares_subject(tokens, k)]


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
_INTERROGATIVES = frozenset({"perché", "quando", "dove", "chi", "come", "quanto"})
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
        if word in _INTERROGATIVES and tokens[-1].text == "?":
            return None  # a question: "Quando paga?", "Perché?"
        if not _finite_follows(tokens, k + n - 1):
            return None
        return phrase, "conjunction", n
    for phrase in RELATIVES:
        n = phrase.count(" ") + 1
        if phrase in _INTERROGATIVES and tokens[-1].text == "?":
            continue  # "Dove vivono e dove lavorano?"
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
    finite = finite_verbs(sent)
    if not finite:
        # "Per confrontare i prezzi:", "perché ha già pagato": a part without a main
        # clause of its own is one statement
        return max(1, len(infinitives))
    return max(1, len(finite) + len(infinitives), 1 + len(subs))


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


# Pronominal verbs: si belongs to the verb, no passive ("si ammala", "si chiama",
# "si iscrive", "si trova"). Verbs whose si form is often a passive (si presenta, si
# cura, si fa) stay out of the list.
PRONOMINAL_VERBS = frozenset(
    {"ammalare", "chiamare", "trovare", "iscrivere", "rivolgere", "recare", "occupare",
     "ricordare", "sentire", "muovere", "sposare", "separare", "preoccupare", "accorgere",
     "dimenticare", "annunciare", "trasferire", "fermare", "svegliare", "alzare", "lavare",
     "vestire", "sedere", "preparare", "lamentare", "comportare", "abituare", "divertire",
     "arrabbiare", "rilassare", "riposare", "vaccinare", "incontrare", "conoscere",
     "sbagliare", "spostare", "allontanare", "avvicinare", "nascondere", "impegnare",
     "stancare", "infettare", "contagiare", "ferire", "bruciare", "disidratare",
     "raffreddare", "trattare"}
)  # fmt: skip


def si_passives(sent: Span) -> list[str]:
    """The si passivante: si before a finite verb in the third person plural ("le
    domande si inviano"), or in the singular after the noun it goes with ("il modulo si
    compila online"). A reflexive or impersonal si before a singular verb at the start
    of a sentence ("si prega", "si iscrive") is not counted."""
    tokens = list(sent)
    found = []
    for k, t in enumerate(tokens):
        if _norm(t.text) != "si" or k + 1 >= len(tokens):
            continue
        verb = tokens[k + 1]
        if not is_finite(verb) or "3" not in verb.morph.get("Person"):
            continue
        if verb.lemma_ in PRONOMINAL_VERBS:
            continue
        plural = "Plur" in verb.morph.get("Number")
        after_noun = k >= 1 and tokens[k - 1].pos_ in ("NOUN", "PROPN")
        if plural or after_noun:
            found.append(_span_text(sent, t, verb))
    return found


def genitives(sent: Span) -> list[tuple[Token, str]]:
    """Italian has no genitive case; di phrases are the usual form."""
    return []


def _span_text(sent: Span, a: Token, b: Token) -> str:
    first, last = sorted((a, b), key=lambda t: t.i)
    if last.i - first.i <= 4:
        return sent.doc[first.i : last.i + 1].text
    return f"{first.text} ... {last.text}"


def _words_before(t: Token, n: int) -> str:
    """The n words before a token, lowercase, elisions joined: "a condizione che"."""
    start = max(t.sent.start, t.i - n)
    text = " ".join(_norm(x.text) for x in t.doc[start : t.i])
    return text.replace("' ", "'")


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


# -- sentence structure ------------------------------------------------------------


@rule(
    "LEN-02",
    lang=IT,
    guide={
        "A2": "Una sola informazione per frase. Niente frasi secondarie: niente frasi con "
        "perché, che, se, quando, affinché, per + verbo o una relativa con che, cui, dove. "
        "Scrivi piuttosto 2 frasi corte.",
        "B1": "Al massimo una frase secondaria per frase. Scrivi piuttosto 2 frasi corte.",
    },
)
def len_02(sent: Span, ctx: Context) -> Iterator[Hit]:
    limit = ctx.params.max_clauses
    worst = max(clause_parts(sent), key=clause_count)
    clauses = clause_count(worst)
    if clauses <= limit:
        return
    # As in German: one clause too many is a warning, nested clauses are an error.
    severity = "warn" if clauses == limit + 1 else "error"
    found = subordinators(worst)
    if found:
        yield hit(
            "LEN-02.sub",
            opener=found[0],
            clauses=clauses,
            limit=limit,
            level=ctx.level,
            evidence=sent.text,
            suggestion=recipe_it(found[0], sent.text),
            severity=severity,
        )
    else:
        yield hit(
            "LEN-02.main",
            clauses=clauses,
            limit=limit,
            level=ctx.level,
            evidence=sent.text,
            suggestion=recipe_it(None),
            severity=severity,
        )


_NOMINAL_TAGS = frozenset({"NOUN", "NPR", "ADJ", "NUM", "DET"})


def _nominal(t: Token) -> bool:
    if t.like_num or t.pos_ in ("NUM", "PROPN"):
        return True
    groups = {_coarse(tag) for _, tag in readings(t)}
    return bool(groups & {"NOUN", "NPR", "ADJ"}) and not (
        t.pos_ in ("VERB", "AUX") and is_finite(t)
    )


def _segment(tokens: list[Token]) -> bool:
    """A short noun phrase: at most 6 words with a noun, a name, an adjective or a
    number in it and no finite verb."""
    if not 0 < len(tokens) <= 6:
        return False
    if any(is_finite(t) or is_infinitive(t) for t in tokens):
        return False
    return any(_nominal(t) for t in tokens)


def _comma_list(sent: Span) -> str | None:
    """ "il passaporto, la carta d'assicurazione e una foto": noun phrases separated by
    commas and a final e, o or oppure."""
    tokens = list(sent)
    for k, t in enumerate(tokens):
        if _norm(t.text) not in ("e", "ed", "o", "od", "oppure"):
            continue
        after = []
        for u in tokens[k + 1 :]:
            if u.is_punct:
                break
            after.append(u)
        before: list[Token] = []
        j = k - 1
        while j >= 0 and not tokens[j].is_punct:
            before.insert(0, tokens[j])
            j -= 1
        if not (_segment(after) and _segment(before) and j >= 1 and tokens[j].text == ","):
            continue
        first = j - 1  # the item before the comma ends with a noun, a name or a number
        if not _nominal(tokens[first]) or is_finite(tokens[first]):
            continue
        start = first
        while (
            start > 0
            and not tokens[start - 1].is_punct
            and not is_finite(tokens[start - 1])
            and (tokens[start - 1].pos_ in ("DET", "ADP", "ADJ") or _nominal(tokens[start - 1]))
        ):
            start -= 1
        return sent.doc[tokens[start].i : after[-1].i + 1].text
    return None


@rule("LEN-03", lang=IT, guide="Citi 3 cose o più? Fai un elenco.")
def len_03(sent: Span, ctx: Context) -> Iterator[Hit]:
    listed = _comma_list(sent)
    if listed:
        yield hit("LEN-03.commas", evidence=listed)


# -- grammar ------------------------------------------------------------------------


@rule(
    "GRAM-01",
    lang=IT,
    guide="Niente forma passiva, neanche con si: di' chi fa che cosa. Non: Il modulo viene "
    "controllato dall'ufficio. Ma: L'ufficio controlla il modulo.",
)
def gram_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    for evidence, strong in passive_constructions(sent):
        if strong:
            yield hit("GRAM-01", found=evidence, evidence=evidence)
        else:
            # "è inviato" may be an action or a state: a warning at most.
            yield hit(
                "GRAM-01.state",
                found=evidence,
                evidence=evidence,
                severity="warn" if ctx.level == "A2" else "info",
            )
    for evidence in si_passives(sent):
        yield hit("GRAM-01.si", found=evidence, evidence=evidence, severity="info")


# Conjunctions and phrases after which the verb is a subjunctive, not a polite
# imperative: "affinché Lei possa", "bisogna che Lei compili", "se fosse".
SUBJUNCTIVE_GOVERNORS = (
    "a condizione che", "a patto che", "nel caso che", "nel caso in cui", "ammesso che",
    "posto che", "prima che", "senza che", "nonostante che", "malgrado che", "come se",
    "affinché", "benché", "sebbene", "purché", "qualora", "quantunque", "nonostante",
    "malgrado", "perché",
)  # fmt: skip
SUBJUNCTIVE_VERBS = frozenset(
    {"bisogna", "occorre", "necessario", "importante", "possibile", "impossibile", "meglio",
     "opportuno", "giusto", "normale", "probabile", "improbabile", "bene", "male",
     "vuole", "vogliamo", "vogliono", "vorrebbe", "chiede", "chiediamo", "chiedono",
     "spera", "speriamo", "teme", "temiamo", "pensa", "pensiamo", "crede", "crediamo",
     "ritiene", "riteniamo", "sembra", "pare", "desidera", "preferisce", "permette",
     "impedisce", "ordina", "consiglia", "basta", "darsi", "dubita", "suppone",
     "auspica", "augura", "esige", "pretende", "raccomanda"}
)  # fmt: skip


def _subjunctive_reason(t: Token) -> str | None:
    """The conjunction or the verb with che that governs a subjunctive form, if one
    stands before the token in its sentence."""
    before = _words_before(t, 7)
    for phrase in SUBJUNCTIVE_GOVERNORS:
        pos = before.rfind(phrase)
        if pos >= 0 and len(before[pos + len(phrase) :].split()) <= 4:
            return phrase
    words_before = before.split()
    for k in range(len(words_before) - 1, -1, -1):
        if words_before[k] != "che" or len(words_before) - 1 - k > 4:
            continue
        for governor in reversed(words_before[max(0, k - 3) : k]):
            if governor in SUBJUNCTIVE_VERBS:
                return f"{governor} che"
        return None
    if ("se" in words_before[-5:]) and all(f == "sub" for f, _ in verb_readings(t)):
        return "se"
    return None


def subjunctives(sent: Span) -> list[tuple[Token, str]]:
    """Subjunctive verbs as (verb, reason): a form with a subjunctive reading after a
    conjunction or a verb that requires it, or an imperfect subjunctive whose readings
    agree (fosse, avesse, compilasse). A present-subjunctive form on its own may be a
    polite imperative (Compili, Faccia) and is left alone."""
    found: list[tuple[Token, str]] = []
    for t in sent:
        forms = verb_readings(t)
        if not any(f == "sub" for f, _ in forms):
            continue
        reason = _subjunctive_reason(t)
        if reason:
            found.append((t, reason))
        elif _all_forms(t, ("sub", "impf")):
            found.append((t, "subjunctive form"))
    return found


@rule(
    "GRAM-03",
    lang=IT,
    guide="Niente congiuntivo e niente condizionale (non: bisognerebbe, Lei potrebbe, "
    "affinché Lei possa). Scrivi in forma diretta: Lei deve, Lei può.",
)
def gram_03(sent: Span, ctx: Context) -> Iterator[Hit]:
    for verb, reason in subjunctives(sent):
        if reason == "subjunctive form":
            yield hit("GRAM-03", mood="Congiuntivo", found=verb.text, evidence=verb.text)
        else:
            yield hit("GRAM-03.after", reason=reason, found=verb.text, evidence=verb.text)
    for t in sent:
        if _all_forms(t, ("cond", "pres")):
            yield hit("GRAM-03.conditional", found=t.text, evidence=t.text)


@rule(
    "GRAM-04",
    lang=IT,
    guide="Scrivi al presente. Per il passato usa il passato prossimo: Lei ha ricevuto una "
    "lettera. Niente passato remoto.",
)
def gram_04(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        if _all_forms(t, ("ind", "past")):
            yield hit("GRAM-04.passato_remoto", found=t.text, evidence=t.text)
        elif _all_forms(t, ("ind", "fut")):
            yield hit("GRAM-04.futuro", found=t.text, evidence=t.text, severity="info")


NOMINAL_SUFFIXES = ("zione", "zioni", "sione", "sioni", "mento", "menti", "ità", "enza",
                    "enze", "anza", "anze", "aggio", "aggi", "ura", "ure", "ismo",
                    "ismi")  # fmt: skip
EVERYDAY_ZIPF = 4.0  # nouns at least this frequent count as everyday words
NOMINAL_ALLOWED = frozenset(
    {"votazione", "votazioni", "elezione", "elezioni", "ambulanza", "stazione", "stazioni",
     "colazione", "vacanza", "vacanze", "pensione", "pensioni", "assicurazione",
     "assicurazioni", "abitazione", "abitazioni", "formazione", "appartamento",
     "appartamenti", "momento", "momenti", "città", "sanità", "università", "parcheggio",
     "viaggio", "viaggi", "bagaglio", "figura", "natura", "cultura", "macchina",
     "vaccinazione", "vaccinazioni", "inclusione", "puntura", "punture", "cura", "cure"}
)  # fmt: skip
LIGHT_VERBS = frozenset(
    {"effettuare", "procedere", "provvedere", "operare", "avvenire", "intervenire",
     "eseguire", "realizzare", "compiere", "attuare", "espletare", "dare", "fare"}
)  # fmt: skip
NOMINAL_PREPOSITIONS = (
    "in caso di", "in occasione di", "a seguito di", "in seguito a", "in ottemperanza a",
    "ai fini di", "al fine di", "nell'ambito di", "in merito a", "a titolo di", "in sede di",
    "in vista di", "mediante", "previa", "previo", "tramite", "durante",
)  # fmt: skip
_DI_RE = re.compile(r"^(?:di|del|dello|della|dell'|dei|degli|delle|d')$")


def nominal_context(sent: Span, t: Token) -> bool:
    """The noun sits in nominal style: with a light verb in the sentence, after a nominal
    preposition (in caso di) or with a di attribute (il versamento della prestazione)."""
    tokens = list(sent)
    k = t.i - sent.start
    if any(x.lemma_ in LIGHT_VERBS and x.pos_ in ("VERB", "AUX") for x in tokens):
        return True
    before = _words_before(t, 5)
    before = re.sub(r" (?:il|lo|la|l'|i|gli|le|un|una|uno|un')$", "", before)
    if any(before.endswith(p) for p in NOMINAL_PREPOSITIONS):
        return True
    if k + 2 < len(tokens) and _DI_RE.match(_norm(tokens[k + 1].text)):
        nxt = tokens[k + 2]
        if nxt.pos_ == "NOUN" or (
            nxt.pos_ == "DET" and k + 3 < len(tokens) and tokens[k + 3].pos_ == "NOUN"
        ):
            return True
    return False


@rule(
    "GRAM-05",
    lang=IT,
    guide="Verbi invece di nomi. Non: L'inoltro della domanda avviene online. "
    "Ma: Lei fa la domanda su internet.",
)
def gram_05(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        if t.pos_ != "NOUN" or ctx.in_glossary(t.text):
            continue
        word = t.lower_
        if len(word) <= 6 or not word.endswith(NOMINAL_SUFFIXES) or word in NOMINAL_ALLOWED:
            continue
        if t.text[:1].isupper() and t.i > sent.start:
            continue  # la Confederazione: a name
        if max(zipf(word, IT), zipf(t.lemma_.lower(), IT)) >= EVERYDAY_ZIPF:
            continue  # informazione, decisione, pagamento: everyday words
        if nominal_context(sent, t):
            yield hit("GRAM-05", found=t.text, evidence=t.text)
        else:
            yield hit("GRAM-05.abstract", found=t.text, evidence=t.text, severity="info")


_PRONOUNS = {
    "lui": ("Masc", "Sing"), "lei": ("Fem", "Sing"), "esso": ("Masc", "Sing"),
    "essa": ("Fem", "Sing"), "essi": ("Masc", "Plur"), "esse": ("Fem", "Plur"),
    "questo": ("Masc", "Sing"), "questa": ("Fem", "Sing"), "questi": ("Masc", "Plur"),
    "queste": ("Fem", "Plur"), "quello": ("Masc", "Sing"), "quella": ("Fem", "Sing"),
    "quelli": ("Masc", "Plur"), "quelle": ("Fem", "Plur"), "lo": ("Masc", "Sing"),
    "la": ("Fem", "Sing"), "li": ("Masc", "Plur"), "le": ("Fem", "Plur"),
}  # fmt: skip


def _is_pronoun(t: Token, sent: Span) -> bool:
    word = _norm(t.text)
    if word not in _PRONOUNS or t.text in ("Lei", "La", "Le"):
        return False  # the formal address
    if word in ("lo", "la", "li", "le") and t.pos_ != "PRON":
        return False  # an article
    if not word.startswith(("quest", "quell")):
        return True
    nxt = sent.doc[t.i + 1] if t.i + 1 < sent.end else None
    # questo modulo: a determiner, not a pronoun
    return nxt is None or nxt.is_punct or not _nominal(nxt)


def _antecedents(pronoun: Token, ctx: Context) -> set[str]:
    gender, number = _PRONOUNS[_norm(pronoun.text)]
    pool = [t for t in pronoun.doc[: pronoun.i] if t.pos_ in ("NOUN", "PROPN")]
    prev = ctx.previous_block()
    if prev:
        pool = [t for s in prev.sentences for t in s if t.pos_ in ("NOUN", "PROPN")] + pool
    found = set()
    for noun in pool:
        numbers, genders = noun.morph.get("Number"), noun.morph.get("Gender")
        if numbers and number not in numbers:
            continue
        if genders and gender not in genders and not (number == "Plur" and gender == "Masc"):
            continue  # "essi" also stands for a mixed group
        found.add(noun.lemma_.lower())
    return found


@rule(
    "GRAM-06",
    lang=IT,
    guide="Usa lui, lei, questo o quello solo se è chiaro di chi o di che cosa parli. "
    "Altrimenti ripeti il nome.",
)
def gram_06(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        if not _is_pronoun(t, sent):
            continue
        found = _antecedents(t, ctx)
        if not found:
            yield hit("GRAM-06", found=t.text, evidence=t.text)
        elif len(found) > 1 and _PRONOUNS[_norm(t.text)][1] == "Sing":
            options = ", ".join(sorted(found)[:3])
            yield hit("GRAM-06.ambiguous", found=t.text, options=options, evidence=t.text)


REPORTED_RE = re.compile(
    r"\b(?:secondo (?:il|lo|la|l'|i|gli|le|quanto|quello)|"
    r"a detta (?:di|del|dello|della|dell'|dei|degli|delle)|stando a|"
    r"come (?:riferito|indicato|comunicato|dichiarato) da)\b",
    re.IGNORECASE,
)


@rule("GRAM-07", lang=IT, guide="Niente discorso indiretto. Di' chi dice che cosa.")
def gram_07(sent: Span, ctx: Context) -> Iterator[Hit]:
    for m in REPORTED_RE.finditer(sent.text):
        label = _norm(m.group(0).split()[0])
        label = "a detta di" if label == "a" else "stando a" if label == "stando" else label
        yield hit("GRAM-07", found=label, evidence=m.group(0))


IMPERSONAL_RE = re.compile(
    r"\b(?:si prega di|si invita (?:a|la lettrice|il lettore)|si raccomanda di|"
    r"si rammenta che|si fa presente che|si comunica che|si informa che|si precisa che|"
    r"è fatto obbligo|è d'obbligo|è opportuno|va (?:ricordato|precisato|sottolineato|"
    r"notato|rilevato|segnalato)|occorre (?:che|\w+[aei]re\b))",
    re.IGNORECASE,
)
# "bisogna" is the everyday impersonal; the official easy-language pages use it
# (calibration of 28 October 2026), so it is a note like "è necessario".
IMPERSONAL_SOFT_RE = re.compile(
    r"\bè (?:necessario|obbligatorio|possibile|importante|vietato|consentito|"
    r"indispensabile|utile|consigliabile) (?:che\b|\w+[aei]re\b)|bisogna (?:che\b|\w+[aei]re\b)",
    re.IGNORECASE,
)


@rule(
    "GRAM-09",
    lang=IT,
    guide="Niente forme impersonali come si prega di, è fatto obbligo di, occorre. "
    "Di' chi deve fare che cosa: Lei deve.",
)
def gram_09(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in IMPERSONAL_RE.finditer(block.text):
        yield hit("GRAM-09", found=m.group(0), evidence=m.group(0))
    for m in IMPERSONAL_SOFT_RE.finditer(block.text):
        yield hit("GRAM-09.soft", found=m.group(0), evidence=m.group(0), severity="info")


@rule(
    "GRAM-10",
    lang=IT,
    guide="Niente gerundio (non: compilando il modulo, avendo pagato). Scrivi 2 frasi: "
    "Lei compila il modulo. Poi ...",
)
def gram_10(sent: Span, ctx: Context) -> Iterator[Hit]:
    tokens = list(sent)
    for k, t in enumerate(tokens):
        if not _all_forms(t, ("ger", "pres")):
            continue
        before = [_norm(x.text) for x in tokens[max(0, k - 2) : k]]
        if any(x.lemma_ == "stare" for x in tokens[max(0, k - 2) : k]) or "sta" in before:
            continue  # "sta compilando": the progressive, not a clause
        yield hit("GRAM-10", found=t.text, evidence=t.text)


# -- negation -----------------------------------------------------------------------

# Words that form one negation together with "non" (negative concord): "non ... mai",
# "non ... nessuno", "non ... né ... né".
CONCORD_WORDS = frozenset(
    {"mai", "niente", "nulla", "nessuno", "nessuna", "nessun", "alcuno", "alcuna", "alcun",
     "affatto", "più", "neanche", "nemmeno", "neppure", "né", "mica", "minimamente"}
)  # fmt: skip
NEGATIVE_ADJECTIVES = frozenset(
    {"impossibile", "inutile", "illegale", "irregolare", "incompleto", "incompleta",
     "sconosciuto", "sconosciuta", "insufficiente", "incapace", "inesatto", "inesatta",
     "inaccettabile", "inammissibile", "ingiusto", "ingiusta", "indisponibile",
     "imprevisto", "imprevista", "illeggibile", "scorretto", "scorretta", "irricevibile",
     "invalido", "invalida", "inesistente", "inevitabile", "improbabile", "incerto",
     "incerta", "inadeguato", "inadeguata", "impagato", "impagata", "infondato",
     "infondata", "irrilevante", "escluso", "esclusa"}
)  # fmt: skip
_PART_SEPARATORS = frozenset({"e", "ed", "o", "od", "oppure", "ma", "però", "perché", "se",
                              "che", "quando", "mentre", "chi", "cui", "dove"})  # fmt: skip


def _negation_parts(sent: Span) -> list[list[Token]]:
    """Clause parts: commas, colons, coordinators and the openers of subordinate clauses
    separate statements."""
    parts: list[list[Token]] = [[]]
    for t in sent:
        word = _norm(t.text)
        if t.text in (",", ";", ":"):
            parts.append([])
        elif word in _PART_SEPARATORS:
            parts.append([t])
        else:
            parts[-1].append(t)
    return parts


def _negation_units(part: list[Token]) -> list[list[Token]]:
    """The logical negations of one clause part: non with its concord words counts
    once; senza, non before a negative adjective and a second non each add one."""
    nons = [t for t in part if _norm(t.text) == "non"]
    concord = [t for t in part if _norm(t.text) in CONCORD_WORDS]
    units: list[list[Token]] = []
    if nons:
        units += [[n] for n in nons]  # two non in one part are two negations
        if concord and len(nons) == 1:
            units = [[nons[0], *concord]]
    elif concord:
        units.append(concord)
    for t in part:
        word = _norm(t.text)
        if word == "senza":
            units.append([t])
        elif nons and (word in NEGATIVE_ADJECTIVES or t.lemma_.lower() in NEGATIVE_ADJECTIVES):
            units.append([t])  # "non è impossibile"
    return units


def _negation_text(unit: list[Token]) -> str:
    return " ... ".join(t.text for t in sorted(unit, key=lambda t: t.i))


@rule("NEG-01", lang=IT, guide="Niente doppia negazione (non: non è impossibile).")
def neg_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    for part in _negation_parts(sent):
        units = _negation_units(part)
        if len(units) >= 2:
            text = " ... ".join(_negation_text(u) for u in units)
            yield hit("NEG-01", found=text, evidence=text)


@rule(
    "NEG-02",
    lang=IT,
    guide="Scrivi in positivo quando puoi: Lei può ... invece di Lei non può ...",
)
def neg_02(sent: Span, ctx: Context) -> Iterator[Hit]:
    found = [u for p in _negation_parts(sent) for u in _negation_units(p)]
    if len(found) == 1:
        text = _negation_text(found[0])
        yield hit("NEG-02", found=text, evidence=text)


# -- words --------------------------------------------------------------------------


@rule("LEX-01", lang=IT, guide="Evita le parole lunghe. Usa la parola corta e conosciuta.")
def lex_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    limit = ctx.params.max_word_letters
    for t in sent:
        if t.like_url or t.like_email or ctx.in_glossary(t.text):
            continue
        for part in re.split(_APOS + "|-", t.text):
            letters = sum(ch.isalpha() for ch in part)
            if letters > limit:
                yield hit(  # a note only: Italian has no compounds to split
                    "LEX-01.no_compound",
                    found=t.text,
                    letters=letters,
                    evidence=t.text,
                    severity="info",
                )
                break


ABBREVIATIONS = [
    r"p\.\s?es\.", r"ad\s?es\.", r"ecc\.", r"cfr\.", r"ca\.", r"risp\.", r"ev\.", r"event\.",
    r"n\.(?=\s?\d)", r"nr\.(?=\s?\d)", r"tel\.", r"all\.(?=\s?\d)", r"max\.", r"min\.",
    r"(?:art|cpv|cap|lett|lit|par|pag|pagg|vol|fig|tab)\.(?=\s?\d)",
    r"(?:[nN]o|n" + _DEGREE + r"|n" + _ORDINAL_O + r")\.?(?=\s?\d)", r"[Ff]r\.(?=\s?\d)",
    r"Sig\.(?:ra|na|ri)?(?=\s)", r"Sigg\.", r"Dott\.(?:ssa)?(?=\s)", r"Avv\.(?=\s)",
    r"On\.(?=\s)", r"Ing\.(?=\s)", r"Arch\.(?=\s)", r"Prof\.(?:ssa)?(?=\s)", r"Spett\.",
    r"Egr\.", r"Gent\.(?:mo|ma)?", r"c\.c\.", r"c\.p\.", r"s\.r\.l\.", r"S\.A\.",
]  # fmt: skip
ABBREVIATION_RE = re.compile(r"(?<![\w.])(?:" + "|".join(ABBREVIATIONS) + r")")
_WEEKDAYS = "lu|ma|me|gi|ve|sa|do|lun|mar|mer|gio|ven|sab|dom"
WEEKDAY_RANGE_RE = re.compile(
    r"(?<![\w.])(?:"
    + _WEEKDAYS
    + r")\.?\s?["
    + DASHES
    + r"]\s?(?:"
    + _WEEKDAYS
    + r")(?!["
    + _LETTER
    + r"])\.?"
)
MONTH_ABBREVIATION_RE = re.compile(
    r"\b\d{1,2}\.?\s(?:gen|feb|mar|apr|mag|giu|lug|ago|set|sett|ott|nov|dic)\."
)
ACRONYM_RE = re.compile(
    r"(?<![\w-])(?:[A-ZÀ-Ý]{2,6}s?|[A-ZÀ-Ý][a-zà-ÿ]{0,4}[A-ZÀ-Ý][A-Za-zÀ-ÿ]{0,4})(?![\w-])"
)  # AVS, UFSP, and law abbreviations in mixed case such as LAMal or LPGA
ACRONYMS_ALLOWED = frozenset({"CHF", "AVS", "AI", "FFS", "PDF", "WC", "SMS", "TV", "ID", "OK"})
# Words in capitals for emphasis, as voting texts write them: "Voti SÌ".
EMPHASIS_WORDS = frozenset(
    {"SÌ", "SI", "NO", "NON", "E", "O", "SOLO", "ANCHE", "MAI", "TUTTO", "TUTTI", "TUTTE"}
)


def _masked_links(text: str) -> str:
    text = mask(text, [m.span() for m in URL_RE.finditer(text)])
    return mask(text, [m.span() for m in EMAIL_RE.finditer(text)])


@rule(
    "LEX-02",
    lang=IT,
    guide="Niente abbreviazioni (non: p. es., ecc., art.). Puoi scrivere CHF, AVS, AI e FFS. "
    "Spiega le altre abbreviazioni.",
)
def lex_02(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    text = _masked_links(block.text)
    letters = [ch for ch in text if ch.isalpha()]
    all_caps = len(letters) >= 8 and sum(ch.isupper() for ch in letters) >= 0.8 * len(letters)
    for regex in (ABBREVIATION_RE, MONTH_ABBREVIATION_RE):
        for m in regex.finditer(text):
            found = m.group(0).strip()
            # "tel." heads the contact lines of the official pages: a note
            severity = "info" if found.lower().startswith("tel") else None
            yield hit(
                "LEX-02",
                found=found,
                evidence=found,
                suggestion=easy_for(IT, found),
                severity=severity,
            )
    for m in WEEKDAY_RANGE_RE.finditer(text):
        yield hit(
            "LEX-02.weekdays",
            found=m.group(0),
            expected="dal lunedì al venerdì",
            evidence=m.group(0),
        )
    for m in ACRONYM_RE.finditer(text):
        acronym = m.group(0)
        if acronym[-1] == "s" and acronym[:-1].isupper():
            acronym = acronym[:-1]
        if (
            acronym in ACRONYMS_ALLOWED
            or acronym in EMPHASIS_WORDS
            or (len(acronym) >= 4 and is_known(acronym.lower(), IT, min_zipf=3.5))
            or (all_caps and is_known(acronym.lower(), IT, min_zipf=3.0))
            or re.fullmatch(r"[IVXLC]+", acronym)
        ):
            continue
        if acronym in ctx.introduced or ctx.in_glossary(acronym):
            yield hit("LEX-02.explained", found=acronym, evidence=acronym, severity="info")
            continue
        yield hit(
            "LEX-02.acronym", found=acronym, evidence=acronym, suggestion=easy_for(IT, acronym)
        )


@rule(
    "LEX-03",
    lang=IT,
    guide="Usa parole semplici e conosciute. Niente parole straniere e niente termini tecnici. "
    "Se una parola difficile è necessaria, spiegala nel glossario.",
)
def lex_03(sent: Span, ctx: Context) -> Iterator[Hit]:
    office = covered_offsets(
        office_words(find_terms(IT, sent), exclude=ROLE_NOUN_WORD_RE), sent.start_char
    )
    for t in sent:
        if t.idx in office:
            continue  # an office word: LEX-07 names the everyday word
        if t.pos_ not in ("NOUN", "VERB", "ADJ", "ADV", "X", ""):
            continue
        parts = [p for p in re.split(_APOS + "|-", t.text) if p]
        if not parts or not all(p.isalpha() for p in parts) or len(t.text) < 4:
            continue
        if t.text.isupper() or ctx.in_glossary(t.text):
            continue
        if max(zipf(t.lower_, IT), zipf(t.lemma_.lower(), IT)) >= 2.5:
            continue
        if len(parts) > 1 and all(zipf(p.lower(), IT) >= 3.0 for p in parts):
            continue
        yield hit("LEX-03", found=t.text, evidence=t.text)


INCLUSIVE_RE = re.compile(
    r"(?<![\w/])[" + _LETTER + r"]{3,}(?:\*|ə|Ə|/[aei]{1,2}\b)(?![" + _LETTER + r"])"
)  # cittadin*, cittadinə, cittadini/e


@rule(
    "LEX-05",
    lang=IT,
    guide="Niente scrittura inclusiva con asterisco, schwa o barra (cittadin*, cittadini/e). "
    "Scrivi le due forme: le cittadine e i cittadini.",
)
def lex_05(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in INCLUSIVE_RE.finditer(_masked_links(block.text)):
        yield hit("LEX-05.inclusive", found=m.group(0), evidence=m.group(0))


# -- numbers, dates, times, amounts -----------------------------------------------

_UNITS = {
    "uno": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7,
    "otto": 8, "nove": 9, "dieci": 10, "undici": 11, "dodici": 12, "tredici": 13,
    "quattordici": 14, "quindici": 15, "sedici": 16, "diciassette": 17, "diciotto": 18,
    "diciannove": 19,
}  # fmt: skip
_TENS = {"venti": 20, "trenta": 30, "quaranta": 40, "cinquanta": 50, "sessanta": 60,
         "settanta": 70, "ottanta": 80, "novanta": 90}  # fmt: skip
_ORDINALS = {"terz": 3, "quart": 4, "quint": 5, "sest": 6, "settim": 7, "ottav": 8, "non": 9,
             "decim": 10}  # fmt: skip
ORDINAL_RE = re.compile(r"^(terz|quart|quint|sest|settim|ottav|decim)[oaie]$")


def italian_number(word: str) -> int | None:
    """due -> 2, ventuno -> 21, trentotto -> 38, duecento -> 200, mille -> 1000."""
    w = word.lower().replace("é", "e").replace("è", "e")
    if w in _UNITS:
        return _UNITS[w]
    if w in _TENS:
        return _TENS[w]
    if w in ("cento", "mille"):
        return 100 if w == "cento" else 1000
    for tens, value in _TENS.items():
        if w.startswith(tens) and w[len(tens) :] in _UNITS and _UNITS[w[len(tens) :]] < 10:
            return value + _UNITS[w[len(tens) :]]
        stem = tens[:-1]
        if w.startswith(stem) and w[len(stem) :] in ("uno", "otto"):
            return value + _UNITS[w[len(stem) :]]
    for prefix, value in list(_UNITS.items())[:9]:
        if w == prefix + "cento":
            return value * 100
        if w == prefix + "mila":
            return value * 1000
    return None


@rule(
    "NUM-01",
    lang=IT,
    guide="Scrivi i numeri in cifre: 2, 3, 12. Solo uno e una si scrivono in lettere.",
)
def num_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        lower = t.lower_
        if not lower.isalpha():
            continue
        value = italian_number(lower)
        if value is not None and value >= 2:
            if lower == "cento" and t.i > sent.start and sent.doc[t.i - 1].lower_ == "per":
                continue  # "per cento" is NUM-06's
            if lower == "sei" and t.pos_ != "NUM":
                continue  # "se sei malato": the verb, "sei mesi" the number
            yield hit("NUM-01", found=t.text, evidence=t.text, suggestion=str(value))
        elif m := ORDINAL_RE.match(lower):
            yield hit(
                "NUM-01.ordinal",
                found=t.text,
                evidence=t.text,
                suggestion=f"{_ORDINALS[m.group(1)]}{_DEGREE}",
            )


_TIME = r"\d{1,2}[.:]\d{2}"
TIME_COLON_RE = re.compile(r"(?<![\d.:])(\d{1,2}):(\d{2})(?!\d)")
TIME_H_RE = re.compile(r"(?<![\d.:,])(\d{1,2})\s?h\s?(\d{2})?(?![\w])")  # 9h, 16h30
TIME_RANGE_RE = re.compile(
    r"(?<![\d.:,])(?:ore\s)?(" + _TIME + r")\s?[" + DASHES + r"]\s?(" + _TIME + r")(?![\d])"
    r"|(?<![\d.:,])ore\s(\d{1,2})\s?[" + DASHES + r"]\s?(\d{1,2})(?![\d:])(?![.,]\d)"
)


def _time_text(hour: str | int, minute: str | None) -> str:
    return f"{int(hour)}.{minute or '00'}"


def _parse_time(text: str) -> tuple[int, str | None] | None:
    m = re.match(r"(\d{1,2})(?:[.:](\d{2}))?", text.strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), m.group(2)
    if hour > 24 or (minute is not None and int(minute) > 59):
        return None
    return hour, minute


@rule(
    "NUM-04",
    lang=IT,
    guide="Un orario si scrive così: 9.00 o ore 9.00. Un periodo così: dalle 9.00 alle 12.00.",
)
def num_04(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    # The ranges are read off the text as written: the number masking takes a final
    # "11.30." for a date.
    spans: list[tuple[int, int]] = []
    for m in TIME_RANGE_RE.finditer(block.text):
        first = _parse_time(m.group(1) or m.group(3))
        second = _parse_time(m.group(2) or m.group(4))
        if first is None or second is None:
            continue
        spans.append(m.span())
        expected = f"dalle {_time_text(*first)} alle {_time_text(*second)}"
        yield hit(
            "NUM-04.range",
            found=m.group(0).strip(),
            expected=expected,
            evidence=m.group(0).strip(),
            suggestion=expected,
        )
    text = mask(mask_numbers(block.text), spans)
    for regex in (TIME_COLON_RE, TIME_H_RE):
        found = []
        for m in regex.finditer(text):
            if int(m.group(1)) > 24 or (m.group(2) and int(m.group(2)) > 59):
                continue
            found.append(m.span())
            expected = _time_text(m.group(1), m.group(2))
            yield hit(
                "NUM-04",
                found=m.group(0).strip(),
                expected=expected,
                evidence=m.group(0).strip(),
                suggestion=expected,
            )
        text = mask(text, found)
