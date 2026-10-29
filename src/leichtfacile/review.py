"""The review of a draft, read from its artifacts (docs/architecture.md §4.7 and §5):
the findings of code and judge per block, the fact checklist with each fact's status,
the reviewer's progress, and the counts the drafts list shows.

No interface text lives here: the review page's view model (web/views.py) renders the
issues in the reviewer's language, and the pipeline writes the counts to the job row
when a job ends (lifecycle.job_counts), so neither the pipeline nor the job row depends
on the web application.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from leichtfacile.export import glossary_ids
from leichtfacile.rules.document import display_value, fact_coverage
from leichtfacile.rules.recipes import RECIPE_RULES
from leichtfacile.rules.values import parse_value_norm
from leichtfacile.schemas import (
    SEVERITY_RANK,
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


@dataclass
class Issue:
    """A finding on a block or on the document, from code (a rule finding) or from the
    judge. The text is rendered by the view model (`message`): a rule finding from its
    key and values, a judge issue from the catalog text `text_key` with the note, a
    semantic finding as the judge's note."""

    source: Literal["rule", "judge"]
    rule_id: str
    severity: str
    finding: Finding | None = None
    text_key: str | None = None  # issue.unsupported, issue.distorted
    note: str = ""  # the judge's note
    suggestion: str | None = None
    evidence: str = ""  # what the rule found, e.g. LEX-01's long word
    fact_id: str | None = None  # FACT-01, FACT-02, FACT-05, SEM-07: the fact concerned
    segment_ids: list[str] = field(default_factory=list)  # FACT-04: the sentences concerned
    applicable: bool = False  # the suggestion can replace the evidence in the block's text
    message: str = ""  # in the interface language, filled by the view model

    @property
    def ref(self) -> str:
        """What a document finding points at: a fact, or a sentence or range of sentences."""
        if self.fact_id:
            return self.fact_id
        if len(self.segment_ids) > 1:
            return f"{self.segment_ids[0]}-{self.segment_ids[-1]}"
        return self.segment_ids[0] if self.segment_ids else ""


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
        # Code decides whether a value is there: the judge's "missing" on a fact whose
        # value code finds is a doubt about the statement, shown in amber. The pipeline
        # still counts it as blocking (docs/prompts.md, "Judge doubts on values").
        if self.judge_status == "missing" and self.code_found:
            return "doubted"
        if self.judge_status in ("missing", "distorted") or self.code_found is False:
            return self.judge_status if self.judge_status in ("missing", "distorted") else "missing"
        if self.judge_status == "present" or self.code_found:
            return "present"
        return "unchecked"


@dataclass
class ReviewData:
    """The artifacts of one draft version, as the review reads them."""

    job: Job
    source: SourceDocument
    draft: Draft
    versions: list[int]
    final_version: int
    summary: PipelineSummary | None
    rules: RuleFindings | None
    judge: JudgeReport | None
    factsheet: FactSheet | None
    review: ReviewState | None  # the stored review, when it decides this version

    @property
    def decisions(self) -> dict[str, Decision]:
        return self.review.by_block() if self.review else {}


def load_review(store: Store, job: Job, version: int | None = None) -> ReviewData | None:
    """The artifacts of `version` (default: the final version, else the latest); None
    before the first draft."""
    source = store.get_artifact(job.id, "source", SourceDocument)
    versions = store.versions(job.id, "draft")
    if source is None or not versions:
        return None
    summary = store.get_artifact(job.id, "summary", PipelineSummary)
    final_version = summary.final_version if summary else versions[-1]
    if version not in versions:
        version = final_version if final_version in versions else versions[-1]
    review = store.get_artifact(job.id, "review", ReviewState)
    if review and review.draft_version != version:
        review = None
    return ReviewData(
        job=job,
        source=source,
        draft=store.get_artifact(job.id, "draft", Draft, version=version),
        versions=versions,
        final_version=final_version,
        summary=summary,
        rules=store.get_artifact(job.id, "rules", RuleFindings, version=version),
        judge=store.get_artifact(job.id, "judge", JudgeReport, version=version),
        factsheet=store.get_artifact(job.id, "factsheet", FactSheet),
        review=review,
    )


def block_issues(
    draft: Draft, rules: RuleFindings | None, judge: JudgeReport | None
) -> tuple[dict[str, list[Issue]], list[Issue]]:
    """The issues per block (every block has a list), worst first, and the document
    findings, which name no block."""
    blocks: dict[str, list[Issue]] = {b.id: [] for b in draft.blocks}
    document: list[Issue] = []
    for f in rules.findings if rules else []:
        issue = Issue(
            "rule",
            f.rule_id,
            f.severity,
            finding=f,
            suggestion=f.suggestion,
            evidence=f.evidence,
            fact_id=f.fact_id,
            segment_ids=list(f.segment_ids),
        )
        if f.block_id in blocks:
            blocks[f.block_id].append(issue)
        else:
            document.append(issue)
    if judge:
        for u in judge.unsupported:
            if u.block_id in blocks:
                blocks[u.block_id].append(
                    Issue("judge", "SEM-06", "error", text_key="issue.unsupported", note=u.note)
                )
        for s in judge.semantic_findings:
            if s.block_id in blocks:
                blocks[s.block_id].append(Issue("judge", s.rule_id, "warn", note=s.note))
        for c in judge.fact_checks:
            if c.status != "distorted":
                continue
            for block_id in c.block_ids:
                if block_id in blocks:
                    blocks[block_id].append(
                        Issue(
                            "judge",
                            "SEM-07",
                            "error",
                            text_key="issue.distorted",
                            note=c.note,
                            fact_id=c.fact_id,
                        )
                    )
    texts = {b.id: b.text for b in draft.blocks}
    for block_id, issues in blocks.items():
        issues.sort(key=lambda i: SEVERITY_RANK[i.severity])
        for issue in issues:
            # A recipe (LEN-02: "make two sentences ...") is advice, not a replacement.
            issue.applicable = bool(
                issue.suggestion
                and issue.evidence
                and issue.rule_id not in RECIPE_RULES
                and issue.evidence != issue.suggestion
                and issue.evidence in texts[block_id]
            )
    return blocks, document


def fact_rows(
    draft: Draft, factsheet: FactSheet, judge: JudgeReport | None, source: SourceDocument
) -> list[FactRow]:
    """The fact checklist: every fact with the value code expects, whether code finds
    it, the blocks that carry it and the judge's verdict."""
    coverage = fact_coverage(draft, factsheet, draft.lang, source)
    judged = {c.fact_id: c for c in judge.fact_checks} if judge else {}
    order = [b.id for b in draft.blocks]
    rows = []
    for fact in factsheet.facts:
        value = parse_value_norm(fact.value_norm, fact.kind, draft.variety)
        check = judged.get(fact.id)
        blocks = sorted(
            set(coverage.found.get(fact.id, []))
            | {b.id for b in draft.blocks if fact.id in b.fact_ids}
            | set(check.block_ids if check else []),
            key=order.index,
        )
        rows.append(
            FactRow(
                fact=fact,
                expected=display_value(value, draft.variety) if value else None,
                code_found=(fact.id in coverage.found) if value and fact.must_keep else None,
                blocks=blocks,
                judge_status=check.status if check else None,
                judge_note=check.note if check else "",
            )
        )
    return rows


def severity_counts(issues: Iterable[Issue]) -> dict[str, int]:
    """Errors and warnings among the issues (notes are not counted)."""
    out = {"error": 0, "warn": 0}
    for issue in issues:
        if issue.severity in out:
            out[issue.severity] += 1
    return out


def fact_counts(rows: Iterable[FactRow]) -> dict[str, int]:
    """The must-keep facts by status, and their total."""
    out = {"present": 0, "missing": 0, "distorted": 0, "doubted": 0, "unchecked": 0, "total": 0}
    for row in rows:
        if row.fact.must_keep:
            out[row.status] += 1
            out["total"] += 1
    return out


def review_items(draft: Draft) -> int:
    """What the reviewer decides: the blocks and the glossary entries."""
    return len(draft.blocks) + len(draft.glossary)


def decided_count(draft: Draft, review: ReviewState | None) -> int:
    """The blocks and glossary entries of the draft that the review decides."""
    if review is None:
        return 0
    ids = {b.id for b in draft.blocks} | set(glossary_ids(draft))
    return sum(1 for block_id in review.by_block() if block_id in ids)


def review_counts(data: ReviewData) -> dict[str, Any]:
    """The counts the drafts list shows for a draft (schemas.JobCounts): the findings
    and the facts of the version, and the review's progress."""
    blocks, document = block_issues(data.draft, data.rules, data.judge)
    counts = severity_counts([i for issues in blocks.values() for i in issues] + document)
    facts = fact_counts(
        fact_rows(data.draft, data.factsheet, data.judge, data.source) if data.factsheet else []
    )
    return {
        "errors": counts["error"],
        "warnings": counts["warn"],
        "facts_present": facts["present"],
        "facts_total": facts["total"],
        "blocks": review_items(data.draft),
        "decided": decided_count(data.draft, data.review),
        "complete": bool(data.review and data.review.completed),
    }
