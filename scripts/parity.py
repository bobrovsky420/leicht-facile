"""Swiss parity: the checker's findings and the hard values on the cached reference
pages, as counts, against a stored baseline.

The German, French and Italian output must stay as it is while the varieties for
Germany and Austria are built (docs/architecture.md section 8). This script runs the
checker over every cached page of the Swiss pairs (both sides, both levels) and counts
the findings per rule and severity, the document metrics and the hard values per kind;
`write` stores the counts in tests/fixtures/parity/swiss.json, `check` diffs the current
code against them. Counts only: the pages may not be reproduced, and the baseline is
committed. It needs the fetched pages (`uv run leichtfacile eval fetch`), so it runs on a
developer's machine, not in CI:

    uv run python scripts/parity.py write
    uv run python scripts/parity.py check
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from leichtfacile.eval.dataset import MANIFEST, Pair, cached_path
from leichtfacile.rules import check_draft, source_as_draft
from leichtfacile.rules.values import hard_values
from leichtfacile.schemas import SourceDocument

BASELINE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "parity" / "swiss.json"
METRICS = ("blocks", "words", "readability", "pct_passive", "pct_genitive", "pct_subordinate")


def swiss_pairs() -> list[Pair]:
    """The pairs of the Swiss varieties: every row without a region, or with CH."""
    pairs = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("region", "CH") == "CH":
            pairs.append(Pair.model_validate(row))
    return pairs


def measure(doc: SourceDocument) -> dict:
    out: dict = {"lang": doc.lang, "segments": len(doc.segments)}
    values = Counter(kind for kind, _ in hard_values(doc.text(), doc.lang))
    out["values"] = dict(sorted(values.items()))
    for level in ("A2", "B1"):
        checked = check_draft(source_as_draft(doc, level))
        findings = Counter(f"{f.rule_id} {f.severity}" for f in checked.findings)
        metrics = {
            name: round(value, 2) if isinstance(value, float) else value
            for name in METRICS
            if (value := getattr(checked.metrics, name)) is not None
        }
        out[level] = {"findings": dict(sorted(findings.items())), "metrics": metrics}
    return out


def collect() -> dict:
    result: dict = {}
    started = time.monotonic()
    for pair in swiss_pairs():
        docs = {}
        for side in ("standard", "easy"):
            path = cached_path(pair.id, side)
            if path.exists():
                docs[side] = SourceDocument.model_validate_json(path.read_text(encoding="utf-8"))
        if not docs:
            continue
        entry = {side: measure(doc) for side, doc in docs.items()}
        if len(docs) == 2:
            standard = hard_values(docs["standard"].text(), docs["standard"].lang)
            easy = hard_values(docs["easy"].text(), docs["easy"].lang)
            entry["kept"] = len(standard & easy)
        result[pair.id] = entry
    print(f"{len(result)} pairs measured in {time.monotonic() - started:.0f} s", file=sys.stderr)
    return result


def differences(expected: dict, actual: dict, prefix: str = "") -> list[str]:
    out = []
    for key in sorted(set(expected) | set(actual)):
        path = f"{prefix}{key}"
        if key not in expected:
            out.append(f"new: {path}")
        elif key not in actual:
            out.append(f"gone: {path}")
        elif isinstance(expected[key], dict) and isinstance(actual[key], dict):
            out += differences(expected[key], actual[key], f"{path} / ")
        elif expected[key] != actual[key]:
            out.append(f"{path}: {expected[key]} -> {actual[key]}")
    return out


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "check"
    if command not in ("write", "check"):
        print(__doc__, file=sys.stderr)
        return 2
    actual = collect()
    if command == "write":
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(actual, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"baseline written: {BASELINE}")
        return 0
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    changes = differences(expected, actual)
    if not changes:
        print(f"parity holds: {len(actual)} pairs as in {BASELINE.name}")
        return 0
    print(f"{len(changes)} differences from {BASELINE.name}:")
    for line in changes:
        print(f"  {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
