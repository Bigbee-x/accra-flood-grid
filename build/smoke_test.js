// Headless self-consistency check of the assembled HTML payload + libs.
const fs = require("fs");
const html = fs.readFileSync(
  "/Users/osborn/BIG PROJECT/accra-flood-grid/dist/accra-flood-grid.html", "utf8");

for (const lib of ["OrbitControls", "UnrealBloomPass", "EffectComposer",
                   "LuminosityHighPassShader", "window.earcut", '"147"']) {
  if (!html.includes(lib)) throw new Error("missing lib: " + lib);
}

const m = html.match(/const P = (\{"meta".*?\});<\/script>/s);
if (!m) throw new Error("payload not found");
const P = JSON.parse(m[1]);
const b64 = (s, T) => new T(Uint8Array.from(Buffer.from(s, "base64")).buffer);

function checkLayer(name, prefix, count) {
  const lens = b64(P[prefix + "Len"], Uint16Array);
  const starts = b64(P[prefix + "Start"], Int32Array);
  const deltas = b64(P[prefix + "Delta"], Int16Array);
  if (lens.length !== count) throw new Error(`${name}: count ${lens.length} != ${count}`);
  if (starts.length !== count * 2) throw new Error(`${name}: starts mismatch`);
  let sum = 0;
  for (const l of lens) sum += l;
  if ((sum - count) * 2 !== deltas.length)
    throw new Error(`${name}: verts ${sum} - ${count} items != ${deltas.length / 2} delta pairs`);
  console.log(`  ${name}: ${count} items, ${sum} verts OK`);
  return sum;
}
checkLayer("buildings", "b", P.meta.nBld);
checkLayer("roads", "r", P.meta.nRoad);
checkLayer("waterways", "w", P.meta.nWater);
checkLayer("waterpolys", "p", P.meta.nPoly);

const bH = b64(P.bH, Float32Array);
if (bH.length !== P.meta.nBld) throw new Error("bH length");
let bad = 0, tagged = 0;
for (const h of bH) { if (!isFinite(h) || h < 0 || h > 350) bad++; if (h > 0) tagged++; }
if (bad) throw new Error("bad heights: " + bad);
console.log(`  heights: all finite, ${tagged} tagged (${(100 * tagged / bH.length).toFixed(1)}%)`);

const n = P.meta.grid.n;
const elev = b64(P.elev, Uint16Array);
if (elev.length !== n * n) throw new Error("elev size");
let mn = 1e9, mx = -1e9;
for (const v of elev) { const e = v * P.meta.grid.elev_scale + P.meta.grid.elev_off;
  if (e < mn) mn = e; if (e > mx) mx = e; }
console.log(`  elev: ${n}x${n}, ${mn.toFixed(1)}..${mx.toFixed(1)} m`);
if (mn < -60 || mx > 500) throw new Error("elev range implausible");
const conv = b64(P.conv, Uint8Array), mask = b64(P.mask, Uint8Array);
if (conv.length !== n * n || mask.length !== n * n) throw new Error("aux size");
let oc = 0, dr = 0;
for (let i = 0; i < n * n; i++) { if (mask[i] & 1) oc++; if (conv[i] > 0) dr++; }
console.log(`  aux: ${oc} ocean cells, ${dr} drain cells`);
if (!oc || !dr) throw new Error("empty masks");
console.log("SMOKE TEST PASS");
