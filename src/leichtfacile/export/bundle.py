"""The JSON audit bundle: everything needed to show where each published sentence comes
from and who approved it (docs/use-case-canton.md, step 8)."""

from __future__ import annotations

from typing import Any

from leichtfacile import __version__
from leichtfacile.export.layout import build_layout, plain_lines
from leichtfacile.rules import get_checker
from leichtfacile.schemas import Draft, Job, ReviewState, utcnow
from leichtfacile.store import Store

BUNDLE_FORMAT = "leicht-facile/audit-bundle@1"


def build_bundle(store: Store, job: Job) -> dict[str, Any]:
    def versions(name: str) -> list[dict]:
        return [store.get_artifact_json(job.id, name, v) for v in store.versions(job.id, name)]

    summary = store.get_artifact_json(job.id, "summary")
    drafts = versions("draft")
    final_version = (summary or {}).get("final_version") or (
        drafts[-1]["version"] if drafts else None
    )
    review_json = store.get_artifact_json(job.id, "review")
    final: dict[str, Any] | None = None
    if final_version is not None:
        draft = store.get_artifact(job.id, "draft", Draft, version=final_version)
        review = ReviewState.model_validate(review_json) if review_json else None
        notice = job.config.notice  # decision mode: the first and the last line
        layout = build_layout(draft, review, notice=notice)
        text = layout.final
        lines = plain_lines(layout)  # the lines every export prints
        checker = get_checker(draft.lang)
        final = {
            "draft_version": final_version,
            "reviewed": text.reviewed,
            "review_complete": text.complete,
            "undecided_blocks": text.undecided,
            "undecided_glossary": text.undecided_glossary,
            "notice": notice,
            "blocks": [b.model_dump() for b in text.blocks],
            "glossary": [g.model_dump() for g in text.glossary],
            "layout_findings": [
                f.model_dump() for f in checker.check_export(lines, draft.level, notice=notice)
            ],
        }
    return {
        "format": BUNDLE_FORMAT,
        "tool": f"leicht-facile {__version__}",
        "exported_at": utcnow().isoformat(),
        "job": job.model_dump(mode="json"),
        "summary": summary,
        "source": store.get_artifact_json(job.id, "source"),
        "factsheet": store.get_artifact_json(job.id, "factsheet"),
        "drafts": drafts,
        "rule_findings": versions("rules"),
        "judge_reports": versions("judge"),
        "repair_records": versions("repair"),
        "review": review_json,
        "final": final,
    }
