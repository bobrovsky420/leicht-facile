"""Language-independent rules: facts, layout of headings, readability, and the ids of
the rules the judge decides (docs/rules.md, "Facts", "Layout", "Readability",
"Delegated to the judge")."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field

from leichtfacile.rules.base import Context, Hit, declare, rule, sev
from leichtfacile.rules.values import (
    HARD_KINDS,
    Value,
    extract_values,
    format_date,
    format_phone,
    format_thousands,
    matches,
    parse_value_norm,
)
from leichtfacile.schemas import Draft, Fact, FactSheet, SourceDocument


@dataclass
class DocInput:
    draft: Draft
    source: SourceDocument | None = None
    factsheet: FactSheet | None = None
    sentences: list[str] = field(default_factory=list)  # sentences of non-heading blocks


# -- facts ---------------------------------------------------------------------------


# How amounts, percentages and times are written, per language (the NUM rules).
_UNITS = {
    "de": {"amount": "{} Franken", "percent": "{} Prozent"},
    "fr": {"amount": "{} francs", "percent": "{} pour cent"},
    "it": {"amount": "{} franchi", "percent": "{} per cento"},
}


def display_value(value: Value, lang: str) -> str:
    """A value as the draft should write it: 4. Februar 2026, 4 février 2026."""
    units = _UNITS.get(lang, _UNITS["de"])
    if value.kind == "date":
        return format_date(value.canonical, lang)
    if value.kind == "amount":
        return units["amount"].format(format_thousands(value.canonical, lang))
    if value.kind == "percent":
        return units["percent"].format(value.canonical)
    if value.kind == "time":
        hour, minute = value.canonical.split(":")
        if lang == "fr":
            return f"{int(hour)} h {minute}"
        return f"ore {int(hour)}.{minute}" if lang == "it" else f"{int(hour)}.{minute} Uhr"
    if value.kind == "phone":
        return format_phone(value.canonical)
    return value.canonical


@dataclass(frozen=True)
class FactCoverage:
    checkable: list[Fact]
    found: dict[str, list[str]]  # fact id -> ids of the blocks that contain the value
    missing: list[Fact]

    @property
    def ratio(self) -> float | None:
        return len(self.found) / len(self.checkable) if self.checkable else None


def fact_coverage(draft: Draft, factsheet: FactSheet, lang: str) -> FactCoverage:
    """FACT-01: which must-keep facts with a normalised value appear in the draft."""
    values_by_block = {b.id: extract_values(b.text, lang) for b in draft.blocks}
    checkable, missing = [], []
    found: dict[str, list[str]] = {}
    for fact in factsheet.must_keep():
        target = parse_value_norm(fact.value_norm, fact.kind, lang)
        if target is None:
            continue
        checkable.append(fact)
        blocks = [
            bid
            for bid, values in values_by_block.items()
            if any(matches(target, v) for v in values)
        ]
        if blocks:
            found[fact.id] = blocks
        else:
            missing.append(fact)
    return FactCoverage(checkable, found, missing)


@rule(
    "FACT-01",
    lang=None,
    title="Every must_keep fact with a normalised value appears in the draft",
    severity=sev("error"),
    scope="document",
)
def fact_01(doc: DocInput, ctx: Context) -> Iterator[Hit]:
    if not doc.factsheet:
        return
    coverage = fact_coverage(doc.draft, doc.factsheet, ctx.lang)
    for fact in coverage.missing:
        target = parse_value_norm(fact.value_norm, fact.kind, ctx.lang)
        expected = display_value(target, ctx.lang) if target else fact.value_norm
        yield Hit(
            f"Fact {fact.id} is missing or changed: {fact.text} (expected {expected}).",
            evidence=fact.text,
            fact_id=fact.id,
        )


@rule(
    "FACT-02",
    lang=None,
    title="Every must_keep fact is referenced by at least one block",
    severity=sev("error"),
    scope="document",
)
def fact_02(doc: DocInput, ctx: Context) -> Iterator[Hit]:
    if not doc.factsheet:
        return
    referenced = {fid for b in doc.draft.blocks for fid in b.fact_ids}
    for fact in doc.factsheet.must_keep():
        if fact.id not in referenced:
            yield Hit(
                f"No block conveys fact {fact.id}: {fact.text}",
                evidence=fact.text,
                fact_id=fact.id,
            )


@rule(
    "FACT-03",
    lang=None,
    title="No block without provenance",
    severity=sev("error"),
    scope="document",
)
def fact_03(doc: DocInput, ctx: Context) -> Iterator[Hit]:
    if not doc.source:
        return
    known = doc.source.segment_ids()
    for block in doc.draft.blocks:
        if block.kind == "heading":
            continue
        valid = [s for s in block.segment_ids if s in known]
        if not valid:
            unknown = [s for s in block.segment_ids if s not in known]
            detail = f" (unknown ids: {', '.join(unknown)})" if unknown else ""
            yield Hit(
                f"The block names no source sentence{detail}.",
                evidence=block.text,
                block_id=block.id,
            )


@rule(
    "FACT-04",
    lang=None,
    title="Omissions are explained",
    severity=sev("warn"),
    scope="document",
)
def fact_04(doc: DocInput, ctx: Context) -> Iterator[Hit]:
    if not doc.source:
        return
    used = {s for b in doc.draft.blocks for s in b.segment_ids}
    explained = {s for o in doc.draft.omissions for s in o.segment_ids}
    if doc.factsheet:
        explained |= {s for o in doc.factsheet.omit_candidates for s in o.segment_ids}
    run: list[str] = []
    runs: list[list[str]] = []
    for seg in doc.source.segments:
        if seg.kind != "heading" and seg.id not in used and seg.id not in explained:
            run.append(seg.id)
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    by_id = doc.source.by_id()
    for ids in runs:
        first = by_id[ids[0]].text
        label = ids[0] if len(ids) == 1 else f"{ids[0]} to {ids[-1]}"
        yield Hit(
            f"Source sentences {label} are neither used nor listed as omitted.",
            evidence=first[:160],
            segment_ids=tuple(ids),
        )


@rule(
    "FACT-05",
    lang=None,
    title="Fact sheet values appear in the source",
    severity=sev("warn"),
    scope="factsheet",
)
def fact_05(doc: DocInput, ctx: Context) -> Iterator[Hit]:
    if not (doc.factsheet and doc.source):
        return
    by_id = doc.source.by_id()
    all_values = extract_values(doc.source.text(), ctx.lang)
    for fact in doc.factsheet.facts:
        unknown = [s for s in fact.segment_ids if s not in by_id]
        if unknown:
            yield Hit(
                f"Fact {fact.id} cites unknown source sentences: {', '.join(unknown)}.",
                evidence=fact.text,
                fact_id=fact.id,
            )
        target = parse_value_norm(fact.value_norm, fact.kind, ctx.lang)
        if target is None:
            continue
        cited = " ".join(by_id[s].text for s in fact.segment_ids if s in by_id)
        in_cited = any(matches(target, v) for v in extract_values(cited, ctx.lang))
        if in_cited:
            continue
        if any(matches(target, v) for v in all_values):
            message = (
                f"Fact {fact.id}: the value {fact.value_norm} is in the source, "
                "but not in the cited sentences."
            )
        else:
            message = (
                f"Fact {fact.id}: the value {fact.value_norm} is not in the source. "
                "The fact sheet may be wrong."
            )
        yield Hit(message, evidence=fact.text, fact_id=fact.id)


# -- values the source does not contain (FACT-06) ------------------------------------

KIND_LABELS = {
    "date": "date",
    "amount": "amount",
    "phone": "phone number",
    "email": "e-mail address",
    "url": "web address",
    "percent": "percentage",
    "time": "time",
}
# Kinds for which the source's only value is suggested in place of a foreign one: a
# document with one phone number means that one. The only date or amount in a
# document (a law's date, a fee) would turn an invented sentence into a wrong one.
SUGGESTED_KINDS = ("phone", "email", "url")


@dataclass(frozen=True)
class ForeignValue:
    """A hard value of the draft that the source does not contain."""

    block_id: str
    value: Value
    suggestion: str | None = None  # the source's only contact of that kind, if it has one


def _supported(value: Value, source_values: list[Value], fact_values: list[Value]) -> bool:
    if any(matches(value, v) for v in source_values) or any(matches(value, v) for v in fact_values):
        return True
    if value.kind == "url":
        # A shortened address that leads to the right site: zh.ch for www.zh.ch/soziales.
        prefix = value.canonical + "/"
        return any(v.kind == "url" and v.canonical.startswith(prefix) for v in source_values)
    if value.kind == "time" and value.canonical.endswith(":00"):
        # "8 Uhr bis 12 Uhr" for a source that says "8-12 Uhr": there the first hour is
        # a plain number.
        hour = str(int(value.canonical[:2]))
        return any(v.kind == "number" and v.canonical == hour for v in source_values)
    return False


def foreign_values(
    draft: Draft, source: SourceDocument, factsheet: FactSheet | None, lang: str
) -> list[ForeignValue]:
    """FACT-06: the dates, amounts, phone numbers, e-mail and web addresses, percentages
    and times in the draft that neither the source nor the fact sheet contains, in
    draft order. Plain numbers are not checked: "zwei Wochen" may become "14 Tage".

    The fact sheet's normalised values count as supported so that FACT-01 (the value
    must be there) and FACT-06 cannot contradict each other; a fact-sheet value that is
    not in the source is FACT-05's finding."""
    source_text = "\n".join(t for t in (source.title, source.text()) if t)
    source_values = extract_values(source_text, lang)
    fact_values: list[Value] = []
    if factsheet:
        for fact in factsheet.facts:
            target = parse_value_norm(fact.value_norm, fact.kind, lang)
            if target is not None:
                fact_values.append(target)
    candidates: dict[str, set[str]] = defaultdict(set)  # kind -> canonical source values
    for v in source_values:
        if v.kind in HARD_KINDS:
            candidates[v.kind].add(v.canonical)
    out: list[ForeignValue] = []
    for block in draft.blocks:
        for value in extract_values(block.text, lang):
            if value.kind not in HARD_KINDS or _supported(value, source_values, fact_values):
                continue
            suggestion = None
            if value.kind in SUGGESTED_KINDS and len(candidates[value.kind]) == 1:
                (only,) = candidates[value.kind]
                suggestion = display_value(Value(value.kind, only), lang)
            out.append(ForeignValue(block.id, value, suggestion))
    return out


@rule(
    "FACT-06",
    lang=None,
    title="Every value in the draft appears in the source",
    severity=sev("error"),
    scope="document",
)
def fact_06(doc: DocInput, ctx: Context) -> Iterator[Hit]:
    if not doc.source:
        return
    for item in foreign_values(doc.draft, doc.source, doc.factsheet, ctx.lang):
        label = KIND_LABELS[item.value.kind]
        yield Hit(
            f"The {label} {item.value.text} is not in the source. "
            "Remove it or take the value from the source.",
            evidence=item.value.text,
            suggestion=item.suggestion,
            block_id=item.block_id,
        )


# -- layout and readability -----------------------------------------------------------


@rule(
    "LAY-03",
    lang=None,
    title="Headings carry the reader's questions",
    severity=sev("info"),
    scope="document",
)
def lay_03(doc: DocInput, ctx: Context) -> Iterator[Hit]:
    blocks = doc.draft.blocks
    headings = [b for b in blocks if b.kind == "heading"]
    if len(blocks) > 6 and len(headings) < len(blocks) / 8:
        noun = "heading" if len(headings) == 1 else "headings"
        yield Hit(
            f"{len(headings)} {noun} for {len(blocks)} blocks: add headings, "
            "ideally as the reader's questions.",
        )
    for b in headings:
        n = len(b.text.split())
        if n > ctx.params.max_heading_words:
            yield Hit(
                f"Heading with {n} words; at most {ctx.params.max_heading_words}.",
                evidence=b.text,
                block_id=b.id,
            )


FORMULAS = {"de": "Amstad", "fr": "Kandel-Moles", "it": "Gulpease"}


@rule(
    "READ-01",
    lang=None,
    title="Readability index at or above the target for the level",
    severity=sev("info"),
    scope="document",
)
def read_01(doc: DocInput, ctx: Context) -> Iterator[Hit]:
    from leichtfacile.rules.readability import readability

    result = readability(doc.sentences, ctx.lang)
    if result.score is None:
        return
    name = FORMULAS.get(ctx.lang, result.formula)
    if ctx.lang == "de" and result.score < ctx.params.readability_target:
        yield Hit(
            f"{name} readability {result.score:.0f} is below the target "
            f"{ctx.params.readability_target:.0f} for {ctx.level}.",
            severity="warn",
        )
    else:
        yield Hit(f"{name} readability {result.score:.0f}.")


declare(
    "READ-02",
    lang=None,
    title="Average and maximum sentence length",
    severity=sev("info"),
    scope="document",
)
declare(
    "READ-03",
    lang=None,
    title="Share of sentences with passive, genitive, subordinate clause",
    severity=sev("info"),
    scope="document",
)

# -- rules the judge decides --------------------------------------------------------

JUDGE_RULES = {
    "SEM-01": "Metaphor, idiom or figurative expression",
    "SEM-02": "Abstract noun where a concrete action or person would do",
    "SEM-03": "Pronoun or demonstrative with an unclear reference",
    "SEM-04": "Assumes knowledge the reader may not have",
    "SEM-05": "Difficult word without an explanation",
    "SEM-06": "Statement the source does not support",
    "SEM-07": "Fact present, missing or distorted",
}
for _rule_id, _title in JUDGE_RULES.items():
    declare(_rule_id, lang=None, title=_title, severity=sev("warn"), scope="judge")
