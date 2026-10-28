"""Publish verified Panhandle model forecasts separately from legacy five-area feeds.

This is a standalone workflow component. On any invalid NOAA forecast, do not
replace the last-known Panhandle publication. The API must independently
enforce source cycle freshness (old files are not current forecasts).
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

import noaa_validator
import publish_forecasts
from panhandle_pilot import LOCATIONS

UTC = dt.timezone.utc
HOURS = tuple(range(3, 37, 3))


def publish(output, pause):
    if pause < 10:
        raise ValueError("NOAA minimum request interval is 10 seconds")
    now = dt.datetime.now(UTC)
    selected = next((p for p in publish_forecasts.candidate_cycles(now)
                     if publish_forecasts.cycle_available(*p)), None)
    if selected is None:
        raise RuntimeError("No verified recent NOAA cycle; previous publication retained")
    date, cycle = selected
    noaa_validator.LOCATIONS.update(LOCATIONS)
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        opts = SimpleNamespace(date=date, cycle=cycle,
                locations=",".join(LOCATIONS), hours=",".join(map(str, HOURS)),
                output=str(Path(directory) / "validation"), pause=pause,
                allow_many=True, keep_grib=False)
        result = noaa_validator.run(opts)
        if result != 0:
            raise RuntimeError("Incomplete NOAA forecasts; previous publication retained")
        report = json.loads((Path(opts.output)/"validation_report.json").read_text())
        bundles = publish_forecasts.convert_report(
            report, now, required_regions=tuple(LOCATIONS), required_hours=HOURS)
        out = Path(output)
        out.mkdir(parents=True, exist_ok=True)
        publish_forecasts.write_publication(bundles, out)
        from validated_grid_lookup import build_index
        grid_index = build_index(report)
        (out / "validated_grid_index.json").write_text(
            json.dumps(grid_index, indent=2) + "\n", encoding="utf-8")
        print(f"Prepared {len(bundles)} verified Panhandle forecasts, cycle {date} {cycle}Z")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="panhandle")
    parser.add_argument("--pause", type=float, default=10.5)
    args = parser.parse_args()
    publish(args.output, args.pause)
