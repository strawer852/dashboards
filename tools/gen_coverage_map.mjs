// Generate SVG path data for a coverage map from Natural Earth (public domain,
// via world-atlas). Two layers: every country as one faint base path, and each
// covered or candidate territory as its own path so it can be a link.
import { readFileSync, writeFileSync } from "node:fs";
import { feature } from "topojson-client";
import { geoNaturalEarth1, geoPath } from "d3-geo";

const W = 900, H = 460;
const topo = JSON.parse(readFileSync("node_modules/world-atlas/countries-110m.json"));
const fc = feature(topo, topo.objects.countries);

// Fit to what is actually DRAWN. Fitting to the full collection reserved a
// third of the height for an Antarctica the map does not show, and the plate
// came out mostly empty southern ocean.
const drawn = { type: "FeatureCollection",
  features: fc.features.filter(f => f.properties.name !== "Antarctica") };
const proj = geoNaturalEarth1().fitExtent([[6, 6], [W - 6, H - 6]], drawn);
// One decimal is well under a pixel at this size and roughly halves the bytes.
const path = geoPath(proj).pointRadius(1);
const round = d => d.replace(/-?\d+\.\d+/g, m => (+m).toFixed(1));
// The base layer is a faint silhouette behind everything; whole pixels at 900
// wide are indistinguishable and cost half the bytes.
const coarse = d => d.replace(/-?\d+\.\d+/g, m => (+m).toFixed(0));

const EURO = new Set(["Austria", "Belgium", "Croatia", "Cyprus", "Estonia",
  "Finland", "France", "Germany", "Greece", "Ireland", "Italy", "Latvia",
  "Lithuania", "Luxembourg", "Malta", "Netherlands", "Portugal", "Slovakia",
  "Slovenia", "Spain"]);
// Only territories that need their OWN path: covered ones (a link) and
// candidates (a dashed outline). Everything else belongs in the base layer --
// China was in here and drawn nowhere, which left a hole in Asia.
const SOLO = { "United States of America": "us", "United Kingdom": "gb",
               "Japan": "jp" };

const names = new Set(fc.features.map(f => f.properties.name));
for (const n of [...EURO, ...Object.keys(SOLO)])
  if (!names.has(n)) console.error("!! name not in dataset:", n);

const out = { w: W, h: H, base: "", euro: "", solo: {} };
const baseParts = [];
const euroParts = [];

for (const f of fc.features) {
  const n = f.properties.name;
  const d = path(f);
  if (!d) continue;
  // Antarctica is a third of the ink and none of the economies.
  if (n === "Antarctica") continue;
  if (SOLO[n]) { out.solo[SOLO[n]] = round(d); continue; }
  if (EURO.has(n)) { euroParts.push(d); continue; }
  baseParts.push(d);
}
out.base = coarse(baseParts.join(" "));
out.euro = round(euroParts.join(" "));

writeFileSync("map.json", JSON.stringify(out));
const kb = s => (s.length / 1024).toFixed(1) + " KB";
console.log("base   ", kb(out.base));
console.log("euro   ", kb(out.euro));
for (const [k, v] of Object.entries(out.solo)) console.log(k.padEnd(7), kb(v));
console.log("total  ", kb(JSON.stringify(out)));
// Where the labels should sit, from each territory's own centroid.
const c = {};
for (const f of fc.features) {
  const n = f.properties.name;
  if (SOLO[n]) c[SOLO[n]] = path.centroid(f).map(v => +v.toFixed(0));
}
c.euro = [proj([10, 50])[0].toFixed(0), proj([10, 50])[1].toFixed(0)];
console.log("centroids", JSON.stringify(c));
