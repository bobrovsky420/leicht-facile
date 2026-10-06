"""The Canton of Zurich's Leichte Sprache prompt as a baseline (conditions C0-ZH-complete
and C0-ZH-condensed, THIRD_PARTY_NOTICES.md)."""

from __future__ import annotations

import json

import pytest

from leichtfacile.eval.dataset import Pair
from leichtfacile.eval.report import render_report
from leichtfacile.eval.run import results_file, run_condition
from leichtfacile.llm.client import LLMClient
from leichtfacile.pipeline.prompts import has_prompt, prompt_versions, render
from leichtfacile.pipeline.stages import ZH_NO_TAGS_NOTE, zh_answer_text, zh_variant
from leichtfacile.schemas import BASELINE_CONDITIONS, CONDITIONS, Draft, PipelineSummary
from leichtfacile.store import Store
from tests.conftest import MODEL, chat_response, make_settings
from tests.pipeline.test_orchestrator import new_job, orchestrator

COMPLETE_LINE = (
    "- Achte immer sehr genau darauf, dass ALLE Informationen aus dem schwer verständlichen "
    "Text in deinem verständlicheren Text enthalten sind. Kürze niemals Informationen. Wo "
    "sinnvoll kannst du zusätzliche Beispiele hinzufügen, um den Text verständlicher zu "
    "machen und relevante Inhalte zu konkretisieren."
)
CONDENSED_LINE = (
    "- Konzentriere dich auf das Wichtigste. Gib die essenziellen Informationen wieder und "
    "lass den Rest weg."
)

ZH_ANSWER = """Hier ist der Text in Leichter Sprache:
<leichtesprache>
Prämien·verbilligung

Sie haben wenig Geld? Dann bekommen Sie Geld für die Kranken·kasse.
Das Gesuch muss bis 31. März 2026 bei der Gemeinde sein.
Die Gebühr ist 20 Franken. Das Amt ist an der Bahnhofstraße.
</leichtesprache>
"""


@pytest.fixture
def store(tmp_path) -> Store:
    s = Store(tmp_path / "test.sqlite")
    yield s
    s.close()


def test_conditions_and_variants() -> None:
    assert CONDITIONS == ("C0", "C0-ZH-complete", "C0-ZH-condensed", "C1", "C2")
    assert {"C0", "C0-ZH-complete", "C0-ZH-condensed"} == BASELINE_CONDITIONS
    assert zh_variant("C0-ZH-complete") == "complete"
    assert zh_variant("C0-ZH-condensed") == "condensed"
    with pytest.raises(ValueError):
        zh_variant("C0")


def test_prompt_is_zurichs_in_both_parts_and_variants() -> None:
    system = render("de", "baseline_zh", part="system", variant="complete", text="")
    assert system.startswith("Du bist ein hilfreicher Assistent, der Texte in Leichte Sprache")
    assert "<leichtesprache> Tags" in system
    complete = render("de", "baseline_zh", part="user", variant="complete", text="QUELLE")
    condensed = render("de", "baseline_zh", part="user", variant="condensed", text="QUELLE")
    for prompt in (system, complete, condensed):
        assert "{{" not in prompt and "{%" not in prompt and "{#" not in prompt
        assert "MIT" not in prompt and "github" not in prompt  # the notice is a comment
    assert complete.startswith("Du bekommst einen schwer verständlichen Text")
    assert COMPLETE_LINE in complete and CONDENSED_LINE not in complete
    assert CONDENSED_LINE in condensed and COMPLETE_LINE not in condensed
    # The two variants differ in the completeness line only.
    assert complete.replace(COMPLETE_LINE, "") == condensed.replace(CONDENSED_LINE, "")
    for prompt in (complete, condensed):
        assert "- Schreibe kurze Sätze mit optimal 8 und höchstens 12 Wörtern." in prompt
        assert "- Eine Textzeile enthält inklusiv Leerzeichen maximal 85 Zeichen." in prompt
        assert prompt.rstrip().endswith("-" * 80 + "\n\nQUELLE")
    assert has_prompt("de", "baseline_zh") and not has_prompt("fr", "baseline_zh")
    assert len(prompt_versions("de")["baseline_zh"]) == 12
    assert prompt_versions("fr")["baseline_zh"] == "none"


def test_answer_text_as_in_zurichs_app() -> None:
    answer = "Gern.\n<leichtesprache>\nDie Straße ist groß.\n</leichtesprache>\nFertig."
    assert zh_answer_text(answer) == ("Die Strasse ist gross.", True)
    two = "<leichtesprache>A</leichtesprache> und <leichtesprache>B</leichtesprache>"
    assert zh_answer_text(two) == ("A\nB", True)
    assert zh_answer_text("  Ohne Tags.  ") == ("Ohne Tags.", False)
    # Their strip_markdown is not applied: underscores in addresses survive.
    assert zh_answer_text("<leichtesprache>info_zh@example.org</leichtesprache>")[0] == (
        "info_zh@example.org"
    )


def test_c0_zh_sends_zurichs_messages_and_keeps_the_tagged_text(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response(ZH_ANSWER))
    job_id = new_job(store, condition="C0-ZH-complete")
    orchestrator(store, endpoint, sleeps).run(job_id)

    job = store.get_job(job_id)
    assert job.status == "needs_review", job.error
    assert [u.stage for u in job.usage] == ["baseline_zh"]
    (body,) = endpoint.chat_bodies()
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["messages"][0]["content"].startswith("Du bist ein hilfreicher Assistent")
    user = body["messages"][1]["content"]
    assert COMPLETE_LINE in user
    assert user.rstrip().endswith("Rechtsgrundlage ist Art. 5 des Einführungsgesetzes.")
    assert body["model"] == MODEL  # the settings of C0: no thinking
    assert body["temperature"] == 0.3 and body["max_tokens"] == 6000

    draft = store.get_artifact(job_id, "draft", Draft)
    assert draft.origin == "baseline"
    assert draft.text().startswith("Prämien·verbilligung")
    assert "Hier ist der Text" not in draft.text()
    assert "Bahnhofstrasse" in draft.text() and "ß" not in draft.text()
    assert all(not b.segment_ids for b in draft.blocks)
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.condition == "C0-ZH-complete"
    assert summary.notes == []
    assert summary.judge_model is None and summary.understand_model is None
    assert len(summary.prompt_versions["baseline_zh"]) == 12


def test_c0_zh_condensed_uses_an_untagged_answer_and_says_so(store, endpoint, sleeps) -> None:
    endpoint.push(chat_response("Sie haben wenig Geld? Dann hilft der Kanton."))
    job_id = new_job(store, condition="C0-ZH-condensed")
    orchestrator(store, endpoint, sleeps).run(job_id)

    assert store.get_job(job_id).status == "needs_review"
    (body,) = endpoint.chat_bodies()
    assert CONDENSED_LINE in body["messages"][1]["content"]
    draft = store.get_artifact(job_id, "draft", Draft)
    assert "Dann hilft der Kanton." in draft.text()
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    assert summary.notes == [ZH_NO_TAGS_NOTE]


def test_results_file_names_the_variant(tmp_path) -> None:
    path = results_file(tmp_path, "C0-ZH-condensed", "swiss-ai/Apertus-v1.5-8B")
    assert path.name == "C0-ZH-condensed_swiss-ai-apertus-v1-5-8b.jsonl"


def test_run_skips_pairs_without_zurichs_prompt(tmp_path, endpoint, sleeps) -> None:
    """Zurich's app has no French prompt: French pairs are skipped, not failed."""
    french = Pair(
        id="syn-fr", lang="fr", url_standard="https://example.org/s", url_easy="https://example.org/e"
    )  # fmt: skip
    settings = make_settings(llm_max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    path = run_condition(
        [french], "C0-ZH-complete", settings=settings, llm=llm, results_dir=tmp_path / "r"
    )
    assert not path.exists() and endpoint.chat_bodies() == []


def test_report_orders_zurichs_baselines_between_c0_and_c1(tmp_path) -> None:
    rows = [
        {"setup": s, "pair_id": "a-de", "role": "eval", "lang": "de", "writer": "m",
         "status": "needs_review"}
        for s in ("C1", "C0-ZH-condensed", "C2", "C0-ZH-complete", "C0")
    ]  # fmt: skip
    (tmp_path / "x.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    report = render_report(tmp_path, role="eval")
    labels = [
        "C0: one prompt (m)",
        "C0-ZH complete: Zurich's prompt, keep everything (m)",
        "C0-ZH condensed: Zurich's prompt, essentials only (m)",
        "C1: fact sheet + draft + rule check (m)",
    ]
    positions = [report.index(label) for label in labels]
    assert positions == sorted(positions)
