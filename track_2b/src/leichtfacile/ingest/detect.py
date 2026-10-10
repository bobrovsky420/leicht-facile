"""Language detection for German, French and Italian from function-word frequencies.

No extra dependency: official texts are full of articles, prepositions and pronouns,
and those differ clearly between the three languages. Every word in a list scores for
its language; a word in several lists splits its point. Month and weekday names are
included because short official texts often mention a date. English is scored too, so
that an English text is rejected instead of being forced into one of the three
languages.

`detect_language` returns `(None, score)` when the text is too short, when the
evidence is not clear, or when the text looks English. The score is the share of the
evidence that points to the winning language (0 to 1).
"""

from __future__ import annotations

import re

_MAX_CHARS = 20_000
_MIN_WORDS = 2
_MIN_EVIDENCE = 1.5
_MIN_SHARE = 0.6

_WORDS: dict[str, str] = {
    "de": """
        ab aber alle allen aller alles als also am an andere anderen auch auf aus
        ausserdem bei beim bin bis bitte bzw dabei dafür daher damit danach dann darf
        darum das dass davon dazu dein deine dem den denn der deren des deshalb dessen
        dich die dies diese diesem diesen dieser dieses dir doch dort durch dürfen ein
        eine einem einen einer eines er erst es etwa etwas euch euer für gegen gibt gilt
        habe haben hat hatte hatten hier ich ihm ihn ihnen ihr ihre ihrem ihren ihrer im
        immer ins ist jede jedem jeden jeder jedes jedoch jetzt kann kein keine keinem
        keinen keiner können könnte man mehr mein meine mich mir mit muss müssen nach
        nicht nichts noch nun nur ob oder ohne schon sehr sein seine seinem seinen seiner
        seit sich sie sind so soll sollen sondern sonst sowie trotzdem um und uns unser
        unsere unter über vom von vor war waren warum was wegen weil weitere welche
        welcher welches wenn wer werden wie wieder wir wird wo wurde wurden während zu
        zudem zuerst zum zur zwischen
    """,
    "fr": """
        afin ai ainsi alors après au aucun aucune aussi autre autres aux avant avec avez
        avoir avons c' car ce ceci cela celle celles celui ces cet cette chaque chez comme
        comment d' dans de depuis des devez doit doivent donc dont du elle elles en encore
        entre est et eux été être fait faire faut font il ils j' je jusqu' l' le les leur
        leurs lors lorsque lui m' mais me merci moi mon même mes n' ne ni nos notre nous on
        ont ou où par pas pendant peu peut peuvent plus pour pourquoi pouvez qu' quand que
        quel quelle quelles quels qui quoi s' sa sans selon sera seront ses soit son sont
        sous sur ta te tes toi ton tous tout toute toutes très tu une vers veuillez voici
        vos votre vous y à ça
    """,
    "it": """
        ad agli ai al all' alla alle allo anche ancora avere aveva c' che chi ci come con
        contro cosa cui dai dal dall' dalla dalle degli dei del dell' della delle dello
        deve devono di dove dopo durante e ed entro era essere fa fino fra gli grazie già
        ha hanno ho i il l' le lei lo loro lui ma mi molto ne nei nel nell' nella nelle
        nello noi non nostra nostro o ogni oppure per perché più presso prima può possono
        quale quali quando quanto quella quelle quello questa queste questi questo
        secondo sempre sia solo sono su sua sue sui sul sull' sulla suo suoi tra tutte
        tutti tutto un' una uno vi voi vostra vostro è
    """,
    "en": """
        about after all and any are as at be been before being between both but by can
        could did do does done each for from had has have he her here his how if into is
        it its may me might must my no not of only or other our out over please she
        should such than that the their them then there these they this those to under
        up we were what when where which who whom why will with would you your
    """,
}

# Dates are frequent in official texts and the names differ between the languages.
_CALENDAR: dict[str, str] = {
    "de": """
        januar februar märz april mai juni juli august september oktober november
        dezember montag dienstag mittwoch donnerstag freitag samstag sonntag franken uhr
    """,
    "fr": """
        janvier février mars avril mai juin juillet août septembre octobre novembre
        décembre lundi mardi mercredi jeudi vendredi samedi dimanche francs heures
    """,
    "it": """
        gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre
        novembre dicembre lunedì martedì mercoledì giovedì venerdì sabato domenica
        franchi ore
    """,
    "en": "",
}

# Function words per language; the segmenter uses them to recognise the first word of
# a sentence. Words that appear in two lists on purpose ("il", "le", "ne") split their
# point. Words that are frequent in several languages ("a", "la", "in", "da", "se",
# "si", "un") are in no list at all.
FUNCTION_WORDS: dict[str, frozenset[str]] = {
    lang: frozenset(words.split()) for lang, words in _WORDS.items()
}
STOPWORDS: dict[str, frozenset[str]] = {
    lang: words | frozenset(_CALENDAR[lang].split()) for lang, words in FUNCTION_WORDS.items()
}
_INDEX: dict[str, tuple[str, ...]] = {}
for _lang, _words in STOPWORDS.items():
    for _word in _words:
        _INDEX[_word] = (*_INDEX.get(_word, ()), _lang)

_TOKEN = re.compile(r"[^\W\d_]+'?")


def detect_language(text: str) -> tuple[str | None, float]:
    """Return ("de" | "fr" | "it", score) or (None, score) when not confident."""
    tokens = _TOKEN.findall(text[:_MAX_CHARS].lower().replace("\u2019", "'"))
    if len(tokens) < _MIN_WORDS:
        return None, 0.0
    scores = dict.fromkeys(STOPWORDS, 0.0)
    for token in tokens:
        langs = _INDEX.get(token) or _INDEX.get(token.rstrip("'"))
        if langs:
            for lang in langs:
                scores[lang] += 1.0 / len(langs)
    total = sum(scores.values())
    if total == 0:
        return None, 0.0
    best = max(scores, key=lambda lang: scores[lang])
    share = round(scores[best] / total, 3)
    evidence = scores[best]
    # One unambiguous function word is enough in a short text ("La SVA vous aide.").
    enough = evidence >= _MIN_EVIDENCE or (evidence >= 1.0 and share == 1.0 and len(tokens) >= 3)
    if best == "en" or not enough or share < _MIN_SHARE:
        return None, share
    return best, share
