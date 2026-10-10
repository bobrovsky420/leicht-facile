"""README.md exists twice, in the repository root and in track_2b/ (AGENTS.md): the same
text, only the relative link targets differ, each written from its own file's folder."""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COPIES = [ROOT / "README.md", ROOT / "track_2b" / "README.md"]
LINK = re.compile(r"(\]\()([^)\s]+)(\))")  # inline links and images
NOT_RELATIVE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:|#|/")  # URL, anchor, from the root


def from_root(readme: Path) -> str:
    """The README with every relative link target written from the repository root."""
    folder = readme.parent.relative_to(ROOT).as_posix()

    def sub(m: re.Match[str]) -> str:
        target = m.group(2)
        if NOT_RELATIVE.match(target):
            return m.group(0)
        path, sep, anchor = target.partition("#")
        full = posixpath.normpath(posixpath.join(folder, path))
        if path.endswith("/"):
            full += "/"
        return f"{m.group(1)}{full}{sep}{anchor}{m.group(3)}"

    return LINK.sub(sub, readme.read_text(encoding="utf-8"))


def test_both_copies_have_the_same_text() -> None:
    root, track = (from_root(readme).splitlines() for readme in COPIES)
    assert root == track


def test_every_relative_link_target_exists() -> None:
    missing = [
        f"{readme.relative_to(ROOT).as_posix()}: {m.group(2)}"
        for readme in COPIES
        for m in LINK.finditer(readme.read_text(encoding="utf-8"))
        if not NOT_RELATIVE.match(m.group(2))
        and not (readme.parent / m.group(2).partition("#")[0]).exists()
    ]
    assert missing == []
