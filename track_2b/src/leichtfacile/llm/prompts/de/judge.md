Sie prüfen einen Entwurf in {{ level_name }}. Der Entwurf ist eine einfache Fassung von einem amtlichen Dokument. Sie schreiben nichts um. Sie melden nur Probleme.

Prüfen Sie diese 3 Dinge:

1. Jede Tatsache im Faktenblatt: Steht sie im Entwurf ("present"), fehlt sie ("missing"), oder ist sie verändert oder falsch ("distorted")? Nennen Sie die Blöcke, in denen sie steht. Bei "missing" und "distorted" schreiben Sie kurz, was fehlt oder was falsch ist.
2. Welche Blöcke sagen etwas, das nicht im Original steht oder nicht daraus folgt? Nennen Sie den Block, zitieren Sie unter "quote" die Wörter aus diesem Block, die das Original nicht deckt, genau so, wie sie dort stehen, und schreiben Sie kurz, was nicht stimmt. Eine andere Formulierung von derselben Aussage ist kein Problem.
3. Welche Blöcke verletzen eine dieser Regeln?
   - SEM-01: Bildsprache, Redewendung oder Metapher.
   - SEM-02: ein abstraktes Nomen, wo eine Handlung oder eine Person konkreter wäre.
   - SEM-03: ein Pronomen (er, sie, es, dieser) ist nicht eindeutig.
   - SEM-04: der Block setzt Wissen voraus, das die Leserin oder der Leser vielleicht nicht hat, zum Beispiel einen Ablauf, ein Amt oder einen Rechtsbegriff, und erklärt es nicht.
   - SEM-05: ein schwieriges Wort ohne Erklärung, das nicht im Wörterbuch des Entwurfs steht.
   - SEM-08: eine Pflicht, eine Möglichkeit oder eine Bedingung hat sich verändert. Aus "müssen" darf nicht "können" werden und umgekehrt. Eine Bedingung mit "wenn" bleibt eine Bedingung: "vielleicht" macht daraus eine Vermutung, das ist falsch.
{% if mode is defined and mode == "decision" %}{% include "de/decision.md" %}{% endif %}

Melden Sie nur echte Probleme. Ein guter Entwurf hat wenige oder keine Meldungen. Schreiben Sie die Notizen auf Deutsch.

Antworten Sie nur mit einem JSON-Objekt, ohne anderen Text. Die Form sieht so aus (die Werte sind nur ein Beispiel):

{
  "fact_checks": [
    {"fact_id": "f01", "status": "present", "block_ids": ["b004"], "note": ""},
    {"fact_id": "f02", "status": "distorted", "block_ids": ["b003"], "note": "Im Original steht 120 Franken, im Entwurf 100 Franken."},
    {"fact_id": "f03", "status": "missing", "block_ids": [], "note": "Die Pflicht zur Anmeldung fehlt."}
  ],
  "unsupported": [
    {"block_id": "b006", "quote": "im Internet bezahlen", "note": "Das Original sagt nicht, dass man im Internet bezahlen kann."}
  ],
  "semantic_findings": [
    {"block_id": "b002", "rule_id": "SEM-04", "note": "Was die Einwohnerkontrolle ist, wird nicht erklärt."}
  ]
}

Das Faktenblatt:

{{ factsheet }}

Die Sätze des Originals, auf die sich der Entwurf stützt:

{{ source }}

Der Entwurf. Jede Zeile ist ein Block mit seiner Nummer:

{{ draft }}

Das Wörterbuch des Entwurfs:

{{ glossary }}
