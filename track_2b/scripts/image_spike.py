"""The image input spike against the live endpoint (PLAN.md WP12, decision D-N).

Usage: uv run python track_2b/scripts/image_spike.py [--scans track_2b/data/examples/print]
                                                     [--max-side 1600] [--strips] [--model NAME]
                                                     [--only CAPTURE ...]
Reads the endpoint from .env or the shell, sends every page of every capture in
`<scans>/scans/` to the model and compares the transcription with the printed text.
With `--strips` each page goes in horizontal strips at the scan's own resolution
instead of whole and scaled (the server keeps at most 1400 x 1400 pixels of an image).
Prints the table and writes the full report (transcriptions included) to
track_2b/eval/results/image_spike.json (`image_spike_strips.json` with `--strips`), git-ignored.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from leichtfacile.config import get_settings
from leichtfacile.eval.image_spike import MAX_SIDE, render_spike, run_spike, to_json
from leichtfacile.llm.client import LLMClient


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scans", type=Path, default=Path("track_2b/data/examples/print"))
    parser.add_argument("--max-side", type=int, default=MAX_SIDE, help="pixels, long side")
    parser.add_argument("--strips", action="store_true", help="strips at the scan's resolution")
    parser.add_argument("--model", help="transcription model (default: LLM_NAME)")
    parser.add_argument("--only", nargs="*", help="only these captures (file name stems)")
    parser.add_argument(
        "--out", type=Path, help="default: track_2b/eval/results/image_spike[_strips].json"
    )
    args = parser.parse_args()
    suffix = "_strips" if args.strips else ""
    out = args.out or Path("track_2b/eval/results") / f"image_spike{suffix}.json"

    llm = LLMClient(get_settings())
    report = run_spike(
        llm,
        args.scans,
        max_side=args.max_side,
        model=args.model,
        names=args.only,
        strips=args.strips,
    )
    print(render_spike(report))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_json(report) + "\n", encoding="utf-8")
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
