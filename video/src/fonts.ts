// The app's own fonts (vendored in the repo, OFL), loaded before the first frame renders.
import { continueRender, delayRender, staticFile } from "remotion";

const FILES: [string, string, string][] = [
  ["Atkinson Hyperlegible Next", "atkinson-hyperlegible-next-latin-400-normal.woff2", "400"],
  ["Atkinson Hyperlegible Next", "atkinson-hyperlegible-next-latin-700-normal.woff2", "700"],
  ["IBM Plex Sans", "ibm-plex-sans-latin-400-normal.woff2", "400"],
  ["IBM Plex Sans", "ibm-plex-sans-latin-500-normal.woff2", "500"],
  ["IBM Plex Sans", "ibm-plex-sans-latin-600-normal.woff2", "600"],
  ["IBM Plex Mono", "ibm-plex-mono-latin-400-normal.woff2", "400"],
  ["IBM Plex Mono", "ibm-plex-mono-latin-600-normal.woff2", "600"],
];

const handle = delayRender("Loading fonts");
Promise.all(
  FILES.map(([family, file, weight]) =>
    new FontFace(family, `url('${staticFile(`fonts/${file}`)}') format('woff2')`, { weight }).load(),
  ),
)
  .then((faces) => {
    faces.forEach((f) => document.fonts.add(f));
    continueRender(handle);
  })
  .catch((err) => {
    console.error("font loading failed", err);
    continueRender(handle);
  });
