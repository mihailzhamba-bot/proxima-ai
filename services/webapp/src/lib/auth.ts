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
      // P5 (Codex audit 22.09): регистрация закрыта по умолчанию - fail-closed.
      // Первая учётная запись создаётся на деплой-сессии при явном
      // WEBAPP_ALLOW_SIGNUP=1 в окружении контейнера, затем контейнер
      // пересоздаётся без флага (runbook release-m03.md §3b, шаг 6).
      disableSignUp: process.env.WEBAPP_ALLOW_SIGNUP !== "1",
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
