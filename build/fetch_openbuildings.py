"""Stream Google Open Buildings v3 (CC BY-4.0) for the Accra bbox.

Downloads the S2 L6 cell 0fdf CSV (no header: latitude, longitude,
area_in_meters, confidence, geometry WKT, full_plus_code), keeps
confident footprints inside the bbox, writes data/openbuildings.jsonl
in the same {"c": [[lon,lat],...]} shape as the OSM extracts.
Credit: Google Open Buildings, CC BY-4.0.
"""
import csv
import gzip
import io
import json
import time
import urllib.request

from shapely import wkt

URL = ("https://storage.googleapis.com/open-buildings-data/v3/"
       "polygons_s2_level_6_gzip_no_header/0fdf_buildings.csv.gz")
DATA = "/Users/osborn/BIG PROJECT/accra-flood-grid/data"
BBOX = (-0.32, 5.52, -0.12, 5.70)
MIN_CONF, MIN_AREA = 0.70, 20.0

t0 = time.time()
kept = seen = 0
resp = urllib.request.urlopen(URL, timeout=120)
stream = io.TextIOWrapper(gzip.GzipFile(fileobj=resp), encoding="utf-8")
with open(f"{DATA}/openbuildings.jsonl", "w") as out:
    for row in csv.reader(stream):
        seen += 1
        lat, lon = float(row[0]), float(row[1])
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            continue
        if float(row[3]) < MIN_CONF or float(row[2]) < MIN_AREA:
            continue
        poly = wkt.loads(row[4])
        if poly.geom_type != "Polygon":
            continue
        coords = [[round(x, 7), round(y, 7)] for x, y in poly.exterior.coords]
        out.write(json.dumps({"c": coords}, separators=(",", ":")) + "\n")
        kept += 1
        if kept % 100000 == 0:
            print(f"  ...{kept} kept / {seen} scanned ({time.time()-t0:.0f}s)")
print(f"done: {kept} footprints kept of {seen} scanned ({time.time()-t0:.0f}s)")
