"""A quiet music bed made by code (additive pads, soft plucks, convolution reverb), ducked
under the narration, and the final mix. Reads src/timeline{-concept}.json and
public/audio/narration{-concept}.wav, writes public/audio/mix{-concept}.wav (48 kHz stereo)."""

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, resample_poly, sosfilt

VIDEO = Path(__file__).parent.parent
SR = 48000
rng = np.random.default_rng(7)
# concept: "" (the first storyboard) or "a" (find the deadline); files get a "-a" suffix
concept = sys.argv[1] if len(sys.argv) > 1 else ""
sfx = f"-{concept}" if concept else ""
timeline = json.loads((VIDEO / "src" / f"timeline{sfx}.json").read_text(encoding="utf-8"))
scenes = {s["id"]: s for s in timeline["scenes"]}
chunks = {c["id"]: c for s in timeline["scenes"] for c in s["chunks"]}
total = timeline["total"]
N = int(total * SR)

CHORDS = {
    "D": [50, 57, 62, 66, 69],
    "Dadd9": [50, 57, 64, 66, 69],
    "Bm7": [47, 54, 57, 62, 66],
    "Gmaj7": [43, 50, 54, 59, 62],
    "G": [43, 50, 55, 59, 62],
    "A": [45, 52, 57, 61, 64],
    "Asus": [45, 52, 57, 62, 64],
    "Em7": [40, 52, 55, 59, 62],
}
# per scene: chords spread evenly over the scene, pad level, pluck subdivisions per chord
PLAN = [
    ("kitchen", ["Bm7", "Gmaj7", "Dadd9", "Asus"], 0.75, 0),
    ("stakes", ["Bm7", "Gmaj7", "Dadd9"], 0.75, 0),
    ("why", ["Bm7", "Gmaj7", "Dadd9", "Asus"], 0.75, 0),
    ("logo", ["Dadd9", "A", "Bm7", "Gmaj7"] if not concept else ["Dadd9", "A"], 0.85, 4),
    ("product", ["D", "Bm7", "Gmaj7", "A", "D", "Bm7", "Gmaj7", "Asus"], 0.8, 8),
    ("compare", ["Gmaj7", "A", "Dadd9"], 0.8, 4),
    ("evidence", ["Gmaj7", "A", "Dadd9"], 0.8, 4),
    ("sovereign", ["Bm7", "Gmaj7", "Dadd9", "A", "Bm7", "Gmaj7", "Asus", "A"], 0.95, 8),
    ("again", ["Gmaj7", "Asus"], 0.8, 0),
]
PLAN = [p for p in PLAN if p[0] in scenes]


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def env(n: int, attack: float, release: float) -> np.ndarray:
    e = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    e[:a] = np.linspace(0, 1, a) ** 2
    e[-r:] *= np.linspace(1, 0, r) ** 1.5
    return e


pad = np.zeros((2, N + SR * 4))
pluck = np.zeros((2, N + SR * 4))
bass = np.zeros(N + SR * 4)


def add_pad(notes: list[int], start: float, dur: float, level: float) -> None:
    i0, n = int(start * SR), int((dur + 1.6) * SR)
    t = np.arange(n) / SR
    e = env(n, 1.4, 2.0) * level
    for note in notes:
        for side, cents in ((0, -5), (1, 6)):
            f = hz(note) * 2 ** (cents / 1200)
            w = sum(
                np.sin(2 * np.pi * f * k * t + rng.uniform(0, 6.28)) / k**1.6 for k in range(1, 6)
            )
            lfo = 1 + 0.12 * np.sin(2 * np.pi * 0.17 * t + rng.uniform(0, 6.28))
            pad[side, i0 : i0 + n] += w * e * lfo / len(notes)
    root = notes[0] - 12 if notes[0] > 45 else notes[0]
    bass[i0 : i0 + n] += np.sin(2 * np.pi * hz(root) * t) * e * 0.55


def add_pluck(note: int, start: float, level: float) -> None:
    n = int(1.6 * SR)
    i0 = int(start * SR)
    t = np.arange(n) / SR
    f = hz(note)
    w = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
    w += 0.12 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 9)
    e = np.exp(-t * 3.2) * np.minimum(t / 0.004, 1)
    pan = rng.uniform(0.3, 0.7)
    pluck[0, i0 : i0 + n] += w * e * level * (1 - pan)
    pluck[1, i0 : i0 + n] += w * e * level * pan


# the opening: a low open fifth that swells out of silence (under the typed sentences,
# or under the two "find the deadline" tests)
if "hook" in scenes:
    h = scenes["hook"]
    add_pad([38, 45, 50], 0.6, h["end"] - 0.6, 0.55)
if "test1" in scenes:
    add_pad([38, 45, 50], 0.4, scenes["test2"]["end"] - 0.4, 0.5)
if "step" in scenes:
    add_pad([38, 45, 50], 0.4, scenes["step"]["end"] - 0.4, 0.5)

for scene_id, chords, level, subdiv in PLAN:
    s = scenes[scene_id]
    span = (s["end"] - s["start"]) / len(chords)
    for i, name in enumerate(chords):
        start = s["start"] + i * span
        add_pad(CHORDS[name], start - 0.4, span + 0.4, level)
        if subdiv:
            tones = sorted(set(m + 12 for m in CHORDS[name][1:]))
            pattern = [
                tones[0],
                tones[1],
                tones[2],
                tones[1],
                tones[3],
                tones[2],
                tones[1],
                tones[2],
            ]
            for k in range(subdiv):
                add_pluck(
                    pattern[k % len(pattern)],
                    start + k * span / subdiv,
                    0.16 if k % 2 == 0 else 0.11,
                )

# end card: the home chord rings out
e_ = scenes["end"]
add_pad(CHORDS["Dadd9"], e_["start"] - 0.3, e_["end"] - e_["start"] - 0.8, 0.9)
add_pluck(74, e_["start"], 0.2)
add_pluck(78, e_["start"] + 0.35, 0.16)
add_pluck(81, e_["start"] + 0.7, 0.14)

lowpass = butter(4, 2600, "low", fs=SR, output="sos")
pad = sosfilt(lowpass, pad, axis=1)
music = pad * 0.9 + pluck * 0.8 + np.stack([bass, bass]) * 0.6

# convolution reverb: decaying stereo noise, darker in its tail
n_ir = int(2.8 * SR)
t_ir = np.arange(n_ir) / SR
ir = rng.normal(size=(2, n_ir)) * np.exp(-t_ir / 0.55)
ir = sosfilt(butter(2, 3500, "low", fs=SR, output="sos"), ir, axis=1)
ir /= np.sqrt((ir**2).sum(axis=1, keepdims=True))
wet = np.stack([fftconvolve(music[c], ir[c])[: music.shape[1]] for c in range(2)])
music = music * 0.75 + wet * 0.55
music = music[:, :N]

# narration at 48 kHz, levelled to about -18 dBFS RMS while speaking
voice, vsr = sf.read(VIDEO / "public" / "audio" / f"narration{sfx}.wav", dtype="float64")
voice = resample_poly(voice, SR, vsr)[:N]
voice = np.pad(voice, (0, N - len(voice)))
active = np.abs(voice) > 0.01
rms = np.sqrt(np.mean(voice[active] ** 2))
voice *= 10 ** (-19.5 / 20) / rms

# ducking: the bed drops about 9 dB under speech, with a slow release
hop = int(0.01 * SR)
frames = np.sqrt(np.mean(voice[: len(voice) // hop * hop].reshape(-1, hop) ** 2, axis=1))
target = (frames > 0.01).astype(float)
g, smooth = 0.0, np.zeros_like(target)
for i, x in enumerate(target):
    g += (x - g) * (0.35 if x > g else 0.025)
    smooth[i] = g
duck = 10 ** (-9 * np.repeat(smooth, hop) / 20)
duck = np.pad(duck, (0, N - len(duck)), constant_values=duck[-1])

music_rms = np.sqrt(np.mean(music**2))
music *= 10 ** (-27 / 20) / music_rms  # bed at about -27 dBFS before ducking
fade = np.ones(N)
fade[-int(1.2 * SR) :] = np.linspace(1, 0, int(1.2 * SR)) ** 2
mix = music * duck * fade + np.stack([voice, voice])


# the countdowns of concept A (same timing rule as the video: a timer starts 0.2 s after
# "You have five seconds" and 0.15 s after "Now the easy-language version")
def place(sound: np.ndarray, at: float, level: float) -> None:
    i = int(at * SR)
    n = min(len(sound), N - i)
    mix[:, i : i + n] += sound[:n] * level


def tick() -> np.ndarray:
    t = np.arange(int(0.06 * SR)) / SR
    return np.sin(2 * np.pi * 2300 * t) * np.exp(-t / 0.006) + 0.3 * rng.normal(
        size=len(t)
    ) * np.exp(-t / 0.002)


def bell(freqs: list[float], decay: float) -> np.ndarray:
    t = np.arange(int(decay * 4 * SR)) / SR
    return sum(
        np.sin(2 * np.pi * f * t) * np.exp(-t / decay) / (k + 1) for k, f in enumerate(freqs)
    ) * np.minimum(t / 0.003, 1)


if "t1-a" in chunks:
    t0 = chunks["t1-a"]["end"] + 0.2
    for k in range(5):
        place(tick(), t0 + k, 0.10)
    place(bell([110, 220, 330], 0.35), t0 + 5.0, 0.16)  # time's up: a low, soft tone
    t0 = chunks["t2-a"]["end"] + 0.15
    place(tick(), t0, 0.10)
    place(bell([1318.5, 1975.5], 0.5), t0 + 0.95, 0.07)  # found: a light chime
    place(bell([1975.5, 2637.0], 0.5), t0 + 1.03, 0.05)
# concept B: a light chime when the rewritten sentences pass the check (video: st-e + 0.9)
if "st-e" in chunks:
    t0 = chunks["st-e"]["start"] + 0.9
    place(bell([1318.5, 1975.5], 0.5), t0, 0.07)
    place(bell([1975.5, 2637.0], 0.5), t0 + 0.08, 0.05)
peak = np.max(np.abs(mix))
# soft limiter above -1.5 dBFS only, so the voice body stays untouched
th = 10 ** (-1.5 / 20)
over = np.abs(mix) > th
mix[over] = np.sign(mix[over]) * (th + (1 - th) * np.tanh((np.abs(mix[over]) - th) / (1 - th)))
print(f"limited {over.mean() * 100:.3f} % of samples")
sf.write(
    VIDEO / "public" / "audio" / f"mix{sfx}.wav", mix.T.astype(np.float32), SR, subtype="PCM_16"
)
db = lambda x: 20 * np.log10(np.sqrt(np.mean(x**2)) + 1e-12)  # noqa: E731
print(
    f"mix {total:.2f} s, peak {peak:.2f}, voice {db(voice[active[: len(voice)]]):.1f} dBFS, "
    f"bed under speech {db((music * duck)[:, active]):.1f} dBFS, "
    f"bed in gaps {db((music * duck)[:, ~active]):.1f} dBFS"
)
