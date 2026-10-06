"""Day-1 checks against the live endpoint (docs/architecture.md §12, PLAN §5).

Usage: uv run python scripts/day1_checks.py [--runs 20] [--doc PATH]
Reads the endpoint from .env, prints a JSON report and writes it to
eval/results/day1_checks.json. Check 6 (P0 baseline on German pairs) runs separately:
uv run python -m leichtfacile eval run --condition P0 --limit 10
"""

from __future__ import annotations

import argparse
from pathlib import Path

from leichtfacile.config import get_settings
from leichtfacile.eval.day1 import run_all, to_json
from leichtfacile.ingest import ingest_file
from leichtfacile.llm.client import LLMClient

DEFAULT_DOC = Path("data/examples/sources/praemienverbilligung-brief.txt")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=20, help="JSON reliability calls per mode")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC, help="document for check 3")
    parser.add_argument("--out", type=Path, default=Path("eval/results/day1_checks.json"))
    args = parser.parse_args()

    settings = get_settings()
    llm = LLMClient(settings)
    report = run_all(llm, ingest_file(args.doc, lang="de"), json_runs=args.runs)
    text = to_json(report)
    print(text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n", encoding="utf-8")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
