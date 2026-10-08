// The kitchen table in evening light, seen from above: wood planks and grain from SVG
// noise, warm light from the top left, a vignette. Drawn in code, no footage.
import React from "react";
import { AbsoluteFill } from "remotion";
import { F } from "../theme";

export const Table: React.FC<{ children?: React.ReactNode; dim?: number }> = ({ children, dim = 0 }) => (
  <AbsoluteFill style={{ background: "linear-gradient(180deg, #7B4F2E 0%, #6A4226 55%, #5E3A21 100%)", overflow: "hidden" }}>
    <svg width="1920" height="1080" style={{ position: "absolute", inset: 0 }}>
      <defs>
        <filter id="grain" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.0032 0.11" numOctaves="4" seed="11" />
          <feColorMatrix type="matrix" values="0 0 0 0 0.20  0 0 0 0 0.10  0 0 0 0 0.04  0 0 0 1.1 -0.35" />
        </filter>
        <filter id="fine" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="4" />
          <feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.5 0" />
        </filter>
      </defs>
      <rect width="1920" height="1080" filter="url(#grain)" opacity="0.75" />
      <rect width="1920" height="1080" filter="url(#fine)" opacity="0.12" />
      {[205, 430, 650, 880].map((y) => (
        <g key={y}>
          <rect x="0" y={y} width="1920" height="3" fill="rgba(35,18,8,0.55)" />
          <rect x="0" y={y + 3} width="1920" height="1" fill="rgba(255,220,180,0.10)" />
        </g>
      ))}
    </svg>
    {children}
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse 75% 70% at 16% 8%, rgba(255,190,115,0.40), rgba(255,160,80,0.12) 45%, rgba(0,0,0,0) 70%)",
        mixBlendMode: "screen",
      }}
    />
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 46%, rgba(0,0,0,0) 46%, rgba(0,0,0,0.62) 100%)" }} />
    <AbsoluteFill style={{ background: "#07080A", opacity: dim }} />
  </AbsoluteFill>
);

export const Mug: React.FC<{ x: number; y: number }> = ({ x, y }) => (
  <div style={{ position: "absolute", left: x - 105, top: y - 105, width: 210, height: 210 }}>
    <div style={{ position: "absolute", left: 178, top: 78, width: 74, height: 54, borderRadius: 30, border: "16px solid #E8E2D6", boxShadow: "14px 18px 22px rgba(0,0,0,0.35)" }} />
    <div style={{ position: "absolute", inset: 0, borderRadius: "50%", background: "radial-gradient(circle at 38% 34%, #FBF8F2, #E6DFD1 70%, #CFC6B4)", boxShadow: "20px 26px 36px rgba(0,0,0,0.45)" }} />
    <div style={{ position: "absolute", inset: 18, borderRadius: "50%", background: "radial-gradient(circle at 42% 38%, #9A6331, #6E4019 62%, #4F2C10)", boxShadow: "inset 0 6px 14px rgba(0,0,0,0.45)" }} />
    <div style={{ position: "absolute", left: 60, top: 54, width: 46, height: 18, borderRadius: "50%", background: "rgba(255,240,220,0.18)", transform: "rotate(-24deg)" }} />
  </div>
);

export const Glasses: React.FC<{ x: number; y: number; r?: number }> = ({ x, y, r = -12 }) => (
  <svg width="300" height="130" viewBox="0 0 300 130" style={{ position: "absolute", left: x, top: y, transform: `rotate(${r}deg)`, filter: "drop-shadow(10px 14px 8px rgba(0,0,0,0.4))" }}>
    <ellipse cx="80" cy="70" rx="58" ry="44" fill="rgba(200,220,235,0.10)" stroke="#1D1B1A" strokeWidth="7" />
    <ellipse cx="220" cy="70" rx="58" ry="44" fill="rgba(200,220,235,0.10)" stroke="#1D1B1A" strokeWidth="7" />
    <path d="M136 62 Q150 50 164 62" fill="none" stroke="#1D1B1A" strokeWidth="7" />
    <path d="M24 56 L2 20 M276 56 L298 20" stroke="#1D1B1A" strokeWidth="6" strokeLinecap="round" />
  </svg>
);

export const Pen: React.FC<{ x: number; y: number; r?: number }> = ({ x, y, r = 64 }) => (
  <div style={{ position: "absolute", left: x, top: y, width: 300, height: 18, borderRadius: 9, transform: `rotate(${r}deg)`, background: "linear-gradient(180deg, #2F4D7A, #1C3152)", boxShadow: "8px 12px 10px rgba(0,0,0,0.4)" }}>
    <div style={{ position: "absolute", right: -22, top: 4, width: 26, height: 10, background: "#C9C2B4", clipPath: "polygon(0 0, 100% 50%, 0 100%)" }} />
    <div style={{ position: "absolute", left: 30, top: -4, width: 90, height: 6, borderRadius: 3, background: "#B9C3D1" }} />
  </div>
);

const bar = (top: number, width: number, left = 60) => (
  <div key={`${top}-${width}`} style={{ position: "absolute", left, top, width, height: 8, borderRadius: 4, background: "#DCDAD4" }} />
);

const Marked: React.FC<{ top: number; p: number; children: React.ReactNode }> = ({ top, p, children }) => (
  <div style={{ position: "absolute", left: 60, top, fontSize: 15, lineHeight: "22px", color: "#2A2D31" }}>
    <span
      style={{
        backgroundImage: "linear-gradient(transparent 48%, rgba(255, 210, 60, 0.9) 48%, rgba(255, 210, 60, 0.9) 92%, transparent 92%)",
        backgroundSize: `${p * 100}% 100%`,
        backgroundRepeat: "no-repeat",
      }}
    >
      {children}
    </span>
  </div>
);

const Label: React.FC<{ top: number; p: number; text: string }> = ({ top, p, text }) => (
  <div style={{ position: "absolute", left: 600, top: top - 14, display: "flex", alignItems: "center", opacity: p, transform: `translateX(${(1 - p) * -20}px)` }}>
    <div style={{ width: 46, height: 3, background: "rgba(255, 210, 60, 0.95)" }} />
    <div style={{ padding: "8px 18px", borderRadius: 999, background: "rgba(16,19,23,0.88)", color: "#fff", fontFamily: F.sans, fontWeight: 600, fontSize: 26, whiteSpace: "nowrap" }}>
      {text}
    </div>
  </div>
);

/** A made-up letter of the invented Gemeinde Musterwil, with the DE-4 sentence in it. */
export const Letter: React.FC<{ marks?: [number, number, number]; labels?: boolean; style?: React.CSSProperties }> = ({ marks = [0, 0, 0], labels = true, style }) => (
  <div style={{ position: "absolute", width: 600, height: 848, ...style }}>
    <div style={{ position: "absolute", inset: 0, background: "#FBFAF6", borderRadius: 3, boxShadow: "24px 34px 50px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,0,0,0.05)", fontFamily: F.sans, overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 60, top: 54, fontSize: 24, fontWeight: 600, color: "#1D2430" }}>Gemeinde Musterwil</div>
      <div style={{ position: "absolute", left: 60, top: 88, fontSize: 15, color: "#5D646E" }}>Sozialversicherungsstelle</div>
      <div style={{ position: "absolute", left: 60, top: 108, fontSize: 13, color: "#7A818B" }}>Dorfstrasse 1 · 8999 Musterwil</div>
      {bar(72, 160, 380)}
      {bar(92, 140, 380)}
      {bar(112, 110, 380)}
      <div style={{ position: "absolute", left: 60, top: 186, fontSize: 13, color: "#5D646E" }}>Musterwil, 1. Oktober 2026</div>
      <div style={{ position: "absolute", left: 60, top: 222, fontSize: 21, fontWeight: 600, color: "#1D2430" }}>Individuelle Prämienverbilligung 2027</div>
      <div style={{ position: "absolute", left: 60, top: 272, fontSize: 15, color: "#2A2D31" }}>Sehr geehrte Damen und Herren</div>
      {bar(314, 480)}
      {bar(334, 430)}
      <Marked top={360} p={marks[0]}>Anspruch bis zu einem Einkommen von CHF 42'000.-.</Marked>
      {bar(402, 470)}
      {bar(422, 300)}
      <Marked top={450} p={marks[1]}>Einzureichen bis spätestens 31. März 2027.</Marked>
      <div lang="de" style={{ position: "absolute", left: 60, top: 494, width: 480, fontSize: 15, lineHeight: "22px", color: "#2A2D31" }}>
        Es ist nicht unwesentlich, dass Kosten, die nicht fristgerecht geltend gemacht werden, nicht vergütet werden können.
      </div>
      {bar(588, 480)}
      {bar(608, 360)}
      <Marked top={640} p={marks[2]}>Gegen die Verfügung ist innert 30 Tagen Einsprache möglich.</Marked>
      {bar(686, 430)}
      <div style={{ position: "absolute", left: 60, top: 732, fontSize: 15, color: "#2A2D31" }}>Freundliche Grüsse</div>
      <div style={{ position: "absolute", left: 60, top: 760, fontSize: 15, color: "#2A2D31" }}>Sozialversicherungsstelle Musterwil</div>
    </div>
    {labels && (
      <>
        <Label top={371} p={marks[0]} text="their money" />
        <Label top={461} p={marks[1]} text="their deadlines" />
        <Label top={651} p={marks[2]} text="their rights" />
      </>
    )}
  </div>
);
