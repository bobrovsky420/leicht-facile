"""Two printable letters for the image input spike (PLAN.md WP12).

Usage: uv run python track_2b/scripts/print_letters.py [--out track_2b/data/examples/print]
Writes <name>.pdf to print at 100 %, fold along the marks on the left edge and scan
or photograph, and <name>.txt with the printed text in reading order, the reference
a transcription is compared with (blocks separated by a blank line, table cells by a
tab). Everything in the letters is invented: the authorities, the people, the streets,
the places Musterwil (9999) and Exempleville (1999) and the `.example` web and e-mail
addresses; the phone numbers follow track_2b/data/examples/README.md; the IBANs carry the check
digits 00 and the AHV number a wrong check digit, so none of them can be a real one.
"""

from __future__ import annotations

import argparse
import math
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

LEFT = 25.0  # mm
RIGHT = 190.0
WIDTH = RIGHT - LEFT
WINDOW_X = 118.0  # address field of a Swiss envelope with the window on the right
WINDOW_Y = 48.0
BOTTOM = 279.0  # body text ends above the footer
BLACK = (0, 0, 0)
GREY = (95, 95, 95)
INK = (25, 45, 140)

Colour = tuple[int, int, int]


class Letter(FPDF):
    """An A4 letter that records every text it prints, in reading order."""

    def __init__(self, title: str) -> None:
        super().__init__(unit="mm", format="A4")
        self.set_auto_page_break(False)
        self.set_margins(LEFT, 15, 210 - RIGHT)
        self.set_title(title)
        self.set_author("Leicht·Facile test letter")
        self.set_creation_date(datetime(2026, 10, 7, tzinfo=UTC))
        self.blocks: list[list[str]] = []

    def transcript(self) -> str:
        return "\n\n".join("\n".join(block) for block in self.blocks) + "\n"

    def font(self, size: float, style: str = "", colour: Colour = BLACK) -> None:
        self.set_font("Helvetica", style=style, size=size)
        self.set_text_color(*colour)

    def rule(self, x1: float, y: float, x2: float, colour: Colour = BLACK) -> None:
        self.set_draw_color(*colour)
        self.set_line_width(0.2)
        self.line(x1, y, x2, y)

    def fits(self) -> None:
        if self.get_y() > BOTTOM:
            raise SystemExit(f"{self.title}: page {self.page} runs into the footer")

    def put(
        self,
        x: float,
        y: float,
        text: str,
        size: float = 10.0,
        style: str = "",
        colour: Colour = BLACK,
        new_block: bool = True,
        align: str = "L",
        w: float = 0.0,
    ) -> float:
        """One line with its top at y, recorded as a new block or as the next line of
        the last one. Returns the y below it."""
        h = size * 0.42
        self.font(size, style, colour)
        self.set_xy(x, y)
        self.cell(w, h, text, align=align)
        if new_block:
            self.blocks.append([text])
        else:
            self.blocks[-1].append(text)
        return y + h

    def para(
        self,
        text: str,
        size: float = 10.0,
        style: str = "",
        gap: float = 3.0,
        bullet: str = "",
    ) -> None:
        """A wrapped paragraph at the current y; a bullet hangs in the left margin."""
        h = size * 0.46
        y = self.get_y()
        self.font(size, style)
        x = LEFT
        if bullet:
            self.set_xy(LEFT, y)
            self.cell(5, h, bullet)
            x = LEFT + 5
        self.set_xy(x, y)
        self.multi_cell(RIGHT - x, h, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.blocks.append([f"{bullet} {text}" if bullet else text])
        self.set_y(self.get_y() + gap)
        self.fits()

    def table(self, rows: list[tuple[str, str, str]], size: float = 10.0) -> None:
        """Label and right-aligned amount per row; kind "H" is the header (rule below),
        "T" a total (bold, rule above)."""
        h = size * 0.55
        col = 135.0
        lines = []
        for label, amount, kind in rows:
            y = self.get_y()
            if kind == "T":
                self.rule(LEFT, y, RIGHT)
            self.font(size, "B" if kind in ("H", "T") else "")
            if self.get_string_width(label) > col - 2:
                raise SystemExit(f"{self.title}: table label too wide: {label}")
            self.set_xy(LEFT, y + 0.5)
            self.cell(col, h, label)
            self.cell(WIDTH - col, h, amount, align="R")
            if kind == "H":
                self.rule(LEFT, y + h + 0.8, RIGHT)
            self.set_y(y + h + 1.1)
            lines.append(f"{label}\t{amount}")
        self.blocks.append(lines)
        self.set_y(self.get_y() + 3)
        self.fits()

    def pairs(self, x: float, y: float, rows: list[tuple[str, str]]) -> None:
        """A reference block: grey label, black value."""
        h = 4.0
        for label, value in rows:
            self.font(8.5, colour=GREY)
            self.set_xy(x, y)
            self.cell(27, h, label)
            self.font(8.5)
            self.cell(0, h, value)
            y += h
        self.blocks.append([f"{label}\t{value}" for label, value in rows])

    def window(self, postage: str, service: str, address: list[str]) -> None:
        """The postage line and the recipient, inside the envelope's window."""
        y = self.put(WINDOW_X, WINDOW_Y, postage, 7, colour=GREY)
        self.put(WINDOW_X, WINDOW_Y, service, 7, "B", new_block=False, align="R",
                 w=RIGHT - WINDOW_X)  # fmt: skip
        self.rule(WINDOW_X, y + 0.8, RIGHT, GREY)
        y += 4.5
        for i, line in enumerate(address):
            y = self.put(WINDOW_X, y, line, 10.5, new_block=i == 0) + 0.7

    def page_header(self, text: str) -> None:
        self.put(LEFT, 15, text, 8, colour=GREY)
        self.rule(LEFT, 19.5, RIGHT, GREY)
        self.set_y(28)

    def footer_lines(self, lines: list[str], page: str = "") -> None:
        self.rule(LEFT, 281, RIGHT, GREY)
        y = 282.5
        for i, line in enumerate(lines):
            y = self.put(LEFT, y, line, 7.5, colour=GREY, new_block=i == 0) + 0.6
        if page:
            self.put(LEFT, 282.5, page, 7.5, colour=GREY, new_block=False, align="R")

    def fold_marks(self) -> None:
        """Fold marks at 105 and 210 mm and the punch mark at 148.5 mm (DIN 5008 B)."""
        self.set_draw_color(*GREY)
        self.set_line_width(0.2)
        for y, length in ((105.0, 5.0), (148.5, 3.0), (210.0, 5.0)):
            self.line(6, y, 6 + length, y)

    def signature(self, x: float, y: float, length: float, loops: int) -> None:
        """A handwritten-looking stroke, drawn, not text."""
        points = []
        steps = 200
        for i in range(steps + 1):
            t = i / steps
            a = 2 * math.pi * loops * t
            points.append(
                (
                    x + length * t + 2.2 * math.cos(a),
                    y + 5 - 3.4 * math.sin(a) * (1 - 0.6 * t) - 2.2 * math.sin(math.pi * t),
                )
            )
        self.set_draw_color(*INK)
        self.set_line_width(0.35)
        self.polyline(points)


def tax_reminder() -> Letter:
    """German, one page: a payment reminder with a table, an IBAN and a deadline."""
    pdf = Letter("1. Mahnung: Staats- und Gemeindesteuern 2025")
    pdf.add_page()
    pdf.fold_marks()
    pdf.set_fill_color(0, 95, 115)
    pdf.rect(LEFT, 15, 13, 13, style="F")
    pdf.set_fill_color(255, 255, 255)
    pdf.ellipse(LEFT + 3.5, 18.5, 6, 6, style="F")
    y = pdf.put(42, 15.5, "Gemeinde Musterwil", 14, "B")
    pdf.put(42, y + 1, "Steueramt", 11, new_block=False)

    pdf.pairs(
        LEFT,
        WINDOW_Y,
        [
            ("Steuernummer", "41.087.736"),
            ("Ansprechperson", "Petra Musterli"),
            ("Telefon direkt", "044 123 45 70"),
            ("E-Mail", "petra.musterli@musterwil.example"),
        ],
    )
    pdf.window(
        "P.P. CH-9999 Musterwil",
        "B-Post",
        ["Herr Thomas Beispiel", "Fiktivweg 7", "9999 Musterwil"],
    )
    pdf.put(LEFT, 92, "Musterwil, 5. Oktober 2026")
    pdf.put(LEFT, 101, "1. Mahnung: Staats- und Gemeindesteuern 2025", 12, "B")

    pdf.set_y(109)
    pdf.para("Sehr geehrter Herr Beispiel")
    pdf.para(
        "Gemäss unserer Buchhaltung ist die Schlussrechnung für die Staats- und "
        "Gemeindesteuern 2025 vom 12. Juni 2026 noch nicht vollständig bezahlt. Die "
        "Zahlungsfrist ist am 12. Juli 2026 abgelaufen. Der offene Betrag setzt sich wie "
        "folgt zusammen:"
    )
    pdf.table(
        [
            ("Position", "Betrag in CHF", "H"),
            ("Schlussrechnung Staats- und Gemeindesteuern 2025", "4'386.40", ""),
            ("Ihre Zahlungen bis 30. September 2026", "-2'000.00", ""),
            ("Verzugszins 4,5 % vom 13. Juli bis 30. September 2026 (78 Tage)", "23.25", ""),
            ("Mahngebühr", "20.00", ""),
            ("Offener Betrag", "2'429.65", "T"),
        ]
    )
    pdf.para(
        "Bitte überweisen Sie den offenen Betrag von CHF 2'429.65 bis spätestens "
        "4. November 2026 auf das Konto der Gemeinde Musterwil, IBAN "
        "CH00 0839 4100 2786 5310 4. Geben Sie als Zahlungszweck Ihre Steuernummer "
        "41.087.736 an."
    )
    pdf.para(
        "Können Sie den Betrag nicht auf einmal bezahlen, so können Sie bis zum gleichen "
        "Datum schriftlich eine Ratenzahlung beantragen. Begründen Sie Ihr Gesuch und legen "
        "Sie eine Aufstellung Ihrer Einnahmen und Ausgaben bei."
    )
    pdf.para(
        "Geht bis zum 4. November 2026 weder die Zahlung noch ein Gesuch ein, leiten wir "
        "ohne weitere Mitteilung die Betreibung ein. Die Kosten der Betreibung gehen zu "
        "Ihren Lasten, und der Verzugszins läuft bis zum Tag der Zahlung weiter. Haben Sie "
        "den Betrag in den letzten Tagen bereits überwiesen, so betrachten Sie diese "
        "Mahnung als gegenstandslos."
    )
    pdf.para(
        "Für Fragen erreichen Sie uns von Montag bis Freitag, 8.00 bis 11.45 Uhr und "
        "13.30 bis 16.30 Uhr, unter Telefon 044 123 45 67 oder per E-Mail an "
        "steueramt@musterwil.example."
    )
    pdf.para("Freundliche Grüsse", gap=1.5)
    y = pdf.put(LEFT, pdf.get_y(), "Steueramt Musterwil")
    pdf.signature(LEFT + 2, y + 1, 30, 5)
    y = pdf.put(LEFT, y + 11, "Petra Musterli")
    pdf.set_y(pdf.put(LEFT, y + 0.5, "Sachbearbeiterin Steuerbezug", new_block=False))
    pdf.fits()
    pdf.footer_lines(
        [
            "Gemeinde Musterwil · Steueramt · Dorfstrasse 1 · Postfach · 9999 Musterwil",
            "Telefon 044 123 45 67 · steueramt@musterwil.example · www.musterwil.example",
        ]
    )
    return pdf


def grant_decision() -> Letter:
    """French, two pages: a registered decision with an AHV number, a calculation,
    payment dates, duties and the means of appeal."""
    footer = [
        "Canton d'Exempleville · Office des bourses d'études · Rue de l'Essai 3 · "
        "Case postale · 1999 Exempleville",
        "Téléphone 022 123 45 67 · bourses@exempleville.example · www.exempleville.example/bourses",
    ]
    pdf = Letter("Décision d'octroi d'une bourse d'études 2026-2027")
    pdf.add_page()
    pdf.fold_marks()
    pdf.set_fill_color(30, 110, 60)
    pdf.polygon([(LEFT, 15), (LEFT + 12, 15), (LEFT + 12, 23), (LEFT + 6, 29), (LEFT, 23)],
                style="F")  # fmt: skip
    pdf.set_fill_color(255, 255, 255)
    pdf.polygon([(LEFT + 6, 15), (LEFT + 12, 15), (LEFT + 12, 23), (LEFT + 6, 29)], style="F")
    pdf.set_draw_color(30, 110, 60)
    pdf.set_line_width(0.4)
    pdf.polygon([(LEFT, 15), (LEFT + 12, 15), (LEFT + 12, 23), (LEFT + 6, 29), (LEFT, 23)],
                style="D")  # fmt: skip
    y = pdf.put(42, 15, "Canton d'Exempleville", 13, "B")
    y = pdf.put(42, y + 1, "Département de la formation", 9.5, new_block=False)
    pdf.put(42, y + 0.5, "Office des bourses d'études", 9.5, "B", new_block=False)

    pdf.pairs(
        LEFT,
        WINDOW_Y,
        [
            ("N° de dossier", "BE-2026-04187"),
            ("N° AVS", "756.4719.2083.50"),
            ("Gestionnaire", "Marc Modèle"),
            ("Tél. direct", "022 123 45 68"),
            ("Courriel", "marc.modele@exempleville.example"),
        ],
    )
    pdf.window(
        "P.P. CH-1999 Exempleville",
        "RECOMMANDÉ",
        ["Madame", "Camille Exemple", "Chemin des Essais 14", "1999 Exempleville"],
    )
    pdf.put(LEFT, 92, "Exempleville, le 2 octobre 2026")
    pdf.put(
        LEFT, 101, "Décision d'octroi d'une bourse d'études pour l'année de formation 2026-2027",
        11.5, "B",
    )  # fmt: skip

    pdf.set_y(111)
    pdf.para("Madame,")
    pdf.para(
        "Nous avons examiné votre demande de bourse du 18 août 2026 pour votre formation de "
        "laborantine CFC (2e année) à l'École professionnelle d'Exempleville. Sur la base "
        "des documents remis, nous rendons la décision suivante :"
    )
    pdf.para("1. Montant de la bourse", 10.5, "B", gap=1.5)
    pdf.table(
        [
            ("Calcul", "CHF", "H"),
            ("Frais de formation reconnus", "3'200.00", ""),
            ("Frais d'entretien reconnus", "14'760.00", ""),
            ("Total des frais reconnus", "17'960.00", "T"),
            ("Revenu propre (salaire d'apprentissage)", "-9'880.00", ""),
            ("Contribution des parents", "-3'450.00", ""),
            ("Bourse annuelle octroyée", "4'630.00", "T"),
        ]
    )
    pdf.para("2. Versement", 10.5, "B", gap=1.5)
    pdf.para(
        "La bourse est versée en deux tranches sur votre compte IBAN CH00 0571 2009 4417 6382 9 :",
        gap=1.5,
    )
    pdf.para("1re tranche de CHF 2'315.00 le 30 octobre 2026 ;", gap=1, bullet="-")
    pdf.para(
        "2e tranche de CHF 2'315.00 le 26 février 2027, à condition que nous ayons reçu "
        "d'ici au 31 janvier 2027 votre attestation de formation du 2e semestre.",
        bullet="-",
    )
    pdf.para("3. Vos obligations", 10.5, "B", gap=1.5)
    pdf.para(
        "Vous devez nous annoncer dans un délai de 14 jours tout changement de votre "
        "situation, en particulier un arrêt ou une interruption de la formation, un "
        "changement de domicile ou une augmentation de votre revenu de plus de "
        "CHF 1'000.00 par année. Les montants perçus à tort doivent être remboursés."
    )
    pdf.footer_lines(footer, "Page 1/2")

    pdf.add_page()
    pdf.page_header(
        "Office des bourses d'études · Décision du 2 octobre 2026 · Dossier BE-2026-04187"
    )
    pdf.para("4. Nouvelle demande", 10.5, "B", gap=1.5)
    pdf.para(
        "La bourse est octroyée pour l'année de formation 2026-2027 seulement. Pour l'année "
        "2027-2028, vous devez déposer une nouvelle demande d'ici au 30 juin 2027."
    )
    pdf.para(
        "Pour toute question, votre gestionnaire de dossier, M. Marc Modèle, est à votre "
        "disposition du lundi au jeudi de 9 h à 12 h au 022 123 45 67 ou par courriel à "
        "bourses@exempleville.example."
    )
    pdf.para("Veuillez agréer, Madame, nos salutations distinguées.", gap=5)
    y = pdf.put(LEFT, pdf.get_y(), "Office des bourses d'études")
    pdf.signature(LEFT + 2, y + 1, 28, 4)
    pdf.signature(102, y + 1.5, 24, 6)
    y += 12
    below = pdf.put(LEFT, y, "Sophie Essai")
    pdf.put(LEFT, below + 0.5, "cheffe de service", new_block=False)
    pdf.put(100, y, "Marc Modèle")
    pdf.put(100, below + 0.5, "gestionnaire de dossier", new_block=False)
    pdf.set_y(below + 14)

    top = pdf.get_y()
    pdf.para("Voies de droit", 9, "B", gap=1)
    pdf.para(
        "La présente décision peut faire l'objet d'une réclamation écrite auprès de "
        "l'Office des bourses d'études, Rue de l'Essai 3, case postale, 1999 Exempleville, "
        "dans un délai de 30 jours dès sa notification. La réclamation est motivée et "
        "signée; elle indique les conclusions et est accompagnée d'une copie de la présente "
        "décision. La procédure de réclamation est gratuite.",
        8.5,
        gap=0,
    )
    pdf.set_draw_color(*GREY)
    pdf.set_line_width(0.6)
    pdf.line(LEFT - 3, top, LEFT - 3, pdf.get_y())
    pdf.footer_lines(footer, "Page 2/2")
    return pdf


LETTERS: dict[str, Callable[[], Letter]] = {
    "steuermahnung-brief": tax_reminder,
    "bourse-etudes-decision": grant_decision,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("track_2b/data/examples/print"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, build in LETTERS.items():
        pdf = build()
        pdf.output(str(args.out / f"{name}.pdf"))
        (args.out / f"{name}.txt").write_text(pdf.transcript(), encoding="utf-8", newline="\n")
        print(f"written: {args.out / name}.pdf ({pdf.pages_count} pages) and .txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
