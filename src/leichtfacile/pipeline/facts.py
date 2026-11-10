"""The fact sheet and its links, without a model call (docs/architecture.md §4.2 and
§4.3): the fact sheet of the Understand answer (`factsheet_of`, `to_factsheet`), one fact
per statement (`merge_twin_facts`), every hard value of the source as a fact
(`complete_factsheet`), the vocabulary's checked explanations for its hard terms
(`vocabulary_terms`), and the bookkeeping between a draft's blocks and the facts and
source sentences they convey (`link_facts`), which the model need not get right.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Collection
from dataclasses import dataclass

from leichtfacile.pipeline.models import UnderstandOut, clean_text
from leichtfacile.pipeline.versions import stems
from leichtfacile.rules.lexicon import MEDIOPUNKT
from leichtfacile.rules.value_index import ValueIndex
from leichtfacile.rules.values import (
    HARD_KINDS,
    Value,
    contains,
    extract_values,
    format_address,
    format_identifier,
    format_period,
    matches,
    parse_value_norm,
)
from leichtfacile.rules.vocabulary import (
    explained_term,
    has_vocabulary,
    is_hard,
    matcher,
    rarity,
)
from leichtfacile.schemas import (
    Block,
    CoreAnswer,
    CoreQuestions,
    Draft,
    Fact,
    FactSheet,
    HardTerm,
    OmitCandidate,
    Segment,
    SourceDocument,
)

log = logging.getLogger(__name__)

# -- the fact sheet of the answer ----------------------------------------------------------


def to_factsheet(out: UnderstandOut, doc_id: str) -> FactSheet:
    facts = [
        Fact(
            id=f"f{i:02d}",
            kind=f.kind,
            text=f.text,
            value_norm=f.value_norm,
            segment_ids=f.segment_ids,
            must_keep=f.must_keep,
        )
        for i, f in enumerate(out.facts, 1)
        if f.text
    ]
    core = CoreQuestions(
        **{
            key: CoreAnswer(
                text=getattr(out.core, key).text, segment_ids=getattr(out.core, key).segment_ids
            )
            for key in ("what", "must_do", "deadline", "cost", "contact")
        }
    )
    return FactSheet(
        doc_id=doc_id,
        doc_type=clean_text(out.doc_type),
        audience=clean_text(out.audience),
        core=core,
        facts=facts,
        hard_terms=[
            HardTerm(
                term=clean_text(t.term),
                explanation=clean_text(t.explanation),
                segment_ids=t.segment_ids,
            )
            for t in out.hard_terms
            if t.term.strip()
        ],
        omit_candidates=[
            OmitCandidate(segment_ids=o.segment_ids, reason=clean_text(o.reason))
            for o in out.omit_candidates
            if o.segment_ids
        ],
    )


def in_source(term: str, source: SourceDocument) -> bool:
    """Whether a hard term of the model is a term of the source: written there, or every
    word of it there in another form (Kantonales Einführungsgesetz, kantonalen
    Einführungsgesetz). The 8B listed the Understand example's own term for 6 documents
    of the CSCS evaluation (Einwohnerkontrolle, contrôle des habitants; 8 October 2026),
    and the writer then sent the reader to that office."""
    text = source.text()
    if term.lower().replace(MEDIOPUNKT, "") in text.lower().replace(MEDIOPUNKT, ""):
        return True
    words = set(stems(term, source.lang))
    return bool(words) and words <= set(stems(text, source.lang))


def factsheet_of(
    out: UnderstandOut, source: SourceDocument, topical: Collection[str] = ()
) -> FactSheet:
    """The fact sheet of the model's answer for a source: its facts without those about
    the prompt's own examples (`topical`, checks.drop_topical), numbered f01, f02, ...,
    and its hard terms that are terms of the source (`in_source`). The answer stays as
    the model gave it."""
    if topical:
        out = out.model_copy(update={"facts": [f for f in out.facts if f.text not in topical]})
    fs = to_factsheet(out, source.id)
    terms = [t for t in fs.hard_terms if in_source(t.term, source)]
    if len(terms) < len(fs.hard_terms):
        log.warning("understand: %d hard terms not in the source", len(fs.hard_terms) - len(terms))
        fs = fs.model_copy(update={"hard_terms": terms})
    return fs


# -- one fact per statement, every hard value a fact -----------------------------------

_DEADLINE_WORDS = re.compile(
    r"\b(?:bis|spätestens|Frist|innert|innerhalb|avant|jusqu|délai|entro|termine)\b",
    re.IGNORECASE,
)
_VALUE_KIND = {
    "amount": "amount",
    "phone": "contact",
    "email": "contact",
    "url": "contact",
    "address": "contact",
}


def _value_norm(value: Value, lang: str) -> str:
    """The value as the fact sheet carries it, readable for the writer and the reviewer
    and parsed back by `parse_value_norm`: the web address as written, a period in
    words (30 Tage), an IBAN in groups, an address with its parts."""
    if value.kind == "url":
        return value.text
    if value.kind == "percent":
        # The canonical form is the bare number; written back as "10%", the form the
        # Understand prompt asks for, it parses as a percentage again. As a bare
        # number it parsed as a plain number and never matched the percentage in a
        # draft (found 7 October 2026 by the silent-loss metric).
        return f"{value.canonical}%"
    if value.kind == "period":
        return format_period(value.canonical, lang)
    if value.kind == "identifier":
        return format_identifier(value.canonical)
    if value.kind == "address":
        return format_address(value.canonical)
    return value.canonical


def _fact_values(fact: Fact, lang: str) -> list[Value]:
    """A fact's values: its normalised value, else the hard values in its text."""
    if value := parse_value_norm(fact.value_norm, fact.kind, lang):
        return [value]
    return [v for v in extract_values(fact.text, lang) if v.kind in HARD_KINDS]


def _values_agree(a: list[Value], b: list[Value]) -> bool:
    """Whether every value of the smaller list has its match in the other."""
    if not a or not b:
        return False
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    return all(any(matches(x, y) or matches(y, x) for y in large) for x in small)


def merge_twin_facts(facts: list[Fact], lang: str) -> list[Fact]:
    """One fact for one statement. The model sometimes lists a statement twice, once
    with its value and once without it in other words ("La fattura ... entro 30 giorni"
    as f04 and f15 in the school letters, 31 October 2026), and a round then adds it
    twice. Two of the model's facts that cite a common sentence, are of one kind, both
    to keep or both not, and agree in their values are one fact: the one with the
    normalised value stays, else the first, with the sentences of both."""
    kept: list[Fact] = []
    values = {f.id: _fact_values(f, lang) for f in facts}
    for fact in facts:
        twin = next(
            (
                k
                for k in kept
                if fact.origin != "code"
                and k.origin != "code"
                and k.kind == fact.kind
                and k.must_keep == fact.must_keep
                and set(k.segment_ids) & set(fact.segment_ids)
                and _values_agree(values[k.id], values[fact.id])
            ),
            None,
        )
        if twin is None:
            kept.append(fact)
            continue
        first, second = (twin, fact) if twin.value_norm or not fact.value_norm else (fact, twin)
        segments = list(dict.fromkeys([*first.segment_ids, *second.segment_ids]))
        kept[kept.index(twin)] = first.model_copy(update={"segment_ids": segments})
    return kept


def _only_value(text: str, lang: str, value: Value) -> bool:
    """Whether the value is the one hard value the text holds."""
    held = [v for v in extract_values(text, lang) if v.kind in HARD_KINDS]
    return len(held) == 1 and (matches(value, held[0]) or matches(held[0], value))


def _occurrences(
    index: ValueIndex, source: SourceDocument
) -> list[tuple[Value, list[Segment], set[str]]]:
    """Each hard value of the source text once: the segments of its first occurrence
    (the fact's sentences and text) and the ids of the segments of every occurrence. A
    later occurrence joins the first as the first covers it (`matches`, in the direction
    of `complete_factsheet`'s cover check). A value of the title alone belongs to no
    segment and makes no fact."""
    found: list[tuple[Value, list[Segment], set[str]]] = []
    by_id = source.by_id()
    for value, holders in zip(index.values, index.holders, strict=True):
        if value.kind not in HARD_KINDS or not holders:
            continue
        segments = [by_id[i] for i in holders]
        ids = set(holders)
        for first, _, everywhere in found:
            if matches(value, first):
                everywhere |= ids
                break
        else:
            found.append((value, segments, ids))
    return found


def complete_factsheet(fs: FactSheet, source: SourceDocument) -> FactSheet:
    """Code makes sure no hard value is forgotten: every date, amount, phone number,
    e-mail address, web address, percentage, time, period (`innert 30 Tagen`),
    identifier (case number, AHV number, IBAN) and postal address in the source that
    no fact carries becomes a fact of its own, or the value of the model's fact that
    holds it in its text without a normalised value. Values in passages the model
    marked as droppable become background facts; the rest must be kept. Before that,
    two of the model's facts for one statement become one (`merge_twin_facts`)."""
    lang = source.variety  # the values are read in the source's variety (de-DE: 1.500,00 €)
    facts = merge_twin_facts(list(fs.facts), lang)
    covered = [v for f in facts if (v := parse_value_norm(f.value_norm, f.kind, lang))]
    omitted = {s for o in fs.omit_candidates for s in o.segment_ids}
    # New ids follow the highest one, so none repeats an id a merge left standing.
    next_id = 1 + max((int(f.id[1:]) for f in facts if f.id[1:].isdigit()), default=0)
    # The values are taken from the document text as the evaluation's "hard facts
    # kept" takes them, not sentence by sentence: an address over two sentences
    # (`Gerichtsstrasse 12` / `8000 Musterwil`) is one value, found in neither alone
    # (the silent-loss metric showed the gap on 7 October 2026). Each value cites
    # the segments it spans.
    index = ValueIndex.of_source(source, lang)
    for value, segments, everywhere in _occurrences(index, source):
        # Covered means: a reader who searches the fact sheet for this value finds it
        # (the evaluation's silent-loss check asks the same question, in the same
        # direction). A fact with the place alone does not cover the full address,
        # and a bare number does not cover a quantity; the fact for the full value
        # is added next to the model's.
        if any(matches(value, c) for c in covered):
            continue
        covered.append(value)
        # The model's fact that holds this value in its text and cites a sentence it
        # stands in becomes the fact for it, not a second fact beside it: the 70B listed
        # "deve essere pagata entro 30 giorni" without a value, code added the period
        # again as a fact of its own, and the rounds then wrote both (31 October 2026).
        # Any occurrence counts: searched at the first alone, a fact citing the second
        # got no value and code added the deadline twice (audit of 6 November 2026).
        holder = next(
            (
                f
                for f in facts
                if f.origin != "code"
                and not f.value_norm
                and set(f.segment_ids) & everywhere
                and _only_value(f.text, lang, value)
            ),
            None,
        )
        if holder is not None:
            facts[facts.index(holder)] = holder.model_copy(
                update={"value_norm": _value_norm(value, lang)}
            )
            continue
        kind = _VALUE_KIND.get(value.kind, "other")
        cited = " ".join(seg.text for seg in segments)
        if value.kind in ("date", "period") and _DEADLINE_WORDS.search(cited):
            kind = "deadline"
        facts.append(
            Fact(
                id=f"f{next_id:02d}",
                kind=kind,
                text=cited if len(cited) <= 200 else cited[:197] + "...",
                value_norm=_value_norm(value, lang),
                segment_ids=[seg.id for seg in segments],
                must_keep=any(s.id not in omitted and s.kind != "heading" for s in segments),
                origin="code",
            )
        )
        next_id += 1
    return fs.model_copy(update={"facts": facts})


# The vocabulary (rules/data/vocabulary_<lang>.toml) in the fact sheet.
MAX_HARD_TERMS = 12  # the fact sheet's hard terms, the model's and the vocabulary's
MAX_VOCABULARY_TERMS = 6  # terms of the source code adds to the model's


def vocabulary_terms(fs: FactSheet, source: SourceDocument) -> FactSheet:
    """The fact sheet with the vocabulary's checked explanations. A hard term the model
    listed gets the vocabulary's explanation when the vocabulary explains it: the 8B's
    own were often hard or wrong (Franchise and Selbstbehalt explained alike, the Urne
    as the place of the vote; CSCS dev run of 7 October 2026). Terms of the source the
    model did not list are added, the rarest first, up to MAX_VOCABULARY_TERMS and
    MAX_HARD_TERMS in all. The write prompt shows the hard terms and asks the writer to
    take the glossary explanations from them."""
    lang = source.variety  # the vocabulary of the variety: Bescheid and Beschwerde in Austria
    if not has_vocabulary(lang):
        return fs
    terms: list[HardTerm] = []
    listed: set[str] = set()
    for term in fs.hard_terms:
        entry = explained_term(term.term, lang)
        if entry is None:
            terms.append(term)
            continue
        listed.add(entry.term)
        update = {"explanation": entry.explanation or term.explanation, "origin": "vocabulary"}
        terms.append(term.model_copy(update=update))
    found: dict[str, tuple] = {}
    texts = (s.text for s in source.segments)
    for seg, found_here in zip(source.segments, matcher(lang).find_texts(texts), strict=True):
        for m in found_here:
            entry = m.entry
            if entry.kind != "explain" or entry.context or entry.term in listed:
                continue
            if not is_hard(entry, lang):
                continue
            segment_ids = found.setdefault(entry.term, (entry, []))[1]
            if seg.id not in segment_ids:
                segment_ids.append(seg.id)
    room = min(MAX_VOCABULARY_TERMS, MAX_HARD_TERMS - len(terms))
    ranked = sorted(found.values(), key=lambda item: rarity(item[0], lang))
    for entry, segment_ids in ranked[: max(0, room)]:
        terms.append(
            HardTerm(
                term=entry.term,
                explanation=entry.explanation or "",
                segment_ids=segment_ids,
                origin="vocabulary",
            )
        )
    return fs.model_copy(update={"hard_terms": terms})


# -- the links between blocks, facts and source sentences ---------------------------------

# Provenance by wording (FACT-03): words of four letters or more that are no function
# words, compared by their first five letters (versée, versement; Prämien·verbilligung,
# Prämienverbilligung). One shared word alone counts from seven letters on: a content
# word (espèces), not an adverb (sofort).
_LONG_WORD = 7


def shared_stems(text: str, other: str, lang: str) -> int:
    """How many word stems two texts share (`versions.stems`): which of several blocks that
    carry a fact states it (rounds.build_request)."""
    return len(stems(text, lang).keys() & stems(other, lang).keys())


def wording_source(text: str, source: SourceDocument) -> str | None:
    """The source sentence a block says in other words, for a block that names neither
    a sentence nor a fact: the sentence it shares the most words with, each word
    weighted by one over the number of sentences that have it. The sentence must reach
    a weight of 1 (a word no other sentence has, or two words shared with one other
    sentence each), share two words or one long word, and outweigh every other; else
    None. In the French example letter the 8B wrote "Vous ne pouvez pas recevoir cet
    argent en espèces." without a source, so FACT-03 flagged it and the judge, which
    sees only the cited sentences, called it invented (CSCS, 8 October 2026)."""
    sentences = [s for s in source.segments if s.kind != "heading"]
    per_sentence = [set(stems(s.text, source.lang)) for s in sentences]
    count: dict[str, int] = {}
    for words in per_sentence:
        for w in words:
            count[w] = count.get(w, 0) + 1
    block = stems(text, source.lang)
    scores = sorted(
        (
            (sum(1 / count[w] for w in block.keys() & words), i)
            for i, words in enumerate(per_sentence)
        ),
        reverse=True,
    )
    if not scores or scores[0][0] < 1 or (len(scores) > 1 and scores[1][0] == scores[0][0]):
        return None
    shared = block.keys() & per_sentence[scores[0][1]]
    if len(shared) < 2 and not any(block[w] >= _LONG_WORD for w in shared):
        return None
    return sentences[scores[0][1]].id


@dataclass(frozen=True)
class _FactGroups:
    """The fact sheet as `link_facts` reads it: the ids it has, the sentences of each
    fact, and its facts in the four groups a block conveys in different ways. `of`
    builds it once per draft."""

    known: set[str]  # the sheet's fact ids
    sources_of: dict[str, list[str]]  # fact id -> its sentences
    # (fact id, its value, its sentences) of the facts with a value
    targets: list[tuple[str, Value, list[str]]]
    # (fact id, its segments) of the facts without a value that code added
    parts: list[tuple[str, set[str]]]
    # (fact id, its segments, the values in its text) of the model's others
    worded: list[tuple[str, set[str], list[Value]]]
    # (fact id, its segments) of the facts with no value anywhere
    plain: list[tuple[str, set[str]]]

    @classmethod
    def of(cls, factsheet: FactSheet, variety: str) -> _FactGroups:
        targets: list[tuple[str, Value, list[str]]] = []
        parts: list[tuple[str, set[str]]] = []
        worded: list[tuple[str, set[str], list[Value]]] = []
        plain: list[tuple[str, set[str]]] = []
        for fact in factsheet.facts:
            value = parse_value_norm(fact.value_norm, fact.kind, variety)
            if value is not None:
                targets.append((fact.id, value, fact.segment_ids))
            elif fact.origin == "code":
                parts.append((fact.id, set(fact.segment_ids)))
            elif in_text := extract_values(fact.text, variety):
                worded.append((fact.id, set(fact.segment_ids), in_text))
            elif fact.segment_ids:
                plain.append((fact.id, set(fact.segment_ids)))
        return cls(
            known=factsheet.fact_ids(),
            sources_of={f.id: f.segment_ids for f in factsheet.facts},
            targets=targets,
            parts=parts,
            worded=worded,
            plain=plain,
        )


def _same_value(target: Value, candidate: Value) -> bool:
    """`matches` for the values in a fact's text: a plain number stands for itself only,
    so "Art. 5 des Gesetzes" is not conveyed by "Das kostet 5 Franken", nor the other way
    round (audit of 6 November 2026). A fact's `value_norm` keeps `matches` as it is: a
    fact "30" written as "30 Tage" is still found."""
    if "number" in (target.kind, candidate.kind) and target.kind != candidate.kind:
        return False
    return matches(target, candidate)


def _own_sentences(b: Block, source_ids: set[str] | None) -> list[str]:
    """The source sentences the block names itself, those the source has."""
    if source_ids is None:
        return list(b.segment_ids)
    # An id the source does not have names no sentence: the 8B cited a block id
    # (`s0009.2`) in the German example letter (CSCS, 8 October 2026).
    return [s for s in b.segment_ids if s in source_ids]


def _held_facts(
    holding: list[tuple[str, Value, list[str]]], cited: set[str]
) -> list[tuple[str, list[str]]]:
    """The facts whose value the block contains (fact id, its sentences). Of two facts
    with one value (a revoked decision and a filing deadline, both of 31 March 2026), a
    block that cites a sentence of one conveys that one alone; both when it cites a
    sentence of neither. The block about the deadline used to get both, so FACT-02 was
    satisfied for the wrong fact and a judge "missing" was routed to that block (audit
    of 6 November 2026)."""
    kept: list[tuple[str, list[str]]] = []
    for fact_id, target, segments in holding:
        rivals = [
            s
            for other, t, s in holding
            if other != fact_id and (matches(target, t) or matches(t, target))
        ]
        if set(segments) & cited or not any(set(s) & cited for s in rivals):
            kept.append((fact_id, segments))
    return kept


def _cited_sentences(
    b: Block,
    facts: _FactGroups,
    held: list[tuple[str, list[str]]],
    source: SourceDocument | None,
    source_ids: set[str] | None,
) -> list[str]:
    """The source sentences a block cites. A content block that cites none (FACT-03)
    takes those of the facts whose values it contains (`held`: fact id, its sentences),
    else those of the facts it names, else, with the `source`, the sentence it says in
    other words (`wording_source`)."""
    segment_ids = _own_sentences(b, source_ids)
    if segment_ids or b.kind == "heading":
        return segment_ids
    for _, fact_segments in held:
        segment_ids += [s for s in fact_segments if s not in segment_ids]
    if not segment_ids:
        for fact_id in b.fact_ids:
            segment_ids += [s for s in facts.sources_of.get(fact_id, []) if s not in segment_ids]
    if not segment_ids and source is not None and (found := wording_source(b.text, source)):
        segment_ids = [found]
    return segment_ids


def _block_links(
    b: Block,
    facts: _FactGroups,
    variety: str,
    source: SourceDocument | None,
    source_ids: set[str] | None,
    values: list[Value],
) -> tuple[list[str], list[str]]:
    """The fact ids and the sentence ids one block ends up with: the ids it names that
    the sheet has and the facts whose value it contains (`_held_facts`), then, by the
    sentences it cites (`_cited_sentences`), the parts and plain facts of a cited
    sentence and the worded facts all of whose values it contains (`_same_value`).
    `values`: the block's values (`ValueIndex.of_blocks`)."""
    holding = [
        (fact_id, target, fact_segments)
        for fact_id, target, fact_segments in facts.targets
        if contains(target, b.text, values)
    ]
    held = _held_facts(holding, set(_own_sentences(b, source_ids)))
    segment_ids = _cited_sentences(b, facts, held, source, source_ids)
    ids = [f for f in b.fact_ids if f in facts.known]
    for fact_id, _ in held:
        if fact_id not in ids:
            ids.append(fact_id)
    for fact_id, segments in (*facts.parts, *facts.plain):
        if fact_id not in ids and segments & set(segment_ids):
            ids.append(fact_id)
    for fact_id, segments, in_text in facts.worded:
        if (
            fact_id not in ids
            and segments & set(segment_ids)
            and all(any(_same_value(t, v) for v in values) for t in in_text)
        ):
            ids.append(fact_id)
    return ids, segment_ids


def _with_spread_facts(
    blocks: list[Block], worded: list[tuple[str, set[str], list[Value]]], index: ValueIndex
) -> list[Block]:
    """The blocks with each worded fact (`_FactGroups.worded`) no block conveys yet whose
    values the writer spread over the blocks that cite its sentences (the two income
    limits in two sentences, 10 October 2026): conveyed when those blocks together hold
    every value, named on each of them that holds one."""
    for fact_id, segments, in_text in worded:
        if any(fact_id in b.fact_ids for b in blocks):
            continue
        citing = [i for i, b in enumerate(blocks) if segments & set(b.segment_ids)]
        held = {i: index.of_part(blocks[i].id) for i in citing}
        if citing and all(any(_same_value(t, v) for i in citing for v in held[i]) for t in in_text):
            for i in citing:
                if any(_same_value(t, v) for t in in_text for v in held[i]):
                    blocks[i] = blocks[i].model_copy(
                        update={"fact_ids": [*blocks[i].fact_ids, fact_id]}
                    )
    return blocks


def link_facts(draft: Draft, factsheet: FactSheet, source: SourceDocument | None = None) -> Draft:
    """Bookkeeping the model need not get right: a block that contains a fact's exact
    value conveys that fact, a block that cites a source sentence of a protected part of
    a decision (a code fact without a value, rules/decision.py) conveys that part, and
    fact ids and, with the `source`, sentence ids that do not exist are dropped. A
    block that cites no source sentence (FACT-03) takes those of the facts whose values
    it contains, else those of the facts it names, else, with the `source`, the sentence
    it says in other words (`wording_source`). A fact without a value whose text holds
    values is conveyed by a block that cites one of its sentences and contains all of
    them (FACT-02: the writer named the narrower facts of those values), or by the blocks
    that cite its sentences and together hold all of them, each that holds one (10
    October 2026). A fact without a value and without values in its text is conveyed by
    every block that cites one of its sentences (10 October 2026: the writer renders the
    sentence and leaves the tag out; the judge's fact check still reads the meaning)."""
    facts = _FactGroups.of(factsheet, draft.variety)
    source_ids = source.segment_ids() if source is not None else None
    index = ValueIndex.of_blocks(draft.blocks, draft.variety)  # the values once per block
    blocks: list[Block] = []
    for b in draft.blocks:
        ids, segment_ids = _block_links(
            b, facts, draft.variety, source, source_ids, index.of_part(b.id)
        )
        if ids == b.fact_ids and segment_ids == b.segment_ids:
            blocks.append(b)
        else:
            blocks.append(b.model_copy(update={"fact_ids": ids, "segment_ids": segment_ids}))
    blocks = _with_spread_facts(blocks, facts.worded, index)
    return draft.model_copy(update={"blocks": blocks})
