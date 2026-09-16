// Trusted evaluator. Host Python owns every assertion over this untrusted capture.
import { pathToFileURL } from "node:url";

const output = process.stdout.write.bind(process.stdout);
const job = process.argv[2];
const allowed = [
  "day-20260916-readiness",
  "day-20260916-readiness-r2",
  "day-20260916-readiness-r3",
];
if (!allowed.includes(job)) throw new Error("unapproved acceptance task");

type Capture = { sql: string; args: unknown[] | null };
type Row = Record<string, unknown>;
type Scenario = {
  name: string;
  tenant?: string;
  offset?: number;
  status?: Row | null;
  brief?: Row | null;
};

const status = (stale: unknown = false): Row => ({
  last_full_day: "2026-09-15",
  collected_at: "2026-09-16T04:00:00Z",
  stale,
});
const brief = (
  briefStatus: string,
  briefDay: unknown = "2026-09-15",
  payload: unknown = {
    source_refs: ["source-a"],
    norm: { sample_days: 14, window_days: 14 },
    preserved: "full-payload",
  },
): Row => ({
  run_id: "brief-run",
  brief_day: briefDay,
  status: briefStatus,
  payload,
});

const scenarios: Scenario[] = [
  { name: "ready", status: status(), brief: brief("ok") },
  { name: "norm-insufficient", status: status(), brief: brief("insufficient",
      "2026-09-15", { source_refs: [], norm: { sample_days: 9, window_days: 14 } }) },
  { name: "brief-blocked", status: status(), brief: brief("blocked",
      "2026-09-15", { source_refs: [], norm: null }) },
  { name: "brief-missing", status: status(), brief: null },
  { name: "stale-brief-missing", status: status(true), brief: null },
  { name: "status-missing", status: null, brief: brief("ok") },
  { name: "stale-priority", status: status(true), brief: brief("insufficient",
      "2026-09-15", { source_refs: [], norm: { sample_days: 9, window_days: 14 } }) },
  { name: "day-mismatch", status: status(), brief: brief("ok", "2026-09-14") },
  { name: "source-refs-missing", status: status(), brief: brief("ok",
      "2026-09-15", { source_refs: [], norm: { sample_days: 14, window_days: 14 } }) },
  { name: "other-not-ready", status: status(), brief: brief("pending") },
  { name: "invalid-progress-string", status: status(), brief: brief("insufficient",
      "2026-09-15", { norm: { sample_days: "9", window_days: 14 } }) },
  { name: "invalid-progress-negative", status: status(), brief: brief("insufficient",
      "2026-09-15", { norm: { sample_days: -1, window_days: 14 } }) },
  { name: "invalid-progress-over", status: status(), brief: brief("insufficient",
      "2026-09-15", { norm: { sample_days: 15, window_days: 14 } }) },
  { name: "invalid-progress-missing", status: status(), brief: brief("insufficient",
      "2026-09-15", { other: true }) },
  { name: "invalid-progress-zero-window", status: status(), brief: brief("insufficient",
      "2026-09-15", { norm: { sample_days: 0, window_days: 0 } }) },
  { name: "invalid-progress-window-over", status: status(), brief: brief("insufficient",
      "2026-09-15", { norm: { sample_days: 1, window_days: 367 } }) },
  { name: "invalid-progress-fractional", status: status(), brief: brief("insufficient",
      "2026-09-15", { norm: { sample_days: 1.5, window_days: 14 } }) },
  { name: "invalid-brief-day", status: status(), brief: brief("ok", "2026-9-15") },
  { name: "tenant-offset-isolation", tenant: "tenant-b", offset: 7,
    status: { ...status(), last_full_day: "2026-09-16" },
    brief: brief("ok", "2026-09-16") },
];

async function evaluateScenario(readPilotContext: Function, scenario: Scenario) {
  const tenant = scenario.tenant ?? "tenant-a";
  const offset = scenario.offset ?? 0;
  const calls: Capture[] = [];
  let releaseCount = 0;
  const queueRow = {
    task_id: "task-a",
    action: "Inspect",
    assignee_id: "employee-a",
    assignee_name: "Employee A",
    due_at: "2026-09-17T12:00:00Z",
    expected_outcome: "Evidence",
    expected: [],
    source_refs: ["task-source"],
    status: "open",
    total: offset + 2,
  };
  const employees = [{ user_id: "employee-a", name: "Employee A" }];
  const responses = [
    { rows: [] },
    { rows: [] },
    { rows: scenario.status ? [scenario.status] : [] },
    { rows: scenario.brief ? [scenario.brief] : [] },
    { rows: [queueRow] },
    { rows: employees },
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
  const result = await readPilotContext(pool, tenant, offset);
  return { name: scenario.name, tenant, offset, calls,
           release_count: releaseCount, result };
}

async function evaluate() {
  const context = await import(pathToFileURL(
    "/work/services/webapp/src/lib/loop/context.ts").href);
  const cases = [];
  for (const scenario of scenarios) {
    cases.push(await evaluateScenario(context.readPilotContext, scenario));
  }
  output(JSON.stringify({ version: 1, job_id: job, cases }) + "\n");
}

evaluate().catch(() => {
  process.stderr.write("candidate evaluation failed\n");
  process.exitCode = 1;
});
