import { afterEach, describe, expect, it } from "vitest";
import { createFixturesProvider } from "@/lib/data/fixtures-provider";
import { createPostgresProvider, POSTGRES_PROVIDER_NOT_IMPLEMENTED } from "@/lib/data/postgres-provider";
import { DATA_MODE_ENV, getDataProvider, resetDataProvider, resolveDataMode } from "@/lib/data";
import { register } from "@/instrumentation";

/*
 * Шов PA-50 (критерий приёмки №3): источник данных меняется конфигом,
 * а не правкой компонентов. Тест держит именно контракт шва, не разметку.
 */

afterEach(() => {
  delete process.env[DATA_MODE_ENV];
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
});

describe("postgres-провайдер — fail-closed до PMM-29 и роли webapp_readonly", () => {
  it("бриф не подменяется пустым экраном, а падает явно", async () => {
    await expect(createPostgresProvider().getBrief("daily")).rejects.toThrow(POSTGRES_PROVIDER_NOT_IMPLEMENTED);
  });

  it("метрики ведут себя так же", async () => {
    await expect(createPostgresProvider().getMetrics()).rejects.toThrow(POSTGRES_PROVIDER_NOT_IMPLEMENTED);
  });
});
