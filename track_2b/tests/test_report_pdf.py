"""The report's PDF renderer (track_2b/scripts/report_pdf.py) without a browser, and the
printed PDF itself: at most six pages before the references, the hackathon's limit, with
its document information (track_2b/docs/submission.md §5)."""

from __future__ import annotations

import importlib.util
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pypdfium2 as pdfium
import pytest

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "track_2b" / "technical_report.md"
PDF = ROOT / "track_2b" / "RoestigrabenBridgers_Report.pdf"
REPO = "https://github.com/bobrovsky420/leicht-facile"

spec = importlib.util.spec_from_file_location("report_pdf", ROOT / "track_2b/scripts/report_pdf.py")
report_pdf = importlib.util.module_from_spec(spec)
sys.modules["report_pdf"] = report_pdf  # the dataclass looks its module up
spec.loader.exec_module(report_pdf)


@pytest.fixture(scope="module")
def report():
    return report_pdf.parse(REPORT.read_text(encoding="utf-8"))


def plain(text: str) -> str:
    """A label as text: no tags, single spaces, straight apostrophes."""
    text = re.sub(r"<br\s*/?>", " ", text)
    return " ".join(re.sub(r"<[^>]+>", "", text).replace("’", "'").split())


@pytest.mark.parametrize(
    ("href", "url"),
    [
        ("docs/architecture.md", f"{REPO}/blob/main/track_2b/docs/architecture.md"),
        (
            "docs/use-cases.md#why-only-apertus",
            f"{REPO}/blob/main/track_2b/docs/use-cases.md#why-only-apertus",
        ),
        ("../LICENSE", f"{REPO}/blob/main/LICENSE"),
        ("eval/hardware/", f"{REPO}/tree/main/track_2b/eval/hardware/"),
        ("https://youtu.be/V_R4AABLriI", "https://youtu.be/V_R4AABLriI"),
    ],
)
def test_a_relative_link_points_to_the_repository_on_github(href: str, url: str) -> None:
    assert report_pdf.absolute(href, REPO, "track_2b") == url


def test_no_relative_link_is_left_on_the_page(report) -> None:
    page = str(report.body) + "".join(str(value) for value in report.meta.values())
    hrefs = re.findall(r'href="([^"]*)"', page)
    assert hrefs and [h for h in hrefs if not re.match(r"https?://|mailto:", h)] == []


def test_every_section_of_the_report_is_on_the_page(report) -> None:
    headings = re.findall(r"^## (?:\d+\. )?(.+)$", REPORT.read_text(encoding="utf-8"), re.MULTILINE)
    shown = [
        plain(h)
        for h in re.findall(r"<h2>(?:<span class=\"num\">\d+\.</span> )?(.*?)</h2>", report.body)
    ]
    assert shown == headings


def test_the_figures_carry_the_labels_of_the_mermaid_diagrams() -> None:
    """The drawings in track_2b/scripts/report/ stand in for the report's Mermaid diagrams;
    a node, group or edge label changed in one must change in the other."""
    diagrams = re.findall(r"```mermaid\n(.*?)```", REPORT.read_text(encoding="utf-8"), re.DOTALL)
    assert len(diagrams) == len(report_pdf.FIGURES)
    for diagram, name in zip(diagrams, report_pdf.FIGURES, strict=True):
        labels = {plain(a or b) for a, b in re.findall(r'\[\(?"([^"]+)"\)?\]|\|([^|]+)\|', diagram)}
        svg = ET.parse(report_pdf.ASSETS / name).getroot()
        texts = {
            plain(" ".join(t.itertext())) for t in svg.iter("{http://www.w3.org/2000/svg}text")
        }
        assert labels and labels <= texts, f"{name} misses {sorted(labels - texts)}"


def test_the_key_figures_come_from_the_results_table(report) -> None:
    rows = [
        [cell.strip().strip("*") for cell in line.strip("|").split("|")]
        for line in REPORT.read_text(encoding="utf-8").splitlines()
        if line.startswith("| ")
    ]
    header = next(row for row in rows if row[:2] == ["Setup", "Fact coverage"])
    ours = next(row for row in rows if row[0] == report_pdf.OURS)
    baseline = next(row for row in rows if row[0] == report_pdf.BASELINE)
    shown = [(f["value"], f["baseline"]) for f in report.key_figures]
    expected = [
        (ours[header.index(column)], baseline[header.index(column)])
        for column, _, _ in report_pdf.KEY_FIGURES
    ]
    assert [
        (v.replace(report_pdf.NBSP, " "), b.replace(report_pdf.NBSP, " ")) for v, b in shown
    ] == expected


def test_the_document_information_replaces_chromiums() -> None:
    fields = {"Title": "Technical report - Leicht·Facile", "Author": "Röstigraben Bridgers"}
    updated = report_pdf.set_info(PDF.read_bytes(), fields)
    meta = pdfium.PdfDocument(updated).get_metadata_dict()
    assert {key: meta[key] for key in fields} == fields
    assert len(pdfium.PdfDocument(updated)) == len(pdfium.PdfDocument(PDF.read_bytes()))


def test_the_report_pdf_has_at_most_six_pages_before_the_references() -> None:
    """The limit leaves the references out (organisers, 11 October 2026)."""
    (pages, _), (counted, _) = report_pdf.measure(PDF.read_bytes())
    assert counted <= report_pdf.MAX_PAGES
    assert counted <= pages


def test_the_report_pdf_was_printed_by_the_renderer(report) -> None:
    meta = pdfium.PdfDocument(PDF.read_bytes()).get_metadata_dict()
    assert meta["Title"] == report.title
    assert meta["Creator"] == "track_2b/scripts/report_pdf.py"
