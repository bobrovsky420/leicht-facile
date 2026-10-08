// The real app, sped up: frames captured from the running UI (capture.mjs) with a camera
// that zooms to what the narration names, a cursor, clicks, key presses and highlight
// rings. The product scenes of both concepts describe their shots and use this.
import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import manifest from "../../public/capture/manifest.json";
import { C, F, easeInOut, lerp, ramp } from "../theme";
import { SceneFade, useSceneTime } from "../ui";

export type R = [number, number, number, number];
export type Cam = { s: number; tx: number; ty: number };
export type Shot = { from: number; img: string; cam: Cam; label: string };
export type Key = { t: number; x: number; y: number };
export type Path = { show: [number, number]; keys: Key[] };
export type Ring = { from: number; to: number; rect: (t: number) => R; color: (t: number) => string };
export type Timer = { from: number; to: number; ms: number; title: string; sub: string };

const K = 1920 / 1440; // CSS px of the capture to video px
const SHOTS = manifest.shots as Record<string, { file: string; rects: Record<string, number[] | null> }>;

export const rect = (shot: string, key: string): R => {
  const r = SHOTS[shot]?.rects[key];
  if (!r) throw new Error(`no rect ${shot}.${key}`);
  return r as R;
};
export const union = (...rs: R[]): R => {
  const x0 = Math.min(...rs.map((r) => r[0]));
  const y0 = Math.min(...rs.map((r) => r[1]));
  const x1 = Math.max(...rs.map((r) => r[0] + r[2]));
  const y1 = Math.max(...rs.map((r) => r[1] + r[3]));
  return [x0, y0, x1 - x0, y1 - y0];
};
export const lerpRect = (a: R, b: R, p: number): R => [lerp(a[0], b[0], p), lerp(a[1], b[1], p), lerp(a[2], b[2], p), lerp(a[3], b[3], p)];
export const FULL: Cam = { s: 1, tx: 0, ty: 0 };
/** The camera that frames a rectangle (CSS px), never showing past the capture's edges. */
export const frame = (r: R, pad = 1.18, maxZoom = 1.9): Cam => {
  const [x, y, w, h] = r;
  const s = Math.max(1, Math.min(maxZoom, 1440 / (w * pad), 810 / (h * pad)));
  const tx = Math.min(0, Math.max(1440 - 1440 * s, 720 - (x + w / 2) * s));
  const ty = Math.min(0, Math.max(810 - 810 * s, 405 - (y + h / 2) * s));
  return { s, tx, ty };
};
const mix = (a: Cam, b: Cam, p: number): Cam => ({ s: lerp(a.s, b.s, p), tx: lerp(a.tx, b.tx, p), ty: lerp(a.ty, b.ty, p) });
const toScreen = (cam: Cam, x: number, y: number) => [(x * cam.s + cam.tx) * K, (y * cam.s + cam.ty) * K];

export const ScreenRecording: React.FC<{
  offset: number;
  end: number;
  shots: Shot[];
  paths: Path[];
  clicks: Key[];
  keycaps: { t: number; label: string }[];
  rings?: Ring[];
  timer?: Timer;
}> = ({ offset, end, shots, paths, clicks, keycaps, rings = [], timer }) => {
  const t = useSceneTime(offset);

  let i = 0;
  while (i + 1 < shots.length && shots[i + 1].from <= t) i++;
  const cur = shots[i];
  const prev = shots[Math.max(0, i - 1)];
  const next = shots[i + 1];
  const move = Math.min(0.55, ((next ? next.from : end) - cur.from) * 0.7);
  const cam = mix(prev.cam, cur.cam, easeInOut((t - cur.from) / Math.max(move, 0.05)));

  let cursor: { x: number; y: number; op: number } | null = null;
  for (const p of paths) {
    if (t < p.show[0] - 0.2 || t > p.show[1] + 0.2) continue;
    const ks = p.keys;
    let x = ks[0].x;
    let y = ks[0].y;
    for (let k = 0; k + 1 < ks.length; k++) {
      if (t >= ks[k].t) {
        const q = easeInOut((t - ks[k].t) / Math.max(0.01, ks[k + 1].t - ks[k].t));
        x = lerp(ks[k].x, ks[k + 1].x, q);
        y = lerp(ks[k].y, ks[k + 1].y, q);
      }
    }
    const op = Math.min(ramp(t, p.show[0] - 0.2, 0.2), 1 - ramp(t, p.show[1], 0.2));
    const [sx, sy] = toScreen(cam, x, y);
    cursor = { x: sx, y: sy, op };
  }

  const labelKey = cur.label;
  const labelStart = shots.find((s) => s.label === labelKey)?.from ?? 0;
  const timerOp = timer ? Math.min(ramp(t, timer.from, 0.25), 1 - ramp(t, timer.to - 0.25, 0.2)) : 0;
  const ms = timer ? Math.round(timer.ms * easeInOut((t - (timer.from + 0.15)) / 0.7)) : 0;

  return (
    <SceneFade offset={offset} bg="#E9ECEF">
      <div style={{ position: "absolute", left: 0, top: 0, width: 1920, height: 1080, transformOrigin: "0 0", transform: `translate(${cam.tx * K}px, ${cam.ty * K}px) scale(${cam.s})` }}>
        <Img src={staticFile(`capture/${SHOTS[cur.img].file}`)} style={{ position: "absolute", left: 0, top: 0, width: 1920, height: 1080 }} />
      </div>

      {rings.map((r, k) => {
        const op = Math.min(ramp(t, r.from, 0.25), 1 - ramp(t, r.to - 0.2, 0.2));
        if (op <= 0.001) return null;
        const [x, y, w, h] = r.rect(t);
        const [x0, y0] = toScreen(cam, x - 5, y - 5);
        const [x1, y1] = toScreen(cam, x + w + 5, y + h + 5);
        return (
          <div
            key={k}
            style={{ position: "absolute", left: x0, top: y0, width: x1 - x0, height: y1 - y0, borderRadius: 12, border: `5px solid ${r.color(t)}`, boxShadow: "0 0 0 6px rgba(255,255,255,0.7)", opacity: op }}
          />
        );
      })}

      {clicks.map((c, k) => {
        const age = t - c.t;
        if (age < 0 || age > 0.45) return null;
        const [x, y] = toScreen(cam, c.x, c.y);
        const r = 12 + age * 90;
        return <div key={k} style={{ position: "absolute", left: x - r, top: y - r, width: r * 2, height: r * 2, borderRadius: "50%", border: "4px solid rgba(31,78,138,0.85)", opacity: 1 - age / 0.45 }} />;
      })}

      {cursor && (
        <svg width="44" height="54" viewBox="0 0 22 27" style={{ position: "absolute", left: cursor.x - 3, top: cursor.y - 2, opacity: cursor.op, filter: "drop-shadow(2px 3px 3px rgba(0,0,0,0.35))" }}>
          <path d="M2 1.5v20.2l5.1-4.6 3.4 7.6 3.6-1.6-3.4-7.4h6.9z" fill="#111" stroke="#fff" strokeWidth="1.6" strokeLinejoin="round" />
        </svg>
      )}

      {keycaps.map((k, n) => {
        const age = t - k.t;
        if (age < 0 || age > 0.5) return null;
        const op = Math.min(ramp(age, 0, 0.06), 1 - ramp(age, 0.38, 0.12));
        return (
          <div key={n} style={{ position: "absolute", left: 60, bottom: 170, opacity: op, transform: `translateY(${(1 - ramp(age, 0, 0.1)) * 6}px)` }}>
            <div style={{ display: "inline-block", minWidth: 80, padding: "14px 24px", textAlign: "center", borderRadius: 14, background: "#fff", border: "2px solid #C9CED6", borderBottomWidth: 6, fontFamily: F.mono, fontWeight: 600, fontSize: 40, color: C.ink, boxShadow: "0 8px 24px rgba(16,24,40,0.25)" }}>
              {k.label}
            </div>
          </div>
        );
      })}

      {timer && timerOp > 0.001 && (
        <div style={{ position: "absolute", right: 90, top: 190, width: 520, padding: "28px 34px", borderRadius: 18, background: "rgba(255,255,255,0.97)", boxShadow: "0 16px 44px rgba(16,24,40,0.28)", borderLeft: `8px solid ${C.code}`, opacity: timerOp, fontFamily: F.sans }}>
          <div style={{ fontSize: 26, color: C.muted, fontWeight: 500 }}>{timer.title}</div>
          <div style={{ fontFamily: F.mono, fontWeight: 600, fontSize: 96, color: C.code, lineHeight: 1.1 }}>
            {ms} <span style={{ fontSize: 48 }}>ms</span>
          </div>
          <div style={{ fontSize: 24, color: C.muted }}>{timer.sub}</div>
        </div>
      )}

      <div style={{ position: "absolute", left: 34, top: 28, display: "flex", gap: 12, alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 16px", borderRadius: 999, background: "rgba(14,17,21,0.78)", color: "#fff", fontFamily: F.sans, fontWeight: 600, fontSize: 20, letterSpacing: 1 }}>
          <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#E5484D" }} />
          REAL APP · SPED UP
        </div>
        <div style={{ padding: "8px 18px", borderRadius: 999, background: "rgba(255,255,255,0.96)", boxShadow: "0 6px 18px rgba(16,24,40,0.18)", color: C.ink, fontFamily: F.sans, fontWeight: 600, fontSize: 24, opacity: ramp(t, labelStart, 0.2) }}>
          {labelKey}
        </div>
      </div>
      <AbsoluteFill style={{ boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.08)", pointerEvents: "none" }} />
    </SceneFade>
  );
};
