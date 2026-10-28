"""Nonpublishing Florida Panhandle NOAA GFS-Wave diagnostic.

Checks distinct Panhandle coastal/offshore target coordinates. All reported
gridpoints are validated by the shared NOAA validator. No live publication.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace
import noaa_validator
import publish_forecasts

LOCATIONS = {
    "pensacola": {"name":"Pensacola / Perdido Key offshore test", "lat":30.18,"lon":-87.39},
    "navarre": {"name":"Navarre Beach offshore test", "lat":30.25,"lon":-86.92},
    "destin": {"name":"Destin offshore test", "lat":30.20,"lon":-86.49},
    "panamacity": {"name":"Panama City Beach offshore test", "lat":30.07,"lon":-85.92},
    "mexicobeach": {"name":"Mexico Beach offshore test", "lat":29.84,"lon":-85.38},
    "portsaintjoe": {"name":"Port St Joe / St Joseph Bay offshore test", "lat":29.64,"lon":-85.08},
    "capesanblas": {"name":"Cape San Blas offshore test", "lat":29.57,"lon":-85.29},
    "apalachicola": {"name":"Apalachicola / St George Island offshore test", "lat":29.65,"lon":-84.83},
    "carrabellewest": {"name":"Carrabelle offshore test", "lat":29.77,"lon":-84.69},
}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="panhandle_results")
    p.add_argument("--hours",default="3,6")
    p.add_argument("--pause",type=float,default=10.5)
    a=p.parse_args()
    if a.pause<10:p.error("Minimum 10 seconds between NOAA downloads")
    selected=next(((d,c) for d,c in publish_forecasts.candidate_cycles(dt.datetime.now(dt.timezone.utc))
                   if publish_forecasts.cycle_available(d,c)),None)
    if selected is None:raise SystemExit("No verified NOAA wave cycle")
    d,c=selected
    noaa_validator.LOCATIONS.update(LOCATIONS)
    rc=noaa_validator.run(SimpleNamespace(date=d,cycle=c,locations=",".join(LOCATIONS),
          hours=a.hours,output=a.output,pause=a.pause,allow_many=True,keep_grib=False))
    out=Path(a.output)
    report=out/"validation_report.json"
    if not report.exists():raise SystemExit("Validation report not produced")
    rows=json.loads(report.read_text())["results"]
    summary={"cycle":f"{d} {c}Z", "coastal_targets":len(LOCATIONS),
             "forecast_hours_each":len(a.hours.split(",")),
             "passed":sum(x["status"]=="PASS" for x in rows),
             "failed":sum(x["status"]!="PASS" for x in rows),
             "swell_rows_with_values":sum(x.get("swell_specific_found",False) for x in rows),
             "locations":{name:{"passed":sum(x["location"]==name and x["status"]=="PASS" for x in rows),
                 "failed":sum(x["location"]==name and x["status"]!="PASS" for x in rows)}
                 for name in LOCATIONS}}
    (out/"panhandle_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))
    print("Nonpublishing diagnostic complete; partial coverage is not a workflow failure")
if __name__=="__main__":main()
