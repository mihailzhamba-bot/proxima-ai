import assert from 'node:assert/strict';
import {createHash,randomBytes} from 'node:crypto';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DEFAULT_FIXTURE_ROOT} from '/work/services/collector/src/wb/fixture-transport.ts';
const {Client}=createRequire('/work/services/collector/package.json')('pg');
assert.ok(process.env.PROXIMA_TEST_POSTGRES_DSN);assert.ok(process.env.PROXIMA_TEST_DSN_COLLECTOR);
const db=new Client({connectionString:process.env.PROXIMA_TEST_POSTGRES_DSN});await db.connect();
const sha=(s)=>createHash('sha256').update(s).digest('hex');
const canonical=(x)=>JSON.stringify(x,Object.keys(x).sort());
const orders=JSON.parse(await readFile(join(DEFAULT_FIXTURE_ROOT,'statistics/orders/sample.json'),'utf8')).slice(0,2);
const sales=JSON.parse(await readFile(join(DEFAULT_FIXTURE_ROOT,'statistics/sales/sample.json'),'utf8')).slice(0,1);
const dir=await mkdtemp(join(tmpdir(),'loop-trusted-warehouse-'));const uri=join(dir,'uri');const token=join(dir,'token');const raw=join(dir,'raw');
await writeFile(uri,process.env.PROXIMA_TEST_DSN_COLLECTOR+'\n',{mode:0o600});
await writeFile(token,Buffer.from('{"alg":"none"}').toString('base64url')+'.'+Buffer.from(JSON.stringify({s:(1<<30)|(1<<5),exp:2000000000})).toString('base64url')+'.fixture-signature\n',{mode:0o600});
let lastRun;const cases=[];
async function collect(o,s,t='fixture-warehouse-a'){
 await db.query('INSERT INTO tenants(tenant_id) VALUES($1) ON CONFLICT DO NOTHING',[t]);
 const nonce=randomBytes(20).toString('hex');
 const request={orders:o,sales:s,args:{tenantId:t,dateFrom:'2026-08-17',statisticsTokenFile:token},env:{COLLECTOR_DATABASE_URI_FILE:uri,PROXIMA_RAW_DIR:raw,PROXIMA_GIT_SHA:nonce}};
 const reply=await new Promise((resolve,reject)=>{
  const child=spawn('node',['--import','/work/node_modules/tsx/dist/loader.mjs','/acceptance/warehouse_candidate.mts'],{env:{PATH:process.env.PATH,LANG:'C.UTF-8',HOME:'/tmp'},stdio:['pipe','pipe','pipe']});
  let out='',err='';const timer=setTimeout(()=>{child.kill('SIGKILL');reject(Error('candidate timeout'));},15000);
  child.stdout.on('data',b=>{out+=b.toString();if(out.length>1000000){child.kill('SIGKILL');reject(Error('candidate output bound'));}});
  child.stderr.on('data',b=>{err+=b.toString();if(err.length>1000000){child.kill('SIGKILL');reject(Error('candidate stderr bound'));}});
  child.on('error',reject);child.on('close',code=>{clearTimeout(timer);try{assert.equal(code,0,'candidate exit');const lines=out.split('\n').filter(l=>l.startsWith('CANDIDATE_RESULT '));assert.equal(lines.length,1);resolve(JSON.parse(lines[0].slice(17)));}catch(e){reject(e);}});
  child.stdin.end(JSON.stringify(request));
 });
 assert.ok(reply && typeof reply==='object' && typeof reply.run_id==='string','candidate run identity');
 lastRun=reply.run_id;
 const ledger=(await db.query('SELECT git_sha FROM collector_runs WHERE run_id=$1',[lastRun])).rows[0];
 assert.equal(ledger?.git_sha,nonce,'observed fresh invocation');
 if(!reply.ok){const e=new Error('candidate rejected data');e.code=reply.code;throw e;}
 return reply.result;
}
async function snapshot(){return (await db.query("SELECT row_to_json(s) AS row FROM stg_wb_orders_obs s WHERE tenant_id='fixture-warehouse-a' ORDER BY srid,last_change_at")).rows;}
async function reject(o,s){
 await assert.rejects(()=>collect(o,s),e=>e?.code==='WB_SCHEMA_DRIFT');
 assert.equal((await db.query('SELECT status FROM collector_runs WHERE run_id=$1',[lastRun])).rows[0].status,'FAILED');
 for(const table of ['stg_wb_orders_obs','stg_wb_sales_obs','fact_cabinet_daily','fact_nm_daily']){
  assert.equal(Number((await db.query('SELECT count(*) n FROM '+table+' WHERE run_id=$1',[lastRun])).rows[0].n),0);
 }
 assert.equal(Number((await db.query('SELECT count(*) n FROM wb_raw_artifacts WHERE run_id=$1',[lastRun])).rows[0].n),2);
}
try{
 const first=await collect(orders,sales);
 // Force genuine legacy full-payload hashes independently of candidate converter.
 for(const row of orders)await db.query('UPDATE stg_wb_orders_obs SET canonical_sha256=$1 WHERE tenant_id=$2 AND srid=$3 AND run_id=$4',[sha(canonical(row)),'fixture-warehouse-a',row.srid,first.runId]);
 const before=await snapshot();assert.equal(before.length,orders.length,'seeded legacy rows exist');const renamed=orders.map(x=>({...x,warehouseName:'renamed-fixture-warehouse'}));
 for(let i=0;i<2;i++){
  const r=await collect(renamed,sales);assert.equal(r.orders.inserted,0);assert.equal(r.orders.skipped,orders.length);assert.deepEqual(await snapshot(),before);
  const evidence=(await db.query("SELECT content_sha256 FROM wb_raw_artifacts WHERE run_id=$1 AND endpoint_id='statistics.orders'",[r.runId])).rows[0];
  assert.equal(evidence.content_sha256,sha(JSON.stringify(renamed)));
  const bytes=await readFile(join(raw,'objects','sha256',evidence.content_sha256.slice(0,2),evidence.content_sha256));
  assert.equal(sha(bytes),evidence.content_sha256);
 }
 cases.push('legacy-hashes-and-payload-preserved','replay-keeps-raw-evidence');
 await reject([{...orders[0],srid:'fixture-new-before-sales-failure'},...renamed],[{...sales[0],totalPrice:Number(sales[0].totalPrice)+1}]);
 assert.deepEqual(await snapshot(),before);cases.push('sales-financial-conflict-rolls-back-new-orders');
 for(const change of [{warehouseName:null},{warehouseName:123},{totalPrice:Number(orders[0].totalPrice)+1},{finishedPrice:Number(orders[0].finishedPrice)+1},{isCancel:!orders[0].isCancel},{date:'2026-08-18T12:00:00'},{unrelated:'new'}]){
  await reject([{...renamed[0],...change},...renamed.slice(1)],sales);
 }
 const missing={...renamed[0]};delete missing.warehouseName;await reject([missing,...renamed.slice(1)],sales);
 cases.push('nonmetadata-and-invalid-warehouse-rejected');
 await reject(orders,[{...sales[0],warehouseName:'changed-sales-warehouse'}]);cases.push('sales-stays-strict');
 const bumped={...orders[0],lastChangeDate:'2026-08-19T12:00:00',totalPrice:Number(orders[0].totalPrice)+1};
 assert.equal((await collect([bumped,...orders.slice(1)],sales)).orders.inserted,1);cases.push('later-version-accepted');
 const other=await collect(orders.map(x=>({...x,totalPrice:Number(x.totalPrice)+2})),sales,'fixture-warehouse-b');
 assert.equal(other.orders.inserted,orders.length);
 const restricted=new Client({connectionString:process.env.PROXIMA_TEST_DSN_COLLECTOR});await restricted.connect();
 await restricted.query("SELECT set_config('proxima.tenant_id','fixture-warehouse-a',false)");
 assert.equal(Number((await restricted.query("SELECT count(*) n FROM stg_wb_orders_obs WHERE tenant_id='fixture-warehouse-b'")).rows[0].n),0);
 await restricted.end();cases.push('tenant-isolation');
 console.log('ACCEPTANCE_RESULT '+JSON.stringify({profile:'wb-warehouse-metadata',cases,passed:cases.length,skipped:0}));
}finally{await db.end();}
