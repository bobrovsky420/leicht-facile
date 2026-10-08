"""Check the synthesized narration without listening: transcribe it with Whisper and
compare each chunk with the script (word error rate per chunk)."""

import json
import re
import sys
from pathlib import Path

import soundfile as sf
from faster_whisper import WhisperModel
from scipy.signal import resample_poly

VIDEO = Path(__file__).parent.parent
sfx = f"-{sys.argv[1]}" if len(sys.argv) > 1 else ""  # concept, as for synth.py
timeline = json.loads((VIDEO / "src" / f"timeline{sfx}.json").read_text(encoding="utf-8"))
model = WhisperModel("small.en", device="cpu", compute_type="int8")
audio, sr = sf.read(VIDEO / "public" / "audio" / f"narration{sfx}.wav", dtype="float32")
audio = resample_poly(audio, 16000, sr).astype("float32")  # passed as samples: avoids PyAV
segments, _ = model.transcribe(audio, word_timestamps=True, beam_size=5)
words = [w for s in segments for w in s.words]


def norm(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", text.lower().replace("-", " ")).split()


def wer(ref: list[str], hyp: list[str]) -> float:
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[len(hyp)] / max(len(ref), 1)


for scene in timeline["scenes"]:
    for ch in scene["chunks"]:
        heard = " ".join(
            w.word.strip() for w in words if ch["start"] - 0.15 <= w.start < ch["end"] + 0.1
        )
        score = wer(norm(ch["text"]), norm(heard))
        flag = "  " if score < 0.15 else "!!"
        print(f"{flag} {ch['id']:10s} wer {score:4.2f} | {heard}")
