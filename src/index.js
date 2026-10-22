const ORIGIN = 'https://gr8polarbear2026.github.io/tidemoon-wave-data';
const LOCATIONS = new Set(['carrabelle', 'boston', 'charleston', 'sandiego', 'galveston']);
const MAX_CYCLE_AGE_MS = 18 * 60 * 60 * 1000;
const MAX_FUTURE_MS = 48 * 60 * 60 * 1000;
const json = (body, status=200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': status === 200 ? 'public, max-age=300' : 'no-store', 'access-control-allow-origin': '*' }
});
const validIso = value => typeof value === 'string' && Number.isFinite(Date.parse(value));
const finite = n => typeof n === 'number' && Number.isFinite(n);

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith('/api/waves')) return env.ASSETS.fetch(request);
    if (request.method !== 'GET') return json({status:'METHOD_NOT_ALLOWED'},405);
    const slug = url.pathname.match(/^\/api\/waves\/([a-z]+)\/?$/)?.[1] || url.searchParams.get('location');
    if (!LOCATIONS.has(slug)) return json({status:'UNSUPPORTED_LOCATION', supported:[...LOCATIONS]},404);
    try {
      const upstream = await fetch(`${ORIGIN}/${slug}.json`, {headers:{accept:'application/json'},redirect:'follow',cf:{cacheTtl:180,cacheEverything:true}});
      if (!upstream.ok) return json({status:'UPSTREAM_ERROR',code:upstream.status},502);
      const data = await upstream.json();
      if (data?.schema_version !== 1 || data.location_id !== slug || !validIso(data.model_cycle_utc) || !validIso(data.generated_at_utc) || !Array.isArray(data.forecast)) {
        return json({status:'DATA_ERROR',reason:'Invalid data schema'},502);
      }
      const now = Date.now();
      const cycle = Date.parse(data.model_cycle_utc);
      if (cycle > now + 15*60*1000 || now-cycle > MAX_CYCLE_AGE_MS) return json({status:'STALE',cycle_utc:data.model_cycle_utc,reason:'Forecast cycle outside allowed age'},503);
      const forecast = data.forecast.filter(f => validIso(f.valid_utc) && Date.parse(f.valid_utc) >= now-60*60*1000 && Date.parse(f.valid_utc) <= now+MAX_FUTURE_MS && finite(f.fields?.swh?.value) && f.fields.swh.value >= 0 && f.fields.swh.value <= 30 && finite(f.ocean_gridpoint?.lat) && finite(f.ocean_gridpoint?.lon)).sort((a,b)=> Date.parse(a.valid_utc)-Date.parse(b.valid_utc));
      if (!forecast.length) return json({status:'STALE',reason:'No usable forecast hours',cycle_utc:data.model_cycle_utc},503);
      return json({status:'CURRENT',source:data.source,location_id:slug,location_label:data.location_label,generated_at_utc:data.generated_at_utc,model_cycle_utc:data.model_cycle_utc,forecast:forecast.map(f=>({valid_utc:f.valid_utc,forecast_hour:f.forecast_hour,grid:f.ocean_gridpoint,wave_height_m:f.fields.swh.value,wave_period_s:f.fields.perpw?.value??null,wave_direction_deg:f.fields.dirpw?.value??null})),disclaimer:'Offshore numerical forecasts, not harbor observations or navigation advice.'});
    } catch {
      return json({status:'UPSTREAM_ERROR',reason:'Unable to retrieve or parse current NOAA publication'},502);
    }
  }
};
