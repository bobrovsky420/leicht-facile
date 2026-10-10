"""Fetch the reference pairs of track_2b/data/pairs/manifest.jsonl into DATA_DIR/cache/pairs/.

Same as `python -m leichtfacile eval fetch`; extra arguments are passed on, for example
`uv run python track_2b/scripts/fetch_pairs.py --ids zh-premium-reduction-de --refresh`.
The texts are cached locally only: the publishers do not allow reproduction
(track_2b/docs/sources.md §4), so they never go into the repository.
"""

from __future__ import annotations

import sys

from leichtfacile.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["eval", "fetch", *sys.argv[1:]]))
