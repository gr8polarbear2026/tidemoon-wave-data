"""Stage complete hourly Panhandle publication; preserve the old feed on validation failure."""
import argparse
import datetime as dt
import json
import tempfile
import time
from pathlib import Path

from regional_panhandle import HOURS, LOCATIONS, UTC, complete_report, cycle_time, regional_url
import noaa_validator
import publish_forecasts
import requests
from validated_grid_lookup import build_index

AGENT = 'TideMoonWavePublisher/2.0 (NOAA regional subset)'


def verify_cells(bundles, sites):
    for loc in sites:
        points = [f['ocean_gridpoint'] for f in bundles[loc]['forecast']]
        if not points or len({(p['lat'],p['lon']) for p in points}) != 1:
            raise ValueError(f'{loc}: missing or mixed ocean cells')
        if loc in {'stmarks','panacea'} and any(p['distance_km'] > 30 for p in points):
            raise ValueError(f'{loc}: no nearby verified ocean point')


def validate_eastern_cells(bundles):
    verify_cells(bundles,('stmarks','panacea'))


def prepare(date, cycle, load_grib, destination, now, *, enforce_freshness=False):
    """Validate every timestamp and location before touching existing output."""
    noaa_validator.LOCATIONS.update(LOCATIONS)
    report = complete_report(date,cycle,load_grib)
    bundles = publish_forecasts.convert_report(report,now,required_regions=tuple(LOCATIONS),required_hours=HOURS)
    verify_cells(bundles, LOCATIONS)
    if enforce_freshness and dt.datetime.now(UTC)-cycle_time(date,cycle) >= dt.timedelta(hours=18):
        raise ValueError('NOAA cycle aged out during validation; prior files retained')
    grid_index = build_index(report)
    if {loc for p in grid_index['points'] for loc in p['validated_sites']} != set(LOCATIONS):
        raise ValueError('Validated coordinate index does not cover all eleven locations')
    destination = Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        staging = Path(temp)
        publish_forecasts.write_publication(bundles,staging)
        (staging/'validated_grid_index.json').write_text(json.dumps(grid_index,indent=2)+'\n',encoding='utf8')
        destination.mkdir(parents=True,exist_ok=True)
        for path in staging.iterdir():
            path.replace(destination/path.name)
    return bundles


def complete_previous(path, date, cycle):
    if path is None:
        return False
    stamp = cycle_time(date,cycle).isoformat().replace('+00:00','Z')
    try:
        for site in LOCATIONS:
            prior = json.loads((path / f'{site}.json').read_text())
            if (prior.get('model_cycle_utc') != stamp or prior.get('location_id') != site or
                tuple(x['forecast_hour'] for x in prior['forecast']) != HOURS or
                not all(0 <= x['fields']['swh']['value'] <= 30 for x in prior['forecast'])):
                return False
        idx=json.loads((path/'validated_grid_index.json').read_text())
        return {s for p in idx['points'] for s in p['validated_sites']}==set(LOCATIONS)
    except (OSError,ValueError,KeyError,TypeError):
        return False


def index_ready(session,date,cycle):
    last=HOURS[-1]
    url=(f'https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/'
         f'gfs.{date}/{cycle}/wave/gridded/gfswave.t{cycle}z.global.0p16.f{last:03d}.grib2.idx')
    try:
        r=session.get(url,timeout=(6,12))
        return r.ok and ':HTSGW:' in r.text
    except requests.RequestException:
        return False


def select_cycle(session,now,previous):
    for date,cycle in publish_forecasts.candidate_cycles(now):
        if now-cycle_time(date,cycle) >= dt.timedelta(hours=18):
            break
        if complete_previous(previous,date,cycle):
            return None
        if index_ready(session,date,cycle):
            return date,cycle
    raise RuntimeError('No verified recent full NOAA cycle; previous files retained')


def publish(output, pause, previous=None, cached=None, date=None, cycle=None):
    if pause < 10:
        raise ValueError('NOAA minimum request spacing is 10 seconds')
    now=dt.datetime.now(UTC)
    start=time.monotonic()
    if cached is not None:
        if date is None or cycle is None:
            raise ValueError('Cached GRIB replay requires the exact --date and --cycle')
        prepare(date,cycle,lambda h:Path(cached)/f'regional_{h:03d}.grib2',output,now)
        print(f'Replayed {len(LOCATIONS)} locations x {len(HOURS)} hours in {time.monotonic()-start:.1f}s; no networking or publication.')
        return True
    if date is not None or cycle is not None:
        raise ValueError('Provide a date and cycle only for a cached replay')
    with requests.Session() as session, tempfile.TemporaryDirectory() as temp:
        session.headers['User-Agent']=AGENT
        selected=select_cycle(session,now,Path(previous) if previous else None)
        if selected is None:
            print('Already have this full cycle; no new NOAA downloads or changes.')
            return False
        date,cycle=selected
        last_finished=None
        def load(hour):
            nonlocal last_finished
            if last_finished is not None:
                time.sleep(max(0, pause-(time.monotonic()-last_finished)))
            response=noaa_validator.get_grib_with_retries(session,regional_url(date,cycle,hour),timeout=(8,25))
            last_finished=time.monotonic()
            path=Path(temp)/f'regional_{hour:03d}.grib2'
            path.write_bytes(response.content)
            print(f'NOAA +{hour:03d}h {len(response.content)} bytes; elapsed {time.monotonic()-start:.1f}s',flush=True)
            return path
        prepare(date,cycle,load,output,dt.datetime.now(UTC),enforce_freshness=True)
        print(f'Prepared complete cycle {date} {cycle}Z in {time.monotonic()-start:.1f}s. No live write.')
    return True


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,help='Local stage directory, not a nested live checkout path.')
    parser.add_argument('--previous')
    parser.add_argument('--pause',type=float,default=10.5)
    parser.add_argument('--cached-grib-dir')
    parser.add_argument('--date')
    parser.add_argument('--cycle',choices=('00','06','12','18'))
    args=parser.parse_args()
    publish(args.output,args.pause,args.previous,args.cached_grib_dir,args.date,args.cycle)
