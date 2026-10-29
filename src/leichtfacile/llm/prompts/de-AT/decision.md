{#- The decision mode's partial for Austria (docs/use-case-decisions.md): the Swiss
    partial (de/decision.md) section by section, in the words of Austrian administrative
    law. A Bescheid has the headings Spruch, Begründung and Rechtsmittelbelehrung (AVG
    § 58 to § 61); the Beschwerde to the Landesverwaltungsgericht is due within four
    weeks of the Zustellung (VwGVG § 7 Abs. 4) and is filed with the authority (VwGVG
    § 12); the Erwachsenenvertretung stands where Switzerland has the Beistandschaft.
    First draft of 29 October 2026, not yet measured on a model. -#}
{% if stage_name == "understand" %}

Das Dokument ist ein Bescheid einer Behörde oder eine Entscheidung eines Gerichts. Dafür gilt zusätzlich:

- Die Kernfragen bedeuten hier: what = Was hat die Behörde entschieden? must_do = Was muss die Person jetzt tun, und was entscheidet sie weiter selbst? deadline = Bis wann kann sie sich wehren (Frist für Beschwerde oder Einspruch, mit dem Beginn der Frist)? cost = Was kostet es, oder wer bezahlt? contact = Wen kann sie fragen, und wo muss eine Beschwerde hin?
- Jeder Punkt des Spruchs (unter der Überschrift "Spruch": "wird stattgegeben", "wird abgewiesen", "wird erteilt") ist eine Tatsache mit "must_keep": true. Die Rechtsmittelbelehrung ist eine Tatsache mit "must_keep": true, mit der Frist, ihrem Beginn und der Adresse.
- Werte im Kopf des Bescheids und in der Begründung (Daten, Beträge, Nummern) sind Hintergrund ("must_keep": false), außer sie beantworten eine Kernfrage.
- Eine Frist übernimmst du so, wie sie im Bescheid steht, mit ihrem Beginn ("binnen vier Wochen nach Zustellung"). Berechne nie ein Datum, das nicht im Bescheid steht.
- Wer eine Aufgabe hat, steht in der Tatsache: "Die Erwachsenenvertreterin legt dem Gericht bis 31. Jänner 2027 einen Bericht vor." Nicht die Person, an die der Bescheid gerichtet ist, wenn der Bescheid die Aufgabe jemand anderem gibt.
- Die Begründung darfst du als Stellen zum Weglassen vorschlagen; den Spruch und die Rechtsmittelbelehrung nie.
{% if addressee %}- Der Bescheid ist an {{ addressee }} gerichtet. Diese Person ist "die Leserin oder der Leser" der Kernfragen.
{% endif %}{% elif stage_name == "write" %}

Das Dokument ist ein Bescheid einer Behörde oder eine Entscheidung eines Gerichts. Dafür gilt zusätzlich:

- Die Überschriften sind diese Fragen, in dieser Reihenfolge, nur so weit das Dokument sie beantwortet: Was hat die Behörde entschieden? Was bedeutet das für Sie? Was entscheiden Sie weiter selbst? Sind Sie nicht einverstanden? Bis wann? Wen können Sie fragen?
- Jeder Punkt des Spruchs und die ganze Rechtsmittelbelehrung stehen im Text, mit der Frist, ihrem Beginn und der Adresse.
- Von der Begründung schreibst du die Hauptgründe. Was du weglässt, steht in "omissions".
- Eine Frist schreibst du so, wie sie im Bescheid steht, mit ihrem Beginn: "binnen vier Wochen nach Zustellung". Kein Datum, das nicht im Bescheid steht.
- Aufgaben der Erwachsenenvertreterin, des Erwachsenenvertreters oder der Behörde bleiben bei ihnen: "Die Erwachsenenvertreterin bezahlt Ihre Rechnungen." Nicht: "Sie bezahlen Ihre Rechnungen."
- Keine Ratschläge, keine Bewertung, kein "leider". Du erklärst, du rätst nicht.
{% if addressee %}- "Sie" ist immer {{ addressee }}. Die Erwachsenenvertreterin, den Erwachsenenvertreter und die Behörde nennst du bei der Rolle oder beim Namen.
{% else %}- "Sie" ist immer die Person, an die der Bescheid gerichtet ist. Die Erwachsenenvertreterin, den Erwachsenenvertreter und die Behörde nennst du bei der Rolle oder beim Namen.
{% endif %}
{% elif stage_name == "judge" %}
   - SEM-09: der Block gibt einen Rat oder eine Bewertung, die nicht im Bescheid steht (zum Beispiel "leider", "Sie sollten Beschwerde erheben").
   - SEM-10: eine Frist steht ohne ihren Beginn (zum Beispiel "nach Zustellung", "ab Erhalt"), oder mit einem berechneten Datum, das nicht im Bescheid steht.
{% if addressee %}   - "Sie" muss immer {{ addressee }} sein; ein "Sie", das eine andere Person meint oder eine Aufgabe der Erwachsenenvertreterin oder der Behörde bekommt, meldest du als SEM-03.
{% endif %}
{% elif stage_name == "repair" %}
- Das Dokument ist ein Bescheid. Jeder Punkt des Spruchs und die Rechtsmittelbelehrung bleiben vollständig: Frist, Beginn der Frist, Adresse. Eine Frist bleibt, wie sie im Bescheid steht; kein berechnetes Datum. Keine Ratschläge, keine Bewertung.
{% if addressee %}- "Sie" ist immer {{ addressee }}. Aufgaben der Erwachsenenvertreterin, des Erwachsenenvertreters oder der Behörde bleiben bei ihnen.
{% endif %}
{% endif %}
