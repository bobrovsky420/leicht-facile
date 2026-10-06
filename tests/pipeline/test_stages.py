"""Stage helpers that need no model: parsing, linking, repairs, prompts, blocks."""

from __future__ import annotations

import re

import pytest

from leichtfacile.pipeline import render as r
from leichtfacile.pipeline.models import RepairOut, UnderstandOut, WriteOut, normalize_id
from leichtfacile.pipeline.prompts import PROMPTS_DIR, examples, level_name, render
from leichtfacile.pipeline.stages import (
    RepairRequest,
    apply_repairs,
    drop_repeats,
    link_facts,
    split_sections,
    text_to_blocks,
    to_factsheet,
)
from leichtfacile.rules import check_draft, style_guide
from leichtfacile.schemas import Block, Draft, Segment, SourceDocument, SourceInfo
from tests.pipeline import fixtures as fx


@pytest.mark.parametrize(
    ("raw", "prefix", "width", "expected"),
    [("s4", "s", 4, "s0004"), ("S0004", "s", 4, "s0004"), ("4", "s", 4, "s0004"),
     ("f1", "f", 2, "f01"), ("b005.1", "b", 3, "b005.1"), ("weird", "s", 4, "weird")],
)  # fmt: skip
def test_normalize_id(raw, prefix, width, expected) -> None:
    assert normalize_id(raw, prefix, width) == expected


def test_lenient_understand_parsing() -> None:
    out = UnderstandOut.model_validate(fx.UNDERSTAND)
    fs = to_factsheet(out, "doc")
    assert [f.kind for f in fs.facts] == ["deadline", "amount", "contact"]
    assert fs.facts[0].segment_ids == ["s0003"]  # a string became a list
    assert fs.facts[2].must_keep is True  # default


def test_write_output_rejects_empty_drafts_and_strips_markdown() -> None:
    with pytest.raises(ValueError):
        WriteOut.model_validate({"blocks": []})
    out = WriteOut.model_validate({"blocks": [{"kind": "Bullet", "text": "- Ihr Ausweis"}]})
    assert out.blocks[0].kind == "list_item" and out.blocks[0].text == "Ihr Ausweis"


def test_link_facts_adds_values_found_by_code() -> None:
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), "doc")
    draft = Draft(doc_id="doc", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Es kostet 20 Franken.", fact_ids=["f99"]),
    ])  # fmt: skip
    linked = link_facts(draft, fs)
    assert linked.blocks[0].fact_ids == ["f02"]  # f99 does not exist, f02 is the value


def test_apply_repairs_splits_and_adds_blocks() -> None:
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), "doc")
    draft = Draft(doc_id="doc", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Alt eins.", fact_ids=["f01"],
              segment_ids=["s0003"]),
        Block(id="b002", kind="sentence", text="Alt zwei.", segment_ids=["s0004"]),
    ])  # fmt: skip
    out = RepairOut.model_validate({
        "repairs": [{"id": "b1", "texts": ["Neu eins.", "Neu eins b."]},
                    {"id": "b002", "texts": ["Nicht markiert."]}],
        "additions": [{"after": "b001", "texts": ["Neu drei."], "fact_ids": ["f03", "f77"]}],
    })  # fmt: skip
    new = apply_repairs(draft, out, RepairRequest({"b001": ["x"]}, []), fs)
    assert [(b.id, b.text) for b in new.blocks] == [
        ("b001", "Neu eins."), ("b001.1", "Neu eins b."), ("b001.2", "Neu drei."),
        ("b002", "Alt zwei."),
    ]  # fmt: skip
    assert new.blocks[1].fact_ids == ["f01"] and new.blocks[2].fact_ids == ["f03"]
    assert new.version == 2 and new.parent_version == 1 and new.origin == "repair"


def test_text_to_blocks() -> None:
    blocks = text_to_blocks(fx.BASELINE_TEXT, "de")
    assert blocks[0].kind == "heading" and blocks[0].text == "Prämien·verbilligung"
    assert [b.text for b in blocks if b.kind == "list_item"] == [
        "Bis 31. März 2026",
        "Gebühr: 20 Franken",
    ]


def test_split_sections_keeps_every_segment_once() -> None:
    segments = []
    for part in range(4):
        segments.append(
            Segment(
                id=f"s{len(segments) + 1:04d}",
                kind="heading",
                text=f"Teil {part}",
                heading_level=2,
                para=part * 10,
            )
        )
        for i in range(30):
            segments.append(
                Segment(
                    id=f"s{len(segments) + 1:04d}",
                    kind="paragraph",
                    text="Wort " * 20,
                    para=part * 10 + 1 + i,
                )
            )
    doc = SourceDocument(id="d", lang="de", source=SourceInfo(type="text"), segments=segments)
    sections = split_sections(doc, max_words=700)  # each part has about 600 words
    assert len(sections) == 4
    assert [s.id for _, segs in sections for s in segs] == [s.id for s in segments]
    assert sections[1][0] == "Teil 1"


def test_prompts_render_completely() -> None:
    source = fx.letter()
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), source.id)
    draft = Draft(doc_id=source.id, lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Das kostet 20 Franken.", segment_ids=["s0004"])
    ])  # fmt: skip
    common = {"level_name": level_name("de", "A2"), "level": "A2"}
    prompts = {
        "understand": render("de", "understand", **common, source=r.source_text(source)),
        "write": render("de", "write", **common, style_guide=style_guide("de", "A2"),
                        examples=examples("de"), section="", factsheet=r.factsheet_text(fs),
                        source=r.source_text(source)),
        "judge": render("de", "judge", **common, factsheet=r.factsheet_text(fs),
                        source=r.source_text(source), draft=r.draft_lines(draft),
                        glossary=r.glossary_text(draft)),
        "repair": render("de", "repair", **common, style_guide=style_guide("de", "A2"),
                         flagged="[b001] ...", missing="", factsheet=r.factsheet_text(fs),
                         draft=r.draft_lines(draft), source=r.source_text(source)),
    }  # fmt: skip
    for stage, text in prompts.items():
        assert "{{" not in text and "{%" not in text, stage
    assert "# [s0001] Prämienverbilligung 2026" in prompts["understand"]
    assert "- f01 (deadline, must_keep): " in prompts["write"]
    assert "höchstens 12 Wörter" in prompts["write"]
    assert "Fassung in Leichter Sprache" in prompts["write"]  # the examples
    assert "Die fehlenden Tatsachen" not in prompts["repair"]  # no missing facts given


def test_prompt_files_use_plain_hyphens() -> None:
    for path in PROMPTS_DIR.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert not re.search("[\u2013\u2014]", text), path


EASY_MARKERS = {"de": "Fassung in Leichter Sprache:", "fr": "Version en FALC :"}


@pytest.mark.parametrize("lang", sorted(EASY_MARKERS))
def test_few_shot_examples_follow_the_rules(lang: str) -> None:
    """The style anchors must not teach what the checker forbids."""
    text = examples(lang)
    easy = []
    for part in text.split("---"):
        easy += [ln for ln in part.split(EASY_MARKERS[lang])[1].splitlines() if ln.strip()]
    assert len(easy) >= 10
    draft = Draft(doc_id="ex", lang=lang, level="A2", blocks=[
        Block(id=f"b{i:03d}", kind="heading" if ln.endswith("?") else "sentence", text=ln)
        for i, ln in enumerate(easy, 1)
    ])  # fmt: skip
    errors = [f for f in check_draft(draft).findings if f.severity == "error"]
    assert errors == [], errors


def test_french_prompts_render_completely_with_french_labels() -> None:
    source = SourceDocument(
        id="d",
        lang="fr",
        source=SourceInfo(type="text"),
        segments=[
            Segment(id="s0001", kind="heading", text="Taxe 2026", heading_level=1, para=0),
            Segment(id="s0002", kind="paragraph", text="La taxe coûte CHF 20.-.", para=1),
        ],
    )
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), source.id)
    draft = Draft(doc_id=source.id, lang="fr", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="La taxe coûte 20 francs.", segment_ids=["s0002"],
              fact_ids=["f02"])
    ])  # fmt: skip
    common = {"level_name": level_name("fr", "A2"), "level": "A2"}
    prompts = {
        "understand": render("fr", "understand", **common, source=r.source_text(source)),
        "write": render("fr", "write", **common, style_guide=style_guide("fr", "A2"),
                        examples=examples("fr"), section="",
                        factsheet=r.factsheet_text(fs, lang="fr"), source=r.source_text(source)),
        "judge": render("fr", "judge", **common, factsheet=r.factsheet_text(fs, lang="fr"),
                        source=r.source_text(source), draft=r.draft_lines(draft),
                        glossary=r.glossary_text(draft)),
        "repair": render("fr", "repair", **common, style_guide=style_guide("fr", "A2"),
                         flagged="[b001] ...", missing="- f01: ...",
                         factsheet=r.factsheet_text(fs, lang="fr"),
                         draft=r.draft_lines(draft), source=r.source_text(source)),
        "baseline": render("fr", "baseline", **common, text=source.text()),
    }  # fmt: skip
    for stage, text in prompts.items():
        assert "{{" not in text and "{%" not in text, stage
    assert "en FALC" in prompts["understand"]
    assert "au plus 15 mots" in prompts["write"]
    assert "Version en FALC" in prompts["write"]  # the examples
    assert "Faits :" in prompts["write"] and "Tatsachen" not in prompts["write"]
    assert "(faits : f02 ; source : s0002)" in prompts["judge"]
    assert "(vide)" in prompts["judge"]  # the empty glossary
    assert "Les faits qui manquent" in prompts["repair"]
    assert prompts["baseline"].startswith("Écrivez ce texte en FALC :")


def test_repairs_do_not_repeat_sentences() -> None:
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), "doc")
    draft = Draft(
        doc_id="doc",
        lang="de",
        level="A2",
        blocks=[
            Block(id="b001", kind="sentence", text="Das Gesuch muss bis 31. März 2026 dort sein."),
            Block(id="b002", kind="sentence", text="Alt."),
        ],
    )
    out = RepairOut.model_validate(
        {
            "repairs": [
                {"id": "b002", "texts": ["Neu.", "Das Gesuch muss bis 31. März 2026 dort sein"]}
            ],
            "additions": [
                {"after": "b002", "texts": ["Das Gesuch muss bis 31. März 2026 dort sein."]}
            ],
        }
    )
    new = apply_repairs(draft, out, RepairRequest({"b002": ["x"]}, []), fs)
    assert [b.text for b in new.blocks] == ["Das Gesuch muss bis 31. März 2026 dort sein.", "Neu."]


def test_an_addition_that_repeats_a_later_repaired_block_is_dropped() -> None:
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), "doc")
    draft = Draft(doc_id="doc", lang="fr", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Appelez le 022 123 45 67."),
        Block(id="b002", kind="sentence", text="Ecrivez a rip@exempleville.example."),
    ])  # fmt: skip
    out = RepairOut.model_validate({
        "repairs": [{"id": "b002", "texts": ["Écrivez à rip@exempleville.example."]}],
        "additions": [{"after": "b001", "texts": ["Écrivez à rip@exempleville.example."]}],
    })  # fmt: skip
    new = apply_repairs(draft, out, RepairRequest({"b002": ["x"]}, []), fs)
    assert [b.text for b in new.blocks].count("Écrivez à rip@exempleville.example.") == 1
    assert [b.id for b in new.blocks] == ["b001", "b001.1"]  # ids stay stable


def test_a_repeated_sentence_is_dropped_with_its_empty_heading() -> None:
    blocks = [
        Block(id="b001", kind="heading", text="Que devez-vous faire ?"),
        Block(id="b002", kind="sentence", text="Payez avant le 31 mars 2027.",
              fact_ids=["f01"], segment_ids=["s0003"]),
        Block(id="b003", kind="heading", text="Jusqu'à quand ?"),
        Block(id="b004", kind="sentence", text="Payez  avant le 31 mars 2027",
              fact_ids=["f02"], segment_ids=["s0004"]),
        Block(id="b005", kind="heading", text="Qui peut vous aider ?"),
        Block(id="b006", kind="sentence", text="Appelez le 022 123 45 67."),
    ]  # fmt: skip
    out = drop_repeats(blocks)
    assert [(b.id, b.text) for b in out] == [
        ("b001", "Que devez-vous faire ?"),
        ("b002", "Payez avant le 31 mars 2027."),
        ("b003", "Qui peut vous aider ?"),
        ("b004", "Appelez le 022 123 45 67."),
    ]
    assert out[1].fact_ids == ["f01", "f02"] and out[1].segment_ids == ["s0003", "s0004"]
    assert drop_repeats(out) == out  # nothing to drop: unchanged


def test_a_bare_list_is_read_as_the_main_list() -> None:
    from leichtfacile.pipeline.models import JudgeOut

    judge = JudgeOut.model_validate([{"fact_id": "f1", "status": "present", "block_ids": ["b2"]}])
    assert judge.fact_checks[0].fact_id == "f01" and judge.fact_checks[0].block_ids == ["b002"]
    with pytest.raises(ValueError):
        JudgeOut.model_validate({"text": "a fragment", "segment_ids": ["s0001"]})
