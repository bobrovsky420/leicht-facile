"""Checker calibration on professionally written easy-language texts.

Official Leichte Sprache pages should raise almost no `error` findings. Each error the
checker raises on them is either a real deviation or a false positive to fix; the rate
per 100 blocks is the false-positive baseline recorded in docs/rules.md.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from leichtfacile.rules import check_draft, source_as_draft
from leichtfacile.rules.messages import render_finding
from leichtfacile.schemas import Level, SourceDocument


@dataclass
class RuleStats:
    rule_id: str
    severity: str
    count: int = 0
    documents: set[str] = field(default_factory=set)
    examples: list[tuple[str, str, str]] = field(default_factory=list)  # doc, text, message


@dataclass
class Calibration:
    level: str
    documents: int = 0
    blocks: int = 0
    rules: dict[str, RuleStats] = field(default_factory=dict)
    severities: Counter = field(default_factory=Counter)

    def per_100(self, severity: str) -> float:
        return 100 * self.severities[severity] / self.blocks if self.blocks else 0.0


def calibrate(
    docs: list[tuple[str, SourceDocument]], level: Level = "A2", examples: int = 3
) -> Calibration:
    result = Calibration(level=level)
    for name, doc in docs:
        draft = source_as_draft(doc, level)
        checked = check_draft(draft)
        texts = {b.id: b.text for b in draft.blocks}
        result.documents += 1
        result.blocks += len(draft.blocks)
        for f in checked.findings:
            key = f"{f.rule_id} {f.severity}"  # one rule can report several severities
            stats = result.rules.setdefault(key, RuleStats(f.rule_id, f.severity))
            stats.count += 1
            stats.documents.add(name)
            result.severities[f.severity] += 1
            if len(stats.examples) < examples:
                stats.examples.append((name, texts.get(f.block_id, ""), render_finding(f)))
    return result


def render_calibration(cal: Calibration, *, show_examples: bool = False) -> str:
    lines = [
        f"Calibration on {cal.documents} official easy-language texts, {cal.blocks} blocks, "
        f"level {cal.level}.",
        "",
        f"Per 100 blocks: {cal.per_100('error'):.1f} errors, {cal.per_100('warn'):.1f} warnings, "
        f"{cal.per_100('info'):.1f} info.",
        "",
        "| Rule | Severity | Findings | Per 100 blocks | Texts |",
        "|------|----------|----------|----------------|-------|",
    ]
    order = {"error": 0, "warn": 1, "info": 2}
    by_rule: dict[str, list[RuleStats]] = defaultdict(list)
    for stats in cal.rules.values():
        by_rule[stats.rule_id].append(stats)
    for stats in sorted(cal.rules.values(), key=lambda s: (order[s.severity], -s.count)):
        rate = 100 * stats.count / cal.blocks if cal.blocks else 0
        lines.append(
            f"| {stats.rule_id} | {stats.severity} | {stats.count} | {rate:.1f} "
            f"| {len(stats.documents)} |"
        )
    if show_examples:
        lines += ["", "Examples (local only: these are quotes from protected pages):", ""]
        for stats in sorted(cal.rules.values(), key=lambda s: (order[s.severity], -s.count)):
            for doc, text, message in stats.examples:
                lines.append(f"- {stats.rule_id} [{doc}] {message}")
                lines.append(f"  | {text[:160]}")
    return "\n".join(lines)
