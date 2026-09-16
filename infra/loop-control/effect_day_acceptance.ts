// Trusted evaluator. Host Python owns every assertion over this untrusted capture.
import { pathToFileURL } from "node:url";

const serialize = JSON.stringify.bind(JSON);
const output = process.stdout.write.bind(process.stdout);
const job = process.argv[2];
const TASK_ID = "11111111-1111-4111-8111-111111111111";
const FACT_RUN_ID = "33333333-3333-4333-8333-333333333333";
const SOURCES = ["a".repeat(64), "b".repeat(64)];
const load = (name: string) =>
  import(pathToFileURL("/work/services/webapp/src/lib/" + name + ".ts").href);

type Capture = { sql: string; args: unknown[] | null };
type Scenario = { name: string; completedAt: string; fact: boolean };

async function runScenario(createQueueService: Function, scenario: Scenario) {
  const calls: Capture[] = [];
  let releaseCount = 0;
  const task = {
    task_id: TASK_ID,
    assignee_id: "employee-b",
    assignee_name: "Employee",
    action: "Check effect",
    due_at: "2026-09-13T20:00:00Z",
    expected_outcome: "Orders and revenue",
    expected_metrics: [],
    horizon_days: 1,
    created_at: "2026-09-12T00:00:00Z",
    status: "completed",
    orphaned: false,
    blocker: null,
    evidence: "completed",
    completed_at: scenario.completedAt,
    observation: null,
  };
  const signalSnapshot = {
    signal_id: "signal-a",
    tenant_id: "tenant-a",
    source_refs: ["signal-source"],
    detection_data: {
      level: { value: "sku", is_unknown: false },
      nm_id: { value: 12345, is_unknown: false },
    },
  };
  const expected = {
    horizon_days: 1,
    metrics: [
      { name: "orders", value: "9.00", unit: "count", source_ref: "goal-orders" },
      { name: "revenue", value: "90.00", unit: "RUB", source_ref: "goal-revenue" },
    ],
  };
  const responses = [
    { rows: [] },
    { rows: [] },
    { rows: [{ role: "owner" }] },
    { rows: [] },
    { rows: [task] },
    { rows: [] },
    { rows: [] },
    { rows: [] },
    { rows: [{ run_id: "brief-run", brief_day: "2026-09-16",
               payload: { source_refs: ["brief-source"] } }] },
    { rows: [{ signal_snapshot: signalSnapshot, payload: { expected } }] },
    { rows: scenario.fact
        ? [{ calendar_day: "captured-untrusted", orders_count: 10,
             revenue_rub: "100.00", run_id: FACT_RUN_ID,
             evidence_sha256: SOURCES }]
        : [] },
    { rows: [] },
    { rows: [] },
    { rows: [] },
  ];
  const db = {
    async query(sql: string, args?: unknown[]) {
      calls.push({ sql, args: args ?? null });
      return responses[calls.length - 1] ?? { rows: [] };
    },
    release() { releaseCount += 1; },
  };
  const pool = { async connect() { return db; } };
  const service = createQueueService(pool, () => new Date("2026-09-18T00:00:00Z"));
  await service.observe(
    { tenantId: "tenant-a", userId: "owner-a" },
    TASK_ID,
    "observe-" + scenario.name,
  );
  return { name: scenario.name, calls, release_count: releaseCount };
}

async function evaluate() {
  if (!["day-20260916-effect-day", "day-20260916-effect-day-r2"].includes(job)) throw new Error("unapproved acceptance task");
  const { createQueueService } = await load("loop/service");
  const cases = [];
  cases.push(await runScenario(createQueueService, {
    name: "before-moscow-midnight",
    completedAt: "2026-09-13T20:59:59Z",
    fact: true,
  }));
  cases.push(await runScenario(createQueueService, {
    name: "at-moscow-midnight",
    completedAt: "2026-09-13T21:00:00Z",
    fact: true,
  }));
  cases.push(await runScenario(createQueueService, {
    name: "missing-fact",
    completedAt: "2026-09-13T21:00:00Z",
    fact: false,
  }));
  output(serialize({ version: 1, job_id: job, cases }) + String.fromCharCode(10));
}

evaluate().catch(() => {
  process.stderr.write("candidate evaluation failed" + String.fromCharCode(10));
  process.exitCode = 1;
});
