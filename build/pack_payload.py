"""Pack extracted layers + DEM into the compact JSON payload for the HTML.

Encoding scheme (all little-endian, base64 per array):
  polylines/rings: per-item vertex count (Uint16), first vertex as Int32
  pair (decimeters rel. to origin), then Int16 delta pairs. Long segments
  are subdivided so every delta fits Int16.
Terrain: 512x512 Uint16 elevation (0.1 m steps, -50 m offset), Uint8 drain
  conveyance, Uint8 mask (bit0 ocean, bit1 waterbody, bit2 wetland).
Grid row 0 = southernmost row (texture v=0 at south).
"""
import base64
import json
import math
import re
import time

import numpy as np
import rasterio
from rasterio import features
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from pyproj import Transformer
from shapely.geometry import LineString, Polygon, box
from shapely.ops import transform as shp_transform

DATA = "/Users/osborn/BIG PROJECT/accra-flood-grid/data"
BBOX = (-0.32, 5.52, -0.12, 5.70)  # W, S, E, N
GRID_N = 512
SCALE = 10  # decimeters
T = Transformer.from_crs("EPSG:4326", "EPSG:32630", always_xy=True)

t0 = time.time()

# ---- grid frame in UTM ----
w, s = T.transform(BBOX[0], BBOX[1])
e, n = T.transform(BBOX[2], BBOX[3])
x0, y0 = math.floor(w), math.floor(s)
x1, y1 = math.ceil(e), math.ceil(n)
cell = max(x1 - x0, y1 - y0) / GRID_N
x1, y1 = x0 + cell * GRID_N, y0 + cell * GRID_N
clip_rect = box(x0, y0, x1, y1)
print(f"grid: origin=({x0},{y0}) cell={cell:.2f}m span={cell*GRID_N/1000:.1f}km")

HEIGHT_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_height(props):
    h = props.get("height")
    if h:
        m = HEIGHT_RE.search(str(h).split(";")[0])
        if m:
            v = float(m.group())
            if 2.0 <= v <= 350.0:
                return v
    lv = props.get("levels")
    if lv:
        m = HEIGHT_RE.search(str(lv).split(";")[0])
        if m:
            v = float(m.group()) * 3.2
            if 2.0 <= v <= 350.0:
                return v
    return 0.0


def load(name):
    with open(f"{DATA}/{name}.jsonl") as f:
        for line in f:
            yield json.loads(line)


def to_utm(coords):
    xs, ys = T.transform([c[0] for c in coords], [c[1] for c in coords])
    return list(zip(xs, ys))


def quantize(pts):
    """UTM pts -> deduped decimeter int pairs relative to origin."""
    out = []
    for x, y in pts:
        q = (round((x - x0) * SCALE), round((y - y0) * SCALE))
        if not out or q != out[-1]:
            out.append(q)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


class PolyEncoder:
    def __init__(self):
        self.lens, self.starts, self.deltas = [], [], []

    def add(self, qpts):
        n_before = len(qpts)
        pts = [qpts[0]]
        for p in qpts[1:]:
            dx, dy = p[0] - pts[-1][0], p[1] - pts[-1][1]
            k = max(abs(dx), abs(dy))
            nsub = (k // 32000) + 1
            for j in range(1, nsub + 1):
                sub = (pts[-1][0] + dx * j // nsub, pts[-1][1] + dy * j // nsub) if nsub > 1 else p
                if sub != pts[-1]:
                    pts.append(sub)
            pts[-1] = p
        self.lens.append(len(pts))
        self.starts.extend(pts[0])
        for a, b in zip(pts, pts[1:]):
            self.deltas.extend((b[0] - a[0], b[1] - a[1]))
        return len(pts) != n_before

    def arrays(self):
        return (np.array(self.lens, "<u2"), np.array(self.starts, "<i4"),
                np.array(self.deltas, "<i2"))


# ---- buildings ----
b_enc, b_heights = PolyEncoder(), []
dens = np.zeros((GRID_N, GRID_N), np.float32)  # north-up, like elev
n_in, n_kept, n_tagged = 0, 0, 0
for rec in load("buildings"):
    n_in += 1
    poly = Polygon(to_utm(rec["c"]))
    if not poly.is_valid:
        poly = poly.buffer(0)
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
    if poly.area < 20.0:
        continue
    c = poly.centroid
    gi = int((c.x - x0) / cell)
    gj = int((y1 - c.y) / cell)
    if 0 <= gi < GRID_N and 0 <= gj < GRID_N:
        dens[gj, gi] += poly.area
    poly = poly.simplify(1.2, preserve_topology=True)
    q = quantize(list(poly.exterior.coords))
    if len(q) < 3:
        continue
    h = parse_height(rec["p"])
    if h > 0:
        n_tagged += 1
    b_enc.add(q)
    b_heights.append(h)
    n_kept += 1
print(f"buildings: {n_in} in, {n_kept} kept, {n_tagged} with real height "
      f"({time.time()-t0:.0f}s)")

# ---- roads / waterways: clip to grid rect ----
WCLASS = {"drain": 0, "ditch": 1, "canal": 1, "stream": 2, "river": 3}


def clip_lines(name, classify):
    enc, klass = PolyEncoder(), []
    for rec in load(name):
        line = LineString(to_utm(rec["c"]))
        g = line.intersection(clip_rect)
        if g.is_empty:
            continue
        parts = g.geoms if g.geom_type == "MultiLineString" else (
            [g] if g.geom_type == "LineString" else [])
        for part in parts:
            part = part.simplify(2.0, preserve_topology=False)
            q = quantize(list(part.coords))
            if len(q) < 2:
                continue
            enc.add(q)
            klass.append(classify(rec["p"]))
    return enc, np.array(klass, "u1")


def road_class(p):
    hw = p["highway"].replace("_link", "")
    return {"motorway": 0, "trunk": 0, "primary": 1, "secondary": 2, "tertiary": 3}[hw]


def water_class(p):
    name = (p.get("name") or "").lower()
    if "odaw" in name:
        return 4
    return WCLASS[p["waterway"]]


r_enc, r_class = clip_lines("roads", road_class)
w_enc, w_class = clip_lines("waterways", water_class)
m_enc, _ = clip_lines("minor", lambda p: 0)
x_enc, x_class = clip_lines("xtras", lambda p: p["k"])
print(f"roads: {len(r_enc.lens)} polylines | minor: {len(m_enc.lens)} | "
      f"xtras: {len(x_enc.lens)} | waterways: {len(w_enc.lens)} "
      f"(odaw segs: {int((w_class == 4).sum())}) ({time.time()-t0:.0f}s)")

# green spaces + airport surfaces -> raster mask bits (terrain tint, no geometry)
green_geoms, aero_geoms = [], []
for rec in load("landpoly"):
    poly = Polygon(to_utm(rec["c"]))
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty:
        continue
    poly = poly.intersection(clip_rect)
    if poly.is_empty or poly.area < 1200:
        continue
    (green_geoms if rec["p"]["role"] == 0 else aero_geoms).append(poly)
print(f"landpolys: {len(green_geoms)} green, {len(aero_geoms)} airport")

# ---- water/wetland polygons (rendered + rasterized) ----
p_enc, p_role, water_geoms, wetland_geoms = PolyEncoder(), [], [], []
for rec in load("waterpoly"):
    poly = Polygon(to_utm(rec["c"]))
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty:
        continue
    poly = poly.intersection(clip_rect)
    if poly.is_empty:
        continue
    geoms = poly.geoms if poly.geom_type == "MultiPolygon" else (
        [poly] if poly.geom_type == "Polygon" else [])
    role = 0 if rec["p"]["natural"] == "water" else 1
    for g in geoms:
        if g.area < 400:
            continue
        gs = g.simplify(3.0, preserve_topology=True)
        q = quantize(list(gs.exterior.coords))
        if len(q) < 3:
            continue
        p_enc.add(q)
        p_role.append(role)
        (water_geoms if role == 0 else wetland_geoms).append(g)
print(f"waterpolys: {len(p_role)} ({sum(1 for r in p_role if r==0)} water)")

# ---- terrain grid ----
grid_transform = from_origin(x0, y1, cell, cell)  # north-up
elev = np.zeros((GRID_N, GRID_N), np.float32)
with rasterio.open(f"{DATA}/cop30_N05_W001.tif") as src:
    reproject(
        rasterio.band(src, 1), elev,
        dst_transform=grid_transform, dst_crs="EPSG:32630",
        resampling=Resampling.bilinear)

# light smoothing (2x 3x3 box) BEFORE channel burning
for _ in range(2):
    p = np.pad(elev, 1, mode="edge")
    elev = sum(p[dy:dy+GRID_N, dx:dx+GRID_N]
               for dy in range(3) for dx in range(3)) / 9.0

# burn channels: shallow, routing-only (deep burns turn 43m cells into
# phantom reservoirs that swallow the whole storm)
BURN = {0: (0.35, 130), 1: (0.3, 110), 2: (0.35, 100), 3: (0.9, 200), 4: (1.8, 255)}
burn_shapes, conv_shapes = [], []
for rec in load("waterways"):
    line = LineString(to_utm(rec["c"])).intersection(clip_rect)
    if line.is_empty:
        continue
    k = water_class(rec["p"])
    depth, conv = BURN[k]
    g = line.buffer(24.0) if k == 4 else line.buffer(cell * 0.35)
    burn_shapes.append((g, depth))
    conv_shapes.append((g, conv))

burn = features.rasterize(burn_shapes, out_shape=(GRID_N, GRID_N),
                          transform=grid_transform, fill=0.0,
                          all_touched=False, merge_alg=rasterio.enums.MergeAlg.replace,
                          dtype="float32")
conveyance = features.rasterize(conv_shapes, out_shape=(GRID_N, GRID_N),
                                transform=grid_transform, fill=0,
                                all_touched=True, dtype="uint8")
# dilate: unmapped street gutters feed the trunk drains, so let drain cells
# sink from a wider band (3x3 max, decayed, twice)
cf = conveyance.astype(np.float32)
for _ in range(2):
    p = np.pad(cf, 1, mode="constant")
    neigh = np.max(np.stack([p[dy:dy+GRID_N, dx:dx+GRID_N]
                             for dy in range(3) for dx in range(3)]), axis=0)
    cf = np.maximum(cf, neigh * 0.55)
conveyance = np.clip(cf, 0, 255).astype("u1")
print(f"conveyance: {int((conveyance > 0).sum())} sink cells after dilation")
elev -= burn

# water bodies (lagoons): depress and mask
water_mask = np.zeros((GRID_N, GRID_N), np.uint8)
if water_geoms:
    water_mask = features.rasterize([(g, 1) for g in water_geoms],
                                    out_shape=(GRID_N, GRID_N),
                                    transform=grid_transform, fill=0,
                                    all_touched=True, dtype="uint8")
    elev = np.where(water_mask == 1, np.minimum(elev, -0.5), elev)

wet_mask = np.zeros((GRID_N, GRID_N), np.uint8)
if wetland_geoms:
    wet_mask = features.rasterize([(g, 1) for g in wetland_geoms],
                                  out_shape=(GRID_N, GRID_N),
                                  transform=grid_transform, fill=0,
                                  all_touched=True, dtype="uint8")

# ocean: cells <=0.5m connected to the south edge (row GRID_N-1 in north-up)
low = elev <= 0.5
ocean = np.zeros_like(low)
ocean[-1, :] = low[-1, :]
for _ in range(GRID_N * 2):
    grown = ocean.copy()
    grown[:-1, :] |= ocean[1:, :]
    grown[1:, :] |= ocean[:-1, :]
    grown[:, :-1] |= ocean[:, 1:]
    grown[:, 1:] |= ocean[:, :-1]
    grown &= low
    if (grown == ocean).all():
        break
    ocean = grown
elev = np.where(ocean, np.minimum(elev, -2.0), elev)
print(f"terrain: elev range {elev.min():.1f}..{elev.max():.1f} m, "
      f"ocean cells {int(ocean.sum())}, water cells {int(water_mask.sum())}, "
      f"wetland cells {int(wet_mask.sum())}")

green_mask = np.zeros((GRID_N, GRID_N), np.uint8)
if green_geoms:
    green_mask = features.rasterize([(g, 1) for g in green_geoms],
                                    out_shape=(GRID_N, GRID_N),
                                    transform=grid_transform, fill=0, dtype="uint8")
aero_mask = np.zeros((GRID_N, GRID_N), np.uint8)
if aero_geoms:
    aero_mask = features.rasterize([(g, 1) for g in aero_geoms],
                                   out_shape=(GRID_N, GRID_N),
                                   transform=grid_transform, fill=0,
                                   all_touched=True, dtype="uint8")
print(f"raster tints: {int(green_mask.sum())} green cells, "
      f"{int(aero_mask.sum())} airport cells")

mask = (ocean.astype(np.uint8) | (water_mask << 1) | (wet_mask << 2)
        | (green_mask << 3) | (aero_mask << 4))

# building density -> imperviousness proxy (blurred footprint fraction)
dens /= cell * cell
for _ in range(2):
    p = np.pad(dens, 1, mode="edge")
    dens = sum(p[dy:dy+GRID_N, dx:dx+GRID_N]
               for dy in range(3) for dx in range(3)) / 9.0
dens_u8 = np.clip(dens * 2.2 * 255.0, 0, 255).astype("u1")
print(f"density: mean footprint frac {dens.mean():.3f}, "
      f"urban cells (>0.35 raw) {(dens_u8 > 90).sum()}")

# flip to row 0 = south for texture layout
elev_s = np.flipud(elev)
conv_s = np.flipud(conveyance)
mask_s = np.flipud(mask)
dens_s = np.flipud(dens_u8)
elev_u16 = np.clip((elev_s + 50.0) * 10.0, 0, 65535).astype("<u2")


def b64(arr):
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode()


bl, bs, bd = b_enc.arrays()
rl, rs, rd = r_enc.arrays()
wl, ws, wd = w_enc.arrays()
pl, ps, pd = p_enc.arrays()
ml, ms, md = m_enc.arrays()
xl, xs, xd = x_enc.arrays()

payload = {
    "meta": {
        "scale": SCALE, "utm_origin": [x0, y0], "epsg": 32630,
        "grid": {"n": GRID_N, "cell": cell, "elev_scale": 0.1, "elev_off": -50.0},
        "nBld": len(bl), "nRoad": len(rl), "nWater": len(wl), "nPoly": len(pl),
        "nMinor": len(ml), "nXtra": len(xl),
        "bbox_wgs84": BBOX,
    },
    "bLen": b64(bl), "bStart": b64(bs), "bDelta": b64(bd),
    "bH": b64(np.array(b_heights, "<f4")),
    "rLen": b64(rl), "rStart": b64(rs), "rDelta": b64(rd), "rClass": b64(r_class),
    "mLen": b64(ml), "mStart": b64(ms), "mDelta": b64(md),
    "xLen": b64(xl), "xStart": b64(xs), "xDelta": b64(xd), "xClass": b64(x_class),
    "wLen": b64(wl), "wStart": b64(ws), "wDelta": b64(wd), "wClass": b64(w_class),
    "pLen": b64(pl), "pStart": b64(ps), "pDelta": b64(pd),
    "pRole": b64(np.array(p_role, "u1")),
    "elev": b64(elev_u16), "conv": b64(conv_s), "mask": b64(mask_s),
    "dens": b64(dens_s),
}

out = f"{DATA}/payload.json"
with open(out, "w") as f:
    json.dump(payload, f, separators=(",", ":"))

import os
print(f"payload: {os.path.getsize(out)/1e6:.1f} MB ({time.time()-t0:.0f}s)")
for k in payload:
    if k != "meta":
        print(f"  {k}: {len(payload[k])//1024} KB")
