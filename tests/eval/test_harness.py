"""The evaluation harness end to end on one synthetic pair, against the fake endpoint."""

from __future__ import annotations

import json

import pytest

from leichtfacile.eval import dataset
from leichtfacile.eval.calibrate import calibrate, render_calibration
from leichtfacile.eval.report import render_report
from leichtfacile.eval.run import reference_rows, run_condition
from leichtfacile.llm.client import LLMClient
from leichtfacile.rules import source_as_draft
from leichtfacile.schemas import FactSheet, Segment, SourceDocument, SourceInfo
from leichtfacile.store import Store
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
    monkeypatch.setenv("LEICHTFACILE_DATA__DIR", str(tmp_path / "data"))
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
    standard, _easy = dataset.load_pair(pairs[0])
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
    settings = make_settings(llm__max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    path = run_condition(pairs, "P2", settings=settings, llm=llm, results_dir=results)
    (row,) = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert row["status"] == "needs_review", row.get("error")
    assert row["fact_coverage"] == 1.0
    assert row["hard_facts_found"] == row["hard_facts_total"] == 3  # 31 March, CHF 20, phone
    assert row["reference_facts_found"] == row["reference_facts_total"] == 3
    assert row["reference_fact_recall"] == 1.0  # the official version keeps all three
    assert row["silent_losses"] == 0 and row["silent_loss_share"] == 0.0
    assert row["calls"] == 5 and row["usd_per_page"] is not None
    assert 0 <= row["sari"] <= 100
    assert row["judge_distorted"] == 0.0

    # Resumable: a second run does nothing for a pair that has a result.
    run_condition(pairs, "P2", settings=settings, llm=llm, results_dir=results)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert len(endpoint.chat_bodies()) == 5

    # After a prompt change, `redo` runs the pair again and replaces its row.
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.JUDGE_FIRST)),
        chat_response(fx.as_json(fx.REPAIR)),
        chat_response(fx.as_json(fx.JUDGE_SECOND)),
    )
    run_condition(pairs, "P2", settings=settings, llm=llm, results_dir=results, redo=True)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert len(endpoint.chat_bodies()) == 10

    report = render_report(results, role="eval")
    assert "| Silent losses |" in report and "zero by design" in report
    assert "| Hard facts kept | Reference facts kept |" in report
    assert "Original (standard language)" in report
    assert "Official easy-language version" in report
    assert "P2 full: pipeline with judge and repair" in report


def test_a_run_takes_the_judges_role_and_its_rows_name_it(
    pair_env, tmp_path, endpoint, sleeps
) -> None:
    """`eval run --judge-role report`: the rounds on the rule findings, one judge call on
    the final draft, whose report fills the row's judge columns; a run without the
    option takes the setting of the model that judges (the loop)."""
    import argparse

    from leichtfacile.eval.cli import add_eval_parser

    pairs = dataset.select(dataset.load_manifest(pair_env), role="eval")
    settings = make_settings(llm__max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.REPAIR)),
        chat_response(fx.as_json(fx.JUDGE_SECOND)),
    )
    path = run_condition(
        pairs, "P2", settings=settings, llm=llm, results_dir=tmp_path / "report",
        judge_role="report",
    )  # fmt: skip
    (row,) = _rows(path)
    assert row["status"] == "needs_review", row.get("error")
    assert row["judge_role"] == "report" and row["calls"] == 4
    assert row["judge_missing"] == 0.0 and row["fact_coverage"] == 1.0

    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.JUDGE_FIRST)),
        chat_response(fx.as_json(fx.REPAIR)),
        chat_response(fx.as_json(fx.JUDGE_SECOND)),
    )
    path = run_condition(pairs, "P2", settings=settings, llm=llm, results_dir=tmp_path / "loop")
    (row,) = _rows(path)
    assert row["judge_role"] == "loop" and row["calls"] == 5

    parser = argparse.ArgumentParser()
    add_eval_parser(parser.add_subparsers(dest="command"))
    args = parser.parse_args(["eval", "run", "--condition", "P2", "--judge-role", "off"])
    assert args.judge_role == "off"
    assert parser.parse_args(["eval", "run", "--condition", "P2"]).judge_role is None


def test_hybrid_run_gets_its_own_file_and_label(pair_env, tmp_path, endpoint, sleeps) -> None:
    """Another model for the Understand stage: its own results file, named in the row and
    in the report, so it is never mixed with the plain writer's run."""
    pairs = dataset.select(dataset.load_manifest(pair_env), role="eval")
    results = tmp_path / "results"
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    settings = make_settings(llm__max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    reader = "swiss-ai/Apertus-v1.5-70B"
    path = run_condition(
        pairs, "P1", settings=settings, llm=llm, results_dir=results, understand=reader
    )
    assert path.name == "P1_swiss-ai-apertus-v1-5-8b_understand-swiss-ai-apertus-v1-5-70b.jsonl"
    (row,) = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert row["status"] == "needs_review", row.get("error")
    assert row["writer"] == settings.llm.models.writer and row["understand"] == reader
    assert [b["model"] for b in endpoint.chat_bodies()] == [
        reader + "-thinking",
        settings.llm.models.writer,
    ]
    models = f"{settings.llm.models.writer}, understand {reader}"
    label = f"P1 no judge: fact sheet + draft + rule check ({models})"
    assert label in render_report(results, role="eval")


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
    settings = make_settings(llm__max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)

    # P0 needs a fact sheet for scoring; the model answers with a fragment, twice.
    endpoint.push(
        chat_response(BASELINE_TEXT), chat_response('{"core": {}}'), chat_response('{"core": {}}')
    )
    path = run_condition(pairs, "P0", settings=settings, llm=llm, results_dir=results)
    (row,) = _rows(path)
    assert row["status"] == "scoring_failed"
    assert "UnderstandOut" in row["error"]

    # The pair runs again next time, and the failed row is replaced, not duplicated.
    endpoint.push(chat_response(BASELINE_TEXT), chat_response(fx.as_json(fx.UNDERSTAND)))
    run_condition(pairs, "P0", settings=settings, llm=llm, results_dir=results)
    (row,) = _rows(path)
    assert row["status"] == "needs_review", row.get("error")
    assert row["fact_coverage"] == 1.0
    assert endpoint.chat_bodies()[-1]["messages"][0]["content"].startswith("Du bereitest")


def test_the_written_report_is_a_page_of_the_docs(tmp_path) -> None:
    from leichtfacile.cli import main

    row = {"setup": "REF", "pair_id": "a-de", "role": "eval", "lang": "de", "errors_per_100": 2.0}
    (tmp_path / "REF.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    out = tmp_path / "evaluation.md"
    assert main(["eval", "report", "--results", str(tmp_path), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Evaluation tables\n") and "do not edit\nby hand." in text
    assert "| 2.0 |" in text


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
        make_settings(llm__max_retries=0), http_client=endpoint.http_client(), sleep=sleeps.append
    )


def test_a_baseline_in_a_fresh_store_is_scored_against_a_completed_fact_sheet(
    pair_env, tmp_path, endpoint, sleeps
) -> None:
    """No P1 or P2 job yet: the scoring fact sheet comes from one Understand call, and code
    completes it with the source's values as in the pipeline. Without that, a baseline
    run first would be measured against fewer facts than one run after the others."""
    pairs = dataset.select(dataset.load_manifest(pair_env), role="eval")
    results = tmp_path / "results"
    no_facts = {**fx.UNDERSTAND, "facts": []}
    endpoint.push(chat_response(BASELINE_TEXT), chat_response(fx.as_json(no_facts)))
    settings = make_settings(llm__max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    path = run_condition(pairs, "P0", settings=settings, llm=llm, results_dir=results)
    (row,) = _rows(path)
    assert row["status"] == "needs_review", row.get("error")
    store = Store(results / "store.sqlite")
    (job,) = store.list_jobs(limit=10)
    fs = store.get_artifact(job.id, "score_factsheet", FactSheet)
    store.close()
    assert fs is not None and fs.facts and all(f.origin == "code" for f in fs.facts)
    assert {f.value_norm for f in fs.facts} == {"2026-03-31", "20", "0441234567"}
    assert row["fact_coverage"] == 1.0  # the baseline text keeps all three


def test_silent_losses_need_a_checklist_or_an_omission_log() -> None:
    from leichtfacile.eval.score import silent_losses
    from leichtfacile.pipeline.facts import complete_factsheet, to_factsheet
    from leichtfacile.pipeline.models import UnderstandOut
    from leichtfacile.schemas import Block, Draft, Omission

    standard = fx.letter()  # three hard values: 31 March 2026, CHF 20, the phone number
    fs = complete_factsheet(
        to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), "d"), standard
    )
    without_phone = Draft(doc_id="d", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Schicken Sie das Gesuch bis 31. März 2026."),
        Block(id="b002", kind="sentence", text="Das kostet 20 Franken."),
    ])  # fmt: skip
    # A single prompt: the lost number is silent, whatever fact sheet the scorer borrows.
    baseline = silent_losses(without_phone, standard, fs, condition="P0")
    assert baseline["silent_losses"] == 1 and baseline["silent_loss_share"] == 0.333
    assert baseline["silent_loss_kinds"] == {"phone": 1}
    # The pipeline: the fact sheet lists the number, the reviewer sees it as missing.
    assert silent_losses(without_phone, standard, fs, condition="P2")["silent_losses"] == 0
    # No fact for it, but its sentence is a listed omission: still told.
    fewer = fs.model_copy(update={"facts": [f for f in fs.facts if f.id != "f03"]})
    assert silent_losses(without_phone, standard, fewer, condition="P2")["silent_losses"] == 1
    omitted = without_phone.model_copy(
        update={"omissions": [Omission(what="Kontakt", why="x", segment_ids=["s0005"])]}
    )
    assert silent_losses(omitted, standard, fewer, condition="P2")["silent_losses"] == 0
    assert silent_losses(without_phone, standard, None, condition="P2")["silent_losses"] == 1


def test_a_completed_percentage_is_told_and_not_a_silent_loss() -> None:
    from leichtfacile.eval.score import silent_losses
    from leichtfacile.pipeline.facts import complete_factsheet
    from leichtfacile.schemas import Block, Draft, FactSheet, Segment, SourceDocument, SourceInfo

    source = SourceDocument(id="d", lang="de", source=SourceInfo(type="text"), segments=[
        Segment(id="s0001", kind="paragraph", text="Der Kanton zahlt 4.5 % der Kosten.", para=1),
        Segment(id="s0002", kind="paragraph", text="Adresse: Gerichtsstrasse 12", para=2),
        Segment(id="s0003", kind="paragraph", text="8000 Musterwil.", para=2),
    ])  # fmt: skip
    fs = complete_factsheet(FactSheet(doc_id="d"), source)
    blocks = [Block(id="b001", kind="sentence", text="Der Kanton zahlt mit.")]
    draft = Draft(doc_id="d", lang="de", level="A2", blocks=blocks)
    assert silent_losses(draft, source, fs, condition="P2")["silent_losses"] == 0
    baseline = silent_losses(draft, source, fs, condition="P0")
    assert baseline["silent_losses"] == 2 and baseline["silent_loss_kinds"] == {
        "address": 1, "percent": 1,
    }  # fmt: skip


def test_rescore_scores_the_stored_jobs_again_under_both_selection_rules(
    pair_env, tmp_path, endpoint, sleeps
) -> None:
    from leichtfacile.eval.run import rescore

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
    settings = make_settings(llm__max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    path = run_condition(pairs, "P2", settings=settings, llm=llm, results_dir=results)
    (row,) = _rows(path)
    calls = len(endpoint.chat_bodies())

    out = rescore(results, pairs=pairs, condition="P2", role="eval")
    assert out == tmp_path / "results-rescored-facts" and (out / "REF.jsonl").exists()
    (again,) = _rows(out / path.name)
    assert again["selection"] == "facts" and again["draft_version"] == row["draft_version"] == 2
    assert again["fact_coverage"] == row["fact_coverage"] == 1.0
    assert again["stored_final_version"] == 2 and again["job_id"] == row["job_id"]
    other = rescore(results, pairs=pairs, condition="P2", role="eval", select="blocking",
                    out_dir=tmp_path / "blocking")  # fmt: skip
    (blocking,) = _rows(other / path.name)
    assert blocking["selection"] == "blocking" and blocking["draft_version"] == 2
    assert len(endpoint.chat_bodies()) == calls  # no model call
    assert "P2 full: pipeline with judge and repair" in render_report(out, role="eval")

    from leichtfacile.cli import main

    assert main(["eval", "rescore", "--manifest", str(pair_env), "--results", str(results),
                 "--role", "eval", "--out", str(tmp_path / "cli")]) == 0  # fmt: skip
    assert (tmp_path / "cli" / path.name).exists()


def test_rescore_in_place_scores_a_baseline_again_without_sampling_it_again(
    pair_env, tmp_path, endpoint, sleeps
) -> None:
    """Since 12 October 2026: after a change of the metrics or of the P2 fact sheets, a
    baseline whose prompt did not change keeps its answers; its rows are replaced in
    the results folder, scored against the newest P1 or P2 fact sheet of its pair (here
    the one the scoring made), without a model call."""
    from leichtfacile.eval.run import rescore

    pairs = dataset.select(dataset.load_manifest(pair_env), role="eval")
    results = tmp_path / "results"
    reference_rows(pairs, results)
    settings = make_settings(llm__max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    endpoint.push(chat_response(BASELINE_TEXT), chat_response(fx.as_json(fx.UNDERSTAND)))
    path = run_condition(pairs, "P0", settings=settings, llm=llm, results_dir=results)
    (row,) = _rows(path)
    assert row["status"] == "needs_review", row.get("error")
    calls = len(endpoint.chat_bodies())

    out = rescore(results, pairs=pairs, condition="P0", role="eval", in_place=True)
    assert out == results and not (tmp_path / "results-rescored-facts").exists()
    (again,) = _rows(path)
    assert again["rescored"] is True and again["job_id"] == row["job_id"]
    assert again["region"] == row["region"]  # dropped, it made a de-DE row Swiss German
    assert again["fact_coverage"] == row["fact_coverage"] == 1.0
    assert "selection" not in again and "stored_final_version" not in again
    assert len(endpoint.chat_bodies()) == calls  # no model call
    assert (results / "REF.jsonl").exists()


def test_rescore_only_adds_a_measure_and_leaves_the_scores_of_the_day(
    pair_env, tmp_path, endpoint, sleeps
) -> None:
    """A measure the stored rows do not have yet reaches them without a model call and
    without a change of their other numbers: a published run keeps the scores of its
    day (docs/model-comparison.md)."""
    from leichtfacile.cli import main
    from leichtfacile.eval.run import rescore

    pairs = dataset.select(dataset.load_manifest(pair_env), role="eval")
    results = tmp_path / "results"
    endpoint.push(
        chat_response(fx.as_json(fx.UNDERSTAND)),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.JUDGE_FIRST)),
        chat_response(fx.as_json(fx.REPAIR)),
        chat_response(fx.as_json(fx.JUDGE_SECOND)),
    )
    settings = make_settings(llm__max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    path = run_condition(pairs, "P2", settings=settings, llm=llm, results_dir=results)
    (row,) = _rows(path)
    calls = len(endpoint.chat_bodies())
    # A row as an earlier version stored it: without the measure, with the scores of its day.
    old = {k: v for k, v in row.items() if not k.startswith("reference_")}
    old["errors_per_100"] = 99.0
    path.write_text(json.dumps(old) + "\n", encoding="utf-8")

    measures = ["reference_fact_recall", "reference_facts_total", "reference_facts_found"]
    out = rescore(results, pairs=pairs, condition="P2", role="eval", in_place=True, only=measures)
    (again,) = _rows(path)
    assert out == results and len(endpoint.chat_bodies()) == calls  # no model call
    assert again["reference_fact_recall"] == 1.0 and again["reference_facts_total"] == 3
    assert again["errors_per_100"] == 99.0 and "rescored" not in again
    assert {k: v for k, v in again.items() if k not in measures} == old

    with pytest.raises(ValueError, match="in_place"):
        rescore(results, pairs=pairs, condition="P2", role="eval", only=measures)
    with pytest.raises(ValueError, match="no such measure"):
        rescore(results, pairs=pairs, condition="P2", role="eval", in_place=True, only=["nope"])
    assert main(["eval", "rescore", "--manifest", str(pair_env), "--results", str(results),
                 "--role", "eval", "--in-place", "--only", "nope"]) == 2  # fmt: skip
    assert _rows(path) == [again]  # a refused measure writes nothing


def test_rows_move_into_place_when_the_file_is_held_for_a_moment(tmp_path, monkeypatch) -> None:
    """A sync client or a virus scanner on Windows has the rows file open for a moment
    and refuses the move: tried again, and only a file that stays held is an error."""
    from pathlib import Path

    from leichtfacile.eval import run

    path = tmp_path / "P2_m.jsonl"
    path.write_text('{"pair_id": "old"}\n', encoding="utf-8")
    move, tries = Path.replace, []

    def held_twice(self, target):
        tries.append(target)
        if len(tries) < 3:
            raise PermissionError(5, "Access is denied")
        return move(self, target)

    monkeypatch.setattr(run.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(Path, "replace", held_twice)
    run._write_rows(path, [{"pair_id": "a"}])
    assert len(tries) == 3 and _rows(path) == [{"pair_id": "a"}]

    def held(self, target):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(Path, "replace", held)
    with pytest.raises(PermissionError):
        run._write_rows(path, [{"pair_id": "b"}])
    assert _rows(path) == [{"pair_id": "a"}]  # the file as it was


def test_reference_facts_ask_for_what_the_official_version_keeps() -> None:
    from leichtfacile.eval.score import hard_values_of, reference_facts
    from leichtfacile.schemas import Block, Draft

    standard = fx.letter()  # three hard values: 31 March 2026, CHF 20, the phone number
    draft = Draft(doc_id="d", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Schicken Sie das Gesuch bis 31. März 2026."),
        Block(id="b002", kind="sentence", text="Rufen Sie an: 044 123 45 67."),
    ])  # fmt: skip
    hard = hard_values_of(draft, standard)
    assert len(hard.found) == 2 and len(hard.keys) == 3  # the amount is lost
    # The official version keeps all three: the draft keeps two of them.
    assert reference_facts(hard, easy_doc()) == {
        "reference_facts_total": 3, "reference_facts_found": 2, "reference_fact_recall": 0.667,
    }  # fmt: skip
    # An official version that leaves the amount out too: nothing it keeps is lost.
    official = easy_doc()
    without_amount = official.model_copy(
        update={"segments": [s for s in official.segments if "Franken" not in s.text]}
    )
    assert reference_facts(hard, without_amount) == {
        "reference_facts_total": 2, "reference_facts_found": 2, "reference_fact_recall": 1.0,
    }  # fmt: skip
    # An official version without a hard value: no share.
    empty = official.model_copy(update={"segments": official.segments[:2]})
    assert reference_facts(hard, empty)["reference_fact_recall"] is None


def test_reference_rows_keep_the_file_when_a_pair_cannot_be_loaded(
    pair_env, tmp_path, monkeypatch
) -> None:
    """The rows are made before the file is touched: a pair whose text was not cached
    raised after the file was truncated, and the rows of every selected pair were gone
    (audit of 6 November 2026)."""
    pairs = dataset.select(dataset.load_manifest(pair_env), role="eval")
    results = tmp_path / "results"
    path = reference_rows(pairs, results)
    before = path.read_text(encoding="utf-8")
    assert before.count("\n") == 2  # the SOURCE and the REF row of the pair

    def not_cached(pair):
        raise FileNotFoundError(pair.id)

    monkeypatch.setattr("leichtfacile.eval.run.load_pair", not_cached)
    with pytest.raises(FileNotFoundError):
        reference_rows(pairs, results)
    assert path.read_text(encoding="utf-8") == before
    assert [p.name for p in results.iterdir()] == ["REF.jsonl"]  # no temporary file left
