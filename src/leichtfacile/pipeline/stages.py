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
from leichtfacile.rules.document import KnownValues, display_value
from leichtfacile.rules.lexicon import MEDIOPUNKT
from leichtfacile.rules.nlp import pipeline as nlp_pipeline
from leichtfacile.rules.styleguide import style_guide
from leichtfacile.rules.values import (
    HARD_KINDS,
    Value,
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
    ZH_CONDITIONS,
    AnsweredAddition,
    AnsweredRepair,
    Block,
    CoreAnswer,
    CoreQuestions,
    Draft,
    DroppedText,
    Fact,
    FactCheck,
    FactSheet,
    GlossaryEntry,
    HardTerm,
    JudgeReport,
    Level,
    Omission,
    OmitCandidate,
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
}


def thinking_for(llm: LLMClient, stage: str) -> bool:
    """Whether a stage uses the thinking model (LLM_THINKING_STAGES)."""
    return stage in llm.settings.thinking_stages


def mode_context(stage: str, mode: str = "standard", addressee: str | None = None) -> dict:
    """The job mode in a prompt's context. The standard templates carry one line each,
    `{% if mode is defined and mode == "decision" %}{% include %}{% endif %}`, which
    renders to nothing for a standard job (same prompt, same cache key) and pulls in the
    section of the decision partial for this stage (docs/use-case-decisions.md)."""
    return {"mode": mode, "stage_name": stage, "addressee": addressee or ""}


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
    thinking = thinking_for(llm, stage)
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
# Words of the examples' topics (a resident parking permit, a dog tax). A sentence with
# one of them, in a document that has none, is example content even in paraphrase: on
# CSCS the 8B wrote "Sie melden neue Hunde bei der Einwohnerkontrolle an" into a page
# about EL costs, with only 2 of 12 sentences verbatim (6 October 2026). Matched on
# lowercased text without the Mediopunkt; "hundert" is not a dog.
EXAMPLE_TOPIC_WORDS: dict[str, tuple[str, ...]] = {
    "de": (
        r"\bhund(?:e|es|en|s)?\b",
        r"\bhundesteuer",
        r"\b(?:anwohner)?parkkarte",
        r"\bimpfausweis",
        r"\bfrontscheibe",
        r"\bwindschutzscheibe",
    ),
    "fr": (
        r"\bchiens?\b",
        r"\bcarte de stationnement",
        r"\bpare-brise",
        r"\bcarnet de vaccination",
    ),
}


def _example_key(text: str) -> str:
    return " ".join(text.lower().replace("·", "").split()).rstrip(".!?:")


def _static_renders(lang: str, stage: str) -> list[str]:
    """The prompt without its document, once per level where the level matters: the
    instructions, the JSON example, the style guide (write and repair) and the few-shot
    pairs (write). The style guide is in since 8 October 2026: a decision-mode draft on
    the 8B carried the write prompt's style guide as a section of the draft."""
    levels = ("A2", "B1") if "style_guide" in _STATIC_CONTEXT[stage] else ("A2",)
    renders = []
    for level in levels:
        context = dict(_STATIC_CONTEXT[stage], level=level, level_name=level_name(lang, level))
        if "style_guide" in context:
            context["style_guide"] = style_guide(lang, level)
        context.update(mode_context(stage))
        if stage == "write":
            context["examples"] = examples(lang)
        renders.append(render(lang, stage, **context))
    return renders


@lru_cache(maxsize=16)
def example_keys(lang: str, stage: str) -> frozenset[str]:
    """The sentences of a prompt's own examples and style guide, normalised, to
    recognise an answer that copies them. On the Public AI 8B, 4 of 12 dev drafts were
    the write prompt's JSON example, word for word (6 October 2026). A list marker in
    front of a line (the style guide's `- `) is not part of the key."""
    keys: set[str] = set()
    for text in _static_renders(lang, stage):
        keys |= {_example_key(line.lstrip(" -*")) for line in text.splitlines()}
        keys |= {_example_key(q) for q in _QUOTED.findall(text)}
    return frozenset(k for k in keys if len(k) >= 12)


def copied_sentences(texts: list[str], lang: str, stage: str) -> int:
    keys = example_keys(lang, stage)
    return sum(1 for t in texts if _example_key(t) in keys)


@lru_cache(maxsize=8)
def _topic_patterns(lang: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p) for p in EXAMPLE_TOPIC_WORDS.get(lang, ()))


@lru_cache(maxsize=16)
def example_values(lang: str, stage: str) -> tuple[Value, ...]:
    """The dates, amounts, phone numbers, addresses and times of a prompt's examples
    and style guide (`044 123 45 67`, `4. Februar 2026`), one Value per canonical."""
    values: dict[tuple[str, str], Value] = {}
    for text in _static_renders(lang, stage):
        for v in extract_values(text, lang):
            if v.kind in HARD_KINDS:
                values.setdefault(v.key, v)
    return tuple(values.values())


def topic_sentences(
    texts: list[str], lang: str, source_text: str, stage: str = "write"
) -> list[str]:
    """The texts about the examples' topics, or with one of the examples' values (their
    phone numbers, dates, amounts and hours), that the source does not have. In the
    first evaluation run on CSCS the examples' phone number and date stood in 4 of 19
    P2 drafts, in sentences without a topic word (6 October 2026)."""
    source = _example_key(source_text)
    patterns = [p for p in _topic_patterns(lang) if not p.search(source)]
    source_values = extract_values(source_text, lang)
    foreign = [
        v for v in example_values(lang, stage) if not any(matches(v, s) for s in source_values)
    ]

    def topical(text: str) -> bool:
        if any(p.search(_example_key(text)) for p in patterns):
            return True
        return any(matches(e, v) for v in extract_values(text, lang) for e in foreign)

    return [t for t in texts if topical(t)]


def _copy_check(lang: str, stage: str, texts_of):
    """A `check` for complete_json: an answer whose sentences are mostly from the prompt's
    examples (COPY_LIMIT or more, and more than half of them) is sent back once with a
    message in the document's language; a second copy fails the stage. A generic
    sentence or two that an honest draft shares with an example ("Sie haben dafür 14
    Tage Zeit.") is no copy."""

    def check(out) -> str | None:
        texts = texts_of(out)
        copies = copied_sentences(texts, lang, stage)
        if copies >= COPY_LIMIT and copies * 2 > len(texts):
            log.warning("stage %s: the answer copies %d sentences of the example", stage, copies)
            return label(lang, "copied_example", count=copies)
        return None

    return check


def _topic_check(lang: str, stage: str, texts_of, source_text: str):
    """A soft `check` for complete_json: an answer with sentences about the examples'
    topics, in a document that has none, is sent back once; what the second answer
    still has, the stage drops (`drop_topical`). One such sentence is not worth a
    failed stage: on CSCS two P1 jobs failed over a single one (6 October 2026)."""

    def check(out) -> str | None:
        topical = topic_sentences(texts_of(out), lang, source_text, stage)
        if topical:
            log.warning("stage %s: %d sentences about the examples' topics", stage, len(topical))
            return label(lang, "copied_example", count=len(topical))
        return None

    return check


def _soft_checks(*checks):
    """One soft check from several: the first message wins."""

    def check(out) -> str | None:
        for c in checks:
            message = c(out)
            if message is not None:
                return message
        return None

    return check


def drop_topical(texts: list[str], lang: str, source_text: str, stage: str) -> set[str]:
    """The texts a stage drops from the answer it uses: still about the examples' topics."""
    dropped = set(topic_sentences(texts, lang, source_text, stage))
    if dropped:
        log.warning("dropping %d sentences about the examples' topics", len(dropped))
    return dropped


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


def _foreign_check(lang: str, known: KnownValues, texts_of):
    """A `check` for complete_json: an answer with a date, amount, phone number, e-mail
    or web address, percentage or time that neither the source nor the fact sheet
    contains (the check of rule FACT-06) is sent back with the values named. Used as a
    soft check, so the stage never fails because of it. On the Public AI 8B the repair
    additions carried the examples' phone number into 8 of 12 dev drafts (6 October
    2026)."""

    def check(out) -> str | None:
        seen: dict[str, None] = {}
        for text in texts_of(out):
            for value in known.foreign(text):
                seen.setdefault(value.text, None)
        if not seen:
            return None
        log.warning("the answer has values not in the document: %s", ", ".join(seen))
        return label(lang, "foreign_values", values=", ".join(seen))

    return check


# -- understand -----------------------------------------------------------------------


def understand(
    llm: LLMClient,
    source: SourceDocument,
    *,
    level: Level,
    model: str | None = None,
    mode: str = "standard",
    addressee: str | None = None,
) -> tuple[FactSheet, list[LLMResult]]:
    prompt = render(
        source.lang,
        "understand",
        **mode_context("understand", mode, addressee),
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
        soft_check=_topic_check(source.lang, "understand", _understand_texts, source.text()),
    )
    dropped = drop_topical(_understand_texts(out), source.lang, source.text(), "understand")
    if dropped:
        out.facts = [f for f in out.facts if f.text not in dropped]
    return to_factsheet(out, source.id), results


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


def complete_factsheet(fs: FactSheet, source: SourceDocument) -> FactSheet:
    """Code makes sure no hard value is forgotten: every date, amount, phone number,
    e-mail address, web address, percentage, time, period (`innert 30 Tagen`),
    identifier (case number, AHV number, IBAN) and postal address in the source that
    no fact carries becomes a fact of its own. Values in passages the model marked as
    droppable become background facts; the rest must be kept."""
    lang = source.lang
    covered = [v for f in fs.facts if (v := parse_value_norm(f.value_norm, f.kind, lang))]
    omitted = {s for o in fs.omit_candidates for s in o.segment_ids}
    facts = list(fs.facts)
    # The values are taken from the document text as the evaluation's "hard facts
    # kept" takes them, not sentence by sentence: an address over two sentences
    # (`Gerichtsstrasse 12` / `8000 Musterwil`) is one value, found in neither alone
    # (the silent-loss metric showed the gap on 7 October 2026). Each value cites
    # the segments it spans.
    text, spans = source.text_with_offsets()
    for value in extract_values(text, lang):
        # Covered means: a reader who searches the fact sheet for this value finds it
        # (the evaluation's silent-loss check asks the same question, in the same
        # direction). A fact with the place alone does not cover the full address,
        # and a bare number does not cover a quantity; the fact for the full value
        # is added next to the model's.
        if value.kind not in HARD_KINDS or any(matches(value, c) for c in covered):
            continue
        segments = [
            seg
            for seg, (start, end) in zip(source.segments, spans, strict=True)
            if start < value.end and value.start < end
        ]
        if not segments:
            continue
        covered.append(value)
        kind = _VALUE_KIND.get(value.kind, "other")
        cited = " ".join(seg.text for seg in segments)
        if value.kind in ("date", "period") and _DEADLINE_WORDS.search(cited):
            kind = "deadline"
        facts.append(
            Fact(
                id=f"f{len(facts) + 1:02d}",
                kind=kind,  # type: ignore[arg-type]
                text=cited if len(cited) <= 200 else cited[:197] + "...",
                value_norm=_value_norm(value, lang),
                segment_ids=[seg.id for seg in segments],
                must_keep=any(s.id not in omitted and s.kind != "heading" for s in segments),
                origin="code",
            )
        )
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
    lang = source.lang
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
    mode: str = "standard",
    addressee: str | None = None,
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
    pending = list(sections)
    sectioned = len(sections) > 1
    while pending:
        title, segments = pending.pop(0)
        in_section = {s.id for s in segments}
        fact_ids = None
        if sectioned:
            fact_ids = [f.id for f in factsheet.facts if set(f.segment_ids) & in_section]
        prompt = render(
            lang,
            "write",
            **mode_context("write", mode, addressee),
            level_name=level_name(lang, level),
            level=level,
            style_guide=style_guide(lang, level),
            examples=examples(lang),
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
                check=_copy_check(lang, "write", _write_texts),
                soft_check=_topic_check(lang, "write", _write_texts, source.text()),
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
        dropped = drop_topical(_write_texts(out), lang, source.text(), "write")
        for b in out.blocks:
            if b.text in dropped:
                continue
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
    # Without the Mediopunkt: a repair that writes Krankenversicherung repeats the
    # Kranken·versicherung sentence code split earlier (rules/mediopunkt.py).
    return " ".join(text.lower().replace(MEDIOPUNKT, "").split()).rstrip(".!?:")


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
    value conveys that fact, a block that cites a source sentence of a protected part of
    a decision (a code fact without a value, rules/decision.py) conveys that part, and
    fact ids that do not exist are dropped."""
    known = factsheet.fact_ids()
    targets = []
    parts = []  # (fact id, its segments) of the facts without a value that code added
    for fact in factsheet.facts:
        value = parse_value_norm(fact.value_norm, fact.kind, draft.lang)
        if value is not None:
            targets.append((fact.id, value))
        elif fact.origin == "code":
            parts.append((fact.id, set(fact.segment_ids)))
    blocks = []
    for b in draft.blocks:
        ids = [f for f in b.fact_ids if f in known]
        if targets:
            values = extract_values(b.text, draft.lang)
            for fact_id, target in targets:
                if fact_id not in ids and any(matches(target, v) for v in values):
                    ids.append(fact_id)
        for fact_id, segments in parts:
            if fact_id not in ids and segments & set(b.segment_ids):
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
    mode: str = "standard",
    addressee: str | None = None,
) -> tuple[JudgeReport, list[LLMResult]]:
    cited = {s for b in draft.blocks for s in b.segment_ids}
    cited |= {s for f in factsheet.facts for s in f.segment_ids}
    excerpt = r.cited_source(source, cited) if cited else r.source_text(source)
    prompt = render(
        draft.lang,
        "judge",
        **mode_context("judge", mode, addressee),
        level_name=level_name(draft.lang, draft.level),
        factsheet=r.factsheet_text(factsheet, lang=draft.lang),
        source=excerpt,
        draft=r.draft_lines(draft, refs=False),
        glossary=r.glossary_text(draft),
    )
    out, results = _call(llm, "judge", prompt, JudgeOut, model)
    name = results[-1].usage.model if results else llm.resolve_model(model, False)[0]
    return to_judge_report(out, draft, factsheet, name, mode=mode), results


def to_judge_report(
    out: JudgeOut, draft: Draft, factsheet: FactSheet, model: str, *, mode: str = "standard"
) -> JudgeReport:
    rule_ids = JUDGE_RULE_IDS | (DECISION_JUDGE_RULE_IDS if mode == "decision" else set())
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
            if s.block_id in blocks and s.rule_id in rule_ids
        ],
    )


# -- repair ---------------------------------------------------------------------------


@dataclass
class RepairRequest:
    problems: dict[str, list[str]]  # block id -> problem lines
    missing: list[Fact]

    def __bool__(self) -> bool:
        return bool(self.problems or self.missing)


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
    kind: str = "repair",
    version: int | None = None,
) -> tuple[Draft, list[LLMResult], RepairRecord]:
    """One repair round. Returns the new draft version, the model calls and the record
    of the round: what was asked, what the model answered, what code left out.
    `version`: the new version's number, when it is not the next after `draft` (the
    vocabulary round starts from the best version, not the latest)."""
    version = version if version is not None else draft.version + 1
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
        missing_lines.append(f"- {fact.id}: {fact.text}{missing_value_label(fact, lang)}")
    prompt = render(
        draft.lang,
        "repair",
        **mode_context("repair", mode, addressee),
        level_name=level_name(draft.lang, draft.level),
        level=draft.level,
        style_guide=style_guide(draft.lang, draft.level),
        flagged="\n\n".join(flagged_lines) or label(lang, "none"),
        missing="\n".join(missing_lines),
        factsheet=r.factsheet_text(factsheet, lang=lang),
        draft=r.draft_lines(draft, refs=False, marked=set(request.problems)),
        source=r.cited_source(source, cited),
    )
    known = KnownValues.of(source, factsheet, lang)
    out, results = _call(
        llm,
        "repair",
        prompt,
        RepairOut,
        model,
        check=_copy_check(lang, "repair", _repair_texts),
        soft_check=_soft_checks(
            _topic_check(lang, "repair", _repair_texts, source.text()),
            _foreign_check(lang, known, _repair_texts),
        ),
    )
    record = RepairRecord(
        draft_version=version,
        parent_version=draft.version,
        kind=kind,  # type: ignore[arg-type]
        requested_blocks=list(request.problems),
        requested_facts=[f.id for f in request.missing],
        repairs=[AnsweredRepair(block_id=i.id, texts=list(i.texts)) for i in out.repairs],
        additions=[
            AnsweredAddition(after=a.after, texts=list(a.texts), fact_ids=list(a.fact_ids))
            for a in out.additions
        ],
    )
    topical = drop_topical(_repair_texts(out), lang, source.text(), "repair")
    if topical:
        for item in out.repairs:
            record.dropped += [
                DroppedText(text=t, reason="example", block_id=item.id)
                for t in item.texts
                if t in topical
            ]
            item.texts = [t for t in item.texts if t not in topical]
        out.repairs = [item for item in out.repairs if item.texts]
        for add in out.additions:
            record.dropped += [
                DroppedText(text=t, reason="example", block_id=add.after, fact_ids=add.fact_ids)
                for t in add.texts
                if t in topical
            ]
            add.texts = [t for t in add.texts if t not in topical]
        out.additions = [add for add in out.additions if add.texts]
    new_draft = apply_repairs(
        draft, out, request, factsheet, dropped=record.dropped, version=version
    )
    return new_draft, results, record


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
    repairs = {item.id: item.texts for item in out.repairs if item.id in request.problems}
    for item in out.repairs:
        if item.id not in request.problems:  # the prompt says: only the flagged blocks
            dropped += [
                DroppedText(text=t, reason="not_flagged", block_id=item.id) for t in item.texts
            ]
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
        return " ".join(text.lower().replace(MEDIOPUNKT, "").split()).rstrip(".!?")

    # A repair must not repeat a sentence that is already in the draft elsewhere.
    kept = {key(b.text) for b in draft.blocks if b.id not in repairs}
    blocks: list[Block] = []
    for b in draft.blocks:
        texts = repairs.get(b.id)
        if texts:
            fresh = [t for t in texts if key(t) not in kept] or texts[:1]
            dropped += [
                DroppedText(text=t, reason="repeat", block_id=b.id) for t in texts if t not in fresh
            ]
            texts = fresh
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
                    dropped.append(
                        DroppedText(
                            text=text, reason="repeat", block_id=b.id, fact_ids=add.fact_ids
                        )
                    )
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
                dropped.append(DroppedText(text=text, reason="repeat", fact_ids=add.fact_ids))
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
    # An addition can land before the repaired block it repeats: drop the repeat.
    final_blocks = drop_repeats(blocks, renumber=False)
    if len(final_blocks) != len(blocks):
        left = {b.id for b in final_blocks}
        dropped += [
            DroppedText(text=b.text, reason="repeat", block_id=b.id, fact_ids=b.fact_ids)
            for b in blocks
            if b.id not in left and b.kind != "heading"
        ]
    return draft.model_copy(
        update={
            "blocks": final_blocks,
            "version": version if version is not None else draft.version + 1,
            "parent_version": draft.version,
            "origin": "repair",
            "code_edits": [],  # each version records the edits made on it
        }
    )


# -- baseline (condition P0) --------------------------------------------------------


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
    `strip_markdown` is not applied: it deletes every underscore, so web and e-mail
    addresses would break (docs/prompts.md)."""
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
    thinking = thinking_for(llm, "baseline")
    context = {"variant": variant, "text": source.text()}
    messages = [
        {"role": part, "content": render(source.lang, "baseline_zh", part=part, **context)}
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
    draft = Draft(doc_id=source.id, lang=source.lang, level=level, origin="baseline", blocks=blocks)
    return draft, [result], [] if tagged else [ZH_NO_TAGS_NOTE]


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
