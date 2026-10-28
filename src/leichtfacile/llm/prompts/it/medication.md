{#- The medication partial (docs/rules.md FACT-09, docs/use-cases.md §3): pulled into the
    understand template when the source has a dose or a dosing scheme, and into the
    write template when the fact sheet names a medication. A document without doses
    never sees a word of it, so the standard prompts and their cache keys stay as
    frozen. Italian version of 28 October 2026, after the French one. -#}
{% if stage_name == "understand" %}

Il documento indica dosi di medicamenti. In più:

- Ogni medicamento che la lettrice o il lettore deve prendere è un fatto a sé, con "kind": "medication" e "must_keep": true.
- "value_norm" è solo il nome del medicamento, scritto esattamente come nel documento: senza dose, senza schema e senza forma come compresse o gocce.
- "text" nomina il medicamento con la sua dose, il suo schema e la sua durata, come nel documento.
{% elif stage_name == "write" %}

Il documento cita dei medicamenti. In più:

- Scrivi ogni medicamento in un punto dell'elenco a sé: il nome, la dose, lo schema e la durata insieme.
- Scrivi il nome esattamente come nel documento. Non cambiare nessuna dose e nessuno schema.
{% endif %}
