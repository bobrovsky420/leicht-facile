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
        "missing_value_exact": " (Wert: {value}; schreibe: {exact})",
        "unsupported": "Das steht nicht im Original.",
        "distorted": "Tatsache {fact_id} ist falsch: {note} Richtig ist: {fact}",
        "section": "die Sätze {first} bis {last}",
        "copied_example": "Die Antwort enthält {count} Sätze aus dem Beispiel in der Anleitung "
        "(Hunde·steuer). Das Beispiel zeigt nur die Form. Schreibe über das Dokument "
        "unten, mit seinen Tatsachen und Satznummern.",
        "foreign_values": "Die Antwort enthält Werte, die nicht im Dokument stehen: {values}. "
        "Jeder Wert muss aus dem Faktenblatt oder aus den Sätzen des Originals kommen. "
        "Schreibe diese Sätze ohne den fremden Wert, oder lass sie weg.",
        # A missing fact asked for from the review page (stages.recover_fact).
        "recover_value": "Deine Sätze haben den Wert {value} nicht. Schreibe ihn genau so.",
        "recover_foreign": "Diese Werte stehen nicht im Absatz des Originals: {values}. "
        "Schreibe nur, was im Absatz steht.",
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
        "missing_value_exact": " (valeur : {value} ; écris : {exact})",
        "unsupported": "Ce n'est pas dans l'original.",
        "distorted": "Le fait {fact_id} est faux : {note} Correct : {fact}",
        "section": "les phrases {first} à {last}",
        "copied_example": "La réponse contient {count} phrases de l'exemple dans les "
        "instructions (taxe des chiens). L'exemple montre seulement la forme. Écris sur le "
        "document plus bas, avec ses faits et ses numéros de phrases.",
        "foreign_values": "La réponse contient des valeurs qui ne sont pas dans le document : "
        "{values}. Chaque valeur doit venir de la fiche de faits ou des phrases de "
        "l'original. Écris ces phrases sans la valeur étrangère, ou laisse-les de côté.",
        "recover_value": "Tes phrases n'ont pas la valeur {value}. Écris-la exactement ainsi.",
        "recover_foreign": "Ces valeurs ne sont pas dans le paragraphe de l'original : "
        "{values}. Écris seulement ce qui est dans le paragraphe.",
    },
    "it": {
        "core_what": "Di che cosa si tratta?",
        "core_must_do": "Che cosa bisogna fare?",
        "core_deadline": "Entro quando?",
        "core_cost": "Quanto costa?",
        "core_contact": "A chi chiedere?",
        "doc_type": "Tipo: {doc_type}. Per: {audience}.",
        "core": "Domande principali:",
        "unanswered": "Il documento non risponde a:",
        "facts": "Fatti:",
        "background": "contesto",
        "fact_value": " | valore: {value}",
        "fact_from": " | fonte: {ids}",
        "hard_terms": "Parole difficili:",
        "omit": "Si può tralasciare:",
        "none": "(nessuno)",
        "empty": "(vuoto)",
        "block_refs": "   (fatti: {facts}; fonte: {sources})",
        "suggestion": "Suggerimento: {text}",
        "problems": "Problemi:",
        "keep_facts": "Il blocco deve mantenere questi fatti:",
        "missing_value": " (valore: {value})",
        "missing_value_exact": " (valore: {value}; scrivi: {exact})",
        "unsupported": "Questo non è nell'originale.",
        "distorted": "Il fatto {fact_id} è sbagliato: {note} Corretto: {fact}",
        "section": "le frasi da {first} a {last}",
        "copied_example": "La risposta contiene {count} frasi dell'esempio nelle istruzioni "
        "(tassa sui cani). L'esempio mostra solo la forma. Scrivi sul documento qui "
        "sotto, con i suoi fatti e i suoi numeri di frase.",
        "foreign_values": "La risposta contiene valori che non sono nel documento: {values}. "
        "Ogni valore deve venire dalla scheda dei fatti o dalle frasi dell'originale. "
        "Scrivi queste frasi senza il valore estraneo, oppure tralasciale.",
        "recover_value": "Le tue frasi non hanno il valore {value}. Scrivilo esattamente così.",
        "recover_foreign": "Questi valori non sono nel paragrafo dell'originale: {values}. "
        "Scrivi solo quello che c'è nel paragrafo.",
    },
}


def label(lang: str, key: str, **values: object) -> str:
    text = LABELS.get(lang, LABELS["de"])[key]
    return text.format(**values) if values else text
