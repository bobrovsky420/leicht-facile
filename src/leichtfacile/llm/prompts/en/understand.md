{#- English instructions for a German or French document (LLM_ENGLISH_PROMPTS,
    docs/prompts.md "English instructions"): de/understand.md and fr/understand.md in
    English, line for line. The JSON example stays in the document's language, word
    for word as in that template. -#}
{% set phone = "0321234567" if lang == "fr" else "0441234567" %}
You are preparing a version in {{ level_name }}. To do this, you read an official Swiss document and make a fact sheet. You do not rewrite anything yet.

The document is below. Each line is a sentence with its number in square brackets. Lines with # are headings, lines with - are list items.

Your task:

1. Say in a few words what kind of document it is (for example letter, decision, form, information sheet, web page) and whom it is for.
2. Answer the 5 core questions of the reader, only with the document. For each answer, give the numbers of the sentences it comes from. If the document does not answer a question, set "text" to null and leave "segment_ids" empty. Never guess.
   - what: What is it about?
   - must_do: What must the reader do?
   - deadline: By when?
   - cost: What does it cost, or how much money is it about?
   - contact: Whom can the reader ask?
3. List every fact that must not get lost: deadlines, amounts, obligations, rights, conditions, contacts, procedures and terms. One fact per entry, numbered f01, f02, f03 and so on.
   - "kind": deadline, amount, obligation, right, condition, contact, procedure, definition or other.
   - "text": the fact in one short sentence, with the exact value.
   - "value_norm": the exact value, if there is one, in this form: a date as YYYY-MM-DD, without a year as --MM-DD; an amount as a number without currency and without separators (1500 or 20.50); a phone number with digits only ({{ phone }}); an e-mail address; a web address; a percentage as 10%; a time as HH:MM. Otherwise null.
   - "segment_ids": the sentences the fact comes from.
   - "must_keep": true if the reader needs the fact. false for mere background.
4. List hard words: technical terms, names of offices, abbreviations. Explain each word simply, in at most 2 short sentences.
5. List passages that a version in {{ level_name }} can leave out, for example articles of law, repetitions or internal notes. Give the sentence numbers and a short reason.
{% if mode is defined and mode == "decision" %}{% include "en/decision.md" %}{% endif %}
{% if medication is defined and medication %}{% include "en/medication.md" %}{% endif %}

Write all texts in {{ language }}.

Answer only with a JSON object, without any other text. The form looks like this (the values are only an example):

{% if lang == "fr" %}
{
  "doc_type": "Lettre",
  "audience": "Les personnes qui ont un chien",
  "core": {
    "what": {"text": "La commune demande une taxe pour les chiens.", "segment_ids": ["s0002"]},
    "must_do": {"text": "Annoncer le chien et payer la taxe.", "segment_ids": ["s0003", "s0005"]},
    "deadline": {"text": "Jusqu'au 30 avril 2026.", "segment_ids": ["s0003"]},
    "cost": {"text": "120 francs par chien.", "segment_ids": ["s0002"]},
    "contact": {"text": "Contrôle des habitants, téléphone 032 987 65 43.", "segment_ids": ["s0008"]}
  },
  "facts": [
    {"id": "f01", "kind": "deadline", "text": "La taxe des chiens doit être payée au plus tard le 30 avril 2026.", "value_norm": "2026-04-30", "segment_ids": ["s0003"], "must_keep": true},
    {"id": "f02", "kind": "amount", "text": "La taxe des chiens coûte 120 francs par chien.", "value_norm": "120", "segment_ids": ["s0002"], "must_keep": true},
    {"id": "f03", "kind": "obligation", "text": "Chaque chien doit être annoncé au contrôle des habitants.", "value_norm": null, "segment_ids": ["s0005"], "must_keep": true}
  ],
  "hard_terms": [
    {"term": "contrôle des habitants", "explanation": "Le bureau de la commune pour les personnes qui habitent là.", "segment_ids": ["s0005"]}
  ],
  "omit_candidates": [
    {"segment_ids": ["s0009"], "reason": "Article de loi, pas nécessaire pour la lectrice"}
  ]
}
{% else %}
{
  "doc_type": "Brief",
  "audience": "Hundehalterinnen und Hundehalter",
  "core": {
    "what": {"text": "Die Gemeinde verlangt eine Steuer für Hunde.", "segment_ids": ["s0002"]},
    "must_do": {"text": "Den Hund anmelden und die Steuer bezahlen.", "segment_ids": ["s0003", "s0005"]},
    "deadline": {"text": "Bis 30. April 2026.", "segment_ids": ["s0003"]},
    "cost": {"text": "120 Franken pro Hund.", "segment_ids": ["s0002"]},
    "contact": {"text": "Einwohnerkontrolle, Telefon 031 987 65 43.", "segment_ids": ["s0008"]}
  },
  "facts": [
    {"id": "f01", "kind": "deadline", "text": "Die Hundesteuer muss bis 30. April 2026 bezahlt sein.", "value_norm": "2026-04-30", "segment_ids": ["s0003"], "must_keep": true},
    {"id": "f02", "kind": "amount", "text": "Die Hundesteuer kostet 120 Franken pro Hund.", "value_norm": "120", "segment_ids": ["s0002"], "must_keep": true},
    {"id": "f03", "kind": "obligation", "text": "Jeder Hund muss bei der Einwohnerkontrolle angemeldet sein.", "value_norm": null, "segment_ids": ["s0005"], "must_keep": true}
  ],
  "hard_terms": [
    {"term": "Einwohnerkontrolle", "explanation": "Das Amt der Gemeinde für die Menschen, die dort wohnen.", "segment_ids": ["s0005"]}
  ],
  "omit_candidates": [
    {"segment_ids": ["s0009"], "reason": "Gesetzesartikel, für die Leserin nicht nötig"}
  ]
}
{% endif %}

The document:

{{ source }}
