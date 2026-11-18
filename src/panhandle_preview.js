// Deployment entrypoint for the existing isolated Panhandle preview service.
import {panhandleByCoordinates} from './panhandle_lookup.js';
const send=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{
  'content-type':'application/json','cache-control':status===200?'public, max-age=120':'no-store','access-control-allow-origin':'*'}});
export default {async fetch(request){
  const url=new URL(request.url);
  if(url.pathname==='/health')return send({status:'PREVIEW',production:false,coverage:'Florida Panhandle through St. Marks',revision:'eastern-20261118'});
  if(url.pathname!=='/api/waves/panhandle/coordinates')return send({status:'NOT_FOUND'},404);
  if(request.method!=='GET')return send({status:'METHOD_NOT_ALLOWED'},405);
  if(!url.searchParams.get('lat')?.trim()||!url.searchParams.get('lon')?.trim())return send({status:'INVALID_COORDINATES'},400);
  const lat=Number(url.searchParams.get('lat')),lon=Number(url.searchParams.get('lon'));
  const fetchCached=(u)=>fetch(u,{cf:{cacheTtl:180,cacheEverything:true}});
  const result=await panhandleByCoordinates(lat,lon,fetchCached);
  const code={CURRENT:200,INVALID_COORDINATES:400,OUTSIDE_VERIFIED_PANHANDLE_COVERAGE:404,STALE:503}[result.status]??502;
  return send(result,code);
}};
