// 0:49 (first storyboard) The real app, sped up: the shots, cursor and overlays along the
// narration "Apertus turns a letter into a fact sheet ... a full audit trail."
import React from "react";
import { C, easeInOut } from "../theme";
import { useTL } from "../tl";
import { FULL, R, ScreenRecording, Shot, frame, lerpRect, rect, union } from "./ScreenRecording";

export const Product: React.FC<{ offset: number }> = ({ offset }) => {
  const { cue, scene } = useTL();
  const end = scene("product").end - scene("product").start;
  const A = cue("product-a");
  const B = cue("product-b");
  const Cc = cue("product-c");
  const D = cue("product-d");
  const E = cue("product-e");
  const Fq = cue("product-f");
  const G = cue("product-g");

  // the pills from v1 to the final version, with the draft's first lines below them
  const versions = frame(union([160, 95, 640, 280], rect("rev-final", "pillFinal")));
  const approve = frame([443, 330, 597, 480]);
  const shots: Shot[] = [
    { from: 0, img: "list", cam: FULL, label: "Drafts" },
    { from: 0.5, img: "new-empty", cam: FULL, label: "New draft" },
    { from: 0.9, img: "new-filled", cam: frame([110, 200, 800, 420]), label: "Paste a letter" },
    { from: 1.8, img: "new-hover", cam: frame([900, 380, 540, 380]), label: "Level A2, full pipeline" },
    { from: 2.5, img: "job-understand", cam: frame([24, 150, 700, 460]), label: "1  Read: Apertus writes the fact sheet" },
    { from: 3.4, img: "job-write", cam: frame(rect("job-write", "factsheet").slice(0, 3).concat(600) as R), label: "1  Read: Apertus writes the fact sheet" },
    { from: A.s + A.d * 0.55, img: "job-write", cam: frame([425, 540, 720, 270]), label: "Every deadline, amount and phone number" },
    { from: B.s - 0.05, img: "job-check", cam: frame(rect("job-check", "draft")), label: "2  Write: the easy-language draft" },
    { from: Cc.s, img: "rev-final", cam: FULL, label: "Every sentence linked to its source" },
    { from: Cc.s + 0.75, img: "rev-select", cam: frame(union(rect("rev-select", "b002"), rect("rev-select", "linked"))), label: "Every sentence linked to its source" },
    { from: Cc.s + Cc.d * 0.58, img: "rev-omitted", cam: frame([0, 300, 560, 300]), label: "Every omission explained" },
    { from: D.s, img: "job-judge", cam: frame([24, 380, 620, 260]), label: "3  Check: 45 rules, by code" },
    { from: D.s + D.d * 0.55, img: "rev-final", cam: frame([1040, 208, 400, 420]), label: "Every date and amount, checked by code" },
    { from: E.s, img: "job-repair", cam: frame([24, 500, 620, 230]), label: "4  Judge: Apertus 70B checks the meaning" },
    { from: Fq.s, img: "rev-v1", cam: versions, label: "5  Repair: only flagged blocks" },
    { from: Fq.s + 1.0, img: "rev-final", cam: versions, label: "5  Repair: only flagged blocks" },
    { from: G.s, img: "rev-approve-0", cam: approve, label: "6  Review: the writer approves every block" },
    ...[1, 2, 3, 4, 5].map((k) => ({ from: G.s + 0.3 * k, img: `rev-approve-${k}`, cam: approve, label: "6  Review: the writer approves every block" })),
    { from: G.s + 2.1, img: "rev-reader", cam: frame([560, 170, 880, 500]), label: "Reader view, export, audit trail" },
  ];

  // the version pills: from v1 (10 blocking) to the final version (2 blocking)
  const pillP = (t: number) => easeInOut((t - (Fq.s + 1.0)) / 0.45);
  return (
    <ScreenRecording
      offset={offset}
      end={end}
      shots={shots}
      paths={[
        {
          show: [0, 2.5],
          keys: [
            { t: 0, x: 1000, y: 560 },
            { t: 0.36, x: 1356, y: 93 },
            { t: 0.5, x: 1356, y: 93 },
            { t: 0.85, x: 520, y: 470 },
            { t: 1.3, x: 520, y: 470 },
            { t: 1.62, x: 974, y: 306 },
            { t: 1.8, x: 974, y: 161 },
            { t: 2.25, x: 1093, y: 711 },
          ],
        },
        { show: [Cc.s, Cc.s + 1.5], keys: [{ t: Cc.s, x: 930, y: 620 }, { t: Cc.s + 0.6, x: 700, y: 272 }] },
        { show: [G.s + 2.1, end], keys: [{ t: G.s + 2.1, x: 900, y: 430 }, { t: G.s + 2.8, x: 1260, y: 546 }] },
      ]}
      clicks={[
        { t: 0.4, x: 1356, y: 93 },
        { t: 1.66, x: 974, y: 306 },
        { t: 2.3, x: 1093, y: 711 },
        { t: Cc.s + 0.65, x: 700, y: 272 },
        { t: G.s + 2.9, x: 1260, y: 546 },
      ]}
      keycaps={[{ t: 0.86, label: "Ctrl V" }, ...[1, 2, 3, 4, 5].map((k) => ({ t: G.s + 0.3 * k - 0.05, label: "A" }))]}
      rings={[
        {
          from: Fq.s + 0.15,
          to: G.s,
          rect: (t) => lerpRect(rect("rev-v1", "pillFirst"), rect("rev-final", "pillFinal"), pillP(t)),
          color: (t) => (pillP(t) < 0.5 ? C.error : C.ok),
        },
      ]}
      timer={{ from: D.s + 0.3, to: D.s + D.d * 0.55, ms: 47, title: "Rule check of draft v1", sub: "45 rules · every value · no model call" }}
    />
  );
};
