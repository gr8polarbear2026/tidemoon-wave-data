"""Nonpublishing GFS-Wave coverage probe for additional US coastlines.

Uses existing NOAA validator and its nearest common valid ocean gridpoint rules.
Outputs diagnostics only. Never changes the live five-location publication.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace
import noaa_validator
import publish_forecasts

# Representative U.S. coastal test locations, not a comprehensive directory.
# Coordinates are ocean-adjacent test requests, not asserted NOAA gridpoints.
PILOT_LOCATIONS = {
    "maine": {"name": "Portland, ME offshore test", "lat": 43.58, "lon": -69.86},
    "outerbanks": {"name": "Outer Banks, NC offshore test", "lat": 35.54, "lon": -75.21},
    "louisiana": {"name": "Grand Isle, LA offshore test", "lat": 29.52, "lon": -89.91},
    "oregon": {"name": "Newport, OR offshore test", "lat": 44.59, "lon": -124.23},
    "alaska": {"name": "Kodiak, AK offshore test", "lat": 57.75, "lon": -152.72},
    "alaska_south": {"name": "Kodiak southern offshore diagnostic", "lat": 57.20, "lon": -152.72},
    "alaska_east": {"name": "Kodiak eastern offshore diagnostic", "lat": 57.75, "lon": -151.70},
    "hawaii": {"name": "Honolulu, HI offshore test", "lat": 21.20, "lon": -157.96},
    "puertorico": {"name": "San Juan, PR offshore test", "lat": 18.55, "lon": -65.92},
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="pilot_results")
    parser.add_argument("--hours", default="3,6")
    parser.add_argument("--pause", type=float, default=10.5)
    parser.add_argument("--date")
    parser.add_argument("--cycle", choices=("00", "06", "12", "18"))
    args = parser.parse_args()
    if args.pause < 10: parser.error("Minimum 10 seconds between NOAA downloads")
    if args.date or args.cycle:
        date, cycle = publish_forecasts.choose_cycle(dt.datetime.now(dt.timezone.utc))
        date = args.date or date
        cycle = args.cycle or cycle
        if not publish_forecasts.cycle_available(date, cycle):
            raise SystemExit("Requested cycle not published; no forecasts collected")
    else:
        selected = next((pair for pair in publish_forecasts.candidate_cycles(dt.datetime.now(dt.timezone.utc))
                         if publish_forecasts.cycle_available(*pair)), None)
        if selected is None: raise SystemExit("No currently verified NOAA cycle available")
        date, cycle = selected
    noaa_validator.LOCATIONS.update(PILOT_LOCATIONS)
    opts = SimpleNamespace(date=date, cycle=cycle, locations=",".join(PILOT_LOCATIONS),
                           hours=args.hours, output=args.output, pause=args.pause,
                           allow_many=True, keep_grib=False)
    code = noaa_validator.run(opts)
    path = Path(args.output) / "validation_report.json"
    if path.exists():
        report = json.loads(path.read_text())
        summary = {
            "source": "NOAA NCEP GFS-Wave validation, nonpublishing pilot",
            "cycle": report["forecast_cycle_utc"],
            "requested_sites": len(PILOT_LOCATIONS),
            "forecast_hours_per_site": len(args.hours.split(",")),
            "passed_points": sum(item["status"] == "PASS" for item in report["results"]),
            "failed_points": sum(item["status"] != "PASS" for item in report["results"]),
            "swell_partition_values_verified": report.get("swell_partition_level_verified", False),
            "details": [
                {"location": row["location"], "hour": row["forecast_hour"],
                 "status": row["status"], "ocean_gridpoint": row.get("common_gridpoint"),
                 "error": row.get("error")}
                for row in report["results"]
            ]
        }
        (Path(args.output) / "pilot_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps({key:value for key,value in summary.items() if key!="details"}, indent=2))
    # A partial NOAA validation is a completed diagnostic, not a failed execution.
    # Preserve the point-level FAIL statuses in the artifact; never publish it.
    if path.exists():
        print("DIAGNOSTIC_COMPLETED_WITH_PARTIAL_COVERAGE" if code else "DIAGNOSTIC_COMPLETED_FULL_COVERAGE")
        return
    raise SystemExit(code)

if __name__ == "__main__":
    main()
