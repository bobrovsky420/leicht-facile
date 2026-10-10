"""Language-independent rules: facts, layout of headings, readability, and the ids of
the rules the judge decides (track_2b/docs/rules.md, "Facts", "Layout", "Readability",
"Delegated to the judge")."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field

from leichtfacile.rules.base import Context, Hit, declare, rule, sev
from leichtfacile.rules.messages import hit
from leichtfacile.rules.values import (
    HARD_KINDS,
    Value,
    contains,
    extract_values,
    format_address,
    format_date,
    format_identifier,
    format_period,
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
    mode: str = "standard"  # the job mode (schemas.JobMode): FACT-08 runs for decisions only


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
    if value.kind == "period":
        return format_period(value.canonical, lang)
    if value.kind == "identifier":
        return format_identifier(value.canonical)
    if value.kind == "address":
        return format_address(value.canonical)
    if value.kind == "medication":
        return value.text or value.canonical  # the name as the fact sheet writes it
    return value.canonical


@dataclass(frozen=True)
class FactCoverage:
    checkable: list[Fact]
    found: dict[str, list[str]]  # fact id -> ids of the blocks that contain the value
    missing: list[Fact]

    @property
    def ratio(self) -> float | None:
        return len(self.found) / len(self.checkable) if self.checkable else None


def source_values(source: SourceDocument, lang: str) -> list[Value]:
    """The values of a source, its title included."""
    return [v for part in (source.title, source.text()) if part for v in extract_values(part, lang)]


def full_text(source: SourceDocument) -> str:
    """The text of a source with its title, where a medication's name is searched."""
    return "\n".join(part for part in (source.title, source.text()) if part)


def fact_coverage(
    draft: Draft, factsheet: FactSheet, lang: str, source: SourceDocument | None = None
) -> FactCoverage:
    """FACT-01: which must-keep facts with a normalised value appear in the draft. With
    the source, a fact whose value the source does not contain is not checkable: the
    model computed or invented it (FACT-05 warns), and the draft may not carry it
    (FACT-06), so it cannot be required either."""
    values_by_block = {b.id: extract_values(b.text, lang) for b in draft.blocks}
    texts = {b.id: b.text for b in draft.blocks}
    in_source = source_values(source, lang) if source is not None else None
    source_text = full_text(source) if source is not None else ""
    checkable, missing = [], []
    found: dict[str, list[str]] = {}
    for fact in factsheet.must_keep():
        target = parse_value_norm(fact.value_norm, fact.kind, lang)
        if target is None:
            continue
        if in_source is not None and not contains(target, source_text, in_source):
            continue
        checkable.append(fact)
        blocks = [
            bid for bid, values in values_by_block.items() if contains(target, texts[bid], values)
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
    coverage = fact_coverage(doc.draft, doc.factsheet, ctx.lang, doc.source)
    for fact in coverage.missing:
        target = parse_value_norm(fact.value_norm, fact.kind, ctx.lang)
        expected = display_value(target, ctx.lang) if target else fact.value_norm
        yield hit(
            "FACT-01",
            fact=fact.id,
            text=fact.text,
            expected=expected,
            evidence=fact.text,
            suggestion=expected,  # the exact string: a reference number, a period
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
    # A value that is missing is FACT-01's finding: one missing fact, one error.
    missing = {f.id for f in fact_coverage(doc.draft, doc.factsheet, ctx.lang, doc.source).missing}
    for fact in doc.factsheet.must_keep():
        if fact.origin == "code" and not fact.value_norm:
            continue  # a protected part of a decision: FACT-08 checks it by its segments
        if fact.id not in referenced and fact.id not in missing:
            yield hit("FACT-02", fact=fact.id, text=fact.text, evidence=fact.text, fact_id=fact.id)


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
            if unknown:
                yield hit(
                    "FACT-03.unknown",
                    ids=", ".join(unknown),
                    evidence=block.text,
                    block_id=block.id,
                )
            else:
                yield hit("FACT-03", evidence=block.text, block_id=block.id)


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
        if len(ids) == 1:
            yield hit(
                "FACT-04.single", sentence=ids[0], evidence=first[:160], segment_ids=tuple(ids)
            )
        else:
            yield hit(
                "FACT-04",
                first=ids[0],
                last=ids[-1],
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
    all_values = source_values(doc.source, ctx.lang)
    source_text = full_text(doc.source)
    for fact in doc.factsheet.facts:
        unknown = [s for s in fact.segment_ids if s not in by_id]
        if unknown:
            yield hit(
                "FACT-05.unknown",
                fact=fact.id,
                ids=", ".join(unknown),
                evidence=fact.text,
                fact_id=fact.id,
            )
        target = parse_value_norm(fact.value_norm, fact.kind, ctx.lang)
        if target is None:
            continue
        cited = " ".join(by_id[s].text for s in fact.segment_ids if s in by_id)
        if contains(target, cited, extract_values(cited, ctx.lang)):
            continue
        yield hit(
            "FACT-05.cited" if contains(target, source_text, all_values) else "FACT-05",
            fact=fact.id,
            value=fact.value_norm,
            evidence=fact.text,
            fact_id=fact.id,
        )


# -- values the source does not contain (FACT-06) ------------------------------------

# Kinds for which the source's only value is suggested in place of a foreign one: a
# document with one phone number, one reference number or one address means that one.
# The only date, amount or period in a document (a law's date, a fee, a period that
# belongs to another duty) would turn an invented sentence into a wrong one.
SUGGESTED_KINDS = ("phone", "email", "url", "identifier", "address")


@dataclass(frozen=True)
class ForeignValue:
    """A hard value of the draft that the source does not contain."""

    block_id: str
    value: Value
    suggestion: str | None = None  # the source's only contact of that kind, if it has one


@dataclass
class KnownValues:
    """The values a draft may contain: those of the source, and the fact sheet's
    normalised values that the source contains in another form (a period as its bare
    count, an identifier with other spacing).

    A fact-sheet value the source does not contain at all (an end of a period the model
    computed, a sum) is not known: FACT-05 warns on the fact sheet, FACT-06 flags it in
    the draft, and FACT-01 does not require it, so the two cannot contradict each
    other."""

    lang: str
    source_values: list[Value]
    fact_values: list[Value]
    candidates: dict[str, set[str]]  # kind -> canonical source values of that kind

    @classmethod
    def of(cls, source: SourceDocument, factsheet: FactSheet | None, lang: str) -> KnownValues:
        values = source_values(source, lang)
        fact_values: list[Value] = []
        if factsheet:
            for fact in factsheet.facts:
                target = parse_value_norm(fact.value_norm, fact.kind, lang)
                if target is not None and any(matches(target, v) for v in values):
                    fact_values.append(target)
        candidates: dict[str, set[str]] = defaultdict(set)
        for v in values:
            if v.kind in HARD_KINDS:
                candidates[v.kind].add(v.canonical)
        return cls(lang, values, fact_values, candidates)

    def supports(self, value: Value) -> bool:
        if any(matches(value, v) for v in self.source_values):
            return True
        if any(matches(value, v) for v in self.fact_values):
            return True
        if value.kind == "url":
            # A shortened address that leads to the right site: zh.ch for www.zh.ch/soziales.
            prefix = value.canonical + "/"
            return any(
                v.kind == "url" and v.canonical.startswith(prefix) for v in self.source_values
            )
        if value.kind == "time" and value.canonical.endswith(":00"):
            # "8 Uhr bis 12 Uhr" for a source that says "8-12 Uhr": there the first hour
            # is a plain number.
            hour = str(int(value.canonical[:2]))
            return any(v.kind == "number" and v.canonical == hour for v in self.source_values)
        return False

    def foreign(self, text: str) -> list[Value]:
        """The hard values of a text that neither the source nor the fact sheet has."""
        return [
            v
            for v in extract_values(text, self.lang)
            if v.kind in HARD_KINDS and not self.supports(v)
        ]

    def suggestion(self, value: Value) -> str | None:
        """The source's only contact of the value's kind, if it has exactly one."""
        if value.kind in SUGGESTED_KINDS and len(self.candidates[value.kind]) == 1:
            (only,) = self.candidates[value.kind]
            return display_value(Value(value.kind, only), self.lang)
        return None


def foreign_values(
    draft: Draft, source: SourceDocument, factsheet: FactSheet | None, lang: str
) -> list[ForeignValue]:
    """FACT-06: the dates, amounts, phone numbers, e-mail and web addresses, percentages,
    times, periods, identifiers and postal addresses in the draft that neither the
    source nor the fact sheet contains, in draft order. Plain numbers are not checked;
    "zwei Wochen" may become "14 Tage" (the periods are equal)."""
    known = KnownValues.of(source, factsheet, lang)
    return [
        ForeignValue(block.id, value, known.suggestion(value))
        for block in draft.blocks
        for value in known.foreign(block.text)
    ]


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
        yield hit(
            f"FACT-06.{item.value.kind}",  # one message per kind: the date, the amount, ...
            value=item.value.text,
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
        yield hit("LAY-03.few", n=len(headings), blocks=len(blocks))
    for b in headings:
        n = len(b.text.split())
        if n > ctx.params.max_heading_words:
            yield hit(
                "LAY-03",
                words=n,
                limit=ctx.params.max_heading_words,
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
    score = f"{result.score:.0f}"
    if ctx.lang == "de" and result.score < ctx.params.readability_target:
        yield hit(
            "READ-01.below",
            formula=name,
            score=score,
            target=f"{ctx.params.readability_target:.0f}",
            level=ctx.level,
            severity="warn",
        )
    else:
        yield hit("READ-01", formula=name, score=score)


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
    "SEM-08": "Obligation, possibility or condition changed",
    # Asked in decision mode only (the partial's judge section), since 8 October 2026.
    "SEM-09": "Advice or evaluation the source does not contain",
    "SEM-10": "Period without its start",
}
for _rule_id, _title in JUDGE_RULES.items():
    declare(_rule_id, lang=None, title=_title, severity=sev("warn"), scope="judge")
