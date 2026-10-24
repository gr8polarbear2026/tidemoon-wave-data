"""Compare NOAA global and North Atlantic swell values without publishing data."""
import datetime as dt
import pathlib
import tempfile
import time
import requests
import noaa_validator as nv
from publish_forecasts import candidate_cycles, cycle_available, UTC

def main():
    selected=next(((d,c) for d,c in candidate_cycles(dt.datetime.now(UTC)) if cycle_available(d,c)),None)
    if not selected:
        raise SystemExit("No ready NOAA cycle; no source comparison possible")
    date,cycle=selected
    loc=nv.LOCATIONS['charleston']
    summaries={}
    for domain in ('global.0p16','atlocn.0p16'):
        url=nv.format_url(date,cycle,6,loc['lat'],loc['lon'],domain=domain)
        print(f"DIAGNOSTIC domain={domain} cycle={date} {cycle}Z forecast=+6h",flush=True)
        response=requests.get(url,timeout=90,headers={'User-Agent':'CoastPilotSwellDiagnostic/1.0'})
        response.raise_for_status()
        if not response.content.startswith(b'GRIB'):
            raise SystemExit(f"{domain}: response was not GRIB")
        with tempfile.TemporaryDirectory() as td:
            path=pathlib.Path(td)/'sample.grib2'
            path.write_bytes(response.content)
            point,fields=nv.extract_grib(path,loc['lat'],loc['lon'])
        swell=[f for f in fields if '_partition_' in f['field_id']]
        valid=[f for f in swell if f['value'] is not None]
        summary={'point':point,'fields':len(swell),'valid_swell_fields':len(valid),
                 'available':[(x['field_id'],x['value'],x['units']) for x in valid],
                 'cell_coverage':[(x['field_id'],x['valid_grid_cells'],x['grid_points']) for x in swell]}
        summaries[domain]=summary
        print(f"SUMMARY {domain} {summary}",flush=True)
        time.sleep(10.5)
    if summaries['atlocn.0p16']['valid_swell_fields']>0:
        print("ATLANTIC_CANDIDATE_HAS_SWELL: Validation for production use still required",flush=True)
    else:
        print("NO_VERIFIED_ALTERNATE_SWELL_AT_CHARLESTON: Keep current data source and report unavailable",flush=True)

if __name__=='__main__':
    main()
