# Third-party notices

## simply-simplify-language (Canton of Zurich)

`src/leichtfacile/llm/prompts/de/baseline_zh.md` reproduces, verbatim, the Leichte
Sprache prompt of the Canton of Zurich's app "simply-simplify-language": the system
message, the user template, the rule list and the two completeness instructions
(`SYSTEM_MESSAGE_LS`, `TEMPLATE_LS`, `RULES_LS`, `REWRITE_COMPLETE` and
`REWRITE_CONDENSED` in `_streamlit_app/utils_prompts.py`), version 1.6.0, commit
`5462559`, https://github.com/machinelearningZH/simply-simplify-language.

It serves as the single-prompt baseline C0-ZH in the evaluation (docs/architecture.md,
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
