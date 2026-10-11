// Concept A, 1:09 One number, by the headline rules (case A of decision D-M in PLAN.md): same model,
// a strong single prompt against our pipeline; Leicht·Facile lists every hard fact it misses. The
// prompt's source is credited on the end card, not here (owner, 10 October: naming it next to a
// project we build on would sound arrogant).
// Numbers from report §5 (CSCS, 20 German eval pairs, final run of 10 October 2026).
import React from "react";
import { Img, staticFile } from "remotion";
import manifest from "../../public/capture/manifest.json";
import { CheckCircle } from "../icons";
import { C, F, easeInOut, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";
import { Wordmark } from "./Logo";

const ERRORS_ZH = 19.5; // P0-ZH complete: rule errors per 100 blocks
const ERRORS_LF = 2.0; // P2, 8B writer: rule errors per 100 blocks
const LOST_ZH = 7; // P0-ZH complete: hard facts lost without a trace, percent
// the facts panel of the review at version 2, as captured: the facts still missing there come
// first (the final version carries every fact, so it has none to show)
const CROP = { x: 1040, y: 208, w: 400, h: 256 }; // CSS px of the capture: the panel down to the missing fact's source sentence
const SCALE = 2; // the capture's device scale
const CROP_W = 620; // narrower since 10 October: the right card gained the rule-errors line

export const Evidence: React.FC<{ offset: number }> = ({ offset }) => {
  const t = useSceneTime(offset);
  const { cue } = useTL();
  const a = cue("ev-a");
  const b = cue("ev-b");
  const n = (ERRORS_ZH * easeInOut((t - (a.s + 0.5)) / 1.0)).toFixed(1);
  const k = CROP_W / (CROP.w * SCALE);
  const file = (manifest.shots as Record<string, { file: string }>)["rev-v2"].file;

  const card: React.CSSProperties = {
    position: "absolute",
    top: 196,
    width: 790,
    height: 676, // the crop and the bottom padding still fit; more room to the title and the footnote
    borderRadius: 22,
    background: C.surface,
    boxShadow: "0 12px 40px rgba(16,24,40,0.10)",
    padding: "38px 44px",
    fontFamily: F.sans,
  };
  return (
    <SceneFade offset={offset} bg={C.app}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 96, textAlign: "center", fontFamily: F.sans, fontWeight: 600, fontSize: 50, color: C.ink, opacity: ramp(t, -0.1, 0.4) }}>
        Same model. A strong single prompt against our pipeline.
      </div>
      <div style={{ ...card, left: 150, borderTop: `8px solid ${C.error}`, opacity: ramp(t, a.s - 0.1, 0.4) }}>
        <div style={{ fontSize: 30, color: C.muted, fontWeight: 500 }}>A strong single prompt, asked to keep every fact</div>
        <div style={{ fontFamily: F.mono, fontWeight: 600, fontSize: 190, color: C.error, lineHeight: 1.1, marginTop: 60 }}>
          {n}
        </div>
        <div style={{ fontSize: 40, color: C.ink, fontWeight: 500, marginTop: 10, lineHeight: 1.25 }}>rule errors per 100 blocks; {LOST_ZH} % of the hard facts lost, and nothing tells the writer</div>
      </div>
      <div style={{ ...card, left: 980, borderTop: `8px solid ${C.ok}`, opacity: ramp(t, b.s - 0.2, 0.4) }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <CheckCircle size={46} color={C.ok} stroke={2.2} />
          <Wordmark size={40} />
        </div>
        <div style={{ fontSize: 40, color: C.ink, fontWeight: 500, marginTop: 18, lineHeight: 1.25 }}>{ERRORS_LF.toFixed(1)} rule errors per 100 blocks</div>
        <div style={{ fontSize: 40, color: C.ink, fontWeight: 500, marginTop: 6, lineHeight: 1.25 }}>lists every hard fact it misses</div>
        <div style={{ position: "relative", width: CROP_W, height: CROP.h * SCALE * k, marginTop: 24, overflow: "hidden", borderRadius: 12, border: "1px solid #D7DBE0" }}>
          <Img
            src={staticFile(`capture/${file}`)}
            style={{ position: "absolute", width: 2880 * k, height: 1620 * k, left: -CROP.x * SCALE * k, top: -CROP.y * SCALE * k }}
          />
        </div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 904, textAlign: "center", fontFamily: F.sans, fontSize: 21, color: C.muted, opacity: ramp(t, a.s + 1, 0.5) }}>
        Apertus 1.5 8B on CSCS · single prompt asked to keep every fact · 20 German test pairs · final run, 10 Oct 2026 · hard facts: dates, amounts, contacts, other countable values
      </div>
    </SceneFade>
  );
};
