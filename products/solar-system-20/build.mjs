// Builds the free lead magnet "The Solar System in 20 Numbers" from content.json:
//   node products/solar-system-20/build.mjs
// Output in products/solar-system-20/out/: the PDF (6x9 in, 13 pages), the Gumroad cover (1280x720) and thumbnail
// (600x600). Fonts from assets/fonts (OFL). Uses the Playwright Chromium already on the runner / cloud container.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require("playwright")); } catch { ({ chromium } = require(path.join(process.env.NODE_PATH || "", "playwright"))); }
const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, "../..");
const OUT = path.join(DIR, "out");
fs.mkdirSync(OUT, { recursive: true });
const c = JSON.parse(fs.readFileSync(path.join(DIR, "content.json"), "utf8"));
const font = (f) => "file://" + path.join(ROOT, "assets/fonts", f);
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");

// deterministic star field (same picture every build)
function stars(n, w, h, seed = 7) {
  let s = seed, out = "";
  const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < n; i++) out += `<circle cx="${(r() * w).toFixed(1)}" cy="${(r() * h).toFixed(1)}" r="${(r() * 1.3 + 0.2).toFixed(2)}" opacity="${(r() * 0.7 + 0.2).toFixed(2)}"/>`;
  return `<svg class="stars" viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid slice" fill="#fff">${out}</svg>`;
}

const css = `
@font-face{font-family:SG;src:url(${font("SpaceGrotesk-Bold.ttf")});font-weight:700}
@font-face{font-family:SG;src:url(${font("SpaceGrotesk-Medium.ttf")});font-weight:500}
@font-face{font-family:In;src:url(${font("Inter-Regular.ttf")});font-weight:400}
@font-face{font-family:In;src:url(${font("Inter-SemiBold.ttf")});font-weight:600}
:root{--bg:#070b1a;--ink:#e8ecf7;--mute:#9aa5c4;--acc:#ffc94d;--acc2:#6fd3ff}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:In,sans-serif}
.page{width:6in;height:9in;position:relative;overflow:hidden;padding:.6in .55in;page-break-after:always;
  background:radial-gradient(120% 70% at 80% -10%,#1b2554 0%,var(--bg) 60%)}
.stars{position:absolute;inset:0;width:100%;height:100%;opacity:.55;z-index:0}
.page>*:not(.stars):not(.foot):not(.badge){position:relative;z-index:1}
.foot,.badge{z-index:1}
.brand{font:500 9pt SG;letter-spacing:.2em;text-transform:uppercase;color:var(--acc2)}
.foot{position:absolute;bottom:.4in;left:.55in;right:.55in;display:flex;justify-content:space-between;font:400 7.5pt In;color:var(--mute)}
.cover h1{font:700 48pt/1.02 SG;margin-top:2.4in}
.cover h1 span{color:var(--acc)}
.cover p.sub{font:400 13pt/1.4 In;color:var(--mute);margin-top:.25in;max-width:4.4in}
.cover .badge{position:absolute;right:.55in;bottom:1.1in;font:600 9pt In;color:var(--bg);background:var(--acc);padding:6px 12px;border-radius:99px}
.intro h2,.cta h2{font:700 26pt/1.1 SG;margin:.3in 0 .2in}
.intro p,.cta p{font:400 12.5pt/1.65 In;color:#cfd6ea;margin-bottom:.15in}
.page.facts{display:flex;flex-direction:column}
.fact{border-top:1px solid #2a3566;padding-top:.24in;margin-top:.22in;flex:1}
.fact:first-of-type{margin-top:.25in}
.fact .k{font:500 8pt SG;color:var(--mute);letter-spacing:.15em}
.fact .n{font:700 44pt/1.05 SG;color:var(--acc);margin:.1in 0 .08in}
.fact .n.long{font-size:30pt}
.fact .l{font:600 15pt/1.3 In;margin-bottom:.14in}
.fact .b{font:400 11.5pt/1.55 In;color:#cfd6ea}
.viz{display:block;width:100%;margin-top:.17in;overflow:visible}
.vn{margin-top:.16in;border-left:3px solid var(--acc);padding-left:.12in;font:600 11.5pt/1.4 In;color:var(--ink)}
.fact .s{font:400 8pt In;color:var(--mute);margin-top:.14in}
.fact .s a{color:var(--acc2);text-decoration:none}
.cta .btn{display:inline-block;margin:.15in 0;background:var(--acc);color:var(--bg);font:700 13pt SG;padding:12px 22px;border-radius:10px;text-decoration:none}
.cta .url{font:400 9pt In;color:var(--acc2)}
.cta .disc{font:400 7.5pt/1.5 In;color:var(--mute);margin-top:.35in}
`;

// One small picture per number, drawn from the values in content.json (viz): nothing here is decoration only.
function viz(v) {
  if (!v) return "";
  const W = 440, ACC = "#ffc94d", DIM = "#3b4a8c", T = (x, y, t, o = "") => `<text x="${x}" y="${y}" font-family="In" font-size="11" fill="#cfd6ea" ${o}>${esc(String(t))}</text>`;
  let h = 0, g = "";
  if (v.type === "bars") {
    const max = Math.max(...v.rows.map((r) => r.value)), L = 150, BW = W - L - 110;
    v.rows.forEach((r, i) => {
      const w = Math.max(2.5, (r.value / max) * BW), y = i * 24;
      g += T(L - 10, y + 13, r.label, 'text-anchor="end"') + `<rect x="${L}" y="${y + 3}" width="${w.toFixed(1)}" height="13" rx="3" fill="${r.hi ? ACC : DIM}"/>` +
        T(L + w + 8, y + 13, r.text, r.hi ? `fill="${ACC}" font-weight="600"` : "");
    });
    h = v.rows.length * 24;
  } else if (v.type === "share") {
    const w = (v.pct / 100) * W;
    g = `<rect x="0" y="0" width="${W}" height="22" rx="5" fill="#6fd3ff"/><rect x="0" y="0" width="${w.toFixed(1)}" height="22" rx="5" fill="${ACC}"/>` +
      `<text x="10" y="15" font-family="SG" font-weight="700" font-size="11" fill="#070b1a">${esc(v.a)}</text>` + T(W, 38, v.b, 'text-anchor="end" fill="#6fd3ff"');
    h = 44;
  } else if (v.type === "range") {
    const x = (t) => ((t - v.min) / (v.max - v.min)) * W;
    g = `<defs><linearGradient id="hc"><stop offset="0" stop-color="#6fd3ff"/><stop offset="1" stop-color="#ff7a45"/></linearGradient></defs>
      <rect x="0" y="16" width="${W}" height="12" rx="6" fill="url(#hc)"/>` + T(0, 10, `night: ${v.min} ${v.unit}`) + T(W, 10, `day: ${v.max} ${v.unit}`, 'text-anchor="end"') +
      v.marks.map((m, i) => `<line x1="${x(m.at)}" x2="${x(m.at)}" y1="13" y2="34" stroke="#e8ecf7"/>` + T(x(m.at) + (i ? 5 : -5), 46, `${m.at} ${v.unit}: ${m.label}`, `text-anchor="${i ? "start" : "end"}" font-size="9.5"`)).join("");
    h = 50;
  } else if (v.type === "dots") {
    const s = (W - 40) / v.n;
    g = Array.from({ length: v.n }, (_, i) => `<circle cx="${(20 + s * (i + 0.5)).toFixed(1)}" cy="12" r="${(s / 2 - 1).toFixed(1)}" fill="${i ? DIM : "#6fd3ff"}"/>`).join("") +
      `<circle cx="${W - 8}" cy="12" r="${(s * 0.27 / 2 + 0.6).toFixed(1)}" fill="#e8ecf7"/>` + T(20, 36, v.a, 'fill="#6fd3ff"') + T(W, 36, v.b, 'text-anchor="end"') + T(W / 2, 36, v.caption, 'text-anchor="middle" font-size="9.5"');
    h = 42;
  } else if (v.type === "circles") {
    const max = Math.max(...v.items.map((i) => i.d)), R = 38; let x = 0;
    v.items.forEach((it) => { const r = Math.max(3.4, (it.d / max) * R); x += r;
      g += `<circle cx="${x.toFixed(1)}" cy="${R}" r="${r.toFixed(1)}" fill="${it.hi ? ACC : "#6fd3ff"}"/>` + T(x + r + 8, R + 4, it.label, it.hi ? `fill="${ACC}" font-weight="600"` : ""); x += r + 8 + it.label.length * 5.6 + 22; });
    h = R * 2;
  } else if (v.type === "tilt") {
    v.items.forEach((it, i) => { const cx = 40 + i * 210, cy = 36;
      g += `<line x1="${cx - 36}" x2="${cx + 36}" y1="${cy}" y2="${cy}" stroke="#2a3566" stroke-dasharray="2 3"/><circle cx="${cx}" cy="${cy}" r="20" fill="${it.hi ? "#7fe0d8" : "#6fd3ff"}"/>
        <line x1="${cx}" y1="${cy + 34}" x2="${cx}" y2="${cy - 34}" stroke="${ACC}" stroke-width="2" transform="rotate(${it.deg} ${cx} ${cy})"/>` + T(cx + 44, cy + 4, it.label, it.hi ? `fill="${ACC}" font-weight="600"` : ""); });
    h = 72;
  } else if (v.type === "note") {
    return `<div class="vn">${esc(v.text)}</div>`;
  }
  return `<svg class="viz" viewBox="0 0 ${W} ${h}" style="height:${(h / 96 * 1.02).toFixed(2)}in">${g}</svg>`;
}

const foot = (i) => `<div class="foot"><span>${esc(c.brand)} · ${esc(c.title)}</span><span>${i}</span></div>`;
const fact = (f, i) => `<div class="fact"><div class="k">NUMBER ${String(i + 1).padStart(2, "0")}</div>
  <div class="n${f.n.length > 11 ? " long" : ""}">${esc(f.n)}</div><div class="l">${esc(f.label)}</div>
  <div class="b">${esc(f.body)}</div>${viz(f.viz)}<div class="s">Source: <a href="${f.url}">${esc(f.src)}</a></div></div>`;

let pages = [`<section class="page cover">${stars(260, 600, 900)}<div class="brand">${esc(c.brand)}</div>
  <h1>The Solar System in <span>20 Numbers</span></h1><p class="sub">${esc(c.subtitle)}</p>
  <div class="badge">Free guide · NASA-checked</div>${foot("")}</section>`,
  `<section class="page intro">${stars(120, 600, 900, 11)}<div class="brand">Before you start</div>
  <h2>Real space, real data.</h2><p>${esc(c.intro)}</p>
  <p>The numbers run from the Sun outward, so by the last page you are 25 billion km from home.</p>${foot(2)}</section>`];
for (let i = 0; i < c.facts.length; i += 2) {
  pages.push(`<section class="page facts">${stars(90, 600, 900, 20 + i)}<div class="brand">${esc(c.brand)}</div>
    ${fact(c.facts[i], i)}${c.facts[i + 1] ? fact(c.facts[i + 1], i + 1) : ""}${foot(pages.length + 1)}</section>`);
}
pages.push(`<section class="page cta">${stars(200, 600, 900, 99)}<div class="brand">What's next</div>
  <h2>${esc(c.cta.head)}</h2><p>${esc(c.cta.body)}</p>
  <a class="btn" href="${c.cta.link}">${esc(c.cta.button)} →</a><div class="url">${c.cta.link.replace("https://", "")}</div>
  <p style="margin-top:.3in">New space-by-the-numbers videos every week: <span class="url">${c.cta.yt}</span></p>
  <p class="disc">${esc(c.disclaimer)}</p>${foot(pages.length + 1)}</section>`);

const html = `<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${pages.join("")}</body></html>`;
fs.writeFileSync(path.join(OUT, "guide.html"), html); // removed after the PDF is made

const coverHtml = (w, h) => `<!doctype html><html><head><meta charset="utf-8"><style>${css}
  body{width:${w}px;height:${h}px;overflow:hidden}
  .art{width:${w}px;height:${h}px;position:relative;padding:${h * 0.09}px;background:radial-gradient(120% 90% at 85% 0%,#22306b 0%,var(--bg) 62%)}
  .art .brand{font-size:${h * 0.03}px}
  .art h1{font:700 ${w > h ? h * 0.15 : h * 0.12}px/1 SG;margin-top:${h * 0.12}px;max-width:${w * 0.8}px}
  .art h1 span{color:var(--acc)}
  .art .tag{position:absolute;left:${h * 0.09}px;bottom:${h * 0.09}px;font:600 ${h * 0.035}px In;color:var(--bg);background:var(--acc);padding:.4em .9em;border-radius:99px}
  .art .num{position:absolute;right:${h * 0.07}px;bottom:${h * 0.02}px;font:700 ${h * 0.5}px/1 SG;color:#ffffff10}
  </style></head><body><div class="art">${stars(Math.round(w * h / 2500), w, h, 5)}<div class="brand">${esc(c.brand)}</div>
  <h1>The Solar System in <span>20 Numbers</span></h1><div class="tag">Free PDF · every number sourced</div><div class="num">20</div></div></body></html>`;

const browser = await chromium.launch(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});
const page = await browser.newPage();
await page.goto("file://" + path.join(OUT, "guide.html"));
await page.waitForTimeout(300);
await page.pdf({ path: path.join(OUT, "the-solar-system-in-20-numbers.pdf"), width: "6in", height: "9in", printBackground: true });
for (const [name, w, h] of [["cover-1280x720.png", 1280, 720], ["thumbnail-600x600.png", 600, 600]]) {
  fs.writeFileSync(path.join(OUT, "_cover.html"), coverHtml(w, h));
  await page.setViewportSize({ width: w, height: h });
  await page.goto("file://" + path.join(OUT, "_cover.html"));
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(OUT, name) });
}
fs.rmSync(path.join(OUT, "_cover.html"));
await browser.close();
fs.rmSync(path.join(OUT, "guide.html"));
console.log("built", pages.length, "pages ->", OUT);
