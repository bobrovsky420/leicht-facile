{#- English instructions for a German or French document (LLM_ENGLISH_PROMPTS,
    docs/prompts.md "English instructions"): de/judge.md and fr/judge.md in English,
    line for line. The rules' example words and the JSON example stay in the
    document's language, word for word as in that template. -#}
{% set pronouns = "il, elle, celui-ci" if lang == "fr" else "er, sie, es, dieser" %}
{% set must, can, cond, maybe = ("devoir", "pouvoir", "si", "peut-être") if lang == "fr" else ("müssen", "können", "wenn", "vielleicht") %}
You check a draft in {{ level_name }}. The draft is a simple version of an official document. You do not rewrite anything. You only report problems.

Check these 3 things:

1. Every fact in the fact sheet: is it in the draft ("present"), is it missing ("missing"), or is it changed or wrong ("distorted")? Name the blocks it is in. For "missing" and "distorted", write briefly what is missing or what is wrong.
2. Which blocks say something that is not in the original or does not follow from it? Name the block and briefly what is wrong.
3. Which blocks break one of these rules?
   - SEM-01: imagery, an idiom or a metaphor.
   - SEM-02: an abstract noun where an action or a person would be more concrete.
   - SEM-03: a pronoun ({{ pronouns }}) is not clear.
   - SEM-04: the block assumes knowledge that the reader may not have, for example a procedure, an office or a legal term, and does not explain it.
   - SEM-05: a hard word without explanation that is not in the draft's glossary.
   - SEM-08: an obligation, a possibility or a condition has changed. "{{ must }}" must not become "{{ can }}", and the other way round. A condition with "{{ cond }}" stays a condition: "{{ maybe }}" turns it into a guess, and that is wrong.
{% if mode is defined and mode == "decision" %}{% include "en/decision.md" %}{% endif %}

Report only real problems. A good draft has few or no findings. Write the notes in {{ language }}.

Answer only with a JSON object, without any other text. The form looks like this (the values are only an example):

{% if lang == "fr" %}
{
  "fact_checks": [
    {"fact_id": "f01", "status": "present", "block_ids": ["b004"], "note": ""},
    {"fact_id": "f02", "status": "distorted", "block_ids": ["b003"], "note": "L'original dit 120 francs, le brouillon dit 100 francs."},
    {"fact_id": "f03", "status": "missing", "block_ids": [], "note": "L'obligation d'annoncer le chien manque."}
  ],
  "unsupported": [
    {"block_id": "b006", "note": "L'original ne dit pas qu'on peut payer sur internet."}
  ],
  "semantic_findings": [
    {"block_id": "b002", "rule_id": "SEM-04", "note": "Le brouillon n'explique pas ce qu'est le contrôle des habitants."}
  ]
}
{% else %}
{
  "fact_checks": [
    {"fact_id": "f01", "status": "present", "block_ids": ["b004"], "note": ""},
    {"fact_id": "f02", "status": "distorted", "block_ids": ["b003"], "note": "Im Original steht 120 Franken, im Entwurf 100 Franken."},
    {"fact_id": "f03", "status": "missing", "block_ids": [], "note": "Die Pflicht zur Anmeldung fehlt."}
  ],
  "unsupported": [
    {"block_id": "b006", "note": "Das Original sagt nicht, dass man im Internet bezahlen kann."}
  ],
  "semantic_findings": [
    {"block_id": "b002", "rule_id": "SEM-04", "note": "Was die Einwohnerkontrolle ist, wird nicht erklärt."}
  ]
}
{% endif %}

The fact sheet:

{{ factsheet }}

The sentences of the original that the draft is based on:

{{ source }}

The draft. Each line is a block with its number:

{{ draft }}

The draft's glossary:

{{ glossary }}
