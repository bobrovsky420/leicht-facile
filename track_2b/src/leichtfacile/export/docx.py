"""Word export (DOCX), for writers who go on in Word: the HTML export's text in its
print layout. A4 with 20 mm margins, Arial 14 points, left-aligned, no hyphenation; a
heading stays with the block after it, and no block is split across two pages.

A block is one paragraph. Its lines break at sense units (`wrap_sentence`), at most
`DOCX_LINE_CHARS` characters long and never inside a value (no-break spaces), and are
joined by line breaks: every sentence starts on a new line, and Word, whose line holds
such a line, does not break it a second time. Title, headings and list items carry
Word's own styles (Heading 1 and 2, List Bullet), so a writer can restyle the document
and the navigation pane shows its outline; the language tag (de-CH, fr-CH, it-CH) gives
the spell checker Swiss spelling. The footer names the tool, the draft version, the day
of the export, the model that wrote the text and the hash of its prompt template.

Arial is the HTML export's fallback (D-V): a DOCX names a single font, and Word replaces
a missing one with a font of its own choosing. Written with the standard library, since
a document is a few short XML parts in a ZIP file; the same input gives the same bytes."""

from __future__ import annotations

import re
import zipfile
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from leichtfacile import __version__
from leichtfacile.export import LABELS, final_blocks, keep_values_together
from leichtfacile.rules.layout import wrap_sentence
from leichtfacile.schemas import ZH_CONDITIONS, Draft, PipelineSummary, ReviewState

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DOCX_LINE_CHARS = 60  # the HTML export's: its print layout is this page at 14 points
LIST_CHARS = 3  # a list item's lines are shorter by the bullet's indent
LANG_TAGS = {"de": "de-CH", "fr": "fr-CH", "it": "it-CH"}

# The prompt template that wrote the text: a baseline's single prompt, else the writer's.
WRITER_PROMPTS = {"P0": "baseline"} | dict.fromkeys(ZH_CONDITIONS, "baseline_zh")

# Lengths in twentieths of a point, font sizes in half points.
_MARGIN = 1134  # 20 mm
_INDENT = 425  # 0.75 cm: where a list item's text starts, its bullet in front
_AFTER = 200  # 10 points below a paragraph

_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
_WML = "application/vnd.openxmlformats-officedocument.wordprocessingml"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

_CONTENT_TYPES = f"""\
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels"
      ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="{_WML}.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="{_WML}.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="{_WML}.numbering+xml"/>
  <Override PartName="/word/settings.xml" ContentType="{_WML}.settings+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="{_WML}.footer+xml"/>
  <Override PartName="/docProps/core.xml"
      ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>
"""

_PACKAGE_RELS = f"""\
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="{_REL}/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Target="docProps/core.xml"
      Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"/>
</Relationships>
"""

_DOCUMENT_RELS = f"""\
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="{_REL}/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="{_REL}/numbering" Target="numbering.xml"/>
  <Relationship Id="rId3" Type="{_REL}/settings" Target="settings.xml"/>
  <Relationship Id="rId4" Type="{_REL}/footer" Target="footer1.xml"/>
</Relationships>
"""

_NUMBERING = f"""\
<w:numbering {_W}>
  <w:abstractNum w:abstractNumId="0">
    <w:multiLevelType w:val="singleLevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/><w:numFmt w:val="bullet"/><w:pStyle w:val="ListBullet"/>
      <w:lvlText w:val="•"/><w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="{_INDENT}" w:hanging="{_INDENT}"/></w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>
"""

_SETTINGS = f"""\
<w:settings {_W}>
  <w:autoHyphenation w:val="false"/>
  <w:characterSpacingControl w:val="doNotCompress"/>
  <w:compat>
    <w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word"
        w:val="15"/>
  </w:compat>
</w:settings>
"""


def _styles(lang: str) -> str:
    # Line 336 is 1.4 lines, which in Arial comes to the HTML export's line height of 1.6.
    return f"""\
<w:styles {_W}>
  <w:docDefaults>
    <w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="Arial" w:eastAsia="Arial" w:hAnsi="Arial" w:cs="Arial"/>
      <w:sz w:val="28"/><w:szCs w:val="28"/><w:lang w:val="{lang}"/>
    </w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr>
      <w:spacing w:after="{_AFTER}" w:line="336" w:lineRule="auto"/>
    </w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/><w:qFormat/>
    <w:pPr><w:keepLines/><w:suppressAutoHyphens/><w:jc w:val="left"/></w:pPr>
  </w:style>
  <w:style w:type="character" w:default="1" w:styleId="DefaultParagraphFont">
    <w:name w:val="Default Paragraph Font"/><w:uiPriority w:val="1"/><w:semiHidden/>
    <w:unhideWhenUsed/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>
    <w:uiPriority w:val="9"/><w:qFormat/>
    <w:pPr><w:keepNext/><w:spacing w:after="240"/><w:outlineLvl w:val="0"/></w:pPr>
    <w:rPr><w:b/><w:bCs/><w:sz w:val="40"/><w:szCs w:val="40"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>
    <w:uiPriority w:val="9"/><w:unhideWhenUsed/><w:qFormat/>
    <w:pPr><w:keepNext/><w:spacing w:before="480" w:after="160"/><w:outlineLvl w:val="1"/></w:pPr>
    <w:rPr><w:b/><w:bCs/><w:sz w:val="34"/><w:szCs w:val="34"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListBullet">
    <w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/><w:uiPriority w:val="99"/>
    <w:unhideWhenUsed/>
    <w:pPr><w:numPr><w:numId w:val="1"/></w:numPr><w:spacing w:after="100"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:customStyle="1" w:styleId="GlossaryTerm">
    <w:name w:val="Glossary Term"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>
    <w:pPr><w:keepNext/><w:spacing w:before="160" w:after="0"/></w:pPr>
    <w:rPr><w:b/><w:bCs/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:customStyle="1" w:styleId="Notice">
    <w:name w:val="Notice"/><w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:pBdr>
        <w:top w:val="single" w:sz="6" w:space="6" w:color="888888"/>
        <w:bottom w:val="single" w:sz="6" w:space="6" w:color="888888"/>
      </w:pBdr>
      <w:spacing w:before="120" w:after="320"/>
    </w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:customStyle="1" w:styleId="DraftNote">
    <w:name w:val="Draft Note"/><w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:pBdr><w:left w:val="single" w:sz="24" w:space="8" w:color="BB0000"/></w:pBdr>
      <w:ind w:left="240"/>
    </w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Footer">
    <w:name w:val="footer"/><w:basedOn w:val="Normal"/><w:uiPriority w:val="99"/>
    <w:unhideWhenUsed/>
    <w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:color w:val="595959"/><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr>
  </w:style>
</w:styles>
"""


_SPACES = re.compile(r"[\t\n\r\x0b\x0c ]+")
_CONTROL = re.compile(r"[\x00-\x08\x0e-\x1f]")  # no place for them in XML 1.0


def _clean(text: str) -> str:
    """Text for one line: a run of white space, a line break in a reviewer's edit
    included, becomes one space, and control characters go."""
    return _CONTROL.sub("", _SPACES.sub(" ", text)).strip()


def _lines(text: str, width: int, lang: str) -> list[str]:
    return wrap_sentence(keep_values_together(_clean(text), lang), width)


def _paragraph(lines: list[str], style: str | None = None, *, after: int | None = None) -> str:
    """One paragraph: its lines in one run, joined by line breaks."""
    props = (f'<w:pStyle w:val="{style}"/>' if style else "") + (
        f'<w:spacing w:after="{after}"/>' if after is not None else ""
    )
    ppr = f"<w:pPr>{props}</w:pPr>" if props else ""
    text = "<w:br/>".join(
        f'<w:t xml:space="preserve">{escape(_clean(line))}</w:t>' for line in lines
    )
    return f"<w:p>{ppr}<w:r>{text}</w:r></w:p>"


def footer_line(draft: Draft, summary: PipelineSummary | None, today: date | None = None) -> str:
    """The tool, the draft version and the day; once the pipeline has run, the model
    that wrote the text and the hash of its prompt template, as the job's summary (and
    the audit bundle) records them."""
    labels = LABELS.get(draft.lang, LABELS["de"])
    parts = [
        f"Leicht·Facile {__version__}",
        labels["version"].format(version=draft.version),
        (today or date.today()).strftime("%d.%m.%Y"),
    ]
    if summary is not None:
        prompt = summary.prompt_versions.get(WRITER_PROMPTS.get(summary.condition, "write"))
        parts += [summary.writer_model, f"Prompt {prompt}" if prompt not in (None, "none") else ""]
    return " · ".join(part for part in parts if part)


def to_docx(
    draft: Draft,
    review: ReviewState | None = None,
    *,
    title: str | None = None,
    width: int = DOCX_LINE_CHARS,
    notice: str | None = None,
    summary: PipelineSummary | None = None,
    today: date | None = None,
) -> bytes:
    """`notice`: the authority's fixed text (decision mode), the first and the last
    paragraph, as it is. `summary` and `today` go into the footer (`footer_line`)."""
    labels = LABELS.get(draft.lang, LABELS["de"])
    final = final_blocks(draft, review)
    body: list[str] = []
    if title:
        body.append(_paragraph([title], "Heading1"))
    if not final.reviewed:
        body.append(_paragraph([labels["draft_note"]], "DraftNote"))
    if notice:
        body.append(_paragraph([notice], "Notice"))
    for i, b in enumerate(final.blocks):
        if b.kind == "heading":
            body.append(_paragraph([b.text], "Heading2"))
        elif b.kind == "list_item":
            # The list's last item gets a paragraph's space below it.
            last = i + 1 == len(final.blocks) or final.blocks[i + 1].kind != "list_item"
            lines = _lines(b.text, width - LIST_CHARS, draft.lang)
            body.append(_paragraph(lines, "ListBullet", after=_AFTER if last else None))
        else:
            body.append(_paragraph(_lines(b.text, width, draft.lang)))
    if final.glossary:
        body.append(_paragraph([labels["glossary"]], "Heading2"))
        for g in final.glossary:
            body.append(_paragraph([g.term], "GlossaryTerm"))
            body.append(_paragraph(_lines(g.explanation, width, draft.lang)))
    if notice:
        body.append(_paragraph([notice], "Notice"))
    lang = LANG_TAGS.get(draft.lang, "de-CH")
    footer = _paragraph([footer_line(draft, summary, today)], "Footer")
    return _package(
        {
            "[Content_Types].xml": _CONTENT_TYPES,
            "_rels/.rels": _PACKAGE_RELS,
            "docProps/core.xml": _core(title, lang),
            "word/document.xml": _document(body),
            "word/_rels/document.xml.rels": _DOCUMENT_RELS,
            "word/styles.xml": _styles(lang),
            "word/numbering.xml": _NUMBERING,
            "word/settings.xml": _SETTINGS,
            "word/footer1.xml": f"<w:ftr {_W}>{footer}</w:ftr>\n",
        }
    )


def _document(body: list[str]) -> str:
    paragraphs = "\n".join(body) or "<w:p/>"
    return f"""\
<w:document {_W} {_R}>
<w:body>
{paragraphs}
<w:sectPr>
  <w:footerReference w:type="default" r:id="rId4"/>
  <w:pgSz w:w="11906" w:h="16838"/>
  <w:pgMar w:top="{_MARGIN}" w:right="{_MARGIN}" w:bottom="{_MARGIN}" w:left="{_MARGIN}"
      w:header="567" w:footer="567" w:gutter="0"/>
</w:sectPr>
</w:body>
</w:document>
"""


def _core(title: str | None, lang: str) -> str:
    """The document's title and language, for the file's properties and a PDF saved
    from it."""
    name = f"<dc:title>{escape(_clean(title))}</dc:title>" if title else ""
    return (
        '<cp:coreProperties xmlns:dc="http://purl.org/dc/elements/1.1/"'
        ' xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties">'
        f"{name}<dc:language>{lang}</dc:language></cp:coreProperties>\n"
    )


def _package(parts: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        for name, xml in parts.items():
            # A fixed time stamp, so that the same input gives the same bytes.
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            package.writestr(info, _HEAD + xml, compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()
