import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
const { session, list, accept }=vi.hoisted(()=>({session:vi.fn(),list:vi.fn(),accept:vi.fn()}));
vi.mock("@/lib/auth",()=>({getAuth:()=>({api:{getSession:session}})}));
vi.mock("next/headers",()=>({headers:async()=>new Headers()}));
vi.mock("@/lib/loop/service",async(importOriginal)=>{
  const actual=await importOriginal<typeof import("@/lib/loop/service")>();
  return {...actual,getQueueService:()=>({list,accept})};
});
import { queueRequest } from "@/lib/loop/http";
import { requiresSession } from "@/lib/loop/access";
describe("queue API authentication",()=>{
  beforeEach(()=>{vi.clearAllMocks();process.env.BETTER_AUTH_URL="https://fixture.invalid";process.env.WEBAPP_TENANT_ID="fixture-cabinet";session.mockResolvedValue({user:{id:"employee"},session:{expiresAt:new Date(Date.now()+60000)}});list.mockResolvedValue({tasks:[]});});
  it("rejects forged cookie and expired/revoked server sessions",async()=>{
    session.mockResolvedValue(null);
    const r=await queueRequest(new Request("https://fixture.invalid/api/loop/queue",{headers:{cookie:"better-auth.session_token=forged"}}),"GET");
    expect(r.status).toBe(401);expect(list).not.toHaveBeenCalled();
    session.mockResolvedValue({user:{id:"employee"},session:{expiresAt:new Date(0)}});
    expect((await queueRequest(new Request("https://fixture.invalid/api/loop/queue"),"GET")).status).toBe(401);
  });
  it("uses the authenticated employee and configured tenant, never caller identity",async()=>{
    await queueRequest(new Request("https://fixture.invalid/api/loop/queue?tenantId=foreign&userId=owner"),"GET");
    expect(list).toHaveBeenCalledWith({userId:"employee",tenantId:"fixture-cabinet"});
    expect(session.mock.calls[0][0].query.disableCookieCache).toBe(true);
  });
  it("rejects cross-origin writes and redacts internal errors",async()=>{
    const make=(origin:string)=>new Request("https://fixture.invalid/api/loop/queue",{method:"POST",headers:{origin},body:JSON.stringify({operation:"accept"})});
    expect((await queueRequest(make("https://evil.invalid"),"POST")).status).toBe(403); expect(accept).not.toHaveBeenCalled();
    accept.mockRejectedValue(new Error("postgres://secret")); const r=await queueRequest(make("https://fixture.invalid"),"POST");expect(r.status).toBe(503);expect(await r.text()).not.toContain("secret");
  });
  it("keeps all app routes dynamic across fixture builds and postgres runtime",()=>{
    const layout=readFileSync(new URL("../app/(app)/layout.tsx",import.meta.url),"utf8");
    expect(layout).toContain('export const dynamic = "force-dynamic"');
  });
  it("cannot turn off auth for the postgres mode",()=>{
    expect(requiresSession({WEBAPP_DATA_MODE:"postgres",WEBAPP_REQUIRE_AUTH:"false"})).toBe(true);
  });
});
