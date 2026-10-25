"""Fact-retention diagnosis: why a must-keep fact is missing from the
final version of a pipeline job.

For every job of a condition in a results folder, every must-keep fact with a value
that FACT-01 does not find in the final version is put into one bucket:

- `a`: never asked for in any repair round, because it was behind the cap of missing
  facts per round, because no round ran at all (the loop stopped or failed before
  one), or because the stored findings never flagged it (not checkable when the job
  ran);
- `b`: asked for and written, but in a form FACT-01 does not accept;
- `c`: asked for and written, then dropped by code (a repeat, example content, a block
  the round had not flagged);
- `d`: asked for, and the model did not write it;
- `k`: asked for and written into a version that was not kept as final (the version
  with the fewest blocking findings is final; a round's gains are lost when the judge
  flags its new sentences);
- `l`: in an earlier version, then lost in a later rewrite (by the model, or by code);
- `x`: asked for, but the round's answer was not recorded (jobs run before the repair
  record existed; `b`, `c` and `d` cannot be told apart for them).

When no round led to the final version (an earlier version was kept), a fact is
classified by the rounds that ran after it, and the reason says so.

Bucket `e` of the plan is the list of background facts (`must_keep` false, marked so by
Understand or by code completion in a passage marked droppable) whose value is not in
the final text: whether the reader needed them is a reading decision, so they are
listed, not counted as missing. Facts without a value that only the judge can check
are counted apart.

The requests of rounds without a record are recomputed from the stored artifacts with
the same code the pipeline uses (`build_request`), so the diagnosis of older runs is
exact for bucket `a`. The detail report quotes fact texts and answers, so it stays in
the git-ignored results folder; the bucket table is what gets published.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from leichtfacile.eval.results import completed_rows
from leichtfacile.pipeline.rounds import MAX_MISSING_PER_ROUND, blocking_count, build_request
from leichtfacile.rules.document import fact_coverage
from leichtfacile.rules.values import (
    MONTH_NAMES,
    Value,
    contains,
    extract_values,
    parse_value_norm,
)
from leichtfacile.schemas import (
    Draft,
    FactSheet,
    JudgeReport,
    PipelineSummary,
    RepairRecord,
    RuleFindings,
    SourceDocument,
)
from leichtfacile.store import Store

BUCKETS = {
    "a": "never asked for",
    "b": "written in a form FACT-01 rejects",
    "c": "written, then dropped by code",
    "d": "asked for, not written",
    "k": "written into a version not kept as final",
    "l": "present once, lost in a later rewrite",
    "x": "asked for, answer not recorded",
}
REASONS_A = {
    "cap": "behind the cap of missing facts per round "
    f"({MAX_MISSING_PER_ROUND} in a repair round, pipeline.missing_per_facts_round in a facts "
    "round)",
    "no_round": "no repair round ran",
    "unflagged": "never flagged by FACT-01 in the stored findings",
}


@dataclass
class MissingFact:
    fact_id: str
    kind: str
    value: str
    text: str
    bucket: str
    reason: str
    asked_in: list[int] = field(default_factory=list)  # versions produced by rounds that asked
    answers: list[str] = field(default_factory=list)  # what the model wrote for it, if recorded


@dataclass
class JobDiagnosis:
    pair_id: str
    job_id: str
    setup: str
    final_version: int
    versions: list[int]
    rounds: int
    facts_rounds: int
    stop_reason: str
    recorded: bool  # the rounds have repair records
    checkable: int
    missing: list[MissingFact]
    background_lost: list[dict[str, str]]  # bucket e, for reading
    judge_only_missing: int  # facts without a value the final judge report calls missing

    def counts(self) -> Counter:
        return Counter(m.bucket for m in self.missing)


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def mentions(target: Value, text: str, lang: str) -> str | None:
    """Whether a text carries the value: "exact" when FACT-01 would accept it, "loose"
    when its digits or its words are there in another form (a heuristic for a reader:
    `31.3.` for `2026-03-31` is exact, `Ende März 2026` loose), else None."""
    if contains(target, text, extract_values(text, lang)):
        return "exact"
    lowered = text.lower()
    if target.kind == "date":
        year, month, day = target.canonical.split("-")
        tokens = set(re.findall(r"\d+", text))
        names = [m.lower() for names in MONTH_NAMES.values() for m in names]
        month_named = any(
            names[i].lower() in lowered for i in range(len(names)) if (i % 12) + 1 == int(month)
        )
        if (day.lstrip("0") in tokens or day in tokens) and (
            month_named or month.lstrip("0") in tokens
        ):
            return "loose"
        return None
    if target.kind in ("email", "url"):
        return "loose" if target.canonical.split("@")[-1].split("/")[0] in lowered else None
    if target.kind == "address":
        street, _, place = target.canonical.lower().split("|")
        return "loose" if (street and street.split(" ")[0] in lowered) or place in lowered else None
    runs = sorted(re.findall(r"\d+", target.canonical), key=len, reverse=True)
    if not runs:
        return None
    if target.kind in ("phone", "identifier", "schedule"):
        # Long digit runs: the number in any spacing, as a substring of the text's digits.
        return "loose" if len(runs[0]) >= 5 and runs[0] in _digits(text) else None
    # Amounts, percentages, periods, quantities: the number as a whole token, with the
    # thousands separators of Swiss and German writing removed (1'500, 1 500, 1.500).
    wanted = re.match(r"\d+(?:\.\d+)?", target.canonical)
    compact = re.sub(r"(?<=\d)[ '\u2019\u00a0\u202f.](?=\d{3}(?!\d))", "", text)
    for token in re.findall(r"\d+(?:[.,]\d+)?", compact):
        try:
            if wanted and Decimal(token.replace(",", ".")) == Decimal(wanted.group(0)):
                return "loose"
        except InvalidOperation:
            continue
    return None


def _requests(
    versions: list[int],
    drafts: dict[int, Draft],
    rules: dict[int, RuleFindings],
    judges: dict[int, JudgeReport | None],
    records: dict[int, RepairRecord | None],
    factsheet: FactSheet,
) -> dict[int, list[str]]:
    """The fact ids each round asked for, keyed by the version the round produced: from
    the record when the round has one, else recomputed as the pipeline did."""
    asked: dict[int, list[str]] = {}
    for v in versions:
        if v == 1:
            continue
        record = records.get(v)
        if record is not None:
            asked[v] = list(record.requested_facts)
            continue
        prev = v - 1
        if prev not in drafts or rules.get(prev) is None:
            asked[v] = []
            continue
        blocking = blocking_count(rules[prev], judges.get(prev))
        request = build_request(
            drafts[prev], rules[prev], judges.get(prev), factsheet, include_warnings=blocking == 0
        )
        asked[v] = [f.id for f in request.missing]
    return asked


def diagnose_job(store: Store, row: dict[str, Any]) -> JobDiagnosis | None:
    job_id = row["job_id"]
    source = store.get_artifact(job_id, "source", SourceDocument)
    factsheet = store.get_artifact(job_id, "factsheet", FactSheet)
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    if source is None or factsheet is None or summary is None:
        return None
    lang = source.lang
    versions = store.versions(job_id, "draft")
    drafts = {v: store.get_artifact(job_id, "draft", Draft, version=v) for v in versions}
    rules = {v: store.get_artifact(job_id, "rules", RuleFindings, version=v) for v in versions}
    judges = {v: store.get_artifact(job_id, "judge", JudgeReport, version=v) for v in versions}
    records = {
        v: store.get_artifact(job_id, "repair", RepairRecord, version=v) for v in versions if v > 1
    }
    final = summary.final_version if summary.final_version in drafts else versions[-1]
    coverage = {v: fact_coverage(drafts[v], factsheet, lang, source) for v in versions}
    asked = _requests(versions, drafts, rules, judges, records, factsheet)
    flagged: dict[int, set[str]] = {
        v: {f.fact_id for f in r.findings if f.rule_id == "FACT-01" and f.fact_id}
        for v, r in rules.items()
        if r is not None
    }
    into_final = [v for v in versions if 2 <= v <= final]
    rounds_run = [v for v in versions if v >= 2]
    missing: list[MissingFact] = []
    for fact in coverage[final].missing:
        target = parse_value_norm(fact.value_norm, fact.kind, lang)
        present_in = [v for v in versions if v <= final and fact.id in coverage[v].found]
        asked_in = [v for v in into_final if fact.id in asked.get(v, [])]
        asked_later = [v for v in rounds_run if v > final and fact.id in asked.get(v, [])]
        present_later = [v for v in versions if v > final and fact.id in coverage[v].found]
        item = MissingFact(
            fact.id, fact.kind, fact.value_norm or "", fact.text, "", "", asked_in=asked_in
        )
        later = ""
        if not asked_in and asked_later:
            # An earlier version was kept as final; the rounds after it tell the story.
            asked_in = asked_later
            item.asked_in = asked_later
            later = f" (v{final} of {len(versions)} is final: {summary.stop_reason})"
        if present_later:
            item.bucket = "k"
            item.reason = (
                f"in v{max(present_later)}, but v{final} of {len(versions)} is final "
                f"({summary.stop_reason})"
            )
        elif present_in:
            lost_at = min(
                v
                for v in versions
                if v <= final and v > max(present_in) and fact.id not in coverage[v].found
            )
            record = records.get(lost_at)
            item.bucket = "l"
            if record is not None and any(
                target is not None and mentions(target, d.text, lang) for d in record.dropped
            ):
                item.reason = f"in v{max(present_in)}, dropped by code in the round to v{lost_at}"
            else:
                item.reason = f"in v{max(present_in)}, gone in v{lost_at}: a rewrite lost it"
                if record is None:
                    item.reason += " (answer not recorded)"
        elif not asked_in:
            item.bucket = "a"
            if not rounds_run:
                item.reason = f"{REASONS_A['no_round']} ({summary.stop_reason})"
            elif any(fact.id in flagged.get(v, set()) for v in versions if v < versions[-1]):
                item.reason = REASONS_A["cap"]
            else:
                item.reason = REASONS_A["unflagged"]
        else:
            last = max(asked_in)
            record = records.get(last)
            if record is None:
                item.bucket = "x"
                item.reason = f"asked in the round to v{last}; the answer was not recorded"
                item.reason += later
            else:
                written = [t for a in record.additions if fact.id in a.fact_ids for t in a.texts]
                others = [t for a in record.additions if fact.id not in a.fact_ids for t in a.texts]
                others += [t for r in record.repairs for t in r.texts]
                if target is not None:
                    written += [t for t in others if mentions(target, t, lang)]
                dropped = [
                    d
                    for d in record.dropped
                    if fact.id in d.fact_ids
                    or (target is not None and mentions(target, d.text, lang))
                    or d.text in written
                ]
                item.answers = written
                if dropped:
                    item.bucket = "c"
                    reasons = ", ".join(sorted({d.reason for d in dropped}))
                    item.reason = f"asked in the round to v{last}; code dropped it ({reasons})"
                elif written:
                    item.bucket = "b"
                    how = (
                        "loose"
                        if target is None
                        else (mentions(target, " ".join(written), lang) or "none")
                    )
                    found = "the digits or words are there" if how == "loose" else "no match"
                    item.reason = (
                        f"asked in the round to v{last}; written, but FACT-01 does not find it "
                        f"({found})"
                    )
                else:
                    item.bucket = "d"
                    item.reason = f"asked in the round to v{last}; the model did not write it"
                item.reason += later
        missing.append(item)
    final_text = drafts[final].text()
    final_values = extract_values(final_text, lang)
    background_lost = []
    for fact in factsheet.facts:
        if fact.must_keep:
            continue
        target = parse_value_norm(fact.value_norm, fact.kind, lang)
        if target is None or contains(target, final_text, final_values):
            continue
        background_lost.append(
            {
                "fact_id": fact.id,
                "kind": fact.kind,
                "value": fact.value_norm or "",
                "text": fact.text,
                "marked_by": "Understand" if fact.origin == "model" else "code completion",
            }
        )
    judge = judges.get(final)
    checkable_ids = {f.id for f in coverage[final].checkable}
    judge_only = 0
    if judge is not None:
        judge_only = sum(
            1 for c in judge.fact_checks if c.status != "present" and c.fact_id not in checkable_ids
        )
    setup = row.get("writer", "?")
    if row.get("understand"):
        setup += f", understand {row['understand']}"
    return JobDiagnosis(
        pair_id=row["pair_id"],
        job_id=job_id,
        setup=setup,
        final_version=final,
        versions=versions,
        rounds=summary.rounds_of("repair"),
        facts_rounds=summary.rounds_of("facts"),
        stop_reason=summary.stop_reason,
        recorded=all(records.get(v) is not None for v in into_final),
        checkable=len(coverage[final].checkable),
        missing=missing,
        background_lost=background_lost,
        judge_only_missing=judge_only,
    )


def diagnose(
    results_dir: Path, *, condition: str = "P2", role: str | None = "dev", writer: str | None = None
) -> list[JobDiagnosis]:
    store = Store(results_dir / "store.sqlite")
    out: list[JobDiagnosis] = []
    try:
        for row in completed_rows(results_dir, condition, role):
            if writer and row.get("writer") != writer:
                continue
            item = diagnose_job(store, row)
            if item is not None:
                out.append(item)
    finally:
        store.close()
    return out


def bucket_table(jobs: list[JobDiagnosis]) -> str:
    """The publishable part: counts per bucket, with the reasons of bucket a apart."""
    counts: Counter = Counter()
    reasons_a: Counter = Counter()
    for job in jobs:
        for m in job.missing:
            counts[m.bucket] += 1
            if m.bucket == "a":
                key = next(
                    (k for k, text in REASONS_A.items() if m.reason.startswith(text)), "other"
                )
                reasons_a[key] += 1
    total = sum(counts.values())
    checkable = sum(j.checkable for j in jobs)
    lines = [
        f"{len(jobs)} jobs, {checkable} checkable must-keep facts, {total} missing in the final "
        f"versions ({_pct(checkable - total, checkable)} found).",
        "",
        "| Bucket | Facts | Share of the missing |",
        "|---|---|---|",
    ]
    for key, name in BUCKETS.items():
        if key == "a":
            for reason, text in REASONS_A.items():
                n = reasons_a[reason]
                lines.append(f"| a: {name}, {text} | {n} | {_pct(n, total)} |")
            if reasons_a["other"]:
                n = reasons_a["other"]
                lines.append(f"| a: {name}, other | {n} | {_pct(n, total)} |")
            continue
        lines.append(f"| {key}: {name} | {counts[key]} | {_pct(counts[key], total)} |")
    background = sum(len(j.background_lost) for j in jobs)
    by_marker = Counter(b["marked_by"] for j in jobs for b in j.background_lost)
    markers = ", ".join(f"{n} marked by {k}" for k, n in sorted(by_marker.items())) or "none"
    lines += [
        "",
        f"Background facts whose value is not in the final text (bucket e, for reading): "
        f"{background} ({markers}).",
        f"Facts without a value that the final judge report calls missing or distorted: "
        f"{sum(j.judge_only_missing for j in jobs)}.",
        f"Jobs with a repair record for every round into the final version: "
        f"{sum(1 for j in jobs if j.recorded)} of {len(jobs)}.",
    ]
    return "\n".join(lines)


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f} %" if whole else "-"


def render_diagnosis(
    jobs: list[JobDiagnosis], *, title: str = "Fact-retention diagnosis", details: bool = True
) -> str:
    out = [f"# {title}", ""]
    by_setup: dict[str, list[JobDiagnosis]] = defaultdict(list)
    for job in jobs:
        by_setup[job.setup].append(job)
    for setup, group in sorted(by_setup.items()):
        if len(by_setup) > 1:
            out += [f"## {setup}", ""]
        out += [bucket_table(group), ""]
        out += [
            "| Pair | Final / versions | Rounds | Stop | Checkable | Missing | "
            + " | ".join(BUCKETS)
            + " |",
            "|---|---|---|---|---|---|" + "---|" * len(BUCKETS),
        ]
        for job in group:
            c = job.counts()
            rounds = f"{job.rounds}" + (f" + {job.facts_rounds} facts" if job.facts_rounds else "")
            out.append(
                f"| {job.pair_id} | v{job.final_version} / {len(job.versions)} | {rounds} "
                f"| {job.stop_reason} | {job.checkable} | {len(job.missing)} | "
                + " | ".join(str(c[k]) for k in BUCKETS)
                + " |"
            )
        out.append("")
        if not details:
            continue
        out += ["Details (local only: they quote the pages):", ""]
        for job in group:
            for m in job.missing:
                out.append(
                    f"- {job.pair_id} {m.fact_id} ({m.kind}, {m.value}): bucket {m.bucket}, "
                    f"{m.reason}. Fact: {m.text}"
                )
                for answer in m.answers:
                    out.append(f"    - written: {answer}")
            for b in job.background_lost:
                out.append(
                    f"- {job.pair_id} {b['fact_id']} ({b['kind']}, {b['value']}): background, "
                    f"marked by {b['marked_by']}. Fact: {b['text']}"
                )
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def to_json(jobs: list[JobDiagnosis]) -> str:
    return json.dumps([asdict(j) for j in jobs], ensure_ascii=False, indent=1)
