// Line icons drawn as SVG (no icon font, no logos).
import React from "react";

type P = { size?: number; color?: string; stroke?: number };

const Svg: React.FC<P & { children: React.ReactNode; vb?: string }> = ({ size = 48, color = "currentColor", stroke = 2, vb = "0 0 24 24", children }) => (
  <svg width={size} height={size} viewBox={vb} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">
    {children}
  </svg>
);

export const Hourglass: React.FC<P> = (p) => (
  <Svg {...p}>
    <path d="M6 2h12M6 22h12M7 2c0 5 10 6 10 10S7 17 7 22M17 2c0 5-10 6-10 10s10 5 10 10" />
  </Svg>
);

export const ChatNoCheck: React.FC<P> = (p) => (
  <Svg {...p}>
    <path d="M4 5h16v10H9l-5 4V5z" />
    <path d="M10 8.2c.3-1 1.2-1.5 2.1-1.5 1.2 0 2 .8 2 1.8 0 1.4-2 1.6-2 3M12 13.4v.1" />
  </Svg>
);

export const Person: React.FC<P> = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c1.2-4 4.4-6 8-6s6.8 2 8 6" />
  </Svg>
);

export const CheckCircle: React.FC<P> = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="10" />
    <path d="M7.5 12.3l3 3 6-6.5" />
  </Svg>
);

export const Check: React.FC<P> = (p) => (
  <Svg {...p}>
    <path d="M5 12.5l4.5 4.5L19 7" />
  </Svg>
);

export const Lock: React.FC<P> = (p) => (
  <Svg {...p}>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </Svg>
);

export const Server: React.FC<P> = (p) => (
  <Svg {...p}>
    <rect x="4" y="3" width="16" height="7" rx="1.5" />
    <rect x="4" y="14" width="16" height="7" rx="1.5" />
    <path d="M8 6.5h.01M8 17.5h.01M12 6.5h5M12 17.5h5" />
  </Svg>
);

export const AirGap: React.FC<P> = (p) => (
  <Svg {...p}>
    <path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5l8-3z" />
    <path d="M8.5 12h2M13.5 12h2" />
  </Svg>
);

export const Cloud: React.FC<P> = (p) => (
  <Svg {...p}>
    <path d="M7 18h10.5a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.4 9.2 4.4 4.4 0 0 0 7 18z" />
  </Svg>
);

export const Chip: React.FC<P> = (p) => (
  <Svg {...p}>
    <rect x="6" y="6" width="12" height="12" rx="2" />
    <path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4" />
  </Svg>
);

export const Code: React.FC<P> = (p) => (
  <Svg {...p}>
    <path d="M8 7l-5 5 5 5M16 7l5 5-5 5" />
  </Svg>
);

/** A window envelope seen from the front, as Swiss authorities send them: the address
 * window bottom right (blank address lines), the flap closed behind. */
export const Envelope: React.FC<{ w: number; h: number }> = ({ w, h }) => {
  const wx = w * 0.5;
  const wy = h * 0.52;
  const ww = w * 0.42;
  const wh = h * 0.34;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <rect x="1" y="1" width={w - 2} height={h - 2} rx="5" fill="#F6F1E6" stroke="#D9CFB8" strokeWidth="2" />
      <rect x={wx} y={wy} width={ww} height={wh} rx="4" fill="#EEF1F3" stroke="#CBD2D8" strokeWidth="1.5" />
      {[0, 1, 2].map((k) => (
        <rect key={k} x={wx + ww * 0.1} y={wy + wh * (0.24 + k * 0.22)} width={ww * (k === 2 ? 0.45 : 0.68)} height={wh * 0.09} rx="2" fill="#C3CAD1" />
      ))}
    </svg>
  );
};
