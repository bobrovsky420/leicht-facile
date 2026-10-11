"""`eval numbers`: the headline means and the D-M case of PLAN.md, on synthetic rows."""

from __future__ import annotations

import json
from pathlib import Path

from leichtfacile.eval.numbers import headline, render_numbers, sentence


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
    assert "Case B of PLAN.md" in text
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
