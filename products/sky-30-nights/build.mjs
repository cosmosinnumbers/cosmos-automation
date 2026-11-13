// Builds the free lead magnet "The Next 30 Nights" (a rolling sky calendar) from out/sky.json:
//   python tools/sky.py window --days 30 --out products/sky-30-nights/out/sky.json
//   node products/sky-30-nights/build.mjs
// Output in products/sky-30-nights/out/: the PDF (6x9 in, 3 pages), the Gumroad cover (1280x720) and thumbnail
// (600x600). Every date and number on the pages comes from sky.json (computed by tools/sky.py): no text is written
// by a model. Rebuilt every week by sky-calendar.yml, so the download is always about the coming nights.
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
const sky = JSON.parse(fs.readFileSync(path.join(OUT, "sky.json"), "utf8"));
const font = (f) => "file://" + path.join(ROOT, "assets/fonts", f);
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
const LOOK = "https://cosmosinnumbers.gumroad.com/l/look-up";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const day = (iso) => { const [y, m, d] = iso.slice(0, 10).split("-").map(Number); return `${MONTHS[m - 1]} ${d}`; };
const range = `${day(sky.start)} to ${day(sky.end)}, ${sky.end.slice(0, 4)}`;

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
:root{--bg:#070b1a;--ink:#e8ecf7;--mute:#9aa5c4;--acc:#ffc94d;--acc2:#6fd3ff;--line:#2a3566}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:In,sans-serif}
.page{width:6in;height:9in;position:relative;overflow:hidden;padding:.5in .5in .7in;page-break-after:always;
  background:radial-gradient(120% 70% at 80% -10%,#1b2554 0%,var(--bg) 60%)}
.stars{position:absolute;inset:0;width:100%;height:100%;opacity:.45;z-index:0}
.page>*:not(.stars):not(.foot){position:relative;z-index:1}
.brand{font:500 8.5pt SG;letter-spacing:.2em;text-transform:uppercase;color:var(--acc2)}
.foot{position:absolute;z-index:1;bottom:.35in;left:.5in;right:.5in;display:flex;justify-content:space-between;font:400 7pt In;color:var(--mute)}
h1{font:700 34pt/1.02 SG;margin-top:.22in}
h1 span{color:var(--acc)}
.range{font:600 11pt In;color:var(--acc);margin-top:.1in}
.sub{font:400 10.5pt/1.5 In;color:var(--mute);margin-top:.1in}
h2{font:700 15pt SG;margin:.28in 0 .06in;color:var(--ink)}
h2 small{font:400 8.5pt In;color:var(--mute);margin-left:8px}
.row{display:flex;gap:.14in;border-top:1px solid var(--line);padding:.085in 0;align-items:baseline}
.row .d{flex:0 0 .78in;font:700 11pt SG;color:var(--acc)}
.row .p{flex:0 0 .78in;font:700 11pt SG;color:var(--acc2)}
.row .t{flex:1;font:400 9.6pt/1.42 In;color:#d5dbee}
.row .t b{font-weight:600;color:var(--ink)}
.row.off .p{color:var(--mute)}.row.off .t{color:var(--mute)}
.tip{border-top:1px solid var(--line);padding:.12in 0}
.tip b{display:block;font:600 11pt In;margin-bottom:3px}
.tip span{font:400 10pt/1.5 In;color:#cfd6ea}
.cta{margin-top:.25in;border:1px solid var(--acc);border-radius:12px;padding:.2in .22in}
.cta h3{font:700 16pt/1.15 SG;color:var(--acc)}
.cta p{font:400 10pt/1.5 In;color:#d5dbee;margin:.08in 0 .12in}
.btn{display:inline-block;background:var(--acc);color:var(--bg);font:700 11.5pt SG;padding:9px 18px;border-radius:9px;text-decoration:none}
.url{font:400 8.5pt In;color:var(--acc2);margin-left:10px}
.disc{font:400 7.2pt/1.5 In;color:var(--mute);margin-top:.18in}
.charts{display:flex;gap:.16in;margin-top:.16in}.chart{flex:1}.chart svg{width:100%;display:block}
.ct{font:500 7.6pt SG;letter-spacing:.14em;text-transform:uppercase;color:var(--acc2);margin-bottom:4px}
.note{font:400 7.8pt/1.45 In;color:var(--mute);margin-top:.08in}
.moons{display:grid;grid-template-columns:repeat(10,1fr);gap:.09in .04in;margin-top:.1in}
.mn{text-align:center}.mn svg{width:.34in;height:.34in;display:block;margin:0 auto 2px}.mn span{font:400 6.6pt In;color:var(--mute);white-space:nowrap}
`;

const foot = (i) => `<div class="foot"><span>Cosmos in Numbers · The Next 30 Nights · ${esc(range)}</span><span>${i}</span></div>`;
const mag = (p) => `magnitude ${p.mag}` + (p.mag <= -3 ? ", brighter than every star" : p.mag <= 0 ? ", as bright as the brightest stars" : "");
const planet = (p) => `<div class="row${p.visible ? "" : " off"}"><div class="p">${esc(p.name)}</div>
  <div class="t">${p.visible ? `<b>${esc(p.text[0].toUpperCase() + p.text.slice(1))}.</b> In ${esc(p.constellation)}, ${mag(p)}.` : esc(p.text[0].toUpperCase() + p.text.slice(1)) + "."}</div></div>`;
const event = (e) => `<div class="row"><div class="d">${day(e.date)}</div><div class="t">${esc(e.text)}</div></div>`;
const seen = sky.planets.filter((p) => p.visible).length;

// Horizon chart: planets by compass direction (east..south..west) and height, as computed for one date at 40° N.
function chart(title, list) {
  const W = 300, H = 215, x = (az) => 14 + ((Math.min(300, Math.max(60, az)) - 60) / 240) * (W - 28), y = (alt) => H - 26 - (Math.min(75, alt) / 75) * (H - 48);
  const sorted = [...list].sort((a, b) => a.az - b.az);
  const dots = sorted.map((p, i) => {
    const r = Math.max(2.2, 6.2 - (p.mag + 4.5) * 0.75), near = (q) => q && Math.abs(q.az - p.az) < 30 && Math.abs(q.alt - p.alt) < 22;
    const side = near(sorted[i + 1]) ? -1 : near(sorted[i - 1]) ? 1 : 0;  // two close planets: names go left and right
    const tx = x(p.az) + side * (r + 5), ty = side ? y(p.alt) + 3.5 : y(p.alt) - r - 6;
    return `<circle cx="${x(p.az).toFixed(1)}" cy="${y(p.alt).toFixed(1)}" r="${(r * 2.4).toFixed(1)}" fill="#ffc94d" opacity=".16"/>
      <circle cx="${x(p.az).toFixed(1)}" cy="${y(p.alt).toFixed(1)}" r="${r.toFixed(1)}" fill="#ffc94d"/>
      <text x="${tx.toFixed(1)}" y="${ty.toFixed(1)}" text-anchor="${side < 0 ? "end" : side > 0 ? "start" : "middle"}" font-family="SG" font-weight="700" font-size="10.5" fill="#e8ecf7">${esc(p.name)}</text>`;
  }).join("");
  const grid = [15, 30, 45, 60].map((a) => `<line x1="14" x2="${W - 14}" y1="${y(a)}" y2="${y(a)}" stroke="#2a3566" stroke-width=".6" stroke-dasharray="2 4"/><text x="${W - 12}" y="${y(a) - 2}" text-anchor="end" font-family="In" font-size="6.5" fill="#6f7ba3">${a}°</text>`).join("");
  const comp = [["E", 90], ["SE", 135], ["S", 180], ["SW", 225], ["W", 270]].map(([c, a]) => `<text x="${x(a)}" y="${H - 8}" text-anchor="middle" font-family="SG" font-weight="500" font-size="9" fill="#6fd3ff">${c}</text>`).join("");
  const empty = list.length ? "" : `<text x="${W / 2}" y="${H / 2}" text-anchor="middle" font-family="In" font-size="9" fill="#9aa5c4">No bright planet at this hour</text>`;
  return `<div class="chart"><div class="ct">${esc(title)}</div><svg viewBox="0 0 ${W} ${H}">
    <rect x="0" y="0" width="${W}" height="${H}" rx="9" fill="#0b1130" stroke="#2a3566"/>${grid}
    <path d="M0 ${H - 24} L${W} ${H - 24} L${W} ${H - 9} Q${W} ${H} ${W - 9} ${H} L9 ${H} Q0 ${H} 0 ${H - 9}Z" fill="#141c45"/>${comp}${dots}${empty}</svg></div>`;
}
// The Moon as it looks from the northern hemisphere on each evening.
function moon(m) {
  const r = 11, f = m.lit / 100, rx = (r * Math.abs(1 - 2 * f)).toFixed(2);
  const lit = f < 0.02 ? "" : f > 0.98 ? `<circle r="${r}" fill="#f1eedc"/>` :
    `<path d="M0 ${-r} A${r} ${r} 0 0 1 0 ${r} A${rx} ${r} 0 0 ${f < 0.5 ? 0 : 1} 0 ${-r}Z" fill="#f1eedc" ${m.waxing ? "" : 'transform="scale(-1,1)"'}/>`;
  const [, mo, d] = m.date.split("-").map(Number);
  return `<div class="mn"><svg viewBox="-13 -13 26 26"><circle r="${r}" fill="#1a2350" stroke="#3a4680" stroke-width=".6"/>${lit}</svg><span>${d === 1 || m === sky.moon[0] ? MONTHS[mo - 1] + " " : ""}${d}</span></div>`;
}


const pages = [
  `<section class="page">${stars(200, 600, 900)}<div class="brand">Cosmos in Numbers · free sky calendar</div>
  <h1>The Next <span>30 Nights</span></h1><div class="range">${esc(range)}</div>
  <p class="sub">What you can see with your own eyes, and when. No telescope, no app.</p>
  <h2>The planets <small>${seen} of 5 visible this period · for mid-northern latitudes (40° N)</small></h2>
  ${sky.planets.map(planet).join("")}
  <div class="charts">${chart("Evening sky · 45 min after sunset", sky.charts.evening)}${chart("Dawn sky · 45 min before sunrise", sky.charts.morning)}</div>
  <p class="note">Face south: east is on your left, west on your right. Height in degrees: your fist at arm's length covers about 10°. Drawn for ${day(sky.charts.date)}; planets drift only a little from night to night. A planet shines with a steady light, stars twinkle. Magnitude: the lower the number, the brighter.</p>
  ${foot(1)}</section>`,
  `<section class="page">${stars(140, 600, 900, 23)}<div class="brand">Nights worth going out</div>
  <h2 style="margin-top:.15in">Dates to circle <small>UTC: where you live it can be the night before or after</small></h2>
  ${sky.events.map(event).join("")}
  <h2>The Moon, night by night <small>evenings, northern hemisphere</small></h2>
  <div class="moons">${sky.moon.map(moon).join("")}</div>
  <p class="note">Thin Moon or no Moon: the best nights for faint stars and meteors. Half Moon: the best nights for craters, along the line between light and shadow.</p>
  ${foot(2)}</section>`,
  `<section class="page">${stars(160, 600, 900, 61)}<div class="brand">How to use this page</div>
  <div class="tip" style="margin-top:.18in;border-top:0"><b>1. Start with the Moon.</b><span>On the dates when the Moon passes a planet, the bright "star" next to it is that planet. Once you have found it that night, you will find it again on any other.</span></div>
  <div class="tip"><b>2. Evening or before dawn.</b><span>"Evening" means from about 45 minutes after sunset. "Before dawn" means the last hour of the night, before the sky brightens.</span></div>
  <div class="tip"><b>3. For meteors, look at the whole sky.</b><span>Lie back, keep your phone away so your eyes adapt to the dark, and give it at least half an hour. The quoted rates are for a perfect dark sky: from a town you will see fewer.</span></div>
  <div class="cta"><h3>Want to know what everything else up there is?</h3>
  <p>LOOK UP is our 173-page beginner's guide to the night sky: how to find the main stars and constellations, another galaxy with ordinary binoculars, a month-by-month 2027 calendar and the total solar eclipse of 2 August 2027. No telescope needed.</p>
  <a class="btn" href="${LOOK}">Get LOOK UP →</a><span class="url">${LOOK.replace("https://", "")}</span></div>
  <p class="sub" style="font-size:9pt;margin-top:.16in">This page is rebuilt every week. Download it again for the next 30 nights: cosmosinnumbers.gumroad.com/l/sky-30-nights</p>
  <p class="disc">${esc(sky.method)} Planet positions are for 45 minutes after sunset or before sunrise. The layout and the calculations were made with the help of AI tools; no organisation cited endorses this page. Free to share unchanged with credit to Cosmos in Numbers.</p>
  ${foot(3)}</section>`,
];

const html = `<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${pages.join("")}</body></html>`;
fs.writeFileSync(path.join(OUT, "guide.html"), html);

const coverHtml = (w, h) => `<!doctype html><html><head><meta charset="utf-8"><style>${css}
  body{width:${w}px;height:${h}px;overflow:hidden}
  .art{width:${w}px;height:${h}px;position:relative;padding:${h * 0.09}px;background:radial-gradient(120% 90% at 85% 0%,#22306b 0%,var(--bg) 62%)}
  .art .brand{font-size:${h * 0.03}px}
  .art h1{font:700 ${w > h ? h * 0.17 : h * 0.13}px/1 SG;margin-top:${h * 0.1}px;max-width:${w * 0.8}px}
  .art .when{font:600 ${h * 0.045}px In;color:var(--ink);margin-top:${h * 0.04}px;max-width:${w * 0.62}px;line-height:1.3}
  .art .tag{position:absolute;left:${h * 0.09}px;bottom:${h * 0.09}px;font:600 ${h * 0.035}px In;color:var(--bg);background:var(--acc);padding:.4em .9em;border-radius:99px}
  .art .num{position:absolute;right:${h * 0.07}px;bottom:${h * 0.02}px;font:700 ${h * 0.5}px/1 SG;color:#ffffff10}
  </style></head><body><div class="art">${stars(Math.round(w * h / 2500), w, h, 5)}<div class="brand">Cosmos in Numbers</div>
  <h1>The Next <span>30 Nights</span></h1><div class="when">Planets, Moon and meteor showers: what to see and when</div>
  <div class="tag">Free sky calendar · updated weekly · no telescope</div><div class="num">30</div></div></body></html>`;

const browser = await chromium.launch(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});
const page = await browser.newPage();
await page.goto("file://" + path.join(OUT, "guide.html"));
await page.waitForTimeout(300);
await page.pdf({ path: path.join(OUT, "the-next-30-nights.pdf"), width: "6in", height: "9in", printBackground: true });
for (const [name, w, h] of [["cover-1280x720.png", 1280, 720], ["thumbnail-600x600.png", 600, 600]]) {
  fs.writeFileSync(path.join(OUT, "_cover.html"), coverHtml(w, h));
  await page.setViewportSize({ width: w, height: h });
  await page.goto("file://" + path.join(OUT, "_cover.html"));
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(OUT, name) });
}
// page previews for a visual check (not uploaded)
await page.setViewportSize({ width: 576, height: 864 });
await page.goto("file://" + path.join(OUT, "guide.html"));
await page.screenshot({ path: path.join(OUT, "_preview.png"), fullPage: true });
fs.rmSync(path.join(OUT, "_cover.html"));
await browser.close();
fs.rmSync(path.join(OUT, "guide.html"));
console.log("built", pages.length, "pages ->", OUT, "| period:", range);
