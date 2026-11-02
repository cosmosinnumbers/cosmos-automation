// 03 Zoom-through: crash-zoom into the centre tile, pass through it like a window and land in a second lit grid.
// Use: moving from one idea to the next without a plain cut. Default length: 10 frames (6 of crash + landing).
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { Stage, Tile, lerp, theme, tileAt, useUnit, wordsAt } from "../lib.jsx";

const Grid = ({ p, t, u, offset, cols, rows, gap, w, h, lit }) => (
  <div style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, ${w}px)`, gap }}>
    {Array.from({ length: cols * rows }).map((_, i) => (
      <Tile key={i} i={i + offset} src={tileAt(p, i + offset)} label={tileAt(p, i + offset) ? null : wordsAt(p, i + offset)}
            t={t} w={w} h={h} radius={20 * u}
            style={{ boxShadow: i === Math.floor(cols * rows / 2) && lit ? `0 0 ${60 * u}px ${t.accent}` : undefined }} />
    ))}
  </div>
);

export const ZoomThrough = (p) => {
  const f = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const { u, vertical } = useUnit();
  const t = theme(p);
  const cols = 3, rows = vertical ? 5 : 3;
  const w = (vertical ? 300 : 360) * u, h = (vertical ? 330 : 220) * u, gap = 26 * u;
  const crash = Math.max(1, Math.round(durationInFrames * 0.6));
  const s1 = lerp(f, 0, crash, 1, 9, Easing.in(Easing.exp));
  const passA = lerp(f, crash - 2, crash, 1, 0);
  const s2 = lerp(f, crash - 2, durationInFrames, 0.55, 1, Easing.bezier(0.16, 1, 0.3, 1));
  const flash = lerp(f, crash - 2, crash, 0, 1) * lerp(f, crash, crash + 3, 1, 0);
  const blur = lerp(f, 0, crash, 0, 14 * u, Easing.in(Easing.quad));
  return (
    <Stage t={t}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: 1 - passA * 0 }}>
        <div style={{ transform: `scale(${s2})`, opacity: 1 - passA }}>
          <Grid p={p} t={t} u={u} offset={20} cols={cols} rows={rows} gap={gap} w={w} h={h} lit />
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: passA,
                             filter: `blur(${blur}px)` }}>
        <div style={{ transform: `scale(${s1})` }}>
          <Grid p={p} t={t} u={u} offset={0} cols={cols} rows={rows} gap={gap} w={w} h={h} lit />
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ background: t.text, opacity: flash * 0.55 }} />
    </Stage>
  );
};
