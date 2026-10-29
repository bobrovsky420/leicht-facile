{#- The decision mode's partial for Germany (docs/use-case-decisions.md): the Swiss
    partial (de-CH/decision.md) section by section, in the words of German administrative
    law. A Bescheid states its decision in the sentences before the heading Begründung,
    without a heading of its own (a court's Beschluss before Gründe); its
    Rechtsbehelfsbelehrung names a Widerspruch, or a Klage at the Verwaltungsgericht,
    within a month of the Bekanntgabe (VwGO § 70, § 74); the rechtliche Betreuung with its
    Betreuerin or Betreuer stands where Switzerland has the Beistandschaft. First draft of
    29 October 2026, not yet measured on a model. -#}
{% if stage_name == "understand" %}

Das Dokument ist ein Bescheid einer Behörde oder eine Entscheidung eines Gerichts. Dafür gilt zusätzlich:

- Die Kernfragen bedeuten hier: what = Was hat die Behörde entschieden? must_do = Was muss die Person jetzt tun, und was entscheidet sie weiter selbst? deadline = Bis wann kann sie sich wehren (Frist für Widerspruch oder Klage, mit dem Beginn der Frist)? cost = Was kostet es, oder wer bezahlt? contact = Wen kann sie fragen, und wo muss ein Widerspruch oder eine Klage hin?
- Jeder Punkt der Entscheidung (die Sätze vor der Überschrift "Begründung" oder "Gründe", meistens ohne eigene Überschrift: "wird bewilligt", "wird abgelehnt", "wird festgesetzt") ist eine Tatsache mit "must_keep": true. Die Rechtsbehelfsbelehrung ist eine Tatsache mit "must_keep": true, mit der Frist, ihrem Beginn und der Adresse.
- Werte im Kopf des Bescheids und in der Begründung (Daten, Beträge, Nummern) sind Hintergrund ("must_keep": false), außer sie beantworten eine Kernfrage.
- Eine Frist übernimmst du so, wie sie im Bescheid steht, mit ihrem Beginn ("innerhalb eines Monats nach Bekanntgabe"). Berechne nie ein Datum, das nicht im Bescheid steht.
- Wer eine Aufgabe hat, steht in der Tatsache: "Die Betreuerin reicht bis 31. Januar 2027 ein Vermögensverzeichnis ein." Nicht die Person, an die der Bescheid gerichtet ist, wenn der Bescheid die Aufgabe jemand anderem gibt.
- Die Begründung darfst du als Stellen zum Weglassen vorschlagen; die Entscheidung selbst und die Rechtsbehelfsbelehrung nie.
{% if addressee %}- Der Bescheid ist an {{ addressee }} gerichtet. Diese Person ist "die Leserin oder der Leser" der Kernfragen.
{% endif %}{% elif stage_name == "write" %}

Das Dokument ist ein Bescheid einer Behörde oder eine Entscheidung eines Gerichts. Dafür gilt zusätzlich:

- Die Überschriften sind diese Fragen, in dieser Reihenfolge, nur so weit das Dokument sie beantwortet: Was hat die Behörde entschieden? Was bedeutet das für Sie? Was entscheiden Sie weiter selbst? Sind Sie nicht einverstanden? Bis wann? Wen können Sie fragen?
- Jeder Punkt der Entscheidung und die ganze Rechtsbehelfsbelehrung stehen im Text, mit der Frist, ihrem Beginn und der Adresse.
- Von der Begründung schreibst du die Hauptgründe. Was du weglässt, steht in "omissions".
- Eine Frist schreibst du so, wie sie im Bescheid steht, mit ihrem Beginn: "innerhalb eines Monats nach Bekanntgabe". Kein Datum, das nicht im Bescheid steht.
- Aufgaben der Betreuerin, des Betreuers oder der Behörde bleiben bei ihnen: "Die Betreuerin bezahlt Ihre Rechnungen." Nicht: "Sie bezahlen Ihre Rechnungen."
- Keine Ratschläge, keine Bewertung, kein "leider". Du erklärst, du rätst nicht.
{% if addressee %}- "Sie" ist immer {{ addressee }}. Die Betreuerin, den Betreuer und die Behörde nennst du bei der Rolle oder beim Namen.
{% else %}- "Sie" ist immer die Person, an die der Bescheid gerichtet ist. Die Betreuerin, den Betreuer und die Behörde nennst du bei der Rolle oder beim Namen.
{% endif %}
{% elif stage_name == "judge" %}
   - SEM-09: der Block gibt einen Rat oder eine Bewertung, die nicht im Bescheid steht (zum Beispiel "leider", "Sie sollten Widerspruch einlegen").
   - SEM-10: eine Frist steht ohne ihren Beginn (zum Beispiel "nach Bekanntgabe", "ab Zustellung"), oder mit einem berechneten Datum, das nicht im Bescheid steht.
{% if addressee %}   - "Sie" muss immer {{ addressee }} sein; ein "Sie", das eine andere Person meint oder eine Aufgabe der Betreuerin oder der Behörde bekommt, meldest du als SEM-03.
{% endif %}
{% elif stage_name == "repair" %}
- Das Dokument ist ein Bescheid. Jeder Punkt der Entscheidung und die Rechtsbehelfsbelehrung bleiben vollständig: Frist, Beginn der Frist, Adresse. Eine Frist bleibt, wie sie im Bescheid steht; kein berechnetes Datum. Keine Ratschläge, keine Bewertung.
{% if addressee %}- "Sie" ist immer {{ addressee }}. Aufgaben der Betreuerin, des Betreuers oder der Behörde bleiben bei ihnen.
{% endif %}
{% endif %}
