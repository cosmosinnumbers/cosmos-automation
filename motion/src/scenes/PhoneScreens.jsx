// 07 Phone Screens: a 3D phone in the centre shows a gently scrolling feed, concentric rings breathe out from
// behind it, small labels pop in on each side. Use: to show a product (our Gumroad guide), an app or a result.
import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY, TEXT, Phone, Stage, Tile, lerp, theme, tileAt, useUnit, wordsAt } from "../lib.jsx";

// Our own cover for the product, drawn in code (no third-party artwork).
const Cover = ({ p, t, w }) => {
  const stars = Array.from({ length: 40 }).map((_, i) => {
    const a = (i * 137.5) % 360, r = ((i * 53) % 100) / 100;
    return { x: 50 + Math.cos(a) * r * 45, y: 42 + Math.sin(a) * r * 30, s: 1 + (i % 4) };
  });
  return (
    <div style={{ width: w * 0.86, height: w * 1.2, margin: `${w * 0.2}px auto ${w * 0.05}px`, borderRadius: w * 0.04,
                  position: "relative", overflow: "hidden",
                  background: `radial-gradient(circle at 50% 35%, ${t.bg2} 0%, ${t.bg} 75%)`,
                  boxShadow: `0 0 0 2px ${t.accent}66, 0 ${w * 0.04}px ${w * 0.1}px #000a` }}>
      {stars.map((s, i) => (
        <div key={i} style={{ position: "absolute", left: `${s.x}%`, top: `${s.y}%`, width: s.s * w / 300,
                              height: s.s * w / 300, borderRadius: 9, background: i % 7 ? t.text : t.accent }} />
      ))}
      <div style={{ position: "absolute", left: 0, right: 0, bottom: w * 0.16, textAlign: "center", fontFamily: DISPLAY,
                    fontWeight: 700, fontSize: w * 0.16, color: t.accent, letterSpacing: w * 0.006 }}>{p.product || "LOOK UP"}</div>
      <div style={{ position: "absolute", left: w * 0.05, right: w * 0.05, bottom: w * 0.07, textAlign: "center",
                    fontFamily: TEXT, fontWeight: 600, fontSize: w * 0.05, color: t.text }}>{p.productSub || ""}</div>
    </div>
  );
};

export const PhoneScreens = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const { u, width, vertical } = useUnit();
  const t = theme(p);
  const pw = (vertical ? 500 : 380) * u;
  const inS = spring({ frame: f, fps, config: { damping: 16, stiffness: 110 } });
  const scroll = f * 2.2 * u;
  const labels = p.labels || [];
  return (
    <Stage t={t} glow={0.5}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        {[0, 1, 2, 3, 4].map((k) => {
          const ph = ((f / fps) * 0.7 + k / 5) % 1;
          return (
            <div key={k} style={{ position: "absolute", width: pw * 1.2, height: pw * 1.2, borderRadius: "50%",
                                  border: `${3 * u}px solid ${k % 2 ? t.accent2 : t.accent}`,
                                  transform: `scale(${0.6 + ph * 2.6})`, opacity: (1 - ph) * 0.55 }} />
          );
        })}
      </AbsoluteFill>
      <AbsoluteFill style={{ perspective: 1600 * u, alignItems: "center", justifyContent: "center" }}>
        <div style={{ transform: `translateY(${(1 - inS) * 400 * u}px) rotateY(${lerp(f, 0, durationInFrames, -14, 10)}deg) rotateX(8deg)` }}>
          <Phone w={pw} t={t} u={u}>
            <div style={{ position: "absolute", left: 0, right: 0, top: -scroll }}>
              {p.product ? <Cover p={p} t={t} w={pw} /> : null}
              {Array.from({ length: 6 }).map((_, i) => (
                <Tile key={i} i={i + 3} src={tileAt(p, i)} label={tileAt(p, i) ? null : wordsAt(p, i)} t={t}
                      w={pw * 0.86} h={pw * 0.55} radius={pw * 0.05} style={{ margin: `${pw * 0.04}px auto` }} />
              ))}
            </div>
          </Phone>
        </div>
      </AbsoluteFill>
      {labels.map((l, i) => {
        const s = spring({ frame: f - 8 - i * 7, fps, config: { damping: 11, stiffness: 180 } });
        const left = i % 2 === 0;
        const y = (vertical ? 22 : 18) + i * (vertical ? 16 : 20);
        return (
          <div key={i} style={{ position: "absolute", top: `${y}%`,
                                [left ? "left" : "right"]: vertical ? 34 * u : width * 0.12,
                                transform: `scale(${s}) rotate(${left ? -4 : 4}deg)`, opacity: Math.min(1, s * 1.4),
                                padding: `${16 * u}px ${24 * u}px`, borderRadius: 18 * u, background: `${t.bg}e6`,
                                border: `${2 * u}px solid ${i % 2 ? t.accent2 : t.accent}`, color: t.text,
                                fontFamily: DISPLAY, fontWeight: 700, fontSize: 50 * u, maxWidth: 480 * u,
                                boxShadow: `0 ${10 * u}px ${40 * u}px #000a` }}>{l}</div>
        );
      })}
    </Stage>
  );
};
