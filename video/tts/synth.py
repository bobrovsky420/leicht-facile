"""Synthesize the narration chunk by chunk with Kokoro (local, open weights) and lay out
the timeline the video follows. Writes video/public/audio/narration.wav and
video/src/timeline.json."""

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

HERE = Path(__file__).parent
VIDEO = HERE.parent
MODELS = HERE / "models"  # kokoro-v1.0.onnx and voices-v1.0.bin, see video/README.md
CACHE = HERE / "cache"
CACHE.mkdir(exist_ok=True)

# concept: "" (the first storyboard), "a", "b" or "c"; files get a "-a", "-b", "-c" suffix
concept = sys.argv[1] if len(sys.argv) > 1 else ""
sfx = f"-{concept}" if concept else ""
spec = json.loads((VIDEO / f"narration{sfx}.json").read_text(encoding="utf-8"))
voice = spec["voice"]
speed = spec["speed"]
say = spec["say"]
kokoro = Kokoro(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin"))
SR = 24000

pattern = re.compile("|".join(re.escape(k) for k in sorted(say, key=len, reverse=True)))


def phonemes(text: str) -> str:
    parts, pos = [], 0
    for m in pattern.finditer(text):
        before = text[pos : m.start()]
        if before.strip():
            parts.append(kokoro.tokenizer.phonemize(before, "en-us"))
        parts.append(say[m.group(0)])
        pos = m.end()
    rest = text[pos:]
    if rest.strip():
        parts.append(kokoro.tokenizer.phonemize(rest, "en-us"))
    return " ".join(p.strip() for p in parts if p.strip())


def trim(audio: np.ndarray, thresh: float = 0.004) -> np.ndarray:
    idx = np.where(np.abs(audio) > thresh)[0]
    if len(idx) == 0:
        return audio
    a, b = max(idx[0] - int(0.02 * SR), 0), min(idx[-1] + int(0.06 * SR), len(audio))
    return audio[a:b]


def synth(text: str) -> np.ndarray:
    ph = phonemes(text)
    key = hashlib.sha1(f"{voice}|{speed}|{ph}".encode()).hexdigest()[:16]
    path = CACHE / f"{key}.wav"
    if not path.exists():
        audio, sr = kokoro.create(ph, voice=voice, speed=speed, lang="en-us", is_phonemes=True)
        assert sr == SR, sr
        sf.write(path, trim(audio), SR)
    audio, _ = sf.read(path, dtype="float32")
    return audio


t = 0.0
pieces: list[tuple[float, np.ndarray]] = []
out_scenes = []
for scene in spec["scenes"]:
    start = t
    t += scene["lead"]
    chunks = []
    for i, ch in enumerate(scene["chunks"]):
        audio = synth(ch["text"])
        dur = len(audio) / SR
        pieces.append((t, audio))
        chunks.append(
            {"id": ch["id"], "text": ch["text"], "start": round(t, 3), "end": round(t + dur, 3)}
        )
        t += dur
        if i < len(scene["chunks"]) - 1:
            t += ch.get("pause", 0.3)
    t += scene["tail"]
    out_scenes.append(
        {"id": scene["id"], "start": round(start, 3), "end": round(t, 3), "chunks": chunks}
    )
    print(f"{scene['id']:10s} {start:6.2f} -> {t:6.2f}  ({t - start:5.2f} s)")

total = t
track = np.zeros(int(total * SR) + SR, dtype=np.float32)
for at, audio in pieces:
    i = int(at * SR)
    track[i : i + len(audio)] += audio
track = track[: int(total * SR)]
(VIDEO / "public" / "audio").mkdir(parents=True, exist_ok=True)
sf.write(VIDEO / "public" / "audio" / f"narration{sfx}.wav", track, SR)
(VIDEO / "src").mkdir(exist_ok=True)
(VIDEO / "src" / f"timeline{sfx}.json").write_text(
    json.dumps(
        {"total": round(total, 3), "speed": speed, "voice": voice, "scenes": out_scenes}, indent=1
    ),
    encoding="utf-8",
)
words = sum(len(c["text"].split()) for s in out_scenes for c in s["chunks"])
speech = sum(c["end"] - c["start"] for s in out_scenes for c in s["chunks"])
print(
    f"total {total:.2f} s, {words} words, speech {speech:.1f} s, "
    f"{60 * words / speech:.0f} wpm while speaking"
)
