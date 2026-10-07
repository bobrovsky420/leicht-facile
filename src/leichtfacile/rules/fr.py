"""French rules (docs/rules.md, "French (FR-CH, FALC)").

Sentence-scope checks read the spaCy parse of fr_core_news_md (Universal Dependencies
labels and features); block-scope checks are regular expressions over the block text.
The parser's tense and mood features are not reliable for French verbs: it reads
"recevrez" as a present, "recevez" as a future and the subjunctive "envoyiez" as an
indicative. The future, the conditional and the passé simple are therefore recognised
from the verb's ending and its lemma, and the subjunctive from the conjunctions and
verbs that require it. Messages are the English templates of rules/messages.py, with
a key and values for the interface's translation; the `guide` texts are French,
because they go into the writer prompt.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator

from spacy.tokens import Span, Token

from leichtfacile.rules.base import BlockInfo, Context, Hit, rule, sev
from leichtfacile.rules.de import ACCEPTED_PHONE_RE, format_phone
from leichtfacile.rules.lexicon import MEDIOPUNKT, is_known, zipf
from leichtfacile.rules.messages import hit
from leichtfacile.rules.recipes import recipe_fr
from leichtfacile.rules.values import (
    DASHES,
    DATE_ISO_RE,
    DATE_NUM_RE,
    DATE_SLASH_RE,
    EMAIL_RE,
    PHONE_RE,
    URL_RE,
    canonical_date,
    format_date,
    format_thousands,
    mask,
)

FR = "fr"
SENTENCE_KINDS = ("sentence", "list_item")
APOSTROPHES = "'" + chr(0x2019)
_APOS = "['" + chr(0x2019) + "]"
_GROUP_SEPARATORS = " '" + chr(0x2019) + chr(0xA0) + chr(0x202F) + chr(0x2009)
_LETTER = "A-Za-zÀ-ÖØ-öø-ÿŒœ"
_DEGREE, _ORDINAL_O, _HALF = chr(0xB0), chr(0xBA), chr(0xBD)


def _norm(text: str) -> str:
    """Lowercase, with the typographic apostrophe as a plain one."""
    return text.lower().replace(chr(0x2019), "'")


def _plain(text: str) -> str:
    """Without accents: achèterez and acheterez compare equal."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# -- sentence analysis ------------------------------------------------------------


def words(sent: Span) -> list[Token]:
    return [t for t in sent if not (t.is_punct or t.is_space)]


def _elided(t: Token) -> bool:
    """l', d', qu', jusqu': an elided word that is read with the next one."""
    return len(t.text) <= 8 and t.text[-1] in APOSTROPHES and t.text[:-1].isalpha()


def word_count(sent: Span) -> int:
    """Words in a sentence. An elided article or pronoun counts with the next word
    (l'argent), a hyphenated pronoun with its verb (appelez-nous), and a run of numbers
    (022 546 52 00) as one word."""
    count = 0
    previous_num = previous_elided = False
    for t in words(sent):
        is_num = t.text[:1].isdigit()
        joined = previous_elided or t.text.startswith("-") or (is_num and previous_num)
        if not joined:
            count += 1
        previous_num, previous_elided = is_num, _elided(t)
    return count


AUX_DEPS = ("aux", "aux:tense", "aux:pass", "cop")
SUBJECT_DEPS = ("nsubj", "nsubj:pass", "expl:subj", "csubj")
SUBORDINATE_DEPS = ("advcl", "ccomp", "acl:relcl", "csubj")
# Words that may stand between a preposition and its infinitive: "pour le faire",
# "sans rien payer", "pour ne pas oublier".
_BEFORE_INFINITIVE = frozenset(
    {"le", "la", "les", "l'", "lui", "leur", "se", "s'", "y", "en", "me", "m'", "te", "t'",
     "nous", "vous", "ne", "n'", "pas", "rien", "jamais", "plus", "bien", "tout"}
)  # fmt: skip


def is_finite(t: Token) -> bool:
    """The token is a finite verb, or the predicate of a finite auxiliary or copula."""
    if "Fin" in t.morph.get("VerbForm"):
        return True
    return any(c.dep_ in AUX_DEPS and "Fin" in c.morph.get("VerbForm") for c in t.children)


def _has_subject(t: Token) -> bool:
    return any(c.dep_ in SUBJECT_DEPS for c in t.children)


def adverbial_infinitive(t: Token) -> Token | None:
    """The preposition when an infinitive opens an adverbial clause: pour payer, afin de
    payer, sans payer, avant de partir, après avoir payé. An infinitive that completes
    a noun (le formulaire pour demander l'aide) does not count."""
    if t.pos_ not in ("VERB", "AUX") or "Inf" not in t.morph.get("VerbForm") or t.dep_ == "acl":
        return None
    doc, start = t.doc, t.sent.start
    i = t.i - 1
    while i >= start and _norm(doc[i].text) in _BEFORE_INFINITIVE:
        i -= 1
    if i < start:
        return None
    word = _norm(doc[i].text)
    if word in ("pour", "sans", "après"):
        return doc[i]
    if word in ("de", "d'") and i > start and _norm(doc[i - 1].text) in ("afin", "avant"):
        return doc[i - 1]
    return None


def _question_que(t: Token) -> bool:
    """The que of est-ce que, which only marks a question."""
    if _norm(t.text) not in ("que", "qu'") or t.i < 1:
        return False
    previous = _norm(t.doc[t.i - 1].text)
    return previous in ("est-ce", "-ce") or (
        previous == "ce" and t.i > 1 and _norm(t.doc[t.i - 2].text).endswith("est")
    )


def _opener(head: Token) -> Token | None:
    """The mark or relative pronoun that opens a clause."""
    marks = [c for c in head.children if c.dep_ == "mark"]
    if marks:
        return min(marks, key=lambda m: m.i)
    relative = [
        c
        for c in head.subtree
        if c.i < head.i and ("Rel" in c.morph.get("PronType") or _question_que(c))
    ]
    return min(relative, key=lambda r: r.i) if relative else None


def _opens_clause(t: Token) -> bool:
    if t.dep_ == "ROOT":
        return True
    if t.dep_ == "conj":
        return is_finite(t) and _has_subject(t)  # "et vous montrez": a statement of its own
    opener = _opener(t)
    if opener is not None and _question_que(opener):
        return False  # "Est-ce que vous avez ...?" is one question
    finite_clause = t.dep_ in (*SUBORDINATE_DEPS, "parataxis") and is_finite(t)
    return finite_clause or adverbial_infinitive(t) is not None


def clause_heads(sent: Span) -> list[Token]:
    """The predicates of the clauses in a sentence: the main predicate, coordinated
    predicates with a subject of their own, finite subordinate clauses and adverbial
    infinitive clauses."""
    return [t for t in sent if _opens_clause(t)]


def marker(head: Token) -> str | None:
    """The words that open a subordinate clause: parce que, pour que, si, qui, pour."""
    marks = [c for c in head.children if c.dep_ == "mark"]
    marks += [f for m in marks for f in m.children if f.dep_ == "fixed"]
    if marks:
        return " ".join(_norm(m.text) for m in sorted(marks, key=lambda m: m.i))
    relative = [c for c in head.subtree if "Rel" in c.morph.get("PronType") and c.i < head.i]
    if relative:
        return _norm(relative[0].text)
    preposition = adverbial_infinitive(head)
    if preposition is not None:
        word = _norm(preposition.text)
        return f"{word} de" if word in ("afin", "avant") else word
    return None


def subordinators(sent: Span) -> list[str]:
    """Openers of the subordinate clauses of a sentence, in order."""
    found = []
    for h in clause_heads(sent):
        if h.dep_ == "ROOT":
            continue
        opener = marker(h)
        if opener is None and h.dep_ in ("conj", "parataxis"):
            continue  # a coordinated main clause
        found.append((h.i, opener or h.text))
    return [opener for _, opener in sorted(found)]


def clause_count(sent: Span) -> int:
    return max(1, len(clause_heads(sent)))


def clause_parts(sent: Span) -> list[Span]:
    """Parts of a sentence separated by a colon; each part is read as a statement of
    its own ("Voici les numéros : 117 pour la police.")."""
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


# Verb forms. Future and conditional: the ending follows the future stem, which for
# most verbs is the infinitive (payer-ez, finir-ez, prendr-ez) and for some is
# irregular (ser-a, aur-ez, pourr-ont).
FUTURE_ENDINGS = ("ront", "rons", "rez", "rai", "ras", "ra")
CONDITIONAL_ENDINGS = ("raient", "rions", "riez", "rais", "rait")
IRREGULAR_FUTURE_STEMS = {
    "être": "ser", "avoir": "aur", "aller": "ir", "faire": "fer", "pouvoir": "pourr",
    "devoir": "devr", "savoir": "saur", "vouloir": "voudr", "voir": "verr",
    "revoir": "reverr", "envoyer": "enverr", "renvoyer": "renverr", "falloir": "faudr",
    "valoir": "vaudr", "courir": "courr", "mourir": "mourr", "recevoir": "recevr",
    "percevoir": "percevr", "apercevoir": "apercevr", "concevoir": "concevr",
    "décevoir": "décevr", "pleuvoir": "pleuvr", "asseoir": "assiér", "acquérir": "acquerr",
    "cueillir": "cueiller", "accueillir": "accueiller", "recueillir": "recueiller",
}  # fmt: skip
PASSE_SIMPLE_ENDINGS = ("a", "as", "âmes", "âtes", "èrent", "it", "is", "îmes", "îtes", "irent",
                        "ut", "us", "ûmes", "ûtes", "urent", "int", "ins", "înmes", "întes",
                        "inrent")  # fmt: skip


def future_stems(lemma: str) -> set[str]:
    lemma = lemma.lower()
    stems = set()
    if lemma in IRREGULAR_FUTURE_STEMS:
        stems.add(IRREGULAR_FUTURE_STEMS[lemma])
    for base, stem in (("venir", "viendr"), ("tenir", "tiendr")):
        if lemma.endswith(base):  # obtenir: obtiendr-ez
            stems.add(lemma[: -len(base)] + stem)
    if lemma.endswith(("er", "ir")):
        stems.add(lemma)
    if lemma.endswith("yer"):
        stems.add(lemma[:-3] + "ier")  # payer: paier-ez, employer: emploier-ez
    if lemma.endswith("re"):
        stems.add(lemma[:-1])  # prendre: prendr-ez
    return stems


def _loose(stem: str) -> str:
    """achèter and acheter, appeller and appeler compare equal."""
    return re.sub(r"([lt])\1", r"\1", _plain(stem))


def verb_tense(t: Token) -> str | None:
    """'future' or 'conditional' when the verb form is one, from its ending and lemma."""
    if t.pos_ not in ("VERB", "AUX") or "Part" in t.morph.get("VerbForm"):
        return None
    form = t.lower_
    stems = future_stems(t.lemma_)
    if not stems:
        return None
    loose = {_loose(s) for s in stems}
    for endings, name in ((CONDITIONAL_ENDINGS, "conditional"), (FUTURE_ENDINGS, "future")):
        for ending in endings:
            if form.endswith(ending) and len(form) > len(ending):
                stem = form[: -len(ending)] + "r"
                if stem in stems or _loose(stem) in loose:
                    return name
    return None


# -ir verbs whose singular passé simple differs from the present: "il part", "il partit".
IR_THIRD_GROUP = ("partir", "sortir", "dormir", "sentir", "servir", "mentir", "ouvrir",
                  "offrir", "couvrir", "souffrir", "cueillir", "bouillir", "faillir",
                  "saillir")  # fmt: skip


def _present_singular(t: Token) -> bool:
    """'il agit', 'je finis', 'il dit', 'cela suffit': the present and the passé simple
    of second-group -ir verbs and of -ire verbs share the singular, and the parser
    tags some of them Past. A plain letter means the present."""
    lemma, form = t.lemma_.lower(), t.lower_
    if lemma.endswith("ire"):
        stem = lemma[:-3]
    elif lemma.endswith("ir") and not lemma.endswith(IR_THIRD_GROUP):
        stem = lemma[:-2]
    else:
        return False
    return form in (stem + "is", stem + "it")


def is_passe_simple(t: Token) -> bool:
    morph = t.morph
    return (
        t.pos_ in ("VERB", "AUX")
        and "Past" in morph.get("Tense")
        and "Fin" in morph.get("VerbForm")
        and "Ind" in morph.get("Mood")
        and t.lower_.endswith(PASSE_SIMPLE_ENDINGS)
        and _has_subject(t)  # "un acte interdit par la loi" is a participle
        and not any(c.dep_ in AUX_DEPS for c in t.children)  # "il est interdit"
        and verb_tense(t) is None
        and not _present_singular(t)
    )


PARTICIPLE_ENDINGS = ("é", "ée", "és", "ées", "i", "ie", "is", "ies", "u", "ue", "us", "ues",
                      "û", "ûe", "ûs", "ûes", "it", "ite", "its", "ites", "ert", "erte",
                      "erts", "ertes", "ort", "orte", "orts", "ortes", "int", "inte", "ints",
                      "intes", "os", "ose", "oses")  # fmt: skip
# Participles that after "être" usually describe a state, not an action: "le bureau
# est fermé", "vous êtes assuré". Without an agent or a compound tense they are no
# passive.
STATIVE_PARTICIPLES = frozenset(
    {"fermer", "ouvrir", "situer", "naître", "marier", "divorcer", "séparer", "pacser",
     "handicaper", "domicilier", "âger", "assurer", "inscrire", "concerner", "intéresser",
     "connaître", "occuper", "installer", "habiller", "fatiguer", "presser", "interdire",
     "permettre", "autoriser", "obliger"}
)  # fmt: skip


def _participle_like(t: Token) -> bool:
    word = t.lower_
    return word.endswith(PARTICIPLE_ENDINGS) and not word.endswith(("ent", "ant", "ents", "ants"))


def passive_constructions(sent: Span) -> list[tuple[str, bool]]:
    """Passive constructions as (evidence, strong). Strong: with an agent (par ...), in
    a compound tense (a été envoyé), after a modal verb or aller (doit être envoyé), or
    in the future (sera envoyé). A plain present (est envoyé) may describe a state; it
    is weak, and the participles of STATIVE_PARTICIPLES are left out."""
    found = []
    for t in sent:
        if t.pos_ not in ("VERB", "AUX") or "Part" not in t.morph.get("VerbForm"):
            continue
        aux = [c for c in t.children if c.dep_ == "aux:pass" and c.lemma_ == "être"]
        if not aux or not _participle_like(t):
            continue
        be = aux[0]
        agent = any(
            c.dep_ == "obl:agent" and any(x.lower_ == "par" for x in c.children) for c in t.children
        )
        strong = (
            agent
            or "Part" in be.morph.get("VerbForm")  # a été envoyé
            or "Inf" in be.morph.get("VerbForm")  # doit être envoyé
            or verb_tense(be) is not None  # sera envoyé
            or any(c.dep_ == "aux:tense" for c in t.children)
        )
        if not strong and t.lemma_.lower() in STATIVE_PARTICIPLES:
            continue
        found.append((_span_text(sent, be, t), strong))
    return found


def genitives(sent: Span) -> list[tuple[Token, str]]:
    """French has no genitive case; "de" phrases are the recommended form."""
    return []


def _span_text(sent: Span, a: Token, b: Token) -> str:
    first, last = sorted((a, b), key=lambda t: t.i)
    if last.i - first.i <= 4:
        return sent.doc[first.i : last.i + 1].text
    return f"{first.text} ... {last.text}"


def _words_before(t: Token, n: int) -> str:
    """The n words before a token, lowercase, elisions joined: "jusqu'à ce"."""
    start = max(t.sent.start, t.i - n)
    text = " ".join(_norm(x.text) for x in t.doc[start : t.i])
    return text.replace("' ", "'")


# -- sentence structure ------------------------------------------------------------


LEN_TOLERANCE = 3  # words over the limit that are a warning, not an error (as in German)


@rule(
    "LEN-01-FR",
    lang=FR,
    title="At most N words per sentence",
    severity=sev("error"),
    scope="sentence",
    guide="Écrivez des phrases courtes : au plus {max_words} mots par phrase.",
    kinds=SENTENCE_KINDS,
)
def len_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    n = word_count(sent)
    limit = ctx.params.max_words
    if n > limit:
        yield hit(
            "LEN-01-FR",
            words=n,
            limit=limit,
            level=ctx.level,
            evidence=sent.text,
            severity="error" if n > limit + LEN_TOLERANCE else "warn",
        )


@rule(
    "LEN-02-FR",
    lang=FR,
    title="One clause per sentence; no subordinate clauses",
    severity=sev("error", "warn"),
    scope="sentence",
    guide={
        "A2": "Une seule information par phrase. Pas de subordonnée : pas de phrase avec "
        "parce que, que, si, quand, pour que, pour + verbe ou une relative avec qui, que, "
        "dont, où. Écrivez plutôt 2 phrases courtes.",
        "B1": "Au plus une subordonnée par phrase. Écrivez plutôt 2 phrases courtes.",
    },
    kinds=SENTENCE_KINDS,
)
def len_02(sent: Span, ctx: Context) -> Iterator[Hit]:
    limit = ctx.params.max_clauses
    worst = max(clause_parts(sent), key=clause_count)
    clauses = clause_count(worst)
    if clauses <= limit:
        return
    # As in German: one clause too many is a warning, nested clauses are an error.
    severity = "warn" if clauses == limit + 1 else "error"
    openers = subordinators(worst)
    # The suggestion is the rewrite recipe for the conjunction (rules/recipes.py).
    if openers:
        yield hit(
            "LEN-02-FR.sub",
            opener=openers[0],
            clauses=clauses,
            limit=limit,
            level=ctx.level,
            evidence=sent.text,
            suggestion=recipe_fr(openers[0], sent.text),
            severity=severity,
        )
    else:
        yield hit(
            "LEN-02-FR.main",
            clauses=clauses,
            limit=limit,
            level=ctx.level,
            evidence=sent.text,
            suggestion=recipe_fr(None),
            severity=severity,
        )


def _conjuncts(token: Token) -> list[Token]:
    items = [token]
    stack = [token]
    while stack:
        t = stack.pop()
        for c in t.children:
            if c.dep_ == "conj":
                items.append(c)
                stack.append(c)
    return items


_NOMINAL = ("NOUN", "PROPN", "ADJ", "NUM")


def _segment(tokens: list[Token]) -> bool:
    """A short noun phrase: at most 6 words, a noun or adjective, no verb."""
    return (
        0 < len(tokens) <= 6
        and any(t.pos_ in _NOMINAL for t in tokens)
        and not any(t.pos_ in ("VERB", "AUX") for t in tokens)
    )


def _comma_list(sent: Span) -> str | None:
    """'votre passeport, votre carte d'assurance et une photo': noun phrases separated by
    commas and a final et or ou. The parser often attaches such lists wrongly."""
    tokens = list(sent)
    for k, t in enumerate(tokens):
        if t.lower_ not in ("et", "ou") or t.pos_ != "CCONJ":
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
        first = j - 1  # the item before the comma ends with a noun, adjective or number
        if tokens[first].pos_ not in _NOMINAL:
            continue
        start = first
        while (
            start > 0
            and not tokens[start - 1].is_punct
            and tokens[start - 1].pos_ in ("NOUN", "PROPN", "ADJ", "NUM", "DET", "ADP")
        ):
            start -= 1
        return sent.doc[tokens[start].i : after[-1].i + 1].text
    return None


@rule(
    "LEN-03-FR",
    lang=FR,
    title="Enumerations of three or more items become a list",
    severity=sev("warn"),
    scope="sentence",
    guide="Vous citez 3 choses ou plus ? Faites une liste.",
    kinds=("sentence",),
)
def len_03(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        if t.dep_ == "conj" or not any(c.dep_ == "conj" for c in t.children):
            continue
        items = [i for i in _conjuncts(t) if i.pos_ in ("NOUN", "PROPN", "VERB", "ADJ")]
        if len(items) >= 3:
            yield hit(
                "LEN-03-FR",
                items=len(items),
                evidence=", ".join(i.text for i in sorted(items, key=lambda i: i.i)),
            )
            return
    listed = _comma_list(sent)
    if listed:
        yield hit("LEN-03-FR.commas", evidence=listed)


# -- grammar ------------------------------------------------------------------------


@rule(
    "GRAM-01-FR",
    lang=FR,
    title="No passive",
    severity=sev("error", "warn"),
    scope="sentence",
    guide="Pas de voix passive. Dites qui fait quoi. Pas : Le formulaire est contrôlé par "
    "l'office. Mais : L'office contrôle le formulaire.",
)
def gram_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    for evidence, strong in passive_constructions(sent):
        if strong:
            yield hit("GRAM-01-FR", found=evidence, evidence=evidence)
        else:
            # "est envoyé" may be an action or a state: a warning at most.
            yield hit(
                "GRAM-01-FR.state",
                found=evidence,
                evidence=evidence,
                severity="warn" if ctx.level == "A2" else "info",
            )


SUBJUNCTIVE_CONJUNCTIONS = (
    "pour que", "afin que", "bien que", "avant que", "sans que", "à condition que",
    "à moins que", "à ce que", "pourvu que", "en attendant que", "de peur que",
    "de crainte que", "pour autant que",
)  # fmt: skip
# Verbs and adjectives after which "que" takes the subjunctive: "il faut que",
# "il est important que", "il vaut mieux que".
SUBJUNCTIVE_GOVERNORS = frozenset(
    {"falloir", "vouloir", "souhaiter", "exiger", "désirer", "ordonner", "craindre",
     "douter", "regretter", "préférer", "attendre", "demander", "permettre", "empêcher",
     "accepter", "refuser", "proposer", "suggérer", "recommander", "aimer", "valoir",
     "pouvoir", "important", "nécessaire", "possible", "impossible", "obligatoire",
     "indispensable", "essentiel", "préférable", "souhaitable", "normal", "dommage",
     "urgent", "utile", "juste", "naturel", "temps", "mieux"}
)  # fmt: skip
# Forms that are only ever subjunctive (soyez, ayez and sachez are also imperatives).
UNAMBIGUOUS_SUBJUNCTIVE = frozenset(
    {"soit", "soient", "sois", "ait", "aient", "aies", "fasse", "fasses", "fassent",
     "fassions", "fassiez", "puisse", "puisses", "puissent", "puissions", "puissiez",
     "sachions", "sachiez", "veuille", "veuilles", "veuillent", "aille", "ailles", "aillent",
     "vaille", "faille"}
)  # fmt: skip


def subjunctives(sent: Span) -> list[tuple[Token, str]]:
    """Subjunctive verbs as (verb, reason): after a conjunction or a verb that requires
    it (pour que, il faut que), or a form that is always subjunctive (puisse, fasse)."""
    found: dict[int, tuple[Token, str]] = {}
    for t in sent:
        word = _norm(t.text)
        if t.dep_ != "mark" or word not in ("que", "qu'", "quoique", "quoiqu'"):
            continue
        clause = t.head
        if not is_finite(clause):
            continue
        before = _words_before(t, 3) + " que"
        conjunction = next((c for c in SUBJUNCTIVE_CONJUNCTIONS if before.endswith(c)), None)
        governor = clause.head if clause.dep_ in ("ccomp", "csubj") else None
        if word.startswith("quoiqu"):
            found[clause.i] = (clause, "quoique")
        elif conjunction:
            found[clause.i] = (clause, conjunction)
        elif governor is not None and (
            governor.lemma_.lower() in SUBJUNCTIVE_GOVERNORS
            or governor.lower_ in SUBJUNCTIVE_GOVERNORS
        ):
            found[clause.i] = (clause, f"{governor.text} que")
    for t in sent:
        if t.i in found or t.pos_ not in ("VERB", "AUX"):
            continue
        if t.lower_ in UNAMBIGUOUS_SUBJUNCTIVE or (
            "Sub" in t.morph.get("Mood")
            and any(_norm(c.text) in ("que", "qu'") for c in t.children)
        ):
            found[t.i] = (t, "subjunctive form")
    return [found[i] for i in sorted(found)]


@rule(
    "GRAM-03-FR",
    lang=FR,
    title="No subjunctive or conditional",
    severity=sev("warn"),
    scope="sentence",
    guide="Pas de subjonctif et pas de conditionnel (pas : il faudrait, vous pourriez, pour "
    "que vous puissiez). Écrivez directement : vous devez, vous pouvez.",
)
def gram_03(sent: Span, ctx: Context) -> Iterator[Hit]:
    for verb, reason in subjunctives(sent):
        if reason == "subjunctive form":
            yield hit("GRAM-03-FR", found=verb.text, evidence=verb.text)
        else:
            yield hit("GRAM-03-FR.after", reason=reason, found=verb.text, evidence=verb.text)
    for t in sent:
        if verb_tense(t) == "conditional":
            yield hit("GRAM-03-FR.conditional", found=t.text, evidence=t.text)


_ALLER = {("1", "Sing"): "vais", ("2", "Sing"): "vas", ("3", "Sing"): "va",
          ("1", "Plur"): "allons", ("2", "Plur"): "allez", ("3", "Plur"): "vont"}  # fmt: skip


@rule(
    "GRAM-04-FR",
    lang=FR,
    title="Present and passé composé; no passé simple, no futur simple where aller + "
    "infinitive works",
    severity=sev("warn"),
    scope="sentence",
    guide="Écrivez au présent. Pour le passé, prenez le passé composé : vous avez reçu une "
    "lettre. Pour le futur, prenez aller + verbe : vous allez recevoir une lettre.",
)
def gram_04(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        if verb_tense(t) == "future":
            person = (t.morph.get("Person") or ["3"])[0]
            number = (t.morph.get("Number") or ["Sing"])[0]
            aller = _ALLER.get((person, number))
            suggestion = None
            if aller and not t.dep_.startswith("aux"):
                suggestion = f"{aller} {t.lemma_.lower()}"
            yield hit("GRAM-04-FR", found=t.text, evidence=t.text, suggestion=suggestion)
        elif is_passe_simple(t):
            yield hit("GRAM-04-FR.passe_simple", found=t.text, evidence=t.text)


NOMINAL_SUFFIXES = ("tion", "tions", "sion", "sions", "ment", "ments", "age", "ages", "ance",
                    "ances", "ence", "ences", "ité", "ités", "ure", "ures", "isme",
                    "ismes")  # fmt: skip
EVERYDAY_ZIPF = 4.0  # nouns at least this frequent count as everyday words
# Everyday or concrete words with a nominal suffix: "votation" is everyday Swiss French.
NOMINAL_ALLOWED = frozenset(
    {"votation", "votations", "ambulance", "ambulances", "permanence", "permanences"}
)
# Verbs that carry no meaning of their own next to a nominalisation:
# "le versement intervient", "procéder au dépôt", "effectuer le paiement".
LIGHT_VERBS = frozenset(
    {"effectuer", "procéder", "opérer", "intervenir", "réaliser", "exécuter", "accomplir",
     "entreprendre"}
)  # fmt: skip
NOMINAL_PREPOSITIONS = ("lors de", "lors du", "lors des", "en vue de", "en vue du", "en cas de",
                        "suite à", "suite au", "aux fins de", "à des fins de", "par voie de",
                        "en raison de", "en raison du", "dans le cadre de", "dans le cadre du",
                        "à titre de", "en matière de", "au moyen de", "au moyen du",
                        "moyennant")  # fmt: skip


def nominal_context(t: Token) -> bool:
    """The noun sits in nominal style: with a light verb, after a nominal preposition
    (lors de), or with a de attribute (le versement de la prestation)."""
    head = t.head
    if head.i != t.i and head.lemma_.lower() in LIGHT_VERBS:
        return True
    before = re.sub(r" (?:le|la|les|l')$", "", _words_before(t, 5))
    if any(before.endswith(p) for p in NOMINAL_PREPOSITIONS):
        return True
    return any(
        c.dep_ == "nmod"
        and c.pos_ in ("NOUN", "PROPN")
        and any(x.dep_ == "case" and _norm(x.text) in ("de", "du", "des", "d'") for x in c.children)
        for c in t.children
    )


def _compound_part(t: Token) -> bool:
    """A bare noun joined by de to the noun before it names a kind of thing, like a
    German compound: "carnet de vaccination", "carte de stationnement"."""
    return (
        t.dep_ == "nmod"
        and t.head.pos_ == "NOUN"
        and t.head.i < t.i
        and not any(c.dep_ == "det" for c in t.children)
        and any(c.dep_ == "case" and _norm(c.text) in ("de", "d'") for c in t.children)
    )


@rule(
    "GRAM-05-FR",
    lang=FR,
    title="No nominalisations",
    severity=sev("warn"),
    scope="sentence",
    guide="Des verbes plutôt que des noms. Pas : Le dépôt de la demande s'effectue en ligne. "
    "Mais : Vous faites la demande sur internet.",
)
def gram_05(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        if t.pos_ != "NOUN" or ctx.in_glossary(t.text):
            continue
        word = t.lower_
        if len(word) <= 6 or not word.endswith(NOMINAL_SUFFIXES) or word in NOMINAL_ALLOWED:
            continue
        if max(zipf(word, FR), zipf(t.lemma_.lower(), FR)) >= EVERYDAY_ZIPF:
            continue  # information, demande, paiement: everyday words
        if nominal_context(t) and not _compound_part(t):
            yield hit("GRAM-05-FR", found=t.text, evidence=t.text)
        else:
            yield hit("GRAM-05-FR.abstract", found=t.text, evidence=t.text, severity="info")


_PRONOUNS = {
    "il": ("Masc", "Sing"), "elle": ("Fem", "Sing"), "ils": ("Masc", "Plur"),
    "elles": ("Fem", "Plur"), "le": ("Masc", "Sing"), "la": ("Fem", "Sing"),
    "celui-ci": ("Masc", "Sing"), "celle-ci": ("Fem", "Sing"), "ceux-ci": ("Masc", "Plur"),
    "celles-ci": ("Fem", "Plur"),
}  # fmt: skip


def _antecedents(pronoun: Token, ctx: Context) -> set[str]:
    gender, number = _PRONOUNS[pronoun.lower_.lstrip("-")]
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
            continue  # "ils" also stands for a mixed group
        found.add(noun.lemma_.lower())
    return found


@rule(
    "GRAM-06-FR",
    lang=FR,
    title="Pronouns only with an unambiguous reference",
    severity=sev("info"),
    scope="sentence",
    guide="Utilisez il, elle ou celui-ci seulement si on sait clairement de qui ou de quoi "
    "vous parlez. Sinon, répétez le nom.",
)
def gram_06(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        if t.pos_ != "PRON" or t.lower_.lstrip("-") not in _PRONOUNS or t.dep_ == "expl:subj":
            continue
        found = _antecedents(t, ctx)
        if not found:
            yield hit("GRAM-06-FR", found=t.text, evidence=t.text)
        elif len(found) > 1 and _PRONOUNS[t.lower_.lstrip("-")][1] == "Sing":
            options = ", ".join(sorted(found)[:3])
            yield hit("GRAM-06-FR.ambiguous", found=t.text, options=options, evidence=t.text)


@rule(
    "GRAM-07-FR",
    lang=FR,
    title="No reported speech",
    severity=sev("info"),
    scope="sentence",
    guide="Pas de discours rapporté. Dites qui dit quoi.",
)
def gram_07(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        word = _norm(t.text)
        if (word == "selon" and t.pos_ == "ADP") or (
            word == "après" and t.i > sent.start and _norm(t.doc[t.i - 1].text) == "d'"
        ):
            label = "selon" if word == "selon" else "d'après"
            yield hit("GRAM-07-FR", found=label, evidence=label)


IMPERSONAL_RE = re.compile(
    r"\bil\s+(?:convient|conviendra|conviendrait|incombe|incombera|appartient|appartiendra|"
    r"importe|sied)\b|\bil\s+y\s+a\s+lieu\b"
    r"|\bil\s+(?:est|sera)\s+(?:loisible|opportun|souhaitable|recommandé|requis)\b",
    re.IGNORECASE,
)
IMPERSONAL_SOFT_RE = re.compile(
    r"\bil\s+(?:est|sera)\s+(?:nécessaire|obligatoire|possible|important|interdit|permis|"
    r"indispensable|utile|conseillé)\s+(?:de\b|d" + _APOS + r"|que\b|qu" + _APOS + ")",
    re.IGNORECASE,
)


@rule(
    "GRAM-08-FR",
    lang=FR,
    title="No impersonal il convient de, il y a lieu de",
    severity=sev("warn"),
    scope="block",
    guide="Pas de tournures impersonnelles comme il convient de ou il y a lieu de. Dites "
    "qui doit faire quoi : vous devez.",
)
def gram_08(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in IMPERSONAL_RE.finditer(block.text):
        yield hit("GRAM-08-FR", found=m.group(0), evidence=m.group(0))
    for m in IMPERSONAL_SOFT_RE.finditer(block.text):
        yield hit("GRAM-08-FR.soft", found=m.group(0), evidence=m.group(0), severity="info")


# -- negation -----------------------------------------------------------------------

# Words that form one negation together with "ne" (French negative concord):
# "ne ... pas", "ne ... jamais rien", "ni ... ni".
CONCORD_WORDS = frozenset(
    {"pas", "point", "jamais", "plus", "rien", "personne", "aucun", "aucune", "nul", "nulle",
     "guère", "ni", "nullement", "aucunement"}
)  # fmt: skip
# Adjectives with a negative prefix that make "ce n'est pas impossible" a double negation.
NEGATIVE_ADJECTIVES = frozenset(
    {"impossible", "inutile", "illégal", "irrégulier", "incomplet", "inconnu", "insuffisant",
     "incapable", "inexact", "inacceptable", "inadmissible", "injuste", "indisponible",
     "inhabituel", "imprévu", "impayé", "illisible", "incorrect", "irrecevable",
     "inéligible", "inaccessible", "inapproprié", "invalide", "inexistant", "inévitable"}
)  # fmt: skip


def _negation_parts(sent: Span) -> list[list[Token]]:
    """Clause parts: commas, colons, et, ou, mais, car and the opener of a subordinate
    clause (si, que, qui) separate statements."""
    parts: list[list[Token]] = [[]]
    for t in sent:
        if t.text in (",", ";", ":") or (
            t.pos_ == "CCONJ" and t.lower_ in ("et", "ou", "mais", "car")
        ):
            parts.append([])
        elif (t.dep_ == "mark" and t.pos_ == "SCONJ") or "Rel" in t.morph.get("PronType"):
            parts.append([t])  # si, que, qui: a new clause ("sans" is a negation itself)
        else:
            parts[-1].append(t)
    return parts


def _negation_units(part: list[Token]) -> list[list[Token]]:
    """The logical negations of one clause part. Negative concord words count as one
    negation together; sans, non and a negative adjective each add one."""
    has_ne = any(_norm(t.text) in ("ne", "n'") for t in part)
    concord = []
    for k, t in enumerate(part):
        w = t.lower_
        if w not in CONCORD_WORDS:
            continue
        if w in ("plus", "point") and not has_ne:
            continue  # "plus d'argent" is no negation
        if w == "plus" and k > 0 and part[k - 1].lower_ == "non":
            continue  # "non plus"
        if w == "personne" and (not has_ne or any(c.dep_ == "det" for c in t.children)):
            continue  # "une personne"
        if w == "pas" and t.pos_ != "ADV":
            continue
        concord.append(t)
    others = [t for k, t in enumerate(part) if _adds_negation(t, k, part, has_ne, bool(concord))]
    units: list[list[Token]] = []
    if concord:
        repeated = [t for t in concord if t.lower_ in ("pas", "point")]
        units += [[t] for t in repeated] if len(repeated) >= 2 else [concord]
    units += [[t] for t in others]
    return units


def _adds_negation(t: Token, k: int, part: list[Token], has_ne: bool, concord: bool) -> bool:
    """sans, non or a negative adjective: a negation besides the concord words."""
    w = t.lower_
    if w == "sans":
        return has_ne or not concord  # "sans rien payer" is one negation
    if w == "non":
        return not (k + 1 < len(part) and part[k + 1].lower_ == "plus")  # "non plus"
    return t.pos_ == "ADJ" and (w in NEGATIVE_ADJECTIVES or t.lemma_.lower() in NEGATIVE_ADJECTIVES)


def _negation_text(unit: list[Token], part: list[Token]) -> str:
    tokens = list(unit)
    if unit[0].lower_ in CONCORD_WORDS:
        ne = [t for t in part if _norm(t.text) in ("ne", "n'")]
        tokens = sorted(set(ne[:1] + unit), key=lambda t: t.i)
    return " ... ".join(t.text for t in tokens)


@rule(
    "NEG-01-FR",
    lang=FR,
    title="No double negation",
    severity=sev("error"),
    scope="sentence",
    guide="Pas de double négation (pas : ce n'est pas impossible).",
)
def neg_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    for part in _negation_parts(sent):
        units = _negation_units(part)
        if len(units) >= 2:
            text = " ... ".join(_negation_text(u, part) for u in units)
            yield hit("NEG-01-FR", found=text, evidence=text)


@rule(
    "NEG-02-FR",
    lang=FR,
    title="Prefer positive formulation",
    severity=sev("info"),
    scope="sentence",
    guide="Écrivez de façon positive quand c'est possible : vous pouvez ... plutôt que vous "
    "ne pouvez pas ...",
)
def neg_02(sent: Span, ctx: Context) -> Iterator[Hit]:
    found = [(u, p) for p in _negation_parts(sent) for u in _negation_units(p)]
    if len(found) == 1:
        text = _negation_text(*found[0])
        yield hit("NEG-02-FR", found=text, evidence=text)


# -- words --------------------------------------------------------------------------

MAX_WORD_LETTERS = 12  # LEX-01-FR, both levels (docs/rules.md)
# Administrative words and phrases with an everyday equivalent, as in the Italian
# "burocratese" list of the rule catalogue: "moyennant" is "avec", "dûment" is "bien".
BUREAUCRATIC_RE = re.compile(
    r"\b(?:émoluments?|moyennant|nonobstant|dûment|susmentionnée?s?|susdite?s?|"
    r"ledit|ladite|lesdite?s|ci-jointe?s?|ci-après|afférente?s?|subséquemment|"
    r"préalablement|le\s+cas\s+échéant|en\s+vertu\s+d(?:e|u|es)|faute\s+de\s+quoi|"
    r"en\s+l" + _APOS + r"espèce|par\s+la\s+présente|eu\s+égard\s+(?:à|au|aux)|"
    r"aux\s+termes\s+d(?:e|u|es)|en\s+sus)\b",
    re.IGNORECASE,
)


@rule(
    "LEX-01-FR",
    lang=FR,
    title="No long words; prefer the everyday synonym",
    severity=sev("info"),
    scope="sentence",
    guide="Évitez les mots longs et les mots de l'administration (pas : émolument, "
    "moyennant, le cas échéant, dûment). Prenez le mot court et connu.",
)
def lex_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    for m in BUREAUCRATIC_RE.finditer(sent.text):
        yield hit(
            "LEX-01-FR.administrative", found=m.group(0), evidence=m.group(0), severity="warn"
        )
    for t in sent:
        if t.like_url or t.like_email or ctx.in_glossary(t.text):
            continue
        for part in re.split(_APOS + "|-", t.text):
            letters = sum(ch.isalpha() for ch in part)
            if letters > MAX_WORD_LETTERS:
                yield hit("LEX-01-FR", found=t.text, letters=letters, evidence=t.text)
                break


ABBREVIATIONS = [
    r"p\.\s?ex\.", r"etc\.", r"cf\.", r"env\.", r"c\.-à-d\.", r"c\.\s?à\s?d\.", r"resp\.",
    r"év\.", r"évent\.", r"y\.?\s?c\.", r"s\.v\.p\.", r"tél\.", r"max\.", r"min\.", r"ss\.",
    r"ibid\.", r"suiv\.", r"(?:art|al|ch|let|lit|p|pp|vol)\.(?=\s?\d)",
    r"(?:[nN]o|n" + _DEGREE + r"|n" + _ORDINAL_O + r")\.?(?=\s?\d)", r"Fr\.(?=\s?\d)",
    r"M\.(?=\s[A-ZÀ-Ý])", r"MM\.(?=\s)", r"Mmes?\b", r"Mlles?\b", r"Dr(?=\s[A-Z])",
]  # fmt: skip
ABBREVIATION_RE = re.compile(r"(?<![\w.])(?:" + "|".join(ABBREVIATIONS) + r")")
_WEEKDAYS = "lu|ma|me|je|ve|sa|di|lun|mar|mer|jeu|ven|sam|dim"
WEEKDAY_RANGE_RE = re.compile(
    r"(?<![\w.])(?:"
    + _WEEKDAYS
    + r")\.?\s?(?:["
    + DASHES
    + r"]|à|au)\s?(?:"
    + _WEEKDAYS
    + r")(?!["
    + _LETTER
    + r"])\.?"
)
MONTH_ABBREVIATION_RE = re.compile(r"\b\d{1,2}\.?\s(?:janv|févr|avr|juil|sept|oct|nov|déc)\.")
ACRONYM_RE = re.compile(
    r"(?<![\w-])(?:[A-ZÀ-Ý]{2,6}s?|[A-ZÀ-Ý][a-zà-ÿ]{0,4}[A-ZÀ-Ý][A-Za-zÀ-ÿ]{0,4})(?![\w-])"
)  # LAVS, OFAE, and law abbreviations in mixed case such as LAMal or LHand
ACRONYMS_ALLOWED = frozenset({"CHF", "AVS", "AI", "CFF", "PDF", "WC", "SMS", "TV", "ID", "OK"})
# Words in capitals for emphasis, as voting texts write them: "Votez OUI".
EMPHASIS_WORDS = frozenset(
    {"OUI", "NON", "PAS", "ET", "OU", "NE", "SEULEMENT", "AUSSI", "JAMAIS", "TOUT", "TOUS"}
)


def _masked_links(text: str) -> str:
    text = mask(text, [m.span() for m in URL_RE.finditer(text)])
    return mask(text, [m.span() for m in EMAIL_RE.finditer(text)])


@rule(
    "LEX-02-FR",
    lang=FR,
    title="No abbreviations except common ones",
    severity=sev("warn"),
    scope="block",
    guide="Pas d'abréviations (pas : p. ex., etc., art.). Vous pouvez écrire CHF, AVS, AI et "
    "CFF. Expliquez les autres abréviations.",
)
def lex_02(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    text = _masked_links(block.text)
    letters = [ch for ch in text if ch.isalpha()]
    all_caps = len(letters) >= 8 and sum(ch.isupper() for ch in letters) >= 0.8 * len(letters)
    for regex in (ABBREVIATION_RE, MONTH_ABBREVIATION_RE):
        for m in regex.finditer(text):
            found = m.group(0).strip()
            yield hit("LEX-02-FR", found=found, evidence=found)
    for m in WEEKDAY_RANGE_RE.finditer(text):
        yield hit("LEX-02-FR.weekdays", found=m.group(0), evidence=m.group(0))
    for m in ACRONYM_RE.finditer(text):
        acronym = m.group(0)
        if acronym[-1] == "s" and acronym[:-1].isupper():
            acronym = acronym[:-1]  # plural s
        if (
            acronym in ACRONYMS_ALLOWED
            or acronym in EMPHASIS_WORDS
            or (len(acronym) >= 4 and is_known(acronym.lower(), FR, min_zipf=3.5))  # TOUR
            or (all_caps and is_known(acronym.lower(), FR, min_zipf=3.0))  # ÉLECTION DU
            or re.fullmatch(r"[IVXLC]+", acronym)
        ):
            continue
        if acronym in ctx.introduced or ctx.in_glossary(acronym):
            yield hit("LEX-02-FR.explained", found=acronym, evidence=acronym, severity="info")
            continue
        yield hit("LEX-02-FR.acronym", found=acronym, evidence=acronym)


@rule(
    "LEX-03-FR",
    lang=FR,
    title="No foreign words, anglicisms, jargon",
    severity=sev("info"),
    scope="sentence",
    guide="Prenez des mots simples et connus. Pas de mots étrangers et pas de mots "
    "techniques. Si un mot difficile est nécessaire, expliquez-le dans le lexique.",
)
def lex_03(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        if t.pos_ not in ("NOUN", "VERB", "ADJ", "ADV"):
            continue
        parts = [p for p in re.split(_APOS + "|-", t.text) if p]
        if not parts or not all(p.isalpha() for p in parts) or len(t.text) < 4:
            continue
        if t.text.isupper():
            continue  # abbreviations are LEX-02-FR
        if ctx.in_glossary(t.text):
            continue
        if max(zipf(t.lower_, FR), zipf(t.lemma_.lower(), FR)) >= 2.5:
            continue
        if len(parts) > 1 and all(zipf(p.lower(), FR) >= 3.0 for p in parts):
            continue  # pare-brise
        yield hit("LEX-03-FR", found=t.text, evidence=t.text)


RARE_PUNCTUATION_RE = re.compile(r"[;()\[\]{}&]")
SLASH_RE = re.compile(r"(?<=[" + _LETTER + r"])\s?/\s?(?=[" + _LETTER + r"])")


@rule(
    "LEX-04-FR",
    lang=FR,
    title="Rare punctuation",
    severity=sev("warn"),
    scope="block",
    guide="Pas de signes rares : pas de point-virgule, pas de parenthèses, pas de & et pas "
    "de / entre les mots.",
)
def lex_04(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    text = _masked_links(block.text)
    seen = set()
    for m in RARE_PUNCTUATION_RE.finditer(text):
        char = {")": "(", "]": "[", "}": "{"}.get(m.group(0), m.group(0))
        if char not in seen:
            seen.add(char)
            yield hit("LEX-04-FR", found=m.group(0), evidence=m.group(0))
    for m in SLASH_RE.finditer(text):
        word = block.text[max(0, m.start() - 12) : m.end() + 12].strip()
        yield hit("LEX-04-FR.slash", evidence=word)


_FEMININE = "(?:e|ne|le|te|se|re|euse|rice|ice|ève|ive|ère|fe|che)"
INCLUSIVE_RE = re.compile(
    r"["
    + _LETTER
    + r"]+(?:["
    + MEDIOPUNKT
    + r".]"
    + _FEMININE
    + r"(?:["
    + MEDIOPUNKT
    + r".]?s)?|\("
    + _FEMININE
    + r"\)s?)(?!["
    + _LETTER
    + r"])"
)  # employé·e·s, employé.e.s, employé(e)s, citoyen·ne·s, tou·te·s


@rule(
    "LEX-05-FR",
    lang=FR,
    title="Inclusive forms without typographic devices",
    severity=sev("info"),
    scope="block",
    guide="Pas d'écriture inclusive avec des points ou des parenthèses (employé·e·s). Écrivez "
    "les deux formes : les employées et les employés.",
)
def lex_05(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in INCLUSIVE_RE.finditer(_masked_links(block.text)):
        yield hit("LEX-05-FR", found=m.group(0), evidence=m.group(0))


ROLE_NOUN_RE = re.compile(
    r"\b(?:le|la|les|l" + _APOS + r"|du|des|au|aux|chaque|tout|toute|tous|toutes)\s?"
    r"(?:requérante?s?|demandeur|demandeuse|demandeurs|demandeuses|assurée?s?|"
    r"bénéficiaires?|contribuables?|intéressée?s?|administrée?s?|titulaires?|"
    r"ayants?\s+droit|preneurs?\s+d" + _APOS + r"assurance|ressortissante?s?|justiciables?|"
    r"personnes?\s+concernées?)\b",
    re.IGNORECASE,
)


@rule(
    "LEX-06-FR",
    lang=FR,
    title="Direct address with vous",
    severity=sev("info"),
    scope="block",
    guide="Parlez directement à la lectrice ou au lecteur avec vous.",
)
def lex_06(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in ROLE_NOUN_RE.finditer(block.text):
        # A text that never says vous gets the reminder with the finding.
        yield hit(
            "LEX-06-FR" if ctx.addresses_reader else "LEX-06-FR.no_address",
            found=m.group(0),
            evidence=m.group(0),
        )


# -- numbers, dates, times, amounts -----------------------------------------------

CARDINAL_WORDS = {
    "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8,
    "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14,
    "quinze": 15, "seize": 16, "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50,
    "soixante": 60, "septante": 70, "huitante": 80, "octante": 80, "nonante": 90,
    "cent": 100, "mille": 1000,
}  # fmt: skip
ORDINAL_RE = re.compile(r"^(deux|trois|quatr|cinqu|six|sept|huit|neuv|dix|onz|douz)ièmes?$")
_ORDINAL_DIGITS = {"deux": 2, "trois": 3, "quatr": 4, "cinqu": 5, "six": 6, "sept": 7,
                   "huit": 8, "neuv": 9, "dix": 10, "onz": 11, "douz": 12}  # fmt: skip


@rule(
    "NUM-01-FR",
    lang=FR,
    title="Numbers as digits, except un/une",
    severity=sev("warn"),
    scope="sentence",
    guide="Écrivez les nombres en chiffres : 2, 3, 12. Seuls un et une s'écrivent en lettres.",
)
def num_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        lower = t.lower_
        if lower in CARDINAL_WORDS and t.pos_ == "NUM":
            if lower == "cent" and t.i > sent.start and t.doc[t.i - 1].lower_ == "pour":
                continue  # "pour cent" is NUM-06-FR
            yield hit(
                "NUM-01-FR",
                found=t.text,
                evidence=t.text,
                suggestion=str(CARDINAL_WORDS[lower]),
            )
        elif m := ORDINAL_RE.match(lower):
            yield hit(
                "NUM-01-FR.ordinal",
                found=t.text,
                evidence=t.text,
                suggestion=f"{_ORDINAL_DIGITS[m.group(1)]}e",
            )
        elif "-" in lower and all(p in CARDINAL_WORDS or p == "et" for p in lower.split("-")):
            yield hit("NUM-01-FR.compound", found=t.text, evidence=t.text)


_IDENTIFIER_BEFORE = re.compile(
    r"(?:n" + _DEGREE + r"|n" + _ORDINAL_O + r"|no\.?|numéro|formulaire|art\.?|article|al\.?|"
    r"alinéa|ch\.?|chiffre|case postale|CP|NPA|code postal|bureau|salle|ligne|bus|tram|"
    r"compte|IBAN|dossier|référence|réf\.?|CH-)\s?$",
    re.IGNORECASE,
)
_CURRENCY_NEAR = re.compile(r"CHF|Fr\.|francs?|centimes?", re.IGNORECASE)
BIG_NUMBER_RE = re.compile(
    r"(?<![\d'.,:/+" + chr(0x2019) + r"])\d{4,}(?![\d'" + chr(0x2019) + r"])"
)


def _masked_numbers_text(text: str) -> str:
    spans = [m.span() for r in (URL_RE, EMAIL_RE, PHONE_RE) for m in r.finditer(text)]
    spans += [m.span() for r in (DATE_ISO_RE, DATE_NUM_RE, DATE_SLASH_RE) for m in r.finditer(text)]
    spans += [m.span() for m in re.finditer(r"\bCH\d{2}(?:\s?[\dA-Z]{4}){4,7}", text)]  # IBAN
    return mask(text, spans)


@rule(
    "NUM-02-FR",
    lang=FR,
    title="Thousands separator with a space: 1 500",
    severity=sev("warn"),
    scope="block",
    guide="Les grands nombres s'écrivent avec une espace : 1 500 francs, 500 000.",
)
def num_02(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    text = _masked_numbers_text(block.text)
    for m in BIG_NUMBER_RE.finditer(text):
        digits = m.group(0)
        before, after = text[max(0, m.start() - 14) : m.start()], text[m.end() : m.end() + 12]
        if _IDENTIFIER_BEFORE.search(before):
            continue
        currency = bool(_CURRENCY_NEAR.search(before[-6:]) or _CURRENCY_NEAR.search(after[:10]))
        if len(digits) == 4 and not currency:
            continue  # years, postal codes and form numbers have 4 digits
        yield hit(
            "NUM-02-FR",
            found=digits,
            evidence=digits,
            suggestion=format_thousands(digits, FR),
        )


# "au 15.09", "dès le 1.3": a day and a month without a year or a final dot. The
# word before tells it from a decimal number.
DATE_SHORT_RE = re.compile(
    r"(?<![\w.])(?:au|le|du|dès|jusqu" + _APOS + r"au)\s(\d{1,2})\.(\d{1,2})(?![\d.,])",
    re.IGNORECASE,
)


@rule(
    "NUM-03-FR",
    lang=FR,
    title="Date 4 février 2020",
    severity=sev("warn"),
    scope="block",
    guide="Une date s'écrit ainsi : 4 février 2026.",
)
def num_03(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    text = mask(block.text, [m.span() for r in (URL_RE, PHONE_RE) for m in r.finditer(block.text)])
    for m in DATE_SHORT_RE.finditer(text):
        canonical = canonical_date(int(m.group(1)), int(m.group(2)), None)
        if canonical is not None:
            found = m.group(0).split()[-1]
            yield hit(
                "NUM-03-FR", found=found, evidence=found, suggestion=format_date(canonical, FR)
            )
    for regex, order in ((DATE_ISO_RE, "ymd"), (DATE_NUM_RE, "dmy"), (DATE_SLASH_RE, "dmy")):
        for m in regex.finditer(text):
            if order == "ymd":
                y, mo, d = m.group(1), m.group(2), m.group(3)
            else:
                d, mo, y = m.group(1), m.group(2), m.group(3)
            canonical = canonical_date(int(d), int(mo), int(y) if y else None)
            if canonical is None:
                continue
            yield hit(
                "NUM-03-FR",
                found=m.group(0).strip(),
                evidence=m.group(0).strip(),
                suggestion=format_date(canonical, FR),
            )


_TIME = r"\d{1,2}(?:\s?h(?:\s?\d{2})?|[.:]\d{2})"
TIME_RANGE_RE = re.compile(
    r"(?<![\d.:,])(" + _TIME + r")\s?[" + DASHES + r"]\s?(" + _TIME + r")(?![\d])"
    r"|(?<![\d.:,])(\d{1,2})\s?[" + DASHES + r"]\s?(\d{1,2})\s?h\b"
)
TIME_COLON_RE = re.compile(r"(?<![\d.:])(\d{1,2}):(\d{2})(?!\d)(?:\s?h\b)?")
TIME_TIGHT_RE = re.compile(r"(?<![\d.:,])(\d{1,2})h(\d{2})?(?![\w])")  # 9h, 16h30
TIME_DOT_RE = re.compile(r"(?<![\d.:,])(\d{1,2})\.(\d{2})\s?h(?:eures?)?\b")  # 9.30 h


def _time_text(hour: str | int, minute: str | None) -> str:
    return f"{int(hour)} h {minute or '00'}"


def _parse_time(text: str) -> tuple[int, str | None] | None:
    m = re.match(r"(\d{1,2})(?:\s?h\s?(\d{2})?|[.:](\d{2}))?", text.strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), m.group(2) or m.group(3)
    if hour > 24 or (minute is not None and int(minute) > 59):
        return None
    return hour, minute


@rule(
    "NUM-04-FR",
    lang=FR,
    title="Time 9 h 00, ranges de 9 h 00 à 12 h 00",
    severity=sev("warn"),
    scope="block",
    guide="Une heure s'écrit ainsi : 9 h 00 ou 9 h 30. Une période ainsi : de 9 h 00 à 12 h 00.",
)
def num_04(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    text = _masked_numbers_text(block.text)
    spans: list[tuple[int, int]] = []
    for m in TIME_RANGE_RE.finditer(text):
        first = _parse_time(m.group(1) or m.group(3))
        second = _parse_time(m.group(2) or m.group(4))
        if first is None or second is None:
            continue
        spans.append(m.span())
        yield hit(
            "NUM-04-FR.range",
            found=m.group(0).strip(),
            evidence=m.group(0).strip(),
            suggestion=f"de {_time_text(*first)} à {_time_text(*second)}",
        )
    text = mask(text, spans)
    for regex in (TIME_COLON_RE, TIME_TIGHT_RE, TIME_DOT_RE):
        found = []
        for m in regex.finditer(text):
            if int(m.group(1)) > 24 or (m.group(2) and int(m.group(2)) > 59):
                continue
            found.append(m.span())
            expected = _time_text(m.group(1), m.group(2))
            yield hit(
                "NUM-04-FR",
                found=m.group(0).strip(),
                expected=expected,
                evidence=m.group(0).strip(),
                suggestion=expected,
                # 8h and 16h30 are common on official Swiss pages (calibration): a note
                severity="info" if regex is TIME_TIGHT_RE else None,
            )
        text = mask(text, found)


DURATION_RE = re.compile(
    r"\d+[.,]\d\s?(?:h|heures?)\b|\d*" + _HALF + r"\s?(?:h|heures?)\b|\b\d+\s?min\b\.?"
)


@rule(
    "NUM-05-FR",
    lang=FR,
    title="Durations in words and digits: 1 heure et 30 minutes",
    severity=sev("info"),
    scope="block",
    guide="Une durée s'écrit ainsi : 1 heure et 30 minutes.",
)
def num_05(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in DURATION_RE.finditer(block.text):
        yield hit("NUM-05-FR", found=m.group(0), evidence=m.group(0))


@rule(
    "NUM-06-FR",
    lang=FR,
    title="Percent written out",
    severity=sev("warn"),
    scope="block",
    guide="Écrivez pour cent en lettres : 10 pour cent.",
)
def num_06(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)?\s?%", block.text):
        number = m.group(1)
        yield hit(
            "NUM-06-FR",
            evidence=m.group(0).strip(),
            suggestion=f"{number} pour cent" if number else "pour cent",
        )


_AMOUNT = r"\d{1,3}(?:[" + _GROUP_SEPARATORS + r"]\d{3})+|\d+"
AMOUNT_STYLE_RE = re.compile(
    r"(?:CHF|Fr\.)\s?(" + _AMOUNT + r")[.,](?:00|[" + DASHES + r"]{1,2})"
    r"|(" + _AMOUNT + r")[.,](?:00|[" + DASHES + r"]{1,2})\s?(?:CHF|Fr\.|francs?)"
    r"|(" + _AMOUNT + r")(?:[.,]\d{2})?\s?CHF\b"
)


@rule(
    "NUM-07-FR",
    lang=FR,
    title="Amounts 500 francs or CHF 500",
    severity=sev("info"),
    scope="block",
    guide="Les montants s'écrivent ainsi : 500 francs ou CHF 500.",
)
def num_07(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in AMOUNT_STYLE_RE.finditer(block.text):
        number = re.sub(r"\D", "", next(g for g in m.groups() if g))
        amount = f"{format_thousands(number, FR) if len(number) > 3 else number} francs"
        yield hit(
            "NUM-07-FR",
            found=m.group(0),
            expected=amount,
            evidence=m.group(0),
            suggestion=amount,
        )


@rule(
    "NUM-08-FR",
    lang=FR,
    title="Phone numbers spaced: 022 123 45 67",
    severity=sev("warn"),
    scope="block",
    guide="Les numéros de téléphone s'écrivent avec des espaces : 022 123 45 67.",
)
def num_08(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in PHONE_RE.finditer(block.text):
        number = m.group(0)
        if ACCEPTED_PHONE_RE.fullmatch(number):
            continue
        yield hit(
            "NUM-08-FR",
            found=number,
            expected=format_phone(number),
            evidence=number,
            suggestion=format_phone(number),
        )


# -- Swiss usage --------------------------------------------------------------------

_FRANCE_TENS = {"soixante": "septante", "quatre-vingt": "nonante"}
_AFTER_TEN = {"dix": "", "onze": " et un", "douze": "-deux", "treize": "-trois",
              "quatorze": "-quatre", "quinze": "-cinq", "seize": "-six", "dix-sept": "-sept",
              "dix-huit": "-huit", "dix-neuf": "-neuf"}  # fmt: skip
FRANCE_NUMERAL_RE = re.compile(
    r"\b(soixante|quatre-vingt)(?:-|\s+et\s+)"
    r"(dix-sept|dix-huit|dix-neuf|dix|onze|douze|treize|quatorze|quinze|seize)\b",
    re.IGNORECASE,
)


@rule(
    "CH-03-FR",
    lang=FR,
    title="Swiss numerals septante, huitante or octante, nonante when numbers are written out",
    severity=sev("info"),
    scope="block",
    guide="Si un nombre s'écrit en lettres, prenez les mots suisses : septante, nonante.",
)
def ch_03(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in FRANCE_NUMERAL_RE.finditer(block.text):
        swiss = _FRANCE_TENS[m.group(1).lower()] + _AFTER_TEN[m.group(2).lower()]
        yield hit("CH-03-FR", found=m.group(0), swiss=swiss, evidence=m.group(0), suggestion=swiss)
