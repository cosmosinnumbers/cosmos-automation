// Render a batch of scenes in one Chrome session: node render.mjs <jobs.json>
// jobs.json: [{"effect": "charts", "out": "/abs/path.mp4", "props": {..., "width", "height", "fps", "frames"}}]
// Bundles once, renders every job to H.264 (no audio), prints one JSON line per job. Exit 0 even if some jobs
// fail: video/ytf/motion.py falls back to the plain footage for those, so a daily video is never lost.
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { readFileSync } from "node:fs";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const jobs = JSON.parse(readFileSync(process.argv[2], "utf8"));
const browserExecutable = process.env.REMOTION_CHROME || null;  // null: Remotion downloads its own headless shell
const t0 = Date.now();
const serveUrl = await bundle({ entryPoint: path.join(here, "src", "index.jsx"), publicDir: path.join(here, "..", "assets") });
console.log(JSON.stringify({ bundled: (Date.now() - t0) / 1000 }));
for (const job of jobs) {
  const t1 = Date.now();
  try {
    const composition = await selectComposition({ serveUrl, id: job.effect, inputProps: job.props, browserExecutable });
    await renderMedia({
      composition, serveUrl, codec: "h264", outputLocation: job.out, inputProps: job.props, browserExecutable,
      crf: 16, pixelFormat: "yuv420p", muted: true, concurrency: Math.max(1, os.cpus().length),
      logLevel: "error",
    });
    console.log(JSON.stringify({ ok: job.out, effect: job.effect, s: (Date.now() - t1) / 1000 }));
  } catch (e) {
    console.log(JSON.stringify({ fail: job.out, effect: job.effect, error: String(e && e.message || e).slice(0, 400) }));
  }
}
