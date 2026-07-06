"""Extract Accra flood-grid layers from the Geofabrik Ghana PBF.

One pass with pyosmium (locations=True). Closed ways only for polygons —
multipolygon buildings are rare in Accra and not worth a relation assembler.
Outputs newline-delimited GeoJSON-ish records per layer (lon/lat, EPSG:4326).
"""
import json
import sys
import time

import osmium

BBOX = (-0.32, 5.52, -0.12, 5.70)  # W, S, E, N — Odaw basin + coastal core
ROAD_CLASSES = {
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link", "tertiary",
}
WATERWAY_CLASSES = {"drain", "river", "stream", "canal", "ditch"}
DATA = "/Users/osborn/BIG PROJECT/accra-flood-grid/data"


def in_bbox(lon, lat):
    return BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]


class Handler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.files = {
            name: open(f"{DATA}/{name}.jsonl", "w")
            for name in ("buildings", "roads", "waterways", "waterpoly")
        }
        self.counts = dict.fromkeys(self.files, 0)
        self.skipped_loc = 0

    def coords(self, w):
        pts = []
        for n in w.nodes:
            try:
                pts.append((round(n.lon, 7), round(n.lat, 7)))
            except osmium.InvalidLocationError:
                self.skipped_loc += 1
                return None
        return pts

    def emit(self, layer, coords, props):
        self.files[layer].write(json.dumps({"c": coords, "p": props}, separators=(",", ":")) + "\n")
        self.counts[layer] += 1

    def way(self, w):
        tags = w.tags
        if "building" in tags and w.is_closed() and len(w.nodes) >= 4:
            pts = self.coords(w)
            if not pts:
                return
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            if not in_bbox(cx, cy):
                return
            self.emit("buildings", pts, {
                "height": tags.get("height"),
                "levels": tags.get("building:levels"),
                "building": tags.get("building"),
            })
            return

        hw = tags.get("highway")
        if hw in ROAD_CLASSES:
            pts = self.coords(w)
            if pts and any(in_bbox(x, y) for x, y in pts):
                self.emit("roads", pts, {"highway": hw})
            return

        ww = tags.get("waterway")
        if ww in WATERWAY_CLASSES:
            pts = self.coords(w)
            if pts and any(in_bbox(x, y) for x, y in pts):
                self.emit("waterways", pts, {"waterway": ww, "name": tags.get("name")})
            return

        nat = tags.get("natural")
        if nat in ("wetland", "water") and w.is_closed() and len(w.nodes) >= 4:
            pts = self.coords(w)
            if pts and any(in_bbox(x, y) for x, y in pts):
                self.emit("waterpoly", pts, {"natural": nat, "name": tags.get("name")})


t0 = time.time()
h = Handler()
h.apply_file(f"{DATA}/ghana-latest.osm.pbf", locations=True, idx="flex_mem")
for f in h.files.values():
    f.close()
print(f"done in {time.time() - t0:.0f}s | skipped (missing locs): {h.skipped_loc}")
for k, v in h.counts.items():
    print(f"  {k}: {v}")
