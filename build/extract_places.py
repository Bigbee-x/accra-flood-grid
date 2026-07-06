"""Extract OSM place nodes (the Accra gazetteer) from the Ghana PBF.

Output: data/places.json with local-meter coords matching the payload's
UTM origin (recomputed identically to pack_payload.py).
"""
import json
import math

import osmium
from pyproj import Transformer

DATA = "/Users/osborn/BIG PROJECT/accra-flood-grid/data"
BBOX = (-0.32, 5.52, -0.12, 5.70)
T = Transformer.from_crs("EPSG:4326", "EPSG:32630", always_xy=True)
w, s = T.transform(BBOX[0], BBOX[1])
X0, Y0 = math.floor(w), math.floor(s)

KEEP = {"suburb": 0, "town": 0, "quarter": 1, "neighbourhood": 1,
        "village": 2, "hamlet": 2, "locality": 2}


class H(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.out = []

    def node(self, n):
        p = n.tags.get("place")
        if p not in KEEP or "name" not in n.tags:
            return
        lon, lat = n.location.lon, n.location.lat
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            return
        x, y = T.transform(lon, lat)
        self.out.append({"n": n.tags["name"], "t": KEEP[p],
                         "x": round(x - X0, 1), "y": round(y - Y0, 1)})


h = H()
h.apply_file(f"{DATA}/ghana-latest.osm.pbf")
# critical flood-history sites that are not OSM place nodes
for name, lon, lat, tier in [
    ("Kwame Nkrumah Circle", -0.2080, 5.5715, 0),
    ("Odawna", -0.2052, 5.5750, 1),
    ("Mamobi", -0.1960, 5.5790, 1),
]:
    x, y = T.transform(lon, lat)
    h.out.append({"n": name, "t": tier, "x": round(x - X0, 1), "y": round(y - Y0, 1)})
# dedupe by name, keep the most important tier
best = {}
for p in h.out:
    k = p["n"].strip().lower()
    if k not in best or p["t"] < best[k]["t"]:
        best[k] = p
places = sorted(best.values(), key=lambda p: (p["t"], p["n"]))
with open(f"{DATA}/places.json", "w") as f:
    json.dump(places, f, ensure_ascii=False, separators=(",", ":"))
print(f"{len(places)} places ({sum(1 for p in places if p['t']==0)} suburbs/towns)")
print("sample:", [p["n"] for p in places[:12]])
