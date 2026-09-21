import { createHash, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { Pool, type PoolClient } from "pg";
import type { BriefV1 } from "@/lib/contracts/brief";
import type { DecisionRecordV1 } from "@/lib/contracts/decision-record";
import { diagnoseSignal } from "./diagnosis";
import { moscowDayAt } from "./calendar";

export class QueueError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export type Principal = { userId: string; tenantId: string };
export type Member = Principal & { role: "owner" | "employee" };
type Db = Pick<PoolClient, "query">;
export type QueuePool = { connect(): Promise<Db & { release(): void }> };
export type Acceptance = {
  idempotencyKey: string; signalId: string; snapshotId: string; assigneeId: string; action: string;
  dueAt: string; expectedOutcome: string; expected: DecisionRecordV1["expected"];
};
export type TaskItem = {
  task_id: string; assignee_id: string; assignee_name: string; action: string; due_at: string;
  expected_metrics: DecisionRecordV1["expected"]["metrics"];
  expected_outcome: string; horizon_days: number; created_at: string;
  status: "open" | "blocked" | "completed" | "cancelled"; orphaned: boolean;
  blocker: string | null; evidence: string | null; completed_at: string | null;
  observation: { status: string; reason: string; created_at: string; snapshot: { evaluation_day: string; measurements: { name: string; expected: string; actual: string; unit: string; source_refs: string[] }[] } | null } | null;
};
export const taskSelect = `SELECT t.task_id, t.assignee_id, u.name AS assignee_name, t.action, to_json(t.due_at)#>>'{}' AS due_at, t.expected_outcome,
 d.payload->'expected'->'metrics' AS expected_metrics, t.horizon_days, to_json(t.created_at)#>>'{}' AS created_at, d.source_brief_run_id IS NULL AS orphaned,
 COALESCE((SELECT e.kind FROM task_events e WHERE e.tenant_id=t.tenant_id AND e.task_id=t.task_id
 ORDER BY (e.kind='cancelled') DESC, (e.kind='completed') DESC, e.created_at DESC LIMIT 1), 'open') AS status,
 (SELECT e.evidence FROM task_events e WHERE e.tenant_id=t.tenant_id AND e.task_id=t.task_id
 AND e.kind='completed') AS evidence,
 (SELECT e.evidence FROM task_events e WHERE e.tenant_id=t.tenant_id AND e.task_id=t.task_id AND e.kind='blocked') AS blocker,
 (SELECT to_json(e.created_at)#>>'{}' FROM task_events e WHERE e.tenant_id=t.tenant_id AND e.task_id=t.task_id
 AND e.kind='completed') AS completed_at,
 (SELECT jsonb_build_object('status', o.status, 'reason', o.reason, 'created_at', o.created_at, 'snapshot', o.snapshot)
 FROM task_observations o WHERE o.tenant_id=t.tenant_id AND o.task_id=t.task_id
 ORDER BY o.created_at DESC, o.observation_id DESC LIMIT 1) AS observation
 FROM loop_tasks t JOIN decision_records d ON d.tenant_id=t.tenant_id AND d.decision_id=t.decision_id JOIN webapp_auth.\"user\" u ON u.id=t.assignee_id`;

function nonempty(value: unknown, max = 2000): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= max;
}
function key(value: unknown): asserts value is string {
  if (!nonempty(value, 120) || !/^[a-zA-Z0-9._:-]+$/.test(value)) throw new QueueError(400, "Неверный ключ команды.");
}
export function validateAcceptance(value: unknown): Acceptance {
  const v = value as Acceptance | null;
  if (!v || typeof v !== "object") throw new QueueError(400, "Не заполнены данные решения.");
  key(v.idempotencyKey);
  if (![v.signalId, v.snapshotId, v.assigneeId, v.action, v.expectedOutcome].every((x) => nonempty(x))) throw new QueueError(400, "Заполните действие, исполнителя и ожидаемый результат.");
  if (!nonempty(v.dueAt, 40) || !/T.*(?:Z|[+-]\d\d:\d\d)$/.test(v.dueAt) || !Number.isFinite(Date.parse(v.dueAt))) throw new QueueError(400, "Укажите срок с часовым поясом.");
  const e = v.expected;
  if (!e || !Number.isInteger(e.horizon_days) || e.horizon_days < 1 || e.horizon_days > 365 || !Array.isArray(e.metrics) || e.metrics.length < 1 || e.metrics.length > 10 || e.metrics.some(m => !m || !nonempty(m.name, 100) || !nonempty(m.unit, 30) || !nonempty(m.source_ref, 500) || typeof m.value !== "string" || !/^-?\d{1,12}\.\d{2}$/.test(m.value))) {
    throw new QueueError(400, "Укажите измеримый результат, источник цели и срок наблюдения.");
  }
  // Stable, allowlisted shape: extra caller fields cannot become persisted identity.
  return { idempotencyKey: v.idempotencyKey, signalId: v.signalId, snapshotId: v.snapshotId, assigneeId: v.assigneeId, action: v.action.trim(), dueAt: new Date(v.dueAt).toISOString(), expectedOutcome: v.expectedOutcome.trim(), expected: { horizon_days: e.horizon_days, metrics: e.metrics.map(m => ({ name: m.name, value: m.value, unit: m.unit, source_ref: m.source_ref })) as DecisionRecordV1["expected"]["metrics"] } };
}
function decimalCents(value: string): bigint {
  if (!/^-?\d+\.\d{2}$/.test(value)) throw new QueueError(409, "Неверный формат измерения.");
  return BigInt(value.replace(".", ""));
}
export function observationReadiness(task: Pick<TaskItem, "status" | "completed_at" | "horizon_days" | "orphaned">, now: Date): string | null {
  if (task.orphaned) return "Исходный прогон удалён. Snapshot сохранён, сравнение не подтверждено.";
  if (task.status !== "completed" || !task.completed_at) return "Выполнение ещё не подтверждено.";
  const until = Date.parse(task.completed_at) + task.horizon_days * 86_400_000;
  if (now.getTime() < until) return "Срок наблюдения после выполнения ещё не прошёл.";
  return null;
}

export type QueuePage = { filter?: "all" | "active" | "history"; cursor?: string; limit?: number };
export function decodeQueuePage(page: QueuePage = {}) {
  const filter = page.filter ?? "all", limit = page.limit ?? 50;
  if (!["all", "active", "history"].includes(filter) || !Number.isInteger(limit) || limit < 1 || limit > 100) throw new QueueError(400, "Неверная страница очереди.");
  let cursor: { active: boolean; created: string; id: string } | null = null;
  if (page.cursor) {
    try {
      cursor = JSON.parse(Buffer.from(page.cursor, "base64url").toString());
      if (!cursor || typeof cursor.active !== "boolean" || typeof cursor.created !== "string" || !Number.isFinite(Date.parse(cursor.created)) || !/^[0-9a-f-]{36}$/i.test(cursor.id)) throw new Error();
    } catch { throw new QueueError(400, "Неверная страница очереди."); }
  }
  return { filter, limit, cursor };
}
export function createQueueService(pool: QueuePool, clock = () => new Date()) {
  async function member(db: Db, p: Principal): Promise<Member> {
    if (!nonempty(p.userId) || !/^[a-z0-9][a-z0-9_-]{2,63}$/.test(p.tenantId)) throw new QueueError(403, "Нет доступа к кабинету.");
    const r = await db.query("SELECT role FROM cabinet_memberships WHERE tenant_id=$1 AND user_id=$2 AND active=true", [p.tenantId, p.userId]);
    if (!r.rows[0]) throw new QueueError(403, "Нет доступа к кабинету.");
    return { ...p, role: r.rows[0].role };
  }
  async function transaction<T>(p: Principal, work: (db: Db, m: Member) => Promise<T>): Promise<T> {
    const db = await pool.connect();
    try {
      await db.query("BEGIN");
      await db.query("SELECT set_config('proxima.tenant_id', $1, true)", [p.tenantId]);
      const m = await member(db, p);
      const result = await work(db, m);
      await db.query("COMMIT");
      return result;
    } catch (e) { await db.query("ROLLBACK"); throw e; }
    finally { db.release(); }
  }
  async function lock(db: Db, name: string) { await db.query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", [name]); }
  async function command(db: Db, p: Principal, id: string, name: string, payload: unknown) {
    key(id);
    await lock(db, `${p.tenantId}:${p.userId}:${id}`);
    const hash = createHash("sha256").update(JSON.stringify({ name, payload })).digest("hex");
    const r = await db.query("SELECT run_id, request_hash, result FROM workflow_runs WHERE tenant_id=$1 AND actor_id=$2 AND idempotency_key=$3", [p.tenantId, p.userId, id]);
    if (r.rows[0]) {
      if (r.rows[0].request_hash !== hash) throw new QueueError(409, "Этот ключ уже использован для другой команды.");
      return { id: r.rows[0].run_id as string, replay: true, result: r.rows[0].result as { taskId: string; runId: string } };
    }
    const run = randomUUID();
    await db.query("INSERT INTO workflow_runs (tenant_id,run_id,actor_id,command,idempotency_key,request_hash,state) VALUES ($1,$2,$3,$4,$5,$6,'running')", [p.tenantId, run, p.userId, name, id, hash]);
    return { id: run, replay: false, result: null };
  }
  async function finish(db: Db, p: Principal, run: string, result: { taskId: string; runId: string }) { await db.query("UPDATE workflow_runs SET state='succeeded', result=$3, finished_at=now() WHERE tenant_id=$1 AND run_id=$2 AND state='running'", [p.tenantId, run, result]); }
  async function task(db: Db, m: Member, id: string): Promise<TaskItem> {
    if (!/^[0-9a-f-]{36}$/i.test(id)) throw new QueueError(404, "Задача недоступна.");
    const r = await db.query(`${taskSelect} WHERE t.tenant_id=$1 AND t.task_id=$2 AND ($3='owner' OR t.assignee_id=$4)`, [m.tenantId, id, m.role, m.userId]);
    if (!r.rows[0]) throw new QueueError(404, "Задача недоступна.");
    return r.rows[0] as TaskItem;
  }
  async function freshBrief(db: Db, p: Principal) {
    const r = await db.query(`SELECT b.run_id, b.brief_day::text, b.payload FROM brief_current b
      JOIN data_status_current s ON s.tenant_id=b.tenant_id
      WHERE b.tenant_id=$1 AND b.status='ok' AND s.stale IS FALSE AND b.brief_day=s.last_full_day`, [p.tenantId]);
    const row = r.rows[0] as { run_id: string; brief_day: string; payload: BriefV1 } | undefined;
    if (!row || !row.payload.source_refs?.length) throw new QueueError(409, "Свежая сводка с источниками недоступна. Дождитесь полного сбора.");
    return row;
  }
  return {
    membership(p: Principal) { return transaction(p, async (_db, m) => m); },
    list(p: Principal, page: QueuePage = {}) { return transaction(p, async (db, m) => {
      const { filter, limit, cursor } = decodeQueuePage(page);
      const r = await db.query(`SELECT * FROM (${taskSelect} WHERE t.tenant_id=$1 AND ($2='owner' OR t.assignee_id=$3)) q
        WHERE ($4='all' OR ($4='active' AND status IN ('open','blocked')) OR ($4='history' AND status IN ('completed','cancelled')))
        AND ($5::boolean IS NULL OR ((status IN ('open','blocked')), created_at::timestamptz, task_id) < ($5::boolean,$6::timestamptz,$7::uuid))
        ORDER BY (status IN ('open','blocked')) DESC, created_at::timestamptz DESC, task_id DESC LIMIT $8`, [p.tenantId, m.role, p.userId, filter, cursor?.active ?? null, cursor?.created ?? null, cursor?.id ?? null, limit + 1]);
      const tasks = r.rows.slice(0, limit) as TaskItem[];
      const last = tasks.at(-1);
      const nextCursor = r.rows.length > limit && last ? Buffer.from(JSON.stringify({ active: ["open", "blocked"].includes(last.status), created: last.created_at, id: last.task_id })).toString("base64url") : null;
      const people = m.role === "owner" ? (await db.query('SELECT m.user_id,u.name FROM cabinet_memberships m JOIN webapp_auth."user" u ON u.id=m.user_id WHERE m.tenant_id=$1 AND m.active=true AND m.role=\'employee\' ORDER BY u.name,m.user_id', [p.tenantId])).rows.map(r => ({ id: r.user_id as string, name: (r.name as string) || "Сотрудник" })) : [];
      return { role: m.role, tasks, assignees: people, nextCursor, filter };
    }); },
    accept(p: Principal, input: unknown) { const v = validateAcceptance(input); return transaction(p, async (db, m) => {
      if (m.role !== "owner") throw new QueueError(403, "Подтверждение доступно владельцу кабинета.");
      const run = await command(db, p, v.idempotencyKey, "accept", v);
      if (run.replay) return run.result!;
      await lock(db, `${p.tenantId}:signal:${v.signalId}`);
      const existing = await db.query("SELECT t.task_id, t.run_id, COALESCE((SELECT e.kind FROM task_events e WHERE e.tenant_id=t.tenant_id AND e.task_id=t.task_id ORDER BY (e.kind='cancelled') DESC, (e.kind='completed') DESC, e.created_at DESC LIMIT 1),'open') AS status FROM loop_tasks t JOIN decision_records d ON d.tenant_id=t.tenant_id AND d.decision_id=t.decision_id WHERE d.tenant_id=$1 AND d.signal_id=$2", [p.tenantId, v.signalId]);
      if (existing.rows[0]) {
        if (existing.rows[0].status === "cancelled") throw new QueueError(409, "Сигнал уже решён, отмена финальна.");
        const result = { taskId: existing.rows[0].task_id as string, runId: existing.rows[0].run_id as string };
        await finish(db, p, run.id, result);
        return result;
      }
      if (Date.parse(v.dueAt) <= clock().getTime()) throw new QueueError(400, "Срок задачи должен быть в будущем.");
      const assignee = await member(db, { ...p, userId: v.assigneeId });
      if (assignee.role !== "employee") throw new QueueError(400, "Выберите сотрудника кабинета.");
      const row = await freshBrief(db, p);
      const signal = row.payload.signals.find(s => s.signal_id === v.signalId && s.tenant_id === p.tenantId);
      if (!signal || !signal.source_refs?.length) throw new QueueError(409, "Сигнал отсутствует в текущей сводке или не имеет источника.");
      if (signal.snapshot_id !== v.snapshotId) throw new QueueError(409, "Данные сигнала обновились. Перечитайте бриф перед подтверждением.");
      const decisionId = randomUUID(), taskId = randomUUID();
      const decision: DecisionRecordV1 = { schema_version: 1, signal_id: signal.signal_id, decision: "accepted", actor: p.userId, decided_at: clock().toISOString(), reason: v.action, expected: v.expected, actual: null, delta: null };
      await db.query("INSERT INTO decision_records (tenant_id,decision_id,run_id,signal_id,actor_id,source_brief_run_id,signal_snapshot,diagnosis_snapshot,payload) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)", [p.tenantId, decisionId, run.id, signal.signal_id, p.userId, row.run_id, signal, diagnoseSignal(signal, row.brief_day), decision]);
      await db.query("INSERT INTO loop_tasks (tenant_id,task_id,decision_id,run_id,assignee_id,action,due_at,expected_outcome,horizon_days) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)", [p.tenantId, taskId, decisionId, run.id, v.assigneeId, v.action, v.dueAt, v.expectedOutcome, v.expected.horizon_days]);
      await finish(db, p, run.id, { taskId, runId: run.id });
      return { taskId, runId: run.id };
    }); },
    event(p: Principal, taskId: string, kind: "blocked" | "completed" | "cancelled", evidence: unknown, idempotencyKey: string) {
      if (!nonempty(evidence, 5000)) throw new QueueError(400, "Приложите подтверждение: ссылку или описание результата.");
      return transaction(p, async (db, m) => {
        await lock(db, `${p.tenantId}:task:${taskId}`);
        const t = await task(db, m, taskId);
        if ((kind !== "cancelled" && t.assignee_id !== p.userId) || (kind === "cancelled" && m.role !== "owner")) throw new QueueError(403, "Действие недоступно.");
        const run = await command(db, p, idempotencyKey, kind, { taskId, evidence });
        if (run.replay) return run.result!;
        if (t.status === "cancelled" || (kind === "completed" && !["open", "blocked"].includes(t.status)) || (kind === "blocked" && t.status !== "open")) throw new QueueError(409, "Статус задачи уже изменился.");
        await db.query("INSERT INTO task_events (tenant_id,event_id,task_id,run_id,actor_id,kind,evidence) VALUES ($1,$2,$3,$4,$5,$6,$7)", [p.tenantId, randomUUID(), taskId, run.id, p.userId, kind, evidence.trim()]);
        await finish(db, p, run.id, { taskId, runId: run.id });
        return { taskId, runId: run.id };
      });
    },
    observe(p: Principal, taskId: string, idempotencyKey: string) { return transaction(p, async (db, m) => {
      await lock(db, `${p.tenantId}:task:${taskId}`);
      const t = await task(db, m, taskId);
      if (m.role !== "owner" || p.userId === t.assignee_id) throw new QueueError(403, "Проверку проводит владелец, отдельно от исполнителя.");
      const run = await command(db, p, idempotencyKey, "observe", { taskId });
      if (run.replay) return run.result!;
      if (t.status === "cancelled") throw new QueueError(409, "Задача отменена.");
      let reason = observationReadiness(t, clock());
      let status = t.orphaned ? "unknown" : reason ? "pending" : "observed";
      let snapshot: unknown = null;
      if (!reason) {
        try {
          const row = await freshBrief(db, p);
          const end = moscowDayAt(new Date(Date.parse(t.completed_at!) + t.horizon_days * 86_400_000));
          if (row.brief_day < end) { status = "unknown"; reason = "В сводке ещё нет полного дня после срока наблюдения."; }
          else if (row.brief_day > end) { status = "unknown"; reason = `Окно наблюдения закончилось днём ${end}, свежая сводка уже позже. Замер по чужому дню не проводится, результат не доказан.`; }
          else {
            const saved = await db.query("SELECT d.signal_snapshot, d.payload FROM decision_records d JOIN loop_tasks t ON d.tenant_id=t.tenant_id AND d.decision_id=t.decision_id WHERE t.tenant_id=$1 AND t.task_id=$2", [p.tenantId, taskId]);
            const original = saved.rows[0].signal_snapshot;
            const nm = original.detection_data.nm_id;
            const expected = saved.rows[0].payload.expected as DecisionRecordV1["expected"];
            const supported = original.detection_data.level?.value === "sku" && nm?.is_unknown === false && Number.isSafeInteger(nm.value) && expected.metrics.every(m => (m.name === "orders" && m.unit === "count") || (m.name === "revenue" && m.unit === "RUB"));
            if (!supported) { status = "unknown"; reason = "Нет сопоставимого ряда для сохранённого субъекта и показателя цели. Результат не доказан."; }
            else {
              const facts = await db.query("SELECT calendar_day::text, orders_count, revenue_rub::text, run_id, evidence_sha256 FROM fact_nm_daily_current WHERE tenant_id=$1 AND nm_id=$2 AND calendar_day=$3", [p.tenantId, nm.value, row.brief_day]);
              const fact = facts.rows[0];
              if (!fact || !fact.evidence_sha256?.length) { status = "unknown"; reason = "За день наблюдения нет полного факта по исходному SKU с источниками."; }
              else {
                const measurements = expected.metrics.map(m => {
                  const value = m.name === "orders" ? `${fact.orders_count}.00` : fact.revenue_rub;
                  return { ...m, expected: m.value, actual: value, target_reached: decimalCents(value) >= decimalCents(m.value), source_refs: fact.evidence_sha256 };
                });
                snapshot = { grain: "sku", nm_id: nm.value, baseline: original, evaluation_day: row.brief_day, fact_run_id: fact.run_id, measurements };
                reason = measurements.every(m => m.target_reached) ? "Цель по исходному SKU достигнута за день наблюдения. Причинная связь с действием не доказана." : "Цель по исходному SKU пока не достигнута за день наблюдения. Причинная связь с действием не доказана.";
              }
            }
          }
        } catch (e) { if (!(e instanceof QueueError)) throw e; status = "unknown"; reason = e.message; }
      }
      await db.query("INSERT INTO task_observations (tenant_id,observation_id,task_id,run_id,actor_id,status,reason,snapshot) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)", [p.tenantId, randomUUID(), taskId, run.id, p.userId, status, reason, snapshot]);
      await finish(db, p, run.id, { taskId, runId: run.id });
      return { taskId, runId: run.id };
    }); },
  };
}
let service: ReturnType<typeof createQueueService> | undefined;
export function getQueueService() {
  if (!service) {
    const path = process.env.WEBAPP_LOOP_DATABASE_URI_FILE;
    if (!path) throw new QueueError(503, "Очередь не подключена к базе данных.");
    let uri: string;
    try { uri = readFileSync(path, "utf8").trim(); } catch { throw new QueueError(503, "Очередь не подключена к базе данных."); }
    if (!uri) throw new QueueError(503, "Очередь не подключена к базе данных.");
    service = createQueueService(new Pool({ connectionString: uri, max: 5 }));
  }
  return service;
}
