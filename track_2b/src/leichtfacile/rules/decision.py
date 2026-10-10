"""Decision mode (track_2b/docs/use-case-decisions.md, PLAN.md WP15): the parts of a decision that
the letter may never drop, found by code, and the check FACT-08 that every one of them
is cited by a block and listed by no omission.

A decision has an operative part (the Dispositiv: what the authority decided, as
numbered items) and the appeal instructions (the Rechtsmittelbelehrung: the period, its
start and the address). Both are found by a heading when the document has one (`III.
Entscheid`, `Rechtsmittelbelehrung`) and by their text when it has not: a sentence that
names the verb of deciding and ends with a colon (`Demnach erkennt das
Verwaltungsgericht:`) followed by numbered items, and a paragraph that begins `Gegen
diesen Entscheid kann`. A court's PDF often has no headings at all: the Schwyz decision
III 2022 132 (track_2b/docs/sources.md) has three, none of them the operative part. Calibrated
on the team's KESB decision (track_2b/data/examples/sources) and on that one, 8 October 2026.

The distribution list that closes an operative part (`Zustellung an:`, `Mitteilung an:`)
is not protected: who gets a copy is not something the letter must carry.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from leichtfacile.rules.base import Context, Hit, rule, sev
from leichtfacile.rules.document import DocInput
from leichtfacile.rules.messages import hit
from leichtfacile.schemas import Fact, FactSheet, Segment, SourceDocument

DECISION_MODE = "decision"
_NUMBERED = r"(?:[IVX]+\.|[A-Z]\.|\d{1,2}\.)?\s*"  # "III. Entscheid", "4. Dispositiv"
# A heading that opens the operative part: the word alone, a numeral in front at most.
# "Entscheid vom 17. Oktober 2022" and "Entscheid über eine Beistandschaft" are titles.
_OPERATIVE_HEADING = {
    "de": re.compile(
        "^" + _NUMBERED + r"(?:Dispositiv|Entscheid|Urteil|Beschluss|Verfügung|Erkenntnis"
        r"|Rechtsspruch)\s*[:.]?$",
        re.IGNORECASE,
    ),
    "fr": re.compile(
        "^" + _NUMBERED + r"(?:Dispositif|Décision|Par ces motifs)\s*[:.]?$", re.IGNORECASE
    ),
}
# A sentence that opens the operative part of a document without headings: the verb of
# deciding, its subject before or after it ("Demnach erkennt das Verwaltungsgericht:",
# "Die KESB verfügt:"), and a colon at the end.
_OPERATIVE_TEXT = {
    "de": re.compile(
        r"\b(?:erkennt|verfügt|beschliesst|beschließt|entscheidet"
        r"|wird (?:erkannt|verfügt|beschlossen|entschieden))\b[^:]{0,80}:$",
        re.IGNORECASE,
    ),
    "fr": re.compile(
        r"(?:^Par ces motifs\b.*|\b(?:prononce|décide|ordonne|arrête|statue)\b[^:]{0,80}):$",
        re.IGNORECASE,
    ),
}
_APPEAL_HEADING = {
    "de": re.compile(
        "^" + _NUMBERED + r"(?:Rechtsmittel(?:belehrung)?|Rechtsbehelf(?:sbelehrung)?)\s*[:.]?$",
        re.IGNORECASE,
    ),
    "fr": re.compile(
        "^" + _NUMBERED + r"(?:(?:Indication des )?voies? de (?:droit|recours)|Recours)\s*[:.]?$",
        re.IGNORECASE,
    ),
}
# The sentence that opens the appeal instructions in a document without a heading for
# them; a court's operative part carries them as one of its numbered items.
_APPEAL_TEXT = {
    "de": re.compile(
        r"^(?:\d{1,2}\.\s*)?Gegen (?:diesen|diese|dieses)\b.*\bkann\b"
        r".*\b(?:Beschwerde|Einsprache|Rekurs|Rechtsmittel|Verwaltungsgerichtsbeschwerde)\b"
        r"|\binnert \d+ Tagen\b.*\b(?:Beschwerde|Einsprache|Rekurs)\b"
        r"|\b(?:Beschwerde|Einsprache|Rekurs) (?:erhoben|eingereicht|geführt) werden\b",
        re.IGNORECASE,
    ),
    "fr": re.compile(
        r"\b(?:peut faire l'objet d'un recours|recours\b.*\bdans (?:les|un délai de) \d+ jours"
        r"|dans les \d+ jours (?:dès|à compter|suivant|qui suivent)\b.*\brecours\b)",
        re.IGNORECASE,
    ),
}
# The distribution list closes the operative part.
_DISTRIBUTION = {
    "de": re.compile(
        r"^(?:\d{1,2}\.\s*)?(?:Zustellung|Zustellungen|Mitteilung|Mitteilungen|Eröffnung|Eröffnet"
        r"|Versand)\b",
        re.IGNORECASE,
    ),
    "fr": re.compile(
        r"^(?:\d{1,2}\.\s*)?(?:Communication|Notification|Expédition)\b", re.IGNORECASE
    ),
}
_ITEM_START = re.compile(r"^\d{1,2}[.)](?:\s|$)|^[a-z][.)]\s")  # "1." alone, "1. Die ...", "a) ..."
# Under an appeal heading, a second paragraph belongs to the instructions when it talks
# about them; the date of dispatch and the signatures do not.
_APPEAL_WORDS = re.compile(
    r"\b(?:Beschwerde\w*|Einsprache|Rekurs|Rechtsmittel\w*|Frist|Tagen|Gericht\w*|Eingabe"
    r"|recours|délai|jours|tribunal|mémoire)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProtectedPart:
    """One numbered item of the operative part, or the appeal instructions."""

    kind: str  # item | appeal
    segment_ids: tuple[str, ...]
    text: str

    @property
    def ids(self) -> set[str]:
        return set(self.segment_ids)


@dataclass(frozen=True)
class ProtectedSegments:
    items: tuple[ProtectedPart, ...]  # the operative part, item by item, in order
    appeal: ProtectedPart | None
    found_by: str = ""  # how the operative part was found: heading, text or nothing

    def parts(self) -> list[ProtectedPart]:
        return [*self.items, *([self.appeal] if self.appeal else [])]

    def ids(self) -> set[str]:
        return {s for part in self.parts() for s in part.segment_ids}


def _lang(source: SourceDocument) -> str:
    return "fr" if source.lang == "fr" else "de"


def _text(segments: list[Segment]) -> str:
    text = " ".join(s.text for s in segments)
    return text if len(text) <= 200 else text[:197] + "..."


def _paras(segments: list[Segment]) -> list[list[Segment]]:
    groups: list[list[Segment]] = []
    for seg in segments:
        if groups and groups[-1][0].para == seg.para:
            groups[-1].append(seg)
        else:
            groups.append([seg])
    return groups


def _under_heading(segments: list[Segment], index: int) -> list[Segment]:
    """The segments after the heading at `index`, up to the next heading of its level
    or above (any heading when levels are unknown)."""
    level = segments[index].heading_level
    run: list[Segment] = []
    for seg in segments[index + 1 :]:
        if seg.kind == "heading":
            if level is None or seg.heading_level is None or seg.heading_level <= level:
                break
            continue
        run.append(seg)
    return run


def _after_marker(segments: list[Segment], index: int) -> list[Segment]:
    """The segments after the marker sentence at `index`: the rest of its paragraph,
    then every paragraph that starts like a numbered item or is a list, up to the
    first that does not (the place and date, the signatures)."""
    marker = segments[index]
    run = [s for s in segments[index + 1 :] if s.para == marker.para and s.kind != "heading"]
    rest = [s for s in segments[index + 1 :] if s.para != marker.para]
    for group in _paras(rest):
        first = group[0]
        if first.kind == "heading":
            break
        if first.kind != "list_item" and not _ITEM_START.match(first.text):
            break
        run += group
    return run


def _operative(segments: list[Segment], lang: str) -> tuple[list[Segment], int | None, str]:
    for i, seg in enumerate(segments):
        if seg.kind == "heading" and _OPERATIVE_HEADING[lang].match(seg.text.strip()):
            return _under_heading(segments, i), i, "heading"
    for i, seg in enumerate(segments):
        if seg.kind != "heading" and _OPERATIVE_TEXT[lang].search(seg.text.strip()):
            return _after_marker(segments, i), i, "text"
    return [], None, ""


def _appeal(segments: list[Segment], lang: str, after: int | None) -> list[Segment]:
    for i, seg in enumerate(segments):
        if seg.kind == "heading" and _APPEAL_HEADING[lang].match(seg.text.strip()):
            run: list[Segment] = []
            for group in _paras(_under_heading(segments, i)):
                if run and not _APPEAL_WORDS.search(" ".join(s.text for s in group)):
                    break
                run += group
            return run
    # Without a heading: the first sentence after the operative part (or anywhere, when
    # there is none) that reads like the instructions, with the rest of its paragraph.
    start = after + 1 if after is not None else 0
    for seg in segments[start:]:
        if seg.kind != "heading" and _APPEAL_TEXT[lang].search(seg.text.strip()):
            return [s for s in segments if s.para == seg.para and s.kind != "heading"]
    return []


def protected_segments(source: SourceDocument) -> ProtectedSegments:
    """The operative part, item by item, and the appeal instructions of a decision.
    Empty when the document has neither: the mode then protects nothing, and the
    reviewer sees an ordinary draft."""
    lang = _lang(source)
    operative, marker, found_by = _operative(source.segments, lang)
    appeal_run = _appeal(source.segments, lang, marker)
    appeal_ids = {s.id for s in appeal_run}
    items: list[ProtectedPart] = []
    for group in _paras([s for s in operative if s.id not in appeal_ids]):
        text = _text(group)
        if _DISTRIBUTION[lang].match(text):
            break  # the list of recipients, and everything after it
        if not re.search(r"[^\W\d_]{3}", text):
            continue  # a bare number: "1." that stands as a segment of its own
        items.append(ProtectedPart("item", tuple(s.id for s in group), text))
    appeal = None
    if appeal_run:
        appeal = ProtectedPart("appeal", tuple(s.id for s in appeal_run), _text(appeal_run))
    return ProtectedSegments(tuple(items), appeal, found_by)


def protect_factsheet(fs: FactSheet, source: SourceDocument) -> FactSheet:
    """The fact sheet of a decision job after the code completion: every fact cited from
    a protected segment is must-keep whatever the model marked; a value code added
    outside them and outside the core answers is background (the header's and the
    reasoning's dates, which the repair rounds would otherwise chase; test runs of
    7 October 2026); no protected segment stays an omit candidate; and each protected
    part gets one fact without a value, so that a dropped part is asked for in a repair
    round like a missing value (FACT-08 names it)."""
    protected = protected_segments(source)
    ids = protected.ids()
    if not ids:
        return fs
    core = {s for answer in fs.core.model_dump().values() for s in answer["segment_ids"]}
    facts: list[Fact] = []
    for fact in fs.facts:
        cited = set(fact.segment_ids)
        if cited & ids:
            keep = True
        elif fact.origin == "code" and not cited & core:
            keep = False
        else:
            keep = fact.must_keep
        if keep != fact.must_keep:
            fact = fact.model_copy(update={"must_keep": keep})
        facts.append(fact)
    for part in protected.parts():
        facts.append(
            Fact(
                id=f"f{len(facts) + 1:02d}",
                kind="deadline" if part.kind == "appeal" else "other",
                text=part.text,
                segment_ids=list(part.segment_ids),
                must_keep=True,
                origin="code",
            )
        )
    omit = [
        o.model_copy(update={"segment_ids": [s for s in o.segment_ids if s not in ids]})
        for o in fs.omit_candidates
    ]
    omit = [o for o in omit if o.segment_ids]
    return fs.model_copy(update={"facts": facts, "omit_candidates": omit})


def part_fact_id(part: ProtectedPart, factsheet: FactSheet | None) -> str | None:
    """The fact `protect_factsheet` added for the part, if the sheet has it."""
    if factsheet is None:
        return None
    for fact in factsheet.facts:
        if fact.origin == "code" and not fact.value_norm and set(fact.segment_ids) == part.ids:
            return fact.id
    return None


@rule(
    "FACT-07",
    lang=None,
    title="The fixed notice is present",
    severity=sev("error"),
    scope="export",
)
def fact_07(lines: list[str], ctx: Context) -> Iterator[Hit]:
    """Decision mode, on the export's lines: the first and the last line are the
    authority's notice, word for word. The exporters write it; the check catches an
    export made without it, and a review edit that removes or changes it."""
    if not ctx.notice:
        return
    text = [line for line in lines if line.strip()]
    if not text or text[0] != ctx.notice:
        yield hit("FACT-07.first", notice=ctx.notice, evidence=text[0] if text else "")
    if not text or text[-1] != ctx.notice:
        yield hit("FACT-07.last", notice=ctx.notice, evidence=text[-1] if text else "")


@rule(
    "FACT-08",
    lang=None,
    title="Nothing from the operative part or the appeal instructions is dropped",
    severity=sev("error"),
    scope="document",
)
def fact_08(doc: DocInput, ctx: Context) -> Iterator[Hit]:
    """Decision mode only: every item of the operative part and the appeal instructions
    are cited by some block and listed by no omission. The hit carries the part's fact
    id, so a repair round asks for the part like a missing value."""
    if doc.mode != DECISION_MODE or doc.source is None:
        return
    protected = protected_segments(doc.source)
    cited = {s for b in doc.draft.blocks for s in b.segment_ids}
    omitted = {s for o in doc.draft.omissions for s in o.segment_ids}
    for number, part in enumerate(protected.items, 1):
        fact_id = part_fact_id(part, doc.factsheet)
        if part.ids & omitted:
            yield hit(
                "FACT-08.omitted",
                item=number,
                text=part.text[:120],
                evidence=part.text,
                fact_id=fact_id,
                segment_ids=part.segment_ids,
            )
        elif not part.ids & cited:
            yield hit(
                "FACT-08",
                item=number,
                text=part.text[:120],
                evidence=part.text,
                fact_id=fact_id,
                segment_ids=part.segment_ids,
            )
    appeal = protected.appeal
    if appeal is None:
        return
    fact_id = part_fact_id(appeal, doc.factsheet)
    if appeal.ids & omitted:
        yield hit(
            "FACT-08.appeal_omitted",
            text=appeal.text[:120],
            evidence=appeal.text,
            fact_id=fact_id,
            segment_ids=appeal.segment_ids,
        )
    elif not appeal.ids & cited:
        yield hit(
            "FACT-08.appeal",
            text=appeal.text[:120],
            evidence=appeal.text,
            fact_id=fact_id,
            segment_ids=appeal.segment_ids,
        )
