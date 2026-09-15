import { drizzle, type NodePgDatabase } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import { readFileSync } from "node:fs";
import { authSchema } from "@/lib/db/schema.auth";

/*
 * Ленивые подключения: инстанцируются только при первом запросе,
 * чтобы typecheck / тесты / next build работали без Postgres.
 *
 * Две роли БД (создаются на деплой-сессии PA-49, сессия 2):
 *  - webapp_auth_writer  - пишет ТОЛЬКО в схему webapp_auth (логины/сессии/решения)
 *  - webapp_readonly     - читает доменные данные, мутации запрещены ролью
 *
 * UI не считает метрики: читает готовые факты/сигналы (детерминированность, AGENTS.md).
 */

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `webapp: env ${name} не задан. Для локальной разработки без БД используй WEBAPP_REQUIRE_AUTH=false и fixtures-режим.`,
    );
  }
  return value;
}

let authDb: NodePgDatabase<typeof authSchema> | undefined;
let dataDb: NodePgDatabase<Record<string, never>> | undefined;

/** Соединение записи для Better Auth (роль webapp_auth_writer). */
export function getAuthDb(): NodePgDatabase<typeof authSchema> {
  if (!authDb) {
    const pool = new Pool({
      connectionString: authUri(),
      max: 5,
    });
    authDb = drizzle(pool, { schema: authSchema });
  }
  return authDb;
}

function authUri(): string {
  const path = process.env.WEBAPP_AUTH_DATABASE_URI_FILE;
  if (!path) return requiredEnv("WEBAPP_AUTH_DATABASE_URI");
  try {
    const value = readFileSync(path, "utf8").trim();
    if (!value) throw new Error();
    return value;
  } catch { throw new Error("webapp: WEBAPP_AUTH_DATABASE_URI_FILE unavailable"); }
}

/** Соединение чтения доменных данных (роль webapp_readonly, мутации запрещены на уровне роли). */
export function getDataDb(): NodePgDatabase<Record<string, never>> {
  if (!dataDb) {
    const pool = new Pool({
      connectionString: process.env.WEBAPP_DATA_DATABASE_URI ?? requiredEnv("DATABASE_URI"),
      max: 5,
    });
    dataDb = drizzle(pool);
  }
  return dataDb;
}

/** true, когда настроен читающий контур данных (иначе UI остаётся на fixtures). */
export function hasDataDb(): boolean {
  return Boolean(process.env.WEBAPP_DATA_DATABASE_URI ?? process.env.DATABASE_URI);
}
