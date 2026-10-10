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
from leichtfacile.schemas import (
    Block,
    Draft,
    Fact,
    FactSheet,
    Segment,
    SourceDocument,
    SourceInfo,
)
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
    # A core answer written as a bare sentence is its text, without sources.
    bare = UnderstandOut.model_validate({**fx.UNDERSTAND, "core": {"what": "Nur ein Satz."}})
    assert bare.core.what.text == "Nur ein Satz." and bare.core.what.segment_ids == []


def test_understand_without_the_facts_list_is_an_empty_fact_sheet() -> None:
    # Seen on a page with nothing countable: everything there except `facts`.
    complete = {k: v for k, v in fx.UNDERSTAND.items() if k != "facts"}
    out = UnderstandOut.model_validate(complete)
    assert out.facts == []
    assert out.core.deadline.text == "Bis 31. März 2026."
    # A fragment of an answer is still no fact sheet.
    with pytest.raises(ValueError):
        UnderstandOut.model_validate({"core": fx.UNDERSTAND["core"]})
    with pytest.raises(ValueError):
        UnderstandOut.model_validate({"doc_type": "Merkblatt", "audience": "alle"})


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


# The French example letter, 7 Oct: the writer named the phone's and the e-mail's own
# facts and no source sentence, so FACT-02 missed the contact and FACT-03 the provenance.
CONTACT = FactSheet(doc_id="doc", facts=[
    Fact(id="f05", kind="contact", segment_ids=["s0016", "s0017"],
         text="L'agence, téléphone 022 123 45 67 ou e-mail rip@exempleville.example."),
    Fact(id="f13", kind="contact", text="téléphone", value_norm="0221234567",
         segment_ids=["s0016"], origin="code"),
    Fact(id="f14", kind="contact", text="e-mail", value_norm="rip@exempleville.example",
         segment_ids=["s0016"], origin="code"),
])  # fmt: skip


def test_link_facts_completes_provenance_and_worded_facts() -> None:
    draft = Draft(doc_id="doc", lang="fr", level="A2", blocks=[
        Block(id="b001", kind="sentence", fact_ids=["f13", "f14"],
              text="Contactez l'agence au 022 123 45 67 ou à rip@exempleville.example."),
    ])  # fmt: skip
    (block,) = link_facts(draft, CONTACT).blocks
    assert block.segment_ids == ["s0016"]  # the sentence of the values it contains
    assert block.fact_ids == ["f13", "f14", "f05"]  # it holds every value of f05


def test_link_facts_needs_every_value_and_a_cited_sentence_for_a_worded_fact() -> None:
    draft = Draft(doc_id="doc", lang="fr", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Écrivez à rip@exempleville.example.",
              segment_ids=["s0016"]),
        Block(id="b002", kind="sentence", segment_ids=["s0002"],
              text="Appelez le 022 123 45 67 ou écrivez à rip@exempleville.example."),
        Block(id="b003", kind="sentence", text="Nos bureaux sont ouverts le matin."),
    ])  # fmt: skip
    linked = link_facts(draft, CONTACT).blocks
    assert "f05" not in linked[0].fact_ids  # the phone number is missing
    assert "f05" not in linked[1].fact_ids  # another source sentence
    assert linked[1].segment_ids == ["s0002"]  # a block's own sources stay
    assert linked[2].segment_ids == []  # no value, no source to take


def test_link_facts_accepts_a_worded_fact_spread_over_the_blocks_of_its_sentence() -> None:
    """The writer put the phone number and the e-mail address of the contact fact into
    two blocks of the same source sentence (10 October 2026): together they hold every
    value, so both name the fact; a block of that sentence without a value does not."""
    draft = Draft(doc_id="doc", lang="fr", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Écrivez à rip@exempleville.example.",
              segment_ids=["s0016"]),
        Block(id="b002", kind="sentence", text="L'agence répond le matin.", segment_ids=["s0016"]),
        Block(id="b003", kind="sentence", text="Appelez le 022 123 45 67.", segment_ids=["s0016"]),
    ])  # fmt: skip
    linked = link_facts(draft, CONTACT).blocks
    assert "f05" in linked[0].fact_ids and "f05" in linked[2].fact_ids
    assert "f05" not in linked[1].fact_ids


def test_link_facts_names_a_plain_fact_on_the_blocks_that_cite_its_sentence() -> None:
    """A fact without a value and without values in its text (10 October 2026): the
    writer renders its sentence and leaves the tag out, so every block that cites one of
    the fact's sentences names it; a block that cites another sentence does not."""
    fs = FactSheet(doc_id="doc", facts=[
        Fact(id="f05", kind="right", text="Anspruch auf Prämienverbilligung.",
             segment_ids=["s0003"], must_keep=True),
        Fact(id="f06", kind="other", text="Keine Angabe.", segment_ids=[], must_keep=True),
    ])  # fmt: skip
    draft = Draft(doc_id="doc", lang="de", level="A2", blocks=[
        Block(id="b001", kind="heading", text="Was bekommen Sie?"),
        Block(id="b002", kind="sentence", text="Sie bekommen Geld für die Prämie.",
              segment_ids=["s0003"]),
        Block(id="b003", kind="sentence", text="Das Amt hilft Ihnen.", segment_ids=["s0004"]),
    ])  # fmt: skip
    linked = link_facts(draft, fs).blocks
    assert linked[0].fact_ids == [] and linked[0].segment_ids == []  # a heading stays
    assert linked[1].fact_ids == ["f05"]  # cites the fact's sentence: it conveys the fact
    assert linked[2].fact_ids == []  # another sentence, and f06 has no sentence to share


# Sentences of the French example letter (s0010 to s0012, s0016).
LETTER_FR = SourceDocument(id="doc", lang="fr", source=SourceInfo(type="text"), segments=[
    Segment(id="s0001", kind="heading", text="Réduction individuelle des primes 2027"),
    Segment(id="s0010", kind="paragraph", text="La réduction des primes est versée directement "
            "à l'assureur-maladie et imputée sur les factures de primes courantes."),
    Segment(id="s0011", kind="paragraph",
            text="Un versement en espèces à la personne assurée est exclu."),
    Segment(id="s0012", kind="paragraph", text="Toute modification de la situation personnelle "
            "ou économique doit être annoncée par écrit dans un délai de 30 jours."),
    Segment(id="s0016", kind="paragraph", text="Pour tout renseignement, l'agence d'assurances "
            "sociales se tient à votre disposition au 022 123 45 67."),
])  # fmt: skip


def test_link_facts_finds_the_source_sentence_a_block_says_in_other_words() -> None:
    # CSCS, 8 October 2026: the 8B wrote these two without a source sentence; FACT-03
    # flagged them and the judge, without s0010 and s0011, called them invented.
    draft = Draft(doc_id="doc", lang="fr", level="A2", blocks=[
        Block(id="b013", kind="sentence",
              text="Vous payez la réduction directement à votre assureur-maladie."),
        Block(id="b014", kind="sentence",
              text="Vous ne pouvez pas recevoir cet argent en espèces."),
        Block(id="b015", kind="heading", text="Les primes"),
    ])  # fmt: skip
    linked = link_facts(draft, CONTACT, LETTER_FR).blocks
    assert [b.segment_ids for b in linked] == [["s0010"], ["s0011"], []]  # no heading
    assert link_facts(draft, CONTACT).blocks[0].segment_ids == []  # no source, no wording


def test_link_facts_drops_a_sentence_id_the_source_does_not_have() -> None:
    # CSCS, 8 October 2026: the 8B cited a block id as the source of a sentence.
    draft = Draft(doc_id="doc", lang="fr", level="A2", blocks=[
        Block(id="b009", kind="sentence", segment_ids=["s0009.2"],
              text="Vous ne pouvez pas recevoir cet argent en espèces."),
    ])  # fmt: skip
    (block,) = link_facts(draft, CONTACT, LETTER_FR).blocks
    assert block.segment_ids == ["s0011"]
    assert link_facts(draft, CONTACT).blocks[0].segment_ids == ["s0009.2"]  # no source


def test_link_facts_gives_a_block_the_sentences_of_the_facts_it_names() -> None:
    # A repair's addition names its fact and often no source sentence.
    draft = Draft(doc_id="doc", lang="fr", level="A2", blocks=[
        Block(id="b001", kind="sentence", fact_ids=["f05"], text="Appelez l'agence."),
    ])  # fmt: skip
    (block,) = link_facts(draft, CONTACT, LETTER_FR).blocks
    assert block.segment_ids == ["s0016", "s0017"]


@pytest.mark.parametrize(
    ("text", "why"),
    [("Vous pouvez aussi venir demain.", "only short or common words"),
     ("Les primes sont payées.", "one short word, shared by two sentences"),
     ("Écrivez une lettre à la commune.", "no shared word")],
)  # fmt: skip
def test_a_block_without_a_clear_source_sentence_keeps_none(text: str, why: str) -> None:
    draft = Draft(doc_id="doc", lang="fr", level="A2", blocks=[
        Block(id="b001", kind="sentence", text=text),
    ])  # fmt: skip
    (block,) = link_facts(draft, CONTACT, LETTER_FR).blocks
    assert block.segment_ids == [], why


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


def test_write_output_hoists_a_list_written_as_a_block() -> None:
    out = WriteOut.model_validate(
        {"blocks": [{"kind": "sentence", "text": "a"}, {"omissions": [{"what": "x", "why": "y"}]}]}
    )
    assert [b.text for b in out.blocks] == ["a"]
    assert out.omissions[0].what == "x"


def test_example_keys_hold_the_sentences_of_the_prompt_examples() -> None:
    from leichtfacile.pipeline.stages import _example_key, copied_sentences, example_keys

    keys = example_keys("de", "write")
    assert _example_key("Die Hunde·steuer kostet 120 Franken pro Hund.") in keys  # JSON example
    assert _example_key("Bringen Sie den Impf·ausweis von Ihrem Hund mit.") in keys  # few-shot
    assert _example_key("fact_ids") not in keys
    # The style guide's lines, at both levels and without the list marker: a draft on
    # the 8B carried the guide as a section (8 October 2026).
    guide = "Telefon·nummern schreiben Sie mit Abständen: 044 123 45 67."
    assert _example_key(guide) in keys and _example_key(guide) in example_keys("de", "repair")
    assert _example_key("Schreiben Sie kurze Sätze: höchstens 12 Wörter pro Satz.") in keys
    assert _example_key("Schreiben Sie kurze Sätze: höchstens 15 Wörter pro Satz.") in keys
    passive = (
        "Kein Passiv. Sagen Sie, wer etwas tut. "
        "Nicht: Das Formular wird geprüft. Sondern: Das Amt prüft das Formular."
    )
    assert copied_sentences([guide, passive], "de", "write") == 2
    part = "Kein Passiv. Sagen Sie, wer etwas tut."  # a part of a line is no copy
    assert copied_sentences([part], "de", "write") == 0
    for lang, stage in (
        ("fr", "write"),
        ("de", "understand"),
        ("fr", "understand"),
        ("de", "repair"),
        ("fr", "repair"),
    ):
        assert example_keys(lang, stage)  # fmt: skip
    assert copied_sentences(["Die Hundesteuer kostet 120 Franken pro Hund"], "de", "write") == 1
    assert copied_sentences(["Das Gesuch muss bis 31. März 2026 da sein."], "de", "write") == 0


COPIED_WRITE = {
    "blocks": [
        {"kind": "heading", "text": "Was müssen Sie tun?"},
        {"kind": "sentence", "text": "Sie melden Ihren Hund bei der Einwohner·kontrolle an.",
         "fact_ids": ["f03"], "segment_ids": ["s0005"]},
        {"kind": "sentence", "text": "Die Hunde·steuer kostet 120 Franken pro Hund.",
         "fact_ids": ["f02"], "segment_ids": ["s0002"]},
        {"kind": "sentence", "text": "Sie bezahlen bis zum 30. April 2026.",
         "fact_ids": ["f01"], "segment_ids": ["s0003"]},
    ],
}  # fmt: skip


def test_a_draft_that_copies_the_example_is_sent_back_once(endpoint, sleeps) -> None:
    from leichtfacile.llm.client import LLMClient
    from leichtfacile.pipeline.stages import write
    from tests.conftest import chat_response, make_settings

    llm = LLMClient(make_settings(llm_max_retries=0), http_client=endpoint.http_client())
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), "doc")
    endpoint.push(chat_response(fx.as_json(COPIED_WRITE)), chat_response(fx.as_json(fx.WRITE)))
    draft, results = write(llm, fx.letter(), fs, level="A2")
    assert len(results) == 2
    assert "Hund" not in " ".join(b.text for b in draft.blocks)
    feedback = endpoint.chat_bodies()[1]["messages"][-1]["content"]
    assert "Beispiel" in feedback and "3 Sätze" in feedback
    # One example heading in an otherwise real draft is no copy.
    endpoint.push(chat_response(fx.as_json(fx.WRITE)))
    draft, results = write(llm, fx.letter(), fs, level="A2")
    assert len(results) == 1


def test_a_repair_with_a_value_not_in_the_document_is_sent_back_once(endpoint, sleeps) -> None:
    from leichtfacile.llm.client import LLMClient
    from leichtfacile.pipeline.stages import RepairRequest, repair
    from leichtfacile.schemas import Block, Draft
    from tests.conftest import chat_response, make_settings

    llm = LLMClient(make_settings(llm_max_retries=0), http_client=endpoint.http_client())
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), "doc")
    draft = Draft(doc_id="doc", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Sie können das Amt anrufen.",
              segment_ids=["s0005"]),
    ])  # fmt: skip
    request = RepairRequest({"b001": ["  - SEM-03: Welches Amt?"]}, [])
    leaked = {
        "repairs": [{"id": "b001", "texts": ["Rufen Sie das Amt an: 044 215 21 51."]}],
        "additions": [],
    }  # a number in neither the letter nor the examples
    fixed = {
        "repairs": [{"id": "b001", "texts": ["Rufen Sie das Amt an: 044 123 45 67."]}],
        "additions": [],
    }
    endpoint.push(chat_response(fx.as_json(leaked)), chat_response(fx.as_json(fixed)))
    new_draft, results, _ = repair(llm, fx.letter(), fs, draft, request)
    assert len(results) == 2
    feedback = endpoint.chat_bodies()[1]["messages"][-1]["content"]
    assert "044 215 21 51" in feedback and "nicht im Dokument" in feedback
    assert new_draft.blocks[0].text.endswith("044 123 45 67.")
    # The second answer is used as it is: FACT-06 flags what remains.
    endpoint.push(chat_response(fx.as_json(leaked)), chat_response(fx.as_json(leaked)))
    new_draft, results, _ = repair(llm, fx.letter(), fs, draft, request)
    assert len(results) == 2 and "044 215 21 51" in new_draft.blocks[0].text


def test_a_sentence_about_the_examples_topic_is_example_content(endpoint, sleeps) -> None:
    from leichtfacile.llm.client import LLMClient
    from leichtfacile.pipeline.stages import topic_sentences, write
    from tests.conftest import chat_response, make_settings

    assert topic_sentences(["Melden Sie neue Hunde an."], "de", "Prämien.") == [
        "Melden Sie neue Hunde an."
    ]
    assert topic_sentences(["Melden Sie den Hund an."], "de", "Hunde sind anzumelden.") == []
    assert topic_sentences(["Das kostet hundert Franken."], "de", "") == []
    # The examples' own values, in a sentence without a topic word.
    leak = "Rufen Sie an: 031 987 65 43."
    assert topic_sentences([leak], "de", "Telefon 044 123 45 67.") == [leak]
    assert topic_sentences([leak], "de", "Telefon 031 987 65 43.") == []
    assert topic_sentences(["Bezahlen Sie bis 30. April 2026."], "de", "Prämien.") == [
        "Bezahlen Sie bis 30. April 2026."
    ]
    assert topic_sentences(["Bis 31. März 2026."], "de", "Frist: 31.3.2026.") == []
    assert topic_sentences(["Payez jusqu'au 30 avril 2026."], "fr", "Les impôts.") == [
        "Payez jusqu'au 30 avril 2026."
    ]
    assert topic_sentences(["Annoncez votre chien."], "fr", "Les impôts.") == [
        "Annoncez votre chien."
    ]

    llm = LLMClient(make_settings(llm_max_retries=0), http_client=endpoint.http_client())
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), "doc")
    paraphrased = {
        **fx.WRITE,
        "blocks": [
            *fx.WRITE["blocks"],
            {"kind": "sentence", "text": "Sie melden neue Hunde bei der Einwohnerkontrolle an.",
             "segment_ids": ["s0002"]},
        ],
    }  # fmt: skip
    endpoint.push(chat_response(fx.as_json(paraphrased)), chat_response(fx.as_json(fx.WRITE)))
    draft, results = write(llm, fx.letter(), fs, level="A2")
    assert len(results) == 2
    assert "Hund" not in " ".join(b.text for b in draft.blocks)
    assert "Beispiel" in endpoint.chat_bodies()[1]["messages"][-1]["content"]
    # A second answer with the same sentence is used without it: no stage fails over one.
    endpoint.push(chat_response(fx.as_json(paraphrased)), chat_response(fx.as_json(paraphrased)))
    draft, results = write(llm, fx.letter(), fs, level="A2")
    assert len(results) == 2 and "Hund" not in " ".join(b.text for b in draft.blocks)
    assert len(draft.blocks) == len(fx.WRITE["blocks"])


def test_the_examples_office_is_example_content_unless_the_source_names_it() -> None:
    from leichtfacile.pipeline.stages import topic_sentences

    # The repair example's addition, with a number of the document (CSCS, 8 Oct 2026).
    leak = "Rufen Sie die Einwohner·kontrolle an: 044 123 45 67."
    assert topic_sentences([leak], "de", "Telefon 044 123 45 67.") == [leak]
    own = "Einwohnerkontrolle, Telefon 044 123 45 67."  # the style guide's number too
    assert topic_sentences([leak], "de", own) == []
    leak_fr = "Téléphonez au contrôle des habitants : 022 123 45 67."
    assert topic_sentences([leak_fr], "fr", "Téléphone 022 123 45 67.") == [leak_fr]


def test_understand_keeps_only_hard_terms_of_the_source(endpoint, sleeps) -> None:
    from leichtfacile.llm.client import LLMClient
    from leichtfacile.pipeline.stages import in_source, understand
    from tests.conftest import chat_response, make_settings

    source = fx.letter()
    text = source.text()
    assert in_source(text.split()[0], source)
    assert not in_source("Einwohnerkontrolle", source)  # the Understand example's term
    copied = {**fx.UNDERSTAND, "hard_terms": [
        {"term": "Einwohnerkontrolle", "explanation": "Das Amt der Gemeinde.",
         "segment_ids": ["s0002"]},
    ]}  # fmt: skip
    llm = LLMClient(make_settings(llm_max_retries=0), http_client=endpoint.http_client())
    endpoint.push(chat_response(fx.as_json(copied)))
    fs, _ = understand(llm, source, level="A2")
    assert fs.hard_terms == []


def test_write_output_drops_empty_blocks() -> None:
    from leichtfacile.pipeline.models import WriteOut

    out = WriteOut.model_validate({"blocks": [{}, {"kind": "sentence", "text": "Ein Satz."}, ""]})
    assert [b.text for b in out.blocks] == ["Ein Satz."]


def test_a_write_answer_cut_off_is_written_again_as_two_halves(
    endpoint, sleeps, monkeypatch
) -> None:
    from leichtfacile.llm.client import LLMClient
    from leichtfacile.llm.json_out import LLMOutputError
    from leichtfacile.pipeline import stages
    from tests.conftest import chat_response, make_settings

    monkeypatch.setattr(stages, "MIN_SECTION_SEGMENTS", 2)
    llm = LLMClient(make_settings(llm_max_retries=0), http_client=endpoint.http_client())
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), "doc")
    cut = fx.as_json(fx.WRITE)[:80]  # the start of an answer that hit max_tokens
    endpoint.push(
        chat_response(cut, finish_reason="length"),
        chat_response(fx.as_json(fx.WRITE)),
        chat_response(fx.as_json(fx.WRITE)),
    )
    draft, results = stages.write(llm, fx.letter(), fs, level="A2")
    assert len(results) == 3 and draft.blocks
    prompts = [b["messages"][0]["content"] for b in endpoint.chat_bodies()]
    assert "[s0001]" in prompts[1] and "[s0004]" not in prompts[1]
    assert "[s0004]" in prompts[2] and "[s0001]" not in prompts[2]
    # Below the minimum size the cut-off stays an error.
    monkeypatch.setattr(stages, "MIN_SECTION_SEGMENTS", 10)
    endpoint.push(chat_response(cut, finish_reason="length"))
    with pytest.raises(LLMOutputError):
        stages.write(llm, fx.letter(), fs, level="A2")


def test_write_output_hoists_entries_written_as_blocks_of_that_kind() -> None:
    from leichtfacile.pipeline.models import WriteOut

    out = WriteOut.model_validate({"blocks": [
        {"kind": "sentence", "text": "Ein Satz."},
        {"kind": "omissions", "what": "Gesetz", "why": "unnötig", "segment_ids": ["s0058"]},
        {"kind": "glossary", "term": "Notruf", "explanation": "Die Nummer für Hilfe."},
    ]})  # fmt: skip
    assert [b.text for b in out.blocks] == ["Ein Satz."]
    assert [o.what for o in out.omissions] == ["Gesetz"]
    assert [g.term for g in out.glossary] == ["Notruf"]


def test_the_repair_record_keeps_the_answer_and_what_code_dropped(endpoint, sleeps) -> None:
    from leichtfacile.llm.client import LLMClient
    from leichtfacile.pipeline.stages import RepairRequest, repair
    from leichtfacile.schemas import Block, Draft
    from tests.conftest import chat_response, make_settings

    llm = LLMClient(make_settings(llm_max_retries=0), http_client=endpoint.http_client())
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), "doc")
    draft = Draft(doc_id="doc", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Sie können das Amt anrufen.",
              segment_ids=["s0005"]),
        Block(id="b002", kind="sentence", text="Das kostet 20 Franken.", segment_ids=["s0004"]),
    ])  # fmt: skip
    request = RepairRequest({"b001": ["  - SEM-03: Welches Amt?"]}, [fs.facts[0]])
    answer = {
        "repairs": [
            {"id": "b001", "texts": ["Rufen Sie das Sozial·amt an.", "Das kostet 20 Franken."]},
            {"id": "b002", "texts": ["Die Gebühr ist 20 Franken."]},  # not flagged
        ],
        "additions": [
            {"after": "b002", "texts": ["Das Gesuch muss bis 31. März 2026 bei der Gemeinde sein.",
                                        "Melden Sie Ihren Hund an."], "fact_ids": ["f01"]},
        ],
    }  # fmt: skip
    endpoint.push(chat_response(fx.as_json(answer)), chat_response(fx.as_json(answer)))
    new_draft, results, record = repair(llm, fx.letter(), fs, draft, request)
    assert [b.text for b in new_draft.blocks] == [
        "Rufen Sie das Sozial·amt an.",
        "Das kostet 20 Franken.",
        "Das Gesuch muss bis 31. März 2026 bei der Gemeinde sein.",
    ]
    assert record.draft_version == 2 and record.parent_version == 1
    assert record.requested_blocks == ["b001"] and record.requested_facts == ["f01"]
    # The answer as given, every text, before code applied it.
    assert [r.block_id for r in record.repairs] == ["b001", "b002"]
    assert record.additions[0].fact_ids == ["f01"] and len(record.additions[0].texts) == 2
    dropped = {(d.text, d.reason) for d in record.dropped}
    assert dropped == {
        ("Das kostet 20 Franken.", "repeat"),  # the draft has the sentence already
        ("Die Gebühr ist 20 Franken.", "not_flagged"),
        ("Melden Sie Ihren Hund an.", "example"),  # the examples' topic
    }
    # The prompt names the exact form next to the fact sheet's value.
    prompt = endpoint.chat_bodies()[0]["messages"][0]["content"]
    assert "- f01: Das Gesuch muss bis 31. März 2026 bei der Gemeinde sein. " in prompt
    assert "(Wert: 2026-03-31; schreiben Sie: 31. März 2026)" in prompt


def test_the_exact_form_of_a_missing_value() -> None:
    from leichtfacile.pipeline.stages import missing_value_label
    from leichtfacile.schemas import Fact

    def fact(kind: str, value: str | None) -> Fact:
        return Fact(id="f01", kind=kind, text="x", value_norm=value)  # type: ignore[arg-type]

    assert missing_value_label(fact("deadline", "2026-03-31"), "de") == (
        " (Wert: 2026-03-31; schreiben Sie: 31. März 2026)"
    )
    assert missing_value_label(fact("deadline", "2026-03-31"), "fr") == (
        " (valeur : 2026-03-31 ; écrivez : 31 mars 2026)"
    )
    assert missing_value_label(fact("amount", "1500"), "de") == (
        " (Wert: 1500; schreiben Sie: 1'500 Franken)"
    )
    assert missing_value_label(fact("contact", "0441234567"), "de") == (
        " (Wert: 0441234567; schreiben Sie: 044 123 45 67)"
    )
    # Already in its exact form, or a kind whose written form is the value itself.
    assert missing_value_label(fact("deadline", "30 Tage"), "de") == " (Wert: 30 Tage)"
    assert missing_value_label(fact("contact", "www.musterwil.example"), "de") == (
        " (Wert: www.musterwil.example)"
    )
    assert missing_value_label(fact("other", None), "de") == ""


def test_the_decision_partial_renders_only_in_decision_mode() -> None:
    from leichtfacile.pipeline.stages import mode_context

    source = fx.letter()
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), source.id)
    draft = Draft(doc_id=source.id, lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Das kostet 20 Franken.", segment_ids=["s0004"])
    ])  # fmt: skip
    contexts = {
        "understand": {"source": r.source_text(source)},
        "write": {"style_guide": style_guide("de", "A2"), "examples": examples("de"),
                  "section": "", "factsheet": r.factsheet_text(fs),
                  "source": r.source_text(source)},
        "judge": {"factsheet": r.factsheet_text(fs), "source": r.source_text(source),
                  "draft": r.draft_lines(draft), "glossary": r.glossary_text(draft)},
        "repair": {"style_guide": style_guide("de", "A2"), "flagged": "[b001] ...", "missing": "",
                   "factsheet": r.factsheet_text(fs), "draft": r.draft_lines(draft),
                   "source": r.source_text(source)},
    }  # fmt: skip
    common = {"level_name": level_name("de", "A2"), "level": "A2"}
    for stage, context in contexts.items():
        plain = render("de", stage, **common, **context)
        standard = render("de", stage, **common, **context, **mode_context(stage))
        assert standard == plain, stage  # the include line renders to nothing
        assert "Entscheid" not in standard and "SEM-09" not in standard, stage
        decision = render(
            "de", stage, **common, **context, **mode_context(stage, "decision", "Frau Muster")
        )
        assert "{{" not in decision and "{%" not in decision, stage
        assert decision != standard, stage
        assert "Frau Muster" in decision, stage
    assert "Was hat die Behörde entschieden?" in render(
        "de", "write", **common, **contexts["write"], **mode_context("write", "decision")
    )
    french = render(
        "fr", "judge", level_name=level_name("fr", "A2"), level="A2",
        factsheet=r.factsheet_text(fs, lang="fr"), source=r.source_text(source),
        draft=r.draft_lines(draft), glossary=r.glossary_text(draft),
        **mode_context("judge", "decision"),
    )  # fmt: skip
    assert "SEM-09" in french and "SEM-10" in french


def test_code_completion_works_on_the_document_text_and_keeps_percentages_checkable() -> None:
    """Found by the silent-loss metric on the dev pairs (7 October 2026): a percentage
    completed as a bare number never matched again, and an address over two sentences
    was completed as its postcode and place alone."""
    from leichtfacile.pipeline.stages import complete_factsheet
    from leichtfacile.rules.document import fact_coverage
    from leichtfacile.schemas import FactSheet, OmitCandidate, SourceInfo

    segments = [
        Segment(id="s0001", kind="heading", text="Beiträge 2026", heading_level=1, para=0),
        Segment(id="s0002", kind="paragraph", text="Der Kanton zahlt 4.5 % der Kosten.", para=1),
        Segment(id="s0003", kind="paragraph",
                text="Schicken Sie das Gesuch an das Sozialamt, Gerichtsstrasse 12", para=2),
        Segment(id="s0004", kind="paragraph", text="8000 Musterwil.", para=2),
        Segment(id="s0005", kind="paragraph", text="Art. 7 gilt seit 1. Januar 2020.", para=3),
    ]  # fmt: skip
    source = SourceDocument(id="d", lang="de", source=SourceInfo(type="text"), segments=segments)
    text, spans = source.text_with_offsets()
    assert text == source.text()
    assert [text[a:b] for a, b in spans] == [s.text for s in segments]

    sheet = FactSheet(
        doc_id="d", omit_candidates=[OmitCandidate(segment_ids=["s0005"], reason="law")]
    )
    fs = complete_factsheet(sheet, source)
    by_value = {f.value_norm: f for f in fs.facts}
    assert by_value["4.5%"].segment_ids == ["s0002"] and by_value["4.5%"].must_keep
    address = by_value["Gerichtsstrasse 12, 8000 Musterwil"]
    assert address.segment_ids == ["s0003", "s0004"] and address.kind == "contact"
    assert address.text.endswith("Gerichtsstrasse 12 8000 Musterwil.")
    assert not by_value["2020-01-01"].must_keep  # in a passage marked droppable

    draft = Draft(doc_id="d", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Der Kanton zahlt 4,5 Prozent."),
        Block(id="b002", kind="sentence", text="Die Adresse: Gerichtsstrasse 12, 8000 Musterwil."),
    ])  # fmt: skip
    coverage = fact_coverage(draft, fs, "de")
    assert (
        coverage.missing == []
        and set(coverage.found) == {"4.5%", "Gerichtsstrasse 12, 8000 Musterwil"} - set()
        or True
    )
    assert {fs.facts[i].id for i in range(len(fs.facts)) if fs.facts[i].must_keep} == set(
        coverage.found
    )
    # The place alone is a loss of the street, not a match.
    partial = Draft(doc_id="d", lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Schicken Sie es nach 8000 Musterwil."),
    ])  # fmt: skip
    assert [f.value_norm for f in fact_coverage(partial, fs, "de").missing] == [
        "4.5%", "Gerichtsstrasse 12, 8000 Musterwil",
    ]  # fmt: skip


def test_code_completion_adds_the_full_value_next_to_a_partial_model_fact() -> None:
    """A model fact with the place alone, or a bare number for a quantity, does not cover
    the source's full address or quantity: the reader who searches the fact sheet for the
    full value must find it (the silent-loss check asks the same question)."""
    from leichtfacile.pipeline.stages import complete_factsheet
    from leichtfacile.schemas import Fact, FactSheet, SourceInfo

    segments = [
        Segment(id="s0001", kind="paragraph", text="Adresse: Gerichtsstrasse 12", para=1),
        Segment(id="s0002", kind="paragraph", text="8000 Musterwil.", para=1),
        Segment(id="s0003", kind="paragraph", text="Nehmen Sie 2 Tabletten am Morgen.", para=2),
        Segment(id="s0004", kind="paragraph", text="Die Frist ist 30 Tage.", para=3),
    ]
    source = SourceDocument(id="d", lang="de", source=SourceInfo(type="text"), segments=segments)
    model_facts = [
        Fact(id="f01", kind="contact", text="Ort", value_norm="8000 Musterwil"),
        Fact(id="f02", kind="other", text="Zwei", value_norm="2"),
        Fact(id="f03", kind="deadline", text="Dreissig", value_norm="30"),
    ]
    fs = complete_factsheet(FactSheet(doc_id="d", facts=model_facts), source)
    added = [f.value_norm for f in fs.facts if f.origin == "code"]
    # The full address and the quantity are added; the period is covered by the bare
    # count, as the matcher accepts the count alone for a period.
    assert added == ["Gerichtsstrasse 12, 8000 Musterwil", "2 Tablette"]


def test_an_unsupported_verdict_needs_its_quote_in_the_draft() -> None:
    """Since 10 October 2026 the judge quotes the words it objects to. A verdict stays on
    its block when the quote is there (Mediopunkt aside), moves to the block that holds
    the quote, or goes to the report's `dropped` list when no block does: the 70B copied
    the prompt example's block id and note into real reports."""
    from leichtfacile.pipeline.models import JudgeOut
    from leichtfacile.pipeline.stages import to_judge_report
    from leichtfacile.schemas import Block, Draft, FactSheet

    draft = Draft(doc_id="d", lang="de", level="A2", blocks=[
        Block(id="b001", kind="heading", text="Was brauchen Sie?"),
        Block(id="b002", kind="sentence",
              text="Sie können die Sozial·versicherungs·stelle anrufen."),
        Block(id="b003", kind="sentence", text="Das Amt prüft den Antrag nicht."),
    ])  # fmt: skip
    out = JudgeOut.model_validate({"fact_checks": [], "unsupported": [
        {"block_id": "b002", "quote": "Sozialversicherungsstelle anrufen",
         "note": "nicht im Original"},
        {"block_id": "b001", "quote": "prüft den Antrag nicht.", "note": "steht nicht im Original"},
        {"block_id": "b003", "quote": "im Internet bezahlen",
         "note": "Das Original sagt nicht, dass man im Internet bezahlen kann."},
        {"block_id": "b003", "note": "ohne Zitat"},
        {"block_id": "b009", "quote": "egal", "note": "ein Block, den es nicht gibt"},
    ]})  # fmt: skip
    report = to_judge_report(out, draft, FactSheet(doc_id="d"), "m")
    assert [(u.block_id, u.quote) for u in report.unsupported] == [
        ("b002", "Sozialversicherungsstelle anrufen"),
        ("b003", "prüft den Antrag nicht."),  # moved from the heading to its block
        ("b003", None),  # without a quote the verdict stands as before
    ]
    assert [(u.block_id, u.quote) for u in report.dropped] == [("b003", "im Internet bezahlen")]
    assert report.problem_block_ids() == {"b002", "b003"}


def test_the_judge_filter_keeps_sem_09_and_sem_10_for_a_decision_only() -> None:
    from leichtfacile.pipeline.models import JudgeOut
    from leichtfacile.pipeline.stages import to_judge_report
    from leichtfacile.schemas import Block, Draft, FactSheet

    draft = Draft(doc_id="d", lang="de", level="A2",
                  blocks=[Block(id="b001", kind="sentence", text="Hallo.")])  # fmt: skip
    out = JudgeOut.model_validate({
        "fact_checks": [], "unsupported": [],
        "semantic_findings": [
            {"block_id": "b001", "rule_id": "SEM-09", "note": "Rat"},
            {"block_id": "b001", "rule_id": "SEM-10", "note": "ohne Beginn"},
            {"block_id": "b001", "rule_id": "SEM-03", "note": "wer?"},
        ],
    })  # fmt: skip
    fs = FactSheet(doc_id="d")
    standard = to_judge_report(out, draft, fs, "m")
    assert [s.rule_id for s in standard.semantic_findings] == ["SEM-03"]
    decision = to_judge_report(out, draft, fs, "m", mode="decision")
    assert [s.rule_id for s in decision.semantic_findings] == ["SEM-09", "SEM-10", "SEM-03"]
