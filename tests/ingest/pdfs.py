"""Synthetic PDFs for the ingest tests, generated with fpdf2 at test time.

Only the core fonts are used, so the tests need no font files: Helvetica covers Latin-1
(umlauts, the Mediopunkt U+00B7, guillemets), and the Symbol font supplies a bullet
glyph that text extraction reports as U+2022, the way many PDFs deliver a Mediopunkt
or a list bullet. All texts are invented.
"""

from __future__ import annotations

from fpdf import FPDF

LEADING = 1.4  # line distance as a multiple of the font size


def new_pdf(title: str | None = None) -> FPDF:
    pdf = FPDF(unit="pt", format="A4")  # 595 x 842 points
    pdf.set_auto_page_break(False)
    if title:
        pdf.set_title(title)
    return pdf


def lines(
    pdf: FPDF, x: float, y: float, texts: list[str], size: float = 11, style: str = ""
) -> float:
    """Write one text per line from baseline y; return the baseline after the last line."""
    pdf.set_font("Helvetica", style=style, size=size)
    for text in texts:
        pdf.text(x, y, text)
        y += size * LEADING
    return y


def symbol_bullet(pdf: FPDF, x: float, y: float, size: float = 11) -> float:
    """A bullet glyph of the Symbol font; returns its width."""
    pdf.set_font("Symbol", size=size)
    pdf.text(x, y, "\u00b7")  # code 0xB7 of the Symbol font is the bullet
    return pdf.get_string_width("\u00b7")


def compound_with_symbol_dot(
    pdf: FPDF, x: float, y: float, first: str, second: str, rest: str
) -> None:
    """Write first + Symbol bullet + second + rest without gaps, like "Merk\u2022blatt"."""
    pdf.set_font("Helvetica", size=11)
    pdf.text(x, y, first)
    x += pdf.get_string_width(first)
    x += symbol_bullet(pdf, x, y)
    pdf.set_font("Helvetica", size=11)
    pdf.text(x, y, second + rest)


def letter() -> bytes:
    """One column: a large title, a bold heading at body size, paragraphs, a hyphenated
    line break and a bulleted list."""
    pdf = new_pdf()
    pdf.add_page()
    y = lines(pdf, 60, 90, ["Prämienverbilligung 2027"], size=20, style="B")
    y = lines(
        pdf,
        60,
        y + 14,
        [
            "Sie haben Anspruch auf eine Prämien-",
            "verbilligung. Der Kanton bezahlt einen Teil",
            "Ihrer Prämie für die Krankenkasse.",
        ],
    )
    y = lines(
        pdf,
        60,
        y + 11,
        [
            "Schreiben Sie uns eine E-",
            "Mail, wenn Sie Fragen haben.",
        ],
    )
    y = lines(pdf, 60, y + 11, ["Was müssen Sie tun"], style="B")
    y = lines(pdf, 60, y, ["Schicken Sie den Antrag bis 31. März 2027 an die SVA."])
    for item in ("den Antrag", "eine Kopie der Steuererklärung"):
        symbol_bullet(pdf, 60, y)
        lines(pdf, 74, y, [item])
        y += 11 * LEADING
    lines(pdf, 60, y + 11, ["Freundliche Grüsse"])
    return bytes(pdf.output())


LEFT = [
    "Die linke Spalte beginnt hier mit",
    "einem Satz über die Kosten der",
    "Behandlung beim Zahnarzt. Die Kosten",
    "müssen vorher geschätzt werden.",
    "Danach prüft die Stelle den Antrag",
    "und schickt Ihnen einen Entscheid.",
    "Bitte bewahren Sie die Rechnung auf.",
    "Der Entscheid kommt mit der Post.",
]
RIGHT = [
    "Die rechte Spalte erklärt die Kosten",
    "für Transporte zum Arzt. Sie bekommen",
    "Geld für das Billett der Bahn in der",
    "zweiten Klasse. Für Fahrten mit dem",
    "Auto gibt es 70 Rappen pro Kilometer.",
    "Schicken Sie uns die Belege bis Ende",
    "des Jahres. Wir zahlen das Geld dann",
    "auf Ihr Konto ein.",
]


def two_columns() -> bytes:
    """A title over both columns, then two columns of text side by side."""
    pdf = new_pdf()
    pdf.add_page()
    lines(pdf, 50, 80, ["Merkblatt zu den Kosten"], size=18, style="B")
    lines(pdf, 50, 130, LEFT, size=10)
    lines(pdf, 320, 130, RIGHT, size=10)
    return bytes(pdf.output())


def two_pages_with_footer() -> bytes:
    """A paragraph that runs over a page break, and a footer with page numbers."""
    pdf = new_pdf(title="Merkblatt 99: Rückvergütung")
    for number, texts in enumerate(
        (
            [
                "Die erste Seite erklärt, wer Geld zurück bekommt. Wer",
                "Ergänzungsleistungen bezieht, kann Kosten für Krankheit",
                "und Behinderung zurück verlangen. Dafür schicken Sie die",
            ],
            [
                "Rechnung innerhalb von 15 Monaten an die Ausgleichskasse.",
                "Die zweite Seite enthält die Adresse der Ausgleichskasse.",
            ],
        ),
        start=1,
    ):
        pdf.add_page()
        lines(pdf, 60, 90, texts)
        lines(pdf, 60, 815, [f"Merkblatt 99 / Stand 1.2026          Seite {number} von 2"], size=7)
    return bytes(pdf.output())


def mediopunkt_and_symbol_bullets() -> bytes:
    """A compound written with a Symbol-font bullet as Mediopunkt."""
    pdf = new_pdf()
    pdf.add_page()
    lines(pdf, 60, 90, ["Ein Merkblatt in Leichter Sprache"], size=18, style="B")
    compound_with_symbol_dot(pdf, 60, 140, "Merk", "blatt", " für Sie.")
    compound_with_symbol_dot(pdf, 60, 140 + 11 * LEADING, "Ergänzungs", "leistungen", " helfen.")
    return bytes(pdf.output())


def without_text() -> bytes:
    """A scanned page in miniature: graphics only, no text layer."""
    pdf = new_pdf()
    pdf.add_page()
    pdf.rect(50, 50, 300, 200, style="F")
    return bytes(pdf.output())
