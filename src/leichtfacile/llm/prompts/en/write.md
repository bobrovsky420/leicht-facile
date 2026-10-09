{#- English instructions for a German or French document (LLM_ENGLISH_PROMPTS,
    docs/prompts.md "English instructions"): de/write.md and fr/write.md in English,
    line for line, with one more line that names the language of the answer. The
    reader's headings, the JSON example and the few-shot pairs stay in the document's
    language, word for word as in that template. -#}
{% set headings = "Que devez-vous faire ? Jusqu'à quand ? À qui pouvez-vous poser des questions ?" if lang == "fr" else "Was müssen Sie tun? Bis wann? Wen können Sie fragen?" %}
You write official texts in {{ level_name }}, level {{ level }}, for people in Switzerland. You write for people who cannot read well. You write only things that are in the document.

{{ style_guide }}

How you work:

1. Plan first. What does the reader want to know first? Order the content by these questions, not by the original. The headings are questions of the reader, for example: {{ headings }}
2. Then write the text. A block is a heading, a sentence or a list item. Each sentence is a block of its own.
3. Every fact of the fact sheet with "must_keep": true must be in the text, with exactly the same value. Do not change any deadline, any amount, any phone number or any address. Write nothing that is not in the document. Take names of offices, addresses and numbers only from the document, never from the examples.
4. For each block, give:
   - "fact_ids": the facts the block contains, for example ["f01"]. Otherwise [].
   - "segment_ids": the sentences of the document the block comes from, for example ["s0004"]. Every block except headings needs at least one sentence.
5. What you leave out of the document goes into "omissions", with a short reason.
6. Explain the hard words you use in "glossary". Take the explanations from the fact sheet.
{% if mode is defined and mode == "decision" %}{% include "en/decision.md" %}{% endif %}
{% if medication is defined and medication %}{% include "en/medication.md" %}{% endif %}

Write every text in {{ language }}.

Answer only with a JSON object, without any other text. The form looks like this. The values are only an example from another document (a dog tax); do not take any sentence from it:

{% if lang == "fr" %}
{
  "blocks": [
    {"kind": "heading", "text": "Que devez-vous faire ?", "fact_ids": [], "segment_ids": []},
    {"kind": "sentence", "text": "Vous annoncez votre chien au contrôle des habitants.", "fact_ids": ["f03"], "segment_ids": ["s0005"]},
    {"kind": "sentence", "text": "La taxe des chiens coûte 120 francs par chien.", "fact_ids": ["f02"], "segment_ids": ["s0002"]},
    {"kind": "sentence", "text": "Vous payez jusqu'au 30 avril 2026.", "fact_ids": ["f01"], "segment_ids": ["s0003"]},
    {"kind": "heading", "text": "De quoi avez-vous besoin ?", "fact_ids": [], "segment_ids": []},
    {"kind": "list_item", "text": "le carnet de vaccination de votre chien", "fact_ids": [], "segment_ids": ["s0006"]},
    {"kind": "list_item", "text": "le numéro de la puce", "fact_ids": [], "segment_ids": ["s0006"]}
  ],
  "omissions": [
    {"what": "Article de loi", "why": "Pas nécessaire pour la lectrice", "segment_ids": ["s0009"]}
  ],
  "glossary": [
    {"term": "contrôle des habitants", "explanation": "Le bureau de la commune pour les personnes qui habitent là."}
  ]
}
{% else %}
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
{% endif %}

Examples in {{ level_name }}. They only show the style. Do not take any content from them.

{{ examples }}

{% if section %}
The document is long. Now write only this part: {{ section }}. You will write the other parts later.

{% endif %}
The fact sheet:

{{ factsheet }}

The document. Each line is a sentence with its number:

{{ source }}

Now write the version in {{ level_name }} of this document, with its facts and sentence numbers. Answer only with the JSON object.
