// 0:00 "Can you read this?": split screen, DE-4 and FR-4 type themselves side by side,
// each with its question, then the negations in both are marked.
import React from "react";
import { F, clamp01, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";

type Seg = { t: string; neg?: boolean };
export const DE: Seg[] = [
  { t: "Es ist " },
  { t: "nicht unwesentlich", neg: true },
  { t: ", dass Kosten, die " },
  { t: "nicht fristgerecht", neg: true },
  { t: " geltend gemacht werden, " },
  { t: "nicht vergütet", neg: true },
  { t: " werden können." },
];
export const FR: Seg[] = [
  { t: "Il convient de relever que les frais qui " },
  { t: "n'auraient pas", neg: true },
  { t: " été annoncés dans les délais " },
  { t: "ne pourront", neg: true },
  { t: " être remboursés." },
];
// one question per line
export const Q_DE = ["Können Sie das lesen?", "Haben Sie es sofort verstanden?"];
export const Q_FR = ["Pouvez-vous lire ceci ?", "L'avez-vous compris tout de suite ?"];
const len = (segs: Seg[]) => segs.reduce((n, s) => n + s.t.length, 0);

const Typed: React.FC<{ segs: Seg[]; chars: number; marks: number[]; caret: boolean; t: number }> = ({ segs, chars, marks, caret, t }) => {
  let left = chars;
  let negIndex = -1;
  const out: React.ReactNode[] = [];
  segs.forEach((s, i) => {
    if (s.neg) negIndex++;
    if (left <= 0) return;
    const shown = s.t.slice(0, left);
    left -= s.t.length;
    if (s.neg) {
      const m = marks[negIndex] ?? 0;
      // an inline background, so a phrase that wraps to the next line is marked on both
      out.push(
        <span
          key={i}
          style={{
            backgroundImage: "linear-gradient(rgba(242, 160, 40, 0.42), rgba(242, 160, 40, 0.42))",
            backgroundSize: `${m * 100}% 100%`,
            backgroundRepeat: "no-repeat",
            borderRadius: 6,
            padding: "0 5px",
            margin: "0 -5px",
          }}
        >
          {shown}
        </span>,
      );
    } else {
      out.push(<span key={i}>{shown}</span>);
    }
  });
  const blink = Math.floor(t * 2.4) % 2 === 0;
  return (
    <>
      {out}
      {caret && (
        <span
          style={{
            display: "inline-block",
            width: "0.08em",
            height: "1.05em",
            marginLeft: 4,
            verticalAlign: "-0.15em",
            background: "#F4F4F2",
            opacity: blink ? 0.9 : 0,
          }}
        />
      )}
    </>
  );
};

export const Column: React.FC<{ lang: string; label: string; segs: Seg[]; chars: number; marks: number[]; caret: boolean; question: string[]; qOp: number[]; t: number }> = ({
  lang,
  label,
  segs,
  chars,
  marks,
  caret,
  question,
  qOp,
  t,
}) => (
  <div lang={lang} style={{ width: 760 }}>
    <div style={{ fontFamily: F.sans, fontWeight: 600, fontSize: 22, letterSpacing: 3, textTransform: "uppercase", color: "#7F8894", marginBottom: 30 }}>{label}</div>
    <div style={{ fontFamily: F.reader, color: "#F4F4F2", fontSize: 54, lineHeight: 1.38, letterSpacing: 0.2, minHeight: 54 * 1.38 * 5 }}>
      <Typed segs={segs} chars={chars} marks={marks} caret={caret} t={t} />
    </div>
    <div style={{ fontFamily: F.reader, color: "#A9B2BE", fontSize: 34, lineHeight: 1.35, marginTop: 34 }}>
      {question.map((q, i) => (
        <div key={q} style={{ opacity: qOp[i] }}>
          {q}
        </div>
      ))}
    </div>
  </div>
);

export const Hook: React.FC<{ offset: number; marksCue?: string }> = ({ offset, marksCue = "hook-c" }) => {
  const t = useSceneTime(offset);
  const { cue } = useTL();
  const a = cue("hook-a");
  const c = cue(marksCue); // the negations light up on this sentence
  const typeStart = 0.35;
  const typeDur = a.s - 0.55 - typeStart; // both sentences are typed before "Can you read this?"

  const deChars = Math.floor(clamp01((t - typeStart) / typeDur) * len(DE));
  const frChars = Math.floor(clamp01((t - typeStart) / typeDur) * len(FR));
  const typing = t < typeStart + typeDur;
  const b = cue("hook-b");
  // each question appears as it is spoken
  const qOp = [ramp(t, a.s - 0.1, 0.4), ramp(t, b.s - 0.1, 0.4)];
  // "do I get my money back, or not?": the negations light up, alternating DE and FR
  const mark = (k: number) => ramp(t, c.s + 0.3 + k * 0.28, 0.3);

  return (
    <SceneFade offset={offset} bg="#0B0C0E">
      <div style={{ position: "absolute", left: 0, right: 0, top: 0, bottom: 150, display: "flex", justifyContent: "center", alignItems: "center", gap: 0 }}>
        <Column lang="de" label="Deutsch" segs={DE} chars={deChars} marks={[mark(0), mark(2), mark(4)]} caret={typing || t < a.s} question={Q_DE} qOp={qOp} t={t} />
        <div style={{ width: 2, alignSelf: "stretch", margin: "150px 70px", background: "rgba(255,255,255,0.14)" }} />
        <Column lang="fr" label="Français" segs={FR} chars={frChars} marks={[mark(1), mark(3)]} caret={typing || t < a.s} question={Q_FR} qOp={qOp} t={t} />
      </div>
    </SceneFade>
  );
};
