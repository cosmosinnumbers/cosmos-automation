// 01 Orbit: a tall phone flies up the frame and turns slowly while its feed of tiles scrolls at blur speed,
// a bright label riding on its top edge. Use: the first second of a video (hook).
import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY, Phone, Pill, Stage, Tile, lerp, outExpo, theme, tileAt, useUnit, wordsAt } from "../lib.jsx";

export const Orbit = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const { u, height, vertical } = useUnit();
  const t = theme(p);
  const pw = (vertical ? 560 : 420) * u;
  const ph = pw * 2.05;
  const rise = spring({ frame: f, fps, config: { damping: 18, stiffness: 90, mass: 0.9 } });
  const y = (1 - rise) * (height * 0.9) - lerp(f, 0, durationInFrames, 0, 60 * u);
  const rotY = lerp(f, 0, durationInFrames, -28, 14, (x) => x);
  const rotX = lerp(f, 0, durationInFrames, 16, 6);
  const rotZ = lerp(f, 0, durationInFrames, -7, 3);
  // feed speed: fast at the start, settling at the end, blur follows the speed
  const speed = lerp(f, 0, durationInFrames * 0.85, 1, 0.12, outExpo);
  const scroll = (f * 70 * u * speed + f * 6 * u) % (ph * 2);
  const blur = 10 * speed * u;
  const tileH = pw * 0.62;
  const rows = 14;
  const labelIn = spring({ frame: f - 8, fps, config: { damping: 12, stiffness: 160 } });
  const kickIn = spring({ frame: f - 14, fps, config: { damping: 14, stiffness: 140 } });
  return (
    <Stage t={t} glow={0.6}>
      {/* light streaks behind the phone */}
      {[0, 1, 2, 3, 4, 5].map((k) => (
        <div key={k} style={{ position: "absolute", left: `${10 + k * 16}%`, top: 0, width: 2 * u, height: "100%",
                              background: `linear-gradient(transparent, ${k % 2 ? t.accent2 : t.accent}55, transparent)`,
                              transform: `translateY(${((f * (18 + k * 4) + k * 300) % (height * 2)) - height}px)`,
                              opacity: 0.6 }} />
      ))}
      <AbsoluteFill style={{ perspective: 1800 * u, alignItems: "center", justifyContent: "center" }}>
        <div style={{ transform: `translateY(${y}px) rotateX(${rotX}deg) rotateY(${rotY}deg) rotateZ(${rotZ}deg)`,
                      transformStyle: "preserve-3d", position: "relative" }}>
          <Phone w={pw} t={t} u={u}>
            <div style={{ position: "absolute", left: 0, right: 0, top: -scroll, filter: `blur(${blur}px)` }}>
              {Array.from({ length: rows }).map((_, i) => (
                <Tile key={i} i={i} src={tileAt(p, i)} label={tileAt(p, i) ? null : wordsAt(p, i)} t={t}
                      w={pw * 0.86} h={tileH} radius={pw * 0.06}
                      style={{ margin: `${pw * 0.04}px auto` }} />
              ))}
            </div>
          </Phone>
          {p.label ? (
            <div style={{ position: "absolute", top: -34 * u, left: "50%",
                          transform: `translateX(-50%) translateZ(${40 * u}px) scale(${labelIn})` }}>
              <Pill text={p.label} t={t} u={u} />
            </div>
          ) : null}
        </div>
      </AbsoluteFill>
      {p.kicker ? (
        <div style={{ position: "absolute", left: 60 * u, right: 60 * u, bottom: vertical ? 210 * u : 90 * u,
                      textAlign: "center", fontFamily: DISPLAY, fontWeight: 700, color: t.text,
                      fontSize: (p.kicker.length > 24 ? 74 : 96) * u, lineHeight: 1.02,
                      opacity: kickIn, transform: `translateY(${(1 - kickIn) * 60 * u}px)`,
                      textShadow: `0 ${6 * u}px ${30 * u}px #000` }}>{p.kicker}</div>
      ) : null}
    </Stage>
  );
};
