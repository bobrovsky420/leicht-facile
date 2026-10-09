// Version C, before the end card: the sentence from the start again, split screen as in
// the hook, now with its easy-language version: "Can you read it now?"
// PLACEHOLDER: the easy texts are the team's rewrite, not tool output (both pass
// `leichtfacile check` at A2 without errors or warnings). Replace them with the real P2
// output for DE-4 and FR-4 after the prompt freeze, and drop the note.
import React from "react";
import { F, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";
import { DE, FR } from "./Hook";

const EASY_DE = ["Das ist wichtig:", "Melden Sie Ihre Kosten rechtzeitig.", "Sonst bekommen Sie kein Geld zurück."];
const EASY_FR = ["C'est important :", "Annoncez vos frais à temps.", "Sinon, vous ne recevez pas d'argent."];
const Q_DE = "Können Sie es jetzt lesen?";
const Q_FR = "Pouvez-vous le lire maintenant ?";
const GREEN = "#8FD3A6";

const Column: React.FC<{ lang: string; label: string; easyLabel: string; source: typeof DE; easy: string[]; question: string; t: number; qAt: number }> = ({
  lang,
  label,
  easyLabel,
  source,
  easy,
  question,
  t,
  qAt,
}) => (
  <div lang={lang} style={{ width: 800 }}>
    <div style={{ fontFamily: F.sans, fontWeight: 600, fontSize: 22, letterSpacing: 3, textTransform: "uppercase", color: "#7F8894", marginBottom: 22 }}>{label}</div>
    {/* the sentence from the start, small and dimmed, its negations still marked */}
    <div style={{ fontFamily: F.reader, fontSize: 30, lineHeight: 1.42, color: "#7F8894", minHeight: 30 * 1.42 * 3 }}>
      {source.map((s, i) => (
        <span key={i} style={s.neg ? { background: "rgba(242, 160, 40, 0.22)", borderRadius: 4, padding: "0 4px", margin: "0 -4px" } : undefined}>
          {s.t}
        </span>
      ))}
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 44, marginBottom: 22, opacity: ramp(t, 0.1, 0.35) }}>
      <div style={{ width: 34, height: 4, borderRadius: 2, background: GREEN }} />
      <div style={{ fontFamily: F.sans, fontWeight: 600, fontSize: 22, letterSpacing: 3, textTransform: "uppercase", color: GREEN }}>{easyLabel}</div>
    </div>
    {easy.map((line, k) => {
      const p = ramp(t, 0.15 + k * 0.25, 0.35);
      return (
        <div key={line} style={{ fontFamily: F.reader, fontSize: 46, lineHeight: 1.3, color: "#F4F4F2", whiteSpace: "nowrap", marginBottom: 12, opacity: p, transform: `translateX(${(1 - p) * -16}px)` }}>
          {line}
        </div>
      );
    })}
    <div style={{ fontFamily: F.reader, color: "#A9B2BE", fontSize: 34, lineHeight: 1.35, marginTop: 34, opacity: ramp(t, qAt - 0.1, 0.4) }}>{question}</div>
  </div>
);

export const Again: React.FC<{ offset: number }> = ({ offset }) => {
  const t = useSceneTime(offset);
  const { cue } = useTL();
  const a = cue("ag-a");
  return (
    <SceneFade offset={offset} bg="#0B0C0E">
      <div style={{ position: "absolute", left: 0, right: 0, top: 0, bottom: 150, display: "flex", justifyContent: "center", alignItems: "center" }}>
        <Column lang="de" label="Deutsch" easyLabel="Leichte Sprache" source={DE} easy={EASY_DE} question={Q_DE} t={t} qAt={a.s} />
        <div style={{ width: 2, alignSelf: "stretch", margin: "150px 60px", background: "rgba(255,255,255,0.14)" }} />
        <Column lang="fr" label="Français" easyLabel="Langage facile" source={FR} easy={EASY_FR} question={Q_FR} t={t} qAt={a.s} />
      </div>
      <div style={{ position: "absolute", left: 30, top: 26, fontFamily: F.sans, fontSize: 18, color: "rgba(255,255,255,0.6)", background: "rgba(255,255,255,0.08)", padding: "6px 14px", borderRadius: 999 }}>
        Placeholder: the team's rewrite, not tool output yet
      </div>
    </SceneFade>
  );
};
