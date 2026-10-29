# Third-party notices

## simply-simplify-language (Canton of Zurich)

`src/leichtfacile/llm/prompts/de/baseline_zh.md` reproduces, verbatim, the Leichte
Sprache prompt of the Canton of Zurich's app "simply-simplify-language": the system
message, the user template, the rule list and the two completeness instructions
(`SYSTEM_MESSAGE_LS`, `TEMPLATE_LS`, `RULES_LS`, `REWRITE_COMPLETE` and
`REWRITE_CONDENSED` in `_streamlit_app/utils_prompts.py`), version 1.6.0, commit
`5462559`, https://github.com/machinelearningZH/simply-simplify-language.

The prompt is used only for evaluation: it is the single-prompt baseline P0-ZH that
Leicht·Facile is compared against (docs/architecture.md, section 9). It is not part of
the final app: the pipeline that produces Leicht·Facile's own texts never uses it, and
the web UI does not offer it. Nothing else of that app is used; its post-processing is
described in docs/prompts.md.

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

## Morph-it! (the Italian lexicon)

The Italian rule checker tags with Morph-it!, the morphological lexicon of the Italian
language by Eros Zanchetta and Marco Baroni (University of Bologna), version 0.4.8 of
23 February 2009, http://sslmit.unibo.it/morphit: about 505,000 inflected forms with
their lemma and morphological features. Every spaCy Italian model is licensed for
non-commercial use only (CC BY-NC-SA 3.0), which is why the lexicon stands in for a
model. `scripts/lexicon_package.py` turns the lexicon's text file, unchanged in
content, into the lookup table of the pipeline component `morphit`
(`scripts/morphit.py`) inside the package `leichtfacile-model-it`, which the app
depends on like the spaCy models for German and French; the lexicon's readme and the
LGPL text travel inside that package.

Morph-it! is dual-licensed: its readme says that it may be redistributed and modified
under the Creative Commons Attribution ShareAlike 2.0 License and the GNU Lesser
General Public License (the readme's GNU section quotes the wording of the GNU General
Public License, version 2 or later, under the LGPL heading, and the archive ships the
LGPL 2.1 text). Copyright (C) 2004-2009 Marco Baroni and Eros Zanchetta. The lexicon
itself is used, not the code of its tools. Reference: E. Zanchetta and M. Baroni,
"Morph-it! A free corpus-based morphological resource for the Italian language",
Proceedings of Corpus Linguistics 2005, Birmingham.

## Fonts of the web UI

The web UI ships two font families, vendored as woff2 files in
`src/leichtfacile/web/static/fonts/` so that it fetches nothing from another host
(docs/ui-design.md, section 3.4). The files are the `latin` and `latin-ext` subsets of
the Fontsource npm packages, version 5.3.0, unchanged:

| Family | Weights | Package | Licence text |
|--------|---------|---------|--------------|
| Atkinson Hyperlegible Next | 400, 500, 600, 700 | `@fontsource/atkinson-hyperlegible-next` | `OFL-Atkinson-Hyperlegible-Next.txt` |
| Atkinson Hyperlegible Mono | 400, 600 | `@fontsource/atkinson-hyperlegible-mono` | `OFL-Atkinson-Hyperlegible-Mono.txt` |

Atkinson Hyperlegible Next: Copyright 2020-2024 The Atkinson Hyperlegible Next Project
Authors, https://github.com/googlefonts/atkinson-hyperlegible-next. Atkinson
Hyperlegible Mono: Copyright 2020-2024 The Atkinson Hyperlegible Mono Project Authors,
https://github.com/googlefonts/atkinson-hyperlegible-next-mono.

Both are licensed under the SIL Open Font License, Version 1.1; the full text
with each family's copyright notice lies next to the font files. The files are
distributed unmodified, bundled with the software, as the licence permits.
