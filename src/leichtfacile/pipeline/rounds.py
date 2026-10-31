"""The rounds after the first draft, as one plan (docs/architecture.md §4.6).

Every round starts from a draft version with its checks, asks the model for a repair
(the recover round: for each missing value alone) and ends like the write stage: code's
edits, the rule check, the judge (`Orchestrator._finish`). The kinds differ only in what
they ask for, which version they start from, what measures their progress and how often
they may run:

- repair, from the latest version, `repair_rounds` times at most: the rule errors, the
  missing values and the judge's problems, or the warnings when nothing blocks; it goes
  on while the blocking findings fall;
- facts, from the latest, `facts_rounds` times: the missing must-keep values alone; it
  goes on while the missing values fall;
- recover, from the best version, once: each missing value with its source paragraph,
  `recover_facts` values at most;
- polish, from the best, `polish_rounds` times: the rule errors, else the warnings, no
  fact and no judge's problem;
- vocabulary, from the best, once: the office words (LEX-07).

Only the repair rounds run without repair rounds, that is none, and nothing runs after
a round the endpoint failed. The best version is the one with the fewest must-keep
values missing, then the fewest blocking findings, then the latest (`best`).

This module holds what a round asks for; the model calls and the stored artifacts are
the orchestrator's.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from leichtfacile.pipeline import render
from leichtfacile.pipeline.labels import label
from leichtfacile.pipeline.stages import RepairRequest, shared_stems
from leichtfacile.rules.vocabulary import OFFICE_RULES
from leichtfacile.schemas import (
    Draft,
    FactSheet,
    Finding,
    JudgeReport,
    PipelineOptions,
    RoundKind,
    RuleFindings,
)

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

# A draft version with its checks: what a round starts from and what it produces.
Step = tuple[Draft, RuleFindings, JudgeReport | None]


def repairable(finding: Finding) -> bool:
    """Whether a repair round can fix the finding by rewriting its block."""
    return finding.rule_id.split("-")[0] in REPAIRABLE or finding.rule_id in REPAIRABLE_RULES


def missing_count(rules: RuleFindings) -> int:
    """Must-keep values the draft still lacks (FACT-01), and in decision mode the parts
    of the decision it dropped (FACT-08): the measure of a facts round."""
    return sum(1 for f in rules.findings if f.rule_id in MISSING_RULES)


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


def version_key(rules: RuleFindings, judge: JudgeReport | None) -> tuple[int, int]:
    """The order of the draft versions, best first: the fewest must-keep values
    missing, then the fewest blocking findings. Facts come first because a reviewer can
    reject an unsupported sentence or mend a long one with a click, but cannot conjure
    a missing deadline; before 8 October 2026 the blocking count alone decided, and the
    dev rerun of 7 October showed it discarding versions a facts round had just filled
    (docs/prompts.md, "Fact-retention diagnosis", bucket k)."""
    return (missing_count(rules), blocking_count(rules, judge))


def best(history: list[Step]) -> Step:
    """The best version so far: by `version_key`, the latest at a tie."""
    return min(history, key=lambda h: (*version_key(h[1], h[2]), -h[0].version))


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
                # A fact a block already carries by code's links (a value it contains, a
                # sentence it cites: stages.link_facts) is asked for on that block, not
                # as new sentences: the 70B called obligations missing that stood there
                # in other words ("Papier vom Arzt" for the Arztzeugnis), and every round
                # then added a paraphrase of the block (the school letters, 31 October
                # 2026). A repair replaces the block, so it cannot repeat it. A heading
                # carries nothing, whatever fact ids the writer gave it: the 70B hangs
                # the facts of a section on its question heading. Its fact ids are loose
                # elsewhere too (the Teilnahme fact on the sentence about finding a
                # place), so of several carrying blocks the one whose words overlap the
                # fact's most is asked, in document order at a tie.
                carrying = sorted(
                    (b for b in draft.blocks if c.fact_id in b.fact_ids and b.kind != "heading"),
                    key=lambda b: -shared_stems(b.text, fact.text, lang),
                )
                if carrying:
                    unclear = label(
                        lang, "judge_missing", fact_id=c.fact_id, note=c.note, fact=fact.text
                    )
                    problems[carrying[0].id].append(f"  - {unclear}")
                else:
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


# -- the plan ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoundSpec:
    """One kind of round in the plan (the table above)."""

    kind: RoundKind
    limit: int  # rounds of this kind at most; 0: the kind does not run
    from_best: bool = False  # start from the best version so far, else from the latest
    measure: Literal["blocking", "missing"] | None = None  # what a round must lower to go on


def plan(options: PipelineOptions) -> list[RoundSpec]:
    """The rounds a job runs, in order. The kinds after the repair rounds need repair
    rounds: a job without them gets the first draft as it is."""
    after = bool(options.repair_rounds)
    return [
        RoundSpec("repair", options.repair_rounds, measure="blocking"),
        RoundSpec("facts", options.facts_rounds if after else 0, measure="missing"),
        RoundSpec("recover", 1 if after and options.recover_facts else 0, from_best=True),
        RoundSpec("polish", options.polish_rounds if after else 0, from_best=True),
        RoundSpec("vocabulary", 1 if after and options.vocabulary else 0, from_best=True),
    ]


def request_for(
    spec: RoundSpec,
    draft: Draft,
    rules: RuleFindings,
    judge: JudgeReport | None,
    factsheet: FactSheet,
    options: PipelineOptions,
) -> RepairRequest:
    """What a round of the spec's kind asks for, from the version it starts from. The
    recover round asks per fact through `stages.recover_fact` instead."""
    if spec.kind == "repair":
        # First what blocks the draft; the warnings get a round once nothing blocks.
        blocking = blocking_count(rules, judge)
        return build_request(
            draft,
            rules,
            judge,
            factsheet,
            include_warnings=blocking == 0,
            vocabulary=options.vocabulary,
        )
    if spec.kind == "facts":
        return build_request(
            draft, rules, judge, factsheet, facts_only=True, limit=options.missing_per_facts_round
        )
    if spec.kind == "polish":
        blocks = draft.by_id()
        errors = any(
            f.severity == "error" and f.block_id in blocks and repairable(f) for f in rules.findings
        )
        return build_request(
            draft, rules, None, factsheet, include_warnings=not errors, limit=0, vocabulary=False
        )
    if spec.kind == "vocabulary":
        return build_request(draft, rules, judge, factsheet, only=OFFICE_RULES)
    raise ValueError(f"no request for a {spec.kind} round")
