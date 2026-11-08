"""The sample letters of Leicht·Facile and their recorded runs (samples/README.md): data
alone, read by the app's leichtfacile.examples and leichtfacile.llm.replay."""

from pathlib import Path

# One letter per .txt (or .md) file, its job settings and description in the .json next
# to it.
LETTERS = Path(__file__).parent / "letters"
# One recorded run per letter and preset: recordings/<preset>/<letter>.json.
RECORDINGS = Path(__file__).parent / "recordings"
