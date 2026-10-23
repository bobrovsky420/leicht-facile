"""`eval numbers`: the headline means and the headline case, on synthetic rows."""

from __future__ import annotations

import json
from pathlib import Path

from leichtfacile.eval.numbers import (
    compare,
    comparisons,
    exact_interval,
    headline,
    pooled,
    render_numbers,
    sentence,
)
from leichtfacile.eval.report import load_rows


def _write(folder: Path, name: str, rows: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _rows(setup: str, writer: str, values: list[dict], status: str = "needs_review") -> list[dict]:
    return [
        {"setup": setup, "writer": writer, "pair_id": f"p{i}", "role": "eval", "lang": "de",
         "status": status, **v}
        for i, v in enumerate(values, 1)
    ]  # fmt: skip


P2 = {
    "fact_coverage": 0.84,
    "hard_fact_recall": 0.80,
    "silent_loss_share": 0.0,
    "errors_per_100": 4.3,
    "invented_values_per_100": 0.1,
    "unsupported_per_100": 3.0,
}
ZH = {"fact_coverage": 0.91, "hard_fact_recall": 0.95, "silent_loss_share": 0.23,
      "errors_per_100": 15.4, "invented_values_per_100": 0.0}  # fmt: skip


def test_case_b_when_p2_wins_on_errors_but_trails_on_coverage(tmp_path: Path) -> None:
    _write(tmp_path, "P2_8b.jsonl", _rows("P2", "8B", [P2] * 4))
    _write(tmp_path, "P2_70b.jsonl", _rows("P2", "70B", [{**P2, "errors_per_100": 1.0}] * 2))
    _write(tmp_path, "P0-ZH-complete_8b.jsonl", _rows("P0-ZH-complete", "8B", [ZH] * 4))
    _write(tmp_path, "REF.jsonl", _rows("REF", "-", [{"hard_fact_recall": 0.6}] * 4))
    h = headline(tmp_path)
    assert h.pairs == 4 and h.case == "B" and h.failed_share == 0.0
    p2 = h.get("P2")
    assert p2.writer == "8B" and p2.pairs == 4 and p2.errors == 4.3  # the largest group
    assert "fewer" in h.reasons[1] and "+7 points" in h.reasons[2]
    text = render_numbers(tmp_path)
    assert "| P2 | 8B | 4 | 84 % | 80 % | 0 % | 4.3 | 0.1 | 3.0 |" in text
    assert "Headline case B" in text
    assert "4.3 against 15.4 rule errors per 100 blocks" in sentence(h)
    assert "loses 23 % of the hard facts" in sentence(h)


def test_case_a_a2_c_and_d(tmp_path: Path) -> None:
    a = tmp_path / "a"
    _write(a, "P2.jsonl", _rows("P2", "8B", [{**P2, "fact_coverage": 0.89}] * 3))
    _write(
        a, "ZH.jsonl", _rows("P0-ZH-complete", "8B", [{**ZH, "invented_values_per_100": 0.5}] * 3)
    )
    ha = headline(a)
    assert ha.case == "A" and "0.4 fewer invented values" in sentence(ha)

    c = tmp_path / "c"
    _write(c, "P2.jsonl", _rows("P2", "8B", [{**P2, "errors_per_100": 20.0}] * 3))
    _write(c, "ZH.jsonl", _rows("P0-ZH-complete", "8B", [ZH] * 3))
    hc = headline(c)
    assert hc.case == "C" and "nobody saw" in sentence(hc)

    a2 = tmp_path / "a2"
    _write(a2, "P2.jsonl", _rows("P2", "8B", [{**P2, "fact_coverage": 1.0}] * 3))
    _write(a2, "ZH.jsonl", _rows("P0-ZH-complete", "8B", [ZH] * 3))
    h2 = headline(a2)
    assert h2.case == "A2"
    assert "finds 100 percent of the must-keep facts against 91" in sentence(h2)
    assert "loses none without a trace against 23 percent" in sentence(h2)
    assert "4.3 against 15.4 rule errors" in sentence(h2)
    assert "rare on both sides (0.1 against 0.0)" in sentence(h2)

    d = tmp_path / "d"
    rows = _rows("P2", "8B", [P2] * 2) + _rows("P2", "8B", [{}] * 2, status="failed")
    for i, r in enumerate(rows[2:], 3):
        r["pair_id"] = f"p{i}"
    _write(d, "P2.jsonl", rows)
    _write(d, "ZH.jsonl", _rows("P0-ZH-complete", "8B", [ZH] * 4))
    hd = headline(d)
    assert hd.case == "D" and hd.failed_share == 0.5
    assert "failure rate (50 %)" in sentence(hd)


def test_numbers_without_rows_say_so(tmp_path: Path) -> None:
    h = headline(tmp_path)
    assert h.pairs == 0 and h.case == "-" and "nothing to compare" in h.reasons[0]


def test_exact_interval_matches_clopper_pearson() -> None:
    low, high = exact_interval(0, 200)
    assert low == 0.0 and round(high, 4) == 0.0183
    low, high = exact_interval(24, 200)
    # the values of scipy.stats.beta.ppf, the textbook form of the interval
    assert (round(low, 5), round(high, 5)) == (0.07842, 0.17327)
    assert exact_interval(5, 5)[1] == 1.0


def test_paired_comparison_counts_pairs_and_brackets_the_mean(tmp_path: Path) -> None:
    p2 = [{**P2, "fact_coverage": c, "errors_per_100": e, "hard_facts_total": 10,
           "silent_losses": 0, "blocks": 20, "invented_values": 0}
          for c, e in ((1.0, 2.0), (1.0, 5.0), (0.9, 3.0), (0.8, 9.0))]  # fmt: skip
    zh = [{**ZH, "silent_loss_share": None, "fact_coverage": c, "errors_per_100": e,
           "hard_fact_recall": 0.7, "hard_facts_total": 10, "hard_facts_found": 7, "blocks": 30}
          for c, e in ((0.8, 10.0), (1.0, 12.0), (0.7, 1.0), (0.9, 15.0))]  # fmt: skip
    _write(tmp_path, "P2.jsonl", _rows("P2", "8B", p2))
    _write(tmp_path, "ZH.jsonl", _rows("P0-ZH-complete", "8B", zh))
    rows = load_rows(tmp_path)
    c = compare(rows, ("P2", None), ("P0-ZH-complete", None))
    assert c.a == "P2 (8B)" and c.b == "P0-ZH-complete (8B)" and c.pairs == 4
    cov = next(d for d in c.diffs if d.label.startswith("Fact coverage"))
    assert round(cov.diff, 1) == 7.5 and (cov.better, cov.worse, cov.tied) == (2, 1, 1)
    assert cov.low <= cov.diff <= cov.high
    errors = next(d for d in c.diffs if d.label.startswith("Rule errors"))
    # fewer errors is better: three pairs better, one worse
    assert (errors.better, errors.worse, errors.tied) == (3, 1, 0)
    # a baseline without the key: its silent losses follow from the hard facts kept
    silent = next(d for d in c.diffs if d.label.startswith("Silent"))
    assert round(silent.mean_b, 6) == 30.0 and silent.better == 4
    assert compare(rows, ("P2", None), ("P0-ZH-complete", None)) == c  # seeded
    text = render_numbers(tmp_path)
    assert "Paired, P2 (8B) against P0-ZH-complete (8B): 4 pairs" in text
    assert "- P2 (8B): 0 of 40 hard values lost without a trace (0.0 %, 0.0 to 8.8 %)" in text
    assert "- P0-ZH-complete (8B): 12 of 40 hard values" in text
    assert pooled(rows, "P1") is None


def test_a_second_p2_writer_is_compared_with_the_headline_writer(tmp_path: Path) -> None:
    _write(tmp_path, "P2_8b.jsonl", _rows("P2", "8B", [P2] * 3))
    _write(tmp_path, "P2_70b.jsonl", _rows("P2", "70B", [{**P2, "errors_per_100": 1.0}] * 2))
    cs = comparisons(load_rows(tmp_path))
    assert len(cs) == 1 and cs[0].a == "P2 (70B)" and cs[0].b == "P2 (8B)" and cs[0].pairs == 2
    errors = next(d for d in cs[0].diffs if d.label.startswith("Rule errors"))
    assert round(errors.diff, 6) == round(errors.low, 6) == round(errors.high, 6) == -3.3
