"""Bake a cloud-free Sentinel-2 true-color texture aligned to the sim grid.

Queries the earth-search STAC for the lowest-cloud L2A scenes over the bbox,
window-reads their `visual` COGs (already EPSG:32630, same CRS as the grid)
into a 2048px north-up mosaic, and writes data/satellite.jpg.
Credit: contains modified Copernicus Sentinel data.
"""
import json
import math
import urllib.request

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from pyproj import Transformer

DATA = "/Users/osborn/BIG PROJECT/accra-flood-grid/data"
BBOX = (-0.32, 5.52, -0.12, 5.70)
GRID_N, TEX = 512, 2048

# grid frame — must match pack_payload.py exactly so texture uv == terrain uv
T = Transformer.from_crs("EPSG:4326", "EPSG:32630", always_xy=True)
w, s = T.transform(BBOX[0], BBOX[1])
e, n = T.transform(BBOX[2], BBOX[3])
x0, y0 = math.floor(w), math.floor(s)
cell = max(math.ceil(e) - x0, math.ceil(n) - y0) / GRID_N
x1, y1 = x0 + cell * GRID_N, y0 + cell * GRID_N
print(f"grid frame: ({x0},{y0})..({x1:.0f},{y1:.0f})")

req = urllib.request.Request(
    "https://earth-search.aws.element84.com/v1/search",
    data=json.dumps({
        "collections": ["sentinel-2-l2a"],
        "bbox": list(BBOX),
        "query": {"eo:cloud_cover": {"lt": 10}},
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
        "limit": 12,
    }).encode(),
    headers={"Content-Type": "application/json"})
feats = json.load(urllib.request.urlopen(req, timeout=60))["features"]
print(f"{len(feats)} candidate scenes")

img = np.zeros((3, TEX, TEX), np.uint8)
filled = np.zeros((TEX, TEX), bool)
for f in feats:
    href = f["assets"]["visual"]["href"]
    date = f["properties"]["datetime"][:10]
    with rasterio.open(href) as src:
        if src.crs.to_epsg() != 32630:
            continue
        win = from_bounds(x0, y0, x1, y1, src.transform)
        data = src.read(window=win, out_shape=(3, TEX, TEX), boundless=True,
                        fill_value=0, resampling=Resampling.bilinear)
    mask = data.sum(axis=0) > 0
    take = mask & ~filled
    img[:, take] = data[:, take]
    filled |= mask
    print(f"  {date}: +{int(take.sum())} px  (filled {100*filled.mean():.1f}%)")
    if filled.all():
        break

assert filled.mean() > 0.98, "mosaic has holes"
out = f"{DATA}/satellite.jpg"
try:
    with rasterio.open(out, "w", driver="JPEG", width=TEX, height=TEX,
                       count=3, dtype="uint8", QUALITY="85") as dst:
        dst.write(img)
except Exception:
    from PIL import Image
    Image.fromarray(np.moveaxis(img, 0, -1)).save(out, quality=85)
import os
print(f"wrote {out} ({os.path.getsize(out)/1e6:.2f} MB)")
