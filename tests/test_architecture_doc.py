"""docs/architecture.md describes the current version, not its history (the map at its
top, "What holds today"): a sentence that dates a behaviour ("since 7 October 2026",
"until ...", "before ...", "after ...") tells history, which belongs in CHANGELOG.md or
in a record under docs/history/. The phrases still in the document are listed with
their counts in tests/fixtures/architecture_dated_wording.txt: a new one fails here,
and one taken out is taken out of the list too, so the list only shrinks."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "architecture.md"
BASELINE = ROOT / "tests" / "fixtures" / "architecture_dated_wording.txt"
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATED = re.compile(
    rf"\b(?:since|until|before|after)\s+\d{{1,2}}\s+(?:{MONTHS})\s+20\d\d\b", re.IGNORECASE
)


def dated_phrases(text: str) -> Counter[str]:
    """Every dated phrase of `text`, in lowercase and on one line, with its count."""
    return Counter(" ".join(m.group(0).lower().split()) for m in DATED.finditer(text))


def test_the_design_document_tells_no_new_history() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert text.startswith("# Leicht·Facile - design and architecture\n\n## What holds today\n")
    found = dated_phrases(text)
    listed: Counter[str] = Counter()
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            count, phrase = line.split(" ", 1)
            listed[phrase] = int(count)
    new = {p: n for p, n in found.items() if n > listed[p]}
    assert not new, f"history in docs/architecture.md; say what holds now instead: {new}"
    gone = {p: listed[p] - found[p] for p in listed if found[p] < listed[p]}
    assert not gone, f"fewer than listed; lower the counts in {BASELINE.name}: {gone}"
