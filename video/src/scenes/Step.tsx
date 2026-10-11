// Concept B, 0:00 "One sentence, step by step": the deadline sentence of the example
// letter (s0007), what the rule checker finds in it, the facts Apertus takes out (f01,
// f06), the two sentences of the real draft (b002, b003) with the facts each carries,
// and the check again. All of it from the example job and `leichtfacile check`.
import React from "react";
import easy from "../a/easy.json";
import { Check, Chip, Code } from "../icons";
import { C, F, clamp01, easeInOut, lerp, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";

type Mark = "lex" | "passive" | "oblig" | "deadline";
const SOURCE: { t: string; m?: Mark }[] = [
  { t: "Das " },
  { t: "Antragsformular", m: "lex" },
  { t: " " },
  { t: "ist", m: "passive" },
  { t: " " },
  { t: "vollständig ausgefüllt und unterzeichnet", m: "oblig" },
  { t: " " },
  { t: "bis spätestens 31. März 2027", m: "deadline" },
  { t: " bei der " },
  { t: "Sozialversicherungsstelle", m: "lex" },
  { t: " " },
  { t: "einzureichen", m: "passive" },
  { t: "." },
];
const LEN = SOURCE.reduce((n, s) => n + s.t.length, 0);
// `leichtfacile check` on the sentence (level A2): 2 errors, 3 warnings
const FINDINGS = [
  { sev: "error", rule: "LEN-01", text: "16 words; at most 12 for A2" },
  { sev: "error", rule: "GRAM-01", text: "Passive 'ist … einzureichen': say who does what" },
  { sev: "warn", rule: "LEN-02", text: "2 clauses in one sentence" },
  { sev: "warn", rule: "LEX-01", text: "Long words: Antragsformular, Sozialversicherungsstelle" },
];
const BLOCKS = ["b002", "b003"].map((id) => easy.blocks.find((b) => b.id === id)!);
// the facts each block carries, as the job records them
const CARRIES: Record<string, string[]> = { b002: ["f01", "f06"], b003: ["f06"] };
const FACTS: Record<string, { kind: string; value: string; color: string; weak: string }> = {
  f01: { kind: "deadline", value: "2027-03-31", color: C.warn, weak: "#FFF4E0" },
  f06: { kind: "procedure", value: "vollständig ausgefüllt und unterzeichnet", color: C.apertus, weak: "#F1ECF9" },
};
const DATE = "31. März 2027";
// the original's two long words, with the Mediopunkt
const MEDIO = ["Antrags·formular", "Sozial·versicherungs·stelle"];

/** The Mediopunkt in a text, lit up with strength p (0 to 1). */
const dots = (text: string, p: number): React.ReactNode =>
  p <= 0
    ? text
    : text.split("·").flatMap((part, i) =>
        i === 0
          ? [part]
          : [
              <span key={i} style={{ color: `rgba(242,160,40,${0.4 + 0.6 * p})`, fontWeight: 700, textShadow: `0 0 ${18 * p}px rgba(242,160,40,${0.9 * p})` }}>
                ·
              </span>,
              part,
            ],
      );

const FactChip: React.FC<{ id: string; p: number; ok?: number; small?: boolean }> = ({ id, p, ok = 0, small }) => {
  const f = FACTS[id];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        padding: small ? "4px 12px" : "8px 16px",
        borderRadius: 999,
        background: f.weak,
        border: `2px solid ${ok > 0.5 ? C.ok : f.color}`,
        color: C.ink,
        fontFamily: F.sans,
        fontSize: small ? 20 : 26,
        opacity: p,
        transform: `translateY(${(1 - p) * 14}px)`,
        marginRight: 12,
        whiteSpace: "nowrap",
      }}
    >
      <span style={{ fontFamily: F.mono, fontWeight: 600, color: f.color }}>{id}</span>
      <span style={{ color: C.muted }}>{f.kind}</span>
      <span lang="de" style={{ fontFamily: id === "f01" ? F.mono : F.sans }}>{f.value}</span>
      {ok > 0 && (
        <span style={{ display: "inline-flex", opacity: ok }}>
          <Check size={small ? 20 : 26} color={C.ok} stroke={3} />
        </span>
      )}
    </span>
  );
};

export const Step: React.FC<{ offset: number }> = ({ offset }) => {
  const t = useSceneTime(offset);
  const { cue, hasCue } = useTL();
  const a = cue("st-a");
  const b = cue("st-b");
  const c = cue("st-c");
  const d = cue("st-d");
  const e = cue("st-e");
  // version C: "A middle dot splits long words into easier parts."
  const md = hasCue("st-md") ? cue("st-md") : null;
  const dotP = md ? Math.min(ramp(t, md.s + 0.1, 0.35), 1 - ramp(t, e.s, 0.4)) : 0;

  const chars = Math.floor(clamp01((t - 0.3) / Math.max(0.5, a.e - 0.4)) * LEN);
  const findingAt = [b.s + 0.05, b.s + b.d * 0.32, b.s + b.d * 0.6, b.s + b.d * 0.78];
  const factAt = { f01: c.s + c.d * 0.55, f06: c.s + c.d * 0.78 };
  const morph = easeInOut((t - (d.s - 0.35)) / 0.75); // the source moves up, the draft appears
  const lineAt = [d.s + 0.35, d.s + d.d * 0.55];
  const checkAt = e.s + 0.25;
  const tickAt = e.s + 0.9;
  const errors = Math.round(lerp(2, 0, easeInOut((t - (checkAt + 0.2)) / 0.5)));

  const markStyle = (m?: Mark): React.CSSProperties => {
    if (m === "passive") {
      const p = ramp(t, findingAt[1], 0.3);
      // dotted, not wavy: a wavy red line reads as a spell checker's mark
      return { textDecorationLine: p > 0.05 ? "underline" : "none", textDecorationStyle: "dotted", textDecorationColor: `rgba(229,72,77,${p})`, textUnderlineOffset: 10, textDecorationThickness: 6 };
    }
    if (m === "lex") {
      const p = ramp(t, findingAt[3], 0.3);
      return { textDecorationLine: p > 0.05 ? "underline" : "none", textDecorationStyle: "wavy", textDecorationColor: `rgba(242,160,40,${p})`, textUnderlineOffset: 10, textDecorationThickness: 1.5 };
    }
    if (m === "deadline" || m === "oblig") {
      const p = ramp(t, m === "deadline" ? factAt.f01 - 0.1 : factAt.f06 - 0.1, 0.35);
      const col = m === "deadline" ? "rgba(242,160,40,0.45)" : "rgba(160,120,220,0.45)";
      return { backgroundImage: `linear-gradient(${col}, ${col})`, backgroundSize: `${p * 100}% 100%`, backgroundRepeat: "no-repeat", borderRadius: 6 };
    }
    return {};
  };

  let left = chars;
  const sentence = SOURCE.map((s, i) => {
    if (left <= 0) return null;
    const shown = s.t.slice(0, left);
    left -= s.t.length;
    return (
      <span key={i} style={markStyle(s.m)}>
        {shown}
      </span>
    );
  });
  const caret = chars < LEN && Math.floor(t * 2.4) % 2 === 0;

  const head: React.CSSProperties = { display: "flex", alignItems: "center", gap: 12, fontFamily: F.sans, fontWeight: 600, fontSize: 26, color: "#C9CED6", marginBottom: 18 };
  const tag = (color: string, weak: string, icon: React.ReactNode, label: string) => (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 14px", borderRadius: 999, background: weak, color, fontSize: 22 }}>
      {icon}
      {label}
    </span>
  );

  return (
    <SceneFade offset={offset} bg="#0B0C0E">
      {/* the source sentence: full size first, then small at the top */}
      <div
        style={{
          position: "absolute",
          left: 160,
          top: lerp(110, 46, morph),
          width: 1600,
          transform: `scale(${lerp(1, 0.56, morph)})`,
          transformOrigin: "0 0",
          opacity: lerp(1, 0.6, morph),
        }}
      >
        <div style={{ fontFamily: F.sans, fontWeight: 600, fontSize: 22, letterSpacing: 3, textTransform: "uppercase", color: "#7F8894", marginBottom: 18 }}>Original</div>
        <div lang="de" style={{ fontFamily: F.reader, fontSize: 56, lineHeight: 1.42, color: "#F4F4F2" }}>
          {sentence}
          {caret && <span style={{ display: "inline-block", width: 5, height: 56, marginLeft: 4, verticalAlign: "-8px", background: "#F4F4F2" }} />}
        </div>
      </div>

      {/* what code finds, and what Apertus takes out */}
      <div style={{ position: "absolute", left: 160, top: 470, width: 1600, opacity: 1 - morph }}>
        <div style={{ ...head, opacity: ramp(t, findingAt[0] - 0.2, 0.3) }}>
          {tag(C.code, "#E3F3F1", <Code size={22} color={C.code} />, "Code")}
          Rule check: 2 errors · 3 warnings
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 24px" }}>
          {FINDINGS.map((f, k) => (
            <div key={f.rule} style={{ display: "flex", alignItems: "center", gap: 14, fontFamily: F.sans, fontSize: 26, color: "#E6E8EB", opacity: ramp(t, findingAt[k], 0.3) }}>
              <span style={{ width: 14, height: 14, borderRadius: "50%", background: f.sev === "error" ? "#E5484D" : "#F2A028", flex: "none" }} />
              <span style={{ fontFamily: F.mono, fontWeight: 600, color: f.sev === "error" ? "#FF8A8D" : "#F5C26B" }}>{f.rule}</span>
              <span>{f.text}</span>
            </div>
          ))}
        </div>
        <div style={{ ...head, marginTop: 50, opacity: ramp(t, c.s, 0.3) }}>
          {tag(C.apertus, "#F1ECF9", <Chip size={22} color={C.apertus} />, "Apertus")}
          Facts that must survive
        </div>
        <div>
          <FactChip id="f01" p={ramp(t, factAt.f01, 0.35)} />
          <FactChip id="f06" p={ramp(t, factAt.f06, 0.35)} />
        </div>
      </div>

      {/* the two sentences of the real draft, with the facts they carry */}
      <div style={{ position: "absolute", left: 160, top: 250, width: 1600, opacity: ramp(t, d.s, 0.4) }}>
        <div style={{ ...head, color: "#8FD6A6" }}>
          {tag(C.apertus, "#F1ECF9", <Chip size={22} color={C.apertus} />, "Apertus")}
          Easy language A2 · the real draft
        </div>
        {BLOCKS.map((blk, k) => {
          const p = ramp(t, lineAt[k], 0.4);
          const at = blk.text.indexOf(DATE);
          const ok = ramp(t, tickAt, 0.3);
          return (
            <div key={blk.id} style={{ marginBottom: 26, opacity: p, transform: `translateX(${(1 - p) * -24}px)` }}>
              <div lang="de" style={{ fontFamily: F.reader, fontSize: 52, lineHeight: 1.3, color: "#F4F4F2" }}>
                {at < 0 ? (
                  dots(blk.text, dotP)
                ) : (
                  <>
                    {dots(blk.text.slice(0, at), dotP)}
                    <span style={{ backgroundImage: "linear-gradient(rgba(80,190,120,0.45), rgba(80,190,120,0.45))", backgroundSize: `${ok * 100}% 100%`, backgroundRepeat: "no-repeat", borderRadius: 6 }}>{DATE}</span>
                    {dots(blk.text.slice(at + DATE.length), dotP)}
                  </>
                )}
              </div>
              <div style={{ marginTop: 8 }}>
                {CARRIES[blk.id].map((id) => (
                  <FactChip key={id} id={id} small p={ramp(t, lineAt[k] + 0.3, 0.3)} ok={id === "f01" && at >= 0 ? ok : 0} />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* the Mediopunkt, named while it lights up (version C); the two sentences have none,
          so two example words show it */}
      {dotP > 0.001 && (
        <div style={{ position: "absolute", left: 160, top: 610, opacity: dotP, transform: `translateY(${(1 - dotP) * 14}px)` }}>
          <div lang="de" style={{ display: "flex", gap: 52, whiteSpace: "nowrap", fontFamily: F.reader, fontSize: 52, lineHeight: 1.3, color: "#F4F4F2" }}>
            {MEDIO.map((word) => (
              <span key={word}>{dots(word, dotP)}</span>
            ))}
          </div>
          <div style={{ marginTop: 12, fontFamily: F.sans, fontSize: 30, color: "#E6E8EB" }}>
            <b>Mediopunkt</b>: long words in readable parts, as later in this draft
          </div>
        </div>
      )}

      {/* the check again */}
      <div style={{ position: "absolute", left: 160, top: 790, display: "flex", alignItems: "center", gap: 18, fontFamily: F.sans, fontSize: 30, color: "#E6E8EB", opacity: ramp(t, checkAt, 0.3) }}>
        {tag(C.code, "#E3F3F1", <Code size={22} color={C.code} />, "Code")}
        <span>
          Rule check: <b style={{ color: errors === 0 ? "#8FD6A6" : "#FF8A8D" }}>{errors} errors</b> (before: 2)
        </span>
        <span style={{ opacity: ramp(t, tickAt, 0.3) }}>· deadline 2027-03-31 present</span>
      </div>
    </SceneFade>
  );
};
