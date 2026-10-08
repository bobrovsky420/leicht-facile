// Timing: every cue follows the narration timeline written by tts/synth.py. Each
// composition (concept) provides its own timeline through TLContext.
import React from "react";

export const FPS = 30;

export type Chunk = { id: string; text: string; start: number; end: number };
export type Scene = { id: string; start: number; end: number; chunks: Chunk[] };
export type TimelineData = { total: number; scenes: Scene[] };

export const makeTL = (data: TimelineData) => {
  const scene = (id: string): Scene => {
    const s = data.scenes.find((x) => x.id === id);
    if (!s) throw new Error(`no scene ${id}`);
    return s;
  };
  /** A chunk's start and end in seconds, relative to the start of its scene. */
  const cue = (id: string): { s: number; e: number; d: number } => {
    for (const sc of data.scenes) {
      for (const c of sc.chunks) {
        if (c.id === id) return { s: c.start - sc.start, e: c.end - sc.start, d: c.end - c.start };
      }
    }
    throw new Error(`no chunk ${id}`);
  };
  const hasCue = (id: string) => data.scenes.some((sc) => sc.chunks.some((c) => c.id === id));
  return { total: data.total, scenes: data.scenes, scene, cue, hasCue };
};
export type TL = ReturnType<typeof makeTL>;

export const TLContext = React.createContext<TL | null>(null);
export const useTL = (): TL => {
  const tl = React.useContext(TLContext);
  if (!tl) throw new Error("no timeline in context");
  return tl;
};

export const sec = (s: number) => Math.round(s * FPS);
