"""The few words code writes into a prompt around the items, per language: the headings
of the fact sheet, the references on draft lines and the problem lines of a repair
round. The prompts themselves are templates in llm/prompts/<lang>/. A language without
its own labels gets the German ones; it has no prompts either."""

from __future__ import annotations

LABELS: dict[str, dict[str, str]] = {
    "de": {
        "core_what": "Worum geht es?",
        "core_must_do": "Was muss man tun?",
        "core_deadline": "Bis wann?",
        "core_cost": "Was kostet es?",
        "core_contact": "Wen kann man fragen?",
        "doc_type": "Art: {doc_type}. Für: {audience}.",
        "core": "Kernfragen:",
        "unanswered": "Das Dokument beantwortet nicht:",
        "facts": "Tatsachen:",
        "background": "Hintergrund",
        "fact_value": " | Wert: {value}",
        "fact_from": " | aus: {ids}",
        "hard_terms": "Schwierige Wörter:",
        "omit": "Kann man weglassen:",
        "none": "(keine)",
        "empty": "(leer)",
        "block_refs": "   (Tatsachen: {facts}; Quelle: {sources})",
        "suggestion": "Vorschlag: {text}",
        "problems": "Probleme:",
        "keep_facts": "Der Block muss diese Tatsachen behalten:",
        "missing_value": " (Wert: {value})",
        "missing_value_exact": " (Wert: {value}; schreiben Sie: {exact})",
        "unsupported": "Das steht nicht im Original.",
        "distorted": "Tatsache {fact_id} ist falsch: {note} Richtig ist: {fact}",
        "section": "die Sätze {first} bis {last}",
        "copied_example": "Die Antwort enthält {count} Sätze aus dem Beispiel in der Anleitung "
        "(Hunde·steuer). Das Beispiel zeigt nur die Form. Schreiben Sie über das Dokument "
        "unten, mit seinen Tatsachen und Satznummern.",
        "foreign_values": "Die Antwort enthält Werte, die nicht im Dokument stehen: {values}. "
        "Jeder Wert muss aus dem Faktenblatt oder aus den Sätzen des Originals kommen. "
        "Schreiben Sie diese Sätze ohne den fremden Wert, oder lassen Sie sie weg.",
        # A missing fact asked for from the review page (stages.recover_fact).
        "recover_value": "Ihre Sätze haben den Wert {value} nicht. Schreiben Sie ihn genau so.",
        "recover_foreign": "Diese Werte stehen nicht im Absatz des Originals: {values}. "
        "Schreiben Sie nur, was im Absatz steht.",
        # Decision mode: the authority's notice, the first and last paragraph of the
        # export, when the job sets none (docs/use-case-decisions.md).
        "notice_default": "Diese Erklärung hilft Ihnen, den Entscheid zu verstehen. "
        "Massgebend ist der Entscheid.",
    },
    "fr": {
        "core_what": "De quoi s'agit-il ?",
        "core_must_do": "Que faut-il faire ?",
        "core_deadline": "Jusqu'à quand ?",
        "core_cost": "Combien ça coûte ?",
        "core_contact": "À qui poser des questions ?",
        "doc_type": "Type : {doc_type}. Pour : {audience}.",
        "core": "Questions principales :",
        "unanswered": "Le document ne répond pas à :",
        "facts": "Faits :",
        "background": "contexte",
        "fact_value": " | valeur : {value}",
        "fact_from": " | source : {ids}",
        "hard_terms": "Mots difficiles :",
        "omit": "Peut être laissé de côté :",
        "none": "(aucun)",
        "empty": "(vide)",
        "block_refs": "   (faits : {facts} ; source : {sources})",
        "suggestion": "Suggestion : {text}",
        "problems": "Problèmes :",
        "keep_facts": "Le bloc doit garder ces faits :",
        "missing_value": " (valeur : {value})",
        "missing_value_exact": " (valeur : {value} ; écrivez : {exact})",
        "unsupported": "Ce n'est pas dans l'original.",
        "distorted": "Le fait {fact_id} est faux : {note} Correct : {fact}",
        "section": "les phrases {first} à {last}",
        "copied_example": "La réponse contient {count} phrases de l'exemple dans les "
        "instructions (taxe des chiens). L'exemple montre seulement la forme. Écrivez sur le "
        "document plus bas, avec ses faits et ses numéros de phrases.",
        "foreign_values": "La réponse contient des valeurs qui ne sont pas dans le document : "
        "{values}. Chaque valeur doit venir de la fiche de faits ou des phrases de "
        "l'original. Écrivez ces phrases sans la valeur étrangère, ou laissez-les de côté.",
        "recover_value": "Vos phrases n'ont pas la valeur {value}. Écrivez-la exactement ainsi.",
        "recover_foreign": "Ces valeurs ne sont pas dans le paragraphe de l'original : "
        "{values}. Écrivez seulement ce qui est dans le paragraphe.",
        "notice_default": "Cette explication vous aide à comprendre la décision. "
        "Seule la décision fait foi.",
    },
}


def label(lang: str, key: str, **values: object) -> str:
    text = LABELS.get(lang, LABELS["de"])[key]
    return text.format(**values) if values else text
