// SPDX-License-Identifier: MIT
// THE SINKING SHIP landing page. All numbers come from SHIP_DATA (generated
// from config/tiers.json + palette.json by scripts/build_site_data.py).
"use strict";

const ZONES = [
  { key: "surface", label: "0 · The Surface", depth: "0 m",
    chapter: "The Abandonment", beat: "Despair",
    line: "Lifeboats, laughter, headlines. The tourists photographed the sinking; nobody photographed who stayed." },
  { key: "sunlight", label: "1 · Sunlight Zone", depth: "0–200 m",
    chapter: "The Doubters", beat: "Doubt",
    line: "Wreckage visible from above. Told-you-so travels at the speed of light — conviction has to swim." },
  { key: "twilight", label: "2 · Twilight Zone", depth: "200–1,000 m",
    chapter: "The Loyal", beat: "Loyalty",
    line: "The first divers found the lights still on below deck. Someone kept the boiler fed the whole time." },
  { key: "midnight", label: "3 · Midnight Zone", depth: "1,000–4,000 m",
    chapter: "The Crew", beat: "Humor · Brotherhood",
    line: "Builders found still working. No sunlight for a thousand meters and the memes are still posting." },
  { key: "abyssal", label: "4 · Abyssal Zone", depth: "4,000–6,000 m",
    chapter: "The Forge", beat: "Building",
    line: "The ship isn't sinking; it's being rebuilt underwater. Sparks look like stars when it's dark enough." },
  { key: "hadal", label: "5 · Hadal Zone", depth: "6,000 m+",
    chapter: "The Light Below", beat: "Hope",
    line: "The wizards, the source, hope itself. At the bottom of everything there is a light, and it is not the sun." },
];

function zoneBg(colors) {
  // darkest two palette colors as a subtle band background
  const sorted = [...colors].sort((a, b) => lum(a) - lum(b));
  return `linear-gradient(180deg, ${sorted[0]}f2, ${sorted[1]}d9)`;
}
function lum(hex) {
  const n = parseInt(hex.slice(1), 16);
  return 0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255);
}
function zoneAccent(colors) {
  const sorted = [...colors].sort((a, b) => lum(a) - lum(b));
  return sorted[sorted.length - 1];
}

// ---- The Descent ----
const zonesEl = document.getElementById("zones");
for (const z of ZONES) {
  const colors = SHIP_DATA.zoneColors[z.key] || [];
  const el = document.createElement("div");
  el.className = "zone";
  el.style.background = zoneBg(colors);
  el.innerHTML = `
    <div class="zone-inner">
      <div class="zone-depth">${z.label.split("·")[0].trim()}<br>${z.depth}</div>
      <div>
        <h3 style="color:${zoneAccent(colors)}">${z.chapter}</h3>
        <span class="beat">${z.beat}</span>
        <p>${z.line}</p>
        <div class="swatches" title="zone sub-palette (from config/palette.json)">
          ${colors.map(c => `<span style="background:${c}"></span>`).join("")}
        </div>
      </div>
    </div>`;
  zonesEl.appendChild(el);
}

// ---- supply stats ----
const stats = [
  [SHIP_DATA.supply.toLocaleString("en-US"), "supply cap"],
  [SHIP_DATA.grails.toString(), "hand-made grails"],
  [SHIP_DATA.reserve.toString(), "treasury (disclosed)"],
  ["100%", "odds published"],
];
document.getElementById("supply-stats").innerHTML = stats
  .map(([n, l]) => `<div class="stat"><div class="n">${n}</div><div class="l">${l}</div></div>`)
  .join("");

// ---- tier table ----
const tbody = document.querySelector("#tier-table tbody");
for (const t of SHIP_DATA.tiers) {
  const colors = SHIP_DATA.zoneColors[t.zone] || ["#8a8a9e"];
  const chip = zoneAccent(colors);
  const eff = t.price ? (parseFloat(t.price) / t.expected).toFixed(3) : null;
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td class="tname">${t.name}</td>
    <td><span class="zone-chip" style="background:${chip}">${t.zone}</span></td>
    <td>${t.price ? t.price + " XCH" : '<span class="not-for-sale">earned, not sold</span>'}</td>
    <td>${t.chest}</td>
    <td>${t.expected}</td>
    <td>${eff ? eff + " XCH" : "—"}</td>
    <td>${t.passes.toLocaleString("en-US")}</td>
    <td class="luck">${t.luck ? t.luck + "×" : "∞"}</td>
    <td class="floor">${t.guarantee}</td>`;
  tbody.appendChild(tr);
}
