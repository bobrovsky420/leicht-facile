// The timelines written by tts/synth.py (src/timeline.json, src/timeline-a.json, ...).
// They are generated and not in git, so only the versions whose voice was made exist;
// Root.tsx registers a composition for each timeline found.
import { TL, TimelineData, makeTL } from "./tl";

declare const require: {
  context: (dir: string, deep: boolean, re: RegExp) => { keys: () => string[]; (key: string): TimelineData };
};

const files = require.context("./", false, /^\.\/timeline(-[a-z])?\.json$/);

/** By version: "" (the first concept), "a", "b", "c". */
export const TIMELINES: Record<string, TL> = {};
for (const key of files.keys()) {
  const version = key.match(/timeline(?:-([a-z]))?\.json$/)?.[1] ?? "";
  TIMELINES[version] = makeTL(files(key));
}
