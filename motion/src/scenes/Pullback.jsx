// 09 Pullback: start tight on one row of a dark grid and crane up fast so row after row floods in, until the whole
// board of cards fills the frame and the big-picture line lands. Use: revealing the big picture after the details.
import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { DISPLAY, Stage, Tile, lerp, theme, tileAt, useUnit, wordsAt } from "../lib.jsx";

export const Pullback = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames: D } = useVideoConfig();
  const { u, width, height, vertical } = useUnit();
  const t = theme(p);
  const cols = vertical ? 5 : 8, rows = vertical ? 9 : 6;
  const gap = 18 * u;
  const cw = (width * 0.96 - gap * (cols - 1)) / cols;
  const ch = cw * (vertical ? 1.15 : 0.62);
  const boardH = rows * ch + (rows - 1) * gap;
  const startRow = rows - 1;
  const prog = lerp(f, 4, D * 0.72, 0, 1, Easing.bezier(0.7, 0, 0.2, 1));
  const zoom = 3.4 - 2.4 * prog * 1.02;
  const focusY = (startRow + 0.5) * (ch + gap) * (1 - prog) + boardH / 2 * prog;
  const titleIn = spring({ frame: f - D * 0.7, fps, config: { damping: 13, stiffness: 140 } });
  const fit = Math.min(1, height * 0.94 / boardH);
  return (
    <Stage t={t} glow={0.2}>
      <AbsoluteFill style={{ perspective: 2000 * u }}>
        <div style={{ position: "absolute", left: (width - (cols * cw + (cols - 1) * gap)) / 2, top: height / 2 - focusY,
                      transformOrigin: `50% ${focusY}px`, transform: `scale(${Math.max(fit, zoom * fit)}) rotateX(${12 * (1 - prog)}deg)`,
                      display: "grid", gridTemplateColumns: `repeat(${cols}, ${cw}px)`, gap }}>
          {Array.from({ length: cols * rows }).map((_, i) => {
            const row = Math.floor(i / cols);
            const dist = startRow - row;
            const appear = lerp(f, 2 + dist * (D * 0.06), 8 + dist * (D * 0.06), 0, 1);
            const hot = p.highlight != null ? i === p.highlight : i === (startRow * cols + Math.floor(cols / 2));
            return (
              <div key={i} style={{ opacity: appear, transform: `translateY(${(1 - appear) * 40 * u}px)` }}>
                <Tile i={i} src={tileAt(p, i)} label={tileAt(p, i) ? null : wordsAt(p, i)} t={t} w={cw} h={ch} radius={14 * u}
                      style={{ outline: hot ? `${4 * u}px solid ${t.accent}` : undefined,
                               boxShadow: hot ? `0 0 ${50 * u}px ${t.accent}` : undefined }} />
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 50%, transparent 30%, ${t.bg}dd 100%)`,
                             opacity: titleIn }} />
      {p.text ? (
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          <div style={{ maxWidth: width * 0.86, padding: `${30 * u}px ${44 * u}px`, borderRadius: 24 * u, background: `${t.bg}ee`,
                        border: `${3 * u}px solid ${t.accent2}`, textAlign: "center", fontFamily: DISPLAY, fontWeight: 700,
                        color: t.text, fontSize: (p.text.length > 26 ? 70 : 92) * u, lineHeight: 1.05,
                        transform: `scale(${titleIn})`, boxShadow: `0 ${30 * u}px ${80 * u}px #000c` }}>{p.text}</div>
        </AbsoluteFill>
      ) : null}
    </Stage>
  );
};
