"""Pure coordinate lookup of previously validated GFS-Wave ocean points.

This module never calls NOAA, assumes coverage, or substitutes invalid grid cells.
A future publisher can provide an index of successfully validated ocean gridpoints.
"""
import json
import math
from pathlib import Path

def km_between(lat1, lon1, lat2, lon2):
    a, b = map(math.radians, (lat1, lat2))
    da = math.radians(lat2 - lat1)
    db = math.radians(((lon2 - lon1 + 180) % 360) - 180)
    h = math.sin(da / 2)**2 + math.cos(a)*math.cos(b)*math.sin(db / 2)**2
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))

def build_index(report):
    """Index distinct actual gridpoints from PASS rows; deduplicate by coordinates."""
    points = {}
    for row in report.get("results", []):
        p = row.get("common_gridpoint")
        if row.get("status") != "PASS" or not p:
            continue
        lat, lon = p.get("lat"), p.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        key = f"{lat:.4f},{lon:.4f}"
        if key not in points:
            points[key] = {"latitude": lat, "longitude": lon, "validated_sites": []}
        site = row.get("location")
        if site not in points[key]["validated_sites"]:
            points[key]["validated_sites"].append(site)
    return {"schema_version": 1, "source": "validated NOAA GFS-Wave gridpoints",
            "coverage_complete": False, "points": list(points.values())}

def nearest(index, latitude, longitude, max_distance_km=90):
    """Return nearest verified point within the limit; otherwise return None."""
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Invalid geographic coordinates")
    if max_distance_km <= 0: raise ValueError("Positive max distance required")
    candidates = [(km_between(latitude, longitude, x["latitude"], x["longitude"]), x)
                  for x in index.get("points", [])]
    if not candidates: return None
    distance, chosen = min(candidates, key=lambda item: item[0])
    if distance > max_distance_km: return None
    return dict(chosen, distance_km=round(distance, 2))

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("validation_report")
    p.add_argument("--output", default="pilot_index.json")
    args = p.parse_args()
    report = json.loads(Path(args.validation_report).read_text())
    Path(args.output).write_text(json.dumps(build_index(report), indent=2) + "\n")

if __name__ == "__main__":
    main()
