"""View models for the pages: everything a template needs, computed once in Python.

The review's substance (the issues per block, the fact checklist, the counts) comes
from `leichtfacile.review`; this module adds the interface texts, which come from the
catalogs (`i18n.py`) through the translator `t`, and the shapes the templates read."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlsplit

from leichtfacile.export import glossary_ids
from leichtfacile.lifecycle import job_counts
from leichtfacile.review import (
    FactRow,
    Issue,
    block_issues,
    decided_count,
    fact_counts,
    fact_rows,
    load_review,
    review_items,
    severity_counts,
)
from leichtfacile.rules.base import RULES
from leichtfacile.rules.mediopunkt import RULE_ID as MEDIOPUNKT_RULE
from leichtfacile.schemas import (
    ROUND_KINDS,
    SEVERITY_RANK,
    Block,
    CoreAnswer,
    Decision,
    DocMetrics,
    Draft,
    FactSheet,
    Finding,
    GlossaryEntry,
    Job,
    JobCounts,
    JudgeReport,
    PipelineSummary,
    ReviewState,
    RuleFindings,
    Segment,
    SourceDocument,
)
from leichtfacile.store import Store
from leichtfacile.varieties import variety
from leichtfacile.web.i18n import ENGLISH, Translator

CORE_KEYS = ("what", "must_do", "deadline", "cost", "contact")
# The stop reasons that name a count of rounds (schemas.StopReason).
_COUNTED_STOPS = {"max_rounds": "repair", "max_facts_rounds": "facts"}
# The export formats every menu offers, in this order; the audit bundle is the whole
# job, so it carries no draft version. A label of None is the catalog text
# review.export.json; the reader view's descriptions are reader.<fmt>.desc.
EXPORT_FORMATS = (
    {"fmt": "md", "label": "Markdown", "ext": ".md"},
    {"fmt": "html", "label": "HTML", "ext": ".html"},
    {"fmt": "docx", "label": "Word", "ext": ".docx"},
    {"fmt": "json", "label": None, "ext": ".json"},
)


def stop_reason(t: Translator, summary: PipelineSummary) -> str:
    """Why the rounds ended, in the interface language (`stop.<code>`)."""
    code = summary.stop_reason
    if code in _COUNTED_STOPS:
        return t(f"stop.{code}", n=summary.rounds_of(_COUNTED_STOPS[code]))
    return t(f"stop.{code}")


# -- the review page ------------------------------------------------------------------


@dataclass
class FindingGroup:
    """Document findings of one rule, for the checks pane."""

    rule_id: str
    title: str
    worst: str
    issues: list[Issue]


@dataclass
class BlockRow:
    block: Block
    issues: list[Issue] = field(default_factory=list)
    decision: Decision | None = None

    @property
    def worst(self) -> str | None:
        ranked = [i.severity for i in self.issues if i.severity != "info"]
        return min(ranked, key=SEVERITY_RANK.__getitem__) if ranked else None

    @property
    def counted(self) -> int:
        """The issues shown as a count next to the severity mark: errors and warnings."""
        return sum(1 for i in self.issues if i.severity != "info")

    @property
    def decided(self) -> str:
        """The decision's code (approved, edited, rejected), "" while undecided."""
        return self.decision.decision if self.decision else ""

    @property
    def text(self) -> str:
        """The reviewer's text when the block was edited, else the draft's."""
        if self.decision and self.decision.text:
            return self.decision.text
        return self.block.text


@dataclass
class GlossaryRow:
    """A glossary entry, decided in the review like a block (`gid`: g01, g02, ...)."""

    gid: str
    entry: GlossaryEntry
    decision: Decision | None = None

    @property
    def decided(self) -> str:
        return self.decision.decision if self.decision else ""

    @property
    def text(self) -> str:
        """The reviewer's explanation when the entry was edited, else the draft's."""
        if self.decision and self.decision.text:
            return self.decision.text
        return self.entry.explanation


@dataclass
class SegmentRow:
    """A source sentence in the source pane: used by a block, left out with a reason
    (`note`), not explained, or a heading; `newpara` starts a new paragraph."""

    segment: Segment
    state: str  # heading, used, omitted, unused
    note: str = ""
    newpara: bool = False


@dataclass
class CoreRow:
    key: str
    label: str
    answer: CoreAnswer


@dataclass
class VersionRow:
    version: int
    blocking: int | None  # blocking problems left after that version, when known
    final: bool
    current: bool


@dataclass
class ReviewView:
    job: Job
    source: SourceDocument
    draft: Draft
    versions: list[int]
    final_version: int | None
    rows: list[BlockRow]
    facts: list[FactRow]
    core: list[CoreRow]
    doc_issues: list[Issue]
    factsheet: FactSheet | None
    summary: PipelineSummary | None
    judge: JudgeReport | None
    rules: RuleFindings | None
    review: ReviewState | None
    segments: list[SegmentRow]
    segment_counts: dict[str, int]  # sentences, omitted, unused (headings not counted)
    counts: dict[str, int]  # errors and warnings over the blocks and the document
    fact_counts: dict[str, int]  # the must-keep facts by status, and their total
    facts_text: str  # the fact counts as one sentence, for the stacked bar
    items: int  # what the reviewer decides: the blocks and the glossary entries
    decided: int
    tokens_in: int
    tokens_out: int
    seconds: float  # model time over all calls
    finding_groups: list[FindingGroup] = field(default_factory=list)  # doc_issues by rule
    saved_at: datetime | None = None  # when the stored review was last saved
    glossary_rows: list[GlossaryRow] = field(default_factory=list)  # decided like blocks

    @property
    def facts_sorted(self) -> list[FactRow]:
        """Problems first: missing, distorted, doubted, unchecked, present; background facts
        last."""
        rank = {"missing": 0, "distorted": 1, "doubted": 2, "unchecked": 3, "present": 4}
        return sorted(self.facts, key=lambda f: (not f.fact.must_keep, rank.get(f.status, 4)))

    @property
    def current_blocking(self) -> int | None:
        """Blocking problems left after the version on screen, when known."""
        return next((row.blocking for row in self.version_rows if row.current), None)

    @property
    def facts_by_id(self) -> dict[str, FactRow]:
        return {f.fact.id: f for f in self.facts}

    @property
    def undecided(self) -> int:
        return self.items - self.decided

    @property
    def decided_pct(self) -> int:
        return round(100 * self.decided / self.items) if self.items else 0

    @property
    def blocking_facts(self) -> int:
        """Must-keep facts missing or distorted: what blocks publication."""
        return self.fact_counts["missing"] + self.fact_counts["distorted"]

    @property
    def blocks_with_issues(self) -> int:
        return sum(1 for r in self.rows if r.worst is not None)

    @property
    def code_splits(self) -> int:
        """Words of this version that code split with its variety's mark (rules/mediopunkt.py)."""
        return sum(1 for e in self.draft.code_edits if e.rule_id == MEDIOPUNKT_RULE)

    @property
    def compound_mark(self) -> str:
        """The mark code splits a long compound with in the draft's variety, a catalog
        key `mark.<name>`: mediopunkt in Switzerland, hyphen in Germany and Austria."""
        return variety(self.draft.variety).compound_mark

    @property
    def version_rows(self) -> list[VersionRow]:
        blocking = self.summary.blocking_findings if self.summary else []
        return [
            VersionRow(
                version=v,
                blocking=blocking[i] if i < len(blocking) else None,
                final=v == self.final_version,
                current=v == self.draft.version,
            )
            for i, v in enumerate(self.versions)
        ]


def finding_text(t: Translator, finding: Finding) -> str:
    """A rule finding's message in the interface language: the catalog text for
    `finding.<key>`, filled with the finding's values (English when the language has
    no text for the key)."""
    params = dict(finding.params)
    n = params.pop("n", None)  # a count picks the .one or .other variant
    return t(f"finding.{finding.key}", n=int(n) if n is not None else None, **params)


def issue_text(t: Translator, issue: Issue) -> str:
    """An issue's message in the interface language: a rule finding's text, a judge
    issue's catalog text with the note, or the judge's note as it stands."""
    if issue.finding is not None:
        return finding_text(t, issue.finding)
    if issue.text_key:
        return t(issue.text_key, note=issue.note, fact=issue.fact_id or "").strip()
    return issue.note


def _with_texts(t: Translator, issues: list[Issue]) -> list[Issue]:
    for issue in issues:
        issue.message = issue_text(t, issue)
    return issues


def review_view(
    store: Store, job: Job, version: int | None = None, t: Translator = ENGLISH
) -> ReviewView | None:
    data = load_review(store, job, version)
    if data is None:
        return None
    draft, source = data.draft, data.source
    by_block, doc_issues = block_issues(draft, data.rules, data.judge)
    _with_texts(t, doc_issues)
    decisions = data.decisions
    rows = [BlockRow(b, _with_texts(t, by_block[b.id]), decisions.get(b.id)) for b in draft.blocks]
    glossary_rows = [
        GlossaryRow(gid, g, decisions.get(gid)) for gid, g in glossary_ids(draft).items()
    ]
    facts = fact_rows(draft, data.factsheet, data.judge, source) if data.factsheet else []
    fc = fact_counts(facts)
    facts_text = ""
    if fc["total"]:
        facts_text = t(
            "review.facts_counts", present=fc["present"], distorted=fc["distorted"],
            missing=fc["missing"],
        )  # fmt: skip
        if fc["doubted"]:
            facts_text += " · " + t("review.facts_doubted", n=fc["doubted"])

    omitted: dict[str, str] = {}
    for o in draft.omissions:
        for s in o.segment_ids:
            omitted[s] = f"{o.what}: {o.why}".strip(": ")
    if data.factsheet:
        for o in data.factsheet.omit_candidates:
            for s in o.segment_ids:
                omitted.setdefault(s, o.reason)
    used = {s for b in draft.blocks for s in b.segment_ids}
    segments: list[SegmentRow] = []
    segment_counts = {"sentences": 0, "omitted": 0, "unused": 0}
    para = None
    for seg in source.segments:
        newpara = para is not None and (seg.kind == "heading" or seg.para != para)
        if seg.kind == "heading":
            segments.append(SegmentRow(seg, "heading", newpara=newpara))
        else:
            state = "used" if seg.id in used else ("omitted" if seg.id in omitted else "unused")
            segments.append(SegmentRow(seg, state, omitted.get(seg.id, ""), newpara))
            segment_counts["sentences"] += 1
            if state != "used":
                segment_counts[state] += 1
        para = seg.para

    usage = job.usage
    return ReviewView(
        job=job,
        source=source,
        draft=draft,
        versions=data.versions,
        final_version=data.final_version,
        rows=rows,
        facts=facts,
        core=core_questions(data.factsheet, t) if data.factsheet else [],
        doc_issues=doc_issues,
        factsheet=data.factsheet,
        summary=data.summary,
        judge=data.judge,
        rules=data.rules,
        review=data.review,
        segments=segments,
        segment_counts=segment_counts,
        counts=severity_counts([i for row in rows for i in row.issues] + doc_issues),
        fact_counts=fc,
        facts_text=facts_text,
        items=review_items(draft),
        decided=decided_count(draft, data.review),
        tokens_in=sum(u.tokens_in for u in usage),
        tokens_out=sum(u.tokens_out for u in usage),
        seconds=sum(u.latency_ms for u in usage) / 1000,
        finding_groups=group_findings(doc_issues, t),
        saved_at=data.review.saved_at if data.review else None,
        glossary_rows=glossary_rows,
    )


def rule_title(t: Translator, rule_id: str) -> str:
    """A rule's title in the interface language (`rule.<ID>`), else the registry's."""
    spec = RULES.get(rule_id)
    return t.get(f"rule.{rule_id}", spec.title if spec else rule_id)


def group_findings(issues: list[Issue], t: Translator = ENGLISH) -> list[FindingGroup]:
    """Document findings grouped by rule, errors first."""
    groups: dict[str, FindingGroup] = {}
    for issue in issues:
        group = groups.get(issue.rule_id)
        if group is None:
            title = rule_title(t, issue.rule_id)
            group = groups[issue.rule_id] = FindingGroup(issue.rule_id, title, issue.severity, [])
        group.issues.append(issue)
        if SEVERITY_RANK[issue.severity] < SEVERITY_RANK[group.worst]:
            group.worst = issue.severity
    return sorted(groups.values(), key=lambda g: (SEVERITY_RANK[g.worst], g.rule_id))


def core_questions(factsheet: FactSheet, t: Translator = ENGLISH) -> list[CoreRow]:
    return [CoreRow(key, t(f"core.{key}"), getattr(factsheet.core, key)) for key in CORE_KEYS]


# -- the progress page ----------------------------------------------------------------

# Who does the work in each step: the model, code, or the reviewer. Title and
# description are the catalog texts `step.<key>.title` and `step.<key>.desc`.
STEP_WHO = {
    "baseline": "model",
    "understand": "model",
    "write": "model",
    "check": "code",
    "judge": "model",
    "repair": "model",
    "review": "human",
}
STEPS_BY_CONDITION = {
    "P0": ("baseline", "check", "review"),
    "P0-ZH-complete": ("baseline", "check", "review"),
    "P0-ZH-condensed": ("baseline", "check", "review"),
    "P1": ("understand", "write", "check", "review"),
    "P2": ("understand", "write", "check", "judge", "repair", "review"),
}


@dataclass
class Step:
    key: str
    title: str
    description: str
    who: str  # model, code, human
    state: str  # pending, running, done, skipped, failed
    detail: str = ""
    usage: StageUsage | None = None  # the stage's model calls so far


@dataclass
class StageUsage:
    stage: str
    calls: int = 0
    cached: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    seconds: float = 0.0


@dataclass
class ProgressView:
    job: Job
    steps: list[Step]
    factsheet: FactSheet | None
    draft: Draft | None
    rules: RuleFindings | None
    summary: PipelineSummary | None
    usage: list[StageUsage]
    elapsed_s: float
    block_marks: dict[str, str] = field(default_factory=dict)  # block id -> worst severity
    core: list[CoreRow] = field(default_factory=list)

    @property
    def current(self) -> Step | None:
        return next((s for s in self.steps if s.state in ("running", "failed")), None)

    @property
    def current_index(self) -> int:
        """1-based position of the running or failed stage; 0 while queued, all when done."""
        if self.current is not None:
            return self.steps.index(self.current) + 1
        if self.job.status in ("needs_review", "done"):
            return len(self.steps)
        return 0

    @property
    def tokens(self) -> int:
        return sum(u.tokens_in + u.tokens_out for u in self.usage)

    @property
    def live(self) -> bool:
        return self.job.status in ("queued", "running")


def progress_view(
    store: Store, job: Job, now: datetime | None = None, t: Translator = ENGLISH
) -> ProgressView:
    keys = STEPS_BY_CONDITION.get(job.config.condition, STEPS_BY_CONDITION["P2"])
    names = store.artifact_names(job.id)
    drafts = names.get("draft", [])
    factsheet = store.get_artifact(job.id, "factsheet", FactSheet)
    draft = store.get_artifact(job.id, "draft", Draft, version=drafts[-1]) if drafts else None
    rules = None
    if draft is not None:
        rules = store.get_artifact(job.id, "rules", RuleFindings, version=draft.version)
    judge_v1 = store.get_artifact(job.id, "judge", JudgeReport, version=1)
    rules_v1 = store.get_artifact(job.id, "rules", RuleFindings, version=1)
    summary = store.get_artifact(job.id, "summary", PipelineSummary)

    stage = job.stage or ""
    stage_key = stage.split(" ")[0]
    if stage_key in ROUND_KINDS:  # every kind of round shows as the repair step
        stage_key = "repair"
    in_loop = len(drafts) > 1 or stage_key == "repair"
    if job.status in ("needs_review", "done"):
        current = "review"
    elif job.status == "queued":
        current = None
    else:
        current = stage_key if stage_key in keys else keys[0]
        if current in ("check", "judge") and in_loop and "repair" in keys:
            current = "repair"
    idx = keys.index(current) if current in keys else -1

    steps: list[Step] = []
    for i, key in enumerate(keys):
        if idx < 0 or i > idx:
            state = "pending"
        elif i < idx or job.status == "done":
            state = "done"
        elif job.status == "failed":
            state = "failed"
        else:
            state = "running"
        steps.append(Step(key, t(f"step.{key}.title"), t(f"step.{key}.desc"), STEP_WHO[key], state))

    for step in steps:
        _add_detail(step, store, job, drafts, factsheet, draft, rules_v1, judge_v1, summary, t)
        if step.state == "failed" and job.error:
            step.detail = job.error
    if job.status == "queued" and steps:
        steps[0].detail = t("detail.waiting")

    block_marks: dict[str, str] = {}
    if rules:
        for f in rules.findings:
            if f.block_id and f.severity != "info":
                worst = block_marks.get(f.block_id)
                if worst is None or SEVERITY_RANK[f.severity] < SEVERITY_RANK[worst]:
                    block_marks[f.block_id] = f.severity

    by_stage: dict[str, StageUsage] = {}
    for u in job.usage:
        key = u.stage.split(" ")[0]
        key = "repair" if key in ROUND_KINDS else key
        row = by_stage.setdefault(key, StageUsage(key))
        row.calls += 1
        row.cached += int(u.cached)
        row.tokens_in += u.tokens_in
        row.tokens_out += u.tokens_out
        row.seconds += u.latency_ms / 1000
    for step in steps:
        step.usage = by_stage.get(step.key)

    now = now or datetime.now(UTC)
    end = now if job.status in ("queued", "running") else job.updated_at
    elapsed = (_aware(end) - _aware(job.created_at)).total_seconds()
    return ProgressView(
        job=job,
        steps=steps,
        factsheet=factsheet,
        draft=draft,
        rules=rules,
        summary=summary,
        usage=list(by_stage.values()),
        elapsed_s=max(elapsed, 0.0),
        block_marks=block_marks,
        core=core_questions(factsheet, t) if factsheet else [],
    )


def _add_detail(
    step: Step,
    store: Store,
    job: Job,
    drafts: list[int],
    factsheet: FactSheet | None,
    draft: Draft | None,
    rules_v1: RuleFindings | None,
    judge_v1: JudgeReport | None,
    summary: PipelineSummary | None,
    t: Translator,
) -> None:
    """One line per step from the artifacts that exist so far."""
    stage = job.stage or ""
    stage_key = stage.split(" ")[0]
    if step.key == "understand" and factsheet:
        keep = sum(1 for f in factsheet.facts if f.must_keep)
        step.detail = t("detail.facts", n=len(factsheet.facts), keep=keep)
    elif step.key in ("write", "baseline") and drafts:
        first = draft if draft and draft.version == 1 else None
        first = first or store.get_artifact(job.id, "draft", Draft, version=1)
        if first:
            step.detail = t("detail.blocks", n=len(first.blocks))
            if first.omissions:
                step.detail += t("detail.omissions", n=len(first.omissions))
    elif step.key == "check" and rules_v1:
        errors = sum(1 for f in rules_v1.findings if f.severity == "error")
        warns = sum(1 for f in rules_v1.findings if f.severity == "warn")
        step.detail = t("detail.checked", errors=errors, warns=warns)
    elif step.key == "judge":
        if judge_v1:
            present = sum(1 for c in judge_v1.fact_checks if c.status == "present")
            step.detail = t(
                "detail.judged",
                n=len(judge_v1.unsupported),
                present=present,
                total=len(judge_v1.fact_checks),
            )
        elif step.state == "done":
            step.state = "skipped"
            step.detail = _note(summary, "judge") or t("detail.not_run")
    elif step.key == "repair":
        if step.state == "running":
            if stage_key == "repair":
                step.detail = t("detail.round", round=stage.split(" ")[-1])
            else:
                step.detail = t("detail.checking_repair")
        elif summary and step.state == "done":
            repairs = summary.rounds_of("repair")
            if repairs == 0:
                step.state = "skipped"
                step.detail = t("detail.not_needed", reason=stop_reason(t, summary))
            else:
                step.detail = t("detail.rounds", n=repairs, reason=stop_reason(t, summary))
                if facts := summary.rounds_of("facts"):
                    step.detail += t("detail.facts_rounds", n=facts)
                if polish := summary.rounds_of("polish"):
                    step.detail += t("detail.polish_rounds", n=polish)
                per_version = ", ".join(
                    f"v{v}: {b}" for v, b in zip(drafts, summary.blocking_findings, strict=False)
                )
                if per_version:
                    step.detail += t("detail.blocking_left", versions=per_version)
    elif step.key == "review":
        if job.status == "needs_review":
            step.detail = t("detail.ready")
        elif job.status == "done":
            step.detail = t("detail.reviewed")


def _note(summary: PipelineSummary | None, word: str) -> str:
    if summary is None:
        return ""
    return next((n for n in summary.notes if word in n), "")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# -- the drafts list ------------------------------------------------------------------


@dataclass
class DraftRow:
    job: Job
    title: str
    language: str  # the document language's name, with the variety where not Swiss
    doc_lang: str | None
    source_line: str = ""
    status_note: str = ""
    has_checks: bool = False  # a draft exists: the counts below are meaningful
    errors: int = 0
    warnings: int = 0
    facts_present: int = 0
    facts_total: int = 0
    decided: int = 0
    blocks: int = 0
    complete: bool = False

    @property
    def review_pct(self) -> int:
        return round(100 * self.decided / self.blocks) if self.blocks else 0


def display_title(job: Job) -> str:
    """The title as the list shows it."""
    return job.title or job.id


def source_line(counts: JobCounts | None, t: Translator = ENGLISH) -> str:
    """Where a document came from, for the second line of a drafts list row."""
    if counts is None or counts.source_type is None:
        return ""
    if counts.source_type == "html":
        host = urlsplit(counts.source_uri or "").hostname or counts.source_uri or ""
        return t("drafts.source.html", host=host.removeprefix("www."))
    if counts.source_type == "pdf":
        return t("drafts.source.pdf", name=counts.source_uri or "PDF")
    if counts.source_type == "image":
        return t("drafts.source.image")
    return t("drafts.source.text", chars=t.number(counts.source_chars or 0))


def drafts_view(
    store: Store, jobs: list[Job], t: Translator = ENGLISH, now: datetime | None = None
) -> list[DraftRow]:
    """One row per job for the drafts list, from the counts on the job row (audit B3):
    no artifact is opened. A job stored before the counts existed gets them computed
    once here and written back."""
    now = now or datetime.now(UTC)
    rows: list[DraftRow] = []
    for job in jobs:
        counts = job.counts
        if counts is None:
            counts = job_counts(store, job)
            store.update_job(job.id, counts=counts)
            job = job.model_copy(update={"counts": counts})
        title = display_title(job)
        doc_lang = job.config.lang
        row = DraftRow(
            job=job,
            title=title,
            language=t.language(doc_lang, job.config.region) if doc_lang else "",
            doc_lang=doc_lang,
            source_line=source_line(counts, t),
        )
        if job.status == "running":
            stage_key = (job.stage or "").split(" ")[0]
            elapsed = format_duration((now - _aware(job.created_at)).total_seconds())
            stage = t.get(f"step.{stage_key}.title", job.stage or "") if stage_key else ""
            row.status_note = t("drafts.running", stage=stage, time=elapsed) if stage else elapsed
        elif job.status == "queued":
            row.status_note = t("detail.waiting")
        elif job.status == "failed" and job.error:
            if job.error == "cancelled":
                row.status_note = t("drafts.stopped")
            else:
                row.status_note = job.error if len(job.error) <= 60 else job.error[:59] + "…"
        if job.status in ("needs_review", "done") and counts.has_draft:
            row.has_checks = True
            row.errors, row.warnings = counts.errors, counts.warnings
            row.facts_present, row.facts_total = counts.facts_present, counts.facts_total
            row.decided, row.blocks = counts.decided, counts.blocks
            row.complete = counts.complete
        rows.append(row)
    return rows


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes, rest = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {rest:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


# -- the Check page: a text checked as it is ---------------------------------------------


@dataclass
class CheckView:
    """A text the writer pasted, checked by the rules alone (no job, no model): its
    blocks with their findings, the document findings by rule, the counts."""

    lang: str
    level: str
    rows: list[BlockRow]
    finding_groups: list[FindingGroup]
    metrics: DocMetrics
    errors: int
    warnings: int
    infos: int

    def per_100(self, count: int) -> float:
        return round(100 * count / max(1, len(self.rows)), 1)

    @property
    def readability_text(self) -> str:
        if self.metrics.readability is None:
            return "-"
        return f"{self.metrics.readability:.0f} ({self.metrics.readability_formula})"


def check_view(draft: Draft, rules: RuleFindings, t: Translator = ENGLISH) -> CheckView:
    by_block, doc_issues = block_issues(draft, rules, None)
    rows = [BlockRow(b, _with_texts(t, by_block[b.id])) for b in draft.blocks]
    counts = Counter(f.severity for f in rules.findings)
    return CheckView(
        draft.lang,
        draft.level,
        rows,
        group_findings(_with_texts(t, doc_issues), t),
        rules.metrics,
        counts["error"],
        counts["warn"],
        counts["info"],
    )
