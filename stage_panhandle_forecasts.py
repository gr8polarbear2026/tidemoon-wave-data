"""Stage (never publish) validated 36-hour Panhandle forecast JSON.

Only creates app-compatible forecast JSON when every Panhandle site and
forecast hour has a valid NOAA significant wave-height gridpoint.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import noaa_validator
import publish_forecasts
from panhandle_pilot import LOCATIONS

HOURS = tuple(range(3, 37, 3))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    report = json.loads(Path(args.report).read_text())
    noaa_validator.LOCATIONS.update(LOCATIONS)
    expected = {(name, hour) for name in LOCATIONS for hour in HOURS}
    records = {(row.get("location"), row.get("forecast_hour")): row for row in report.get("results", [])}
    failed = [f"{name} +{hour}" for name, hour in sorted(expected)
              if (name, hour) not in records or records[(name, hour)].get("status") != "PASS"]
    if failed:
        print("Panhandle staging withheld: unverified slots:", ", ".join(failed))
        return
    # The converter rejects rows with missing wave height even if a row was PASS.
    try:
        bundles = publish_forecasts.convert_report(
            dict(report, status="PASS"),
            dt.datetime.now(dt.timezone.utc),
            required_regions=tuple(LOCATIONS),
            required_hours=HOURS,
        )
    except (KeyError, ValueError) as exc:
        print(f"Panhandle staging withheld: {exc}")
        return
    publish_forecasts.write_publication(bundles, args.out)
    # Note this directory is ONLY a GitHub Actions artifact, not the live site.
    print(f"Staged {len(bundles)} validated Panhandle JSON files; no live publication.")

if __name__ == "__main__":
    main()
