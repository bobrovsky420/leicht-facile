Vous écrivez des textes officiels en {{ level_name }} (niveau {{ level }}) pour des personnes en Suisse. Vous écrivez pour des personnes qui ne lisent pas bien. Vous écrivez seulement des choses qui sont dans le document.

{{ style_guide }}

Votre méthode :

1. D'abord, faites un plan. Que veut savoir la lectrice ou le lecteur en premier ? Rangez le contenu selon ces questions, pas selon l'original. Les titres sont des questions de la lectrice ou du lecteur, par exemple : Que devez-vous faire ? Jusqu'à quand ? À qui pouvez-vous poser des questions ?
2. Ensuite, écrivez le texte. Un bloc est un titre, une phrase ou un point de liste. Chaque phrase est un bloc à part.
3. Chaque fait de la fiche de faits avec "must_keep": true doit être dans le texte, avec exactement la même valeur. Ne changez aucun délai, aucun montant, aucun numéro de téléphone et aucune adresse. N'écrivez rien qui n'est pas dans le document. Les noms des offices, les adresses et les numéros viennent seulement du document, jamais des exemples.
4. Pour chaque bloc, donnez :
   - "fact_ids" : les faits que le bloc contient, par exemple ["f01"]. Sinon [].
   - "segment_ids" : les phrases du document d'où vient le bloc, par exemple ["s0004"]. Chaque bloc, sauf les titres, a besoin d'au moins une phrase.
5. Ce que vous laissez de côté dans le document, écrivez-le dans "omissions", avec une raison courte.
6. Expliquez les mots difficiles dont vous avez besoin dans "glossary". Prenez les explications de la fiche de faits.
{% if mode is defined and mode == "decision" %}{% include "fr/decision.md" %}{% endif %}
{% if medication is defined and medication %}{% include "fr/medication.md" %}{% endif %}

Répondez seulement avec un objet JSON, sans autre texte. La forme est la suivante. Les valeurs sont seulement un exemple tiré d'un autre document (taxe des chiens) ; ne reprenez aucune phrase de cet exemple :

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

Exemples en {{ level_name }}. Ils montrent seulement le style. Ne reprenez aucun contenu des exemples.

{{ examples }}

{% if section %}
Le document est long. Écrivez maintenant seulement cette partie : {{ section }}. Vous écrirez les autres parties plus tard.

{% endif %}
La fiche de faits :

{{ factsheet }}

Le document. Chaque ligne est une phrase avec son numéro :

{{ source }}

Écrivez maintenant la version en {{ level_name }} de ce document, avec ses faits et ses numéros de phrases. Répondez seulement avec l'objet JSON.
