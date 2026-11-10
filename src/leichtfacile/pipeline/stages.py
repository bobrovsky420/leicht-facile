"""The model stages: understand, write, judge, repair, and the single-prompt baseline.

Each stage renders its prompt, calls the model through `complete_json` (schema-checked
output with one repair round on invalid JSON), and turns the lenient model answer into
a strict artifact. Settings per stage follow docs/architecture.md §4.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache

from leichtfacile.llm.client import LLMClient, LLMResult
from leichtfacile.llm.json_out import LLMOutputError, complete_json
from leichtfacile.pipeline import render as r
from leichtfacile.pipeline.labels import label
from leichtfacile.pipeline.models import (
    JudgeOut,
    RecoverOut,
    RepairOut,
    UnderstandOut,
    WriteOut,
    clean_text,
)
from leichtfacile.pipeline.prompts import examples, level_name, render
from leichtfacile.pipeline.versions import (
    RepairRequest,
    apply_repairs,
    carries,
    drop_repeats,
    fact_window,
    repeats,
    stems,
    target_block,
    wording_key,
)
from leichtfacile.rules.checker import check_draft
from leichtfacile.rules.document import KnownValues, display_value
from leichtfacile.rules.lexicon import MEDIOPUNKT
from leichtfacile.rules.medication import has_doses, names_medication
from leichtfacile.rules.nlp import parse
from leichtfacile.rules.styleguide import style_guide
from leichtfacile.rules.value_index import ValueIndex
from leichtfacile.rules.values import (
    HARD_KINDS,
    Value,
    contains,
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
    Finding,
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
    variety_chain,
)
from leichtfacile.varieties import variety as variety_table


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


def mode_context(
    stage: str,
    mode: str = "standard",
    addressee: str | None = None,
    sender: str = "authority",
    address: str = "formal",
) -> dict:
    """The job's options in a prompt's context. The standard templates carry one line
    each, `{% if mode is defined and mode == "decision" %}{% include %}{% endif %}`,
    which renders to nothing for a standard job (same prompt, same cache key) and pulls
    in the section of the decision partial for this stage (docs/use-case-decisions.md).
    `sender` and `address` become the sender's phrases and the form's note in
    `prompts.render`; their defaults render the templates as before (31 October 2026)."""
    return {
        "mode": mode,
        "stage_name": stage,
        "addressee": addressee or "",
        "sender": sender,
        "address": address,
    }


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
    "de-CH": (
        r"\bhund(?:e|es|en|s)?\b",
        r"\bhundesteuer",
        r"\b(?:anwohner)?parkkarte",
        r"\bimpfausweis",
        r"\bfrontscheibe",
        r"\bwindschutzscheibe",
        # The office of the examples: the repair example's addition "Rufen Sie die
        # Einwohner·kontrolle an" came back with a number of the document in 4 P2 jobs of
        # the CSCS evaluation and 3 example builds (by 8 October 2026), in documents that
        # never name the office.
        r"\beinwohnerkontrolle",
        r"\bchip\b",  # "die Nummer vom Chip" of the write example
    ),
    # Germany and Austria (29 October 2026): the shared JSON example's dog tax, and the
    # examples of their own (prompts/de-DE/examples, de-AT/examples): a parking permit
    # and a dog-tax letter; the office comes from the variety's table (`_topic_patterns`).
    "de-DE": (
        r"\bhund(?:e|es|en|s)?\b",
        r"\bhundesteuer",
        r"\b(?:bewohner)?parkausweis",
        r"\bimpfausweis",
        r"\bfrontscheibe",
        r"\bwindschutzscheibe",
        r"\bchip\b",
    ),
    "de-AT": (
        r"\bhund(?:e|es|en|s)?\b",
        r"\bhunde(?:steuer|abgabe)",
        r"\bparkpickerl",
        r"\bimpf(?:ausweis|pass)",
        r"\bfrontscheibe",
        r"\bwindschutzscheibe",
        r"\bchip\b",
    ),
    "fr-CH": (
        r"\bchiens?\b",
        r"\bcarte de stationnement",
        r"\bpare-brise",
        r"\bcarnet de vaccination",
        r"\bcontrôle des habitants",
        # The dog's microchip of the write example: "le numéro de la puce" stood in five
        # sentences of a final draft about petitions in the run of 11 October 2026.
        r"\bpuce\b",
    ),
    # The Italian examples (28 October 2026) are the French ones in Italian wording:
    # the dog and its tax, the parking permit, the office and the microchip of the
    # write example. Not measured on a model yet.
    "it-CH": (
        r"\bcan[ei]\b",
        r"\btassa sui cani",
        r"\b(?:carta|contrassegno) di parcheggio",
        r"\bparabrezza",
        r"\blibretto delle vaccinazioni",
        r"\bcontrollo (?:degli )?abitanti",
        r"\bmicrochip\b",
    ),
}


def _example_key(text: str) -> str:
    # Without the compound marks: the Mediopunkt, and the hyphen between letters that
    # Germany and Austria write for it (Hunde-Steuer).
    plain = re.sub(r"(?<=[^\W\d_])-(?=[^\W\d_])", "", text.lower().replace("·", ""))
    return " ".join(plain.split()).rstrip(".!?:")


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
    return len(_copied(texts, lang, stage))


def _copied(texts: list[str], lang: str, stage: str) -> list[str]:
    keys = example_keys(lang, stage)
    return [t for t in texts if _example_key(t) in keys]


_SPECIFIC_STEMS = 3  # content words that make a sentence more than a stock phrase


def _specific(text: str, lang: str) -> bool:
    """Whether a sentence says something of its own: a hard value, or three content
    words or more (`_stems`). "Haben Sie Fragen?" and "Sie können von Montag bis Freitag
    anrufen." are stock phrases of easy language that the few-shot example shares with
    honest drafts: two of them in a draft of three sentences were a copied example, sent
    back, and a second such answer failed the stage (audit of 6 November 2026)."""
    if any(v.kind in HARD_KINDS for v in extract_values(text, lang)):
        return True
    return len(stems(text, lang.partition("-")[0])) >= _SPECIFIC_STEMS


@lru_cache(maxsize=8)
def _topic_patterns(lang: str) -> tuple[re.Pattern[str], ...]:
    words = next(
        (EXAMPLE_TOPIC_WORDS[k] for k in variety_chain(lang) if k in EXAMPLE_TOPIC_WORDS), ()
    )
    # The office of the variety's own dog-tax example (varieties.toml, `prompt.office`),
    # so a variety whose example names another office than the Swiss Einwohnerkontrolle
    # is guarded the same way.
    office = variety_table(lang).prompt.get("office")
    extra = (r"\b" + re.escape(office.lower()),) if office else ()
    return tuple(re.compile(p) for p in (*words, *extra))


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
    examples (COPY_LIMIT or more, and more than half of them, one of them saying
    something of its own, `_specific`) is sent back once with a message in the
    document's language; a second copy fails the stage. A stock phrase or two that an
    honest draft shares with an example ("Haben Sie Fragen?") is no copy."""

    def check(out) -> str | None:
        texts = texts_of(out)
        copied = _copied(texts, lang, stage)
        copies = len(copied)
        if (
            copies >= COPY_LIMIT
            and copies * 2 > len(texts)
            and any(_specific(t, lang) for t in copied)
        ):
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
        # The values themselves only at DEBUG: they are the model's words (operations.md).
        log.warning("the answer has %d values not in the document", len(seen))
        log.debug("values not in the document: %s", ", ".join(seen))
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
        check=_copy_check(source.variety, "understand", _understand_texts),
        soft_check=_topic_check(source.variety, "understand", _understand_texts, source.text()),
    )
    dropped = drop_topical(_understand_texts(out), source.variety, source.text(), "understand")
    if dropped:
        out.facts = [f for f in out.facts if f.text not in dropped]
    fs = to_factsheet(out, source.id)
    terms = [t for t in fs.hard_terms if in_source(t.term, source)]
    if len(terms) < len(fs.hard_terms):
        log.warning("understand: %d hard terms not in the source", len(fs.hard_terms) - len(terms))
        fs = fs.model_copy(update={"hard_terms": terms})
    return fs, results


def in_source(term: str, source: SourceDocument) -> bool:
    """Whether a hard term of the model is a term of the source: written there, or every
    word of it there in another form (Kantonales Einführungsgesetz, kantonalen
    Einführungsgesetz). The 8B listed the Understand example's own term for 6 documents
    of the CSCS evaluation (Einwohnerkontrolle, contrôle des habitants; 8 October 2026),
    and the writer then sent the reader to that office."""
    text = source.text()
    if term.lower().replace(MEDIOPUNKT, "") in text.lower().replace(MEDIOPUNKT, ""):
        return True
    words = set(stems(term, source.lang))
    return bool(words) and words <= set(stems(text, source.lang))


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


def _fact_values(fact: Fact, lang: str) -> list[Value]:
    """A fact's values: its normalised value, else the hard values in its text."""
    if value := parse_value_norm(fact.value_norm, fact.kind, lang):
        return [value]
    return [v for v in extract_values(fact.text, lang) if v.kind in HARD_KINDS]


def _values_agree(a: list[Value], b: list[Value]) -> bool:
    """Whether every value of the smaller list has its match in the other."""
    if not a or not b:
        return False
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    return all(any(matches(x, y) or matches(y, x) for y in large) for x in small)


def merge_twin_facts(facts: list[Fact], lang: str) -> list[Fact]:
    """One fact for one statement. The model sometimes lists a statement twice, once
    with its value and once without it in other words ("La fattura ... entro 30 giorni"
    as f04 and f15 in the school letters, 31 October 2026), and a round then adds it
    twice. Two of the model's facts that cite a common sentence, are of one kind, both
    to keep or both not, and agree in their values are one fact: the one with the
    normalised value stays, else the first, with the sentences of both."""
    kept: list[Fact] = []
    values = {f.id: _fact_values(f, lang) for f in facts}
    for fact in facts:
        twin = next(
            (
                k
                for k in kept
                if fact.origin != "code"
                and k.origin != "code"
                and k.kind == fact.kind
                and k.must_keep == fact.must_keep
                and set(k.segment_ids) & set(fact.segment_ids)
                and _values_agree(values[k.id], values[fact.id])
            ),
            None,
        )
        if twin is None:
            kept.append(fact)
            continue
        first, second = (twin, fact) if twin.value_norm or not fact.value_norm else (fact, twin)
        segments = list(dict.fromkeys([*first.segment_ids, *second.segment_ids]))
        kept[kept.index(twin)] = first.model_copy(update={"segment_ids": segments})
    return kept


def _only_value(text: str, lang: str, value: Value) -> bool:
    """Whether the value is the one hard value the text holds."""
    held = [v for v in extract_values(text, lang) if v.kind in HARD_KINDS]
    return len(held) == 1 and (matches(value, held[0]) or matches(held[0], value))


def _occurrences(
    index: ValueIndex, source: SourceDocument
) -> list[tuple[Value, list[Segment], set[str]]]:
    """Each hard value of the source text once: the segments of its first occurrence
    (the fact's sentences and text) and the ids of the segments of every occurrence. A
    later occurrence joins the first as the first covers it (`matches`, in the direction
    of `complete_factsheet`'s cover check). A value of the title alone belongs to no
    segment and makes no fact."""
    found: list[tuple[Value, list[Segment], set[str]]] = []
    by_id = source.by_id()
    for value, holders in zip(index.values, index.holders, strict=True):
        if value.kind not in HARD_KINDS or not holders:
            continue
        segments = [by_id[i] for i in holders]
        ids = set(holders)
        for first, _, everywhere in found:
            if matches(value, first):
                everywhere |= ids
                break
        else:
            found.append((value, segments, ids))
    return found


def complete_factsheet(fs: FactSheet, source: SourceDocument) -> FactSheet:
    """Code makes sure no hard value is forgotten: every date, amount, phone number,
    e-mail address, web address, percentage, time, period (`innert 30 Tagen`),
    identifier (case number, AHV number, IBAN) and postal address in the source that
    no fact carries becomes a fact of its own, or the value of the model's fact that
    holds it in its text without a normalised value. Values in passages the model
    marked as droppable become background facts; the rest must be kept. Before that,
    two of the model's facts for one statement become one (`merge_twin_facts`)."""
    lang = source.variety  # the values are read in the source's variety (de-DE: 1.500,00 €)
    facts = merge_twin_facts(list(fs.facts), lang)
    covered = [v for f in facts if (v := parse_value_norm(f.value_norm, f.kind, lang))]
    omitted = {s for o in fs.omit_candidates for s in o.segment_ids}
    # New ids follow the highest one, so none repeats an id a merge left standing.
    next_id = 1 + max((int(f.id[1:]) for f in facts if f.id[1:].isdigit()), default=0)
    # The values are taken from the document text as the evaluation's "hard facts
    # kept" takes them, not sentence by sentence: an address over two sentences
    # (`Gerichtsstrasse 12` / `8000 Musterwil`) is one value, found in neither alone
    # (the silent-loss metric showed the gap on 7 October 2026). Each value cites
    # the segments it spans.
    index = ValueIndex.of_source(source, lang)
    for value, segments, everywhere in _occurrences(index, source):
        # Covered means: a reader who searches the fact sheet for this value finds it
        # (the evaluation's silent-loss check asks the same question, in the same
        # direction). A fact with the place alone does not cover the full address,
        # and a bare number does not cover a quantity; the fact for the full value
        # is added next to the model's.
        if any(matches(value, c) for c in covered):
            continue
        covered.append(value)
        # The model's fact that holds this value in its text and cites a sentence it
        # stands in becomes the fact for it, not a second fact beside it: the 70B listed
        # "deve essere pagata entro 30 giorni" without a value, code added the period
        # again as a fact of its own, and the rounds then wrote both (31 October 2026).
        # Any occurrence counts: searched at the first alone, a fact citing the second
        # got no value and code added the deadline twice (audit of 6 November 2026).
        holder = next(
            (
                f
                for f in facts
                if f.origin != "code"
                and not f.value_norm
                and set(f.segment_ids) & everywhere
                and _only_value(f.text, lang, value)
            ),
            None,
        )
        if holder is not None:
            facts[facts.index(holder)] = holder.model_copy(
                update={"value_norm": _value_norm(value, lang)}
            )
            continue
        kind = _VALUE_KIND.get(value.kind, "other")
        cited = " ".join(seg.text for seg in segments)
        if value.kind in ("date", "period") and _DEADLINE_WORDS.search(cited):
            kind = "deadline"
        facts.append(
            Fact(
                id=f"f{next_id:02d}",
                kind=kind,
                text=cited if len(cited) <= 200 else cited[:197] + "...",
                value_norm=_value_norm(value, lang),
                segment_ids=[seg.id for seg in segments],
                must_keep=any(s.id not in omitted and s.kind != "heading" for s in segments),
                origin="code",
            )
        )
        next_id += 1
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
    lang = source.variety  # the vocabulary of the variety: Bescheid and Beschwerde in Austria
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
            kind=f.kind,
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
    sender: str = "authority",
    address: str = "formal",
) -> tuple[Draft, list[LLMResult]]:
    lang = source.lang
    variety = source.variety  # the prompts, the style guide and the examples are the variety's
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
                check=_copy_check(variety, "write", _write_texts),
                soft_check=_topic_check(variety, "write", _write_texts, source.text()),
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
        dropped = drop_topical(_write_texts(out), variety, source.text(), "write")
        for b in out.blocks:
            if b.text in dropped:
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
    draft = Draft(
        doc_id=source.id,
        lang=lang,
        region=source.region,
        level=level,
        address=address,
        version=1,
        origin="write",
        blocks=drop_repeats(blocks),
        omissions=omissions,
        glossary=list(glossary.values()),
    )
    return draft, results


# Provenance by wording (FACT-03): words of four letters or more that are no function
# words, compared by their first five letters (versée, versement; Prämien·verbilligung,
# Prämienverbilligung). One shared word alone counts from seven letters on: a content
# word (espèces), not an adverb (sofort).
_LONG_WORD = 7


def shared_stems(text: str, other: str, lang: str) -> int:
    """How many word stems two texts share (`_stems`): which of several blocks that
    carry a fact states it (rounds.build_request)."""
    return len(stems(text, lang).keys() & stems(other, lang).keys())


def wording_source(text: str, source: SourceDocument) -> str | None:
    """The source sentence a block says in other words, for a block that names neither
    a sentence nor a fact: the sentence it shares the most words with, each word
    weighted by one over the number of sentences that have it. The sentence must reach
    a weight of 1 (a word no other sentence has, or two words shared with one other
    sentence each), share two words or one long word, and outweigh every other; else
    None. In the French example letter the 8B wrote "Vous ne pouvez pas recevoir cet
    argent en espèces." without a source, so FACT-03 flagged it and the judge, which
    sees only the cited sentences, called it invented (CSCS, 8 October 2026)."""
    sentences = [s for s in source.segments if s.kind != "heading"]
    per_sentence = [set(stems(s.text, source.lang)) for s in sentences]
    count: dict[str, int] = {}
    for words in per_sentence:
        for w in words:
            count[w] = count.get(w, 0) + 1
    block = stems(text, source.lang)
    scores = sorted(
        (
            (sum(1 / count[w] for w in block.keys() & words), i)
            for i, words in enumerate(per_sentence)
        ),
        reverse=True,
    )
    if not scores or scores[0][0] < 1 or (len(scores) > 1 and scores[1][0] == scores[0][0]):
        return None
    shared = block.keys() & per_sentence[scores[0][1]]
    if len(shared) < 2 and not any(block[w] >= _LONG_WORD for w in shared):
        return None
    return sentences[scores[0][1]].id


@dataclass(frozen=True)
class _FactGroups:
    """The fact sheet as `link_facts` reads it: the ids it has, the sentences of each
    fact, and its facts in the four groups a block conveys in different ways. `of`
    builds it once per draft."""

    known: set[str]  # the sheet's fact ids
    sources_of: dict[str, list[str]]  # fact id -> its sentences
    # (fact id, its value, its sentences) of the facts with a value
    targets: list[tuple[str, Value, list[str]]]
    # (fact id, its segments) of the facts without a value that code added
    parts: list[tuple[str, set[str]]]
    # (fact id, its segments, the values in its text) of the model's others
    worded: list[tuple[str, set[str], list[Value]]]
    # (fact id, its segments) of the facts with no value anywhere
    plain: list[tuple[str, set[str]]]

    @classmethod
    def of(cls, factsheet: FactSheet, variety: str) -> _FactGroups:
        targets: list[tuple[str, Value, list[str]]] = []
        parts: list[tuple[str, set[str]]] = []
        worded: list[tuple[str, set[str], list[Value]]] = []
        plain: list[tuple[str, set[str]]] = []
        for fact in factsheet.facts:
            value = parse_value_norm(fact.value_norm, fact.kind, variety)
            if value is not None:
                targets.append((fact.id, value, fact.segment_ids))
            elif fact.origin == "code":
                parts.append((fact.id, set(fact.segment_ids)))
            elif in_text := extract_values(fact.text, variety):
                worded.append((fact.id, set(fact.segment_ids), in_text))
            elif fact.segment_ids:
                plain.append((fact.id, set(fact.segment_ids)))
        return cls(
            known=factsheet.fact_ids(),
            sources_of={f.id: f.segment_ids for f in factsheet.facts},
            targets=targets,
            parts=parts,
            worded=worded,
            plain=plain,
        )


def _same_value(target: Value, candidate: Value) -> bool:
    """`matches` for the values in a fact's text: a plain number stands for itself only,
    so "Art. 5 des Gesetzes" is not conveyed by "Das kostet 5 Franken", nor the other way
    round (audit of 6 November 2026). A fact's `value_norm` keeps `matches` as it is: a
    fact "30" written as "30 Tage" is still found."""
    if "number" in (target.kind, candidate.kind) and target.kind != candidate.kind:
        return False
    return matches(target, candidate)


def _own_sentences(b: Block, source_ids: set[str] | None) -> list[str]:
    """The source sentences the block names itself, those the source has."""
    if source_ids is None:
        return list(b.segment_ids)
    # An id the source does not have names no sentence: the 8B cited a block id
    # (`s0009.2`) in the German example letter (CSCS, 8 October 2026).
    return [s for s in b.segment_ids if s in source_ids]


def _held_facts(
    holding: list[tuple[str, Value, list[str]]], cited: set[str]
) -> list[tuple[str, list[str]]]:
    """The facts whose value the block contains (fact id, its sentences). Of two facts
    with one value (a revoked decision and a filing deadline, both of 31 March 2026), a
    block that cites a sentence of one conveys that one alone; both when it cites a
    sentence of neither. The block about the deadline used to get both, so FACT-02 was
    satisfied for the wrong fact and a judge "missing" was routed to that block (audit
    of 6 November 2026)."""
    kept: list[tuple[str, list[str]]] = []
    for fact_id, target, segments in holding:
        rivals = [
            s
            for other, t, s in holding
            if other != fact_id and (matches(target, t) or matches(t, target))
        ]
        if set(segments) & cited or not any(set(s) & cited for s in rivals):
            kept.append((fact_id, segments))
    return kept


def _cited_sentences(
    b: Block,
    facts: _FactGroups,
    held: list[tuple[str, list[str]]],
    source: SourceDocument | None,
    source_ids: set[str] | None,
) -> list[str]:
    """The source sentences a block cites. A content block that cites none (FACT-03)
    takes those of the facts whose values it contains (`held`: fact id, its sentences),
    else those of the facts it names, else, with the `source`, the sentence it says in
    other words (`wording_source`)."""
    segment_ids = _own_sentences(b, source_ids)
    if segment_ids or b.kind == "heading":
        return segment_ids
    for _, fact_segments in held:
        segment_ids += [s for s in fact_segments if s not in segment_ids]
    if not segment_ids:
        for fact_id in b.fact_ids:
            segment_ids += [s for s in facts.sources_of.get(fact_id, []) if s not in segment_ids]
    if not segment_ids and source is not None and (found := wording_source(b.text, source)):
        segment_ids = [found]
    return segment_ids


def _block_links(
    b: Block,
    facts: _FactGroups,
    variety: str,
    source: SourceDocument | None,
    source_ids: set[str] | None,
    values: list[Value],
) -> tuple[list[str], list[str]]:
    """The fact ids and the sentence ids one block ends up with: the ids it names that
    the sheet has and the facts whose value it contains (`_held_facts`), then, by the
    sentences it cites (`_cited_sentences`), the parts and plain facts of a cited
    sentence and the worded facts all of whose values it contains (`_same_value`).
    `values`: the block's values (`ValueIndex.of_blocks`)."""
    holding = [
        (fact_id, target, fact_segments)
        for fact_id, target, fact_segments in facts.targets
        if contains(target, b.text, values)
    ]
    held = _held_facts(holding, set(_own_sentences(b, source_ids)))
    segment_ids = _cited_sentences(b, facts, held, source, source_ids)
    ids = [f for f in b.fact_ids if f in facts.known]
    for fact_id, _ in held:
        if fact_id not in ids:
            ids.append(fact_id)
    for fact_id, segments in (*facts.parts, *facts.plain):
        if fact_id not in ids and segments & set(segment_ids):
            ids.append(fact_id)
    for fact_id, segments, in_text in facts.worded:
        if (
            fact_id not in ids
            and segments & set(segment_ids)
            and all(any(_same_value(t, v) for v in values) for t in in_text)
        ):
            ids.append(fact_id)
    return ids, segment_ids


def _with_spread_facts(
    blocks: list[Block], worded: list[tuple[str, set[str], list[Value]]], index: ValueIndex
) -> list[Block]:
    """The blocks with each worded fact (`_FactGroups.worded`) no block conveys yet whose
    values the writer spread over the blocks that cite its sentences (the two income
    limits in two sentences, 10 October 2026): conveyed when those blocks together hold
    every value, named on each of them that holds one."""
    for fact_id, segments, in_text in worded:
        if any(fact_id in b.fact_ids for b in blocks):
            continue
        citing = [i for i, b in enumerate(blocks) if segments & set(b.segment_ids)]
        held = {i: index.of_part(blocks[i].id) for i in citing}
        if citing and all(any(_same_value(t, v) for i in citing for v in held[i]) for t in in_text):
            for i in citing:
                if any(_same_value(t, v) for t in in_text for v in held[i]):
                    blocks[i] = blocks[i].model_copy(
                        update={"fact_ids": [*blocks[i].fact_ids, fact_id]}
                    )
    return blocks


def link_facts(draft: Draft, factsheet: FactSheet, source: SourceDocument | None = None) -> Draft:
    """Bookkeeping the model need not get right: a block that contains a fact's exact
    value conveys that fact, a block that cites a source sentence of a protected part of
    a decision (a code fact without a value, rules/decision.py) conveys that part, and
    fact ids and, with the `source`, sentence ids that do not exist are dropped. A
    block that cites no source sentence (FACT-03) takes those of the facts whose values
    it contains, else those of the facts it names, else, with the `source`, the sentence
    it says in other words (`wording_source`). A fact without a value whose text holds
    values is conveyed by a block that cites one of its sentences and contains all of
    them (FACT-02: the writer named the narrower facts of those values), or by the blocks
    that cite its sentences and together hold all of them, each that holds one (10
    October 2026). A fact without a value and without values in its text is conveyed by
    every block that cites one of its sentences (10 October 2026: the writer renders the
    sentence and leaves the tag out; the judge's fact check still reads the meaning)."""
    facts = _FactGroups.of(factsheet, draft.variety)
    source_ids = source.segment_ids() if source is not None else None
    index = ValueIndex.of_blocks(draft.blocks, draft.variety)  # the values once per block
    blocks: list[Block] = []
    for b in draft.blocks:
        ids, segment_ids = _block_links(
            b, facts, draft.variety, source, source_ids, index.of_part(b.id)
        )
        if ids == b.fact_ids and segment_ids == b.segment_ids:
            blocks.append(b)
        else:
            blocks.append(b.model_copy(update={"fact_ids": ids, "segment_ids": segment_ids}))
    blocks = _with_spread_facts(blocks, facts.worded, index)
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
    version = version if version is not None else draft.version + 1
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
        check=_copy_check(variety, "repair", _repair_texts),
        soft_check=_soft_checks(
            _topic_check(variety, "repair", _repair_texts, source.text()),
            _foreign_check(variety, known, _repair_texts),
        ),
    )
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
    topical = drop_topical(_repair_texts(out), variety, source.text(), "repair")
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
    each once, in order. Repeats (`_repeats`) are left out before the paragraph check,
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
