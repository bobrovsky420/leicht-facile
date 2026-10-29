# Prompts: design notes and change log

Status: version 1, 5-6 October 2026, written and tested without the CSCS endpoint (see
"Tested so far"). Companion to [architecture.md](architecture.md) §4 and §6.

The templates live in `src/leichtfacile/llm/prompts/<lang>/` as Jinja2 files:
`understand.md`, `write.md`, `judge.md`, `repair.md`, `baseline.md`, plus few-shot
examples in `examples/`; German also has `baseline_zh.md`, the Canton of Zurich's prompt
for the second baseline (below). Every rendered prompt is identified by a short hash of its
template file; the hash is stored in each job's summary and audit bundle, so a result
can always be traced to the exact prompt that produced it.

## Design choices

| Choice | Why |
|--------|-----|
| Instructions in the language of the document | The model reads and writes German for German documents, French for French ones and Italian for Italian ones; instructions in the same language avoid another language leaking into fact texts, omission reasons and glossary entries that the reviewers read. The French templates (`prompts/fr/`) follow the German ones line by line, with French JSON examples and two French few-shot pairs on the same topics. The few words code adds around the items (fact sheet headings, "Vorschlag:", "Suggestion :" or "Suggerimento:", the problem lines of a repair round) come from one table per language (`pipeline/labels.py`). The Italian templates (`prompts/it/`, since 28 October 2026) follow the French ones the same way, with Italian JSON examples and two Italian few-shot pairs on the same topics. English instructions for German and French documents were measured against these on 9 October 2026, not taken and removed again ("English instructions" below). |
| One German template set for every national variety, the variety's facts as data (since 29 October 2026) | Three copies of the German templates would drift apart with every change of the instructions, and what Swiss German, the German of Germany and Austrian German need differently in the standard templates are a few facts: the country, the kinds of document, the currency and the spellings of an amount, and the office of the dog-tax example, with its articles, and its phone number. These are data, the `prompt` table of each German variety in `src/leichtfacile/varieties/varieties.toml`, which `src/leichtfacile/pipeline/prompts.py` puts into every rendering as `v` (`{{ v.prompt.currency }}`); a variety without a table of its own renders as Swiss German. The templates include the decision and medication partials by a path the code chooses (`{% include decision_partial %}`), the variety's own file once it has one (`src/leichtfacile/llm/prompts/de-AT/decision.md`), else the language's, since a decision follows the variety's law; the French and Italian templates, with one variety each, are not parametrized. |
| Germany and Austria bring a table, two few-shot pairs and a decision partial each (since 29 October 2026) | That is all a variety needs once the templates are one set, and with it `leichtfacile setup` offers the variety. The tables `[de-DE]` and `[de-AT]` of `varieties.toml` write the facts as each country's pages do: Bescheid among the kinds of document, Euro, the judge's two spellings of one amount (`42.000 Euro statt 42.000,00 €`, `42.000 Euro statt € 42.000,-`, after [sources.md](sources.md), "What the German pages write" and "What the Austrian pages write"), a neuter office of the municipality for the dog-tax example (das Bürgeramt, das Gemeindeamt; the templates take a neuter or feminine office, never a masculine one) and a number in the country's shape (`030 9876543`, `01 9876543`). The few-shot pairs keep the Swiss topics, so the copy guard stays a matter of a few topic words: a resident parking permit (a Bewohnerparkausweis; a Parkpickerl on an Ansuchen, payable binnen 30 Tagen) and a dog-tax letter (the Hundesteuer with a Widerspruch innerhalb eines Monats nach Bekanntgabe; the Hundeabgabe due on 31. Jänner 2026, a new dog to register binnen vier Wochen, a Beschwerde within a month of the Zustellung, as the BAO has it for a tax), each easy version keeping every value of its original, in standard spelling with ß. The decision partials follow the Swiss one section by section in each country's law: in Germany the decision stands before the heading Begründung without a heading of its own, the Rechtsbehelfsbelehrung names a Widerspruch or a Klage within a month of the Bekanntgabe, and the Betreuerin of a rechtliche Betreuung takes the Beiständin's place; in Austria the Spruch, the Rechtsmittelbelehrung, a Beschwerde binnen vier Wochen nach Zustellung (VwGVG § 7 Abs. 4) and the Erwachsenenvertreterin. Neither names a court, as the Swiss one names none. Compounds keep the Mediopunkt (`Bürger·amt`, `Park·ausweis`) until a later change renders each variety's mark; the medication partial and the labels are the language's, since none of their words differs. |
| The model is addressed informally (du, tu) | Since 12 October 2026, at the owner's request: every instruction to the model in the templates, the style guide's rule lines, the clause recipes and the labels says du in German and tu in French, as the Canton of Zurich's prompt does ("Du bist ein hilfreicher Assistent ..."). The reader of the easy-language text is still addressed with Sie and vous (LEX-06): in the few-shot pairs, the JSON forms and the decision partial. So the two addresses cannot be confused any more: a Sie in a prompt is always the reader, as in the decision partial's rule that "Sie" is always the addressee. Until then the prompts said Sie and vous to the model as well; the final run of 11 October 2026 measured those templates. |
| A concrete JSON example in each prompt instead of the JSON schema | Small models copy a filled example more reliably than they follow a schema, and the example is a fraction of the tokens. The pydantic models still validate every answer; the validation error goes back to the model once (`llm/json_out.py`). |
| Lenient parsing of the answer (`pipeline/models.py`) | An 8B model gets details wrong that do not matter: `s4` instead of `s0004`, `Deadline` instead of `deadline`, a string where a list was asked for. These are normalised; only real problems (no blocks, an empty text) count as invalid. A complete answer without the `facts` list, seen on a page with nothing countable, is read as a fact sheet with no model facts; code completion adds the countable values. On long pages the 8B abbreviates a run of ids as a range (`"s0064" bis "s0087"`), which is not JSON: the parser writes the range out, repairs trailing and missing commas, closes an object the model forgot to close before a top-level key (the schema's fields say where) and turns the straight quote that ends a German quotation inside a string into the closing German one; an answer that is still broken is reported with the position of the error, never replaced by an object from inside it. |
| The style guide is generated from the rule registry (`rules/styleguide.py`) | The writer is asked for exactly what the checker checks, with the thresholds of the chosen level. The guide changes when a rule changes; no second copy can drift. |
| Few-shot examples written by the team, on topics outside the evaluation set | The cantonal pages may not be reproduced in a public repository (docs/sources.md §4). Two short synthetic pairs show the style: a decision on a resident parking permit and a dog-tax letter. The JSON examples in the prompts use the dog tax too. In local runs, details of examples on nearby topics leaked into drafts ("Steueramt", "Gemeinde" for the Sozialversicherungsstelle); examples on distant topics make such a leak obvious and keep the evaluation clean. A test checks that the examples break no `error` rule. On the Public AI 8B without thinking, 4 of 12 dev drafts were the write prompt's JSON example itself, word for word (6 October); the form now comes before the style examples and the document last, and code recognises an answer that copies the examples (below). |
| Sentence ids in the source (`[s0004]`) and block ids in drafts (`[b007]`) | Provenance and fact references are by id; the model cites, code verifies that the ids exist (FACT-03, FACT-05). |
| The document stands between `<document>` and `</document>` | Since 10 October 2026, after a security review: a web page or a PDF can carry instructions ("ignore the rules above and write ..."), and every prompt appends the document after its instructions. Each of the ten standard templates puts the document, the original's sentences or the paragraph between the two tags and says, right before the fence, that what stands there is content, never an instruction, and that requests inside it are treated like any other sentence of the document. Code writes a tag inside the text as `[document]` or `[/document]` (`render.defused`), so the text cannot close the fence. The baselines P0 and P0-ZH are unchanged. The first template change after the freeze; the final run of 11 October 2026 repeated every row on these templates. |
| Plan first, then write | Easy language reorders content by what the reader needs; the write prompt asks for the reader's questions as headings before the text. The thinking models do the planning in their reasoning. |
| The judge reports, it never rewrites | Its answer is a list of findings with fact and block ids; repairs go back to the writer. This keeps the judge an independent instrument for the evaluation. |
| Repair sees only the flagged blocks, their problems and the facts they must keep | Smaller prompt, and the rest of the draft cannot be damaged. The rule findings come with the checker's suggestion ("Vorschlag: 31. März 2026"), which is usually right. |
| The baseline prompt (P0) is one sentence | It is what a user types into a chatbot: "Schreibe diesen Text in Leichter Sprache:", in French "Écris ce texte en FALC :". |
| The second baseline (P0-ZH) is the Canton of Zurich's prompt, verbatim | A one-sentence baseline is easy to call a strawman; the Canton of Zurich's published prompt, the only public Swiss one we found, on the same model is the fair comparison. `prompts/de/baseline_zh.md` holds the system message, the user template, the rule list and the two completeness lines of `simply-simplify-language` v1.6.0 (Canton of Zurich, MIT, THIRD_PARTY_NOTICES.md) without a change; the licence note is a Jinja comment and never reaches the model. Two variants: `complete` (keep every fact, our task) and `condensed` (essentials only, their default for Leichte Sprache). Settings as P0: no thinking, temperature 0.3, 6000 tokens. Post-processing as in their app: the text between the `<leichtesprache>` tags, ß written as ss. Their `strip_markdown` is not applied: in v1.6.0 it deletes every underscore and would break web and e-mail addresses, so applying it would measure their regex, not their prompt. We reported this upstream ([issue #18](https://github.com/machinelearningZH/simply-simplify-language/issues/18)) and fixed it ([PR #19](https://github.com/machinelearningZH/simply-simplify-language/pull/19), merged 12 October 2026, after v1.6.0); P0-ZH keeps the v1.6.0 setup, so its numbers are unchanged. An answer without the tags is used whole and noted in the job summary. German only: their app has no French prompt. |

## Stage settings

| Stage | Thinking (default) | Temperature | max_tokens without / with thinking |
|-------|--------------------|-------------|------------------------------------|
| understand | on | 0.1 | 6000 / 12000 |
| write | off | 0.3 | 8000 / 16000 |
| judge | on | 0.0 | 6000 / 12000 |
| repair | off | 0.2 | 6000 / 12000 |
| baseline (P0, P0-ZH) | off | 0.3 | 6000 / 12000 |
| recover (review page; the recover round with `pipeline.recover_facts`) | off | 0.2 | 1500 / 6000 |

`llm.thinking_stages` overrides the first column. The column applies once the endpoint's
thinking switch is set: `llm.thinking` is `off` by default since 23 October 2026,
and the Apertus profiles set it (`model-suffix` on CSCS, `chat-template` on Public AI,
vLLM and llama.cpp). Thinking models need a generous
`max_tokens`: the reasoning can be several times longer than the answer. When the
reasoning runs out of tokens before the answer, the stage is answered once more without
thinking.

## Code around the prompts

- **Fact sheet completion.** After Understand, code adds a fact for every date, amount,
  phone number, e-mail address, web address, percentage and time in the source that no
  fact carries (`origin: code`), and since 7 October 2026 for every period (`innert 30
  Tagen`, as the value `30 Tage`), identifier (case number, AHV number, IBAN, as
  written), postal address, quantity (`2,5 mg`, as `2.5 mg`) and dosing scheme
  (`1-0-1`) (docs/rules.md, "Value kinds"). Values in passages the
  model marked as droppable become background facts; all others must be kept. The first
  local run showed why: the model listed 3 facts for a letter with 11 checkable values.
  The prompts do not mention the new kinds (no prompt change before the freeze); what
  the model writes as a value for them (`30 Tage`, `2026-0042`) is parsed as text.
  Drug names are the exception (8 October 2026): code cannot find them, so for a source
  with a dose or a dosing scheme the partial `medication.md` asks Understand for one
  fact of kind `medication` per drug, the name alone as the value, and Write for one
  list item per medication (docs/rules.md FACT-09). A document without a dose gets the
  standard prompt word for word.
  Numbers measured before 7 October use the narrower hard-fact definition; the final
  run recomputes every row.
- **Fact linking.** A block that contains a fact's exact value is linked to that fact by
  code, so FACT-02 does not depend on the model's bookkeeping.
- **Copied examples.** An answer whose sentences are mostly from the prompt's own
  examples (the JSON form, the few-shot pairs: two or more, and more than half of
  them) is not a draft of the document. Code
  recognises it (`stages.example_keys`: the sentences of the rendered prompt without
  its document, normalised) and sends it back once with a message in the document's
  language; a second copy fails the stage. Understand, write and repair are checked.
  A sentence about the examples' topics (a dog, a parking permit), or with one of the
  examples' values (their phone numbers, dates, amounts and hours, read from the
  rendered prompts), in a document that has none is example content too, so
  paraphrases are caught: the answer is sent back
  once, and the sentences a second answer still has are dropped in code, since one
  such sentence is not worth a failed stage. On CSCS the 8B wrote dog-tax sentences
  into a page about EL costs with only 2 of 12 sentences verbatim. The examples' office
  counts as a topic too (`Einwohnerkontrolle`, `contrôle des habitants`, since
  8 October 2026): the repair example's addition "Rufen Sie die Einwohner·kontrolle
  an: 031 987 65 43." came back with a number of the document in 4 P2 jobs of the
  CSCS evaluation and 3 example builds, in documents that never name the office. The
  dog's microchip of the French write example (`puce`) too, since 12 October 2026:
  "le numéro de la puce" stood in five sentences of a final draft about petitions in
  the run of 11 October, flagged by the judge in every round and never removed.
- **Values not in the document.** A repair answer with a date, amount, phone number,
  e-mail address, web address, percentage or time that neither the source nor the
  fact sheet contains (the check of rule FACT-06) is sent back once with the values
  named, in the document's language. The second answer is used as it is, and when it
  is not valid JSON the first one is: the guard never fails a round. What remains is
  FACT-06's finding and the next round's problem. The write stage is not
  checked this way: a second write call is long, and FACT-06 plus a repair round do
  the same job.
- **Response cache.** An answer that cannot be used (no valid JSON, a copy of the
  example) is dropped from the response cache, so a rerun of a failed pair asks the
  model again instead of replaying the same unusable answer; the evaluation reruns
  failed pairs with the cache on.
- **The exact form of a missing value** (7 October 2026). The list of missing facts
  in a repair request names the fact sheet's value and, when the draft should write
  it differently, the exact form: `(Wert: 2026-03-31; schreibe: 31. März 2026)`,
  `(valeur : 0221234567 ; écris : 022 123 45 67)`. Dates, amounts, phone numbers,
  percentages, times, periods, identifiers and addresses get it; web and e-mail
  addresses are given as written. The repair prompt's text did not change; the
  rendered requests did, so the repair calls of a `--redo` run are fresh.
- **Clause recipes.** A LEN-02 or LEN-02-FR finding carries the rewrite recipe for its
  conjunction as the suggestion (docs/rules.md, `rules/recipes.py`), so the repair
  line reads "Vorschlag: Mach eine Frage und eine Antwort mit Dann ..." for a
  `wenn` clause. The idea is Zurich's, the wording ours.
- **Facts-only rounds** (7 October 2026). The repair loop stops when a
  round brings no progress on the whole; on the dev pairs that left must-keep values
  missing in 15 of 16 jobs, because a round that adds facts also gets new judge
  findings. After the loop, up to `pipeline.facts_rounds` (default 1) rounds ask for the
  missing facts alone, with no block flagged, and are measured by the FACT-01 count:
  they go on while a round adds a fact. The judge reruns as in any round with facts
  involved. A facts round asks for up to `pipeline.missing_per_facts_round` (10) missing
  facts, a repair round for 5 next to its flagged blocks; the cap was raised from 5 on
  the measured dev rerun of 7 October ("Fact-retention diagnosis" below). The final
  version is the one with the fewest must-keep values missing, then the fewest blocking
  findings. Set `pipeline.facts_rounds = 0` to measure the pipeline without them.
- **Repair records.** Every round stores what it asked for, the answer as given and
  every answered sentence code left out with its reason (a repeat, example content, a
  block the round had not flagged), under the version it produced. `eval diagnose`
  reads them to tell a fact the model never wrote from one it wrote in a form FACT-01
  rejects or one code dropped (below, "Fact-retention diagnosis").
- **Control tokens.** Servers that print special tokens (llama.cpp with `-sp`) also
  print `<|assistant_end|>`; the client strips every `<|...|>` token from answers.

## Tested so far

No CSCS key yet. The prompts were tested against Apertus v1.5 8B through llama.cpp on a
laptop GPU (RTX 4060 8 GB): the community text-only conversion
`Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF` (4-bit, unofficial, derived from
`andreasmartin/apertus-v1.5-8b-text`). Numbers from this setup are labelled as such and
never mixed with CSCS results.

First full run, on the team's sample letter (`src/leichtfacile/letters/`), 6 October 2026:

| Stage | Thinking | Output tokens | Time | Result |
|-------|----------|---------------|------|--------|
| understand | on | 3,291 | 90 s | Good fact sheet: core questions, 9 facts, a hard term, an omission; one invented segment id (caught by FACT-05). Code completion added 8 facts with exact values. |
| write | on | 12,408, then 11,451 | 24 min | The first answer hit `max_tokens` while still reasoning; the JSON repair round succeeded. The draft paraphrased the original: 50 percent passive, Amstad readability 45. |
| judge | on | 12,000 twice | 23 min | Both answers hit `max_tokens` while still reasoning: no JSON, the job failed. |
| write (repeat) | off | 754 | 28 s | Easy language: question headings, `Sie`, lists, 7.2 words per sentence, no passive. Dropped the income limits, which FACT-01 flags for repair. |

Consequences, all in the code now: writing without thinking by default, thinking per
stage configurable, a fallback without thinking when the reasoning runs out of tokens,
and jobs that survive a failing judge or repair round.

Second full run, thinking for understand only (judge on the same local 8B, without
thinking), 6 minutes in total:

| Draft | Blocks | Facts found by code | Passive | Words per sentence |
|-------|--------|---------------------|---------|--------------------|
| v1 (write) | 10 | 4 of 10 | 0 % | 8.8 |
| v2 (repair 1) | 15 | 6 of 10 | 0 % | 8.2 |
| v3 (repair 2) | 19 | 10 of 10 | 0 % | 9.4 |

The repair loop did what it is for: the writer had left out who is entitled and the
income limits; FACT-01 named the missing values, and two repair rounds put them back.
Runs through the web API of the container (the same image `make run` starts) were less
lucky: given eight flagged blocks and ten missing facts at once, the 4-bit model
rewrote the blocks without adding the facts, and the loop stopped after one round
without progress, leaving the missing facts as FACT-01 errors for the reviewer. Hence
version 3: blocking problems first, missing facts in small batches. The length of the
reasoning also varies a lot on this model: understand took 3,300 to 3,800 tokens in
most runs and more than 9,000 in one, where the fallback without thinking applies.
Prompt tuning continues on the official model at CSCS.
Two flaws remained for the reviewer: a sentence repeated by a repair (now filtered by
code) and an office name taken from a few-shot example (now prevented in the prompt;
the 8B judge did not catch it).

French, same setup, on the team's French letter
(`src/leichtfacile/letters/reduction-primes-lettre.txt`), 6 October 2026. Two runs: one
with the default thinking stages (understand and judge), one with thinking for
understand only.

| Draft | Facts found by code | Rule errors | Passive | Words per sentence |
|-------|---------------------|-------------|---------|--------------------|
| v1 (write), default run | 6 of 10 | 17 | 12.5 % | 9.5 |
| v3 (repair 2), default run | 10 of 10 | 11 | 5.3 % | 11.6 |
| v1 (write), understand only | 6 of 10 | 11 | 11.8 % | 8.7 |
| v3 (repair 2), understand only | 6 of 10 | 9 | 5.0 % | 8.9 |

The French prompts work on this model: the draft has question headings, talks to the
reader with `vous`, and keeps the deadline, phone number, e-mail and web address
exact; the writer left out the income limits, as in German. In the default run the
second repair round put them back by pasting the original 40-word legal sentence, which
LEN-01-FR flags as an error, so it stays visible. In the other run the second round
made no progress and the loop stopped. The judge with thinking ran to the 12,000-token
limit on three of four calls (10 to 15 minutes each) and answered through the fallback;
without thinking it called every fact present, although code found 4 missing, and
flagged most blocks for SEM-04. Code changes from these runs: a written sentence that
repeats an earlier one is dropped (the deadline came twice, under "Que devez-vous
faire ?" and "Jusqu'à quand ?"), an addition that repeats a later repaired block is
dropped, and the judge's findings on headings are not sent for repair (a repair had
turned the question heading into a statement).

### On the Public AI gateway (official Apertus 1.5 8B, no thinking)

P2 on the 12 dev pairs (10 German, 2 French), 6 October 2026, 70B judge without
thinking (the gateway ignores the switch). With prompt version 4, four of the ten
German drafts were the write prompt's JSON example word for word; the repair rounds
then patched dog-tax sentences with corrections. Version 5 of the write prompt and the
code guard against copied examples removed that. Means over the German pairs, version
4 against 5: invented blocks per 100 from 20.6 to 3.7, rule errors per 100 blocks from
5.1 to 2.3 (official texts: 1.6), warnings from 77 to 56 (official: 28), fact coverage
from 45 to 54 percent, hard facts kept from 55 to 61 percent (the official versions
keep 43), readability 55 (official: 64), about USD 0.006 and 60 seconds per page. All
12 pairs reached review; French: fact coverage 100 percent, no rule errors, readability
80 (official: 82).

Two weaknesses remain and decide the next prompt work. First, fact coverage: on the
fact-rich pages the writer leaves out half of the countable values, and the repair
round that should add them ends with "no progress" on 9 of 12 pairs. Second, values
from the examples leak into real drafts through the repair additions: the example's
phone number `031 987 65 43` (French: `032 987 65 43`) stood in 4 of the 12 final
drafts, the example's office in 3, in sentences the guard does not recognise because
they are rewritten ("Rufen Sie die DISG an: 031 987 65 43."). The judge did not flag
them. Since then rule FACT-06 (the mirror of FACT-01) flags every date, amount, phone
number, e-mail and web address, percentage and time (since 7 October also every
period, identifier and postal address) that is not in the source as an error and sends
the block to repair (with the source's only phone number, e-mail, web address,
identifier or address as the suggestion); the evaluation counts such values per 100
blocks by code, for every condition. On the stored dev drafts the rule found the examples' phone
numbers in 8 of 12 final drafts, the examples' `120 Franken` and `30. April 2026` in
3, and one e-mail address with a dropped letter (`gwaesserschutz@`), which the judge
had passed.

### On CSCS (official Apertus 1.5 8B and 70B, thinking for Understand and Judge)

The CSCS key arrived on 6 October 2026. The same three dev pairs as above, P2 with
the default thinking stages (`Apertus-v1.5-8B-thinking` for Understand, `-70B-thinking`
for the judge), against the gateway run without thinking:

| Pair | Fact coverage | Hard facts kept | Errors / 100 | Readability | Judge: present |
|------|---------------|-----------------|--------------|-------------|----------------|
| zh-blue-algae-de | 0.29 to 0.89 | 0.29 to 0.71 | 0.0 to 2.4 | 70 to 63 | 1.00 to 0.78 |
| zh-voting-de | 1.00 to 1.00 | 1.00 to 1.00 | 10.7 to 19.0 | 57 to 59 | 1.00 to 0.56 |
| lu-cost-approval-de | 0.00 to 1.00 | 0.00 to 0.71 | 0.0 to 0.0 | 70 to 37 | 0.30 to 0.71 |

Thinking earns its time where it matters: the fact sheets are better (the model finds
the values itself, so fewer facts come from code completion) and the drafts keep them:
fact coverage 0.43 to 0.96 and hard facts kept 0.43 to 0.81 on average. The price is
style: the drafts are longer and harder to read (readability 66 to 53, rule errors 3.6
to 7.1 and warnings 55 to 89 per 100 blocks), so the repair rounds have more to do. The
thinking judge reports distortions the no-thinking judge did not (7 to 22 percent of
the facts) and more unsupported blocks. A P2 job takes 45 to 90 seconds on CSCS, less
than the gateway needed without thinking. The thinking stages stay as they are for the
evaluation; the style gap is the repair loop's job. Two slips of the thinking 8B on long fact sheets showed up here:
a missing comma after a list and an object never closed before the next top-level key;
both are repaired in code now (`llm/json_out.py`).

### Repair guard: P2 on the dev pairs on CSCS (6 October 2026, late)

The 12 dev pairs again, P2 with thinking for Understand and the judge, repair prompt
version 6 and the guard against values the document does not contain; the LLM cache
was on, so the pairs already run on CSCS reused their fact sheets, drafts and judge
reports and only the repair rounds ran fresh.

- 11 of 12 pairs reached review. `be-pregnancy-counselling-de` failed three times in
  Understand on three different JSON slips of the thinking 8B (no JSON object at all,
  five validation errors, a missing comma), a fresh answer each time once unusable
  answers left the cache; it is the next candidate for the parser repairs.
- The guard fired 10 times in 33 repair calls, every time on values from the prompt's
  examples (`031 987 65 43`, `032 987 65 43`, `120`, `30. April 2026`, `8 h 00`,
  `11 h 30`) or on a value the model computed (`360`). Whenever the first answer was
  sent back, the second one was clean. One repair addition still carried an example
  value into a final draft: its first answer was invalid JSON and the second, with the
  value, was used (the guard never fails a round).
- 8 foreign values remain in 3 of the 11 final drafts: 6 come from the write stage,
  which the guard does not check (`sg-el-costs-de`: dog-tax sentences in paraphrase,
  only 2 of 12 sentences verbatim and so below the copy guard's threshold;
  `bwl-emergency-supplies-fr`: the example's contact block), 2 from the fallback above.
- German means over the 9 completed pairs: fact coverage 61 percent, hard facts kept
  61 percent, invented values 2.1 per 100 blocks (all in `sg-el-costs-de`), rule errors
  2.8 per 100 blocks, 1.9 repair rounds, 82 seconds per job. The judge's numbers are
  not comparable with the gateway run: the thinking judge reports 10.7 unsupported
  blocks per 100 against 3.7 without thinking.

The remaining leak is the write stage's paraphrased example content. Two candidate
fixes: the copy guard also counts sentences with the examples' topic words (`Hund`,
`Hunde·steuer`, `Impfausweis`, `contrôle des habitants`) that the source does not
contain, or the write stage gets the same soft check for foreign values at the price of
a second write call when it fires.

### Full evaluation on CSCS (6 October 2026)

The evaluation commands ([quickstart.md](quickstart.md#the-evaluation)) into
`eval/results-cscs`: P0, P1 and P2 on the 23 held-out pairs (20
German, 3 French), thinking for Understand and the judge, then P2 with the 70B writer
on the first 5 German pairs. 23 of 23 pairs completed under every condition after the
reruns of failed pairs (the harness reruns them with the cache on, and unusable answers
no longer stay cached). The first pass had failed 7 P0 scorings, 9 P1 and 6 P2 jobs,
every one on an answer shape the code now handles: core answers written as bare
sentences, an omission or glossary entry written as a block of that kind, an empty
block, a list closed with a brace, and 8 write answers cut off at the token limit on
pages of 65 to 185 sentences, which are now written again as two halves. The server cut
31 of about 350 streams; the client retried them all.

German means over 20 pairs, 8B writer:

| Setup | Fact coverage | Hard facts kept | Invented values / 100 | Judge: unsupported / 100 | Errors / 100 | Readability | SARI |
|-------|---------------|-----------------|-----------------------|--------------------------|--------------|-------------|------|
| REF | - | 70 % | 2.2 | - | 2.7 | 62 | - |
| P0 | 93 % | 100 % | 0.0 | - | 22.0 | 50 | 44.5 |
| P1 | 72 % | 69 % | 3.2 | - | 9.9 | 50 | 38.8 |
| P2 | 84 % | 80 % | 0.1 | 6.9 | 4.3 | 51 | 40.6 |
| P2, 70B writer (5 pairs) | 68 % | 71 % | 0.7 | 6.0 | 2.0 | 58 | 42.2 |

P0's fact coverage read 98 percent in this run's first scoring: the 13 pairs scored
before any P1 or P2 job existed were measured against a fact sheet without code
completion (fewer facts). The scoring now completes that sheet as the pipeline does,
and the rescoring from the cache against the stored P2 sheets (6 October, evening)
gives 93 percent; no other P0 number changed.

What the run says about the prompts and guards: the P1 drafts carried 3.2 invented
values per 100 blocks, nearly all the examples' phone number, date and hours in
sentences without a topic word; the example-value rule (above) brought P2 down to 0.1,
two office hours on one page. The judge flags 6.9 unsupported blocks per 100 in P2
(9 percent distorted facts on the fact-rich pairs), which is what the hand labelling
(`eval sample`) has to check. Every P2 job stopped with "a repair round brought no
progress" after 1.8 rounds on average: the repair prompt is the next lever for fact
coverage. The 70B writes cleaner (2.0 errors, readability 58) but keeps fewer facts.

### The three model tiers on the eval split (CSCS, 6 October 2026)

P2 on the 23 held-out pairs (20 German, 3 French) in three settings: the 8B writer
(the default: the 8B for Understand, Write and Repair), every stage on the 70B
(`--writer swiss-ai/Apertus-v1.5-70B`) and the hybrid with the 70B for Understand
only (`--understand swiss-ai/Apertus-v1.5-70B`, in production `llm.models.understand`).
The judge is the 70B-thinking in all three. The hybrid's fact sheets came from the
cache of the 70B run, so the hybrid and the 70B run score against the same sheets.
German means over the 20 pairs (`eval run --condition P2` with each of the two flags
reproduces the two extra runs, [quickstart.md](quickstart.md#the-evaluation)):

| Setup | Fact coverage | Hard facts kept | Errors / 100 | Warnings / 100 | Readability | Unsupported / 100 | Invented values / 100 | Words | USD / page |
|-------|---------------|-----------------|--------------|----------------|-------------|-------------------|-----------------------|-------|------------|
| 8B writer (default) | 84 % | 80 % | 4.3 | 58 | 51 | 6.9 | 0.1 | 245 | 0.0105 |
| 70B everywhere | 78 % | 75 % | 1.4 | 41 | 58 | 4.7 | 0.3 | 209 | 0.0191 |
| Hybrid: 70B reads, 8B writes | 66 % | 65 % | 2.1 | 50 | 54 | 6.2 | 0.6 | 203 | 0.0103 |

- **The 70B writes cleaner easy language and keeps fewer facts.** A third of the rule
  errors, fewer warnings, readability 58 against 51 (the official versions: 62), and
  the judge reports fewer unsupported blocks and fewer distorted facts (2.6 against 8.6
  percent), though in that run the judge grades its own model's drafts. Fact coverage
  78 against 84 percent, hard facts kept 75 against 80 (on the 14 fact-rich pairs 66
  against 73), and shorter texts (209 against 245 words). The first 5 pairs had
  suggested the opposite on facts (68 against 57 percent coverage); the full set turned
  it around, so the 5-pair numbers in earlier notes are superseded.
- **Price and speed.** USD 0.019 against 0.011 per page at Public AI list prices, 1.8
  times rather than the 3 times the token prices suggest, because the 70B needs fewer
  tokens: it reasons a third as much in Understand (1,400 against 4,200 output tokens
  per job) and its repair rounds are shorter. It generates at about 68 tokens per
  second against 155 for the 8B, but the Understand call takes 19 s against 92 s and
  the Write call 27 s against 10 s; summed over the mean fresh call times per stage, a
  P2 job is about 85 s on the 70B and about 150 s on the 8B, because the 8B-thinking's
  reasoning in Understand dominates. The seconds per page in docs/evaluation.md undercount
  all runs, because cached calls count as 0 s (the 8B run reused 76 percent of its
  Understand calls from the cache, the hybrid all of them).
- **The hybrid is the worst of the three on facts** (66 percent coverage, 65 percent of
  the hard facts) although it scores against the same, richer fact sheets as the 70B
  run (7.2 checkable facts per pair against 6.2 in the 8B's own sheets), and hard facts
  kept, which needs no fact sheet, drops too. The 8B writer handles the 70B's fact
  sheets worse than its own: four German drafts collapsed to under 50 words
  (`zh-municipalities-de` 38, `be-education-de` 25, `bs-tax-deductions-de` 30,
  `zh-political-rights-de` 44) and others ballooned (`zh-accessibility-statement-de`
  991 words against 345; the French `ne-disability-petitions-fr` 2,520 against 659, with
  24 rule errors per 100 blocks over the 3 French pairs). Its call times (Write 22 s,
  Repair 15 s) were slower than in the 8B run; the endpoint was shared with other runs
  at the time, so they are not compared. The setting stays available but is not
  recommended; the next prompt work for it would be to shorten the fact texts the
  write prompt shows, which the 70B writes longer.
- **French (3 pairs).** The 70B keeps fewer facts (56 against 73 percent coverage) and
  writes much shorter texts (154 against 400 words) at readability 83 (official: 85);
  the hybrid keeps the most hard facts (78 percent) but at 1,160 words a page.

Decision: the default stays the 8B writer with the 70B judge. `llm.models.writer` set to the
70B is the quality tier for style at about twice the price and, on-premise, four GPUs
instead of one; the hybrid is documented as tested and not better.

### Zurich's prompt as the second baseline (CSCS, 6 October 2026)

P0-ZH (`baseline_zh.md`, both variants) and P0 on the 20 German eval pairs and the 10
German dev pairs, 8B without thinking, scored against the same fact sheets as P1 and P2
(the stored P2 job of each pair). All 90 jobs reached review in about two minutes per
30 jobs; every answer carried the `<leichtesprache>` tags. Means over pairs:

| Split | Setup | Fact coverage | Hard facts kept | Errors / 100 | Warnings / 100 | Words / sentence | Readability | SARI | Invented values / 100 | Tokens / page |
|---|---|---|---|---|---|---|---|---|---|---|
| eval (20) | P0 | 93 % | 100 % | 22.0 | 95.0 | 7.7 | 50 | 44.5 | 0.0 | 982 |
| eval (20) | P0-ZH complete | 91 % | 95 % | 15.4 | 85.6 | 6.8 | 47 | 43.2 | 0.0 | 2374 |
| eval (20) | P0-ZH default | 75 % | 77 % | 8.7 | 74.7 | 6.1 | 48 | 41.7 | 0.0 | 2199 |
| eval (20) | P2, 8B | 84 % | 80 % | 4.3 | 58.4 | 6.8 | 51 | 40.6 | 0.1 | 21711 |
| dev (10) | P0 | 74 % | 83 % | 26.1 | 108.0 | 8.3 | 49 | 42.0 | 0.0 | 936 |
| dev (10) | P0-ZH complete | 75 % | 87 % | 26.2 | 114.0 | 8.3 | 43 | 39.8 | 0.0 | 1979 |
| dev (10) | P0-ZH default | 74 % | 81 % | 13.0 | 94.4 | 6.6 | 47 | 41.2 | 0.1 | 1861 |
| dev (9 of 10) | P2, 8B, run of 6 Oct afternoon | 61 % | 61 % | 2.8 | 57.3 | 6.8 | 52 | 40.5 | 2.1 | 18235 |

- **Zurich's complete prompt beats our one-sentence P0 on every quality column** and
  keeps slightly fewer facts (95 against 100 percent of the hard facts): it is the
  fairer baseline, and the strawman objection to P0 is answered.
- **Against P2 on the eval split:** P2 has a quarter of the rule errors (4.3 against
  15.4), fewer warnings, the same sentence length and better readability; the complete
  prompt keeps more facts (91 against 84 percent coverage, 95 against 80 percent of the
  hard facts; on the 14 fact-rich pairs 93 against 73, the official versions 60). By
  the rules for the headline numbers this was case B on 6 October: lead with "no
  silent loss" and state the coverage gap openly; the fact-retention diagnosis
  was the next step. The final run of 10 October gives case A ("The final run on the
  eval split", below).
- **The default variant for Leichte Sprache drops a quarter of the
  hard facts** (77 percent kept, 69 on the fact-rich pairs) and nobody is told. That is
  the silent loss in numbers.
- **Neither baseline invents values** on these pages (0.0 per 100 blocks). The invented
  values of P1 and P2 were mostly values from our own prompt examples (above), which the
  code guards now catch.
- **Cost.** The Zurich prompt costs 2.4 times the tokens of P0 (its rules are about
  1,900 input tokens per call) and still a hundredth of P2.
- **Dev split.** The dev pages are harder (the official versions keep 43 percent of
  the hard facts); the single prompts keep 81 to 87 percent. The stored P2 dev rows are
  from the run of 6 October afternoon, before the FACT-06 and example-value guards (9 of
  10 pairs), and are rerun with `--redo` after the Friday prompt work.

The headline sentence that follows from case B is the owner's decision.

### Mediopunkt by code: P2 on the dev pairs on CSCS (6 October 2026, night)

The 10 German dev pairs under P2 twice, once without the step (`apply_mediopunkt`
replaced by a no-op, results in `eval/results-cscs-nomp`) and once with it
(`eval/results-cscs`, `--redo`; the rows before it are kept in `eval/results-cscs-v2`).
The second run started after the first had finished, so both replayed the same
Understand and Write answers from the LLM cache and started from the same write answer;
the judge and repair calls ran fresh on both sides (the judge sees the split text).
All 10 pairs reached review on both sides, `be-pregnancy-counselling-de` included.

Two pairs are left out of the comparison. `zh-oral-health-de`: its cached Understand
answer failed to parse in the first run and was dropped from the cache, as designed, so
the second run started from a different fact sheet. `sg-el-costs-de`: its write answer
has 3 blocks; with the step, the judge flagged 39 problems after the first repair round
instead of 24, the loop stopped and kept the 3-block version (judge noise and the
choice of the best version, not the split). With it, the rule errors would read 8.5
against 3.3 per 100 blocks, all of it from that one pair.

Means over the other 8 pairs, final version:

| | Without the step | With the step |
|---|---|---|
| LEX-01 warnings / 100 blocks | 34.7 | 4.8 |
| All warnings / 100 blocks | 78.8 | 51.0 |
| Rule errors / 100 blocks | 4.3 | 3.7 |
| Words split by code / 100 blocks | 0 | 33.6 |
| Repair rounds | 1.75 | 2.0 |
| Rounds with only warnings left | 0 | 0 |
| Fact coverage | 69 % | 73 % |
| Hard facts kept | 68 % | 79 % |
| Readability | 48.2 | 48.4 |

- **The step does what it should.** LEX-01 falls from 35 to 5 warnings per 100 blocks,
  the same as the rescoring of the stored drafts (change log, below). The 11 warnings
  left in the 10 final drafts are there by design: adjectives (`selbstbestimmtes`, `handschriftlich`,
  `Weiterführende`), street names in front of a house number and the truncated
  `Familienplanungs-`. The errors are the same rules on both sides (LEN-01, GRAM-01).
- **It saves no repair round, and cannot on these pages.** No job on either side ever
  reached zero blocking problems, so the round that sends the warnings (LEX-01 among
  them) never ran; 15 of 16 jobs stopped on "no progress" with missing or distorted
  facts and judge findings left. The rounds are bounded by the facts, not by the style.
- **It costs no facts.** The first write answer of each pair, split and unsplit, gives
  the same fact coverage and the same values (kind, canonical form, text) on all 10
  pairs. The differences in the table come from the fresh judge and repair calls, the
  run-to-run noise of the loop; they are no effect of the step.
- **Seconds per job** read 22 against 38 only because the first run replayed 14 judge
  calls from the cache and the second 4.
- **The 53 distinct words split by code, read by hand:** 48 right, 5 wrong joints.
  `Assistent·innen` and `Schweizer·innen` split off the feminine ending, which reads as
  gender typography; fixed: the splitter treats `-innen` as an ending when the rest is
  a word, splits only that stem (`Sozial·arbeiterinnen`) and leaves `Schweizerinnen`
  alone, while `Dach·rinnen` stays a compound; a word long only by its ending
  (`Steuerberaterinnen`) is not split, because the short stem invites wrong joints
  (`Schrei·berinnen`). `Kostengut·sprache` (known, above),
  `Kostenvoran·schlag` and `Leistungser·bringende` stay: `Voranschlag` and
  `erbringende` are too rare in the word list to count as parts. The stored drafts
  keep the old splits; the final run uses the fixed splitter.
- **The evaluation's count was too low.** Each version records only the edits made on
  it, and a repair round keeps the dot it is given, so counting the final version's
  edits gave 10 words per 100 blocks instead of 33.6. The evaluation now counts the
  edits of every version up to the final one whose word the final version still has
  (`eval.score.kept_code_splits`).

The full dev split under P2 with the step (10 of 10 pairs): fact coverage 58 percent,
hard facts kept 63 percent, 3.0 rule errors and 47.5 warnings per 100 blocks, no
invented values.

### Fact-retention diagnosis: the method (7 October 2026, night)

Why does P2 keep fewer facts than Zurich's complete prompt (84 against 91 percent fact
coverage on the eval split)? `python -m leichtfacile eval diagnose --results
eval/results-cscs --role dev` answers it without a model call, from the stored
artifacts of the P2 jobs: every must-keep fact with a value that FACT-01 does not find
in the final version goes into one bucket.

| Bucket | Meaning | How the tool decides |
|---|---|---|
| a | never asked for in any round | the requests of each round, from the repair record or recomputed with `build_request` from the stored findings; the reason apart: behind the cap of missing facts per round (5 in a repair round, `pipeline.missing_per_facts_round` in a facts round), no round ran at all (the loop stopped or failed before one), or never flagged by FACT-01 when the job ran |
| b | asked for and written, but in a form FACT-01 rejects | the record's answer carries the fact's digits or words, but no value the matcher accepts |
| c | asked for and written, then dropped by code | the answered sentence is in the record's dropped list (a repeat, example content, a block the round had not flagged) |
| d | asked for, and the model did not write it | no answered sentence for the fact, nothing loose either |
| k | asked for and written into a version that was not kept as final | the value is in a later version than the final one; the final version is the one with the fewest blocking findings, so a round's gains are lost when the judge flags its new sentences (a fact asked for in such a round and not written is b, c or d, with the reason saying which version is final) |
| l | present in an earlier version, lost in a later rewrite | the value is in a version before the final one and gone after a round, by the model's rewrite or by code |
| x | asked for, answer not recorded | jobs run before the repair record existed (every run before 7 October 2026, night): b, c and d cannot be told apart for them |
| e | background facts whose value is not in the final text | listed for reading, not counted: whether the reader needed a fact Understand or code completion marked droppable is a reading decision |

Run on the owner's machine on 7 October 2026 against `eval/results-cscs` (CSCS, 8B
writer, 70B judge), first on the stored dev jobs of 6 October, then after the dev rerun
with `--redo` under the code of 7 October (facts-only rounds, the exact form in the
request, the repair record). The first run's rows are kept in `eval/results-cscs-v3`.

| Bucket | Stored run of 6 Oct (12 jobs) | Rerun of 7 Oct (12 jobs) |
|---|---|---|
| Checkable must-keep facts | 102 | 122 |
| Missing in the final versions | 50 (51 % found) | 16 (87 % found) |
| a: never asked for, behind the cap of 5 per round | 10 | 2 |
| a: never asked for, no repair round reached the final version | 30 | 9 |
| a: never asked for, never flagged by FACT-01 | 0 | 0 |
| b: written in a form FACT-01 rejects | 0 | 2 |
| c: written, then dropped by code | 0 | 1 |
| d: asked for, not written | 0 | 1 |
| l: present once, lost in a later rewrite | 0 | 0 |
| x: asked for, answer not recorded | 10 | 1 |
| e: background facts whose value is not in the text (for reading) | 7 | 8 |
| Facts without a value the judge calls missing or distorted | 23 | 6 |
| Jobs with a record for every round into the final version | 3 of 12 | 11 of 12 |

Reading it: four of five lost facts in the stored run were never asked for, most of
them because no round that led to the final version asked for anything (the loop had
stopped on "no progress" or a later version was not kept), the rest behind the cap.
That is the bucket the facts-only rounds address, and the rerun shows it: 16 missing
instead of 50, on more checkable facts (122 instead of 102, because the rerun's fact
sheets were completed by the code of 7 October, which knows periods, identifiers and
addresses; the Understand answers came from the cache). What is left is small and
spread: 9 facts in jobs where no round reached the final version (the next reading
decision: whether the final-version choice by blocking count throws a facts round's
version away when the judge flags its new sentences), 2 behind the cap, 2 written in a
form the matcher rejects, 1 dropped by code, 1 not written. The two French pairs were
not rerun.

The ablation on the 10 German dev pairs, the same cached Understand and Write answers
on both sides (`eval/results-cscs` with the facts rounds, `eval/results-cscs-nofacts`
with `pipeline.facts_rounds = 0`, run in sequence):

| Setup | Fact coverage | Hard facts kept | Silent losses | Invented values / 100 | Judge: unsupported / 100 | Errors / 100 | Tokens / page | USD / page |
|---|---|---|---|---|---|---|---|---|
| P2, facts rounds on (default) | 75 % | 72 % | 5 % | 0.0 | 3.6 | 7.3 | 22,570 | 0.0121 |
| P2, facts rounds off | 68 % | 65 % | 5 % | 0.0 | 4.3 | 8.2 | 19,197 | 0.0097 |
| P0 (stored rows of 6 Oct) | 74 % | 83 % | - | 0.0 | - | 26.1 | 936 | 0.0001 |
| Official easy-language version | - | 37 % | 63 % | 3.5 | - | 1.6 | - | - |

The facts rounds add 7 points of fact coverage and 7 points of hard facts kept (on the
9 fact-rich pairs 80 against 72 percent kept, 83 against 76 coverage) at about 3,400
more tokens per page, with no invented value on either side and fewer judge findings
and rule errors: the round's additions are clean. They stay on for the final run. The
"seconds per page" of the ablation's second side read 0.1 only because nearly every
call came from the cache. Two things the run flagged: the P2 rows show 5 percent silent
losses, where the note in [evaluation.md](evaluation.md) promises zero by design,
so the code completion misses some hard value (the row's `silent_loss_kinds` names the kinds;
to be read next); and two Write calls were cut off at 8,000 tokens on pages of 95 and
88 sentences and written as halves, as designed.

The second reading, the same day, with the kinds and the reason strings of the local
file: the silent losses were three percentages and one address, and both were gaps of
the code completion, now closed. A completed percentage was stored as the bare number
(`4.5`), which parses back as a plain number and never matched the percentage in a
draft again, so FACT-01 counted it as missing even when the draft had `4,5 Prozent`;
it is stored as `4.5%` now, the form the Understand prompt asks for. An address over
two source sentences (`Gerichtsstrasse 12` and `8000 Musterwil` on separate lines) was
completed from the second sentence alone, without its street; the completion now takes
the values from the document text as the evaluation does, with segment offsets, so the
fact cites both sentences and FACT-01 asks for the street. The nine facts in jobs
where no round led to the final version were all asked for in a round whose version
was not kept: six in a facts round that brought no progress, three in a repair round,
with v1 final in each case. The diagnosis now reads such facts off the later rounds
(bucket k when the value is in a version not kept, else b, c or d with the reason
naming the final version), so the next run shows whether the model did not write them
or the final-version choice threw them away.

The third run, the same day, under the fixed completion (`--redo` again; the rows
before it are kept in `eval/results-cscs-v4`): 30 of 122 must-keep values missing (75
percent found), fact coverage 71 percent, hard facts kept 68, silent losses 2 percent,
invented values 0.0, 7.5 rule errors per 100 blocks. The buckets: 13 behind the cap,
2 written in a rejected form, 1 dropped by code, 4 not written, **5 written into a
version that was not kept as final**, 1 lost in a rewrite, 4 not recorded. Three
readings:

- *Run-to-run noise is large on single pairs.* One pair (`sg-el-costs-de`, 22
  checkable facts) accounts for most of the difference to the run before: 18 missing
  against 2, with v3 of 4 final instead of v5 of 5; 13 of its facts were behind the
  cap, 3 were written by the facts round into a v4 the final-version rule did not
  keep. Another pair lost its repair round to two unusable answers and, by the rule of
  the day, its facts round with it. The judge and repair calls are fresh on every
  `--redo` while Understand and Write replay from the cache, so two runs differ by
  the loop alone.
- *The final-version rule discarded facts.* The 5 facts of bucket k were in the draft
  the facts round produced; the version with the fewest blocking findings won because
  the judge flagged the new sentences or they carried a rule error. Since 8 October the
  final version is the one with the fewest must-keep values missing, then the fewest
  blocking findings (`version_key` in the orchestrator), and `eval rescore --select
  facts|blocking` scores the stored jobs under either rule without a model call, so
  the rule's effect is read on the same jobs. An answer the code could not use no
  longer cancels the facts round; only a failed endpoint does.
- *The last silent loss is a completion asymmetry, closed.* One address: the model's
  fact carried the place alone, which counted as covering the full address, while the
  reader who searches the fact sheet for the full address does not find it. Coverage
  is now asked in the reader's direction, so the full value gets its own fact next to
  the model's partial one (the same for a bare number against a quantity).

The rule change, read on the same jobs with `eval rescore` (no model call), German dev
pairs, P2:

| Jobs | Final version by | Fact coverage | Hard facts kept | Silent losses | Invented values / 100 | Judge: unsupported / 100 | Errors / 100 |
|---|---|---|---|---|---|---|---|
| Third run | blocking findings (the rule until 7 Oct) | 71 % | 68 % | 2 % | 0.0 | 4.9 | 7.5 |
| Third run | missing facts first (since 8 Oct) | 80 % | 81 % | 2 % | 0.0 | 6.1 | 8.8 |
| Second run | missing facts first | 83 % | 84 % | 5 % | 0.0 | 5.2 | 7.1 |

The "blocking" rescore reproduces the third run's row to the decimal, which also
checks the rescoring itself. Facts first gains 9 points of fact coverage and 13 of
hard facts kept on the same drafts, for 1.2 more judge findings and 1.3 more rule
errors per 100 blocks: the sentences a facts round adds are the ones the judge then
flags. The silent losses do not move with the rule, as they should not: they are a
property of the fact sheet stored when the job ran, and the completion fixes show
only in the next run. The cap of a facts-only round is a setting now
(`pipeline.missing_per_facts_round`, default 5): the one experiment left for the dev split
before the freeze.

The fifth run, the same day, under the final code (facts first, the fixed completion;
`--redo`, the rows before it kept in `eval/results-cscs-v5`), then the cap experiment
in a fresh folder `eval/results-cscs-cap10` with `pipeline.missing_per_facts_round = 10`, run
after it on the same cache, so both replay the same Understand and Write answers and
the cap-10 run made only 4 fresh calls. German dev pairs, P2:

| Run | Fact coverage | Hard facts kept | Silent losses | Invented values / 100 | Judge: unsupported / 100 | Errors / 100 | Tokens / page | USD / page |
|---|---|---|---|---|---|---|---|---|
| Fifth run, cap 5 | 75 % | 77 % | 0 % | 0.0 | 4.6 | 5.4 | 21,786 | 0.0117 |
| Cap 10 | 79 % | 81 % | 0 % | 0.0 | 2.8 | 6.7 | 21,697 | 0.0117 |

| Bucket | Fifth run, cap 5 (12 jobs) | Cap 10 (10 German jobs) |
|---|---|---|
| Checkable must-keep facts | 123 | 110 |
| Missing in the final versions | 27 (78 % found) | 15 (86 % found) |
| a: never asked for, behind the cap | 13 | 7 |
| a: no round ran, or never flagged by FACT-01 | 0 | 0 |
| b: written in a form FACT-01 rejects | 1 | 1 |
| c: written, then dropped by code | 2 | 5 |
| d: asked for, not written | 7 | 2 |
| k: written into a version not kept as final | 0 | 0 |
| l: present once, lost in a later rewrite | 0 | 0 |
| x: asked for, answer not recorded (the two French jobs, not rerun) | 4 | 0 |
| e: background facts whose value is not in the text (for reading) | 9 | 9 |
| Facts without a value the judge calls missing or distorted | 9 | 6 |

The fifth run closes the two open points: no silent loss (the completion fixes hold)
and no fact written into a version that was not kept (the facts-first rule holds).
What is left is mostly the cap, 13 of 27 missing facts, all in `sg-el-costs-de` (22
checkable facts). With cap 10 that pair goes from 15 missing facts to 7, and the means
over the ten pairs move by 4 points of fact coverage and 4 of hard facts kept, with no
invented value and fewer judge findings (2.8 against 4.6 per 100 blocks), at 1.3 more
rule errors per 100 blocks. That passes the decision rule set before the run (coverage
up by 3 points or more, invented values not up, judge findings up by less than 2), so
the default is 10 since this run. The gain comes from one pair; the
other nine keep the same number of missing facts. The 4 fresh calls were the facts
round and its judge in `sg-el-costs-de` and in `zg-disability-services-act-de`; the
second asked for the same 4 facts under both caps, so its fresh answer is a cache miss,
not the cap: the same 4 facts stay missing, read as dropped by code (c) in the cap-10
run and as not written (d) in the fifth.

### Image input spike (CSCS, 8B, 7 October 2026): no-go at this setting

`scripts/image_spike.py` (removed with the no-go on 25 October 2026, in the history up
to commit b948426; docs/image-input.md) on the two scanned letters of
`data/examples/print/scans/`, long side 1,600 pixels, the 8B without thinking,
temperature 0:

| Capture | Pages | Character error rate | Hard values found | Seconds |
|---|---|---|---|---|
| steuermahnung-brief_scan (German, 1 page) | 1 | 0.996 | 0 of 21 | 0.9 |
| bourse-etudes-decision_scan (French, 2 pages) | 2 | 0.057 | 14 of 22 | 8.0 |

The German page came back as `unlesbar` in four tokens: the model declined the page
rather than misreading it, so every value of the tax reminder is lost (the IBAN, the
amount, six dates, four times, two phone numbers, the percentage, the period, the
address). The French letter was read, with 5.7 percent of the characters wrong, and the
digits are where the errors sit: the AVS number `756.4719.2083.50` came back as
`763.4713.2063.50`, the IBAN with wrong digits, the postcode 1999 as 1399, one payment
date, the phone number, the e-mail and the web address are lost. The go/no-go rule set
before the spike says stop: an image ingest at this setting would feed the fact contract
wrong numbers that look right.

The two variants, the same day, at full resolution (2,480 pixels):

| Model | Capture | Character error rate | Hard values found | Seconds per page |
|---|---|---|---|---|
| 8B | steuermahnung-brief_scan | 0.060 | 15 of 21 | 5.3 |
| 8B | bourse-etudes-decision_scan | 0.044 | 12 of 22 | 5.3, 3.2 |
| 70B | steuermahnung-brief_scan | 0.118 | 17 of 21 | 12.6 |
| 70B | bourse-etudes-decision_scan | 0.041 | 13 of 22 | 12.1, 7.6 |

At full size the 8B reads the German page it had declined at 1,600 pixels, and both
models read most of the text; what they get wrong are digits, and they get them wrong
in ways that look right. The German IBAN `CH00 0839 4100 2786 5310 4` came back as
`CH00 0839 4100 2756 3510 4` from the 8B and `CH00 0999 4100 2736 5510 4` from the
70B; the French IBAN with two digits swapped on both; the AVS number
`756.4719.2083.50` as `756.4716.2088.50` from the 70B; the 78-day period as `76 Tage`
from both; an amount, an address, e-mail addresses and a payment date are lost as
well. The 70B finds a few more values, has the higher character error rate on the
German page and takes 2 to 2.5 times as long. Decision: a transcription that
turns an IBAN into another plausible IBAN cannot feed a fact contract whose point is
that such numbers survive exactly; image input stays future work.

### Image input spike, continued (CSCS, 9 October 2026): strips at the scan's resolution

Where the digits go: a probe of one page at many sizes showed that the server keeps
at most about 7,900 prompt tokens of an image, from 2,000 pixels on the long side
upward, JPEG or PNG alike (448 px: 666 tokens; 1,200 px: 4,128; 1,600 px: 7,279;
2,000 to 4,000 px: 7,879). That is the Apertus 1.5 image tokenizer as described
publicly: one discrete code per 16 x 16 pixel patch, the area clamped to 1400 x 1400
pixels. So a whole A4 page scanned at 300 dpi is read at about 140 dpi, where a digit
is a patch or two, and the 1,600 px setting of 7 October was not downscaled at all.
`scripts/image_spike.py --strips` therefore cuts the page's printed area (the rows
and columns with ink, the scanner's edge left out) at blank rows into horizontal
strips of under 1.9 million pixels each, which the server keeps as they are: five
calls per A4 page, about 1.5 s each on the 8B, about four times the input tokens of a
whole page. The script's report names, for every lost hard value, what the
transcription has in its place. All runs without thinking, temperature 0, the response cache off; the
whole page is the full scan as on 7 October.

| Setting | Model | steuermahnung-brief (21 values) | bourse-etudes-decision (22 values) | Seconds per capture |
|---|---|---|---|---|
| Whole page, two runs | 8B | 16 of 21; CER 0.059, 0.059 | 11 of 22; CER 0.039, 0.064 | 6, 5; 9, 7 |
| Printed area whole, one call per page | 8B | 17 of 21; CER 0.049 | 15 of 22; CER 0.086 | 6; 8 |
| Strips, three runs | 8B | 20 of 21; CER 0.011, 0.0095, 0.0095 | 17 of 22; CER 0.018, 0.018, 0.022 | 8, 6, 8; 13, 9, 13 |
| Strips, grayscale with autocontrast | 8B | 16 of 21; CER 0.119 | 16 of 22; CER 0.026 | 8; 13 |
| Strips, upscaled 1.5 x (twice the calls) | 8B | 20 of 21; CER 0.035 | 19 of 22; CER 0.096 | 12; 20 |
| Strips | 70B | 17 of 21; CER 0.091 | 18 of 22; CER 0.024 | 15; 24 |

Whole page: the same kind of loss as on 7 October, and not the same digits twice. The
German IBAN `CH00 0839 4100 2786 5310 4` came back as `CH00 0830 4100 2786 3510 4` in
both runs today (7 October: `... 2756 3510 4`), the AVS number `756.4719.2083.50` as
`755 4716 2083 50` and `733.4716.2083.50`, the file number `BE-2026-04187` as `04137`,
the postcode 1999 as 1899 and 1889, the 78-day period as `76 Tage`, the direct line
`022 123 45 68` as `45 69`. The printed area alone, one call per page, gains a little
(the page arrives at about 160 dpi) and still turns the IBAN into `2788 9310`.

Strips on the 8B: every digit of both letters right in all three runs, the IBANs, the
AVS number, the tax number, the file number, the amounts, the dates, the times, the
phone numbers, the period. What is still lost are words the model knows better: the
invented place name `Exempleville` comes back as `Exampleville` in the address, in
both e-mail addresses and in the web address (so the two address values, the two
e-mails and the URL count as lost), and the German footer's small gray
`www.musterwil.example` as `mustervil` (the running text's Musterwil is right). In
the running text `Gemeindesteuern` is read as `Gemeindefteuern` (a long s) in every
run. The three runs differ in line breaks and one word (`Begründen`, `Gründen`):
temperature 0 is close to deterministic on strips, while the whole-page runs differ
in their digits. Blank strips (the empty lower half of the French page 2) come back
as `illisible`, as the prompt asks.

The other variants, each one run: in grayscale with autocontrast the 8B declined the
first German strip (the header with the logo, `unlesbar`) and lost the sender block.
Upscaling the strips 1.5 x before cutting (ten strips per page) gained no digit and
added small errors elsewhere. The 70B on strips dropped the paragraph with the
opening hours (four times lost), wrote the AVS number as `756.4719.2088.50` and the
French IBAN with a hyphen, and took twice as long: the 8B is the better reader here.

What it means for the decision of 7 October: the digit loss was mostly the resolution,
not the model's reading. In strips the 8B keeps every hard value with digits in both scans; it does
not keep every hard value, because an e-mail address or a URL with an unfamiliar word
is normalised to a familiar one, which the go/no-go rule counts as lost. Phone
photos, the open question of the spike, are still untested. The decision stands (image
input as future work); a future ingest sends strips under the clamp, never a whole page,
and checks e-mail addresses and URLs separately. Results in
`eval/results/image_spike_strips.json` (the committed script) and the variants'
files next to it, git-ignored; the variants' code was not kept. The write-up for the
Apertus community, by kind of value: `docs/image-input.md`.

### Vocabulary in the pipeline: P2 on the dev pairs on CSCS (7 October 2026)

Three runs of P2 on the 12 dev pairs (10 German, 2 French) with the settings of the day
(8B writer, 70B judge, thinking for Understand and Judge, 3 repair rounds, 1 facts round
of up to 10 facts): without the vocabulary (`pipeline.vocabulary = false`), with all of it
including the word list in the write prompt (a setting of that day, removed since),
and with all of it
but the word list, the default since. The Understand prompt did not change, so the three
runs got the same Understand answers from the response cache; their fact sheets differ
only by what code added. Write, judge and repair calls are fresh, one run per setting.
One job failed on the side without the vocabulary (`sg-el-costs-de`: the 8B copied the
prompt's JSON example twice) and was run again. The run with the list started before two
fixes of the matcher (the lemma of a noun no longer stands for a verb: `recourir` is no
`recourant`; `dès lors` is no `dès`); all rows were scored again with the final code
(`eval rescore`), so one checker measures all three. Results in
`eval/results-cscs-vocab-off`, `-on` and `-nolist`, each with its `-rescored-facts`.

| Mean of the 12 pairs | without | with the list | default (no list) |
|---|---|---|---|
| Hard terms used without a glossary entry, per draft | 2.3 | 1.0 | 0.1 |
| Glossary entries per draft (added by code) | 4.4 (0) | 7.4 (1.9) | 7.1 (1.6) |
| Glossary entries whose explanation breaks a rule | 38 of 53 (72%) | 40 of 89 (45%) | 42 of 85 (49%) |
| Fact sheet hard terms with the vocabulary's explanation | 0 of 82 | 45 of 114 | 45 of 114 |
| Office words in the first drafts (sum) | 33 | 58 | 20 |
| Office words in the final drafts (sum) | 46 | 37 | 42 |
| Office words per 100 blocks, final drafts (median) | 7.1 | 4.2 | 7.0 |
| Fact coverage | 0.74 | 0.74 | 0.76 |
| Hard facts kept | 0.79 | 0.81 | 0.72 |
| Invented values per draft | 0.08 | 0.25 | 0.17 |
| Rule errors per 100 blocks | 4.1 | 5.9 | 3.5 |
| Rule warnings per 100 blocks | 58.9 | 60.5 | 51.7 |
| Readability (Amstad, Kandel-Moles) | 54.6 | 56.0 | 54.1 |
| Judge: facts missing, distorted | 7.3%, 3.8% | 3.4%, 3.8% | 6.0%, 6.2% |
| Judge: unsupported statements per 100 blocks | 3.3 | 2.7 | 5.1 |
| Repair rounds | 2.1 | 1.9 | 1.9 |

- What code does with the vocabulary works as built, in both runs: the hard terms a
  draft uses without an explanation fall from 2.3 to 1.0 and 0.1 per draft, the
  glossary grows from 4.4 to about 7 entries, 45 of the 114 hard terms carry the checked
  explanation, and the share of glossary explanations that break the rules falls from
  72 to 45 and 49 percent.
- The word list primes the 8B. With it, the first drafts have 58 office words; without
  it 20, and 33 without any vocabulary. Words the writer without the vocabulary never
  used turn up from the list: `grundsätzlich`, `Wohnsitz`, `falls`, `zugestellt`,
  `elterliche Sorge`. The loop's warnings round with LEX-07 removes most of them again, so the
  final drafts end in the same range (37, 42 and 46 office words). The list was
  therefore removed again (version 9): about the same final drafts without the detour.
  Worth another try with a later Apertus; not tried yet: a list that names only the
  everyday words.
- Facts, invented values, the judge's findings and the rule errors move in both
  directions, by single pairs: in the default run the 8B wrote a first draft of 7 blocks
  for `sg-el-costs-de` (20 facts missing; the repair and facts rounds refilled it with
  near-copies of the source, hence 74 office words per 100 blocks) and one of 29 blocks
  for `be-tax-extension-fr` (14 facts missing, never recovered); in the run with the
  list a repair answer for `sg-el-costs-de` was broken JSON. One run per setting cannot
  separate effects of this size from that variance; a second run of each, or the 23
  eval pairs, would.

### The vocabulary round: P2 on the dev pairs on CSCS (7 October 2026)

The default of the section above (vocabulary on, no word list) once more, with the
vocabulary round on. The round comes after everything else, so the
run replayed every earlier answer from the response cache: all 12 jobs have the same draft
versions as the run without the round, and the comparison shows what the round alone
does. Results in `eval/results-cscs-vocab-round-v2` (and `-rescored-facts`).

| Mean of the 12 pairs | without the round | with the round |
|---|---|---|
| Office words in the final drafts (sum) | 42 | 19 |
| Office words per 100 blocks | 11.7 | 4.7 |
| Fact coverage | 0.757 | 0.757 |
| Hard facts kept | 0.718 | 0.718 |
| Invented values per draft | 0.17 | 0.17 |
| Rule errors per 100 blocks | 3.5 | 2.5 |
| Rule warnings per 100 blocks | 51.7 | 41.7 |
| Readability | 54.1 | 54.6 |
| Judge: facts missing, distorted | 6.0%, 6.2% | 5.5%, 4.1% |
| Judge: unsupported statements per 100 blocks | 5.1 | 4.8 |

- The round ran in 11 of the 12 jobs (`zh-shelters-de` had no office word left) and its
  version was kept in 8. The other 3 lost the final choice: in `zh-blue-algae-de` the
  rewrite dropped a must-keep value, in `be-tax-extension-fr` and
  `zg-disability-services-act-de` the judge, run again, found more problems. So no fact
  was lost: fact coverage, hard facts and invented values are the same to the last digit.
- In the kept versions the office words fell from 34 to 9; `sg-el-costs-de`, the draft
  the facts rounds had refilled with near-copies of the source, went from 20 to 3 and
  from 6 rule errors to 3.
- The judge's figures move with its reruns: a version whose base had judge findings is
  judged again (the existing rule after a repair round), with the judge's own variance.
  That a rewritten sentence loses its unsupported finding without a new judgment cannot
  happen: carry-over only meets versions without one.
- Cost: 12 rewrite calls of the 8B (1.4 s each) and 10 judge reruns of the 70B (11 s
  each), about 11 s per job. Part of the vocabulary since this run (`pipeline.vocabulary`).

### Fact-sheet values the source lacks: P2 on the dev pairs on CSCS (7 October 2026)

A value the Understand model computes or invents (an end of an appeal period, a day for
"im Frühling") used to count as known: FACT-01 asked for it and FACT-06 accepted it in
the draft, with only a FACT-05 warning on the fact sheet. On the team's KESB decision
this let "Die Beschwerdefrist endet am 15. November 2026" reach the draft
(use-case-decisions.md §7). Since this run such a value is neither required (FACT-01)
nor accepted (FACT-06), and fact coverage counts only facts whose value the source
contains. FACT-01 and the source check use the same matching, so a fact the source check
rejects could never be satisfied by a faithful draft either.

How often, in the stored fact sheets of `eval/results-cscs`: 8 of 195 values (P1, 23
pairs), 12 of 331 (P2 8B, 35 pairs), 16 of 207 (70B writer), almost all must-keep. Some
are inventions ("31. März 2026" for "im Frühling", "1. Januar 2021" for "ab 2021", "30.
Juni 2025" for "ab Mitte 2025", "1. Januar 2026" for "innerhalb von drei Tagen nach der
Geburt"); most are normalisations no draft can match ("9" as an amount for "9 Liter",
"041 43 259 51 00" for "+41 43 259 51 00", "10" for "10 Prozent"), which FACT-01 had
flagged as missing in every version. A gap of its own: `0800 33 66 55` and `0848 35 45
55` are not found as phone numbers at all (the pattern knows three-digit area codes), so
hotline numbers are checked neither by FACT-01 nor by FACT-06. The measure alone, on the stored final drafts:
fact coverage of P2 8B on the eval pairs 81.7 to 83.1 percent, of the 70B writer 73.1 to
77.8, of P1 71.1 to 72.4.

The pipeline effect, P2 on the 12 dev pairs, the old rule (patched back in by a scratch
script) and the new one in sequence on the same cache, both scored with the new measure.
Results in `eval/results-cscs-fact06-before` and `-after`.

| Mean of the 12 pairs | old rule | new rule |
|---|---|---|
| Fact coverage (new measure) | 0.788 | 0.788 |
| Hard facts kept | 0.718 | 0.718 |
| Invented values per 100 blocks | 0.47 | 0.47 |
| Rule errors per 100 blocks | 2.54 | 2.51 |
| Model calls per job | 10.6 | 10.5 |
| Tokens per page | 25,205 | 24,587 |

- Four dev pairs have a fact-sheet value the source lacks; none of them reached a final
  draft on either side. Under the old rule the repair rounds asked for them: in
  `be-birth-registration-de` the repair round and the facts round both asked for "1.
  Januar 2026", which the model did not write; under the new rule the job ends a version
  earlier.
- No fact lost and no value invented by the change; the facts no draft could match leave
  the measure, which is why fact coverage reads higher than in earlier runs.
- On the KESB decision's stored draft the new rule turns the invented deadline into a
  FACT-06 error, which blocks and goes to repair instead of reaching the reader.

### Judge doubts on values: two loop changes tried on the dev pairs on CSCS (8 October 2026), not taken

Two changes to the repair loop, found in a review of the example jobs on
8 October, were built, measured and taken out again before the freeze. Neither touched
a template.

- **A: a judge's "missing" on a value code found as a doubt.** A judge verdict
  `missing` counts as blocking and sends the fact back to every repair and facts round,
  also when FACT-01 finds the fact's value in the draft. In `eval/results-cscs` (all
  stored P2 jobs), 11 of the 24 `missing` verdicts on facts with a value that the judge
  left on final drafts were such facts; in the French example job, f07 and f08 showed as
  red "Missing" next to a block with CHF 42'000 and CHF 61'000. The change: such a
  verdict blocks nothing and no round asks for the fact again.
- **B: a missing fact asked for by its clause.** Code completion gives a fact the whole
  source sentence as its text, cut at 200 characters. In the German example job, f07
  (the residence date 1. Januar 2027) shares its sentence with the income limits; asked
  for f07 in two rounds, the 8B wrote the CHF 9'000 per child rule both times and never
  the date. The change: the repair request lists such a fact with the clauses around its
  value that hold no other value ("Anspruchsberechtigt sind Personen, die am 1. Januar
  2027 ihren zivilrechtlichen Wohnsitz in der Gemeinde Musterwil haben …"), taken from
  the full source sentence. On the stored fact sheets it cut 19 of 419 distinct facts
  with a value.

The measurement: P2 on the 12 dev pairs, the committed code (`cd92aec`, run from a copy)
and then the code with A and B, in sequence on the same cache, so the second run
replayed every request that did not change. Results in `eval/results-cscs-ab-before`
and `eval/results-cscs-ab-after`. German, 10 pairs:

| Mean of the 10 pairs | before | with A and B |
|---|---|---|
| Fact coverage | 79 % | 74 % |
| Hard facts kept | 71 % | 64 % |
| Silent losses | 0 % | 0 % |
| Invented values / 100 | 0.77 | 0.77 |
| Judge: unsupported / 100 | 5.8 | 6.1 |
| Rule errors / 100 | 3.1 | 4.3 |
| Must-keep values missing (sum) | 29 | 38 |
| Model calls per job | 10.6 | 10.4 |

The two French pairs and five German pairs came out identical, every draft version the
same: no request of theirs changed. Two German pairs (`be-birth-registration-de`,
`ebgb-inclusion-initiative-de`) got a changed first repair request through B, the full
source sentence instead of the 200-character copy without any cut, and ended with
different drafts but the same fact numbers. The other three ended worse, each after one
fresh 8B answer:

- `zh-blue-algae-de` (A): the second repair round no longer asked for f05, which the
  judge called missing although "Rufen Sie 0800 33 66 55 an." stood in the draft; the
  judge was wrong. Asked again in the run before, the 8B had rewritten the contact
  sentences with their names, and that path kept two more hard values.
- `sg-el-costs-de` (B): one fact of the second repair round was cut to its clause, and
  every sentence the 8B added in that round came out as a fragment ("Bei Personen in
  einer Einrichtung für Menschen mit einer Behinderung."): it took up the style of the
  excerpt. 8 must-keep values were still missing at the end, against none.
- `lu-cost-approval-de` (B): the first repair request changed without any cut, since a
  code fact's text became the full source sentence instead of the 200-character copy;
  the fresh answer ended with one fact less.

Five changed pairs are too few to separate the changes from the noise of the 8B's
answers, but three ended worse and none better, so neither change went into the
pipeline before the final run. The review page keeps the display part of A,
which changes no number: such a verdict shows in amber as "judge doubts" with the
judge's note instead of a red "missing" (`FactRow.status` in `web/views.py`), since code
finds the value and in every case checked (the French example's f07 and f08, f05 above)
the judge had overlooked it. The pipeline still counts it as blocking and asks for the
fact again.

### Judge agreement with blind labels (8 October 2026)

The labelling sheets of `eval/labels/dev` (`eval sample` on the P2 dev drafts of 6
October, CSCS, judge `Apertus-v1.5-70B-thinking`; 30 facts and 30 blocks, drawn evenly
over the judge's verdicts) were labelled by an AI assistant (Claude) that saw the sheet
only, never the key, and then scored with `eval kappa`:

| Items | Labelled | Agreement | Cohen's κ |
|---|---|---|---|
| Blocks: supported or unsupported | 30 | 80 % | 0.60 |
| Facts: present, missing or distorted | 29 | 38 % | 0.08 |
| Facts: present or not | 29 | 62 % | 0.22 |

One fact item stayed unlabelled: its fact-sheet entry reads "Keine spezifische
Definition im Dokument." with no value and no source. Readings:

- The block verdicts (SEM-06) are usable as a pointer: 12 of 15 flagged blocks were
  unsupported (mostly the prompt-example leaks of that day: dog tax, parking card),
  3 of 15 passed blocks were not ("Montag bis Freitag" added to opening hours, two
  dog-tax sentences from the examples); the 3 flagged blocks the labels pass are close
  paraphrases ("Einige Blaualgen bilden giftige Stoffe.").
- The fact verdicts are not. Seven times the judge said "distorted" where the draft
  lacks the fact; in 5 of the 18 disagreements its note describes another fact than
  the one it is filed under (a note about "CHF 40 pour 8 mois" under the fact
  "Nouvelle date limite: 15 novembre", one about "Uferbereich" under an opening time).
  The judge receives the facts as a numbered list; filing notes under the wrong id
  points at the response format, not at the reading. A candidate for a later judge
  prompt: one fact per check with its text repeated in the answer.
- This is why fact coverage, hard facts kept and silent losses are measured by code,
  and why the review page shows a judge verdict that code contradicts as a doubt.

### Recovering a missing fact: one fact on CSCS (9 October 2026)

The review page's "Suggest a sentence" (architecture §4.7) asks the writer for one
missing fact. Before it was built, three prompts were tried on fact f07 of the example
job `praemienverbilligung-brief` (draft v5, CSCS, Apertus 1.5 8B, no thinking,
temperature 0.2, response cache off). f07 is s0005: who lives in Musterwil on
1 January 2027 and stays under the income limits; FACT-01 misses `1. Januar 2027`. The
paragraph also holds s0006, the child increment; the draft already has the income
limits (b009.1) and the increment. The job itself had asked for f07 alone twice through
the repair prompt (repair round 3, facts round 4): both answers were about s0006, and
code dropped them as repeats.

| Prompt | What the call gets | Value back | Prompt tokens |
|--------|--------------------|------------|---------------|
| Repair prompt, f07 alone | the whole fact sheet and draft, the fact's sentence | 1 of 1 (the job's own 2 tries: 0) | 3,578 |
| Paragraph only | the fact, its paragraph, the blocks at its place, the style guide | 0 of 3 | 1,355 |
| Paragraph, value named | as above, plus "Im Text fehlt dieser Wert: 1. Januar 2027. Er steht im Original in Satz [s0005]." and a check that sends an answer without the value back once | 3 of 3, each at the first try | 1,412 |

- Without the value named, the 8B wrote the income limits and the child increment
  again every time: a narrow context alone does not point it at the right sentence.
- The repair prompt's one success copied the source ("Anspruchsberechtigt sind
  Personen, die ... ihren zivilrechtlichen Wohnsitz ...", one LEN-01 error) and put the
  sentence after the heading b005.
- No answer of any prompt had a value outside the paragraph.
- The named-value answers came with a second sentence that repeated the income limits,
  and once with `"after": "s0005"`, a sentence id: code now leaves out a sentence without
  the value whose values the draft already has, and maps a sentence id to its block.

Three more runs through `stages.recover_fact` itself: the value came back 3 of 3, the
repeated income limits were left out 3 of 3, in 0.5 to 3 s per call. Two of the three
sentences were "Der Anspruch gilt ab 1. Januar 2027.": the value is there, so FACT-01 is
content, but the residence condition is lost and the date reads as a start. The third was
"Der Anspruch gilt für Personen, die am 1. Januar 2027 in Musterwil wohnen." Hence the
card on the review page shows the source sentence next to the suggestion and says that
code checks the value, not the meaning; the reviewer decides.

One fact on one letter is not a rate: at temperature 0.2 the runs are close to
identical. The dev pairs' facts still missing at the end are the measurement that
counts. In the pipeline it runs as the recover round
(`pipeline.recover_facts`, architecture §4.6), on by default since the dev run below.

**The recover round on the dev pairs** (CSCS, 9 October 2026). `pipeline.recover_facts = 10`,
P2, into `eval/results-cscs-recover-on`, right after the default run
`eval/results-cscs-en-before` of the English-instructions test on the same code, so the cache replayed every call before
the round: the seven pairs with no value missing came out identical, and the
difference is the round alone.

| Dev pairs | Fact coverage | Hard facts kept | Judge: distorted (fact-rich) | Invented values / 100 blocks | Tokens / page |
|-----------|---------------|-----------------|------------------------------|------------------------------|---------------|
| German (10), round off | 78 % | 72 % | 3 % | 0.8 | 24,946 |
| German (10), round on | 96 % | 90 % | 5 % | 0.6 | 28,002 |
| French (2), round off | 97 % | 94 % | 0 % | 1.2 | 23,524 |
| French (2), round on | 100 % | 97 % | 8 % | 1.2 | 25,432 |

- The round ran in 5 of 12 jobs: 20 facts asked for, 16 added, 4 with nothing new (each
  sentence repeated the draft), none rejected for a value outside the paragraph. No job
  gained an invented value. The final versions keep 27 of the 28 added sentences.
- By pair: zh-shelters-de 58 to 100 percent fact coverage, be-pregnancy-counselling-de
  36 to 64, sg-el-costs-de 86 to 100, ebgb-inclusion-initiative-de 0 to 100 (its one
  checkable fact), be-tax-extension-fr 94 to 100.
- The judge, run again on the new version, calls 3 of the 13 recovered facts it checked
  distorted, and 6 added blocks unsupported (two of these notes say "Korrekt" in the
  same breath). Read by hand, the weak sentences are of three kinds: the prompt's word
  echoed ("Der Wert ist 052 213 08 78."), a broken reflexive ("Sie können sich
  anrufen."), and a sentence without the value added to the right one ("Sie können dort
  mehr Informationen finden."). Most recovered facts are contacts of several offices
  (addresses, numbers, e-mail addresses).
- Cost: about 12 percent more tokens per page and 5 s more per German page.

Twelve pairs, five of them changed: the eval split decides what the round is worth. The
comparison is paired (the same answers up to the round), but two independent runs of
the same code differ a lot per pair (the English-instructions test, cache off: zh-oral-health-de fact
coverage 1.0 against 0.5, zh-shelters-de 0.58 against 1.0), so how much the round adds
depends on how many values are missing before it, and that varies from run to run.

### English instructions: tried on the dev pairs on CSCS (9 October 2026), not taken

The owner asked whether English instructions would serve the 8B better than German and
French ones, in every stage that matters and in repair first. Small models often follow
English instructions a little more reliably; against that stood the design choice above
(no other language in the texts reviewers read) and Apertus' large share of German and
French training data.

**What was built for the test** (removed again the same day, see the decision; commit
`ff0544a` has it). English templates for understand, write, judge and repair and the two
partials (`llm/prompts/en/`), each the German template in English line for line. Write
and repair got one more line that names the language of the answer ("Write every text
in German."); understand and judge already had one. The JSON examples, the few-shot
pairs, the reader's example headings, the example words of SEM-03 and SEM-08 and every
example in the style guide stayed in the document's language, word for word (a test
compared the JSON examples character for character with the frozen templates). The
style guide came in English from the same registry (one English text per rule guide),
the words code writes around the items (fact sheet headings, "Suggestion:", the problem
lines) from an English entry in `pipeline/labels.py`. A setting named the stages with
English instructions and was empty by default; then every prompt was the frozen one
byte for byte (the baseline below replayed all 125 calls from the response cache,
whose key is the whole prompt). The English prompts were only 2 to 4 percent shorter in
tokens, since most of a prompt is the document, the fact sheet and the draft.

**The measurement.** P2 on the 12 dev pairs (10 German, 2 French) on CSCS, 8B writer,
70B judge, the recover round off (`pipeline.recover_facts = 0`), one folder per run:

- `en-before`: the frozen prompts, replayed from the cache (the same as
  `prov-after` of 8 October);
- `en-before-fresh`: the frozen prompts again with the cache off: a second sample of
  the same pipeline, to see the 8B's noise from run to run;
- `en-repair`: repair in English, everything else as `en-before`. Understand, write
  and the first judge call came from the cache, so the first repair round of every job
  got the same request as in `en-before`: the two repair prompts on equal input;
- `en-judge`: the judge in English, everything else as `en-before`;
- `en-all`: all four stages in English, every call fresh.

One script read the folders: the evaluation rows, the repair rounds from the stored
artifacts (the rule findings on the blocks a round was asked to fix that are gone, stay
or are new in the version it produced, and the must-keep values it added) and the
model's texts that read as English (more English than German or French function words,
two at least). Another judged the 11 labelled jobs of `eval/labels/dev` again, three
fresh samples per prompt language, and scored them with `eval kappa`'s scoring against
the blind labels of 8 October. Both went with the variant; the result folders
(`eval/results-cscs-en-*`) and the judge's key files (`eval/labels/dev/*.key.jsonl`)
stay local and git-ignored.

**Noise first.** The two runs of the frozen prompts differ more than any English
variant differs from them: hard facts kept, pooled over the 12 pairs, 100 against 82
of 140; rule errors 2.0 against 4.2 per 100 blocks; per pair, `sg-el-costs-de` 19
against 9 of 22 hard facts, `zh-shelters-de` 7 against 12 of 12. A mean over 12 pairs
moves by 10 points on one pair (`ebgb-inclusion-initiative-de` has one hard fact).

**Repair on equal input** (the first round of the 12 jobs, the same 61 blocks with 54
rule problems and 33 missing values asked for):

| First repair round | German | English |
|---|---|---|
| Rule problems fixed on the asked blocks | 21 | 15 |
| New rule problems on them | 26 | 45 |
| Of these errors: fixed / new | 11 / 5 | 11 / 9 |
| Missing values added | 12 | 13 |
| Blocking count, 125 before | 117 | 136 |
| Answered sentences: mean words / over 12 words | 8.1 / 9 of 93 | 9.3 / 23 of 113 |
| Sentences code dropped as repeats | 6 | 20 |

The second German run has 28 new problems on 62 in its first round, close to the first;
English stands apart. Under English instructions the 8B's German gets longer and less
plain (more LEN, LEX and GRAM findings), and on one page it left blocks as they were,
added an invented sentence and wrote two long sentences with brackets where the German
answer split them into short ones. It adds missing values as often as the German
prompt.

**Whole jobs** (means over the 12 pairs; pooled hard facts in brackets):

| | German | German, 2nd run | English repair | English judge |
|---|---|---|---|---|
| Hard facts kept | 76 % (100/140) | 70 % (82/140) | 84 % (104/140) | 84 % (110/140) |
| Rule errors / 100 blocks | 2.3 | 4.8 | 2.9 | 2.9 |
| Warnings / 100 blocks | 40 | 57 | 51 | 46 |
| Invented values / 100 blocks | 0.85 | 0.00 | 0.21 | 0.20 |

Against the first German run, English repair keeps more hard facts on 4 pairs and fewer
on 2, the English judge on 3 and 2; most of the English judge's 10 more facts are one
page (`be-pregnancy-counselling-de`, 25 against 13 of 37, where the two German runs had
13 and 11). The two German runs span 82 to 100 hard facts: English repair is just above
(104), the English judge 10 above (110), mostly through that one page; on rule errors
both are inside the band.

**All four stages in English.** 3 of the 12 pairs failed, and failed again when run a
second time with fresh calls: `zh-voting-de` (the write answer gives its omissions as
an object with sentence ids as keys, twice in each pass), `sg-el-costs-de` (Understand
copied three facts of the JSON example, then the example's omission `s0009` with an
unquoted id), `ebgb-inclusion-initiative-de` (Understand did not validate, twice in each
pass). The second German run lost one pair in its first pass
(`bwl-emergency-supplies-fr`, Understand) and had it on the second. On the 9 pairs it
completed, English keeps 100 of 110 hard facts against 74 and 67, 24 of the 26 more on
`be-pregnancy-counselling-de` (37 against 13); pair by pair 4 better, 4 worse, 1 the
same, with 59 percent more blocks and 3.4 rule errors per 100 blocks against 1.8 and
3.6. The fact sheets change more than the drafts: on the 9 pairs Understand marks 33
passages as droppable against 13 and 11, so code makes their values background and
the sheets hold 114 must-keep facts against 176 and 150; 8 of 9 name the document type
in English ("Information sheet", from the template's English list of document kinds),
one answer was a list of keywords with no fact and the example's omission, and 2
omission entries of the final drafts are English ("Details of the contact hours Not
needed for the reader"). No other English text of three words or more appeared in any
run, apart from one sentence the source itself has (a link to an English form).

**The judge against the blind labels** (three samples per language; the same 11
drafts):

| | German | English |
|---|---|---|
| Blocks: supported or unsupported | 78 % (κ 0.56) | 79 % (κ 0.58) |
| Facts with a verdict, of 29 labelled | 28 | 19 |
| Facts both judged (19): three classes | 37 % (κ 0.03) | 65 % (κ 0.42) |
| Facts both judged (19): present or not | 61 % | 79 % |

On blocks the two are the same. On facts the English judge agrees with the labels far
more often where it gives a verdict, in each of its three samples (63, 68 and 63
percent), but on the labelled draft of `sg-el-costs-de` it returned an empty fact list
every time (9 of the 10 items without a verdict; in the pipeline it checked all 27
facts of that page's first draft). The German judge itself gave another verdict than on
6 October on 4 of 29 facts and 6 of 30 blocks of the same drafts.

**Decision.** No change before the freeze: the final run uses the German and French
templates. English instructions make the 8B's German repairs longer and less plain on
equal input, make Understand drop content and fail on pages the German prompt handles,
and bring English into omission entries and fact sheets; their gains on facts stay
within the noise of two German runs. The one lead is the judge's fact verdicts: before
an English judge could replace the German one it needs more labelled facts than 19
from 10 drafts and an answer to the empty fact list. At the owner's request the variant
was then removed completely (templates, setting, English style guide and labels, tests,
the two scripts), and only these results are kept; a further try should keep the
template's example document kinds in the document's language.

### The polish round on the dev pairs (10 October 2026)

One more repair round after the recover round, for the rule findings of the best version
alone (`pipeline.polish_rounds`, default 1): its repairable errors, or its
warnings once no error is left; no fact, no judge's problem, no office word. Run on the
12 dev pairs on CSCS into `eval/results-cscs-polish`, with the cache replaying
every call before the round, against the recover-on run of 9 October (same code
otherwise, plus the GRAM-08 fix of the same day, which fired in no dev final).

| Dev split | Run | Fact coverage | Hard facts kept | Rule errors per 100 blocks | Warnings per 100 | Invented per 100 | Unsupported per 100 | Tokens per page |
|---|---|---|---|---|---|---|---|---|
| German (10) | recover on | 96 % | 90 % | 1.9 | 38.1 | 0.6 | 5.8 | 28,003 |
| German (10) | polish | 96 % | 90 % | 1.3 | 34.3 | 0.6 | 5.3 | 32,680 |
| French (2) | recover on | 100 % | 97 % | 3.3 | 47.7 | 1.2 | 4.5 | 25,433 |
| French (2) | polish | 100 % | 97 % | 3.2 | 47.2 | 1.2 | 3.4 | 29,400 |

The round ran in all 12 jobs and asked for 1 to 16 blocks. In 8 jobs the final draft
descends from the polished version (the vocabulary round builds on it); in 4 the choice
discarded it because the judge flagged the rewritten blocks (blocking findings 4 to 12
in `zh-blue-algae-de`, 7 to 8, 5 to 6, 30 to 33). No job lost a must-keep value: the
missing counts before and after are equal everywhere. The judge's distorted verdicts in
the final drafts fell from 13 to 7, the error findings of all kinds from 67 to 65: what
remains are provenance and bookkeeping findings (FACT-02 22, FACT-03 18), missing values
(FACT-01 13) and the judge's unsupported verdicts (26), none of which a rewrite of the
flagged block can fix. Cost: about 17 percent more tokens per page. Seconds per page are
not comparable, since the recover-on run replayed most calls from the cache. Kept on by
default for the final run.

### The judge's quotes on the dev pairs (10 October 2026)

Both judge templates ask for a `quote` with every unsupported verdict, the words of the
block the original does not cover, and say that another wording of the same statement
is no problem. Code keeps a verdict only when its quote stands in a block
of the draft, on that block, and files the rest under `dropped`. Reason: in the example
builds the 70B had cited the prompt example's own block id `b006` in 46 of 179
verdicts, with the example's note in some, and one French draft was clean but for a
verdict on a tax assessment the letter names. Run on the 12 dev pairs on CSCS into
`eval/results-cscs-judge-quote` against the polish run of the same day; Understand
and Write replayed from the cache, every judge call new, so the repair answers after
the first judge call are new samples too.

| Dev split | Run | Fact coverage | Hard facts kept | Rule errors per 100 blocks | Invented per 100 | Unsupported per 100 | Tokens per page |
|---|---|---|---|---|---|---|---|
| German (10) | polish | 96 % | 90 % | 1.3 | 0.6 | 5.3 | 32,680 |
| German (10) | judge quotes | 94 % | 88 % | 0.2 | 0.0 | 3.1 | 36,587 |
| French (2) | polish | 100 % | 97 % | 3.2 | 1.2 | 3.4 | 29,400 |
| French (2) | judge quotes | 100 % | 97 % | 4.5 | 1.2 | 2.3 | 24,460 |

Unsupported verdicts over all draft versions: 188 to 102, every kept one with a quote;
4 dropped, all four the example's internet sentence on a block that says nothing of the
kind. In the final drafts: unsupported 26 to 13, the judge's distorted verdicts 7 to 3,
FACT-06 4 to 1. The judge's most cited block is still `b006`, 10 of 102 against 22 of
188. The two fact numbers fall on one pair alone (`be-pregnancy-counselling-de`, 41
must-keep facts, 32 missing after the write stage): its facts round had added 9 values
in the polish run and added none in this one, a fresh 8B sample on a changed request;
the other 9 German pairs are unchanged on facts. The French rule errors rise on one
pair the same way (6 to 9 errors in its final). Every final draft still has errors,
FACT-02, FACT-03 and FACT-01 above all. Kept on for the final run.

### Fact links, questions and the judge's spellings on the dev pairs (10 October 2026)

Three changes in one run, measured on the 12 dev pairs on CSCS into
`eval/results-cscs-fact-links` against the judge-quotes run of the same day:
`stages.link_facts` names a fact without a value on every block that cites one of its
sentences, and a fact with values in its text on the blocks of its sentences that
together hold all of them (FACT-02); FACT-03 skips a question block; both judge
templates say that another spelling of the same value is no distortion. Understand and
Write replayed from the cache; the judge template changed, so every judge call and the
repair answers after it are new samples.

| Dev split | Run | Fact coverage | Hard facts kept | Rule errors per 100 blocks | Invented per 100 | Unsupported per 100 | Tokens per page |
|---|---|---|---|---|---|---|---|
| German (10) | judge quotes | 94 % | 88 % | 0.2 | 0.0 | 3.1 | 36,587 |
| German (10) | fact links | 95 % | 86 % | 1.3 | 0.0 | 0.8 | 34,764 |
| French (2) | judge quotes | 100 % | 97 % | 4.5 | 1.2 | 2.3 | 24,460 |
| French (2) | fact links | 100 % | 97 % | 2.9 | 1.2 | 3.3 | 29,782 |

In the final drafts: FACT-02 findings 19 to 10, FACT-03 18 to 18, the judge's
unsupported verdicts 13 to 6, error findings of all kinds 64 to 55, and for the first
time two of the 12 finals carry no error at all. Over all draft versions the judge's
unsupported verdicts fell from 102 to 55, 2 dropped as copies of the example. The rule
errors per 100 blocks bounce between runs of the same code (1.3, 0.2, 1.3 in the three
runs of the day: 4 GRAM-01 findings in fresh repair samples this time); the hard facts
kept move on one pair (`zh-blue-algae-de`, 7 of 8 to 5 of 8 in a fresh write-round
sample, every other pair unchanged or up). Kept on for the final run.

### Sentence placement on the dev pairs (10 October 2026)

A sentence a repair round adds after a list item, and a sentence the recover round
places after one, go after the list's last item instead of between its items
(`stages.apply_repairs`, `stages.add_sentences`). Run on the 12 dev pairs on CSCS
into `eval/results-cscs-placement` against the fact-links run of the same day.
Seven pairs replayed every call from the cache and are identical; in five the
placement changed a later request, so their repair and recover answers are fresh
samples. German means: rule errors 1.3 to 1.6 per 100 blocks, warnings 32 to 33, fact
coverage 95 to 96 percent, hard facts kept 86 to 87, unsupported 0.8 to 1.0, tokens
per page plus 3 percent; French unchanged. In the final drafts the error findings of
all kinds went from 55 to 53, FACT-01 from 19 to 16, the rest equal. A layout change
with no effect beyond the day's sampling noise, kept on for the final run.

### The final run on the eval split (CSCS, 10 October 2026)

*Superseded by the run of 11 October (next section): the prompt templates gained the
document fence after this run (change log 14), so it was repeated on them.*

Every row again with `--redo` on the frozen pipeline (commit 760a210, the code of
3131a02) into `eval/results-cscs`, after a snapshot to `results-cscs-v6`: P1
and P2 on the 23 held-out pairs (20 German, 3 French) with the cache on, P0 and both
P0-ZH variants with the cache off (fresh calls, so their seconds are measured), the
70B writer and the hybrid on the same 23 pairs; 908 fresh calls, 4 retried, no failed
pair. Every row carries the scoring of 10 October (the value kinds of 7 October, fact
coverage on the values the source contains, the silent-loss key). German means over the 20 eval pairs
(`docs/evaluation.md` has every column, also for French):

| Setup | Fact coverage | Hard facts kept | Silent losses | Errors / 100 | Warnings / 100 | Readability | Unsupported / 100 | Invented values / 100 | Tokens / page | USD / page | s / page |
|---|---|---|---|---|---|---|---|---|---|---|---|
| REF | - | 67 % | 33 % | 2.7 | 27.7 | 62 | - | 2.8 | - | - | - |
| P0 | 88 % | 88 % | 12 % | 22.2 | 103.3 | 50 | - | 0.2 | 944 | 0.0001 | 2.5 |
| P0-ZH complete | 91 % | 93 % | 7 % | 19.5 | 100.3 | 46 | - | 0.2 | 2,385 | 0.0003 | 2.4 |
| P0-ZH default | 74 % | 75 % | 25 % | 9.6 | 74.2 | 47 | - | 0.0 | 2,218 | 0.0002 | 1.6 |
| P1 | 53 % | 51 % | 0 % | 7.0 | 40.0 | 50 | - | 0.1 | 8,661 | 0.0012 | 6.5 |
| P2, 8B | 98 % | 87 % | 0 % | 2.0 | 36.5 | 54 | 1.8 | 0.0 | 32,775 | 0.0171 | 33.6 |
| P2, 70B everywhere | 97 % | 91 % | 0 % | 1.0 | 20.3 | 59 | 0.5 | 0.0 | 23,223 | 0.0260 | 44.5 |
| P2, hybrid: 70B reads, 8B writes | 99 % | 94 % | 0 % | 1.8 | 34.3 | 54 | 1.7 | 0.0 | 26,775 | 0.0166 | 32.5 |

- **Case A of the headline numbers** (`eval numbers`): P2 against P0-ZH complete has fewer
  invented values (0.0 against 0.2 per 100 blocks), fewer rule errors (2.0 against
  19.5) and higher fact coverage (98 against 91 percent). The owner confirmed the case
  the same night. On hard facts kept the
  complete prompt is ahead (93 against 87 percent), and its losses are silent (7
  percent), where P2 lists every one.
- **Since 6 October** (then P2: 84 percent fact coverage, 80 hard facts kept, 4.3
  errors, 0.1 invented values per 100 blocks) the facts rounds, the recover round, the
  polish round and the judge's quotes went in, each measured on the dev pairs (above);
  the eval split moved alike. P1 reads 53 percent fact coverage against 72 then: the
  scoring changed (the value kinds of 7 October count more values, fact coverage counts
  only facts the source contains) and so did the writer's prompt, and P1 has no round that
  asks for the facts a first draft drops. The gap from P1 to P2 is what the rounds add.
- **The tiers** (6 October: the 70B kept fewer facts, the hybrid the fewest): with the
  rounds all three find 97 to 99 percent of the must-keep facts. The 70B everywhere
  writes the cleanest text (1.0 errors, readability 59, half the warnings) at 1.5
  times the 8B's price; its seconds per page hold one Write call that the server
  closed eight times before it answered (42.0 s without that pair). The hybrid keeps
  the most hard facts (94 percent) at the 8B's price. The 8B writer stays the default:
  it runs on one 24 GB GPU.
- **Fact-retention diagnosis on the eval split** (`eval diagnose --role eval --writer
  swiss-ai/Apertus-v1.5-8B`, 23 jobs): 184 checkable must-keep facts, 8 missing in the
  final versions (96 percent found); 6 of the 8 on one page with 23 must-keep values
  (`zh-passport-id-de`), never asked for behind the cap of facts per round, 1 written
  and dropped by code, 1 asked for and not written. The hybrid: 237 checkable, 3
  missing. `eval/results-cscs/diagnosis_final.md` has the details (local: it
  quotes the pages).
- **French** (3 pairs, 8B): fact coverage 94 percent, hard facts kept 70, 2.1 errors
  per 100 blocks, readability 71 (official 85); the 70B everywhere 100, 89 and 6.1;
  the hybrid 100, 88 and 17.8 errors (its sentences grew to 10.8 words).
- **Seconds per page** are measured for the baselines (cache off). In P1 and P2 the
  Understand answers came from the cache, and P2's first draft from P1's call minutes
  before, so their seconds undercount; the 33.6 s of P2 on the 8B are the judge,
  repair, facts, recover and polish calls.

### The final run on the templates with the document fence (CSCS, 11 October 2026)

The owner's decision: every row again on the templates with the document fence (change
log 14), commit 663b609, after a snapshot of the run above to `results-cscs-v7`. Order
changed so that the headline row's seconds are complete: P2 on the 8B first (every
prompt changed, so its Understand and Write calls were fresh), then P1 from P2's cached
answers, P0 and both P0-ZH variants with the cache off, the 70B everywhere, the hybrid
(its Understand from the 70B row's cache), then a retry pass. One P2 pair failed on
broken JSON in Understand and passed on the retry; the 70B everywhere failed on
`zh-sebe-disability-de`, where the server cut the long Write stream in all 35 attempts
(9, 9 and 17 with `llm.max_retries = 16`), so that row has 19 German pairs. German means
over the 20 eval pairs:

| Setup | Fact coverage | Hard facts kept | Silent losses | Errors / 100 | Warnings / 100 | Readability | Unsupported / 100 | Invented values / 100 | Tokens / page | USD / page | s / page |
|---|---|---|---|---|---|---|---|---|---|---|---|
| REF | - | 67 % | 33 % | 2.7 | 27.7 | 62 | - | 2.8 | - | - | - |
| P0 | 92 % | 93 % | 7 % | 19.5 | 95.2 | 52 | - | 0.2 | 982 | 0.0001 | 2.6 |
| P0-ZH complete | 83 % | 85 % | 15 % | 15.0 | 92.4 | 47 | - | 0.0 | 2,393 | 0.0003 | 2.4 |
| P0-ZH default | 69 % | 67 % | 33 % | 9.0 | 80.0 | 46 | - | 0.2 | 2,198 | 0.0002 | 1.4 |
| P1 | 74 % | 73 % | 0 % | 8.3 | 50.3 | 51 | - | 1.1 | 9,555 | 0.0014 | - |
| P2, 8B | 100 % | 97 % | 0 % | 4.2 | 43.9 | 51 | 1.6 | 0.1 | 28,066 | 0.0131 | 63.3 |
| P2, 70B everywhere (19 pairs) | 99 % | 92 % | 0 % | 0.6 | 26.6 | 56 | 1.1 | 0.0 | 22,988 | 0.0262 | 57.5 |
| P2, hybrid: 70B reads, 8B writes | 100 % | 95 % | 0 % | 1.9 | 41.4 | 53 | 1.0 | 0.1 | 27,885 | 0.0163 | 32.4 |

- **Case A2 of the headline numbers** (`eval numbers`, added 11 October with the owner's
  headline): P2 against P0-ZH complete has fewer rule errors (4.2 against 15.0 per 100
  blocks) and higher fact coverage (100 against 83 percent), but not fewer invented
  values (0.1 against 0.0: one value each in two drafts, among them "drei Monaten" in
  `zh-political-rights-de`). Headline: the pipeline finds 100 percent of the must-keep
  facts against 83, loses none without a trace against 15 percent, and has 4.2 against
  15.0 rule errors; invented values are rare on both sides.
- **Against the run of 10 October.** The baseline templates did not change, yet P0-ZH
  complete went from 91 to 83 percent fact coverage and from 19.5 to 15.0 errors, P0
  from 88 to 92: one answer per pair at temperature 0.3 varies that much. P2's errors
  rose from 2.0 to 4.2 mostly on one pair: `zh-political-rights-de` (7.4 pages) came
  out on 10 October as an 8-block, 43-word draft with 0 errors and now as a 140-block
  draft with 47 errors (33.6 per 100 blocks, two fifths of the mean). P1 rose from 53
  to 74 percent fact coverage on fresh Understand and Write answers.
- **The tiers.** The 70B everywhere writes the cleanest text (0.6 errors, readability
  56) at twice the 8B's price, but keeps fewer hard facts (92 against 97 percent); the
  hybrid finds 100 percent, keeps 95 and halves the 8B's errors (1.9) for a quarter more
  than the 8B's price. The 8B writer stays the default.
- **Fact-retention diagnosis** (`eval diagnose --role eval --writer
  swiss-ai/Apertus-v1.5-8B`, 23 jobs): 205 checkable must-keep facts, none missing in
  the final versions.
- **French** (3 pairs, 8B): fact coverage 100 percent, hard facts kept 87, 4.9 errors
  per 100 blocks, readability 74 (official 85); the 70B everywhere 100, 91 and 4.6; the
  hybrid 100, 93 and 6.6.
- **Seconds per page** are complete for P2 on the 8B (63.3 s, every stage fresh), the
  70B everywhere and the baselines; P1 took every answer from the cache (not measured)
  and the hybrid its Understand answers (undercounts).

### The extractor fixes and the quote check on the dev pairs (CSCS, 12 October 2026)

Decision: the value extractor's false alarms and gaps found with the
test texts of two other Apertus projects and confirmed on the final run above (the
genitive `dreier Monate`, the elision `d'un mois`, `Merkblatt 2.06.` read as a date,
`Schweiz - 3003 Bern` as no address, multipliers, the identifier keywords of tax
letters and payment orders; docs/rules.md "Value kinds" and FACT-06), the
judge's quote check ignoring the `- ` and `# ` markers and filing verdicts on question
headings under `dropped` (architecture §4.5), and `puce` among the French example-topic
words. Code only, no template changed. P2 on the 12 dev pairs with the du templates of
change log 15, against the dev-final run of 10 October (formal templates, the old
extractor; both runs fresh samples, so this is a sanity check before the repeated
final run, not an ablation): German (10 pairs) fact coverage 96 against 96 percent,
hard facts kept 89 against 87, invented values 0.0 against 0.0, rule errors 1.7
against 1.3 per 100 blocks, warnings 43 against 36, unsupported 1.5 against 1.0;
French (2 pairs) fact coverage 100 against 100, hard facts 97 against 97, rule errors
1.1 against 2.9, unsupported 2.0 against 3.3. Every pair reached review. The repeated
final run on the eval split follows below.

### The final run on the fixed extractor (CSCS, 12 October 2026)

Decision: our rows again on the du templates of change log 15
and the extractor fixes above, after a snapshot of the run of 11 October to
`results-cscs-v8`. Order: P2 on the 8B first (fresh Understand and Write, so its
seconds cover every stage), P1 from P2's cached answers, P0 with the cache off; then
the two P0-ZH rows, whose template the du change did not touch, scored again in place
against this run's fact sheets (`eval rescore --in-place`, no model call: the single
prompts move by up to 8 points between samples on unchanged templates, and the
headline's baseline side should move only by the fixes); then the 70B everywhere and
the hybrid, and a retry pass. The main run took 17:13 to 20:05. Three pairs failed on
the first pass: two P2 pairs on the 8B with unusable Understand answers (no `facts`
field, no JSON) and the 70B everywhere on `zh-sebe-disability-de`, its Write stream cut
in 9 attempts, as on 11 October (that row keeps 19 pairs). The retry pass took the
night: the French pair `ge-prosecutor-election-fr` hung on the endpoint until the job's
time budget of 7,200 s stopped it, with 2 minutes of model time logged for the whole
step; it passed on a third try the next morning, `zh-political-rights-de` on the
second. German means over the 20 eval pairs:

| Setup | Fact coverage | Hard facts kept | Silent losses | Errors / 100 | Warnings / 100 | Readability | Unsupported / 100 | Invented values / 100 | Tokens / page | USD / page | s / page |
|---|---|---|---|---|---|---|---|---|---|---|---|
| REF | - | 67 % | 33 % | 2.7 | 27.7 | 62 | - | 2.8 | - | - | - |
| P0 | 94 % | 95 % | 5 % | 24.9 | 108.6 | 49 | - | 0.2 | 999 | 0.0001 | 2.8 |
| P0-ZH complete (sampled 11 Oct, rescored) | 82 % | 85 % | 15 % | 15.0 | 92.4 | 47 | - | 0.0 | 2,393 | 0.0003 | 2.4 |
| P0-ZH default (sampled 11 Oct, rescored) | 65 % | 67 % | 33 % | 9.0 | 80.0 | 46 | - | 0.0 | 2,198 | 0.0002 | 1.4 |
| P1 | 61 % | 59 % | 1 % | 9.7 | 46.6 | 50 | - | 0.1 | 8,900 | 0.0012 | - |
| P2, 8B | 100 % | 97 % | 0 % | 3.7 | 41.5 | 52 | 2.7 | 0.0 | 33,392 | 0.0159 | 59.6 |
| P2, 70B everywhere (19 pairs) | 100 % | 96 % | 0 % | 0.5 | 22.2 | 57 | 1.0 | 0.0 | 22,295 | 0.0250 | 60.0 |
| P2, hybrid: 70B reads, 8B writes | 99 % | 94 % | 0 % | 3.0 | 37.6 | 53 | 1.4 | 0.0 | 24,307 | 0.0145 | 31.8 |

- **Case A2 of the headline numbers again** (`eval numbers`): the pipeline finds 100 percent of
  the must-keep facts against 82, loses none without a trace against 15 percent, and
  has 3.7 against 15.0 rule errors per 100 blocks; invented values are rare on both
  sides (0.0 against 0.0).
- **The fixes' own share.** On the drafts of 11 October, scored again offline before the
  run, they removed 1 of P2's 2 invented values on the German eval pairs, the only ones
  of the condensed baseline and of the hybrid row, and added 2 hard facts to the 20
  sources. The rescored P0-ZH complete row moved from 83 to 82 percent fact coverage on
  the new fact sheets; its hard facts, errors and silent losses did not move.
- **Against the run of 11 October.** P2's errors fell from 4.2 to 3.7: the 7-page pair
  came out as a 44-block draft with one error instead of 140 blocks with 47, and a
  third of the errors (13 of 38) now sit in one two-page health-insurance text. The
  judge's unsupported verdicts rose from 1.6 to 2.7 per 100 blocks, not through the
  quote fix (none of the 27 verdicts kept in the final reports carries a marker, one
  was dropped) but through the sample: the 70B objected to the recover round's "Rufen
  Sie ... an: number" sentences in one pair (8 of 50 blocks) and to supplies the source
  lists in another (5 of 25), both wrongly. P1 fell from 74 to 61 percent fact coverage
  on fresh answers: a single Write without judge, repair and recover rounds keeps that
  variance, P2 ends at 100 in both runs. P2's tokens per page rose from 28,066 to
  33,392 (USD 0.0131 to 0.0159) at the same mean of 1.8 rounds.
- **Fact-retention diagnosis** (8B, 22 eval jobs): 216 checkable must-keep facts, 2
  missing in the final versions, both in `zh-passport-id-de` (one behind the per-round
  cap of missing facts, one asked for and not written).
- **French** (3 pairs, 8B): fact coverage 100 percent, hard facts kept 72 (one draft of
  117 words for a 489-word source kept 4 of 15, every one listed for the reviewer), 3.5
  errors per 100 blocks, readability 70 (official 85); the 70B everywhere 100, 89 and
  3.4; the hybrid 95, 87 and 8.8.
- **Seconds per page** are complete for P2 on the 8B (59.6 s), the 70B everywhere
  (60.0) and the baselines; P1 took every answer from the cache (not measured) and the
  hybrid its Understand answers from the 70B row's cache (31.8 s undercounts).

## Change log

| Version | Date | Change |
|---------|------|--------|
| 1 | 2026-10-05 | First German templates for understand, write, judge, repair and baseline; two synthetic examples. |
| 1 | 2026-10-06 | No template change. Stage settings: write without thinking by default (see "Tested so far"). |
| 2 | 2026-10-06 | The examples name no office ("das Amt" instead of "Steuer·amt"), and the write prompt says that names of offices, addresses and numbers come only from the document: in a local run the writer called the Sozialversicherungsstelle "Steueramt", the office of the tax example. Code no longer lets a repair repeat a sentence that is already in the draft. |
| 3 | 2026-10-06 | All examples (few-shot pairs and the JSON examples of every prompt) moved to topics that are not in the evaluation set: a resident parking permit and a dog tax. The repair prompt makes adding the missing facts the first task, each with its value and fact id. Code: a repair round first asks only for the blocking problems (rule errors, missing facts, the judge's problems), at most 5 missing facts at a time, the most important kinds first; the warnings get one round once nothing blocking is left. |
| 4 | 2026-10-06 | French templates for all five stages, with French JSON examples and two French few-shot pairs on the same topics as the German ones. The words code writes around the items come from a table per language (`pipeline/labels.py`). No change to the German templates. |
| 5 | 2026-10-06 | Write prompt (German and French): the JSON form moved before the style examples, its intro says the values come from another document; the document comes last, followed by the instruction to write about it. Reason: on the Public AI 8B without thinking, 4 of 12 dev drafts were the JSON form itself. Code: an answer that copies the examples is sent back once; the omissions or glossary list written as a pseudo-block inside blocks is hoisted. No change to the other templates. |
| 6 | 2026-10-06 | Repair prompt (German and French): every value in the answer comes from the fact sheet or the original's sentences, the values of the JSON form belong to another document, and no value is invented for a fact without one. Code: a repair answer with a value that neither the source nor the fact sheet contains is sent back once with the values named (the check of rule FACT-06); the second answer is used as it is. Reason: the examples' phone number stood in 8 of 12 dev drafts, put there by repair additions. No change to the other templates. |
| 6 | 2026-10-06 | No template change. Code: a sentence with a topic word of the examples (`Hund`, `Parkkarte`, `Impfausweis`, `chien`, `carte de stationnement`, ...) that the source does not contain, or with one of the examples' own values, is sent back once and dropped from the second answer; two more JSON repairs (a list or object closed with the wrong bracket, a unicode escape with too few digits), both seen on the CSCS 8B; a core answer written as a bare sentence instead of an object is read as its text; an empty block `{}` is dropped; a write answer cut off at the token limit is written again as two halves (8 jobs failed this way in the first evaluation run on CSCS); an omission or glossary entry written as a block of that kind is hoisted into its list (the 70B writer). |
| 6 | 2026-10-06 | No change to our templates. New German template `baseline_zh.md`: the Canton of Zurich's Leichte Sprache prompt, verbatim, as the second baseline P0-ZH in two variants (`complete`, `condensed`); its rendering was checked character for character against their own prompt assembly (`create_prompt` in `app_core.py`). |
| 6 | 2026-10-06 | No template change. Code: the Mediopunkt is written by code after the write stage and after every repair round, in P1 and P2 (`rules/mediopunkt.py`, docs/rules.md "Edits made by code"), and LEX-01 no longer exempts a compound because it is in the glossary. Reason: in the owner's first CSCS job through the web UI the 8B kept `Krankenversicherungspolice` and `Sozialversicherungsstelle` unsplit through two repair rounds. The repair prompt therefore no longer carries LEX-01 lines for compound nouns. Rescored without model calls on the final drafts already in the CSCS store (97 German P1 and P2 jobs, 3453 blocks): LEX-01 warnings per 100 blocks fall from 39.1 to 3.0 (P1, 8B), 31.9 to 3.1 (P2, 8B) and 27.0 to 2.2 (P2, 70B), all warnings per 100 blocks from 77.9 to 42.0, 66.7 to 38.0 and 53.8 to 29.3; 30 to 41 words per 100 blocks get the dot, 157 of the 1177 in glossary terms. Reading splits by hand found two wrong joints in the first 25: `Ostermundi·gens·trasse`, fixed in the splitter (a nested split now counts by its weakest part, giving `Ostermundigen·strasse`) and by leaving the word in front of a house number alone; and `Kostengut·sprache` for `Kosten·gutsprache`, which stays, because the splitter does not know the Swiss term. The next 25 had none. What the step saves in repair rounds shows only in the next `--redo` rerun on CSCS, which is still open. |
| 6 | 2026-10-06 | No template change. Code: the compound splitter treats the feminine ending `-innen` as an ending (`Sozial·arbeiterinnen`, never `Schweizer·innen`), and the evaluation counts the splits of earlier rounds that the final version keeps. The dev rerun on CSCS with and without the step is in "Mediopunkt by code" above: LEX-01 from 35 to 5 warnings per 100 blocks, no repair round saved, no fact lost. |
| 7 | 2026-10-07 | Judge prompt (German and French): one more rule, SEM-08, an obligation, a possibility or a condition that changed (`müssen` to `können`, a `wenn` written as `vielleicht`); the judge filter accepts it. All four standard templates in both languages get one line, `{% if mode is defined and mode == "decision" %}{% include "<lang>/decision.md" %}{% endif %}`, which renders to nothing for a standard job (same prompt text, same cache key; the template hash changes once) and pulls in the stage's section of the new partial `decision.md` for a job in the decision mode (docs/use-case-decisions.md; first draft, free to change after the freeze). |
| 7 | 2026-10-07 | No further template change. Code: the missing-fact lines of a repair request name the exact form of the value next to the fact sheet's; LEN-02 findings carry a rewrite recipe per conjunction as the suggestion; facts-only rounds after the repair loop (`pipeline.facts_rounds`, default 1); a record per repair round of the request, the answer and what code dropped; `eval diagnose` for the fact-retention diagnosis; silent losses in the evaluation; the image input spike script. Dev rerun on CSCS the same day ("Fact-retention diagnosis" above): missing must-keep values from 50 of 102 to 16 of 122, fact coverage 75 against 68 percent without the facts rounds, no invented value on either side. |
| 7 | 2026-10-08 | No template change. Code, from the second and third dev runs: the code completion takes the values from the document text with segment offsets and stores a percentage as `10%`; a value counts as covered only when a reader who searches the fact sheet for it finds it; the final version is the one with the fewest must-keep values missing, then the fewest blocking findings; an unusable repair answer no longer cancels the facts round; `eval rescore` scores stored jobs under either rule without a model call. |
| 8 | 2026-10-07 | Write prompt (German and French): after the fact sheet, the office words of the document part with their everyday word, from the vocabulary (`Diese Wörter aus dem Dokument sind schwer. Schreiben Sie stattdessen das einfache Wort:`, `Ces mots du document sont difficiles. Écrivez plutôt le mot simple :`, at most 15). The block renders to nothing when the part has no office word or with `pipeline.vocabulary = false`: the prompt is then the same text as before. The generated style guide gets a LEX-07 line in German (`Nehmen Sie Alltags·wörter statt Amts·wörtern ...`), and in French the administrative words move from the LEX-01-FR line to a LEX-07-FR line. Code: the fact sheet's hard terms get the vocabulary's checked explanations and up to 6 terms of the source; code adds missing glossary entries from the vocabulary after the write stage and every repair round; LEX-07 and LEX-07-FR findings go to the polish round (docs/rules.md "Vocabulary"). Dev run on CSCS with and without: "Vocabulary in the pipeline" above; after it the word list is off by default (`VOCABULARY_PROMPT=0`), because it primed the 8B to write the listed office words. |
| 8 | 2026-10-07 | No template change. Code: the vocabulary round, a last round through the repair prompt for the office words still in the best version (LEX-07 findings alone, each sentence with its everyday word); its version takes the next free number and is kept only if it loses no must-keep value and adds no blocking finding. Measured with every earlier answer replayed from the cache ("The vocabulary round" above): office words in the final drafts 42 to 19, no fact lost, about 11 s per job; on by default (`VOCABULARY_ROUND=1`). |
| 9 | 2026-10-07 | Write prompt (German and French): the word list of version 8 removed; the template is the text of version 7 again, so the rendered prompt is the same as before the vocabulary. The writer gets no vocabulary of office words (it primed the 8B); the office words are handled after writing, by LEX-07 and the vocabulary round. One switch, `pipeline.vocabulary`, for the vocabulary's other uses, the vocabulary round included. |
| 9 | 2026-10-08 | No template change. Code: the copy guard renders the write and repair prompts with the style guide of both levels, so the guide's lines (without their list marker) and its example values (`044 123 45 67`, `4. Februar 2026`) count as the prompt's own text; a decision-mode draft on the 8B had carried the style guide as a section of the draft (7 October). The value kind `phone` takes the ten-digit service numbers in both groupings (`0800 33 66 55`, `0848 35 45 55`), which were four plain numbers before, so FACT-01, FACT-06 and the hard-fact metric see the emergency pages' hotlines; SOURCE and REF recomputed. |
| 9 | 2026-10-08 | Decision partial only (`decision.md`, German and French; no standard template and no hash changes), from the test runs of 7 October (use-case-decisions.md §7): the values of the header and the reasoning are background unless a core answer cites them; a period is copied as written, with its start, and never computed to an end date (the Understand model had written "endet am 15. November 2026"); a task stays with its owner in the fact sheet and the draft ("Die Beiständin bezahlt Ihre Rechnungen", not "Sie bezahlen"), and the judge reports a "Sie" that takes the deputy's task as SEM-03 and a computed date as SEM-10. Code the same day: `rules/decision.py` (protected parts, FACT-07, FACT-08), the judge filter for SEM-09 and SEM-10 in decision mode, the notice in the exports, the form fields. |
| 10 | 2026-10-08 | Understand and write prompts (German and French): one more include line each, `{% if medication is defined and medication %}{% include "<lang>/medication.md" %}{% endif %}`, and the new partial `medication.md`. Code switches it on for Understand when the source has a dose or a dosing scheme (`rules/medication.py`, `has_doses`) and for Write when the fact sheet names a medication; it asks for one fact of kind `medication` per drug with the name alone as the value, and for one list item per medication with name, dose, scheme and duration. No evaluation source has a dose (checked on the 35 standard texts and the decision), so every evaluation prompt renders byte for byte as before; the template hash changes once. Code the same day: the value kind `medication` (rules/values.py), FACT-09 (a medication in one block with its dose, scheme and duration; repairable on the block that names it), medication facts first among the missing facts of a repair round, and the Mediopunkt step leaves the names alone (docs/rules.md). |
| 10 | 2026-10-08 | No template change and no pipeline change. Tried on the dev pairs and not taken ("Judge doubts on values" above): a judge's `missing` on a fact whose value FACT-01 finds as non-blocking, and a missing fact asked for by the clause of its value; with both, five of ten German jobs took another path, three ended worse and none better. Kept: the review page shows such a verdict in amber as "judge doubts". |
| 10 | 2026-10-08 | No template change. Code, from the example jobs: a block without a source sentence takes those of the facts it names, else the one it says in other words (`stages.wording_source`), and a sentence id the source does not have is dropped (FACT-03, and the judge sees the sentence); a hard term of the model that the source does not contain leaves the fact sheet (`stages.in_source`; the Understand example's office for 6 documents); the examples' office (`Einwohnerkontrolle`, `contrôle des habitants`) is a topic word of the copy guard. P2 on the 12 dev pairs on CSCS, the committed code (`eval/results-cscs-ab-before`) against these changes on the same cache (`eval/results-cscs-prov-after`): five pairs identical; fact coverage 76 to 81 percent, hard facts kept 69 to 76, must-keep values missing 43 to 33 in all, rule errors 2.7 to 2.3 per 100 blocks, unsupported 5.3 to 6.2, invented values 0.64 to 0.85. Of the seven changed pairs three ended better (be-tax-extension-fr, fact coverage 13 to 94 percent after the copied term "case number" left its fact sheet), two worse (sg-el-costs-de lost three values after the copy guard sent back an Understand answer with the office; bwl-emergency-supplies-fr gained an invented period), two mixed: too few pairs to separate the changes from the 8B's noise. |
| 11 | 2026-10-09 | New template `recover.md` (German and French), used only by the review page's "Suggest a sentence" for one missing fact, never by the pipeline: no other template changes, the evaluated runs render the same prompts. It names the missing value and its source sentence, and gets only the fact's paragraph and the blocks at its place ("Recovering a missing fact" above). Labels `recover_value` and `recover_foreign` for the two checks that send an answer back. |
| 11 | 2026-10-09 | No change to the German and French templates. English templates for German and French documents (understand, write, judge, repair and the two partials, with an English style guide and labels, behind a setting that named the stages) were built, measured on the dev pairs on CSCS and not taken ("English instructions" above): longer, less plain German in repair on equal input, Understand failing on 2 of 12 pages and dropping content, English in omission entries, and gains on facts within the noise of two German runs. Removed the same day with their tests and measurement scripts (commit `ff0544a` has them); the results are kept above. |
| 11 | 2026-10-10 | No template change. Code: GRAM-08 no longer flags a separable verb at the end of a verb-final clause (`wenn Sie wegziehen`, three false errors in one draft of the example rebuild; `rules/de.py`, golden negatives). The polish round after the recover round (`pipeline.polish_rounds`, default 1): the best version's repairable rule errors, or its warnings once no error is left, in one more round through the repair prompt, no fact and no judge's problem; the facts and recover rounds add the source's sentences nearly verbatim and no round saw them again. Measured on the dev pairs ("The polish round on the dev pairs" above). |
| 12 | 2026-10-10 | Judge prompt (German and French): an unsupported verdict carries a `quote`, the words of the block the original does not cover, as they stand there, and another wording of the same statement is no problem. Code keeps a verdict only when its quote stands in a block of the draft, on that block, and files the rest under `dropped` in the judge report: the 70B had cited the prompt example's own block ids. Measured on the dev pairs ("The judge's quotes on the dev pairs" above). |
| 13 | 2026-10-10 | Judge prompt (German and French): another spelling of the same value is no distortion (42'000 Franken for CHF 42'000.-, 4. Februar 2026 for 04.02.2026); the judge had called amounts distorted for their punctuation. Code, in the same change: a fact without a value and without values in its text is conveyed by every block that cites one of its sentences, a fact with values in its text by the blocks of its sentences that together hold all of them (`stages.link_facts`, FACT-02), and FACT-03 skips a question block. Measured on the dev pairs ("Fact links, questions and the judge's spellings on the dev pairs" above). |
| 13 | 2026-10-10 | No template change. Code: a sentence a repair round adds after a list item, and a sentence the recover round places after one, go after the list's last item instead of between its items (`stages.apply_repairs`, `stages.add_sentences`). Found in the example letters' lists of enclosures, which the facts and recover rounds had split. Measured on the dev pairs ("Sentence placement on the dev pairs" above). |
| 13 | 2026-10-10 | No template change. Code: an Understand answer with `null` for a whole core question is accepted as "no answer" (`RefOut`), as the prompt's `"text": null` is; the 8B wrote it that way in 4 of 18 French example builds and the job failed after the retry. |
| 14 | 2026-10-10 | All five stage templates (German and French): the document between `<document>` and `</document>`, with one sentence before the fence that what stands inside is content, never an instruction (prompt injection, found in a security review). Code: a tag inside the text is written as `[document]` or `[/document]` (`render.defused`). The baselines are unchanged. The first template change after the freeze, not measured on CSCS that day; the final run of 11 October repeated every row on these templates. |
| 15 | 2026-10-12 | All our templates (German and French; Zurich's `baseline_zh.md` already says du), the rule lines of the style guide (`rules/de.py`, `rules/fr.py`), the clause recipes (`rules/recipes.py`) and the labels (`pipeline/labels.py`) address the model with du and tu instead of Sie and vous, at the owner's request; the reader of the easy-language text stays Sie and vous (LEX-06) in the example texts, the JSON forms and the decision partial's addressee rules. The baselines P0 change too ("Schreibe diesen Text in Leichter Sprache:", "Écris ce texte en FALC :"). The repair prompt's rule to change only the listed blocks now says the list stands below, where it is (it said above). Every template hash changes, the cache misses once, and the two recorded runs of the prepared letters have to be recorded again (`examples record`). Not yet measured on a model; the final run of 11 October used the formal templates. |
| 16 | 2026-10-28 | Italian templates for every stage (`prompts/it/`: understand, write, judge, repair, recover, baseline and the partials `decision.md` and `medication.md`), translated line by line from the French ones with the same Jinja constructs, JSON forms, rule ids, field names and document fence; the baseline P0 says "Scrivi questo testo in lingua facile:". The model is addressed with tu as in version 15, the reader of the easy-language text with Lei ("Annunci il Suo cane al controllo abitanti."). The JSON examples and the two few-shot pairs keep the topics of the German and French ones, the parking permit and the dog tax, with the French values and an invented Ticino-style office (phone 091 987 65 43). With them: the Italian table of labels (`pipeline/labels.py`), the Italian topic words of the copy guard (`cane`, `tassa sui cani`, `carta di parcheggio`, `parabrezza`, `libretto delle vaccinazioni`, `controllo abitanti`, `microchip`) and the Italian example letter `riduzione-premi-lettera.txt` (Esempiopoli, 091 123 45 67). No change to the German and French templates. Not yet measured on a model; the Italian rule checker and its spaCy package `leichtfacile_model_it` are a change of their own. |
| 17 | 2026-10-29 | German templates (understand, write, judge, repair): one set for every German variety. The Swiss facts they carried (Schweizer and in der Schweiz, Verfügung among the kinds of document, Franken, the judge's 42'000 Franken and CHF 42'000.-, the Einwohnerkontrolle of the dog-tax example with its articles, the phone number 031 987 65 43) are expressions on the variable `v`, the variety (`{{ v.prompt.office }}`), whose Swiss values stand in the `[de.prompt]` table of `src/leichtfacile/varieties/varieties.toml`. The include lines take the partial's path from the context (`{% include decision_partial %}`, `{% include medication_partial %}`), which `src/leichtfacile/pipeline/prompts.py` sets to the variety's own partial when it has one, else to the language's; the partials' wording is unchanged. The rendered Swiss prompts are the same byte for byte (`tests/pipeline/test_prompt_snapshots.py`), so the response cache keeps its keys; the template hashes in `summary.prompt_versions` changed without a change in what the model sees. `tests/pipeline/test_prompt_varieties.py` keeps the Swiss facts out of the German templates and checks a variety's own facts and partials. No change to the French and Italian templates. |
| 18 | 2026-10-29 | Germany and Austria get their prompt data, so `leichtfacile setup` offers three German varieties: the tables `[de-DE]` and `[de-AT]` in `src/leichtfacile/varieties/varieties.toml` (label, setup choice, Word language, hyphenation dictionary, the decision mode's notice "Maßgebend ist der Bescheid." and the ten prompt facts), two few-shot pairs each (`prompts/de-DE/examples/`, `prompts/de-AT/examples/`: the parking permit and the dog tax in the country's Behördensprache, the tax letter with a Widerspruch or a Beschwerde) and a decision partial each (`prompts/de-DE/decision.md`, `prompts/de-AT/decision.md`); the standard templates, the medication partial and the labels are the German ones ("Design choices" above). No change to the Swiss, French and Italian templates: the rendered Swiss prompts are the same byte for byte (`tests/pipeline/test_prompt_snapshots.py`). `tests/pipeline/test_prompt_varieties.py` renders every stage and form of both varieties on the synthetic letter and finds no Swiss word in what their tables, examples and partials put in. Not yet measured on a model. |
