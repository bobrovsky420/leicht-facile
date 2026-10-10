"""README.md, technical_report.md and the report PDF exist twice, in the repository root
and in track_2b/ (AGENTS.md). The Markdown copies have the same text, only the relative
link targets differ, each written from its own file's folder; the PDF copies are the
same file (its links are absolute)."""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEXTS = ["README.md", "technical_report.md"]
PDF = "RoestigrabenBridgers_Report.pdf"
LINK = re.compile(r"(\]\()([^)\s]+)(\))")  # inline links and images
NOT_RELATIVE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:|#|/")  # URL, anchor, from the root


def from_root(path: Path) -> str:
    """The file with every relative link target written from the repository root."""
    folder = path.parent.relative_to(ROOT).as_posix()

    def sub(m: re.Match[str]) -> str:
        target = m.group(2)
        if NOT_RELATIVE.match(target):
            return m.group(0)
        link, sep, anchor = target.partition("#")
        full = posixpath.normpath(posixpath.join(folder, link))
        if link.endswith("/"):
            full += "/"
        return f"{m.group(1)}{full}{sep}{anchor}{m.group(3)}"

    return LINK.sub(sub, path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", TEXTS)
def test_both_copies_have_the_same_text(name: str) -> None:
    root, track = (from_root(folder / name).splitlines() for folder in (ROOT, ROOT / "track_2b"))
    assert root == track


@pytest.mark.parametrize("name", TEXTS)
def test_every_relative_link_target_exists(name: str) -> None:
    missing = [
        f"{path.relative_to(ROOT).as_posix()}: {m.group(2)}"
        for path in (ROOT / name, ROOT / "track_2b" / name)
        for m in LINK.finditer(path.read_text(encoding="utf-8"))
        if not NOT_RELATIVE.match(m.group(2))
        and not (path.parent / m.group(2).partition("#")[0]).exists()
    ]
    assert missing == []


def test_both_report_pdfs_are_the_same_file() -> None:
    assert (ROOT / PDF).read_bytes() == (ROOT / "track_2b" / PDF).read_bytes()


def test_the_report_pdf_links_to_no_local_file() -> None:
    """Printed without the base URL, the browser writes each relative link as a path on
    the machine that printed it (track_2b/docs/submission.md §5)."""
    links = re.findall(rb"/URI\s*\(([^)]*)\)", (ROOT / PDF).read_bytes())
    assert links and not [u for u in links if u.startswith(b"file:")]
