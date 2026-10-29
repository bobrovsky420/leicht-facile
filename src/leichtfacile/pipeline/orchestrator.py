"""Runs a job through the pipeline and stores every artifact (docs/architecture.md §4).

Conditions (§9): P0 and the P0-ZH pair are single-prompt baselines (one sentence, or the
Canton of Zurich's prompt); P1 is understand, write and the rule check; P2 adds the judge
and the rounds of pipeline/rounds.py. Every stage stores its result before the next
starts, so a failed job resumes from the last good stage.

One orchestrator serves every worker thread. What belongs to one run (the notes, the
last round's failure, the stage to stop after, the time budget and the stop signal)
lives in a `RunState` made by `run()` and passed along, never on the orchestrator.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from leichtfacile import logs
from leichtfacile.config import LLM, Settings
from leichtfacile.lifecycle import job_counts
from leichtfacile.llm.client import LLMClient, LLMError, LLMInterrupted, RunLimit
from leichtfacile.llm.json_out import LLMOutputError
from leichtfacile.llm.registry import Registry
from leichtfacile.pipeline import stages
from leichtfacile.pipeline.prompts import prompt_versions
from leichtfacile.pipeline.rounds import (
    MISSING_PRIORITY,
    MISSING_RULES,
    Step,
    best,
    blocking_count,
    missing_count,
    plan,
    request_for,
)
from leichtfacile.pipeline.stages import RepairRequest
from leichtfacile.rules import check_draft
from leichtfacile.rules.decision import protect_factsheet
from leichtfacile.rules.glossary import fill_glossary
from leichtfacile.rules.medication import medication_names
from leichtfacile.rules.mediopunkt import apply_mediopunkt
from leichtfacile.rules.swiss import apply_spelling
from leichtfacile.rules.vocabulary import vocabulary_version
from leichtfacile.schemas import (
    BASELINE_CONDITIONS,
    AnsweredAddition,
    Draft,
    DroppedText,
    FactSheet,
    Job,
    JobConfig,
    JudgeReport,
    PipelineSummary,
    RepairRecord,
    RoundRecord,
    RuleFindings,
    SourceDocument,
    StopReason,
)
from leichtfacile.store import Store

log = logging.getLogger(__name__)

STAGE_ORDER = ("understand", "write", "check", "judge", "repair", "review")
ARTIFACTS_FROM = {
    "understand": ["factsheet", "draft", "rules", "judge", "repair", "summary", "review"],
    "write": ["draft", "rules", "judge", "repair", "summary", "review"],
    "judge": ["judge", "repair", "summary", "review"],
}
# The error a job carries when it was stopped (web/templates/_progress.html shows it as
# such) or ran over its time budget (`jobs.time_budget_s`).
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
    llm: LLMClient = None  # type: ignore[assignment]  # the job's endpoint, set by run()

    @property
    def stop(self) -> threading.Event:
        assert self.limit.stop is not None
        return self.limit.stop


class Orchestrator:
    def __init__(
        self,
        store: Store,
        llm: LLMClient | Registry,
        settings: Settings | None = None,
        *,
        clients: Mapping[str, LLMClient] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """On a registry of clients (the web app's, which follows the settings), or on
        one client with its settings and the clients of the other presets a draft may
        pick, by name (a command, the tests)."""
        self.store = store
        if isinstance(llm, Registry):
            self.registry = llm
        else:
            assert settings is not None
            self.registry = Registry(settings, llm=llm, clients=clients)
        self._clock = clock
        self._runs: dict[str, RunState] = {}  # the jobs running now, by id
        self._runs_lock = threading.Lock()

    # -- public -----------------------------------------------------------------------

    @property
    def settings(self) -> Settings:
        """The settings as they are now (the registry reloads them on a change)."""
        return self.registry.settings

    @property
    def llm(self) -> LLMClient | None:
        """The client of the preset in use; None while it is not ready."""
        return self.registry.llm

    def client_for(self, job: Job) -> LLMClient:
        """The client of the job's preset: the one in use unless the job picked another.
        PipelineError when it is not ready (no key) or no longer offered."""
        name = job.config.endpoint
        try:
            return self.registry.client_for(name)
        except KeyError:
            raise PipelineError(
                f"the preset {name or self.registry.in_use} is not available (no key, or not "
                "offered any more)"
            ) from None

    def llm_for(self, job: Job) -> LLM:
        """The `[llm]` settings the job runs with; the preset in use when the job's is
        not available any more (a page can always be shown)."""
        try:
            return self.client_for(job).settings.llm
        except PipelineError:
            return self.settings.llm

    def presets(self) -> list[tuple[str, LLM]]:
        """The ready presets a draft may pick, the one in use first: name and settings."""
        return self.registry.ready()

    def run(self, job_id: str, *, stop_after: str | None = None) -> None:
        """Run or resume a job. stop_after: understand, write, check or judge."""
        if stop_after is not None and stop_after not in STAGE_ORDER:
            raise PipelineError(f"unknown stage {stop_after!r}; use one of {STAGE_ORDER}")
        job = self.store.get_job(job_id)
        if job is None:
            raise PipelineError(f"unknown job {job_id}")
        try:
            llm = self.client_for(job)
        except PipelineError as exc:  # recorded like any other failure of the job
            log.info("job %s failed: %s", job_id, exc)
            self._set(job_id, status="failed", error=str(exc))
            return
        budget = self.settings.jobs.time_budget_s
        run = RunState(
            job_id,
            stop_after,
            limit=RunLimit(
                deadline=self._clock() + budget if budget else None,
                stop=threading.Event(),
                clock=self._clock,
            ),
            llm=llm,
        )
        with self._runs_lock:
            self._runs[job_id] = run
        logged = logs.job_id.set(job_id)  # every log line of the run names the job
        try:
            # Each model call is billed to the job when it is made, so a stage that fails
            # after some calls has them in the usage too. The limit ends a stopped job's
            # calls early (llm/client.py).
            with (
                llm.recording(lambda usage: self.store.add_usage(job_id, usage)),
                llm.limited(run.limit),
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
                else OVER_BUDGET.format(seconds=int(self.settings.jobs.time_budget_s))
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
                    run.llm, source, level=job.config.level, model=job.config.writer_model
                )
            else:  # the Canton of Zurich's prompt, complete or condensed
                draft, _, notes = stages.baseline_zh(
                    run.llm,
                    source,
                    level=job.config.level,
                    variant=stages.zh_variant(job.config.condition),
                    model=job.config.writer_model,
                )
                run.notes.extend(notes)
            self.store.put_artifact(job.id, "draft", draft, draft.version)
        rules = self._check(run, job, draft, source, None)
        self._summary(run, job, source, [(draft, rules, None)], reason="baseline")

    def _run_pipeline(self, run: RunState, job: Job, source: SourceDocument) -> None:
        cfg = job.config
        factsheet = self.store.get_artifact(job.id, "factsheet", FactSheet)
        if factsheet is None:
            self._stage(run, "understand")
            factsheet, _ = stages.understand(
                run.llm,
                source,
                level=cfg.level,
                model=self._understand_model(run, cfg),
                mode=cfg.mode,
                addressee=cfg.addressee,
            )
            factsheet = stages.complete_factsheet(factsheet, source)
            if cfg.mode == "decision":
                factsheet = protect_factsheet(factsheet, source)
            if cfg.pipeline.vocabulary:
                factsheet = stages.vocabulary_terms(factsheet, source)
            self.store.put_artifact(job.id, "factsheet", factsheet)
        self._maybe_stop(run, "understand")

        draft = self.store.get_artifact(job.id, "draft", Draft, version=1)
        if draft is None:
            self._stage(run, "write")
            draft, _ = stages.write(
                run.llm,
                source,
                factsheet,
                level=cfg.level,
                model=cfg.writer_model,
                mode=cfg.mode,
                addressee=cfg.addressee,
            )
            draft = stages.link_facts(draft, factsheet, source)
            if cfg.pipeline.vocabulary:  # before the Mediopunkt: it splits the terms too
                draft, _ = fill_glossary(draft)
            # P1 and P2 only; a baseline measures the prompt
            draft, _ = apply_mediopunkt(draft, keep=medication_names(factsheet))
            draft, _ = apply_spelling(draft)
            self.store.put_artifact(job.id, "draft", draft, draft.version)
        self._maybe_stop(run, "write")
        rules = self._check(run, job, draft, source, factsheet)
        self._maybe_stop(run, "check")
        if cfg.condition == "P1":
            self._summary(run, job, source, [(draft, rules, None)], reason="p1")
            return

        judge = self._judge(run, job, source, factsheet, draft) if cfg.use_judge else None
        self._maybe_stop(run, "judge")
        history, records, reason = self._rounds(run, job, source, factsheet, (draft, rules, judge))
        self._summary(run, job, source, history, rounds=records, reason=reason)

    # -- the rounds after the first draft (pipeline/rounds.py) ----------------------------

    def _rounds(
        self,
        run: RunState,
        job: Job,
        source: SourceDocument,
        factsheet: FactSheet,
        first: Step,
    ) -> tuple[list[Step], list[RoundRecord], StopReason]:
        """The plan, kind by kind: every version made, one record per round, and why
        the repair and facts rounds ended. A round that fails leaves the versions so
        far standing; after a round the endpoint failed, nothing more runs."""
        options = job.config.pipeline
        history = [first]
        records: list[RoundRecord] = []
        reason: StopReason = "no_problems"
        for spec in plan(options):
            if spec.kind != "repair" and run.round_failure == "endpoint":
                break
            for number in range(1, spec.limit + 1):
                base = best(history) if spec.from_best else history[-1]
                draft, rules, judge = base
                before = (blocking_count(rules, judge), missing_count(rules))
                if spec.measure == "missing" and before[1] == 0:
                    break
                version = max(h[0].version for h in history) + 1
                if spec.kind == "recover":
                    step = self._recover(run, job, source, factsheet, *base, version=version)
                else:
                    request = request_for(spec, draft, rules, judge, factsheet, options)
                    if not request:
                        if spec.kind == "repair":
                            reason = "no_problems"
                        break
                    step = self._round(
                        run, job, source, factsheet, *base, request, number,
                        kind=spec.kind, version=version,
                    )  # fmt: skip
                if step is None:
                    if spec.kind == "repair":
                        reason = "round_failed"
                    elif spec.kind == "facts":
                        reason = "facts_round_failed"
                    break
                history.append(step)
                after = (blocking_count(step[1], step[2]), missing_count(step[1]))
                records.append(
                    RoundRecord(
                        kind=spec.kind,
                        number=number,
                        parent_version=draft.version,
                        version=step[0].version,
                        blocking_before=before[0],
                        blocking_after=after[0],
                        missing_before=before[1],
                        missing_after=after[1],
                    )
                )
                if spec.measure == "blocking":
                    if after[0] == 0:
                        reason = "no_blocking"
                        break
                    if after[0] >= before[0]:
                        reason = "no_progress"
                        break
                elif spec.measure == "missing":
                    if after[1] == 0:
                        reason = "no_missing_facts"
                        break
                    if after[1] >= before[1]:
                        reason = "facts_no_progress"
                        break
            else:  # every round of the kind ran
                if spec.kind == "repair":
                    reason = "max_rounds"
                elif spec.kind == "facts" and spec.limit:
                    reason = "max_facts_rounds"
        return history, records, reason

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
        kind: str,
        version: int,
    ) -> Step | None:
        """One round through the repair prompt: the new version, checked and judged; None
        when the model call failed (the job goes on with the versions it has)."""
        cfg = job.config
        self._stage(run, f"{kind} {number}")
        run.round_failure = None
        try:
            new_draft, _, record = stages.repair(
                run.llm,
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
    ) -> Step | None:
        """The recover round: one call per missing must-keep value (FACT-01), the most
        important kinds first, up to pipeline.recover_facts; each call sees the draft with
        the sentences recovered before it. None when no sentence was accepted."""
        facts = {f.id: f for f in factsheet.facts}
        missing = {f.fact_id for f in rules.findings if f.rule_id == "FACT-01" and f.fact_id}
        wanted = sorted(
            (facts[i] for i in missing if i in facts),
            key=lambda f: (MISSING_PRIORITY.get(f.kind, len(MISSING_PRIORITY)), f.id),
        )[: job.config.pipeline.recover_facts]
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
                    run.llm, source, factsheet, current, fact.id, model=job.config.writer_model
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
    ) -> Step:
        """A round's new version after the model: code's edits, stored, checked and
        judged (again when facts were involved, else the judge's findings carried over)."""
        new_draft = stages.link_facts(new_draft, factsheet, source)
        if job.config.pipeline.vocabulary:  # a repair can bring a new hard term
            new_draft, _ = fill_glossary(new_draft)
        # Before the check: one text for all.
        new_draft, _ = apply_mediopunkt(new_draft, keep=medication_names(factsheet))
        new_draft, _ = apply_spelling(new_draft)
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
        model = job.config.judge_model or run.llm.judge_model()
        try:
            report, _ = stages.judge(
                run.llm,
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
        history: list[Step],
        *,
        reason: StopReason,
        rounds: list[RoundRecord] | None = None,
    ) -> None:
        """The summary of the run: the best version is final (`best`), one record per
        round, the blocking findings of every version."""
        cfg = job.config
        final = best(history)[0]
        writer = run.llm.resolve_model(cfg.writer_model, False)[0]
        reader = run.llm.resolve_model(self._understand_model(run, cfg), False)[0]
        pipeline = cfg.condition not in BASELINE_CONDITIONS
        summary = PipelineSummary(
            condition=cfg.condition,
            mode=cfg.mode,
            final_version=final.version,
            rounds=rounds or [],
            stop_reason=reason,
            endpoint=cfg.endpoint or run.llm.settings.llm.preset,
            writer_model=writer,
            understand_model=reader if pipeline and reader != writer else None,
            judge_model=(cfg.judge_model or run.llm.judge_model())
            if cfg.condition == "P2" and cfg.use_judge
            else None,
            prompt_versions=prompt_versions(source.variety),
            blocking_findings=[blocking_count(h[1], h[2]) for h in history],
            notes=list(run.notes),
            vocabulary=vocabulary_version(source.lang)
            if pipeline and cfg.pipeline.vocabulary
            else None,
        )
        self.store.put_artifact(job.id, "summary", summary)

    # -- helpers ----------------------------------------------------------------------

    def _understand_model(self, run: RunState, cfg: JobConfig) -> str | None:
        return understand_model(
            run.llm.settings, understand=cfg.understand_model, writer=cfg.writer_model
        )

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


def understand_model(
    settings: Settings, *, understand: str | None, writer: str | None
) -> str | None:
    """The Understand stage's model: the job's, else the endpoint's `llm.models.understand`,
    else the job's writer (None: `llm.models.writer`). The hybrid lets the 70B read and
    the 8B write; the evaluation names its result files by this choice."""
    return understand or settings.llm.models.understand or writer


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
