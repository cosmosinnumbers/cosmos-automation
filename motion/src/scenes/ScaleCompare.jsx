// 16 Scale Compare (15/11/2026): "33 times heavier than the Sun" shown, not just said. One cyan dot is the thing
// everybody knows (the Sun, Earth, Jupiter); the amber dots pile up next to it, one per multiple, while the
// counter runs to the number. It is a count, not a drawing to scale: the picture stays true for mass, size,
// brightness or speed alike. props: value, decimals, word ("heavier"), refName ("the Sun"), poster.
// Use: the first "N times <more> than <something>" sentence of a Short, in place of the Charts dashboard.
import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY, TEXT, Grain, Stage, flashAt, lerp, outExpo, shakeAt, theme, useUnit } from "../lib.jsx";

const fmt = (v, d) => v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

export const ScaleCompare = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames: D } = useVideoConfig();
  const { u, width, height, vertical } = useUnit();
  const t = theme(p);
  const value = p.value || 2;
  const dec = p.decimals || 0;
  const N = Math.max(2, Math.min(300, Math.round(value)));
  const land = Math.round(Math.min(D * 0.62, fps * 1.7));          // the last dot and the number land here
  const prog = lerp(f, 4, land, 0, 1, outExpo);
  const shown = Math.max(1, Math.round(1 + (N - 1) * prog));
  const num = prog >= 1 ? value : Math.min(value, 1 + (value - 1) * prog);
  // grid of dots: as square as the area allows
  const gw = width * (vertical ? 0.84 : 0.5);
  const gh = (vertical ? 360 : 420) * u;
  let cols = Math.ceil(Math.sqrt(N * gw / gh));
  let rows = Math.ceil(N / cols);
  const cell = Math.min(gw / cols, gh / rows, 150 * u);
  const dot = cell * 0.78;
  const sh = shakeAt(f, [land], 14 * u);
  const flash = flashAt(f, [land], 5, 0.5);
  const slam = spring({ frame: f - land, fps, config: { damping: 11, stiffness: 240, mass: 0.6 } });
  const numTxt = `${fmt(num, prog >= 1 ? dec : 0)}×`;
  const size = Math.min(250 * u, width * 0.8 / Math.max(1, numTxt.length * 0.6));
  const ref = (p.refName || "").trim();
  return (
    <Stage t={t} poster={p.poster} f={f} glow={0.3}>
      <AbsoluteFill style={{ transform: `translate(${sh.x}px, ${sh.y}px)`, alignItems: "center",
                             justifyContent: vertical ? "flex-start" : "center", paddingTop: vertical ? 470 * u : 0 }}>
        <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: size, lineHeight: 0.95, color: t.accent,
                      fontVariantNumeric: "tabular-nums", letterSpacing: -4 * u,
                      transform: `scale(${1 + 0.12 * Math.sin(Math.PI * Math.min(1, slam))})`,
                      textShadow: `0 0 ${50 * u}px ${t.accent}88, 0 ${8 * u}px ${30 * u}px #000c` }}>{numTxt}</div>
        <div style={{ marginTop: 14 * u, fontFamily: DISPLAY, fontWeight: 700, fontSize: 50 * u, color: t.bg,
                      background: t.text, padding: `${6 * u}px ${24 * u}px`, transform: "skewX(-8deg)",
                      textTransform: "uppercase", opacity: lerp(f, 6, 12, 0, 1), maxWidth: width * 0.88,
                      textAlign: "center" }}>{`${p.word || "more"} than ${ref}`}</div>
        <div style={{ marginTop: 46 * u, width: cols * cell, display: "flex", flexWrap: "wrap", justifyContent: "center" }}>
          {Array.from({ length: N }).map((_, i) => {
            const on = i < shown;
            const born = i === 0 ? 0 : 4 + ((i - 1) / Math.max(1, N - 1)) * (land - 4);
            const pop = spring({ frame: f - born, fps, config: { damping: 10, stiffness: 300, mass: 0.5 } });
            const col = i === 0 ? t.accent2 : t.accent;
            return (
              <div key={i} style={{ width: cell, height: cell, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <div style={{ width: dot, height: dot, borderRadius: "50%", opacity: on ? 1 : 0,
                              transform: `scale(${on ? pop : 0})`,
                              background: `radial-gradient(circle at 35% 30%, #fff 0%, ${col} 28%, ${col}aa 70%, ${col}55 100%)`,
                              boxShadow: `0 0 ${dot * 0.5}px ${col}99` }} />
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 22 * u, display: "flex", alignItems: "center", gap: 14 * u, fontFamily: TEXT,
                      fontWeight: 600, fontSize: 32 * u, color: t.text, opacity: lerp(f, 2, 10, 0, 1),
                      textShadow: "0 2px 10px #000" }}>
          <div style={{ width: 22 * u, height: 22 * u, borderRadius: 99, background: t.accent2,
                        boxShadow: `0 0 ${14 * u}px ${t.accent2}` }} />
          {`= 1 × ${ref}`}
        </div>
      </AbsoluteFill>
      <Grain f={f} u={u} opacity={0.1} />
      <AbsoluteFill style={{ background: "#fff", opacity: flash }} />
    </Stage>
  );
};
