"""A synthetic letter and hand-written model answers for pipeline tests.

The answers are written by hand in the shape the prompts ask for. They are not
recorded model output; recorded fixtures follow once the endpoint is available.
"""

from __future__ import annotations

import json

from leichtfacile.schemas import Segment, SourceDocument, SourceInfo


def letter() -> SourceDocument:
    texts = [
        ("heading", "Prämienverbilligung 2026", 1, 0),
        (
            "paragraph",
            "Personen mit geringem Einkommen haben Anspruch auf eine Prämienverbilligung.",
            None,
            1,
        ),
        (
            "paragraph",
            "Das Gesuch ist bis spätestens 31. März 2026 bei der Gemeinde einzureichen.",
            None,
            1,
        ),
        ("paragraph", "Für die Bearbeitung wird eine Gebühr von CHF 20.- erhoben.", None, 2),
        ("paragraph", "Auskunft erteilt das Sozialamt unter Telefon 044 123 45 67.", None, 3),
        ("paragraph", "Rechtsgrundlage ist Art. 5 des Einführungsgesetzes.", None, 4),
    ]
    segments = [
        Segment(id=f"s{i:04d}", kind=k, text=t, heading_level=h, para=p,
                heading_path=[] if k == "heading" else ["Prämienverbilligung 2026"])
        for i, (k, t, h, p) in enumerate(texts, 1)
    ]  # fmt: skip
    return SourceDocument(
        id="doc-letter", lang="de", title="Prämienverbilligung 2026",
        source=SourceInfo(type="text"), segments=segments,
    )  # fmt: skip


UNDERSTAND = {
    "doc_type": "Merkblatt",
    "audience": "Personen mit wenig Einkommen",
    "core": {
        "what": {"text": "Der Kanton bezahlt einen Teil der Prämie.", "segment_ids": ["s0002"]},
        "must_do": {"text": "Ein Gesuch an die Gemeinde schicken.", "segment_ids": ["s0003"]},
        "deadline": {"text": "Bis 31. März 2026.", "segment_ids": ["s3"]},
        "cost": {"text": "Gebühr 20 Franken.", "segment_ids": ["s0004"]},
        "contact": {"text": "Sozialamt, 044 123 45 67.", "segment_ids": ["s0005"]},
    },
    "facts": [
        {"id": "f1", "kind": "Deadline",
         "text": "Das Gesuch muss bis 31. März 2026 bei der Gemeinde sein.",
         "value_norm": "2026-03-31", "segment_ids": "s0003", "must_keep": True},
        {"id": "f2", "kind": "amount", "text": "Die Gebühr ist 20 Franken.", "value_norm": "20",
         "segment_ids": ["s0004"], "must_keep": True},
        {"id": "f3", "kind": "contact",
         "text": "Das Sozialamt hat die Telefonnummer 044 123 45 67.",
         "value_norm": "0441234567", "segment_ids": ["s0005"]},
    ],
    "hard_terms": [
        {"term": "Prämienverbilligung", "explanation": "Der Kanton bezahlt einen Teil."}
    ],
    "omit_candidates": [{"segment_ids": ["s0006"], "reason": "Gesetzesartikel"}],
}  # fmt: skip

WRITE = {
    "blocks": [
        {"kind": "heading", "text": "Was müssen Sie tun?"},
        {"kind": "sentence", "text": "Das Gesuch muss bis 31. März 2026 eingereicht werden.",
         "fact_ids": ["f01"], "segment_ids": ["s0003"]},
        {"kind": "sentence", "text": "Das kostet 20 Franken.", "segment_ids": ["s0004"]},
        {"kind": "sentence", "text": "Rufen Sie das Sozial·amt an: 044 123 45 76.",
         "fact_ids": ["f03"], "segment_ids": ["s0005"]},
        {"kind": "sentence", "text": "Sie haben wenig Geld.", "segment_ids": ["s0002"]},
    ],
    "omissions": [{"what": "Gesetzesartikel", "why": "nicht nötig", "segment_ids": ["s0006"]}],
    "glossary": [{"term": "Prämien·verbilligung", "explanation": "Der Kanton bezahlt einen Teil."}],
}  # fmt: skip

JUDGE_FIRST = {
    "fact_checks": [
        {"fact_id": "f01", "status": "present", "block_ids": ["b002"]},
        {"fact_id": "f02", "status": "present", "block_ids": ["b003"]},
        {"fact_id": "f03", "status": "distorted", "block_ids": ["b004"],
         "note": "Die Nummer ist falsch."},
    ],
    "unsupported": [],
    "semantic_findings": [{"block_id": "b005", "rule_id": "sem-3", "note": "Unklar."}],
}  # fmt: skip

REPAIR = {
    "repairs": [
        {"id": "b002", "texts": ["Schicken Sie das Gesuch an die Gemeinde.",
                                 "Das Gesuch muss bis 31. März 2026 dort sein."]},
        {"id": "b004", "texts": "Rufen Sie das Sozial·amt an: 044 123 45 67."},
        {"id": "b005", "texts": ["Sie haben wenig Geld?"]},
    ],
    "additions": [],
}  # fmt: skip

JUDGE_SECOND = {
    "fact_checks": [
        {"fact_id": "f01", "status": "present", "block_ids": ["b002.1"]},
        {"fact_id": "f02", "status": "present", "block_ids": ["b003"]},
        {"fact_id": "f03", "status": "present", "block_ids": ["b004"]},
    ],
}

BASELINE_TEXT = """# Prämien·verbilligung

Sie haben wenig Geld?
Dann bekommen Sie Geld für die Kranken·kasse. Sie müssen ein Gesuch schicken.

- Bis 31. März 2026
- Gebühr: 20 Franken
"""


def as_json(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False)
