// Shared overlays: burned-in English captions, the mock-up label, scene wrapper.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { C, F, ramp } from "./theme";
import { Scene, useTL } from "./tl";

type Cap = { start: number; end: number; text: string };

/** Splits a long chunk into two captions at the punctuation nearest its middle. */
function split(text: string): string[] {
  if (text.length <= 62) return [text];
  const mid = text.length / 2;
  const cands = [...text.matchAll(/[,:;] /g)].map((m) => (m.index ?? 0) + 1);
  let at = -1;
  if (cands.length) {
    at = cands.reduce((best, c) => (Math.abs(c - mid) < Math.abs(best - mid) ? c : best), cands[0]);
  }
  if (at < 15 || at > text.length - 15) {
    let i = Math.floor(mid);
    while (i < text.length && text[i] !== " ") i++;
    at = i;
  }
  return [text.slice(0, at).trim(), text.slice(at).trim()];
}

const buildCaps = (scenes: Scene[]): Cap[] => {
  const caps: Cap[] = [];
  for (const s of scenes) {
    for (const c of s.chunks) {
      const parts = split(c.text);
      const total = parts.reduce((n, p) => n + p.length, 0);
      let t = c.start;
      for (const p of parts) {
        const d = ((c.end - c.start) * p.length) / total;
        caps.push({ start: t, end: t + d, text: p });
        t += d;
      }
    }
  }
  return caps;
};

export const Captions: React.FC = () => {
  const { scenes } = useTL();
  const CAPS = React.useMemo(() => buildCaps(scenes), [scenes]);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const i = CAPS.findIndex((c, k) => {
    const next = CAPS[k + 1];
    const until = next ? Math.min(c.end + 0.35, next.start - 0.02) : c.end + 0.35;
    return t >= c.start - 0.05 && t < until;
  });
  if (i < 0) return null;
  const cap = CAPS[i];
  const next = CAPS[i + 1];
  const until = next ? Math.min(cap.end + 0.35, next.start - 0.02) : cap.end + 0.35;
  const op = Math.min(ramp(t, cap.start - 0.05, 0.12), 1 - ramp(t, until - 0.1, 0.1));
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 54 }}>
      <div
        style={{
          opacity: op,
          maxWidth: 1500,
          padding: "12px 26px",
          borderRadius: 12,
          background: "rgba(14, 17, 21, 0.78)",
          color: "#fff",
          fontFamily: F.sans,
          fontWeight: 500,
          fontSize: 40,
          lineHeight: 1.3,
          textAlign: "center",
        }}
      >
        {cap.text}
      </div>
    </AbsoluteFill>
  );
};

export const MockLabel: React.FC = () => (
  <AbsoluteFill style={{ alignItems: "flex-end", padding: "26px 30px" }}>
    <div
      style={{
        fontFamily: F.sans,
        fontWeight: 600,
        fontSize: 17,
        letterSpacing: 2,
        color: "rgba(255,255,255,0.92)",
        background: "rgba(14,17,21,0.55)",
        padding: "6px 14px",
        borderRadius: 999,
      }}
    >
      MOCK-UP
    </div>
  </AbsoluteFill>
);

/** Scene time in seconds (0 at the scene's start; negative during the cross-fade in). */
export const useSceneTime = (offset: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return frame / fps - offset;
};

export const SceneFade: React.FC<{ offset: number; children: React.ReactNode; bg?: string }> = ({ offset, children, bg }) => {
  const t = useSceneTime(offset);
  const op = offset > 0 ? ramp(t, -offset, offset) : 1;
  return <AbsoluteFill style={{ opacity: op, background: bg }}>{children}</AbsoluteFill>;
};

export const Pill: React.FC<{ children: React.ReactNode; color?: string; bg?: string; size?: number; style?: React.CSSProperties }> = ({
  children,
  color = C.ink,
  bg = C.surface,
  size = 26,
  style,
}) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 12,
      padding: "10px 20px",
      borderRadius: 999,
      background: bg,
      color,
      fontFamily: F.sans,
      fontWeight: 500,
      fontSize: size,
      ...style,
    }}
  >
    {children}
  </div>
);
