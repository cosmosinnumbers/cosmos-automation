// 14 Light Sweep: the "product launch" reveal of the Katana presets. On a dark stage a huge metallic number tilts up
// from the floor in 3D while it counts, a band of light sweeps across its face, an anamorphic flare streaks through
// at the landing and the number sits on a glossy reflection. props: value, decimals, prefix, suffix, label, sub
// (the same as Charts). Use: a key number, presented like a product spec.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY, Grain, flashAt, inOut, lerp, outExpo, rng, theme, useUnit } from "../lib.jsx";

const fmt = (v, dec) => v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });

export const LightSweep = (p) => {
  const f = useCurrentFrame();
  const { durationInFrames: D } = useVideoConfig();
  const { u, width, height, vertical } = useUnit();
  const t = theme(p);
  const land = Math.min(Math.round(D * 0.55), 54);
  const value = Number(p.value || 0);
  const from = Number(p.from || 0);
  const cnt = lerp(f, 4, land, from, value, outExpo);
  const txt = `${p.prefix || ""}${fmt(f >= land ? value : cnt, p.decimals || 0)}${p.suffix || ""}`;
  const size = Math.min((vertical ? 300 : 280) * u, width * 0.9 / Math.max(1, txt.length * 0.62));
  const tiltX = lerp(f, 0, land, 62, 8, outExpo);
  const tiltY = lerp(f, 0, D, -14, 10, inOut);
  const rise = lerp(f, 0, land, 160 * u, 0, outExpo);
  const sweep = lerp(f, land - 10, land + 14, -60, 160, inOut);    // light band position (%)
  const flare = flashAt(f, [land], 14, 1);
  const r = rng(11);
  const dust = Array.from({ length: 36 }).map(() => [r() * width, r() * height, 1 + r() * 3, r()]);
  const metal = `linear-gradient(100deg, #8d96a8 0%, #f4f6fb 18%, #9aa3b5 34%, #ffffff ${sweep - 6}%, ${t.accent} ${sweep}%, #ffffff ${sweep + 6}%, #aab2c2 78%, #e9edf5 100%)`;
  const textStyle = { fontFamily: DISPLAY, fontWeight: 700, fontSize: size, lineHeight: 1, letterSpacing: -4 * u,
                      whiteSpace: "nowrap", backgroundImage: metal, WebkitBackgroundClip: "text", backgroundClip: "text",
                      color: "transparent" };
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 58%, ${t.bg2} 0%, #05060c 70%)`, overflow: "hidden" }}>
      {/* spotlight cone from above */}
      <AbsoluteFill style={{ background: `conic-gradient(from 168deg at 50% -10%, transparent 0deg, ${t.text}18 12deg, transparent 24deg)`,
                             opacity: lerp(f, 0, 12, 0, 1) }} />
      {dust.map(([x, y, s, k], i) => (
        <div key={i} style={{ position: "absolute", left: x, top: y - f * (0.6 + k) * u, width: s * u, height: s * u,
                              borderRadius: "50%", background: t.text, opacity: 0.12 + 0.25 * k }} />
      ))}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", perspective: 1400 * u }}>
        {p.label ? (
          <div style={{ fontFamily: DISPLAY, fontWeight: 500, fontSize: 38 * u, letterSpacing: 14 * u, color: t.accent2,
                        textTransform: "uppercase", marginBottom: 30 * u, opacity: lerp(f, 6, 16, 0, 1) }}>{p.label}</div>
        ) : null}
        <div style={{ transform: `translateY(${rise}px) rotateX(${tiltX}deg) rotateY(${tiltY}deg)`, transformStyle: "preserve-3d",
                      position: "relative" }}>
          <div style={{ ...textStyle, filter: `drop-shadow(0 ${20 * u}px ${40 * u}px #000)` }}>{txt}</div>
          {/* glossy floor reflection */}
          <div style={{ ...textStyle, position: "absolute", top: "100%", left: 0, transform: "scaleY(-1)", opacity: 0.28,
                        WebkitMaskImage: "linear-gradient(to top, #000 0%, transparent 55%)",
                        maskImage: "linear-gradient(to top, #000 0%, transparent 55%)" }}>{txt}</div>
        </div>
        {p.sub ? (
          <div style={{ marginTop: size * 0.55, fontFamily: DISPLAY, fontWeight: 500, fontSize: 54 * u, color: t.text,
                        opacity: lerp(f, land, land + 10, 0, 0.9), letterSpacing: 2 * u, textAlign: "center",
                        maxWidth: width * 0.85 }}>{p.sub}</div>
        ) : null}
      </AbsoluteFill>
      {/* anamorphic flare at the landing */}
      <div style={{ position: "absolute", left: 0, right: 0, top: "50%", height: 6 * u, marginTop: -3 * u, opacity: flare,
                    background: `linear-gradient(90deg, transparent, ${t.glow} 30%, #fff 50%, ${t.glow} 70%, transparent)`,
                    filter: `blur(${2 * u}px)`, transform: `scaleX(${0.4 + flare * 0.8})` }} />
      <div style={{ position: "absolute", left: "50%", top: "50%", width: 600 * u, height: 600 * u, margin: -300 * u,
                    borderRadius: "50%", opacity: flare * 0.7,
                    background: `radial-gradient(circle, #fff 0%, ${t.glow}55 18%, transparent 55%)` }} />
      <Grain f={f} u={u} opacity={0.12} />
    </AbsoluteFill>
  );
};
