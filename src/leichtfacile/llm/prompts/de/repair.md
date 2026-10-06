Sie verbessern einzelne Blöcke von einem Text in {{ level_name }} (Niveau {{ level }}). Sie ändern nur die Blöcke, die unten stehen. Alles andere bleibt gleich.

{{ style_guide }}

Regeln für die Verbesserung:

- Für jeden Block schreiben Sie einen neuen Text. Sie dürfen einen Block in 2 oder 3 kurze Sätze teilen. Dann schreiben Sie mehrere Texte.
- Lösen Sie jedes genannte Problem. Ein Vorschlag nach "Vorschlag:" ist meistens richtig.
- Behalten Sie alle Werte genau: Fristen, Beträge, Telefonnummern, Adressen.
- Schreiben Sie nichts, was nicht im Original steht.
{% if missing %}- Einige Tatsachen fehlen im Text. Das ist das Wichtigste: Schreiben Sie für jede fehlende Tatsache 1 oder 2 neue Sätze in "additions", mit genau dem Wert aus dem Faktenblatt. Sagen Sie, nach welchem Block sie kommen ("after"), und nennen Sie die Tatsache in "fact_ids".
- Ändern Sie Blöcke nur, wenn sie oben unter "Die Blöcke, die Sie verbessern" stehen.
{% endif %}
Antworten Sie nur mit einem JSON-Objekt, ohne anderen Text. Die Form sieht so aus (die Werte sind nur ein Beispiel):

{
  "repairs": [
    {"id": "b005", "texts": ["Sie bezahlen bis zum 30. April 2026.", "Sie bezahlen bei der Gemeinde."]}
  ],
  "additions": [
    {"after": "b007", "texts": ["Rufen Sie die Einwohner·kontrolle an: 031 987 65 43."], "fact_ids": ["f04"], "segment_ids": ["s0008"]}
  ]
}

Die Blöcke, die Sie verbessern:

{{ flagged }}
{% if missing %}
Die fehlenden Tatsachen:

{{ missing }}
{% endif %}
Das Faktenblatt:

{{ factsheet }}

Der ganze Entwurf, damit Sie den Zusammenhang kennen:

{{ draft }}

Die Sätze des Originals zu diesen Blöcken:

{{ source }}
