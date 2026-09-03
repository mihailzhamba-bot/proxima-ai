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
    const payload = briefPayload();
    const { provider, log } = makeProvider(rowsWith(payload));
    const summary = await provider.getSummary();
    expect(summary.status).toBe("ok");
    expect(summary.briefDay).toBe("2026-08-29");
    expect(summary.orders).toEqual({ actual: 27, norm: "34.50", deviationPct: -21.7 });
    expect(summary.revenue).toEqual({ actual: "41141.00", norm: "34595.00", deviationPct: 18.9 });
    expect(summary.normProgress).toEqual({ sampleDays: 14, windowDays: 14 });
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

describe("deviationGyr - цвет по знаку через lib/gyr", () => {
  it("минус - красное падение, плюс - зелёный рост, ноль и «нет отклонения» - нейтральное", () => {
    expect(deviationGyr(-21.7)).toBe("red");
    expect(deviationGyr(18.9)).toBe("green");
    expect(deviationGyr(0)).toBe("neutral");
    expect(deviationGyr(null)).toBe("neutral");
  });
});
