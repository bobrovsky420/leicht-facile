"""The vocabulary lists (rules/data/vocabulary_<name>.toml): well formed, no term twice
in a variety, every glossary explanation passes the checker at A2, the German split into
a shared file and country files, the spelling of Germany and Austria, and the matcher
finds the terms in their inflected, separated and abbreviated forms."""

from __future__ import annotations

import hashlib
import re
import tomllib
from collections import defaultdict
from importlib import resources

import pytest

from leichtfacile.rules import check_draft
from leichtfacile.rules.messages import render_finding
from leichtfacile.rules.vocabulary import (
    easy_for,
    load_vocabulary,
    matcher,
    office_words,
    read_vocabulary,
    standard_spelling,
    vocabulary_files,
    vocabulary_version,
)
from leichtfacile.schemas import Block, Draft, GlossaryEntry, base_lang

DATA = resources.files("leichtfacile.rules") / "data"
# The varieties: a language's shared file and the variety's own, as the loader reads them.
KEYS = ("de", "de-DE", "de-AT", "fr", "it")
# Every file as written, with the variety it belongs to: the shared German file and the
# Swiss one make the Swiss variety, de.
FILES = {"de": "de", "de-CH": "de", "de-DE": "de-DE", "de-AT": "de-AT", "fr": "fr", "it": "it"}
GERMAN_FILES = ("de", "de-CH", "de-DE", "de-AT")
# LEX-01 wants a Mediopunkt in long German words; code adds it to drafts at A2 only,
# so the level-neutral list keeps the plain spelling.
SKIP_RULES = {"LEX-01"}
DASHES = {chr(0x2013), chr(0x2014)}  # en and em dash: plain hyphen only
SHARP_S = chr(0xDF)  # every German file is written in the Swiss spelling: ss
# What makes an entry Swiss: an institution, the money, a procedure or a word of
# Switzerland (or of Switzerland and Austria). The shared German file has none.
SWISS_MARKERS = re.compile(
    r"\b(?:Kanton\w*|kantonal\w*|Franken|CHF|AHV|IV|IV-\w+|EL|ELG|KVG|KESB|RAV|Suva|Spitex|"
    r"SKOS|Betreibung\w*|Schweiz\w*|Spital\w*|Steueramt\w*|Einwohnerkontrolle|"
    r"Gemeindeversammlung|Zivilstand\w*|Entscheid|Entscheide|Entscheids|Einsprache\w*|"
    r"Rekurs\w*|Ausweis [BCFLS]|Franchise|Prämienverbilligung|Arztzeugnis|innert|"
    r"allfällig\w*|vorgängig\w*|gesamthaft|Pendenz\w*|Traktand\w*|\w*[Bb]ezüger\w*)\b"
)
# The German terms before the split into the shared file and vocabulary_de-CH.toml
# (29 October 2026), by kind and group: the Swiss variety keeps every one of them where
# it was. A deliberate change of the Swiss list updates this table.
SWISS_BEFORE_SPLIT = {
    "replace.connectors": (
        "innert|gemäss|bezüglich|hinsichtlich|betreffend|seitens|mittels|zwecks|infolge|"
        "aufgrund|anlässlich|zuzüglich|abzüglich|nebst|samt|exklusive|ungeachtet|mangels|"
        "sofern|falls|andernfalls|ansonsten|jedoch|indes|sowie|zudem|ferner|überdies|"
        "des Weiteren|ebenfalls|diesbezüglich|hierzu|hierfür|hiermit|beiliegend|"
        "in der Beilage|diesfalls|untenstehend|nachstehend|vorstehend|respektive|resp.|"
        "widrigenfalls|zulasten|namentlich|obgenannt|vorgenannt|vorliegend"
    ),
    "replace.adverbs": (
        "gegebenenfalls|nötigenfalls|allenfalls|allfällig|etwaig|unter Umständen|"
        "voraussichtlich|umgehend|unverzüglich|baldmöglichst|fristgerecht|fristgemäss|"
        "vorgängig|vorab|nachträglich|erneut|derzeit|künftig|fortan|bislang|sämtliche|"
        "lediglich|ausschliesslich|vollumfänglich|gesamthaft|grundsätzlich|zwingend|"
        "fakultativ|unentgeltlich|kostenpflichtig|befristet|unbefristet|wohnhaft|zuständig|"
        "minderjährig|volljährig|verstorben|säumig|in Verzug|berechtigt|verpflichtet|befugt|"
        "ledig|erwerbstätig|erwerbslos|angemessen|ausstehend|abschlägig|gegenstandslos|"
        "anspruchsberechtigt|alleinstehend|rückwirkend"
    ),
    "replace.verbs": (
        "einreichen|zustellen|übermitteln|retournieren|beilegen|beifügen|nachreichen|"
        "unterzeichnen|ersuchen|erachten|entrichten|begleichen|vergüten|rückerstatten|"
        "gewähren|erteilen|beanspruchen|in Anspruch nehmen|geltend machen|verwirken|"
        "erlöschen|mitteilen|in Kenntnis setzen|benachrichtigen|kontaktieren|vorweisen|"
        "vorlegen|bewilligen|genehmigen|ermächtigen|untersagen|abweisen|gutheissen|anfechten|"
        "widerrufen|sistieren|obliegen|ermitteln|festsetzen|bemessen|abklären|tätigen|"
        "vornehmen|durchführen|veranlassen|gewährleisten|sicherstellen|berücksichtigen|"
        "in Kraft treten|verfügen über|zur Auszahlung gelangen|bedürfen|offenlegen|"
        "verauslagen|veräussern"
    ),
    "replace.nouns": (
        "Amtsstelle|Wohnsitz|Domizil|Ehegatte|Ehegattin|Erziehungsberechtigte|Minderjährige|"
        "Hinterbliebene|Ableben|Drittperson|Gesuchsteller|Antragsteller|Leistungsbezüger|"
        "Gläubiger|Schuldner|Entgelt|Erwerbseinkommen|Erwerbstätigkeit|Vergütung|"
        "Aufwendungen|Auslagen|Rückerstattung|Restbetrag|Saldo|Ratenzahlung|Teilzahlung|"
        "Ermässigung|Vergünstigung|Beleg|Nachweis|Wegleitung|Vorschrift|Sachverhalt|"
        "Angelegenheit|Anliegen|Zuschrift|Eingabe|Korrespondenz|Mitteilung|Auskunft|"
        "Kenntnisnahme|Bewilligung|Einwilligung|Berechtigung|Verpflichtung|Abklärung|Bedarf|"
        "Inanspruchnahme|Einreichung|Kalenderjahr|Stichtag|Zeitraum|Inkrafttreten|Mietzins|"
        "Liegenschaft|Webauftritt|obligatorische Krankenpflegeversicherung|elterliche Sorge|"
        "Kindes- und Erwachsenenschutzbehörde|Beschwerdeführer|Rechtsgrundlage|"
        "Verfahrenskosten|Pauschale|Staatsangehörigkeit|Personalien|Wohnsitzgemeinde|"
        "Voraussetzung|Attest|Wegzug|Nachfrist|Sanktion"
    ),
    "replace.abbreviations": (
        "z. B.|bzw.|ggf.|evtl.|ca.|inkl.|exkl.|usw.|u. a.|d. h.|vgl.|Nr.|Tel.|Art.|Abs.|lit.|"
        "EL|IPV|KVG|ELG|BehiG"
    ),
    "replace.context": (
        "Schreiben|erhalten|beziehen|Bestimmung|aufheben|ausrichten|unterliegen|Auflage|"
        "Unterlagen|obligatorisch|Dienststelle|Beeinträchtigung|inklusive"
    ),
    "explain.law": (
        "Verfügung|Entscheid|Einsprache|Beschwerde|Rekurs|Rechtsmittel|Rechtsmittelbelehrung|"
        "rechtskräftig|Frist|Fristerstreckung|Gesuch|Anspruch|Nichteintreten|Beilage|"
        "Vollmacht|Gesetz|Gericht|Datenschutz|Schweigepflicht|KESB|Beistandschaft|Beistand|"
        "unentgeltliche Rechtspflege|Akteneinsicht|rechtliches Gehör|Zustellung|"
        "Mitwirkungspflicht|Meldepflicht|Rückerstattungspflicht|Härtefall|Urteilsfähigkeit|"
        "Handlungsfähigkeit|gesetzliche Vertretung|Vorsorgeauftrag|Patientenverfügung|"
        "fürsorgerische Unterbringung|Kindesschutzmassnahme|aufschiebende Wirkung|"
        "Kostenvorschuss|Wiedererwägung|Vorbescheid|Rückforderung|Weisung|Verjährung|"
        "Vorinstanz|vollstreckbar|Gefährdungsmeldung|Vormundschaft|Busse|Strafregisterauszug|"
        "Behörde|Merkblatt"
    ),
    "explain.debt": (
        "Mahnung|Betreibung|Betreibungsamt|Zahlungsbefehl|Rechtsvorschlag|Pfändung|"
        "Verlustschein|Existenzminimum|Inkasso|Schuldenberatung|Verrechnung|Verzugszins|"
        "Betreibungsregisterauszug|Lohnpfändung|Konkurs|Stundung|Rechtsöffnung|IBAN"
    ),
    "explain.insurance": (
        "Krankenkasse|Grundversicherung|Zusatzversicherung|Prämie|Prämienverbilligung|"
        "Franchise|Selbstbehalt|Kostenbeteiligung|Rente|AHV|IV|Ergänzungsleistungen|"
        "Hilflosenentschädigung|Assistenzbeitrag|Taggeld|Kostengutsprache|Hilfsmittel|"
        "Pensionskasse|Säule 3a|Arbeitslosenversicherung|RAV|Unfallversicherung|"
        "Leistungserbringer|Hausarztmodell|Versicherungspflicht|Generikum|Suva|"
        "Arbeitsunfähigkeit|Erwerbsunfähigkeit|Invaliditätsgrad|berufliche Eingliederung|"
        "Einspracheentscheid|Arbeitslosenentschädigung|Einstelltage|zumutbare Arbeit|"
        "Rahmenfrist|Beitragslücke|Mutterschaftsentschädigung|Familienzulage|Kinderzulage|"
        "Ausbildungszulage|anrechenbare Einnahmen|anerkannte Ausgaben|Vermögensverzehr|"
        "Verzichtsvermögen|Durchschnittsprämie|Prämienregion|Richtprämie|Sozialversicherung|"
        "Lebensbedarf|Freibetrag|Entschädigung"
    ),
    "explain.health": (
        "ambulant|stationär|Spitex|Arztzeugnis|Bedarfsabklärung|Opferhilfe|Gebärdensprache|"
        "barrierefrei"
    ),
    "explain.social": (
        "Sozialhilfe|Sozialdienst|Lohnausweis|Kündigungsfrist|Probezeit|Nebenkosten|"
        "Mietzinsdepot|Hausverwaltung|Sorgerecht|Obhut|Unterhaltsbeitrag|Zivilstand|"
        "verwitwet|Stipendium|Ausbildungsbeitrag|Konkubinat|Unterhaltspflicht|"
        "Mietzinsmaximum|Grundbedarf|Unterstützungseinheit|Alimentenbevorschussung|"
        "Nettomiete|Bruttomiete"
    ),
    "explain.tax": (
        "Steuererklärung|Veranlagung|provisorische Rechnung|Quellensteuer|Abzug|"
        "steuerbares Einkommen|massgebendes Einkommen|Vermögen|steuerpflichtig|Steuererlass|"
        "Zahlungserleichterung|Steuerperiode|Schlussrechnung|Nachsteuer|Ermessensveranlagung"
    ),
    "explain.residence": (
        "Aufenthaltsbewilligung|Niederlassungsbewilligung|Einwohnerkontrolle|Zivilstandsamt|"
        "Einbürgerung|Heimatort|vorläufige Aufnahme|Schutzstatus S|Familiennachzug"
    ),
    "explain.vote": (
        "Abstimmung|Stimmrecht|stimmberechtigt|Volksinitiative|Referendum|Gegenvorschlag|"
        "Stimmrechtsausweis|Urne|Kantonsrat|Regierungsrat|Gemeindeversammlung|Vernehmlassung|"
        "Verfassung"
    ),
    "explain.context": "Eröffnung|Wartezeit|Beitrag|Leistung|solidarisch|Forderung|Verordnung",
}


@pytest.mark.parametrize("key", KEYS)
def test_a_variety_has_every_term_once(key: str) -> None:
    entries = load_vocabulary(key)
    replace = [e for e in entries if e.kind == "replace"]
    explain = [e for e in entries if e.kind == "explain"]
    assert len(replace) >= 150 and len(explain) >= 90

    seen: dict[str, str] = {}
    for e in entries:
        term = e.term.casefold()
        assert term not in seen, f"{e.term!r} in {e.group} and {seen[term]}"
        seen[term] = e.group


@pytest.mark.parametrize("name", FILES)
def test_vocabulary_file_is_well_formed(name: str) -> None:
    for e in read_vocabulary(name):
        text = e.easy if e.kind == "replace" else e.explanation
        assert text and text == text.strip() and e.term == e.term.strip()
        assert not DASHES & set(e.term + text), e.term
        if name in GERMAN_FILES:
            assert SHARP_S not in e.term + text + "".join(e.not_in), e.term
        if e.kind == "replace":
            assert e.easy != e.term
        else:
            assert text[-1] in ".?", e.term


@pytest.mark.parametrize("key", ["de", "de-DE", "de-AT"])
def test_a_term_stands_in_one_file_of_a_variety(key: str) -> None:
    shared, own = (read_vocabulary(name) for name in vocabulary_files(key))
    assert {e.term.casefold() for e in shared} & {e.term.casefold() for e in own} == set()


@pytest.mark.parametrize("name", FILES)
def test_explanations_pass_the_checker(name: str) -> None:
    """Every file through the checker of its language at A2; the German files of all
    varieties through the Swiss one, since they are written in its spelling, with the
    explained terms of their variety as the glossary."""
    key = FILES[name]
    explain = [e for e in read_vocabulary(name) if e.kind == "explain"]
    glossary = [e for n in vocabulary_files(key) for e in read_vocabulary(n) if e.kind == "explain"]
    blocks, owner = [], {}
    for i, e in enumerate(explain):
        for j, sentence in enumerate(re.split(r"(?<=[.?])\s+", e.explanation)):
            block = Block(id=f"b{i:03d}.{j}", kind="sentence", text=sentence)
            blocks.append(block)
            owner[block.id] = e.term
    draft = Draft(
        doc_id="vocabulary",
        lang=base_lang(key),
        level="A2",
        blocks=blocks,
        glossary=[GlossaryEntry(term=e.term, explanation=e.explanation) for e in glossary],
    )
    findings = [
        f"{owner.get(f.block_id, '-')}: {f.rule_id} {render_finding(f)}"
        for f in check_draft(draft).findings
        if f.severity != "info" and f.rule_id not in SKIP_RULES
    ]
    assert findings == []


@pytest.mark.parametrize("key", ["de-DE", "de-AT"])
def test_explanations_use_no_office_word_of_their_variety(key: str) -> None:
    """The Swiss checker knows the Swiss office words only: the explanations and easy
    words of Germany and Austria are searched for their own (zeitnah, ehestmöglich)."""
    texts = [e.explanation or e.easy or "" for e in load_vocabulary(key)]
    found = [m.text for matches in matcher(key).find_texts(texts) for m in office_words(matches)]
    assert found == []


# -- the split and the varieties -------------------------------------------------------


def test_the_split_keeps_every_swiss_term_in_its_group() -> None:
    by_group: dict[str, list[str]] = defaultdict(list)
    for e in load_vocabulary("de"):
        by_group[f"{e.kind}.{e.group}"].append(e.term)
    expected = {group: sorted(terms.split("|")) for group, terms in SWISS_BEFORE_SPLIT.items()}
    assert {group: sorted(terms) for group, terms in by_group.items()} == expected


def test_the_shared_german_file_has_no_swiss_marker() -> None:
    found = [
        (e.term, marker)
        for e in read_vocabulary("de")
        for marker in SWISS_MARKERS.findall(" ".join(filter(None, (e.term, e.easy, e.explanation))))
    ]
    assert found == []


def test_a_variety_reads_the_shared_file_and_its_own() -> None:
    assert vocabulary_files("de") == ("de", "de-CH")
    assert vocabulary_files("de-DE") == ("de", "de-DE")
    assert vocabulary_files("de-AT") == ("de", "de-AT")
    assert vocabulary_files("fr") == ("fr",) and vocabulary_files("it") == ("it",)
    swiss = {e.term: e for e in load_vocabulary("de")}
    german = {e.term: e for e in load_vocabulary("de-DE")}
    assert "innert" in swiss and "innert" not in german  # Swiss
    assert "Bescheid" in german and "Bescheid" not in swiss  # German
    # a shared entry in the spelling of Germany
    assert "gemäss" in swiss and "gemäß" in german
    assert german["Prämie"].explanation == swiss["Prämie"].explanation.replace(
        "regelmässig", "regelmäßig"
    )
    assert easy_for("de-DE", "d. h.") == "das heißt" and easy_for("de", "d. h.") == "das heisst"
    assert easy_for("de-AT", "iVm") == "zusammen mit" and easy_for("de-DE", "EL") is None
    versions = {key: vocabulary_version(key) for key in KEYS}
    assert len(set(versions.values())) == len(KEYS)
    # a key of one file keeps the hash of that file alone
    french = (DATA / "vocabulary_fr.toml").read_bytes()
    assert versions["fr"] == hashlib.sha256(french).hexdigest()[:12]


@pytest.mark.parametrize(
    ("swiss", "standard"),
    [
        ("Bundesstrasse", "Bundesstraße"),  # a stem inside a word
        ("gemäss", "gemäß"),
        ("gemässe", "gemäße"),
        ("grösser", "größer"),
        ("Massnahmen", "Maßnahmen"),
        ("Masse", "Masse"),  # mass or measures: ambiguous, as written
        ("in Massen", "in Massen"),
        ("Busse", "Busse"),  # buses or a fine
        ("Ausweisstelle", "Ausweisstelle"),  # no stem weiss: Ausweis and a joining s
        ("Fussel", "Fussel"),  # a stem written as it is wins over fuss
        ("STRASSE", "STRASSE"),  # capitals stay
        ("muss", "muss"),
    ],
)
def test_the_spelling_of_germany_and_austria(swiss: str, standard: str) -> None:
    assert standard_spelling(swiss) == standard


def test_the_spelling_table_turns_ss_into_sharp_s_only() -> None:
    table = tomllib.loads((DATA / "spelling_de.toml").read_text(encoding="utf-8"))["sharp_s"]
    for stem, standard in table.items():
        assert stem == stem.lower() and SHARP_S not in stem, stem
        assert standard.replace(SHARP_S, "ss") == stem, stem


def test_sharp_s_and_ss_are_the_same_letters() -> None:
    # The file of Germany writes Massnahme; Germany reads it as Maßnahme.
    assert "Massnahme" in {e.term for e in read_vocabulary("de-DE")}
    assert _found("de-DE", "Die Maßnahme gilt.") == [("Maßnahme", "Maßnahme")]
    assert _found("de-DE", "Die Massnahme gilt.") == [("Maßnahme", "Massnahme")]
    # and the Swiss list finds a word written with sharp s
    assert _found("de", "Die Kindesschutzmaßnahme gilt.") == [
        ("Kindesschutzmassnahme", "Kindesschutzmaßnahme")
    ]


# -- matching ----------------------------------------------------------------------------


def _found(key: str, text: str) -> list[tuple[str, str]]:
    return [(m.entry.term, m.text) for m in matcher(key).find_text(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sie reichen das Gesuch innert 30 Tagen ein.",
         [("einreichen", "reichen ... ein"), ("Gesuch", "Gesuch"), ("innert", "innert")]),
        ("Das Formular ist einzureichen.", [("einreichen", "einzureichen")]),
        ("Das Gesetz tritt am 1. Januar in Kraft.",
         [("Gesetz", "Gesetz"), ("in Kraft treten", "tritt ... in Kraft")]),
        ("Sie machen die Kosten geltend.", [("geltend machen", "machen ... geltend")]),
        ("Sie bekommen die Prämien·verbilligung.",
         [("Prämienverbilligung", "Prämien·verbilligung")]),
        ("Die Verfügungen stehen Ihnen zur Verfügung.", [("Verfügung", "Verfügungen")]),
        ("Er bekam eine IV-Rente, z.B. im Mai.",
         [("IV", "IV"), ("Rente", "Rente"), ("z. B.", "z.B.")]),
        ("Die Ergänzungsleistung kommt.", [("Ergänzungsleistungen", "Ergänzungsleistung")]),
    ],
)  # fmt: skip
def test_german_terms_in_their_forms(text: str, expected: list[tuple[str, str]]) -> None:
    assert _found("de", text) == expected


@pytest.mark.parametrize(
    ("key", "text", "expected"),
    [
        ("de-DE", "Wir stellen Ihnen die Kosten zeitnah in Rechnung.",
         [("in Rechnung stellen", "stellen ... in Rechnung"), ("zeitnah", "zeitnah")]),
        # Bescheid sagen is no decision, im Widerspruch zu no objection (not_in)
        ("de-DE", "Geben Sie uns Bescheid, falls der Bescheid fehlt.",
         [("falls", "falls"), ("Bescheid", "Bescheid")]),
        ("de-DE", "Das steht im Widerspruch zum Bussgeldbescheid.",
         [("Bußgeldbescheid", "Bussgeldbescheid")]),
        ("de-AT", "Ihr Ansuchen ist ho. eingelangt und wird in Evidenz gehalten.",
         [("Ansuchen", "Ansuchen"), ("ho.", "ho."), ("eingelangt", "eingelangt"),
          ("in Evidenz halten", "in Evidenz ... gehalten")]),
        ("de-AT", "Die BH und die Kinder- und Jugendhilfe brauchen Ihre e-card nach § 7 iVm § 9.",
         [("BH", "BH"), ("Kinder- und Jugendhilfe", "Kinder- und Jugendhilfe"),
          ("e-card", "e-card"), ("iVm", "iVm")]),
    ],
)  # fmt: skip
def test_terms_of_germany_and_austria_in_their_forms(
    key: str, text: str, expected: list[tuple[str, str]]
) -> None:
    assert _found(key, text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Vous vous acquittez de la facture ci-jointe.",
         [("s'acquitter de", "acquittez de"), ("ci-joint", "ci-jointe")]),
        ("Dans le cadre du projet, vous faites valoir vos droits.",
         [("dans le cadre de", "Dans le cadre du"), ("faire valoir", "faites valoir")]),
        ("Les prestations susmentionnées sont versées.",
         [("prestation", "prestations"), ("susmentionné", "susmentionnées"),
          ("verser", "versées")]),
        ("Vous faites opposition à la poursuite.",
         [("opposition à la poursuite", "opposition à la poursuite")]),
        # recourir is no recourant, and dès lors is no dès (not_in)
        ("Il est dès lors important de pouvoir recourir à sa réserve.", []),
        ("J'ai reçu la rente AI, p. ex. en mai.",
         [("rente", "rente"), ("AI", "AI"), ("p. ex.", "p. ex.")]),
    ],
)  # fmt: skip
def test_french_terms_in_their_forms(text: str, expected: list[tuple[str, str]]) -> None:
    assert _found("fr", text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # inflected nouns and adjectives: the ending swapped for the base form's
        ("I premi suddetti sono esigibili.",
         [("premio", "premi"), ("suddetto", "suddetti"), ("esigibile", "esigibili")]),
        ("La prestazione complementare e l'assegno familiare.",
         [("prestazioni complementari", "prestazione complementare"),
          ("assegni familiari", "assegno familiare")]),
        # verb forms, and an articulated preposition for the term's bare one
        ("Ai sensi della legge, l'ufficio provvede al pagamento e ha effettuato il controllo.",
         [("ai sensi di", "Ai sensi della"), ("legge", "legge"),
          ("provvedere", "provvede"), ("effettuare", "effettuato")]),
        # a reflexive verb: listed with its pronoun, which the text puts before the verb
        ("Lei si rivolge all'ufficio e deve annunciarsi all'URC.",
         [("rivolgersi a", "rivolge all'"), ("annunciarsi", "annunciarsi"), ("URC", "URC")]),
        # inoltre is no inoltrare, verso no versare, and in sostanza no sostanza (not_in)
        ("Inoltre, verso sera la decisione è in sostanza chiara.", [("decisione", "decisione")]),
        ("Porti i documenti, p. es. il permesso B, ecc.",
         [("p. es.", "p. es."), ("permesso B", "permesso B"), ("ecc.", "ecc.")]),
    ],
)  # fmt: skip
def test_italian_terms_in_their_forms(text: str, expected: list[tuple[str, str]]) -> None:
    assert _found("it", text) == expected


def test_context_words_are_no_office_words() -> None:
    matches = matcher("de").find_text("Schreiben Sie uns, gemäss dem Gesetz zur Abklärungs-Stelle.")
    assert [m.entry.term for m in matches] == ["Schreiben", "gemäss", "Gesetz", "Abklärung"]
    # Schreiben is context-dependent, Gesetz is explained, Abklärungs-Stelle is a name
    assert [m.entry.term for m in office_words(matches)] == ["gemäss"]


def test_abbreviations_give_their_full_word() -> None:
    assert easy_for("de", "z.B.") == "zum Beispiel"
    assert easy_for("fr", "p. ex.") == "par exemple"
    assert easy_for("de", "CHF") is None
    assert easy_for("it", "ecc.") == "eccetera"
