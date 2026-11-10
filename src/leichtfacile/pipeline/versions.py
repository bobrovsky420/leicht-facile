"""A new draft version from a model's answer, without a model call (docs/architecture.md
§4.6): the pure half of the write, repair and recover rounds, which `stages.write`,
`stages.repair` and `stages.recover_fact` hand their parsed answers to. An answer is
read, never changed (the answer models are frozen): what a version leaves out of it is
left out of a copy, so the record of what the model answered and what code applied
cannot drift apart.

One module decides what every round shares: how a sentence is keyed to find a repeat
(`sentence_key`, `wording_key`), what a repeat removes (the newcomer, never the block it
repeats), which ids a split or an added sentence gets (`child_id`), what counts as part
of a list so that an addition lands after the list (`in_list`, `list_end`), where a
recovered sentence goes (`fact_window`, `target_block`, `add_sentences`), and what of an
answer is left out, recorded with its reason (`DroppedText`). The recorded rounds of
tests/fixtures/repairs/ replay `apply_repairs` and pin what it makes of a real answer.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field

from leichtfacile.ingest.detect import STOPWORDS
from leichtfacile.ingest.segment import split_sentences
from leichtfacile.pipeline.models import AdditionItem, RepairOut, WriteOut, clean_text
from leichtfacile.rules.lexicon import MEDIOPUNKT
from leichtfacile.rules.values import (
    HARD_KINDS,
    Value,
    contains,
    extract_values,
    matches,
    parse_value_norm,
)
from leichtfacile.schemas import (
    AnsweredAddition,
    AnsweredRepair,
    Block,
    Draft,
    DroppedText,
    DropReason,
    Fact,
    FactSheet,
    GlossaryEntry,
    Level,
    Omission,
    RepairRecord,
    SourceDocument,
)

# -- the keys of a sentence ------------------------------------------------------------


def sentence_key(text: str) -> str:
    """A sentence as `drop_repeats` compares it: lower case, without the Mediopunkt (a
    repair that writes Krankenversicherung repeats the Kranken·versicherung sentence
    code split earlier, rules/mediopunkt.py), single spaces, no final full stop,
    exclamation or question mark and no final colon (an intro line of a list repeats
    the sentence it was made from)."""
    return wording_key(text).rstrip(":")


def wording_key(text: str) -> str:
    """A sentence's wording for the repeat checks of the repair and recover rounds: lower
    case, without the Mediopunkt, single spaces, no final full stop, exclamation or
    question mark. A final colon stays: an intro line and a sentence differ."""
    return " ".join(text.lower().replace(MEDIOPUNKT, "").split()).rstrip(".!?")


# Provenance by wording (FACT-03) and the restatement check: words of four letters or
# more that are no function words, compared by their first five letters (versée,
# versement; Prämien·verbilligung, Prämienverbilligung).
_WORD_RE = re.compile(r"[^\W\d_]{4,}")
_STEM_LETTERS = 5


def stems(text: str, lang: str) -> dict[str, int]:
    """The stems of a text's words, each with the length of its longest word."""
    stop = STOPWORDS.get(lang, frozenset())
    found: dict[str, int] = {}
    for word in _WORD_RE.findall(text.lower().replace(MEDIOPUNKT, "")):
        if word not in stop:
            stem = word[:_STEM_LETTERS]
            found[stem] = max(found.get(stem, 0), len(word))
    return found


# -- ids and lists -----------------------------------------------------------------------


def child_id(base: str, taken: set[str]) -> str:
    """The first of `base.1`, `base.2`, ... that no block has yet, marked as taken: the
    id of a sentence split off a block or added after it."""
    n = 1
    while f"{base}.{n}" in taken:
        n += 1
    taken.add(f"{base}.{n}")
    return f"{base}.{n}"


def in_list(b: Block, by_id: dict[str, Block]) -> bool:
    """Whether a block is part of a list: an item, or a sentence placed after an item
    under its id (`b005.1`, a recovered fact). `apply_repairs` and `list_end` share the
    rule, so an addition after an item lands after such a sentence too."""
    base = by_id.get(b.id.split(".")[0])
    return b.kind == "list_item" or ("." in b.id and base is not None and base.kind == "list_item")


def list_end(blocks: list[Block], at: int) -> int:
    """From `at`, the index after the list the blocks there belong to (`in_list`)."""
    by_id = {b.id: b for b in blocks}
    while at < len(blocks) and in_list(blocks[at], by_id):
        at += 1
    return at


# -- repeats -----------------------------------------------------------------------------


def drop_repeats(blocks: list[Block], *, renumber: bool = True) -> list[Block]:
    """A sentence or list item that repeats an earlier one is dropped, and its fact and
    source references go to the first; a heading this leaves without content goes too.
    Small models repeat a fact under every heading it answers (the deadline under "What
    must you do?" and again under "By when?"). After a repair the ids stay as they are."""
    kept: list[Block] = []
    first: dict[str, int] = {}
    heading: int | None = None  # the index in `kept` of the heading the blocks are under
    with_content: set[int] = set()  # the headings that keep content below them
    emptied: set[int] = set()  # the headings whose content this pass removed
    for b in blocks:
        if b.kind == "heading":
            kept.append(b)
            heading = len(kept) - 1
            continue
        key = sentence_key(b.text)
        if key in first:
            i = first[key]
            kept[i] = kept[i].model_copy(
                update={
                    "fact_ids": list(dict.fromkeys(kept[i].fact_ids + b.fact_ids)),
                    "segment_ids": list(dict.fromkeys(kept[i].segment_ids + b.segment_ids)),
                }
            )
            if heading is not None:
                emptied.add(heading)
            continue
        first[key] = len(kept)
        kept.append(b)
        if heading is not None:
            with_content.add(heading)
    if len(kept) == len(blocks):
        return blocks
    # A heading goes only when this pass removed everything below it. A title above a
    # section heading, or a heading the writer left empty, went too whenever a repeat
    # stood anywhere, and the ids moved (audit of 6 November 2026).
    content = [b for k, b in enumerate(kept) if k not in emptied or k in with_content]
    if not renumber:
        return content
    return [b.model_copy(update={"id": f"b{i:03d}"}) for i, b in enumerate(content, 1)]


def value_present(fact: Fact, draft: Draft) -> bool:
    """Whether a block of the draft carries the fact's value, FACT-01's question for one
    fact: the recover round asks for a value only while the draft lacks it, since a
    recovery before it in the same round may have brought it (the 70B's sentence for
    the departure time named the return time too, and the next call then wrote the
    return time twice more; 31 October 2026)."""
    target = parse_value_norm(fact.value_norm, fact.kind, draft.variety)
    if target is None:
        return False
    return any(
        contains(target, b.text, extract_values(b.text, draft.variety)) for b in draft.blocks
    )


def carries(target: Value | None, text: str, variety: str) -> bool:
    """Whether a text contains the fact's value; a fact without one is carried by none."""
    return target is not None and contains(target, text, extract_values(text, variety))


def repeats(
    text: str, target: Value | None, had: set[str], draft_values: list[Value], variety: str
) -> bool:
    """Whether an answered sentence repeats the draft: its wording is one of the draft's
    (`had`, by `wording_key`), or it lacks the fact's value and the draft has its hard
    values already (`draft_values`). A sentence without the fact's value whose values
    the draft already has repeats the draft: the 8B added the income limits of block
    b009.1 to the date it was asked for."""
    if wording_key(text) in had:
        return True
    if carries(target, text, variety):
        return False
    hard = [v for v in extract_values(text, variety) if v.kind in HARD_KINDS]
    return bool(hard) and all(any(matches(v, d) for d in draft_values) for v in hard)


# -- the write stage's answers ---------------------------------------------------------------


def first_version(
    source: SourceDocument,
    factsheet: FactSheet,
    answers: Iterable[tuple[WriteOut, Collection[str]]],
    *,
    level: Level,
    address: str = "formal",
) -> Draft:
    """Version 1 from the write stage's answers, one per section in the source's order,
    each with the texts left out of it (about the prompt's own examples,
    checks.drop_topical): the blocks numbered b001, b002, ... across the sections, with
    the fact ids the sheet has; the omissions; the glossary, a term once; and no sentence
    twice (`drop_repeats`)."""
    known_facts = factsheet.fact_ids()
    blocks: list[Block] = []
    omissions: list[Omission] = []
    glossary: dict[str, GlossaryEntry] = {}
    for out, left_out in answers:
        for b in out.blocks:
            if b.text in left_out:
                continue
            blocks.append(
                Block(
                    id=f"b{len(blocks) + 1:03d}",
                    kind=b.kind,
                    text=b.text,
                    fact_ids=[f for f in b.fact_ids if f in known_facts],
                    segment_ids=b.segment_ids,
                )
            )
        omissions += [
            Omission(what=clean_text(o.what), why=clean_text(o.why), segment_ids=o.segment_ids)
            for o in out.omissions
            if o.what or o.segment_ids
        ]
        for g in out.glossary:
            glossary.setdefault(
                g.term.strip().lower(),
                GlossaryEntry(term=clean_text(g.term), explanation=clean_text(g.explanation)),
            )
    return Draft(
        doc_id=source.id,
        lang=source.lang,
        region=source.region,
        level=level,
        address=address,
        version=1,
        origin="write",
        blocks=drop_repeats(blocks),
        omissions=omissions,
        glossary=list(glossary.values()),
    )


# -- the repair round's answer ------------------------------------------------------------


@dataclass
class RepairRequest:
    problems: dict[str, list[str]]  # block id -> problem lines
    missing: list[Fact]

    def __bool__(self) -> bool:
        return bool(self.problems or self.missing)


_SENTENCE_END = (".", "!", "?", ":")


def sentences_of(texts: list[str], lang: str) -> list[str]:
    """The answer's texts as sentences: a text without final punctuation joins the next
    one when that starts in lower case (the 70B split a sentence at its comma into two
    texts, "Wenn du nicht entschuldigt fehlst" and "werden die Absenzen im Zeugnis
    vermerkt."), and a text of several sentences is split into them (it wrote three as
    one; 31 October 2026)."""
    joined: list[str] = []
    for text in (t.strip() for t in texts if t.strip()):
        if joined and not joined[-1].endswith(_SENTENCE_END) and text[:1].islower():
            joined[-1] = f"{joined[-1]} {text}"
        else:
            joined.append(text)
    out: list[str] = []
    for text in joined:
        out += split_sentences(text, lang) or [text]
    return out


def _answer_by_block(
    draft: Draft, out: RepairOut, request: RepairRequest, dropped: list[DroppedText]
) -> tuple[dict[str, list[str]], dict[str | None, list[AdditionItem]]]:
    """The answer as sentences: the repairs by block id, the flagged blocks' only, and
    the additions by the block they follow (None: a block the draft does not have, or
    none named). A repair of a block the round had not flagged goes to `dropped`: the
    prompt says only the flagged blocks. A block the answer repairs twice gets the texts
    of both (the second used to replace the first). The answer is not changed: an
    addition comes back as a copy with its texts as sentences."""
    repairs: dict[str, list[str]] = {}
    for item in out.repairs:
        texts = sentences_of(item.texts, draft.lang)
        if item.id in request.problems:
            repairs.setdefault(item.id, []).extend(texts)
        else:  # the prompt says: only the flagged blocks
            dropped += [DroppedText(text=t, reason="not_flagged", block_id=item.id) for t in texts]
    additions: dict[str | None, list[AdditionItem]] = {}
    block_ids = set(draft.by_id())
    for add in out.additions:
        anchor = add.after if add.after in block_ids else None
        sentences = add.model_copy(update={"texts": sentences_of(add.texts, draft.lang)})
        additions.setdefault(anchor, []).append(sentences)
    return repairs, additions


@dataclass(frozen=True)
class _Given:
    """What a repair round is given before its answer is placed: the draft's language,
    what the draft keeps and conveys without the blocks under repair, what the round
    asked for and where the draft's content blocks stand. The checks on an answered
    sentence read it (`_left_out`, `_restates`, the repeat checks of `_append_repair`
    and `_append_additions`); `of` builds it once per round."""

    lang: str
    variety: str
    fact_ids: set[str]  # the fact sheet's: an id the writer invented carries nothing
    kept: set[str]  # the wording of every block not under repair (`wording_key`)
    conveyed: set[str]  # the facts the content blocks not under repair carry
    requested: set[str]  # the facts asked for
    targets: dict[str, Value]  # their values, where the sheet has one to parse
    content: list[Block]  # the draft's content blocks in order, no headings
    position: dict[str, int]  # block id -> its index in `content`

    @classmethod
    def of(
        cls, draft: Draft, request: RepairRequest, factsheet: FactSheet, repaired: set[str]
    ) -> _Given:
        # A repair must not repeat a sentence that is already in the draft elsewhere.
        kept = {wording_key(b.text) for b in draft.blocks if b.id not in repaired}
        # A heading carries nothing, whatever fact ids the writer gave it (`link_facts`).
        conveyed = {
            f
            for b in draft.blocks
            if b.id not in repaired and b.kind != "heading"
            for f in b.fact_ids
        }
        requested = {f.id: f for f in request.missing}
        targets = {
            fact_id: target
            for fact_id, fact in requested.items()
            if (target := parse_value_norm(fact.value_norm, fact.kind, draft.variety)) is not None
        }
        content = [b for b in draft.blocks if b.kind != "heading"]
        return cls(
            lang=draft.lang,
            variety=draft.variety,
            fact_ids=factsheet.fact_ids(),
            kept=kept,
            conveyed=conveyed,
            requested=set(requested),
            targets=targets,
            content=content,
            position={b.id: i for i, b in enumerate(content)},
        )


def _known_ids(add: AdditionItem, given: _Given) -> list[str]:
    """The addition's fact ids the sheet has, in the answer's order."""
    return [f for f in add.fact_ids if f in given.fact_ids]


def _left_out(add: AdditionItem, given: _Given) -> DropReason | None:
    """Why an addition stays out of the version, None when it goes in. An addition must
    not say again, in other words, what the draft already says: one whose facts the
    draft's content blocks all carry (by the links of `link_facts`), none of them asked
    for, is left out as `conveyed`. The model volunteers such sentences next to the
    ones asked for: 35 of the 80 sentences the rounds added to the six school letters
    (Apertus 70B, 31 October 2026) were of this kind, and the check on wording
    (`_Given.kept`, by `wording_key`) sees only the same wording. And an addition
    asked for a value that brings none of it is not what was asked for (`no_value`):
    the 70B hung the requested fact id on six sentences that restated the packing
    list. A fact FACT-01 asks for is never carried: its value is nowhere."""
    ids = set(_known_ids(add, given))
    asked = ids & given.requested
    if ids and not asked and ids <= given.conveyed:
        return "conveyed"
    if asked and asked <= given.targets.keys():
        values = [(t, extract_values(t, given.variety)) for t in add.texts]
        if not any(contains(given.targets[f], t, v) for f in asked for t, v in values):
            return "no_value"
    return None


def _restates(text: str, anchor_id: str | None, add: AdditionItem, given: _Given) -> bool:
    """Whether a volunteered sentence says in other words what one block near its place
    already says: every content word of it and every value stands in that one block
    (the block it follows, that block's neighbours, a block that cites one of its
    source sentences or carries one of its facts; without a block, or after a heading,
    the draft's last two content blocks). The 70B adds "Ruf den Betrieb und das
    Schulsekretariat an." after the sentence that says so, whatever fact ids it gives
    the addition (31 October 2026). Words are compared by their first four letters
    (Tage, Tagen), values by `matches`. One block, not the words of several, and never
    a sentence asked for: easy language reuses its words, and the first form of this
    check, against the words of all the blocks around and on repair texts too, dropped
    rewrites that said something new in known words, so the loop stopped on "no
    progress" and the eval pairs kept 1 to 2 more errors per 100 blocks (the Public AI
    rerun of the same day)."""
    if set(_known_ids(add, given)) & given.requested:
        return False
    words = {s[:4] for s in stems(text, given.lang)}
    values = extract_values(text, given.variety)
    if len(words) < 2 and not values:
        return False
    content = given.content
    i = given.position.get(anchor_id) if anchor_id is not None else None
    around = content[max(0, i - 1) : i + 2] if i is not None else content[-2:]
    around += [
        b
        for b in content
        if set(b.segment_ids) & set(add.segment_ids) or set(b.fact_ids) & set(add.fact_ids)
    ]
    for b in around:
        known_values = extract_values(b.text, given.variety)
        if words <= {s[:4] for s in stems(b.text, given.lang)} and all(
            any(matches(v, k) or matches(k, v) for k in known_values) for v in values
        ):
            return True
    return False


@dataclass
class _NewVersion:
    """The version under construction: its blocks so far, the ids given out (the draft's
    and the new blocks') and every answered sentence left out, with its reason. The walk
    of `apply_repairs` grows all three."""

    dropped: list[DroppedText]
    taken: set[str]
    blocks: list[Block] = field(default_factory=list)

    def new_id(self, base: str) -> str:
        return child_id(base, self.taken)

    def last_id(self) -> str:
        """The id a sentence without a block goes under: the last block's (so the next
        one chains under it, `b012.1`, `b012.1.1`), `b000` while there is none."""
        return self.blocks[-1].id if self.blocks else "b000"


def _append_additions(
    anchor_id: str | None, adds: list[AdditionItem], given: _Given, new: _NewVersion
) -> None:
    """The additions after one block as blocks at the end of the version so far, one per
    sentence, numbered under the block (`b005.1`, `b005.2`, ...). An addition the draft
    conveys or that lacks the value asked for stays out whole (`_left_out`); a sentence
    the draft keeps elsewhere, one placed already, or one that restates a block near its
    place (`_restates`) is a repeat; what stays out goes to `new.dropped` with its
    reason. Without a block (None: the answer named none of the draft's) the sentences
    go at the end, each numbered under the block before it, so a batch chains:
    `b012.1`, then `b012.1.1` (`b000.1` in an empty draft)."""
    for add in adds:
        if reason := _left_out(add, given):
            new.dropped.extend(
                DroppedText(text=t, reason=reason, block_id=anchor_id, fact_ids=add.fact_ids)
                for t in add.texts
            )
            continue
        for text in add.texts:
            if (
                wording_key(text) in given.kept
                or any(wording_key(text) == wording_key(x.text) for x in new.blocks)
                or _restates(text, anchor_id, add, given)
            ):
                new.dropped.append(
                    DroppedText(
                        text=text, reason="repeat", block_id=anchor_id, fact_ids=add.fact_ids
                    )
                )
                continue
            base = anchor_id if anchor_id is not None else new.last_id()
            new.blocks.append(
                Block(
                    id=new.new_id(base),
                    kind=add.kind,
                    text=text,
                    fact_ids=_known_ids(add, given),
                    segment_ids=add.segment_ids,
                )
            )


def _append_repair(b: Block, texts: list[str], kept: set[str], new: _NewVersion) -> None:
    """The repaired block replaced by its texts, one block per sentence: the first keeps
    the id, the others get `b005.1`, `b005.2`. A text that ends another text of the same
    answer goes (the 70B wrote a sentence and then its tail once more, 31 October 2026);
    so does one the draft has elsewhere (`kept`, the draft's wording only, not the blocks
    placed so far). What goes is dropped as a repeat. An answer with nothing else leaves
    the block as it was: the answer is the repeat, not the block it repeats (the answer
    used to take the block's place, and `drop_repeats` then removed the later of the two,
    an unflagged block with its heading included; audit of 6 November 2026)."""
    keys = [wording_key(t) for t in texts]
    parts = [
        t for i, t in enumerate(texts) if any(k != keys[i] and k.endswith(keys[i]) for k in keys)
    ]
    new.dropped += [DroppedText(text=t, reason="repeat", block_id=b.id) for t in parts]
    texts = [t for t in texts if t not in parts] or texts[:1]
    fresh = [t for t in texts if wording_key(t) not in kept]
    new.dropped += [
        DroppedText(text=t, reason="repeat", block_id=b.id) for t in texts if t not in fresh
    ]
    if not fresh:
        new.blocks.append(b)
        return
    for i, text in enumerate(fresh):
        block_id = b.id if i == 0 else new.new_id(b.id)
        new.blocks.append(b.model_copy(update={"id": block_id, "text": text}))


def _without_late_repeats(new: _NewVersion) -> list[Block]:
    """An addition can land before the repaired block it repeats: the repeat goes
    (`drop_repeats`, ids kept), to `new.dropped` with its block; a heading left without
    content goes with it but is no sentence to record."""
    final_blocks = drop_repeats(new.blocks, renumber=False)
    if len(final_blocks) != len(new.blocks):
        left = {b.id for b in final_blocks}
        new.dropped += [
            DroppedText(text=b.text, reason="repeat", block_id=b.id, fact_ids=b.fact_ids)
            for b in new.blocks
            if b.id not in left and b.kind != "heading"
        ]
    return final_blocks


def apply_repairs(
    draft: Draft,
    out: RepairOut,
    request: RepairRequest,
    factsheet: FactSheet,
    dropped: list[DroppedText] | None = None,
    version: int | None = None,
) -> Draft:
    """The new version: repaired blocks replaced (split into several when the answer
    has several texts), additions placed after their blocks. `dropped`, when given,
    collects every answered sentence code leaves out, with its reason."""
    dropped = [] if dropped is None else dropped
    repairs, additions = _answer_by_block(draft, out, request, dropped)
    given = _Given.of(draft, request, factsheet, repaired=set(repairs))
    new = _NewVersion(dropped, taken=set(draft.by_id()))
    # Sentences added after a list item go after the list, not between its items
    # (10 October 2026: the example letters' lists of enclosures were split by them). A
    # sentence a recover round placed after an item (`b005.1`) is part of the list, as
    # `list_end` counts it (`in_list`; the additions flushed at the first block that was
    # no item landed inside the list, audit of 6 November 2026).
    pending: list[tuple[str, list[AdditionItem]]] = []
    by_id = draft.by_id()
    for b in draft.blocks:
        listed = in_list(b, by_id)
        if pending and not listed:
            for anchor_id, adds in pending:
                _append_additions(anchor_id, adds, given, new)
            pending.clear()
        texts = repairs.get(b.id)
        if texts:
            _append_repair(b, texts, given.kept, new)
        else:
            new.blocks.append(b)
        adds = additions.get(b.id, [])
        if adds and listed:
            pending.append((b.id, adds))
        elif adds:
            _append_additions(b.id, adds, given, new)
    for anchor_id, adds in pending:  # a list at the end of the draft
        _append_additions(anchor_id, adds, given, new)
    _append_additions(None, additions.get(None, []), given, new)  # after no block of the draft
    return draft.model_copy(
        update={
            "blocks": _without_late_repeats(new),
            "version": version if version is not None else draft.version + 1,
            "parent_version": draft.version,
            "origin": "repair",
            "code_edits": [],  # each version records the edits made on it
        }
    )


def without_texts(out: RepairOut, texts: Collection[str]) -> RepairOut:
    """The answer without these texts, as a copy: a repair or an addition that keeps no
    text goes whole."""
    if not texts:
        return out
    repairs = [
        item.model_copy(update={"texts": kept})
        for item in out.repairs
        if (kept := [t for t in item.texts if t not in texts])
    ]
    additions = [
        add.model_copy(update={"texts": kept})
        for add in out.additions
        if (kept := [t for t in add.texts if t not in texts])
    ]
    return out.model_copy(update={"repairs": repairs, "additions": additions})


def repair_version(
    draft: Draft,
    out: RepairOut,
    request: RepairRequest,
    factsheet: FactSheet,
    *,
    topical: Collection[str] = (),
    kind: str = "repair",
    version: int | None = None,
) -> tuple[Draft, RepairRecord]:
    """One round's new version and its record: what was asked, what the model answered
    and what code left out. The answer's sentences about the prompt's own examples
    (`topical`, checks.drop_topical) are left out as `example` before the rest is placed
    (`apply_repairs`). `version`: the new version's number, when it is not the next
    after `draft` (the vocabulary round starts from the best version, not the latest)."""
    version = version if version is not None else draft.version + 1
    record = RepairRecord(
        draft_version=version,
        parent_version=draft.version,
        kind=kind,
        requested_blocks=list(request.problems),
        requested_facts=[f.id for f in request.missing],
        repairs=[AnsweredRepair(block_id=i.id, texts=list(i.texts)) for i in out.repairs],
        additions=[
            AnsweredAddition(
                after=a.after,
                kind=a.kind,
                texts=list(a.texts),
                fact_ids=list(a.fact_ids),
                segment_ids=list(a.segment_ids),
            )
            for a in out.additions
        ],
    )
    for item in out.repairs:
        record.dropped += [
            DroppedText(text=t, reason="example", block_id=item.id)
            for t in item.texts
            if t in topical
        ]
    for add in out.additions:
        record.dropped += [
            DroppedText(text=t, reason="example", block_id=add.after, fact_ids=add.fact_ids)
            for t in add.texts
            if t in topical
        ]
    new_draft = apply_repairs(
        draft,
        without_texts(out, topical),
        request,
        factsheet,
        dropped=record.dropped,
        version=version,
    )
    return new_draft, record


# -- the recover round's sentences ---------------------------------------------------------


def fact_window(draft: Draft, source: SourceDocument, segment_ids: set[str]) -> list[Block]:
    """The blocks at the place a fact belongs: those built from its paragraph with one
    block before and after; without such a block, the two around the paragraph's place
    in the source order; none in a draft without blocks."""
    order = {s.id: i for i, s in enumerate(source.segments)}
    blocks = draft.blocks
    if not blocks:
        return []
    hits = [i for i, b in enumerate(blocks) if segment_ids & set(b.segment_ids)]
    if not hits:
        start = min((order[s] for s in segment_ids if s in order), default=0)
        before = [
            i for i, b in enumerate(blocks)
            if any(order.get(s, len(order)) <= start for s in b.segment_ids)
        ]  # fmt: skip
        hits = [before[-1]] if before else [0]
    lo, hi = max(min(hits) - 1, 0), min(max(hits) + 1, len(blocks) - 1)
    return blocks[lo : hi + 1]


def target_block(
    draft: Draft, window: list[Block], after: str | None, segment_ids: set[str]
) -> str | None:
    """The block the sentences go after: the answer's block, or the block built from the
    source sentence it names (the 8B answered `"after": "s0005"`, 9 October 2026), else
    the window's last block from the paragraph. A heading passes to the next block.
    None in a draft without blocks."""
    blocks = draft.blocks
    ids = [b.id for b in blocks]
    if not ids:
        return None
    chosen = None
    if after in ids:
        chosen = after
    elif after:
        carrying = [b.id for b in window if after in b.segment_ids]
        carrying = carrying or [b.id for b in blocks if after in b.segment_ids]
        chosen = carrying[-1] if carrying else None
    if chosen is None:
        from_para = [b.id for b in window if segment_ids & set(b.segment_ids)]
        chosen = (from_para or [window[-1].id if window else ids[-1]])[-1]
    i = ids.index(chosen)
    while blocks[i].kind == "heading" and i + 1 < len(blocks):
        i += 1
    return ids[i]


def add_sentences(draft: Draft, block_id: str, texts: list[str], fact: Fact) -> Draft:
    """The draft with the sentences of a recovered fact as new blocks after `block_id`
    (`b009.1`, `b009.2`, ...), each carrying the fact. They go after the blocks that
    follow it under its id, so a second fact for the same block comes after the first,
    and after the whole list when the block is a list item (10 October 2026)."""
    taken = {b.id for b in draft.blocks}
    blocks = list(draft.blocks)
    at = next((i for i, b in enumerate(blocks) if b.id == block_id), None)
    if at is None:
        return draft
    anchor = blocks[at]
    at += 1
    while at < len(blocks) and blocks[at].id.startswith(f"{block_id}."):
        at += 1
    if anchor.kind == "list_item":
        at = list_end(blocks, at)
    blocks[at:at] = [
        Block(id=child_id(block_id, taken), kind="sentence", text=t, fact_ids=[fact.id],
              segment_ids=list(fact.segment_ids))
        for t in texts
    ]  # fmt: skip
    return draft.model_copy(update={"blocks": blocks})
