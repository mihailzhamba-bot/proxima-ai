import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { getAuthDb } from "@/lib/db/client";
import { account, session, user, verification } from "@/lib/db/schema.auth";

/*
 * Better Auth: email/password, пользователи в нашем Postgres (схема webapp_auth).
 * Инстанс ленивый: создаётся при первом обращении к /api/auth/*,
 * чтобы сборка и тесты не требовали БД.
 *
 * BETTER_AUTH_SECRET задаётся окружением (VPS: /etc/proxima-ai/secrets/), никогда в Git.
 * Trusted origins конфигурируются на деплой-сессии вместе с доменом.
 */

function createAuth() {
  return betterAuth({
    database: drizzleAdapter(getAuthDb(), {
      provider: "pg",
      schema: { user, session, account, verification },
    }),
    emailAndPassword: {
      enabled: true,
    },
  });
}

export type Auth = ReturnType<typeof createAuth>;

let auth: Auth | undefined;

export function getAuth(): Auth {
  if (!auth) {
    auth = createAuth();
  }
  return auth;
}
