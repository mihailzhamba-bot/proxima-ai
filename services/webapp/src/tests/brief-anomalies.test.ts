import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AnomaliesBlock, BLOCKED_TEXT, NO_ANOMALIES_TEXT } from "@/components/brief/anomalies";
import { AnomalyRow, UNKNOWN_SUBJECT_LABEL, anomalyTitle, headlineDeviation } from "@/components/brief/anomaly-row";
import type { SignalV1 } from "@/lib/contracts/signal";
import { anomaliesFromSignals, anomalyFromSignal } from "@/lib/data/anomalies";
import type { BriefAnomaly, BriefSummary } from "@/lib/data/view-model";
import { FIXTURE_BRIEF_SIGNALS, getSummary } from "@/lib/fixtures/brief";

/*
 * Story 4.3: блок «Аномалии» на /brief. Рендер - серверная разметка без DOM
 * (react-dom/server, без новых зависимостей): проверяется содержание и порядок
 * строк, а не пиксели. Маппинг проводного сигнала в строку экрана - отдельно.
 */

const SIGNALS = FIXTURE_BRIEF_SIGNALS;

function summaryWith(overrides: Partial<BriefSummary>): BriefSummary {
  return { ...getSummary(), ...overrides };
}

function render(summary: BriefSummary, demo = false): string {
  return renderToStaticMarkup(createElement(AnomaliesBlock, { summary, demo }));
}

function rowIds(markup: string): string[] {
  return [...markup.matchAll(/data-signal-id="([^"]+)"/g)].map((match) => match[1] ?? "");
}

/** Разметка секции с учётом вложенных <section> (карточка строки содержит «Источники»). */
function sectionMarkup(markup: string, label: string): string {
  const start = markup.indexOf(`<section aria-label="${label}"`);
  expect(start).toBeGreaterThanOrEqual(0);
  const tags = /<section\b|<\/section>/g;
  tags.lastIndex = start;
  let depth = 0;
  for (let match = tags.exec(markup); match !== null; match = tags.exec(markup)) {
    depth += match[0] === "</section>" ? -1 : 1;
    if (depth === 0) {
      return markup.slice(start, match.index);
    }
  }
  throw new Error(`unbalanced <section> for ${label}`);
}

function signalWith(overrides: Partial<SignalV1>, detection: SignalV1["detection_data"] = {}): SignalV1 {
  const base = SIGNALS[1]!;
  return { ...base, ...overrides, detection_data: { ...base.detection_data, ...detection } };
}

describe("anomaliesFromSignals - проводной сигнал в строку экрана без арифметики", () => {
  it("порядок и состав: одна строка на сигнал, порядок signals[] сохраняется", () => {
    const anomalies = anomaliesFromSignals(SIGNALS);
    expect(anomalies.map((anomaly) => anomaly.id)).toEqual(SIGNALS.map((signal) => signal.signal_id));
    expect(anomalies.map((anomaly) => anomaly.moneyAtRisk)).toEqual(SIGNALS.map((signal) => signal.rub_assessment?.value_rub));
  });

  it("SKU: nmId, артикул, предмет, метрики и triggered_by читаются из detection_data (AD-19)", () => {
    const anomaly = anomalyFromSignal(SIGNALS[1]!);
    expect(anomaly).toMatchObject({
      level: "sku",
      nmId: 2002,
      supplierArticle: "fixture-art-2002",
      subjectName: "Платье",
      skuCount: 1,
      triggeredBy: ["orders", "revenue"],
      moneyAtRisk: "800.00",
      moneyMethod: "revenue",
      thresholdPct: null,
      scenarioCode: "SCN-001",
      trust: "unreleased",
    });
    expect(anomaly.orders).toEqual({ actual: 12, norm: "20.00", deviationPct: -40 });
    expect(anomaly.revenue).toEqual({ actual: "1200.00", norm: "2000.00", deviationPct: -40 });
    expect(anomaly.sourceRefs).toEqual(SIGNALS[1]!.source_refs);
  });

  it("категория: предмет и число SKU, nmId и артикула нет", () => {
    const anomaly = anomalyFromSignal(SIGNALS[0]!);
    expect(anomaly).toMatchObject({ level: "subject", subjectName: "Платье", skuCount: 2, nmId: null, supplierArticle: null });
  });

  it("is_unknown, отсутствующий ключ и чужой тип - null, а не выдуманное значение", () => {
    const anomaly = anomalyFromSignal(
      signalWith(
        {},
        {
          subject_name: { value: null, is_unknown: true },
          supplier_article: { value: 42, is_unknown: false },
          orders_deviation_pct: { value: "−40", is_unknown: false },
          revenue_norm_median: { value: "2000", is_unknown: false },
          sku_count: { value: 1.5, is_unknown: false },
        },
      ),
    );
    expect(anomaly.subjectName).toBeNull();
    expect(anomaly.supplierArticle).toBeNull();
    expect(anomaly.orders?.deviationPct).toBeNull();
    expect(anomaly.revenue?.norm).toBeNull();
    expect(anomaly.skuCount).toBeNull();
  });

  it("без факта дня метрика null; без rub_assessment денег нет; порог из detection_data", () => {
    const anomaly = anomalyFromSignal(
      signalWith(
        { rub_assessment: null },
        {
          orders_actual: { value: null, is_unknown: true },
          threshold_pct: { value: -30, is_unknown: false },
          triggered_by: { value: ["revenue", "growth"], is_unknown: false },
        },
      ),
    );
    expect(anomaly.orders).toBeNull();
    expect(anomaly.moneyAtRisk).toBeNull();
    expect(anomaly.moneyMethod).toBeNull();
    expect(anomaly.thresholdPct).toBe(-30);
    expect(anomaly.triggeredBy).toEqual(["revenue"]);
  });

  it("уровень без ключа level: nmId есть - SKU, нет - категория", () => {
    const withNm = anomalyFromSignal(signalWith({}, { level: { value: null, is_unknown: true } }));
    expect(withNm.level).toBe("sku");
    const withoutNm = anomalyFromSignal(
      signalWith({}, { level: { value: null, is_unknown: true }, nm_id: { value: null, is_unknown: true } }),
    );
    expect(withoutNm.level).toBe("subject");
  });
});

describe("AnomalyRow - свёрнутая строка и раскрытие", () => {
  const anomalies = anomaliesFromSignals(SIGNALS);

  it("заголовок: nmId · артикул · категория у SKU; предмет · N SKU у категории; UNKNOWN явно", () => {
    expect(anomalyTitle(anomalies[1]!)).toBe("2002 · fixture-art-2002 · Платье");
    expect(anomalyTitle(anomalies[0]!)).toBe("Платье · 2 SKU");
    expect(anomalyTitle(anomalies[4]!)).toBe(`2006 · ${UNKNOWN_SUBJECT_LABEL}`);
  });

  it("отклонение строки - самое глубокое из падений triggered_by; рост не выбирается", () => {
    expect(headlineDeviation(anomalies[1]!)).toEqual({ metric: "orders", pct: -40 });
    // 2003: заказы −12.5 %, выручка +12.5 % - в строке падение заказов.
    expect(headlineDeviation(anomalies[5]!)).toEqual({ metric: "orders", pct: -12.5 });
    const noDeviation: BriefAnomaly = { ...anomalies[1]!, orders: null, revenue: null, triggeredBy: [] };
    expect(headlineDeviation(noDeviation)).toBeNull();
  });

  it("без раскрытия: nmId, категория, отклонение %, scenario_code, ₽; source_refs - по раскрытию", () => {
    const markup = renderToStaticMarkup(createElement(AnomalyRow, { anomaly: anomalies[1]! }));
    const summaryEnd = markup.indexOf("</summary>");
    const collapsed = markup.slice(0, summaryEnd);
    const expanded = markup.slice(summaryEnd);
    expect(collapsed).toContain("2002");
    expect(collapsed).toContain("fixture-art-2002");
    expect(collapsed).toContain("Платье");
    expect(collapsed).toContain("−40,0");
    expect(collapsed).toContain("SCN-001");
    expect(collapsed).toContain("800");
    expect(collapsed).not.toContain("table://fact_nm_daily/nm/2002");
    for (const ref of anomalies[1]!.sourceRefs) {
      expect(expanded).toContain(ref.replace(/\//g, "/"));
    }
    expect(expanded).toContain("не применяется"); // порог Story 4.2 ещё null
  });

  it("FX-бейдж только у демо-цифр (ADR-0004)", () => {
    const live = renderToStaticMarkup(createElement(AnomalyRow, { anomaly: anomalies[1]! }));
    const demo = renderToStaticMarkup(createElement(AnomalyRow, { anomaly: anomalies[1]!, demo: true }));
    expect(live).not.toContain(">FX<");
    expect(demo).toContain(">FX<");
  });

  it("деньги под риском со знаком: отрицательная оценка (D32) не обрезается", () => {
    const markup = renderToStaticMarkup(createElement(AnomalyRow, { anomaly: anomalies[5]! }));
    expect(markup).toContain("-100");
    expect(markup).toContain("+12,5"); // рост выручки показан числом (PRD FR-34)
  });
});

describe("AnomaliesBlock - состояния блока на /brief", () => {
  it("ok с сигналами: порядок строк = порядок signals[] (деньги по убыванию)", () => {
    const markup = render(summaryWith({ status: "ok", anomalies: anomaliesFromSignals(SIGNALS) }));
    const skuIds = rowIds(sectionMarkup(markup, "Аномалии по SKU"));
    const subjectIds = rowIds(sectionMarkup(markup, "Аномалии по категориям"));
    const expectedSku = SIGNALS.filter((s) => s.detection_data.level?.value === "sku").map((s) => s.signal_id);
    const expectedSubject = SIGNALS.filter((s) => s.detection_data.level?.value === "subject").map((s) => s.signal_id);
    expect(skuIds).toEqual(expectedSku);
    expect(subjectIds).toEqual(expectedSubject);
    expect(skuIds.length + subjectIds.length).toBe(SIGNALS.length);
  });

  it("раздел категорий - только предметные строки, с числом SKU", () => {
    const markup = render(summaryWith({ status: "ok", anomalies: anomaliesFromSignals(SIGNALS) }));
    const subjects = sectionMarkup(markup, "Аномалии по категориям");
    expect(subjects).toContain("Платье");
    expect(subjects).toContain("2 SKU");
    expect(subjects).toContain("Юбка");
    expect(subjects).not.toContain("fixture-art-");
  });

  it("категория UNKNOWN показана явно", () => {
    const markup = render(summaryWith({ status: "ok", anomalies: anomaliesFromSignals(SIGNALS) }));
    const sku = sectionMarkup(markup, "Аномалии по SKU");
    expect(sku).toContain(UNKNOWN_SUBJECT_LABEL);
    expect(sku).toContain("2006");
  });

  it("ok пусто: «критичных нет», строк нет", () => {
    const markup = render(summaryWith({ status: "ok", anomalies: [] }));
    expect(markup).toContain(NO_ANOMALIES_TEXT);
    expect(rowIds(markup)).toEqual([]);
    expect(markup).toContain("Порог тревоги не применяется");
  });

  it("подпись порога читает значение, источник и дату из payload view-model", () => {
    const markup = render(
      summaryWith({
        status: "ok",
        anomalies: [],
        threshold: { value: -30, source: "ретро-разметка Владислава", date: "2026-09-09" },
      }),
    );
    expect(markup).toContain("Порог тревоги");
    expect(markup).toContain("-30 %");
    expect(markup).toContain("источник ретро-разметка Владислава");
    expect(markup).toContain("дата <time dateTime=\"2026-09-09\">2026-09-09</time>");
  });

  it("insufficient: «норма копится: N/14 дней», строк нет", () => {
    const markup = render(
      summaryWith({ status: "insufficient", anomalies: [], normProgress: { sampleDays: 9, windowDays: 14 } }),
    );
    expect(markup).toContain("Норма копится: 9/14 дней");
    expect(rowIds(markup)).toEqual([]);
  });

  it("blocked: блок скрыт, причина «данных за день нет»", () => {
    const markup = render(summaryWith({ status: "blocked", anomalies: [], normProgress: null }));
    expect(markup).toContain(BLOCKED_TEXT);
    expect(markup).not.toContain('aria-label="Аномалии"');
    expect(rowIds(markup)).toEqual([]);
  });

  it("stale при свежем сборе и несовпадении дней: показывает дни сводки и данных", () => {
    const markup = render(
      summaryWith({
        status: "stale",
        briefDay: "2026-09-06",
        dataStatus: { lastFullDay: "2026-09-07", collectedAt: "2026-09-08T00:10:00.000Z", stale: false },
        anomalies: [],
      }),
    );
    expect(markup).toContain("Сводка за 06.09, данные уже за 07.09");
    expect(rowIds(markup)).toEqual([]);
  });

  it("stale: предупреждение сводки вместо строк; no-brief: блока нет", () => {
    expect(render(summaryWith({ status: "stale", anomalies: [] }))).toContain("Сбор не проходил больше суток");
    expect(render(summaryWith({ status: "no-brief", anomalies: [] }))).toBe("");
  });

  it("status != ok: строки не рисуются, даже если список непуст", () => {
    for (const status of ["insufficient", "blocked", "stale", "no-brief"] as const) {
      const markup = render(summaryWith({ status, anomalies: anomaliesFromSignals(SIGNALS) }));
      expect(rowIds(markup), status).toEqual([]);
    }
  });

  it("fixtures-образец: daily с аномалиями и FX, quiet - «критичных нет»", () => {
    expect(getSummary("daily").anomalies).toHaveLength(SIGNALS.length);
    expect(render(getSummary("daily"), true)).toContain(">FX<");
    expect(render(getSummary("quiet"), true)).toContain(NO_ANOMALIES_TEXT);
  });
});
