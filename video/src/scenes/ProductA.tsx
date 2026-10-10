// Concept A, 0:40 The real app, sped up, following the deadline the viewer looked for:
// the fact sheet's "By when?", the deadline fact, the code check, the repair rounds,
// the sentence linked to its source, the writer's approval.
import React from "react";
import { C, easeInOut } from "../theme";
import { useTL } from "../tl";
import { FULL, R, ScreenRecording, Shot, frame, lerpRect, rect, union } from "./ScreenRecording";

export const ProductA: React.FC<{ offset: number }> = ({ offset }) => {
  const { cue, scene } = useTL();
  const end = scene("product").end - scene("product").start;
  const A = cue("pa-a"); // Apertus reads the letter ... whom to ask
  const B = cue("pa-b"); // Then it writes the draft
  const Cc = cue("pa-c"); // Code checks every date, amount and phone number ...
  const D = cue("pa-d"); // A larger Apertus model judges ...; only flagged sentences are repaired
  const E = cue("pa-e"); // Every sentence links to its source. The writer approves each one.

  // the pills from v1 to the final version, with the draft's first lines below them
  const versions = frame(union([160, 95, 640, 280], rect("rev-final", "pillFinal")));
  const approve = frame([443, 330, 597, 480]);
  const repairAt = D.s + D.d * 0.5;
  const approveAt = E.s + E.d * 0.5;
  const readerAt = end - 0.95;
  const shots: Shot[] = [
    { from: 0, img: "new-filled", cam: frame([110, 200, 800, 420]), label: "New draft: the same letter" },
    { from: 0.75, img: "new-hover", cam: frame([900, 380, 540, 380]), label: "Level A2, full pipeline" },
    { from: 1.45, img: "job-understand", cam: frame([24, 150, 700, 460]), label: "1  Read: Apertus answers the letter's questions" },
    { from: A.s + A.d * 0.3, img: "job-write", cam: frame(rect("job-write", "coreList")), label: "1  Read: Apertus answers the letter's questions" },
    { from: A.s + A.d * 0.86, img: "job-write", cam: frame([425, 520, 720, 290]), label: "Each answer is a fact: the deadline 2027-03-31" },
    { from: B.s - 0.05, img: "job-check", cam: frame(rect("job-check", "draft")), label: "2  Write: the easy-language draft" },
    { from: Cc.s, img: "job-judge", cam: frame([24, 380, 620, 260]), label: "3  Check: every value, 45 rules, by code" },
    { from: Cc.s + Cc.d * 0.55, img: "rev-final", cam: frame([1040, 208, 400, 420]), label: "The deadline is present: checked by code" },
    { from: D.s, img: "job-repair", cam: frame([24, 500, 620, 230]), label: "4  Judge: Apertus 70B checks the meaning" },
    { from: repairAt, img: "rev-v1", cam: versions, label: "5  Repair: only flagged sentences" },
    { from: repairAt + 0.9, img: "rev-final", cam: versions, label: "5  Repair: only flagged sentences" },
    { from: E.s, img: "rev-final", cam: FULL, label: "Every sentence linked to its source" },
    { from: E.s + 0.7, img: "rev-select", cam: frame(union(rect("rev-select", "b002"), rect("rev-select", "s0007"))), label: "Every sentence linked to its source" },
    { from: approveAt, img: "rev-approve-0", cam: approve, label: "6  Review: the writer approves each one" },
    ...[1, 2, 3, 4, 5].map((k) => ({ from: approveAt + 0.25 * k, img: `rev-approve-${k}`, cam: approve, label: "6  Review: the writer approves each one" })),
    { from: readerAt, img: "rev-reader", cam: frame([560, 170, 880, 500]), label: "Reader view and export" },
  ];

  const pillP = (t: number) => easeInOut((t - (repairAt + 0.9)) / 0.45);
  return (
    <ScreenRecording
      offset={offset}
      end={end}
      shots={shots}
      paths={[
        {
          show: [0, 1.45],
          keys: [
            { t: 0, x: 520, y: 470 },
            { t: 0.45, x: 974, y: 306 },
            { t: 0.75, x: 974, y: 161 },
            { t: 1.2, x: 1093, y: 711 },
          ],
        },
        { show: [E.s, E.s + 1.4], keys: [{ t: E.s, x: 930, y: 620 }, { t: E.s + 0.6, x: 700, y: 272 }] },
        { show: [readerAt, end], keys: [{ t: readerAt, x: 900, y: 430 }, { t: readerAt + 0.55, x: 1260, y: 546 }] },
      ]}
      clicks={[
        { t: 0.5, x: 974, y: 306 },
        { t: 1.25, x: 1093, y: 711 },
        { t: E.s + 0.65, x: 700, y: 272 },
        { t: readerAt + 0.65, x: 1260, y: 546 },
      ]}
      keycaps={[{ t: 0.05, label: "Ctrl V" }, ...[1, 2, 3, 4, 5].map((k) => ({ t: approveAt + 0.25 * k - 0.05, label: "A" }))]}
      rings={[
        // "by when": the question the viewer just tried to answer
        { from: A.s + A.d * 0.66, to: A.s + A.d * 0.86 + 0.05, rect: () => rect("job-write", "byWhen"), color: () => C.warn },
        // the deadline as a fact with its value
        { from: A.s + A.d * 0.9, to: B.s - 0.05, rect: () => rect("job-write", "f01"), color: () => C.warn },
        // in the review: the deadline fact, present
        { from: Cc.s + Cc.d * 0.6, to: D.s, rect: () => rect("rev-final", "factF01"), color: () => C.ok },
        // the version pills: from v1 (10 blocking) to the final version (2 blocking)
        {
          from: repairAt + 0.1,
          to: E.s,
          rect: (t) => lerpRect(rect("rev-v1", "pillFirst"), rect("rev-final", "pillFinal"), pillP(t)) as R,
          color: (t) => (pillP(t) < 0.5 ? C.error : C.ok),
        },
      ]}
      timer={{ from: Cc.s + 0.3, to: Cc.s + Cc.d * 0.55, ms: 47, title: "Rule check of draft v1", sub: "every value · 45 rules · no model call" }}
    />
  );
};
