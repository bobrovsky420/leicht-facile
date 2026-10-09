{#- The decision mode's partial with English instructions (LLM_ENGLISH_PROMPTS,
    docs/prompts.md "English instructions"): de/decision.md and fr/decision.md in
    English, line for line. The legal terms, the quoted examples and the reader's
    headings stay in the document's language, as in that partial. -#}
{% set fr = lang == "fr" %}
{% set operative = 'dispositif, "décide", "prononce", "par ces motifs"' if fr else 'Dispositiv, "erkennt", "verfügt", "beschliesst"' %}
{% set appeal = "voies de droit" if fr else "Rechtsmittelbelehrung" %}
{% set period = "dans les 30 jours dès la notification" if fr else "innert 30 Tagen seit Mitteilung" %}
{% set task = "La curatrice remet un inventaire jusqu'au 31 janvier 2027." if fr else "Die Beiständin reicht bis 31. Januar 2027 ein Inventar ein." %}
{% set deputy = "curatrice or curateur" if fr else "Beiständin or Beistand" %}
{% set headings = "Qu'a décidé l'autorité ? Qu'est-ce que cela veut dire pour vous ? Que décidez-vous encore vous-même ? Vous n'êtes pas d'accord ? Jusqu'à quand ? À qui pouvez-vous poser des questions ?" if fr else "Was hat die Behörde entschieden? Was bedeutet das für Sie? Was entscheiden Sie weiter selbst? Sind Sie nicht einverstanden? Bis wann? Wen können Sie fragen?" %}
{% set duty = "La curatrice paie vos factures." if fr else "Die Beiständin bezahlt Ihre Rechnungen." %}
{% set not_duty = "Vous payez vos factures." if fr else "Sie bezahlen Ihre Rechnungen." %}
{% set unfortunately = "malheureusement" if fr else "leider" %}
{% set advice = '"malheureusement", "vous devriez faire recours"' if fr else '"leider", "Sie sollten Beschwerde erheben"' %}
{% set start = '"dès réception", "dès la notification"' if fr else '"nach Erhalt", "ab Zustellung"' %}
{% set you = "Vous" if fr else "Sie" %}
{% if stage_name == "understand" %}

The document is a decision of an authority or a court. For it, these rules apply as well:

- The core questions mean here: what = What has the authority decided? must_do = What must the person do now, and what does the person go on deciding alone? deadline = By when can the person object (the period for an appeal or an objection, with the start of the period)? cost = What does it cost, or who pays? contact = Whom can the person ask, and where must an appeal go?
- Every point of the operative part ({{ operative }}) is a fact with "must_keep": true. The instructions on how to appeal ({{ appeal }}) are a fact with "must_keep": true, with the period, its start and the address.
- Values in the header of the decision and in its reasons (dates, amounts, numbers) are background ("must_keep": false), unless they answer a core question.
- Take a period as it stands in the decision, with its start ("{{ period }}"). Never calculate a date that is not in the decision.
- Who has a task is in the fact: "{{ task }}" Not the person the decision is addressed to, if the decision gives the task to someone else.
- You may suggest the reasons as passages to leave out; never the decision itself and never the instructions on how to appeal.
{% if addressee %}- The decision is addressed to {{ addressee }}. This person is "the reader" of the core questions.
{% endif %}{% elif stage_name == "write" %}

The document is a decision of an authority or a court. For it, these rules apply as well:

- The headings are these questions, in this order, as far as the document answers them: {{ headings }}
- Every point of the operative part and all of the instructions on how to appeal are in the text, with the period, its start and the address.
- Of the reasons, write the main ones. What you leave out goes into "omissions".
- Write a period as it stands in the decision, with its start: "{{ period }}". No date that is not in the decision.
- Tasks of the deputy ({{ deputy }}) or of the authority stay with them: "{{ duty }}" Not: "{{ not_duty }}"
- No advice, no judgement, no "{{ unfortunately }}". You explain, you do not advise.
{% if addressee %}- "{{ you }}" is always {{ addressee }}. Name the deputy and the authority by their role or by their name.
{% else %}- "{{ you }}" is always the person the decision is addressed to. Name the deputy and the authority by their role or by their name.
{% endif %}
{% elif stage_name == "judge" %}
   - SEM-09: the block gives advice or a judgement that is not in the decision (for example {{ advice }}).
   - SEM-10: a period stands without its start (for example {{ start }}), or with a calculated date that is not in the decision.
{% if addressee %}   - "{{ you }}" must always be {{ addressee }}; report a "{{ you }}" that means another person, or that gets a task of the deputy or of the authority, as SEM-03.
{% endif %}
{% elif stage_name == "repair" %}
- The document is a decision. Every point of the operative part and the instructions on how to appeal stay complete: period, start of the period, address. A period stays as it stands in the decision; no calculated date. No advice, no judgement.
{% if addressee %}- "{{ you }}" is always {{ addressee }}. Tasks of the deputy ({{ deputy }}) or of the authority stay with them.
{% endif %}
{% endif %}
