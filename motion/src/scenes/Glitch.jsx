// 10 Glitch: for 8 frames the picture breaks up, red and blue channels split and horizontal bands jump sideways,
// then it snaps back clean. Use: a hard cut between sections, or a mistake reveal. Works on a still (props.src)
// or on a text card. Between two real clips the Python renderer applies the same effect to the live frames
// (video/ytf/motion.py glitch()).
import React from "react";
import { AbsoluteFill, Img, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY, Stage, rng, theme, useUnit } from "../lib.jsx";

const Content = ({ p, t, u }) => (p.src ? (
  <Img src={p.src} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
) : (
  <Stage t={t}>
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: 60 * u, textAlign: "center",
                           fontFamily: DISPLAY, fontWeight: 700, color: t.text, fontSize: 120 * u, lineHeight: 1.02 }}>
      {p.text || ""}
    </AbsoluteFill>
  </Stage>
));

export const Glitch = (p) => {
  const f = useCurrentFrame();
  const { durationInFrames: D } = useVideoConfig();
  const { u, height } = useUnit();
  const t = theme(p);
  const glitchFrames = p.glitchFrames || 8;
  const start = p.at != null ? p.at : Math.max(0, Math.floor((D - glitchFrames) / 2));
  const on = f >= start && f < start + glitchFrames;
  const r = rng(f * 13 + 1);
  const amp = on ? (1 - Math.abs((f - start) / glitchFrames - 0.5) * 1.4) * 40 * u : 0;
  const bands = 9;
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <AbsoluteFill><Content p={p} t={t} u={u} /></AbsoluteFill>
      {on ? (
        <>
          <AbsoluteFill style={{ mixBlendMode: "screen", transform: `translateX(${amp}px)`, opacity: 0.85,
                                 filter: "url(#r)" }}><Content p={p} t={t} u={u} /></AbsoluteFill>
          <AbsoluteFill style={{ mixBlendMode: "screen", transform: `translateX(${-amp}px)`, opacity: 0.85,
                                 filter: "url(#b)" }}><Content p={p} t={t} u={u} /></AbsoluteFill>
          {Array.from({ length: bands }).map((_, i) => {
            if (r() < 0.45) return null;
            const y0 = r() * 100, hgt = 2 + r() * 9;
            return (
              <AbsoluteFill key={i} style={{ clipPath: `inset(${y0}% 0 ${Math.max(0, 100 - y0 - hgt)}% 0)`,
                                             transform: `translateX(${(r() - 0.5) * 220 * u}px)` }}>
                <Content p={p} t={t} u={u} />
              </AbsoluteFill>
            );
          })}
          <AbsoluteFill style={{ background: `repeating-linear-gradient(0deg, #0000 0 ${3 * u}px, #0004 ${3 * u}px ${4 * u}px)` }} />
        </>
      ) : null}
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <filter id="r"><feColorMatrix type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" /></filter>
        <filter id="b"><feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" /></filter>
      </svg>
    </AbsoluteFill>
  );
};
