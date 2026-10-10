{#- The medication partial (docs/rules.md FACT-09, docs/use-cases.md §3): pulled into the
    understand template when the source has a dose or a dosing scheme, and into the
    write template when the fact sheet names a medication. A document without doses
    never sees a word of it, so the standard prompts and their cache keys stay as
    frozen. First draft of 8 October 2026. -#}
{% if stage_name == "understand" %}

Das Dokument nennt Dosen von Medikamenten. Dafür gilt zusätzlich:

- Jedes Medikament, das die Leserin oder der Leser nehmen soll, ist eine eigene Tatsache mit "kind": "medication" und "must_keep": true.
- "value_norm" ist nur der Name des Medikaments, genau so geschrieben wie im Dokument: ohne Dosis, ohne Schema und ohne Form wie Tabletten oder Tropfen.
- "text" nennt das Medikament mit seiner Dosis, seinem Schema und seiner Dauer, so wie sie im Dokument stehen.
{% elif stage_name == "write" %}

Das Dokument nennt Medikamente. Dafür gilt zusätzlich:

- Schreiben Sie jedes Medikament in einen eigenen Listenpunkt: den Namen, die Dosis, das Schema und die Dauer zusammen.
- Schreiben Sie den Namen genau so wie im Dokument. Ändern Sie keine Dosis und kein Schema.
{% endif %}
