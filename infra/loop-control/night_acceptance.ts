// Trusted operator assertions. Mounted read-only outside the candidate checkout.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

async function check() {
  const job = process.argv[2];
  const load = (name: string) => import(pathToFileURL(`/work/services/webapp/src/lib/${name}.ts`).href);
  if (job.startsWith("tg-")) {
    const { LOOP_ROUTE_PROBE } = await load("loop-route-probe");
    assert.equal(LOOP_ROUTE_PROBE, "paperclip-hermes-openhands-harper");
  } else if (job === "night-20260915-observation") {
    const { observationReadiness } = await load("loop/service");
    const task = { status: "completed", completed_at: "2026-09-15T12:00:00Z", horizon_days: 2, orphaned: false };
    const now = new Date("2026-09-18T12:00:00Z");
    const blocked = (value: unknown) => assert.ok(typeof value === "string" && value.length > 0);
    for (const horizon_days of [NaN, Infinity, 0, -1, 1.5, 366, null, "2"]) {
      blocked(observationReadiness({ ...task, horizon_days }, now));
    }
    for (const completed_at of ["not-a-date", "", null]) blocked(observationReadiness({ ...task, completed_at }, now));
    blocked(observationReadiness(task, new Date(NaN)));
    blocked(observationReadiness(task, new Date("2026-09-17T11:59:59Z")));
    assert.equal(observationReadiness(task, new Date("2026-09-17T12:00:00Z")), null);
    blocked(observationReadiness({ ...task, orphaned: true }, now));
    blocked(observationReadiness({ ...task, status: "cancelled" }, now));
  } else if (job === "night-20260915-diagnosis") {
    const { diagnoseSignal } = await load("loop/diagnosis");
    const signal = { source_refs: ["fixture-source-exact"], detection_data: {} };
    for (const value of [NaN, Infinity, -Infinity, "UNKNOWN", "", "NaN", "1O", true, null]) {
      const result = diagnoseSignal({ ...signal, detection_data: { orders_actual: { value, is_unknown: false } } }, "2026-09-15");
      assert.deepEqual(result.facts, []);
      assert.ok(result.unknowns.length > 0);
    }
    for (const value of [0, 12, "0.00", "12345678901234567890.12", "-30.00"]) {
      const result = diagnoseSignal({ ...signal, detection_data: { orders_actual: { value, is_unknown: false } } }, "2026-09-15");
      assert.equal(result.facts.length, 1);
      assert.equal(result.facts[0].value, value);
      assert.deepEqual(result.facts[0].sourceRefs, signal.source_refs);
    }
    const measured = { ...signal, detection_data: { orders_actual: { value: 12, is_unknown: false } } };
    for (const day of ["", "2026-02-30", "2026-9-15", "not-a-day"]) {
      const result = diagnoseSignal(measured, day);
      assert.deepEqual(result.facts, []);
      assert.ok(result.unknowns.length > 0);
    }
    assert.equal(diagnoseSignal(measured, "2024-02-29").facts.length, 1);
    for (const source_refs of [[], [""], ["   "]]) {
      assert.deepEqual(diagnoseSignal({ ...measured, source_refs }, "2026-09-15").facts, []);
    }
    assert.deepEqual(diagnoseSignal({ ...signal, detection_data: { orders_actual: { value: 12, is_unknown: true } } }, "2026-09-15").facts, []);
  } else throw new Error("unapproved acceptance task");
}
check().catch(() => { process.stderr.write("independent acceptance blocked\n"); process.exitCode = 1; });
