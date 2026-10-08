// Concept A, 0:00 "Find the deadline": the viewer looks for the deadline in the real
// example letter (5 seconds), then in the first blocks of its real P2 draft, unedited.
// Both texts are German, copied word for word by make_a_data.py.
import React from "react";
import easy from "../a/easy.json";
import letter from "../a/letter.json";
import { Check } from "../icons";
import { C, F, clamp01, lerp, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";

const TARGET_LETTER = "bis spätestens 31. März 2027";
const TARGET_EASY = "31. März 2027";
const AMBER = "rgba(242, 160, 40, 0.55)";
const GREEN = "rgba(80, 190, 120, 0.45)";

const Marker: React.FC<{ p: number; color: string; children: React.ReactNode }> = ({ p, color, children }) => (
  <span
    style={{
      backgroundImage: `linear-gradient(${color}, ${color})`,
      backgroundSize: `${p * 100}% 100%`,
      backgroundRepeat: "no-repeat",
      borderRadius: 5,
      padding: "1px 4px",
      margin: "0 -4px",
    }}
  >
    {children}
  </span>
);

const Paper: React.FC<{ children: React.ReactNode; p: number }> = ({ children, p }) => (
  <div
    style={{
      position: "absolute",
      left: 80,
      top: 46,
      width: 1120,
      height: 990,
      background: "#FBFAF6",
      borderRadius: 4,
      boxShadow: "0 30px 70px rgba(0,0,0,0.55)",
      padding: "54px 66px",
      opacity: p,
      transform: `translateY(${(1 - p) * 30}px)`,
      overflow: "hidden",
    }}
  >
    {children}
  </div>
);

/** The instruction (English, German below as an illustration) and the countdown ring. */
const Countdown: React.FC<{ t: number; start: number; found?: number; inP: number }> = ({ t, start, found, inP }) => {
  const stop = found ?? start + 5;
  const elapsed = Math.max(0, Math.min(t, stop) - start);
  const left = clamp01(1 - elapsed / 5);
  const isFound = found !== undefined && t >= found;
  const timeUp = found === undefined && t >= start + 5;
  const digit = Math.max(0, Math.ceil(5 - elapsed - 1e-6));
  const r = 118;
  const circ = 2 * Math.PI * r;
  const color = isFound ? "#3FB56A" : left < 0.4 ? "#F2A028" : "#F4F4F2";
  return (
    <div style={{ position: "absolute", left: 1260, top: 150, width: 600, opacity: inP }}>
      <div style={{ fontFamily: F.sans, fontWeight: 600, fontSize: 64, color: "#F4F4F2", lineHeight: 1.1 }}>Find the deadline.</div>
      <div lang="de" style={{ fontFamily: F.reader, fontSize: 36, color: "#A9B2BE", marginTop: 14 }}>
        Finden Sie die Frist.
      </div>
      <div style={{ position: "relative", width: 280, height: 280, marginTop: 70 }}>
        <svg width="280" height="280" viewBox="0 0 280 280">
          <circle cx="140" cy="140" r={r} fill="none" stroke="rgba(255,255,255,0.14)" strokeWidth="14" />
          <circle
            cx="140"
            cy="140"
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="14"
            strokeLinecap="round"
            strokeDasharray={`${circ * left} ${circ}`}
            transform="rotate(-90 140 140)"
          />
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: F.mono, fontWeight: 600, fontSize: 112, color }}>
          {isFound ? <Check size={120} color="#3FB56A" stroke={2.6} /> : digit}
        </div>
      </div>
      <div style={{ marginTop: 34, fontFamily: F.sans, fontWeight: 600, fontSize: 36, color: isFound ? "#3FB56A" : "#F2A028", opacity: isFound ? ramp(t, found!, 0.25) : timeUp ? ramp(t, start + 5, 0.25) : 0 }}>
        {isFound ? "Found in 1 second" : "Time's up"}
      </div>
    </div>
  );
};

export const TestLetter: React.FC<{ offset: number }> = ({ offset }) => {
  const t = useSceneTime(offset);
  const { cue } = useTL();
  const start = cue("t1-a").e + 0.2; // the countdown starts after "You have five seconds"
  const up = start + 5;
  const dimP = ramp(t, up, 0.5);
  const markP = ramp(t, up + 0.1, 0.45);
  const dimmed = { opacity: lerp(1, 0.28, dimP) };

  return (
    <SceneFade offset={offset} bg="#0B0C0E">
      <Paper p={ramp(t, 0, 0.5)}>
        <div lang="de" style={{ fontFamily: F.sans, color: "#23262B", fontSize: 20, lineHeight: 1.5 }}>
          <div style={{ ...dimmed, fontSize: 27, fontWeight: 600, marginBottom: 22 }}>{letter.title}</div>
          {letter.paragraphs.map((para, k) => {
            const at = para.indexOf(TARGET_LETTER);
            return (
              <p key={k} style={{ margin: "0 0 13px" }}>
                {at < 0 ? (
                  <span style={dimmed}>{para}</span>
                ) : (
                  <>
                    <span style={dimmed}>{para.slice(0, at)}</span>
                    <Marker p={markP} color={AMBER}>
                      {TARGET_LETTER}
                    </Marker>
                    <span style={dimmed}>{para.slice(at + TARGET_LETTER.length)}</span>
                  </>
                )}
              </p>
            );
          })}
        </div>
      </Paper>
      <Countdown t={t} start={start} inP={ramp(t, 0.3, 0.4)} />
    </SceneFade>
  );
};

export const TestEasy: React.FC<{ offset: number }> = ({ offset }) => {
  const t = useSceneTime(offset);
  const { cue } = useTL();
  const start = cue("t2-a").e + 0.15; // after "Now the easy-language version"
  const found = start + 0.95;
  const markP = ramp(t, found - 0.1, 0.3);

  return (
    <SceneFade offset={offset} bg="#0B0C0E">
      <Paper p={1}>
        <div style={{ position: "absolute", right: 34, top: 28, fontFamily: F.sans, fontSize: 19, color: C.muted, background: C.app, padding: "6px 14px", borderRadius: 999 }}>
          Draft by Leicht·Facile, before review · first {easy.blocks.length} of {easy.total_blocks} blocks
        </div>
        <div lang="de" style={{ fontFamily: F.reader, color: "#1D2127" }}>
          <div style={{ fontSize: 40, fontWeight: 700, marginTop: 34, marginBottom: 10 }}>{easy.title}</div>
          {easy.blocks.map((b) => {
            const at = b.text.indexOf(TARGET_EASY);
            const text =
              at < 0 ? (
                b.text
              ) : (
                <>
                  {b.text.slice(0, at)}
                  <Marker p={markP} color={GREEN}>
                    {TARGET_EASY}
                  </Marker>
                  {b.text.slice(at + TARGET_EASY.length)}
                </>
              );
            if (b.kind === "heading") return <div key={b.id} style={{ fontSize: 32, fontWeight: 700, marginTop: 28, marginBottom: 8 }}>{text}</div>;
            if (b.kind === "list_item")
              return (
                <div key={b.id} style={{ fontSize: 30, lineHeight: 1.45, paddingLeft: 34, position: "relative" }}>
                  <span style={{ position: "absolute", left: 6 }}>•</span>
                  {text}
                </div>
              );
            return <div key={b.id} style={{ fontSize: 30, lineHeight: 1.45, marginBottom: 6 }}>{text}</div>;
          })}
        </div>
      </Paper>
      <Countdown t={t} start={start} found={found} inP={1} />
    </SceneFade>
  );
};
