"""Compare P2 runs that differ in the language of the prompt instructions (docs/prompts.md,
"English instructions", 9 October 2026). No model call.

Usage: uv run python scripts/prompt_language.py eval/results-cscs-en-before \
           eval/results-cscs-en-repair eval/results-cscs-en-all [--role dev] [--json OUT]

The first folder is the reference. For each folder (its P2 file of the 8B writer):

- the means of the evaluation rows, per language;
- the repair rounds, measured on the stored artifacts: the rule findings on the blocks a
  round was asked to fix that are gone, stay or are new in the version it produced, the
  must-keep values it was asked for that the version has, the blocking count before and
  after, and what code dropped from the answer. The first repair round of a job has the
  same request in every folder when Understand, Write and the first judge call came from
  the cache, so it compares the repair prompts on equal input;
- the texts the model wrote that read as English (the language detector's word lists):
  the fact sheet, the final draft, the judge's notes and the repair answers.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from leichtfacile.ingest.detect import STOPWORDS
from leichtfacile.pipeline.orchestrator import MISSING_RULES, blocking_count, repairable
from leichtfacile.schemas import (
    Draft,
    FactSheet,
    JudgeReport,
    PipelineSummary,
    RepairRecord,
    RuleFindings,
)
from leichtfacile.store import Store

ROW_KEYS = (
    "fact_coverage",
    "hard_fact_recall",
    "silent_loss_share",
    "invented_values_per_100",
    "unsupported_per_100",
    "errors_per_100",
    "warnings_per_100",
    "readability",
    "avg_words",
    "rounds",
    "calls",
    "tokens_in",
    "tokens_out",
)
_OK = ("needs_review", "done")


# -- English in the model's texts -------------------------------------------------------

_LANGS_OF: dict[str, list[str]] = defaultdict(list)
for _lang, _words in STOPWORDS.items():
    for _word in _words:
        _LANGS_OF[_word].append(_lang)


def looks_english(text: str) -> bool:
    """English function words outweigh the German, French and Italian ones, with at
    least two of them (the detector's scoring: a shared word splits its point)."""
    scores: Counter = Counter()
    for token in text.lower().replace("’", "'").split():
        token = token.strip(".,:;!?()\"'")
        langs = _LANGS_OF.get(token)
        for lang in langs or ():
            scores[lang] += 1 / len(langs)
    return scores["en"] >= 2 and scores["en"] > max(scores[x] for x in ("de", "fr", "it"))


def _texts(store: Store, job_id: str) -> dict[str, list[str]]:
    """The model's texts of a job, by where they stand."""
    out: dict[str, list[str]] = defaultdict(list)
    fs = store.get_artifact(job_id, "factsheet", FactSheet)
    if fs:
        out["fact sheet"] += [f.text for f in fs.facts if f.origin == "model"]
        out["fact sheet"] += [a["text"] for a in fs.core.model_dump().values() if a.get("text")]
        out["fact sheet"] += [t.explanation for t in fs.hard_terms if t.origin == "model"]
        out["fact sheet"] += [o.reason for o in fs.omit_candidates]
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    draft = store.get_artifact(
        job_id, "draft", Draft, version=summary.final_version if summary else None
    )
    if draft:
        out["final draft"] += [b.text for b in draft.blocks]
        out["final draft"] += [g.explanation for g in draft.glossary if g.origin == "model"]
        out["final draft"] += [f"{o.what} {o.why}" for o in draft.omissions]
    for v in store.versions(job_id, "judge"):
        report = store.get_artifact(job_id, "judge", JudgeReport, version=v)
        if report:
            notes = [c.note for c in report.fact_checks] + [u.note for u in report.unsupported]
            out["judge notes"] += [n for n in notes + [s.note for s in report.semantic_findings]]
    for v in store.versions(job_id, "repair"):
        record = store.get_artifact(job_id, "repair", RepairRecord, version=v)
        if record:
            out["repair answers"] += [t for i in record.repairs for t in i.texts]
            out["repair answers"] += [t for a in record.additions for t in a.texts]
    return {k: [t for t in v if t and len(t.split()) >= 3] for k, v in out.items()}


# -- repair rounds ----------------------------------------------------------------------


def _base(block_id: str | None, requested: set[str]) -> str | None:
    """The requested block a block of the new version comes from: b004 for b004.2."""
    if block_id is None:
        return None
    base = block_id.split(".")[0]
    return base if base in requested else None


def _problems(rules: RuleFindings, requested: set[str], errors_only: bool) -> set[tuple]:
    severities = ("error",) if errors_only else ("error", "warn")
    return {
        (_base(f.block_id, requested), f.rule_id)
        for f in rules.findings
        if f.severity in severities and repairable(f) and _base(f.block_id, requested)
    }


def _missing(rules: RuleFindings) -> set[str]:
    return {f.fact_id for f in rules.findings if f.rule_id in MISSING_RULES and f.fact_id}


def repair_rounds(store: Store, job_id: str) -> list[dict[str, Any]]:
    rounds = []
    for v in store.versions(job_id, "repair"):
        record = store.get_artifact(job_id, "repair", RepairRecord, version=v)
        before = store.get_artifact(job_id, "rules", RuleFindings, version=record.parent_version)
        after = store.get_artifact(job_id, "rules", RuleFindings, version=v)
        if not (record and before and after):
            continue
        judge_before = store.get_artifact(
            job_id, "judge", JudgeReport, version=record.parent_version
        )
        judge_after = store.get_artifact(job_id, "judge", JudgeReport, version=v)
        requested = set(record.requested_blocks)
        answered = {i.block_id for i in record.repairs} & requested
        row: dict[str, Any] = {
            "kind": record.kind,
            "parent": record.parent_version,
            "version": v,
            "request": (sorted(requested), sorted(record.requested_facts)),
            "blocks": len(requested),
            "answered": len(answered),
            "additions": sum(len(a.texts) for a in record.additions),
            "dropped": Counter(d.reason for d in record.dropped),
            "blocking_before": blocking_count(before, judge_before),
            "blocking_after": blocking_count(after, judge_after),
            "invented_before": sum(1 for f in before.findings if f.rule_id == "FACT-06"),
            "invented_after": sum(1 for f in after.findings if f.rule_id == "FACT-06"),
        }
        for name, errors_only in (("problems", False), ("errors", True)):
            p_before = _problems(before, requested, errors_only)
            p_after = _problems(after, requested, errors_only)
            row[f"{name}_before"] = len(p_before)
            row[f"{name}_fixed"] = len(p_before - p_after)
            row[f"{name}_new"] = len(p_after - p_before)
        asked = set(record.requested_facts) & _missing(before)
        row["facts_asked"] = len(asked)
        row["facts_added"] = len(asked - _missing(after))
        rounds.append(row)
    return rounds


def _sum_rounds(rounds: list[dict[str, Any]]) -> dict[str, Any]:
    keys = (
        "blocks",
        "answered",
        "additions",
        "problems_before",
        "problems_fixed",
        "problems_new",
        "errors_before",
        "errors_fixed",
        "errors_new",
        "facts_asked",
        "facts_added",
        "blocking_before",
        "blocking_after",
        "invented_before",
        "invented_after",
    )
    total: dict[str, Any] = {k: sum(r[k] for r in rounds) for k in keys}
    total["rounds"] = len(rounds)
    total["dropped"] = sum((r["dropped"] for r in rounds), Counter())
    return total


# -- one folder -------------------------------------------------------------------------


def load(folder: Path, role: str) -> dict[str, Any]:
    files = sorted(folder.glob("P2_*8b.jsonl"))
    if len(files) != 1:
        raise SystemExit(f"{folder}: expected one P2 file of the 8B writer, found {files}")
    rows = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
    rows = [r for r in rows if line_ok(r, role)]
    store = Store(folder / "store.sqlite")
    jobs: dict[str, Any] = {}
    for row in rows:
        job_id = row["job_id"]
        texts = _texts(store, job_id)
        jobs[row["pair_id"]] = {
            "row": row,
            "rounds": repair_rounds(store, job_id),
            "english": {k: [t for t in v if looks_english(t)] for k, v in texts.items()},
            "texts": {k: len(v) for k, v in texts.items()},
        }
    store.close()
    return jobs


def line_ok(row: dict[str, Any], role: str) -> bool:
    return role == "all" or row.get("role") == role


def _mean(values: list[float | None]) -> float | None:
    values = [v for v in values if v is not None]
    return round(mean(values), 3) if values else None


def summarise(jobs: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for lang in ("de", "fr", "all"):
        chosen = [j for j in jobs.values() if lang == "all" or j["row"]["lang"] == lang]
        ok = [j for j in chosen if j["row"].get("status") in _OK]
        means = {k: _mean([j["row"].get(k) for j in ok]) for k in ROW_KEYS}
        means["pairs"] = len(chosen)
        means["failed"] = len(chosen) - len(ok)
        out[lang] = means
    all_rounds = [r for j in jobs.values() for r in j["rounds"]]
    out["rounds"] = {
        kind: _sum_rounds([r for r in all_rounds if r["kind"] == kind])
        for kind in ("repair", "facts", "vocabulary")
    }
    out["first_round"] = _sum_rounds(
        [r for r in all_rounds if r["kind"] == "repair" and r["parent"] == 1]
    )
    english: Counter = Counter()
    texts: Counter = Counter()
    for j in jobs.values():
        for k, v in j["english"].items():
            english[k] += len(v)
        texts.update(j["texts"])
    out["english"] = {k: (english[k], texts[k]) for k in sorted(texts)}
    return out


# -- report -----------------------------------------------------------------------------


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".") if abs(value) < 10 else f"{value:.1f}"
    return str(value)


def report(names: list[str], runs: list[dict[str, Any]]) -> str:
    sums = [summarise(jobs) for jobs in runs]
    lines = []
    for lang in ("all", "de", "fr"):
        lines += [f"\n### Means of the rows ({lang})\n", "| | " + " | ".join(names) + " |"]
        lines.append("|---|" + "---|" * len(names))
        for key in ("pairs", "failed", *ROW_KEYS):
            lines.append(f"| {key} | " + " | ".join(_fmt(s[lang][key]) for s in sums) + " |")
    for title, pick in (
        ("First repair round (same request when replayed)", lambda s: s["first_round"]),
        ("All repair rounds", lambda s: s["rounds"]["repair"]),
        ("Facts rounds", lambda s: s["rounds"]["facts"]),
        ("Vocabulary rounds", lambda s: s["rounds"]["vocabulary"]),
    ):
        lines += [f"\n### {title}\n", "| | " + " | ".join(names) + " |"]
        lines.append("|---|" + "---|" * len(names))
        keys = ("rounds", "blocks", "answered", "additions", "problems_before",
                "problems_fixed", "problems_new", "errors_before", "errors_fixed",
                "errors_new", "facts_asked", "facts_added", "blocking_before",
                "blocking_after", "invented_before", "invented_after")  # fmt: skip
        for key in keys:
            lines.append(f"| {key} | " + " | ".join(_fmt(pick(s)[key]) for s in sums) + " |")
        lines.append(
            "| dropped | " + " | ".join(dict(pick(s)["dropped"]).__repr__() for s in sums) + " |"
        )
    lines += ["\n### Texts that read as English (count / texts)\n"]
    lines += ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    places = sorted({k for s in sums for k in s["english"]})
    for place in places:
        cells = [
            "{} / {}".format(*s["english"].get(place, (0, 0))) for s in sums
        ]
        lines.append(f"| {place} | " + " | ".join(cells) + " |")
    # The first round's request per pair: equal input when the cache replayed it.
    ref = runs[0]
    for name, jobs in zip(names[1:], runs[1:], strict=True):
        same = sum(
            1
            for pair, job in jobs.items()
            if pair in ref
            and job["rounds"][:1]
            and ref[pair]["rounds"][:1]
            and job["rounds"][0]["request"] == ref[pair]["rounds"][0]["request"]
        )
        lines.append(f"\nFirst round with the same request as {names[0]}: {name} {same}")
    lines += ["\n### Per pair\n"]
    keys = ("fact_coverage", "hard_fact_recall", "errors_per_100", "unsupported_per_100")
    lines += ["| pair | " + " | ".join(f"{k} ({n})" for k in keys for n in names) + " |"]
    lines.append("|---|" + "---|" * (len(keys) * len(names)))
    for pair in sorted(ref):
        cells = [
            _fmt(jobs[pair]["row"].get(k)) if pair in jobs else "-" for k in keys for jobs in runs
        ]
        lines.append(f"| {pair} | " + " | ".join(cells) + " |")
    examples = [
        f"- {name}, {pair}, {place}: {text}"
        for name, jobs in zip(names, runs, strict=True)
        for pair, job in sorted(jobs.items())
        for place, texts in job["english"].items()
        for text in texts[:2]
    ]
    if examples:
        lines += ["\n### English texts (up to two per pair and place)\n", *examples[:60]]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--role", default="dev", choices=["dev", "eval", "all"])
    parser.add_argument("--json", type=Path, help="write the summaries as JSON to this file")
    args = parser.parse_args()
    runs = [load(folder, args.role) for folder in args.folders]
    names = [folder.name.removeprefix("results-") for folder in args.folders]
    # Only the pairs every folder has a row for, so that the sums compare like with like.
    common = set.intersection(*(set(jobs) for jobs in runs))
    for name, jobs in zip(names, runs, strict=True):
        if set(jobs) - common:
            print(f"{name}: left out (not in every folder): {', '.join(sorted(set(jobs) - common))}")
    runs = [{p: j for p, j in jobs.items() if p in common} for jobs in runs]
    print(report(names, runs))
    if args.json:
        data = {n: summarise(jobs) for n, jobs in zip(names, runs, strict=True)}
        args.json.write_text(json.dumps(data, indent=1, default=dict), encoding="utf-8")


if __name__ == "__main__":
    main()
