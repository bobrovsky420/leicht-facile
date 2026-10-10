from __future__ import annotations

import pytest

from leichtfacile.ingest.segment import Unit, build_segments, split_sentences

GERMAN = [
    (
        "Die Frist endet am 31. März 2026. Danach ist es zu spät.",
        ["Die Frist endet am 31. März 2026.", "Danach ist es zu spät."],
    ),
    (
        "Bis zum 15. Juli können Sie die Frist verlängern. Das kostet Geld.",
        ["Bis zum 15. Juli können Sie die Frist verlängern.", "Das kostet Geld."],
    ),
    (
        "Gemäss Art. 5 Abs. 2 IPVG haben Sie Anspruch. Bitte melden Sie sich.",
        ["Gemäss Art. 5 Abs. 2 IPVG haben Sie Anspruch.", "Bitte melden Sie sich."],
    ),
    (
        "Gemäss Art. 12 Abs. 3 lit. a KVG gilt das. Danke.",
        ["Gemäss Art. 12 Abs. 3 lit. a KVG gilt das.", "Danke."],
    ),
    (
        "Sie brauchen Unterlagen, z. B. einen Ausweis. Bringen Sie alles mit.",
        ["Sie brauchen Unterlagen, z. B. einen Ausweis.", "Bringen Sie alles mit."],
    ),
    (
        "Sie brauchen Unterlagen, z.B. einen Ausweis. Bringen Sie alles mit.",
        ["Sie brauchen Unterlagen, z.B. einen Ausweis.", "Bringen Sie alles mit."],
    ),
    (
        "Sie können anrufen bzw. schreiben. Wir helfen gern.",
        ["Sie können anrufen bzw. schreiben.", "Wir helfen gern."],
    ),
    (
        "Das kostet ca. 20 Franken. Sie zahlen bar.",
        ["Das kostet ca. 20 Franken.", "Sie zahlen bar."],
    ),
    (
        "Füllen Sie das Formular Nr. 5100 aus. Senden Sie es zurück.",
        ["Füllen Sie das Formular Nr. 5100 aus.", "Senden Sie es zurück."],
    ),
    (
        "Die Gebühr beträgt Fr. 60.- pro Jahr. Sie zahlen online.",
        ["Die Gebühr beträgt Fr. 60.- pro Jahr.", "Sie zahlen online."],
    ),
    ("Das Amt ist in St. Gallen. Es ist offen.", ["Das Amt ist in St. Gallen.", "Es ist offen."]),
    ("Fragen Sie Dr. med. Muster. Er hilft.", ["Fragen Sie Dr. med. Muster.", "Er hilft."]),
    (
        "Der Preis ist inkl. MWST angegeben. Alles klar.",
        ["Der Preis ist inkl. MWST angegeben.", "Alles klar."],
    ),
    (
        "Brot, Milch, Käse usw. kaufen Sie selbst. Danke.",
        ["Brot, Milch, Käse usw. kaufen Sie selbst.", "Danke."],
    ),
    (
        "Brot, Milch, Käse usw. Danach gehen Sie heim.",
        ["Brot, Milch, Käse usw.", "Danach gehen Sie heim."],
    ),
    (
        "Rufen Sie an: 044 123 45 67. Wir sind da.",
        ["Rufen Sie an: 044 123 45 67.", "Wir sind da."],
    ),
    ("Es gilt ab dem 1.1.2026. Danke.", ["Es gilt ab dem 1.1.2026.", "Danke."]),
    ("Bitte bezahlen Sie bis 31.03.2026. Danke.", ["Bitte bezahlen Sie bis 31.03.2026.", "Danke."]),
    ("Es kostet 60 Fr. Das ist günstig.", ["Es kostet 60 Fr.", "Das ist günstig."]),
    ("Er bekommt die 2. Mahnung. Sie ist teuer.", ["Er bekommt die 2. Mahnung.", "Sie ist teuer."]),
    (
        "Die Kosten (ca. 20 Fr.) übernimmt der Kanton. Gut.",
        ["Die Kosten (ca. 20 Fr.) übernimmt der Kanton.", "Gut."],
    ),
    (
        "Die Adresse ist Bahnhofstr. 5 in Bern. Kommen Sie vorbei.",
        ["Die Adresse ist Bahnhofstr. 5 in Bern.", "Kommen Sie vorbei."],
    ),
    (
        "Was kostet das? Das kostet 20 Franken!",
        ["Was kostet das?", "Das kostet 20 Franken!"],
    ),
    (
        "\u00abSo viel müssen Sie bezahlen.\u00bb Danach kommt die Rechnung.",
        ["\u00abSo viel müssen Sie bezahlen.\u00bb", "Danach kommt die Rechnung."],
    ),
    (
        "Manchmal gibt es eine Hitze·welle. \u00abHitze·welle\u00bb bedeutet: Es ist heiss.",
        ["Manchmal gibt es eine Hitze·welle.", "\u00abHitze·welle\u00bb bedeutet: Es ist heiss."],
    ),
    (
        "Das gilt für alle. (Ausnahmen stehen unten.) Danke.",
        ["Das gilt für alle.", "(Ausnahmen stehen unten.)", "Danke."],
    ),
]

FRENCH = [
    ("Vous pouvez p. ex. appeler. Merci.", ["Vous pouvez p. ex. appeler.", "Merci."]),
    (
        "Selon l'art. 12 al. 3 de la loi, vous avez droit. Merci.",
        ["Selon l'art. 12 al. 3 de la loi, vous avez droit.", "Merci."],
    ),
    (
        "Selon l\u2019art. 5 al. 2 LAMal, vous payez. Merci.",
        ["Selon l\u2019art. 5 al. 2 LAMal, vous payez.", "Merci."],
    ),
    ("Écrivez à M. Dupont. Il répond vite.", ["Écrivez à M. Dupont.", "Il répond vite."]),
    (
        "Le délai est le 31 mars 2026. Après, c'est trop tard.",
        ["Le délai est le 31 mars 2026.", "Après, c'est trop tard."],
    ),
    ("Le prix est env. 20 francs. Merci.", ["Le prix est env. 20 francs.", "Merci."]),
    ("Vous payez 20 fr. par mois. Merci.", ["Vous payez 20 fr. par mois.", "Merci."]),
    ("Des formulaires, etc. Merci.", ["Des formulaires, etc.", "Merci."]),
]

ITALIAN = [
    (
        "Documenti, moduli ecc. sono necessari. Grazie.",
        ["Documenti, moduli ecc. sono necessari.", "Grazie."],
    ),
    ("Documenti, moduli ecc. Grazie.", ["Documenti, moduli ecc.", "Grazie."]),
    (
        "Per esempio, p. es. il passaporto. Grazie.",
        ["Per esempio, p. es. il passaporto.", "Grazie."],
    ),
    (
        "Secondo l'art. 5 cpv. 2 della legge, pagate. Grazie.",
        ["Secondo l'art. 5 cpv. 2 della legge, pagate.", "Grazie."],
    ),
    ("Scriva al Sig. Rossi. Grazie.", ["Scriva al Sig. Rossi.", "Grazie."]),
    ("Scriva alla Sig.ra Bianchi. Grazie.", ["Scriva alla Sig.ra Bianchi.", "Grazie."]),
    (
        "Il termine scade il 31 marzo 2026. Grazie.",
        ["Il termine scade il 31 marzo 2026.", "Grazie."],
    ),
    ("Il costo è di fr. 20. Grazie.", ["Il costo è di fr. 20.", "Grazie."]),
]


@pytest.mark.parametrize(("text", "expected"), GERMAN)
def test_german_sentences(text, expected):
    assert split_sentences(text, "de") == expected


@pytest.mark.parametrize(("text", "expected"), FRENCH)
def test_french_sentences(text, expected):
    assert split_sentences(text, "fr") == expected


@pytest.mark.parametrize(("text", "expected"), ITALIAN)
def test_italian_sentences(text, expected):
    assert split_sentences(text, "it") == expected


def test_empty_and_unsupported():
    assert split_sentences("   ", "de") == []
    with pytest.raises(ValueError, match="unsupported language"):
        split_sentences("Hello.", "en")


def test_build_segments():
    units = [
        Unit("heading", "Merkblatt", heading_level=1, page=1),
        Unit("paragraph", "Die Frist endet am 31. März 2026. Danach ist es zu spät.", page=1),
        Unit("heading", "Kosten", heading_level=2, page=1),
        Unit("list_item", "Bis 15. Juli: 20 Franken. Online gratis.", page=2),
        Unit("paragraph", "   ", page=2),
        Unit("table_cell", "60 Franken", page=2),
        Unit("heading", "Kontakt", page=2),  # no level: 2
        Unit("heading", "Telefon", heading_level=3, page=2),
        Unit("paragraph", "044 123 45 67", page=2),
        Unit("heading", "Anhang", heading_level=1, page=3),
    ]
    segments = build_segments(units, "de")
    assert [s.id for s in segments] == [f"s{i:04d}" for i in range(1, 12)]
    assert [(s.kind, s.text) for s in segments] == [
        ("heading", "Merkblatt"),
        ("paragraph", "Die Frist endet am 31. März 2026."),
        ("paragraph", "Danach ist es zu spät."),
        ("heading", "Kosten"),
        ("list_item", "Bis 15. Juli: 20 Franken."),
        ("list_item", "Online gratis."),
        ("table_cell", "60 Franken"),
        ("heading", "Kontakt"),
        ("heading", "Telefon"),
        ("paragraph", "044 123 45 67"),
        ("heading", "Anhang"),
    ]
    assert [s.para for s in segments] == [0, 1, 1, 2, 3, 3, 4, 5, 6, 7, 8]
    assert [s.heading_level for s in segments] == [
        1,
        None,
        None,
        2,
        None,
        None,
        None,
        2,
        3,
        None,
        1,
    ]
    assert [s.heading_path for s in segments] == [
        [],
        ["Merkblatt"],
        ["Merkblatt"],
        ["Merkblatt"],
        ["Merkblatt", "Kosten"],
        ["Merkblatt", "Kosten"],
        ["Merkblatt", "Kosten"],
        ["Merkblatt"],
        ["Merkblatt", "Kontakt"],
        ["Merkblatt", "Kontakt", "Telefon"],
        [],
    ]
    assert [s.page for s in segments] == [1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3]


def test_build_segments_normalises_text():
    segments = build_segments(
        [Unit("paragraph", "Merk\u2022blatt  für\u00a0Sie.\nNeue Zeile.")], "de"
    )
    assert [s.text for s in segments] == ["Merk\u00b7blatt für Sie.", "Neue Zeile."]
