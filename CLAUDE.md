# Accra // flood grid: project brief

An interactive 3D flood simulation of Accra's Odaw basin, shipped as **one self-contained HTML file**: `dist/accra-flood-grid.html` (about 22 MB). It holds roughly 491k building footprints (OpenStreetMap plus Google Open Buildings gap-fill), terrain, the drainage network, a place gazetteer, a GPU shallow-water solver and three.js r147, all inlined. It works offline except for the optional live rain forecast (Open-Meteo) and the news-video lightbox (YouTube embeds). It is published on GitHub Pages from `docs/`. `README.md` is accurate and explains the features, method and limits, so read it first.

## Source of truth
- The app source is **`build/template.html`** (about 2,200 lines of HTML, CSS, JS and GLSL shaders). Never hand-edit `dist/accra-flood-grid.html` or `docs/index.html`; they are generated output.
- After a rebuild, copy the output to `docs/index.html` so GitHub Pages matches `dist/`. They are currently byte-identical.

## Build pipeline (Python 3 and Node)
`extract_osm.py` (PBF to JSONL), then `pack_payload.py` (to `data/payload.json`), then `assemble.py` (template, three.js, earcut, payload and places into the `dist/` HTML), then `node build/smoke_test.js` (payload self-consistency check). `fetch_openbuildings.py`, `extract_places.py` and `fetch_satellite.py` produce supporting data. Python deps: `numpy shapely geopandas pyproj rasterio osmium`. The exact steps and download URLs are in the README under "Rebuild from scratch".
- Raw inputs are gitignored and must be re-downloaded: `data/ghana-latest.osm.pbf` (Geofabrik), `data/cop30_N05_W001.tif` (Copernicus DEM), `data/*.jsonl`, `data/payload.json`, and the npm-packed `build/three-pkg` and `build/earcut-pkg`. Tracked data: `data/places.json` and `data/satellite.jpg`.
- Without those inputs `assemble.py` can't run, so any template change needs the full rebuild.
- The build scripts find the repo from their own location (`ROOT` and `DATA` come from `__file__`; `smoke_test.js` uses `__dirname`), so the checkout can live anywhere. Don't hard-code absolute paths. `node build/smoke_test.js` checks the committed `dist/` file, so it runs without any downloads.

## Rules
- Keep the "Honest limits" intact: this is a basin-scale explainer, not parcel-level prediction (30 m terrain, 43 m simulation grid, about 90% of building heights are heuristic, parameters tuned rather than gauge-calibrated). Prediction mode must keep its "indicative only, not an official warning; heed GMet/NADMO advisories" disclaimer.
- Keep the attributions from the README's "Data & attribution": OpenStreetMap (ODbL), Google Open Buildings (CC BY-4.0), Copernicus GLO-30 DEM, and the GMet and NADMO figures.
- Stay dependency-free at runtime: one file, no server, no CDN scripts. Don't add npm packages or external script tags.
- Simulation time is frame-rate independent, and runs are deterministic for a given storm (that is how the README results table is reproduced). Keep both properties.
- There is no automated UI test. After any change, open the built HTML in a browser, press **start storm**, and check it visually.
