"""Runs a job through the pipeline and stores every artifact (track_2b/docs/architecture.md §4).

Conditions (§9): P0 and the P0-ZH pair are single-prompt baselines (one sentence, or the
Canton of Zurich's prompt); P1 is understand, write and the rule check; P2 adds the judge
and the repair loop. Every stage stores its result before the
next starts, so a failed job resumes from the last good stage.

One orchestrator serves every worker thread. What belongs to one run (the notes, the
last round's failure, the stage to stop after, the time budget and the stop signal)
lives in a `RunState` made by `run()` and passed along, never on the orchestrator.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from leichtfacile import logs
from leichtfacile.config import Settings
from leichtfacile.lifecycle import job_counts
from leichtfacile.llm.client import LLMClient, LLMError, LLMInterrupted, RunLimit
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
    AnsweredAddition,
    Draft,
    DroppedText,
    FactSheet,
    Finding,
    Job,
    JobConfig,
    JudgeReport,
    PipelineSummary,
    RepairRecord,
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
# The error a job carries when it was stopped (web/templates/_progress.html shows it as
# such) or ran over its time budget (`JOB_TIME_BUDGET_S`).
CANCELLED = "cancelled"
OVER_BUDGET = "stopped after the time budget of {seconds} s"


class PipelineError(RuntimeError):
    pass


class JobBusy(PipelineError):
    """A worker is running the job: stop it before a rerun or a deletion (audit V14)."""


class _Stopped(Exception):  # noqa: N818  (control flow, not an error)
    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


@dataclass
class RunState:
    """What belongs to one `run()`: made per call, passed to every step (audit B2)."""

    job_id: str
    stop_after: str | None = None  # understand, write, check or judge: for tests and the CLI
    notes: list[str] = field(default_factory=list)  # stages that failed and were skipped
    round_failure: str | None = None  # "endpoint" or "output" after a failed round
    limit: RunLimit = field(default_factory=RunLimit)

    @property
    def stop(self) -> threading.Event:
        assert self.limit.stop is not None
        return self.limit.stop


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
    (track_2b/docs/prompts.md, "Fact-retention diagnosis", bucket k)."""
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
    model asked to fix everything at once tends to fix nothing (track_2b/docs/prompts.md). A
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
    def __init__(
        self,
        store: Store,
        llm: LLMClient,
        settings: Settings,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.store = store
        self.llm = llm
        self.settings = settings
        self._clock = clock
        self._runs: dict[str, RunState] = {}  # the jobs running now, by id
        self._runs_lock = threading.Lock()

    # -- public -----------------------------------------------------------------------

    def run(self, job_id: str, *, stop_after: str | None = None) -> None:
        """Run or resume a job. stop_after: understand, write, check or judge."""
        if stop_after is not None and stop_after not in STAGE_ORDER:
            raise PipelineError(f"unknown stage {stop_after!r}; use one of {STAGE_ORDER}")
        job = self.store.get_job(job_id)
        if job is None:
            raise PipelineError(f"unknown job {job_id}")
        budget = self.settings.job_time_budget_s
        run = RunState(
            job_id,
            stop_after,
            limit=RunLimit(
                deadline=self._clock() + budget if budget else None,
                stop=threading.Event(),
                clock=self._clock,
            ),
        )
        with self._runs_lock:
            self._runs[job_id] = run
        logged = logs.job_id.set(job_id)  # every log line of the run names the job
        try:
            # Each model call is billed to the job when it is made, so a stage that fails
            # after some calls has them in the usage too. The limit ends a stopped job's
            # calls early (llm/client.py). The recorded runs of the prepared letters
            # answer a job's first run only (no call billed yet): a rerun asks the model.
            # A job run without cache (`live`) takes neither them nor cached responses.
            with (
                self.llm.recording(lambda usage: self.store.add_usage(job_id, usage)),
                self.llm.limited(run.limit),
                self.llm.replaying(not job.usage and not job.config.live),
                self.llm.reading_cache(not job.config.live),
            ):
                self._run(run, job)
        finally:
            logs.job_id.reset(logged)
            with self._runs_lock:
                self._runs.pop(job_id, None)

    def cancel(self, job_id: str) -> bool:
        """Ask the worker running the job to stop: at the next stage, the next model
        attempt or the next streamed chunk the job fails with `CANCELLED` and keeps the
        artifacts it has. False when no worker runs it."""
        with self._runs_lock:
            run = self._runs.get(job_id)
        if run is None:
            return False
        run.stop.set()
        return True

    def running(self) -> list[str]:
        with self._runs_lock:
            return list(self._runs)

    def _run(self, run: RunState, job: Job) -> None:
        job_id = run.job_id
        try:
            self._set(job_id, status="running", error=None)
            source = self.store.get_artifact(job_id, "source", SourceDocument)
            if source is None:
                raise PipelineError("the job has no source document")
            if job.config.lang and job.config.lang != source.lang:
                source = source.model_copy(update={"lang": job.config.lang})
            if job.config.condition in BASELINE_CONDITIONS:
                self._run_baseline(run, job, source)
            else:
                self._run_pipeline(run, job, source)
            self._done(job, status="needs_review", stage="review")
        except _Stopped as stop:
            self._done(job, status="needs_review", stage=f"stopped after {stop.stage}")
        except LLMInterrupted as exc:
            error = (
                CANCELLED
                if exc.reason == "cancelled"
                else OVER_BUDGET.format(seconds=int(self.settings.job_time_budget_s))
            )
            log.info("job %s %s", job_id, error)
            self._set(job_id, status="failed", error=error)
        except (LLMError, LLMOutputError) as exc:
            # Known failures carry a message without the document's or the model's
            # words (llm/json_out.redacted_error); no traceback, whose chained cause
            # would print the validation error with its input values (audit V10).
            log.error("job %s failed: %s", job_id, _short(exc))
            self._set(job_id, status="failed", error=f"{type(exc).__name__}: {exc}"[:2000])
        except Exception as exc:  # the job fails; the service keeps running
            log.exception("job %s failed", job_id)
            self._set(job_id, status="failed", error=f"{type(exc).__name__}: {exc}"[:2000])

    def _done(self, job: Job, **fields: object) -> None:
        """The job ends with the counts the drafts list shows (audit B3). The counts
        are a convenience: a failure in them never costs a finished job, the list
        computes them on its first visit instead."""
        try:
            fields["counts"] = job_counts(self.store, job)
        except Exception:
            log.exception("job %s: the counts for the drafts list could not be computed", job.id)
        self._set(job.id, **fields)

    def rerun(self, job_id: str, from_stage: str) -> None:
        """Delete the artifacts from `from_stage` on and queue the job again, in one
        guarded step: `JobBusy` while a worker runs it (audit V14)."""
        names = ARTIFACTS_FROM.get(from_stage)
        if names is None:
            raise PipelineError(f"cannot rerun from {from_stage!r}; use {sorted(ARTIFACTS_FROM)}")
        trim = ("draft", "rules") if from_stage == "judge" else ()
        if not self.store.requeue(job_id, delete=names, trim=trim):
            if self.store.get_job(job_id) is None:
                raise PipelineError(f"unknown job {job_id}")
            raise JobBusy(f"job {job_id} is running; stop it first")

    # -- conditions -------------------------------------------------------------------

    def _run_baseline(self, run: RunState, job: Job, source: SourceDocument) -> None:
        draft = self.store.get_artifact(job.id, "draft", Draft, version=1)
        if draft is None:
            self._stage(run, "baseline")
            if job.config.condition == "P0":
                draft, _ = stages.baseline(
                    self.llm, source, level=job.config.level, model=job.config.writer_model
                )
            else:  # the Canton of Zurich's prompt, complete or condensed
                draft, _, notes = stages.baseline_zh(
                    self.llm,
                    source,
                    level=job.config.level,
                    variant=stages.zh_variant(job.config.condition),
                    model=job.config.writer_model,
                )
                run.notes.extend(notes)
            self.store.put_artifact(job.id, "draft", draft, draft.version)
        rules = self._check(run, job, draft, source, None)
        self._summary(
            run, job, source, draft, rules=[rules], judge=None, rounds=0, reason="baseline"
        )

    def _run_pipeline(self, run: RunState, job: Job, source: SourceDocument) -> None:
        cfg = job.config
        factsheet = self.store.get_artifact(job.id, "factsheet", FactSheet)
        if factsheet is None:
            self._stage(run, "understand")
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
        self._maybe_stop(run, "understand")

        draft = self.store.get_artifact(job.id, "draft", Draft, version=1)
        if draft is None:
            self._stage(run, "write")
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
        self._maybe_stop(run, "write")
        rules = self._check(run, job, draft, source, factsheet)
        self._maybe_stop(run, "check")
        if cfg.condition == "P1":
            self._summary(run, job, source, draft, rules=[rules], judge=None, rounds=0, reason="P1")
            return

        judge = self._judge(run, job, source, factsheet, draft) if cfg.use_judge else None
        self._maybe_stop(run, "judge")
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
            step = self._round(run, job, source, factsheet, draft, rules, judge, request, rounds)
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
        # job (track_2b/docs/prompts.md). These rounds ask for the missing facts alone and are
        # measured by them: they go on while a round adds a fact, up to the limit.
        facts_rounds = 0
        # Not without repair (max_repair_rounds 0), and not after a round the endpoint
        # failed: then the drafts so far stand. After an answer the code could not use
        # (no valid JSON twice) the facts round still runs: a smaller prompt, a new try.
        limit = cfg.max_facts_rounds if cfg.max_repair_rounds else 0
        if reason == "a repair round failed" and run.round_failure == "endpoint":
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
                run, job, source, factsheet, draft, rules, judge, request, facts_rounds,
                kind="facts",
            )  # fmt: skip
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
        # The recover round (MAX_RECOVER_FACTS, off by default): the must-keep values
        # still missing in the best version, each asked for alone with its source
        # paragraph and its value named (stages.recover_fact, the review page's "Suggest
        # a sentence"); the sentences code accepts go after their blocks as one new
        # version, checked and judged. The choice below keeps it only if it is better.
        endpoint_down = run.round_failure == "endpoint"
        if self.settings.max_recover_facts and cfg.max_repair_rounds and not endpoint_down:
            base = min(history, key=lambda h: (*version_key(h[1], h[2]), -h[0].version))
            latest = max(h[0].version for h in history)
            step = self._recover(run, job, source, factsheet, *base, version=latest + 1)
            if step is not None:
                history.append(step)
        # The polish round (MAX_POLISH_ROUNDS, 1 by default since 10 October 2026, PLAN.md
        # D-AF): the facts and recover rounds add the source's sentences nearly verbatim,
        # and the loop above never sees them again. Up to that many repair rounds on the
        # best version, for its rule findings alone: the errors, or the warnings once no
        # error is left; no fact and no judge's problem, so the round cannot fall into
        # the loop's no-progress spiral. Office words stay with the vocabulary round. The
        # choice below keeps a polished version only if it loses no fact and adds no
        # blocking finding.
        polish_rounds = 0
        if self.settings.max_polish_rounds and cfg.max_repair_rounds and not endpoint_down:
            for number in range(1, self.settings.max_polish_rounds + 1):
                base = min(history, key=lambda h: (*version_key(h[1], h[2]), -h[0].version))
                blocks = base[0].by_id()
                errors = any(
                    f.severity == "error" and f.block_id in blocks and repairable(f)
                    for f in base[1].findings
                )
                request = build_request(
                    base[0], base[1], None, factsheet,
                    include_warnings=not errors, limit=0, vocabulary=False,
                )  # fmt: skip
                if not request:
                    break
                latest = max(h[0].version for h in history)
                step = self._round(
                    run, job, source, factsheet, *base, request, number, kind="polish",
                    version=latest + 1,
                )  # fmt: skip
                if step is None:
                    break
                history.append(step)
                polish_rounds = number
        # The vocabulary round: the office words still in the best version, each sentence
        # rewritten with its everyday word (LEX-07), after everything else, so that the
        # repair rounds stay on the facts. Its version is a new one after the latest;
        # the choice below keeps it only if it loses no fact and adds no blocking problem.
        vocabulary_rounds = 0
        if self.settings.use_vocabulary and cfg.max_repair_rounds and not endpoint_down:
            base = min(history, key=lambda h: (*version_key(h[1], h[2]), -h[0].version))
            request = build_request(*base, factsheet, only=OFFICE_RULES)
            if request:
                latest = max(h[0].version for h in history)
                step = self._round(
                    run, job, source, factsheet, *base, request, 1, kind="vocabulary",
                    version=latest + 1,
                )  # fmt: skip
                if step is not None:
                    history.append(step)
                    vocabulary_rounds = 1
        best = min(history, key=lambda h: (*version_key(h[1], h[2]), -h[0].version))
        self._summary(
            run,
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
            polish_rounds=polish_rounds,
        )

    def _round(
        self,
        run: RunState,
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
        self._stage(run, f"{kind} {number}")
        run.round_failure = None
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
            run.notes.append(f"{kind} round {number} failed: {_short(exc)}")
            run.round_failure = "endpoint" if isinstance(exc, LLMError) else "output"
            return None
        return self._finish(run, job, source, factsheet, draft, rules, judge, new_draft, record)

    def _recover(
        self,
        run: RunState,
        job: Job,
        source: SourceDocument,
        factsheet: FactSheet,
        draft: Draft,
        rules: RuleFindings,
        judge: JudgeReport | None,
        *,
        version: int,
    ) -> tuple[Draft, RuleFindings, JudgeReport | None] | None:
        """The recover round: one call per missing must-keep value (FACT-01), the most
        important kinds first, up to MAX_RECOVER_FACTS; each call sees the draft with the
        sentences recovered before it. None when no sentence was accepted."""
        facts = {f.id: f for f in factsheet.facts}
        missing = {f.fact_id for f in rules.findings if f.rule_id == "FACT-01" and f.fact_id}
        wanted = sorted(
            (facts[i] for i in missing if i in facts),
            key=lambda f: (MISSING_PRIORITY.get(f.kind, len(MISSING_PRIORITY)), f.id),
        )[: self.settings.max_recover_facts]
        if not wanted:
            return None
        self._stage(run, "recover")
        record = RepairRecord(
            draft_version=version,
            parent_version=draft.version,
            kind="recover",
            requested_facts=[f.id for f in wanted],
        )
        current = draft
        for fact in wanted:
            try:
                rec, _ = stages.recover_fact(
                    self.llm, source, factsheet, current, fact.id, model=job.config.writer_model
                )
            except LLMInterrupted:
                raise  # a stopped job ends here, whatever came back so far
            except LLMError as exc:  # the endpoint is down: keep what came back so far
                run.notes.append(f"recover {fact.id} failed: {_short(exc)}")
                break
            except Exception as exc:  # the round is on by default: it never costs the job
                log.exception("recover %s failed", fact.id)  # the versions it has
                run.notes.append(f"recover {fact.id} failed: {_short(exc)}")
                break
            record.dropped += [
                DroppedText(text=t, reason="repeat", block_id=rec.block_id, fact_ids=[fact.id])
                for t in rec.dropped
            ]
            if rec.rejected or rec.resolved is False or not rec.block_id:
                run.notes.append(f"recover {fact.id}: {rec.rejected or 'value not found'}")
                continue
            record.additions.append(
                AnsweredAddition(after=rec.block_id, texts=list(rec.texts), fact_ids=[fact.id])
            )
            current = stages.add_sentences(current, rec.block_id, rec.texts, fact)
        if not record.additions:
            return None
        new_draft = current.model_copy(
            update={
                "version": version,
                "parent_version": draft.version,
                "origin": "repair",
                "code_edits": [],
            }
        )
        return self._finish(run, job, source, factsheet, draft, rules, judge, new_draft, record)

    def _finish(
        self,
        run: RunState,
        job: Job,
        source: SourceDocument,
        factsheet: FactSheet,
        draft: Draft,
        rules: RuleFindings,
        judge: JudgeReport | None,
        new_draft: Draft,
        record: RepairRecord,
    ) -> tuple[Draft, RuleFindings, JudgeReport | None]:
        """A round's new version after the model: code's edits, stored, checked and
        judged (again when facts were involved, else the judge's findings carried over)."""
        new_draft = stages.link_facts(new_draft, factsheet, source)
        if self.settings.use_vocabulary:  # a repair can bring a new hard term
            new_draft, _ = fill_glossary(new_draft)
        # Before the check: one text for all.
        new_draft, _ = apply_mediopunkt(new_draft, keep=medication_names(factsheet))
        new_draft, _ = apply_ss(new_draft)
        self.store.put_artifact(job.id, "draft", new_draft, new_draft.version)
        self.store.put_artifact(job.id, "repair", record, new_draft.version)
        new_rules = self._check(run, job, new_draft, source, factsheet)
        if self._judge_again(judge, rules):
            new_judge = self._judge(run, job, source, factsheet, new_draft)
        else:
            new_judge = _carry_over(judge, draft, new_draft) if judge else None
            if new_judge:
                self.store.put_artifact(job.id, "judge", new_judge, new_draft.version)
        return new_draft, new_rules, new_judge

    # -- stages -----------------------------------------------------------------------

    def _check(
        self,
        run: RunState,
        job: Job,
        draft: Draft,
        source: SourceDocument,
        factsheet: FactSheet | None,
    ) -> RuleFindings:
        self._stage(run, "check")
        rules = check_draft(draft, source=source, factsheet=factsheet, mode=job.config.mode)
        self.store.put_artifact(job.id, "rules", rules, draft.version)
        return rules

    def _judge(
        self,
        run: RunState,
        job: Job,
        source: SourceDocument,
        factsheet: FactSheet,
        draft: Draft,
    ) -> JudgeReport | None:
        existing = self.store.get_artifact(job.id, "judge", JudgeReport, version=draft.version)
        if existing:
            return existing
        self._stage(run, "judge")
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
            run.notes.append(f"judge on draft {draft.version} failed: {_short(exc)}")
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
        run: RunState,
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
        polish_rounds: int = 0,
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
            polish_rounds=polish_rounds,
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
            notes=list(run.notes),
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

    def _maybe_stop(self, run: RunState, stage: str) -> None:
        if run.stop_after == stage:
            raise _Stopped(stage)

    def _stage(self, run: RunState, stage: str) -> None:
        """Enter a stage: a stopped job or one over its budget ends here, before the
        stage's model call, and a running one shows the stage on its page."""
        run.limit.check()
        self._set(run.job_id, stage=stage)

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
            "dropped": [],  # the old version's unquoted verdicts say nothing about this one
            "semantic_findings": [s for s in judge.semantic_findings if s.block_id in unchanged],
        }
    )
