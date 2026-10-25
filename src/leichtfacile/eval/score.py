"""Scores for one output: the metrics of docs/architecture.md §9.

Every condition is scored the same way: language rules recomputed on the final text,
fact coverage against one fact sheet per pair, hard facts found by code, readability,
SARI against the official easy version, judge statistics where a judge ran, and the
cost of the model calls that produced the output.
"""

from __future__ import annotations

import re
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from leichtfacile.eval.calibrate import source_as_draft
from leichtfacile.eval.metrics import compression_ratio, sari_document
from leichtfacile.rules import check_draft
from leichtfacile.rules.document import fact_coverage, foreign_values
from leichtfacile.rules.glossary import unexplained_terms
from leichtfacile.rules.mediopunkt import GLOSSARY
from leichtfacile.rules.mediopunkt import RULE_ID as MEDIOPUNKT_RULE
from leichtfacile.rules.values import (
    Value,
    extract_values,
    hard_value_found,
    hard_values,
    matches,
    parse_value_norm,
)
from leichtfacile.rules.vocabulary import OFFICE_RULES
from leichtfacile.schemas import (
    BASELINE_CONDITIONS,
    CodeEdit,
    Draft,
    FactSheet,
    Job,
    JudgeReport,
    SourceDocument,
)

WORDS_PER_PAGE = 250
# USD per million input and output tokens by a part of the model's name, from prices.toml
# next to this module: Apertus at Public AI's list prices (the CSCS endpoint of the
# reported runs charged nothing), gpt-oss at Groq's; an entry without prices is a server
# of one's own, which pays for hardware instead. Reported as an order of magnitude.
PRICES_FILE = Path(__file__).with_name("prices.toml")
LANGUAGE_FAMILIES = ("LEN", "ORD", "GRAM", "NEG", "LEX", "NUM", "CH")


@dataclass(frozen=True)
class Price:
    match: tuple[str, ...]  # lowercase parts of model names, any of them
    input: float | None  # USD per million tokens; None: no price per token
    output: float | None
    note: str = ""


def read_prices(path: Path) -> list[Price]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    prices = []
    for entry in data.get("model", []):
        match = entry["match"]
        parts = (match,) if isinstance(match, str) else tuple(match)
        prices.append(
            Price(
                tuple(part.lower() for part in parts),
                entry.get("input"),
                entry.get("output"),
                entry.get("note", ""),
            )
        )
    return prices


PRICES = read_prices(PRICES_FILE)


def price(model: str) -> tuple[float, float] | None:
    """The prices of the first entry whose match is part of the model's name; None for a
    model without a price per token (own hardware) or an unknown one."""
    name = model.lower()
    for entry in PRICES:
        if any(part in name for part in entry.match):
            if entry.input is None or entry.output is None:
                return None
            return entry.input, entry.output
    return None


def text_metrics(draft: Draft, standard: SourceDocument) -> dict[str, Any]:
    """Model-free metrics of a text, comparable across conditions and the reference."""
    checked = check_draft(draft)
    blocks = max(1, len(draft.blocks))
    severity = Counter(f.severity for f in checked.findings)
    by_family: Counter = Counter()
    for f in checked.findings:
        family = f.rule_id.split("-")[0]
        if family in LANGUAGE_FAMILIES and f.severity != "info":
            by_family[family] += 1
    source_keys = hard_values(standard.text(), standard.lang)
    out_values = extract_values(draft.text(), draft.lang)
    found = sum(1 for key in source_keys if hard_value_found(key, out_values))
    # Without a fact checklist and an omission log (the baselines, the official version)
    # every hard value the text lost is lost in silence; `silent_losses` below narrows
    # this for a pipeline job.
    silent = len(source_keys) - found
    # Values the source does not contain, strictly against the source (the runtime
    # rule FACT-06 also accepts the fact sheet's values; here a value the fact sheet
    # invented counts too).
    invented = foreign_values(draft, standard, None, draft.lang)
    m = checked.metrics
    return {
        "blocks": len(draft.blocks),
        "sentences": m.sentences,
        "words": m.words,
        "avg_words": m.avg_words,
        "max_words": m.max_words,
        "readability": m.readability,
        "errors_per_100": round(100 * severity["error"] / blocks, 2),
        "warnings_per_100": round(100 * severity["warn"] / blocks, 2),
        "by_family_per_100": {k: round(100 * v / blocks, 2) for k, v in sorted(by_family.items())},
        # office words left (LEX-07, any level), comparable with the reference
        "office_words_per_100": round(
            100 * sum(1 for f in checked.findings if f.rule_id in OFFICE_RULES) / blocks, 2
        ),
        "pct_passive": m.pct_passive,
        "pct_subordinate": m.pct_subordinate,
        "hard_facts_total": len(source_keys),
        "hard_facts_found": found,
        "hard_fact_recall": round(found / len(source_keys), 3) if source_keys else None,
        "silent_losses": silent,
        "silent_loss_share": round(silent / len(source_keys), 3) if source_keys else None,
        "invented_values": len(invented),
        "invented_values_per_100": round(100 * len(invented) / blocks, 2),
        "compression": round(compression_ratio(max(1, standard.word_count()), m.words), 3),
    }


def score_reference(standard: SourceDocument, easy: SourceDocument) -> dict[str, Any]:
    """The official easy-language version, scored like an output."""
    draft = source_as_draft(easy, "A2")
    return {"setup": "REF", **text_metrics(draft, standard)}


def score_source(standard: SourceDocument) -> dict[str, Any]:
    """The standard-language original, scored as if it were a draft (how far from easy)."""
    return {"setup": "SOURCE", **text_metrics(source_as_draft(standard, "A2"), standard)}


def silent_losses(
    draft: Draft, standard: SourceDocument, factsheet: FactSheet | None, *, condition: str
) -> dict[str, Any]:
    """Hard values of the source that the output lost without a trace: not in the text,
    and nowhere a reviewer would see them. For a pipeline job (P1, P2) a lost value is
    told when the fact sheet carries it (the review checklist lists every fact, must-keep
    or background, with its status) or when the source sentence it stands in is listed
    as left out, by the draft's omissions or the fact sheet's omit candidates. A single
    prompt (P0, P0-ZH) has neither, so every value it loses is silent; the reference
    fact sheet the scorer borrows for it does not count. Zero by design for P1 and P2
    as long as the code completion of the fact sheet covers every hard value: a count
    above zero there names a value the completion missed."""
    lang = standard.lang
    keys = hard_values(standard.text(), lang)
    out_values = extract_values(draft.text(), draft.lang)
    lost = [key for key in keys if not hard_value_found(key, out_values)]
    told: set[tuple[str, str]] = set()
    if factsheet is not None and condition not in BASELINE_CONDITIONS:
        fact_values = [
            v for f in factsheet.facts if (v := parse_value_norm(f.value_norm, f.kind, lang))
        ]
        omitted = {s for o in draft.omissions for s in o.segment_ids}
        omitted |= {s for o in factsheet.omit_candidates for s in o.segment_ids}
        omitted_values = [
            v
            for seg in standard.segments
            if seg.id in omitted
            for v in extract_values(seg.text, lang)
        ]
        for key in lost:
            target = Value(*key)  # type: ignore[arg-type]
            if any(matches(target, v) for v in fact_values) or hard_value_found(
                key, omitted_values
            ):
                told.add(key)
    silent = [key for key in lost if key not in told]
    return {
        "silent_losses": len(silent),
        "silent_loss_share": round(len(silent) / len(keys), 3) if keys else None,
        "silent_loss_kinds": dict(sorted(Counter(k[0] for k in silent).items())),
    }


def kept_code_splits(final: Draft, edits: list[CodeEdit]) -> int:
    """Edits made by code on any version up to `final` whose split word is still in it.
    A repair gets the split text and mostly keeps the dot, and each version records only
    the edits made on it, so the final version's own edits miss the earlier rounds'."""
    texts = {"blocks": final.text(), GLOSSARY: "\n".join(g.term for g in final.glossary)}
    kept = set()
    for edit in edits:
        if edit.rule_id != MEDIOPUNKT_RULE:  # a glossary entry from the vocabulary
            continue
        text = texts[GLOSSARY if edit.block_id == GLOSSARY else "blocks"]
        if re.search(rf"(?<!\w){re.escape(edit.after)}(?!\w)", text):
            kept.add((edit.block_id, edit.after))
    return len(kept)


def score_output(
    job: Job,
    draft: Draft,
    standard: SourceDocument,
    easy: SourceDocument,
    factsheet: FactSheet | None,
    judge: JudgeReport | None,
    code_edits: list[CodeEdit] | None = None,
) -> dict[str, Any]:
    """`code_edits`: the edits of every version up to `draft` (default: its own only)."""
    row: dict[str, Any] = {"setup": job.config.condition, **text_metrics(draft, standard)}
    row.update(silent_losses(draft, standard, factsheet, condition=job.config.condition))
    # Compounds split by code that stand in the final version (rules/mediopunkt.py, P1 and
    # P2 only): the deterministic share of the LEX improvement, reported next to the LEX
    # family.
    splits = kept_code_splits(draft, draft.code_edits if code_edits is None else code_edits)
    row["code_splits"] = splits
    row["mediopunkt_per_100"] = round(100 * splits / max(1, len(draft.blocks)), 2)
    # The glossary (rules/glossary.py): its entries, those code added from the
    # vocabulary, and the hard terms of the vocabulary the text uses without one.
    row["glossary_entries"] = len(draft.glossary)
    row["code_glossary"] = sum(1 for g in draft.glossary if g.origin == "vocabulary")
    row["unexplained_terms"] = len(unexplained_terms(draft))
    if factsheet is not None:
        coverage = fact_coverage(draft, factsheet, draft.lang, standard)
        row["facts_checkable"] = len(coverage.checkable)
        row["fact_coverage"] = round(coverage.ratio, 3) if coverage.ratio is not None else None
    row["sari"] = round(
        sari_document(standard.text(), draft.text(), [easy.text()], lang=draft.lang), 2
    )
    if judge is not None:
        statuses = Counter(c.status for c in judge.fact_checks)
        total = max(1, sum(statuses.values()))
        row["judge_present"] = round(statuses["present"] / total, 3)
        row["judge_missing"] = round(statuses["missing"] / total, 3)
        row["judge_distorted"] = round(statuses["distorted"] / total, 3)
        row["unsupported_per_100"] = round(
            100 * len(judge.unsupported) / max(1, len(draft.blocks)), 2
        )
        row["judge_model"] = judge.model
    usage = job.usage
    tokens_in = sum(u.tokens_in for u in usage)
    tokens_out = sum(u.tokens_out for u in usage)
    pages = max(standard.word_count() / WORDS_PER_PAGE, 0.25)
    cost = 0.0
    priced = True
    for u in usage:
        p = price(u.model)
        if p is None:
            priced = False
            continue
        cost += u.tokens_in * p[0] / 1e6 + u.tokens_out * p[1] / 1e6
    row.update(
        calls=len(usage),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_s=round(sum(u.latency_ms for u in usage) / 1000, 1),
        pages=round(pages, 2),
        tokens_per_page=round((tokens_in + tokens_out) / pages),
        usd_per_page=round(cost / pages, 5) if priced and usage else None,
        latency_s_per_page=round(sum(u.latency_ms for u in usage) / 1000 / pages, 1),
        draft_version=draft.version,
    )
    return row
