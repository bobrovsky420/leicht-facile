"""View models for the pages: everything a template needs, computed once in Python.

Texts come from the interface catalogs (`i18n.py`) through the translator `t`."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlsplit

from leichtfacile.examples import EXAMPLE_PREFIX
from leichtfacile.rules.base import RULES
from leichtfacile.rules.document import display_value, fact_coverage
from leichtfacile.rules.mediopunkt import RULE_ID as MEDIOPUNKT_RULE
from leichtfacile.rules.messages import recover
from leichtfacile.rules.recipes import RECIPE_RULES
from leichtfacile.rules.values import parse_value_norm
from leichtfacile.schemas import (
    SEVERITY_RANK,
    Block,
    CoreAnswer,
    Decision,
    Draft,
    Fact,
    FactSheet,
    Finding,
    Job,
    JudgeReport,
    PipelineSummary,
    ReviewState,
    RuleFindings,
    SourceDocument,
)
from leichtfacile.store import Store
from leichtfacile.web.i18n import ENGLISH, Translator

CORE_KEYS = ("what", "must_do", "deadline", "cost", "contact")

# The pipeline's stop reasons (orchestrator.py) and their catalog keys.
STOP_KEYS = {
    "baseline": "stop.baseline",
    "P1": "stop.p1",
    "no problems left": "stop.no_problems",
    "only warnings left": "stop.only_warnings",
    "no blocking problems left": "stop.no_blocking",
    "a repair round failed": "stop.round_failed",
    "a repair round brought no progress": "stop.no_progress",
    "no missing facts left": "stop.no_missing_facts",
    "a facts round failed": "stop.facts_round_failed",
    "a facts round brought no progress": "stop.facts_no_progress",
}


def stop_reason(t: Translator, reason: str) -> str:
    rounds = re.fullmatch(r"stopped after (\d+) repair rounds", reason)
    if rounds:
        return t("stop.max_rounds", n=int(rounds.group(1)))
    facts = re.fullmatch(r"stopped after (\d+) facts rounds", reason)
    if facts:
        return t("stop.max_facts_rounds", n=int(facts.group(1)))
    return t(STOP_KEYS[reason]) if reason in STOP_KEYS else reason


# -- the review page ------------------------------------------------------------------


@dataclass
class Issue:
    source: str  # "rule" or "judge"
    rule_id: str
    severity: str
    message: str
    suggestion: str | None = None
    evidence: str = ""  # what the rule found, e.g. LEX-01's long word
    fact_id: str | None = None  # FACT-01, FACT-02, FACT-05: the fact concerned
    segment_ids: list[str] = field(default_factory=list)  # FACT-04: the sentences concerned
    applicable: bool = False  # the suggestion can replace the evidence in the block's text

    @property
    def ref(self) -> str:
        """What a document finding points at: a fact, or a sentence or range of sentences."""
        if self.fact_id:
            return self.fact_id
        if len(self.segment_ids) > 1:
            return f"{self.segment_ids[0]}-{self.segment_ids[-1]}"
        return self.segment_ids[0] if self.segment_ids else ""


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


@dataclass
class FactRow:
    fact: Fact
    expected: str | None  # the normalised value as easy language writes it
    code_found: bool | None  # None: no value code can check
    blocks: list[str]
    judge_status: str | None
    judge_note: str = ""

    @property
    def status(self) -> str:
        if self.judge_status in ("missing", "distorted") or self.code_found is False:
            return self.judge_status if self.judge_status in ("missing", "distorted") else "missing"
        if self.judge_status == "present" or self.code_found:
            return "present"
        return "unchecked"


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
    used_segments: set[str]
    omitted_segments: dict[str, str]
    tokens_in: int
    tokens_out: int
    seconds: float  # model time over all calls
    finding_groups: list[FindingGroup] = field(default_factory=list)  # doc_issues by rule
    saved_at: datetime | None = None  # when the stored review was last saved

    @property
    def facts_sorted(self) -> list[FactRow]:
        """Problems first: missing, distorted, unchecked, present; background facts last."""
        rank = {"missing": 0, "distorted": 1, "unchecked": 2, "present": 3}
        return sorted(self.facts, key=lambda f: (not f.fact.must_keep, rank.get(f.status, 4)))

    @property
    def segment_counts(self) -> dict[str, int]:
        """Source sentences without headings: all, left out with a reason, not explained."""
        counts = {"sentences": 0, "omitted": 0, "unused": 0}
        for seg in self.source.segments:
            if seg.kind == "heading":
                continue
            counts["sentences"] += 1
            if seg.id not in self.used_segments:
                counts["omitted" if seg.id in self.omitted_segments else "unused"] += 1
        return counts

    @property
    def current_blocking(self) -> int | None:
        """Blocking problems left after the version on screen, when known."""
        return next((row.blocking for row in self.version_rows if row.current), None)

    @property
    def facts_by_id(self) -> dict[str, FactRow]:
        return {f.fact.id: f for f in self.facts}

    @property
    def decided_pct(self) -> int:
        return round(100 * self.decided / len(self.rows)) if self.rows else 0

    @property
    def counts(self) -> dict[str, int]:
        out = {"error": 0, "warn": 0}
        for row in self.rows:
            for issue in row.issues:
                if issue.severity in out:
                    out[issue.severity] += 1
        for issue in self.doc_issues:
            if issue.severity in out:
                out[issue.severity] += 1
        return out

    @property
    def fact_counts(self) -> dict[str, int]:
        out = {"present": 0, "missing": 0, "distorted": 0, "unchecked": 0, "total": 0}
        for f in self.facts:
            if f.fact.must_keep:
                out[f.status] += 1
                out["total"] += 1
        return out

    @property
    def decided(self) -> int:
        return sum(1 for r in self.rows if r.decision is not None)

    @property
    def blocks_with_issues(self) -> int:
        return sum(1 for r in self.rows if r.worst is not None)

    @property
    def code_splits(self) -> int:
        """Words of this version that code split with a Mediopunkt (rules/mediopunkt.py)."""
        return sum(1 for e in self.draft.code_edits if e.rule_id == MEDIOPUNKT_RULE)

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
    `finding.<message_key>`, filled with the finding's values. A finding stored before
    the keys existed gets key and values read off its English text; the stored text
    stands in when that fails or the catalogs have no text for the key."""
    key, params = finding.message_key, dict(finding.message_params)
    if not key:
        recovered = recover(finding.rule_id, finding.message)
        if recovered is None:
            return finding.message
        key, params = recovered
    n = params.pop("n", None)  # a count picks the .one or .other variant
    count = int(n) if n is not None else None
    key = f"finding.{key}"
    if not t.has(key, count):
        return finding.message
    try:
        return t(key, n=count, **params)
    except (KeyError, IndexError):  # the template and the stored values drifted apart
        return finding.message


def review_view(
    store: Store, job: Job, version: int | None = None, t: Translator = ENGLISH
) -> ReviewView | None:
    source = store.get_artifact(job.id, "source", SourceDocument)
    versions = store.versions(job.id, "draft")
    if source is None or not versions:
        return None
    summary = store.get_artifact(job.id, "summary", PipelineSummary)
    final_version = summary.final_version if summary else versions[-1]
    if version not in versions:
        version = final_version if final_version in versions else versions[-1]
    draft = store.get_artifact(job.id, "draft", Draft, version=version)
    rules = store.get_artifact(job.id, "rules", RuleFindings, version=version)
    judge = store.get_artifact(job.id, "judge", JudgeReport, version=version)
    factsheet = store.get_artifact(job.id, "factsheet", FactSheet)
    review = store.get_artifact(job.id, "review", ReviewState)
    if review and review.draft_version != version:
        review = None

    rows = {b.id: BlockRow(b) for b in draft.blocks}
    doc_issues: list[Issue] = []
    for f in rules.findings if rules else []:
        issue = Issue(
            "rule",
            f.rule_id,
            f.severity,
            finding_text(t, f),
            f.suggestion,
            evidence=f.evidence,
            fact_id=f.fact_id,
            segment_ids=list(f.segment_ids),
        )
        if f.block_id in rows:
            rows[f.block_id].issues.append(issue)
        else:
            doc_issues.append(issue)
    if judge:
        for u in judge.unsupported:
            if u.block_id in rows:
                message = t("issue.unsupported", note=u.note).strip()
                rows[u.block_id].issues.append(Issue("judge", "SEM-06", "error", message))
        for s in judge.semantic_findings:
            if s.block_id in rows:
                rows[s.block_id].issues.append(Issue("judge", s.rule_id, "warn", s.note))
        for c in judge.fact_checks:
            if c.status == "distorted":
                for block_id in c.block_ids:
                    if block_id in rows:
                        rows[block_id].issues.append(
                            Issue(
                                "judge",
                                "SEM-07",
                                "error",
                                t("issue.distorted", fact=c.fact_id, note=c.note).strip(),
                            )
                        )
    for row in rows.values():
        row.issues.sort(key=lambda i: SEVERITY_RANK[i.severity])
        for issue in row.issues:
            # A recipe (LEN-02: "make two sentences ...") is advice, not a replacement.
            issue.applicable = bool(
                issue.suggestion
                and issue.evidence
                and issue.rule_id not in RECIPE_RULES
                and issue.evidence != issue.suggestion
                and issue.evidence in row.block.text
            )
    if review:
        for d in review.decisions:
            if d.block_id in rows:
                rows[d.block_id].decision = d

    fact_rows: list[FactRow] = []
    core_rows: list[CoreRow] = []
    if factsheet:
        coverage = fact_coverage(draft, factsheet, draft.lang)
        judged = {c.fact_id: c for c in judge.fact_checks} if judge else {}
        for fact in factsheet.facts:
            value = parse_value_norm(fact.value_norm, fact.kind, draft.lang)
            check = judged.get(fact.id)
            blocks = sorted(
                set(coverage.found.get(fact.id, []))
                | {b.id for b in draft.blocks if fact.id in b.fact_ids}
                | set(check.block_ids if check else []),
                key=[b.id for b in draft.blocks].index,
            )
            fact_rows.append(
                FactRow(
                    fact=fact,
                    expected=display_value(value, draft.lang) if value else None,
                    code_found=(fact.id in coverage.found) if value and fact.must_keep else None,
                    blocks=blocks,
                    judge_status=check.status if check else None,
                    judge_note=check.note if check else "",
                )
            )
        core_rows = core_questions(factsheet, t)
    omitted = {}
    for o in draft.omissions:
        for s in o.segment_ids:
            omitted[s] = f"{o.what}: {o.why}".strip(": ")
    if factsheet:
        for o in factsheet.omit_candidates:
            for s in o.segment_ids:
                omitted.setdefault(s, o.reason)
    usage = job.usage
    return ReviewView(
        job=job,
        source=source,
        draft=draft,
        versions=versions,
        final_version=final_version,
        rows=list(rows.values()),
        facts=fact_rows,
        core=core_rows,
        doc_issues=doc_issues,
        factsheet=factsheet,
        summary=summary,
        judge=judge,
        rules=rules,
        review=review,
        used_segments={s for b in draft.blocks for s in b.segment_ids},
        omitted_segments=omitted,
        tokens_in=sum(u.tokens_in for u in usage),
        tokens_out=sum(u.tokens_out for u in usage),
        seconds=sum(u.latency_ms for u in usage) / 1000,
        finding_groups=group_findings(doc_issues, t),
        saved_at=max((d.at for d in review.decisions), default=None) if review else None,
    )


def rule_title(t: Translator, rule_id: str) -> str:
    """A rule's title in the interface language (`rule.<ID>`), else the registry's."""
    base = rule_id.removesuffix("-DE").removesuffix("-FR")
    spec = RULES.get(rule_id) or RULES.get(base)
    return t.get(f"rule.{base}", spec.title if spec else rule_id)


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
    "baseline": "apertus",
    "understand": "apertus",
    "write": "apertus",
    "check": "code",
    "judge": "apertus",
    "repair": "apertus",
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
    who: str  # apertus, code, human
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
    if stage_key in ("facts", "vocabulary"):  # rounds for facts or office words: repair
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
        key = "repair" if key in ("facts", "vocabulary") else key  # repair calls
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
            if summary.rounds == 0:
                step.state = "skipped"
                step.detail = t("detail.not_needed", reason=stop_reason(t, summary.stop_reason))
            else:
                step.detail = t(
                    "detail.rounds", n=summary.rounds, reason=stop_reason(t, summary.stop_reason)
                )
                if summary.facts_rounds:
                    step.detail += t("detail.facts_rounds", n=summary.facts_rounds)
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
    title: str  # without the example prefix
    is_example: bool
    language: str  # the document language's name
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


def display_title(job: Job) -> tuple[str, bool]:
    """The title as the list shows it, and whether the job is an example."""
    title = job.title or job.id
    if title.startswith(EXAMPLE_PREFIX):
        return title.removeprefix(EXAMPLE_PREFIX), True
    return title, False


def format_number(n: int, lang: str) -> str:
    """Thousands separated the way the interface language writes them: 1,960 or 1'960."""
    text = f"{n:,}"
    return text.replace(",", "'") if lang == "de" else text


def source_line(source: SourceDocument | None, t: Translator = ENGLISH) -> str:
    """Where a document came from, for the second line of a drafts list row."""
    if source is None:
        return ""
    info = source.source
    if info.type == "html":
        host = urlsplit(info.uri or "").hostname or info.uri or ""
        return t("drafts.source.html", host=host.removeprefix("www."))
    if info.type == "pdf":
        return t("drafts.source.pdf", name=info.uri or "PDF")
    if info.type == "image":
        return t("drafts.source.image")
    return t("drafts.source.text", chars=format_number(len(source.text()), t.lang))


def drafts_view(
    store: Store, jobs: list[Job], t: Translator = ENGLISH, now: datetime | None = None
) -> list[DraftRow]:
    """One row per job for the drafts list. Jobs with a draft get the review page's
    counts (computed here, per request: D-Y); the others a status note."""
    now = now or datetime.now(UTC)
    rows: list[DraftRow] = []
    for job in jobs:
        source = store.get_artifact(job.id, "source", SourceDocument)
        title, is_example = display_title(job)
        doc_lang = job.config.lang or (source.lang if source else None)
        row = DraftRow(
            job=job,
            title=title,
            is_example=is_example,
            language=t.get(f"lang.{doc_lang}", doc_lang) if doc_lang else "",
            doc_lang=doc_lang,
            source_line=source_line(source, t),
        )
        if job.status == "running":
            stage_key = (job.stage or "").split(" ")[0]
            elapsed = format_duration((now - _aware(job.created_at)).total_seconds())
            stage = t.get(f"step.{stage_key}.title", job.stage or "") if stage_key else ""
            row.status_note = t("drafts.running", stage=stage, time=elapsed) if stage else elapsed
        elif job.status == "queued":
            row.status_note = t("detail.waiting")
        elif job.status == "failed" and job.error:
            row.status_note = job.error if len(job.error) <= 60 else job.error[:59] + "…"
        if job.status in ("needs_review", "done"):
            view = review_view(store, job, None, t)
            if view is not None:
                row.has_checks = True
                row.errors, row.warnings = view.counts["error"], view.counts["warn"]
                row.facts_present = view.fact_counts["present"]
                row.facts_total = view.fact_counts["total"]
                row.decided, row.blocks = view.decided, len(view.rows)
                row.complete = bool(view.review and view.review.completed)
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
