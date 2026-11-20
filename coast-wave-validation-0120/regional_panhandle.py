"""Validate one NOAA-fed Panhandle regional subset per model hour, never publish on its own."""
import datetime as dt
from pathlib import Path
from urllib.parse import urlencode

import eccodes as ec
import numpy as np

import noaa_validator as legacy
from panhandle_pilot import LOCATIONS
from publish_forecasts import UTC, FIELDS

HOURS = tuple(range(3, 73))
CROP = 0.5
RADIUS_EPSILON = 1e-5  # NOAA coordinates are encoded on a fractional-degree grid.


def cycle_time(date, cycle):
    return dt.datetime.strptime(date + cycle, '%Y%m%d%H').replace(tzinfo=UTC)


def regional_url(date, cycle, hour):
    lats = [x['lat'] for x in LOCATIONS.values()]
    lons = [x['lon'] for x in LOCATIONS.values()]
    query = {
        'file': f'gfswave.t{cycle}z.global.0p16.f{hour:03d}.grib2', 'lev_surface': 'on',
        **{'lev_' + key: 'on' for key in legacy.SEQUENCE_LEVELS},
        **{'var_' + key: 'on' for key in legacy.SURFACE_VARS + legacy.SWELL_VARS},
        'subregion': '', 'leftlon': round(min(lons)-CROP, 3), 'rightlon': round(max(lons)+CROP, 3),
        'toplat': round(max(lats)+CROP, 3), 'bottomlat': round(min(lats)-CROP, 3),
        'dir': f'/gfs.{date}/{cycle}/wave/gridded',
    }
    return 'https://nomads.ncep.noaa.gov/cgi-bin/filter_gfswave.pl?' + urlencode(query)


def decode(path, date, cycle, hour):
    """Validate exact model run and native valid time for every decoded field."""
    issue = cycle_time(date, cycle)
    valid = issue + dt.timedelta(hours=hour)
    fields = []
    with Path(path).open('rb') as stream:
        if stream.read(4) != b'GRIB':
            raise ValueError(f'f{hour:03d}: not a GRIB payload')
        stream.seek(-4, 2)
        if stream.read(4) != b'7777':
            raise ValueError(f'f{hour:03d}: incomplete GRIB payload')
        stream.seek(0)
        while (gid := ec.codes_grib_new_from_file(stream)) is not None:
            try:
                actual = tuple(int(ec.codes_get(gid, k)) for k in
                    ('dataDate','dataTime','validityDate','validityTime'))
                expected = (int(date), int(cycle)*100, int(valid.strftime('%Y%m%d')), valid.hour*100)
                if actual != expected or str(ec.codes_get(gid,'stepRange')) != str(hour):
                    raise ValueError(f'f{hour:03d}: wrong model cycle or valid hour: {actual}')
                short = str(ec.codes_get(gid,'shortName')).lower()
                key = short
                if short in {'shts','mpts','swdir','swell','swper'}:
                    for field in ('level','scaledValueOfFirstFixedSurface','levelist'):
                        try:
                            level = str(ec.codes_get(gid,field))
                        except ec.CodesInternalError:
                            continue
                        if level in {'1','2','3'}:
                            key += '_partition_'+level
                            break
                if key not in FIELDS:
                    continue
                fields.append({
                    'short':short, 'field_id':key, 'units':str(ec.codes_get(gid,'units')),
                    'missing':ec.codes_get(gid,'missingValue'), 'lats':ec.codes_get_array(gid,'latitudes'),
                    'lons':(ec.codes_get_array(gid,'longitudes')+180)%360-180,
                    'values':ec.codes_get_array(gid,'values'),
                })
            finally:
                ec.codes_release(gid)
    keys = [f['field_id'] for f in fields]
    if not fields or len(keys) != len(set(keys)) or 'swh' not in keys:
        raise ValueError(f'f{hour:03d}: missing significant wave height or duplicate fields')
    return fields


def crop_fields(fields, lat, lon):
    """Recreate each legacy location's requested plus/minus 0.50-degree box."""
    cropped = []
    for f in fields:
        mask = (np.abs(f['lats']-lat) <= CROP+RADIUS_EPSILON) & (np.abs(f['lons']-lon) <= CROP+RADIUS_EPSILON)
        cropped.append(dict(f, **{k:f[k][mask] for k in ('lats','lons','values')}))
    return cropped


def location_rows(fields, hour):
    for key, loc in LOCATIONS.items():
        lat, lon = loc['lat'], loc['lon']
        crop = crop_fields(fields, lat, lon)
        point = legacy.select_common_gridpoint(crop, lat, lon)
        if point is None:
            raise ValueError(f'{key} +{hour}h: no verified ocean cell')
        available = []
        for f in crop:
            val = legacy.value_at_gridpoint(f, point)
            available.append({'field_id':f['field_id'],'units':f['units'], 'value':val,
                              'status':'MISSING_AT_COMMON_POINT' if val is None else 'AVAILABLE'})
        swh = next((f for f in available if f['field_id']=='swh'),{})
        if swh.get('units') != 'm' or swh.get('value') is None or not 0 <= swh['value'] <= 30:
            raise ValueError(f'{key} +{hour}h: invalid significant wave height')
        yield {'location':key,'forecast_hour':hour,'status':'PASS','common_gridpoint':point,'fields':available}


def complete_report(date, cycle, loader, hours=HOURS):
    expected = {(key,h) for key in LOCATIONS for h in hours}
    rows = [r for h in hours for r in location_rows(decode(loader(h),date,cycle,h),h)]
    if len(rows) != len(expected) or {(r['location'],r['forecast_hour']) for r in rows} != expected:
        raise ValueError('Regional forecast batch incomplete')
    return {'forecast_cycle_utc':f'{date} {cycle}Z','status':'PASS','results':rows}
