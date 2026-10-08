// 0:32 The wordmark, what it does, that the writer stays in charge, and the split of the
// work: Apertus for language, code for everything countable.
import React from "react";
import { AbsoluteFill } from "remotion";
import { CheckCircle, Chip, Code, Person } from "../icons";
import { C, F, easeInOut, lerp, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";

export const Wordmark: React.FC<{ size: number; color?: string; dot?: string }> = ({ size, color = C.ink, dot = C.accent }) => (
  <span style={{ fontFamily: F.reader, fontWeight: 700, fontSize: size, color, letterSpacing: -0.5 }}>
    Leicht<span style={{ color: dot }}>·</span>Facile
  </span>
);

export const Statement: React.FC<{ p: number; icon: React.ReactNode; children: React.ReactNode; tone: string; bg: string }> = ({ p, icon, children, tone, bg }) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: 22,
      padding: "18px 34px 18px 24px",
      borderRadius: 999,
      background: bg,
      color: tone,
      fontFamily: F.sans,
      fontWeight: 500,
      fontSize: 44,
      opacity: p,
      transform: `translateY(${(1 - p) * 18}px)`,
    }}
  >
    {icon}
    <span style={{ color: C.ink }}>{children}</span>
  </div>
);

const Side: React.FC<{ p: number; color: string; weak: string; icon: React.ReactNode; who: string; title: string; items: string[] }> = ({
  p,
  color,
  weak,
  icon,
  who,
  title,
  items,
}) => (
  <div
    style={{
      width: 680,
      borderRadius: 22,
      background: C.surface,
      boxShadow: "0 12px 40px rgba(16,24,40,0.10)",
      borderTop: `8px solid ${color}`,
      padding: "34px 40px 38px",
      opacity: p,
      transform: `translateY(${(1 - p) * 26}px)`,
      fontFamily: F.sans,
    }}
  >
    <div style={{ display: "inline-flex", alignItems: "center", gap: 12, padding: "8px 18px", borderRadius: 999, background: weak, color, fontWeight: 600, fontSize: 28 }}>
      {icon}
      {who}
    </div>
    <div style={{ fontSize: 46, fontWeight: 600, color: C.ink, marginTop: 22, lineHeight: 1.15 }}>{title}</div>
    <div style={{ marginTop: 18 }}>
      {items.map((it) => (
        <div key={it} style={{ fontSize: 30, color: C.muted, lineHeight: 1.6 }}>
          {it}
        </div>
      ))}
    </div>
  </div>
);

export const Logo: React.FC<{ offset: number }> = ({ offset }) => {
  const t = useSceneTime(offset);
  const { cue } = useTL();
  const a = cue("logo-a");
  const b = cue("logo-b");
  const c = cue("logo-c");
  const d = cue("logo-d");
  const e = cue("logo-e");

  const lift = easeInOut((t - (b.s - 0.2)) / 0.6); // the wordmark moves up for the statements
  const lift2 = easeInOut((t - (d.s - 0.25)) / 0.6); // and further up for the two cards
  const markY = lerp(lerp(420, 250, lift), 150, lift2);
  const markScale = lerp(lerp(1, 0.72, lift), 0.5, lift2);
  const statements = 1 - ramp(t, d.s - 0.25, 0.3);

  return (
    <SceneFade offset={offset} bg={C.app}>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse 60% 55% at 50% 40%, #FFFFFF 0%, rgba(255,255,255,0) 70%)" }} />
      <div style={{ position: "absolute", left: 0, right: 0, top: markY - 110, textAlign: "center", transform: `scale(${markScale})`, transformOrigin: "50% 50%" }}>
        <div style={{ opacity: ramp(t, -0.1, 0.5), transform: `scale(${lerp(0.94, 1, ramp(t, -0.1, 0.8))})` }}>
          <Wordmark size={164} />
        </div>
        <div style={{ fontFamily: F.sans, fontSize: 44, color: C.muted, marginTop: 6, opacity: ramp(t, a.s + 0.6, 0.5) * (1 - lift2) }}>
          easy-language drafts of official texts
        </div>
        <div style={{ marginTop: 30, opacity: ramp(t, a.s + a.d * 0.62, 0.45) * (1 - lift2) }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 14, padding: "12px 26px", borderRadius: 999, background: C.apertusWeak, color: C.apertus, fontFamily: F.sans, fontWeight: 600, fontSize: 36 }}>
            <Chip size={36} color={C.apertus} />
            with Apertus, the Swiss open model
          </span>
        </div>
      </div>

      {statements > 0.001 && (
        <div style={{ position: "absolute", left: 0, right: 0, top: 470, display: "flex", flexDirection: "column", alignItems: "center", gap: 26, opacity: statements }}>
          <Statement p={ramp(t, b.s + 0.1, 0.4)} icon={<Person size={46} color={C.warn} />} tone={C.warn} bg={C.warnWeak}>
            The writers stay in charge
          </Statement>
          <Statement p={ramp(t, c.s + 0.1, 0.4)} icon={<CheckCircle size={46} color={C.ok} />} tone={C.ok} bg={C.okWeak}>
            A checked first draft
          </Statement>
        </div>
      )}

      <div style={{ position: "absolute", left: 0, right: 0, top: 300, display: "flex", justifyContent: "center", gap: 60 }}>
        <Side
          p={ramp(t, d.s + 0.05, 0.45)}
          color={C.apertus}
          weak={C.apertusWeak}
          icon={<Chip size={30} color={C.apertus} />}
          who="Apertus"
          title="Language understanding"
          items={["Reads the letter into a fact sheet", "Writes the easy-language draft", "Judges the meaning"]}
        />
        <Side
          p={ramp(t, e.s + 0.05, 0.45)}
          color={C.code}
          weak={C.codeWeak}
          icon={<Code size={30} color={C.code} />}
          who="Code"
          title="Everything that can be counted"
          items={["42 easy-language rules", "Every date, amount and phone number", "No model call, milliseconds"]}
        />
      </div>
    </SceneFade>
  );
};
