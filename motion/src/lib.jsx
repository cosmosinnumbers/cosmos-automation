// Shared helpers for the 11 motion-graphics scenes: theme, fonts, easing, seeded random, tiles.
// Everything is drawn in code (CSS/SVG): no third-party footage, images or music. Tiles can show stills of the
// video's own public-domain footage (NASA/ESA), passed in by video/ytf/motion.py as small data URIs.
import React from "react";
import { AbsoluteFill, continueRender, delayRender, Img, interpolate, staticFile, useVideoConfig, Easing } from "remotion";
import "@fontsource/jetbrains-mono/700.css";

export const THEMES = {
  // Cosmos in Numbers (video/ytf/common.py BRAND)
  cosmos: { bg: "#0B1026", bg2: "#141B3D", accent: "#F6AD55", accent2: "#4FD1C5", text: "#F7FAFC",
            muted: "#8A94A6", paper: "#F3EAD7", ink: "#1D1A16", glow: "#4FD1C5" },
  // Companies in Numbers: green/gold finance palette on near-black
  companies: { bg: "#0A0F0D", bg2: "#14201B", accent: "#F2C14E", accent2: "#3DDC97", text: "#F4F7F5",
               muted: "#8E9B95", paper: "#F1EADB", ink: "#1C1A17", glow: "#3DDC97" },
};

export const theme = (p) => ({ ...THEMES[(p && p.brand) || "cosmos"], ...((p && p.theme) || {}) });

export const DISPLAY = "'Space Grotesk', 'Inter', sans-serif";
export const TEXT = "'Inter', sans-serif";
export const MONO = "'JetBrains Mono', 'DejaVu Sans Mono', monospace";

let fontsPromise = null;
const loadFonts = () => {
  if (!fontsPromise) {
    const faces = [
      ["Space Grotesk", "fonts/SpaceGrotesk-Bold.ttf", "700"],
      ["Space Grotesk", "fonts/SpaceGrotesk-Medium.ttf", "500"],
      ["Inter", "fonts/Inter-Bold.ttf", "700"],
      ["Inter", "fonts/Inter-SemiBold.ttf", "600"],
      ["Inter", "fonts/Inter-Regular.ttf", "400"],
    ];
    fontsPromise = Promise.all(
      faces.map(([fam, file, weight]) => {
        const f = new FontFace(fam, `url(${staticFile(file)})`, { weight });
        return f.load().then((ff) => document.fonts.add(ff)).catch(() => null);
      }).concat([document.fonts.load("700 20px 'JetBrains Mono'").catch(() => null)])
    );
  }
  return fontsPromise;
};

export const useFonts = () => {
  const [handle] = React.useState(() => delayRender("fonts"));
  React.useEffect(() => {
    loadFonts().then(() => continueRender(handle));
  }, [handle]);
};

// Unit: 1u = 1px on a 1080-wide vertical frame; scenes work at 1080x1920 and 1920x1080.
export const useUnit = () => {
  const { width, height } = useVideoConfig();
  return { u: Math.min(width, height) / 1080, width, height, vertical: height > width };
};

export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" };
export const lerp = (f, a, b, x, y, ease) =>
  interpolate(f, [a, b], [x, y], { ...clamp, easing: ease || Easing.bezier(0.22, 1, 0.36, 1) });
export const outExpo = Easing.bezier(0.16, 1, 0.3, 1);
export const inOut = Easing.bezier(0.65, 0, 0.35, 1);

export const rng = (seed) => {
  let s = (seed * 9301 + 49297) % 233280 || 1;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
};

// A card: a still of the video's own footage when given, else a generated gradient with a number/word.
export const Tile = ({ i, src, label, t, w, h, radius, style }) => {
  const r = rng(i + 7);
  const hue = r();
  const bgGrad = hue < 0.5
    ? `linear-gradient(${Math.round(r() * 360)}deg, ${t.bg2}, ${t.accent2}55)`
    : `linear-gradient(${Math.round(r() * 360)}deg, ${t.bg2}, ${t.accent}55)`;
  return (
    <div style={{ width: w, height: h, borderRadius: radius, overflow: "hidden", position: "relative",
                  background: bgGrad, border: `1px solid ${t.text}22`, boxShadow: `0 ${h * 0.04}px ${h * 0.12}px #0008`,
                  ...style }}>
      {src ? <Img src={src} style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : null}
      {label ? (
        <div style={{ position: "absolute", left: w * 0.08, bottom: h * 0.08, right: w * 0.08, color: t.text,
                      fontFamily: DISPLAY, fontWeight: 700, fontSize: Math.min(w, h) * 0.2, lineHeight: 1.05,
                      textShadow: "0 2px 12px #000a" }}>{label}</div>
      ) : null}
    </div>
  );
};

export const tileAt = (p, i) => {
  const tiles = (p && p.tiles) || [];
  return tiles.length ? tiles[i % tiles.length] : null;
};

export const wordsAt = (p, i) => {
  const w = (p && p.tileWords) || [];
  return w.length ? w[i % w.length] : null;
};

export const Stage = ({ t, children, glow = 0.35 }) => (
  <div style={{ position: "absolute", inset: 0, overflow: "hidden",
                background: `radial-gradient(ellipse at 50% 45%, ${t.bg2} 0%, ${t.bg} 70%)` }}>
    <div style={{ position: "absolute", inset: 0, opacity: glow,
                  background: `radial-gradient(circle at 50% 50%, ${t.glow}33 0%, transparent 55%)` }} />
    {children}
  </div>
);

export const Pill = ({ text, t, u, color, style }) => (
  <div style={{ display: "inline-block", padding: `${12 * u}px ${26 * u}px`, borderRadius: 999,
                background: color || t.accent, color: t.bg, fontFamily: DISPLAY, fontWeight: 700,
                fontSize: 34 * u, letterSpacing: 1.5 * u, textTransform: "uppercase", whiteSpace: "nowrap",
                boxShadow: `0 ${8 * u}px ${30 * u}px ${(color || t.accent)}66`, ...style }}>{text}</div>
);

// Phone body used by Orbit (01) and Phone Screens (07).
export const Phone = ({ w, t, children, u }) => {
  const h = w * 2.05;
  return (
    <div style={{ width: w, height: h, borderRadius: w * 0.14, background: "#05070d", padding: w * 0.035,
                  boxShadow: `0 ${40 * u}px ${120 * u}px #000c, inset 0 0 0 ${3 * u}px #2a3150, 0 0 0 ${2 * u}px #000`,
                  position: "relative" }}>
      <div style={{ width: "100%", height: "100%", borderRadius: w * 0.11, overflow: "hidden", position: "relative",
                    background: t.bg }}>
        {children}
      </div>
      <div style={{ position: "absolute", top: w * 0.06, left: "50%", width: w * 0.28, height: w * 0.07,
                    marginLeft: -w * 0.14, borderRadius: 999, background: "#000" }} />
    </div>
  );
};

// ---------- Katana kit (06/11/2026): the look of the viral "Katana" edits, all drawn in code ----------
// Film grain: an SVG noise layer whose seed changes every 2 frames (moving grain, not a static texture).
export const Grain = ({ f, opacity = 0.14, u = 1 }) => (
  <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: "overlay", opacity }}>
    <svg width="100%" height="100%">
      <filter id={`grain${Math.floor(f / 2) % 24}`}>
        <feTurbulence type="fractalNoise" baseFrequency={0.9 / Math.max(0.5, u)} numOctaves="2"
                      seed={Math.floor(f / 2) % 24} stitchTiles="stitch" />
        <feColorMatrix type="saturate" values="0" />
      </filter>
      <rect width="100%" height="100%" filter={`url(#grain${Math.floor(f / 2) % 24})`} />
    </svg>
  </AbsoluteFill>
);

// Hand-held camera shake that decays after each hit (frames in `hits`).
export const shakeAt = (f, hits, amp, seed = 3) => {
  let x = 0, y = 0, r = 0;
  for (const h of hits || []) {
    const d = f - h;
    if (d < 0 || d > 9) continue;
    const k = Math.pow(1 - d / 9, 2) * amp;
    const g = rng(h * 31 + d * 7 + seed);
    x += (g() - 0.5) * 2 * k;
    y += (g() - 0.5) * 2 * k;
    r += (g() - 0.5) * 0.6 * k / Math.max(1, amp);
  }
  return { x, y, r };
};

// White flash that fades out over `len` frames after each hit.
export const flashAt = (f, hits, len = 4, peak = 0.75) => {
  let a = 0;
  for (const h of hits || []) {
    const d = f - h;
    if (d >= 0 && d < len) a = Math.max(a, peak * (1 - d / len));
  }
  return a;
};

// The still behind a Katana scene: the shot's own poster, else one of the footage tiles.
export const posterOf = (p, i = 0) => p.poster || p.src || tileAt(p, i);

// Red/cyan split text shadow (chromatic aberration) of strength `k` px.
export const rgbSplit = (k) => k > 0.2 ? `${k}px 0 0 #ff2b5ccc, ${-k}px 0 0 #22e6ffcc` : "none";
