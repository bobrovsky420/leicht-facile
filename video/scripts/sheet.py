"""Tiles stills 2x2 into contact sheets with their names.

python scripts/sheet.py out/stills/*.png
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

files = sorted(Path(p) for p in sys.argv[1:])
for n in range(0, len(files), 4):
    group = files[n : n + 4]
    first = Image.open(group[0])
    w, h = first.size
    sheet = Image.new("RGB", (w * 2 + 6, h * 2 + 6), "white")
    for k, f in enumerate(group):
        im = Image.open(f).convert("RGB")
        x, y = (k % 2) * (w + 6), (k // 2) * (h + 6)
        sheet.paste(im, (x, y))
        d = ImageDraw.Draw(sheet)
        d.rectangle([x, y, x + 140, y + 26], fill="black")
        d.text((x + 6, y + 6), f.stem, fill="white")
    out = Path("out/sheets") / f"sheet-{group[0].stem}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(out)
