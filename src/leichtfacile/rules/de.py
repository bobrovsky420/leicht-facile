"""German rules (docs/rules.md, "German (DE-CH)").

Sentence-scope checks read the spaCy parse of de_core_news_md (STTS tags, TIGER
dependency labels, morphology); block-scope checks are regular expressions over the
block text. Messages are the English templates of rules/messages.py, with a key and
values for the interface's translation; the `guide` texts are German, because they go
into the writer prompt.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from spacy.tokens import Span, Token

from leichtfacile.rules.base import BlockInfo, Context, Hit, rule
from leichtfacile.rules.lexicon import (
    MEDIOPUNKT,
    hyphenated,
    is_common_compound,
    is_known,
    lowercase_after_mediopunkt,
    mediopunkt_suggestion,
    split_compound,
    zipf,
)
from leichtfacile.rules.mediopunkt import NOUN_TAGS
from leichtfacile.rules.messages import hit
from leichtfacile.rules.recipes import recipe_de
from leichtfacile.rules.values import (
    DASHES,
    EMAIL_RE,
    URL_RE,
    mask,
    mask_numbers,
)
from leichtfacile.rules.vocabulary import (
    covered_offsets,
    easy_for,
    find_terms,
    office_words,
    standard_spelling,
)
from leichtfacile.varieties import variety as variety_table

DE = "de"  # the language: a check every German variety runs
CH = "de-CH"  # the Swiss variety: a check of its own (the REG rules)
# The German varieties (schemas.variety): Switzerland, Germany, Austria. A check or a
# guide registered for all three differs by `ctx.region`.
GERMAN = (CH, "de-DE", "de-AT")
STANDARD = ("de-DE", "de-AT")  # the varieties of the standard spelling, with the sharp s
SENTENCE_KINDS = ("sentence", "list_item")
FINITE_TAGS = frozenset({"VVFIN", "VAFIN", "VMFIN", "VVIMP", "VAIMP"})
INFINITIVE_TAGS = frozenset({"VVINF", "VAINF", "VMINF"})
_LETTER = "A-Za-zÄÖÜäöüÀ-ÿ"


# -- sentence analysis ------------------------------------------------------------


def words(sent: Span) -> list[Token]:
    return [t for t in sent if not (t.is_punct or t.is_space)]


def word_count(sent: Span) -> int:
    """Words in a sentence; a run of numbers (044 123 45 67) counts as one word."""
    count = 0
    previous_num = False
    for t in words(sent):
        is_num = t.like_num or t.tag_ == "CARD"
        if not (is_num and previous_num):
            count += 1
        previous_num = is_num
    return count


_JOINING_HYPHENS = "-\u2010\u2011"


def word_count_joined(sent: Span) -> int:
    """`word_count` for the German of Germany and Austria, whose easy-language texts split
    a long compound with a hyphen (Kranken-Kasse, Bundes-Gleichstellungs-Gesetz): spaCy
    makes three tokens of it, and the parts joined by a hyphen without spaces count as
    one word, as a Mediopunkt compound does in Switzerland (29 October 2026)."""
    count = 0
    previous_num = False
    joined = False
    for t in sent:
        if t.is_space:
            continue
        if t.is_punct:
            glued = t.i > sent.start and not sent.doc[t.i - 1].whitespace_
            joined = t.text in _JOINING_HYPHENS and glued and not t.whitespace_
            continue
        is_num = t.like_num or t.tag_ == "CARD"
        if not (is_num and previous_num) and not joined:
            count += 1
        previous_num = is_num
        joined = False
    return count


def finite_verbs(sent: Span) -> list[Token]:
    """Finite verbs that open a clause of their own."""
    out = []
    for t in sent:
        if t.tag_ not in FINITE_TAGS:
            continue
        forms = t.morph.get("VerbForm")
        if forms and "Fin" not in forms:
            continue  # tagged finite, but the morphology says infinitive or participle
        own_subject = any(c.dep_ in ("sb", "cp") for c in t.children)
        if (
            t.dep_ in ("oc", "pd")
            and t.head.i != t.i
            and t.head.tag_.startswith(("VA", "VM"))
            and not own_subject
        ):
            continue  # "sollen ... teilnehmen können": part of the verb complex
        if t.dep_ == "cj" and not own_subject:
            continue  # "plant und macht": one subject, one statement
        out.append(t)
    return out


def infinitive_clauses(sent: Span) -> list[Token]:
    """zu-infinitive clauses, except the predicates "ist ... einzureichen" and
    "hat ... zu zahlen", which do not add a clause."""
    out = []
    for t in sent:
        zu = t.tag_ == "VVIZU" or (
            t.tag_ in INFINITIVE_TAGS and any(c.tag_ == "PTKZU" for c in t.children)
        )
        if (
            zu
            and t.dep_ != "ROOT"
            and t.head.pos_ not in ("ADJ", "ADV")  # "Gut zu wissen:"
            and t.head.lemma_ not in ("sein", "haben", "brauchen", "scheinen")
        ):
            out.append(t)
    return out


def clause_parts(sent: Span) -> list[Span]:
    """Parts of a sentence separated by a colon. Easy language uses the colon to
    introduce an explanation ("Das bedeutet: Wir helfen Ihnen."); each part is read as
    a statement of its own."""
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


def subordinators(sent: Span) -> list[Token]:
    """Words that open a subordinate clause: weil, dass, wenn, um ... zu, relative clauses."""
    out = [t for t in sent if t.tag_ in ("KOUS", "KOUI")]
    for t in sent:
        if t.dep_ == "rc":  # head verb of a relative clause; report its pronoun
            rel = next((c for c in t.subtree if c.tag_ in ("PRELS", "PRELAT")), t)
            out.append(rel)
    covered = {t.head.i for t in out if t.tag_ == "KOUI"}
    out += [t for t in infinitive_clauses(sent) if t.i not in covered]
    return sorted(out, key=lambda t: t.i)


def clause_count(sent: Span) -> int:
    subs = subordinators(sent)
    by_verbs = len(finite_verbs(sent)) + len([t for t in infinitive_clauses(sent) if t not in subs])
    return max(1, by_verbs, 1 + len(subs))


# A werden-passive the rule leaves alone: "geboren wurden" has no active form a reader
# would want ("zur Welt kamen"), and the easy-language pages write it (3 of the 24
# passives in the German and Austrian evaluation of 30 October 2026).
PASSIVE_ALLOWED = frozenset({"geboren"})
# The finding's advice for the repair round and the reviewer (rules/recipes.py: a recipe,
# never a replacement text). The 70B left "werden nicht erstattet" and "wird gefördert"
# standing through every repair round of that evaluation; the message alone said what
# was wrong, not what to write.
PASSIVE_RECIPE = (
    "Wer tut es? Nenne die Person oder das Amt: Das Amt zahlt das Geld. "
    "Oder: Sie bekommen das Geld."
)


def passive_constructions(sent: Span) -> list[str]:
    found = []
    for t in sent:
        if t.lemma_ == "werden" and t.tag_.startswith("VA"):
            participles = [
                c
                for c in t.children
                if c.tag_ == "VVPP" and c.dep_ == "oc" and c.lower_ not in PASSIVE_ALLOWED
            ]
            if participles:
                found.append(_span_text(sent, t, participles[0]))
        zu_inf = t.tag_ == "VVIZU" or (
            t.tag_ == "VVINF" and any(c.tag_ == "PTKZU" for c in t.children)
        )
        if zu_inf:
            # "ist ... einzureichen", also behind coordinated participles:
            # "ist ausgefüllt und unterzeichnet ... einzureichen"
            head, hops = t.head, 0
            while hops < 4 and head.i != t.i:
                if head.lemma_ == "sein":
                    found.append(_span_text(sent, head, t))
                    break
                if head.tag_ not in ("VVPP", "KON") and head.dep_ not in ("cj", "cd"):
                    break
                head, hops = head.head, hops + 1
    return found


def genitives(sent: Span) -> list[tuple[Token, str]]:
    """Genitive noun phrases: (head noun, phrase text)."""
    out = []
    for t in sent:
        if t.pos_ not in ("NOUN", "PROPN") or "Gen" not in t.morph.get("Case"):
            continue
        left = [c for c in t.lefts if c.pos_ in ("DET", "ADJ", "NUM")]
        start = left[0].i if left else t.i
        out.append((t, sent.doc[start : t.i + 1].text))
    return out


def _span_text(sent: Span, a: Token, b: Token) -> str:
    first, last = sorted((a, b), key=lambda t: t.i)
    if last.i - first.i <= 4:
        return sent.doc[first.i : last.i + 1].text
    return f"{first.text} ... {last.text}"


def _alpha(text: str) -> int:
    return sum(ch.isalpha() for ch in text)


# -- sentence structure ------------------------------------------------------------


@rule(
    "LEN-02",
    lang=DE,
    guide={
        "A2": "Ein Satz hat nur eine Aussage. Keine Nebensätze: kein Satz mit weil, dass, "
        "wenn, damit, obwohl, um ... zu oder einem Relativsatz. Schreibe lieber "
        "zwei kurze Sätze.",
        "B1": "Höchstens ein Nebensatz pro Satz. Schreibe lieber zwei kurze Sätze.",
    },
)
def len_02(sent: Span, ctx: Context) -> Iterator[Hit]:
    limit = ctx.params.max_clauses
    worst = max(clause_parts(sent), key=clause_count)
    clauses = clause_count(worst)
    if clauses <= limit:
        return
    # One clause too many is a warning: professional texts use a simple "wenn" clause.
    # Two or more too many (nested clauses) is an error.
    severity = "warn" if clauses == limit + 1 else "error"
    subs = subordinators(worst)
    # The suggestion is the rewrite recipe for the conjunction (rules/recipes.py).
    if subs:
        yield hit(
            "LEN-02.sub",
            opener=subs[0].text,
            clauses=clauses,
            limit=limit,
            level=ctx.level,
            evidence=sent.text,
            suggestion=recipe_de(subs[0]),
            severity=severity,
        )
    else:
        yield hit(
            "LEN-02.main",
            clauses=clauses,
            limit=limit,
            level=ctx.level,
            evidence=sent.text,
            suggestion=recipe_de(None),
            severity=severity,
        )


def _conjunct_chain(token: Token) -> list[Token]:
    items = [token]
    stack = [token]
    while stack:
        t = stack.pop()
        for c in t.children:
            if c.dep_ == "cj":
                items.append(c)
                stack.append(c)
            elif c.dep_ == "cd":
                stack.append(c)
    return items


@rule(
    "LEN-03",
    lang=DE,
    guide="Zählst du 3 oder mehr Dinge auf? Dann schreibe eine Liste.",
)
def len_03(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        if t.dep_ == "cj" or not any(c.dep_ in ("cj", "cd") for c in t.children):
            continue
        items = [i for i in _conjunct_chain(t) if i.pos_ in ("NOUN", "PROPN", "VERB", "ADJ")]
        if len(items) >= 3:
            yield hit("LEN-03", items=len(items), evidence=", ".join(i.text for i in items))


@rule(
    "ORD-01",
    lang=DE,
    guide="Satzbau: zuerst wer, dann was er tut. Beispiel: Sie bekommen einen Brief.",
)
def ord_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    root = sent.root
    if root.tag_ not in FINITE_TAGS or sent.text.rstrip().endswith("?"):
        return
    first = words(sent)[0] if words(sent) else None
    if first is None or first.i == root.i:  # questions and imperatives start with the verb
        return
    subjects = [c for c in root.children if c.dep_ == "sb"]
    if subjects and subjects[0].i > root.i:
        yield hit("ORD-01", subject=subjects[0].text, verb=root.text, evidence=sent.text)


# -- grammar ------------------------------------------------------------------------


@rule(
    "GRAM-01",
    lang=DE,
    guide="Kein Passiv. Sag, wer etwas tut. Nicht: Das Formular wird geprüft. "
    "Sondern: Das Amt prüft das Formular.",
)
def gram_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    for evidence in passive_constructions(sent):
        yield hit("GRAM-01", found=evidence, evidence=evidence, suggestion=PASSIVE_RECIPE)


GENITIVE_ALLOWED = (
    "anfang des jahres",
    "ende des jahres",
    "anfang des monats",
    "ende des monats",
    "mitte des monats",
    "eines tages",
)


@rule(
    "GRAM-02",
    lang=DE,
    guide="Kein Genitiv. Schreibe von + Dativ: das Auto von meinem Vater.",
)
def gram_02(sent: Span, ctx: Context) -> Iterator[Hit]:
    for noun, phrase in genitives(sent):
        context = f"{noun.head.text} {phrase}".lower()
        if any(allowed in context or allowed == phrase.lower() for allowed in GENITIVE_ALLOWED):
            continue
        yield hit("GRAM-02", found=phrase, evidence=phrase)


# Konjunktiv II forms that are never indicative.
KONJUNKTIV_II = frozenset(
    [
        "wäre",
        "wären",
        "wärst",
        "wärest",
        "hätte",
        "hätten",
        "hättest",
        "würde",
        "würden",
        "würdest",
        "könnte",
        "könnten",
        "könntest",
        "müsste",
        "müssten",
        "müsstest",
        "dürfte",
        "dürften",
        "dürftest",
    ]
)


@rule(
    "GRAM-03",
    lang=DE,
    guide="Kein Konjunktiv (nicht: würde, hätte, wäre, könnte). Schreibe direkt.",
)
def gram_03(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in (t for t in sent if t.tag_ in FINITE_TAGS):  # also "sind bzw. wären"
        lower = t.lower_
        conditional = (
            t.i == sent.start
            and t.dep_ == "mo"
            and lower in ("sollte", "sollten", "solltest", "würde", "würden", "wäre", "wären")
        )  # "Sollten Sie ... geraten, ...": a condition without "wenn"
        if conditional:
            yield hit("GRAM-03.condition", found=t.text, evidence=t.text)
        elif ("Sub" in t.morph.get("Mood") or lower in KONJUNKTIV_II) and not lower.startswith(
            "möcht"
        ):
            yield hit("GRAM-03", mood="Konjunktiv", found=t.text, evidence=t.text)


@rule(
    "GRAM-04",
    lang=DE,
    guide="Für Vergangenes nimmst du das Perfekt: Sie haben einen Brief bekommen. "
    "Nicht: Sie bekamen einen Brief.",
)
def gram_04(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        if t.tag_ == "VVFIN" and "Past" in t.morph.get("Tense") and "Ind" in t.morph.get("Mood"):
            yield hit("GRAM-04", found=t.text, evidence=t.text)


NOMINAL_SUFFIXES = ("ung", "ungen", "heit", "heiten", "keit", "keiten", "nis", "nisse",
                    "nissen", "tum", "tümer")  # fmt: skip
# Everyday nouns with a nominal suffix that easy-language texts use freely.
NOMINAL_ALLOWED = frozenset(
    [
        "wohnung",
        "zeitung",
        "rechnung",
        "versicherung",
        "krankenversicherung",
        "zeugnis",
        "ergebnis",
        "erlaubnis",
        "gefängnis",
        "geheimnis",
        "zeichnung",
        "kleidung",
        "heizung",
        "nahrung",
        "richtung",
        "ordnung",
        "meinung",
        "hoffnung",
        "sendung",
        "werbung",
        "übung",
        "prüfung",
        "sitzung",
        "lösung",
        "gesundheit",
        "krankheit",
        "sicherheit",
        "freiheit",
        "kindheit",
        "möglichkeit",
        "schwierigkeit",
        "arbeit",
        "eigentum",
        "irrtum",
        "hilfeleistung",
        "bildung",
        "ausbildung",
        "weiterbildung",
        "leistung",
        "leistungen",
    ]
)
NOMINALISED_INFINITIVE_ALLOWED = frozenset({"schreiben"})  # das Schreiben: the letter
EVERYDAY_ZIPF = 4.0  # nouns at least this frequent count as everyday words
# Verbs that carry no meaning of their own next to a nominalisation:
# "die Einreichung erfolgt", "eine Prüfung vornehmen", "zur Anwendung kommen".
LIGHT_VERBS = frozenset(
    [
        "erfolgen",
        "stattfinden",
        "vornehmen",
        "durchführen",
        "vollziehen",
        "tätigen",
        "bewirken",
        "gelangen",
        "kommen",
        "bringen",
        "finden",
        "nehmen",
        "treffen",
        "unterliegen",
        "bedürfen",
        "unterziehen",
    ]
)
NOMINAL_PREPOSITIONS = frozenset(
    [
        "zur",
        "zum",
        "bei",
        "beim",
        "nach",
        "vor",
        "durch",
        "mittels",
        "zwecks",
        "infolge",
        "aufgrund",
    ]
)


def nominal_context(t: Token) -> bool:
    """The noun sits in nominal style: with a light verb, after "zur" or "bei der", or
    with a genitive or "von" attribute ("die Einreichung des Gesuchs")."""
    head = t.head
    if head.i != t.i and head.lemma_ in LIGHT_VERBS:
        return True
    if head.tag_ in ("APPR", "APPRART") and head.lower_ in NOMINAL_PREPOSITIONS:
        return True
    return any(
        c.dep_ == "ag" or (c.dep_ in ("pg", "mnr") and c.lower_ == "von") for c in t.children
    )


@rule(
    "GRAM-05",
    lang=DE,
    guide="Verben statt Nomen. Nicht: Die Anmeldung erfolgt online. Sondern: Sie melden "
    "sich im Internet an.",
)
def gram_05(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        if t.pos_ != "NOUN" or ctx.in_glossary(t.text):
            continue
        word = t.text.lower()
        parts = [p for p in re.split(r"[·-]", word) if p]
        if len(parts) == 1:
            split = split_compound(t.text)
            if split:  # Behinderten·gleichstellungs·gesetz: look at every part
                parts = [p.lower() for p in split]
        joined = word.replace(MEDIOPUNKT, "").replace("-", "")
        nominal = [
            stem
            for part in parts
            if (stem := part[:-1] if part.endswith(("ungs", "heits", "keits")) else part)
            and stem.endswith(NOMINAL_SUFFIXES)
            and len(stem) > 5
            and not stem.endswith(tuple(NOMINAL_ALLOWED))  # Sozial·versicherung
            and zipf(stem) < EVERYDAY_ZIPF
        ]
        if nominal and joined not in NOMINAL_ALLOWED:
            if max(zipf(joined), zipf(t.lemma_.lower())) >= EVERYDAY_ZIPF:
                continue  # Unter·stützung, Behinderung: everyday words
            if nominal_context(t):
                yield hit("GRAM-05", found=t.text, evidence=t.text)
            else:
                yield hit("GRAM-05.abstract", found=t.text, evidence=t.text, severity="info")
        elif (
            t.lemma_ == word  # das Einreichen: lemma einreichen
            and t.text[:1].isupper()
            and word.endswith(("en", "ern", "eln"))
            and word not in NOMINALISED_INFINITIVE_ALLOWED
        ):
            yield hit(
                "GRAM-05.infinitive",
                found=t.text,
                evidence=t.text,
                severity=None if nominal_context(t) else "info",
            )


_PRONOUN_FEATURES = {"er": ("Masc",), "ihn": ("Masc",), "ihm": ("Masc", "Neut")}
_DEMONSTRATIVES = frozenset({"dieser", "diese", "dieses", "diesem", "diesen"})


def _antecedents(pronoun: Token, ctx: Context, sent: Span) -> tuple[set[str], bool]:
    """Matching nouns before the pronoun in this and the previous block, and whether
    several of them make a real ambiguity."""
    text = pronoun.text
    if text.lower() in _PRONOUN_FEATURES:
        readings = [(_PRONOUN_FEATURES[text.lower()], "Sing")]
    elif text.lower() == "sie" and pronoun.dep_ != "sb":
        # Only a subject "sie" shows its number on the verb; the object "sie" can be
        # feminine singular or plural ("diese prüft sie": die Stelle or die Unterlagen?).
        readings = [(("Fem",), "Sing"), (("Masc", "Fem", "Neut"), "Plur")]
    else:
        genders = tuple(pronoun.morph.get("Gender")) or ("Masc", "Fem", "Neut")
        readings = [(genders, (pronoun.morph.get("Number") or ["Sing"])[0])]
    pool: list[Token] = [t for t in sent.doc[: pronoun.i] if t.pos_ in ("NOUN", "PROPN")]
    prev = ctx.previous_block()
    if prev:
        pool = [t for s in prev.sentences for t in s if t.pos_ in ("NOUN", "PROPN")] + pool
    found = set()
    for genders, number in readings:
        for noun in pool:
            if number not in noun.morph.get("Number"):
                continue
            if number == "Sing" and not set(noun.morph.get("Gender")) & set(genders):
                continue
            found.add(noun.lemma_)
    ambiguous_counts = len(readings) > 1 or readings[0][1] == "Sing"
    return found, ambiguous_counts


@rule(
    "GRAM-06",
    lang=DE,
    guide="Pronomen wie er, sie oder dieser nur, wenn klar ist, wen sie meinen. "
    "Wiederhole lieber das Nomen.",
)
def gram_06(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        lower = t.text.lower()
        # A capital "Sie" is almost always the reader, even where the tagger says
        # singular; only the lowercase "sie" is checked.
        third_person = t.tag_ == "PPER" and (lower in _PRONOUN_FEATURES or t.text == "sie")
        demonstrative = t.tag_ == "PDS" and lower in _DEMONSTRATIVES
        if not (third_person or demonstrative):
            continue
        found, ambiguous_counts = _antecedents(t, ctx, sent)
        if not found:
            yield hit("GRAM-06", found=t.text, evidence=t.text)
        elif len(found) > 1 and ambiguous_counts:
            options = ", ".join(sorted(found)[:3])
            yield hit("GRAM-06.ambiguous", found=t.text, options=options, evidence=t.text)


@rule(
    "GRAM-07",
    lang=DE,
    guide="Keine indirekte Rede. Schreibe, wer was sagt.",
)
def gram_07(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        morph = t.morph
        if (
            t.tag_ in FINITE_TAGS
            and "Sub" in morph.get("Mood")
            and "Pres" in morph.get("Tense")
            and "3" in morph.get("Person")
        ):
            yield hit("GRAM-07", found=t.text, evidence=t.text)
        elif t.pos_ == "ADP" and t.lower_ in ("laut", "gemäss", "gemäß", "zufolge"):
            yield hit("GRAM-07.reported", found=t.text, evidence=t.text)


# Prefixes that always separate (`mitschicken`: `schicken ... mit`), longest first. The
# two-way prefixes (`über`, `unter`, `um`, `durch`, `wieder`, `hinter`, `voll`) stay out:
# `überweisen` is one word in every form.
SEPARABLE_PREFIXES = tuple(
    sorted(
        (
            "ab", "an", "auf", "aus", "bei", "ein", "mit", "nach", "vor", "zu", "zurück",
            "zusammen", "zurecht", "her", "hin", "heraus", "hinaus", "herein", "hinein",
            "herunter", "hinunter", "hinauf", "herauf", "weiter", "fort", "fest", "frei",
            "heim", "hoch", "klar", "los", "weg", "statt", "teil", "wahr", "bereit", "preis",
            "kennen",
        ),
        key=len,
        reverse=True,
    )
)  # fmt: skip
GLUED_ALLOWED = frozenset({"anerkennen"})  # Swiss usage keeps it in one word


def separable_split(word: str, glued_allowed: bool = True) -> tuple[str, str] | None:
    """(prefix, verb) when the lowercase word is a separable prefix plus a known verb
    infinitive (`mitschicken`: `mit`, `schicken`); None otherwise (`antworten`,
    `beinhalten`, `einigen`: what follows the prefix is no verb)."""
    if glued_allowed and word in GLUED_ALLOWED:
        return None  # Swiss usage; Germany and Austria split anerkennen like any other verb
    for prefix in SEPARABLE_PREFIXES:
        if word.startswith(prefix):
            stem = word[len(prefix) :]
            if (
                len(stem) >= 4
                and stem.endswith(("en", "ern", "eln"))
                and is_known(stem, min_zipf=3.0)
            ):
                return prefix, stem
    return None


# A clause these open puts the finite verb at its end, in one word (`wenn Sie
# wegziehen`, `Personen, die wegziehen`): subordinating conjunctions and relative or
# interrogative pronouns, as the tagger names them.
SUBORDINATOR_TAGS = frozenset({"KOUS", "PRELS", "PRELAT", "PWS", "PWAV", "PWAT"})


def verb_final_positions(sent: Span) -> set[int]:
    """Indices into the sentence's non-punctuation tokens that stand in a verb-final
    clause: from a subordinator up to the next comma. Found 10 October 2026 in the
    example rebuild: `Wenn Sie wegziehen, melden Sie das` was flagged as a glued verb."""
    out: set[int] = set()
    inside = False
    n = 0
    for t in sent:
        if t.is_space:
            continue
        if t.is_punct:
            if t.text == ",":
                inside = False
            continue
        if t.tag_ in SUBORDINATOR_TAGS:
            inside = True
        elif inside:
            out.add(n)
        n += 1
    return out


@rule(
    "GRAM-08",
    lang=DE,
)
def gram_08(sent: Span, ctx: Context) -> Iterator[Hit]:
    """A separable verb written as one finite word in verb-second position (`Sie
    mitschicken eine Kopie`, found in an example draft on 8 October 2026): the tagger
    calls it VVFIN by its position, and only the form gives it away. An infinitive at
    the end of a phrase (`Kopie mitschicken`) or under a modal is fine, and so is a
    verb-final clause (`wenn Sie wegziehen`, 10 October 2026). No writer instruction
    (`guide`), so the style guide in the prompts stays as frozen."""
    tokens = [t for t in sent if not (t.is_punct or t.is_space)]
    verb_final = verb_final_positions(sent)
    for n, t in enumerate(tokens):
        if n == 0 or t.tag_ != "VVFIN" or t.text[:1].isupper():
            continue
        if n in verb_final:
            continue  # `wenn Sie wegziehen`: the verb ends the clause, in one word
        if any(x.tag_ in FINITE_TAGS for x in tokens[:n]):
            continue  # a verb before it: not the main clause's verb
        if not any(x.is_alpha for x in tokens[n + 1 :]):
            continue  # at the end: an infinitive phrase, not a glued finite verb
        split = separable_split(t.lower_, glued_allowed=ctx.region == "CH")
        if split is None:
            continue
        prefix, stem = split
        expected = f"{stem} ... {prefix}"
        yield hit("GRAM-08", found=t.text, expected=expected, evidence=t.text, suggestion=expected)


# -- negation -----------------------------------------------------------------------

NEGATION_WORDS = frozenset(
    {"nicht", "nie", "niemals", "niemand", "niemanden", "niemandem", "nichts", "ohne",
     "weder", "nirgends", "nirgendwo"}
)  # fmt: skip


def negations(sent: Span) -> list[Token]:
    out = []
    for t in sent:
        lower = t.lower_
        if (
            lower in NEGATION_WORDS
            or (lower.startswith("kein") and t.tag_ in ("PIAT", "PIS"))
            or (
                t.tag_ in ("ADJA", "ADJD")
                and lower.startswith("un")
                and len(lower) >= 6
                and is_known(lower[2:], min_zipf=2.5)
            )
        ):
            out.append(t)
    return out


def _negation_groups(sent: Span) -> list[list[Token]]:
    """Negations by clause part: commas, colons and coordinating conjunctions separate
    statements ("kein Licht und keinen Strom" is not a double negation)."""
    found = {t.i for t in negations(sent)}
    groups: list[list[Token]] = [[]]
    for t in sent:
        if t.text in (",", ";", ":") or (
            t.tag_ == "KON" and t.lower_ in ("und", "oder", "aber", "sondern")
        ):
            groups.append([])
        elif t.i in found:
            groups[-1].append(t)
    return groups


@rule(
    "NEG-01",
    lang=DE,
    guide="Keine doppelte Verneinung.",
)
def neg_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    for group in _negation_groups(sent):
        if len(group) >= 2:
            yield hit(
                "NEG-01",
                found=" ... ".join(t.text for t in group),
                evidence=" ".join(t.text for t in group),
            )


@rule(
    "NEG-02",
    lang=DE,
    guide="Schreibe positiv, wenn es geht: Sie dürfen ... statt Sie dürfen nicht ...",
)
def neg_02(sent: Span, ctx: Context) -> Iterator[Hit]:
    found = negations(sent)
    if len(found) == 1:
        yield hit("NEG-02", found=found[0].text, evidence=found[0].text)


# -- words --------------------------------------------------------------------------


@rule(
    "LEX-01",
    lang=GERMAN,
    guide={
        "de-CH": "Lange Wörter trennst du mit dem Medio·punkt: Prämien·verbilligung, "
        "Kranken·kasse. Nach dem Punkt schreibst du klein weiter.",
        # Rendered with the hyphen by the prompt (Binde-Strich, Kranken-Kasse).
        "de-DE": "Lange Wörter trennst du mit einem Binde·strich: Prämien·verbilligung, "
        "Kranken·kasse. Nach dem Bindestrich schreibst du gross weiter.",
        "de-AT": "Lange Wörter trennst du mit einem Binde·strich: Prämien·verbilligung, "
        "Kranken·kasse. Nach dem Bindestrich schreibst du gross weiter.",
    },
)
def lex_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    limit = ctx.params.max_word_letters
    # Germany and Austria split with a hyphen and a capital (varieties.toml,
    # `compound_mark`): the suggestion takes that form, and a Mediopunkt is a finding.
    hyphen = variety_table(ctx.variety).compound_mark == "hyphen"
    for t in sent:
        if t.like_url or t.like_email or not any(ch.isalpha() for ch in t.text):
            continue
        if hyphen and "·" in t.text:
            marked = hyphenated(lowercase_after_mediopunkt(t.text) or t.text)
            yield hit(
                "LEX-01.mark", found=t.text, expected=marked, evidence=t.text, suggestion=marked
            )
        elif lowered := lowercase_after_mediopunkt(t.text):
            yield hit("LEX-01.lowercase", found=t.text, evidence=t.text, suggestion=lowered)
        long_parts = [p for p in re.split(r"[·-]", t.text) if _alpha(p) > limit]
        if not long_parts:
            continue
        # The same split the pipeline writes by code (rules/mediopunkt.py). A glossary
        # entry explains the word but does not make it shorter, so a compound is flagged
        # whether it is in the glossary or not; only a long word that cannot be split
        # needs no note when it is explained. Nouns alone get a split, as the code
        # splitting does (rules/mediopunkt.py): the splitter offered unterschriebe·nes and
        # minder·jährigen for a participle and an adjective (the German and Austrian
        # evaluation of 30 October 2026); a long word of another kind is the note below.
        noun = t.pos_ in NOUN_TAGS and t.text[:1].isupper()
        split = mediopunkt_suggestion(t.text, limit) if noun else None
        if split:
            yield hit(
                "LEX-01.hyphen" if hyphen else "LEX-01",
                found=t.text,
                letters=_alpha(long_parts[0]),
                limit=limit,
                evidence=t.text,
                suggestion=hyphenated(split) if hyphen else split,
            )
        elif not ctx.in_glossary(t.text):  # no compound: only a shorter word helps
            yield hit(
                "LEX-01.no_compound",
                found=t.text,
                letters=_alpha(long_parts[0]),
                evidence=t.text,
                severity="info",
            )


ABBREVIATIONS = [
    r"z\.\s?B\.", r"bzw\.", r"ggf\.", r"usw\.", r"etc\.", r"u\.\s?a\.", r"d\.\s?h\.",
    r"z\.\s?T\.", r"inkl\.", r"exkl\.", r"evtl\.", r"ca\.", r"vgl\.", r"u\.\s?U\.",
    r"i\.\s?d\.\s?R\.", r"sog\.", r"bspw\.", r"v\.\s?a\.", r"zzgl\.", r"mind\.", r"max\.",
    r"min\.", r"gem\.", r"resp\.", r"allf\.", r"bzgl\.", r"betr\.", r"Hr\.", r"Tel\.",
    r"Str\.", r"Abt\.", r"Dr\.", r"Prof\.", r"o\.\s?Ä\.", r"u\.\s?Ä\.", r"s\.\s?o\.",
    r"s\.\s?u\.", r"Kt\.", r"Gde\.", r"Mo\.", r"Di\.", r"Mi\.", r"Do\.", r"Sa\.",
    r"(?:Art|Abs|Nr|Ziff|lit|Bst|S)\.(?=\s?\d)",
]  # fmt: skip
ABBREVIATION_RE = re.compile(r"(?<![\w.])(?:" + "|".join(ABBREVIATIONS) + r")")
WEEKDAY_RANGE_RE = re.compile(
    r"\b(?:Mo|Di|Mi|Do|Fr|Sa|So)\.?\s?(?:-|bis|\u2013)\s?(?:Mo|Di|Mi|Do|Fr|Sa|So)\b\.?"
)
ACRONYM_RE = re.compile(
    r"(?<![\w-])(?:[A-ZÄÖÜ]{2,5}s?|[A-ZÄÖÜ][a-zäöü]{0,4}[A-ZÄÖÜ][A-Za-zÄÖÜäöü]{0,4})(?![\w-])"
)  # KVG, EL, and law abbreviations in mixed case such as BehiG or SchKG
ACRONYMS_ALLOWED = frozenset({"WC", "SBB", "PDF", "AHV", "IV", "CHF", "SMS", "TV", "ID"})
# Germany: the Netzwerk Leichte Sprache's rule W6 names WC, LKW, Dr. and ICE as known;
# Austria: the ÖBB and the AMS are everyday names. Dr. is allowed outside Switzerland.
ACRONYMS_ALLOWED_REGION = {
    "CH": ACRONYMS_ALLOWED,
    "DE": frozenset({"WC", "LKW", "PKW", "ICE", "PDF", "EU", "SMS", "TV", "ID", "OK", "EC"}),
    "AT": frozenset({"WC", "LKW", "PKW", "ÖBB", "AMS", "PDF", "EU", "SMS", "TV", "ID", "OK"}),
}
# Words in capitals for emphasis, as voting texts write them: "Sagen Sie JA".
EMPHASIS_WORDS = frozenset({"JA", "NEIN", "NICHT", "KEIN", "UND", "ODER", "NUR", "AUCH", "NIE"})


@rule(
    "LEX-02",
    lang=GERMAN,
    guide={
        "de-CH": "Keine Abkürzungen (nicht: z. B., bzw., ggf., Art.). Erlaubt sind CHF, AHV, IV, "
        "SBB, WC und PDF. Andere Abkürzungen erklärst du.",
        "de-DE": "Keine Abkürzungen (nicht: z. B., bzw., ggf., Art.). Erlaubt sind WC, LKW, "
        "Dr., ICE und PDF. Andere Abkürzungen erklärst du.",
        "de-AT": "Keine Abkürzungen (nicht: z. B., bzw., ggf., Art.). Erlaubt sind WC, ÖBB, "
        "AMS, Dr. und PDF. Andere Abkürzungen erklärst du.",
    },
)
def lex_02(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    text = mask(block.text, [m.span() for m in URL_RE.finditer(block.text)])
    text = mask(text, [m.span() for m in EMAIL_RE.finditer(text)])
    allowed = ACRONYMS_ALLOWED_REGION.get(ctx.region, ACRONYMS_ALLOWED)
    for m in ABBREVIATION_RE.finditer(text):
        if m.group(0) == "St." and text[m.end() :].lstrip().startswith("Gallen"):
            continue
        if m.group(0) == "Dr." and ctx.region != "CH":
            continue  # known everywhere in Germany and Austria (Netzwerk, rule W6)
        found = m.group(0)
        yield hit("LEX-02", found=found, evidence=found, suggestion=easy_for(ctx.variety, found))
    for m in WEEKDAY_RANGE_RE.finditer(text):
        yield hit(
            "LEX-02.weekdays",
            found=m.group(0),
            expected="Montag bis Freitag",
            evidence=m.group(0),
        )
    for m in ACRONYM_RE.finditer(text):
        acronym = m.group(0)
        if acronym[-1] == "s" and acronym[:-1].isupper():
            acronym = acronym[:-1]  # plural s: die KVGs
        if (
            acronym in allowed
            or acronym in EMPHASIS_WORDS
            or (len(acronym) >= 4 and is_known(acronym.lower(), min_zipf=3.5))  # BITTE
            or re.fullmatch(r"[IVXLC]+", acronym)
        ):
            continue
        if acronym in ctx.introduced or ctx.in_glossary(acronym):
            yield hit("LEX-02.explained", found=acronym, evidence=acronym, severity="info")
            continue
        yield hit(
            "LEX-02.acronym",
            found=acronym,
            evidence=acronym,
            suggestion=easy_for(ctx.variety, acronym),
        )


@rule(
    "LEX-03",
    lang=DE,
    guide="Nimm einfache, bekannte Wörter. Keine Fremdwörter und keine Fachwörter. "
    "Ist ein schwieriges Wort nötig, erkläre es im Wörterbuch.",
)
def lex_03(sent: Span, ctx: Context) -> Iterator[Hit]:
    office = covered_offsets(
        office_words(find_terms(DE, sent), exclude=ROLE_NOUN_RE), sent.start_char
    )
    for t in sent:
        if (
            t.idx in office  # LEX-07 names the everyday word
            or t.pos_ not in ("NOUN", "VERB", "ADJ", "ADV")
            or not t.text.replace(MEDIOPUNKT, "").replace("-", "").isalpha()
            or len(t.text) < 4
            or ctx.in_glossary(t.text)
        ):
            continue
        parts = [p for p in re.split(r"[·-]", t.text) if p]
        rare_parts = [p for p in parts if max(zipf(p.lower()), zipf(t.lemma_.lower())) < 2.5]
        if rare_parts and max(zipf(t.text.lower()), zipf(t.lemma_.lower())) < 2.5:
            if len(parts) == 1 and is_common_compound(t.text):  # Kranken·kassen·karte
                continue
            yield hit("LEX-03", found=t.text, evidence=t.text)


SLASH_RE = re.compile(rf"(?<=[{_LETTER}])\s?/\s?(?=[{_LETTER}])")


GENDER_SIGN_RE = re.compile(rf"[{_LETTER}]+[*:_](?:innen|in)\b|[a-zäöü]Innen\b")


@rule(
    "LEX-05",
    lang=DE,
    guide="Keine Gender·zeichen wie * oder :. Schreibe beide Formen: "
    "Mitarbeiterinnen und Mitarbeiter.",
)
def lex_05(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in GENDER_SIGN_RE.finditer(block.text):
        yield hit("LEX-05", found=m.group(0), evidence=m.group(0))
    for sent in block.sentences:
        for t in sent:
            participle = t.pos_ == "NOUN" and re.search(r"[a-zäöü](?:ende|enden|ender)$", t.text)
            if participle and (t.lemma_.lower().endswith("end") or t.lemma_.endswith("ende")):
                yield hit("LEX-05.participle", found=t.text, evidence=t.text)


ROLE_NOUN_RE = re.compile(
    r"\b(?:Antragsteller|Gesuchsteller|Antragstellende|Gesuchstellende|Versicherte|"
    r"Steuerpflichtige|Leistungsbezüger|Bezüger|Leistungsempfänger|Rentenbezüger)\w*"
    r"|\b(?:betroffene|versicherte|berechtigte|gesuchstellende|antragstellende)n?\s+Person\w*",
    re.IGNORECASE,
)


# -- numbers, dates, times, amounts -----------------------------------------------

CARDINAL_WORDS = {
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8,
    "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12, "zwanzig": 20, "dreissig": 30,
    "dreißig": 30, "vierzig": 40, "fünfzig": 50, "sechzig": 60, "siebzig": 70,
    "achtzig": 80, "neunzig": 90, "hundert": 100, "tausend": 1000,
}  # fmt: skip
ORDINAL_RE = re.compile(
    r"^(zweit|dritt|viert|fünft|sechst|siebt|acht|neunt|zehnt|elft|zwölft)(e|er|en|em|es)$"
)
_ORDINAL_DIGITS = {"zweit": 2, "dritt": 3, "viert": 4, "fünft": 5, "sechst": 6, "siebt": 7,
                   "acht": 8, "neunt": 9, "zehnt": 10, "elft": 11, "zwölft": 12}  # fmt: skip


@rule(
    "NUM-01",
    lang=DE,
    guide="Zahlen schreibst du als Ziffern: 2, 3, 12. Nur ein und eine schreibst du als Wort.",
)
def num_01(sent: Span, ctx: Context) -> Iterator[Hit]:
    for t in sent:
        lower = t.lower_
        if lower in CARDINAL_WORDS and (t.tag_ == "CARD" or t.pos_ == "NUM"):
            yield hit(
                "NUM-01",
                found=t.text,
                evidence=t.text,
                suggestion=str(CARDINAL_WORDS[lower]),
            )
        elif m := ORDINAL_RE.match(lower):
            if ctx.region != "CH":
                continue  # Germany and Austria: ordinals as words are fine (DIN SPEC 33429)
            if t.pos_ in ("NOUN", "PROPN") or (lower.startswith("acht") and t.pos_ != "ADJ"):
                continue  # "Dritte" (third parties) is no number
            yield hit(
                "NUM-01.ordinal",
                found=t.text,
                evidence=t.text,
                suggestion=f"{_ORDINAL_DIGITS[m.group(1)]}.",
            )


IDENTIFIER_BEFORE_RE = re.compile(
    r"(?:Nr\.?|Nummer|Formular|Merkblatt|Art\.?|Artikel|Abs\.?|Ziff\.?|Ziffer|Postfach|"
    r"PLZ|Zimmer|Raum|Büro|Linie|Bus|Tram|Konto|IBAN|Gesuch|Fall|Dossier|Referenz|CH-)\s?$",
    re.IGNORECASE,
)
CURRENCY_NEAR_RE = re.compile(r"CHF|Fr\.|Franken|Rappen", re.IGNORECASE)
# Germany and Austria (29 October 2026): the euro, and the file numbers of a Bescheid
# before a number that is no amount.
CURRENCY_NEAR_RE_DE = re.compile(r"EUR|€|Euro|Cent", re.IGNORECASE)
IDENTIFIER_BEFORE_RE_DE = re.compile(
    IDENTIFIER_BEFORE_RE.pattern[: -len(r")\s?$")]
    + r"|Kassenzeichen|Geschäftszahl|GZ|Aktenzeichen|Az\.|Steuernummer|Steuer-ID"
    # The Austrian insurance number, also written as a sentence: "Die SV-Nummer ist
    # 1230140104" (the Bescheid of the evaluation, 30 October 2026).
    + r"|SV-Nummer|SVNR|Versicherungsnummer)(?:\s+(?:ist|lautet))?\s?:?\s?$",
    re.IGNORECASE,
)


TIME_RANGE_RE = re.compile(
    r"(?<![\d.:])(\d{1,2})(?:[.:](\d{2}))?\s?(?:Uhr\s?)?[" + DASHES + r"]\s?"
    r"(\d{1,2})(?:[.:](\d{2}))?(?:\s?Uhr)?(?![\d])"
)
TIME_COLON_RE = re.compile(r"(?<![\d.:])(\d{1,2}):(\d{2})(?!\d)(?:\s?Uhr)?")
TIME_H_RE = re.compile(r"(?<![\d.:])(\d{1,2})\s?h(?:\s?(\d{2}))?(?![\w])")


def _time_text(hour: str, minute: str | None, colon: bool = False) -> str:
    """9 Uhr, 9.30 Uhr; the German of Germany writes the minutes after a colon (9:30 Uhr),
    Austria's easy-language pages after a dot like Switzerland."""
    if minute in (None, "00"):
        return f"{int(hour)} Uhr"
    return f"{int(hour)}:{minute} Uhr" if colon else f"{int(hour)}.{minute} Uhr"


def _range_text(m: re.Match[str], colon: bool = False) -> str:
    first = _time_text(m.group(1), m.group(2), colon)
    return f"{first} bis {_time_text(m.group(3), m.group(4), colon)}"


@rule(
    "NUM-04",
    lang=GERMAN,
    guide={
        "de-CH": "Uhrzeiten schreibst du so: 9 Uhr oder 9.30 Uhr. Zeitspannen so: 9 Uhr bis "
        "12 Uhr.",
        "de-DE": "Uhrzeiten schreibst du so: 9 Uhr oder 9:30 Uhr. Zeitspannen so: 9 Uhr bis "
        "12 Uhr.",
        "de-AT": "Uhrzeiten schreibst du so: 9 Uhr oder 9.30 Uhr. Zeitspannen so: 9 Uhr bis "
        "12 Uhr.",
    },
)
def num_04(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    colon = ctx.region == "DE"  # 9:30 Uhr is the form there, so the colon is no finding
    text = mask_numbers(block.text)
    spans: list[tuple[int, int]] = []
    for m in TIME_RANGE_RE.finditer(text):
        is_time = "Uhr" in m.group(0) or m.group(2) or m.group(4)
        if not is_time or int(m.group(1)) > 24 or int(m.group(3)) > 24:
            continue
        spans.append(m.span())
        yield hit(
            "NUM-04.range",
            found=m.group(0).strip(),
            expected=_range_text(m, colon),
            evidence=m.group(0).strip(),
            suggestion=_range_text(m, colon),
        )
    text = mask(text, spans)
    for regex in (TIME_H_RE,) if colon else (TIME_COLON_RE, TIME_H_RE):
        found = []
        for m in regex.finditer(text):
            minute = m.group(2)
            if int(m.group(1)) > 24:
                continue
            found.append(m.span())
            yield hit(
                "NUM-04",
                found=m.group(0).strip(),
                expected=_time_text(m.group(1), minute, colon),
                evidence=m.group(0).strip(),
                suggestion=_time_text(m.group(1), minute, colon),
            )
        text = mask(text, found)


DURATION_RE = re.compile(
    r"\d+[.,]\d+\s?(?:h|Std\.?|Stunden)\b|\d*\u00bd\s?(?:h|Std\.?|Stunden)|\b\d+\s?(?:min|Min\.)(?!\w)"
)


AMOUNT_STYLE_RE = re.compile(
    r"(?:CHF|Fr\.)\s?(\d[\d'\u2019]*)\.(?:00|[" + DASHES + r"]{1,2})"
    r"|(\d[\d'\u2019]*)\.(?:00|[" + DASHES + r"]{1,2})\s?(?:CHF|Fr\.|Franken)"
    r"|(\d[\d'\u2019]*)(?:\.\d{2})?\s?CHF\b"
)


# The amount styles of Germany and Austria the rule flags (NUM-07 asks for `500 Euro`):
# the currency before the number (`€ 330,-`, `EUR 1.234,56`), decimals or dashes before
# the currency (`1.500,00 €`, `500,00 Euro`), and `EUR` or `€` after the number.
AMOUNT_STYLE_DE_RE = re.compile(
    r"(?:EUR|€)\s?(\d[\d.]*)(?:,(?:\d{2}|[" + DASHES + r"]{1,2}))?"
    r"|(\d[\d.]*),(?:\d{2}|[" + DASHES + r"]{1,2})\s?(?:€|EUR|Euro)"
    r"|(\d[\d.]*)\s?(?:EUR|€)(?!\w)"
)

# A service number in either usual grouping (0800 123 456, 0848 35 45 55) is fine too.


# -- the region: spelling, quotation marks, words (REG-01 to REG-03; Swiss checks) ----


@rule(
    "REG-01",
    lang=CH,
    guide="Schweizer Recht·schreibung: immer ss, nie ß.",
)
def ch_01(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for m in re.finditer(rf"[{_LETTER}·]*ß[{_LETTER}·]*", block.text):
        yield hit(
            "REG-01",
            found=m.group(0),
            evidence=m.group(0),
            suggestion=m.group(0).replace("ß", "ss"),
        )


QUOTE_RE = re.compile("[\u00ab\u00bb\u2039\u203a\u201e\u201c\u201d\u201a\u2018]")


@rule(
    "REG-02",
    lang=CH,
    guide="Keine Anführungs·zeichen.",
)
def ch_02(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    found = sorted(set(QUOTE_RE.findall(block.text)))
    if found:
        yield hit("REG-02", evidence=" ".join(found))


@rule(
    "REG-01",
    lang=STANDARD,
    guide={
        "de-DE": "Recht·schreibung: ß, wo es hingehört: Straße, groß, außerdem.",
        "de-AT": "Recht·schreibung: ß, wo es hingehört: Straße, groß, außerdem.",
    },
)
def reg_01_standard(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    """Germany and Austria write ß where the standard spelling has it. A Swiss `ss` in a
    word of the spelling table (rules/data/spelling_de.toml, the unambiguous stems the
    vocabulary is rendered with) is a warning, and code writes the ß after the write
    stage and every repair round (rules/swiss.py), as it writes ss in Switzerland."""
    for m in re.finditer(rf"[{_LETTER}·]+", block.text):
        word = m.group(0)
        if "ss" not in word.lower():
            continue
        standard = standard_spelling(word)
        if standard != word:
            yield hit(
                "REG-01.standard",
                found=word,
                expected=standard,
                evidence=word,
                suggestion=standard,
                severity="warn",
            )


# Not the German „ “: guillemets and single low quotes.
QUOTE_RE_STANDARD = re.compile("[\u00ab\u00bb\u2039\u203a\u201a\u2018]")


@rule(
    "REG-02",
    lang=STANDARD,
    guide={
        "de-DE": "Anführungs·zeichen nur für wörtliche Rede, und dann so: „ “.",
        "de-AT": "Anführungs·zeichen nur für wörtliche Rede, und dann so: „ “.",
    },
)
def reg_02_standard(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    """Germany and Austria write „ “, for direct speech only (DIN SPEC 33429); guillemets
    and single quotes are a note."""
    found = sorted(set(QUOTE_RE_STANDARD.findall(block.text)))
    if found:
        yield hit("REG-02.standard", found=" ".join(found), evidence=" ".join(found))


# The Swiss words a Swiss-trained writer puts into a German or Austrian text, with the
# word of Germany and the word of Austria; None where that country uses the Swiss word.
REGIONAL_WORDS: dict[str, tuple[str | None, str | None]] = {
    "velo": ("Fahrrad", "Fahrrad"), "parkieren": ("parken", "parken"),
    "trottoir": ("Gehweg", "Gehsteig"), "spital": ("Krankenhaus", None),
    "billett": ("Fahrkarte", "Fahrkarte"), "tram": ("Straßenbahn", "Straßenbahn"),
    "perron": ("Bahnsteig", "Bahnsteig"), "matura": ("Abitur", None),
    "hauswart": ("Hausmeister", "Hausbesorger"), "grillieren": ("grillen", "grillen"),
    "rahm": ("Sahne", "Obers"), "fahrausweis": ("Führerschein", "Führerschein"),
    "identitätskarte": ("Personalausweis", "Personalausweis"), "natel": ("Handy", "Handy"),
    "offerte": ("Angebot", "Angebot"), "unterbruch": ("Unterbrechung", "Unterbrechung"),
    "januar": (None, "Jänner"),
}  # fmt: skip


@rule(
    "REG-03",
    lang=STANDARD,
    guide={
        "de-DE": "Nimm die Wörter, die in Deutschland üblich sind: Fahrrad, parken, Gehweg, "
        "Krankenhaus.",
        "de-AT": "Nimm die Wörter, die in Österreich üblich sind: Fahrrad, parken, Gehsteig, "
        "Jänner.",
    },
)
def reg_03_standard(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    """A warning, not a note as in Switzerland: the writer was trained on Swiss texts and
    puts Velo and Spital into German drafts."""
    index = 0 if ctx.region == "DE" else 1
    for sent in block.sentences:
        for t in sent:
            words = REGIONAL_WORDS.get(t.lemma_.lower()) or REGIONAL_WORDS.get(t.lower_)
            if words and words[index]:
                yield hit(
                    "REG-03.germany" if ctx.region == "DE" else "REG-03.austria",
                    found=t.text,
                    expected=words[index],
                    evidence=t.text,
                    suggestion=words[index],
                    severity="warn",
                )


HELVETISMS = {
    "fahrrad": "Velo", "parken": "parkieren", "bürgersteig": "Trottoir",
    "gehweg": "Trottoir", "krankenhaus": "Spital", "führerschein": "Fahrausweis",
    "personalausweis": "Identitätskarte", "abitur": "Matura", "hausmeister": "Hauswart",
    "sahne": "Rahm", "grillen": "grillieren", "fahrkarte": "Billett",
    "fahrschein": "Billett", "straßenbahn": "Tram", "strassenbahn": "Tram",
    "bahnsteig": "Perron", "tüte": "Sack", "kasse": None,
}  # fmt: skip


@rule(
    "REG-03",
    lang=CH,
    guide="Nimm Schweizer Wörter: Velo, parkieren, Trottoir, Spital.",
)
def ch_03(block: BlockInfo, ctx: Context) -> Iterator[Hit]:
    for sent in block.sentences:
        for t in sent:
            swiss = HELVETISMS.get(t.lemma_.lower()) or HELVETISMS.get(t.lower_)
            if swiss:
                yield hit("REG-03", found=t.text, swiss=swiss, evidence=t.text, suggestion=swiss)
