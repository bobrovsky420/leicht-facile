"""The headline numbers of a results folder (`eval numbers`): the means README, report
§1 and §5 and the video quote, P2 against the Zurich prompt in its complete mode, and
the case of decision D-M (PLAN.md, WP13) the numbers fall into. No model call, no text
of the protected pages: the numbers audit at G4 and G6 becomes a diff, not a hunt.

Since 14 October 2026 also the uncertainty of the headline: each comparison paired
over the pairs both setups have, with a bootstrap 95 % interval of the mean difference
and the count of pairs where P2 is better, worse or level, and the hard values lost
without a trace pooled over all pairs, with an exact 95 % interval.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import comb
from pathlib import Path
from statistics import fmean, mean

from leichtfacile.eval.report import LANGUAGES, ORDER, load_rows
from leichtfacile.schemas import BASELINE_CONDITIONS

OK_STATUS = (None, "needs_review", "done")
SHOWN = ("REF", "P0", "P0-ZH-complete", "P0-ZH-condensed", "P1", "P2")
# Rows without a fact checklist: every hard value they lose is a silent loss, so the
# share follows from the hard facts kept when a row stored before the key has none.
NO_CHECKLIST = frozenset({"SOURCE", "REF", *BASELINE_CONDITIONS})
COVERAGE_GAP = 0.05  # case A allows P2 up to 5 points below P0-ZH on fact coverage
FAILURE_LIMIT = 0.25  # case D: the final run fails on more than a quarter of the pairs
RESAMPLES = 10_000  # bootstrap resamples of the pairs
SEED = 0  # fixed, so the intervals do not move between two prints of the same results
# the paired measures: row key, label, scale, digits, whether a higher value is better
PAIRED = (
    ("fact_coverage", "Fact coverage (points)", 100, 1, True),
    ("hard_fact_recall", "Hard facts kept (points)", 100, 1, True),
    ("silent_loss_share", "Silent losses (points)", 100, 1, False),
    ("errors_per_100", "Rule errors / 100 blocks", 1, 1, False),
    ("readability", "Readability (Amstad, Flesch)", 1, 1, True),
    ("usd_per_page", "USD per page", 1, 4, False),
)


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
    case: str  # A, A2, B, C, D; "A?" for a mix the rules do not cover; "-" without rows
    reasons: list[str]

    def get(self, setup: str) -> SetupNumbers | None:
        return next((s for s in self.setups if s.setup == setup), None)


@dataclass(frozen=True)
class PairedDiff:
    """One measure of setup a against setup b over the pairs both have a value for."""

    label: str
    digits: int
    pairs: int
    mean_a: float
    mean_b: float
    diff: float  # mean of a - b, in the measure's scale
    low: float  # bootstrap 95 % interval of `diff`
    high: float
    better: int  # pairs where a is better than b
    worse: int
    tied: int


@dataclass(frozen=True)
class Comparison:
    a: str  # "P2 (8B)"
    b: str
    pairs: int
    diffs: list[PairedDiff]


@dataclass(frozen=True)
class Pooled:
    """Hard values lost without a trace, pooled over the pairs of one group."""

    name: str
    hard_values: int
    silent: int
    low: float  # exact (Clopper-Pearson) 95 % interval of the share
    high: float
    blocks: int
    invented: int  # values not in the source


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
    if errors_better and gap <= 0:
        # case A2 (owner, 11 Oct): fewer rule errors and at least the same fact coverage,
        # but not fewer invented values; the headline names facts and rules
        return "A2", reasons
    reasons.append(
        "better on one of the two counts only, coverage within 5 points: the rules of "
        "D-M do not cover this mix; read as A and name the count"
    )
    return "A?", reasons


def _split_rows(results_dir: Path, role: str, lang: str) -> list[dict]:
    return [
        r
        for r in load_rows(results_dir)
        if (role == "all" or r.get("role") == role) and r.get("lang", "de") == lang
    ]


def _group_rows(rows: list[dict], setup: str, key: str | None = None) -> tuple[str, list[dict]]:
    """The ok rows of one setup: the group `key` (writer, and reader if another), or the
    group `setup_numbers` uses when `key` is None."""
    ok = [r for r in rows if r.get("setup") == setup and r.get("status") in OK_STATUS]
    if not ok:
        return "-", []
    if setup in ("SOURCE", "REF"):
        return "-", ok
    if key is None:
        return _headline_group(ok)
    return key, [r for r in ok if _group_key(r) == key]


def _value(row: dict, key: str) -> float | None:
    value = row.get(key)
    if value is None and key == "silent_loss_share" and row.get("setup") in NO_CHECKLIST:
        kept = row.get("hard_fact_recall")
        value = None if kept is None else 1 - kept
    return value


def bootstrap_interval(
    diffs: list[float], resamples: int = RESAMPLES, seed: int = SEED
) -> tuple[float, float]:
    """Percentile 95 % interval of the mean of `diffs`, resampling them with replacement."""
    rnd = random.Random(seed)
    means = sorted(fmean(rnd.choices(diffs, k=len(diffs))) for _ in range(resamples))
    return means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]


def exact_interval(k: int, n: int) -> tuple[float, float]:
    """Clopper-Pearson 95 % interval of a share of k in n, by bisection on the binomial."""

    def cdf(p: float, upto: int) -> float:
        return sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(upto + 1))

    def solve(target: float, upto: int) -> float:  # the p where P(X <= upto) = target
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if cdf(mid, upto) > target else (lo, mid)
        return (lo + hi) / 2

    low = 0.0 if k == 0 else solve(0.975, k - 1)  # P(X >= k) = 0.025
    high = 1.0 if k >= n else solve(0.025, k)  # P(X <= k) = 0.025
    return low, high


def compare(rows: list[dict], a: tuple[str, str | None], b: tuple[str, str | None]) -> Comparison:
    """Setup a against setup b, paired over the pairs both have; each a (setup, group
    key) with the key None for the group the headline uses."""
    a_key, a_rows = _group_rows(rows, *a)
    b_key, b_rows = _group_rows(rows, *b)
    a_by = {r["pair_id"]: r for r in a_rows}
    b_by = {r["pair_id"]: r for r in b_rows}
    common = sorted(set(a_by) & set(b_by))
    diffs = []
    for key, label, scale, digits, higher in PAIRED:
        values = [(_value(a_by[p], key), _value(b_by[p], key)) for p in common]
        values = [(x, y) for x, y in values if x is not None and y is not None]
        if not values:
            continue
        d = [scale * (x - y) for x, y in values]
        low, high = bootstrap_interval(d)
        up = sum(1 for x in d if x > 1e-9)
        down = sum(1 for x in d if x < -1e-9)
        diffs.append(
            PairedDiff(
                label, digits, len(d),
                fmean(scale * x for x, _ in values), fmean(scale * y for _, y in values),
                fmean(d), low, high,
                up if higher else down, down if higher else up, len(d) - up - down,
            )
        )  # fmt: skip
    return Comparison(_name(a[0], a_key), _name(b[0], b_key), len(common), diffs)


def _name(setup: str, key: str) -> str:
    if key == "-":
        return setup
    return f"{setup} ({key.removeprefix('swiss-ai/')})"


def pooled(rows: list[dict], setup: str, key: str | None = None) -> Pooled | None:
    group_key, group = _group_rows(rows, setup, key)
    group = [r for r in group if r.get("hard_facts_total") is not None]
    if not group:
        return None
    total = sum(r["hard_facts_total"] for r in group)
    silent = 0
    for r in group:
        if r.get("silent_losses") is not None:
            silent += r["silent_losses"]
        elif setup in NO_CHECKLIST:
            silent += r["hard_facts_total"] - (r.get("hard_facts_found") or 0)
    low, high = exact_interval(silent, total) if total else (0.0, 1.0)
    return Pooled(
        _name(setup, group_key), total, silent, low, high,
        sum(r.get("blocks") or 0 for r in group),
        sum(r.get("invented_values") or 0 for r in group),
    )  # fmt: skip


def headline(results_dir: Path, *, role: str = "eval", lang: str = "de") -> Headline:
    rows = _split_rows(results_dir, role, lang)
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
    if h.case == "A2":
        lost = (
            "loses none without a trace"
            if not p2.silent_losses
            else f"loses {_pct(p2.silent_losses)} percent without a trace"
        )
        return (
            "Same model, a strong single prompt against our pipeline: the pipeline finds "
            f"{_pct(p2.fact_coverage)} percent of the must-keep facts against "
            f"{_pct(zh.fact_coverage)}, {lost} against {_pct(zh.silent_losses)} percent, "
            f"and has {_num(p2.errors)} against {_num(zh.errors)} rule errors per 100 "
            f"blocks. Invented values are rare on both sides ({_num(p2.invented)} against "
            f"{_num(zh.invented)})."
        )
    if h.case.startswith("A"):
        return (
            "Same model, a strong single prompt against our pipeline: "
            # differences of the rounded means, so the sentence agrees with the table
            f"{_num(round(zh.invented or 0, 1) - round(p2.invented or 0, 1))} fewer invented "
            f"values and {_num(round(zh.errors or 0, 1) - round(p2.errors or 0, 1))} fewer rule "
            "errors per 100 blocks, "
            "and every hard fact it misses is listed for the reviewer."
        )
    if h.case == "B":
        return (
            f"Against a strong single prompt: {_num(p2.errors)} against {_num(zh.errors)} rule "
            f"errors per 100 blocks. The prompt in its complete mode loses "
            f"{_pct(zh.silent_losses)} % of the hard facts without a trace; the pipeline lists "
            f"every hard fact it misses (fact coverage {_pct(p2.fact_coverage)} against "
            f"{_pct(zh.fact_coverage)} percent, stated openly)."
        )
    return (
        "We ran the Canton of Zurich's published prompt through our checks: "
        f"{_num(zh.invented)} invented values per 100 blocks and "
        f"{_pct(zh.silent_losses)} % of the hard facts lost that nobody saw."
    )


def comparisons(rows: list[dict]) -> list[Comparison]:
    """P2 against the Zurich prompt (complete), and every other plain P2 writer (the 70B
    everywhere) against the P2 of the headline."""
    out = []
    head_key, head = _group_rows(rows, "P2")
    if not head:
        return out
    if _group_rows(rows, "P0-ZH-complete")[1]:
        out.append(compare(rows, ("P2", None), ("P0-ZH-complete", None)))
    keys = {_group_key(r) for r in rows if r.get("setup") == "P2" and not r.get("understand")}
    for key in sorted(keys - {head_key}):
        if _group_rows(rows, "P2", key)[1]:
            out.append(compare(rows, ("P2", key), ("P2", head_key)))
    return out


def _signed(value: float, digits: int) -> str:
    return f"{value:+.{digits}f}"


def render_uncertainty(results_dir: Path, *, role: str = "eval", lang: str = "de") -> list[str]:
    rows = _split_rows(results_dir, role, lang)
    out = []
    for c in comparisons(rows):
        out += [
            "",
            f"Paired, {c.a} against {c.b}: {c.pairs} pairs; the mean difference with a "
            f"bootstrap 95 % interval over the pairs ({RESAMPLES:,} resamples, seed {SEED}); "
            f"better, worse and level count the pairs, from the side of {c.a}.",
            "",
            f"| Measure | Pairs | {c.a} | {c.b} | Difference | 95 % interval "
            "| Better / worse / level |",
            "|---|---|---|---|---|---|---|",
        ]
        for d in c.diffs:
            out.append(
                f"| {d.label} | {d.pairs} | {d.mean_a:.{d.digits}f} | {d.mean_b:.{d.digits}f} "
                f"| {_signed(d.diff, d.digits)} | {_signed(d.low, d.digits)} to "
                f"{_signed(d.high, d.digits)} | {d.better} / {d.worse} / {d.tied} |"
            )
    pools = [p for p in (pooled(rows, "P2"), pooled(rows, "P0-ZH-complete")) if p is not None]
    if pools:
        out += ["", "Pooled over the pairs (exact 95 % interval of the share):"]
        for p in pools:
            share = p.silent / p.hard_values if p.hard_values else 0.0
            out.append(
                f"- {p.name}: {p.silent} of {p.hard_values} hard values lost without a trace "
                f"({100 * share:.1f} %, {100 * p.low:.1f} to {100 * p.high:.1f} %); "
                f"{p.invented} values not in the source in {p.blocks} blocks"
            )
    return out


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
        "| Errors / 100 | Not in source / 100 | Unsupported / 100 |",
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
    out += render_uncertainty(results_dir, role=role, lang=lang)
    out += [
        "",
        "Headline:",
        sentence(h),
        "",
        "Name the endpoint and the split next to every number (README, report sections 1 "
        "and 5, the video).",
    ]
    return "\n".join(out)
