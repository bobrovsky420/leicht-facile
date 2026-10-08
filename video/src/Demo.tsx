import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { Compare } from "./scenes/Compare";
import { End } from "./scenes/End";
import { Evidence } from "./scenes/Evidence";
import { Hook } from "./scenes/Hook";
import { Kitchen } from "./scenes/Kitchen";
import { Logo } from "./scenes/Logo";
import { LogoA } from "./scenes/LogoA";
import { Product } from "./scenes/Product";
import { ProductA } from "./scenes/ProductA";
import { ProductC } from "./scenes/ProductC";
import { Sovereign } from "./scenes/Sovereign";
import { Step } from "./scenes/Step";
import { TestEasy, TestLetter } from "./scenes/Tests";
import { TIMELINES } from "./timelines";
import { TL, TLContext, sec } from "./tl";
import { Captions, MockLabel } from "./ui";

type Part = { id: string; C: React.FC<{ offset: number }> };
const OVERLAP = 0.3; // each scene fades in over the end of the one before

const Video: React.FC<{ tl: TL; audio: string; parts: Part[] }> = ({ tl, audio, parts }) => (
  <TLContext.Provider value={tl}>
    <AbsoluteFill style={{ background: "#000" }}>
      <Audio src={staticFile(audio)} />
      {parts.map(({ id, C }, i) => {
        const s = tl.scene(id);
        const offset = i === 0 ? 0 : OVERLAP;
        const from = sec(s.start - offset);
        return (
          <Sequence key={id} from={from} durationInFrames={sec(s.end) - from} name={id}>
            <C offset={offset} />
          </Sequence>
        );
      })}
      <Captions />
      <MockLabel />
    </AbsoluteFill>
  </TLContext.Provider>
);

/** The first storyboard: "Can you read this?" */
export const Demo: React.FC = () => (
  <Video
    tl={TIMELINES[""]}
    audio="audio/mix.wav"
    parts={[
      { id: "hook", C: Hook },
      { id: "kitchen", C: Kitchen },
      { id: "logo", C: Logo },
      { id: "product", C: Product },
      { id: "compare", C: Compare },
      { id: "sovereign", C: Sovereign },
      { id: "end", C: End },
    ]}
  />
);

const WhyA: React.FC<{ offset: number }> = ({ offset }) => (
  <Kitchen offset={offset} sceneId="why" number="why-a" marks="why-b" push="why-c" cards="why-d" chatbot={false} />
);
const EndA: React.FC<{ offset: number }> = ({ offset }) => <End offset={offset} kicker="The deadline. In the first sentence." />;

/** Concept A: "Find the deadline" */
export const DemoA: React.FC = () => (
  <Video
    tl={TIMELINES.a}
    audio="audio/mix-a.wav"
    parts={[
      { id: "test1", C: TestLetter },
      { id: "test2", C: TestEasy },
      { id: "why", C: WhyA },
      { id: "logo", C: LogoA },
      { id: "product", C: ProductA },
      { id: "evidence", C: Evidence },
      { id: "sovereign", C: Sovereign },
      { id: "end", C: EndA },
    ]}
  />
);

/** Concept B: "One sentence, step by step", then concept A from the kitchen on */
export const DemoB: React.FC = () => (
  <Video
    tl={TIMELINES.b}
    audio="audio/mix-b.wav"
    parts={[
      { id: "step", C: Step },
      { id: "why", C: WhyA },
      { id: "logo", C: LogoA },
      { id: "product", C: ProductA },
      { id: "evidence", C: Evidence },
      { id: "sovereign", C: Sovereign },
      { id: "end", C: EndA },
    ]}
  />
);

const StakesC: React.FC<{ offset: number }> = ({ offset }) => (
  <Kitchen offset={offset} sceneId="stakes" number="sk-b" marks="sk-c" push={null} cards={null} chatbot={false} />
);
const HookC: React.FC<{ offset: number }> = ({ offset }) => <Hook offset={offset} marksCue="hook-b" />;
const LogoC: React.FC<{ offset: number }> = ({ offset }) => <LogoA offset={offset} introCue="lg-0" />;
const EndC: React.FC<{ offset: number }> = ({ offset }) => <End offset={offset} sub="Every person. Every fact." />;

/** Concept C: the "Can you read this?" opening, then the step by step and B's composition */
export const DemoC: React.FC = () => (
  <Video
    tl={TIMELINES.c}
    audio="audio/mix-c.wav"
    parts={[
      { id: "hook", C: HookC },
      { id: "stakes", C: StakesC },
      { id: "logo", C: LogoC },
      { id: "step", C: Step },
      { id: "product", C: ProductC },
      { id: "evidence", C: Evidence },
      { id: "sovereign", C: Sovereign },
      { id: "end", C: EndC },
    ]}
  />
);
