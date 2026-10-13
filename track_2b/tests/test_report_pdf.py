"""The report's PDF renderer (track_2b/scripts/report_pdf.py) without a browser, and the
printed PDF itself: at most six pages before the references, the hackathon's limit, with
its document information (submission.md §5)."""

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
        ("https://youtu.be/5el7q6Xtgik", "https://youtu.be/5el7q6Xtgik"),
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


def test_the_team_shows_one_member_per_line_and_its_name_by_the_wordmark(report) -> None:
    lines = [plain(line) for line in str(report.meta["Team"]).split("<br>")]
    assert lines == [
        "Alexander Bobrovsky (bobrovsky@seznam.cz)",
        "Ivan Kuzmych (i.kuzmych@hotmail.com)",
    ]
    assert "by Team Röstigraben Bridgers" in report_pdf.page_html(report)


def test_the_foot_table_moves_down_its_subsection_only() -> None:
    """The renderer tries the target-architecture table further down, never past the end
    of its subsection (report §2, "Target architecture")."""
    text = REPORT.read_text(encoding="utf-8")
    reach, heading, header = report_pdf.parse(text).foot
    assert (heading, header) == ("Target architecture", "Architecture How it is met Tested on")
    for shift in (*range(reach + 1), reach + 3):
        body = str(report_pdf.parse(text, shift=shift).body)
        table, after = body.index("How it is met"), body.index("Apart from that endpoint")
        assert body.index("Target architecture") < table < body.index("Use of Apertus")
        assert (table < after) == (shift == 0)
        # the page ends with the table
        end = body.index("</table>", table)
        assert body[end:].startswith('</table>\n<div class="balance new-page"></div>')


def test_the_summary_starts_its_second_column_with_the_deployment(report) -> None:
    assert '<p class="new-column">One container plus an' in str(report.body)


def test_the_data_chapter_runs_across_the_page(report) -> None:
    body = str(report.body)
    assert body.count('<section class="numbered single">') == 1
    assert body.index('<section class="numbered single">') < body.index("Dev pairs serve")


def test_the_results_table_leaves_its_introduction_in_the_columns(report) -> None:
    body = str(report.body)
    assert '<div class="spread">\n<p>Results on the' not in body
    assert "<p>Results on the" in body


def test_the_hardware_tables_model_column_does_not_wrap(report) -> None:
    assert str(report.body).count('<td class="nobr">8B in ') == 2


def test_a_second_actor_in_the_done_by_column_gets_its_own_mark(report) -> None:
    body = str(report.body)
    assert '<td class="who human">Human <span class="who code"></span>Code</td>' in body
    assert body.count('<span class="who') == 1


def test_a_title_found_alone_starts_a_new_page() -> None:
    text = REPORT.read_text(encoding="utf-8")
    body = str(report_pdf.parse(text, breaks=frozenset({"8. Next steps", "4. Data"})).body)
    assert '<h2 class="new-page"><span class="num">8.</span> Next steps</h2>' in body
    assert '<div class="spread new-page">\n<h2><span class="num">4.</span> Data' in body


def test_no_chapter_title_stands_alone_at_the_foot_of_a_page() -> None:
    assert report_pdf.stranded_titles(PDF.read_bytes()) == set()


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
