Vous préparez une version en {{ level_name }}. Pour cela, vous lisez un document officiel suisse et vous faites une fiche de faits. Vous ne réécrivez encore rien.

Le document est plus bas. Chaque ligne est une phrase avec son numéro entre crochets. Les lignes avec # sont des titres, les lignes avec - sont des points de liste.

Votre tâche :

1. Dites en quelques mots de quel type de document il s'agit (par exemple lettre, décision, formulaire, notice, page web) et à qui il s'adresse.
2. Répondez aux 5 questions principales de la lectrice ou du lecteur, seulement avec le document. Pour chaque réponse, donnez les numéros des phrases d'où elle vient. Si le document ne répond pas à une question, mettez "text" à null et laissez "segment_ids" vide. Ne devinez jamais.
   - what : De quoi s'agit-il ?
   - must_do : Que doit faire la lectrice ou le lecteur ?
   - deadline : Jusqu'à quand ?
   - cost : Combien ça coûte, ou de combien d'argent s'agit-il ?
   - contact : À qui peut-on poser des questions ?
3. Faites la liste de tous les faits qu'il ne faut pas perdre : délais, montants, obligations, droits, conditions, contacts, démarches et notions. Un fait par entrée, numéroté f01, f02, f03 et ainsi de suite.
   - "kind" : deadline, amount, obligation, right, condition, contact, procedure, definition ou other.
   - "text" : le fait en une phrase courte, avec la valeur exacte.
   - "value_norm" : la valeur exacte, s'il y en a une, sous cette forme : une date en AAAA-MM-JJ, sans année en --MM-JJ ; un montant en nombre, sans monnaie et sans séparateur (1500 ou 20.50) ; un numéro de téléphone en chiffres seulement (0321234567) ; une adresse e-mail ; une adresse internet ; un pourcentage en 10% ; une heure en HH:MM. Sinon null.
   - "segment_ids" : les phrases d'où vient le fait.
   - "must_keep" : true si la lectrice ou le lecteur a besoin de ce fait. false pour une simple information de contexte.
4. Faites la liste des mots difficiles : mots techniques, noms d'offices, abréviations. Expliquez chaque mot simplement, en 2 phrases courtes au plus.
5. Faites la liste des passages qu'une version en {{ level_name }} peut laisser de côté, par exemple des articles de loi, des répétitions ou des remarques internes. Donnez les numéros des phrases et une raison courte.

Écrivez tous les textes en français.

Répondez seulement avec un objet JSON, sans autre texte. La forme est la suivante (les valeurs sont seulement un exemple) :

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

Le document :

{{ source }}
