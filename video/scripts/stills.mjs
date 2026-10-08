// Renders stills at given seconds for a visual check: node stills.mjs 2.5 14 49.5 ...
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { mkdirSync } from "node:fs";
import path from "node:path";

const times = process.argv.slice(2).map(Number);
const scale = Number(process.env.SCALE || 0.5);
mkdirSync("out/stills", { recursive: true });
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts") });
const id = process.env.COMP || "Demo";
const composition = await selectComposition({ serveUrl, id });
for (const s of times) {
  const frame = Math.min(composition.durationInFrames - 1, Math.round(s * composition.fps));
  const output = `out/stills/${id}-t${s.toFixed(2).padStart(6, "0")}.png`;
  await renderStill({ composition, serveUrl, output, frame, scale });
  console.log(output);
}
