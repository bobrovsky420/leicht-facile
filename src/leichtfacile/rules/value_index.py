"""The values of a document's parts, extracted once (`ValueIndex`): the source's
segments or a draft's blocks, each value with the parts that hold it. The fact rules,
the document metrics, the code completion of the fact sheet and the linking of facts to
blocks read the index instead of extracting the same texts again; the checker used to
extract each block's values four times and the source's seven times per check.

A source is read as one text (`SourceDocument.text_with_offsets`), so an address over two
sentences is one value, traced to the segments it spans; the title's values belong to no
segment. A draft is read block by block: a block is one text, and a value never spans
two blocks.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from leichtfacile.rules.values import HARD_KINDS, Value, extract_values, find_medication, matches
from leichtfacile.schemas import Block, SourceDocument


@dataclass(frozen=True)
class ValueIndex:
    lang: str
    values: tuple[Value, ...]  # every value, the title's first, then in text order
    holders: tuple[tuple[str, ...], ...]  # per value, the ids of the parts it spans
    texts: dict[str, str]  # part id -> its text, where a medication's name is searched
    text: str  # the whole text, title included

    @classmethod
    def of_source(cls, source: SourceDocument, lang: str | None = None) -> ValueIndex:
        """The source's values in its variety (or `lang`): the title's, then the text's,
        each with the segments it spans."""
        lang = lang or source.variety
        text, spans = source.text_with_offsets()
        values: list[Value] = []
        holders: list[tuple[str, ...]] = []
        if source.title:
            for value in extract_values(source.title, lang):
                values.append(value)
                holders.append(())
        for value in extract_values(text, lang):
            values.append(value)
            holders.append(
                tuple(
                    seg.id
                    for seg, (start, end) in zip(source.segments, spans, strict=True)
                    if start < value.end and value.start < end
                )
            )
        full = "\n".join(part for part in (source.title, text) if part)
        return cls(
            lang, tuple(values), tuple(holders), {s.id: s.text for s in source.segments}, full
        )

    @classmethod
    def of_blocks(cls, blocks: Iterable[Block], lang: str) -> ValueIndex:
        """A draft's values, block by block."""
        blocks = list(blocks)
        values: list[Value] = []
        holders: list[tuple[str, ...]] = []
        for block in blocks:
            for value in extract_values(block.text, lang):
                values.append(value)
                holders.append((block.id,))
        texts = {b.id: b.text for b in blocks}
        return cls(lang, tuple(values), tuple(holders), texts, "\n".join(texts.values()))

    def of_part(self, part_id: str) -> list[Value]:
        """The values that stand in one part (a segment or a block), wholly or in part."""
        return [v for v, held in zip(self.values, self.holders, strict=True) if part_id in held]

    def hard(self) -> list[Value]:
        return [v for v in self.values if v.kind in HARD_KINDS]

    def contains(self, target: Value) -> bool:
        """Whether the text carries the fact's value anywhere (`values.contains`)."""
        if target.kind == "medication":
            return bool(find_medication(target, self.text))
        return any(matches(target, v) for v in self.values)

    def part_contains(self, target: Value, part_id: str) -> bool:
        """Whether one part carries the fact's value, as `values.contains` reads the
        part's text alone."""
        if target.kind == "medication":
            return bool(find_medication(target, self.texts.get(part_id, "")))
        return any(matches(target, v) for v in self.of_part(part_id))

    def holders_of(self, target: Value) -> list[str]:
        """The parts that carry the fact's value, in text order, each once."""
        if target.kind == "medication":
            return [pid for pid, text in self.texts.items() if find_medication(target, text)]
        found: dict[str, None] = {}
        for value, held in zip(self.values, self.holders, strict=True):
            if matches(target, value):
                found.update(dict.fromkeys(held))
        return list(found)
