// The letter on the kitchen table: the number, what such letters decide, the letter
// pushed away, why today's options fall short. Used by both concepts with their cues.
import React from "react";
import { AbsoluteFill } from "remotion";
import { ChatNoCheck, Hourglass } from "../icons";
import { C, F, easeInOut, lerp, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";
import { Glasses, Letter, Mug, Pen, Table } from "./Table";

const Card: React.FC<{ x: number; p: number; icon: React.ReactNode; title: string; sub: string }> = ({ x, p, icon, title, sub }) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: 300,
      width: 470,
      padding: "34px 36px",
      borderRadius: 18,
      background: "rgba(251,250,246,0.97)",
      boxShadow: "20px 28px 44px rgba(0,0,0,0.45)",
      opacity: p,
      transform: `translateY(${(1 - p) * 30}px) rotate(${x < 900 ? -1.5 : 1.2}deg)`,
      fontFamily: F.sans,
    }}
  >
    <div style={{ color: C.ink }}>{icon}</div>
    <div style={{ fontSize: 40, fontWeight: 600, color: C.ink, marginTop: 18, lineHeight: 1.15 }}>{title}</div>
    <div style={{ fontSize: 26, color: C.muted, marginTop: 10 }}>{sub}</div>
  </div>
);

export const Kitchen: React.FC<{
  offset: number;
  sceneId?: string;
  number?: string; // "1.25 million adults ..."
  marks?: string; // "Letters like this decide their money, their deadlines, their rights."
  push?: string | null; // "No one should be shut out ..." (null: the letter stays)
  cards?: string | null; // "But easy-language versions are slow expert work ..." (null: no cards)
  chatbot?: boolean; // the second card, "A chatbot checks nothing"
}> = ({ offset, sceneId = "kitchen", number = "kitchen-b", marks = "kitchen-c", push = "kitchen-d", cards = "kitchen-e", chatbot = true }) => {
  const t = useSceneTime(offset);
  const { cue, scene } = useTL();
  const dur = scene(sceneId).end - scene(sceneId).start;
  const b = cue(number);
  const c = cue(marks);
  const d = push ? cue(push) : { s: 1e9, e: 1e9, d: 0 };
  const e = cards ? cue(cards) : null;

  // where the words fall inside "Letters like this decide their money, their deadlines, their rights."
  const at = (frac: number) => c.s + c.d * frac;
  const fadeMarks = 1 - ramp(t, d.s - 0.1, 0.4);
  const markP: [number, number, number] = [
    ramp(t, at(0.34), 0.45) * fadeMarks,
    ramp(t, at(0.53), 0.45) * fadeMarks,
    ramp(t, at(0.78), 0.45) * fadeMarks,
  ];

  const pushP = easeInOut((t - (d.s + 0.45)) / 1.2);
  const cam = lerp(1, 1.09, Math.min(1, Math.max(0, t / dur)));
  const numberIn = ramp(t, b.s + 0.15, 0.5) * (1 - ramp(t, c.s - 0.1, 0.35));
  const dim = 0.5 * numberIn + (e ? 0.22 * ramp(t, e.s, 0.5) : 0);

  return (
    <SceneFade offset={offset}>
      <Table dim={dim}>
        <AbsoluteFill style={{ transform: `scale(${cam})`, transformOrigin: "640px 470px" }}>
          <Glasses x={1170} y={150} />
          <Pen x={1180} y={520} r={-28} />
          <Mug x={1500} y={740} />
          <Letter
            marks={markP}
            style={{
              left: 300,
              top: 96,
              transform: `translate(${pushP * 260}px, ${pushP * -1040}px) rotate(${-2.5 + pushP * 16}deg) scale(${1 - pushP * 0.08})`,
            }}
          />
        </AbsoluteFill>
      </Table>
      {numberIn > 0.001 && (
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingLeft: 760, paddingBottom: 140, opacity: numberIn }}>
          <div style={{ fontFamily: F.sans, fontWeight: 600, fontSize: 210, color: "#fff", letterSpacing: -4, textShadow: "0 10px 40px rgba(0,0,0,0.5)", transform: `translateY(${(1 - numberIn) * 24}px)`, whiteSpace: "nowrap" }}>
            1.25<span style={{ fontSize: 120, letterSpacing: -1, marginLeft: 24 }}>million</span>
          </div>
          <div style={{ fontFamily: F.sans, fontSize: 34, color: "rgba(255,255,255,0.85)", marginTop: 4 }}>22% of adults aged 16-65 struggle with reading</div>
          {/* on screen only: who the survey counts (track_2b/docs/hard-texts.md §2) */}
          <div style={{ fontFamily: F.sans, fontSize: 24, color: "rgba(255,255,255,0.65)", marginTop: 10, letterSpacing: 0.5 }}>All residents, whatever their first language, tested in German, French or Italian</div>
          <div style={{ fontFamily: F.sans, fontSize: 24, color: "rgba(255,255,255,0.65)", marginTop: 4, letterSpacing: 0.5 }}>Source: Swiss Federal Statistical Office, PIAAC 2022/23</div>
        </AbsoluteFill>
      )}
      {e && <Card x={chatbot ? 420 : 725} p={ramp(t, e.s + 0.35, 0.5)} icon={<Hourglass size={72} stroke={1.4} />} title="Slow expert work" sub="Easy-language versions by hand" />}
      {e && chatbot && <Card x={1030} p={ramp(t, e.s + e.d * 0.62, 0.5)} icon={<ChatNoCheck size={72} stroke={1.8} />} title="A chatbot checks nothing" sub="No proof that facts survived" />}
    </SceneFade>
  );
};
