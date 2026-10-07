"""The fact-retention diagnosis (eval/diagnose.py) on a hand-built results folder: one
job of each kind, every bucket once."""

from __future__ import annotations

import json
from pathlib import Path

from leichtfacile.eval.diagnose import (
    BUCKETS,
    bucket_table,
    diagnose,
    mentions,
    render_diagnosis,
    to_json,
)
from leichtfacile.rules.values import Value
from leichtfacile.schemas import (
    AnsweredAddition,
    Block,
    Draft,
    DroppedText,
    Fact,
    FactCheck,
    FactSheet,
    Finding,
    JobConfig,
    JudgeReport,
    PipelineSummary,
    RepairRecord,
    RuleFindings,
)
from leichtfacile.store import Store
from tests.pipeline import fixtures as fx


def _fact(fid: str, kind: str, value: str | None, *, keep: bool = True, origin: str = "model"):
    return Fact(id=fid, kind=kind, text=f"Tatsache {fid}", value_norm=value, must_keep=keep,
                origin=origin, segment_ids=["s0002"])  # type: ignore[arg-type]  # fmt: skip


def _draft(version: int, *texts: str) -> Draft:
    blocks = [Block(id=f"b{i:03d}", kind="sentence", text=t) for i, t in enumerate(texts, 1)]
    return Draft(doc_id="d", lang="de", level="A2", version=version, blocks=blocks,
                 parent_version=version - 1 if version > 1 else None)  # fmt: skip


def _rules(version: int, *missing: str) -> RuleFindings:
    findings = [
        Finding(block_id=None, rule_id="FACT-01", severity="error", message="x", fact_id=f)
        for f in missing
    ]
    return RuleFindings(draft_version=version, level="A2", findings=findings)


def _summary(final: int, rounds: int, reason: str, facts_rounds: int = 0) -> PipelineSummary:
    return PipelineSummary(condition="P2", final_version=final, rounds=rounds,
                           facts_rounds=facts_rounds, stop_reason=reason, writer_model="w",
                           blocking_findings=[])  # fmt: skip


def _results(tmp_path: Path) -> Path:
    store = Store(tmp_path / "store.sqlite")
    rows = []

    def job(pair: str, fs: FactSheet) -> str:
        j = store.create_job(JobConfig(condition="P2"), title=pair)
        store.put_artifact(j.id, "source", fx.letter())
        store.put_artifact(j.id, "factsheet", fs)
        rows.append({"pair_id": pair, "job_id": j.id, "role": "dev", "setup": "P2",
                     "status": "needs_review", "writer": "w"})  # fmt: skip
        return j.id

    # Job A, run before the record existed: seven missing facts, one round, the cap.
    facts_a = [
        _fact("f01", "deadline", "2026-03-31"), _fact("f02", "amount", "20"),
        _fact("f03", "contact", "0441234567"), _fact("f04", "amount", "1500"),
        _fact("f05", "deadline", "2026-04-30"), _fact("f06", "other", "10%"),
        _fact("f07", "contact", "info@musterwil.example"),
    ]  # fmt: skip
    a = job("pair-a", FactSheet(doc_id="d", facts=facts_a))
    store.put_artifact(a, "draft", _draft(1, "Hallo."), 1)
    store.put_artifact(a, "rules", _rules(1, *[f.id for f in facts_a if f.id != "f07"]), 1)
    store.put_artifact(a, "draft", _draft(2, "Bis 31. März 2026.", "Das kostet 20 Franken."), 2)
    store.put_artifact(a, "rules", _rules(2, "f03", "f04", "f05", "f06", "f07"), 2)
    store.put_artifact(a, "summary", _summary(2, 1, "a repair round brought no progress"))

    # Job B, with records: dropped by code, a rejected form, not written, lost later.
    facts_b = [
        _fact("f01", "deadline", "2026-03-31"), _fact("f02", "amount", "20"),
        _fact("f03", "contact", "0441234567"), _fact("f04", "amount", "1500"),
        _fact("f05", "amount", "300", keep=False, origin="code"), _fact("f06", "obligation", None),
    ]  # fmt: skip
    b = job("pair-b", FactSheet(doc_id="d", facts=facts_b))
    store.put_artifact(b, "draft", _draft(1, "Bis 31. März 2026."), 1)
    store.put_artifact(b, "rules", _rules(1, "f02", "f03", "f04"), 1)
    store.put_artifact(b, "draft", _draft(2, "Bis 31. März 2026.", "Rufen Sie an: 044 123 45 67.",
                                          "Sie zahlen 1.500 Franken."), 2)  # fmt: skip
    store.put_artifact(b, "rules", _rules(2, "f02", "f04"), 2)
    store.put_artifact(b, "repair", RepairRecord(
        draft_version=2, parent_version=1, requested_facts=["f02", "f03", "f04"],
        additions=[
            AnsweredAddition(after="b001", texts=["Das kostet 20 Franken."], fact_ids=["f02"]),
            AnsweredAddition(after="b001", texts=["Rufen Sie an: 044 123 45 67."],
                             fact_ids=["f03"]),
            AnsweredAddition(after="b001", texts=["Sie zahlen 1.500 Franken."], fact_ids=["f04"]),
        ],
        dropped=[DroppedText(text="Das kostet 20 Franken.", reason="repeat", fact_ids=["f02"])],
    ), 2)  # fmt: skip
    store.put_artifact(b, "draft", _draft(3, "Bis 31. März 2026.", "Rufen Sie an.",
                                          "Sie zahlen 1.500 Franken."), 3)  # fmt: skip
    store.put_artifact(b, "rules", _rules(3, "f02", "f03", "f04"), 3)
    store.put_artifact(b, "repair", RepairRecord(
        draft_version=3, parent_version=2, kind="facts", requested_facts=["f02"],
    ), 3)  # fmt: skip
    store.put_artifact(b, "judge", JudgeReport(draft_version=3, model="j", fact_checks=[
        FactCheck(fact_id="f01", status="present"), FactCheck(fact_id="f06", status="missing"),
    ]), 3)  # fmt: skip
    store.put_artifact(b, "summary", _summary(3, 1, "a facts round brought no progress", 1))

    # Job C: no repair round ran at all.
    c = job("pair-c", FactSheet(doc_id="d", facts=[_fact("f01", "deadline", "2026-03-31")]))
    store.put_artifact(c, "draft", _draft(1, "Hallo."), 1)
    store.put_artifact(c, "rules", _rules(1, "f01"), 1)
    store.put_artifact(c, "summary", _summary(1, 0, "a repair round failed"))

    # Job D: two rounds ran, but v1 stayed final (fewest blocking findings). f01 was
    # written into v3, f02 was asked in the facts round and not written.
    facts_d = [_fact("f01", "deadline", "2026-03-31"), _fact("f02", "amount", "20")]
    d = job("pair-d", FactSheet(doc_id="d", facts=facts_d))
    store.put_artifact(d, "draft", _draft(1, "Hallo."), 1)
    store.put_artifact(d, "rules", _rules(1, "f01", "f02"), 1)
    store.put_artifact(d, "draft", _draft(2, "Hallo.", "Guten Tag."), 2)
    store.put_artifact(d, "rules", _rules(2, "f01", "f02"), 2)
    store.put_artifact(d, "repair", RepairRecord(
        draft_version=2, parent_version=1, requested_blocks=["b001"], requested_facts=[],
    ), 2)  # fmt: skip
    store.put_artifact(d, "draft", _draft(3, "Hallo.", "Guten Tag.", "Bis 31. März 2026."), 3)
    store.put_artifact(d, "rules", _rules(3, "f02"), 3)
    store.put_artifact(d, "repair", RepairRecord(
        draft_version=3, parent_version=2, kind="facts", requested_facts=["f01", "f02"],
        additions=[AnsweredAddition(after="b002", texts=["Bis 31. März 2026."],
                                    fact_ids=["f01"])],
    ), 3)  # fmt: skip
    store.put_artifact(d, "summary", _summary(1, 1, "a facts round brought no progress", 1))
    store.close()
    (tmp_path / "P2_w.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    return tmp_path


def test_every_bucket_once(tmp_path) -> None:
    jobs = {j.pair_id: j for j in diagnose(_results(tmp_path), role="dev")}
    assert set(jobs) == {"pair-a", "pair-b", "pair-c", "pair-d"}

    a = jobs["pair-a"]
    assert not a.recorded and a.checkable == 7 and len(a.missing) == 5
    buckets = {m.fact_id: (m.bucket, m.reason) for m in a.missing}
    assert buckets["f06"][0] == "a" and "cap" in buckets["f06"][1]  # behind f01 f05 f02 f04 f03
    assert buckets["f07"] == ("a", "never flagged by FACT-01 in the stored findings")
    for fid in ("f03", "f04", "f05"):
        assert buckets[fid][0] == "x" and "not recorded" in buckets[fid][1], fid
    assert {m.asked_in[0] for m in a.missing if m.bucket == "x"} == {2}

    b = jobs["pair-b"]
    assert b.recorded and b.final_version == 3 and b.facts_rounds == 1
    by_id = {m.fact_id: m for m in b.missing}
    assert by_id["f02"].bucket == "d" and by_id["f02"].asked_in == [2, 3]
    assert by_id["f03"].bucket == "l" and "gone in v3" in by_id["f03"].reason
    assert by_id["f04"].bucket == "b" and by_id["f04"].answers == ["Sie zahlen 1.500 Franken."]
    assert "digits or words are there" in by_id["f04"].reason
    assert b.background_lost == [
        {"fact_id": "f05", "kind": "amount", "value": "300", "text": "Tatsache f05",
         "marked_by": "code completion"}
    ]  # fmt: skip
    assert b.judge_only_missing == 1

    c = jobs["pair-c"]
    (only,) = c.missing
    assert only.bucket == "a" and only.reason == "no repair round ran (a repair round failed)"

    d = jobs["pair-d"]
    by_id = {m.fact_id: m for m in d.missing}
    assert by_id["f01"].bucket == "k"
    assert by_id["f01"].reason == "in v3, but v1 of 3 is final (a facts round brought no progress)"
    assert by_id["f02"].bucket == "d" and by_id["f02"].asked_in == [3]
    assert by_id["f02"].reason.endswith("(v1 of 3 is final: a facts round brought no progress)")

    table = bucket_table(list(jobs.values()))
    assert "4 jobs, 14 checkable must-keep facts, 11 missing" in table
    assert "| x: asked for, answer not recorded | 3 | 27 % |" in table
    assert "| k: written into a version not kept as final | 1 | 9 % |" in table
    assert (
        "| a: never asked for, behind the cap of missing facts per round (5 in a repair round, "
        "MAX_MISSING_PER_FACTS_ROUND in a facts round) | 1 |" in table
    )
    assert (
        "Background facts whose value is not in the final text (bucket e, for reading): 1" in table
    )
    report = render_diagnosis(list(jobs.values()), details=True)
    assert "| pair-b | v3 / 3 | 1 + 1 facts |" in report
    assert "    - written: Sie zahlen 1.500 Franken." in report
    assert "Tatsache f05" in report and "Tatsache f05" not in render_diagnosis(
        list(jobs.values()), details=False
    )
    assert json.loads(to_json(list(jobs.values())))[0]["pair_id"] == "pair-a"
    assert set(BUCKETS) == {"a", "b", "c", "d", "k", "l", "x"}


def test_a_dropped_answer_is_bucket_c(tmp_path) -> None:
    """The same job B with the one answered text for f04 dropped by code."""
    results = _results(tmp_path)
    store = Store(results / "store.sqlite")
    (job_id,) = [j.id for j in store.list_jobs() if j.title == "pair-b"]
    record = store.get_artifact(job_id, "repair", RepairRecord, version=2)
    record.dropped.append(DroppedText(text="Sie zahlen 1.500 Franken.", reason="example"))
    store.put_artifact(job_id, "repair", record, 2)
    store.close()
    (b,) = [j for j in diagnose(results, role="dev") if j.pair_id == "pair-b"]
    f04 = next(m for m in b.missing if m.fact_id == "f04")
    assert f04.bucket == "c" and "example" in f04.reason


def test_mentions_tells_exact_from_loose() -> None:
    date = Value("date", "2026-03-31")
    assert mentions(date, "Bis 31.3.2026.", "de") == "exact"
    assert mentions(date, "Bis Ende März 2026, am 31.", "de") == "loose"
    assert mentions(date, "Bis 30. April 2026.", "de") is None
    amount = Value("amount", "1500")
    assert mentions(amount, "Sie zahlen 1'500 Franken.", "de") == "exact"
    assert mentions(amount, "Sie zahlen 1.500 Franken.", "de") == "loose"
    assert mentions(amount, "Sie zahlen 150 Franken.", "de") is None
    phone = Value("phone", "0441234567")
    assert mentions(phone, "Telefon 044 123 45 67", "de") == "exact"
    assert mentions(phone, "Telefon 0441234567.", "de") == "exact"
    email = Value("email", "info@musterwil.example")
    assert mentions(email, "Schreiben Sie an musterwil.example.", "de") == "loose"


def test_the_cli_prints_the_table_and_writes_the_files(tmp_path, capsys) -> None:
    from leichtfacile.cli import main

    results = _results(tmp_path)
    code = main([
        "eval", "diagnose", "--results", str(results), "--role", "dev",
        "--out", str(tmp_path / "diagnosis.md"), "--json", str(tmp_path / "diagnosis.json"),
    ])  # fmt: skip
    out = capsys.readouterr().out
    assert code == 0 and "| Bucket | Facts | Share of the missing |" in out
    assert "Tatsache" not in out  # the details stay in the file
    assert "Tatsache f05" in (tmp_path / "diagnosis.md").read_text(encoding="utf-8")
    assert len(json.loads((tmp_path / "diagnosis.json").read_text(encoding="utf-8"))) == 4
