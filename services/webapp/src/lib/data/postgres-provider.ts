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
import { anomaliesFromSignals } from "@/lib/data/anomalies";
import { diagnoseSignal } from "@/lib/loop/diagnosis";

/*
 * Боевой источник данных (AD-9, Story 2.5 со статусом Story 1.11).
 *
 * Провайдер владеет собственным Pool: URI читается из файла секрета
 * (WEBAPP_DATA_DATABASE_URI_FILE), tenant задаётся GUC proxima.tenant_id
 * первым statement каждого соединения - без него RLS отдаёт 0 строк (AD-13).
 * Значение URI никогда не попадает в лог или исключение: наружу - только
 * имя переменной или файла (политика секретов AGENTS.md).
 *
 * Каждый читатель делает не больше двух SELECT под proxima_webapp_readonly (AD-9):
 * сводка читает data_status_current + brief_current, полоса метрик —
 * data_status_current + fact_cabinet_daily_current. Цифры сводки показываются только при
 * `brief.status = 'ok' AND stale IS FALSE AND brief_day = last_full_day`;
 * иначе - предупреждение вместо цифр (AC Story 1.11). Аномалии дня
 * (`payload.signals[]`, Story 4.3) подчиняются тому же правилу и приходят
 * из той же строки brief_current - третьего SELECT нет.
 */

const TENANT_PATTERN = /^[a-z0-9][a-z0-9_-]{2,63}$/;

const TENANT_ENV = "WEBAPP_TENANT_ID";
const URI_FILE_ENV = "WEBAPP_DATA_DATABASE_URI_FILE";

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

type MetricFactRow = {
  calendar_day: string;
  orders_count: number | string;
  revenue_rub: string;
};

const METRIC_LABELS = {
  signals: "Сигналы",
  revenue: "Выручка / день",
  orders: "Заказы / день",
  oos: "OOS-риски",
  freshness: "Свежесть данных",
} as const;

function parseMoneyCents(value: string): bigint {
  const match = /^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec(value);
  if (!match) {
    throw new Error("webapp: revenue_rub из Postgres не соответствует numeric(14,2).");
  }
  const sign = match[1] === "-" ? -1n : 1n;
  const fraction = (match[3] ?? "").padEnd(2, "0");
  return sign * (BigInt(match[2]) * 100n + BigInt(fraction || "0"));
}

function roundRatio(numerator: bigint, denominator: bigint): bigint {
  if (denominator === 0n) {
    throw new Error("webapp: denominator must not be zero");
  }
  const sign = numerator < 0n !== denominator < 0n ? -1n : 1n;
  const absNumerator = numerator < 0n ? -numerator : numerator;
  const absDenominator = denominator < 0n ? -denominator : denominator;
  return sign * ((absNumerator + absDenominator / 2n) / absDenominator);
}

function centsToRoundedRubles(cents: bigint): number {
  return Number(roundRatio(cents, 100n));
}

/** Отклонение дня к среднему только по имеющимся строкам семи предыдущих дней. */
function deltaPercent(current: bigint, previous: readonly bigint[]): number | null {
  const sum = previous.reduce((total, value) => total + value, 0n);
  if (previous.length === 0 || sum === 0n) {
    return null;
  }
  // Считаем в десятых процента без Number до последнего шага:
  // (current - sum/n) / (sum/n) * 100 = (current*n - sum) / sum * 100.
  return Number(roundRatio((current * BigInt(previous.length) - sum) * 1_000n, sum)) / 10;
}

function isoDaysEndingAt(lastDay: string, count: number): string[] {
  const end = new Date(`${lastDay}T00:00:00.000Z`);
  if (Number.isNaN(end.getTime())) {
    throw new Error("webapp: last_full_day из Postgres не является ISO-днём.");
  }
  return Array.from({ length: count }, (_, index) => {
    const day = new Date(end);
    day.setUTCDate(end.getUTCDate() - (count - 1 - index));
    return day.toISOString().slice(0, 10);
  });
}

function moscowMinuteOfDay(value: Date | string | null): number | null {
  if (value === null) {
    return null;
  }
  const moment = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(moment.getTime())) {
    return null;
  }
  return ((moment.getUTCHours() + 3) % 24) * 60 + moment.getUTCMinutes();
}

function emptyMetrics(): readonly Metric[] {
  return [
    { id: "signals", label: METRIC_LABELS.signals, value: null, format: "count", status: null, deltaPercent: null, deltaGoodWhen: null, points: [], fx: false },
    { id: "revenue-day", label: METRIC_LABELS.revenue, value: null, format: "rub-compact", status: null, deltaPercent: null, deltaGoodWhen: "up", points: [], fx: false },
    { id: "orders-day", label: METRIC_LABELS.orders, value: null, format: "count", status: null, deltaPercent: null, deltaGoodWhen: "up", points: [], fx: false },
    { id: "oos-risks", label: METRIC_LABELS.oos, value: null, format: "count", status: null, deltaPercent: null, deltaGoodWhen: null, points: [], fx: false },
    { id: "freshness", label: METRIC_LABELS.freshness, value: null, format: "clock", status: null, deltaPercent: null, deltaGoodWhen: null, points: [], fx: false },
  ];
}

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
        stale: row.stale !== false,
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
    supportsMetrics: true,

    /**
     * Редакционная часть брифа. До первого SUCCEEDED brief работает режим
     * «только статус» (AC Story 1.11): отдаётся fixtures-бриф с пометкой
     * «сводка ещё не считается» в дайджесте; цифры сводки приносит getSummary().
     */
    async getBrief(variant: BriefVariant): Promise<BriefData> {
      // Читателей ровно два SELECT на отрисовку (AD-9), поэтому brief_current
      // читает только getSummary. Признак «сводка ещё не считается» страница берёт
      // из его статуса no-brief, а не из второго чтения той же строки.
      return { variant, dateIso: "", signals: [], attentionCount: 0, digest: [], dataMode: "postgres" };
    },

    /** Сводка «вчера против нормы» и аномалии дня с правилом показа AD-9. */
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
          threshold: { value: null, source: null, date: null },
          anomalies: [],
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
      const status: SummaryStatus = showNumbers ? "ok" : row.status === "ok" ? "stale" : (row.status as SummaryStatus);
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
        // Порог — конфигурация, а не вычисленная цифра дня: показываем его даже
        // при insufficient/blocked/stale, прямо из того же payload (без SELECT).
        threshold: payload.threshold,
        // Аномалии - те же цифры дня (Story 4.3): порядок payload сохраняется
        // (Story 4.2 ранжирует по деньгам), а при подавленных цифрах список пуст -
        // экран не покажет сигналы против сводки, которой нельзя верить.
        anomalies: showNumbers ? anomaliesFromSignals(payload.signals ?? []).map(a => {
          const signal = payload.signals.find(s => s.signal_id === a.id)!;
          return { ...a, snapshotId: signal.snapshot_id, diagnosis: diagnoseSignal(signal, row.brief_day) };
        }) : [],
      };
    },

    /**
     * Полоса метрик C3: ровно два SELECT под тем же GUC, что и сводка.
     * `orders_count` — заказы на момент run_day−3 (D35); UI это не переопределяет.
     * Дельта — день против среднего имеющихся строк [day−7, day−1]; пропуски
     * исключаются из среднего, а при нуле строк дельта null. В 30-точечном
     * календарном спарклайне те же пропуски становятся нулями.
     * Деньги разбираются как целые копейки и округляются лишь на границе UI (AD-10).
     * `signals` ждёт снятия лимита двух SELECT AD-9 и истории brief_daily;
     * `oos-risks` не имеет источника остатков в текущей лестнице (D35).
     */
    async getMetrics(): Promise<readonly Metric[]> {
      const status = await readStatus();
      if (status === null || status.lastFullDay === "") {
        return emptyMetrics();
      }

      if (status.stale) return emptyMetrics().map(m => m.id === "freshness" ? { ...m, value: moscowMinuteOfDay(status.collectedAt), status: "red" as const } : m);
      const rows = await withClient(async (client) => {
        const result = await client.query(
          `SELECT calendar_day::text AS calendar_day, orders_count, revenue_rub::text AS revenue_rub
           FROM fact_cabinet_daily_current
           WHERE calendar_day BETWEEN $1::date - 29 AND $1::date
           ORDER BY calendar_day ASC`,
          [status.lastFullDay],
        );
        return result.rows as MetricFactRow[];
      });
      const byDay = new Map(rows.map((row) => [row.calendar_day, row]));
      const days = isoDaysEndingAt(status.lastFullDay, 30);
      const current = byDay.get(status.lastFullDay);
      const previousRows = days.slice(-8, -1).flatMap((day) => {
        const row = byDay.get(day);
        return row === undefined ? [] : [row];
      });
      const orderPoints = days.map((day) => Number(byDay.get(day)?.orders_count ?? 0));
      const revenuePoints = days.map((day) => {
        const row = byDay.get(day);
        return row === undefined ? 0 : centsToRoundedRubles(parseMoneyCents(row.revenue_rub));
      });
      const currentOrders = current === undefined ? null : BigInt(current.orders_count);
      const currentRevenue = current === undefined ? null : parseMoneyCents(current.revenue_rub);

      return [
        { id: "signals", label: METRIC_LABELS.signals, value: null, format: "count", status: null, deltaPercent: null, deltaGoodWhen: null, points: [], fx: false },
        {
          id: "revenue-day", label: METRIC_LABELS.revenue,
          value: currentRevenue === null ? null : centsToRoundedRubles(currentRevenue), format: "rub-compact", status: null,
          deltaPercent: currentRevenue === null ? null : deltaPercent(currentRevenue, previousRows.map((row) => parseMoneyCents(row.revenue_rub))),
          deltaGoodWhen: "up", points: revenuePoints, fx: false,
        },
        {
          id: "orders-day", label: METRIC_LABELS.orders,
          value: currentOrders === null ? null : Number(currentOrders), format: "count", status: null,
          deltaPercent: currentOrders === null ? null : deltaPercent(currentOrders, previousRows.map((row) => BigInt(row.orders_count))),
          deltaGoodWhen: "up", points: orderPoints, fx: false,
        },
        { id: "oos-risks", label: METRIC_LABELS.oos, value: null, format: "count", status: null, deltaPercent: null, deltaGoodWhen: null, points: [], fx: false },
        {
          id: "freshness", label: METRIC_LABELS.freshness, value: moscowMinuteOfDay(status.collectedAt), format: "clock",
          status: status.stale ? "red" : "green", deltaPercent: null, deltaGoodWhen: null, points: [], fx: false,
        },
      ];
    },
  };
}
