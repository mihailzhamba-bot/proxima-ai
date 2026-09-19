import {runCollect} from '/work/services/collector/src/jobs/collect.ts';
import {FixtureTransport} from '/work/services/collector/src/wb/fixture-transport.ts';
let text='';for await(const chunk of process.stdin){text+=chunk.toString();if(text.length>1000000)throw Error('input bound');}
const req=JSON.parse(text);let runId=null;
const transport=new FixtureTransport({scripts:{'statistics.orders':[{status:200,body:JSON.stringify(req.orders),headers:{'content-type':'application/json'}}],'statistics.sales':[{status:200,body:JSON.stringify(req.sales),headers:{'content-type':'application/json'}}]}}).transport;
try{
 const result=await runCollect(req.args,{transport,env:req.env,repositoryRoot:'/work',clock:{now:()=>Date.parse('2026-08-20T10:00:00Z'),sleep:async()=>{}},onRunOpened:id=>{runId=id;}});
 console.log('CANDIDATE_RESULT '+JSON.stringify({ok:true,result,run_id:runId}));
}catch(e){console.log('CANDIDATE_RESULT '+JSON.stringify({ok:false,code:e?.code??'unexpected',run_id:runId}));}
