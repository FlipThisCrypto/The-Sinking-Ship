// SPDX-License-Identifier: MIT
// THE SINKING SHIP landing page. All numbers come from SHIP_DATA (generated
// from config/tiers.json + palette.json by scripts/build_site_data.py).
"use strict";

const ZONES = [
  { key: "surface", label: "0 · The Surface", depth: "0 m",
    chapter: "The Abandonment", beat: "Despair",
    art: "assets/depths/surface",
    line: "Lifeboats, laughter, headlines. The tourists photographed the sinking; nobody photographed who stayed." },
  { key: "sunlight", label: "1 · Sunlight Zone", depth: "0–200 m",
    chapter: "The Doubters", beat: "Doubt",
    art: "assets/depths/sunlight",
    line: "Wreckage visible from above. Told-you-so travels at the speed of light — conviction has to swim." },
  { key: "twilight", label: "2 · Twilight Zone", depth: "200–1,000 m",
    chapter: "The Loyal", beat: "Loyalty",
    art: "assets/depths/twilight",
    line: "The first divers found the lights still on below deck. Someone kept the boiler fed the whole time." },
  { key: "midnight", label: "3 · Midnight Zone", depth: "1,000–4,000 m",
    chapter: "The Crew", beat: "Humor · Brotherhood",
    art: "assets/depths/midnight",
    line: "Builders found still working. No sunlight for a thousand meters and the memes are still posting." },
  { key: "abyssal", label: "4 · Abyssal Zone", depth: "4,000–6,000 m",
    chapter: "The Forge", beat: "Building",
    art: "assets/depths/abyssal",
    line: "The ship isn't sinking; it's being rebuilt underwater. Sparks look like stars when it's dark enough." },
  { key: "hadal", label: "5 · Hadal Zone", depth: "6,000 m+",
    chapter: "The Light Below", beat: "Hope",
    art: "assets/depths/hadal",
    line: "The wizards, the source, hope itself. At the bottom of everything there is a light, and it is not the sun." },
];

// Dive pass icon slug from display name (matches site/assets/passes/<slug>.jpg)
function passSlug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

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

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "className") node.className = v;
      else if (k === "style" && typeof v === "object") Object.assign(node.style, v);
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    }
  }
  for (const c of children) {
    if (c == null || c === false) continue;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

// ---- The Descent ----
const zonesEl = document.getElementById("zones");
if (zonesEl && typeof SHIP_DATA !== "undefined") {
  for (const z of ZONES) {
    const colors = SHIP_DATA.zoneColors[z.key] || [];
    const zone = el("div", { className: "zone", style: { background: zoneBg(colors) } });
    const inner = el("div", { className: "zone-inner" });
    const depth = el("div", { className: "zone-depth" });
    depth.appendChild(document.createTextNode(z.label.split("·")[0].trim()));
    depth.appendChild(document.createElement("br"));
    depth.appendChild(document.createTextNode(z.depth));
    const body = el("div", { className: "zone-body" });
    const picture = el("picture", { className: "zone-art" });
    picture.appendChild(el("img", {
      src: z.art + "-removebg.png",
      alt: z.chapter + " — " + z.label,
      width: "768",
      height: "768",
      loading: "lazy",
    }));
    const copy = el("div", { className: "zone-copy" });
    const h3 = el("h3", { style: { color: zoneAccent(colors) } }, z.chapter);
    const beat = el("span", { className: "beat" }, z.beat);
    const p = el("p", null, z.line);
    const swatches = el("div", {
      className: "swatches",
      title: "zone sub-palette (from config/palette.json)",
    });
    for (const c of colors) {
      swatches.appendChild(el("span", { style: { background: c } }));
    }
    copy.append(h3, beat, p, swatches);
    body.append(picture, copy);
    inner.append(depth, body);
    zone.appendChild(inner);
    zonesEl.appendChild(zone);
  }
}

// ---- supply stats ----
const supplyStats = document.getElementById("supply-stats");
if (supplyStats && typeof SHIP_DATA !== "undefined") {
  const stats = [
    [SHIP_DATA.supply.toLocaleString("en-US"), "supply cap"],
    [SHIP_DATA.grails.toString(), "hand-made grails"],
    [SHIP_DATA.reserve.toString(), "treasury (disclosed)"],
    ["100%", "odds published"],
  ];
  for (const [n, l] of stats) {
    supplyStats.appendChild(
      el("div", { className: "stat" },
        el("div", { className: "n" }, n),
        el("div", { className: "l" }, l),
      ),
    );
  }
}

// ---- Dive Pass art cards ----
const passGrid = document.getElementById("pass-grid");
if (passGrid && typeof SHIP_DATA !== "undefined") {
  for (const t of SHIP_DATA.tiers) {
    const slug = passSlug(t.name);
    const colors = SHIP_DATA.zoneColors[t.zone] || ["#8a8a9e"];
    const chip = zoneAccent(colors);
    const card = el("article", { className: "pass-card" });
    const picture = el("picture", { className: "pass-art" });
    picture.appendChild(el("img", {
      src: "assets/passes/" + slug + "-removebg.png",
      alt: t.name + " dive pass",
      width: "768",
      height: "768",
      loading: "lazy",
    }));
    const meta = el("div", { className: "pass-meta" });
    meta.append(
      el("h3", null, t.name),
      el("span", { className: "zone-chip", style: { background: chip } }, t.zone),
      el("p", { className: "pass-price" }, t.price ? t.price + " XCH" : "earned, not sold"),
      el("p", { className: "pass-chest" },
        "Chest " + t.chest + " · Luck " + (t.luck ? t.luck + "×" : "∞")),
    );
    card.append(picture, meta);
    passGrid.appendChild(card);
  }
}

// ---- tier table ----
const tbody = document.querySelector("#tier-table tbody");
if (tbody && typeof SHIP_DATA !== "undefined") {
  for (const t of SHIP_DATA.tiers) {
    const colors = SHIP_DATA.zoneColors[t.zone] || ["#8a8a9e"];
    const chip = zoneAccent(colors);
    const eff = t.price ? (parseFloat(t.price) / t.expected).toFixed(3) : null;
    const tr = document.createElement("tr");
    const priceTd = document.createElement("td");
    if (t.price) {
      priceTd.textContent = t.price + " XCH";
    } else {
      priceTd.appendChild(el("span", { className: "not-for-sale" }, "earned, not sold"));
    }
    tr.append(
      el("td", { className: "tname" }, t.name),
      el("td", null, el("span", { className: "zone-chip", style: { background: chip } }, t.zone)),
      priceTd,
      el("td", null, String(t.chest)),
      el("td", null, String(t.expected)),
      el("td", null, eff ? eff + " XCH" : "—"),
      el("td", null, t.passes.toLocaleString("en-US")),
      el("td", { className: "luck" }, t.luck ? t.luck + "×" : "∞"),
      el("td", { className: "floor" }, t.guarantee),
    );
    tbody.appendChild(tr);
  }
}
