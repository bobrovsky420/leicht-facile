"""The rendered prompts, frozen: every template of every language, in every form a job
can render it (level, decision mode, medication partial, missing facts), on one
synthetic letter. The snapshots in tests/fixtures/prompts/<lang>.md are the rendered
Swiss prompts byte for byte; a change in a template, a label, the style guide or the
few-shot examples fails here first, and the response cache keys on these very texts.

A deliberate change refreshes the snapshots: UPDATE_SNAPSHOTS=1 uv run pytest
tests/pipeline/test_prompt_snapshots.py. On a failure the rendered text is written next
to the snapshot as <lang>.actual.md for a diff.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from leichtfacile.pipeline import render as r
from leichtfacile.pipeline.models import UnderstandOut
from leichtfacile.pipeline.prompts import PROMPTS_DIR, examples, has_prompt, level_name, render
from leichtfacile.pipeline.stages import mode_context, to_factsheet
from leichtfacile.rules import style_guide
from leichtfacile.schemas import LANGS, Block, Draft
from tests.pipeline import fixtures as fx

SNAPSHOTS = Path(__file__).resolve().parents[1] / "fixtures" / "prompts"
MARKER = "===== "


def rendered_prompts(lang: str) -> dict[str, str]:
    """Every prompt of a language on the synthetic letter, by a name that says the stage
    and the form: `write A2`, `write A2 decision`, `understand A2 medication`, ..."""
    source = fx.letter()
    fs = to_factsheet(UnderstandOut.model_validate(fx.UNDERSTAND), source.id)
    draft = Draft(doc_id=source.id, lang="de", level="A2", blocks=[
        Block(id="b001", kind="sentence", text="Das kostet 20 Franken.", segment_ids=["s0004"]),
        Block(id="b002", kind="sentence", text="Rufen Sie an.", segment_ids=["s0005"]),
    ])  # fmt: skip
    cited = {"s0003", "s0004", "s0005"}
    decision = ("decision", "Frau Muster")
    out: dict[str, str] = {}

    def add(name: str, stage: str, level: str = "A2", mode=("standard", None), **context) -> None:
        # The four standard stages always render with the job's mode (stages.py); the
        # recover and baseline prompts have no mode.
        with_mode = stage in ("understand", "write", "judge", "repair")
        extra = mode_context(stage, *mode) if with_mode else {}
        out[name] = render(
            lang, stage, level_name=level_name(lang, level), level=level, **extra, **context
        )

    source_text = r.source_text(source)
    for level in ("A2", "B1"):
        add(f"understand {level}", "understand", level, source=source_text, medication=False)
        add(f"write {level}", "write", level, style_guide=style_guide(lang, level),
            examples=examples(lang), section="", medication=False,
            factsheet=r.factsheet_text(fs, lang=lang), source=source_text)  # fmt: skip
        add(f"baseline {level}", "baseline", level, text=source.text())
    add("understand A2 decision", "understand", mode=decision, source=source_text,
        medication=False)  # fmt: skip
    add("understand A2 medication", "understand", source=source_text, medication=True)
    add("write A2 decision", "write", mode=decision, style_guide=style_guide(lang, "A2"),
        examples=examples(lang), section="", medication=False,
        factsheet=r.factsheet_text(fs, lang=lang), source=source_text)  # fmt: skip
    add("write A2 medication", "write", style_guide=style_guide(lang, "A2"),
        examples=examples(lang), section="", medication=True,
        factsheet=r.factsheet_text(fs, lang=lang), source=source_text)  # fmt: skip
    add("write A2 section", "write", style_guide=style_guide(lang, "A2"),
        examples=examples(lang), section="die Sätze 1 bis 3", medication=False,
        factsheet=r.factsheet_text(fs, ["f01"], lang),
        source=r.source_lines(source.segments[:3]))  # fmt: skip
    judge = dict(factsheet=r.factsheet_text(fs, lang=lang),
                 source=r.cited_source(source, cited), draft=r.draft_lines(draft, refs=False),
                 glossary=r.glossary_text(draft))  # fmt: skip
    add("judge A2", "judge", **judge)
    add("judge A2 decision", "judge", mode=decision, **judge)
    repair = dict(style_guide=style_guide(lang, "A2"), flagged="[b001] Das kostet 20 Franken.\n"
                  "  - LEN-01: 14 words", factsheet=r.factsheet_text(fs, lang=lang),
                  draft=r.draft_lines(draft, refs=False, marked={"b001"}),
                  source=r.cited_source(source, cited))  # fmt: skip
    add("repair A2", "repair", missing="", **repair)
    add("repair A2 missing", "repair", missing="- f03: Sozialamt, 044 123 45 67.", **repair)
    add("repair A2 decision", "repair", mode=decision, missing="", **repair)
    recover = dict(style_guide=style_guide(lang, "A2"), sentence_ids="[s0005]",
                   fact="- f03: Sozialamt, 044 123 45 67.",
                   paragraph=r.source_lines(source.segments[4:5]),
                   blocks="[b001] Das kostet 20 Franken.\n[b002] Rufen Sie an.")  # fmt: skip
    add("recover A2 value", "recover", value="044 123 45 67", **recover)
    add("recover A2 no value", "recover", value="", **recover)
    if has_prompt(lang, "baseline_zh"):
        for variant in ("complete", "condensed"):
            for part in ("system", "user"):
                out[f"baseline_zh {variant} {part}"] = render(
                    lang, "baseline_zh", part=part, variant=variant, text=source.text()
                )
    return out


def _serialise(prompts: dict[str, str]) -> str:
    return "".join(f"{MARKER}{name}\n{text}\n" for name, text in prompts.items())


def _parse(text: str) -> dict[str, str]:
    parts = re.split(rf"^{re.escape(MARKER)}(.*)\n", text, flags=re.MULTILINE)
    names, bodies = parts[1::2], parts[2::2]
    # The serialiser puts one newline after each text; the text itself ends with one.
    return {name: body[:-1] for name, body in zip(names, bodies, strict=True)}


@pytest.mark.parametrize("lang", [lang for lang in LANGS if (PROMPTS_DIR / lang).is_dir()])
def test_rendered_prompts_match_the_snapshot(lang: str) -> None:
    prompts = rendered_prompts(lang)
    for name, text in prompts.items():
        assert "{{" not in text and "{%" not in text, name
    path = SNAPSHOTS / f"{lang}.md"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1" or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_serialise(prompts), encoding="utf-8", newline="\n")
        return
    expected = _parse(path.read_text(encoding="utf-8"))
    if prompts != expected:
        actual = path.with_suffix(".actual.md")
        actual.write_text(_serialise(prompts), encoding="utf-8", newline="\n")
        changed = [n for n in prompts if expected.get(n) != prompts[n]]
        missing = [n for n in expected if n not in prompts]
        pytest.fail(
            f"the rendered {lang} prompts differ from {path.name} in: {', '.join(changed)}"
            + (f"; gone: {', '.join(missing)}" if missing else "")
            + f". The rendering is in {actual.name}; UPDATE_SNAPSHOTS=1 refreshes the snapshot "
            "when the change is deliberate."
        )
