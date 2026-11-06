"""The shared spaCy pipelines (rules/nlp.py)."""

from __future__ import annotations

import threading
import time

from leichtfacile.pipeline.stages import text_to_blocks
from leichtfacile.rules.checker import get_checker
from leichtfacile.rules.mediopunkt import apply_mediopunkt
from leichtfacile.rules.nlp import pipeline
from leichtfacile.rules.vocabulary import matcher
from leichtfacile.schemas import Block, Draft


def test_every_caller_of_a_shared_pipeline_takes_its_one_lock(monkeypatch) -> None:
    """The worker threads and the web requests share the German pipeline through the
    de-CH and de-DE checkers, the vocabulary matcher, the code splitting and the block
    split of free text: one text at a time. The checkers had a lock each, so de-CH and
    de-DE ran the pipeline at once, and the others took none."""
    nlp = pipeline("de")
    real, guard = nlp.pipe, threading.Lock()
    inside, most, errors = [0], [0], []

    def pipe(texts, *args, **kwargs):
        with guard:
            inside[0] += 1
            most[0] = max(most[0], inside[0])
        try:
            time.sleep(0.005)  # widens the window two callers could share
            return list(real(texts, *args, **kwargs))
        finally:
            with guard:
                inside[0] -= 1

    monkeypatch.setattr(nlp, "pipe", pipe)
    blocks = [Block(id="b001", kind="sentence", text="Die Krankenversicherungspolice kommt.")]
    draft = Draft(doc_id="d", lang="de", level="A2", blocks=blocks)
    calls = [
        lambda: get_checker("de-CH").analyse(blocks),
        lambda: get_checker("de-DE").analyse(blocks),
        lambda: matcher("de-CH").find_text("Sie erhalten eine Verfügung."),
        lambda: apply_mediopunkt(draft),
        lambda: text_to_blocks("Ein Satz. Noch ein Satz.", "de"),
    ]

    def run(call) -> None:
        try:
            call()
        except Exception as exc:  # noqa: BLE001  (reported by the assertion below)
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(call,)) for call in calls * 4]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert not errors and most[0] == 1, (errors, most)
