# Accra // flood grid

An interactive 3D flood simulation of Accra's Odaw basin — **one self-contained HTML file**, no server, no dependencies, works offline (only the optional live-forecast feature calls the internet). 209,457 real building footprints, the city's mapped drainage network, real terrain, a 210-place gazetteer, and a GPU shallow-water simulation of the June 29, 2026 storm (~140 mm in 24h, the worst June on record).

Open [`dist/accra-flood-grid.html`](dist/accra-flood-grid.html) in any modern browser, press **start storm**, and watch the water obey Accra's actual topography: it pools at Alajo, traces the Odaw corridor through Avenor and Adabraka, and floods Sakumono/Klagon and Mallam — the same neighborhoods in the real June 2026 damage reports. Nobody told the simulation where to flood.

## Why

Accra floods every June, and every credible study points to the same causes: a low-lying basin funneled into one silted channel, drains choked with plastic, buildings on floodplains, and drainage built for a much smaller city. This project turns those causes into switches you can flip:

- **Drains: clogged → clear** — today's reality vs. maintained drains
- **Odaw dredged** — the completed-GARID counterfactual
- **Wetlands restored** — upstream infiltration recovered
- **Tide at Korle outlet** — compound coastal flooding

And it knows the city by name:

- **210 real places** from the OSM gazetteer, labeled in the 3D scene with declutter and zoom tiers; flood-history areas (Alajo, Kaneshie, Circle, Old Fadama…) carry an orange marker and a short incident note (2015 disaster, June 2026 storms). Labels turn blue live when a place is currently under >0.3 m of simulated water.
- **Search** any place — the camera flies there and an info card shows what happened, plus live simulation stats: water depth right now, peak this run, ground elevation.
- **Prediction mode** — one click fetches Accra's real 7-day hourly rain forecast ([Open-Meteo](https://open-meteo.com/), no key), finds the worst 24-hour window, feeds the actual hourly rainfall through the simulation as a hyetograph at 4× speed, and reports a risk verdict with the most-affected neighbourhoods by name. *Indicative only — from this simplified basin model, not an official warning; heed GMet/NADMO advisories.*

## What the simulation says

Same 140 mm storm, deterministic runs:

| At storm end (T+3:00) | Drains clogged (today) | Cleared + dredged + wetlands | Change |
|---|---|---|---|
| Flooded area (>0.25 m) | 8.4 km² | 4.5 km² | −46% |
| Buildings in water (>0.3 m) | 4,032 | 1,218 | **−70%** |
| Buildings still wet 2h after rain | 1,631 | 400 | ~2× faster recovery |

Interventions don't abolish the flood — they cut its reach in half and get homes dry hours sooner.

## How it works

```
OSM Ghana extract ─┐
Copernicus GLO-30 ─┼─→ Python packer ─→ one 11 MB HTML
storm presets ─────┘      (quantize, delta-encode, base64)
                            ├─ three.js sand-table city model (terrain + 209k extruded buildings)
                            ├─ GPU shallow-water sim (virtual pipes, ping-pong shaders, 512² @ 43 m)
                            └─ scenario UI with live readouts
```

- **Terrain**: Copernicus GLO-30 DEM resampled to a 512² grid (UTM 30N), drainage channels burned in shallow (routing-only), ocean detected by connectivity and used as an absorbing tide boundary.
- **Water**: virtual-pipes shallow-water solver in WebGL fragment shaders — rain, infiltration (scaled by building-density imperviousness), drain conveyance sinks, velocity-capped overland flow (1.3 m/s streets, 4.5 m/s channels), open boundaries.
- **Buildings**: OSM footprints extruded; heights from `height`/`building:levels` where tagged (~10%), vernacular heuristic elsewhere; baked vertex-color shading, buildings turn orange as water reaches them.
- **Look**: solid daylight "sand-table" palette — paper sky, sandstone city, orange drainage network, blue water whose surface streaks are advected by the simulation's own flux field, so the water visibly flows in the direction and speed the solver computes.
- **Weather**: procedural storm clouds roll in as the rain starts and darken with its intensity, casting drifting shadows on the city (the same wind-advected noise field is sampled in the terrain, building, and cloud shaders); the sky desaturates, rain streaks thicken with rainfall rate, and lightning flashes during heavy rain. Clouds linger through the recession, then clear. Time is frame-rate-independent with a ½× / 1× / 3× / 10× speed control — the default runs the 3-hour storm over ~70 seconds so you can watch it unfold.

## Rebuild from scratch

```bash
pip install numpy shapely geopandas pyproj rasterio osmium
cd build
curl -L -o ../data/ghana-latest.osm.pbf https://download.geofabrik.de/africa/ghana-latest.osm.pbf
curl -L -o ../data/cop30_N05_W001.tif https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N05_00_W001_00_DEM/Copernicus_DSM_COG_10_N05_00_W001_00_DEM.tif
npm pack three@0.147.0 earcut@2.2.4 && tar xzf three-0.147.0.tgz && mv package three-pkg && tar xzf earcut-2.2.4.tgz && mv package earcut-pkg
python3 extract_osm.py     # PBF -> per-layer JSONL (28 s)
python3 pack_payload.py    # geometry + terrain -> data/payload.json (12 s)
python3 assemble.py        # template + libs + payload -> dist/accra-flood-grid.html
node smoke_test.js         # payload self-consistency check
```

(Paths in the build scripts are absolute for the original machine — adjust `DATA`/`ROOT` constants if you rebuild elsewhere.)

## Honest limits

This is a **basin-scale explainer, not parcel-level prediction**. 30 m terrain and a 43 m simulation grid cannot see individual streets or gutters. Sim parameters are physically motivated and mass-conserving but tuned to reproduce reported flood behavior, not calibrated against gauge data. ~90% of building heights are heuristic. Don't use this to decide whether a specific plot floods; use it to understand why the city floods and what classes of intervention change that.

## Data & attribution

- Building footprints, roads, drains: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, ODbL. Extract via [Geofabrik](https://download.geofabrik.de/).
- Terrain: [Copernicus GLO-30 DEM](https://registry.opendata.aws/copernicus-dem/) © ESA / European Commission.
- Rainfall and impact figures: Ghana Meteorological Agency and NADMO totals as reported in Ghanaian press, June–July 2026.
- Libraries: [three.js](https://threejs.org/) r147, [earcut](https://github.com/mapbox/earcut) (both inlined; MIT).

Built with [Claude Code](https://claude.com/claude-code) (Claude Fable 5) in a single session — data download to verified simulation.
