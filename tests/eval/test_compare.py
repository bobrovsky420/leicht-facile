"""The prices by model name (eval/prices.toml) and `eval compare` (eval/compare.py): the
runs a document declares, the tables from their results folders, the markers kept."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leichtfacile.eval import compare, score


def test_prices_follow_the_model_name() -> None:
    assert score.price("swiss-ai/Apertus-v1.5-70B") == (0.82, 2.92)
    assert score.price("swiss-ai/apertus-v1.5-8b") == (0.10, 0.20)
    assert score.price("swiss-ai/Apertus-8B-Instruct-2509") == (0.10, 0.20)
    assert score.price("openai/gpt-oss-120b:groq") == (0.15, 0.75)
    assert score.price("openai/gpt-oss-20b") == (0.10, 0.50)
    assert score.price("gpt-5.4-nano") == (0.20, 1.25)  # before the "gpt-5.4" entry
    assert score.price("gpt-5.4") == (2.50, 15.00)
    assert score.price("gpt-5.6-luna") == (0.20, 1.20) and score.price("gpt-5-nano") == (0.05, 0.40)
    assert score.price("claude-haiku-5-5") == (0.10, 0.50)
    for own in ("apertus-v1.5-8b-q4-llamacpp", "qwen3.5:9b", "local-model", "unknown"):
        assert score.price(own) is None
    for entry in score.PRICES:  # a match list, and both prices or none
        assert entry.match and (entry.input is None) == (entry.output is None)


def _row(**values) -> str:
    row = {"setup": "P2", "role": "eval", "lang": "de", "status": "needs_review", **values}
    return json.dumps(row)


DOC = """# Comparison

<!-- runs:start -->
```toml
[[run]]
label = "Model M"
results = "eval/results-x"
file = "P2_m.jsonl"
date = 2026-10-25
writer = "m"
notes = "a test"
```
<!-- runs:end -->

<!-- tables:start -->
old tables
<!-- tables:end -->

Tail.
"""


def test_compare_fills_the_tables_from_the_declared_runs(tmp_path) -> None:
    results = tmp_path / "eval" / "results-x"
    results.mkdir(parents=True)
    (results / "P2_m.jsonl").write_text(
        "\n".join([
            _row(pair_id="a", hard_fact_recall=1.0, fact_coverage=1.0, errors_per_100=2.0,
                 usd_per_page=0.01, hard_facts_total=4, judge_distorted=0.0,
                 by_family_per_100={"LEN": 2.0}, mediopunkt_per_100=5.0),
            _row(pair_id="b", hard_fact_recall=0.5, fact_coverage=0.9, errors_per_100=4.0,
                 usd_per_page=0.03, hard_facts_total=2),
            _row(pair_id="c", status="failed", error="boom"),
            _row(pair_id="d", role="dev", hard_fact_recall=0.0),  # another split: not counted
        ]) + "\n",
        encoding="utf-8",
    )  # fmt: skip
    (results / "REF.jsonl").write_text(
        _row(setup="REF", pair_id="a", hard_fact_recall=0.5, errors_per_100=3.0)
        + "\n"
        + _row(setup="SOURCE", pair_id="a", hard_fact_recall=1.0, errors_per_100=30.0)
        + "\n",
        encoding="utf-8",
    )
    doc = tmp_path / "docs" / "model-comparison.md"
    doc.parent.mkdir()
    doc.write_text(DOC, encoding="utf-8")

    assert compare.update(doc, root=tmp_path) == 1
    text = doc.read_text(encoding="utf-8")
    assert "old tables" not in text and text.endswith("<!-- tables:end -->\n\nTail.\n")
    assert text.count("<!-- runs:start -->") == 1 and "[[run]]" in text  # the block stays
    facts = "| Model M | 2026-10-25 | - | m | - | - | - | - | a test | `eval/results-x/P2_m.jsonl` |"  # fmt: skip  # noqa: E501
    assert facts in text
    assert "| Original (standard language) | 1 | - | 100 % |" in text
    assert "| Official easy-language version | 1 | - | 50 % |" in text
    # two pairs in the means (the failed one and the dev one are not), USD 0.02 per page
    assert "| Model M | 2 | 95 % | 75 % | - | 3.0 |" in text and "| 0.0200 |" in text
    assert "| Model M | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 5.0 | 0.0 | 0.0 |" in text  # families
    assert "| Model M | 1 | 100 % | 100 % | 0 % |" in text  # the fact-rich subset: pair a
    assert "Failed pairs (not in the means): Model M: c." in text

    doc.write_text(DOC.replace("P2_m.jsonl", "gone.jsonl"), encoding="utf-8")
    with pytest.raises(compare.CompareError, match="no rows at"):
        compare.update(doc, root=tmp_path)
    doc.write_text(DOC.replace("<!-- runs:start -->", ""), encoding="utf-8")
    with pytest.raises(compare.CompareError, match="no <!-- runs:start -->"):
        compare.update(doc, root=tmp_path)


def test_the_comparison_document_declares_runs_that_parse() -> None:
    root = Path(__file__).resolve().parents[2]
    runs = compare.read_runs((root / "docs" / "model-comparison.md").read_text(encoding="utf-8"))
    assert len(runs) >= 5 and all(run.facts.get("date") for run in runs)
    assert all(run.file.startswith("P2_") and run.file.endswith(".jsonl") for run in runs)
