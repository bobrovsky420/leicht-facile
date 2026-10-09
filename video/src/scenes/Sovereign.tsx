// 1:27 Letters under secrecy may not leave the authority; the kinds of models that fall
// out one by one; Apertus is left, in-house. Categories only, no products or logos.
import React from "react";
import { AirGap, CheckCircle, Cloud, Envelope, Lock, Server } from "../icons";
import { C, F, easeInOut, lerp, ramp } from "../theme";
import { useTL } from "../tl";
import { SceneFade, useSceneTime } from "../ui";
import { Table } from "./Table";

// German, as the letters would be: patient letter, child protection decision, penal order, tax assessment
const LETTERS = ["Patientenbrief", "KESB-Entscheid", "Strafbefehl", "Steuerveranlagung"];
// each kind of model, with the part that rules it out (turns red when it is struck)
const TILES = [
  { pre: "", bad: "Foreign cloud" },
  { pre: "", bad: "Closed model" },
  { pre: "Open weights, ", bad: "secret training data" },
  { pre: "Open data, ", bad: "built abroad" },
];
// version C: in the order the narration names them (the penal order is not named)
const LETTERS_C = ["KESB-Entscheid", "Patientenbrief", "Steuerveranlagung", "Strafbefehl"];
const ROT = [-4, 3, -2, 4];
const rgb = (a: number[], b: number[], p: number) => `rgb(${a.map((v, i) => Math.round(lerp(v, b[i], p))).join(",")})`;
const INK = [26, 30, 35];
const GREY = [138, 144, 153];
const RED = [198, 40, 40];
// the strike line grows from its left end and is turned about it, so it starts below the
// tile's middle (150 px tile, 6 px line) by half its rise: its middle crosses the text's
const STRIKE_W = 354;
const STRIKE_DEG = 6;
const STRIKE_TOP = 150 / 2 - 3 + (STRIKE_W / 2) * Math.sin((STRIKE_DEG * Math.PI) / 180);

export const Sovereign: React.FC<{ offset: number }> = ({ offset }) => {
  const t = useSceneTime(offset);
  const { cue, hasCue } = useTL();
  const a = cue("sov-a");
  // version C opens with "Easy language matters most in the most personal letters." and
  // names the letters one by one, the child protection decision first
  const intro = hasCue("sov-0") ? cue("sov-0") : null;
  const letters = intro ? LETTERS_C : LETTERS;
  const arrive = intro ? [0, 0.62, 0.86, 0.95] : [0, 0.24, 0.48, 0.72];
  const b = cue("sov-b");
  const c = cue("sov-c");
  const d = cue("sov-d");
  const d2 = cue("sov-d2");
  const e = cue("sov-e");
  // version C leaves out Ticino (owner, 9 October): the envelopes stay for "For these letters"
  const f = hasCue("sov-f") ? cue("sov-f") : null;
  const g = cue("sov-g");

  const tilesAt = b.s + b.d * 0.45;
  const up = easeInOut((t - tilesAt) / 0.6);
  // every tile falls on its own sentence, all four before Apertus is named
  const strikes = [b.s + b.d * 0.8, c.s + c.d * 0.35, d.s + d.d * 0.55, d2.s + d2.d * 0.6];
  const apertusAt = e.s + 0.1;
  const iconsAt = e.e - 0.5;
  const envelopesOut = f ? 1 - ramp(t, f.s - 0.1, 0.35) : 1;

  return (
    <SceneFade offset={offset}>
      <Table dim={lerp(0.12, 0.62, up)}>
        {letters.map((label, k) => {
          const inP = easeInOut((t - (a.s + arrive[k] * a.d)) / 0.65);
          const x = 225 + k * 380;
          const y = lerp(320, 60, up) + (1 - inP) * 900; // starts fully below the frame
          const s = lerp(1, 0.56, up);
          const lock = ramp(t, b.s + 0.45 + k * 0.12, 0.3);
          return (
            <div
              key={label}
              style={{
                position: "absolute",
                left: x,
                top: y,
                width: 330,
                height: 220,
                transform: `rotate(${ROT[k] * (1 - up * 0.6)}deg) scale(${s})`,
                transformOrigin: "50% 0%",
                filter: "drop-shadow(16px 22px 18px rgba(0,0,0,0.45))",
                opacity: envelopesOut,
              }}
            >
              <Envelope w={330} h={220} />
              <div lang="de" style={{ position: "absolute", left: 22, top: 20, fontFamily: F.sans, fontWeight: 600, fontSize: 25, color: C.ink }}>{label}</div>
              <div
                style={{
                  position: "absolute",
                  right: -18,
                  top: -18,
                  width: 64,
                  height: 64,
                  borderRadius: "50%",
                  background: C.ink,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transform: `scale(${lock})`,
                  boxShadow: "0 6px 14px rgba(0,0,0,0.35)",
                }}
              >
                <Lock size={34} color="#fff" stroke={2.2} />
              </div>
            </div>
          );
        })}
      </Table>

      {intro && (
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 380,
            textAlign: "center",
            fontFamily: F.reader,
            fontWeight: 700,
            fontSize: 64,
            color: "#fff",
            textShadow: "0 6px 30px rgba(0,0,0,0.6)",
            opacity: Math.min(ramp(t, intro.s - 0.1, 0.4), 1 - ramp(t, a.s - 0.1, 0.35)),
          }}
        >
          Easy language matters most
          <br />
          in the most personal letters.
        </div>
      )}

      {TILES.map((tile, k) => {
        const p = ramp(t, tilesAt + 0.15 + k * 0.08, 0.4);
        const s = easeInOut((t - strikes[k]) / 0.35);
        return (
          <div
            key={tile.bad}
            style={{
              position: "absolute",
              left: 141 + k * 416,
              top: 360,
              width: 390,
              height: 150,
              borderRadius: 18,
              background: `rgba(255,255,255,${lerp(0.96, 0.78, s)})`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0 26px",
              textAlign: "center",
              fontFamily: F.sans,
              fontWeight: 600,
              fontSize: 32,
              lineHeight: 1.2,
              opacity: p,
              transform: `translateY(${(1 - p) * 24}px)`,
            }}
          >
            <span>
              <span style={{ color: rgb(INK, GREY, s) }}>{tile.pre}</span>
              <span style={{ color: rgb(INK, RED, s) }}>{tile.bad}</span>
            </span>
            <div style={{ position: "absolute", left: 18, top: STRIKE_TOP, height: 6, borderRadius: 3, background: "rgba(198,40,40,0.85)", width: STRIKE_W * s, transform: `rotate(-${STRIKE_DEG}deg)`, transformOrigin: "left center" }} />
          </div>
        );
      })}

      <div
        style={{
          position: "absolute",
          left: 460,
          top: 560,
          width: 1000,
          height: 124,
          borderRadius: 20,
          background: "#fff",
          border: `5px solid ${C.ok}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 22,
          fontFamily: F.sans,
          fontWeight: 600,
          fontSize: 38,
          color: C.ink,
          opacity: ramp(t, apertusAt, 0.4),
          transform: `scale(${lerp(0.94, 1, ramp(t, apertusAt, 0.5))})`,
          boxShadow: "0 16px 44px rgba(0,0,0,0.35)",
        }}
      >
        <CheckCircle size={54} color={C.ok} stroke={2.4} />
        Apertus: open data, built in Switzerland, in-house
      </div>

      <div style={{ position: "absolute", left: 0, right: 0, top: 730, display: "flex", justifyContent: "center", gap: 130 }}>
        {[
          { icon: <Server size={58} color="#fff" />, label: "On-premise" },
          { icon: <AirGap size={58} color="#fff" />, label: "Air-gapped" },
          { icon: <Cloud size={58} color="#fff" />, label: "Swiss cloud" },
        ].map((it, k) => (
          <div key={it.label} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, opacity: ramp(t, iconsAt + k * 0.12, 0.35) }}>
            {it.icon}
            <div style={{ fontFamily: F.sans, fontWeight: 500, fontSize: 30, color: "#fff" }}>{it.label}</div>
            {k === 2 && <div style={{ fontFamily: F.sans, fontSize: 22, color: "rgba(255,255,255,0.75)", opacity: ramp(t, g.s + 0.2, 0.4) }}>This demo: CSCS, Lugano</div>}
          </div>
        ))}
      </div>

      {f && (
        <div style={{ position: "absolute", left: 0, right: 0, top: 120, display: "flex", justifyContent: "center", opacity: ramp(t, f.s + 0.15, 0.4) }}>
          <div style={{ padding: "16px 34px", borderRadius: 999, background: "rgba(255,255,255,0.96)", fontFamily: F.sans, fontWeight: 600, fontSize: 36, color: C.ink, boxShadow: "0 12px 34px rgba(0,0,0,0.35)" }}>
            Canton of Ticino: Apertus in-house for sensitive documents
          </div>
        </div>
      )}
    </SceneFade>
  );
};
