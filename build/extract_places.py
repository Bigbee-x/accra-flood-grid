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
        t = n.tags
        if "name" not in t:
            return
        tier = KEEP.get(t.get("place"))
        if tier is None and (
                t.get("tourism") in ("attraction", "museum", "monument", "zoo",
                                     "theme_park", "viewpoint")
                or "historic" in t
                or t.get("amenity") in ("hospital", "university", "marketplace")
                or t.get("leisure") == "stadium"):
            tier = 3  # landmark POI
        if tier is None:
            return
        lon, lat = n.location.lon, n.location.lat
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            return
        x, y = T.transform(lon, lat)
        self.out.append({"n": t["name"], "t": tier,
                         "x": round(x - X0, 1), "y": round(y - Y0, 1)})


h = H()
h.apply_file(f"{DATA}/ghana-latest.osm.pbf")
# critical flood-history sites that are not OSM place nodes
for name, lon, lat, tier in [
    ("Kwame Nkrumah Circle", -0.2080, 5.5715, 0),
    ("Odawna", -0.2052, 5.5750, 1),
    ("Mamobi", -0.1960, 5.5790, 1),
    ("Kotoka Int'l Airport", -0.1719, 5.6052, 3),
    ("Black Star Square", -0.1877, 5.5424, 3),
    ("Kwame Nkrumah Mausoleum", -0.2011, 5.5449, 3),
    ("Makola Market", -0.2098, 5.5468, 3),
    ("Jamestown Lighthouse", -0.2153, 5.5316, 3),
    ("National Theatre", -0.2003, 5.5490, 3),
    ("Accra Sports Stadium", -0.1898, 5.5495, 3),
    ("Korle Bu Teaching Hospital", -0.2266, 5.5364, 3),
    ("University of Ghana", -0.1868, 5.6508, 3),
    ("Achimota Forest", -0.2325, 5.6208, 3),
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
