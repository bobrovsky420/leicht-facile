// Concept A, 1:09 One number, by the headline rules (case A2 of decision D-M in PLAN.md): same model,
// a strong single prompt against our pipeline, compared on the hard facts lost without a trace
// (owner, 11 October: more important than the rule errors); Leicht·Facile lists every one. The
// prompt's source is credited on the end card, not here (owner, 10 October: naming it next to a
// project we build on would sound arrogant).
// Numbers from report §5 (CSCS, 20 German eval pairs, final run of 11 October 2026).
import React from "react";
import { Img, staticFile } from "remotion";
import manifest from "../../public/capture/manifest.json";
import { CheckCircle } from "../icons";
import { C, F, easeInOut, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";
import { Wordmark } from "./Logo";

const LOST_ZH = 15; // P0-ZH complete: hard facts lost without a trace, percent
const LOST_LF = 0; // P2, 8B writer: none lost without a trace (each missing one is listed)
// the facts panel of the review at version 2, as captured: the bar with 15 of 16 facts present,
// then the list of facts with the missing one first (the final version carries every fact, so
// it has none to show). Two crops of the capture stacked as one panel, without the help text
// between them (CSS px of the capture).
const CROPS = [
  { x: 1040, y: 212, w: 400, h: 76 }, // "15 of 16 facts present", the bar, "1 missing"
  { x: 1040, y: 392, w: 400, h: 248 }, // f07 Missing with its sentence, then f01 and f02 present
];
const SCALE = 2; // the capture's device scale
const CROP_W = 530; // shown width of the panel: it ends inside the card

export const Evidence: React.FC<{ offset: number }> = ({ offset }) => {
  const t = useSceneTime(offset);
  const { cue } = useTL();
  const a = cue("ev-a");
  const b = cue("ev-b");
  const n = Math.round(LOST_ZH * easeInOut((t - (a.s + 0.5)) / 1.0)); // counts up from 0 (owner)
  const k = CROP_W / (400 * SCALE);
  const file = (manifest.shots as Record<string, { file: string }>)["rev-v2"].file;

  const card: React.CSSProperties = {
    position: "absolute",
    top: 196,
    width: 790,
    height: 676, // the panel and the bottom padding still fit; more room to the title and the footnote
    borderRadius: 22,
    background: C.surface,
    boxShadow: "0 12px 40px rgba(16,24,40,0.10)",
    padding: "38px 44px",
    fontFamily: F.sans,
  };
  const pct: React.CSSProperties = { fontFamily: F.sans, fontSize: 130, marginLeft: 10 }; // no monospace gap before %
  return (
    <SceneFade offset={offset} bg={C.app}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 96, textAlign: "center", fontFamily: F.sans, fontWeight: 600, fontSize: 50, color: C.ink, opacity: ramp(t, -0.1, 0.4) }}>
        Same model. A strong single prompt against our pipeline.
      </div>
      <div style={{ ...card, left: 150, borderTop: `8px solid ${C.error}`, opacity: ramp(t, a.s - 0.1, 0.4) }}>
        <div style={{ fontSize: 30, color: C.muted, fontWeight: 500 }}>A strong single prompt, asked to keep every fact</div>
        <div style={{ fontFamily: F.mono, fontWeight: 600, fontSize: 190, color: C.error, lineHeight: 1.1, marginTop: 32 }}>
          {n}
          <span style={pct}>%</span>
        </div>
        <div style={{ fontSize: 40, color: C.ink, fontWeight: 500, marginTop: 4, lineHeight: 1.25 }}>of the hard facts lost, and nothing tells the writer</div>
      </div>
      <div style={{ ...card, left: 980, borderTop: `8px solid ${C.ok}`, opacity: ramp(t, b.s - 0.2, 0.4) }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <CheckCircle size={46} color={C.ok} stroke={2.2} />
          <Wordmark size={40} />
        </div>
        <div style={{ fontSize: 30, color: C.ink, fontWeight: 500, marginTop: 14, lineHeight: 1.25 }}>
          <span style={{ fontWeight: 700, fontSize: 36, color: C.ok }}>{LOST_LF} %</span> lost without a trace: it lists every one it misses
        </div>
        <div style={{ width: CROP_W, marginTop: 16, overflow: "hidden", borderRadius: 12, border: "1px solid #D7DBE0" }}>
          {CROPS.map((c) => (
            <div key={c.y} style={{ position: "relative", width: CROP_W, height: c.h * SCALE * k, overflow: "hidden" }}>
              <Img
                src={staticFile(`capture/${file}`)}
                style={{ position: "absolute", width: 2880 * k, height: 1620 * k, left: -c.x * SCALE * k, top: -c.y * SCALE * k }}
              />
            </div>
          ))}
        </div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 904, textAlign: "center", fontFamily: F.sans, fontSize: 21, color: C.muted, opacity: ramp(t, a.s + 1, 0.5) }}>
        Apertus 1.5 8B on CSCS · single prompt asked to keep every fact · 20 German test pairs · final run, 11 Oct 2026 · hard facts: dates, amounts, contacts, other countable values
      </div>
    </SceneFade>
  );
};
