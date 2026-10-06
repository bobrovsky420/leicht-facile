Vous améliorez certains blocs d'un texte en {{ level_name }} (niveau {{ level }}). Vous changez seulement les blocs qui sont plus bas. Tout le reste ne change pas.

{{ style_guide }}

Règles pour l'amélioration :

- Pour chaque bloc, vous écrivez un nouveau texte. Vous pouvez couper un bloc en 2 ou 3 phrases courtes. Dans ce cas, vous écrivez plusieurs textes.
- Résolvez chaque problème signalé. Une suggestion après "Suggestion :" est en général juste.
- Gardez toutes les valeurs exactes : délais, montants, numéros de téléphone, adresses.
- N'écrivez rien qui n'est pas dans l'original.
{% if missing %}- Certains faits manquent dans le texte. C'est le plus important : pour chaque fait qui manque, écrivez 1 ou 2 nouvelles phrases dans "additions", avec exactement la valeur de la fiche de faits. Dites après quel bloc elles viennent ("after") et donnez le fait dans "fact_ids".
- Changez des blocs seulement s'ils sont plus haut sous "Les blocs à améliorer".
{% endif %}
Répondez seulement avec un objet JSON, sans autre texte. La forme est la suivante (les valeurs sont seulement un exemple) :

{
  "repairs": [
    {"id": "b005", "texts": ["Vous payez jusqu'au 30 avril 2026.", "Vous payez à la commune."]}
  ],
  "additions": [
    {"after": "b007", "texts": ["Téléphonez au contrôle des habitants : 032 987 65 43."], "fact_ids": ["f04"], "segment_ids": ["s0008"]}
  ]
}

Les blocs à améliorer :

{{ flagged }}
{% if missing %}
Les faits qui manquent :

{{ missing }}
{% endif %}
La fiche de faits :

{{ factsheet }}

Tout le brouillon, pour que vous connaissiez le contexte :

{{ draft }}

Les phrases de l'original pour ces blocs :

{{ source }}
