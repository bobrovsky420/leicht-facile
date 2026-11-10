"""The model stages: understand, write, judge, repair, recover, and the single-prompt
baselines.

Each stage renders its prompt, calls the model through `complete_json` (schema-checked
output with one repair round on invalid JSON, and the checks of pipeline/checks.py on
the answer), and hands the lenient answer to the code that makes the strict artifact of
it: the fact sheet (pipeline/facts.py), a draft version (pipeline/versions.py), the
judge report (`to_judge_report`). An answer is never changed on the way. Settings per
stage follow docs/architecture.md §4.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from leichtfacile.llm.client import LLMClient, LLMResult
from leichtfacile.llm.json_out import LLMOutputError, complete_json
from leichtfacile.pipeline import render as r
from leichtfacile.pipeline.checks import (
    copy_check,
    drop_topical,
    foreign_check,
    repair_texts,
    soft_checks,
    topic_check,
    understand_texts,
    write_texts,
)
from leichtfacile.pipeline.facts import factsheet_of
from leichtfacile.pipeline.labels import label
from leichtfacile.pipeline.models import (
    JudgeOut,
    RecoverOut,
    RepairOut,
    UnderstandOut,
    WriteOut,
    clean_text,
)
from leichtfacile.pipeline.prompts import examples, level_name, mode_context, render
from leichtfacile.pipeline.versions import (
    RepairRequest,
    carries,
    fact_window,
    first_version,
    repair_version,
    repeats,
    target_block,
    wording_key,
)
from leichtfacile.rules.checker import check_draft
from leichtfacile.rules.document import KnownValues, display_value
from leichtfacile.rules.medication import has_doses, names_medication
from leichtfacile.rules.nlp import parse
from leichtfacile.rules.styleguide import style_guide
from leichtfacile.rules.values import Value, extract_values, parse_value_norm
from leichtfacile.schemas import (
    ZH_CONDITIONS,
    Block,
    Draft,
    Fact,
    FactCheck,
    FactSheet,
    Finding,
    JudgeReport,
    Level,
    RepairRecord,
    Segment,
    SemanticFinding,
    SourceDocument,
    Unsupported,
)


@dataclass(frozen=True)
class StageSettings:
    temperature: float
    max_tokens: int  # without thinking
    max_tokens_thinking: int  # the reasoning comes on top of the answer


STAGES: dict[str, StageSettings] = {
    "understand": StageSettings(temperature=0.1, max_tokens=6000, max_tokens_thinking=12000),
    "write": StageSettings(temperature=0.3, max_tokens=8000, max_tokens_thinking=16000),
    "judge": StageSettings(temperature=0.0, max_tokens=6000, max_tokens_thinking=12000),
    "repair": StageSettings(temperature=0.2, max_tokens=6000, max_tokens_thinking=12000),
    "baseline": StageSettings(temperature=0.3, max_tokens=6000, max_tokens_thinking=12000),
    "recover": StageSettings(temperature=0.2, max_tokens=1500, max_tokens_thinking=6000),
}


def thinking_for(llm: LLMClient, stage: str, model: str | None = None) -> bool:
    """Whether a stage thinks: the `thinking_stages` of the model it calls (the writer
    unless named), as the provider, the model's table and the preset set them."""
    settings = llm.settings.llm
    return stage in settings.for_model(model or settings.models.writer).thinking_stages


log = logging.getLogger(__name__)
LONG_DOCUMENT_WORDS = 3000  # longer sources are written section by section
SECTION_WORDS = 1500
MIN_SECTION_SEGMENTS = 6  # a cut-off answer for fewer sentences is an error
JUDGE_RULE_IDS = {"SEM-01", "SEM-02", "SEM-03", "SEM-04", "SEM-05", "SEM-08"}
# Asked in decision mode only (the partial's judge section): a standard judge is not
# asked, and an answer it gives anyway is dropped.
DECISION_JUDGE_RULE_IDS = {"SEM-09", "SEM-10"}


def _call(
    llm: LLMClient,
    stage: str,
    prompt: str,
    schema,
    model: str | None,
    check=None,
    soft_check=None,
):
    """Call the model for a stage. When the reasoning of a thinking call runs out of
    tokens before the answer, the stage is answered once more without thinking."""
    s = STAGES[stage]
    messages = [{"role": "user", "content": prompt}]
    thinking = thinking_for(llm, stage, model)
    try:
        return complete_json(
            llm,
            messages,
            schema,
            check=check,
            soft_check=soft_check,
            model=model,
            thinking=thinking,
            temperature=s.temperature,
            max_tokens=s.max_tokens_thinking if thinking else s.max_tokens,
            stage=stage,
        )
    except LLMOutputError as exc:
        if not (thinking and any(r.truncated for r in exc.results)):
            raise
        log.warning("stage %s: the reasoning ran out of tokens; answering without thinking", stage)
        out, results = complete_json(
            llm,
            messages,
            schema,
            check=check,
            soft_check=soft_check,
            model=model,
            thinking=False,
            temperature=s.temperature,
            max_tokens=s.max_tokens,
            stage=stage,
        )
        return out, exc.results + results


# -- understand -----------------------------------------------------------------------


def understand(
    llm: LLMClient,
    source: SourceDocument,
    *,
    level: Level,
    model: str | None = None,
    mode: str = "standard",
    addressee: str | None = None,
    sender: str = "authority",
) -> tuple[FactSheet, list[LLMResult]]:
    prompt = render(
        source.variety,
        "understand",
        **mode_context("understand", mode, addressee, sender),
        medication=has_doses(source),
        level_name=level_name(source.variety, level),
        source=r.source_text(source),
    )
    out, results = _call(
        llm,
        "understand",
        prompt,
        UnderstandOut,
        model,
        check=copy_check(source.variety, "understand", understand_texts),
        soft_check=topic_check(source.variety, "understand", understand_texts, source.text()),
    )
    topical = drop_topical(understand_texts(out), source.variety, source.text(), "understand")
    return factsheet_of(out, source, topical), results


# -- write ----------------------------------------------------------------------------


def split_sections(
    source: SourceDocument, max_words: int = SECTION_WORDS
) -> list[tuple[str, list[Segment]]]:
    """Group segments by top-level heading, then pack groups up to max_words."""
    levels = [s.heading_level for s in source.segments if s.kind == "heading" and s.heading_level]
    top = min(levels) if levels else None
    groups: list[list[Segment]] = []
    for seg in source.segments:
        starts_group = seg.kind == "heading" and seg.heading_level == top
        if not groups or starts_group:
            groups.append([])
        groups[-1].append(seg)
    sections: list[tuple[str, list[Segment]]] = []
    current: list[Segment] = []
    for group in groups:
        words = sum(len(s.text.split()) for s in current + group)
        if current and words > max_words:
            sections.append((_section_title(current, source.lang), current))
            current = []
        current = current + group
    if current:
        sections.append((_section_title(current, source.lang), current))
    return sections


def _section_title(segments: list[Segment], lang: str = "de") -> str:
    heading = next((s.text for s in segments if s.kind == "heading"), None)
    return heading or label(lang, "section", first=segments[0].id, last=segments[-1].id)


def write(
    llm: LLMClient,
    source: SourceDocument,
    factsheet: FactSheet,
    *,
    level: Level,
    model: str | None = None,
    mode: str = "standard",
    addressee: str | None = None,
    sender: str = "authority",
    address: str = "formal",
) -> tuple[Draft, list[LLMResult]]:
    lang = source.lang
    variety = source.variety  # the prompts, the style guide and the examples are the variety's
    if source.word_count() > LONG_DOCUMENT_WORDS:
        sections = split_sections(source)
    else:
        sections = [("", source.segments)]
    # Each section's answer with the texts it leaves out: about the prompt's own examples.
    answers: list[tuple[WriteOut, set[str]]] = []
    results: list[LLMResult] = []
    pending = list(sections)
    sectioned = len(sections) > 1
    # A fact without a sentence belongs to no section: the first section written gets
    # it, since FACT-01 asks for it later (audit of 6 November 2026).
    unplaced = {f.id for f in factsheet.facts if not f.segment_ids}
    while pending:
        title, segments = pending.pop(0)
        in_section = {s.id for s in segments}
        fact_ids = None
        if sectioned:
            fact_ids = [
                f.id for f in factsheet.facts if set(f.segment_ids) & in_section or f.id in unplaced
            ]
        prompt = render(
            variety,
            "write",
            **mode_context("write", mode, addressee, sender, address),
            medication=names_medication(factsheet),
            level_name=level_name(variety, level),
            level=level,
            style_guide=style_guide(variety, level, address),
            examples=examples(variety),
            section=title if sectioned else "",
            factsheet=r.factsheet_text(factsheet, fact_ids, lang),
            source=r.source_lines(segments),
        )
        try:
            out, res = _call(
                llm,
                "write",
                prompt,
                WriteOut,
                model,
                check=copy_check(variety, "write", write_texts),
                soft_check=topic_check(variety, "write", write_texts, source.text()),
            )
        except LLMOutputError as exc:
            results += exc.results
            cut_off = bool(exc.results) and exc.results[-1].truncated
            if not cut_off or len(segments) < 2 * MIN_SECTION_SEGMENTS:
                raise
            # The answer for this many sentences did not fit max_tokens (a cut-off
            # answer is never used: its last objects are incomplete). The part is
            # written again as two halves; on CSCS 8 jobs failed this way on pages the
            # splitter had left whole (6 October 2026).
            half = len(segments) // 2
            log.warning("write: answer cut off for %d sentences; writing two halves", len(segments))
            halves = [segments[:half], segments[half:]]
            pending[:0] = [(_section_title(part, lang), part) for part in halves]
            sectioned = True
            continue
        results += res
        unplaced = set()
        answers.append((out, drop_topical(write_texts(out), variety, source.text(), "write")))
    return first_version(source, factsheet, answers, level=level, address=address), results


# -- judge ----------------------------------------------------------------------------


def judge(
    llm: LLMClient,
    source: SourceDocument,
    factsheet: FactSheet,
    draft: Draft,
    *,
    model: str | None = None,
    mode: str = "standard",
    addressee: str | None = None,
    sender: str = "authority",
) -> tuple[JudgeReport, list[LLMResult]]:
    cited = {s for b in draft.blocks for s in b.segment_ids}
    cited |= {s for f in factsheet.facts for s in f.segment_ids}
    excerpt = r.cited_source(source, cited) if cited else r.source_text(source)
    prompt = render(
        draft.variety,
        "judge",
        **mode_context("judge", mode, addressee, sender, draft.address),
        level_name=level_name(draft.variety, draft.level),
        factsheet=r.factsheet_text(factsheet, lang=draft.lang),
        source=excerpt,
        draft=r.draft_lines(draft, refs=False),
        glossary=r.glossary_text(draft),
    )
    out, results = _call(llm, "judge", prompt, JudgeOut, model)
    name = results[-1].usage.model if results else llm.resolve_model(model, False)[0]
    return to_judge_report(out, draft, factsheet, name, mode=mode), results


def _quote_key(text: str) -> str:
    """A text as the quote check compares it: no block id, heading or list marker in
    front (the judge reads `[b012] - text`, `render.draft_lines`, and quoted the marker
    in 43 of 66 dropped verdicts of the final run; 12 October 2026), no Mediopunkt or
    soft hyphen, one space between words, no quotation marks or punctuation at the
    ends, lower case."""
    text = re.sub(r"^\s*(?:\[b[\w.]+\]\s*)?(?:#+\s+|-\s+)?", "", text)
    text = text.replace("·", "").replace("­", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip("\"'«»„“”‚‘’.,;:!? ").casefold()


def quoted_block(quote: str | None, block_id: str, draft: Draft) -> str | None:
    """The block an unsupported verdict belongs to: the cited block when it holds the
    quote, else the first block that does, else None. Without a quote (or one too short
    to mean anything) the cited block, as before 10 October 2026. The 70B judge cited
    the block ids of the prompt's own example (`b006` in 46 of 179 verdicts of the
    example builds), so a verdict has to point at words that stand in the draft."""
    by_id = draft.by_id()
    key = _quote_key(quote or "")
    if len(key) < 3:
        return block_id if block_id in by_id else None
    cited = by_id.get(block_id)
    if cited is not None and key in _quote_key(cited.text):
        return block_id
    for block in draft.blocks:
        if key in _quote_key(block.text):
            return block.id
    return None


def to_judge_report(
    out: JudgeOut, draft: Draft, factsheet: FactSheet, model: str, *, mode: str = "standard"
) -> JudgeReport:
    rule_ids = JUDGE_RULE_IDS | (DECISION_JUDGE_RULE_IDS if mode == "decision" else set())
    by_id = draft.by_id()
    blocks = set(by_id)
    facts = factsheet.fact_ids()
    seen: set[str] = set()
    checks = []
    for c in out.fact_checks:
        if c.fact_id in facts and c.fact_id not in seen:
            seen.add(c.fact_id)
            checks.append(
                FactCheck(
                    fact_id=c.fact_id,
                    status=c.status,
                    block_ids=[b for b in c.block_ids if b in blocks],
                    note=clean_text(c.note),
                )
            )
    unsupported: list[Unsupported] = []
    dropped: list[Unsupported] = []
    for u in out.unsupported:
        target = quoted_block(u.quote, u.block_id, draft)
        quote = clean_text(u.quote) if u.quote and u.quote.strip() else None
        item = Unsupported(block_id=target or u.block_id, quote=quote, note=clean_text(u.note))
        if target is not None and by_id[target].kind == "heading":
            # A question heading is the reader's question (LAY-03), no statement: the
            # 70B objected to "De quoi avez-vous besoin ?" as not in the original, and a
            # repair would turn it into a statement (12 October 2026; the audit keeps it).
            dropped.append(item)
        elif target is not None:
            unsupported.append(item)
        elif u.block_id in blocks:  # a quote the draft does not contain: the audit keeps it
            dropped.append(item)
    return JudgeReport(
        draft_version=draft.version,
        model=model,
        fact_checks=checks,
        unsupported=unsupported,
        dropped=dropped,
        semantic_findings=[
            SemanticFinding(block_id=s.block_id, rule_id=s.rule_id, note=clean_text(s.note))
            for s in out.semantic_findings
            if s.block_id in blocks and s.rule_id in rule_ids
        ],
    )


# -- repair ---------------------------------------------------------------------------


# The kinds whose exact form the repair request spells out next to the fact sheet's
# value: a date as 31. März 2026, an amount as 1'500 Franken, a phone number in groups.
# Web and e-mail addresses are given as written; a quantity keeps the sheet's form.
_SPELLED_OUT_KINDS = frozenset(
    {"date", "amount", "phone", "percent", "time", "period", "identifier", "address"}
)


def missing_value_label(fact: Fact, lang: str) -> str:
    """The value a missing fact must get, with the exact form the draft should write it
    in when that differs from the fact sheet's form (`2026-03-31`: `31. März 2026`).
    A small model asked for `2026-03-31` sometimes writes it as it stands."""
    if not fact.value_norm:
        return ""
    target = parse_value_norm(fact.value_norm, fact.kind, lang)
    if target is not None and target.kind in _SPELLED_OUT_KINDS:
        exact = display_value(target, lang)
        if exact and exact != fact.value_norm:
            return label(lang, "missing_value_exact", value=fact.value_norm, exact=exact)
    return label(lang, "missing_value", value=fact.value_norm)


def repair(
    llm: LLMClient,
    source: SourceDocument,
    factsheet: FactSheet,
    draft: Draft,
    request: RepairRequest,
    *,
    model: str | None = None,
    mode: str = "standard",
    addressee: str | None = None,
    sender: str = "authority",
    kind: str = "repair",
    version: int | None = None,
) -> tuple[Draft, list[LLMResult], RepairRecord]:
    """One repair round. Returns the new draft version, the model calls and the record
    of the round: what was asked, what the model answered, what code left out.
    `version`: the new version's number, when it is not the next after `draft` (the
    vocabulary round starts from the best version, not the latest)."""
    lang = draft.lang
    variety = draft.variety  # the prompt and the style guide are the variety's
    by_id = draft.by_id()
    facts = {f.id: f for f in factsheet.facts}
    flagged_lines = []
    cited: set[str] = set()
    for block_id, problems in request.problems.items():
        block = by_id[block_id]
        cited |= set(block.segment_ids)
        lines = [f"[{block_id}] {block.text}", "  " + label(lang, "problems"), *problems]
        needed = [facts[f] for f in block.fact_ids if f in facts]
        if needed:
            lines.append("  " + label(lang, "keep_facts"))
            lines += [f"  - {f.id}: {f.text}" for f in needed]
        flagged_lines.append("\n".join(lines))
    missing_lines = []
    for fact in request.missing:
        cited |= set(fact.segment_ids)
        missing_lines.append(f"- {fact.id}: {fact.text}{missing_value_label(fact, variety)}")
    prompt = render(
        variety,
        "repair",
        **mode_context("repair", mode, addressee, sender, draft.address),
        level_name=level_name(variety, draft.level),
        level=draft.level,
        style_guide=style_guide(variety, draft.level, draft.address),
        flagged="\n\n".join(flagged_lines) or label(lang, "none"),
        missing="\n".join(missing_lines),
        factsheet=r.factsheet_text(factsheet, lang=lang),
        draft=r.draft_lines(draft, refs=False, marked=set(request.problems)),
        source=r.cited_source(source, cited),
    )
    known = KnownValues.of(source, factsheet, variety)
    out, results = _call(
        llm,
        "repair",
        prompt,
        RepairOut,
        model,
        check=copy_check(variety, "repair", repair_texts),
        soft_check=soft_checks(
            topic_check(variety, "repair", repair_texts, source.text()),
            foreign_check(variety, known, repair_texts),
        ),
    )
    topical = drop_topical(repair_texts(out), variety, source.text(), "repair")
    new_draft, record = repair_version(
        draft, out, request, factsheet, topical=topical, kind=kind, version=version
    )
    return new_draft, results, record


# -- recover (one missing fact, asked for from the review page) ----------------------


@dataclass
class Recovery:
    """Sentences for one missing fact, to add to a block; code never applies them, the
    reviewer does. `rejected` says why there are none: "no_source" (the fact has no
    source sentence), "no_answer" (no usable answer in two tries, the fact's value still
    missing included), "foreign" (values the paragraph does not have, after one retry),
    "nothing_new" (every sentence repeats the draft), "no_blocks" (the draft has no block
    to place them after)."""

    fact_id: str
    block_id: str | None = None  # the block the sentences go after
    texts: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)  # the rules on the sentences
    resolved: bool | None = None  # FACT-01 finds the value with them; None: no value
    dropped: list[str] = field(default_factory=list)  # sentences that repeat the draft
    foreign: list[str] = field(default_factory=list)
    rejected: str | None = None


def fact_paragraph(source: SourceDocument, fact: Fact) -> list[Segment]:
    """The sentences of the paragraphs the fact comes from."""
    paras = {s.para for s in source.segments if s.id in fact.segment_ids}
    return [s for s in source.segments if s.para in paras]


def _foreign_values(
    texts: list[str],
    known: KnownValues,
    target: Value | None,
    had: set[str],
    draft_values: list[Value],
    variety: str,
) -> list[str]:
    """The values of the answered sentences that the paragraph does not have (`known`),
    each once, in order. Repeats (`versions.repeats`) are left out before the paragraph check,
    so the office's number from another paragraph does not cost a good sentence."""
    found = {
        v.text: None
        for t in texts
        if not repeats(t, target, had, draft_values, variety)
        for v in known.foreign(t)
    }
    return list(found)


def _placed_findings(
    recovery: Recovery,
    fact: Fact,
    target: Value | None,
    draft: Draft,
    source: SourceDocument,
    factsheet: FactSheet,
) -> tuple[list[Finding], bool | None]:
    """The rules on the sentences, placed after their block, and FACT-01 with them: the
    findings on the new blocks and, for a must-keep fact with a value, whether FACT-01
    finds the value with them (None for the others)."""
    added = [
        Block(id=f"{recovery.block_id}.r{i}", kind="sentence", text=t, fact_ids=[fact.id],
              segment_ids=list(fact.segment_ids))
        for i, t in enumerate(recovery.texts, 1)
    ]  # fmt: skip
    blocks: list[Block] = []
    for b in draft.blocks:
        blocks.append(b)
        if b.id == recovery.block_id:
            blocks += added
    findings = check_draft(
        draft.model_copy(update={"blocks": blocks}), source=source, factsheet=factsheet
    ).findings
    new_ids = {b.id for b in added}
    resolved: bool | None = None
    if target is not None and fact.must_keep:
        resolved = not any(f.rule_id == "FACT-01" and f.fact_id == fact.id for f in findings)
    return [f for f in findings if f.block_id in new_ids], resolved


def recover_fact(
    llm: LLMClient,
    source: SourceDocument,
    factsheet: FactSheet,
    draft: Draft,
    fact_id: str,
    *,
    model: str | None = None,
) -> tuple[Recovery, list[LLMResult]]:
    """Ask for the sentences of one missing fact with only its paragraph and the blocks
    at its place: no fact sheet, no rest of the draft, so the model has no other value
    to take. The prompt names the value and its sentence; an answer without the value is
    sent back once, one with values the paragraph lacks as well. On the 8B over CSCS the
    paragraph alone recovered f07 of the premium letter in 0 of 3 runs, with the value
    and its sentence named in 3 of 3 (docs/prompts.md, "Recovering a missing fact")."""
    variety = draft.variety  # the prompt, the style guide and the values are the variety's
    fact = next(f for f in factsheet.facts if f.id == fact_id)
    recovery = Recovery(fact_id=fact.id)
    if not draft.blocks:  # nothing to place a sentence after (audit of 6 November 2026)
        recovery.rejected = "no_blocks"
        return recovery, []
    paragraph = fact_paragraph(source, fact)
    if not paragraph:
        recovery.rejected = "no_source"
        return recovery, []
    para_ids = {s.id for s in paragraph}
    window = fact_window(draft, source, para_ids)
    target = parse_value_norm(fact.value_norm, fact.kind, variety)
    exact = (display_value(target, variety) if target else "") or (fact.value_norm or "")
    prompt = render(
        variety,
        "recover",
        level_name=level_name(variety, draft.level),
        level=draft.level,
        style_guide=style_guide(variety, draft.level),
        value=exact,
        sentence_ids=", ".join(f"[{i}]" for i in fact.segment_ids if i in para_ids),
        fact=f"- {fact.id}: {fact.text}{missing_value_label(fact, variety)}",
        paragraph=r.source_lines(paragraph),
        blocks="\n".join(f"[{b.id}] {b.text}" for b in window),
    )
    para_source = source.model_copy(update={"segments": paragraph, "title": None})
    known = KnownValues.of(para_source, factsheet.model_copy(update={"facts": [fact]}), variety)
    had = {wording_key(b.text) for b in draft.blocks}  # the draft's wordings
    draft_values = [v for b in draft.blocks for v in extract_values(b.text, variety)]

    def is_repeat(text: str) -> bool:
        return repeats(text, target, had, draft_values, variety)

    def has_value(out: RecoverOut) -> str | None:
        if target is None or any(carries(target, t, variety) for t in out.texts):
            return None
        return label(variety, "recover_value", value=exact)

    def in_paragraph(out: RecoverOut) -> str | None:
        foreign = _foreign_values(out.texts, known, target, had, draft_values, variety)
        return label(variety, "recover_foreign", values=", ".join(foreign)) if foreign else None

    try:
        out, results = _call(
            llm, "recover", prompt, RecoverOut, model, check=has_value, soft_check=in_paragraph
        )
    except LLMOutputError as exc:
        recovery.rejected = "no_answer"
        return recovery, exc.results
    recovery.texts = [t for t in out.texts if not is_repeat(t)]
    recovery.dropped = [t for t in out.texts if is_repeat(t)]
    recovery.foreign = _foreign_values(out.texts, known, target, had, draft_values, variety)
    if recovery.foreign:
        recovery.rejected = "foreign"
        recovery.texts = []
        return recovery, results
    if not recovery.texts:
        recovery.rejected = "nothing_new"
        return recovery, results
    recovery.block_id = target_block(draft, window, out.after, para_ids)
    recovery.findings, recovery.resolved = _placed_findings(
        recovery, fact, target, draft, source, factsheet
    )
    return recovery, results


# -- baseline (condition P0) --------------------------------------------------------


def baseline(
    llm: LLMClient, source: SourceDocument, *, level: Level, model: str | None = None
) -> tuple[Draft, list[LLMResult]]:
    """What a single chatbot prompt gives: no fact sheet, no provenance, no checks."""
    s = STAGES["baseline"]
    thinking = thinking_for(llm, "baseline", model)
    prompt = render(
        source.variety, "baseline", level_name=level_name(source.variety, level), text=source.text()
    )
    result = llm.complete(
        [{"role": "user", "content": prompt}],
        model=model,
        thinking=thinking,
        temperature=s.temperature,
        max_tokens=s.max_tokens_thinking if thinking else s.max_tokens,
        stage="baseline",
    )
    blocks = text_to_blocks(result.text, source.lang)
    draft = Draft(
        doc_id=source.id, lang=source.lang, region=source.region, level=level, origin="baseline",
        blocks=blocks,
    )  # fmt: skip
    return draft, [result]


# -- baseline with the Canton of Zurich's prompt (conditions P0-ZH-*) ------------------

ZH_VARIANTS = ("complete", "condensed")
ZH_TAG = "leichtesprache"
ZH_NO_TAGS_NOTE = f"P0-ZH: the answer had no <{ZH_TAG}> tags; the whole answer was used"
_ZH_TAGGED = re.compile(rf"<{ZH_TAG}>(.*?)</{ZH_TAG}>", re.DOTALL)


def zh_variant(condition: str) -> str:
    """The completeness instruction of a P0-ZH condition: `complete` or `condensed`."""
    variant = condition.rsplit("-", 1)[-1]
    if condition not in ZH_CONDITIONS or variant not in ZH_VARIANTS:
        raise ValueError(f"not a P0-ZH condition: {condition!r}")
    return variant


def zh_answer_text(answer: str) -> tuple[str, bool]:
    """Post-processing as in Zurich's app: the parts between the <leichtesprache> tags
    joined with a line break, stripped, and ß written as ss. Their app reports an error
    when the tags are missing; here the whole answer is used and the flag says so. Their
    `strip_markdown` is not applied: in v1.6.0 it deletes every underscore, so web and
    e-mail addresses would break; fixed upstream after v1.6.0 by our PR #19
    (docs/prompts.md)."""
    parts = _ZH_TAGGED.findall(answer)
    text = "\n".join(parts).strip() if parts else answer.strip()
    return text.replace("ß", "ss"), bool(parts)


def baseline_zh(
    llm: LLMClient,
    source: SourceDocument,
    *,
    level: Level,
    variant: str,
    model: str | None = None,
) -> tuple[Draft, list[LLMResult], list[str]]:
    """The Canton of Zurich's Leichte Sprache prompt (simply-simplify-language v1.6.0,
    THIRD_PARTY_NOTICES.md) as a single-prompt baseline: their system message, rules and
    completeness line verbatim, with the model settings of P0. Returns the draft, the
    model call and the notes for the summary (an answer without the tags)."""
    if variant not in ZH_VARIANTS:
        raise ValueError(f"unknown P0-ZH variant {variant!r}; use one of {ZH_VARIANTS}")
    s = STAGES["baseline"]
    thinking = thinking_for(llm, "baseline", model)
    context = {"variant": variant, "text": source.text()}
    messages = [
        {"role": part, "content": render(source.variety, "baseline_zh", part=part, **context)}
        for part in ("system", "user")
    ]
    result = llm.complete(
        messages,
        model=model,
        thinking=thinking,
        temperature=s.temperature,
        max_tokens=s.max_tokens_thinking if thinking else s.max_tokens,
        stage="baseline_zh",
    )
    text, tagged = zh_answer_text(result.text)
    blocks = text_to_blocks(text, source.lang)
    draft = Draft(
        doc_id=source.id, lang=source.lang, region=source.region, level=level, origin="baseline",
        blocks=blocks,
    )  # fmt: skip
    return draft, [result], [] if tagged else [ZH_NO_TAGS_NOTE]


_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$|^\*\*(.+?)\*\*:?$")
_ITEM_RE = re.compile(r"^(?:[-*\u2022]|\d+[.)])\s+(.*)$")


def text_to_blocks(text: str, lang: str) -> list[Block]:
    """Split free model text into blocks: Markdown headings, list items, sentences."""
    blocks: list[Block] = []

    def add(kind: str, content: str) -> None:
        content = clean_text(content.replace("**", ""))
        if content:
            blocks.append(Block(id=f"b{len(blocks) + 1:03d}", kind=kind, text=content))

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if m := _HEADING_RE.match(line):
            add("heading", m.group(1) or m.group(2))
        elif m := _ITEM_RE.match(line):
            add("list_item", m.group(1))
        else:
            for sent in parse(lang, [line])[0].sents:  # under the pipeline's lock
                add("sentence", sent.text)
    return blocks
