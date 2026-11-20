// Replay isolated publisher output through the actual Worker coordinate contract.
// No HTTP or deployment. Pass the staging directory and an output directory.
import assert from 'node:assert/strict';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {panhandleByCoordinates,PANHANDLE_IDS,convert} from '../src/panhandle_lookup.js';

const [from,to]=process.argv.slice(2);
if(!from||!to)throw new Error('Usage: node tests/replay_staged_contract.mjs STAGED_DIR RESPONSE_OUTPUT_DIR');
const get=async (f)=>JSON.parse(await readFile(join(from,f),'utf8'));
const index=await get('validated_grid_index.json');
const pointById=new Map(index.points.flatMap(p=>p.validated_sites.map(id=>[id,p])));
await mkdir(to,{recursive:true});
for(const id of PANHANDLE_IDS){
  const raw=await get(id+'.json');
  const cycle=Date.parse(raw.model_cycle_utc);
  const now=cycle+8*3600000;
  const p=pointById.get(id);
  assert.ok(p,id+' must appear in validated coordinate index');
  const full=convert(raw,id,now);
  assert.equal(full.status,'CURRENT',id);
  assert.equal(full.forecast.length,66,id);
  assert.equal(full.forecast[0].forecast_hour,7,id);
  assert.equal(full.forecast.at(-1).forecast_hour,72,id);
  for(let i=1;i<full.forecast.length;i++)assert.equal(Date.parse(full.forecast[i].valid_utc)-Date.parse(full.forecast[i-1].valid_utc),3600000,id);
  // A shared grid cell may legitimately select the first validated station.
  const r=await panhandleByCoordinates(p.latitude,p.longitude,async u=>({ok:true,json:()=>get(new URL(u).pathname.split('/').pop())}),now);
  assert.equal(r.status,'CURRENT',id);
  assert.equal(r.forecast.length,66,id);
  assert.equal(r.forecast.at(-1).forecast_hour,72,id);
  await writeFile(join(to,id+'.json'),JSON.stringify(full)+'\n');
}
console.log('PASS: all eleven staged locations through Worker converter and coordinate route; offline replay only.');
