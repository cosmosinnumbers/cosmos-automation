// 11 Typewriter: a terminal window where the line types out at a natural speed with a blinking cursor. The frame of
// every keystroke comes from props.keys (computed by video/ytf/motion.py, which also puts a click sound on each).
// Use: a closing line / CTA, or to show something being built.
import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { MONO, TEXT, Stage, theme, useUnit } from "../lib.jsx";

export const Typewriter = (p) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u, width, vertical } = useUnit();
  const t = theme(p);
  const lines = p.lines || [p.text || ""];
  const full = lines.join("\n");
  const keys = p.keys || Array.from(full).map((_, i) => 6 + i * 2);
  const typed = keys.filter((k) => k <= f).length;
  const shown = full.slice(0, typed);
  const blink = Math.floor(f / (fps * 0.45)) % 2 === 0 || typed < full.length;
  const inS = spring({ frame: f, fps, config: { damping: 16, stiffness: 140 } });
  const ww = vertical ? width * 0.94 : width * 0.66;
  const size = (vertical ? 62 : 50) * u;
  const out = shown.split("\n");
  return (
    <Stage t={t} glow={0.3}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ width: ww, borderRadius: 22 * u, overflow: "hidden", background: "#070a14ee",
                      border: `${2 * u}px solid ${t.text}26`, boxShadow: `0 ${40 * u}px ${110 * u}px #000d, 0 0 ${60 * u}px ${t.glow}22`,
                      transform: `translateY(${(1 - inS) * 120 * u}px) scale(${0.92 + 0.08 * inS})`, opacity: inS }}>
          <div style={{ height: 66 * u, background: "#141a2c", display: "flex", alignItems: "center", gap: 14 * u,
                        padding: `0 ${26 * u}px` }}>
            {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
              <div key={c} style={{ width: 22 * u, height: 22 * u, borderRadius: 99, background: c }} />
            ))}
            <div style={{ flex: 1, textAlign: "center", fontFamily: TEXT, fontWeight: 600, color: t.muted,
                          fontSize: 26 * u, marginRight: 80 * u }}>{p.title || "cosmos ~ zsh"}</div>
          </div>
          <div style={{ padding: `${40 * u}px ${44 * u}px ${54 * u}px`, fontFamily: MONO, fontWeight: 700, fontSize: size,
                        lineHeight: 1.35, color: t.text, minHeight: size * 1.35 * lines.length, whiteSpace: "pre-wrap",
                        wordBreak: "break-word" }}>
            {out.map((ln, i) => (
              <div key={i}>
                <span style={{ color: i === 0 ? t.accent2 : t.muted }}>{p.prompt != null ? (i === 0 ? p.prompt : "  ") : "> "}</span>
                <span style={{ color: i === (p.hotLine != null ? p.hotLine : lines.length - 1) ? t.accent : t.text }}>{ln}</span>
                {i === out.length - 1 ? (
                  <span style={{ display: "inline-block", width: size * 0.58, height: size * 1.05, marginLeft: 4 * u,
                                 verticalAlign: "text-bottom", background: t.accent, opacity: blink ? 1 : 0 }} />
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </AbsoluteFill>
    </Stage>
  );
};
