"""The model stages: understand, write, judge, repair, and the single-prompt baseline.

Each stage renders its prompt, calls the model through `complete_json` (schema-checked
output with one repair round on invalid JSON), and turns the lenient model answer into
a strict artifact. Settings per stage follow docs/architecture.md §4.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache

from leichtfacile.llm.client import LLMClient, LLMResult
from leichtfacile.llm.json_out import LLMOutputError, complete_json
from leichtfacile.pipeline import render as r
from leichtfacile.pipeline.labels import label
from leichtfacile.pipeline.models import (
    JudgeOut,
    RepairOut,
    UnderstandOut,
    WriteOut,
    clean_text,
)
from leichtfacile.pipeline.prompts import examples, level_name, render
from leichtfacile.rules.nlp import pipeline as nlp_pipeline
from leichtfacile.rules.styleguide import style_guide
from leichtfacile.rules.values import HARD_KINDS, Value, extract_values, matches, parse_value_norm
from leichtfacile.schemas import (
    Block,
    CoreAnswer,
    CoreQuestions,
    Draft,
    Fact,
    FactCheck,
    FactSheet,
    GlossaryEntry,
    HardTerm,
    JudgeReport,
    Level,
    Omission,
    OmitCandidate,
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
}


def thinking_for(llm: LLMClient, stage: str) -> bool:
    """Whether a stage uses the thinking model (LLM_THINKING_STAGES)."""
    return stage in llm.settings.thinking_stages


log = logging.getLogger(__name__)
LONG_DOCUMENT_WORDS = 3000  # longer sources are written section by section
SECTION_WORDS = 1500
JUDGE_RULE_IDS = {"SEM-01", "SEM-02", "SEM-03", "SEM-04", "SEM-05"}


def _call(llm: LLMClient, stage: str, prompt: str, schema, model: str | None, check=None):
    """Call the model for a stage. When the reasoning of a thinking call runs out of
    tokens before the answer, the stage is answered once more without thinking."""
    s = STAGES[stage]
    messages = [{"role": "user", "content": prompt}]
    thinking = thinking_for(llm, stage)
    try:
        return complete_json(
            llm,
            messages,
            schema,
            check=check,
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
            model=model,
            thinking=False,
            temperature=s.temperature,
            max_tokens=s.max_tokens,
            stage=stage,
        )
        return out, exc.results + results


# -- the prompt's own examples ---------------------------------------------------------

# Rendering a template without its document gives the static text: the instructions,
# the JSON example and (for write) the few-shot pairs.
_STATIC_CONTEXT: dict[str, dict[str, str]] = {
    "understand": {"source": ""},
    "write": {"level": "A2", "style_guide": "", "section": "", "factsheet": "", "source": ""},
    "repair": {
        "level": "A2", "style_guide": "", "flagged": "", "missing": "", "factsheet": "",
        "draft": "", "source": "",
    },
}  # fmt: skip
_QUOTED = re.compile(r'"([^"\n]{12,})"')
COPY_LIMIT = 2  # sentences from the examples that make an answer a copy


def _example_key(text: str) -> str:
    return " ".join(text.lower().replace("·", "").split()).rstrip(".!?:")


@lru_cache(maxsize=16)
def example_keys(lang: str, stage: str) -> frozenset[str]:
    """The sentences of a prompt's own examples, normalised, to recognise an answer that
    copies them. On the Public AI 8B, 4 of 12 dev drafts were the write prompt's JSON
    example, word for word (6 October 2026)."""
    context = dict(_STATIC_CONTEXT[stage], level_name=level_name(lang, "A2"))
    if stage == "write":
        context["examples"] = examples(lang)
    text = render(lang, stage, **context)
    keys = {_example_key(line) for line in text.splitlines()}
    keys |= {_example_key(q) for q in _QUOTED.findall(text)}
    return frozenset(k for k in keys if len(k) >= 12)


def copied_sentences(texts: list[str], lang: str, stage: str) -> int:
    keys = example_keys(lang, stage)
    return sum(1 for t in texts if _example_key(t) in keys)


def _copy_check(lang: str, stage: str, texts_of):
    """A `check` for complete_json: an answer whose sentences are mostly from the prompt's
    examples (COPY_LIMIT or more, and more than half of them) is sent back once with a
    message in the document's language. A generic sentence or two that an honest draft
    shares with an example ("Sie haben dafür 14 Tage Zeit.") is no copy."""

    def check(out) -> str | None:
        texts = texts_of(out)
        copies = copied_sentences(texts, lang, stage)
        if copies >= COPY_LIMIT and copies * 2 > len(texts):
            log.warning("stage %s: the answer copies %d sentences of the example", stage, copies)
            return label(lang, "copied_example", count=copies)
        return None

    return check


def _understand_texts(out: UnderstandOut) -> list[str]:
    # Facts only: the short core answers ("120 francs par chien.") can coincide with the
    # example for a document on the same topic; a copied fact sheet repeats its facts.
    return [f.text for f in out.facts]


def _write_texts(out: WriteOut) -> list[str]:
    return [b.text for b in out.blocks if b.kind != "heading"]


def _repair_texts(out: RepairOut) -> list[str]:
    return [t for item in out.repairs for t in item.texts] + [
        t for add in out.additions for t in add.texts
    ]


# -- understand -----------------------------------------------------------------------


def understand(
    llm: LLMClient, source: SourceDocument, *, level: Level, model: str | None = None
) -> tuple[FactSheet, list[LLMResult]]:
    prompt = render(
        source.lang,
        "understand",
        level_name=level_name(source.lang, level),
        source=r.source_text(source),
    )
    out, results = _call(
        llm,
        "understand",
        prompt,
        UnderstandOut,
        model,
        check=_copy_check(source.lang, "understand", _understand_texts),
    )
    return to_factsheet(out, source.id), results


_DEADLINE_WORDS = re.compile(
    r"\b(?:bis|spätestens|Frist|innert|innerhalb|avant|jusqu|délai|entro|termine)\b",
    re.IGNORECASE,
)
_VALUE_KIND = {"amount": "amount", "phone": "contact", "email": "contact", "url": "contact"}


def _value_norm(value: Value) -> str:
    return value.text if value.kind == "url" else value.canonical


def complete_factsheet(fs: FactSheet, source: SourceDocument) -> FactSheet:
    """Code makes sure no hard value is forgotten: every date, amount, phone number,
    e-mail address, web address, percentage and time in the source that no fact
    carries becomes a fact of its own. Values in passages the model marked as
    droppable become background facts; the rest must be kept."""
    lang = source.lang
    covered = [v for f in fs.facts if (v := parse_value_norm(f.value_norm, f.kind, lang))]
    omitted = {s for o in fs.omit_candidates for s in o.segment_ids}
    facts = list(fs.facts)
    for seg in source.segments:
        for value in extract_values(seg.text, lang):
            if value.kind not in HARD_KINDS or any(matches(c, value) for c in covered):
                continue
            covered.append(value)
            kind = _VALUE_KIND.get(value.kind, "other")
            if value.kind == "date" and _DEADLINE_WORDS.search(seg.text):
                kind = "deadline"
            text = seg.text if len(seg.text) <= 200 else seg.text[:197] + "..."
            facts.append(
                Fact(
                    id=f"f{len(facts) + 1:02d}",
                    kind=kind,  # type: ignore[arg-type]
                    text=text,
                    value_norm=_value_norm(value),
                    segment_ids=[seg.id],
                    must_keep=seg.id not in omitted and seg.kind != "heading",
                    origin="code",
                )
            )
    return fs.model_copy(update={"facts": facts})


def to_factsheet(out: UnderstandOut, doc_id: str) -> FactSheet:
    facts = [
        Fact(
            id=f"f{i:02d}",
            kind=f.kind,  # type: ignore[arg-type]
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
) -> tuple[Draft, list[LLMResult]]:
    lang = source.lang
    if source.word_count() > LONG_DOCUMENT_WORDS:
        sections = split_sections(source)
    else:
        sections = [("", source.segments)]
    blocks: list[Block] = []
    omissions: list[Omission] = []
    glossary: dict[str, GlossaryEntry] = {}
    results: list[LLMResult] = []
    known_facts = factsheet.fact_ids()
    for title, segments in sections:
        in_section = {s.id for s in segments}
        fact_ids = None
        if len(sections) > 1:
            fact_ids = [f.id for f in factsheet.facts if set(f.segment_ids) & in_section]
        prompt = render(
            lang,
            "write",
            level_name=level_name(lang, level),
            level=level,
            style_guide=style_guide(lang, level),
            examples=examples(lang),
            section=title if len(sections) > 1 else "",
            factsheet=r.factsheet_text(factsheet, fact_ids, lang),
            source=r.source_lines(segments),
        )
        out, res = _call(
            llm, "write", prompt, WriteOut, model, check=_copy_check(lang, "write", _write_texts)
        )
        results += res
        for b in out.blocks:
            blocks.append(
                Block(
                    id=f"b{len(blocks) + 1:03d}",
                    kind=b.kind,  # type: ignore[arg-type]
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
    draft = Draft(
        doc_id=source.id,
        lang=lang,
        level=level,
        version=1,
        origin="write",
        blocks=drop_repeats(blocks),
        omissions=omissions,
        glossary=list(glossary.values()),
    )
    return draft, results


def _sentence_key(text: str) -> str:
    return " ".join(text.lower().split()).rstrip(".!?:")


def drop_repeats(blocks: list[Block], *, renumber: bool = True) -> list[Block]:
    """A sentence or list item that repeats an earlier one is dropped, and its fact and
    source references go to the first; a heading left without content goes too. Small
    models repeat a fact under every heading it answers (the deadline under "What must
    you do?" and again under "By when?"). After a repair the ids stay as they are."""
    kept: list[Block] = []
    first: dict[str, int] = {}
    for b in blocks:
        key = _sentence_key(b.text)
        if b.kind != "heading" and key in first:
            i = first[key]
            kept[i] = kept[i].model_copy(
                update={
                    "fact_ids": list(dict.fromkeys(kept[i].fact_ids + b.fact_ids)),
                    "segment_ids": list(dict.fromkeys(kept[i].segment_ids + b.segment_ids)),
                }
            )
            continue
        if b.kind != "heading":
            first[key] = len(kept)
        kept.append(b)
    if len(kept) == len(blocks):
        return blocks
    content = [
        b
        for k, b in enumerate(kept)
        if b.kind != "heading" or (k + 1 < len(kept) and kept[k + 1].kind != "heading")
    ]
    if not renumber:
        return content
    return [b.model_copy(update={"id": f"b{i:03d}"}) for i, b in enumerate(content, 1)]


def link_facts(draft: Draft, factsheet: FactSheet) -> Draft:
    """Bookkeeping the model need not get right: a block that contains a fact's exact
    value conveys that fact, and fact ids that do not exist are dropped."""
    known = factsheet.fact_ids()
    targets = []
    for fact in factsheet.facts:
        value = parse_value_norm(fact.value_norm, fact.kind, draft.lang)
        if value is not None:
            targets.append((fact.id, value))
    blocks = []
    for b in draft.blocks:
        ids = [f for f in b.fact_ids if f in known]
        if targets:
            values = extract_values(b.text, draft.lang)
            for fact_id, target in targets:
                if fact_id not in ids and any(matches(target, v) for v in values):
                    ids.append(fact_id)
        blocks.append(b if ids == b.fact_ids else b.model_copy(update={"fact_ids": ids}))
    return draft.model_copy(update={"blocks": blocks})


# -- judge ----------------------------------------------------------------------------


def judge(
    llm: LLMClient,
    source: SourceDocument,
    factsheet: FactSheet,
    draft: Draft,
    *,
    model: str | None = None,
) -> tuple[JudgeReport, list[LLMResult]]:
    cited = {s for b in draft.blocks for s in b.segment_ids}
    cited |= {s for f in factsheet.facts for s in f.segment_ids}
    excerpt = r.cited_source(source, cited) if cited else r.source_text(source)
    prompt = render(
        draft.lang,
        "judge",
        level_name=level_name(draft.lang, draft.level),
        factsheet=r.factsheet_text(factsheet, lang=draft.lang),
        source=excerpt,
        draft=r.draft_lines(draft, refs=False),
        glossary=r.glossary_text(draft),
    )
    out, results = _call(llm, "judge", prompt, JudgeOut, model)
    name = results[-1].usage.model if results else llm.resolve_model(model, False)[0]
    return to_judge_report(out, draft, factsheet, name), results


def to_judge_report(out: JudgeOut, draft: Draft, factsheet: FactSheet, model: str) -> JudgeReport:
    blocks = set(draft.by_id())
    facts = factsheet.fact_ids()
    seen: set[str] = set()
    checks = []
    for c in out.fact_checks:
        if c.fact_id in facts and c.fact_id not in seen:
            seen.add(c.fact_id)
            checks.append(
                FactCheck(
                    fact_id=c.fact_id,
                    status=c.status,  # type: ignore[arg-type]
                    block_ids=[b for b in c.block_ids if b in blocks],
                    note=clean_text(c.note),
                )
            )
    return JudgeReport(
        draft_version=draft.version,
        model=model,
        fact_checks=checks,
        unsupported=[
            Unsupported(block_id=u.block_id, note=clean_text(u.note))
            for u in out.unsupported
            if u.block_id in blocks
        ],
        semantic_findings=[
            SemanticFinding(block_id=s.block_id, rule_id=s.rule_id, note=clean_text(s.note))
            for s in out.semantic_findings
            if s.block_id in blocks and s.rule_id in JUDGE_RULE_IDS
        ],
    )


# -- repair ---------------------------------------------------------------------------


@dataclass
class RepairRequest:
    problems: dict[str, list[str]]  # block id -> problem lines
    missing: list[Fact]

    def __bool__(self) -> bool:
        return bool(self.problems or self.missing)


def repair(
    llm: LLMClient,
    source: SourceDocument,
    factsheet: FactSheet,
    draft: Draft,
    request: RepairRequest,
    *,
    model: str | None = None,
) -> tuple[Draft, list[LLMResult]]:
    lang = draft.lang
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
        value = label(lang, "missing_value", value=fact.value_norm) if fact.value_norm else ""
        missing_lines.append(f"- {fact.id}: {fact.text}{value}")
    prompt = render(
        draft.lang,
        "repair",
        level_name=level_name(draft.lang, draft.level),
        level=draft.level,
        style_guide=style_guide(draft.lang, draft.level),
        flagged="\n\n".join(flagged_lines) or label(lang, "none"),
        missing="\n".join(missing_lines),
        factsheet=r.factsheet_text(factsheet, lang=lang),
        draft=r.draft_lines(draft, refs=False, marked=set(request.problems)),
        source=r.cited_source(source, cited),
    )
    out, results = _call(
        llm, "repair", prompt, RepairOut, model, check=_copy_check(lang, "repair", _repair_texts)
    )
    return apply_repairs(draft, out, request, factsheet), results


def apply_repairs(
    draft: Draft, out: RepairOut, request: RepairRequest, factsheet: FactSheet
) -> Draft:
    repairs = {item.id: item.texts for item in out.repairs if item.id in request.problems}
    known_facts = factsheet.fact_ids()
    additions: dict[str | None, list] = {}
    block_ids = set(draft.by_id())
    for add in out.additions:
        key = add.after if add.after in block_ids else None
        additions.setdefault(key, []).append(add)
    used: set[str] = set()

    def new_id(base: str) -> str:
        n = 1
        while f"{base}.{n}" in used or f"{base}.{n}" in block_ids:
            n += 1
        used.add(f"{base}.{n}")
        return f"{base}.{n}"

    def key(text: str) -> str:
        return " ".join(text.lower().split()).rstrip(".!?")

    # A repair must not repeat a sentence that is already in the draft elsewhere.
    kept = {key(b.text) for b in draft.blocks if b.id not in repairs}
    blocks: list[Block] = []
    for b in draft.blocks:
        texts = repairs.get(b.id)
        if texts:
            texts = [t for t in texts if key(t) not in kept] or texts[:1]
            for i, text in enumerate(texts):
                block_id = b.id if i == 0 else new_id(b.id)
                used.add(block_id)
                blocks.append(b.model_copy(update={"id": block_id, "text": text}))
        else:
            used.add(b.id)
            blocks.append(b)
        for add in additions.get(b.id, []):
            for text in add.texts:
                if key(text) in kept or any(key(text) == key(x.text) for x in blocks):
                    continue
                blocks.append(
                    Block(
                        id=new_id(b.id),
                        kind=add.kind,
                        text=text,
                        fact_ids=[f for f in add.fact_ids if f in known_facts],
                        segment_ids=add.segment_ids,
                    )
                )
    for add in additions.get(None, []):
        for text in add.texts:
            if key(text) in kept or any(key(text) == key(x.text) for x in blocks):
                continue
            base = blocks[-1].id if blocks else "b000"
            blocks.append(
                Block(
                    id=new_id(base),
                    kind=add.kind,
                    text=text,
                    fact_ids=[f for f in add.fact_ids if f in known_facts],
                    segment_ids=add.segment_ids,
                )
            )
    return draft.model_copy(
        update={
            # An addition can land before the repaired block it repeats: drop the repeat.
            "blocks": drop_repeats(blocks, renumber=False),
            "version": draft.version + 1,
            "parent_version": draft.version,
            "origin": "repair",
        }
    )


# -- baseline (condition C0) --------------------------------------------------------


def baseline(
    llm: LLMClient, source: SourceDocument, *, level: Level, model: str | None = None
) -> tuple[Draft, list[LLMResult]]:
    """What a single chatbot prompt gives: no fact sheet, no provenance, no checks."""
    s = STAGES["baseline"]
    thinking = thinking_for(llm, "baseline")
    prompt = render(
        source.lang, "baseline", level_name=level_name(source.lang, level), text=source.text()
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
    draft = Draft(doc_id=source.id, lang=source.lang, level=level, origin="baseline", blocks=blocks)
    return draft, [result]


_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$|^\*\*(.+?)\*\*:?$")
_ITEM_RE = re.compile(r"^(?:[-*\u2022]|\d+[.)])\s+(.*)$")


def text_to_blocks(text: str, lang: str) -> list[Block]:
    """Split free model text into blocks: Markdown headings, list items, sentences."""
    nlp = nlp_pipeline(lang)
    blocks: list[Block] = []

    def add(kind: str, content: str) -> None:
        content = clean_text(content.replace("**", ""))
        if content:
            blocks.append(Block(id=f"b{len(blocks) + 1:03d}", kind=kind, text=content))  # type: ignore[arg-type]

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if m := _HEADING_RE.match(line):
            add("heading", m.group(1) or m.group(2))
        elif m := _ITEM_RE.match(line):
            add("list_item", m.group(1))
        else:
            for sent in nlp(line).sents:
                add("sentence", sent.text)
    return blocks
