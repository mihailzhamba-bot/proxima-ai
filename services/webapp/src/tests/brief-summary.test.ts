import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { BRIEF_PENDING_TEXT, BriefSummaryBlock, numbersWarning } from "@/components/brief/brief-summary";
import type { BriefSummary } from "@/lib/data/view-model";
import { getSummary } from "@/lib/fixtures/brief";

/*
 * Блок «вчера против нормы» и состояние «сводки ещё нет» (no-brief). Замечание
 * ревью готовности 1.14: при свежем сборе без строки в brief_current блок писал
 * «Сбор не проходил больше суток» и тут же «Данные до …». Рендер - серверная
 * разметка без DOM, как в brief-anomalies.test.
 */

const STALE_TEXT = "Сбор не проходил больше суток";
const FRESH = { lastFullDay: "2026-09-07", collectedAt: "2026-09-08T00:10:00.000Z", stale: false };
const STALE = { ...FRESH, stale: true };

/** Ровно то, что отдаёт postgres-провайдер, пока строки в brief_current нет (режим «только статус»). */
function noBrief(dataStatus: BriefSummary["dataStatus"]): BriefSummary {
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

function render(summary: BriefSummary): string {
  return renderToStaticMarkup(createElement(BriefSummaryBlock, { summary }));
}

describe("numbersWarning - текст вместо цифр", () => {
  it("blocked: данных за день нет независимо от статуса сбора", () => {
    expect(numbersWarning("blocked", null, FRESH, "2026-09-07")).toBe("Данных за день нет");
    expect(numbersWarning("blocked", null, null, "2026-09-07")).toBe("Данных за день нет");
  });

  it("stale при свежем сборе и несовпадении дней: называет обе даты", () => {
    expect(numbersWarning("stale", null, FRESH, "2026-09-06")).toBe("Сводка за 06.09, данные уже за 07.09");
  });

  it("stale при stale или пустом статусе данных: сбор не проходил больше суток", () => {
    expect(numbersWarning("stale", null, STALE, "2026-09-06")).toBe(STALE_TEXT);
    expect(numbersWarning("stale", null, null, "2026-09-06")).toBe(STALE_TEXT);
  });

  it("сводки нет, сбор свежий: «сводка ещё не считается», а не «сбор не проходил»", () => {
    expect(numbersWarning("no-brief", null, FRESH)).toBe(BRIEF_PENDING_TEXT);
  });

  it("сводки нет и сбора нет (пустой view) или он stale: по-прежнему «сбор не проходил» (AC 1.11)", () => {
    expect(numbersWarning("no-brief", null, null)).toBe(STALE_TEXT);
    expect(numbersWarning("no-brief", null, STALE)).toBe(STALE_TEXT);
  });

  it("insufficient: прогресс нормы независимо от статуса данных", () => {
    expect(numbersWarning("insufficient", { sampleDays: 9, windowDays: 14 }, FRESH)).toBe("Норма копится: 9/14 дней");
    expect(numbersWarning("insufficient", null, null)).toBe("Норма копится: окно неполное");
  });

  it("короткая форма не повторяет предложение дайджеста «ждём первый утренний прогон»", () => {
    expect(BRIEF_PENDING_TEXT).not.toContain("ждём");
  });
});

describe("BriefSummaryBlock - состояния блока", () => {
  it("no-brief при свежем сборе: пометка «сводка ещё не считается» и строка «Данные до …» без противоречия", () => {
    const markup = render(noBrief(FRESH));
    expect(markup).toContain(BRIEF_PENDING_TEXT);
    expect(markup).not.toContain(STALE_TEXT);
    expect(markup).toContain("Данные до 07.09");
    expect(markup).not.toContain("против нормы </span>"); // строк с цифрами нет
  });

  it("no-brief при пустом view: «сбор не проходил», строки «Данные до» нет", () => {
    const markup = render(noBrief(null));
    expect(markup).toContain(STALE_TEXT);
    expect(markup).not.toContain("Данные до");
  });

  it("stale: «сбор не проходил», строки «Данные до» нет (без изменений)", () => {
    const markup = render({ ...noBrief(STALE), status: "stale", briefDay: "2026-09-06" });
    expect(markup).toContain(STALE_TEXT);
    expect(markup).not.toContain(BRIEF_PENDING_TEXT);
    expect(markup).not.toContain("Данные до");
  });

  it("ok (fixtures): цифры и строка «Данные до», предупреждений нет", () => {
    const markup = render(getSummary());
    expect(markup).toContain("Заказы");
    expect(markup).toContain("Данные до");
    expect(markup).not.toContain(STALE_TEXT);
    expect(markup).not.toContain(BRIEF_PENDING_TEXT);
  });
});
