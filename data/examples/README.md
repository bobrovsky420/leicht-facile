# Example documents

Texts in `sources/` are written by the team for testing and demonstration. They imitate
the style of Swiss official letters but describe no real authority: the municipalities
Musterwil and Exempleville are invented, the web and e-mail addresses use the reserved
`.example` domain, and 044 123 45 67 and 022 123 45 67 are example numbers in the style
of Swiss style guides.

| File | Content | Use |
|------|---------|-----|
| `sources/praemienverbilligung-brief.txt` | Letter about health insurance premium reduction: income limits, a deadline, documents to enclose, objection period, contact | Smoke test (`make smoke`), day-1 check 3, example job |
| `sources/reduction-primes-lettre.txt` | The same letter in French (réduction individuelle des primes) | French test runs, French example job |

Texts from cantonal or federal web pages are not stored here: their publishers do not
allow reproduction (docs/sources.md §4). The evaluation fetches them into the
git-ignored `data/cache/` instead.
