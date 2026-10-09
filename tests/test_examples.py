"""Example sources and their job settings (data/examples/README.md)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leichtfacile.examples import example_config, example_sources, open_problems
from leichtfacile.schemas import JobConfig, JudgeReport, PipelineSummary, RuleFindings

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "examples"


def test_a_source_without_a_settings_file_has_none(tmp_path: Path) -> None:
    (tmp_path / "brief.txt").write_text("Text", encoding="utf-8")
    assert example_config(tmp_path / "brief.txt") == {}


def test_the_settings_file_next_to_a_source_sets_the_job(tmp_path: Path) -> None:
    (tmp_path / "entscheid.txt").write_text("Text", encoding="utf-8")
    settings = {"mode": "decision", "addressee": "Lea Muster"}
    (tmp_path / "entscheid.json").write_text(json.dumps(settings), encoding="utf-8")
    assert example_config(tmp_path / "entscheid.txt") == settings


def test_a_settings_file_with_other_keys_is_refused(tmp_path: Path) -> None:
    (tmp_path / "entscheid.txt").write_text("Text", encoding="utf-8")
    (tmp_path / "entscheid.json").write_text('{"modus": "decision"}', encoding="utf-8")
    with pytest.raises(ValueError, match="modus"):
        example_config(tmp_path / "entscheid.txt")


def test_the_settings_files_are_no_example_texts() -> None:
    ids = [e["id"] for e in example_sources(EXAMPLES)]
    assert "entscheid-beistandschaft-musterwil" in ids
    assert len(ids) == len(set(ids))  # the .json next to the .txt is not listed


def test_the_kesb_decision_runs_in_decision_mode() -> None:
    config = JobConfig.model_validate(
        example_config(EXAMPLES / "sources" / "entscheid-beistandschaft-musterwil.txt")
    )
    assert config.mode == "decision"
    assert config.addressee == "Lea Muster"
    assert config.notice and "Massgebend ist der Entscheid" in config.notice


def test_example_sources_carry_the_decision_settings() -> None:
    by_id = {e["id"]: e for e in example_sources(EXAMPLES)}
    kesb = by_id["entscheid-beistandschaft-musterwil"]
    assert kesb["mode"] == "decision" and kesb["addressee"] == "Lea Muster"
    assert kesb["notice"].endswith("Massgebend ist der Entscheid.")
    assert "mode" not in by_id["praemienverbilligung-brief"]


def _rules(*severities: str) -> RuleFindings:
    findings = [
        {"block_id": "b001", "rule_id": "LEN-01", "severity": s, "message": "m"} for s in severities
    ]
    return RuleFindings.model_validate({"draft_version": 1, "level": "A2", "findings": findings})


def test_open_problems_count_rule_errors_and_judge_problems() -> None:
    judge = JudgeReport.model_validate(
        {
            "draft_version": 1,
            "model": "m",
            "fact_checks": [
                {"fact_id": "f01", "status": "present"},
                {"fact_id": "f02", "status": "missing"},
            ],
            "unsupported": [{"block_id": "b001", "note": "n"}],
        }
    )
    assert open_problems(_rules("warn", "info"), None) == 0
    assert open_problems(_rules("error", "warn"), judge) == 3


# The shipped bundles whose final draft still shows errors: the 8B's output on these
# letters, and no rebuild has been clean yet (PLAN.md WP8). Strict: a clean rebuild
# fails here until its name leaves the set.
KNOWN_PROBLEMS = {"praemienverbilligung-brief", "reduction-primes-lettre"}


def _example_job(path: Path) -> object:
    marks = []
    if path.stem in KNOWN_PROBLEMS:
        marks.append(pytest.mark.xfail(strict=True, reason="shipped with errors, PLAN.md WP8"))
    return pytest.param(path, id=path.stem, marks=marks)


@pytest.mark.parametrize(
    "path", [_example_job(p) for p in sorted((EXAMPLES / "jobs").glob("*.json"))]
)
def test_the_example_jobs_show_no_errors(path: Path) -> None:
    """A first-time visitor reads a red error count as a fault of the application."""
    bundle = json.loads(path.read_text(encoding="utf-8"))
    final = PipelineSummary.model_validate(bundle["summary"]).final_version
    rules = [RuleFindings.model_validate(r) for r in bundle["rule_findings"]]
    judges = [JudgeReport.model_validate(j) for j in bundle["judge_reports"]]
    rules_final = next((r for r in rules if r.draft_version == final), None)
    judge_final = next((j for j in judges if j.draft_version == final), None)
    assert rules_final is not None
    assert open_problems(rules_final, judge_final) == 0
