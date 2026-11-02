// 02 Vertigo: a long corridor of cards on walls, floor and ceiling, receding to a glowing vanishing point.
// The centre card keeps its size (it sits on the z=0 plane) while the perspective changes: a dolly zoom.
// Use: a shock moment, a line that must land hard.
import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY, Stage, Tile, lerp, inOut, theme, tileAt, useUnit, wordsAt } from "../lib.jsx";

export const Vertigo = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const { u, width, height, vertical } = useUnit();
  const t = theme(p);
  // perspective from long lens to wide angle: the corridor stretches behind a card that never changes size
  const persp = lerp(f, 0, durationInFrames, 2600 * u, 420 * u, inOut);
  const hw = width * 0.5;
  const hh = height * 0.5;
  const depth = 520 * u;
  const n = 9;
  const cardW = vertical ? 330 * u : 300 * u;
  const cards = [];
  for (let k = 0; k < n; k++) {
    const z = -(k + 0.6) * depth;
    // left / right walls
    [[-1, 0], [1, 0], [0, -1], [0, 1]].forEach(([sx, sy], w) => {
      const idx = k * 4 + w;
      const isWall = sx !== 0;
      const cw = isWall ? depth * 0.86 : cardW * 1.6;
      const ch = isWall ? (vertical ? hh * 0.9 : hh * 0.8) : depth * 0.86;
      const tr = isWall
        ? `translate3d(${sx * hw - cw / 2}px, ${-ch / 2}px, ${z}px) rotateY(${-sx * 90}deg)`
        : `translate3d(${-cw / 2}px, ${sy * hh - ch / 2}px, ${z}px) rotateX(${sy * 90}deg)`;
      cards.push(
        <div key={idx} style={{ position: "absolute", left: 0, top: 0, transform: tr, transformStyle: "preserve-3d" }}>
          <Tile i={idx} src={tileAt(p, idx)} label={tileAt(p, idx) ? null : wordsAt(p, idx)} t={t} w={cw} h={ch}
                radius={18 * u} style={{ opacity: 0.92 - k * 0.06 }} />
        </div>
      );
    });
  }
  const pop = spring({ frame: f - 2, fps, config: { damping: 11, stiffness: 170 } });
  const cw0 = vertical ? 820 * u : 900 * u;
  return (
    <Stage t={t} glow={0.2}>
      <AbsoluteFill style={{ perspective: persp, perspectiveOrigin: "50% 50%" }}>
        <div style={{ position: "absolute", left: "50%", top: "50%", transformStyle: "preserve-3d" }}>
          {/* vanishing-point glow */}
          <div style={{ position: "absolute", left: -500 * u, top: -500 * u, width: 1000 * u, height: 1000 * u,
                        borderRadius: "50%", transform: `translateZ(${-(n + 1) * depth}px) scale(3)`,
                        background: `radial-gradient(circle, ${t.glow} 0%, ${t.glow}55 25%, transparent 65%)` }} />
          {cards}
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ width: cw0, padding: `${56 * u}px ${48 * u}px`, borderRadius: 28 * u, background: `${t.bg}ee`,
                      border: `${3 * u}px solid ${t.accent}`, textAlign: "center", transform: `scale(${0.6 + 0.4 * pop})`,
                      boxShadow: `0 0 ${80 * u}px ${t.accent}55, 0 ${30 * u}px ${80 * u}px #000c` }}>
          {p.kicker ? <div style={{ fontFamily: DISPLAY, fontWeight: 700, color: t.accent2, fontSize: 40 * u,
                                    letterSpacing: 3 * u, textTransform: "uppercase", marginBottom: 16 * u }}>{p.kicker}</div> : null}
          <div style={{ fontFamily: DISPLAY, fontWeight: 700, color: t.text, lineHeight: 1.0,
                        fontSize: ((p.text || "").length > 22 ? 84 : 120) * u }}>{p.text}</div>
          {p.sub ? <div style={{ fontFamily: DISPLAY, fontWeight: 500, color: t.muted, fontSize: 40 * u,
                                 marginTop: 18 * u }}>{p.sub}</div> : null}
        </div>
      </AbsoluteFill>
    </Stage>
  );
};
