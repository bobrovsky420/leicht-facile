"""Stored jobs run again on their recorded answers, without a model call (`eval replay`).

A job's model calls are in `llm_calls` with their stage and the response cache's key
(llm/cache.py), and the cache holds the answers while `llm.cache` is on. The replay makes
the job again in a scratch store, the same settings and the same source, and runs the
pipeline on a client that answers every call from those recorded answers and asks no
endpoint: by key when the prompt is byte for byte the recorded one, else with the first
recorded answer of the stage that no call took yet. So a change of the code between a
prompt and the model's answer (a fact sheet completed differently alters the write
prompt) does not end the replay: the recorded answer is applied to what the code makes
now. A call the run never made (the code asks once more than the run did, or the cache
lost the answer) fails as an endpoint failure does, and the report says where.

What the code makes of the answers is compared with the stored artifacts, the fact
sheet, every draft version with its rule findings, judge report and round record, and
the summary, and written in a canonical form, one JSON file per job, to a folder. A
folder written before a change (`--against`) says what the change made of the same
recorded answers over every stored job, before a run against a model.
"""

from __future__ import annotations

import difflib
import json
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx

from leichtfacile.config import Settings
from leichtfacile.eval.results import OK
from leichtfacile.llm.cache import ResponseCache, cache_key
from leichtfacile.llm.client import LLMClient, LLMError, LLMResult, Usage, check_limit
from leichtfacile.pipeline.orchestrator import Orchestrator
from leichtfacile.schemas import (
    Draft,
    FactSheet,
    Job,
    JudgeReport,
    PipelineSummary,
    RepairRecord,
    RuleFindings,
    SourceDocument,
)
from leichtfacile.store import Store

Match = Literal["key", "order", "none"]
REPORT_NAME = "report.md"
_EXAMPLES = 3  # how many items a difference line names


@dataclass
class Recorded:
    """One recorded call of the job: its stage, the response cache's key and the answer
    the cache holds for it (None when the row is gone, or no cache was on)."""

    stage: str
    key: str | None
    answer: dict[str, Any] | None
    taken: bool = False  # answered a call of the replay by order


def recorded_calls(store: Store, job_id: str, cache: ResponseCache) -> list[Recorded]:
    """The job's calls in the order made, each with its answer; a prompt the run asked
    twice (the second time from the cache) is one call."""
    calls: list[Recorded] = []
    seen: set[str] = set()
    for stage, _model, key in store.call_keys(job_id):
        if key in seen:
            continue
        if key is not None:
            seen.add(key)
        calls.append(Recorded(stage, key, cache.get(key) if key else None))
    return calls


def _refuse(request: httpx.Request) -> httpx.Response:
    return httpx.Response(400, json={"error": {"message": "a replay asks no endpoint"}})


class RecordedClient(LLMClient):
    """A client that answers from a job's recorded calls and never asks an endpoint:
    `served` says how each call of the replay was answered."""

    def __init__(self, settings: Settings, calls: list[Recorded]) -> None:
        super().__init__(settings, http_client=httpx.Client(transport=httpx.MockTransport(_refuse)))
        self.calls = calls
        self.served: list[tuple[str, Match]] = []

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        thinking: bool = False,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        stage: str = "adhoc",
        response_format: dict[str, Any] | None = None,
    ) -> LLMResult:
        name, params, _ = self._prepare(model, thinking, temperature, max_tokens, response_format)
        check_limit()
        key = cache_key(name, messages, params)
        call, how = self._take(stage, key)
        self.served.append((stage, how))
        if call is None or call.answer is None:
            raise LLMError(
                f"no recorded answer for this {stage} call: the run made fewer calls of the "
                "stage, or the cache lost the answer"
            )
        hit = call.answer
        usage = Usage(
            stage, name, hit["tokens_in"], hit["tokens_out"], 0, cached=True, cache_key=key
        )
        self._record(usage)
        return LLMResult(hit["text"], hit["reasoning"], hit["finish_reason"], usage, cache_key=key)

    def _take(self, stage: str, key: str) -> tuple[Recorded | None, Match]:
        """The recorded call that answers this one: the one with this prompt (as often
        as it is asked, as the cache answered it), else the first of the stage no call
        took yet."""
        for call in self.calls:
            if call.key == key and call.answer is not None:
                return call, "key"
        for call in self.calls:
            if call.stage == stage and not call.taken and call.answer is not None:
                call.taken = True
                return call, "order"
        return None, "none"

    def forget(self, result: LLMResult) -> None:
        """Nothing: the recorded answers stay, so the replay takes the run's path."""

    def judge_model(self) -> str:
        """The judge the settings name (`replay_settings`), never the endpoint's list."""
        return self.settings.llm.judge_model

    def list_models(self, timeout_s: float = 10.0) -> list[str]:
        raise LLMError("a replay asks no endpoint")


def replay_settings(settings: Settings, summary: PipelineSummary | None) -> Settings:
    """The settings a replay runs with: no time budget (a replay is as slow as its rule
    checks), and the judge the run used when the settings name none, so that no call
    asks the endpoint which models it lists."""
    llm = settings.llm
    if llm.models.judge is None and summary is not None and summary.judge_model:
        models = llm.models.model_copy(update={"judge": summary.judge_model})
        llm = llm.model_copy(update={"models": models})
    jobs = settings.jobs.model_copy(update={"time_budget_s": 0.0})
    return settings.model_copy(update={"llm": llm, "jobs": jobs})


# -- the canonical form -------------------------------------------------------------------


def canonical(store: Store, job_id: str) -> dict[str, Any]:
    """A job's pipeline artifacts in one form, the same for a stored job and its replay,
    so that two of them compare field by field (`differences`): the fact sheet, every
    draft version with its rule findings, judge report and round record, the summary."""
    factsheet = store.get_artifact(job_id, "factsheet", FactSheet)
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    versions = []
    for number in store.versions(job_id, "draft"):
        draft = store.get_artifact(job_id, "draft", Draft, version=number)
        if draft is None:
            continue
        rules = store.get_artifact(job_id, "rules", RuleFindings, version=number)
        judge = store.get_artifact(job_id, "judge", JudgeReport, version=number)
        record = store.get_artifact(job_id, "repair", RepairRecord, version=number)
        versions.append(_version(draft, rules, judge, record))
    return {
        "factsheet": _factsheet(factsheet) if factsheet else None,
        "versions": versions,
        "summary": _summary(summary) if summary else None,
    }


def _factsheet(fs: FactSheet) -> dict[str, Any]:
    return {
        "facts": [
            {
                "id": f.id,
                "kind": f.kind,
                "text": f.text,
                "value_norm": f.value_norm,
                "segment_ids": list(f.segment_ids),
                "must_keep": f.must_keep,
                "origin": f.origin,
            }
            for f in fs.facts
        ],
        "hard_terms": [t.term for t in fs.hard_terms],
        "omit_candidates": len(fs.omit_candidates),
    }


def _version(
    draft: Draft,
    rules: RuleFindings | None,
    judge: JudgeReport | None,
    record: RepairRecord | None,
) -> dict[str, Any]:
    return {
        "version": draft.version,
        "parent_version": draft.parent_version,
        "kind": record.kind if record else draft.origin,
        "blocks": [
            {
                "id": b.id,
                "kind": b.kind,
                "text": b.text,
                "fact_ids": list(b.fact_ids),
                "segment_ids": list(b.segment_ids),
            }
            for b in draft.blocks
        ],
        "glossary": [g.term for g in draft.glossary],
        "code_edits": sorted(f"{e.rule_id} {e.block_id}" for e in draft.code_edits),
        "findings": sorted(
            f"{f.rule_id} {f.block_id or '-'} {f.key} {f.fact_id or '-'}" for f in rules.findings
        )
        if rules
        else None,
        "fact_coverage": rules.metrics.fact_coverage if rules else None,
        "judge": {
            "fact_checks": {c.fact_id: c.status for c in judge.fact_checks},
            "unsupported": sorted(u.block_id for u in judge.unsupported),
            "semantic": sorted(f"{s.rule_id} {s.block_id}" for s in judge.semantic_findings),
            "dropped": len(judge.dropped),
        }
        if judge
        else None,
        "record": {
            "requested_blocks": list(record.requested_blocks),
            "requested_facts": list(record.requested_facts),
            "repairs": len(record.repairs),
            "additions": len(record.additions),
            "dropped": sorted(f"{d.reason} {d.block_id or '-'}" for d in record.dropped),
        }
        if record
        else None,
    }


def _summary(summary: PipelineSummary) -> dict[str, Any]:
    return {
        "final_version": summary.final_version,
        "stop_reason": summary.stop_reason,
        "rounds": [
            f"{r.kind} {r.number}: v{r.parent_version} to v{r.version}, blocking "
            f"{r.blocking_before} to {r.blocking_after}, missing {r.missing_before} to "
            f"{r.missing_after}"
            for r in summary.rounds
        ],
        "blocking_findings": list(summary.blocking_findings),
        "notes": list(summary.notes),
    }


# -- what differs ---------------------------------------------------------------------------


def differences(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """What `after` holds differently from `before`, one line each; none when the two
    agree on everything the canonical form carries."""
    return [
        *_factsheet_differences(before["factsheet"], after["factsheet"]),
        *_versions_differences(before["versions"], after["versions"]),
        *_summary_differences(before["summary"], after["summary"]),
    ]


def _examples(items: Iterable[str]) -> str:
    listed = list(items)
    shown = "; ".join(listed[:_EXAMPLES])
    return shown + (f"; and {len(listed) - _EXAMPLES} more" if len(listed) > _EXAMPLES else "")


def _short(text: str, limit: int = 48) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _fact_line(fact: dict[str, Any]) -> str:
    return f'{fact["id"]} {fact["kind"]} "{_short(fact["text"])}"'


def _factsheet_differences(a: dict[str, Any] | None, b: dict[str, Any] | None) -> list[str]:
    if a is None or b is None:
        return [] if a is b else ["fact sheet " + ("gone" if b is None else "new")]
    # Facts match by kind and text: ids shift when code adds or merges a fact.
    facts_a = {(f["kind"], f["text"]): f for f in a["facts"]}
    facts_b = {(f["kind"], f["text"]): f for f in b["facts"]}
    lines = []
    if added := [f for k, f in facts_b.items() if k not in facts_a]:
        lines.append(f"facts: +{len(added)} ({_examples(map(_fact_line, added))})")
    if removed := [f for k, f in facts_a.items() if k not in facts_b]:
        lines.append(f"facts: -{len(removed)} ({_examples(map(_fact_line, removed))})")
    changed = [
        f"{facts_b[k]['id']} {facts_a[k]['value_norm']} to {facts_b[k]['value_norm']}, "
        f"{','.join(facts_a[k]['segment_ids']) or '-'} to "
        f"{','.join(facts_b[k]['segment_ids']) or '-'}"
        for k in facts_a
        if k in facts_b
        and (facts_a[k]["value_norm"], facts_a[k]["segment_ids"], facts_a[k]["must_keep"])
        != (facts_b[k]["value_norm"], facts_b[k]["segment_ids"], facts_b[k]["must_keep"])
    ]
    if changed:
        lines.append(
            f"facts: {len(changed)} with another value, sentence or must-keep "
            f"({_examples(changed)})"
        )
    terms_a, terms_b = set(a["hard_terms"]), set(b["hard_terms"])
    if terms_a != terms_b:
        lines.append(f"hard terms: +{len(terms_b - terms_a)} -{len(terms_a - terms_b)}")
    return lines


def _versions_differences(a_list: list[dict[str, Any]], b_list: list[dict[str, Any]]) -> list[str]:
    a = {v["version"]: v for v in a_list}
    b = {v["version"]: v for v in b_list}
    lines = []
    if set(a) != set(b):
        lines.append(
            f"versions: {', '.join(f'v{n}' for n in sorted(a)) or 'none'} before, "
            f"{', '.join(f'v{n}' for n in sorted(b)) or 'none'} after"
        )
    for number in sorted(set(a) & set(b)):
        lines += _version_differences(f"v{number}", a[number], b[number])
    return lines


def _version_differences(tag: str, va: dict[str, Any], vb: dict[str, Any]) -> list[str]:
    lines = _blocks_differences(tag, va, vb)
    if set(va["glossary"]) != set(vb["glossary"]):
        added = set(vb["glossary"]) - set(va["glossary"])
        gone = set(va["glossary"]) - set(vb["glossary"])
        lines.append(f"{tag}: glossary +{len(added)} -{len(gone)}")
    if va["code_edits"] != vb["code_edits"]:
        lines.append(
            f"{tag}: code edits {len(va['code_edits'])} before, {len(vb['code_edits'])} after"
        )
    lines += _counted(tag, "findings", va["findings"], vb["findings"])
    if va["fact_coverage"] != vb["fact_coverage"]:
        lines.append(f"{tag}: fact coverage {va['fact_coverage']} to {vb['fact_coverage']}")
    lines += _judge_differences(tag, va["judge"], vb["judge"])
    lines += _record_differences(tag, va["record"], vb["record"])
    return lines


def _blocks_differences(tag: str, va: dict[str, Any], vb: dict[str, Any]) -> list[str]:
    """The round that made the version and its blocks: the texts, or, when they are the
    same, the facts and the sentences the blocks are linked to."""
    lines = []
    if va["kind"] != vb["kind"]:
        lines.append(f"{tag}: made by {va['kind']} before, {vb['kind']} after")
    texts_a = [(x["kind"], x["text"]) for x in va["blocks"]]
    texts_b = [(x["kind"], x["text"]) for x in vb["blocks"]]
    if texts_a != texts_b:
        matcher = difflib.SequenceMatcher(None, texts_a, texts_b, autojunk=False)
        changed = sum(
            max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in matcher.get_opcodes() if op != "equal"
        )
        lines.append(
            f"{tag}: {changed} of {len(texts_b)} blocks differ ({len(texts_a)} blocks before)"
        )
        return lines
    pairs = list(zip(va["blocks"], vb["blocks"], strict=True))
    if relinked := sum(1 for x, y in pairs if set(x["fact_ids"]) != set(y["fact_ids"])):
        lines.append(f"{tag}: fact links differ on {relinked} blocks")
    if cited := sum(1 for x, y in pairs if set(x["segment_ids"]) != set(y["segment_ids"])):
        lines.append(f"{tag}: cited sentences differ on {cited} blocks")
    return lines


def _record_differences(
    tag: str, ra: dict[str, Any] | None, rb: dict[str, Any] | None
) -> list[str]:
    if ra is None or rb is None:
        return [] if ra is rb else [f"{tag}: round record " + ("gone" if rb is None else "new")]
    lines = []
    asked_a = (ra["requested_blocks"], ra["requested_facts"])
    asked_b = (rb["requested_blocks"], rb["requested_facts"])
    if asked_a != asked_b:
        lines.append(
            f"{tag}: the round asked for {len(asked_a[0])} blocks and {len(asked_a[1])} facts "
            f"before, {len(asked_b[0])} and {len(asked_b[1])} after"
        )
    lines += _counted(tag, "dropped texts", ra["dropped"], rb["dropped"])
    return lines


def _counted(tag: str, what: str, a: list[str] | None, b: list[str] | None) -> list[str]:
    """One line when the two multisets of lines differ: how many came, how many went."""
    if a is None or b is None:
        return [] if a is b else [f"{tag}: {what} " + ("gone" if b is None else "new")]
    added, gone = Counter(b) - Counter(a), Counter(a) - Counter(b)
    if not added and not gone:
        return []
    parts = []
    if added:
        parts.append(f"+{sum(added.values())} ({_examples(added.elements())})")
    if gone:
        parts.append(f"-{sum(gone.values())} ({_examples(gone.elements())})")
    return [f"{tag}: {what} " + " ".join(parts)]


def _judge_differences(tag: str, a: dict[str, Any] | None, b: dict[str, Any] | None) -> list[str]:
    if a is None or b is None:
        return [] if a is b else [f"{tag}: judge report " + ("gone" if b is None else "new")]
    lines = []
    checks_a, checks_b = a["fact_checks"], b["fact_checks"]
    changed = [
        f"{fid} {checks_a.get(fid, 'unjudged')} to {checks_b.get(fid, 'unjudged')}"
        for fid in sorted(set(checks_a) | set(checks_b))
        if checks_a.get(fid) != checks_b.get(fid)
    ]
    if changed:
        lines.append(f"{tag}: judge fact checks differ on {len(changed)} ({_examples(changed)})")
    lines += _counted(tag, "judge unsupported", a["unsupported"], b["unsupported"])
    lines += _counted(tag, "judge semantic findings", a["semantic"], b["semantic"])
    return lines


def _summary_differences(a: dict[str, Any] | None, b: dict[str, Any] | None) -> list[str]:
    if a is None or b is None:
        return [] if a is b else ["summary " + ("gone" if b is None else "new")]
    lines = []
    if a["final_version"] != b["final_version"]:
        lines.append(f"final version v{a['final_version']} before, v{b['final_version']} after")
    if a["stop_reason"] != b["stop_reason"]:
        lines.append(f"stop reason {a['stop_reason']} before, {b['stop_reason']} after")
    if a["rounds"] != b["rounds"]:
        lines.append(f"rounds: {len(a['rounds'])} before, {len(b['rounds'])} after")
        lines += [f"  before: {r}" for r in a["rounds"] if r not in b["rounds"]]
        lines += [f"  after: {r}" for r in b["rounds"] if r not in a["rounds"]]
    lines += _counted("summary", "notes", a["notes"], b["notes"])
    return lines


# -- the replay -----------------------------------------------------------------------------


@dataclass
class JobReplay:
    """One stored job replayed: how its calls were answered, how the replay ended and
    what it made differently from the stored artifacts and, with `--against`, from the
    earlier replay (None without one to compare with)."""

    job_id: str
    title: str
    status: str
    error: str | None
    answered: dict[str, int]  # calls answered by key, by order, and not at all
    gone: int  # recorded calls whose answer the cache no longer holds
    stored: dict[str, Any]
    replayed: dict[str, Any]
    differences: list[str]
    changes: list[str] | None = None

    @property
    def agrees(self) -> bool:
        return self.status in OK and not self.differences

    def to_json(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "status": self.status,
            "error": self.error,
            "answered": self.answered,
            "gone": self.gone,
            "differences": self.differences,
            "changes": self.changes,
            "stored": self.stored,
            "replayed": self.replayed,
        }


@dataclass
class Replay:
    """A replay of several jobs: the folder it was written to, and one entry per job."""

    out_dir: Path
    jobs: list[JobReplay] = field(default_factory=list)

    @property
    def agreeing(self) -> int:
        return sum(1 for j in self.jobs if j.agrees)


def select_jobs(
    store: Store, ids: Iterable[str] | None = None, limit: int | None = None
) -> list[Job]:
    """The jobs to replay, oldest first: those `ids` name (an id or its beginning), else
    every job that reached the review; in each case only those with a source document
    and at least one recorded call, the first `limit` of them."""
    wanted = list(ids or [])
    jobs = sorted(store.list_jobs(limit=100_000), key=lambda j: j.created_at)
    if wanted:
        jobs = [j for j in jobs if any(j.id == w or j.id.startswith(w) for w in wanted)]
    else:
        jobs = [j for j in jobs if j.status in OK]
    jobs = [j for j in jobs if "source" in store.artifact_names(j.id) and store.call_keys(j.id)]
    return jobs[:limit] if limit else jobs


def replay_job(store: Store, job: Job, cache: ResponseCache, settings: Settings) -> JobReplay:
    """The job run again on its recorded answers in a scratch store, compared with its
    stored artifacts. `settings`: those the prompts' cache keys are computed with, the
    preset the job ran on for a key that matches."""
    source = store.get_artifact(job.id, "source", SourceDocument)
    if source is None:
        raise ValueError(f"job {job.id} has no source document")
    summary = store.get_artifact(job.id, "summary", PipelineSummary)
    calls = recorded_calls(store, job.id, cache)
    client = RecordedClient(replay_settings(settings, summary), calls)
    config = job.config.model_copy(update={"endpoint": None})  # the replay's one client
    with tempfile.TemporaryDirectory(prefix="leichtfacile-replay-") as tmp:
        scratch = Store(Path(tmp) / "replay.sqlite")
        try:
            scratch.create_job(config, title=job.title, job_id=job.id)
            scratch.put_artifact(job.id, "source", source)
            Orchestrator(scratch, client, client.settings).run(job.id)
            ended = scratch.get_job(job.id)
            replayed = canonical(scratch, job.id)
        finally:
            scratch.close()
    if ended is None:  # pragma: no cover - the scratch store is nobody else's
        raise RuntimeError(f"job {job.id} is gone from the scratch store")
    stored = canonical(store, job.id)
    answered = Counter(how for _, how in client.served)
    return JobReplay(
        job_id=job.id,
        title=job.title or "",
        status=ended.status,
        error=ended.error,
        answered={how: answered.get(how, 0) for how in ("key", "order", "none")},
        gone=sum(1 for c in calls if c.answer is None),
        stored=stored,
        replayed=replayed,
        differences=differences(stored, replayed),
    )


def replay_jobs(
    store: Store,
    cache: ResponseCache,
    out_dir: Path,
    *,
    settings_for: Callable[[str | None], Settings],
    ids: Iterable[str] | None = None,
    limit: int | None = None,
    against: Path | None = None,
    on_job: Callable[[JobReplay], None] | None = None,
) -> Replay:
    """Every selected job (`select_jobs`) replayed, one JSON file per job in `out_dir`
    and the report (`render_report`) with them. `settings_for` gives the settings for a
    preset's name (the one the job ran on; None for a job without one). With `against`,
    a folder this function wrote before a change, each job's `changes` say what the
    replay now makes differently from the replay then. `on_job` sees each job as it ends."""
    out_dir.mkdir(parents=True, exist_ok=True)
    replay = Replay(out_dir)
    for job in select_jobs(store, ids, limit):
        summary = store.get_artifact(job.id, "summary", PipelineSummary)
        preset = job.config.endpoint or (summary.endpoint if summary else None)
        done = replay_job(store, job, cache, settings_for(preset))
        if against is not None:
            earlier = against / f"{job.id}.json"
            if earlier.exists():
                before = json.loads(earlier.read_text(encoding="utf-8"))
                done.changes = differences(before["replayed"], done.replayed)
        (out_dir / f"{job.id}.json").write_text(
            json.dumps(done.to_json(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        replay.jobs.append(done)
        if on_job is not None:
            on_job(done)
    (out_dir / REPORT_NAME).write_text(render_report(replay, against), encoding="utf-8")
    return replay


# -- the report -----------------------------------------------------------------------------


def _final(form: dict[str, Any]) -> str:
    return f"v{form['summary']['final_version']}" if form["summary"] else "-"


def render_line(job: JobReplay, against: Path | None = None) -> str:
    """One line per job for the console: the final versions, how the calls were
    answered, how the replay ended, and whether it agrees with the stored artifacts
    (and with the earlier replay)."""
    a = job.answered
    calls = f"{a['key']} by key, {a['order']} by order"
    if a["none"]:
        calls += f", {a['none']} unanswered"
    if job.gone:
        calls += f", {job.gone} gone from the cache"
    verdict = "agrees" if not job.differences else f"{len(job.differences)} differences"
    if against is not None:
        if job.changes is None:
            verdict += f"; not in {against}"
        elif job.changes:
            verdict += f"; {len(job.changes)} changes"
        else:
            verdict += "; unchanged"
    return (
        f"{job.job_id}  {_short(job.title, 40):<40}  {_final(job.stored)} to "
        f"{_final(job.replayed)}  calls: {calls}  {job.status}  {verdict}"
    )


def render_report(replay: Replay, against: Path | None = None) -> str:
    """The report of a replay as Markdown: the counts, then each job with how its calls
    were answered and every difference from the stored artifacts and, with `against`,
    every change from the earlier replay."""
    jobs = replay.jobs
    failed = sum(1 for j in jobs if j.status not in OK)
    lines = [
        "# Stored jobs replayed on their recorded answers",
        "",
        f"{len(jobs)} jobs: {replay.agreeing} agree with the stored artifacts, "
        f"{len(jobs) - replay.agreeing - failed} differ, {failed} did not reach the review.",
    ]
    if against is not None:
        compared = [j for j in jobs if j.changes is not None]
        changed = sum(1 for j in compared if j.changes)
        lines.append(
            f"Against {against.as_posix()}: {len(compared)} jobs compared, {changed} changed."
        )
    for job in jobs:
        a = job.answered
        lines += [
            "",
            f"## {job.job_id} {job.title}".rstrip(),
            "",
            f"- Replay: {job.status}" + (f" ({job.error})" if job.error else "") + ".",
            f"- Calls: {a['key']} answered by key, {a['order']} by order, {a['none']} "
            f"unanswered; {job.gone} recorded answers gone from the cache.",
            f"- Final version: {_final(job.stored)} stored, {_final(job.replayed)} replayed.",
        ]
        if job.differences:
            lines += ["", "Against the stored artifacts:", ""]
            lines += [f"- {d}" for d in job.differences]
        else:
            lines += ["", "Agrees with the stored artifacts."]
        if against is not None:
            if job.changes is None:
                lines += ["", f"Not in {against.as_posix()}."]
            elif job.changes:
                lines += ["", f"Against {against.as_posix()}:", ""]
                lines += [f"- {c}" for c in job.changes]
            else:
                lines += ["", f"Unchanged against {against.as_posix()}."]
    return "\n".join(lines) + "\n"
