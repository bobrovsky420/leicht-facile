"""Patient letters (docs/use-cases.md §3): a medication stays in one block with its
dose, scheme and duration (FACT-09), so a reader cannot pair a dose with the wrong drug.

The fact sheet names the medications (facts of kind `medication`, the name as the
value; rules/values.py). Code finds what belongs to each name in the source: the
doses (`500 mg`, `2 Tabletten`), the dosing schemes (`1-0-1`) and the durations
(`während 5 Tagen`, `7 Tage`) in the source sentence that names it. With several
names in one sentence, a value belongs to the nearest name (`2 Tabletten Dafalgan
500 mg 1-0-1 und 1 Tablette Ponstan 0-0-1`). A measurement (`über 38,5 Grad`) is no
dose, and a period after `nach`, `in`, `ab`, `bis`, ... is a point in time, an age or
a condition (`nach 3 Tagen`, `ab 12 Jahren`), not how long the drug is taken. A period
in years is mostly an age and is left out too.

A table whose cells hold the name and the dose apart is not checked: the source keeps
no rows, only cells.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from leichtfacile.rules.base import Context, Hit, rule, sev
from leichtfacile.rules.document import DocInput, display_value
from leichtfacile.rules.messages import hit
from leichtfacile.rules.values import (
    DOSE_UNITS,
    Value,
    contains,
    extract_values,
    find_medication,
    parse_value_norm,
)
from leichtfacile.schemas import Block, FactSheet, SourceDocument

# A period after one of these words is a point in time, an age or a condition, not a
# duration: "nach 3 Tagen", "innert 30 Tagen", "ab 12 Jahren", "dans 2 semaines". A
# frequency ("alle 2 Tage", "tous les 2 jours") is part of the scheme and stays.
_NOT_A_DURATION = re.compile(
    r"\b(?:nach|in|innert|innerhalb|binnen|vor|seit|ab|bis|von|unter|über|spätestens"
    r"|après|dans|dès|depuis|avant|sous|jusqu'à|d'ici|dopo|tra|fra|entro|da)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MedicationValues:
    """The doses, schemes and durations of one medication in one source sentence."""

    fact_id: str
    name: Value  # the medication fact's value: the name
    segment_id: str
    values: tuple[Value, ...]


def _belongs(value: Value, text: str) -> bool:
    if value.kind == "schedule":
        return True
    if value.kind == "quantity":
        return value.canonical.split(" ", 1)[1] in DOSE_UNITS
    if value.kind == "period":
        if value.canonical.endswith(("y", "wd")):
            return False  # an age (`ab 12 Jahren`), not a course of a drug
        return not _NOT_A_DURATION.search(text[: value.start])
    return False


def has_doses(source: SourceDocument) -> bool:
    """Whether the source gives a dose or a dosing scheme. Then the understand prompt
    asks for the medications (the partial `medication.md`); a document without one gets
    the standard prompt, word for word."""
    return any(
        v.kind == "schedule" or (v.kind == "quantity" and _belongs(v, ""))
        for v in extract_values(source.text(), source.lang)
    )


def names_medication(factsheet: FactSheet) -> bool:
    """Whether the fact sheet names a medication the letter must keep: then the write
    prompt asks for one list item per medication."""
    return any(f.kind == "medication" for f in factsheet.must_keep())


def medication_names(factsheet: FactSheet) -> list[str]:
    """The names of the fact sheet's medications, which the Mediopunkt step leaves as
    they are (rules/mediopunkt.py)."""
    return [
        target.text
        for f in factsheet.facts
        if f.kind == "medication" and (target := parse_value_norm(f.value_norm, f.kind)) is not None
    ]


def _distance(value: Value, name: Value) -> int:
    if value.start >= name.end:
        return value.start - name.end
    if name.start >= value.end:
        return name.start - value.end
    return 0


def medication_values(
    source: SourceDocument, factsheet: FactSheet, lang: str
) -> list[MedicationValues]:
    """For every must-keep medication of the fact sheet, the source sentences that name
    it and the values that belong to it there. A sentence with no such value is left
    out: there is nothing to keep together."""
    names: list[tuple[str, Value]] = []
    for fact in factsheet.must_keep():
        target = parse_value_norm(fact.value_norm, fact.kind, lang)
        if target is None or target.kind != "medication":
            continue
        if all(target.canonical != other.canonical for _, other in names):
            names.append((fact.id, target))
    result: list[MedicationValues] = []
    if not names:
        return result
    for segment in source.segments:
        found = [
            (fact_id, place)
            for fact_id, target in names
            for place in find_medication(target, segment.text)
        ]
        if not found:
            continue
        values = [v for v in extract_values(segment.text, lang) if _belongs(v, segment.text)]
        owned: dict[str, list[Value]] = {fact_id: [] for fact_id, _ in found}
        for value in values:
            # The nearest name; on a tie the one before the value (`Dafalgan 500 mg`).
            fact_id, _ = min(
                found, key=lambda item: (_distance(value, item[1]), item[1].start > value.start)
            )
            owned[fact_id].append(value)
        for fact_id, target in names:
            if owned.get(fact_id):
                result.append(MedicationValues(fact_id, target, segment.id, tuple(owned[fact_id])))
    return result


@dataclass(frozen=True)
class Separated:
    """A medication whose values the draft writes apart from its name."""

    item: MedicationValues
    block: Block  # the block that names the medication with most of its values
    values: tuple[Value, ...]  # the values that are in the draft, but not in that block


def separated_values(
    blocks: list[Block], source: SourceDocument, factsheet: FactSheet, lang: str
) -> list[Separated]:
    """FACT-09: for each medication and source sentence, the values the draft carries
    but not in a block that names the medication. A value the draft lacks is FACT-01's
    finding (code completion makes every dose, scheme and period a fact), a name the
    draft lacks too."""
    in_block = {b.id: extract_values(b.text, lang) for b in blocks}
    out: list[Separated] = []
    for item in medication_values(source, factsheet, lang):
        naming = [b for b in blocks if find_medication(item.name, b.text)]
        if not naming:
            continue
        present = [
            v for v in item.values if any(contains(v, b.text, in_block[b.id]) for b in blocks)
        ]
        if not present:
            continue

        def carried(block: Block, present: list[Value] = present) -> list[Value]:
            return [v for v in present if contains(v, block.text, in_block[block.id])]

        best = max(naming, key=lambda b: len(carried(b)))  # the first of equals
        apart = tuple(v for v in present if v not in carried(best))
        if apart:
            out.append(Separated(item, best, apart))
    return out


@rule(
    "FACT-09",
    lang=None,
    title="A medication stays in one block with its dose, scheme and duration",
    severity=sev("error"),
    scope="document",
)
def fact_09(doc: DocInput, ctx: Context) -> Iterator[Hit]:
    if not (doc.factsheet and doc.source):
        return
    for found in separated_values(doc.draft.blocks, doc.source, doc.factsheet, ctx.lang):
        yield hit(
            "FACT-09",
            name=display_value(found.item.name, ctx.lang),
            values=", ".join(display_value(v, ctx.lang) for v in found.values),
            evidence=found.block.text,
            fact_id=found.item.fact_id,
            segment_ids=(found.item.segment_id,),
            block_id=found.block.id,
        )
