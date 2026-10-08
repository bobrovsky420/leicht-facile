// Colours from the app's tokens (app.css), plus the architecture colours: purple for
// Apertus, teal for code, amber for the human.
export const C = {
  ink: "#1A1E23",
  muted: "#646C78",
  border: "#D7DBE0",
  app: "#F1F3F5",
  surface: "#FFFFFF",
  accent: "#1F4E8A",
  accentWeak: "#E9EDF3",
  error: "#B42318",
  errorWeak: "#FDEEEC",
  warn: "#B26B00",
  warnWeak: "#FFF4E0",
  ok: "#1E6B3A",
  okWeak: "#E8F3EC",
  apertus: "#6B4FA0",
  apertusWeak: "#F1ECF9",
  code: "#0F766E",
  codeWeak: "#E3F3F1",
  night: "#121519",
};

export const F = {
  sans: '"IBM Plex Sans", system-ui, sans-serif',
  mono: '"IBM Plex Mono", ui-monospace, monospace',
  reader: '"Atkinson Hyperlegible Next", Arial, sans-serif',
};

export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const easeOut = (x: number) => 1 - Math.pow(1 - clamp01(x), 3);
export const easeInOut = (x: number) => {
  const v = clamp01(x);
  return v < 0.5 ? 4 * v * v * v : 1 - Math.pow(-2 * v + 2, 3) / 2;
};
/** 0 before `start`, rising to 1 over `dur` seconds. */
export const ramp = (t: number, start: number, dur = 0.35) => easeOut((t - start) / dur);
/** Fades in at `start`, out before `end`. */
export const win = (t: number, start: number, end: number, fin = 0.3, fout = 0.3) =>
  Math.min(ramp(t, start, fin), 1 - ramp(t, end - fout, fout));
export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
