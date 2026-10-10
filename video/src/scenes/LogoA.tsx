// Concept A, 0:33 The wordmark, Apertus, and that the writers get a checked first draft.
import React from "react";
import { AbsoluteFill } from "remotion";
import { Check, CheckCircle, Chip, Hourglass, Person, Scales } from "../icons";
import { C, F, lerp, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";
import { Statement, Wordmark } from "./Logo";

// What easy language is, for the bridge "For them, there is easy language." Its names in
// German and French as the illustration, three of its rules, and the federal law behind
// equal access (owner, 9 October), named as in German and French. Its art. 14 names only
// speech, hearing and visual disabilities; the revision before Parliament (message of
// 20 December 2024) adds understandable communication for people with learning
// disabilities. So the card says what the law is for, not that it requires easy language.
const EASY_RULES = ["Short sentences", "Everyday words", "One idea at a time"];

const EasyLanguage: React.FC<{ op: number; rules: number[]; law: number }> = ({ op, rules, law }) => (
  <div style={{ position: "absolute", left: 0, right: 0, top: 170, display: "flex", justifyContent: "center", opacity: op }}>
    <div style={{ padding: "40px 64px 46px", borderRadius: 22, background: C.surface, boxShadow: "0 12px 40px rgba(16,24,40,0.10)", fontFamily: F.sans, textAlign: "center" }}>
      <div style={{ fontSize: 64, fontWeight: 600, color: C.ink }}>Easy language</div>
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 26, marginTop: 10, fontFamily: F.reader, fontSize: 36, color: C.muted }}>
        <span lang="de">Leichte Sprache</span>
        <span style={{ width: 2, height: 34, background: C.border }} />
        <span lang="fr">Langage facile</span>
      </div>
      <div style={{ display: "flex", justifyContent: "center", gap: 18, marginTop: 34 }}>
        {EASY_RULES.map((r, i) => (
          <span
            key={r}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 22px 10px 16px",
              borderRadius: 999,
              background: C.accentWeak,
              color: C.accent,
              fontWeight: 600,
              fontSize: 30,
              opacity: rules[i],
              transform: `translateY(${(1 - rules[i]) * 12}px)`,
            }}
          >
            <Check size={30} color={C.accent} stroke={2.4} />
            {r}
          </span>
        ))}
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          gap: 16,
          marginTop: 30,
          paddingTop: 24,
          borderTop: `1px solid ${C.border}`,
          fontSize: 30,
          color: C.muted,
          opacity: law,
          transform: `translateY(${(1 - law) * 10}px)`,
        }}
      >
        <Scales size={36} color={C.muted} stroke={1.8} />
        <span>Equal access by Swiss law:</span>
        <span lang="de" style={{ fontWeight: 600, color: C.ink }}>BehiG</span>
        <span style={{ width: 2, height: 28, background: C.border }} />
        <span lang="fr" style={{ fontWeight: 600, color: C.ink }}>LHand</span>
      </div>
    </div>
  </div>
);

export const LogoA: React.FC<{ offset: number; introCue?: string; bridgeCue?: string }> = ({ offset, introCue, bridgeCue }) => {
  const t = useSceneTime(offset);
  const { cue } = useTL();
  const a = cue("lg-a");
  const b = cue("lg-b");
  // concept C opens with "But easy-language versions are slow expert work." before the wordmark
  const intro = introCue ? cue(introCue) : null;
  const markAt = intro ? a.s - 0.25 : -0.1;
  const introOp = intro ? Math.min(ramp(t, intro.s - 0.1, 0.35), 1 - ramp(t, a.s - 0.45, 0.3)) : 0;
  // concept C first says that easy language exists; its card stays above the expert-work card
  const bridge = bridgeCue ? cue(bridgeCue) : null;
  const bridgeOp = bridge ? Math.min(ramp(t, bridge.s - 0.1, 0.35), 1 - ramp(t, a.s - 0.45, 0.3)) : 0;
  const rules = EASY_RULES.map((_, k) => (bridge ? ramp(t, bridge.s + 0.5 + k * 0.3, 0.35) : 0));
  const law = bridge ? ramp(t, bridge.s + 1.6, 0.4) : 0;
  return (
    <SceneFade offset={offset} bg={C.app}>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse 60% 55% at 50% 40%, #FFFFFF 0%, rgba(255,255,255,0) 70%)" }} />
      {bridgeOp > 0.001 && <EasyLanguage op={bridgeOp} rules={rules} law={law} />}
      {introOp > 0.001 && (
        <div style={{ position: "absolute", left: 0, right: 0, top: bridge ? 610 : 340, display: "flex", justifyContent: "center", opacity: introOp }}>
          <div style={{ display: "flex", alignItems: "center", gap: 28, padding: "34px 48px", borderRadius: 22, background: C.surface, boxShadow: "0 12px 40px rgba(16,24,40,0.10)", fontFamily: F.sans }}>
            <Hourglass size={84} stroke={1.4} color={C.ink} />
            <div>
              <div style={{ fontSize: 52, fontWeight: 600, color: C.ink }}>Slow expert work</div>
              <div style={{ fontSize: 30, color: C.muted, marginTop: 6 }}>Easy-language versions by hand</div>
            </div>
          </div>
        </div>
      )}
      <div style={{ position: "absolute", left: 0, right: 0, top: 190, textAlign: "center" }}>
        <div style={{ opacity: ramp(t, markAt, 0.5), transform: `scale(${lerp(0.94, 1, ramp(t, markAt, 0.8))})` }}>
          <Wordmark size={164} />
        </div>
        <div style={{ fontFamily: F.sans, fontSize: 44, color: C.muted, marginTop: 6, opacity: ramp(t, a.s + 0.5, 0.5) }}>easy-language drafts of official texts</div>
        <div style={{ marginTop: 30, opacity: ramp(t, a.s + a.d * 0.55, 0.45) }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 14, padding: "12px 26px", borderRadius: 999, background: C.apertusWeak, color: C.apertus, fontFamily: F.sans, fontWeight: 600, fontSize: 36 }}>
            <Chip size={36} color={C.apertus} />
            with Apertus, the Swiss open model
          </span>
        </div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 660, display: "flex", justifyContent: "center", gap: 40 }}>
        <Statement p={ramp(t, b.s + 0.05, 0.4)} icon={<Person size={46} color={C.warn} />} tone={C.warn} bg={C.warnWeak}>
          The writers stay in charge
        </Statement>
        <Statement p={ramp(t, b.s + b.d * 0.45, 0.4)} icon={<CheckCircle size={46} color={C.ok} />} tone={C.ok} bg={C.okWeak}>
          A checked first draft
        </Statement>
      </div>
    </SceneFade>
  );
};
