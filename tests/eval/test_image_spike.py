"""The image input spike (eval/image_spike.py), without a key: the pages of the committed
scans, the scaling, the strips, the measures, and the runs against the fake endpoint."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

from leichtfacile.eval.image_spike import (
    INK,
    STRIP_AREA,
    came_back_as,
    capture_pages,
    captures,
    character_error_rate,
    ink_box,
    levenshtein,
    page_images,
    page_parts,
    render_spike,
    run_spike,
    scaled,
    strip_boxes,
    value_recall,
)
from leichtfacile.llm.client import LLMClient
from tests.conftest import chat_response, make_settings

PRINT = Path("data/examples/print")


def test_the_committed_scans_pair_with_their_printed_text() -> None:
    found = {c.name: c for c in captures(PRINT)}
    assert set(found) == {"bourse-etudes-decision_scan", "steuermahnung-brief_scan"}
    assert found["steuermahnung-brief_scan"].reference == PRINT / "steuermahnung-brief.txt"
    assert [p.name for p in found["bourse-etudes-decision_scan"].files] == [
        "bourse-etudes-decision_scan.pdf"
    ]


def test_the_scan_pages_come_out_as_their_jpegs_unchanged() -> None:
    pages = page_images((PRINT / "scans" / "bourse-etudes-decision_scan.pdf").read_bytes())
    assert len(pages) == 2
    for raw in pages:
        assert raw[:3] == b"\xff\xd8\xff"  # JPEG, not re-encoded
        with Image.open(io.BytesIO(raw)) as image:
            assert image.size == (2480, 3507)
    (page,) = capture_pages(captures(PRINT)[1])
    assert len(page) > 500_000


def test_scaling_keeps_the_aspect_ratio_and_the_long_side_limit() -> None:
    raw = page_images((PRINT / "scans" / "steuermahnung-brief_scan.pdf").read_bytes())[0]
    sent, size = scaled(raw, 1600)
    assert size == (1131, 1600)
    with Image.open(io.BytesIO(sent)) as image:
        assert image.size == size and image.format == "JPEG"
    assert len(sent) < len(raw)
    same, size = scaled(sent, 1600)
    assert size == (1131, 1600)


def test_character_error_rate_and_value_recall() -> None:
    assert levenshtein("kitten", "sitting") == 3
    assert character_error_rate("Frist: 31. März 2026", "Frist: 31. März 2026") == 0.0
    assert character_error_rate("abcd", "abzd") == 0.25
    assert character_error_rate("Zwei  Wörter\nhier", "Zwei Wörter hier") == 0.0  # whitespace
    reference = (PRINT / "steuermahnung-brief.txt").read_text(encoding="utf-8")
    recall = value_recall(reference, reference, "de")
    assert recall["recall"] == 1.0 and recall["lost"] == [] and recall["hard_values"] >= 8
    partial = value_recall(reference, "Bitte zahlen Sie bis 31. Oktober 2026.", "de")
    assert partial["found"] < partial["hard_values"]
    assert any(lost.startswith("identifier:") for lost in partial["lost"])  # the IBAN


def test_the_spike_runs_every_page_against_the_endpoint(endpoint, sleeps) -> None:
    de = (PRINT / "steuermahnung-brief.txt").read_text(encoding="utf-8")
    fr = (PRINT / "bourse-etudes-decision.txt").read_text(encoding="utf-8")
    half = len(fr) // 2
    endpoint.push(chat_response(fr[:half]), chat_response(fr[half:]), chat_response(de))
    llm = LLMClient(make_settings(llm_max_retries=0), http_client=endpoint.http_client())
    report = run_spike(llm, PRINT, max_side=800)
    assert [c["capture"] for c in report["captures"]] == [
        "bourse-etudes-decision_scan", "steuermahnung-brief_scan",
    ]  # fmt: skip
    french, german = report["captures"]
    assert french["lang"] == "fr" and german["lang"] == "de"
    assert len(french["pages"]) == 2 and french["pages"][0]["sent_pixels"] == [566, 800]
    assert german["character_error_rate"] == 0.0 and german["recall"] == 1.0
    assert french["character_error_rate"] < 0.01 and french["lost"] == []
    body = endpoint.chat_bodies()[0]
    assert body["temperature"] == 0.0 and not body["model"].endswith("-thinking")
    content = body["messages"][0]["content"]
    assert content[0]["text"].startswith("Recopie le texte")
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    table = render_spike(report)
    assert "| steuermahnung-brief_scan | 1 | 0.0 |" in table
    assert "No hard value lost." in table


def test_strips_cover_the_printed_area_and_cut_only_blank_rows() -> None:
    raw = page_images((PRINT / "scans" / "steuermahnung-brief_scan.pdf").read_bytes())[0]
    with Image.open(io.BytesIO(raw)) as picture:
        page = picture.convert("RGB")
    box = ink_box(page)
    assert 250 < box[0] < 320 and 150 < box[1] < 250  # the margins; the scanner's edge left out
    assert 2200 < box[2] < 2300 and 3350 < box[3] < 3420
    boxes = strip_boxes(page, box)
    assert 4 <= len(boxes) <= 6
    assert boxes[0][1] == box[1] and boxes[-1][3] == box[3]
    gray = ImageOps.grayscale(page)
    for (left, top, right, bottom), following in zip(boxes, boxes[1:], strict=False):
        assert following[1] == bottom and (left, right) == (box[0], box[2])  # contiguous
        assert (right - left) * (bottom - top) <= STRIP_AREA
        row = gray.crop((left, bottom, right, bottom + 1)).tobytes()
        assert sum(1 for v in row if v < INK) <= 4  # the cut runs through a blank row
    parts = page_parts(raw, strips=True)
    assert [p.label for p in parts] == [f"strip {i}" for i in range(1, len(boxes) + 1)]
    assert all(p.size[0] * p.size[1] <= STRIP_AREA for p in parts)
    assert all(p.data[:3] == bytes([0xFF, 0xD8, 0xFF]) and p.box in boxes for p in parts)
    (whole,) = page_parts(raw, max_side=800)
    assert whole.label == "page" and whole.size == (566, 800) and whole.box is None


def test_came_back_as_names_what_the_transcription_has_in_place_of_a_lost_value() -> None:
    reference = "Konto IBAN CH00 0839 4100 2786 5310 4. Frist: 4. November 2026."
    hypothesis = "Konto IBAN CH00 0839 4100 2756 3510 4. Frist: 4. November 2026."
    recall = value_recall(reference, hypothesis, "de")
    assert recall["lost"] == ["identifier: CH0008394100278653104"]
    back = came_back_as(reference, hypothesis, "de", recall["lost"])
    assert "2756 3510" in back["identifier: CH0008394100278653104"]
    assert came_back_as(reference, "unlesbar", "de", recall["lost"]) == {
        "identifier: CH0008394100278653104": "(not aligned)"
    }


def test_the_spike_in_strips_joins_the_parts_in_order(endpoint, sleeps) -> None:
    de = (PRINT / "steuermahnung-brief.txt").read_text(encoding="utf-8")
    raw = page_images((PRINT / "scans" / "steuermahnung-brief_scan.pdf").read_bytes())[0]
    count = len(page_parts(raw, strips=True))
    lines = de.splitlines(keepends=True)
    step = -(-len(lines) // count)
    chunks = ["".join(lines[i : i + step]) for i in range(0, len(lines), step)]
    assert len(chunks) == count
    endpoint.push(*(chat_response(chunk) for chunk in chunks))
    llm = LLMClient(make_settings(llm_max_retries=0), http_client=endpoint.http_client())
    report = run_spike(llm, PRINT, strips=True, names=["steuermahnung-brief_scan"])
    (german,) = report["captures"]
    assert [p["part"] for p in german["pages"]] == [f"strip {i}" for i in range(1, count + 1)]
    assert all(p["sent_pixels"][0] * p["sent_pixels"][1] <= STRIP_AREA for p in german["pages"])
    assert german["pages"][0]["box"][1] < german["pages"][1]["box"][1]
    assert german["character_error_rate"] == 0.0 and german["lost"] == []
    table = render_spike(report)
    assert f"| steuermahnung-brief_scan | {count} | 0.0 |" in table
    assert "strips at the scan's resolution" in table and "No hard value lost." in table
