{#- The decision mode's partial (docs/use-case-decisions.md): one section
    per stage, pulled into the standard template by its include line when a job runs
    with mode "decision". A standard job never sees a word of it. Italian version of
    28 October 2026, after the French one line by line; free to change, since the
    standard prompts and their cache keys do not depend on it. -#}
{% if stage_name == "understand" %}

Il documento è una decisione di un'autorità o di un tribunale. In più:

- Le domande principali qui significano: what = Che cosa ha deciso l'autorità? must_do = Che cosa deve fare la persona adesso, e che cosa decide ancora da sola? deadline = Entro quando può contestare la decisione (termine di ricorso o di reclamo, con l'inizio del termine)? cost = Quanto costa, o chi paga? contact = A chi può fare domande, e dove inviare un ricorso?
- Ogni punto del dispositivo ("decide", "dispone", "per questi motivi") è un fatto con "must_keep": true. I rimedi giuridici sono un fatto con "must_keep": true, con il termine, il suo inizio e l'indirizzo.
- I valori dell'intestazione e dei motivi (date, importi, numeri) sono contesto ("must_keep": false), a meno che rispondano a una domanda principale.
- Un termine lo riprendi come è scritto nella decisione, con il suo inizio ("entro 30 giorni dalla notificazione"). Non calcolare mai una data che non è nella decisione.
- Chi ha un compito è nel fatto: "La curatrice consegna un inventario entro il 31 gennaio 2027." Non la persona a cui si rivolge la decisione, se la decisione dà il compito a qualcun altro.
- Puoi proporre di tralasciare una parte dei motivi; mai il dispositivo né i rimedi giuridici.
{% if addressee %}- La decisione si rivolge a {{ addressee }}. Questa persona è "la lettrice o il lettore" delle domande principali.
{% endif %}{% elif stage_name == "write" %}

Il documento è una decisione di un'autorità o di un tribunale. In più:

- I titoli sono queste domande, in questo ordine, solo se il documento risponde: Che cosa ha deciso l'autorità? Che cosa significa per Lei? Che cosa decide ancora Lei? Non è d'accordo? Entro quando? A chi può fare domande?
- Ogni punto del dispositivo e tutti i rimedi giuridici sono nel testo, con il termine, il suo inizio e l'indirizzo.
- Dei motivi scrivi le ragioni principali. Quello che tralasci è in "omissions".
- Un termine lo scrivi come è nella decisione, con il suo inizio: "entro 30 giorni dalla notificazione". Nessuna data che non è nella decisione.
- I compiti della curatrice, del curatore o dell'autorità restano a loro: "La curatrice paga le Sue fatture." Non: "Lei paga le Sue fatture."
- Niente consigli, niente giudizi, niente "purtroppo". Tu spieghi, tu non consigli.
{% if addressee %}- "Lei" è sempre {{ addressee }}. La curatrice, il curatore e l'autorità li chiami con il loro ruolo o con il loro nome.
{% else %}- "Lei" è sempre la persona a cui si rivolge la decisione. La curatrice, il curatore e l'autorità li chiami con il loro ruolo o con il loro nome.
{% endif %}
{% elif stage_name == "judge" %}
   - SEM-09: il blocco dà un consiglio o un giudizio che non è nella decisione (per esempio "purtroppo", "dovrebbe fare ricorso").
   - SEM-10: un termine è scritto senza il suo inizio (per esempio "dal ricevimento", "dalla notificazione"), o con una data calcolata che non è nella decisione.
{% if addressee %}   - "Lei" deve essere sempre {{ addressee }}; un "Lei" che indica un'altra persona o che riceve un compito della curatrice o dell'autorità è un SEM-03.
{% endif %}
{% elif stage_name == "repair" %}
- Il documento è una decisione. Ogni punto del dispositivo e i rimedi giuridici restano completi: termine, inizio del termine, indirizzo. Un termine resta come è nella decisione; nessuna data calcolata. Niente consigli, niente giudizi.
{% if addressee %}- "Lei" è sempre {{ addressee }}. I compiti della curatrice, del curatore o dell'autorità restano a loro.
{% endif %}
{% endif %}
