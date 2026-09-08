import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MetricStrip } from "@/components/metrics/metric-strip";
import { DATA_MODE_ENV, resetDataProvider } from "@/lib/data";
import { createFixturesProvider } from "@/lib/data/fixtures-provider";
import { createPostgresProvider, type DatabasePool } from "@/lib/data/postgres-provider";
import type { DataProvider } from "@/lib/data/provider";
import { getMetrics } from "@/lib/fixtures/metrics";

/*
 * Полоса метрик шелла и источник без метрик. Баг репетиционного стенда 08.09:
 * в WEBAPP_DATA_MODE=postgres layout звал getMetrics(), провайдер отвечал
 * NOT_IMPLEMENTED, и каждая страница шелла отдавала 500. Асинхронный серверный
 * компонент вызывается как функция (react-dom/server async-компоненты не рендерит),
 * результат - разметка без DOM, как в brief-anomalies.test.
 */

const stubPool = (): DatabasePool => ({
  on() {},
  async connect() {
    throw new Error("stub pool must not connect");
  },
  async end() {},
});

/** Провайдер без метрик, считающий вызовы getMetrics(): полоса не должна звать его вовсе. */
function providerWithoutMetrics(calls: { getMetrics: number }): DataProvider {
  return {
    mode: "postgres",
    supportsMetrics: false,
    getBrief: () => Promise.reject(new Error("not used by the strip")),
    getSummary: () => Promise.reject(new Error("not used by the strip")),
    getMetrics: () => {
      calls.getMetrics += 1;
      return Promise.reject(new Error("must not be called when supportsMetrics is false"));
    },
  };
}

async function render(provider?: DataProvider): Promise<string> {
  const element = await (provider === undefined ? MetricStrip() : MetricStrip({ provider }));
  return element === null ? "" : renderToStaticMarkup(element);
}

beforeEach(() => {
  delete process.env[DATA_MODE_ENV];
  resetDataProvider();
});

afterEach(() => {
  delete process.env[DATA_MODE_ENV];
  delete process.env.WEBAPP_TENANT_ID;
  resetDataProvider();
});

describe("MetricStrip - источник без метрик", () => {
  it("supportsMetrics = false: полосы нет (null), getMetrics() не вызывается", async () => {
    const calls = { getMetrics: 0 };
    expect(await MetricStrip({ provider: providerWithoutMetrics(calls) })).toBeNull();
    expect(calls.getMetrics).toBe(0);
  });

  it("настоящий postgres-провайдер: полосы нет и ошибки NOT_IMPLEMENTED нет", async () => {
    const provider = createPostgresProvider({ WEBAPP_TENANT_ID: "amirova-test" }, { createPool: stubPool });
    expect(await MetricStrip({ provider })).toBeNull();
  });

  it("режим postgres через getDataProvider(): шелл без полосы, без 500", async () => {
    process.env[DATA_MODE_ENV] = "postgres";
    process.env.WEBAPP_TENANT_ID = "amirova-test";
    resetDataProvider();
    expect(await MetricStrip()).toBeNull();
  });
});

describe("MetricStrip - fixtures-провайдер", () => {
  it("рисует свитчер кабинета и все пять карточек", async () => {
    const markup = await render(createFixturesProvider());
    expect(markup).toContain('aria-label="Показатели кабинета"');
    expect(markup).toContain('data-testid="cabinet-switcher"');
    for (const metric of getMetrics()) {
      expect(markup, metric.id).toContain(metric.label);
    }
  });

  it("без пропсов берёт провайдер по WEBAPP_DATA_MODE: разметка та же, что и с fixtures явно", async () => {
    expect(await render()).toBe(await render(createFixturesProvider()));
    expect(await render()).not.toBe("");
  });
});
