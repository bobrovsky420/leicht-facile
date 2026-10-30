"""HTML ingest on hand-written pages shaped like Swiss official pages (no real page texts)."""

from __future__ import annotations

import pytest

from leichtfacile.ingest import html
from leichtfacile.ingest.html import decode_html, extract_html
from leichtfacile.ingest.segment import Unit

PAGE = """<!doctype html>
<html lang="de">
<head>
<title>Steuern verstehen | Kanton Muster</title>
<meta property="og:title" content="Steuern verstehen">
<style>.x { color: red; }</style>
<script>var hotline = "044 999 99 99";</script>
</head>
<body>
<div class="cookie-banner" id="cookie-consent"><p>Wir verwenden Cookies. Sind Sie mit allen
Cookies einverstanden?</p><button>Akzeptieren</button></div>
<header><nav><ul><li><a href="/">Startseite</a></li><li><a href="/steuern">Steuern</a></li>
<li><a href="/kontakt">Kontakt</a></li></ul></nav></header>
<main>
<div class="lang-switch"><h2>Diese Seite gibt es in:</h2><ul><li><a href="/fr">Français</a></li>
<li><a href="/it">Italiano</a></li><li><a href="/ls">Leichte Sprache</a></li></ul></div>
<h1>Steuern verstehen</h1>
<p>Alle Menschen im Kanton zahlen Steuern. Mit dem Geld bezahlt der Kanton Schulen, Spitäler
und Strassen.<span class="visually-hidden"> Hinweis für Screenreader.</span></p>
<p>Die Steuer-Erklärung müssen Sie jedes Jahr ausfüllen. Sie bekommen dafür einen Brief vom
Steueramt. Im Brief steht, bis wann Sie die Steuer-Erklärung schicken müssen.</p>
<h2>Fristen</h2>
<p>Die Frist endet am <strong>15. März</strong>. Sie können die Frist verlängern. Dafür bezahlen
Sie eine Gebühr.</p>
<ul><li>Bis 15. Juli zahlen Sie 20 Franken.</li>
<li>Bis 15. September zahlen Sie 40 Franken.</li></ul>
<div class="accordion">
  <button aria-expanded="false" aria-controls="panel-1" id="button-1"><h3>Wie viel kostet die
  Verlängerung im Internet?</h3></button>
  <div id="panel-1" role="region" aria-labelledby="button-1" aria-hidden="true"
    style="display:none;">
    <p>Im Internet ist die Verlängerung billiger. Bis 15. Juli ist sie gratis.</p>
  </div>
</div>
<h2>Gebühren</h2>
<table><tr><th>Frist</th><th>Gebühr</th></tr><tr><td>15. Juli</td><td>20 Franken</td></tr>
<tr><td>15. September</td><td>40 Franken</td></tr></table>
<p>- Die Gebühr steht auf der Rechnung.</p>
<div class="feedback"><h2>Ist diese Seite verständlich?</h2><div><button>Ja</button>
<button>Nein</button></div></div>
</main>
<footer><p>Kanton Muster, Musterstrasse 1, 9999 Musterdorf</p>
<ul><li><a href="/i">Impressum</a></li>
<li><a href="/d">Datenschutz</a></li></ul></footer>
</body>
</html>"""


def test_main_content_with_structure():
    title, units = extract_html(PAGE, "https://www.example.ch/steuern.html")
    assert title == "Steuern verstehen"
    by_text = {u.text: u for u in units}
    assert by_text["Steuern verstehen"].kind == "heading"
    assert by_text["Steuern verstehen"].heading_level == 1
    assert by_text["Fristen"].heading_level == 2
    assert by_text["Bis 15. Juli zahlen Sie 20 Franken."].kind == "list_item"
    # accordion title and its hidden panel
    assert by_text["Wie viel kostet die Verlängerung im Internet?"].kind == "heading"
    assert by_text["Wie viel kostet die Verlängerung im Internet?"].heading_level == 3
    assert "Im Internet ist die Verlängerung billiger. Bis 15. Juli ist sie gratis." in by_text
    # table cells and a paragraph that starts with a bullet
    assert [u.text for u in units if u.kind == "table_cell"] == [
        "Frist",
        "Gebühr",
        "15. Juli",
        "20 Franken",
        "15. September",
        "40 Franken",
    ]
    assert by_text["Die Gebühr steht auf der Rechnung."].kind == "list_item"
    # inline formatting does not glue words
    assert "Die Frist endet am 15. März. Sie können die Frist verlängern." in " ".join(by_text)


@pytest.mark.parametrize(
    "boilerplate",
    [
        "Cookies",
        "Startseite",
        "Diese Seite gibt es in",
        "Italiano",
        "Screenreader",
        "Ist diese Seite verständlich",
        "Impressum",
        "Musterstrasse",
        "999 99 99",
    ],
)
def test_boilerplate_is_dropped(boilerplate):
    _, units = extract_html(PAGE)
    assert not any(boilerplate in u.text for u in units)


def test_units_are_in_document_order():
    _, units = extract_html(PAGE)
    texts = [u.text for u in units]
    assert texts.index("Fristen") < texts.index("Bis 15. Juli zahlen Sie 20 Franken.")
    assert texts.index("Wie viel kostet die Verlängerung im Internet?") < texts.index("Gebühren")


# -- contact cards (zh.ch) and phone lines (be.ch) -------------------------------------

CARD = """
<div class="contactcontent"><div id="contact" class="mdl-contact" tabindex="-1">
  <div class="mdl-contact_entry">
    <div class="mdl-contact_entry__header">
      <h3 class="mdl-contact_entry__title"><a href="https://{slug}.example/">{name}</a></h3>
      <p class="mdl-contact_entry__infotext">Für Frauen und Kinder</p>
    </div>
    <div class="mdl-contact_entry__section">
      <div class="mdl-contact_entry__section-cell">
        <div class="mdl-contact_entry__cell-icon">
          <h4 class="visuallyhidden">Telefon</h4><svg></svg></div>
        <div class="mdl-contact_entry__cell-content">
          <a class="mdl-contact_entry__phone" href="tel:+41{digits}">+41 {phone}</a>
          <div class="mdl-contact_entry__text"><p>Tag und Nacht</p></div>
        </div>
      </div>
      <div class="mdl-contact_entry__section-cell">
        <div class="mdl-contact_entry__cell-icon">
          <h4 class="visuallyhidden">E-Mail</h4><svg></svg></div>
        <div class="mdl-contact_entry__cell-content">
          <a class="mdl-contact_entry__mail" href="mailto:info@{slug}.example">
            info@{slug}.example</a>
        </div>
      </div>
    </div>
  </div>
</div></div>
"""

CARD_MUSTER = CARD.format(
    slug="frauenhaus-muster", name="Frauenhaus Muster", digits="521234567", phone="52 123 45 67"
)
CARD_BEISPIEL = CARD.format(
    slug="frauenhaus-beispiel",
    name="Frauenhaus Beispiel",
    digits="447654321",
    phone="44 765 43 21",
)

CARDS_PAGE = f"""<!doctype html><html lang="de"><head><title>Schutz bei Gewalt</title></head><body>
<header><nav><a href="/">Start</a></nav></header>
<main id="main"><div class="grid-x"><div class="cell">
<h1>Schutz bei Gewalt</h1>
<div class="mdl-richtext"><p>Wer zu Hause Gewalt erlebt, findet Schutz in einer Unterkunft. Die
Unterkünfte sind Tag und Nacht erreichbar und beraten auch am Telefon.</p>
<p>Die Beratung ist kostenlos und vertraulich. Sie können anonym bleiben.</p></div>
<div class="mdl-richtext"><h2>Frauenhäuser</h2></div>
{CARD_MUSTER}
{CARD_BEISPIEL}
<div class="mdl-richtext"><h2>Weitere Angebote</h2><p>Die Opferhilfe berät Betroffene von Gewalt
und hilft bei Fragen zu Geld, Recht und Unterkunft.</p></div>
</div></div></main>
<footer><p>Kanton Muster, Telefon +41 99 999 99 99</p></footer>
</body></html>"""


def test_contact_cards_survive_extraction():
    _, units = extract_html(CARDS_PAGE)
    texts = [u.text for u in units]
    for fact in (
        "+41 52 123 45 67",
        "info@frauenhaus-muster.example",
        "+41 44 765 43 21",
        "info@frauenhaus-beispiel.example",
    ):
        assert any(fact in text for text in texts), fact
    assert not any("99 999 99 99" in text for text in texts)  # the page footer stays out
    first = next(i for i, t in enumerate(texts) if "52 123 45 67" in t)
    second = texts.index("Frauenhaus Beispiel")
    assert texts.index("Frauenhaus Muster") < first < second


def test_rescue_inserts_missing_contact_facts_at_their_place():
    # trafilatura often keeps the card titles and drops the numbers (zh.ch)
    tree = html._prepare(html._parse(CARDS_PAGE))
    kept = [
        Unit("heading", "Schutz bei Gewalt", heading_level=1),
        Unit("heading", "Frauenhäuser", heading_level=2),
        Unit("heading", "Frauenhaus Muster", heading_level=3),
        Unit("paragraph", "Für Frauen und Kinder"),
        Unit("heading", "Frauenhaus Beispiel", heading_level=3),
        Unit("paragraph", "Für Frauen und Kinder"),
        Unit("heading", "Weitere Angebote", heading_level=2),
    ]
    texts = [u.text for u in html._rescue_contacts(tree, kept)]
    assert texts == [
        "Schutz bei Gewalt",
        "Frauenhäuser",
        "Frauenhaus Muster",
        "Für Frauen und Kinder",
        "+41 52 123 45 67",
        "Tag und Nacht",
        "info@frauenhaus-muster.example",
        "Frauenhaus Beispiel",
        "Für Frauen und Kinder",
        "+41 44 765 43 21",
        "Tag und Nacht",
        "info@frauenhaus-beispiel.example",
        "Weitere Angebote",
    ]


def test_rescue_leaves_complete_extractions_alone():
    tree = html._prepare(html._parse(CARDS_PAGE))
    units = [Unit("paragraph", "+41 52 123 45 67 info@frauenhaus-muster.example")]
    units.append(Unit("paragraph", "Telefon 044 765 43 21, info@frauenhaus-beispiel.example"))
    assert html._rescue_contacts(tree, units) == units


def test_phone_numbers_in_links_are_kept():
    lines = "".join(
        f'<p><b>{name}: <a href="tel:{number}">{number}</a></b></p>'
        for name, number in [("Polizei", "117"), ("Feuerwehr", "118"), ("Sanität", "144")]
    )
    page = f"""<html><body><main><h1>Notfall</h1>
    <p>Bei einem Notfall brauchen Sie schnell Hilfe. Rufen Sie sofort die richtige Nummer an.
    Die Nummern sind gratis und Tag und Nacht erreichbar.</p>
    <h2>Wichtige Nummern</h2>{lines}
    <p>Sagen Sie am Telefon, wer Sie sind und wo Sie sind. Bleiben Sie am Telefon.</p></main>
    </body></html>"""
    _, units = extract_html(page)
    joined = " ".join(u.text for u in units)
    for expected in ("Polizei: 117", "Feuerwehr: 118", "Sanität: 144"):
        assert expected in joined


def test_fallback_for_tiny_pages():
    title, units = extract_html("<h2>Kurz</h2><p>Nur ein Satz.</p>")
    assert [(u.kind, u.text) for u in units] == [
        ("heading", "Kurz"),
        ("paragraph", "Nur ein Satz."),
    ]
    assert title is None  # no og:title, <title> or <h1>


# -- decoding ----------------------------------------------------------------------


def test_decode_html():
    latin = '<html><head><meta charset="iso-8859-1"></head><body>Prämie</body></html>'
    assert "Prämie" in decode_html(latin.encode("cp1252"))
    assert "Prämie" in decode_html("<p>Prämie</p>".encode()), "UTF-8 without declaration"
    assert decode_html(b"\xef\xbb\xbf<p>Pr\xc3\xa4mie</p>") == "<p>Prämie</p>"
    assert "Prämie" in decode_html("<p>Prämie</p>".encode("cp1252"), "windows-1252")


def test_contact_facts_read_the_bracketed_zero_as_the_trunk_prefix():
    # "+41 (0)44 123 45 67" and "044 123 45 67" are one number (rules/values.canonical_phone).
    assert html._facts("Tel. +41 (0)44 123 45 67 oder 044 123 45 67") == {"0441234567"}


def test_touching_inline_elements_get_a_space():
    # tirol.gv.at's contact boxes: the icon label and the value are two inline elements
    # with nothing between them and read "AdresseMeinhardstrasse 16" (29 October 2026);
    # a word split by markup and a punctuation mark after an element stay as they are.
    page = """<html><body><main><h1>Kindergeld Plus</h1>
    <p>Das Land unterstuetzt Familien mit geringem Einkommen. Der Antrag ist bis zum
    31. Dezember des Jahres zu stellen. Die Foerderung betraegt bis zu 550 Euro pro Kind.</p>
    <h2>Ansprechpersonen</h2>
    <div class="contact-box"><h5>Carmen Muster</h5>
    <p><span class="icon icon-pin" title="Adresse">Adresse</span><a
      href="https://maps.example/?q=1"><span>Musterstrasse 16, 6020 Innsbruck</span></a></p>
    <p><span class="icon icon-phone" title="Telefon">Telefon</span><a
      href="tel:+43-512-5087843"><span>+43 512 508 7843</span></a></p>
    <p><span class="icon icon-mail" title="E-Mail">E-Mail</span><a
      href="mailto:amt@tirol.example">amt@tirol.example</a></p></div>
    <p>Prae<b>mien</b>verbilligung gibt es in der <b>Schweiz</b>.
    Der Betrag ist in <b>Franken</b>.</p>
    </main></body></html>"""
    _, units = extract_html(page)
    texts = [u.text for u in units]
    assert "Adresse Musterstrasse 16, 6020 Innsbruck" in texts
    assert "Telefon +43 512 508 7843" in texts
    assert "E-Mail amt@tirol.example" in texts
    assert "Praemienverbilligung gibt es in der Schweiz. Der Betrag ist in Franken." in texts
