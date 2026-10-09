# Image input: what Apertus 1.5 reads from a scanned official letter

*Measured on the CSCS inference API on 7 and 9 October 2026 with `swiss-ai/Apertus-v1.5-8B`
and `-70B`, on two printed, folded and flatbed-scanned letters. Written for the jury of
Hack Apertus and for anyone who wants to feed Apertus 1.5 a photo or a scan of a letter
that carries phone numbers, e-mail addresses, account numbers or names.*

## Summary

Apertus 1.5, as served on the CSCS API in October 2026, cannot be trusted to read an
official letter from an image when every character of a value matters. Three findings:

1. **A whole page arrives too small.** The server keeps at most about 1400 x 1400 pixels
   of an image, whatever is uploaded. An A4 scan at 300 dpi is read at about 140 dpi,
   and at that size both models turn digits into other digits: an IBAN into another
   IBAN, an AVS number into another AVS number, a 78-day period into 76 days, a
   postcode 1999 into 1899. The errors look right.
2. **Cut into strips at the scan's own resolution, the 8B reads every digit right,
   three runs out of three, on both letters.** The 70B does not: it still misreads one
   AVS digit, writes an IBAN with a hyphen, and dropped a whole paragraph once.
3. **Letters in names, e-mail addresses and web addresses are not safe in any
   setting.** The 8B replaces an unfamiliar word by a familiar one: the invented place
   name `Exempleville` becomes `Exampleville` in 8 of its 10 occurrences, inside the
   e-mail addresses and the web address too; `Musterwil` becomes `Mustervil` in half
   of its occurrences; a surname under a signature loses a letter. The 70B keeps the
   names but not the digits. No model and no setting got both.

For a system whose promise is that every fact value survives exactly, this is a no-go
for image input without a human check against the paper. A wrong e-mail address that
looks right sends a person to nobody; a wrong IBAN that looks right sends money to the
wrong account. The one honest use today: the 8B in strips as a first reading for a
reviewer who checks every name, e-mail and web address against the original.

## What we needed

Leicht·Facile drafts easy-language versions of official texts and promises that every
fact value of the source (dates, amounts, deadlines, account numbers, contact details)
survives into the draft exactly, checked by code. Letters reach people on paper. The
question of this spike (PLAN.md WP12, decision D-N): can a photo or a scan of a letter
be transcribed by Apertus 1.5 itself, so that the pipeline has no second model and no
OCR engine? The rule set in advance: stop if a hard value is lost. A value that is
transcribed as another plausible value is worse than a page that is declined, because
the error is silent.

## What we tested

- **Two letters, invented from scratch** (`scripts/print_letters.py`, text and PDF in
  `data/examples/print/`): a German tax reminder, one page (a table of amounts, an
  IBAN, a tax number, deadlines, opening hours, two phone numbers, two e-mail
  addresses, a web address) and a French grant decision, two pages, registered (an AVS
  number, a file number, a calculation table, an IBAN, payment dates, periods, the
  means of appeal). The names, the place names, the IBANs and the AVS number are
  invented; the IBANs and the AVS number have invalid check digits on purpose.
- **Printed, folded in three, scanned** on a Canon flatbed at 300 dpi in colour, saved
  by the scanner as a PDF with one JPEG per page (2480 x 3507 pixels), no text layer
  (`data/examples/print/scans/`). The creases cross the German subject line and the
  French IBAN line.
- **One prompt per language**, "transcribe the text word for word, change no number,
  date or name, one line per table row, answer `unlesbar`/`illisible` if the image
  cannot be read" (`src/leichtfacile/eval/image_spike.py`), the image as a base64
  JPEG in an OpenAI-style `image_url` part, temperature 0, no thinking, the response
  cache off.
- **Settings:** the whole page scaled to a long side of 1,600 pixels (7 October); the
  whole page at full size; the printed area only; the printed area cut at blank rows
  into horizontal strips of under 1.9 million pixels each (`scripts/image_spike.py
  --strips`, five calls per A4 page); the strips in grayscale with autocontrast; the
  strips upscaled 1.5 x; the 8B and the 70B.
- **Measures:** the character error rate against the printed text (Levenshtein over
  whitespace-normalised text), the share of the printed text's hard values found in
  the transcription with the project's own value matcher (which forgives spacing and
  apostrophes in numbers), and, for every lost value, what the transcription has in
  its place. Names, e-mail addresses and web addresses were counted as exact strings.

Not tested: phone photos (the open question the spike was meant to answer), a third
letter, handwriting, an OCR engine on the same scans, an on-premise deployment with a
larger image budget, the `-thinking` variants.

## How the server sees a page

One page, uploaded at different sizes with a five-token prompt, cost these prompt
tokens on CSCS (9 October; about 180 of them are text):

| Long side of the uploaded page | Pixels sent | Prompt tokens |
|---|---|---|
| 448 | 317 x 448 | 666 |
| 800 | 566 x 800 | 1,878 |
| 1,200 | 849 x 1,200 | 4,128 |
| 1,600 | 1,131 x 1,600 | 7,279 |
| 2,000 | 1,414 x 2,000 | 7,879 |
| 2,480 (the scan) | 1,754 x 2,480 | 7,879 |
| 4,000 | 2,829 x 4,000 | 7,879 |

PNG instead of JPEG: the same count. The count stops growing at about 1.96 million
pixels, which is 1400 x 1400. This matches the description of the Apertus 1.5 image
tokenizer in the community port for Apple silicon (mlx-vlm, pull request 1847): a
VQGAN-style tokenizer with one code per 16 x 16 pixel patch and 1712 x 1136 as the
largest image the processor allows. So a whole A4 page scanned at 300 dpi is read at
about 1,177 x 1,664 pixels, about 140 dpi, where a 10-point digit is one or two
patches high. A page at 1,600 pixels is not downscaled at all; it was simply uploaded
small. A strip of the page with fewer than 1.96 million pixels keeps every pixel of the
scan.

## What came back

Hard values found by the value matcher (German letter 21 values, French letter 22),
character error rate in brackets, all without thinking at temperature 0:

| Setting | Model | German tax reminder | French grant decision |
|---|---|---|---|
| Whole page, 1,600 px (7 Oct) | 8B | 0 of 21: the page declined as `unlesbar` | 14 of 22 (0.057) |
| Whole page, full size (7 Oct, 9 Oct twice) | 8B | 15, 16, 16 of 21 (0.060, 0.059, 0.059) | 12, 11, 11 of 22 (0.044, 0.039, 0.064) |
| Whole page, full size (7 Oct) | 70B | 17 of 21 (0.118) | 13 of 22 (0.041) |
| Printed area only, one call per page | 8B | 17 of 21 (0.049) | 15 of 22 (0.086) |
| Strips, three runs | 8B | 20, 20, 20 of 21 (0.011, 0.010, 0.010) | 17, 17, 17 of 22 (0.018, 0.018, 0.022) |
| Strips, grayscale | 8B | 16 of 21 (0.119) | 16 of 22 (0.026) |
| Strips, upscaled 1.5 x | 8B | 20 of 21 (0.035) | 19 of 22 (0.096) |
| Strips | 70B | 17 of 21 (0.091) | 18 of 22 (0.024) |

By kind of value, counted as exact strings over every occurrence in both letters. "8B
strips" is the best setting, three runs; "8B whole page" the two full-size runs of 9
October; "70B strips" one run.

| Kind (occurrences) | 8B strips | 8B whole page | 70B strips |
|---|---|---|---|
| IBAN (2) | 2 of 2, every run | 0 of 2: `CH00 0830 4100 2786 3510 4` for `... 0839 ... 2786 5310 4`; `CH90 0571 ...` | 1 of 2: the French one ends `6382-9` |
| AVS number (1) | right | `755 4716 2083 50`, `733.4716.2083.50` for `756.4719.2083.50` | `756.4719.2088.50` |
| Tax and file numbers (4) | 4 of 4 | 0 of 4: `41 097 738`, `41.997.756` for `41.087.736`; `BE-2026-04137` for `-04187` | 4 of 4 |
| Amounts (15) | 15 of 15, every run | 11 and 4 of 15: `4'586.40`, `4'986.40` for `4'386.40`, `2 429.55` for `2'429.65`; in the second run the French calculation table left out and the amounts written with a decimal comma | 15 of 15 |
| Dates and periods (18) | 18 of 18, every run | 15 of 18 in both runs: `16 août`, `13 août` for `18 août 2026`; `25 février` for `26 février 2027`; `76 Tage` for `78 Tage` | 18 of 18 |
| Times of day (6) | 6 of 6, every run | 6 of 6 | 2 of 6: the paragraph with the opening hours left out |
| Phone numbers (7) | 7 of 7, every run | 6 of 7: `022 123 45 69` for `... 45 68` | 6 of 7: one in the paragraph left out |
| Postcodes (8) | 8 of 8, every run | 2 and 0 of 8: `1899`, `1889` for `1999`; `9639` for `9999` | 7 of 8 |
| Persons' names (8) | 6 or 7 of 8: `Petra Musteri` for `Musterli` once or twice in every run | 4 or 5 of 8: `Belspiel`, `Mustenli`, `Musterrl` | 8 of 8 |
| Street names (6) | 6 of 6, every run | 4 or 5 of 6: `Fitzliweg`, `Fikitivweg` for `Fiktivweg`; `Chemin des Essais 14` once lost | 6 of 6 |
| Place names (18) | 6 of 18: `Exampleville` for `Exempleville` 8 of 10 times, `Mustervil` 4 of 8 | 12 of 18: `Exampleville` 6 of 10 times, `Musterwil` right | 17 of 18 |
| E-mail addresses (7) | 2 of 7: `bourses@exampleville.example`, `marc.modèle@exampleville.example`, `steueramt@mustervil.example` | 2 of 7: `petra.mustenl@`, `bourses@example`, `marc.modèle@example` | 2 of 7 |
| Web addresses (3) | 0 of 3: `www.mustervil.example`, `www.exampleville.example/bourses` | 1 of 3 | 3 of 3 |

Other behaviour worth knowing:

- **Declining.** At 1,600 pixels the 8B answered `unlesbar` to a readable German page
  in four tokens; in grayscale it declined the header strip. A model that declines is
  honest, but it declines readable pages.
- **Dropping.** The 70B left out the paragraph with the opening hours on the German
  page in strips; the 8B left out the French calculation table in one whole-page
  run. Nothing in the output marks the gap.
- **Normalising.** The 8B writes the invented word `Exempleville` as the familiar
  `Exampleville`, reads `Gemeindesteuern` as `Gemeindefteuern` in every strips run
  (a long s that is not on the page) and the bold header `Gemeinde` as `Gemielnde`. In the whole-page setting `Musterwil` is right
  all eight times; in strips, four of eight become `Mustervil`: the header's bold
  `Musterwil` is in another strip, and the model no longer sees the word it would
  copy.
- **Not deterministic.** At temperature 0 the whole-page runs of two days gave
  different wrong digits for the same IBAN; the strips runs differ in line breaks and
  one word.
- **Cost.** A whole page is about 7,900 input tokens and 4 to 6 seconds on the 8B; in
  strips about 30,000 input tokens in five calls of about 1.5 seconds each.

## What it means

- **Digits are a resolution problem, and it can be solved on the client side.** Keep
  every image under the server's budget by cutting the page at blank rows; never send
  a whole page. On the 8B this made every number of both letters come out right. The
  70B gains less from it.
- **Letters in names, e-mail addresses and web addresses are a model problem.** The
  transcription is a language model's best guess, and an unfamiliar word is corrected
  to a familiar one. Invented names in a test letter are an unfair case in one way (no
  real place is called Exempleville) and a fair one in another: real surnames, street
  names and e-mail local parts are exactly the words a model has seen least.
- **The failure is silent.** Nothing in the output marks the changed digit or letter.
  A pipeline that trusts the transcription will carry the wrong value through every
  later check, because the checks compare against the transcription.
- **The two models fail differently.** The 8B keeps the digits and loses the names;
  the 70B keeps the names and loses digits and a paragraph. Combining them would be
  a research project, not a feature.

## Limits of this evidence

Two letters, three pages, one scanner, one API, two days. The letters are synthetic,
in a clean sans-serif font, and their names are invented. Real letters have logos,
stamps, handwriting and worse paper; phone photos have shadows, skew and blur, and
were not tested. We did not run an OCR engine on the same scans, so this report says
nothing about whether a conventional OCR step would do better; that is the obvious
next test. We measured the API as served by CSCS; a self-hosted deployment might set a
larger image budget, with unknown effect on reading quality. All runs were without
thinking; the `-thinking` variants were not tried on images.

## What we recommend

1. For the project: image input stays future work (decision D-N). The report names it
   as such with these numbers.
2. For anyone who builds it anyway: send strips under 1.9 million pixels, never a
   whole page; use the 8B for the reading; treat every name, e-mail address and web
   address as unverified until a person has compared it with the paper; show the
   strip next to the transcription so that the check is quick; and test on phone
   photos before trusting any of this.
3. For the Apertus team, as a user's observation: the image budget of about 1.96
   million pixels is small for documents, and the transcription behaviour of the 8B
   (declining readable pages, normalising unfamiliar words) and of the 70B (dropping
   a paragraph without a trace) would both be worth a line in the model card.

## Files and sources

- Script: `scripts/image_spike.py` (`--strips`), module
  `src/leichtfacile/eval/image_spike.py`, tests in `tests/eval/test_image_spike.py`.
- Inputs: `data/examples/print/` (the letters' text and PDFs) and
  `data/examples/print/scans/` (the scans).
- Results with every transcription: `eval/results/image_spike*.json` (git-ignored,
  on the owner's machine); the tables of every run in `docs/prompts.md`, "Image
  input spike".
- The image tokenizer: pull request 1847 of mlx-vlm, "Add Apertus 1.5 (image + audio +
  text)", github.com/Blaizzy/mlx-vlm/pull/1847 (community port; the official model
  card does not document the image processor). The token counts above are our own
  measurement on api.inference.cscs.ch.
