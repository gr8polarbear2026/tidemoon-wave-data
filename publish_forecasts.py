"""Publish small verified forecast JSON from NOAA GFS-Wave; never invent missing values."""
import argparse
import datetime as dt
import json
import pathlib
import shutil
import tempfile
from types import SimpleNamespace
import noaa_validator

UTC = dt.timezone.utc
REGIONS = ('carrabelle', 'boston', 'charleston', 'sandiego', 'galveston')
HOURS = tuple(range(3, 37, 3))  # Twelve native 3-hour slots through +36h; no interpolation.
FIELDS = {'swh','perpw','dirpw','shww','mpww','wvdir','wvhgt','wvper','wind','ws','wdir'} | {
    f'{prefix}_partition_{n}' for prefix in ('shts','mpts','swdir','swell','swper') for n in range(1,4)
}

def choose_cycle(now):
    """Most recent nominal 6-hour model cycle; publication is checked separately."""
    lagged=now.astimezone(UTC)-dt.timedelta(hours=4)
    cycle=(lagged.hour//6)*6
    return lagged.strftime('%Y%m%d'), f'{cycle:02d}'


def candidate_cycles(now, count=5):
    """Try recent cycles in UTC order, allowing for publication delays."""
    lagged=now.astimezone(UTC)-dt.timedelta(hours=4)
    start=lagged.replace(hour=(lagged.hour//6)*6, minute=0, second=0, microsecond=0)
    for i in range(count):
        current=start-dt.timedelta(hours=6*i)
        yield current.strftime('%Y%m%d'), current.strftime('%H')


def cycle_available(date, cycle, timeout=20):
    """Check published GRIB index files before expensive filtered downloads.

    The f012 index is published after earlier forecast hours. A missing index
    means the cycle is not ready for this publisher; never fabricate values.
    """
    import requests
    filename=f'gfswave.t{cycle}z.global.0p16.f012.grib2.idx'
    url=(f'https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/'
         f'gfs.{date}/{cycle}/wave/gridded/{filename}')
    try:
        response=requests.get(url, timeout=timeout,
                              headers={'User-Agent':'TideMoonWavePublisher/1.1'})
        if response.status_code != 200:
            print(f'NOAA cycle {date} {cycle}Z not ready: HTTP {response.status_code}',flush=True)
            return False
        if not response.text.strip() or 'HTSGW' not in response.text and 'WVHGT' not in response.text:
            print(f'NOAA cycle {date} {cycle}Z missing wave fields in index',flush=True)
            return False
        return True
    except requests.RequestException as exc:
        print(f'NOAA cycle {date} {cycle}Z availability error: {exc}',flush=True)
        return False

def compact_row(row, cycle_time):
    if row.get('status')!='PASS' or not row.get('common_gridpoint'): return None
    fields={}
    for f in row.get('fields',[]):
        key=f.get('field_id')
        if key not in FIELDS: continue
        val=f.get('value')
        if f.get('status') == 'AVAILABLE' and noaa_validator.value_valid(val):
            fields[key]={'value':val,'units':f.get('units','')}
        else:
            fields[key]=None
    if not fields.get('swh'): return None
    h=int(row['forecast_hour'])
    return {'forecast_hour':h,
            'valid_utc':(cycle_time+dt.timedelta(hours=h)).isoformat().replace('+00:00','Z'),
            'ocean_gridpoint':row['common_gridpoint'], 'fields':fields}

def convert_report(report, generated_at, required_regions=REGIONS, required_hours=HOURS):
    if report.get('status')!='PASS': raise ValueError('NOAA report not completely successful')
    day,cycle=report['forecast_cycle_utc'].split(' ')
    cycle_time=dt.datetime.strptime(day+cycle[:2],'%Y%m%d%H').replace(tzinfo=UTC)
    got={(r.get('location'),r.get('forecast_hour')):r for r in report['results']}
    bundles={}
    for loc in required_regions:
        points=[]
        for hour in required_hours:
            row=got.get((loc,hour))
            if row is None: raise ValueError(f'Missing {loc} +{hour}h')
            value=compact_row(row,cycle_time)
            if value is None: raise ValueError(f'No valid wave value for {loc} +{hour}h')
            points.append(value)
        meta=noaa_validator.LOCATIONS[loc]
        bundles[loc]={
            'schema_version':1,'source':'NOAA NCEP GFS-Wave NOMADS',
            'generated_at_utc':generated_at.isoformat().replace('+00:00','Z'),
            'model_cycle_utc':cycle_time.isoformat().replace('+00:00','Z'),
            'location_id':loc,'location_label':meta['name'],
            'requested_coordinates':{'lat':meta['lat'],'lon':meta['lon']},
            'disclaimer':'Offshore model forecasts, not local harbor observations or navigation advice.',
            'forecast':points}
    return bundles

def write_publication(bundles, destination):
    out=pathlib.Path(destination)
    out.mkdir(parents=True,exist_ok=True)
    for loc, payload in bundles.items():
        (out/f'{loc}.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    index={'schema_version':1,'source':'NOAA NCEP GFS-Wave NOMADS',
           'generated_at_utc':next(iter(bundles.values()))['generated_at_utc'],
           'model_cycle_utc':next(iter(bundles.values()))['model_cycle_utc'],
           'locations':list(bundles.keys()),
           'disclaimer':'Forecast data may become stale; check generated and valid timestamps.'}
    (out/'index.json').write_text(json.dumps(index,indent=2)+'\n',encoding='utf-8')
    (out/'.nojekyll').write_text('',encoding='utf-8')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--date',help='NOAA cycle UTC date YYYYMMDD (default: verified recent cycle)')
    p.add_argument('--cycle',choices=('00','06','12','18'))
    p.add_argument('--output',default='site')
    p.add_argument('--pause',type=float,default=10.5)
    args=p.parse_args()
    now=dt.datetime.now(UTC)
    if args.pause < 10: p.error('NOAA requires at least 10 seconds between downloads')
    if args.date or args.cycle:
        # Explicit cycle is useful for diagnostics and must not silently change.
        date,cycle=choose_cycle(now)
        date=args.date or date; cycle=args.cycle or cycle
        if not cycle_available(date,cycle):
            raise SystemExit(f'NOAA cycle {date} {cycle}Z not published; existing site remains unchanged.')
    else:
        selected=next(((d,c) for d,c in candidate_cycles(now) if cycle_available(d,c)),None)
        if selected is None:
            raise SystemExit('No verified NOAA forecast cycle in last 28 hours; existing site remains unchanged.')
        date,cycle=selected
    print(f'Using verified NOAA cycle {date} {cycle}Z',flush=True)
    # No public site files are created unless every download and decode passes.
    with tempfile.TemporaryDirectory() as temp:
        opts=SimpleNamespace(date=date, cycle=cycle,
            locations=','.join(REGIONS),hours=','.join(map(str,HOURS)),
            output=str(pathlib.Path(temp)/'raw'),pause=args.pause,
            keep_grib=False,allow_many=True)
        rc=noaa_validator.run(opts)
        if rc != 0: raise SystemExit('NOAA incomplete: NO publication. Retry later or choose prior cycle.')
        report=json.loads((pathlib.Path(temp)/'raw'/'validation_report.json').read_text('utf-8'))
        bundles=convert_report(report,now)
        write_publication(bundles,args.output)
    print(f'Published {len(bundles)} region files to {args.output}')

if __name__=='__main__': main()
