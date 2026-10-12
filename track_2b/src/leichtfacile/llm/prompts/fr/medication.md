{#- The medication partial (docs/rules.md FACT-09, docs/use-cases.md §3): pulled into the
    understand template when the source has a dose or a dosing scheme, and into the
    write template when the fact sheet names a medication. A document without doses
    never sees a word of it, so the standard prompts and their cache keys stay as
    frozen. First draft of 8 October 2026. -#}
{% if stage_name == "understand" %}

Le document indique des doses de médicaments. En plus :

- Chaque médicament que la lectrice ou le lecteur doit prendre est un fait à part, avec "kind" : "medication" et "must_keep" : true.
- "value_norm" est seulement le nom du médicament, écrit exactement comme dans le document : sans dose, sans schéma et sans forme comme comprimés ou gouttes.
- "text" nomme le médicament avec sa dose, son schéma et sa durée, comme dans le document.
{% elif stage_name == "write" %}

Le document cite des médicaments. En plus :

- Écris chaque médicament dans son propre point de liste : le nom, la dose, le schéma et la durée ensemble.
- Écris le nom exactement comme dans le document. Ne change aucune dose et aucun schéma.
{% endif %}
