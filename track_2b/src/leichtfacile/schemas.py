"""Artifacts of the pipeline (track_2b/docs/architecture.md §5).

Every stage reads and writes these models; the store keeps them as JSON. The models
the language model answers with are separate (see `leichtfacile.pipeline`), so the
model never has to produce bookkeeping fields such as ids of the job or versions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

Lang = Literal["de", "fr", "it"]
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
# authority or a court (track_2b/docs/use-case-decisions.md): the operative part and the appeal
# instructions are untouchable, the text speaks to one named person, and the export
# carries the authority's fixed notice. A job option, never an evaluation condition.
JobMode = Literal["standard", "decision"]
JOB_MODES: tuple[str, ...] = get_args(JobMode)
# P as in pipeline: the letter C would read as a CEFR level next to A2 and B1.
Condition = Literal["P0", "P0-ZH-complete", "P0-ZH-condensed", "P1", "P2"]
CONDITIONS: tuple[str, ...] = get_args(Condition)
# The conditions were called C0 to C2 until 6 October 2026; stored jobs, result rows
# and old command lines still say so.
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
LEVELS: tuple[Level, ...] = ("A2", "B1")
SEVERITY_RANK: dict[str, int] = {"error": 0, "warn": 1, "info": 2}


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
    title: str | None = None
    source: SourceInfo
    segments: list[Segment]

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
    level: Level
    version: int = 1
    parent_version: int | None = None
    origin: DraftOrigin = "write"
    blocks: list[Block]
    omissions: list[Omission] = Field(default_factory=list)
    glossary: list[GlossaryEntry] = Field(default_factory=list)
    code_edits: list[CodeEdit] = Field(default_factory=list)  # made on this version

    def by_id(self) -> dict[str, Block]:
        return {b.id: b for b in self.blocks}

    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)


# -- checks ------------------------------------------------------------------------


class Finding(Artifact):
    block_id: str | None  # None: the finding concerns the whole document
    rule_id: str
    severity: Severity
    message: str  # English (rules/messages.py); the UI translates by key and params
    message_key: str | None = None  # the template's key; None in older artifacts
    message_params: dict[str, str | int | float] = Field(default_factory=dict)
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


DropReason = Literal["repeat", "example", "not_flagged"]


class DroppedText(Artifact):
    """A sentence of a repair answer that code left out of the new version: a repeat of
    a sentence the draft already has, a sentence about the prompt's examples, or the
    repair of a block the round had not flagged."""

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
    # facts: a round that asks for facts only; vocabulary: the last round, for the
    # office words of the best version (LEX-07); recover: the missing values asked for
    # one by one with their source paragraphs (MAX_RECOVER_FACTS); polish: the rule
    # findings of the best version after the recover round (MAX_POLISH_ROUNDS)
    kind: Literal["repair", "facts", "vocabulary", "recover", "polish"] = "repair"
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
    # reviewers cannot overwrite each other without noticing (web/api.py). None in
    # reviews stored before 11 October 2026.
    saved_at: datetime | None = None

    def by_block(self) -> dict[str, Decision]:
        return {d.block_id: d for d in self.decisions}

    @property
    def last_saved(self) -> datetime | None:
        """`saved_at`, else the latest decision's time (older reviews)."""
        return self.saved_at or max((d.at for d in self.decisions), default=None)


# -- pipeline summary -----------------------------------------------------------------


class PipelineSummary(Artifact):
    """How a job's pipeline ran: which draft version is final and why it stopped."""

    condition: Condition
    mode: JobMode = "standard"
    final_version: int
    rounds: int = 0
    facts_rounds: int = 0  # rounds that asked for missing facts only, after the loop
    stop_reason: str = ""
    writer_model: str = ""
    understand_model: str | None = None  # only when it differs from the writer
    judge_model: str | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    blocking_findings: list[int] = Field(default_factory=list)  # per draft version
    notes: list[str] = Field(default_factory=list)  # stages that failed and were skipped
    # The version of the vocabulary the job used (rules/vocabulary.py); None: not used.
    vocabulary: str | None = None
    vocabulary_rounds: int = 0  # the last round, for the office words (0 or 1)
    polish_rounds: int = 0  # rounds for the rule findings after the recover round

    @field_validator("condition", mode="before")
    @classmethod
    def _old_condition_names(cls, value: object) -> object:
        # Summaries stored before 6 October 2026 say C0 to C2 (the eval stores do).
        return canonical_condition(value) if isinstance(value, str) else value


# -- jobs --------------------------------------------------------------------------


class JobConfig(Artifact):
    lang: Lang | None = None  # None: detect from the source
    level: Level = "A2"
    condition: Condition = "P2"
    writer_model: str | None = None  # None: LLM_NAME
    understand_model: str | None = None  # None: LLM_UNDERSTAND_NAME, else the writer
    judge_model: str | None = None  # None: LLM_JUDGE_NAME
    use_judge: bool = True  # P2 only: False repairs on rule findings alone
    max_repair_rounds: int = Field(default=3, ge=0, le=10)  # 0: no repair
    # Rounds that ask for the missing facts alone once the loop above has stopped with
    # must-keep values still missing (P2 only; 0: none).
    max_facts_rounds: int = Field(default=1, ge=0, le=5)
    mode: JobMode = "standard"
    addressee: str | None = None  # decision mode: the person the letter speaks to
    notice: str | None = None  # decision mode: the authority's fixed notice in the export
    # True: no recorded answer (llm/replay.py) and no cached response, every call goes
    # to the model (the prepared letters' "Run without cache").
    live: bool = False

    @field_validator("condition", mode="before")
    @classmethod
    def _old_condition_names(cls, value: object) -> object:
        return canonical_condition(value) if isinstance(value, str) else value


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
