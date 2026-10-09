"""The headline numbers of a results folder (`eval numbers`): the means README, report
§1 and §5 and the video quote, P2 against the Zurich prompt in its complete mode, and
the case of decision D-M (PLAN.md, WP13) the numbers fall into. No model call, no text
of the protected pages: the numbers audit at G4 and G6 becomes a diff, not a hunt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from leichtfacile.eval.report import LANGUAGES, ORDER, load_rows
from leichtfacile.schemas import BASELINE_CONDITIONS

OK_STATUS = (None, "needs_review", "done")
SHOWN = ("REF", "P0", "P0-ZH-complete", "P0-ZH-condensed", "P1", "P2")
# Rows without a fact checklist: every hard value they lose is a silent loss, so the
# share follows from the hard facts kept when a row stored before the key has none.
NO_CHECKLIST = frozenset({"SOURCE", "REF", *BASELINE_CONDITIONS})
COVERAGE_GAP = 0.05  # case A allows P2 up to 5 points below P0-ZH on fact coverage
FAILURE_LIMIT = 0.25  # case D: the final run fails on more than a quarter of the pairs


@dataclass(frozen=True)
class SetupNumbers:
    setup: str
    writer: str  # the writer (and reader) model of the rows used
    pairs: int
    fact_coverage: float | None
    hard_facts_kept: float | None
    silent_losses: float | None
    errors: float | None  # rule errors per 100 blocks
    invented: float | None  # invented values per 100 blocks
    unsupported: float | None  # the judge's unsupported statements per 100 blocks


@dataclass(frozen=True)
class Headline:
    results: str
    role: str
    lang: str
    pairs: int
    setups: list[SetupNumbers]
    failed_share: float  # pairs whose P2 run failed, as a share of the pairs
    case: str  # A, B, C, D; "A?" for the mix the rules do not cover; "-" without rows
    reasons: list[str]

    def get(self, setup: str) -> SetupNumbers | None:
        return next((s for s in self.setups if s.setup == setup), None)


def _mean(rows: list[dict], key: str) -> float | None:
    values = [r[key] for r in rows if r.get(key) is not None]
    return mean(values) if values else None


def _group_key(row: dict) -> str:
    key = row.get("writer", "?")
    if row.get("understand"):  # the hybrid: another model read the source
        key += f", understand {row['understand']}"
    return key


def _headline_group(rows: list[dict]) -> tuple[str, list[dict]]:
    """The rows of one writer: the plain setup (no other model as reader) with the
    most pairs; a hybrid or a 70B run next to it is reported by `eval report`, not
    here. Without a plain group, the largest group there is."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(_group_key(r), []).append(r)
    plain = {k: v for k, v in groups.items() if "understand" not in k}
    pool = plain or groups
    return max(pool.items(), key=lambda kv: (len(kv[1]), kv[0]))


def setup_numbers(setup: str, rows: list[dict]) -> SetupNumbers | None:
    ok = [r for r in rows if r.get("setup") == setup and r.get("status") in OK_STATUS]
    if not ok:
        return None
    writer, group = ("-", ok) if setup in ("SOURCE", "REF") else _headline_group(ok)
    kept = _mean(group, "hard_fact_recall")
    silent = _mean(group, "silent_loss_share")
    if silent is None and setup in NO_CHECKLIST and kept is not None:
        silent = 1 - kept
    return SetupNumbers(
        setup,
        writer,
        len({r["pair_id"] for r in group}),
        _mean(group, "fact_coverage"),
        kept,
        silent,
        _mean(group, "errors_per_100"),
        _mean(group, "invented_values_per_100"),
        _mean(group, "unsupported_per_100"),
    )


def decide_case(
    p2: SetupNumbers | None, zh: SetupNumbers | None, failed_share: float
) -> tuple[str, list[str]]:
    """The case of decision D-M (PLAN.md, WP13), with the comparisons it rests on."""
    if failed_share > FAILURE_LIMIT:
        share = f"{100 * failed_share:.0f} %"
        return "D", [f"the P2 run failed on {share} of the pairs (more than a quarter)"]
    if p2 is None or zh is None:
        return "-", ["P2 or P0-ZH complete has no rows: nothing to compare"]
    p2_invented, zh_invented = p2.invented or 0, zh.invented or 0
    p2_errors, zh_errors = p2.errors or 0, zh.errors or 0
    invented_better = p2_invented < zh_invented
    errors_better = p2_errors < zh_errors
    gap = (zh.fact_coverage or 0) - (p2.fact_coverage or 0)
    reasons = [
        f"invented values per 100 blocks: P2 {p2_invented:.1f} against P0-ZH "
        f"{zh_invented:.1f} ({'fewer' if invented_better else 'not fewer'})",
        f"rule errors per 100 blocks: P2 {p2_errors:.1f} against P0-ZH {zh_errors:.1f} "
        f"({'fewer' if errors_better else 'not fewer'})",
        f"fact coverage: P2 {100 * (p2.fact_coverage or 0):.0f} against P0-ZH "
        f"{100 * (zh.fact_coverage or 0):.0f} percent ({100 * gap:+.0f} points for P0-ZH)",
    ]
    if invented_better and errors_better and gap <= COVERAGE_GAP:
        return "A", reasons
    if (invented_better or errors_better) and gap > COVERAGE_GAP:
        return "B", reasons
    if not invented_better and not errors_better:
        return "C", reasons
    reasons.append(
        "better on one of the two counts only, coverage within 5 points: the rules of "
        "D-M do not cover this mix; read as A and name the count"
    )
    return "A?", reasons


def headline(results_dir: Path, *, role: str = "eval", lang: str = "de") -> Headline:
    rows = [
        r
        for r in load_rows(results_dir)
        if (role == "all" or r.get("role") == role) and r.get("lang", "de") == lang
    ]
    pairs = {r["pair_id"] for r in rows}
    setups = [s for s in (setup_numbers(name, rows) for name in SHOWN) if s is not None]
    p2_rows = [r for r in rows if r.get("setup") == "P2"]
    failed_pairs = {r["pair_id"] for r in p2_rows if r.get("status") not in OK_STATUS}
    ok_pairs = {r["pair_id"] for r in p2_rows if r.get("status") in OK_STATUS}
    failed_share = len(failed_pairs - ok_pairs) / len(pairs) if pairs else 0.0
    by_name = {s.setup: s for s in setups}
    case, reasons = decide_case(by_name.get("P2"), by_name.get("P0-ZH-complete"), failed_share)
    return Headline(str(results_dir), role, lang, len(pairs), setups, failed_share, case, reasons)


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{100 * value:.0f}"


def _num(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}"


def sentence(h: Headline) -> str:
    """The headline sentence the case asks for, with the numbers filled in."""
    p2, zh = h.get("P2"), h.get("P0-ZH-complete")
    if h.case == "D" or p2 is None or zh is None:
        return (
            "No headline comparison with P0-ZH: report the v1 and dev numbers, labelled, "
            f"with the failure rate ({100 * h.failed_share:.0f} %)."
        )
    if h.case.startswith("A"):
        return (
            "Same model, the best public Swiss prompt against our pipeline: "
            f"{_num((zh.invented or 0) - (p2.invented or 0))} fewer invented values and "
            f"{_num((zh.errors or 0) - (p2.errors or 0))} fewer rule errors per 100 blocks, "
            "and every missing fact is listed for the reviewer."
        )
    if h.case == "B":
        return (
            f"Against a strong single prompt: {_num(p2.errors)} against {_num(zh.errors)} rule "
            f"errors per 100 blocks. The prompt in its complete mode loses "
            f"{_pct(zh.silent_losses)} % of the hard facts without a trace; the pipeline lists "
            f"every missing fact (fact coverage {_pct(p2.fact_coverage)} against "
            f"{_pct(zh.fact_coverage)} percent, stated openly)."
        )
    return (
        "We ran the best single prompt through our checks: "
        f"{_num(zh.invented)} invented values per 100 blocks and "
        f"{_pct(zh.silent_losses)} % of the hard facts lost that nobody saw."
    )


def render_numbers(results_dir: Path, *, role: str = "eval", lang: str = "de") -> str:
    h = headline(results_dir, role=role, lang=lang)
    language = LANGUAGES.get(h.lang, h.lang)
    out = [
        f"Results: {h.results}, split {h.role}, {language}, {h.pairs} pairs.",
        "Means over pairs; a dash means not applicable. Per setup the plain writer with "
        "the most pairs (no other model as reader); the silent losses of a row without a "
        "fact checklist follow from the hard facts kept.",
        "",
        "| Setup | Writer | Pairs | Fact coverage | Hard facts kept | Silent losses "
        "| Errors / 100 | Invented / 100 | Unsupported / 100 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in sorted(h.setups, key=lambda s: ORDER.get(s.setup, 9)):
        out.append(
            f"| {s.setup} | {s.writer} | {s.pairs} | {_pct(s.fact_coverage)} % "
            f"| {_pct(s.hard_facts_kept)} % | {_pct(s.silent_losses)} % | {_num(s.errors)} "
            f"| {_num(s.invented)} | {_num(s.unsupported)} |"
        )
    out += ["", f"Case {h.case} of PLAN.md, decision D-M (P2 against P0-ZH complete):"]
    out += [f"- {reason}" for reason in h.reasons]
    out += [
        "",
        "Headline:",
        sentence(h),
        "",
        "Name the endpoint and the split next to every number (README, report sections 1 "
        "and 5, the video).",
    ]
    return "\n".join(out)
