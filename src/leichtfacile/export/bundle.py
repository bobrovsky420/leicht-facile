"""The JSON audit bundle: everything needed to show where each published sentence comes
from and who approved it (docs/use-case-canton.md, step 8): the job with who submitted
it (`created_by`), every decision with its stamp and the user who made it (`by`), the
review with who saved it last, `final.reviewers` (the users who decided, once each) and
`exported_by`, who downloaded the bundle. The users are the ones the proxy login names
(web/security.py); without one they are null."""

from __future__ import annotations

from typing import Any

from leichtfacile import __version__
from leichtfacile.export.layout import build_layout, plain_lines
from leichtfacile.rules import get_checker
from leichtfacile.schemas import Draft, Job, ReviewState, utcnow
from leichtfacile.store import Store

BUNDLE_FORMAT = "leicht-facile/audit-bundle@1"


def build_bundle(store: Store, job: Job, *, exported_by: str | None = None) -> dict[str, Any]:
    def versions(name: str) -> list[dict]:
        found = (store.get_artifact_json(job.id, name, v) for v in store.versions(job.id, name))
        return [a for a in found if a is not None]

    summary = store.get_artifact_json(job.id, "summary")
    drafts = versions("draft")
    final_version = (summary or {}).get("final_version") or (
        drafts[-1]["version"] if drafts else None
    )
    review_json = store.get_artifact_json(job.id, "review")
    final: dict[str, Any] | None = None
    draft = (
        store.get_artifact(job.id, "draft", Draft, version=final_version)
        if final_version is not None
        else None
    )
    if draft is not None:
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
            "reviewers": text.reviewers,
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
        "exported_by": exported_by,
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
