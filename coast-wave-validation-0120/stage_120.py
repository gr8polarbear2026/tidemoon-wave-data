"""Staging-only +120h test; never writes production paths or changes production modules."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import publish_panhandle as publisher
from regional_panhandle import HOURS, LOCATIONS, UTC, complete_report

extended = tuple(range(3, 121))
original = complete_report
baseline = None


def with_independent_72_reference(date, cycle, load):
    # Use the exact same real GRIB bytes and cycle; re-decode the first 70
    # files independently with the original +72 range, without extra HTTP.
    acquired = {}
    def remember(hour):
        result = load(hour)
        acquired[hour] = result
        return result
    full = original(date, cycle, remember, hours=extended)
    report = original(date, cycle, acquired.__getitem__)
    assert report['forecast_cycle_utc'] == full['forecast_cycle_utc']
    ref = publisher.publish_forecasts.convert_report(
        report, dt.datetime.now(UTC), required_regions=tuple(LOCATIONS), required_hours=HOURS)
    publisher.verify_cells(ref, LOCATIONS)
    global baseline
    baseline = ref
    return full


def comparable(row):
    return {k: row[k] for k in ('forecast_hour', 'valid_utc', 'ocean_gridpoint', 'fields')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--published-reference', required=True)
    a = parser.parse_args()
    root = Path(os.environ['RUNNER_TEMP']).resolve()
    output = Path(a.output).resolve()
    assert output.is_relative_to(root) and not output.exists(), 'Stage output must be fresh under RUNNER_TEMP'
    publisher.HOURS = extended
    publisher.complete_report = with_independent_72_reference
    assert publisher.publish(output, 10.5) and baseline is not None
    index = json.loads((output/'index.json').read_text())
    cycle = index['model_cycle_utc']
    assert len(index['locations']) == len(LOCATIONS) == 11
    actual = dt.datetime.fromisoformat(cycle)
    assert dt.timedelta(0) <= dt.datetime.now(UTC)-actual < dt.timedelta(hours=18), 'Cycle stale at final gate'
    compare_published = 0
    for site in LOCATIONS:
        current = json.loads((output/f'{site}.json').read_text())
        rows = current['forecast']
        assert current['model_cycle_utc'] == cycle == baseline[site]['model_cycle_utc'], site
        assert tuple(r['forecast_hour'] for r in rows) == extended, site
        assert [comparable(r) for r in rows[:len(HOURS)]] == [comparable(r) for r in baseline[site]['forecast']], site
        assert all(dt.datetime.fromisoformat(r['valid_utc']) == actual + dt.timedelta(hours=r['forecast_hour']) for r in rows), site
        path = Path(a.published_reference)/f'{site}.json'
        if path.exists():
            prev = json.loads(path.read_text())
            if prev.get('model_cycle_utc') == cycle:
                assert [comparable(r) for r in rows[:len(HOURS)]] == [comparable(r) for r in prev['forecast']], site
                compare_published += 1
    assert compare_published in (0, len(LOCATIONS)), 'Mixed-cycle existing publication'
    print(f'PASS: {cycle}, 11 sites x 118 native hourly samples (+3 through +120), exact 770-row parity with unmodified same-cycle +72 pipeline; same-cycle published sites also compared: {compare_published}. No publish.')


if __name__ == '__main__':
    main()
