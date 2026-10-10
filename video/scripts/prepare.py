"""Prepares the inputs that are copied from the repo, not kept in video/: the app's fonts
(public/fonts) and the texts the scenes show word for word, the example letter and the
first blocks of its real P2 draft (src/a). Run from anywhere: python scripts/prepare.py"""

import json
import os
import shutil
from pathlib import Path

VIDEO = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("LF_REPO", VIDEO.parent))  # set it when building outside the repo
TRACK = REPO / "track_2b"
OUT = VIDEO / "src" / "a"
OUT.mkdir(parents=True, exist_ok=True)

FONTS = VIDEO / "public" / "fonts"
FONTS.mkdir(parents=True, exist_ok=True)
for font in (TRACK / "src/leichtfacile/web/static/fonts").glob("*latin-[4-7]00-normal.woff2"):
    shutil.copy2(font, FONTS / font.name)

text = (TRACK / "data/examples/sources/praemienverbilligung-brief.txt").read_text(encoding="utf-8")
paras = [p.strip() for p in text.split("\n\n") if p.strip()]
title = paras[0].lstrip("# ").strip()
(OUT / "letter.json").write_text(
    json.dumps({"title": title, "paragraphs": paras[1:]}, ensure_ascii=False, indent=1),
    encoding="utf-8",
)

bundle = json.loads(
    (TRACK / "data/examples/jobs/praemienverbilligung-brief.json").read_text(encoding="utf-8")
)
final = bundle["summary"]["final_version"]
draft = next(d for d in bundle["drafts"] if d["version"] == final)
blocks = [{"id": b["id"], "kind": b["kind"], "text": b["text"]} for b in draft["blocks"]]
# the first blocks, contiguous, up to the end of the list of documents
upto = next(i for i, b in enumerate(blocks) if b["id"] == "b008") + 1
(OUT / "easy.json").write_text(
    json.dumps(
        {"title": title, "version": final, "blocks": blocks[:upto], "total_blocks": len(blocks)},
        ensure_ascii=False,
        indent=1,
    ),
    encoding="utf-8",
)
print(title, len(paras) - 1, "paragraphs;", f"draft v{final}: {upto} of {len(blocks)} blocks")
for b in blocks[:upto]:
    print(" ", b["id"], b["kind"], b["text"])
