"""Fetch the reference pairs of data/pairs/manifest.jsonl into cache/pairs/ in data.dir.

Same as `python -m leichtfacile eval fetch`; extra arguments are passed on, for example
`uv run python scripts/fetch_pairs.py --ids zh-premium-reduction-de --refresh`.
The texts are cached locally only: the publishers do not allow reproduction
(docs/sources.md §4), so they never go into the repository.
"""

from __future__ import annotations

import sys

from leichtfacile.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["eval", "fetch", *sys.argv[1:]]))
