# Third-party notices

## simply-simplify-language (Canton of Zurich)

`src/leichtfacile/llm/prompts/de/baseline_zh.md` reproduces, verbatim, the Leichte
Sprache prompt of the Canton of Zurich's app "simply-simplify-language": the system
message, the user template, the rule list and the two completeness instructions
(`SYSTEM_MESSAGE_LS`, `TEMPLATE_LS`, `RULES_LS`, `REWRITE_COMPLETE` and
`REWRITE_CONDENSED` in `_streamlit_app/utils_prompts.py`), version 1.6.0, commit
`5462559`, https://github.com/machinelearningZH/simply-simplify-language.

It serves as the single-prompt baseline P0-ZH in the evaluation (docs/architecture.md,
section 9). Nothing else of that app is used; its post-processing is described in
docs/prompts.md.

Licence of that repository:

```
MIT License

Copyright (c) 2026 Canton of Zurich / Department of Justice and Home Affairs / Office for Statistics and Data / Team Data

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Fonts of the web UI

The web UI ships three font families, vendored as woff2 files in
`src/leichtfacile/web/static/fonts/` so that it fetches nothing from another host
(docs/ui-design.md, section 3.4). The files are the `latin` and `latin-ext` subsets of
the Fontsource npm packages, version 5.3.0, unchanged:

| Family | Weights | Package | Licence text |
|--------|---------|---------|--------------|
| IBM Plex Sans | 400, 500, 600 | `@fontsource/ibm-plex-sans` | `OFL-IBM-Plex-Sans.txt` |
| IBM Plex Mono | 400, 600 | `@fontsource/ibm-plex-mono` | `OFL-IBM-Plex-Mono.txt` |
| Atkinson Hyperlegible Next | 400, 700 | `@fontsource/atkinson-hyperlegible-next` | `OFL-Atkinson-Hyperlegible-Next.txt` |

IBM Plex: Copyright 2017-2019 IBM Corp., https://github.com/IBM/plex. Atkinson
Hyperlegible Next: Copyright 2020-2024 The Atkinson Hyperlegible Next Project Authors,
https://github.com/googlefonts/atkinson-hyperlegible-next.

All three are licensed under the SIL Open Font License, Version 1.1; the full text
with each family's copyright notice lies next to the font files. The files are
distributed unmodified, bundled with the software, as the licence permits.
