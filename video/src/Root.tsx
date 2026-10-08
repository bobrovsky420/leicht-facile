import React from "react";
import { Composition } from "remotion";
import "./fonts";
import { Demo, DemoA, DemoB, DemoC } from "./Demo";
import { TIMELINES } from "./timelines";
import { FPS } from "./tl";

// one composition per version whose timeline exists (tts/synth.py writes it)
const VERSIONS: [string, string, React.FC][] = [
  ["Demo", "", Demo],
  ["DemoA", "a", DemoA],
  ["DemoB", "b", DemoB],
  ["DemoC", "c", DemoC],
];

export const RemotionRoot: React.FC = () => (
  <>
    {VERSIONS.filter(([, v]) => TIMELINES[v]).map(([id, v, component]) => (
      <Composition
        key={id}
        id={id}
        component={component}
        durationInFrames={Math.ceil(TIMELINES[v].total * FPS)}
        fps={FPS}
        width={1920}
        height={1080}
      />
    ))}
  </>
);
