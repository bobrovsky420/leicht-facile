"""The image input spike (eval/image_spike.py), without a key: the pages of the committed
scans, the scaling, the two measures, and the run against the fake endpoint."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from leichtfacile.eval.image_spike import (
    capture_pages,
    captures,
    character_error_rate,
    levenshtein,
    page_images,
    render_spike,
    run_spike,
    scaled,
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
    assert content[0]["text"].startswith("Recopiez le texte")
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    table = render_spike(report)
    assert "| steuermahnung-brief_scan | 1 | 0.0 |" in table
    assert "No hard value lost." in table
