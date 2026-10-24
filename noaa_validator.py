"""Real NOAA GFS-Wave location/time validation. No synthetic NOAA results.

Requires Python 3.14 (Windows), requests, eccodes.
Run: py -3.14 validate_wave_forecasts.py --date 20261021 --cycle 00
If the given cycle isn't published, select another date/cycle. NOT for vessel navigation.
"""
import argparse
import datetime as dt
import json
import math
import pathlib
import time
from urllib.parse import urlencode

import requests

LOCATIONS = {
    'carrabelle': {'name':'Carrabelle / Apalachicola FL (offshore grid)', 'lat':29.83, 'lon':-84.66},
    'boston': {'name':'Boston MA (offshore grid)', 'lat':42.12, 'lon':-70.40},
    'charleston': {'name':'Charleston SC (offshore grid)', 'lat':32.40, 'lon':-79.55},
    'sandiego': {'name':'San Diego CA (offshore grid)', 'lat':32.60, 'lon':-117.45},
    'galveston': {'name':'Galveston TX (offshore grid)', 'lat':29.15, 'lon':-94.45},
}
# First six files: 0 through 15 hours in 3-hour intervals. A user can choose
# 0,1,2,... to check for actual hourly availability; no interpolation is assumed.
# NOAA's filter selects partitioned swell by GRIB level, NOT var_SWELL2 etc.
# Surface variables plus SWELL/SWPER/SWDIR at sequence levels 1, 2, and 3.
SURFACE_VARS = ('HTSGW','PERPW','DIRPW','WVHGT','WVPER','WVDIR','WIND','WDIR')
SWELL_VARS = ('SWELL','SWPER','SWDIR')
SEQUENCE_LEVELS = ('1_in_sequence','2_in_sequence','3_in_sequence')


def classify_field(short_name, level_text):
    name = short_name.lower()
    if name in {'swell','swper','swdir'}:
        import re
        m = re.search(r'\b([123])\s+in\s+sequence\b', str(level_text), re.I)
        return name + '_partition_' + m.group(1) if m else name + '_unknown_partition'
    return name


def normalize_lon(lon):
    return ((float(lon) + 180) % 360) - 180


def distance_km(lat1,lon1,lat2,lon2):
    a,b,c,d = map(math.radians, (lat1,lat2,lon1,lon2))
    x = math.sin((b-a)/2)**2 + math.cos(a)*math.cos(b)*math.sin((d-c)/2)**2
    return 6371 * 2 * math.asin(min(1,math.sqrt(x)))


def value_valid(v, missing=None):
    try: n=float(v)
    except (TypeError, ValueError): return False
    if not math.isfinite(n) or abs(n) >= 9990: return False
    if missing is not None and math.isclose(n,float(missing),rel_tol=0,abs_tol=1e-9): return False
    return True


def format_url(date, cycle, hour, lat, lon):
    filename=f'gfswave.t{cycle}z.global.0p16.f{hour:03d}.grib2'
    directory=f'/gfs.{date}/{cycle}/wave/gridded'
    # small box around target. Tested target point can snap to ocean or masked land.
    q={'file':filename,'lev_surface':'on',
       **{'lev_'+level:'on' for level in SEQUENCE_LEVELS},
       **{'var_'+x:'on' for x in SURFACE_VARS + SWELL_VARS},
       'subregion':'','leftlon':round(lon-0.50,3), 'rightlon':round(lon+0.50,3),
       'toplat':round(lat+0.50,3),'bottomlat':round(lat-0.50,3), 'dir':directory}
    return 'https://nomads.ncep.noaa.gov/cgi-bin/filter_gfswave.pl?'+urlencode(q)


def select_common_gridpoint(decoded, lat, lon, max_km=90):
    """Choose one valid SWH ocean point, shared by every field, no interpolation."""
    reference = next((f for f in decoded if f['short'].lower() == 'swh'), None)
    if reference is None:
        return None
    candidates = []
    for la, lo, v in zip(reference['lats'], reference['lons'], reference['values']):
        la, lo = float(la), normalize_lon(lo)
        dist = distance_km(lat, lon, la, lo)
        if dist <= max_km and value_valid(v, reference['missing']):
            candidates.append((dist, la, lo))
    if not candidates:
        return None
    # Prefer the nearest SWH-valid gridpoint. Do not move offshore merely
    # because swell values are missing: that would misrepresent the location.
    _, la, lo = min(candidates)
    return {'lat':round(la,4), 'lon':round(lo,4),
            'distance_km':round(distance_km(lat,lon,la,lo),1)}


def value_at_gridpoint(field, point, tolerance_km=0.3):
    if point is None:
        return None
    for la, lo, v in zip(field['lats'],field['lons'],field['values']):
        if (abs(float(la)-point['lat']) < 0.003
            and abs(normalize_lon(lo)-point['lon']) < 0.003
            and distance_km(float(la),normalize_lon(lo),point['lat'],point['lon']) < tolerance_km):
            return round(float(v),4) if value_valid(v, field['missing']) else None
    return None


def extract_grib(path, lat, lon):
    import eccodes
    decoded=[]
    with open(path,'rb') as stream:
        while True:
            gid=eccodes.codes_grib_new_from_file(stream)
            if gid is None: break
            try:
                def get_key(k, default=''):
                    try: return str(eccodes.codes_get(gid,k))
                    except Exception: return default
                short=get_key('shortName')
                level=get_key('level','unknown')
                lev_string=get_key('levelist')
                scaled_surface=get_key('scaledValueOfFirstFixedSurface')
                surface_type=get_key('typeOfFirstFixedSurface')
                # GRIB libraries may expose ordered swell levels under different
                # key names. Match an actual sequence index; never guess a partition.
                field_id=short.lower()
                if field_id in {'shts','mpts','swdir','swell','swper'}:
                    sequence_candidates=(level, scaled_surface, get_key('levelist'))
                    sequence=next((str(v) for v in sequence_candidates
                                   if str(v) in {'1','2','3'}),None)
                    if sequence:
                        field_id=field_id+'_partition_'+sequence
                try: missing=eccodes.codes_get(gid,'missingValue')
                except Exception: missing=None
                decoded.append({'short':short,'field_id':field_id,'level':level,
                    'typeOfLevel':get_key('typeOfLevel'), 'levelist':lev_string,
                    'first_surface_type':surface_type,'first_surface_value':scaled_surface,
                    'description':get_key('name'),'units':get_key('units'),
                    'forecast_step':get_key('stepRange'), 'missing':missing,
                    'lats':eccodes.codes_get_array(gid,'latitudes'),
                    'lons':eccodes.codes_get_array(gid,'longitudes'),
                    'values':eccodes.codes_get_array(gid,'values')})
            finally:
                eccodes.codes_release(gid)
    point=select_common_gridpoint(decoded,lat,lon)
    print('GRIB fields:',[(x['field_id'],x['level'],x['typeOfLevel'],x['first_surface_value']) for x in decoded],flush=True)
    # Diagnostic: distinguish NOAA-masked swell at the chosen common point
    # from a field missing throughout the downloaded coastal subregion.
    # Nearby values are diagnostic ONLY: never substitute another gridpoint.
    rows=[]
    for f in decoded:
        valid_count=sum(1 for v in f['values'] if value_valid(v,f['missing']))
        val=value_at_gridpoint(f,point)
        if f['field_id'].endswith(('_partition_1','_partition_2','_partition_3')):
            print('SWELL_DIAGNOSTIC',f['field_id'],
                  'valid_grid_cells',valid_count,'of',len(f['values']),
                  'at_common_point',val,'missing_marker',str(f['missing']),flush=True)
        rows.append({k:f[k] for k in ('field_id','level','typeOfLevel','levelist','first_surface_type',
                                     'first_surface_value','description','units','forecast_step')} |
                    {'field':f['short'], 'grid_points':len(f['values']),
                     'value':val, 'valid_grid_cells':valid_count,
                     'status':'AVAILABLE' if val is not None else ('MISSING_AT_COMMON_POINT' if valid_count else 'NO_VALID_CELLS_IN_SUBREGION')})
    return point, rows

def run(args):
    output=pathlib.Path(args.output);output.mkdir(parents=True,exist_ok=True)
    names=args.locations.split(',')
    hours=[int(x) for x in args.hours.split(',')]
    for n in names:
        if n not in LOCATIONS: raise SystemExit('Unknown location '+n)
    if not all(0<=h<=120 for h in hours): raise SystemExit('Hours must be 0..120')
    if len(names)*len(hours)>35 and not args.allow_many:
        raise SystemExit('More than 35 downloads; add --allow-many if intended')
    report={'run_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'forecast_cycle_utc':f'{args.date} {args.cycle}Z',
            'method':'One nearest valid significant-wave-height ocean grid point within 90 km; all fields sampled at that exact grid point; no interpolation or cross-point substitution',
            'results':[], 'status':'INCOMPLETE'}
    session=requests.Session();session.headers['User-Agent']='TideMoonWaveValidator/1.0 (private prototype)'
    for name in names:
        loc=LOCATIONS[name]
        for hour in hours:
            url=format_url(args.date,args.cycle,hour,loc['lat'],loc['lon'])
            entry={'location':name,'coordinates':{'lat':loc['lat'],'lon':loc['lon']},
                   'forecast_hour':hour,'url':url,'status':'FAIL'}
            print(f'{name} +{hour:03d}h...',flush=True)
            try:
                response=session.get(url,timeout=70)
                response.raise_for_status()
                if not response.content.startswith(b'GRIB'):
                    raise RuntimeError('Expected GRIB response, got '+repr(response.text[:170]))
                path=output/f'{name}_f{hour:03d}.grib2';path.write_bytes(response.content)
                point,fields=extract_grib(path,loc['lat'],loc['lon'])
                entry.update(status='PASS' if point and any(f['field_id']=='swh' and f['value'] is not None for f in fields) else 'NO_VALID_GRIDPOINT',
                             bytes=len(response.content), common_gridpoint=point, fields=fields,
                             swell_specific_found=any((f['field_id'].startswith(('shts_partition_','mpts_partition_','swdir_partition_','swell_partition_','swper_partition_'))) and f['value'] is not None for f in fields),
                             missing_value_count=sum(f['value'] is None for f in fields))
                if not args.keep_grib: path.unlink(missing_ok=True)
            except Exception as exc: entry['error']=f'{type(exc).__name__}: {exc}'
            report['results'].append(entry)
            (output/'validation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            time.sleep(args.pause)
    report['status']='PASS' if report['results'] and all(x['status']=='PASS' for x in report['results']) else 'PARTIAL_OR_FAIL'
    report['forecast_swell_fields_verified']=any(x.get('swell_specific_found') for x in report['results'])
    report['swell_partition_level_verified']=any(f.get('field_id','').endswith(('_partition_1','_partition_2','_partition_3')) for x in report['results'] for f in x.get('fields',[]) if f.get('value') is not None)
    (output/'validation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('\nReport:',(output/'validation_report.json').resolve())
    print('Download/decode status:',report['status'])
    print('Swell-specific forecast field found:',report['forecast_swell_fields_verified'])
    print('Named swell partitions verified:',report['swell_partition_level_verified'])
    for e in report['results']:
        vals=[f"{f['field_id']}={f['value']} {f['units']}" for f in e.get('fields',[]) if f['value'] is not None]
        print(e['location'],f"+{e['forecast_hour']}h",e['status'],'; '.join(vals[:6]) or e.get('error','no valid values'))
    return 0 if report['status']=='PASS' else 2

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--date',default=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d'))
    p.add_argument('--cycle',default='00',choices=('00','06','12','18'))
    p.add_argument('--locations',default='charleston,carrabelle,boston,sandiego,galveston')
    p.add_argument('--hours',default='0,3,6,9')
    p.add_argument('--output',default='results_validation')
    p.add_argument('--pause',type=float,default=0.5)
    p.add_argument('--keep-grib',action='store_true')
    p.add_argument('--allow-many',action='store_true')
    a=p.parse_args()
    raise SystemExit(run(a))
