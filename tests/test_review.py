"""The review read from the artifacts without the web application (review.py): the
issues per block, the fact checklist, the counts, and that the module imports no web
module, so the pipeline's counts never depend on the interface."""

from __future__ import annotations

import subprocess
import sys

from leichtfacile.review import (
    block_issues,
    decided_count,
    fact_counts,
    review_items,
    severity_counts,
)
from leichtfacile.schemas import (
    Block,
    Decision,
    Draft,
    Finding,
    GlossaryEntry,
    JudgeReport,
    ReviewState,
    RuleFindings,
    Unsupported,
)


def draft() -> Draft:
    return Draft(
        doc_id="d", lang="de", level="A2",
        blocks=[
            Block(id="b001", kind="sentence", text="Die Antragstellung erfolgt bis 31. März."),
            Block(id="b002", kind="sentence", text="Das kostet 20 Franken."),
        ],
        glossary=[GlossaryEntry(term="Antrag", explanation="Ein Formular.")],
    )  # fmt: skip


def test_issues_are_sorted_per_block_and_document_findings_kept_apart() -> None:
    rules = RuleFindings(
        draft_version=1, level="A2",
        findings=[
            Finding(block_id="b001", rule_id="GRAM-05", severity="warn", key="GRAM-05",
                    params={"found": "Antragstellung"}, evidence="Antragstellung",
                    suggestion="den Antrag stellen"),
            Finding(block_id="b001", rule_id="LEN-02", severity="error", key="LEN-02",
                    params={}, evidence="x", suggestion="x"),
            Finding(block_id=None, rule_id="FACT-04", severity="warn", key="FACT-04",
                    params={"n": 1}, segment_ids=["s0003", "s0004"]),
        ],
    )  # fmt: skip
    judge = JudgeReport(
        draft_version=1, model="m",
        unsupported=[Unsupported(block_id="b002", note="not in the source")],
    )  # fmt: skip
    blocks, document = block_issues(draft(), rules, judge)
    assert [i.rule_id for i in blocks["b001"]] == ["LEN-02", "GRAM-05"]  # errors first
    assert blocks["b001"][1].applicable and not blocks["b001"][0].applicable  # x == x
    assert [(i.source, i.rule_id, i.text_key) for i in blocks["b002"]] == [
        ("judge", "SEM-06", "issue.unsupported")
    ]
    assert [i.ref for i in document] == ["s0003-s0004"]
    assert severity_counts([*blocks["b001"], *blocks["b002"], *document]) == {
        "error": 2, "warn": 2,
    }  # fmt: skip
    assert fact_counts([]) == {
        "present": 0, "missing": 0, "distorted": 0, "doubted": 0, "unchecked": 0, "total": 0,
    }  # fmt: skip


def test_the_reviewer_decides_blocks_and_glossary_entries() -> None:
    d = draft()
    assert review_items(d) == 3
    review = ReviewState(
        draft_version=1,
        decisions=[
            Decision(block_id="b001", decision="approved"),
            Decision(block_id="g01", decision="rejected"),
            Decision(block_id="b999", decision="approved"),  # not of this draft
        ],
    )
    assert decided_count(d, review) == 2 and decided_count(d, None) == 0


def test_the_module_imports_no_web_module() -> None:
    code = (
        "import sys, leichtfacile.review, leichtfacile.lifecycle; "
        "print(sorted(m for m in sys.modules if m.startswith('leichtfacile.web')))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"
