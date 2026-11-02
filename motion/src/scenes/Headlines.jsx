// 04 Headlines: a wall tilted back in 3D with four columns of bold headline cards; neighbouring columns scroll in
// opposite directions. Use: to show that many sources are talking about something. Headlines come from the
// titles of the video's own primary sources (NASA, ESA...), never from other channels.
import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY, TEXT, Pill, Stage, lerp, theme, useUnit } from "../lib.jsx";

export const Headlines = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const { u, width, height, vertical } = useUnit();
  const t = theme(p);
  const heads = (p.headlines && p.headlines.length ? p.headlines : ["New data", "Record", "Confirmed"]);
  const sources = p.sources || [];
  const cols = 4;
  const colW = (vertical ? 380 : 470) * u;
  const cardH = (vertical ? 300 : 250) * u;
  const per = 9;
  const wallIn = spring({ frame: f, fps, config: { damping: 20, stiffness: 80 } });
  const titleIn = spring({ frame: f - 10, fps, config: { damping: 13, stiffness: 150 } });
  return (
    <Stage t={t} glow={0.3}>
      <AbsoluteFill style={{ perspective: 1400 * u, alignItems: "center", justifyContent: "center" }}>
        <div style={{ display: "flex", gap: 28 * u, transformStyle: "preserve-3d",
                      transform: `rotateX(${34 - 6 * wallIn}deg) rotateZ(${-14}deg) scale(${(vertical ? 1.45 : 1.15) * (0.85 + 0.15 * wallIn)})` }}>
          {Array.from({ length: cols }).map((_, c) => {
            const dir = c % 2 ? 1 : -1;
            const off = dir * f * (9 + c) * u - (dir > 0 ? per * (cardH + 24 * u) * 0.5 : 0);
            return (
              <div key={c} style={{ width: colW, transform: `translateY(${off}px)` }}>
                {Array.from({ length: per }).map((_, k) => {
                  const i = (c * 3 + k) % heads.length;
                  const hot = (c + k) % 3 === 0;
                  return (
                    <div key={k} style={{ height: cardH, marginBottom: 24 * u, borderRadius: 18 * u, padding: 28 * u,
                                          boxSizing: "border-box", background: hot ? t.text : t.bg2,
                                          border: `${2 * u}px solid ${hot ? t.text : t.text + "22"}`,
                                          display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                      <div style={{ fontFamily: TEXT, fontWeight: 600, fontSize: 22 * u, letterSpacing: 2 * u,
                                    color: hot ? t.bg : t.accent2, textTransform: "uppercase" }}>
                        {sources.length ? sources[(c + k) % sources.length] : "News"}
                      </div>
                      <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 40 * u, lineHeight: 1.08,
                                    color: hot ? t.bg : t.text, overflow: "hidden", maxHeight: cardH * 0.7 }}>{heads[i]}</div>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ background: `linear-gradient(${t.bg}00 40%, ${t.bg}cc 100%)` }} />
      {p.title ? (
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          <div style={{ transform: `scale(${titleIn}) rotate(-3deg)` }}>
            <Pill text={p.title} t={t} u={u * 1.5} />
          </div>
        </AbsoluteFill>
      ) : null}
    </Stage>
  );
};
