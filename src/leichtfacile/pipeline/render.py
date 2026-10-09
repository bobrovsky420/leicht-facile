"""How source, fact sheet and draft look inside a prompt: one line per item, each with
its id, so the model can cite segments, facts and blocks by id."""

from __future__ import annotations

from collections.abc import Iterable

from leichtfacile.pipeline.labels import label
from leichtfacile.schemas import Draft, FactSheet, Finding, Segment, SourceDocument


def source_lines(segments: Iterable[Segment]) -> str:
    lines: list[str] = []
    last_para: int | None = None
    for seg in segments:
        if last_para is not None and seg.para != last_para:
            lines.append("")
        last_para = seg.para
        if seg.kind == "heading":
            lines.append(f"{'#' * (seg.heading_level or 2)} [{seg.id}] {seg.text}")
        elif seg.kind == "list_item":
            lines.append(f"- [{seg.id}] {seg.text}")
        else:
            lines.append(f"[{seg.id}] {seg.text}")
    return "\n".join(lines).strip()


def source_text(doc: SourceDocument) -> str:
    return source_lines(doc.segments)


def cited_source(doc: SourceDocument, segment_ids: Iterable[str]) -> str:
    wanted = set(segment_ids)
    return source_lines(s for s in doc.segments if s.id in wanted) or label(doc.lang, "none")


def factsheet_text(fs: FactSheet, fact_ids: Iterable[str] | None = None, lang: str = "de") -> str:
    wanted = set(fact_ids) if fact_ids is not None else None
    lines = []
    if fs.doc_type or fs.audience:
        lines.append(
            label(lang, "doc_type", doc_type=fs.doc_type or "?", audience=fs.audience or "?")
        )
    core = fs.core.model_dump()
    answered = [(k, v) for k, v in core.items() if v.get("text")]
    if answered and wanted is None:
        lines.append(label(lang, "core"))
        for key, value in answered:
            refs = ", ".join(value["segment_ids"])
            question = label(lang, f"core_{key}")
            lines.append(f"- {question} {value['text']}" + (f" ({refs})" if refs else ""))
        unanswered = [label(lang, f"core_{k}") for k, v in core.items() if not v.get("text")]
        if unanswered:
            lines.append(label(lang, "unanswered") + " " + " ".join(unanswered))
    lines.append(label(lang, "facts"))
    for f in fs.facts:
        if wanted is not None and f.id not in wanted:
            continue
        keep = "must_keep" if f.must_keep else label(lang, "background")
        value = label(lang, "fact_value", value=f.value_norm) if f.value_norm else ""
        refs = label(lang, "fact_from", ids=", ".join(f.segment_ids)) if f.segment_ids else ""
        lines.append(f"- {f.id} ({f.kind}, {keep}): {f.text}{value}{refs}")
    if fs.hard_terms and wanted is None:
        lines.append(label(lang, "hard_terms"))
        lines += [f"- {t.term}: {t.explanation}" for t in fs.hard_terms]
    if fs.omit_candidates and wanted is None:
        lines.append(label(lang, "omit"))
        lines += [f"- {', '.join(o.segment_ids)}: {o.reason}" for o in fs.omit_candidates]
    return "\n".join(lines)


def draft_lines(draft: Draft, *, refs: bool = True, marked: set[str] | None = None) -> str:
    lines = []
    for b in draft.blocks:
        prefix = {"heading": "# ", "list_item": "- "}.get(b.kind, "")
        mark = " <<<" if marked and b.id in marked else ""
        extra = ""
        if refs and (b.fact_ids or b.segment_ids):
            facts = ", ".join(b.fact_ids) or "-"
            sources = ", ".join(b.segment_ids) or "-"
            extra = label(draft.lang, "block_refs", facts=facts, sources=sources)
        lines.append(f"[{b.id}] {prefix}{b.text}{extra}{mark}")
    return "\n".join(lines)


def glossary_text(draft: Draft) -> str:
    entries = "\n".join(f"- {g.term}: {g.explanation}" for g in draft.glossary)
    return entries or label(draft.lang, "empty")


def finding_line(f: Finding, lang: str = "de") -> str:
    """One problem line of a repair round, with the checker's suggestion if any."""
    line = f"  - {f.rule_id}: {f.message}"
    if f.suggestion:
        line += " " + label(lang, "suggestion", text=f.suggestion)
    return line


def findings_text(findings: Iterable[Finding], lang: str = "de") -> str:
    return "\n".join(finding_line(f, lang) for f in findings)
