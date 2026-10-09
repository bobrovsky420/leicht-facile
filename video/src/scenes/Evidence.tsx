// Concept A, 1:09 One number, by the headline rules (case B of decision D-M in PLAN.md): a strong
// single prompt loses hard facts without a trace; Leicht·Facile lists every one it misses.
// Numbers from report §5 (CSCS, 20 German eval pairs, 6 October 2026), provisional.
import React from "react";
import { Img, staticFile } from "remotion";
import manifest from "../../public/capture/manifest.json";
import { CheckCircle } from "../icons";
import { C, F, easeInOut, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";
import { Wordmark } from "./Logo";

const LOST = 23; // P0-ZH condensed: hard facts kept 77 percent, silent losses 23 percent
// the facts panel of the review, as captured: "13 of 14 facts present", the missing fact first
const CROP = { x: 1040, y: 208, w: 400, h: 280 }; // CSS px of the capture
const SCALE = 2; // the capture's device scale
const CROP_W = 700;

export const Evidence: React.FC<{ offset: number }> = ({ offset }) => {
  const t = useSceneTime(offset);
  const { cue } = useTL();
  const a = cue("ev-a");
  const b = cue("ev-b");
  const n = Math.round(LOST * easeInOut((t - (a.s + 0.5)) / 1.0));
  const k = CROP_W / (CROP.w * SCALE);
  const file = (manifest.shots as Record<string, { file: string }>)["rev-final"].file;

  const card: React.CSSProperties = {
    position: "absolute",
    top: 178,
    width: 790,
    height: 712,
    borderRadius: 22,
    background: C.surface,
    boxShadow: "0 12px 40px rgba(16,24,40,0.10)",
    padding: "38px 44px",
    fontFamily: F.sans,
  };
  return (
    <SceneFade offset={offset} bg={C.app}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 96, textAlign: "center", fontFamily: F.sans, fontWeight: 600, fontSize: 50, color: C.ink, opacity: ramp(t, -0.1, 0.4) }}>
        No hard fact lost without a trace
      </div>
      <div style={{ ...card, left: 150, borderTop: `8px solid ${C.error}`, opacity: ramp(t, a.s - 0.1, 0.4) }}>
        <div style={{ fontSize: 30, color: C.muted, fontWeight: 500 }}>A strong single prompt, in its default mode</div>
        <div style={{ fontFamily: F.mono, fontWeight: 600, fontSize: 190, color: C.error, lineHeight: 1.1, marginTop: 60 }}>
          {n} <span style={{ fontSize: 110 }}>%</span>
        </div>
        <div style={{ fontSize: 40, color: C.ink, fontWeight: 500, marginTop: 10, lineHeight: 1.25 }}>of the hard facts lost, and nothing tells the writer</div>
      </div>
      <div style={{ ...card, left: 980, borderTop: `8px solid ${C.ok}`, opacity: ramp(t, b.s - 0.2, 0.4) }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <CheckCircle size={46} color={C.ok} stroke={2.2} />
          <Wordmark size={40} />
        </div>
        <div style={{ fontSize: 40, color: C.ink, fontWeight: 500, marginTop: 18, lineHeight: 1.25 }}>lists every hard fact it misses, for the writer</div>
        <div style={{ position: "relative", width: CROP_W, height: CROP.h * SCALE * k, marginTop: 30, overflow: "hidden", borderRadius: 12, border: "1px solid #D7DBE0" }}>
          <Img
            src={staticFile(`capture/${file}`)}
            style={{ position: "absolute", width: 2880 * k, height: 1620 * k, left: -CROP.x * SCALE * k, top: -CROP.y * SCALE * k }}
          />
        </div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 904, textAlign: "center", fontFamily: F.sans, fontSize: 21, color: C.muted, opacity: ramp(t, a.s + 1, 0.5) }}>
        Hard facts: dates, amounts, contacts and other countable values · same model, Apertus 1.5 8B on CSCS · 20 German test pairs · 6 Oct 2026 · provisional
      </div>
    </SceneFade>
  );
};
