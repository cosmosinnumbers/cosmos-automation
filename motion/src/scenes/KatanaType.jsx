// 12 Katana Type: the viral "Katana" kinetic typography. Every word of the line slams onto the screen on the beat of
// the voice (props.words: [{text, at}], `at` in seconds from the start of the scene), huge and uppercase, with a
// white flash, a camera shake and a motion-blur landing. Styles rotate word by word (solid, outline, highlight bar),
// numbers and accent words come in the accent colour with an RGB split. Behind: the shot's own still, dark,
// slowly pushing in, with moving film grain. Use: a short punchy line of the narration.
import React from "react";
import { AbsoluteFill, Img, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY, Grain, flashAt, lerp, outExpo, posterOf, rgbSplit, shakeAt, theme, useUnit } from "../lib.jsx";

const clean = (w) => w.toUpperCase().replace(/[.,!?;:"“”]/g, "");

export const KatanaType = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames: D } = useVideoConfig();
  const { u, width, vertical } = useUnit();
  const t = theme(p);
  let words = p.words && p.words.length ? p.words : null;
  if (!words) {
    const list = (p.text || "").split(/\s+/).filter(Boolean);
    const step = (D / fps * 0.8) / Math.max(1, list.length);
    words = list.map((w, i) => ({ text: w, at: 0.1 + i * step }));
  }
  const accent = new Set((p.accent || []).map(clean));
  const hot = (w) => accent.has(clean(w)) || /\d/.test(w);
  const hits = words.map((w) => Math.round(w.at * fps));
  // the word on screen now (the last one that has landed) and the one before it
  let cur = -1;
  hits.forEach((h, i) => { if (f >= h) cur = i; });
  const sh = shakeAt(f, hits, 16 * u);
  const flash = flashAt(f, hits.filter((_, i) => hot(words[i].text)), 5, 0.85) ||
                flashAt(f, hits, 3, 0.28);
  const bg = posterOf(p, 0);
  const push = lerp(f, 0, D, 1.08, 1.22);
  const maxW = width * (vertical ? 0.9 : 0.8);
  const styleOf = (i, w) => {
    if (hot(w)) return "hot";
    return ["solid", "outline", "bar", "solid"][i % 4];
  };
  const Word = ({ i, big }) => {
    const w = words[i];
    const d = f - hits[i];
    const land = lerp(d, 0, 6, 0, 1, outExpo);
    const kind = styleOf(i, w.text);
    const txt = clean(w.text);
    const base = (big ? (vertical ? 260 : 230) : (vertical ? 96 : 84)) * u;
    // long words shrink to fit the width (approx. 0.62 em per uppercase glyph of Space Grotesk Bold)
    const size = Math.min(base, maxW / Math.max(1, txt.length * 0.64));
    const scale = big ? 1.55 - 0.55 * land : 1;
    const blur = big ? (1 - land) * 14 * u : 0;
    const split = big ? (kind === "hot" ? 10 : 4) * u * (1 - land * 0.7) : 0;
    const common = { fontFamily: DISPLAY, fontWeight: 700, fontSize: size, lineHeight: 0.92, letterSpacing: -2 * u,
                     display: "inline-block", whiteSpace: "nowrap", transform: `scale(${scale}) skewX(${big ? (1 - land) * -12 : 0}deg)`,
                     filter: blur > 0.3 ? `blur(${blur}px)` : "none" };
    if (kind === "outline") {
      return <span style={{ ...common, color: "transparent", WebkitTextStroke: `${(big ? 5 : 2.5) * u}px ${t.text}`,
                             textShadow: rgbSplit(split) }}>{txt}</span>;
    }
    if (kind === "bar") {
      const wipe = lerp(d, 0, 5, 0, 100, outExpo);
      return (
        <span style={{ ...common, color: t.bg, padding: `0 ${0.12 * size}px`,
                       background: `linear-gradient(90deg, ${t.text} ${wipe}%, transparent ${wipe}%)` }}>{txt}</span>
      );
    }
    if (kind === "hot") {
      return <span style={{ ...common, color: t.accent, textShadow: `${rgbSplit(split)}, 0 0 ${40 * u}px ${t.accent}aa` }}>{txt}</span>;
    }
    return <span style={{ ...common, color: t.text, textShadow: `${rgbSplit(split)}, 0 ${6 * u}px ${30 * u}px #000c` }}>{txt}</span>;
  };
  return (
    <AbsoluteFill style={{ background: t.bg, overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `translate(${sh.x}px, ${sh.y}px) rotate(${sh.r}deg)` }}>
        {bg ? (
          <Img src={bg} style={{ position: "absolute", inset: -40 * u, width: `calc(100% + ${80 * u}px)`,
                                 height: `calc(100% + ${80 * u}px)`, objectFit: "cover", transform: `scale(${push})`,
                                 filter: "brightness(0.38) contrast(1.25) saturate(0.8) blur(2px)" }} />
        ) : (
          <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 45%, ${t.bg2} 0%, ${t.bg} 75%)` }} />
        )}
        {/* vignette */}
        <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 50%, transparent 35%, #000b 100%)" }} />
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 26 * u }}>
          {cur >= 1 ? <div style={{ opacity: 0.45, transform: `translateY(${-lerp(f - hits[cur], 0, 6, 0, 30 * u, outExpo)}px)` }}>
            <Word i={cur - 1} big={false} /></div> : null}
          {cur >= 0 ? <Word i={cur} big /> : null}
        </AbsoluteFill>
      </AbsoluteFill>
      {/* thin accent frame lines that snap in on the first hit */}
      <AbsoluteFill style={{ border: `${4 * u}px solid ${t.accent}`, margin: 36 * u, opacity: cur >= 0 ? 0.5 : 0,
                             transform: `scale(${1 + 0.04 * (1 - lerp(f - hits[0], 0, 8, 0, 1, outExpo))})` }} />
      <Grain f={f} u={u} opacity={0.16} />
      <AbsoluteFill style={{ background: "#fff", opacity: flash }} />
    </AbsoluteFill>
  );
};
