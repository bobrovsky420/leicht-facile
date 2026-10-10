"""Day-1 verification (track_2b/docs/architecture.md §12, PLAN §5): the questions only the live
endpoint can answer. Run with `uv run python track_2b/scripts/day1_checks.py` once .env exists.

1. Which models does the endpoint list?
2. How do thinking models return their reasoning?
3. How reliable is JSON output, with and without response_format?
4. Does the endpoint accept image input?
5. What happens with parallel calls (rate limits, latency spread)?
6. Baseline quality: P0 on German pairs (run separately: `eval run --condition P0`).
"""

from __future__ import annotations

import base64
import io
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pydantic import ValidationError

from leichtfacile.llm.client import LLMClient, LLMError
from leichtfacile.llm.json_out import JSONExtractionError, extract_json
from leichtfacile.pipeline.models import UnderstandOut
from leichtfacile.pipeline.prompts import level_name, render
from leichtfacile.pipeline.render import source_text
from leichtfacile.schemas import SourceDocument

EXPECTED = (
    "Apertus-v1.5-8B",
    "Apertus-v1.5-8B-thinking",
    "Apertus-v1.5-70B",
    "Apertus-v1.5-70B-thinking",
)


def check_models(llm: LLMClient) -> dict[str, Any]:
    models = llm.list_models()
    lowered = [m.lower() for m in models]
    return {
        "models": models,
        "expected_listed": {
            name: any(m.endswith(name.lower()) for m in lowered) for name in EXPECTED
        },
    }


def check_thinking(llm: LLMClient) -> dict[str, Any]:
    result = llm.complete(
        [
            {
                "role": "user",
                "content": "Ein Velo kostet 120 Franken, ein Helm 45. "
                "Was kostet beides? Nur die Zahl.",
            }
        ],
        thinking=True,
        max_tokens=4096,
        stage="day1",
    )
    return {
        "model": result.usage.model,
        "answer": result.text,
        "reasoning_found": bool(result.reasoning),
        "reasoning_chars": len(result.reasoning or ""),
        "finish_reason": result.finish_reason,
        "tokens_out": result.usage.tokens_out,
        "latency_ms": result.usage.latency_ms,
    }


def check_json(llm: LLMClient, doc: SourceDocument, runs: int = 20) -> dict[str, Any]:
    prompt = render(
        doc.lang, "understand", level_name=level_name(doc.lang, "A2"), source=source_text(doc)
    )
    out: dict[str, Any] = {}
    for mode, response_format in (("plain", None), ("json_object", {"type": "json_object"})):
        counts = {"ok": 0, "no_json": 0, "invalid": 0, "error": 0, "truncated": 0}
        errors: list[str] = []
        latencies = []
        for i in range(runs):
            try:
                result = llm.complete(
                    [{"role": "user", "content": prompt}],
                    thinking=True,
                    temperature=0.1,
                    max_tokens=12000,
                    stage=f"day1-json-{i}",
                    response_format=response_format,
                )
            except LLMError as exc:
                counts["error"] += 1
                errors.append(str(exc)[:200])
                if mode == "json_object":
                    break  # the endpoint rejects response_format: no point repeating
                continue
            latencies.append(result.usage.latency_ms)
            if result.truncated:
                counts["truncated"] += 1
            try:
                UnderstandOut.model_validate(extract_json(result.text))
                counts["ok"] += 1
            except JSONExtractionError:
                counts["no_json"] += 1
            except ValidationError:
                counts["invalid"] += 1
        out[mode] = {**counts, "errors": errors[:3],
                     "median_latency_ms": statistics.median(latencies) if latencies
                     else None}  # fmt: skip
    return out


def _letter_png() -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (900, 360), "white")
    draw = ImageDraw.Draw(image)
    lines = [
        "Gemeinde Musterdorf, Steueramt",
        "Ihre Steuererklaerung 2025",
        "Bitte reichen Sie die Steuererklaerung",
        "bis zum 31. Maerz 2026 ein.",
        "Fragen: Telefon 044 123 45 67",
    ]
    for i, line in enumerate(lines):
        draw.text((40, 40 + 55 * i), line, fill="black", font_size=32)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def check_image(llm: LLMClient) -> dict[str, Any]:
    data = base64.b64encode(_letter_png()).decode()
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Lies den Brief auf dem Bild. "
                    "Bis wann muss man was tun? Antworte kurz.",
                },
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}},
            ],
        }
    ]
    try:
        result = llm.complete(messages, max_tokens=512, stage="day1-image")  # type: ignore[arg-type]
    except LLMError as exc:
        return {"supported": False, "error": str(exc)[:300]}
    text = result.text
    return {"supported": "31" in text and ("März" in text or "Maerz" in text or "3." in text),
            "answer": text[:300]}  # fmt: skip


def check_parallel(llm: LLMClient, calls: int = 8) -> dict[str, Any]:
    def one(i: int) -> tuple[bool, int, str]:
        started = time.perf_counter()
        try:
            llm.complete(
                [{"role": "user", "content": f"Sag nur die Zahl {i}."}],
                max_tokens=16,
                stage=f"day1-par-{i}",
            )
            return True, int((time.perf_counter() - started) * 1000), ""
        except LLMError as exc:
            return False, int((time.perf_counter() - started) * 1000), str(exc)[:120]

    with ThreadPoolExecutor(max_workers=calls) as pool:
        results = list(pool.map(one, range(calls)))
    latencies = [ms for ok, ms, _ in results if ok]
    return {
        "calls": calls,
        "succeeded": sum(1 for ok, _, _ in results if ok),
        "errors": [e for ok, _, e in results if not ok][:3],
        "latency_ms_min": min(latencies) if latencies else None,
        "latency_ms_max": max(latencies) if latencies else None,
    }


def run_all(llm: LLMClient, doc: SourceDocument, *, json_runs: int = 20) -> dict[str, Any]:
    report: dict[str, Any] = {"endpoint": llm.settings.llm_base_url}
    checks = (
        ("1_models", lambda: check_models(llm)),
        ("2_thinking", lambda: check_thinking(llm)),
        ("3_json", lambda: check_json(llm, doc, json_runs)),
        ("4_image", lambda: check_image(llm)),
        ("5_parallel", lambda: check_parallel(llm)),
    )
    for name, check in checks:
        try:
            report[name] = check()
        except Exception as exc:  # report and continue with the next check
            report[name] = {"failed": f"{type(exc).__name__}: {exc}"[:300]}
    report["6_baseline"] = "run: uv run python -m leichtfacile eval run --condition P0 --limit 10"
    return report


def to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)
