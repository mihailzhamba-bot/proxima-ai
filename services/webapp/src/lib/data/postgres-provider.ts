import { readFileSync } from "node:fs";
import { Pool, type PoolClient } from "pg";
import type { BriefV1 } from "@/lib/contracts/brief";
import type { DataProvider } from "@/lib/data/provider";
import type {
  BriefData,
  BriefSummary,
  BriefVariant,
  DataStatusInfo,
  Metric,
  SummaryMetric,
  SummaryStatus,
} from "@/lib/data/view-model";
import { getBrief as getFixturesBrief } from "@/lib/fixtures/brief";

/*
 * Боевой источник данных (AD-9, Story 2.5 со статусом Story 1.11).
 *
 * Провайдер владеет собственным Pool: URI читается из файла секрета
 * (WEBAPP_DATA_DATABASE_URI_FILE), tenant задаётся GUC proxima.tenant_id
 * первым statement каждого соединения - без него RLS отдаёт 0 строк (AD-13).
 * Значение URI никогда не попадает в лог или исключение: наружу - только
 * имя переменной или файла (политика секретов AGENTS.md).
 *
 * Ровно два SELECT под proxima_webapp_readonly (AD-9): data_status_current
 * и brief_current. Цифры показываются только при
 * `brief.status = 'ok' AND stale IS FALSE AND brief_day = last_full_day`;
 * иначе - предупреждение вместо цифр (AC Story 1.11).
 */

const TENANT_PATTERN = /^[a-z0-9][a-z0-9_-]{2,63}$/;

const TENANT_ENV = "WEBAPP_TENANT_ID";
const URI_FILE_ENV = "WEBAPP_DATA_DATABASE_URI_FILE";

/** Метрики экрана дашборда в postgres-режиме не реализованы; сводка /brief - да. */
export const POSTGRES_PROVIDER_NOT_IMPLEMENTED = "NOT_IMPLEMENTED";

const NOT_IMPLEMENTED =
  `${POSTGRES_PROVIDER_NOT_IMPLEMENTED}: webapp: метрики дашборда в режиме postgres ещё не реализованы ` +
  "(сводка /brief читает brief_current, метрики - отдельная единица).";

export function validateTenantId(value: string | undefined): string {
  if (!value) {
    throw new Error(
      `webapp: env ${TENANT_ENV} не задан: postgres-режим обязан знать tenant для GUC proxima.tenant_id (AD-9).`,
    );
  }
  if (!TENANT_PATTERN.test(value)) {
    throw new Error(`webapp: env ${TENANT_ENV}="${value}" не подходит под ^[a-z0-9][a-z0-9_-]{2,63}$.`);
  }
  return value;
}

function readDatabaseUri(env: Readonly<Record<string, string | undefined>>): string {
  const path = env[URI_FILE_ENV];
  if (!path) {
    throw new Error(`webapp: env ${URI_FILE_ENV} не задан: URI роли webapp_readonly приходит файлом секрета.`);
  }
  try {
    const value = readFileSync(path, "utf8").trim();
    if (!value) {
      throw new Error(`webapp: файл ${URI_FILE_ENV} пуст: ${path}`);
    }
    return value;
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("webapp:")) {
      throw error;
    }
    // Сам путь не секрет, но и его не печатаем: наружу - только имя переменной.
    throw new Error(`webapp: файл ${URI_FILE_ENV} не читается (путь из env).`);
  }
}

/** Минимальная поверхность Pool, которую использует провайдер; шов для тестов (AC 1.11: мок Pool). */
export type DatabasePool = {
  on(event: "connect", listener: (client: PoolClient) => void): unknown;
  connect(): Promise<PoolClient>;
  end(): Promise<void>;
};

export type PostgresProviderOptions = {
  /** Тестовый шов: подмена Pool вместо реального соединения (сеть в тестах запрещена, AD-4). */
  createPool?: (connectionString: string) => DatabasePool;
};

function defaultCreatePool(connectionString: string): DatabasePool {
  return new Pool({ connectionString, max: 5 });
}

type QueryableClient = {
  query(text: string, values?: readonly unknown[]): Promise<{ rows: Record<string, unknown>[] }>;
  release(): void;
};

type StatusRow = {
  last_full_day: string | null;
  collected_at: Date | string | null;
  stale: boolean | null;
};

type BriefRow = {
  brief_day: string;
  status: string;
  payload: BriefV1;
};

function toIsoMoment(value: Date | string | null): string {
  if (value instanceof Date) {
    return value.toISOString();
  }
  return value ?? "";
}

export function createPostgresProvider(
  env: Readonly<Record<string, string | undefined>> = process.env,
  options: PostgresProviderOptions = {},
): DataProvider {
  // Валидация tenant - при создании провайдера, то есть при старте процесса (AD-9):
  // неверный конфиг не может выглядеть как поднявшийся webapp.
  const tenantId = validateTenantId(env[TENANT_ENV]);
  const createPool = options.createPool ?? defaultCreatePool;
  // Pool ленивый: создаётся при первом запросе, чтобы typecheck/тесты/build жили без БД.
  let pool: DatabasePool | undefined;

  function getPool(): DatabasePool {
    if (!pool) {
      pool = createPool(readDatabaseUri(env));
      // GUC сессионный (false, не true): живёт с соединением. pg-pool эмитит 'connect'
      // до выдачи клиента, set_config уходит первым statement (обзор AD-9, вопрос 8).
      // catch обязателен: необработанный rejection в on('connect') роняет процесс.
      pool.on("connect", (client) => {
        client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]).catch(() => {
          // RLS без GUC сам вернёт 0 строк; падать весь webapp из-за этого не должен.
        });
      });
    }
    return pool;
  }

  async function withClient<T>(work: (client: QueryableClient) => Promise<T>): Promise<T> {
    const client = await getPool().connect();
    try {
      return await work(client as unknown as QueryableClient);
    } finally {
      client.release();
    }
  }

  /** SELECT №1 из data_status_current (AD-9). */
  async function readStatus(): Promise<DataStatusInfo | null> {
    return withClient(async (client) => {
      const result = await client.query(
        // Даты - текстом: pg парсит `date` в Date локальной таймзоны, а нужен чистый ISO дня.
        "SELECT last_full_day::text AS last_full_day, collected_at, stale FROM data_status_current",
      );
      const row = (result.rows[0] ?? null) as StatusRow | null;
      if (row === null) {
        return null;
      }
      return {
        lastFullDay: row.last_full_day ?? "",
        collectedAt: toIsoMoment(row.collected_at),
        stale: row.stale === true,
      };
    });
  }

  /** SELECT №2 из brief_current (AD-9): view отдаёт ровно одну строку на tenant. */
  async function readBriefRow(): Promise<BriefRow | null> {
    return withClient(async (client) => {
      const result = await client.query(
        "SELECT brief_day::text AS brief_day, status, payload FROM brief_current",
      );
      return ((result.rows[0] ?? null) as BriefRow | null);
    });
  }

  return {
    mode: "postgres",

    /**
     * Редакционная часть брифа. До первого SUCCEEDED brief работает режим
     * «только статус» (AC Story 1.11): отдаётся fixtures-бриф с пометкой
     * «сводка ещё не считается» в дайджесте; цифры сводки приносит getSummary().
     */
    async getBrief(variant: BriefVariant): Promise<BriefData> {
      // Читателей ровно два SELECT на отрисовку (AD-9), поэтому brief_current
      // читает только getSummary. Признак «сводка ещё не считается» страница берёт
      // из его статуса no-brief, а не из второго чтения той же строки.
      return getFixturesBrief(variant);
    },

    /** Сводка «вчера против нормы» с правилом показа AD-9. */
    async getSummary(): Promise<BriefSummary> {
      const [row, dataStatus] = await Promise.all([readBriefRow(), readStatus()]);
      if (row === null) {
        return {
          status: "no-brief",
          briefDay: null,
          orders: null,
          revenue: null,
          normProgress: null,
          dataStatus,
        };
      }
      const payload = row.payload;
      // Правило AD-9 сверяется с живым data_status_current, а не с копией внутри
      // payload: та копия снята в момент записи брифа и всегда совпадает с brief_day,
      // поэтому сравнение с ней тождественно истинно. Ровно этот случай AD-9 и
      // называет в Prevents - вчерашняя сводка, показанная как свежая: сбор ушёл
      // вперёд, норма и бриф за новый день ещё не посчитаны, а экран рисует цифры.
      // Нет живого статуса данных - свежесть подтвердить нечем, поэтому цифры не
      // показываются: fail-closed, а не «наверное, всё в порядке».
      const dayMatches = dataStatus !== null && row.brief_day === dataStatus.lastFullDay;
      const showNumbers = row.status === "ok" && dataStatus?.stale === false && dayMatches;
      // Сводка формально ok, но верить цифрам нельзя (stale или день уже не последний
      // полный): на экране предупреждение, а не числа - тот же fail-closed, что и в AC 1.11.
      const status: SummaryStatus = showNumbers ? "ok" : row.status === "ok" ? ("stale" as SummaryStatus) : (row.status as SummaryStatus);
      const metric = (actual: number | string | null, norm: string | null, deviationPct: number | null): SummaryMetric | null =>
        actual === null || !showNumbers ? null : { actual, norm, deviationPct };
      return {
        status,
        briefDay: row.brief_day,
        orders: metric(payload.actual?.orders ?? null, payload.norm?.orders ?? null, payload.deviation_pct?.orders ?? null),
        revenue: metric(payload.actual?.revenue ?? null, payload.norm?.revenue ?? null, payload.deviation_pct?.revenue ?? null),
        // Прогресс «норма копится: 9/14» известен и для insufficient: норма в payload
        // есть (D30), отклонение против неё не называется - но образец окна это факт.
        normProgress:
          payload.norm === null ? null : { sampleDays: payload.norm.sample_days, windowDays: payload.norm.window_days },
        dataStatus,
      };
    },

    getMetrics(): Promise<readonly Metric[]> {
      return Promise.reject(new Error(NOT_IMPLEMENTED));
    },
  };
}
