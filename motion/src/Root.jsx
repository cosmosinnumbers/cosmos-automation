// The 15 scenes (11 + the Katana kit) as Remotion compositions. Size, fps, length and props are set per render by render.mjs
// (calculateMetadata reads them from the input props), so the same scene serves Shorts (1080x1920) and
// long videos (1920x1080).
import React from "react";
import { Composition } from "remotion";
import { useFonts } from "./lib.jsx";
import { Orbit } from "./scenes/Orbit.jsx";
import { Vertigo } from "./scenes/Vertigo.jsx";
import { ZoomThrough } from "./scenes/ZoomThrough.jsx";
import { Headlines } from "./scenes/Headlines.jsx";
import { PaperCut } from "./scenes/PaperCut.jsx";
import { Charts } from "./scenes/Charts.jsx";
import { PhoneScreens } from "./scenes/PhoneScreens.jsx";
import { FrameBreak } from "./scenes/FrameBreak.jsx";
import { Pullback } from "./scenes/Pullback.jsx";
import { Glitch } from "./scenes/Glitch.jsx";
import { Typewriter } from "./scenes/Typewriter.jsx";
import { KatanaType } from "./scenes/KatanaType.jsx";
import { ImpactFrame } from "./scenes/ImpactFrame.jsx";
import { LightSweep } from "./scenes/LightSweep.jsx";
import { FlashCuts } from "./scenes/FlashCuts.jsx";

export const SCENES = {
  orbit: [Orbit, 54], vertigo: [Vertigo, 75], zoomthrough: [ZoomThrough, 10], headlines: [Headlines, 90],
  papercut: [PaperCut, 90], charts: [Charts, 90], phonescreens: [PhoneScreens, 75], framebreak: [FrameBreak, 75],
  pullback: [Pullback, 75], glitch: [Glitch, 8], typewriter: [Typewriter, 90],
  // Katana kit (06/11/2026)
  katanatype: [KatanaType, 75], impactframe: [ImpactFrame, 66], lightsweep: [LightSweep, 84], flashcuts: [FlashCuts, 75],
};

const withFonts = (C) => (props) => {
  useFonts();
  return <C {...props} />;
};

export const Root = () => (
  <>
    {Object.entries(SCENES).map(([id, [C, frames]]) => (
      <Composition key={id} id={id} component={withFonts(C)} durationInFrames={frames} fps={30} width={1080} height={1920}
                   defaultProps={{ brand: "cosmos" }}
                   calculateMetadata={({ props }) => ({
                     durationInFrames: props.frames || frames, fps: props.fps || 30,
                     width: props.width || 1080, height: props.height || 1920,
                   })} />
    ))}
  </>
);
