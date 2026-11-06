// 13 Impact Frame: the "aura" hit of the Katana edits. A white flash, then the picture freezes into a 1-bit manga
// frame (black and white, high contrast, halftone dots) with radial speed lines; the number slams in the middle
// with an RGB split and the camera shakes. In the last frames the colour comes back with a second, smaller flash.
// props: text (the number, e.g. "49×"), sub (what it counts), kicker (optional). Use: a shock number.
import React from "react";
import { AbsoluteFill, Img, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY, Grain, flashAt, lerp, outExpo, posterOf, rgbSplit, rng, shakeAt, theme, useUnit } from "../lib.jsx";

const SpeedLines = ({ f, w, h, color, n = 72, seed = 5 }) => {
  const r = rng(seed + Math.floor(f / 2));   // re-drawn every 2 frames: the lines flicker like hand-drawn ones
  const cx = w / 2, cy = h / 2, R = Math.hypot(w, h);
  const lines = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2 + r() * 0.08;
    const r0 = R * (0.18 + r() * 0.14);
    const spread = 0.004 + r() * 0.01;
    const p1 = [cx + Math.cos(a - spread) * R, cy + Math.sin(a - spread) * R];
    const p2 = [cx + Math.cos(a + spread) * R, cy + Math.sin(a + spread) * R];
    const p0 = [cx + Math.cos(a) * r0, cy + Math.sin(a) * r0];
    lines.push(<polygon key={i} points={`${p0[0]},${p0[1]} ${p1[0]},${p1[1]} ${p2[0]},${p2[1]}`} fill={color} />);
  }
  return <svg width={w} height={h} style={{ position: "absolute", inset: 0 }}>{lines}</svg>;
};

export const ImpactFrame = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames: D } = useVideoConfig();
  const { u, width, height, vertical } = useUnit();
  const t = theme(p);
  const bg = posterOf(p, 1);
  const back = Math.max(D - 10, Math.round(D * 0.8));          // colour returns here
  const mono = f < back;
  const sh = shakeAt(f, [2, 4, back], 22 * u);
  const flash = Math.max(flashAt(f, [0], 4, 1), flashAt(f, [back], 4, 0.6));
  const slam = spring({ frame: f - 3, fps, config: { damping: 12, stiffness: 260, mass: 0.7 } });
  const zoom = lerp(f, 0, D, 1.04, 1.16);
  const text = p.text || "";
  const size = Math.min((vertical ? 380 : 330) * u, width * 0.88 / Math.max(1, text.length * 0.6));
  const split = lerp(f, 3, 12, 18 * u, 3 * u, outExpo);
  return (
    <AbsoluteFill style={{ background: "#000", overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `translate(${sh.x}px, ${sh.y}px) rotate(${sh.r}deg) scale(${zoom})` }}>
        {bg ? (
          <Img src={bg} style={{ width: "100%", height: "100%", objectFit: "cover",
                                 filter: mono ? "grayscale(1) contrast(3.2) brightness(0.9)" : "contrast(1.15) saturate(1.2)" }} />
        ) : (
          <AbsoluteFill style={{ background: mono ? "#111" : `radial-gradient(ellipse, ${t.bg2}, ${t.bg})` }} />
        )}
        {mono ? (
          <>
            {/* halftone dots */}
            <AbsoluteFill style={{ mixBlendMode: "multiply", opacity: 0.55,
                                   backgroundImage: `radial-gradient(circle, #000 ${2.2 * u}px, transparent ${2.6 * u}px)`,
                                   backgroundSize: `${9 * u}px ${9 * u}px` }} />
            <SpeedLines f={f} w={width} h={height} color="#fff" />
            <SpeedLines f={f + 1} w={width} h={height} color="#000" n={40} seed={19} />
          </>
        ) : null}
      </AbsoluteFill>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
        {p.kicker ? <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 46 * u, letterSpacing: 8 * u,
                                  color: mono ? "#000" : t.bg, background: mono ? "#fff" : t.accent, padding: `${6 * u}px ${20 * u}px`,
                                  marginBottom: 24 * u, opacity: slam }}>{p.kicker.toUpperCase()}</div> : null}
        <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: size, lineHeight: 0.9, letterSpacing: -6 * u,
                      color: mono ? "#fff" : t.accent, transform: `scale(${2.2 - 1.2 * slam}) rotate(${(1 - slam) * -6}deg)`,
                      opacity: f >= 3 ? 1 : 0, WebkitTextStroke: mono ? `${4 * u}px #000` : "none",
                      textShadow: `${rgbSplit(split)}, 0 0 ${60 * u}px ${mono ? "#000" : t.accent + "99"}`,
                      paintOrder: "stroke fill" }}>{text}</div>
        {p.sub ? (
          <div style={{ marginTop: 30 * u, fontFamily: DISPLAY, fontWeight: 700, fontSize: 52 * u, color: "#000",
                        background: "#fff", padding: `${8 * u}px ${24 * u}px`, transform: `skewX(-8deg) translateX(${lerp(f, 8, 16, -60 * u, 0, outExpo)}px)`,
                        opacity: lerp(f, 8, 12, 0, 1), maxWidth: width * 0.86, textAlign: "center", textTransform: "uppercase" }}>
            {p.sub}
          </div>
        ) : null}
      </AbsoluteFill>
      <Grain f={f} u={u} opacity={mono ? 0.28 : 0.14} />
      <AbsoluteFill style={{ background: "#fff", opacity: flash }} />
    </AbsoluteFill>
  );
};
