// Panhandle-only coordinate lookup. Not wired into the production Worker yet.
// Returns null outside the validated offshore-grid radius. Never invents waves.
export const PANHANDLE_IDS = new Set([
  'pensacola','navarre','destin','panamacity','mexicobeach',
  'portsaintjoe','capesanblas','apalachicola','carrabellewest'
]);
export const PANHANDLE_RAW = 'https://raw.githubusercontent.com/gr8polarbear2026/tidemoon-wave-data/main/panhandle';
const validCoord = (a,b) => Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a)<=90&&Math.abs(b)<=180;
export function distanceKm(a,b,c,d) {
  const rad=Math.PI/180;
  const dl=(((d-b+540)%360)-180)*rad;
  const h=Math.sin((c-a)*rad/2)**2+Math.cos(a*rad)*Math.cos(c*rad)*Math.sin(dl/2)**2;
  return 12742*Math.asin(Math.min(1,Math.sqrt(h)));
}
export function locate(index,lat,lon,maxKm=90) {
  if (!validCoord(lat,lon)||!index||index.schema_version!==1||!Array.isArray(index.points)) return null;
  let best=null;
  for (const point of index.points) {
    const a=point.latitude,b=point.longitude;
    const id=point.validated_sites?.find(x=>PANHANDLE_IDS.has(x));
    if(!id || !validCoord(a,b))continue;
    const km=distanceKm(lat,lon,a,b);
    if (km <= maxKm && (!best || km<best.distance_km))
      best={location_id:id,grid:{lat:a,lon:b},distance_km:Math.round(km*10)/10};
  }
  return best;
}
const finite=n=>typeof n==='number'&&Number.isFinite(n);
const safe=(v,min,max)=>finite(v)&&v>=min&&v<=max?v:null;
export function convert(data,id,now=Date.now()) {
  if (data?.schema_version!==1 || data.location_id!==id ||
      !Array.isArray(data.forecast) || !Number.isFinite(Date.parse(data.model_cycle_utc)))
    return {status:'DATA_ERROR'};
  const cycle=Date.parse(data.model_cycle_utc);
  if(cycle>now+900000 || now-cycle>18*3600000)
    return {status:'STALE',model_cycle_utc:data.model_cycle_utc};
  const forecast=data.forecast.filter(f=>
    Number.isFinite(Date.parse(f.valid_utc))&&Date.parse(f.valid_utc)>=now-3600000 &&
    Date.parse(f.valid_utc)<=now+48*3600000 &&
    safe(f.fields?.swh?.value,0,30)!==null &&
    validCoord(f.ocean_gridpoint?.lat,f.ocean_gridpoint?.lon))
    .sort((a,b)=>Date.parse(a.valid_utc)-Date.parse(b.valid_utc));
  if(!forecast.length)return {status:'STALE',reason:'No current verified forecast times'};
  return {status:'CURRENT',source:data.source,location_id:id,location_label:data.location_label,
    generated_at_utc:data.generated_at_utc,model_cycle_utc:data.model_cycle_utc,
    forecast:forecast.map(f=>({
      valid_utc:f.valid_utc,forecast_hour:f.forecast_hour,grid:f.ocean_gridpoint,
      wave_height_m:f.fields.swh.value,
      wave_period_s:safe(f.fields.perpw?.value,0,40),
      wave_direction_deg:safe(f.fields.dirpw?.value,0,360),
      wind_wave_height_m:safe(f.fields.shww?.value,0,30),
      wind_wave_period_s:safe(f.fields.wvper?.value??f.fields.mpww?.value,0,40),
      wind_wave_direction_deg:safe(f.fields.wvdir?.value,0,360),
      swell_partitions:[1,2,3].map(n=>({
        partition:n,
        height_m:safe(f.fields['shts_partition_'+n]?.value??f.fields['swell_partition_'+n]?.value,0,30),
        period_s:safe(f.fields['mpts_partition_'+n]?.value??f.fields['swper_partition_'+n]?.value,0,40),
        direction_deg:safe(f.fields['swdir_partition_'+n]?.value,0,360)
      }))
    })), disclaimer:'Offshore numerical forecasts; not harbor observations or navigation advice.'};
}
export async function panhandleByCoordinates(lat,lon,fetchFn=fetch,now=Date.now()) {
  if(!validCoord(lat,lon))return {status:'INVALID_COORDINATES'};
  let index;
  try {
    const response=await fetchFn(PANHANDLE_RAW+'/validated_grid_index.json');
    if(!response.ok)return {status:'UPSTREAM_ERROR',code:response.status};
    index=await response.json();
  }catch{return {status:'UPSTREAM_ERROR'};}
  const match=locate(index,lat,lon);
  if(!match)return {status:'OUTSIDE_VERIFIED_PANHANDLE_COVERAGE'};
  try {
    const response=await fetchFn(PANHANDLE_RAW+'/'+match.location_id+'.json');
    if(!response.ok)return {status:'UPSTREAM_ERROR',code:response.status};
    const result=convert(await response.json(),match.location_id,now);
    return {...result,requested_coordinates:{lat,lon},selected_grid:match.grid,distance_km:match.distance_km};
  }catch{return {status:'UPSTREAM_ERROR'};}
}
