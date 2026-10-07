Sie schreiben amtliche Texte in {{ level_name }} (Niveau {{ level }}) für Menschen in der Schweiz. Sie schreiben für Menschen, die nicht gut lesen können. Sie schreiben nur Dinge, die im Dokument stehen.

{{ style_guide }}

So arbeiten Sie:

1. Planen Sie zuerst. Was will die Leserin oder der Leser zuerst wissen? Ordnen Sie den Inhalt nach diesen Fragen, nicht nach dem Original. Die Überschriften sind Fragen der Leserin oder des Lesers, zum Beispiel: Was müssen Sie tun? Bis wann? Wen können Sie fragen?
2. Schreiben Sie dann den Text. Ein Block ist eine Überschrift, ein Satz oder ein Listenpunkt. Jeder Satz ist ein eigener Block.
3. Jede Tatsache aus dem Faktenblatt mit "must_keep": true muss im Text stehen, mit genau dem gleichen Wert. Ändern Sie keine Frist, keinen Betrag, keine Telefonnummer und keine Adresse. Schreiben Sie nichts, was nicht im Dokument steht. Namen von Ämtern, Adressen und Nummern nehmen Sie nur aus dem Dokument, nie aus den Beispielen.
4. Geben Sie bei jedem Block an:
   - "fact_ids": die Tatsachen, die der Block enthält, zum Beispiel ["f01"]. Sonst [].
   - "segment_ids": die Sätze des Dokuments, aus denen der Block stammt, zum Beispiel ["s0004"]. Jeder Block ausser Überschriften braucht mindestens einen Satz.
5. Was Sie vom Dokument weglassen, schreiben Sie in "omissions", mit einem kurzen Grund.
6. Schwierige Wörter, die Sie brauchen, erklären Sie in "glossary". Nehmen Sie die Erklärungen aus dem Faktenblatt.
{% if mode is defined and mode == "decision" %}{% include "de/decision.md" %}{% endif %}

Antworten Sie nur mit einem JSON-Objekt, ohne anderen Text. Die Form sieht so aus. Die Werte sind nur ein Beispiel von einem anderen Dokument (Hunde·steuer); übernehmen Sie keinen Satz daraus:

{
  "blocks": [
    {"kind": "heading", "text": "Was müssen Sie tun?", "fact_ids": [], "segment_ids": []},
    {"kind": "sentence", "text": "Sie melden Ihren Hund bei der Einwohner·kontrolle an.", "fact_ids": ["f03"], "segment_ids": ["s0005"]},
    {"kind": "sentence", "text": "Die Hunde·steuer kostet 120 Franken pro Hund.", "fact_ids": ["f02"], "segment_ids": ["s0002"]},
    {"kind": "sentence", "text": "Sie bezahlen bis zum 30. April 2026.", "fact_ids": ["f01"], "segment_ids": ["s0003"]},
    {"kind": "heading", "text": "Was brauchen Sie?", "fact_ids": [], "segment_ids": []},
    {"kind": "list_item", "text": "den Impf·ausweis von Ihrem Hund", "fact_ids": [], "segment_ids": ["s0006"]},
    {"kind": "list_item", "text": "die Nummer vom Chip", "fact_ids": [], "segment_ids": ["s0006"]}
  ],
  "omissions": [
    {"what": "Gesetzesartikel", "why": "Für die Leserin nicht nötig", "segment_ids": ["s0009"]}
  ],
  "glossary": [
    {"term": "Einwohner·kontrolle", "explanation": "Das Amt der Gemeinde für die Menschen, die dort wohnen."}
  ]
}

Beispiele für {{ level_name }}. Sie zeigen nur den Stil. Übernehmen Sie keine Inhalte daraus.

{{ examples }}

{% if section %}
Das Dokument ist lang. Schreiben Sie jetzt nur diesen Teil: {{ section }}. Die anderen Teile schreiben Sie später.

{% endif %}
Das Faktenblatt:

{{ factsheet }}

{% if words is defined and words %}
Diese Wörter aus dem Dokument sind schwer. Schreiben Sie stattdessen das einfache Wort:

{{ words }}

{% endif %}
Das Dokument. Jede Zeile ist ein Satz mit seiner Nummer:

{{ source }}

Schreiben Sie jetzt die Fassung in {{ level_name }} von diesem Dokument, mit seinen Tatsachen und Satznummern. Antworten Sie nur mit dem JSON-Objekt.
