import http from 'k6/http';
import crypto from 'k6/crypto';
import {sleep} from 'k6';
import {SharedArray} from 'k6/data';
import {Counter, Trend} from 'k6/metrics';

const BASE=__ENV.BASE||'http://127.0.0.1:8058';
if(!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(BASE))throw new Error('Only the isolated loopback fixture is permitted');
const USERS=Number(__ENV.USERS||1200),RAMP=Number(__ENV.RAMP||60),HOLD=Number(__ENV.HOLD||180),FINISH=Number(__ENV.FINISH||30);
const profiles=new SharedArray('real opening profiles',()=>JSON.parse(open(__ENV.MANIFEST)));
const errors=new Counter('application_errors'),completed=new Counter('users_completed'),started=new Counter('users_started');
const heartbeat=new Trend('heartbeat_ms',true),opening=new Trend('opening_http_ms',true);
const ranking=new Trend('ranking_ms',true);
export const options={
  scenarios:{players:{executor:'per-vu-iterations',vus:USERS,iterations:1,maxDuration:`${RAMP+HOLD+FINISH+90}s`}},
  discardResponseBodies:true,batchPerHost:2,batch:20,
  summaryTrendStats:['avg','min','med','max','p(95)','p(99)'],
  systemTags:['status','method','name','expected_response'],
  thresholds:{http_req_failed:['rate==0'],application_errors:['count==0'],users_completed:[`count==${USERS}`],users_started:[`count==${USERS}`],heartbeat_ms:['p(95)<500','p(99)<1500'],ranking_ms:['p(95)<500','p(99)<1500'],opening_http_ms:['p(95)<2500']},
};
const secret=new Uint8Array(crypto.hmac('sha256','WebAppData','1200:synthetic-isolated-capacity-test','binary')).buffer;
function signedData(index){
  const fields={auth_date:String(Math.floor(Date.now()/1000)),user:JSON.stringify({id:9000000000+index,first_name:`Teste ${index}`})};
  const check=Object.keys(fields).sort().map(k=>`${k}=${fields[k]}`).join('\n');
  fields.hash=crypto.hmac('sha256',secret,check,'hex');
  return Object.entries(fields).map(([k,v])=>`${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
}
export function setup(){errors.add(0);return {start:Date.now()+1000};}
function request(method,path,body,headers,kind){
  const response=http.request(method,BASE+path,body===null?null:JSON.stringify(body),{headers:{'Content-Type':'application/json',...headers},responseType:'text',timeout:'15s',tags:{name:kind}});
  if(response.status!==200){errors.add(1,{kind});return null;}
  return response;
}
export default function(data){
  const index=__VU-1,scheduled=data.start+index*RAMP*1000/USERS;
  sleep(Math.max(0,(scheduled-Date.now())/1000));
  const began=Date.now();
  const session=request('POST','/api/session',{init_data:signedData(index)},{},'session');
  if(!session)return;
  const auth={Authorization:'Bearer '+session.json('token')};
  const profile=profiles[index%profiles.length];
  const responses=http.batch(profile.paths.map(path=>({method:'GET',url:BASE+path,params:{responseType:'none',timeout:'15s',tags:{name:'opening-asset'}}})));
  for(const response of responses)if(response.status!==200)errors.add(1,{kind:'opening-asset'});
  opening.add(Date.now()-began);
  const firstRanking=Date.now();request('GET','/api/leaderboard',null,auth,'ranking');ranking.add(Date.now()-firstRanking);
  const run=request('POST','/api/runs',{game_slug:profile.slug},auth,'start');
  if(!run)return;
  const runId=run.json('run_id');started.add(1);
  const stop=data.start+(RAMP+HOLD)*1000;
  let next=Date.now()+8000+(index%20)*100;
  let beats=0;
  while(next<stop){
    sleep(Math.max(0,(next-Date.now())/1000));
    const before=Date.now();request('POST',`/api/runs/${runId}/heartbeat`,{active:true},auth,'heartbeat');heartbeat.add(Date.now()-before);
    if(++beats%3===0){const beganRanking=Date.now();request('GET','/api/leaderboard',null,auth,'ranking');ranking.add(Date.now()-beganRanking);}
    next+=10000;
  }
  sleep(Math.max(0,(stop+index*FINISH*1000/USERS-Date.now())/1000));
  const finish=request('POST',`/api/runs/${runId}/finish`,{outcome:'ended',score:index},auth,'finish');
  if(finish){const points=finish.json('points');if(points<1||points>10)errors.add(1,{kind:'points'});completed.add(1);}
  const finalRanking=request('GET','/api/leaderboard',null,auth,'persisted-ranking');
  if(finalRanking&&finish&&finalRanking.json('me.points')<finish.json('points'))errors.add(1,{kind:'persisted-points'});
}
export function handleSummary(data){
  data.capacity_scope={users:USERS,ramp_seconds:RAMP,hold_seconds:HOLD,finish_seconds:FINISH,profile:'cold-cache real asset profiles, signed identities sharing one IP, one live run each, authenticated ranking every 30s and persisted-point verification',physical_browsers:false,telegram_polling:false,public_internet_bandwidth:false};
  return {[__ENV.OUTPUT]:JSON.stringify(data,null,2)};
}
