{#- English instructions for a German or French document (LLM_ENGLISH_PROMPTS,
    docs/prompts.md "English instructions"): de/repair.md and fr/repair.md in English,
    line for line, with one more rule that names the language of the answer. The JSON
    example and its values stay in the document's language, word for word as in that
    template. -#}
{% set example_values = "30 avril 2026, 032 987 65 43" if lang == "fr" else "30. April 2026, 031 987 65 43" %}
You improve single blocks of a text in {{ level_name }}, level {{ level }}. You change only the blocks that are listed below. Everything else stays the same.

{{ style_guide }}

Rules for the improvement:

- For each block, you write a new text. You may split a block into 2 or 3 short sentences. Then you write several texts.
- Solve every problem that is named. A suggestion after "Suggestion:" is usually right.
- Keep all values exactly: deadlines, amounts, phone numbers, addresses.
- Write nothing that is not in the original. Every value in your answer (date, amount, phone number, e-mail address, web address, percentage, time) is in the fact sheet or in the sentences of the original below. The values in the example of the form below ({{ example_values }}) belong to another document: never use them.
- Write every text in {{ language }}.
{% if missing %}- Some facts are missing from the text. That is the most important thing: for each missing fact, write 1 or 2 new sentences in "additions", with exactly the value that is given with the fact. If the fact has no value, do not invent one. Say after which block they come ("after"), and name the fact in "fact_ids".
- Change blocks only if they are listed above under "The blocks you improve".
{% endif %}
{% if mode is defined and mode == "decision" %}{% include "en/decision.md" %}{% endif %}
Answer only with a JSON object, without any other text. The form looks like this (the values are only an example):

{% if lang == "fr" %}
{
  "repairs": [
    {"id": "b005", "texts": ["Vous payez jusqu'au 30 avril 2026.", "Vous payez à la commune."]}
  ],
  "additions": [
    {"after": "b007", "texts": ["Téléphonez au contrôle des habitants : 032 987 65 43."], "fact_ids": ["f04"], "segment_ids": ["s0008"]}
  ]
}
{% else %}
{
  "repairs": [
    {"id": "b005", "texts": ["Sie bezahlen bis zum 30. April 2026.", "Sie bezahlen bei der Gemeinde."]}
  ],
  "additions": [
    {"after": "b007", "texts": ["Rufen Sie die Einwohner·kontrolle an: 031 987 65 43."], "fact_ids": ["f04"], "segment_ids": ["s0008"]}
  ]
}
{% endif %}

The blocks you improve:

{{ flagged }}
{% if missing %}
The missing facts:

{{ missing }}
{% endif %}
The fact sheet:

{{ factsheet }}

The whole draft, so that you know the context:

{{ draft }}

The sentences of the original for these blocks:

{{ source }}
