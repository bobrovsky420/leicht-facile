// Concept C, 0:52 The real app for the whole letter, short: pasted and started, the judge
// and the repair rounds (the version pills), the sentence linked to its source, approval,
// reader view and export. The step-by-step scene before it explained facts and checks.
import React from "react";
import { C, easeInOut } from "../theme";
import { useTL } from "../tl";
import { FULL, R, ScreenRecording, Shot, frame, lerpRect, rect, union } from "./ScreenRecording";

export const ProductC: React.FC<{ offset: number }> = ({ offset }) => {
  const { cue, scene } = useTL();
  const end = scene("product").end - scene("product").start;
  const A = cue("pc-a"); // The same for the whole letter.
  const B = cue("pc-b"); // A larger Apertus model judges the meaning; only flagged sentences are repaired.
  const Cc = cue("pc-c"); // Every sentence links to its source, and the writer approves each one.

  // the pills from v1 to the final version, with the draft's first lines below them
  const versions = frame(union([160, 95, 640, 280], rect("rev-final", "pillFinal")));
  const approve = frame([443, 330, 597, 480]);
  const repairAt = B.s + B.d * 0.5;
  const approveAt = Cc.s + Cc.d * 0.48;
  const readerAt = end - 0.85;
  const shots: Shot[] = [
    { from: 0, img: "new-filled", cam: frame([110, 200, 800, 420]), label: "New draft: the whole letter" },
    { from: 0.6, img: "new-hover", cam: frame([900, 380, 540, 380]), label: "Level A2, full pipeline" },
    { from: 1.2, img: "job-check", cam: frame([24, 150, 1392, 620]), label: "Fact sheet, draft, 45 rules" },
    { from: B.s, img: "job-repair", cam: frame([24, 500, 620, 230]), label: "Judge: Apertus 70B checks the meaning" },
    { from: repairAt, img: "rev-v1", cam: versions, label: "Repair: only flagged sentences" },
    { from: repairAt + 0.9, img: "rev-final", cam: versions, label: "Repair: only flagged sentences" },
    { from: Cc.s, img: "rev-final", cam: FULL, label: "Every sentence linked to its source" },
    { from: Cc.s + 0.6, img: "rev-select", cam: frame(union(rect("rev-select", "b002"), rect("rev-select", "s0007"))), label: "Every sentence linked to its source" },
    { from: approveAt, img: "rev-approve-0", cam: approve, label: "Review: the writer approves each one" },
    ...[1, 2, 3, 4, 5].map((k) => ({ from: approveAt + 0.22 * k, img: `rev-approve-${k}`, cam: approve, label: "Review: the writer approves each one" })),
    { from: readerAt, img: "rev-reader", cam: frame([560, 170, 880, 500]), label: "Reader view and export" },
  ];
  const pillP = (t: number) => easeInOut((t - (repairAt + 0.9)) / 0.45);
  return (
    <ScreenRecording
      offset={offset}
      end={end}
      shots={shots}
      paths={[
        { show: [0, 1.2], keys: [{ t: 0, x: 974, y: 306 }, { t: 0.6, x: 974, y: 161 }, { t: 1.0, x: 1093, y: 711 }] },
        { show: [Cc.s, Cc.s + 1.2], keys: [{ t: Cc.s, x: 930, y: 620 }, { t: Cc.s + 0.5, x: 700, y: 272 }] },
        { show: [readerAt, end], keys: [{ t: readerAt, x: 900, y: 430 }, { t: readerAt + 0.5, x: 1260, y: 546 }] },
      ]}
      clicks={[
        { t: 1.05, x: 1093, y: 711 },
        { t: Cc.s + 0.55, x: 700, y: 272 },
        { t: readerAt + 0.6, x: 1260, y: 546 },
      ]}
      keycaps={[{ t: 0.05, label: "Ctrl V" }, ...[1, 2, 3, 4, 5].map((k) => ({ t: approveAt + 0.22 * k - 0.05, label: "A" }))]}
      rings={[
        {
          from: repairAt + 0.1,
          to: Cc.s,
          rect: (t) => lerpRect(rect("rev-v1", "pillFirst"), rect("rev-final", "pillFinal"), pillP(t)) as R,
          color: (t) => (pillP(t) < 0.5 ? C.error : C.ok),
        },
      ]}
    />
  );
};
