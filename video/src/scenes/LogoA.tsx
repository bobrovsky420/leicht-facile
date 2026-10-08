// Concept A, 0:33 The wordmark, Apertus, and that the writers get a checked first draft.
import React from "react";
import { AbsoluteFill } from "remotion";
import { CheckCircle, Chip, Hourglass, Person } from "../icons";
import { C, F, lerp, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";
import { Statement, Wordmark } from "./Logo";

export const LogoA: React.FC<{ offset: number; introCue?: string }> = ({ offset, introCue }) => {
  const t = useSceneTime(offset);
  const { cue } = useTL();
  const a = cue("lg-a");
  const b = cue("lg-b");
  // concept C opens with "Easy-language versions are slow expert work." before the wordmark
  const intro = introCue ? cue(introCue) : null;
  const markAt = intro ? a.s - 0.25 : -0.1;
  const introOp = intro ? Math.min(ramp(t, intro.s - 0.1, 0.35), 1 - ramp(t, a.s - 0.45, 0.3)) : 0;
  return (
    <SceneFade offset={offset} bg={C.app}>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse 60% 55% at 50% 40%, #FFFFFF 0%, rgba(255,255,255,0) 70%)" }} />
      {introOp > 0.001 && (
        <div style={{ position: "absolute", left: 0, right: 0, top: 340, display: "flex", justifyContent: "center", opacity: introOp }}>
          <div style={{ display: "flex", alignItems: "center", gap: 28, padding: "34px 48px", borderRadius: 22, background: C.surface, boxShadow: "0 12px 40px rgba(16,24,40,0.10)", fontFamily: F.sans }}>
            <Hourglass size={84} stroke={1.8} color={C.ink} />
            <div>
              <div style={{ fontSize: 52, fontWeight: 600, color: C.ink }}>Slow expert work</div>
              <div style={{ fontSize: 30, color: C.muted, marginTop: 6 }}>Easy-language versions by hand</div>
            </div>
          </div>
        </div>
      )}
      <div style={{ position: "absolute", left: 0, right: 0, top: 190, textAlign: "center" }}>
        <div style={{ opacity: ramp(t, markAt, 0.5), transform: `scale(${lerp(0.94, 1, ramp(t, markAt, 0.8))})` }}>
          <Wordmark size={164} />
        </div>
        <div style={{ fontFamily: F.sans, fontSize: 44, color: C.muted, marginTop: 6, opacity: ramp(t, a.s + 0.5, 0.5) }}>easy-language drafts of official texts</div>
        <div style={{ marginTop: 30, opacity: ramp(t, a.s + a.d * 0.55, 0.45) }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 14, padding: "12px 26px", borderRadius: 999, background: C.apertusWeak, color: C.apertus, fontFamily: F.sans, fontWeight: 600, fontSize: 36 }}>
            <Chip size={36} color={C.apertus} />
            with Apertus, the Swiss open model
          </span>
        </div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 660, display: "flex", justifyContent: "center", gap: 40 }}>
        <Statement p={ramp(t, b.s + 0.05, 0.4)} icon={<Person size={46} color={C.warn} />} tone={C.warn} bg={C.warnWeak}>
          The writers stay in charge
        </Statement>
        <Statement p={ramp(t, b.s + b.d * 0.45, 0.4)} icon={<CheckCircle size={46} color={C.ok} />} tone={C.ok} bg={C.okWeak}>
          A checked first draft
        </Statement>
      </div>
    </SceneFade>
  );
};
