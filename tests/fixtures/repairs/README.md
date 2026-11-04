# Recorded repair rounds

Replay cases of `stages.apply_repairs`, the function that makes the new draft version
out of a repair round's answer: for each, the version the round started from, the
job's fact sheet, the blocks and facts the round asked for, the model's answer as code
applied it (the example sentences `stages.repair` drops already taken out), and what
the function made of it with the code of the day of the export, the new version and
the sentences left out with their reasons. `tests/pipeline/test_repair_replay.py`
replays every case and compares both outputs, so a change of the function that alters
an output fails there. A deliberate change exports the cases again in the same commit
(`uv run python scripts/repair_fixtures.py`, from the job store of a checkout with
`llm.cache = true`), and the diff of the fixtures shows the reviewer what changed.

The rounds are real answers of the models named below on the shipped example letters
(`src/leichtfacile/letters/`, invented senders and people); the jobs ran on the days
named. The expected outputs are not what the pipeline stored then: the function is
replayed with the current code at the export, and a case marked in the last column
has a list of dropped sentences unlike the one its record holds (`recorded_dropped` in
the file), the rules that changed since the job ran. The sentence splitting the
function uses comes from the spaCy models the package depends on, so a model bump that
moves a sentence boundary shows up here first; the stems it compares are the first
letters of the words, no model.

Kept: 15 of the 114 replayable rounds of the store: a small set, chosen greedily, that runs every branch of `stages.py` any of them runs, plus one round per shape of answer, per variety and round kind, and per letter. Exported with 0.11.0.

| Case | Letter | Kind | Model | Day | Blocks in | Blocks out | Dropped | Differs |
|------|--------|------|-------|-----|-----------|------------|---------|---------|
| `camp-de-classe-lettre-parents-a9c9516b-v02-repair` | camp-de-classe-lettre-parents.txt | repair | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 23 | 24 | 6 | yes |
| `camp-de-classe-lettre-parents-a9c9516b-v06-vocabulary` | camp-de-classe-lettre-parents.txt | vocabulary | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 32 | 33 | 0 |  |
| `klassenlager-elternbrief-8579f981-v03-facts` | klassenlager-elternbrief.txt | facts | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 24 | 24 | 2 | yes |
| `praemienverbilligung-brief-3dc9ebd2-v02-repair` | praemienverbilligung-brief.txt | repair | claude-haiku-5-5 | 2026-10-26 | 32 | 39 | 4 | yes |
| `schnupperwoche-schuelerbrief-3acf822c-v06-polish` | schnupperwoche-schuelerbrief.txt | polish | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 29 | 29 | 0 |  |
| `schnupperwoche-schuelerbrief-7acc6d5a-v03-repair` | schnupperwoche-schuelerbrief.txt | repair | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 32 | 31 | 3 |  |
| `schnupperwoche-schuelerbrief-a9d39c54-v04-vocabulary` | schnupperwoche-schuelerbrief.txt | vocabulary | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 22 | 23 | 0 |  |
| `semaine-de-stage-lettre-eleves-17591eff-v04-polish` | semaine-de-stage-lettre-eleves.txt | polish | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 28 | 30 | 0 |  |
| `semaine-de-stage-lettre-eleves-5f778912-v03-facts` | semaine-de-stage-lettre-eleves.txt | facts | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 24 | 32 | 6 | yes |
| `settimana-di-stage-lettera-allievi-92d0f0d8-v04-facts` | settimana-di-stage-lettera-allievi.txt | facts | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 29 | 31 | 1 |  |
| `settimana-di-stage-lettera-allievi-92d0f0d8-v07-vocabulary` | settimana-di-stage-lettera-allievi.txt | vocabulary | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 33 | 32 | 1 |  |
| `settimana-verde-lettera-genitori-41a86f91-v02-repair` | settimana-verde-lettera-genitori.txt | repair | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 30 | 32 | 26 |  |
| `settimana-verde-lettera-genitori-41a86f91-v03-repair` | settimana-verde-lettera-genitori.txt | repair | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 32 | 34 | 11 |  |
| `settimana-verde-lettera-genitori-c1015be7-v05-polish` | settimana-verde-lettera-genitori.txt | polish | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 32 | 32 | 0 |  |
| `settimana-verde-lettera-genitori-dec3544d-v02-repair` | settimana-verde-lettera-genitori.txt | repair | swiss-ai/apertus-v1.5-70b | 2026-10-31 | 37 | 41 | 20 | yes |
