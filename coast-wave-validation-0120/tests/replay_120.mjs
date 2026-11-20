import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {convert as live,PANHANDLE_IDS} from '../src/panhandle_lookup.js';
const folder=process.argv[2];
const moduleText=await readFile(new URL('../src/panhandle_lookup.js',import.meta.url),'utf8');
const extendedText=moduleText.replace('PANHANDLE_LOOKAHEAD_MS=72*3600*1000','PANHANDLE_LOOKAHEAD_MS=120*3600*1000');
assert.notEqual(moduleText,extendedText);
const {convert,panhandleByCoordinates}=await import('data:text/javascript;base64,'+Buffer.from(extendedText).toString('base64'));
const get=async name=>JSON.parse(await readFile(join(folder,name),'utf8'));
const index=await get('validated_grid_index.json');
const byId=new Map(index.points.flatMap(p=>p.validated_sites.map(id=>[id,p])));
assert.equal(byId.size,11);
for(const id of PANHANDLE_IDS){
  const raw=await get(id+'.json'), cycle=Date.parse(raw.model_cycle_utc), now=cycle+8*3600000, p=byId.get(id);
  const x=convert(raw,id,now), y=live(raw,id,now);
  assert.equal(x.status,'CURRENT',id);
  assert.deepEqual(x.forecast.map(z=>z.forecast_hour),Array.from({length:114},(_,i)=>i+7),id);
  assert.deepEqual(x.forecast.slice(0,y.forecast.length),y.forecast,id);
  assert.equal(convert(raw,id,cycle+18*3600000+1).status,'STALE',id);
  const r=await panhandleByCoordinates(p.latitude,p.longitude,async u=>({ok:true,json:()=>get(new URL(u).pathname.split('/').pop())}),now);
  assert.equal(r.status,'CURRENT',id);
  assert.equal(r.forecast.at(-1).forecast_hour,120,id);
}
console.log('PASS: unchanged Worker contract plus stage-only 120h ceiling; all 11 routes and 72h wire parity; no network or deploy.');
