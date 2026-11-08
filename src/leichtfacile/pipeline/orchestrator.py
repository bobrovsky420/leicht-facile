"""Runs a job through the pipeline and stores every artifact (docs/architecture.md §4).

Conditions (§9): P0 and the P0-ZH pair are single-prompt baselines (one sentence, or the
Canton of Zurich's prompt); P1 is understand, write and the rule check; P2 adds the judge
and the rounds of pipeline/rounds.py. Every stage stores its result before the next
starts, and every round its version with its record, so a job that failed or was
interrupted resumes from what is stored: the stages it has, and after the first draft
the rounds already done, each version with its checks (`_stored_rounds`), so a restart
costs at most the round under way. Every change of the job's state is an event the
store records with it (events.py): the claim, each stage's start and end, each round,
the end of the run and why.

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
from leichtfacile.events import CANCELLED
from leichtfacile.lifecycle import job_counts
from leichtfacile.llm.client import LLMClient, LLMError, LLMInterrupted, RunLimit
from leichtfacile.llm.json_out import LLMOutputError
from leichtfacile.llm.registry import Registry
from leichtfacile.pipeline import stages
from leichtfacile.pipeline.prompts import prompt_versions
from leichtfacile.pipeline.rounds import (
    MISSING_PRIORITY,
    MISSING_RULES,
    RoundSpec,
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
from leichtfacile.rules.lists import protect_lists
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
# The error a job carries when it ran over its time budget (`jobs.time_budget_s`); a
# stopped one carries `CANCELLED` (events.py; web/templates/_progress.html shows it so).
OVER_BUDGET = "stopped after the time budget of {seconds} s"


class PipelineError(RuntimeError):
    pass


class JobBusy(PipelineError):
    """A worker is running the job: stop it before a rerun or a deletion (audit V14)."""


class _Stopped(Exception):  # control flow, not an error
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
    stage: str | None = None  # the stage under way, for its `stage_finished` event
    cancelled_by: str | None = None  # who asked to stop the job (web/security.py's user)

    @property
    def stop(self) -> threading.Event:
        if self.limit.stop is None:
            raise RuntimeError("the run has no stop event")
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
            if settings is None:
                raise TypeError("a client needs its settings")
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
            self.store.record(job_id, "failed", {"error": str(exc)})
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
            # calls early (llm/client.py). The recorded runs of the sample letters answer
            # a job's first run alone (no call billed yet, llm/replay.py): a rerun asks
            # the model again.
            with (
                llm.recording(lambda usage: self.store.add_usage(job_id, usage)),
                llm.limited(run.limit),
                llm.replaying(not job.usage),
            ):
                self._run(run, job)
        finally:
            logs.job_id.reset(logged)
            with self._runs_lock:
                self._runs.pop(job_id, None)

    def cancel(self, job_id: str, *, by: str | None = None) -> bool:
        """Ask the worker running the job to stop: at the next stage, the next model
        attempt or the next streamed chunk the job fails with `CANCELLED` and keeps the
        artifacts it has; the `cancelled` event names `by`, the user who asked. False
        when no worker runs it."""
        with self._runs_lock:
            run = self._runs.get(job_id)
        if run is None:
            return False
        run.cancelled_by = by
        run.stop.set()
        return True

    def running(self) -> list[str]:
        with self._runs_lock:
            return list(self._runs)

    def _run(self, run: RunState, job: Job) -> None:
        job_id = run.job_id
        try:
            if job.status != "running":  # a worker's claim recorded it; a direct run here
                self.store.record(job_id, "claimed")
            source = self.store.get_artifact(job_id, "source", SourceDocument)
            if source is None:  # raised inside the try: the handler below records it
                raise PipelineError("the job has no source document")  # noqa: TRY301
            if job.config.lang and job.config.lang != source.lang:
                source = source.model_copy(update={"lang": job.config.lang})
            if job.config.condition in BASELINE_CONDITIONS:
                self._run_baseline(run, job, source)
            else:
                self._run_pipeline(run, job, source)
            self._done(run, job, stage="review")
        except _Stopped as stop:
            self._done(run, job, stage=f"stopped after {stop.stage}")
        except LLMInterrupted as exc:
            self._end_stage(run)
            if exc.reason == "cancelled":
                log.info("job %s %s", job_id, CANCELLED)
                payload = {"by": run.cancelled_by} if run.cancelled_by else {}
                self.store.record(job_id, "cancelled", payload)
            else:
                error = OVER_BUDGET.format(seconds=int(self.settings.jobs.time_budget_s))
                log.info("job %s %s", job_id, error)
                self.store.record(job_id, "failed", {"error": error})
        except (LLMError, LLMOutputError) as exc:
            # Known failures carry a message without the document's or the model's
            # words (llm/json_out.redacted_error); no traceback, whose chained cause
            # would print the validation error with its input values (audit V10).
            log.error("job %s failed: %s", job_id, _short(exc))  # noqa: TRY400
            self._failed(run, f"{type(exc).__name__}: {exc}"[:2000])
        except Exception as exc:  # the job fails; the service keeps running
            log.exception("job %s failed", job_id)
            self._failed(run, f"{type(exc).__name__}: {exc}"[:2000])

    def _failed(self, run: RunState, error: str) -> None:
        self._end_stage(run)
        self.store.record(run.job_id, "failed", {"error": error})

    def _done(self, run: RunState, job: Job, *, stage: str) -> None:
        """The job ends (`finished`) at `stage` with the counts the drafts list shows
        (audit B3). The counts are a convenience: a failure in them never costs a
        finished job, the list computes them on its first visit instead."""
        self._end_stage(run)
        counts = None
        try:
            counts = job_counts(self.store, job)
        except Exception:
            log.exception("job %s: the counts for the drafts list could not be computed", job.id)
        self.store.record(job.id, "finished", {"stage": stage}, counts=counts)

    def rerun(self, job_id: str, from_stage: str, *, by: str | None = None) -> None:
        """Delete the artifacts from `from_stage` on and queue the job again, in one
        guarded step: `JobBusy` while a worker runs it (audit V14). The `queued` event
        names the stage and `by`, the user who asked."""
        names = ARTIFACTS_FROM.get(from_stage)
        if names is None:
            raise PipelineError(f"cannot rerun from {from_stage!r}; use {sorted(ARTIFACTS_FROM)}")
        trim = ("draft", "rules") if from_stage == "judge" else ()
        if not self.store.requeue(job_id, delete=names, trim=trim, from_stage=from_stage, by=by):
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
                sender=cfg.sender,
            )
            factsheet = stages.complete_factsheet(factsheet, source)
            if cfg.mode == "decision":
                factsheet = protect_factsheet(factsheet, source)
            factsheet = protect_lists(factsheet, source)  # after the decision's parts
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
                sender=cfg.sender,
                address=cfg.address,
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
        the repair and facts rounds ended. The rounds a run before this one made
        (`_stored_rounds`) count as done: their records are rebuilt from their versions
        and the kind goes on from the next number, or ends where they ended it. A round
        that fails leaves the versions so far standing; after a round the endpoint
        failed, nothing more runs."""
        history, done = self._stored_rounds(run, job, source, factsheet, first)
        records: list[RoundRecord] = []
        reason: StopReason = "no_problems"
        for spec in plan(job.config.pipeline):
            if spec.kind != "repair" and run.round_failure == "endpoint":
                break
            stored = [d for d in done if d.kind == spec.kind]
            ended = _replayed(spec, stored, records)
            if ended is None:
                ended = self._kind(
                    run, job, source, factsheet, spec, history, len(stored) + 1, records
                )
            if ended:
                reason = ended
        return history, records, reason

    def _kind(
        self,
        run: RunState,
        job: Job,
        source: SourceDocument,
        factsheet: FactSheet,
        spec: RoundSpec,
        history: list[Step],
        start: int,
        records: list[RoundRecord],
    ) -> StopReason | None:
        """The rounds of one kind from the number `start` on, each version appended to
        `history` and its record to `records` and the log: the reason the kind ended,
        None when it leaves the reason as it was."""
        for number in range(start, spec.limit + 1):
            base = best(history) if spec.from_best else history[-1]
            before = _counts(base)
            if spec.measure == "missing" and before[1] == 0:
                return None
            version = max(h[0].version for h in history) + 1
            step, ended = self._step(run, job, source, factsheet, spec, base, number, version)
            if step is None:
                return ended
            history.append(step)
            after = _counts(step)
            record = _round_record(spec, number, base, step, before, after)
            records.append(record)
            self.store.record(job.id, "round_finished", record.model_dump())
            if ended := _stop_reason(spec, before, after):
                return ended
        # Every round of the kind ran.
        if spec.kind == "repair":
            return "max_rounds"
        if spec.kind == "facts" and spec.limit:
            return "max_facts_rounds"
        return None

    def _stored_rounds(
        self,
        run: RunState,
        job: Job,
        source: SourceDocument,
        factsheet: FactSheet,
        first: Step,
    ) -> tuple[list[Step], list[_Done]]:
        """The versions a run before this one made (a job queued again after a stop, a
        crash or a restart), each with its checks, and the round that made each, in
        order: what the rounds start from instead of draft 1. A version whose rule
        findings or judge report the crash came before gets them now, as `_finish`
        gives them to a new version. A resumed job used to run every round again,
        overwrite the stored versions and take the old version's judge report for the
        new one (audit of 6 November 2026)."""
        history = [first]
        done: list[_Done] = []
        by_version = {first[0].version: first}
        for version in self.store.versions(job.id, "draft"):
            if version <= first[0].version:
                continue
            draft = self.store.get_artifact(job.id, "draft", Draft, version=version)
            record = self.store.get_artifact(job.id, "repair", RepairRecord, version=version)
            if draft is None:
                continue
            kind = record.kind if record else "repair"
            parent = record.parent_version if record else version - 1
            base = by_version.get(parent, history[-1])
            rules = self.store.get_artifact(job.id, "rules", RuleFindings, version=version)
            if rules is None:
                rules = self._check(run, job, draft, source, factsheet)
            judge = self._judged(run, job, source, factsheet, base, draft)
            step: Step = (draft, rules, judge)
            history.append(step)
            by_version[version] = step
            done.append(_Done(kind, base, step))
        return history, done

    def _step(
        self,
        run: RunState,
        job: Job,
        source: SourceDocument,
        factsheet: FactSheet,
        spec: RoundSpec,
        base: Step,
        number: int,
        version: int,
    ) -> tuple[Step | None, StopReason | None]:
        """One round of the kind on `base`: the recover round, else the repair prompt with
        the round's request. No step means the kind's rounds end here: with the reason
        (a repair round with nothing to ask for, a failed repair or facts round), or
        without one when the reason so far stands."""
        if spec.kind == "recover":
            step = self._recover(run, job, source, factsheet, *base, version=version)
        else:
            draft, rules, judge = base
            request = request_for(spec, draft, rules, judge, factsheet, job.config.pipeline)
            if not request:
                return None, ("no_problems" if spec.kind == "repair" else None)
            step = self._round(
                run, job, source, factsheet, *base, request, number,
                kind=spec.kind, version=version,
            )  # fmt: skip
        if step is None:
            if spec.kind == "repair":
                return None, "round_failed"
            if spec.kind == "facts":
                return None, "facts_round_failed"
        return step, None

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
                sender=cfg.sender,
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
            if stages.value_present(fact, current):
                continue  # a recovery before it in this round brought the value
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
                AnsweredAddition(
                    after=rec.block_id,
                    texts=list(rec.texts),
                    fact_ids=[fact.id],
                    segment_ids=list(fact.segment_ids),
                )
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
        # The version and its record together: neither ever exists without the other.
        version = new_draft.version
        self.store.put_artifacts(
            job.id, [("draft", new_draft, version), ("repair", record, version)]
        )
        new_rules = self._check(run, job, new_draft, source, factsheet)
        new_judge = self._judged(run, job, source, factsheet, (draft, rules, judge), new_draft)
        return new_draft, new_rules, new_judge

    def _judged(
        self,
        run: RunState,
        job: Job,
        source: SourceDocument,
        factsheet: FactSheet,
        base: Step,
        new_draft: Draft,
    ) -> JudgeReport | None:
        """The judge report of a round's new version: the judge runs again when facts
        or invented statements were involved in the version it started from
        (`_judge_again`), else that version's findings are carried over to the blocks
        the round left as they were."""
        _, rules, judge = base
        if self._judge_again(judge, rules):
            return self._judge(run, job, source, factsheet, new_draft)
        if judge is None:
            return None
        carried = _carry_over(judge, base[0], new_draft)
        self.store.put_artifact(job.id, "judge", carried, new_draft.version)
        return carried

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
        # A stored report counts for this version only while it names this content
        # (`draft_hash`): a resumed job used to take the old version's report for a
        # new version of the same number (audit of 6 November 2026).
        existing = self.store.get_artifact(job.id, "judge", JudgeReport, version=draft.version)
        if existing and existing.draft_hash == draft.content_hash():
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
                sender=job.config.sender,
            )
        except (LLMError, LLMOutputError) as exc:
            # Without the judge the draft still has its rule and fact checks.
            run.notes.append(f"judge on draft {draft.version} failed: {_short(exc)}")
            return None
        report = report.model_copy(update={"draft_hash": draft.content_hash()})
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
        stage's model call; the stage before ends (`stage_finished`), this one starts
        (`stage_started`), and a running job shows it on its page."""
        run.limit.check()
        self._end_stage(run)
        self.store.record(run.job_id, "stage_started", {"stage": stage})
        run.stage = stage

    def _end_stage(self, run: RunState) -> None:
        if run.stage is not None:
            self.store.record(run.job_id, "stage_finished", {"stage": run.stage})
            run.stage = None


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
            "draft_hash": new.content_hash(),
            "fact_checks": [
                c.model_copy(update={"block_ids": [b for b in c.block_ids if b in existing]})
                for c in judge.fact_checks
            ],
            "unsupported": [u for u in judge.unsupported if u.block_id in unchanged],
            "dropped": [],  # the old version's unquoted verdicts say nothing about this one
            "semantic_findings": [s for s in judge.semantic_findings if s.block_id in unchanged],
        }
    )


# -- the rounds' bookkeeping (pipeline/rounds.py) -----------------------------------------


@dataclass(frozen=True)
class _Done:
    """A round a run before this one made: its kind, the version it started from and
    the version it made, each with its checks (`_stored_rounds`)."""

    kind: str
    base: Step
    step: Step


def _replayed(
    spec: RoundSpec, stored: list[_Done], records: list[RoundRecord]
) -> StopReason | None:
    """The records of the rounds of this kind a run before this one made, rebuilt from
    their versions and appended to `records`, and the reason they ended the kind; None
    when the kind goes on with the next number."""
    for number, past in enumerate(stored, 1):
        before, after = _counts(past.base), _counts(past.step)
        records.append(_round_record(spec, number, past.base, past.step, before, after))
        if ended := _stop_reason(spec, before, after):
            return ended
    return None


def _counts(step: Step) -> tuple[int, int]:
    """What the rounds measure on a version: its blocking findings and its missing
    must-keep values."""
    _, rules, judge = step
    return blocking_count(rules, judge), missing_count(rules)


def _round_record(
    spec: RoundSpec,
    number: int,
    base: Step,
    step: Step,
    before: tuple[int, int],
    after: tuple[int, int],
) -> RoundRecord:
    """One round's record: the version it started from, the one it made, the counts
    before and after."""
    return RoundRecord(
        kind=spec.kind,
        number=number,
        parent_version=base[0].version,
        version=step[0].version,
        blocking_before=before[0],
        blocking_after=after[0],
        missing_before=before[1],
        missing_after=after[1],
    )


def _stop_reason(
    spec: RoundSpec, before: tuple[int, int], after: tuple[int, int]
) -> StopReason | None:
    """Why a kind's rounds end after a round, by what the kind measures: the count is
    zero, or the round did not lower it. None: the next round runs (a kind without a
    measure runs to its limit)."""
    if spec.measure == "blocking":
        if after[0] == 0:
            return "no_blocking"
        if after[0] >= before[0]:
            return "no_progress"
    elif spec.measure == "missing":
        if after[1] == 0:
            return "no_missing_facts"
        if after[1] >= before[1]:
            return "facts_no_progress"
    return None
