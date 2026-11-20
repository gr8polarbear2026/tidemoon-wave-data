import assert from 'node:assert/strict';
import test from 'node:test';
import {locate,convert,distanceKm,panhandleByCoordinates} from '../src/panhandle_lookup.js';

const index={schema_version:1,points:[
  {latitude:29.5,longitude:-85.3333,validated_sites:['capesanblas']},
  {latitude:30.1667,longitude:-87.3333,validated_sites:['pensacola']}
]};
const now=Date.parse('2026-10-28T04:00:00Z');
const sample={schema_version:1,location_id:'capesanblas',source:'NOAA GFS-Wave',
  location_label:'Cape San Blas',model_cycle_utc:'2026-10-28T00:00:00Z',
  generated_at_utc:'2026-10-28T02:30:00Z',forecast:[
    {forecast_hour:6,valid_utc:'2026-10-28T06:00:00Z',
      ocean_gridpoint:{lat:29.5,lon:-85.3333,distance_km:8.8},
      fields:{swh:{value:0.5},perpw:{value:5},dirpw:{value:80},
        shww:null,shts_partition_1:null,mpts_partition_1:null,swdir_partition_1:null}}
]};
test('Cape San Blas snaps to validated grid point',()=>{
  const result=locate(index,29.57,-85.29);
  assert.equal(result.location_id,'capesanblas');
  assert.ok(result.distance_km<15);
});
test('Out-of-region query is rejected, not routed to distant coastal waves',()=>{
  assert.equal(locate(index,39,-84),null);
});
test('Only validated coastal IDs are selectable',()=>{
  assert.equal(locate({schema_version:1,points:[{latitude:29.5,longitude:-85.3,validated_sites:['invented']}]},29.5,-85.3),null);
});
test('Current NOAA sample includes null, not invented swell partitions',()=>{
  const actual=convert(sample,'capesanblas',now);
  assert.equal(actual.status,'CURRENT');
  assert.equal(actual.forecast[0].wave_height_m,0.5);
  assert.equal(actual.forecast[0].swell_partitions[0].height_m,null);
});
test('Stale NOAA model cycle is rejected',()=>{
  assert.equal(convert(sample,'capesanblas',now+24*3600000).status,'STALE');
});
test('Geographic distance across dateline remains small',()=>{
  assert.ok(distanceKm(20,179.9,20,-179.9)<30);
});
test('Coordinate API selects proper JSON and returns forecast',async()=>{
  const responses=[index,sample];let i=0;
  const stub=async()=>({ok:true,json:async()=>responses[i++]});
  const result=await panhandleByCoordinates(29.57,-85.29,stub,now);
  assert.equal(result.status,'CURRENT');
  assert.equal(result.location_id,'capesanblas');
});

test('Eastern extension never substitutes distant Carrabelle cell',()=>{
  const old={schema_version:1,points:[{latitude:29.6667,longitude:-84.6666,validated_sites:['carrabellewest']}]};
  assert.equal(locate(old,30.0783,-84.1783),null);
});
test('St Marks entrance selects nearby verified eastern cell',()=>{
  const east={schema_version:1,points:[{latitude:30,longitude:-84.1666,validated_sites:['stmarks']}]};
  const found=locate(east,30.0783,-84.1783);
  assert.equal(found.location_id,'stmarks');assert.ok(found.distance_km<10);
});
test('API reports request-to-cell distance consistently in every row',async()=>{
 const responses=[index,sample];let i=0;
 const r=await panhandleByCoordinates(29.57,-85.29,async()=>({ok:true,json:async()=>responses[i++]}),now);
 assert.equal(r.forecast[0].grid.distance_km,r.distance_km);
});
test('Reject mismatched index or mixed forecast grid cells',async()=>{
 const changed=structuredClone(sample);changed.forecast[0].ocean_gridpoint.lon=-85.1;
 const responses=[index,changed];let i=0;
 const r=await panhandleByCoordinates(29.57,-85.29,async()=>({ok:true,json:async()=>responses[i++]}),now);
 assert.equal(r.status,'DATA_ERROR');
});
test('Past-only forecast rows do not count as current forecast availability',()=>{
 const old=structuredClone(sample);old.forecast[0].valid_utc='2026-10-28T03:30:00Z';
 assert.equal(convert(old,'capesanblas',now).status,'STALE');
});

test('Expanded Panhandle route retains exact supplied timestamps within its boundary only',()=>{
  const h=3600000;
  const offsets=[-90*60000-1,-90*60000,-60*60000,0,48*h+1,72*h,72*h+1];
  const all=structuredClone(sample);
  all.forecast=offsets.slice().reverse().map(offset=>({
    ...sample.forecast[0],valid_utc:new Date(now+offset).toISOString()
  }));
  const r=convert(all,'capesanblas',now);
  assert.equal(r.status,'CURRENT');
  assert.deepEqual(r.forecast.map(row=>Date.parse(row.valid_utc)-now),offsets.slice(1,-1));
  assert.equal(r.forecast.at(-1).wave_height_m,0.5);
  assert.equal(r.forecast.at(-1).swell_partitions[0].height_m,null);
});

test('Coordinate route does not fabricate hours or resolve an invalid late sample',async()=>{
  const expanded=structuredClone(sample);
  const late=structuredClone(expanded.forecast[0]);
  late.valid_utc=new Date(now+60*3600000).toISOString();
  late.forecast_hour=64;
  late.fields.swh.value=0.9;
  expanded.forecast.push(late);
  const responses=[index,expanded];let i=0;
  const r=await panhandleByCoordinates(29.57,-85.29,async()=>({ok:true,json:async()=>responses[i++]}),now);
  assert.equal(r.status,'CURRENT');
  assert.deepEqual(r.forecast.map(({valid_utc,wave_height_m})=>[valid_utc,wave_height_m]),
    [[sample.forecast[0].valid_utc,0.5],[late.valid_utc,0.9]]);
  late.ocean_gridpoint.lon+=1;
  i=0;
  const invalid=await panhandleByCoordinates(29.57,-85.29,async()=>({ok:true,json:async()=>responses[i++]}),now);
  assert.equal(invalid.status,'DATA_ERROR');
});
