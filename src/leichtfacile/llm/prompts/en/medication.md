{#- The medication partial with English instructions (LLM_ENGLISH_PROMPTS, docs/prompts.md
    "English instructions"): de/medication.md and fr/medication.md in English, line
    for line. -#}
{% if stage_name == "understand" %}

The document names doses of medicines. For it, these rules apply as well:

- Every medicine that the reader is to take is a fact of its own, with "kind": "medication" and "must_keep": true.
- "value_norm" is only the name of the medicine, written exactly as in the document: without dose, without scheme and without a form such as tablets or drops.
- "text" names the medicine with its dose, its scheme and its duration, as they stand in the document.
{% elif stage_name == "write" %}

The document names medicines. For it, these rules apply as well:

- Write each medicine in a list item of its own: the name, the dose, the scheme and the duration together.
- Write the name exactly as in the document. Do not change any dose or any scheme.
{% endif %}
