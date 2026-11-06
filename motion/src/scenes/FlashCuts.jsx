// 15 Flash Cuts: the rapid-fire "clipping" montage of the Katana edits. Stills of the video's own footage cut on a
// fast beat (every `cut` frames, speeding up), each one punching in with a different move (zoom, tilt, whip,
// mirror), white frames between some cuts, while one big line stays locked in the centre. props: text (the line),
// cut (frames per still, default 4). Use: a big-picture line, an energy peak.
import React from "react";
import { AbsoluteFill, Img, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY, Grain, Tile, flashAt, lerp, outExpo, rgbSplit, theme, tileAt, useUnit, wordsAt } from "../lib.jsx";

export const FlashCuts = (p) => {
  const f = useCurrentFrame();
  const { durationInFrames: D } = useVideoConfig();
  const { u, width, height, vertical } = useUnit();
  const t = theme(p);
  // cut times: start slow (6 frames) and accelerate down to `cut` frames, like a speed ramp
  const minCut = p.cut || 3;
  const cuts = [0];
  let step = 7;
  while (cuts[cuts.length - 1] < D) {
    cuts.push(cuts[cuts.length - 1] + Math.round(step));
    step = Math.max(minCut, step * 0.82);
  }
  let k = 0;
  cuts.forEach((c, i) => { if (f >= c) k = i; });
  const d = f - cuts[k];
  const len = (cuts[k + 1] || D) - cuts[k];
  const q = d / Math.max(1, len);
  const move = k % 4;
  const tr = [
    `scale(${1.25 - 0.15 * q})`,
    `scale(1.15) rotate(${(1 - q) * 4 - 2}deg)`,
    `scale(1.2) translateX(${(0.5 - q) * 8}%)`,
    `scale(${1.1 + 0.15 * q}) scaleX(-1)`,
  ][move];
  const src = tileAt(p, k);
  const white = flashAt(f, cuts.filter((_, i) => i % 3 === 2), 2, 0.9);
  const text = (p.text || "").toUpperCase();
  const size = Math.min((vertical ? 150 : 140) * u, width * 0.88 / Math.max(6, Math.min(text.length, 16) * 0.6));
  const tIn = lerp(f, 2, 10, 0, 1, outExpo);
  return (
    <AbsoluteFill style={{ background: "#000", overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: tr }}>
        {src ? (
          <Img src={src} style={{ width: "100%", height: "100%", objectFit: "cover",
                                  filter: `contrast(1.25) saturate(1.3) brightness(${k % 2 ? 0.55 : 0.7})` }} />
        ) : (
          <Tile i={k} label={wordsAt(p, k)} t={t} w={width} h={height} radius={0} />
        )}
      </AbsoluteFill>
      {/* letterbox bars: the cinematic crop of the edits */}
      <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: (vertical ? 150 : 90) * u, background: "#000" }} />
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: (vertical ? 150 : 90) * u, background: "#000" }} />
      {/* dark band behind the line: readable on bright stills too */}
      <AbsoluteFill style={{ background: "radial-gradient(ellipse 80% 22% at 50% 50%, #000c 0%, #0008 55%, transparent 100%)" }} />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: `0 ${50 * u}px` }}>
        <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: size, lineHeight: 0.95, color: t.text, textAlign: "center",
                      letterSpacing: -2 * u, transform: `scale(${1.3 - 0.3 * tIn})`, opacity: tIn,
                      textShadow: `${rgbSplit(k % 2 ? 6 * u : 2 * u)}, 0 ${8 * u}px ${40 * u}px #000` }}>{text}</div>
      </AbsoluteFill>
      {/* cut counter in the corner, like a timeline readout */}
      <div style={{ position: "absolute", right: 60 * u, bottom: (vertical ? 180 : 110) * u, fontFamily: DISPLAY, fontWeight: 700,
                    fontSize: 30 * u, color: t.accent, letterSpacing: 4 * u }}>{String(k + 1).padStart(2, "0")} / {String(cuts.length - 1).padStart(2, "0")}</div>
      <Grain f={f} u={u} opacity={0.2} />
      <AbsoluteFill style={{ background: "#fff", opacity: white }} />
    </AbsoluteFill>
  );
};
