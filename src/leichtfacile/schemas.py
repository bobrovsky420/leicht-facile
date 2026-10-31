"""Artifacts of the pipeline (docs/architecture.md §5).

Every stage reads and writes these models; the store keeps them as JSON. The models
the language model answers with are separate (see `leichtfacile.pipeline`), so the
model never has to produce bookkeeping fields such as ids of the job or versions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

Lang = Literal["de", "fr", "it"]
# The national variety of the language: Switzerland (the project's home, the default of
# every stored artifact without the field), Germany or Austria. One setting per
# installation (`texts.region`, set by `leichtfacile setup`), carried by the job, the
# source and the drafts; it shapes German only, French and Italian are always Swiss.
Region = Literal["CH", "DE", "AT"]
Level = Literal["A2", "B1"]
Severity = Literal["error", "warn", "info"]
SegmentKind = Literal["heading", "paragraph", "list_item", "table_cell"]
BlockKind = Literal["heading", "sentence", "list_item"]
FactKind = Literal[
    "deadline",
    "amount",
    "obligation",
    "right",
    "condition",
    "contact",
    "procedure",
    "definition",
    "medication",
    "other",
]
SourceType = Literal["text", "html", "pdf", "image"]
DraftOrigin = Literal["write", "repair", "baseline", "review"]
FactStatus = Literal["present", "missing", "distorted"]
DecisionKind = Literal["approved", "edited", "rejected"]
JobStatus = Literal["queued", "running", "needs_review", "done", "failed"]
# standard: any official text. decision: the letter that goes out with a decision of an
# authority or a court (docs/use-case-decisions.md): the operative part and the appeal
# instructions are untouchable, the text speaks to one named person, and the export
# carries the authority's fixed notice. A job option, never an evaluation condition.
JobMode = Literal["standard", "decision"]
JOB_MODES: tuple[str, ...] = get_args(JobMode)
# The sender a job names (senders/senders.toml): the prompts call the source an official
# text, a school's or an organisation's. authority renders the prompts as before the
# option existed (31 October 2026).
Sender = Literal["authority", "school", "organisation"]
SENDERS: tuple[str, ...] = get_args(Sender)
# The form in which the text addresses its reader: formal (Sie, vous, Lei), informal
# (du, tu) or plural (ihr, vous, voi). The style guide's line for LEX-06, the checker's
# hint and a note in the write, repair and recover prompts follow it.
Address = Literal["formal", "informal", "plural"]
ADDRESS_FORMS: tuple[str, ...] = get_args(Address)
# P as in pipeline: the letter C would read as a CEFR level next to A2 and B1.
Condition = Literal["P0", "P0-ZH-complete", "P0-ZH-condensed", "P1", "P2"]
CONDITIONS: tuple[str, ...] = get_args(Condition)
# The conditions were called C0 to C2 until 6 October 2026. A store with the old names
# is rewritten when it is opened (store.py); the evaluation's result rows written before
# are read through `canonical_condition` (eval/report.py). The models take P names only.
CONDITION_ALIASES: dict[str, str] = {f"C{c[1:]}": c for c in CONDITIONS}


def canonical_condition(name: str) -> str:
    """The current name of a condition: `C2` becomes `P2`; unknown names pass through."""
    return CONDITION_ALIASES.get(name, name)


# Single-prompt baselines: no fact sheet, no judge, no repair. P0 is one sentence; the
# P0-ZH pair is the Canton of Zurich's Leichte Sprache prompt (THIRD_PARTY_NOTICES.md)
# with its "keep everything" or its "essentials only" instruction.
ZH_CONDITIONS: frozenset[str] = frozenset({"P0-ZH-complete", "P0-ZH-condensed"})
BASELINE_CONDITIONS: frozenset[str] = frozenset({"P0"}) | ZH_CONDITIONS

LANGS: tuple[Lang, ...] = ("de", "fr", "it")
REGIONS: tuple[Region, ...] = ("CH", "DE", "AT")
LEVELS: tuple[Level, ...] = ("A2", "B1")


def variety(lang: str, region: str = "CH") -> str:
    """The key of a language's national variety, the language and its region: `de-CH`,
    `de-DE`, `de-AT`, `fr-CH`, `it-CH`. The variety tables, the few-shot examples, the
    rule checks and guides and the vocabulary are looked up by this key and fall back
    along `variety_chain`. The Swiss keys were the bare language codes until 29 October
    2026; a bare code still names the Swiss variety wherever a key is taken."""
    return f"{lang}-{region}"


def canonical_variety(key: str) -> str:
    """A variety key as the tables name it: a bare language code (`de`) is its Swiss
    variety (`de-CH`), a key with a region is itself."""
    return key if "-" in key else variety(key)


def base_lang(key: str) -> str:
    """The language of a variety key: `de` for `de-AT` and `de-CH`; a plain language code
    as it is."""
    return key.partition("-")[0]


def variety_chain(key: str) -> tuple[str, ...]:
    """The keys a lookup by a variety tries, in order: the key itself (`de-AT`), the
    language's Swiss variety (`de-CH`, which every language has) and the language (`de`,
    what the varieties share). The prompt folders, the rule checks and guides, the
    shared checks' tables and the vocabulary files resolve along it, so a variety brings
    its own where it differs and inherits the rest, and an unknown variety of a language
    reads as its Swiss one."""
    key = canonical_variety(key)
    lang = base_lang(key)
    return tuple(dict.fromkeys((key, variety(lang), lang)))


SEVERITY_RANK: dict[str, int] = {"error": 0, "warn": 1, "info": 2}
# The rounds after the first draft, in the order the plan runs them (pipeline/rounds.py):
# repair (the loop on the findings), facts (the missing must-keep values alone), recover
# (each missing value with its source paragraph), polish (the rule findings of the best
# version) and vocabulary (the office words of the best version).
RoundKind = Literal["repair", "facts", "recover", "polish", "vocabulary"]
ROUND_KINDS: tuple[str, ...] = get_args(RoundKind)
# Why the repair and facts rounds ended; the interface translates the code (`stop.<code>`).
# max_rounds and max_facts_rounds carry the count of rounds of their kind.
StopReason = Literal[
    "baseline",
    "p1",
    "no_problems",
    "no_blocking",
    "round_failed",
    "no_progress",
    "max_rounds",
    "no_missing_facts",
    "facts_round_failed",
    "facts_no_progress",
    "max_facts_rounds",
]
STOP_REASONS: tuple[str, ...] = get_args(StopReason)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")


# -- source ------------------------------------------------------------------------


class SourceInfo(Artifact):
    type: SourceType
    uri: str | None = None  # URL or uploaded file name
    fetched_at: datetime | None = None
    license_note: str | None = None


class Segment(Artifact):
    """One sentence of the source (or one heading, list item or table cell)."""

    id: str  # s0001, s0002, ... in document order
    kind: SegmentKind
    text: str
    heading_path: list[str] = Field(default_factory=list)
    heading_level: int | None = None  # 1-6 for headings, else None
    para: int = 0  # index of the paragraph or list item the sentence belongs to
    page: int | None = None  # PDF page, 1-based


class SourceDocument(Artifact):
    id: str
    lang: Lang
    region: Region = "CH"  # the national variety the job reads the text in
    title: str | None = None
    source: SourceInfo
    segments: list[Segment]

    @property
    def variety(self) -> str:
        return variety(self.lang, self.region)

    def segment_ids(self) -> set[str]:
        return {s.id for s in self.segments}

    def by_id(self) -> dict[str, Segment]:
        return {s.id: s for s in self.segments}

    def text(self) -> str:
        """Plain text: paragraphs separated by blank lines, sentences by spaces."""
        return self.text_with_offsets()[0]

    def text_with_offsets(self) -> tuple[str, list[tuple[int, int]]]:
        """The plain text and, per segment, its character span in it, so that a value
        found in the text (an address over two sentences) can be traced to the
        segments it spans."""
        parts: list[str] = []
        spans: list[tuple[int, int]] = []
        position = 0
        last_para: int | None = None
        for seg in self.segments:
            if parts:
                separator = "\n\n" if seg.para != last_para else " "
                parts.append(separator)
                position += len(separator)
            parts.append(seg.text)
            spans.append((position, position + len(seg.text)))
            position += len(seg.text)
            last_para = seg.para
        return "".join(parts), spans

    def word_count(self) -> int:
        return sum(len(s.text.split()) for s in self.segments)


# -- fact sheet --------------------------------------------------------------------


class CoreAnswer(Artifact):
    text: str | None = None  # None: the source does not answer the question
    segment_ids: list[str] = Field(default_factory=list)


class CoreQuestions(Artifact):
    what: CoreAnswer = Field(default_factory=CoreAnswer)
    must_do: CoreAnswer = Field(default_factory=CoreAnswer)
    deadline: CoreAnswer = Field(default_factory=CoreAnswer)
    cost: CoreAnswer = Field(default_factory=CoreAnswer)
    contact: CoreAnswer = Field(default_factory=CoreAnswer)


class Fact(Artifact):
    id: str  # f01, f02, ...
    kind: FactKind
    text: str
    # Canonical value for the exact check (rules.md FACT-01): ISO date (2026-03-31 or
    # --03-31 without year), amount as decimal number (500 or 1500.50), phone as
    # digits (0441234567), e-mail, URL, percent (10%), time (09:00), period in words
    # (30 Tage), identifier as written (2026-0042, 756.1234.5678.97), postal address
    # (Gerichtsstrasse 12, 8000 Musterwil), a medication by its name (Dafalgan).
    value_norm: str | None = None
    segment_ids: list[str] = Field(default_factory=list)
    must_keep: bool = True
    origin: Literal["model", "code"] = "model"  # code: a value the model left out


class HardTerm(Artifact):
    term: str
    explanation: str
    segment_ids: list[str] = Field(default_factory=list)
    # vocabulary: the explanation is the vocabulary's (rules/vocabulary.py), the term the
    # model's or, for a term code added, the vocabulary's
    origin: Literal["model", "vocabulary"] = "model"


class OmitCandidate(Artifact):
    segment_ids: list[str]
    reason: str


class FactSheet(Artifact):
    doc_id: str
    doc_type: str = ""
    audience: str = ""
    core: CoreQuestions = Field(default_factory=CoreQuestions)
    facts: list[Fact] = Field(default_factory=list)
    hard_terms: list[HardTerm] = Field(default_factory=list)
    omit_candidates: list[OmitCandidate] = Field(default_factory=list)

    def fact_ids(self) -> set[str]:
        return {f.id for f in self.facts}

    def must_keep(self) -> list[Fact]:
        return [f for f in self.facts if f.must_keep]


# -- draft -------------------------------------------------------------------------


class Block(Artifact):
    id: str  # b001, b002, ...; repairs that split a block add .1, .2
    kind: BlockKind
    text: str
    fact_ids: list[str] = Field(default_factory=list)
    segment_ids: list[str] = Field(default_factory=list)


class Omission(Artifact):
    what: str
    why: str
    segment_ids: list[str] = Field(default_factory=list)


class GlossaryEntry(Artifact):
    term: str
    explanation: str
    origin: Literal["model", "vocabulary"] = "model"  # vocabulary: added by code


class CodeEdit(Artifact):
    """A word the pipeline changed by code, not by the model (rules/mediopunkt.py):
    `Krankenversicherungspolice` to `Kranken·versicherungs·police`."""

    block_id: str  # a block id, or "glossary" for a glossary term
    rule_id: str  # the rule the edit satisfies, LEX-01
    before: str
    after: str


class Draft(Artifact):
    doc_id: str
    lang: Lang
    region: Region = "CH"  # the national variety the draft is written and checked in
    level: Level
    address: Address = "formal"  # the form of address the text is written and checked in
    version: int = 1
    parent_version: int | None = None
    origin: DraftOrigin = "write"
    blocks: list[Block]
    omissions: list[Omission] = Field(default_factory=list)
    glossary: list[GlossaryEntry] = Field(default_factory=list)
    code_edits: list[CodeEdit] = Field(default_factory=list)  # made on this version

    @property
    def variety(self) -> str:
        return variety(self.lang, self.region)

    def by_id(self) -> dict[str, Block]:
        return {b.id: b for b in self.blocks}

    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)


# -- checks ------------------------------------------------------------------------


class Finding(Artifact):
    block_id: str | None  # None: the finding concerns the whole document
    rule_id: str
    severity: Severity
    # The message as a template key and its values (rules/messages.py): English through
    # `messages.render`, the interface languages through the catalogs (`finding.<key>`).
    key: str
    params: dict[str, str | int | float] = Field(default_factory=dict)
    evidence: str = ""
    suggestion: str | None = None
    fact_id: str | None = None  # FACT-01, FACT-02, FACT-05: the fact concerned
    segment_ids: list[str] = Field(default_factory=list)  # FACT-04: unexplained segments


class DocMetrics(Artifact):
    blocks: int = 0
    sentences: int = 0
    words: int = 0
    avg_words: float = 0.0
    max_words: int = 0
    pct_passive: float = 0.0
    pct_genitive: float = 0.0
    pct_subordinate: float = 0.0
    readability: float | None = None
    readability_formula: str | None = None
    facts_total: int = 0
    facts_found: int = 0
    fact_coverage: float | None = None  # None when the fact sheet has no checkable facts


class RuleFindings(Artifact):
    draft_version: int
    level: Level
    findings: list[Finding] = Field(default_factory=list)
    metrics: DocMetrics = Field(default_factory=DocMetrics)

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity == severity)

    def for_block(self, block_id: str) -> list[Finding]:
        return [f for f in self.findings if f.block_id == block_id]


class FactCheck(Artifact):
    fact_id: str
    status: FactStatus
    block_ids: list[str] = Field(default_factory=list)
    note: str = ""


class Unsupported(Artifact):
    block_id: str
    # The words of the block the source does not cover, as the judge quoted them; code
    # keeps a verdict only when its quote stands in a block of the draft (10 Oct 2026).
    quote: str | None = None
    note: str = ""


class SemanticFinding(Artifact):
    block_id: str
    rule_id: str  # SEM-01 ... SEM-05, SEM-08; SEM-09 and SEM-10 in decision mode
    note: str = ""


class JudgeReport(Artifact):
    draft_version: int
    model: str
    fact_checks: list[FactCheck] = Field(default_factory=list)
    unsupported: list[Unsupported] = Field(default_factory=list)
    semantic_findings: list[SemanticFinding] = Field(default_factory=list)
    # Unsupported verdicts whose quote stands in no block of the draft: kept for the
    # audit, counted nowhere (since 10 October 2026).
    dropped: list[Unsupported] = Field(default_factory=list)

    def problem_block_ids(self) -> set[str]:
        ids = {u.block_id for u in self.unsupported}
        ids |= {s.block_id for s in self.semantic_findings}
        for fc in self.fact_checks:
            if fc.status == "distorted":
                ids |= set(fc.block_ids)
        return ids


# -- repair rounds -------------------------------------------------------------------


DropReason = Literal["repeat", "example", "not_flagged", "conveyed", "no_value"]


class DroppedText(Artifact):
    """A sentence of a repair answer that code left out of the new version: a repeat of
    a sentence the draft already has, a sentence about the prompt's examples, the
    repair of a block the round had not flagged, an addition for facts the draft
    already conveys, none of them asked for (`conveyed`), or an addition asked for a
    value that brings none of it (`no_value`; both since 31 October 2026)."""

    text: str
    reason: DropReason
    block_id: str | None = None  # the repaired block, or the block the addition follows
    fact_ids: list[str] = Field(default_factory=list)


class AnsweredRepair(Artifact):
    block_id: str
    texts: list[str]


class AnsweredAddition(Artifact):
    after: str | None = None
    texts: list[str]
    fact_ids: list[str] = Field(default_factory=list)


class RepairRecord(Artifact):
    """What a repair round asked for and what the model answered, before code applied
    it (one per round, stored under the version the round produced). The fact-retention
    diagnosis (`eval diagnose`) reads it to tell a fact the model never wrote from one
    it wrote in a form FACT-01 does not accept or one that code dropped."""

    draft_version: int  # the version the round produced
    parent_version: int
    kind: RoundKind = "repair"
    requested_blocks: list[str] = Field(default_factory=list)  # blocks with problems
    requested_facts: list[str] = Field(default_factory=list)  # missing facts asked for
    repairs: list[AnsweredRepair] = Field(default_factory=list)
    additions: list[AnsweredAddition] = Field(default_factory=list)
    dropped: list[DroppedText] = Field(default_factory=list)


# -- review ------------------------------------------------------------------------


class Decision(Artifact):
    block_id: str
    decision: DecisionKind
    text: str | None = None  # the edited text, for "edited"
    comment: str | None = None
    at: datetime = Field(default_factory=utcnow)


class ReviewState(Artifact):
    draft_version: int
    decisions: list[Decision] = Field(default_factory=list)
    completed: bool = False
    # When the server stored this review. A save names the value it loaded, so two
    # reviewers cannot overwrite each other without noticing (web/api.py). None only in
    # a review that was never stored (the reader view of unsaved decisions).
    saved_at: datetime | None = None

    def by_block(self) -> dict[str, Decision]:
        return {d.block_id: d for d in self.decisions}


# -- the rounds after the first draft -------------------------------------------------


class PipelineOptions(Artifact):
    """The rounds after the first draft (docs/architecture.md §4.6)."""

    repair_rounds: int = Field(
        3, ge=0, le=10, description="Repair rounds on the rule findings and the judge's; 0: none."
    )
    facts_rounds: int = Field(
        1,
        ge=0,
        le=5,
        description="Rounds that ask only for the must-keep facts still missing after the "
        "repair rounds; 0: none.",
    )
    # 10 since the dev rerun of 7 October 2026 (docs/prompts.md): fact coverage 79 against
    # 75 percent with 5, no invented value, fewer judge findings.
    missing_per_facts_round: int = Field(
        10,
        ge=1,
        le=20,
        description="Missing facts one such round asks for (a repair round asks for 5).",
    )
    # On since 9 October 2026: German fact coverage on the dev pairs rose from 78 to 96
    # percent, no invented value added (docs/prompts.md).
    recover_facts: int = Field(
        10,
        ge=0,
        le=20,
        description="Must-keep values still missing then, asked for one by one with their "
        "source paragraph, as one new version; 0: none.",
    )
    # The facts and recover rounds add the source's sentences nearly verbatim, and the
    # loop never sees them again (10 October 2026; measured in docs/prompts.md).
    polish_rounds: int = Field(
        1,
        ge=0,
        le=3,
        description="Repair rounds on the best version's rule findings alone, at the end; 0: none.",
    )
    # The writer itself gets no list of office words: such a list made the 8B write more
    # of them (docs/prompts.md).
    vocabulary: bool = Field(
        True,
        description="The vocabulary of hard words in the pipeline; false only to measure "
        "what it brings.",
    )


class RoundRecord(Artifact):
    """One round after the first draft (pipeline/rounds.py): the version it started from,
    the version it produced, and the blocking findings and missing must-keep values
    before and after it. The counts are None in records rebuilt for jobs stored before
    the records existed (25 October 2026)."""

    kind: RoundKind
    number: int  # 1-based among the rounds of its kind
    parent_version: int
    version: int
    blocking_before: int | None = None
    blocking_after: int | None = None
    missing_before: int | None = None
    missing_after: int | None = None


# -- pipeline summary -----------------------------------------------------------------


class PipelineSummary(Artifact):
    """How a job's pipeline ran: which draft version is final and why it stopped."""

    condition: Condition
    mode: JobMode = "standard"
    final_version: int
    rounds: list[RoundRecord] = Field(default_factory=list)  # every round that made a version
    stop_reason: StopReason = "no_problems"  # why the repair and facts rounds ended
    endpoint: str | None = None  # the endpoint the job ran on; None: one without a name
    writer_model: str = ""
    understand_model: str | None = None  # only when it differs from the writer
    judge_model: str | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    blocking_findings: list[int] = Field(default_factory=list)  # per draft version
    notes: list[str] = Field(default_factory=list)  # stages that failed and were skipped
    # The version of the vocabulary the job used (rules/vocabulary.py); None: not used.
    vocabulary: str | None = None

    def rounds_of(self, kind: str) -> int:
        """How many rounds of a kind made a version."""
        return sum(1 for r in self.rounds if r.kind == kind)


# -- jobs --------------------------------------------------------------------------


class JobConfig(Artifact):
    lang: Lang | None = None  # None: detect from the source
    # The installation's `texts.region` when the job was created, so a later setup
    # never alters a stored job; a job stored before the field existed is Swiss.
    region: Region = "CH"
    level: Level = "A2"
    condition: Condition = "P2"
    endpoint: str | None = None  # the endpoint picked for this job; None: the one in use
    writer_model: str | None = None  # None: llm.models.writer
    understand_model: str | None = None  # None: llm.models.understand, else the writer
    judge_model: str | None = None  # None: llm.models.judge
    use_judge: bool = True  # P2 only: False repairs on rule findings alone
    # The rounds after the first draft (P2 only): the [pipeline] settings when the job was
    # created, so a settings change never alters a stored job.
    pipeline: PipelineOptions = Field(default_factory=PipelineOptions)
    mode: JobMode = "standard"
    addressee: str | None = None  # decision mode: the person the letter speaks to
    notice: str | None = None  # decision mode: the authority's fixed notice in the export
    sender: Sender = "authority"  # who writes: the prompts' name for the source
    address: Address = "formal"  # how the text addresses its reader


class UsageRecord(Artifact):
    stage: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cached: bool = False


class JobCounts(Artifact):
    """What the drafts list shows per job, written to the job row so that the list
    never opens an artifact (`lifecycle.job_counts`): where the document came from
    (set when the job is created), the final version's findings and facts (set when
    the pipeline ends) and the review's progress (set when a review is saved)."""

    source_type: SourceType | None = None
    source_uri: str | None = None  # the URL or the uploaded file's name
    source_chars: int | None = None  # pasted or uploaded text: its length
    has_draft: bool = False  # the counts below are meaningful
    errors: int = 0
    warnings: int = 0
    facts_present: int = 0
    facts_total: int = 0  # the facts that must survive
    blocks: int = 0  # what the reviewer decides: blocks and glossary entries
    decided: int = 0
    complete: bool = False


class Job(Artifact):
    id: str
    status: JobStatus = "queued"
    stage: str | None = None
    title: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    config: JobConfig = Field(default_factory=JobConfig)
    usage: list[UsageRecord] = Field(default_factory=list)
    error: str | None = None
    counts: JobCounts | None = None  # None: a job stored before the column existed
