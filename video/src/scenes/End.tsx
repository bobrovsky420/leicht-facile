// The end card: the message, the name, the team, the repository; concept A adds a kicker.
import React from "react";
import { C, F, ramp } from "../theme";
import { SceneFade, useSceneTime } from "../ui";
import { Wordmark } from "./Logo";

export const End: React.FC<{ offset: number; kicker?: string; line?: string; sub?: string }> = ({
  offset,
  kicker,
  line = "No one left out.",
  sub,
}) => {
  const t = useSceneTime(offset);
  return (
    <SceneFade offset={offset} bg={C.night}>
      <div style={{ position: "absolute", left: 0, right: 0, top: kicker ? 200 : 250, textAlign: "center" }}>
        {kicker && <div style={{ fontFamily: F.reader, fontSize: 46, color: "#A9B2BE", marginBottom: 26, opacity: ramp(t, 0, 0.4) }}>{kicker}</div>}
        <div style={{ fontFamily: F.reader, fontWeight: 700, fontSize: 118, color: "#fff", opacity: ramp(t, kicker ? 0.3 : 0.05, 0.5) }}>{line}</div>
        {sub && <div style={{ fontFamily: F.reader, fontSize: 50, color: "#C9CED6", marginTop: 14, opacity: ramp(t, 0.35, 0.5) }}>{sub}</div>}
        <div style={{ marginTop: 70, opacity: ramp(t, 0.45, 0.5) }}>
          <Wordmark size={62} color="#fff" dot="#8FB3E6" />
        </div>
        <div style={{ marginTop: 18, fontFamily: F.sans, fontSize: 32, color: "rgba(255,255,255,0.78)", opacity: ramp(t, 0.6, 0.5) }}>
          Team Röstigraben Bridgers · Hack Apertus 2026
        </div>
        <div style={{ marginTop: 14, fontFamily: F.mono, fontSize: 30, color: "#8FB3E6", opacity: ramp(t, 0.75, 0.5) }}>github.com/bobrovsky420/leicht-facile</div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 64, textAlign: "center", fontFamily: F.sans, fontSize: 21, lineHeight: 1.5, color: "rgba(255,255,255,0.55)", opacity: ramp(t, 0.9, 0.5) }}>
        <div>Inspired by simply-simplify-language, Team Data, Office for Statistics and Data, Canton of Zurich.</div>
      </div>
      {/* the only AI-generated part of the video; pictures are drawn in code or captured from the app */}
      <div style={{ position: "absolute", right: 64, bottom: 64, fontFamily: F.sans, fontSize: 18, lineHeight: 1.5, color: "rgba(255,255,255,0.45)", opacity: ramp(t, 0.9, 0.5) }}>
        Voice AI-generated (Kokoro)
      </div>
    </SceneFade>
  );
};
