"""Runs a job through the pipeline and stores every artifact (docs/architecture.md §4).

Conditions (§9): P0 and the P0-ZH pair are single-prompt baselines (one sentence, or the
Canton of Zurich's prompt); P1 is understand, write and the rule check; P2 adds the judge
and the repair loop. Every stage stores its result before the
next starts, so a failed job resumes from the last good stage.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from leichtfacile.config import Settings
from leichtfacile.llm.client import LLMClient, LLMError
from leichtfacile.llm.json_out import LLMOutputError
from leichtfacile.pipeline import render, stages
from leichtfacile.pipeline.labels import label
from leichtfacile.pipeline.prompts import prompt_versions
from leichtfacile.pipeline.stages import RepairRequest
from leichtfacile.rules import check_draft
from leichtfacile.rules.decision import protect_factsheet
from leichtfacile.rules.glossary import fill_glossary
from leichtfacile.rules.medication import medication_names
from leichtfacile.rules.mediopunkt import apply_mediopunkt
from leichtfacile.rules.swiss import apply_ss
from leichtfacile.rules.vocabulary import OFFICE_RULES, vocabulary_version
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
# source does not contain (FACT-06) is fixed the same way, and a medication written
# apart from its dose (FACT-09) on the block that names it; a missing fact value
# (FACT-01) gets new sentences. Provenance and bookkeeping findings (FACT-02 to
# FACT-05) and layout go to the reviewer instead.
REPAIRABLE = ("LEN", "ORD", "GRAM", "NEG", "LEX", "NUM", "CH")
REPAIRABLE_RULES = ("FACT-06", "FACT-09")
# Findings that name a fact the draft lacks: a missing must-keep value, and in decision
# mode a dropped part of the operative part or the appeal instructions (rules/decision.py).
MISSING_RULES = ("FACT-01", "FACT-08")
STAGE_ORDER = ("understand", "write", "check", "judge", "repair", "review")
MAX_MISSING_PER_ROUND = 5
MISSING_PRIORITY = {
    kind: rank
    for rank, kind in enumerate(
        (
            "medication",
            "deadline",
            "amount",
            "obligation",
            "condition",
            "right",
            "contact",
            "procedure",
        )
    )
}
ARTIFACTS_FROM = {
    "understand": ["factsheet", "draft", "rules", "judge", "repair", "summary", "review"],
    "write": ["draft", "rules", "judge", "repair", "summary", "review"],
    "judge": ["judge", "repair", "summary", "review"],
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


def missing_count(rules: RuleFindings) -> int:
    """Must-keep values the draft still lacks (FACT-01), and in decision mode the parts
    of the decision it dropped (FACT-08): the measure of a facts round."""
    return sum(1 for f in rules.findings if f.rule_id in MISSING_RULES)


def version_key(rules: RuleFindings, judge: JudgeReport | None) -> tuple[int, int]:
    """The order of the draft versions, best first: the fewest must-keep values
    missing, then the fewest blocking findings. Facts come first because a reviewer can
    reject an unsupported sentence or mend a long one with a click, but cannot conjure
    a missing deadline; before 8 October 2026 the blocking count alone decided, and the
    dev rerun of 7 October showed it discarding versions a facts round had just filled
    (docs/prompts.md, "Fact-retention diagnosis", bucket k)."""
    return (missing_count(rules), blocking_count(rules, judge))


def blocking_count(rules: RuleFindings, judge: JudgeReport | None) -> int:
    """Findings that should not survive into the draft the reviewer gets."""
    count = sum(
        1
        for f in rules.findings
        if f.severity == "error" and (repairable(f) or f.rule_id in MISSING_RULES)
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
    facts_only: bool = False,
    limit: int = MAX_MISSING_PER_ROUND,
    vocabulary: bool = True,
    only: tuple[str, ...] = (),
) -> RepairRequest:
    """What a repair round should fix. Without warnings, the round concentrates on what
    blocks the draft: rule errors, missing fact values and the judge's problems. A small
    model asked to fix everything at once tends to fix nothing (docs/prompts.md). A
    facts-only round asks for the missing facts alone and flags no block. Without
    `vocabulary` the office words of LEX-07 are left to the reviewer. With `only`, the
    round asks for the findings of these rules alone, no fact and no judge's problem:
    the vocabulary round."""
    severities = ("error", "warn") if include_warnings else ("error",)
    lang = draft.lang
    blocks = draft.by_id()
    if only:
        flagged: dict[str, list[str]] = defaultdict(list)
        for f in rules.findings:
            if f.rule_id in only and f.block_id in blocks and f.severity in ("error", "warn"):
                flagged[f.block_id].append(render.finding_line(f, lang))
        return RepairRequest(dict(flagged), [])
    facts = {f.id: f for f in factsheet.facts}
    problems: dict[str, list[str]] = defaultdict(list)
    missing: set[str] = set()
    dropped: set[str] = set()  # parts of a decision (FACT-08): first in the list
    for f in rules.findings:
        if not vocabulary and f.rule_id in OFFICE_RULES:
            continue
        if f.block_id in blocks and f.severity in severities and repairable(f):
            problems[f.block_id].append(render.finding_line(f, lang))
        elif f.rule_id in MISSING_RULES and f.fact_id:
            missing.add(f.fact_id)
            if f.rule_id == "FACT-08":
                dropped.add(f.fact_id)
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
    # A few missing facts per round, the most important kinds first (a dropped part of a
    # decision before any value): a small model adds some of a long list and drops the
    # rest; the next round takes the next ones.
    ordered_missing = sorted(
        (f for f in factsheet.facts if f.id in missing),
        key=lambda f: (
            f.id not in dropped,
            MISSING_PRIORITY.get(f.kind, len(MISSING_PRIORITY)),
            f.id,
        ),
    )[:limit]
    if facts_only:
        return RepairRequest({}, ordered_missing)
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
        # Each model call is billed to the job when it is made, so a stage that fails
        # after some calls has them in the usage too.
        with self.llm.recording(lambda usage: self.store.add_usage(job_id, usage)):
            self._run(job_id, job)

    def _run(self, job_id: str, job: Job) -> None:
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
                draft, _ = stages.baseline(
                    self.llm, source, level=job.config.level, model=job.config.writer_model
                )
            else:  # the Canton of Zurich's prompt, complete or condensed
                draft, _, self._notes = stages.baseline_zh(
                    self.llm,
                    source,
                    level=job.config.level,
                    variant=stages.zh_variant(job.config.condition),
                    model=job.config.writer_model,
                )
            self.store.put_artifact(job.id, "draft", draft, draft.version)
        rules = self._check(job, draft, source, None)
        self._summary(job, source, draft, rules=[rules], judge=None, rounds=0, reason="baseline")

    def _run_pipeline(self, job: Job, source: SourceDocument) -> None:
        cfg = job.config
        factsheet = self.store.get_artifact(job.id, "factsheet", FactSheet)
        if factsheet is None:
            self._set(job.id, stage="understand")
            factsheet, _ = stages.understand(
                self.llm,
                source,
                level=cfg.level,
                model=self._understand_model(cfg),
                mode=cfg.mode,
                addressee=cfg.addressee,
            )
            factsheet = stages.complete_factsheet(factsheet, source)
            if cfg.mode == "decision":
                factsheet = protect_factsheet(factsheet, source)
            if self.settings.use_vocabulary:
                factsheet = stages.vocabulary_terms(factsheet, source)
            self.store.put_artifact(job.id, "factsheet", factsheet)
        self._maybe_stop("understand")

        draft = self.store.get_artifact(job.id, "draft", Draft, version=1)
        if draft is None:
            self._set(job.id, stage="write")
            draft, _ = stages.write(
                self.llm,
                source,
                factsheet,
                level=cfg.level,
                model=cfg.writer_model,
                mode=cfg.mode,
                addressee=cfg.addressee,
            )
            draft = stages.link_facts(draft, factsheet, source)
            if self.settings.use_vocabulary:  # before the Mediopunkt: it splits the terms too
                draft, _ = fill_glossary(draft)
            # P1 and P2 only; a baseline measures the prompt
            draft, _ = apply_mediopunkt(draft, keep=medication_names(factsheet))
            draft, _ = apply_ss(draft)
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
            request = build_request(
                draft,
                rules,
                judge,
                factsheet,
                include_warnings=blocking == 0,
                vocabulary=self.settings.use_vocabulary,
            )
            if not request:
                reason = "no problems left"
                rounds -= 1
                break
            polished = polished or blocking == 0
            step = self._round(job, source, factsheet, draft, rules, judge, request, rounds)
            if step is None:
                # The drafts so far stay valid; the reviewer gets the best of them.
                reason = "a repair round failed"
                rounds -= 1
                break
            history.append(step)
            progress = blocking_count(step[1], step[2]) < blocking
            draft, rules, judge = step
            if blocking_count(rules, judge) == 0:
                reason = "no blocking problems left"
                break
            if not progress:
                reason = "a repair round brought no progress"
                break
        else:
            reason = f"stopped after {cfg.max_repair_rounds} repair rounds"
        # Facts-only rounds: the loop above stops when a round brings no progress on the
        # whole, which on the dev pairs left must-keep values missing in nearly every
        # job (docs/prompts.md). These rounds ask for the missing facts alone and are
        # measured by them: they go on while a round adds a fact, up to the limit.
        facts_rounds = 0
        # Not without repair (max_repair_rounds 0), and not after a round the endpoint
        # failed: then the drafts so far stand. After an answer the code could not use
        # (no valid JSON twice) the facts round still runs: a smaller prompt, a new try.
        limit = cfg.max_facts_rounds if cfg.max_repair_rounds else 0
        if reason == "a repair round failed" and self._round_failure == "endpoint":
            limit = 0
        for facts_rounds in range(1, limit + 1):  # noqa: B007
            missing = missing_count(rules)
            if missing == 0:
                facts_rounds -= 1
                break
            request = build_request(
                draft,
                rules,
                judge,
                factsheet,
                facts_only=True,
                limit=self.settings.max_missing_per_facts_round,
            )
            step = self._round(
                job, source, factsheet, draft, rules, judge, request, facts_rounds, kind="facts"
            )
            if step is None:
                reason = "a facts round failed"
                facts_rounds -= 1
                break
            history.append(step)
            draft, rules, judge = step
            if missing_count(rules) == 0:
                reason = "no missing facts left"
                break
            if missing_count(rules) >= missing:
                reason = "a facts round brought no progress"
                break
        else:
            if facts_rounds:
                reason = f"stopped after {facts_rounds} facts rounds"
        # The vocabulary round: the office words still in the best version, each sentence
        # rewritten with its everyday word (LEX-07), after everything else, so that the
        # repair rounds stay on the facts. Its version is a new one after the latest;
        # the choice below keeps it only if it loses no fact and adds no blocking problem.
        vocabulary_rounds = 0
        if (
            self.settings.use_vocabulary
            and cfg.max_repair_rounds
            and getattr(self, "_round_failure", None) != "endpoint"
        ):
            base = min(history, key=lambda h: (*version_key(h[1], h[2]), -h[0].version))
            request = build_request(*base, factsheet, only=OFFICE_RULES)
            if request:
                latest = max(h[0].version for h in history)
                step = self._round(
                    job, source, factsheet, *base, request, 1, kind="vocabulary", version=latest + 1
                )
                if step is not None:
                    history.append(step)
                    vocabulary_rounds = 1
        best = min(history, key=lambda h: (*version_key(h[1], h[2]), -h[0].version))
        self._summary(
            job,
            source,
            best[0],
            rules=[h[1] for h in history],
            judge=judge,
            rounds=max(rounds, 0),
            facts_rounds=max(facts_rounds, 0),
            reason=reason,
            history=history,
            vocabulary_rounds=vocabulary_rounds,
        )

    def _round(
        self,
        job: Job,
        source: SourceDocument,
        factsheet: FactSheet,
        draft: Draft,
        rules: RuleFindings,
        judge: JudgeReport | None,
        request: RepairRequest,
        number: int,
        *,
        kind: str = "repair",
        version: int | None = None,
    ) -> tuple[Draft, RuleFindings, JudgeReport | None] | None:
        """One repair round: the new version, checked and judged; None when the model
        call failed (the job goes on with the versions it has). `version`: the new
        version's number when it is not the next after `draft`."""
        cfg = job.config
        self._set(job.id, stage=f"{kind} {number}")
        self._round_failure: str | None = None
        try:
            new_draft, _, record = stages.repair(
                self.llm,
                source,
                factsheet,
                draft,
                request,
                model=cfg.writer_model,
                mode=cfg.mode,
                addressee=cfg.addressee,
                kind=kind,
                version=version,
            )
        except (LLMError, LLMOutputError) as exc:
            self._notes.append(f"{kind} round {number} failed: {_short(exc)}")
            self._round_failure = "endpoint" if isinstance(exc, LLMError) else "output"
            return None
        new_draft = stages.link_facts(new_draft, factsheet, source)
        if self.settings.use_vocabulary:  # a repair can bring a new hard term
            new_draft, _ = fill_glossary(new_draft)
        # Before the check: one text for all.
        new_draft, _ = apply_mediopunkt(new_draft, keep=medication_names(factsheet))
        new_draft, _ = apply_ss(new_draft)
        self.store.put_artifact(job.id, "draft", new_draft, new_draft.version)
        self.store.put_artifact(job.id, "repair", record, new_draft.version)
        new_rules = self._check(job, new_draft, source, factsheet)
        if self._judge_again(judge, rules):
            new_judge = self._judge(job, source, factsheet, new_draft)
        else:
            new_judge = _carry_over(judge, draft, new_draft) if judge else None
            if new_judge:
                self.store.put_artifact(job.id, "judge", new_judge, new_draft.version)
        return new_draft, new_rules, new_judge

    # -- stages -----------------------------------------------------------------------

    def _check(
        self, job: Job, draft: Draft, source: SourceDocument, factsheet: FactSheet | None
    ) -> RuleFindings:
        self._set(job.id, stage="check")
        rules = check_draft(draft, source=source, factsheet=factsheet, mode=job.config.mode)
        self.store.put_artifact(job.id, "rules", rules, draft.version)
        return rules

    def _judge(
        self, job: Job, source: SourceDocument, factsheet: FactSheet, draft: Draft
    ) -> JudgeReport | None:
        existing = self.store.get_artifact(job.id, "judge", JudgeReport, version=draft.version)
        if existing:
            return existing
        self._set(job.id, stage="judge")
        model = job.config.judge_model or self.llm.judge_model()
        try:
            report, _ = stages.judge(
                self.llm,
                source,
                factsheet,
                draft,
                model=model,
                mode=job.config.mode,
                addressee=job.config.addressee,
            )
        except (LLMError, LLMOutputError) as exc:
            # Without the judge the draft still has its rule and fact checks.
            getattr(self, "_notes", []).append(
                f"judge on draft {draft.version} failed: {_short(exc)}"
            )
            return None
        self.store.put_artifact(job.id, "judge", report, draft.version)
        return report

    @staticmethod
    def _judge_again(judge: JudgeReport | None, rules: RuleFindings) -> bool:
        """The judge reruns only when facts or invented statements were involved."""
        if judge is None:
            return False
        fact_issue = any(c.status != "present" for c in judge.fact_checks) or judge.unsupported
        return bool(fact_issue) or any(f.rule_id in MISSING_RULES for f in rules.findings)

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
        facts_rounds: int = 0,
        vocabulary_rounds: int = 0,
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
            mode=job.config.mode,
            final_version=final.version,
            rounds=rounds,
            facts_rounds=facts_rounds,
            vocabulary_rounds=vocabulary_rounds,
            stop_reason=reason,
            writer_model=writer,
            understand_model=reader
            if job.config.condition not in BASELINE_CONDITIONS and reader != writer
            else None,
            judge_model=(job.config.judge_model or self.llm.judge_model())
            if job.config.condition == "P2" and job.config.use_judge
            else None,
            prompt_versions=prompt_versions(source.lang),
            blocking_findings=blocking,
            notes=list(getattr(self, "_notes", [])),
            vocabulary=vocabulary_version(source.lang)
            if self.settings.use_vocabulary and job.config.condition not in BASELINE_CONDITIONS
            else None,
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
