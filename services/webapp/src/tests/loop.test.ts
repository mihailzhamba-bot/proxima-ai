import { describe, expect, it } from "vitest";
import { formatTarget } from "@/lib/loop/format-target";
import { authenticateContext } from "@/lib/loop/context";
import { lastFullMoscowDay } from "@/lib/loop/calendar";
import { diagnoseSignal } from "@/lib/loop/diagnosis";
import { observationReadiness, validateAcceptance } from "@/lib/loop/service";
import type { SignalV1 } from "@/lib/contracts/signal";
describe("LOOP deterministic boundaries",()=>{
  it("formats approved targets without floating-point rounding or technical units",()=>{
    expect(formatTarget("32.00","count")).toBe("32 шт.");
    expect(formatTarget("123456789012.01","RUB")).toBe("123 456 789 012,01 ₽");
  });
  it("context reader accepts only its credential and a fixed server scope",()=>{
    expect(()=>authenticateContext(new Request("https://fixture.invalid/api/loop/context",{headers:{authorization:"Bearer fixture-key"}}),"fixture-key")).not.toThrow();
    expect(()=>authenticateContext(new Request("https://fixture.invalid/api/loop/context?tenant=foreign",{headers:{authorization:"Bearer fixture-key"}}),"fixture-key")).toThrow();
    expect(()=>authenticateContext(new Request("https://fixture.invalid/api/loop/context",{headers:{cookie:"better-auth.session_token=human-session"}}),"fixture-key")).toThrow();
  });
  it("changes the full Moscow day exactly at 21:00 UTC",()=>{
    expect(lastFullMoscowDay(new Date("2026-09-13T20:59:59Z"))).toBe("2026-09-12");
    expect(lastFullMoscowDay(new Date("2026-09-13T21:00:00Z"))).toBe("2026-09-13");
  });
  it("does not invent unknown metrics or call an assessment an LLM diagnosis",()=>{
    const signal={source_refs:["source"],detection_data:{orders_actual:{value:5,is_unknown:false},orders_norm_median:{value:"10.00",is_unknown:false},revenue_actual:{value:"100.00",is_unknown:true},unsupported:{value:999,is_unknown:false}}} as unknown as SignalV1;
    const d=diagnoseSignal(signal,"2026-09-13");
    expect(d.kind).toBe("deterministic-pilot-v1"); expect(d.facts.map(f=>f.value)).toEqual([5,"10.00"]);
    expect(d.alternatives).toHaveLength(2); expect(d.facts[0].date).toBe("2026-09-13");
    expect(diagnoseSignal({...signal,source_refs:[] as unknown as SignalV1["source_refs"]},"2026-09-13").facts).toEqual([]);
  });
  it("does not claim an effect before completion, horizon or with deleted source",()=>{
    const t={status:"completed" as const,completed_at:"2026-09-13T12:00:00Z",horizon_days:3,orphaned:false};
    expect(observationReadiness(t,new Date("2026-09-15T12:00:00Z"))).toContain("ещё не прошёл");
    expect(observationReadiness(t,new Date("2026-09-16T12:00:00Z"))).toBeNull();
    expect(observationReadiness({...t,orphaned:true},new Date("2026-09-20T12:00:00Z"))).toContain("удалён");
  });
  it("rejects missing fields, unknown numeric strings and missing source",()=>{
    expect(()=>validateAcceptance({})).toThrow();
    const v={idempotencyKey:"fixture-key",signalId:"fixture-signal",snapshotId:"fixture-snapshot",assigneeId:"fixture-person",action:"Check",dueAt:"2026-10-01T12:00:00Z",expectedOutcome:"Observed",expected:{horizon_days:1,metrics:[{name:"orders",value:"5.00",unit:"count",source_ref:"owner-target:2026-09-13"}]}};
    expect(validateAcceptance(v).expected.metrics[0].value).toBe("5.00");
    expect(()=>validateAcceptance({...v,snapshotId:""})).toThrow();
    expect(()=>validateAcceptance({...v,expected:{...v.expected,metrics:[{...v.expected.metrics[0],value:"NaN"}]}})).toThrow();
  });
});
