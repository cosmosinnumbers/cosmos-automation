// 06 Charts: a dark dashboard panel where 16 bars grow from the baseline in a staggered wave; height, colour and
// sharpness build from the first bar to the last, and a second wave follows. The headline number counts up.
// Use: any number or growth claim. The bars are a visual rhythm, not data: the real value is the counter.
import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY, TEXT, Stage, lerp, outExpo, theme, useUnit } from "../lib.jsx";

const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const mix = (a, b, k) => {
  const x = hex(a), y = hex(b);
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * k).toString(16).padStart(2, "0")).join("");
};
const fmt = (v, d) => v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

export const Charts = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const { u, width, height, vertical } = useUnit();
  const t = theme(p);
  const N = 16;
  const pw = vertical ? width * 0.88 : width * 0.72;
  const ph = vertical ? height * 0.5 : height * 0.78;
  const chartH = ph * (vertical ? 0.52 : 0.5);
  const panelIn = spring({ frame: f, fps, config: { damping: 18, stiffness: 120 } });
  const countEnd = Math.min(durationInFrames * 0.6, fps * 1.6);
  const prog = lerp(f, 3, countEnd, 0, 1, outExpo);
  const dec = p.decimals || 0;
  const val = p.value != null ? (p.from || 0) + (p.value - (p.from || 0)) * prog : null;
  const finalTxt = p.display || (p.value != null ? `${p.prefix || ""}${fmt(p.value, dec)}${p.suffix || ""}` : "");
  const txt = p.display && prog >= 1 ? p.display
    : val != null ? `${p.prefix || ""}${fmt(val, dec)}${p.suffix || ""}` : finalTxt;
  const big = (finalTxt.length <= 8 ? 170 : finalTxt.length <= 12 ? 130 : 100) * u;
  return (
    <Stage t={t} glow={0.25}>
      {/* vertical: panel kept between the Short's headline (top) and its captions (bottom third) */}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: vertical ? "flex-start" : "center",
                             paddingTop: vertical ? 360 * u : 0 }}>
        <div style={{ width: pw, height: ph, borderRadius: 34 * u, background: `linear-gradient(160deg, ${t.bg2}, ${t.bg})`,
                      border: `${2 * u}px solid ${t.text}1f`, boxShadow: `0 ${40 * u}px ${100 * u}px #000b`,
                      padding: 54 * u, boxSizing: "border-box", position: "relative",
                      transform: `translateY(${(1 - panelIn) * 200 * u}px) scale(${0.9 + 0.1 * panelIn})`, opacity: panelIn }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 * u }}>
            <div style={{ width: 16 * u, height: 16 * u, borderRadius: 99, background: t.accent2,
                          boxShadow: `0 0 ${16 * u}px ${t.accent2}` }} />
            <div style={{ fontFamily: TEXT, fontWeight: 600, fontSize: 30 * u, letterSpacing: 3 * u, color: t.muted,
                          textTransform: "uppercase" }}>{p.label || "Real data"}</div>
          </div>
          <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: big, color: t.accent, marginTop: 18 * u,
                        lineHeight: 1, fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>{txt}</div>
          {p.sub ? <div style={{ fontFamily: DISPLAY, fontWeight: 500, fontSize: 40 * u, color: t.text, marginTop: 14 * u,
                                 opacity: lerp(f, countEnd * 0.7, countEnd, 0, 1) }}>{p.sub}</div> : null}
          <div style={{ position: "absolute", left: 54 * u, right: 54 * u, bottom: 54 * u, height: chartH,
                        display: "flex", alignItems: "flex-end", gap: 12 * u }}>
            {[0.25, 0.5, 0.75].map((g) => (
              <div key={g} style={{ position: "absolute", left: 0, right: 0, bottom: chartH * g, height: 1,
                                    background: `${t.text}14` }} />
            ))}
            {Array.from({ length: N }).map((_, i) => {
              const k = i / (N - 1);
              const w1 = spring({ frame: f - 4 - i * 2.2, fps, config: { damping: 13, stiffness: 120 } });
              const w2 = spring({ frame: f - durationInFrames * 0.5 - i * 1.6, fps, config: { damping: 10, stiffness: 160 } });
              const target = 0.18 + 0.78 * Math.pow(k, 1.35);
              const hgt = chartH * target * w1 * (1 + 0.08 * Math.sin(Math.PI * Math.min(1, w2)));
              const col = mix(t.accent2, t.accent, k);
              return (
                <div key={i} style={{ flex: 1, height: hgt, borderRadius: `${10 * u}px ${10 * u}px 2px 2px`,
                                      background: `linear-gradient(${col}, ${col}66)`,
                                      filter: `blur(${(1 - k) * 2.5 * u}px)`, opacity: 0.55 + 0.45 * k,
                                      boxShadow: i === N - 1 ? `0 0 ${30 * u}px ${t.accent}` : undefined }} />
              );
            })}
          </div>
        </div>
      </AbsoluteFill>
    </Stage>
  );
};
