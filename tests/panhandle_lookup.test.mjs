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
