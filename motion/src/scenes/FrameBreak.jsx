// 08 Frame Break: a character inside a framed poster leans past the edge, then bursts through; the poster cracks
// into a 5x5 grid of tiles that spin away from the centre. Use: a surprise moment or a mid-video reset.
// The character is our own vector drawing (astronaut or rocket); the poster shows a still of the video's own footage.
import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { DISPLAY, Stage, lerp, rng, theme, tileAt, useUnit } from "../lib.jsx";

const Astronaut = ({ s, t }) => (
  <svg width={s} height={s * 1.3} viewBox="0 0 200 260">
    <defs>
      <linearGradient id="suit" x1="0" x2="1"><stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor="#c9d1e3" /></linearGradient>
      <linearGradient id="visor" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor={t.accent2} /><stop offset="1" stopColor="#101830" /></linearGradient>
    </defs>
    <rect x="52" y="92" width="96" height="88" rx="30" fill="#9aa5bd" />
    <rect x="40" y="100" width="34" height="78" rx="17" fill="url(#suit)" transform="rotate(18 57 139)" />
    <rect x="128" y="96" width="34" height="80" rx="17" fill="url(#suit)" transform="rotate(-38 145 136)" />
    <rect x="58" y="96" width="84" height="100" rx="34" fill="url(#suit)" />
    <rect x="74" y="126" width="52" height="26" rx="6" fill="#dfe5f1" stroke="#9aa5bd" strokeWidth="3" />
    <circle cx="86" cy="139" r="5" fill={t.accent} /><circle cx="102" cy="139" r="5" fill={t.accent2} />
    <rect x="64" y="182" width="32" height="64" rx="16" fill="url(#suit)" />
    <rect x="104" y="182" width="32" height="64" rx="16" fill="url(#suit)" />
    <circle cx="100" cy="62" r="52" fill="url(#suit)" />
    <ellipse cx="102" cy="64" rx="38" ry="31" fill="url(#visor)" />
    <ellipse cx="88" cy="52" rx="12" ry="7" fill="#ffffff88" transform="rotate(-20 88 52)" />
  </svg>
);

const Rocket = ({ s, t }) => (
  <svg width={s} height={s * 1.3} viewBox="0 0 200 260">
    <path d="M100 8 C140 40 150 110 140 180 L60 180 C50 110 60 40 100 8 Z" fill="#f2f4fa" />
    <path d="M100 8 C120 24 132 46 137 70 L63 70 C68 46 80 24 100 8 Z" fill={t.accent} />
    <circle cx="100" cy="110" r="20" fill={t.bg2} stroke="#9aa5bd" strokeWidth="6" />
    <path d="M60 140 L28 200 L64 186 Z" fill={t.accent2} /><path d="M140 140 L172 200 L136 186 Z" fill={t.accent2} />
    <path d="M78 184 L122 184 L112 250 Q100 230 88 250 Z" fill={t.accent} opacity="0.9" />
  </svg>
);

export const FrameBreak = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames: D } = useVideoConfig();
  const { u, width, height, vertical } = useUnit();
  const t = theme(p);
  const pw = vertical ? width * 0.74 : width * 0.4;
  const ph = pw * 1.3;
  const burst = Math.round(D * 0.52);
  const inS = spring({ frame: f, fps, config: { damping: 16, stiffness: 120 } });
  const lean = lerp(f, D * 0.18, burst - 2, 0, 1, Easing.bezier(0.5, 0, 0.75, 0));
  const out = spring({ frame: f - burst, fps, config: { damping: 12, stiffness: 120 } });
  const src = p.poster || tileAt(p, 0);
  const cs = pw * 0.7;
  const Char = p.character === "rocket" ? Rocket : Astronaut;
  const broken = f >= burst;
  const r = rng(5);
  const flash = broken ? lerp(f, burst, burst + 5, 0.7, 0) : 0;
  const posterBg = src ? `url(${src}) center/cover` : `linear-gradient(160deg, ${t.bg2}, ${t.accent2}66)`;
  return (
    <Stage t={t} glow={0.35}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", perspective: 1600 * u }}>
        <div style={{ position: "relative", width: pw, height: ph, transform: `scale(${0.8 + 0.2 * inS}) rotate(${-2 * inS}deg)`,
                      opacity: Math.min(1, inS * 2) }}>
          {!broken ? (
            <div style={{ position: "absolute", inset: 0, background: posterBg, borderRadius: 6 * u,
                          boxShadow: `0 0 0 ${18 * u}px #f4f1ea, 0 0 0 ${22 * u}px #0006, 0 ${40 * u}px ${90 * u}px #000c` }} />
          ) : (
            Array.from({ length: 25 }).map((_, i) => {
              const cx = i % 5, cy = Math.floor(i / 5);
              const dx = cx - 2 + (r() - 0.5) * 0.6, dy = cy - 2 + (r() - 0.5) * 0.6;
              const sp = 1 + r();
              const k = out;
              return (
                <div key={i} style={{ position: "absolute", left: cx * pw / 5, top: cy * ph / 5, width: pw / 5 + 1,
                                      height: ph / 5 + 1, background: src ? `url(${src})` : posterBg,
                                      backgroundSize: src ? `${pw}px ${ph}px` : undefined,
                                      backgroundPosition: src ? `${-cx * pw / 5}px ${-cy * ph / 5}px` : undefined,
                                      border: `${2 * u}px solid #f4f1ea`, boxSizing: "border-box",
                                      transform: `translate3d(${dx * k * 320 * u * sp}px, ${dy * k * 320 * u * sp + k * k * 200 * u}px, ${k * 400 * u * sp}px) rotateX(${dy * k * 220}deg) rotateY(${dx * k * 260}deg) rotateZ(${(r() - 0.5) * k * 180}deg)`,
                                      opacity: 1 - lerp(f, burst + D * 0.25, D, 0, 1) }} />
              );
            })
          )}
          {/* the character: clipped by the poster, then leaning past its right edge, then free */}
          <div style={{ position: "absolute", inset: 0,
                        clipPath: broken ? "none" : `inset(0 ${-lean * 70}% 0 0)` }}>
            <div style={{ position: "absolute", left: pw / 2 - cs / 2, top: ph / 2 - cs * 0.6,
                          transform: broken
                            ? `translate(${lerp(f, burst, D, pw * 0.25, 0)}px, ${-out * 60 * u}px) scale(${1 + out * 0.55}) rotate(${-8 + out * 8}deg)`
                            : `translate(${lean * pw * 0.32}px, ${Math.sin(f / 6) * 6 * u}px) rotate(${lean * 14}deg)` }}>
              <Char s={cs} t={t} />
            </div>
          </div>
        </div>
      </AbsoluteFill>
      {p.text && broken ? (
        <div style={{ position: "absolute", left: 50 * u, right: 50 * u, bottom: vertical ? 240 * u : 80 * u, textAlign: "center",
                      fontFamily: DISPLAY, fontWeight: 700, fontSize: 88 * u, color: t.accent, lineHeight: 1.02,
                      transform: `scale(${out})`, textShadow: `0 ${6 * u}px ${30 * u}px #000` }}>{p.text}</div>
      ) : null}
      <AbsoluteFill style={{ background: t.text, opacity: flash }} />
    </Stage>
  );
};
