"""Live API smoke test for Panhandle preview and five legacy endpoints.

Runs only in GitHub Actions; must not publish or edit backend data.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

PREVIEW="https://coast-pilot-panhandle-preview.gr8polarbear.workers.dev"
LEGACY="https://tidemoon-wave-data.gr8polarbear.workers.dev"
cases=[
    ("Cape San Blas",PREVIEW+"/api/waves/panhandle/coordinates?lat=29.57&lon=-85.29",True),
    ("Port St Joe",PREVIEW+"/api/waves/panhandle/coordinates?lat=29.64&lon=-85.08",True),
    ("Pensacola",PREVIEW+"/api/waves/panhandle/coordinates?lat=30.18&lon=-87.39",True),
    ("Outside coverage",PREVIEW+"/api/waves/panhandle/coordinates?lat=39&lon=-84",False),
]+[(name,LEGACY+"/api/waves/"+name,True) for name in
   ["carrabelle","boston","charleston","sandiego","galveston"]]

failed=0
for label,url,expect_current in cases:
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={"Accept":"application/json"}),timeout=20) as f:
            code=f.status
            data=json.load(f)
    except urllib.error.HTTPError as err:
        code=err.code
        data=json.loads(err.read().decode("utf-8"))
    except Exception as err:
        failed+=1
        print(f"FAIL {label}: network error: {err}")
        continue
    status=data.get("status")
    if expect_current:
        valid=code==200 and status=="CURRENT" and len(data.get("forecast",[]))>0
        if valid:
            valid=all("valid_utc" in x and isinstance(x.get("wave_height_m"),(int,float))
                      and "grid" in x and len(x.get("swell_partitions",[]))==3
                      for x in data["forecast"])
        print(f"{'PASS' if valid else 'FAIL'} {label}: HTTP {code} status={status} forecast_slots={len(data.get('forecast',[]))}")
    else:
        valid=code==404 and status=="OUTSIDE_VERIFIED_PANHANDLE_COVERAGE"
        print(f"{'PASS' if valid else 'FAIL'} {label}: HTTP {code} status={status}")
    if not valid: failed+=1
print(f"Live smoke test: {len(cases)-failed}/{len(cases)} successful")
sys.exit(1 if failed else 0)
