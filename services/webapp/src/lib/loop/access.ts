import { headers } from "next/headers";
import { getAuth } from "@/lib/auth";
import { getQueueService, QueueError, type Principal } from "./service";

export function requiresSession(env: Readonly<Record<string, string | undefined>> = process.env) {
  return env.WEBAPP_DATA_MODE === "postgres" || env.WEBAPP_REQUIRE_AUTH === "true";
}
export async function currentPrincipal(requestHeaders?: Headers): Promise<Principal> {
  const h = requestHeaders ?? await headers();
  // Always ask BetterAuth: signed/expired/revoked/secure cookies are its responsibility.
  const session = await getAuth().api.getSession({ headers: h, query: { disableCookieCache: true } });
  if (!session?.user?.id || new Date(session.session.expiresAt).getTime() <= Date.now()) throw new QueueError(401, "Войдите в свой аккаунт.");
  const tenantId = process.env.WEBAPP_TENANT_ID;
  if (!tenantId) throw new QueueError(503, "Кабинет ещё не подключён.");
  return { userId: session.user.id, tenantId };
}
export async function currentMember(requestHeaders?: Headers) {
  return getQueueService().membership(await currentPrincipal(requestHeaders));
}
