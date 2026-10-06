"""Runs a job through the pipeline and stores every artifact (docs/architecture.md §4).

Conditions (§9): P0 and the P0-ZH pair are single-prompt baselines (one sentence, or the
Canton of Zurich's prompt); P1 is understand, write and the rule check; P2 adds the judge
and the repair loop. Every stage stores its result before the
next starts, so a failed job resumes from the last good stage.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable

from leichtfacile.config import Settings
from leichtfacile.llm.client import LLMClient, LLMError, LLMResult
from leichtfacile.llm.json_out import LLMOutputError
from leichtfacile.pipeline import render, stages
from leichtfacile.pipeline.labels import label
from leichtfacile.pipeline.prompts import prompt_versions
from leichtfacile.pipeline.stages import RepairRequest
from leichtfacile.rules import check_draft
from leichtfacile.schemas import (
    BASELINE_CONDITIONS,
    Draft,
    FactSheet,
    Finding,
    Job,
    JobConfig,
    JudgeReport,
    PipelineSummary,
    RuleFindings,
    SourceDocument,
)
from leichtfacile.store import Store

log = logging.getLogger(__name__)

# Rule families whose findings the model can fix by rewriting a block. A value the
# source does not contain (FACT-06) is fixed the same way; a missing fact value
# (FACT-01) gets new sentences. Provenance and bookkeeping findings (FACT-02 to
# FACT-05) and layout go to the reviewer instead.
REPAIRABLE = ("LEN", "ORD", "GRAM", "NEG", "LEX", "NUM", "CH")
REPAIRABLE_RULES = ("FACT-06",)
STAGE_ORDER = ("understand", "write", "check", "judge", "repair", "review")
MAX_MISSING_PER_ROUND = 5
MISSING_PRIORITY = {
    kind: rank
    for rank, kind in enumerate(
        ("deadline", "amount", "obligation", "condition", "right", "contact", "procedure")
    )
}
ARTIFACTS_FROM = {
    "understand": ["factsheet", "draft", "rules", "judge", "summary", "review"],
    "write": ["draft", "rules", "judge", "summary", "review"],
    "judge": ["judge", "summary", "review"],
}


class PipelineError(RuntimeError):
    pass


class _Stopped(Exception):  # noqa: N818  (control flow, not an error)
    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


def repairable(finding: Finding) -> bool:
    """Whether a repair round can fix the finding by rewriting its block."""
    return finding.rule_id.split("-")[0] in REPAIRABLE or finding.rule_id in REPAIRABLE_RULES


def blocking_count(rules: RuleFindings, judge: JudgeReport | None) -> int:
    """Findings that should not survive into the draft the reviewer gets."""
    count = sum(
        1
        for f in rules.findings
        if f.severity == "error" and (repairable(f) or f.rule_id == "FACT-01")
    )
    if judge:
        count += sum(1 for c in judge.fact_checks if c.status != "present")
        count += len(judge.unsupported)
    return count


def build_request(
    draft: Draft,
    rules: RuleFindings,
    judge: JudgeReport | None,
    factsheet: FactSheet,
    *,
    include_warnings: bool = True,
) -> RepairRequest:
    """What a repair round should fix. Without warnings, the round concentrates on what
    blocks the draft: rule errors, missing fact values and the judge's problems. A small
    model asked to fix everything at once tends to fix nothing (docs/prompts.md)."""
    severities = ("error", "warn") if include_warnings else ("error",)
    lang = draft.lang
    blocks = draft.by_id()
    facts = {f.id: f for f in factsheet.facts}
    problems: dict[str, list[str]] = defaultdict(list)
    missing: set[str] = set()
    for f in rules.findings:
        if f.block_id in blocks and f.severity in severities and repairable(f):
            problems[f.block_id].append(render.finding_line(f, lang))
        elif f.rule_id == "FACT-01" and f.fact_id:
            missing.add(f.fact_id)
    if judge:
        for u in judge.unsupported:
            problems[u.block_id].append(
                f"  - SEM-06: {label(lang, 'unsupported')} {u.note}".rstrip()
            )
        for s in judge.semantic_findings:
            block = blocks.get(s.block_id)
            if block is not None and block.kind == "heading":
                continue  # a repair turns a question heading into a statement
            problems[s.block_id].append(f"  - {s.rule_id}: {s.note}".rstrip())
        for c in judge.fact_checks:
            fact = facts.get(c.fact_id)
            if fact is None:
                continue
            if c.status == "distorted":
                for block_id in c.block_ids:
                    wrong = label(lang, "distorted", fact_id=c.fact_id, note=c.note, fact=fact.text)
                    problems[block_id].append(f"  - {wrong}")
            elif c.status == "missing" and fact.must_keep:
                missing.add(c.fact_id)
    # A few missing facts per round, the most important kinds first: a small model adds
    # some of a long list and drops the rest; the next round takes the next ones.
    ordered_missing = sorted(
        (f for f in factsheet.facts if f.id in missing),
        key=lambda f: (MISSING_PRIORITY.get(f.kind, len(MISSING_PRIORITY)), f.id),
    )[:MAX_MISSING_PER_ROUND]
    return RepairRequest({k: v for k, v in problems.items() if k in blocks}, ordered_missing)


class Orchestrator:
    def __init__(self, store: Store, llm: LLMClient, settings: Settings) -> None:
        self.store = store
        self.llm = llm
        self.settings = settings

    # -- public -----------------------------------------------------------------------

    def run(self, job_id: str, *, stop_after: str | None = None) -> None:
        """Run or resume a job. stop_after: understand, write, check or judge."""
        if stop_after is not None and stop_after not in STAGE_ORDER:
            raise PipelineError(f"unknown stage {stop_after!r}; use one of {STAGE_ORDER}")
        self._stop_after = stop_after
        job = self.store.get_job(job_id)
        if job is None:
            raise PipelineError(f"unknown job {job_id}")
        try:
            self._set(job_id, status="running", error=None)
            source = self.store.get_artifact(job_id, "source", SourceDocument)
            if source is None:
                raise PipelineError("the job has no source document")
            if job.config.lang and job.config.lang != source.lang:
                source = source.model_copy(update={"lang": job.config.lang})
            if job.config.condition in BASELINE_CONDITIONS:
                self._run_baseline(job, source)
            else:
                self._run_pipeline(job, source)
            self._set(job_id, status="needs_review", stage="review")
        except _Stopped as stop:
            self._set(job_id, status="needs_review", stage=f"stopped after {stop.stage}")
        except Exception as exc:  # the job fails; the service keeps running
            log.exception("job %s failed", job_id)
            self._set(job_id, status="failed", error=f"{type(exc).__name__}: {exc}"[:2000])

    def rerun(self, job_id: str, from_stage: str) -> None:
        names = ARTIFACTS_FROM.get(from_stage)
        if names is None:
            raise PipelineError(f"cannot rerun from {from_stage!r}; use {sorted(ARTIFACTS_FROM)}")
        if from_stage == "judge":
            for name in ("draft", "rules"):
                for version in self.store.versions(job_id, name):
                    if version > 1:
                        self.store.delete_artifacts_version(job_id, name, version)
        self.store.delete_artifacts(job_id, names)
        self._set(job_id, status="queued", stage=None, error=None)

    # -- conditions -------------------------------------------------------------------

    def _run_baseline(self, job: Job, source: SourceDocument) -> None:
        self._notes: list[str] = []
        draft = self.store.get_artifact(job.id, "draft", Draft, version=1)
        if draft is None:
            self._set(job.id, stage="baseline")
            if job.config.condition == "P0":
                draft, results = stages.baseline(
                    self.llm, source, level=job.config.level, model=job.config.writer_model
                )
            else:  # the Canton of Zurich's prompt, complete or condensed
                draft, results, self._notes = stages.baseline_zh(
                    self.llm,
                    source,
                    level=job.config.level,
                    variant=stages.zh_variant(job.config.condition),
                    model=job.config.writer_model,
                )
            self._record(job.id, results)
            self.store.put_artifact(job.id, "draft", draft, draft.version)
        rules = self._check(job, draft, source, None)
        self._summary(job, source, draft, rules=[rules], judge=None, rounds=0, reason="baseline")

    def _run_pipeline(self, job: Job, source: SourceDocument) -> None:
        cfg = job.config
        factsheet = self.store.get_artifact(job.id, "factsheet", FactSheet)
        if factsheet is None:
            self._set(job.id, stage="understand")
            factsheet, results = stages.understand(
                self.llm, source, level=cfg.level, model=self._understand_model(cfg)
            )
            self._record(job.id, results)
            factsheet = stages.complete_factsheet(factsheet, source)
            self.store.put_artifact(job.id, "factsheet", factsheet)
        self._maybe_stop("understand")

        draft = self.store.get_artifact(job.id, "draft", Draft, version=1)
        if draft is None:
            self._set(job.id, stage="write")
            draft, results = stages.write(
                self.llm, source, factsheet, level=cfg.level, model=cfg.writer_model
            )
            self._record(job.id, results)
            draft = stages.link_facts(draft, factsheet)
            self.store.put_artifact(job.id, "draft", draft, draft.version)
        self._maybe_stop("write")
        rules = self._check(job, draft, source, factsheet)
        self._maybe_stop("check")
        if cfg.condition == "P1":
            self._summary(job, source, draft, rules=[rules], judge=None, rounds=0, reason="P1")
            return

        self._notes: list[str] = []
        judge = self._judge(job, source, factsheet, draft) if cfg.use_judge else None
        self._maybe_stop("judge")
        history = [(draft, rules, judge)]
        reason = "no problems left"
        rounds = 0
        polished = False  # warnings get one round, once nothing blocking is left
        for rounds in range(1, cfg.max_repair_rounds + 1):  # noqa: B007
            blocking = blocking_count(rules, judge)
            if blocking == 0 and polished:
                reason = "only warnings left"
                rounds -= 1
                break
            request = build_request(draft, rules, judge, factsheet, include_warnings=blocking == 0)
            if not request:
                reason = "no problems left"
                rounds -= 1
                break
            polished = polished or blocking == 0
            self._set(job.id, stage=f"repair {rounds}")
            try:
                new_draft, results = stages.repair(
                    self.llm, source, factsheet, draft, request, model=cfg.writer_model
                )
            except (LLMError, LLMOutputError) as exc:
                # The drafts so far stay valid; the reviewer gets the best of them.
                self._record(job.id, getattr(exc, "results", []))
                self._notes.append(f"repair round {rounds} failed: {_short(exc)}")
                reason = "a repair round failed"
                rounds -= 1
                break
            self._record(job.id, results)
            new_draft = stages.link_facts(new_draft, factsheet)
            self.store.put_artifact(job.id, "draft", new_draft, new_draft.version)
            new_rules = self._check(job, new_draft, source, factsheet)
            if self._judge_again(judge, rules):
                new_judge = self._judge(job, source, factsheet, new_draft)
            else:
                new_judge = _carry_over(judge, draft, new_draft) if judge else None
                if new_judge:
                    self.store.put_artifact(job.id, "judge", new_judge, new_draft.version)
            history.append((new_draft, new_rules, new_judge))
            progress = blocking_count(new_rules, new_judge) < blocking
            draft, rules, judge = new_draft, new_rules, new_judge
            if blocking_count(rules, judge) == 0:
                reason = "no blocking problems left"
                break
            if not progress:
                reason = "a repair round brought no progress"
                break
        else:
            reason = f"stopped after {cfg.max_repair_rounds} repair rounds"
        best = min(history, key=lambda h: (blocking_count(h[1], h[2]), -h[0].version))
        self._summary(
            job,
            source,
            best[0],
            rules=[h[1] for h in history],
            judge=judge,
            rounds=max(rounds, 0),
            reason=reason,
            history=history,
        )

    # -- stages -----------------------------------------------------------------------

    def _check(
        self, job: Job, draft: Draft, source: SourceDocument, factsheet: FactSheet | None
    ) -> RuleFindings:
        self._set(job.id, stage="check")
        rules = check_draft(draft, source=source, factsheet=factsheet)
        self.store.put_artifact(job.id, "rules", rules, draft.version)
        return rules

    def _judge(
        self, job: Job, source: SourceDocument, factsheet: FactSheet, draft: Draft
    ) -> JudgeReport | None:
        existing = self.store.get_artifact(job.id, "judge", JudgeReport, version=draft.version)
        if existing:
            return existing
        self._set(job.id, stage="judge")
        model = job.config.judge_model or self.settings.judge_name
        try:
            report, results = stages.judge(self.llm, source, factsheet, draft, model=model)
        except (LLMError, LLMOutputError) as exc:
            # Without the judge the draft still has its rule and fact checks.
            self._record(job.id, getattr(exc, "results", []))
            getattr(self, "_notes", []).append(
                f"judge on draft {draft.version} failed: {_short(exc)}"
            )
            return None
        self._record(job.id, results)
        self.store.put_artifact(job.id, "judge", report, draft.version)
        return report

    @staticmethod
    def _judge_again(judge: JudgeReport | None, rules: RuleFindings) -> bool:
        """The judge reruns only when facts or invented statements were involved."""
        if judge is None:
            return False
        fact_issue = any(c.status != "present" for c in judge.fact_checks) or judge.unsupported
        return bool(fact_issue) or any(f.rule_id == "FACT-01" for f in rules.findings)

    def _summary(
        self,
        job: Job,
        source: SourceDocument,
        final: Draft,
        *,
        rules: list[RuleFindings],
        judge: JudgeReport | None,
        rounds: int,
        reason: str,
        history: list | None = None,
    ) -> None:
        blocking = (
            [blocking_count(h[1], h[2]) for h in history]
            if history
            else [blocking_count(r, None) for r in rules]
        )
        writer = self.llm.resolve_model(job.config.writer_model, False)[0]
        reader = self.llm.resolve_model(self._understand_model(job.config), False)[0]
        summary = PipelineSummary(
            condition=job.config.condition,
            final_version=final.version,
            rounds=rounds,
            stop_reason=reason,
            writer_model=writer,
            understand_model=reader
            if job.config.condition not in BASELINE_CONDITIONS and reader != writer
            else None,
            judge_model=(job.config.judge_model or self.settings.judge_name)
            if job.config.condition == "P2" and job.config.use_judge
            else None,
            prompt_versions=prompt_versions(source.lang),
            blocking_findings=blocking,
            notes=list(getattr(self, "_notes", [])),
        )
        self.store.put_artifact(job.id, "summary", summary)

    # -- helpers ----------------------------------------------------------------------

    def _understand_model(self, cfg: JobConfig) -> str | None:
        """The Understand stage's model: the job's, else LLM_UNDERSTAND_NAME, else the
        job's writer (None: LLM_NAME). The hybrid lets the 70B read and the 8B write."""
        return cfg.understand_model or self.settings.llm_understand_name or cfg.writer_model

    def _maybe_stop(self, stage: str) -> None:
        if getattr(self, "_stop_after", None) == stage:
            raise _Stopped(stage)

    def _record(self, job_id: str, results: Iterable[LLMResult]) -> None:
        for result in results:
            self.store.add_usage(job_id, result.usage)

    def _set(self, job_id: str, **fields: object) -> None:
        self.store.update_job(job_id, **fields)


def _short(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:300]


def _carry_over(judge: JudgeReport, old: Draft, new: Draft) -> JudgeReport:
    """Keep the judge's findings for blocks the repair did not touch."""
    unchanged = {
        b.id for b in new.blocks if (o := old.by_id().get(b.id)) is not None and o.text == b.text
    }
    existing = set(new.by_id())
    return judge.model_copy(
        update={
            "draft_version": new.version,
            "fact_checks": [
                c.model_copy(update={"block_ids": [b for b in c.block_ids if b in existing]})
                for c in judge.fact_checks
            ],
            "unsupported": [u for u in judge.unsupported if u.block_id in unchanged],
            "semantic_findings": [s for s in judge.semantic_findings if s.block_id in unchanged],
        }
    )
