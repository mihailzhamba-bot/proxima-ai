import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { createFixturesProvider } from "@/lib/data/fixtures-provider";
import {
  createPostgresProvider,
  type DatabasePool,
} from "@/lib/data/postgres-provider";
import { DATA_MODE_ENV, getDataProvider, resetDataProvider, resolveDataMode } from "@/lib/data";
import { register } from "@/instrumentation";

/*
 * Шов PA-50 (критерий приёмки №3): источник данных меняется конфигом,
 * а не правкой компонентов. Тест держит именно контракт шва, не разметку.
 */

const stubPool = (): DatabasePool => ({
  on() {},
  async connect() {
    throw new Error("stub pool must not connect");
  },
  async end() {},
});

function postgresEnv(): Record<string, string> {
  const dir = mkdtempSync(join(tmpdir(), "proxima-webapp-test-"));
  const path = join(dir, "webapp_uri");
  writeFileSync(path, "postgresql://webapp:secret@127.0.0.1:1/proxima", { mode: 0o600 });
  return { WEBAPP_TENANT_ID: "pilot-tenant", WEBAPP_DATA_DATABASE_URI_FILE: path };
}

afterEach(() => {
  delete process.env[DATA_MODE_ENV];
  delete process.env.WEBAPP_TENANT_ID;
  resetDataProvider();
});

describe("resolveDataMode — режим данных из окружения", () => {
  it("по умолчанию fixtures: без переменной кабинет остаётся демонстрационным", () => {
    expect(resolveDataMode({})).toBe("fixtures");
    expect(resolveDataMode({ [DATA_MODE_ENV]: "" })).toBe("fixtures");
  });

  it("оба режима читаются явно", () => {
    expect(resolveDataMode({ [DATA_MODE_ENV]: "fixtures" })).toBe("fixtures");
    expect(resolveDataMode({ [DATA_MODE_ENV]: "postgres" })).toBe("postgres");
  });

  it("неизвестное значение — ошибка, а не молчаливый откат на fixtures", () => {
    expect(() => resolveDataMode({ [DATA_MODE_ENV]: "staging" })).toThrow(/не поддерживается/);
  });
});

describe("getDataProvider — выбор провайдера", () => {
  it("режим fixtures отдаёт fixtures-провайдер", () => {
    process.env[DATA_MODE_ENV] = "fixtures";
    resetDataProvider();
    expect(getDataProvider().mode).toBe("fixtures");
  });

  it("режим postgres отдаёт postgres-провайдер без правки вызывающего кода", () => {
    process.env[DATA_MODE_ENV] = "postgres";
    process.env.WEBAPP_TENANT_ID = "pilot-tenant";
    resetDataProvider();
    expect(getDataProvider().mode).toBe("postgres");
  });

  it("неизвестный режим через process.env роняет получение провайдера", () => {
    process.env[DATA_MODE_ENV] = "postgress";
    resetDataProvider();
    expect(() => getDataProvider()).toThrow(/не поддерживается/);
  });

  it("провайдер кэшируется на процесс: режим — свойство деплоя", () => {
    process.env[DATA_MODE_ENV] = "fixtures";
    resetDataProvider();
    expect(getDataProvider()).toBe(getDataProvider());
  });
});

describe("instrumentation register — валидация при старте", () => {
  it("неизвестный режим останавливает старт server runtime", () => {
    process.env[DATA_MODE_ENV] = "staging";
    expect(() => register()).toThrow(/не поддерживается/);
  });

  it("пустой и допустимые режимы проходят без ошибки", () => {
    expect(() => register()).not.toThrow();
    process.env[DATA_MODE_ENV] = "fixtures";
    expect(() => register()).not.toThrow();
    process.env[DATA_MODE_ENV] = "postgres";
    expect(() => register()).not.toThrow();
  });
});

describe("fixtures-провайдер — форма данных стабильна", () => {
  it("бриф приходит через тот же контракт, что ждёт UI", async () => {
    const brief = await createFixturesProvider().getBrief("daily");
    expect(brief.dataMode).toBe("fixtures");
    expect(brief.signals.length).toBeGreaterThan(0);
  });

  it("тихий вариант проходит через провайдер без критичных", async () => {
    const brief = await createFixturesProvider().getBrief("quiet");
    expect(brief.signals).toHaveLength(0);
  });

  it("метрики приходят списком", async () => {
    const metrics = await createFixturesProvider().getMetrics();
    expect(metrics.length).toBe(5);
  });

  it("метрики дашборда поддерживаются: шелл рисует полосу", () => {
    expect(createFixturesProvider().supportsMetrics).toBe(true);
  });
});

describe("postgres-провайдер — сводка и метрики по AD-9", () => {
  it("создание без tenant роняется явно: конфиг не может притвориться поднявшимся webapp", () => {
    expect(() => createPostgresProvider({}, { createPool: stubPool })).toThrow(/WEBAPP_TENANT_ID/);
  });

  it("метрики дашборда поддерживаются обоими провайдерами", () => {
    const provider = createPostgresProvider(postgresEnv(), { createPool: stubPool });
    expect(provider.supportsMetrics).toBe(true);
    expect(createFixturesProvider().supportsMetrics).toBe(true);
  });

  it("сводка требует файл URI: без него первый запрос падает с именем переменной", async () => {
    const provider = createPostgresProvider({ WEBAPP_TENANT_ID: "pilot-tenant" }, { createPool: stubPool });
    await expect(provider.getSummary()).rejects.toThrow(/WEBAPP_DATA_DATABASE_URI_FILE/);
  });
});
