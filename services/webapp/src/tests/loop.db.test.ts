import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { randomUUID } from "node:crypto";
import { Pool } from "pg";
import { createQueueService, type Acceptance } from "@/lib/loop/service";
import { readPilotContext } from "@/lib/loop/context";
import { lastFullMoscowDay } from "@/lib/loop/calendar";
import type { SignalV1 } from "@/lib/contracts/signal";
const dsn = process.env.PROXIMA_TEST_POSTGRES_DSN;
const suite = dsn ? describe : describe.skip;
suite("LOOP PostgreSQL roles and transactions", () => {
  const admin = new Pool({ connectionString: dsn });
  const tenant = `loop-${randomUUID().slice(0, 8)}`;
  const owner = { tenantId: tenant, userId: `${tenant}-owner` };
  const employee = { tenantId: tenant, userId: `${tenant}-employee` };
  const other = { tenantId: tenant, userId: `${tenant}-other` };
  const seed = randomUUID(), collect = randomUUID(), brief = randomUUID();
  const day = lastFullMoscowDay(new Date());
  const signal: SignalV1 = { schema_version:1, scenario_code:"SCN-001", signal_id:`${tenant}-signal`, snapshot_id:"snapshot-a", tenant_id:tenant, created_at:new Date().toISOString(), trust_marking:"unreleased", source_refs:["fixture-source"], rub_assessment:{value_rub:"30.00",method:"revenue"}, detection_data:{ level:{value:"sku",is_unknown:false},nm_id:{value:12345,is_unknown:false},orders_actual:{value:7,is_unknown:false},orders_norm_median:{value:"10.00",is_unknown:false} } };
  const now = new Date();
  const queue = createQueueService({ async connect() {
    const db = await admin.connect(); await db.query("SET ROLE proxima_loop_writer");
    return { query:db.query.bind(db), release(){ db.release(); } };
  } }, () => now);
  async function sql(text: string, args: unknown[] = []) { const c = await admin.connect(); try { await c.query("RESET ROLE"); return await c.query(text,args); } finally { c.release(); } }
  const command = (overrides: Partial<Acceptance> = {}): Acceptance => ({ idempotencyKey:randomUUID(),signalId:signal.signal_id,snapshotId:signal.snapshot_id,assigneeId:employee.userId,action:"Проверить карточку",dueAt:new Date(Date.now()+86400000).toISOString(),expectedOutcome:"Заказы достигли цели",expected:{horizon_days:1,metrics:[{name:"orders",value:"9.00",unit:"count",source_ref:"fixture-owner-target:2026-09-13"}]},...overrides });
  beforeAll(async () => {
    await sql("INSERT INTO tenants (tenant_id) VALUES ($1)",[tenant]);
    for (const p of [owner,employee,other]) await sql("INSERT INTO webapp_auth.\"user\" (id,name,email) VALUES ($1,$1,$2)",[p.userId,p.userId+"@fixture.invalid"]);
    await sql("INSERT INTO workflow_runs (tenant_id,run_id,actor_id,command,idempotency_key,request_hash,state) VALUES ($1,$2,$3,'provision','seed',$4,'succeeded')",[tenant,seed,owner.userId,"0".repeat(64)]);
    for (const p of [owner,employee,other]) await sql("INSERT INTO cabinet_memberships (tenant_id,user_id,role,run_id) VALUES ($1,$2,$3,$4)",[tenant,p.userId,p===owner?"owner":"employee",seed]);
    for (const [id,kind] of [[collect,"collect"],[brief,"norm"]]) await sql("INSERT INTO collector_runs (run_id,tenant_id,kind,status,started_at,finished_at) VALUES ($1,$2,$3,'SUCCEEDED',now(),now())",[id,tenant,kind]);
    await sql("INSERT INTO fact_cabinet_daily (tenant_id,calendar_day,run_id,orders_count,cancelled_count,sales_count,returns_count,revenue_rub,forpay_rub,evidence_sha256) VALUES ($1,$2,$3,7,0,7,0,70,70,$4)",[tenant,day,collect,["a".repeat(64)]]);
    await sql("INSERT INTO fact_nm_daily (tenant_id,calendar_day,nm_id,run_id,orders_count,cancelled_count,sales_count,returns_count,revenue_rub,forpay_rub,evidence_sha256) VALUES ($1,$2,12345,$3,10,0,10,0,100,100,$4)",[tenant,day,collect,["a".repeat(64)]]);
    await sql("INSERT INTO brief_daily (tenant_id,brief_day,run_id,status,payload) VALUES ($1,$2,$3,'ok',$4)",[tenant,day,brief,{signals:[signal],source_refs:["fixture-source"],actual:{orders:7,revenue:"70.00"}}]);
  });
  afterAll(async () => {
    for (const table of ["task_observations","task_events","loop_tasks","decision_records","cabinet_memberships","workflow_runs"]) await sql(`DELETE FROM ${table} WHERE tenant_id=$1`,[tenant]);
    await sql("DELETE FROM collector_runs WHERE run_id=ANY($1::uuid[])",[[collect,brief]]);
    await sql("DELETE FROM webapp_auth.\"user\" WHERE id=ANY($1::text[])",[[owner.userId,employee.userId,other.userId]]);
    await sql("DELETE FROM tenants WHERE tenant_id=$1",[tenant]); await admin.end();
  });
  let taskId: string;
  it("binds session membership, atomic decision/task, two retries including a new key", async () => {
    await expect(queue.list({...employee,tenantId:"foreign-tenant"})).rejects.toMatchObject({status:403});
    await expect(queue.accept(employee,command())).rejects.toMatchObject({status:403});
    const body=command(); const results=await Promise.all([queue.accept(owner,body),queue.accept(owner,body)]);
    expect(results[0]).toEqual(results[1]); taskId=results[0].taskId;
    expect(await queue.accept(owner,{...body,idempotencyKey:randomUUID()})).toEqual(results[0]);
    expect((await sql("SELECT count(*) FROM decision_records WHERE tenant_id=$1",[tenant])).rows[0].count).toBe("1");
    expect((await queue.list(other)).tasks).toEqual([]);
    expect((await queue.list(employee)).tasks.map(t=>t.task_id)).toEqual([taskId]);
    await expect(queue.accept(owner,{...body,action:"Другая команда"})).rejects.toMatchObject({status:409});
  });
  it("uses a dedicated read-only service role for live cabinet context",async()=>{
    const contextPool={async connect(){const c=await admin.connect();await c.query("SET ROLE proxima_loop_context");return {query:c.query.bind(c),release(){c.release();}};}};
    const context=await readPilotContext(contextPool,tenant);
    expect(context.brief?.payload.signals[0].signal_id).toBe(signal.signal_id);
    expect(context.queue.tasks[0].expected.metrics[0].value).toBe("9.00");
    expect(context.employees.map(e=>e.user_id)).toContain(employee.userId);
    expect((await readPilotContext(contextPool,"foreign-tenant")).queue.tasks).toEqual([]);
    const c=await contextPool.connect();
    try {await expect(c.query("INSERT INTO workflow_runs DEFAULT VALUES")).rejects.toMatchObject({code:"42501"});}
    finally {c.release();}
  });
  it("refuses revoked membership and another employee's event without data leak", async () => {
    await expect(queue.event(other,taskId,"completed","evidence",randomUUID())).rejects.toMatchObject({status:404});
    await sql("UPDATE cabinet_memberships SET active=false WHERE tenant_id=$1 AND user_id=$2",[tenant,employee.userId]);
    await expect(queue.list(employee)).rejects.toMatchObject({status:403});
    await sql("UPDATE cabinet_memberships SET active=true WHERE tenant_id=$1 AND user_id=$2",[tenant,employee.userId]);
  });
  it("blocks, completes idempotently, keeps effect pending, then measures the same SKU", async () => {
    await queue.event(employee,taskId,"blocked","Ждём источник",randomUUID());
    expect((await queue.list(employee)).tasks[0].status).toBe("blocked");
    const id=randomUUID(); const first=await queue.event(employee,taskId,"completed","fixture evidence",id);
    expect(await queue.event(employee,taskId,"completed","fixture evidence",id)).toEqual(first);
    await queue.observe(owner,taskId,randomUUID());
    expect((await queue.list(owner)).tasks[0].observation?.status).toBe("pending");
    // The verdict must measure exactly the horizon end day: shift completed_at so
    // completed_at + horizon lands inside `day`, the day the fresh brief covers.
    await sql("UPDATE task_events SET created_at=(($1::date - 1)::timestamptz + interval '00:30') WHERE tenant_id=$2 AND kind='completed'",[day,tenant]);
    await queue.observe(owner,taskId,randomUUID());
    expect((await queue.list(owner)).tasks[0].observation?.reason).toContain("Цель по исходному SKU достигнута");
    const d=await sql("SELECT payload FROM decision_records WHERE tenant_id=$1",[tenant]); expect(d.rows[0].payload.actual).toBeNull();
    await queue.event(owner,taskId,"cancelled","Отмена",randomUUID());
    await expect(queue.event(employee,taskId,"completed","late",randomUUID())).rejects.toMatchObject({status:409});
    await expect(queue.observe(owner,taskId,randomUUID())).rejects.toMatchObject({status:409});
  });
  it("rejects changed snapshots and stale sources, rolls back all command rows", async () => {
    const next={...signal,signal_id:signal.signal_id+"-new"};
    await sql("UPDATE brief_daily SET payload=jsonb_set(payload,'{signals}',$2) WHERE tenant_id=$1",[tenant,JSON.stringify([next])]);
    const before=(await sql("SELECT count(*) FROM workflow_runs WHERE tenant_id=$1",[tenant])).rows[0].count;
    await expect(queue.accept(owner,command({signalId:next.signal_id,snapshotId:"old"}))).rejects.toMatchObject({status:409});
    expect((await sql("SELECT count(*) FROM workflow_runs WHERE tenant_id=$1",[tenant])).rows[0].count).toBe(before);
    await sql("UPDATE collector_runs SET finished_at=now()-interval '2 days' WHERE run_id=$1",[collect]);
    await expect(queue.accept(owner,command({signalId:next.signal_id}))).rejects.toMatchObject({status:409});
  });
  it("keeps old active tasks ahead of paginated history and exposes approved targets", async () => {
    for (let i=0;i<55;i++) {
      const run=randomUUID(),decision=randomUUID(),id=randomUUID();
      await sql("INSERT INTO workflow_runs (tenant_id,run_id,actor_id,command,idempotency_key,request_hash,state) VALUES ($1,$2,$3,'fixture',$4,$5,'succeeded')",[tenant,run,owner.userId,`page-${i}`,"0".repeat(64)]);
      await sql("INSERT INTO decision_records (tenant_id,decision_id,run_id,signal_id,actor_id,source_brief_run_id,signal_snapshot,diagnosis_snapshot,payload) VALUES ($1,$2,$3,$4,$5,$6,$7,'{}',$8)",[tenant,decision,run,`page-signal-${i}`,owner.userId,brief,signal,{expected:command().expected}]);
      await sql("INSERT INTO loop_tasks (tenant_id,task_id,decision_id,run_id,assignee_id,action,due_at,expected_outcome,horizon_days,created_at) VALUES ($1,$2,$3,$4,$5,$6,now(),'Fixture',1,$7)",[tenant,id,decision,run,employee.userId,`Page ${i}`,i===0?"2020-01-01T00:00:00Z":new Date().toISOString()]);
      if(i>0) await sql("INSERT INTO task_events (tenant_id,event_id,task_id,run_id,actor_id,kind,evidence) VALUES ($1,$2,$3,$4,$5,'completed','fixture')",[tenant,randomUUID(),id,run,employee.userId]);
    }
    const first=await queue.list(employee);
    expect(first.tasks[0].action).toBe("Page 0");
    expect(first.tasks[0].expected_metrics[0]).toEqual(command().expected.metrics[0]);
    expect(first.nextCursor).not.toBeNull();
    const second=await queue.list(employee,{cursor:first.nextCursor!});
    expect(second.tasks.length).toBeGreaterThan(0);
    expect(second.tasks.some(t=>first.tasks.some(f=>f.task_id===t.task_id))).toBe(false);
    expect((await queue.list(employee,{filter:"active"})).tasks.map(t=>t.action)).toEqual(["Page 0"]);
  });
  it("enforces domain immutability and RLS under runtime role; source deletion orphans", async () => {
    const c=await admin.connect();
    try { await c.query("SET ROLE proxima_loop_writer"); await c.query("SELECT set_config('proxima.tenant_id','foreign-tenant',false)"); expect((await c.query("SELECT * FROM loop_tasks")).rows).toEqual([]); await expect(c.query("UPDATE decision_records SET payload='{}'")).rejects.toMatchObject({code:"42501"}); await expect(c.query("UPDATE cabinet_memberships SET role='owner'")).rejects.toMatchObject({code:"42501"}); }
    finally { c.release(); }
    await sql("DELETE FROM collector_runs WHERE run_id=$1",[brief]);
    expect((await queue.list(owner)).tasks.every(t=>t.orphaned)).toBe(true);
  });
  it("emits ISO task timestamps and rejects re-accepting a cancelled signal", async () => {
    const listed=(await queue.list(owner,{filter:"history",limit:100})).tasks.find(t=>t.task_id===taskId);
    expect(listed).toBeDefined();
    expect(listed!.due_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(Number.isNaN(Date.parse(listed!.due_at))).toBe(false);
    expect(Number.isNaN(Date.parse(listed!.created_at))).toBe(false);
    await expect(queue.accept(owner,command({idempotencyKey:randomUUID()}))).rejects.toMatchObject({status:409});
  });
});
