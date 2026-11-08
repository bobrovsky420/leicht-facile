# Example documents

The example documents live in two folders. The example letters the app offers are the
package leichtfacile-samples, a dependency of the app, in
[`samples/leichtfacile_samples/letters/`](../../samples/leichtfacile_samples/letters/),
with the recorded runs the web app answers them from; [samples/README.md](../../samples/README.md)
describes them. This folder, `data/examples/`, holds the printed letters of the image
input spike in `data/examples/print/` (below).

## Printed letters (image input)

`data/examples/print/` holds two more letters, made for the image input spike ([image-input.md](../../docs/image-input.md)): each as a
PDF to print and as the printed text in reading order (`.txt`: blocks separated by a
blank line, table cells by a tab), the reference a transcription is compared with.
`uv run python scripts/print_letters.py` writes all four files again, byte for byte the
same. Everything in them is invented as in the sample letters, and so are the people and the streets;
the IBANs carry the check digits 00 and the AHV number a wrong check digit, so none of
them can belong to anyone.

| File | Content | What it tests |
|------|---------|---------------|
| `print/steuermahnung-brief.pdf` | German, 1 page: first reminder for unpaid taxes | A table of amounts with a negative line and a bold total, an IBAN, a tax number, dates and a payment deadline, a percentage, office hours, a drawn signature |
| `print/bourse-etudes-decision.pdf` | French, 2 pages: registered decision granting a study grant | A reference block with an AHV and a file number, a calculation table, two payment dates, periods of 14 and 30 days, a running header on page 2, the means of appeal in small print, two signatures |

Print at 100 % (not "fit to page") and fold in three along the marks on the left edge,
as for a window envelope. Scan to JPEG or PNG, or to a PDF without OCR: a scanner's
searchable PDF carries its own text layer, which the PDF ingest would read instead of
Apertus.

Scans and photos go to `print/scans/`, named `<letter>_<capture>` with the letter's
file name in front, so a test pairs each with its `.txt`. A scan is the scanner's PDF
with all pages of the letter in order; photos are JPEGs, one per page, with `_p<page>`
(`steuermahnung-brief_photo-dim_p1.jpg`). A page scanned at 300 dpi is 0.5 to 0.8 MB.

| File | Capture |
|------|---------|
| `print/scans/steuermahnung-brief_scan.pdf` | 7 October 2026: printed, folded in three, flatbed scan at 300 dpi in colour (Canon), 1 page. One crease runs along the top of the subject line, one through the last line of the paragraph on instalments |
| `print/scans/bourse-etudes-decision_scan.pdf` | The same, 2 pages in one file. On page 1 a crease runs through the IBAN line (`CH00 0571 2009 4417 6382 9`); page 2 is slightly skewed |

Each page of these PDFs is one JPEG (2480 x 3507 pixels) and the PDFs have no text
layer, so the PDF ingest refuses them as scans. A test takes the page JPEGs out
unchanged (pdfplumber: `page.images[0]["stream"].get_rawdata()`), without rendering
or re-encoding.

Texts from cantonal or federal web pages are stored in neither folder: their
publishers do not allow reproduction (docs/sources.md §4). The evaluation fetches them
into the git-ignored `data/cache/` instead.
