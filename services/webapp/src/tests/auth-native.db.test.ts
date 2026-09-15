import { beforeAll, afterAll, describe, it, expect } from "vitest";
import { randomUUID } from "node:crypto";
import { Pool } from "pg";
import { drizzle } from "drizzle-orm/node-postgres";
import { createAuth } from "@/lib/auth";
import { authSchema } from "@/lib/db/schema.auth";
const dsn=process.env.PROXIMA_TEST_POSTGRES_DSN;
(dsn ? describe : describe.skip)("native BetterAuth HTTP with PostgreSQL runtime role",()=>{
  const admin=new Pool({connectionString:dsn});
  const runtime=new Pool({connectionString:dsn,options:"-c role=proxima_auth_writer"});
  const email=`native-${randomUUID()}@fixture.invalid`;
  const password="fixture-native-password-2026";
  const origin="http://localhost:3371";
  let auth: ReturnType<typeof createAuth>;
  let userId="";
  let cookie="";
  const request=(path:string,body?:unknown,sessionCookie=cookie)=>auth.handler(new Request(origin+"/api/auth/"+path,{method:body===undefined?"GET":"POST",headers:{origin,cookie:sessionCookie,...(body===undefined?{}:{"Content-Type":"application/json"})},...(body===undefined?{}:{body:JSON.stringify(body)})}));
  const cookies=(r:Response)=>r.headers.getSetCookie().map(c=>c.split(";")[0]).join("; ");
  beforeAll(()=>{
    process.env.BETTER_AUTH_URL=origin;
    process.env.BETTER_AUTH_SECRET="fixture-auth-secret-000000000000000000000000";
    auth=createAuth(drizzle(runtime,{schema:authSchema}));
  });
  afterAll(async()=>{await admin.query('DELETE FROM webapp_auth."user" WHERE email=$1',[email]);await runtime.end();await admin.end();});
  it("signs up through the native handler and persists the required issuer without membership",async()=>{
    const response=await request("sign-up/email",{email,password,name:"Fixture employee"},"");
    expect(response.status).toBe(200);
    const body=await response.json();userId=body.user.id;cookie=cookies(response);
    const account=await admin.query('SELECT issuer FROM webapp_auth.account WHERE user_id=$1',[userId]);
    expect(account.rows.map(r=>r.issuer)).toEqual(["local:credential"]);
    expect((await admin.query('SELECT count(*) FROM cabinet_memberships WHERE user_id=$1',[userId])).rows[0].count).toBe("0");
    const result=await request("get-session?disableCookieCache=true");
    expect(result.status).toBe(200);expect((await result.json()).user.id).toBe(userId);
  });
  it("rejects forged and expired cookies, then signs in and revokes the new session",async()=>{
    const forged=await request("get-session?disableCookieCache=true",undefined,"better-auth.session_token=forged");expect(await forged.json()).toBeNull();
    await admin.query("UPDATE webapp_auth.session SET expires_at=now()-interval '1 minute' WHERE user_id=$1",[userId]);
    expect(await (await request("get-session?disableCookieCache=true")).json()).toBeNull();
    const response=await request("sign-in/email",{email,password},"");expect(response.status).toBe(200);cookie=cookies(response);
    expect((await (await request("get-session?disableCookieCache=true")).json()).user.id).toBe(userId);
    expect((await request("sign-out",{})).status).toBe(200);
    expect(await (await request("get-session?disableCookieCache=true")).json()).toBeNull();
  });
});
