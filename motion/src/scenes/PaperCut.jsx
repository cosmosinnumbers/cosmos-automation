// 05 Paper Cut: a cream paper sheet slaps onto a dark stage with a small bounce, and the words press onto it one at
// a time like a letterpress, in sync with the voice (props.words: [{text, at}] with `at` in seconds from the start
// of the scene, from the narration timings). Use: a change of texture in the middle of a dark video.
import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY, Stage, theme, useUnit } from "../lib.jsx";

export const PaperCut = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const { u, width, height, vertical } = useUnit();
  const t = theme(p);
  let words = p.words && p.words.length ? p.words : null;
  if (!words) {
    const list = (p.text || "").split(/\s+/).filter(Boolean);
    const step = (durationInFrames / fps * 0.75) / Math.max(1, list.length);
    words = list.map((w, i) => ({ text: w, at: 0.25 + i * step }));
  }
  const accent = new Set((p.accent || []).map((w) => w.toUpperCase().replace(/[.,!?]/g, "")));
  const slap = spring({ frame: f, fps, config: { damping: 9, stiffness: 220, mass: 0.7 } });
  const sw = vertical ? width * 0.86 : width * 0.62;
  const sh = vertical ? height * 0.56 : height * 0.74;
  const n = words.length;
  const size = (n <= 4 ? 128 : n <= 8 ? 104 : n <= 12 ? 86 : 70) * u;
  return (
    <Stage t={t} glow={0.15}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        {/* drop shadow first, then the sheet */}
        <div style={{ position: "absolute", width: sw, height: sh, borderRadius: 6 * u, background: "#000",
                      filter: `blur(${30 * u}px)`, opacity: 0.6 * slap,
                      transform: `translate(${18 * u}px, ${30 * u}px) rotate(-1.6deg) scale(${1.25 - 0.25 * slap})` }} />
        <div style={{ position: "relative", width: sw, height: sh, borderRadius: 6 * u, overflow: "hidden",
                      background: `radial-gradient(ellipse at 30% 20%, #fffaf0 0%, ${t.paper} 55%, #e2d6bd 100%)`,
                      transform: `rotate(-1.6deg) scale(${1.25 - 0.25 * slap})`, opacity: Math.min(1, slap * 3),
                      boxSizing: "border-box", padding: `${70 * u}px ${64 * u}px`,
                      display: "flex", flexWrap: "wrap", alignContent: "center", justifyContent: "center", gap: `${8 * u}px ${26 * u}px` }}>
          {/* paper fibres */}
          <div style={{ position: "absolute", inset: 0, opacity: 0.18, mixBlendMode: "multiply",
                        backgroundImage: "repeating-linear-gradient(17deg, #0000 0 3px, #a8977633 3px 4px), repeating-linear-gradient(-71deg, #0000 0 5px, #9c8a6922 5px 6px)" }} />
          {words.map((w, i) => {
            const at = Math.round(w.at * fps);
            const press = spring({ frame: f - at, fps, config: { damping: 14, stiffness: 300, mass: 0.6 } });
            const hot = accent.has(w.text.toUpperCase().replace(/[.,!?]/g, ""));
            return (
              <span key={i} style={{ position: "relative", fontFamily: DISPLAY, fontWeight: 700, fontSize: size,
                                      lineHeight: 1.04, color: hot ? "#B4472A" : t.ink, opacity: f >= at ? 1 : 0,
                                      transform: `scale(${1.35 - 0.35 * press})`,
                                      textShadow: `0 ${1.5 * u}px 0 #ffffffaa, 0 -${1 * u}px 0 #00000055`,
                                      filter: `blur(${(1 - press) * 3 * u}px)` }}>{w.text}</span>
            );
          })}
        </div>
      </AbsoluteFill>
    </Stage>
  );
};
