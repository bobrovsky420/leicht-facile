// 1:15 The hook sentence again, now in easy language, then one evaluation number:
// rule errors per 100 blocks against a strong single prompt on the same model.
import React from "react";
import { AbsoluteFill } from "remotion";
import { CheckCircle } from "../icons";
import { C, F, easeInOut, lerp, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";
import { Wordmark } from "./Logo";

const DE4 = "Es ist nicht unwesentlich, dass Kosten, die nicht fristgerecht geltend gemacht werden, nicht vergütet werden können.";
const A2 = ["Sie haben Kosten?", "Melden Sie die Kosten rechtzeitig.", "Sonst bekommen Sie kein Geld zurück."];
// report §5 (CSCS, 20 German eval pairs, final run of 10 October 2026): P0-ZH complete against P2
const BASE = 19.5;
const OURS = 2.0;

const Bar: React.FC<{ label: React.ReactNode; value: number; p: number; color: string }> = ({ label, value, p, color }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 30, height: 96 }}>
    <div style={{ width: 430, textAlign: "right", fontFamily: F.sans, fontSize: 36, color: C.ink, fontWeight: 500 }}>{label}</div>
    <div style={{ width: 980, height: 64, position: "relative" }}>
      <div style={{ position: "absolute", left: 0, top: 0, height: 64, width: (980 * value * p) / BASE, background: color, borderRadius: 10 }} />
      <div style={{ position: "absolute", top: 4, left: (980 * value * p) / BASE + 22, fontFamily: F.mono, fontWeight: 600, fontSize: 48, color }}>
        {(value * p).toFixed(1)}
      </div>
    </div>
  </div>
);

export const Compare: React.FC<{ offset: number }> = ({ offset }) => {
  const t = useSceneTime(offset);
  const { cue } = useTL();
  const a = cue("compare-a");
  const b = cue("compare-b");
  const c = cue("compare-c");
  const d = cue("compare-d");

  const out = easeInOut((t - (c.s - 0.3)) / 0.5); // the sentences make room for the number
  const card: React.CSSProperties = {
    width: 780,
    minHeight: 470,
    borderRadius: 22,
    background: C.surface,
    boxShadow: "0 12px 40px rgba(16,24,40,0.10)",
    padding: "40px 46px",
    fontFamily: F.reader,
  };
  const head: React.CSSProperties = { fontFamily: F.sans, fontWeight: 600, fontSize: 26, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 26 };

  return (
    <SceneFade offset={offset} bg={C.app}>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 150,
          display: "flex",
          justifyContent: "center",
          gap: 60,
          opacity: 1 - out,
          transform: `translateY(${-out * 60}px) scale(${lerp(1, 0.94, out)})`,
        }}
      >
        <div style={{ ...card, opacity: ramp(t, -0.1, 0.4) }}>
          <div style={{ ...head, color: C.muted }}>Before: the letter</div>
          <div lang="de" style={{ fontSize: 44, lineHeight: 1.42, color: C.ink }}>
            {DE4}
          </div>
        </div>
        <div style={{ ...card, borderTop: `8px solid ${C.ok}`, opacity: ramp(t, a.s + 0.2, 0.4), position: "relative" }}>
          <div style={{ ...head, color: C.ok }}>After: easy language A2</div>
          {A2.map((line, k) => (
            <div key={line} lang="de" style={{ fontSize: 54, lineHeight: 1.3, color: C.ink, marginBottom: 18, opacity: ramp(t, b.s + k * b.d * 0.3, 0.35), transform: `translateX(${(1 - ramp(t, b.s + k * b.d * 0.3, 0.35)) * -16}px)` }}>
              {line}
            </div>
          ))}
          <div style={{ position: "absolute", right: 26, bottom: 20, fontFamily: F.sans, fontSize: 19, color: C.muted, background: C.app, padding: "6px 12px", borderRadius: 8 }}>
            illustrative rewrite, not tool output
          </div>
        </div>
      </div>

      <AbsoluteFill style={{ opacity: ramp(t, c.s - 0.05, 0.4), alignItems: "center", paddingTop: 170 }}>
        <div style={{ fontFamily: F.sans, fontWeight: 600, fontSize: 52, color: C.ink, marginBottom: 46 }}>Rule errors per 100 blocks</div>
        <Bar label="A strong single prompt" value={BASE} p={easeInOut((t - (c.s + 0.2)) / 0.9)} color={C.error} />
        <Bar label={<Wordmark size={40} />} value={OURS} p={easeInOut((t - (c.s + 0.9)) / 0.9)} color={C.ok} />
        <div style={{ display: "flex", alignItems: "center", gap: 18, marginTop: 50, opacity: ramp(t, d.s + 0.1, 0.4), fontFamily: F.sans, fontSize: 42, color: C.ink, fontWeight: 500 }}>
          <CheckCircle size={52} color={C.ok} />
          Every missing fact is listed for the writer.
        </div>
        <div style={{ marginTop: 30, fontFamily: F.sans, fontSize: 22, color: C.muted, opacity: ramp(t, c.s + 1.2, 0.5) }}>
          Same model, Apertus 1.5 8B on CSCS · 20 German test pairs · 6 Oct 2026 · provisional
        </div>
      </AbsoluteFill>
    </SceneFade>
  );
};
