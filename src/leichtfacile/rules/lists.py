"""Lists of the source stay whole: every item of a list in the source becomes a fact
the draft must carry, and the check FACT-10 fires when an item is cited by no block or
listed as omitted (docs/use-cases.md section 8).

A letter's list enumerates what the reader must know or bring: the documents to
enclose, the conditions, the packing list of a school camp. The 70B kept 2 of 7 items
of the camp letter's packing list in German and none in French (the school letters,
31 October 2026): an item carries no value, so neither FACT-01 nor the judge's fact
checks missed it. As the decision mode does for the operative part (rules/decision.py,
FACT-08), code adds one fact without a value per item after the fact sheet is
completed (`protect_lists`), so that the writer sees the items among the facts it must
keep, a block that cites the item carries the fact (`stages.link_facts`), and a dropped
item is asked for in a repair round like a missing value (rounds.MISSING_RULES).

An item that a code fact already cites (an item that is a value, such as the pocket
money's amount, or an item of a decision's operative part) gets no second fact; an item
in a passage the model marked as droppable is a background fact and not checked; a
list of more than MAX_ITEMS items is an enumeration the easy text cannot carry and is
left to the writer. An item that ends in a colon introduces the items after it, an
item that is a question is a teaser or a table of contents (the cover of the German
pension brochure), and an item that repeats a heading or an earlier line of the source
(a table of contents, an income table printed twice) tells nothing of its own; none
becomes a fact (the Public AI regression run of 31 October 2026, where they were 5 of
the 58 items the final drafts lacked). The 70B also carries an item under the id of
its neighbour (the label "Telefon" cited as the number's line, a group of recipients
cited as the group before it), and a repair round that adds the item again only
repeats the draft, so an item also counts as kept when a block that cites the same
list, or the line before it, contains the item's words (`_carried`).
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from leichtfacile.ingest.detect import STOPWORDS
from leichtfacile.rules.base import Context, Hit, rule, sev
from leichtfacile.rules.document import DocInput
from leichtfacile.rules.lexicon import MEDIOPUNKT
from leichtfacile.rules.messages import hit
from leichtfacile.schemas import Block, Fact, FactSheet, Segment, SourceDocument

MAX_ITEMS = 20
_WORD_RE = re.compile(r"[^\W\d_]{4,}")  # content words, as stages._stems reads them
_STEM_LETTERS = 5


def source_lists(source: SourceDocument) -> list[list[Segment]]:
    """The lists of the source: runs of consecutive list items."""
    lists: list[list[Segment]] = []
    for seg in source.segments:
        if seg.kind == "list_item":
            if lists and lists[-1][-1].id == _previous_id(seg.id):
                lists[-1].append(seg)
            else:
                lists.append([seg])
    return lists


def _previous_id(segment_id: str) -> str:
    """The id of the segment before this one (`s0021` for `s0022`)."""
    return f"s{int(segment_id[1:]) - 1:04d}" if segment_id[1:].isdigit() else ""


def _key(text: str) -> str:
    """A line's text for the comparison with another line: the words, lower case."""
    return " ".join(re.findall(r"\w+", text.casefold()))


def _stems(text: str, lang: str) -> set[str]:
    """The stems of a text's content words (words of four letters or more that are
    no function words, by their first five letters, like `stages._stems`)."""
    stop = STOPWORDS.get(lang, frozenset())
    words = _WORD_RE.findall(text.lower().replace(MEDIOPUNKT, ""))
    return {w[:_STEM_LETTERS] for w in words if w not in stop}


def _carried(item: str, blocks: list[Block], lang: str) -> bool:
    """Whether one of the blocks contains the item's words: all of them for an item
    of up to three content words, three of them for a longer item."""
    stems = _stems(item, lang)
    need = min(len(stems), 3)
    return bool(stems) and any(len(stems & _stems(b.text, lang)) >= need for b in blocks)


def list_facts(factsheet: FactSheet) -> list[Fact]:
    """The facts `protect_lists` added: code's, without a value, one segment each,
    marked by their kind."""
    return [
        f
        for f in factsheet.facts
        if f.origin == "code" and not f.value_norm and f.kind == "other" and f.text.startswith("- ")
    ]


def protect_lists(fs: FactSheet, source: SourceDocument) -> FactSheet:
    """The fact sheet after the code completion (and, for a decision, after
    `protect_factsheet`): one fact without a value per item of every list of the source
    that no code fact cites yet, must-keep unless the item lies in a passage the model
    marked as droppable. The text is the item behind a dash, which tells the writer it
    is a list item and `list_facts` what it is."""
    cited = {s for f in fs.facts if f.origin == "code" for s in f.segment_ids}
    omitted = {s for o in fs.omit_candidates for s in o.segment_ids}
    headings = {_key(s.text) for s in source.segments if s.kind == "heading"}
    first_line = {}  # a line's words -> the id of the first segment that says them
    for s in source.segments:
        first_line.setdefault(_key(s.text), s.id)
    facts = list(fs.facts)
    next_id = 1 + max((int(f.id[1:]) for f in facts if f.id[1:].isdigit()), default=0)
    for items in source_lists(source):
        if len(items) > MAX_ITEMS:
            continue
        for item in items:
            text = item.text.strip()
            if item.id in cited or not text or text[-1] in ":?":
                continue
            if _key(text) in headings or first_line[_key(text)] != item.id:
                continue
            text = "- " + " ".join(item.text.split())
            facts.append(
                Fact(
                    id=f"f{next_id:02d}",
                    kind="other",
                    text=text if len(text) <= 200 else text[:197] + "...",
                    segment_ids=[item.id],
                    must_keep=item.id not in omitted,
                    origin="code",
                )
            )
            next_id += 1
    return fs.model_copy(update={"facts": facts}) if len(facts) > len(fs.facts) else fs


@rule(
    "FACT-10",
    lang=None,
    title="Every item of a list in the source is kept",
    severity=sev("error"),
    scope="document",
)
def fact_10(doc: DocInput, ctx: Context) -> Iterator[Hit]:
    """Every must-keep list item (a fact of `protect_lists`) is cited by some block, or
    worded by a block that cites the same list or the line before it (`_carried`), and
    listed by no omission. The hit carries the fact id, so a repair round asks for the
    item like a missing value."""
    if doc.factsheet is None:
        return
    cited = {s for b in doc.draft.blocks for s in b.segment_ids}
    omitted = {s for o in doc.draft.omissions for s in o.segment_ids}
    neighbours: dict[str, set[str]] = {}  # an item's id -> the ids of its list and intro
    if doc.source is not None:
        for items in source_lists(doc.source):
            ids = {s.id for s in items} | {_previous_id(items[0].id)}
            neighbours.update(dict.fromkeys(ids, ids))
    for fact in list_facts(doc.factsheet):
        if not fact.must_keep:
            continue
        ids = set(fact.segment_ids)
        text = fact.text[2:]
        near = neighbours.get(fact.segment_ids[0], set())
        wording = [b for b in doc.draft.blocks if near & set(b.segment_ids)]
        if ids & omitted:
            yield hit(
                "FACT-10.omitted",
                text=text[:120],
                evidence=text,
                fact_id=fact.id,
                segment_ids=tuple(fact.segment_ids),
            )
        elif not ids & cited and not _carried(text, wording, ctx.lang):
            yield hit(
                "FACT-10",
                text=text[:120],
                evidence=text,
                fact_id=fact.id,
                segment_ids=tuple(fact.segment_ids),
            )
