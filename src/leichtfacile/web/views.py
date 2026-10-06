"""View models for the pages: everything a template needs, computed once in Python."""

from __future__ import annotations

from dataclasses import dataclass, field

from leichtfacile.rules.document import display_value, fact_coverage
from leichtfacile.rules.values import parse_value_norm
from leichtfacile.schemas import (
    SEVERITY_RANK,
    Block,
    Decision,
    Draft,
    Fact,
    FactSheet,
    Job,
    JudgeReport,
    PipelineSummary,
    ReviewState,
    RuleFindings,
    SourceDocument,
)
from leichtfacile.store import Store

STAGE_LABELS = {
    "understand": "Apertus reads the document and writes the fact sheet",
    "write": "Apertus writes the easy-language draft",
    "check": "Code checks the rules and the facts",
    "judge": "A second Apertus model checks meaning and facts",
    "baseline": "Apertus rewrites the text with one prompt (baseline)",
}


@dataclass
class Issue:
    source: str  # "rule" or "judge"
    rule_id: str
    severity: str
    message: str
    suggestion: str | None = None


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
class ReviewView:
    job: Job
    source: SourceDocument
    draft: Draft
    versions: list[int]
    final_version: int | None
    rows: list[BlockRow]
    facts: list[FactRow]
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


def review_view(store: Store, job: Job, version: int | None = None) -> ReviewView | None:
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
        issue = Issue("rule", f.rule_id, f.severity, f.message, f.suggestion)
        if f.block_id in rows:
            rows[f.block_id].issues.append(issue)
        else:
            doc_issues.append(issue)
    if judge:
        for u in judge.unsupported:
            if u.block_id in rows:
                rows[u.block_id].issues.append(
                    Issue(
                        "judge", "SEM-06", "error", f"Not supported by the source. {u.note}".strip()
                    )
                )
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
                                f"Fact {c.fact_id} distorted. {c.note}".strip(),
                            )
                        )
    for row in rows.values():
        row.issues.sort(key=lambda i: SEVERITY_RANK[i.severity])
    if review:
        for d in review.decisions:
            if d.block_id in rows:
                rows[d.block_id].decision = d

    fact_rows: list[FactRow] = []
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
    )
