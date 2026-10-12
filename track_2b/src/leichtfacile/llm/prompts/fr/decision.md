{#- The decision mode's partial (PLAN.md WP15, docs/use-case-decisions.md): one section
    per stage, pulled into the standard template by its include line when a job runs
    with mode "decision". A standard job never sees a word of it. First draft of
    7 October 2026; free to change after the prompt freeze, since the standard
    prompts and their cache keys do not depend on it. -#}
{% if stage_name == "understand" %}

Le document est une décision d'une autorité ou d'un tribunal. En plus :

- Les questions principales signifient ici : what = Qu'a décidé l'autorité ? must_do = Que doit faire la personne maintenant, et que décide-t-elle encore elle-même ? deadline = Jusqu'à quand peut-elle contester (délai de recours ou d'opposition, avec le début du délai) ? cost = Combien ça coûte, ou qui paie ? contact = À qui peut-elle poser des questions, et où envoyer un recours ?
- Chaque point du dispositif ("décide", "prononce", "par ces motifs") est un fait avec "must_keep": true. Les voies de droit sont un fait avec "must_keep": true, avec le délai, son début et l'adresse.
- Les valeurs de l'en-tête et des motifs (dates, montants, numéros) sont du contexte ("must_keep": false), sauf si elles répondent à une question principale.
- Un délai, tu le reprends tel qu'il est écrit dans la décision, avec son début ("dans les 30 jours dès la notification"). Ne calcule jamais une date qui n'est pas dans la décision.
- Qui a une tâche est dans le fait : "La curatrice remet un inventaire jusqu'au 31 janvier 2027." Pas la personne à qui la décision s'adresse, si la décision donne la tâche à quelqu'un d'autre.
- Tu peux proposer de laisser de côté une partie des motifs ; jamais le dispositif ni les voies de droit.
{% if addressee %}- La décision s'adresse à {{ addressee }}. Cette personne est "la lectrice ou le lecteur" des questions principales.
{% endif %}{% elif stage_name == "write" %}

Le document est une décision d'une autorité ou d'un tribunal. En plus :

- Les titres sont ces questions, dans cet ordre, seulement si le document y répond : Qu'a décidé l'autorité ? Qu'est-ce que cela veut dire pour vous ? Que décidez-vous encore vous-même ? Vous n'êtes pas d'accord ? Jusqu'à quand ? À qui pouvez-vous poser des questions ?
- Chaque point du dispositif et toutes les voies de droit sont dans le texte, avec le délai, son début et l'adresse.
- Des motifs, tu écris les raisons principales. Ce que tu laisses de côté est dans "omissions".
- Un délai, tu l'écris tel qu'il est dans la décision, avec son début : "dans les 30 jours dès la notification". Pas de date qui n'est pas dans la décision.
- Les tâches de la curatrice, du curateur ou de l'autorité restent chez eux : "La curatrice paie vos factures." Pas : "Vous payez vos factures."
- Pas de conseil, pas de jugement, pas de "malheureusement". Tu expliques, tu ne conseilles pas.
{% if addressee %}- "Vous" est toujours {{ addressee }}. La curatrice, le curateur et l'autorité sont nommés par leur rôle ou leur nom.
{% else %}- "Vous" est toujours la personne à qui la décision s'adresse. La curatrice, le curateur et l'autorité sont nommés par leur rôle ou leur nom.
{% endif %}
{% elif stage_name == "judge" %}
   - SEM-09 : le bloc donne un conseil ou un jugement qui n'est pas dans la décision (par exemple "malheureusement", "vous devriez faire recours").
   - SEM-10 : un délai est écrit sans son début (par exemple "dès réception", "dès la notification"), ou avec une date calculée qui n'est pas dans la décision.
{% if addressee %}   - "Vous" doit toujours être {{ addressee }} ; un "vous" qui désigne une autre personne ou qui reçoit une tâche de la curatrice ou de l'autorité est un SEM-03.
{% endif %}
{% elif stage_name == "repair" %}
- Le document est une décision. Chaque point du dispositif et les voies de droit restent complets : délai, début du délai, adresse. Un délai reste tel qu'il est dans la décision ; pas de date calculée. Pas de conseil, pas de jugement.
{% if addressee %}- "Vous" est toujours {{ addressee }}. Les tâches de la curatrice, du curateur ou de l'autorité restent chez eux.
{% endif %}
{% endif %}
