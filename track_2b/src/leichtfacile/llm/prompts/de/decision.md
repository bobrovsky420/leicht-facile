{#- The decision mode's partial (PLAN.md WP15, docs/use-case-decisions.md): one section
    per stage, pulled into the standard template by its include line when a job runs
    with mode "decision". A standard job never sees a word of it. First draft of
    7 October 2026; free to change after the prompt freeze, since the standard
    prompts and their cache keys do not depend on it. -#}
{% if stage_name == "understand" %}

Das Dokument ist ein Entscheid einer Behörde oder eines Gerichts. Dafür gilt zusätzlich:

- Die Kernfragen bedeuten hier: what = Was hat die Behörde entschieden? must_do = Was muss die Person jetzt tun, und was entscheidet sie weiter selbst? deadline = Bis wann kann sie sich wehren (Frist für Beschwerde oder Einsprache, mit dem Beginn der Frist)? cost = Was kostet es, oder wer bezahlt? contact = Wen kann sie fragen, und wo muss eine Beschwerde hin?
- Jeder Punkt des Entscheids (Dispositiv, "erkennt", "verfügt", "beschliesst") ist eine Tatsache mit "must_keep": true. Die Rechtsmittelbelehrung ist eine Tatsache mit "must_keep": true, mit der Frist, ihrem Beginn und der Adresse.
- Werte im Kopf des Entscheids und in der Begründung (Daten, Beträge, Nummern) sind Hintergrund ("must_keep": false), ausser sie beantworten eine Kernfrage.
- Eine Frist übernimmst du so, wie sie im Entscheid steht, mit ihrem Beginn ("innert 30 Tagen seit Mitteilung"). Berechne nie ein Datum, das nicht im Entscheid steht.
- Wer eine Aufgabe hat, steht in der Tatsache: "Die Beiständin reicht bis 31. Januar 2027 ein Inventar ein." Nicht die Person, an die der Entscheid gerichtet ist, wenn der Entscheid die Aufgabe jemand anderem gibt.
- Die Begründung darfst du als Stellen zum Weglassen vorschlagen; den Entscheid selbst und die Rechtsmittelbelehrung nie.
{% if addressee %}- Der Entscheid ist an {{ addressee }} gerichtet. Diese Person ist "die Leserin oder der Leser" der Kernfragen.
{% endif %}{% elif stage_name == "write" %}

Das Dokument ist ein Entscheid einer Behörde oder eines Gerichts. Dafür gilt zusätzlich:

- Die Überschriften sind diese Fragen, in dieser Reihenfolge, nur so weit das Dokument sie beantwortet: Was hat die Behörde entschieden? Was bedeutet das für Sie? Was entscheiden Sie weiter selbst? Sind Sie nicht einverstanden? Bis wann? Wen können Sie fragen?
- Jeder Punkt des Entscheids und die ganze Rechtsmittelbelehrung stehen im Text, mit der Frist, ihrem Beginn und der Adresse.
- Von der Begründung schreibst du die Hauptgründe. Was du weglässt, steht in "omissions".
- Eine Frist schreibst du so, wie sie im Entscheid steht, mit ihrem Beginn: "innert 30 Tagen seit Mitteilung". Kein Datum, das nicht im Entscheid steht.
- Aufgaben der Beiständin, des Beistands oder der Behörde bleiben bei ihnen: "Die Beiständin bezahlt Ihre Rechnungen." Nicht: "Sie bezahlen Ihre Rechnungen."
- Keine Ratschläge, keine Bewertung, kein "leider". Du erklärst, du rätst nicht.
{% if addressee %}- "Sie" ist immer {{ addressee }}. Die Beiständin, den Beistand und die Behörde nennst du bei der Rolle oder beim Namen.
{% else %}- "Sie" ist immer die Person, an die der Entscheid gerichtet ist. Die Beiständin, den Beistand und die Behörde nennst du bei der Rolle oder beim Namen.
{% endif %}
{% elif stage_name == "judge" %}
   - SEM-09: der Block gibt einen Rat oder eine Bewertung, die nicht im Entscheid steht (zum Beispiel "leider", "Sie sollten Beschwerde erheben").
   - SEM-10: eine Frist steht ohne ihren Beginn (zum Beispiel "nach Erhalt", "ab Zustellung"), oder mit einem berechneten Datum, das nicht im Entscheid steht.
{% if addressee %}   - "Sie" muss immer {{ addressee }} sein; ein "Sie", das eine andere Person meint oder eine Aufgabe der Beiständin oder der Behörde bekommt, meldest du als SEM-03.
{% endif %}
{% elif stage_name == "repair" %}
- Das Dokument ist ein Entscheid. Jeder Punkt des Entscheids und die Rechtsmittelbelehrung bleiben vollständig: Frist, Beginn der Frist, Adresse. Eine Frist bleibt, wie sie im Entscheid steht; kein berechnetes Datum. Keine Ratschläge, keine Bewertung.
{% if addressee %}- "Sie" ist immer {{ addressee }}. Aufgaben der Beiständin, des Beistands oder der Behörde bleiben bei ihnen.
{% endif %}
{% endif %}
