"""README.md exists twice, in the repository root and in track_2b/ (AGENTS.md): the same
text, only the relative link targets differ, each written from its own file's folder. The
technical report and its PDF exist only in track_2b/ (owner, 11 October 2026)."""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = "README.md"
PDF = ROOT / "track_2b" / "RoestigrabenBridgers_Report.pdf"
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


def test_both_readme_copies_have_the_same_text() -> None:
    root, track = (from_root(folder / README).splitlines() for folder in (ROOT, ROOT / "track_2b"))
    assert root == track


def test_every_relative_link_target_exists() -> None:
    missing = [
        f"{path.relative_to(ROOT).as_posix()}: {m.group(2)}"
        for path in (
            ROOT / README,
            ROOT / "track_2b" / README,
            ROOT / "track_2b/technical_report.md",
        )
        for m in LINK.finditer(path.read_text(encoding="utf-8"))
        if not NOT_RELATIVE.match(m.group(2))
        and not (path.parent / m.group(2).partition("#")[0]).exists()
    ]
    assert missing == []


def test_the_report_and_its_pdf_are_in_track_2b_only() -> None:
    assert (ROOT / "track_2b/technical_report.md").exists() and PDF.exists()
    assert not (ROOT / "technical_report.md").exists()
    assert not (ROOT / PDF.name).exists()


def test_the_report_pdf_links_to_no_local_file() -> None:
    """Printed without absolute links, the browser writes each relative link as a path on
    the machine that printed it (submission.md §5)."""
    links = re.findall(rb"/URI\s*\(([^)]*)\)", PDF.read_bytes())
    assert links and not [u for u in links if u.startswith(b"file:")]
