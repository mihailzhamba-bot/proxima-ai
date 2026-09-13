import { beforeAll, beforeEach, afterAll, afterEach, describe, expect, it, vi } from "vitest";
import { mkdtempSync, writeFileSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const db=vi.hoisted(()=>({created:vi.fn(),query:vi.fn(),release:vi.fn(),connect:vi.fn()}));
vi.mock("pg",()=>({Pool:class {
  constructor(options:unknown){db.created(options);}
  async connect(){db.connect();return {query:db.query,release:db.release};}
}}));
let folder:string;
beforeAll(()=>{folder=mkdtempSync(join(tmpdir(),"loop-context-route-"));writeFileSync(join(folder,"token"),"fixture-private-context",{mode:0o600});writeFileSync(join(folder,"uri"),"postgresql://fixture.invalid/context",{mode:0o600});});
afterAll(()=>rmSync(folder,{recursive:true,force:true}));
beforeEach(()=>{vi.resetModules();vi.clearAllMocks();db.query.mockResolvedValue({rows:[]});vi.stubEnv("WEBAPP_LOOP_CONTEXT_TOKEN_FILE",join(folder,"token"));vi.stubEnv("WEBAPP_LOOP_CONTEXT_DATABASE_URI_FILE",join(folder,"uri"));vi.stubEnv("WEBAPP_TENANT_ID","fixture-server-cabinet");});
afterEach(()=>vi.unstubAllEnvs());
async function get(url="https://fixture.invalid/api/loop/context",token="fixture-private-context"){
  const {GET}=await import("@/app/api/loop/context/route");
  return GET(new Request(url,{headers:{authorization:"Bearer "+token,"X-Tenant-ID":"foreign-header"}}));
}
describe("registered context GET route",()=>{
  it("denies a missing configuration before DB initialization",async()=>{
    vi.stubEnv("WEBAPP_LOOP_CONTEXT_TOKEN_FILE","");expect((await get()).status).toBe(503);expect(db.created).not.toHaveBeenCalled();expect(db.query).not.toHaveBeenCalled();
  });
  it("denies wrong credential before DB initialization",async()=>{
    expect((await get(undefined,"wrong")).status).toBe(403);expect(db.created).not.toHaveBeenCalled();expect(db.connect).not.toHaveBeenCalled();
  });
  it("accepts a private valid token and binds the server cabinet",async()=>{
    expect(statSync(join(folder,"token")).mode & 0o077).toBe(0);
    const response=await get();expect(response.status).toBe(200);expect((await response.json()).cabinet_id).toBe("fixture-server-cabinet");
    expect(db.created).toHaveBeenCalledOnce();expect(db.query).toHaveBeenCalledWith("SELECT set_config('proxima.tenant_id',$1,true)",["fixture-server-cabinet"]);
    expect(db.query).toHaveBeenCalledWith("BEGIN READ ONLY");
  });
  it("cannot override tenant through query even with a valid token",async()=>{
    expect((await get("https://fixture.invalid/api/loop/context?tenant_id=foreign")).status).toBe(400);expect(db.created).not.toHaveBeenCalled();expect(db.query).not.toHaveBeenCalled();
  });
});
