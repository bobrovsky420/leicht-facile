"""The evaluation harness end to end on one synthetic pair, against the fake endpoint."""

from __future__ import annotations

import json

import pytest

from leichtfacile.eval import dataset
from leichtfacile.eval.calibrate import calibrate, render_calibration, source_as_draft
from leichtfacile.eval.day1 import (
    check_image,
    check_json,
    check_models,
    check_parallel,
    check_thinking,
)
from leichtfacile.eval.report import render_report
from leichtfacile.eval.run import reference_rows, run_condition
from leichtfacile.llm.client import LLMClient
from leichtfacile.schemas import Segment, SourceDocument, SourceInfo
from tests.conftest import FakeEndpoint, chat_response, make_settings
from tests.pipeline import fixtures as fx

EASY_LINES = [
    ("heading", "Was ist die Prämien·verbilligung?"),
    ("sentence", "Sie haben wenig Geld?"),
    ("sentence", "Dann bezahlt der Kanton einen Teil von Ihrer Kranken·kasse."),
    ("heading", "Was müssen Sie tun?"),
    ("sentence", "Schicken Sie das Gesuch bis 31. März 2026 an die Gemeinde."),
    ("sentence", "Das kostet 20 Franken."),
    ("sentence", "Fragen? Rufen Sie an: 044 123 45 67."),
]


def easy_doc() -> SourceDocument:
    kinds = {"heading": "heading", "sentence": "paragraph"}
    return SourceDocument(
        id="pair.easy", lang="de", source=SourceInfo(type="text"),
        segments=[Segment(id=f"s{i:04d}", kind=kinds[k], text=t, para=i,
                          heading_level=2 if k == "heading" else None)
                  for i, (k, t) in enumerate(EASY_LINES, 1)],
    )  # fmt: skip


@pytest.fixture
def pair_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    manifest = tmp_path / "manifest.jsonl"
    rows = [
        {"id": "syn-letter-de", "publisher": "Team", "canton": "ZH", "lang": "de", "level": "A2",
         "role": "eval", "standard_url": "https://example.org/s", "easy_url": "https://example.org/e",
         "license": "synthetic"},
        {"id": "syn-other-de", "lang": "de", "role": "dev", "url_standard": "https://example.org/a",
         "url_easy": "https://example.org/b", "licence_note": "synthetic"},
    ]  # fmt: skip
    manifest.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    cache = dataset.cache_dir()
    cache.mkdir(parents=True)
    dataset.cached_path("syn-letter-de", "standard").write_text(
        fx.letter().model_dump_json(), encoding="utf-8"
    )
    dataset.cached_path("syn-letter-de", "easy").write_text(
        easy_doc().model_dump_json(), encoding="utf-8"
    )
    return manifest


def test_manifest_accepts_both_field_spellings(pair_env) -> None:
    pairs = dataset.load_manifest(pair_env)
    assert [p.url_standard for p in pairs] == ["https://example.org/s", "https://example.org/a"]
    assert pairs[0].licence_note == "synthetic"
    assert [p.id for p in dataset.select(pairs, role="eval")] == ["syn-letter-de"]
    standard, easy = dataset.load_pair(pairs[0])
    assert standard.segments[0].text == "Prämienverbilligung 2026"
    with pytest.raises(FileNotFoundError):
        dataset.load_pair(pairs[1])


def test_calibration_on_an_easy_text() -> None:
    cal = calibrate([("syn", easy_doc())], "A2")
    assert cal.blocks == len(EASY_LINES)
    assert cal.per_100("error") == 0.0
    assert "| Rule | Severity |" in render_calibration(cal)
    assert source_as_draft(easy_doc()).blocks[0].kind == "heading"


def test_reference_run_and_report(pair_env, tmp_path, endpoint, sleeps) -> None:
    pairs = dataset.select(dataset.load_manifest(pair_env), role="eval")
    results = tmp_path / "results"
    reference_rows(pairs, results)
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.JUDGE_FIRST)),
        chat_response(fx.as_json(fx.REPAIR)),
        chat_response(fx.as_json(fx.JUDGE_SECOND)),
    )
    settings = make_settings(llm_max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    path = run_condition(pairs, "C2", settings=settings, llm=llm, results_dir=results)
    (row,) = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert row["status"] == "needs_review", row.get("error")
    assert row["fact_coverage"] == 1.0
    assert row["hard_facts_found"] == row["hard_facts_total"] == 3  # 31 March, CHF 20, phone
    assert row["calls"] == 5 and row["usd_per_page"] is not None
    assert 0 <= row["sari"] <= 100
    assert row["judge_distorted"] == 0.0

    # Resumable: a second run does nothing for a pair that has a result.
    run_condition(pairs, "C2", settings=settings, llm=llm, results_dir=results)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1

    report = render_report(results, role="eval")
    assert "Original (standard language)" in report
    assert "Official easy-language version" in report
    assert "C2: full pipeline with judge and repair" in report


BASELINE_TEXT = (
    "Der Kanton bezahlt einen Teil von Ihrer Kranken·kasse.\n"
    "Schicken Sie das Gesuch bis 31. März 2026 an die Gemeinde.\n"
    "Das kostet 20 Franken. Fragen? Rufen Sie an: 044 123 45 67."
)


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_a_failed_scoring_call_marks_the_pair_and_reruns_it(
    pair_env, tmp_path, endpoint, sleeps
) -> None:
    pairs = dataset.select(dataset.load_manifest(pair_env), role="eval")
    results = tmp_path / "results"
    settings = make_settings(llm_max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)

    # C0 needs a fact sheet for scoring; the model answers with a fragment, twice.
    endpoint.push(
        chat_response(BASELINE_TEXT), chat_response('{"core": {}}'), chat_response('{"core": {}}')
    )
    path = run_condition(pairs, "C0", settings=settings, llm=llm, results_dir=results)
    (row,) = _rows(path)
    assert row["status"] == "scoring_failed"
    assert "UnderstandOut" in row["error"]

    # The pair runs again next time, and the failed row is replaced, not duplicated.
    endpoint.push(chat_response(BASELINE_TEXT), chat_response(fx.as_json(fx.UNDERSTAND)))
    run_condition(pairs, "C0", settings=settings, llm=llm, results_dir=results)
    (row,) = _rows(path)
    assert row["status"] == "needs_review", row.get("error")
    assert row["fact_coverage"] == 1.0
    assert endpoint.chat_bodies()[-1]["messages"][0]["content"].startswith("Sie bereiten")


def test_report_has_one_section_per_language(tmp_path) -> None:
    rows = [
        {"setup": "REF", "pair_id": "a-de", "role": "eval", "lang": "de", "errors_per_100": 2.0},
        {"setup": "REF", "pair_id": "b-fr", "role": "eval", "lang": "fr", "errors_per_100": 4.0},
    ]
    (tmp_path / "REF.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    report = render_report(tmp_path)
    assert report.index("## German") < report.index("## French")
    german, french = report.split("## French")
    assert "| 2.0 |" in german and "| 4.0 |" not in german
    assert "| 4.0 |" in french
    only_french = render_report(tmp_path, lang="fr")
    assert "## " not in only_french and "| 4.0 |" in only_french


@pytest.fixture
def llm(endpoint: FakeEndpoint, sleeps) -> LLMClient:
    return LLMClient(
        make_settings(llm_max_retries=0), http_client=endpoint.http_client(), sleep=sleeps.append
    )


def test_day1_checks_against_the_fake_endpoint(llm, endpoint) -> None:
    assert check_models(llm)["expected_listed"]["Apertus-v1.5-8B"] is True
    endpoint.push(chat_response("165", reasoning_content="120 + 45 = 165"))
    thinking = check_thinking(llm)
    assert thinking["reasoning_found"] and thinking["model"].endswith("-thinking")
    endpoint.push(*[chat_response(fx.as_json(fx.UNDERSTAND)) for _ in range(2)])
    endpoint.push(chat_response("kein JSON"), chat_response(fx.as_json(fx.UNDERSTAND)))
    result = check_json(llm, fx.letter(), runs=2)
    assert result["plain"]["ok"] == 2
    assert result["json_object"]["no_json"] == 1 and result["json_object"]["ok"] == 1
    assert endpoint.chat_bodies()[-1]["response_format"] == {"type": "json_object"}
    endpoint.push(chat_response("Bis 31. März 2026 die Steuererklärung einreichen."))
    assert check_image(llm)["supported"] is True
    endpoint.push(*[chat_response(str(i)) for i in range(8)])
    assert check_parallel(llm)["succeeded"] == 8
