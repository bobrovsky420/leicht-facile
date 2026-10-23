"""The Word export: a DOCX package in the reader layout, the review applied, the
provenance in the footer. Word opened the files while this was built (every part, the
line breaks, de-CH and fr-CH); these tests pin what it saw."""

from __future__ import annotations

import io
import zipfile
from datetime import date
from xml.etree import ElementTree

from leichtfacile import __version__, cli
from leichtfacile.export.docx import DOCX_LINE_CHARS, LIST_CHARS, footer_line, to_docx
from leichtfacile.llm.client import LLMClient
from leichtfacile.schemas import (
    Block,
    Decision,
    Draft,
    GlossaryEntry,
    PipelineSummary,
    ReviewState,
)
from tests.conftest import MODEL, chat_response, make_settings
from tests.pipeline import fixtures as fx

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DC = "{http://purl.org/dc/elements/1.1/}"
DAY = date(2026, 10, 11)
NOTICE = "Diese Erklärung hilft Ihnen, den Entscheid zu verstehen. Massgebend ist der Entscheid."
CALL = "Für Fragen rufen Sie die Sozial·versicherungs·stelle an: 044 123 45 67 oder mailen."
ITEM = "eine Kopie der Steuer·veranlagung und der Kranken·versicherungs·police vom letzten Jahr"


def draft(lang: str = "de") -> Draft:
    return Draft(
        doc_id="d", lang=lang, level="A2", version=2,
        blocks=[
            Block(id="b001", kind="heading", text="Was müssen Sie tun?"),
            Block(id="b002", kind="sentence", text="Schicken Sie das Gesuch bis 31. März 2026."),
            Block(id="b003", kind="sentence", text=CALL),
            Block(id="b004", kind="list_item", text="den Antrag"),
            Block(id="b005", kind="list_item", text=ITEM),
            Block(id="b006", kind="sentence", text="Sie haben wenig Geld."),
        ],
        glossary=[GlossaryEntry(term="Prämie", explanation="Das Geld für die Kranken·kasse.")],
    )  # fmt: skip


def parts(data: bytes) -> dict[str, ElementTree.Element]:
    """Every part of the package, parsed: a part that is not well-formed XML fails here."""
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        return {name: ElementTree.fromstring(package.read(name)) for name in package.namelist()}


def style_of(p: ElementTree.Element) -> str | None:
    found = p.find(f"{W}pPr/{W}pStyle")
    return None if found is None else found.get(f"{W}val")


def paragraphs(root: ElementTree.Element) -> list[tuple[str | None, list[str]]]:
    """Each paragraph's style and its lines, the text between its line breaks."""
    found = []
    for p in root.iter(f"{W}p"):
        lines = [""]
        for element in p.iter():
            if element.tag == f"{W}t":
                lines[-1] += element.text or ""
            elif element.tag == f"{W}br":
                lines.append("")
        found.append((style_of(p), lines))
    return found


def style(styles: ElementTree.Element, style_id: str) -> ElementTree.Element:
    return next(s for s in styles.iter(f"{W}style") if s.get(f"{W}styleId") == style_id)


def test_the_package_has_its_parts_their_content_types_and_relationships() -> None:
    package = parts(to_docx(draft(), title="Brief", today=DAY))
    assert set(package) == {
        "[Content_Types].xml", "_rels/.rels", "docProps/core.xml", "word/document.xml",
        "word/_rels/document.xml.rels", "word/styles.xml", "word/numbering.xml",
        "word/settings.xml", "word/footer1.xml",
    }  # fmt: skip
    types = {t.get("PartName") for t in package["[Content_Types].xml"] if t.get("PartName")}
    assert types == {f"/{n}" for n in package if n.endswith(".xml") and not n.startswith("[")}
    for rels, folder in (("_rels/.rels", ""), ("word/_rels/document.xml.rels", "word/")):
        assert all(folder + rel.get("Target") in package for rel in package[rels])
    footer = package["word/document.xml"].find(f"{W}body/{W}sectPr/{W}footerReference")
    assert footer is not None and footer.get(f"{W}type") == "default"


def test_the_page_and_the_styles_are_the_reader_layout() -> None:
    package = parts(to_docx(draft(), today=DAY))
    styles = package["word/styles.xml"]
    defaults = styles.find(f"{W}docDefaults/{W}rPrDefault/{W}rPr")
    assert defaults.find(f"{W}rFonts").get(f"{W}ascii") == "Arial"
    assert defaults.find(f"{W}sz").get(f"{W}val") == "28"  # half points: 14 points
    assert defaults.find(f"{W}lang").get(f"{W}val") == "de-CH"  # Swiss spelling, no sharp s
    normal = style(styles, "Normal").find(f"{W}pPr")
    assert normal.find(f"{W}jc").get(f"{W}val") == "left"
    assert normal.find(f"{W}suppressAutoHyphens") is not None  # no hyphenation
    assert normal.find(f"{W}keepLines") is not None  # no block split across pages
    for kept in ("Heading1", "Heading2", "GlossaryTerm"):  # with the paragraph after
        assert style(styles, kept).find(f"{W}pPr/{W}keepNext") is not None
    section = package["word/document.xml"].find(f"{W}body/{W}sectPr")
    size, margins = section.find(f"{W}pgSz"), section.find(f"{W}pgMar")
    assert (size.get(f"{W}w"), size.get(f"{W}h")) == ("11906", "16838")  # A4
    assert {margins.get(f"{W}{side}") for side in ("top", "right", "bottom", "left")} == {"1134"}
    core = package["docProps/core.xml"]
    assert core.find(f"{DC}language").text == "de-CH" and core.find(f"{DC}title") is None


def test_each_block_is_a_paragraph_in_words_styles_with_the_glossary_last() -> None:
    document = parts(to_docx(draft(), title="Brief", today=DAY))["word/document.xml"]
    found = paragraphs(document)
    assert [s for s, _ in found] == [
        "Heading1", "DraftNote", "Heading2", None, None, "ListBullet", "ListBullet", None,
        "Heading2", "GlossaryTerm", None,
    ]  # fmt: skip
    assert found[0][1] == ["Brief"] and found[1][1] == ["Entwurf: noch nicht geprüft."]
    assert found[8][1] == ["Wörterbuch"] and found[9][1] == ["Prämie"]
    assert found[10][1] == ["Das Geld für die Kranken·kasse."]
    # The list's last item gets a paragraph's space below it, the others the list's.
    items = [p for p in document.iter(f"{W}p") if style_of(p) == "ListBullet"]
    spacing = [p.find(f"{W}pPr/{W}spacing") for p in items]
    assert spacing[0] is None and spacing[1].get(f"{W}after") == "200"


def test_lines_break_at_sense_units_within_the_page_and_never_inside_a_value() -> None:
    found = paragraphs(parts(to_docx(draft(), today=DAY))["word/document.xml"])
    call = next(lines for _, lines in found if lines[0].startswith("Für Fragen"))
    assert len(call) > 1 and all(len(line) <= DOCX_LINE_CHARS for line in call)
    assert " ".join(call).replace("\xa0", " ") == CALL
    assert any("044\xa0123\xa045\xa067" in line for line in call)
    item = next(lines for s, lines in found if s == "ListBullet" and lines[0].startswith("eine"))
    assert len(item) > 1 and all(len(line) <= DOCX_LINE_CHARS - LIST_CHARS for line in item)
    assert " ".join(item) == ITEM


def test_the_review_applies_and_a_decision_job_opens_and_ends_with_the_notice() -> None:
    review = ReviewState(
        draft_version=2,
        decisions=[
            Decision(block_id="b002", decision="edited",
                     text="Schicken Sie das Gesuch\nbis 31. März 2026 an die Gemeinde."),
            Decision(block_id="b006", decision="rejected"),
            Decision(block_id="g01", decision="rejected"),
        ],
    )  # fmt: skip
    data = to_docx(draft(), review, title="Entscheid", notice=NOTICE, today=DAY)
    found = paragraphs(parts(data)["word/document.xml"])
    assert found[1] == ("Notice", [NOTICE]) and found[-1] == ("Notice", [NOTICE])
    assert [s for s, _ in found].count("Notice") == 2
    assert "DraftNote" not in [s for s, _ in found]  # reviewed
    texts = [" ".join(lines).replace("\xa0", " ") for _, lines in found]
    # The edit's line break is a space: in Word only `wrap_sentence` breaks lines.
    assert "Schicken Sie das Gesuch bis 31. März 2026 an die Gemeinde." in texts
    assert "Sie haben wenig Geld." not in texts and "Wörterbuch" not in texts
    standard = paragraphs(parts(to_docx(draft(), review, today=DAY))["word/document.xml"])
    assert "Notice" not in [s for s, _ in standard]


def test_the_footer_names_the_tool_draft_day_model_and_the_prompt_that_wrote_the_text() -> None:
    summary = PipelineSummary(
        condition="P2", final_version=2, writer_model="swiss-ai/Apertus-v1.5-8B",
        prompt_versions={"write": "a644e7997ea4", "baseline": "0b0b0b0b0b0b",
                         "baseline_zh": "2c2c2c2c2c2c"},
    )  # fmt: skip
    line = (
        f"Leicht·Facile {__version__} · Entwurf v2 · 11.10.2026 · swiss-ai/Apertus-v1.5-8B"
        " · Prompt a644e7997ea4"
    )
    assert footer_line(draft(), summary, DAY) == line
    zurich = summary.model_copy(update={"condition": "P0-ZH-complete"})
    assert footer_line(draft(), zurich, DAY).endswith(" · Prompt 2c2c2c2c2c2c")
    single = summary.model_copy(update={"condition": "P0"})
    assert footer_line(draft(), single, DAY).endswith(" · Prompt 0b0b0b0b0b0b")
    unknown = summary.model_copy(update={"prompt_versions": {"write": "none"}})
    assert footer_line(draft(), unknown, DAY).endswith("swiss-ai/Apertus-v1.5-8B")
    before_the_pipeline = f"Leicht·Facile {__version__} · Brouillon v2 · 11.10.2026"
    assert footer_line(draft("fr"), None, DAY) == before_the_pipeline
    footer = parts(to_docx(draft(), summary=summary, today=DAY))["word/footer1.xml"]
    assert paragraphs(footer) == [("Footer", [line])]


def test_a_french_draft_gets_french_labels_and_swiss_french_spelling() -> None:
    package = parts(to_docx(draft("fr"), today=DAY))
    lang = package["word/styles.xml"].find(f"{W}docDefaults/{W}rPrDefault/{W}rPr/{W}lang")
    assert lang.get(f"{W}val") == "fr-CH"
    found = paragraphs(package["word/document.xml"])
    assert found[0] == ("DraftNote", ["Brouillon : pas encore relu."])
    assert ("Heading2", ["Lexique"]) in found


def test_markup_is_escaped_control_characters_go_and_the_bytes_repeat() -> None:
    d = draft().model_copy(
        update={"blocks": [Block(id="b001", kind="sentence", text="A <b> & C\x0cD\x01E.")]}
    )
    data = to_docx(d, title="<Brief> & Co", today=DAY)
    package = parts(data)
    found = paragraphs(package["word/document.xml"])
    assert found[0] == ("Heading1", ["<Brief> & Co"]) and found[2] == (None, ["A <b> & C DE."])
    assert package["docProps/core.xml"].find(f"{DC}title").text == "<Brief> & Co"
    assert to_docx(d, title="<Brief> & Co", today=DAY) == data


LETTER = """# Prämienverbilligung 2026

Personen mit geringem Einkommen haben Anspruch auf eine Prämienverbilligung.
Das Gesuch ist bis spätestens 31. März 2026 bei der Gemeinde einzureichen.

Für die Bearbeitung wird eine Gebühr von CHF 20.- erhoben.

Auskunft erteilt das Sozialamt unter Telefon 044 123 45 67.

Rechtsgrundlage ist Art. 5 des Einführungsgesetzes.
"""


def test_simplify_writes_the_word_export_next_to_the_others(
    tmp_path, endpoint, sleeps, monkeypatch
) -> None:
    settings = make_settings(data__dir=tmp_path, llm__max_retries=0)
    monkeypatch.setattr("leichtfacile.config.get_settings", lambda: settings)
    monkeypatch.setattr(
        LLMClient,
        "from_settings",
        lambda s: LLMClient(s, http_client=endpoint.http_client(), sleep=sleeps.append),
    )
    endpoint.push(chat_response(fx.as_json(fx.UNDERSTAND)), chat_response(fx.as_json(fx.WRITE)))
    letter = tmp_path / "brief.txt"
    letter.write_text(LETTER, encoding="utf-8")
    out = tmp_path / "out"
    assert cli.main(["simplify", str(letter), "--condition", "P1", "--out", str(out)]) == 0
    (folder,) = out.iterdir()
    assert {p.name for p in folder.iterdir()} == {
        "bundle.json", "draft.md", "draft.html", "draft.docx",
    }  # fmt: skip
    package = parts((folder / "draft.docx").read_bytes())
    assert ("Heading2", ["Was müssen Sie tun?"]) in paragraphs(package["word/document.xml"])
    [(_, [footer])] = paragraphs(package["word/footer1.xml"])
    assert footer.startswith(f"Leicht·Facile {__version__} · Entwurf v1 · ") and MODEL in footer
