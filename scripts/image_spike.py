"""The image input spike against the live endpoint (PLAN.md WP12, decision D-N).

Usage: uv run python scripts/image_spike.py [--scans data/examples/print] [--max-side 1600]
                                             [--model NAME] [--only CAPTURE ...]
Reads the endpoint from .env or the shell, sends every page of every capture in
`<scans>/scans/` to the model and compares the transcription with the printed text.
Prints the table and writes the full report (transcriptions included) to
eval/results/image_spike.json, which is git-ignored.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from leichtfacile.config import get_settings
from leichtfacile.eval.image_spike import MAX_SIDE, render_spike, run_spike, to_json
from leichtfacile.llm.client import LLMClient


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scans", type=Path, default=Path("data/examples/print"))
    parser.add_argument("--max-side", type=int, default=MAX_SIDE, help="pixels, long side")
    parser.add_argument("--model", help="transcription model (default: LLM_NAME)")
    parser.add_argument("--only", nargs="*", help="only these captures (file name stems)")
    parser.add_argument("--out", type=Path, default=Path("eval/results/image_spike.json"))
    args = parser.parse_args()

    llm = LLMClient(get_settings())
    report = run_spike(llm, args.scans, max_side=args.max_side, model=args.model, names=args.only)
    print(render_spike(report))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(to_json(report) + "\n", encoding="utf-8")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
