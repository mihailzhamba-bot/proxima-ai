import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import type { PoolClient } from "pg";
import type { BriefV1 } from "@/lib/contracts/brief";
import {
  createPostgresProvider,
  type DatabasePool,
  type PostgresProviderOptions,
} from "@/lib/data/postgres-provider";
import { deviationGyr } from "@/components/brief/brief-summary";
import { FIXTURE_BRIEF_SIGNALS } from "@/lib/fixtures/brief";

/*
 * Story 2.5 (со статусом 1.11): postgres-провайдер через шов. Сеть в тестах
 * запрещена (AD-4), поэтому Pool подменяется стабом, который исполняет тот же
 * код провайдера - SQL-тексты, разбор строк и правило показа AD-9
 * (`status = 'ok' AND stale IS FALSE AND brief_day = last_full_day`).
 */

const TENANT = "amirova-test";

const FRESH_STATUS = {
  last_full_day: "2026-08-29",
  collected_at: new Date("2026-08-30T02:41:12.000Z"),
  stale: false,
};

function briefPayload(overrides: Partial<BriefV1> = {}): BriefV1 {
  return {
    schema_version: 1,
    evaluation_day: "2026-08-29",
    data_status: { last_full_day: "2026-08-29", collected_at: "2026-08-30T02:41:12.000Z", stale: false },
    actual: { orders: 27, revenue: "41141.00" },
    norm: { orders: "34.50", revenue: "34595.00", window_days: 14, sample_days: 14 },
    deviation_pct: { orders: -21.7, revenue: 18.9 },
    threshold: { value: null, source: null, date: null },
    signals: [],
    source_refs: ["table://fact_cabinet_daily/2026-08-29"],
    ...overrides,
  };
}

/** Стаб Pool: запоминает on('connect')-хук и отдаёт canned строки на SELECT. */
function stubPool(
  rowsFor: (text: string) => Record<string, unknown>[],
  log: { queries: string[]; connectHooks: ((client: PoolClient) => void)[] },
): DatabasePool {
  return {
    on(event, listener) {
      if (event === "connect") {
        log.connectHooks.push(listener);
      }
    },
    async connect() {
      const client = {
        async query(text: string) {
          log.queries.push(text);
          return { rows: rowsFor(text), rowCount: rowsFor(text).length };
        },
        release() {},
      };
      for (const hook of log.connectHooks) {
        // Как в pg: хук получает клиента сразу после соединения; провайдер
        // обязан выставить GUC и не упасть процессом при отказе (catch).
        hook(client as unknown as PoolClient);
      }
      return client as unknown as PoolClient;
    },
    async end() {},
  };
}

function makeProvider(rowsFor: (text: string) => Record<string, unknown>[], env: Record<string, string> = {}) {
  const log = { queries: [] as string[], connectHooks: [] as ((client: PoolClient) => void)[] };
  const options: PostgresProviderOptions = { createPool: () => stubPool(rowsFor, log) };
  const provider = createPostgresProvider(
    {
      WEBAPP_TENANT_ID: TENANT,
      WEBAPP_DATA_DATABASE_URI_FILE: writeUriFile(),
      ...env,
    },
    options,
  );
  return { provider, log };
}

let uriDirs: string[] = [];

function writeUriFile(content = "postgresql://webapp:secret@127.0.0.1:1/proxima"): string {
  const dir = mkdtempSync(join(tmpdir(), "proxima-webapp-uri-"));
  uriDirs.push(dir);
  const path = join(dir, "webapp_uri");
  writeFileSync(path, content, { mode: 0o600 });
  return path;
}

afterEach(() => {
  uriDirs = [];
});

const STATUS_SQL = "data_status_current";
const BRIEF_SQL = "brief_current";
const FACT_SQL = "fact_cabinet_daily_current";

function isoDay(day: number): string {
  return `2026-08-${String(day).padStart(2, "0")}`;
}

describe("provider: tenant validation (AD-9)", () => {
  const rows = () => [];

  it(" отсутствующий WEBAPP_TENANT_ID роняет создание провайдера до всякого соединения", () => {
    expect(() =>
      createPostgresProvider({
        WEBAPP_TENANT_ID: "",
        WEBAPP_DATA_DATABASE_URI_FILE: writeUriFile(),
      }),
    ).toThrow(/WEBAPP_TENANT_ID/);
  });

  it("невалидный tenant не подходит под шаблон AD-9", () => {
    expect(() =>
      createPostgresProvider(
        { WEBAPP_TENANT_ID: "Amirova Test", WEBAPP_DATA_DATABASE_URI_FILE: writeUriFile() },
        { createPool: () => stubPool(rows, { queries: [], connectHooks: [] }) },
      ),
    ).toThrow(/не подходит/);
  });

  it("отсутствующий файл URI роняет первый запрос, имя переменной - наружу, URI - нет", async () => {
    const provider = createPostgresProvider(
      { WEBAPP_TENANT_ID: TENANT },
      { createPool: () => stubPool(rows, { queries: [], connectHooks: [] }) },
    );
    await expect(provider.getSummary()).rejects.toThrow(/WEBAPP_DATA_DATABASE_URI_FILE/);
  });
});

describe("provider: data status states (Story 1.11)", () => {
  it("не stale: строка статуса складывается из data_status_current", async () => {
    const { provider, log } = makeProvider((text) =>
      text.includes(STATUS_SQL) ? [{ ...FRESH_STATUS }] : [],
    );
    const summary = await provider.getSummary();
    expect(summary.dataStatus).toEqual({
      lastFullDay: "2026-08-29",
      collectedAt: "2026-08-30T02:41:12.000Z",
      stale: false,
    });
    expect(summary.status).toBe("no-brief"); // сводки ещё нет: режим «только статус»
    expect(log.queries.join(" ")).toContain(STATUS_SQL);
    expect(log.queries.filter((text) => !text.includes("set_config"))).toHaveLength(2); // ровно два SELECT (AD-9)
  });

  it("живой статус ушёл вперёд: вчерашняя сводка не выдаётся за свежую", async () => {
    // Ровно то, что AD-9 называет в Prevents. Раньше правило сверялось с копией
    // data_status внутри payload, а она снимается в момент записи и всегда равна
    // brief_day - сравнение было тождественно истинным, и цифры показывались.
    const payload = briefPayload();
    const { provider } = makeProvider((text) =>
      text.includes(STATUS_SQL)
        ? [{ last_full_day: "2026-08-30", collected_at: "2026-08-31T02:41:12.000Z", stale: false }]
        : [{ brief_day: payload.evaluation_day, status: "ok", payload }],
    );
    const summary = await provider.getSummary();
    expect(summary.status).toBe("stale");
    expect(summary.orders).toBeNull();
    expect(summary.revenue).toBeNull();
  });

  it("stale: предупреждение вместо цифр", async () => {
    const { provider } = makeProvider((text) =>
      text.includes(STATUS_SQL) ? [{ ...FRESH_STATUS, stale: true }] : [],
    );
    const summary = await provider.getSummary();
    expect(summary.dataStatus?.stale).toBe(true);
    expect(summary.orders).toBeNull();
    expect(summary.revenue).toBeNull();
  });

  it("пустой view: данных нет вовсе, цифр не бывает", async () => {
    const { provider } = makeProvider(() => []);
    const summary = await provider.getSummary();
    expect(summary.dataStatus).toBeNull();
    expect(summary.status).toBe("no-brief");
    expect(summary.orders).toBeNull();
  });

  it("отрисовка страницы стоит ровно двух SELECT, а не трёх (AD-9)", async () => {
    // Страница зовёт getBrief и getSummary вместе. Раньше оба читали brief_current,
    // и на одну отрисовку уходило три запроса при двух разрешённых. Признак
    // «сводки ещё нет» теперь несёт статус сводки, а не второе чтение той же строки.
    const { provider, log } = makeProvider(() => []);
    const [brief, summary] = await Promise.all([provider.getBrief("daily"), provider.getSummary()]);
    expect(log.queries.filter((text) => !text.includes("set_config"))).toHaveLength(2);
    expect(summary.status).toBe("no-brief");
    expect(brief.digest.every((entry) => entry.id !== "postgres-brief-pending")).toBe(true);
  });
});

describe("provider: brief states (Story 2.5)", () => {
  function rowsWith(payload: BriefV1, overrides: Record<string, unknown> = {}) {
    return (text: string) => {
      if (text.includes(BRIEF_SQL)) {
        return [{ brief_day: payload.evaluation_day, status: "ok", payload, ...overrides }];
      }
      return [{ ...FRESH_STATUS }];
    };
  }

  it("ok: значения, норма и отклонение проходят через шов без пересчёта", async () => {
    const threshold = { value: -30, source: "ретро-разметка Владислава", date: "2026-09-09" } as const;
    const payload = briefPayload({ threshold });
    const { provider, log } = makeProvider(rowsWith(payload));
    const summary = await provider.getSummary();
    expect(summary.status).toBe("ok");
    expect(summary.briefDay).toBe("2026-08-29");
    expect(summary.orders).toEqual({ actual: 27, norm: "34.50", deviationPct: -21.7 });
    expect(summary.revenue).toEqual({ actual: "41141.00", norm: "34595.00", deviationPct: 18.9 });
    expect(summary.normProgress).toEqual({ sampleDays: 14, windowDays: 14 });
    expect(summary.threshold).toEqual(threshold);
    expect(log.queries.join(" ")).toContain(BRIEF_SQL);
  });

  it("ok, но stale: цифры подавлены (правило показа AD-9)", async () => {
    const payload = briefPayload({ data_status: { ...briefPayload().data_status, stale: true } });
    const { provider } = makeProvider((text) => {
      if (text.includes(BRIEF_SQL)) {
        return [{ brief_day: payload.evaluation_day, status: "ok", payload }];
      }
      // View статуса тоже показывает stale: collected_at старше суток.
      return [{ last_full_day: "2026-08-29", collected_at: new Date("2026-08-28T02:41:12.000Z"), stale: true }];
    });
    const summary = await provider.getSummary();
    expect(summary.status).toBe("stale");
    expect(summary.orders).toBeNull();
    expect(summary.revenue).toBeNull();
    expect(summary.dataStatus?.stale).toBe(true);
  });

  it("ok, но день сводки уже не последний полный: цифры подавлены", async () => {
    const payload = briefPayload({
      data_status: { ...briefPayload().data_status, last_full_day: "2026-08-30" },
    });
    const { provider } = makeProvider((text) => {
      if (text.includes(BRIEF_SQL)) {
        return [{ brief_day: "2026-08-29", status: "ok", payload }];
      }
      return [
        { last_full_day: "2026-08-30", collected_at: new Date("2026-08-31T02:41:12.000Z"), stale: false },
      ];
    });
    const summary = await provider.getSummary();
    expect(summary.status).toBe("stale");
    expect(summary.orders).toBeNull();
  });

  it("insufficient: норма видна, отклонение не называется, прогресс копится", async () => {
    const payload = briefPayload({
      norm: { orders: "34.50", revenue: "34595.00", window_days: 14, sample_days: 9 },
      deviation_pct: null,
    });
    const { provider } = makeProvider((text) =>
      text.includes(BRIEF_SQL) ? [{ brief_day: payload.evaluation_day, status: "insufficient", payload }] : [{ ...FRESH_STATUS }],
    );
    const summary = await provider.getSummary();
    expect(summary.status).toBe("insufficient");
    expect(summary.orders).toBeNull();
    expect(summary.normProgress).toEqual({ sampleDays: 9, windowDays: 14 });
  });

  it("blocked: нет ни нормы, ни отклонения; фактические null в payload читаются как отсутствие", async () => {
    const payload = briefPayload({ actual: null, norm: null, deviation_pct: null, reason: "norm version missing" });
    const { provider } = makeProvider((text) =>
      text.includes(BRIEF_SQL) ? [{ brief_day: payload.evaluation_day, status: "blocked", payload }] : [{ ...FRESH_STATUS }],
    );
    const summary = await provider.getSummary();
    expect(summary.status).toBe("blocked");
    expect(summary.orders).toBeNull();
    expect(summary.revenue).toBeNull();
  });

  it("GUC tenant уходит первым statement каждого соединения (AD-13)", async () => {
    const executed: string[] = [];
    const { provider } = makeProvider((text) => {
      executed.push(text);
      return [];
    });
    await provider.getSummary();
    expect(executed[0]).toContain("set_config('proxima.tenant_id', $1, false)");
  });
});

describe("provider: signals states (Story 4.3)", () => {
  /*
   * Аномалии дня приходят из той же строки brief_current, что и сводка (AD-9: два
   * SELECT на отрисовку), и подчиняются тому же правилу показа: список непуст
   * только при `status = ok` и свежих данных; порядок строк = порядок `signals[]`.
   */
  const SIGNALS = [...FIXTURE_BRIEF_SIGNALS];

  function rowsWith(payload: BriefV1, status = "ok", statusRow: Record<string, unknown> = FRESH_STATUS) {
    return (text: string) =>
      text.includes(BRIEF_SQL) ? [{ brief_day: payload.evaluation_day, status, payload }] : [{ ...statusRow }];
  }

  it("ok с сигналами: строки в порядке signals[] (деньги по убыванию, Story 4.2), без пересчёта", async () => {
    const payload = briefPayload({ signals: SIGNALS });
    const { provider, log } = makeProvider(rowsWith(payload));
    const summary = await provider.getSummary();
    expect(summary.status).toBe("ok");
    expect(summary.anomalies.map((anomaly) => anomaly.id)).toEqual(SIGNALS.map((signal) => signal.signal_id));
    expect(summary.anomalies.map((anomaly) => anomaly.moneyAtRisk)).toEqual(
      SIGNALS.map((signal) => signal.rub_assessment?.value_rub ?? null),
    );
    const [subject, sku] = summary.anomalies;
    expect(subject).toMatchObject({ level: "subject", subjectName: "Платье", skuCount: 2, nmId: null, scenarioCode: "SCN-001" });
    expect(sku).toMatchObject({ level: "sku", nmId: 2002, supplierArticle: "fixture-art-2002", subjectName: "Платье" });
    expect(sku?.orders).toEqual({ actual: 12, norm: "20.00", deviationPct: -40 });
    expect(sku?.revenue).toEqual({ actual: "1200.00", norm: "2000.00", deviationPct: -40 });
    expect(sku?.sourceRefs).toEqual(SIGNALS[1]?.source_refs);
    // UNKNOWN категория (D32) доходит до экрана как null, а не как пустая строка или выдуманный предмет.
    const unknown = summary.anomalies.find((anomaly) => anomaly.id === "fixture-signal-sku-2006-unknown-subject");
    expect(unknown).toMatchObject({ level: "sku", nmId: 2006, subjectName: null, supplierArticle: null });
    // Сводка не изменилась от присутствия сигналов, и SELECT по-прежнему два.
    expect(summary.orders).toEqual({ actual: 27, norm: "34.50", deviationPct: -21.7 });
    expect(log.queries.filter((text) => !text.includes("set_config"))).toHaveLength(2);
  });

  it("ok пусто: статус ok, аномалий нет - экран скажет «критичных нет»", async () => {
    const payload = briefPayload({ signals: [] });
    const { provider } = makeProvider(rowsWith(payload));
    const summary = await provider.getSummary();
    expect(summary.status).toBe("ok");
    expect(summary.anomalies).toEqual([]);
  });

  it("insufficient: аномалий нет, прогресс нормы известен - «норма копится: 9/14 дней»", async () => {
    const payload = briefPayload({
      norm: { orders: "34.50", revenue: "34595.00", window_days: 14, sample_days: 9 },
      deviation_pct: null,
      signals: [],
    });
    const { provider } = makeProvider(rowsWith(payload, "insufficient"));
    const summary = await provider.getSummary();
    expect(summary.status).toBe("insufficient");
    expect(summary.anomalies).toEqual([]);
    expect(summary.normProgress).toEqual({ sampleDays: 9, windowDays: 14 });
  });

  it("blocked: нет версии за evaluation_day (Story 2.4) - аномалий нет, причина в статусе", async () => {
    const payload = briefPayload({ actual: null, norm: null, deviation_pct: null, signals: [], reason: "no fact version for evaluation_day" });
    const { provider } = makeProvider(rowsWith(payload, "blocked"));
    const summary = await provider.getSummary();
    expect(summary.status).toBe("blocked");
    expect(summary.anomalies).toEqual([]);
    expect(summary.normProgress).toBeNull();
  });

  it("ok, но stale: сигналы в payload есть, на экран не попадают (правило AD-9 общее с цифрами)", async () => {
    const payload = briefPayload({ signals: SIGNALS });
    const { provider } = makeProvider(rowsWith(payload, "ok", { ...FRESH_STATUS, stale: true }));
    const summary = await provider.getSummary();
    expect(summary.status).toBe("stale");
    expect(summary.anomalies).toEqual([]);
  });

  it("сигналы не ok-статуса игнорируются даже если писатель их оставил (PRD FR-7, fail-closed)", async () => {
    const payload = briefPayload({
      norm: { orders: "34.50", revenue: "34595.00", window_days: 14, sample_days: 9 },
      deviation_pct: null,
      signals: SIGNALS,
    });
    const { provider } = makeProvider(rowsWith(payload, "insufficient"));
    const summary = await provider.getSummary();
    expect(summary.anomalies).toEqual([]);
  });

  it("режим «только статус» (no-brief): список пуст", async () => {
    const { provider } = makeProvider((text) => (text.includes(STATUS_SQL) ? [{ ...FRESH_STATUS }] : []));
    const summary = await provider.getSummary();
    expect(summary.status).toBe("no-brief");
    expect(summary.anomalies).toEqual([]);
  });
});

describe("provider: dashboard metrics (D36 C3)", () => {
  it("полный ряд: значения последнего дня, дельта к 7 предыдущим и 30 точек по порядку", async () => {
    const facts = Array.from({ length: 30 }, (_, index) => ({
      calendar_day: isoDay(index + 1),
      orders_count: index + 1,
      revenue_rub: `${index + 1}.00`,
    }));
    const { provider, log } = makeProvider((text) => {
      if (text.includes(STATUS_SQL)) {
        return [{ last_full_day: "2026-08-30", collected_at: "2026-08-30T03:12:45.000Z", stale: false }];
      }
      return text.includes(FACT_SQL) ? facts : [];
    });

    const metrics = await provider.getMetrics();
    expect(metrics.find((metric) => metric.id === "orders-day")).toMatchObject({
      value: 30,
      deltaPercent: 15.4,
      deltaGoodWhen: "up",
      points: Array.from({ length: 30 }, (_, index) => index + 1),
      fx: false,
    });
    expect(metrics.find((metric) => metric.id === "revenue-day")).toMatchObject({
      value: 30,
      deltaPercent: 15.4,
      points: Array.from({ length: 30 }, (_, index) => index + 1),
      fx: false,
    });
    expect(metrics.find((metric) => metric.id === "freshness")).toMatchObject({ value: 6 * 60 + 12, status: "green" });
    expect(log.queries.filter((text) => !text.includes("set_config"))).toHaveLength(2);
    expect(log.queries.join(" ")).not.toContain("fact_nm_daily");
  });

  it("пропуски календаря скрывают неполный sparkline и неполную семидневную дельту", async () => {
    const { provider } = makeProvider((text) => {
      if (text.includes(STATUS_SQL)) {
        return [{ last_full_day: "2026-08-30", collected_at: "2026-08-30T03:12:00.000Z", stale: false }];
      }
      return text.includes(FACT_SQL)
        ? [
            { calendar_day: "2026-08-23", orders_count: 10, revenue_rub: "10.10" },
            { calendar_day: "2026-08-27", orders_count: 20, revenue_rub: "20.20" },
            { calendar_day: "2026-08-30", orders_count: 30, revenue_rub: "30.30" },
          ]
        : [];
    });

    const metrics = await provider.getMetrics();
    const orders = metrics.find((metric) => metric.id === "orders-day");
    const revenue = metrics.find((metric) => metric.id === "revenue-day");
    expect(orders?.points).toEqual([]);
    expect(orders?.deltaPercent).toBeNull();
    expect(revenue?.points).toEqual([]);
    expect(revenue?.deltaPercent).toBeNull();
    expect(orders?.value).toBe(30);
  });

  it("копейки участвуют в дельте до округления значения для UI", async () => {
    const { provider } = makeProvider((text) => {
      if (text.includes(STATUS_SQL)) {
        return [{ last_full_day: "2026-08-30", collected_at: "2026-08-30T03:12:00.000Z", stale: false }];
      }
      return text.includes(FACT_SQL)
        ? [
            ...Array.from({length:7},(_,i)=>({calendar_day:`2026-08-${23+i}`,orders_count:1,revenue_rub:"0.01"})),
            { calendar_day: "2026-08-30", orders_count: 1, revenue_rub: "0.02" },
          ]
        : [];
    });
    const revenue = (await provider.getMetrics()).find((metric) => metric.id === "revenue-day");
    expect(revenue).toMatchObject({ value: 0, deltaPercent: 100 });
  });

  it("полный ряд реальных нулей остаётся данными", async () => {
    const {provider}=makeProvider(text=>text.includes(STATUS_SQL)?[{last_full_day:"2026-08-30",collected_at:"2026-08-30T03:12:00Z",stale:false}]:text.includes(FACT_SQL)?Array.from({length:30},(_,i)=>({calendar_day:isoDay(i+1),orders_count:0,revenue_rub:"0.00"})):[]);
    const metric=(await provider.getMetrics()).find(m=>m.id==="orders-day");
    expect(metric?.value).toBe(0);expect(metric?.points).toEqual(Array(30).fill(0));expect(metric?.deltaPercent).toBeNull();
  });

  it("stale=true окрашивает freshness в red", async () => {
    const { provider } = makeProvider((text) =>
      text.includes(STATUS_SQL)
        ? [{ last_full_day: "2026-08-30", collected_at: "2026-08-30T23:59:00.000Z", stale: true }]
        : [],
    );
    const freshness = (await provider.getMetrics()).find((metric) => metric.id === "freshness");
    expect(freshness).toMatchObject({ value: 2 * 60 + 59, status: "red", points: [], deltaPercent: null });
  });

  it("без data_status_current возвращает пять null-карточек и не читает факты", async () => {
    const { provider, log } = makeProvider(() => []);
    const metrics = await provider.getMetrics();
    expect(metrics).toHaveLength(5);
    expect(metrics.every((metric) => metric.value === null)).toBe(true);
    expect(log.queries.filter((text) => !text.includes("set_config"))).toHaveLength(1);
    expect(log.queries.join(" ")).not.toContain(FACT_SQL);
  });
});

describe("deviationGyr - цвет по знаку через lib/gyr", () => {
  it("минус - красное падение, плюс - зелёный рост, ноль и «нет отклонения» - нейтральное", () => {
    expect(deviationGyr(-21.7)).toBe("red");
    expect(deviationGyr(18.9)).toBe("green");
    expect(deviationGyr(0)).toBe("neutral");
    expect(deviationGyr(null)).toBe("neutral");
  });
});
