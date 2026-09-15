// Trusted evaluator. Assertions run in the separate host Python process.
import { pathToFileURL } from "node:url";
const serialize = JSON.stringify.bind(JSON);
const output = process.stdout.write.bind(process.stdout);
const job = process.argv[2];
const load = (name: string) => import(pathToFileURL(`/work/services/webapp/src/lib/${name}.ts`).href);
async function evaluate() {
  const results: unknown[] = [];
  if (job.startsWith("tg-")) {
    const { LOOP_ROUTE_PROBE } = await load("loop-route-probe");
    results.push(LOOP_ROUTE_PROBE);
  } else if (job === "night-20260915-observation") {
    const { observationReadiness } = await load("loop/service");
    const task = { status: "completed", completed_at: "2026-09-15T12:00:00Z", horizon_days: 2, orphaned: false };
    const now = new Date("2026-09-18T12:00:00Z");
    for (const horizon_days of [NaN, Infinity, 0, -1, 1.5, 366, null, "2"]) results.push(observationReadiness({ ...task, horizon_days }, now));
    for (const completed_at of ["not-a-date", "", null]) results.push(observationReadiness({ ...task, completed_at }, now));
    results.push(observationReadiness(task, new Date(NaN)));
    results.push(observationReadiness(task, new Date("2026-09-17T11:59:59Z")));
    results.push(observationReadiness({ ...task, orphaned: true }, now));
    results.push(observationReadiness({ ...task, status: "cancelled" }, now));
    results.push(observationReadiness(task, new Date("2026-09-17T12:00:00Z")));
  } else if (job === "night-20260915-diagnosis") {
    const { diagnoseSignal } = await load("loop/diagnosis");
    const signal = { source_refs: ["fixture-source-exact"], detection_data: {} };
    for (const value of [NaN, Infinity, -Infinity, "UNKNOWN", "", "NaN", "1O", true, null]) {
      results.push(diagnoseSignal({ ...signal, detection_data: { orders_actual: { value, is_unknown: false } } }, "2026-09-15"));
    }
    for (const value of [0, 12, "0.00", "12345678901234567890.12", "-30.00"]) {
      results.push(diagnoseSignal({ ...signal, detection_data: { orders_actual: { value, is_unknown: false } } }, "2026-09-15"));
    }
    const measured = { ...signal, detection_data: { orders_actual: { value: 12, is_unknown: false } } };
    for (const day of ["", "2026-02-30", "2026-9-15", "not-a-day"]) results.push(diagnoseSignal(measured, day));
    results.push(diagnoseSignal(measured, "2024-02-29"));
    for (const source_refs of [[], [""], ["   "]]) results.push(diagnoseSignal({ ...measured, source_refs }, "2026-09-15"));
    results.push(diagnoseSignal({ ...signal, detection_data: { orders_actual: { value: 12, is_unknown: true } } }, "2026-09-15"));
  } else throw new Error("unapproved acceptance task");
  output(serialize({ version: 1, job_id: job, results }) + "\n");
}
evaluate().catch(() => { process.stderr.write("candidate evaluation failed\n"); process.exitCode = 1; });
