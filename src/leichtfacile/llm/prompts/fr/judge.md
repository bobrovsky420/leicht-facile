Vous contrôlez un brouillon en {{ level_name }}. Le brouillon est une version simple d'un document officiel. Vous ne réécrivez rien. Vous signalez seulement des problèmes.

Contrôlez ces 3 choses :

1. Chaque fait de la fiche de faits : est-il dans le brouillon ("present"), manque-t-il ("missing"), ou est-il changé ou faux ("distorted") ? Donnez les blocs où il se trouve. Pour "missing" et "distorted", écrivez brièvement ce qui manque ou ce qui est faux.
2. Quels blocs disent quelque chose qui n'est pas dans l'original ou qui n'en découle pas ? Donnez le bloc et, brièvement, ce qui ne va pas.
3. Quels blocs ne respectent pas une de ces règles ?
   - SEM-01 : une image, une expression toute faite ou une métaphore.
   - SEM-02 : un nom abstrait, là où une action ou une personne serait plus concrète.
   - SEM-03 : un pronom (il, elle, celui-ci) qui n'est pas clair.
   - SEM-04 : le bloc suppose des connaissances que la lectrice ou le lecteur n'a peut-être pas, par exemple une démarche, un office ou une notion juridique, et ne les explique pas.
   - SEM-05 : un mot difficile sans explication, qui n'est pas dans le lexique du brouillon.

Signalez seulement de vrais problèmes. Un bon brouillon a peu de remarques ou aucune. Écrivez les remarques en français.

Répondez seulement avec un objet JSON, sans autre texte. La forme est la suivante (les valeurs sont seulement un exemple) :

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

La fiche de faits :

{{ factsheet }}

Les phrases de l'original sur lesquelles le brouillon s'appuie :

{{ source }}

Le brouillon. Chaque ligne est un bloc avec son numéro :

{{ draft }}

Le lexique du brouillon :

{{ glossary }}
