"""The image input spike (PLAN.md WP12, decision D-N): can the model transcribe a
scanned or photographed letter word for word, with every hard value intact?

Each capture in `track_2b/data/examples/print/scans/` (a scanner's PDF without a text layer,
one JPEG per page, or a phone photo as JPEG or PNG) is paired with the printed text
of its letter (`track_2b/data/examples/print/<letter>.txt`, blocks separated by a blank line,
table cells by a tab) by the file name in front of the first underscore. Every page
goes to the model as an image with a "transcribe word for word" prompt, either whole
(scaled to a long side of `max_side` pixels) or, with `strips`, cut into horizontal
strips at blank rows. The transcription is compared with the printed text: the
character error rate (Levenshtein distance over the whitespace-normalised text,
divided by its length) and the share of the printed text's hard values (dates,
amounts, phone numbers, IBAN and AHV numbers, periods, ...) found in the
transcription, with the lost values named and what the transcription has in their
place. The go/no-go rule of the plan: stop when hard values are lost.

Why strips: Apertus 1.5 turns an image into discrete tokens, one per 16 x 16 pixel
patch, and the server clamps the image's area to 1400 x 1400 pixels first (measured
on CSCS on 9 October 2026: about 7,900 prompt tokens for any page from 2,000 pixels
up, whatever its size). A whole A4 page scanned at 300 dpi therefore arrives at about
140 dpi, where the model turns digits into other digits. A strip whose area stays
under the clamp keeps every pixel of the scan.
"""

from __future__ import annotations

import base64
import difflib
import io
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber
from PIL import Image, ImageOps

from leichtfacile.ingest.detect import detect_language
from leichtfacile.llm.client import LLMClient, LLMError
from leichtfacile.rules.values import HARD_KINDS, Value, extract_values, hard_values, matches

MAX_SIDE = 1600
MAX_AREA = 1400 * 1400  # what the server keeps of an image, in pixels (measured 9 Oct 2026)
STRIP_AREA = 1_900_000  # a strip's area: under MAX_AREA with the tokenizer's rounding to 16
INK = 140  # gray level below which a pixel counts as ink
BORDER = 60  # pixels of the scanner's edge left out when the ink is measured
PAD = 48  # margin kept around the ink
PROMPTS = {
    "de": "Schreiben Sie den Text auf dem Bild Wort für Wort ab. Fassen Sie nichts zusammen, "
    "lassen Sie nichts weg und ändern Sie keine Zahl, kein Datum und keinen Namen. Tabellen: "
    "eine Zeile pro Tabellenzeile, die Zellen mit einem Tabulator getrennt. Antworten Sie nur "
    "mit dem abgeschriebenen Text. Wenn das Bild nicht lesbar ist, antworten Sie nur: "
    "unlesbar.",
    "fr": "Recopiez le texte de l'image mot pour mot. Ne résumez rien, n'omettez rien et ne "
    "changez aucun chiffre, aucune date, aucun nom. Tableaux : une ligne par ligne du tableau, "
    "les cellules séparées par une tabulation. Répondez seulement avec le texte recopié. Si "
    "l'image n'est pas lisible, répondez seulement : illisible.",
}
UNREADABLE = ("unlesbar", "illisible", "unreadable")
_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")

Box = tuple[int, int, int, int]  # left, top, right, bottom


@dataclass
class Capture:
    """One capture of a letter: the scan PDF or the photos of its pages, in order."""

    letter: str  # the letter's file stem (steuermahnung-brief)
    name: str  # the capture's name (steuermahnung-brief_scan)
    reference: Path  # the printed text
    files: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class Part:
    """What one call sends: the whole page or one strip of it, as JPEG."""

    label: str  # "page", "strip 3"
    data: bytes
    size: tuple[int, int]
    box: Box | None = None  # the strip's place on the page


def captures(folder: Path) -> list[Capture]:
    """The captures in `<folder>/scans`, paired with the `.txt` next to the folder."""
    by_name: dict[str, Capture] = {}
    for path in sorted((folder / "scans").glob("*")):
        if path.suffix.lower() not in (".pdf", *_IMAGE_SUFFIXES):
            continue
        stem = path.stem
        name = re.sub(r"_p\d+$", "", stem)  # photos: one file per page, _p1, _p2
        letter = name.split("_")[0]
        reference = folder / f"{letter}.txt"
        if not reference.exists():
            continue
        by_name.setdefault(name, Capture(letter, name, reference)).files.append(path)
    return list(by_name.values())


def page_images(data: bytes) -> list[bytes]:
    """The pages of a scanned PDF as images: the embedded JPEG of each page unchanged
    (a scanner writes one DCT-encoded image per page), else the page rendered."""
    out: list[bytes] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            images = page.images
            raw = None
            if len(images) == 1:
                stream = images[0]["stream"]
                filters = stream.get("Filter")
                names = filters if isinstance(filters, list) else [filters]
                if any("DCT" in str(f) for f in names if f is not None):
                    raw = stream.get_rawdata()
            if raw is None:  # no plain JPEG inside: render the page
                image = page.to_image(resolution=200).original.convert("RGB")
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=90)
                raw = buffer.getvalue()
            out.append(raw)
    return out


def capture_pages(capture: Capture) -> list[bytes]:
    pages: list[bytes] = []
    for path in capture.files:
        data = path.read_bytes()
        pages += page_images(data) if path.suffix.lower() == ".pdf" else [data]
    return pages


def _jpeg(picture: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    picture.convert("RGB").save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def scaled(image: bytes, max_side: int = MAX_SIDE) -> tuple[bytes, tuple[int, int]]:
    """The image with its long side at most `max_side` pixels, EXIF rotation applied,
    as JPEG; returns the bytes and the size sent."""
    with Image.open(io.BytesIO(image)) as opened:
        picture = ImageOps.exif_transpose(opened).convert("RGB")
        width, height = picture.size
        longest = max(width, height)
        if longest > max_side:
            factor = max_side / longest
            picture = picture.resize((round(width * factor), round(height * factor)))
        return _jpeg(picture, 88), picture.size


def _ink_profile(picture: Image.Image) -> tuple[bytes, bytes]:
    """Per row and per column of the picture, the share of ink pixels as a byte (0 to
    255): a box resize of the binarised picture to one column and to one row."""
    binary = ImageOps.grayscale(picture).point(lambda p: 255 if p < INK else 0)
    width, height = binary.size
    rows = binary.resize((1, height), Image.Resampling.BOX).tobytes()
    columns = binary.resize((width, 1), Image.Resampling.BOX).tobytes()
    return rows, columns


def ink_box(picture: Image.Image) -> Box:
    """The printed area of a scanned page: the rows and columns with ink, the
    scanner's edge left out, with a margin of PAD pixels."""
    width, height = picture.size
    core = picture.crop((BORDER, BORDER, width - BORDER, height - BORDER))
    rows, columns = _ink_profile(core)
    ys = [i for i, v in enumerate(rows) if v]
    xs = [i for i, v in enumerate(columns) if v]
    if not ys or not xs:
        return (0, 0, width, height)
    return (
        max(0, xs[0] + BORDER - PAD),
        max(0, ys[0] + BORDER - PAD),
        min(width, xs[-1] + BORDER + PAD + 1),
        min(height, ys[-1] + BORDER + PAD + 1),
    )


def strip_boxes(picture: Image.Image, box: Box, area: int = STRIP_AREA) -> list[Box]:
    """Horizontal strips of the page's printed area, each with at most `area` pixels,
    cut in the middle of the longest blank run of rows in the lower half of the
    strip's allowed height, so that no line of text is cut."""
    left, top, right, bottom = box
    width = right - left
    max_height = max(16, area // width)
    rows, _ = _ink_profile(picture.crop(box))
    height = bottom - top
    boxes: list[Box] = []
    start = 0
    while height - start > max_height:
        low, high = start + max_height // 2, start + max_height
        best: tuple[int, int] | None = None
        run_start: int | None = None
        for y in range(low, high + 1):
            if y < height and rows[y] == 0:
                run_start = y if run_start is None else run_start
                continue
            if run_start is not None and (best is None or y - run_start > best[1] - best[0]):
                best = (run_start, y)
            run_start = None
        cut = (best[0] + best[1]) // 2 if best and best[1] - best[0] >= 6 else high
        boxes.append((left, top + start, right, top + cut))
        start = cut
    boxes.append((left, top + start, right, bottom))
    return boxes


def page_parts(image: bytes, *, strips: bool = False, max_side: int = MAX_SIDE) -> list[Part]:
    """What goes to the model for one page: the page scaled to `max_side`, or its
    strips at the scan's own resolution."""
    if not strips:
        data, size = scaled(image, max_side)
        return [Part("page", data, size)]
    with Image.open(io.BytesIO(image)) as opened:
        picture = ImageOps.exif_transpose(opened).convert("RGB")
        parts = []
        for number, box in enumerate(strip_boxes(picture, ink_box(picture)), 1):
            strip = picture.crop(box)
            parts.append(Part(f"strip {number}", _jpeg(strip, 90), strip.size, box))
        return parts


def transcribe(llm: LLMClient, image: bytes, lang: str, *, model: str | None = None):
    """One transcription call: the image and the prompt in the letter's language,
    without thinking, temperature 0."""
    encoded = base64.b64encode(image).decode()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPTS.get(lang, PROMPTS["de"])},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
            ],
        }
    ]
    return llm.complete(messages, model=model, temperature=0.0, max_tokens=6000, stage="transcribe")  # type: ignore[arg-type]


def normalised(text: str) -> str:
    """NFC, every run of whitespace one space, for the character error rate."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def character_error_rate(reference: str, hypothesis: str) -> float:
    ref, hyp = normalised(reference), normalised(hypothesis)
    return round(levenshtein(ref, hyp) / max(1, len(ref)), 4)


def value_recall(reference: str, hypothesis: str, lang: str) -> dict[str, Any]:
    """The printed text's hard values found in the transcription, and the lost ones."""
    keys = sorted(hard_values(reference, lang))
    found_values = extract_values(hypothesis, lang)
    lost = [
        key
        for key in keys
        if not any(matches(Value(key[0], key[1]), v) for v in found_values)  # type: ignore[arg-type]
    ]
    return {
        "hard_values": len(keys),
        "found": len(keys) - len(lost),
        "recall": round((len(keys) - len(lost)) / len(keys), 3) if keys else None,
        "lost": [f"{kind}: {canonical}" for kind, canonical in lost],
    }


def came_back_as(reference: str, hypothesis: str, lang: str, lost: list[str]) -> dict[str, str]:
    """For every lost hard value, what the transcription has at its place: the
    reference and the transcription aligned on their matching stretches, the value's
    offset carried over."""
    ref, hyp = normalised(reference), normalised(hypothesis)
    blocks = difflib.SequenceMatcher(None, ref, hyp, autojunk=False).get_matching_blocks()
    values = {
        f"{v.kind}: {v.canonical}": v for v in extract_values(ref, lang) if v.kind in HARD_KINDS
    }
    out: dict[str, str] = {}
    for key in lost:
        value = values.get(key)
        if value is None or value.start < 0:
            out[key] = "?"
            continue
        anchor = None
        for a, b, size in blocks:  # the last real matching stretch before the value
            if size >= 4 and a <= value.start:
                anchor = (a, b, size)
        if anchor is None:
            out[key] = "(not aligned)"
            continue
        a, b, size = anchor
        start = value.start + (b - a)
        length = value.end - value.start
        out[key] = hyp[max(0, start - 2) : start + length + 6].strip() or "(nothing)"
    return out


def run_spike(
    llm: LLMClient,
    folder: Path,
    *,
    max_side: int = MAX_SIDE,
    model: str | None = None,
    names: list[str] | None = None,
    strips: bool = False,
) -> dict[str, Any]:
    """Every capture of the folder through the model; the report per capture and call."""
    report: dict[str, Any] = {
        "endpoint": llm.settings.llm_base_url,
        "model": llm.resolve_model(model, False)[0],
        "max_side": max_side,
        "strips": strips,
        "captures": [],
    }
    for capture in captures(folder):
        if names and capture.name not in names:
            continue
        reference = capture.reference.read_text(encoding="utf-8")
        lang = detect_language(reference)[0] or "de"
        item: dict[str, Any] = {"capture": capture.name, "letter": capture.letter, "lang": lang,
                                "pages": []}  # fmt: skip
        transcription: list[str] = []
        for number, image in enumerate(capture_pages(capture), 1):
            for part in page_parts(image, strips=strips, max_side=max_side):
                page: dict[str, Any] = {
                    "page": number,
                    "part": part.label,
                    "sent_pixels": list(part.size),
                    "sent_bytes": len(part.data),
                }
                if part.box:
                    page["box"] = list(part.box)
                try:
                    result = transcribe(llm, part.data, lang, model=model)
                except LLMError as exc:
                    page["error"] = str(exc)[:300]
                    item["pages"].append(page)
                    continue
                text = result.text.strip()
                page.update(
                    chars=len(text),
                    tokens_in=result.usage.tokens_in,
                    tokens_out=result.usage.tokens_out,
                    seconds=round(result.usage.latency_ms / 1000, 1),
                    unreadable=text.lower().rstrip(".") in UNREADABLE,
                )
                transcription.append(text)
                item["pages"].append(page)
        joined = "\n\n".join(transcription)
        item["character_error_rate"] = character_error_rate(reference, joined)
        item.update(value_recall(reference, joined, lang))
        item["came_back_as"] = came_back_as(reference, joined, lang, item["lost"])
        item["transcription"] = joined
        report["captures"].append(item)
    return report


def render_spike(report: dict[str, Any]) -> str:
    setting = (
        f"strips at the scan's resolution, at most {STRIP_AREA:,} pixels each"
        if report.get("strips")
        else f"long side {report['max_side']} px"
    )
    lines = [
        f"Image input spike: {report['model']} at {report['endpoint']}, {setting}.",
        "",
        "| Capture | Calls | Character error rate | Hard values found | Lost |",
        "|---|---|---|---|---|",
    ]
    for item in report["captures"]:
        errors = [p["error"] for p in item["pages"] if "error" in p]
        lost = ", ".join(item.get("lost", [])) or "-"
        if errors:
            lost = "call failed: " + errors[0]
        recall = item.get("recall")
        lines.append(
            f"| {item['capture']} | {len(item['pages'])} | {item.get('character_error_rate', '-')} "
            f"| {item.get('found', 0)} of {item.get('hard_values', 0)}"
            f"{'' if recall is None else f' ({100 * recall:.0f} %)'} | {lost} |"
        )
    for item in report["captures"]:
        if item.get("lost"):
            lines += ["", f"{item['capture']}, lost values and what came back:"]
            for key in item["lost"]:
                lines.append(f"  {key} -> {item.get('came_back_as', {}).get(key, '?')!r}")
    pages = [p for item in report["captures"] for p in item["pages"] if "seconds" in p]
    if pages:
        lines += [
            "",
            f"{len(pages)} calls, {sum(p['seconds'] for p in pages):.0f} s in total, "
            f"{sum(p['tokens_out'] for p in pages)} output tokens.",
        ]
    lost_any = any(item.get("lost") for item in report["captures"])
    lines += [
        "",
        "Hard values lost: go/no-go says stop here." if lost_any else "No hard value lost.",
    ]
    return "\n".join(lines)


def to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=1)
