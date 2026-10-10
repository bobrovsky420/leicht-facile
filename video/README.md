# Demo video: source

The demo video is made in code: [Remotion](https://www.remotion.dev/) scenes in
`src/`, a narration script per version (`narration*.json`), and scripts for the
voice, the music, the UI frames and the checks. The storyboard and the decisions are
in [track_2b/docs/demo-video.md](../track_2b/docs/demo-video.md). Only source lives here; everything
generated is ignored by git (see `.gitignore`).

| Composition | Version | Narration |
|-------------|---------|-----------|
| `DemoC` | **The current draft** (8 October 2026): "Can you read this?" opening, kitchen table, one sentence step by step, short app scene, evidence, "only Apertus", the opening sentence in easy language, "No one left out." | `narration-c.json` |
| `DemoB` | Concept A with the step-by-step opening | `narration-b.json` |
| `DemoA` | Concept A, "Find the deadline" | `narration-a.json` |
| `Demo` | The first concept, "Can you read this?" | `narration.json` |

## Build outside OneDrive

The repository sits in OneDrive, and `node_modules/` alone is about 300 MB. Build in a
copy of this folder outside OneDrive and tell the scripts where the repo is:

```
robocopy video C:\Users\bobro\Developer\lf-video /MIR /XD node_modules out public models cache a /XF timeline*.json
set LF_REPO=C:\Users\bobro\OneDrive\Developer\leicht-facile
```

(Git Bash: `export LF_REPO=...`.) `/MIR` deletes everything in the build folder that is
not in the repo and not excluded; `/XD` matches folder names, not relative paths
(`tts\models` would not protect the voice models), so the generated `src/a/`,
`src/timeline*.json` and `tts/models/` are excluded by name. Copy changed source back
into the repo afterwards.

## Steps (version C; the argument is the version: none, `a`, `b` or `c`)

| Step | Command (in the build folder) | Writes |
|------|-------------------------------|--------|
| 1. Packages | `npm ci` (Node 24; Remotion downloads its headless Chrome on the first render) | `node_modules/` |
| 2. Fonts and texts from the repo | `python scripts/prepare.py` | `public/fonts/`, `src/a/` |
| 3. Voice model | download `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the kokoro-onnx GitHub releases (`model-files-v1.0`) into `tts/models/` | |
| 4. Voice and timeline | `uv run --python 3.12 --with kokoro-onnx --with soundfile python tts/synth.py c` | `public/audio/narration-c.wav`, `src/timeline-c.json` |
| 5. Check the voice without listening | `uv run --python 3.12 --with faster-whisper --with soundfile --with scipy python tts/verify.py c` | word error rate per sentence |
| 6. Music and mix | `uv run --python 3.12 --with soundfile --with scipy --with numpy python tts/music.py c` | `public/audio/mix-c.wav` |
| 7. UI frames | start the app with `DATA_DIR=<build folder>/out/capture-data`, a dead `LLM_BASE_URL` (for example `http://127.0.0.1:9/v1`) and `--port 8791`; then `node scripts/capture.mjs` (if Edge has an update pending, `npx remotion browser ensure` and set `EDGE` to the `chrome-headless-shell.exe` it names) | `public/capture/` |
| 8. Look at stills | `COMP=DemoC node scripts/stills.mjs 6.9 45 106` and `uv run --python 3.12 --with pillow python scripts/sheet.py out/stills/*.png` | `out/stills/`, `out/sheets/` |
| 9. Render | `npx remotion render src/index.ts DemoC out/demo.mp4` (about 3 minutes) | `out/demo.mp4` |

Step 7 imports the example jobs on the app's first start; `scripts/stage_demo.py` then
copies the real premium-reduction job into the states the job page shows (no model call).
The other versions need step 4 and 6 with their own argument; all share steps 1, 2, 3
and 7. Remotion lists a composition only for the versions whose timeline step 4 wrote
(`npx remotion compositions src/index.ts`).

## What is still a placeholder

- The voice is Kokoro `af_heart` (open weights, run locally) at speed 0.90, with
  pronunciations in each narration file's `say` block. The final voice replaces
  `public/audio/narration-c.wav` sentence by sentence; the timeline follows the audio.
- The kitchen table, the letter and the envelopes are drawn in code; generated
  footage may replace the table later (track_2b/docs/demo-video.md).
- The music is made in code.
- The evidence number (23 %) is report §5 of 6 October, provisional until the final run.
- The easy-language text of the opening sentence before the end card (`src/scenes/Again.tsx`)
  is the team's rewrite, labelled on screen; the tool's real output replaces it.
- Every frame carries a "MOCK-UP" label (`src/ui.tsx`), and the end card a mock-up note
  (`src/scenes/End.tsx`); both go for the final render.
