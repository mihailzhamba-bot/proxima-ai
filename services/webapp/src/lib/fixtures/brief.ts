/*
 * Structural fixtures для утреннего брифа (PA-49/PA-50, fixtures-first 2026-08-25).
 * Обезличено: fixture-* идентификаторы, структурные суммы без привязки к боевому кабинету (DEC-006).
 * Типы живут в @/lib/data/view-model - форма данных общая для fixtures и будущего Postgres.
 */

import type { SignalV1 } from "@/lib/contracts/signal";
import { anomaliesFromSignals } from "@/lib/data/anomalies";
import type {
  BriefData,
  BriefDigestItem,
  BriefSignal,
  BriefSummary,
  BriefVariant,
} from "@/lib/data/view-model";

export type {
  BriefData,
  BriefDigestItem,
  BriefSignal,
  BriefSummary,
  BriefVariant,
} from "@/lib/data/view-model";

const DAILY_SIGNALS: readonly BriefSignal[] = [
  {
    id: "fixture-brief-signal-oos",
    status: "red",
    title: "Хит выкупается в ноль",
    cause: "маржа после логистики ушла в минус",
    period: "7 дней к предыдущим 7",
    costEstimate: 41200,
    riskLevel: "R2",
    trust: "unreleased",
    primaryCause: {
      id: "fixture-cause-oos-primary",
      text: "Логистика и хранение росли быстрее цены: юнит-экономика позиции перевернулась внутри окна наблюдения.",
      sourceRefIds: ["fixture-ref-oos-margin", "fixture-ref-oos-logistics"],
    },
    alternatives: [
      {
        id: "fixture-cause-oos-alt-returns",
        text: "Всплеск возвратов по размерной сетке: выкуп падает, а расходы на обратную логистику остаются.",
        sourceRefIds: ["fixture-ref-oos-returns"],
      },
      {
        id: "fixture-cause-oos-alt-promo",
        text: "Позиция попала в акцию со скидкой, перекрывшей заложенную маржу.",
        sourceRefIds: ["fixture-ref-oos-margin"],
      },
    ],
    unknowns: [
      {
        id: "fixture-unknown-oos-cogs",
        question: "Какая себестоимость партии, из которой идут текущие отгрузки?",
        whyItMatters: "Без COGS знак маржи считается по прошлой партии — вывод может развернуться.",
      },
      {
        id: "fixture-unknown-oos-promo-plan",
        question: "Планируется ли участие позиции в акции на следующей неделе?",
        whyItMatters: "Если да, снятие с продвижения сегодня не остановит отток маржи.",
      },
    ],
    recommendation:
      "Снять позицию с платного продвижения до пересчёта юнит-экономики и запросить COGS текущей партии.",
    sourceRefs: [
      {
        id: "fixture-ref-oos-margin",
        label: "Маржа после логистики, ₽/шт",
        period: "7 дней к предыдущим 7",
        source: "витрина маржинальности (staging)",
      },
      {
        id: "fixture-ref-oos-logistics",
        label: "Логистика и хранение, ₽/шт",
        period: "7 дней",
        source: "отчёт по услугам (staging)",
      },
      {
        id: "fixture-ref-oos-returns",
        label: "Доля возвратов, %",
        period: "14 дней",
        source: "витрина заказов и выкупа (staging)",
      },
    ],
  },
  {
    id: "fixture-brief-signal-cpc",
    status: "red",
    title: "Ставка РК перегрета",
    cause: "CPM вырос при падающей выкупаемости",
    period: "3 дня к предыдущим 14",
    costEstimate: 12800,
    riskLevel: "R1",
    trust: "unreleased",
    primaryCause: {
      id: "fixture-cause-cpc-primary",
      text: "Аукцион в категории подорожал: та же позиция в выдаче стоит дороже, а конверсия в выкуп не выросла.",
      sourceRefIds: ["fixture-ref-cpc-cpm", "fixture-ref-cpc-buyout"],
    },
    alternatives: [
      {
        id: "fixture-cause-cpc-alt-budget",
        text: "Дневной бюджет исчерпывается к середине дня, и показы уходят в дорогое окно.",
        sourceRefIds: ["fixture-ref-cpc-cpm"],
      },
      {
        id: "fixture-cause-cpc-alt-content",
        text: "Изменилась карточка (фото или заголовок), и просела конверсия из показа в заказ.",
        sourceRefIds: ["fixture-ref-cpc-buyout"],
      },
    ],
    unknowns: [
      {
        id: "fixture-unknown-cpc-competitors",
        question: "Кто из конкурентов зашёл в аукцион в это окно?",
        whyItMatters: "Разовый заход конкурента лечится паузой, структурный сдвиг ставки — пересчётом ДРР.",
      },
    ],
    recommendation:
      "Снизить ставку до уровня предыдущих 14 дней и пересмотреть кампанию после суток наблюдения.",
    sourceRefs: [
      {
        id: "fixture-ref-cpc-cpm",
        label: "CPM, ₽",
        period: "3 дня к предыдущим 14",
        source: "витрина рекламы (staging)",
      },
      {
        id: "fixture-ref-cpc-buyout",
        label: "Выкупаемость, %",
        period: "3 дня к предыдущим 14",
        source: "витрина заказов и выкупа (staging)",
      },
    ],
  },
];

const QUIET_DIGEST_EXTRA: readonly BriefDigestItem[] = [
  {
    id: "fixture-brief-digest-fresh",
    tone: "neutral",
    text: "Свежесть данных — 4 часа, следующий сбор ночью",
  },
];

const BASE_DIGEST: readonly BriefDigestItem[] = [
  {
    id: "fixture-brief-digest-orders",
    tone: "green",
    text: "Заказы за сутки держатся выше недельного уровня",
  },
  {
    id: "fixture-brief-digest-feedback",
    tone: "yellow",
    text: "Три отзыва про размер ждут ответа до вечера",
  },
];

/*
 * Структурный образец `signals[]` брифа (Story 4.3) в проводной форме signal v1
 * (AD-10) - той же, что пишет детектор SCN-001 в `brief_daily.payload` (AD-19).
 * Ряды и суммы повторяют синтетику гейта Story 4.2 (`tools/verify_signals_ranking.py`:
 * пять SKU в двух предметах с известными потерями) плюс один SKU без строки
 * словаря - его предмет `UNKNOWN` (D32). Порядок - по деньгам под риском по
 * убыванию, при равных деньгах глубже падение раньше (CAP-7, Story 4.2).
 */

const FIXTURE_EVALUATION_DAY = "2026-08-29";
const FIXTURE_TENANT = "fixture-tenant-001";
const FIXTURE_SNAPSHOT = "fixture-snapshot-scn001-2026-08-29";
const FIXTURE_RUN = "fixture-run-001";
const FIXTURE_CREATED_AT = "2026-08-30T02:45:00Z";
const FIXTURE_EVIDENCE = `artifact://business-signal/sha256/${"c".repeat(64)}`;
const FIXTURE_CALC = `calc://scn001/norm-median-14d/v1/snapshot/${FIXTURE_SNAPSHOT}`;

type Known = { value: number | string | boolean | readonly ("orders" | "revenue")[]; is_unknown: false };
type Unknown = { value: null; is_unknown: true };

const UNKNOWN: Unknown = { value: null, is_unknown: true };

function known(value: Known["value"]): Known {
  return { value, is_unknown: false };
}

type FixtureRow = {
  id: string;
  level: "sku" | "subject";
  nmIds: readonly number[];
  subjectName: string | null;
  ordersNorm: string;
  ordersActual: number;
  ordersDeviationPct: number;
  revenueNorm: string;
  revenueActual: string;
  revenueDeviationPct: number;
  moneyAtRisk: string;
};

function fixtureSignal(row: FixtureRow): SignalV1 {
  const sku = row.level === "sku";
  const nmId = row.nmIds[0];
  const triggeredBy = (["orders", "revenue"] as const).filter((metricName) =>
    metricName === "orders" ? row.ordersDeviationPct < 0 : row.revenueDeviationPct < 0,
  );
  const subjectRefs = row.nmIds.map((id) =>
    row.subjectName === null
      ? `table://dim_nm_subject/nm/${id}/is_unknown`
      : `table://dim_nm_subject/nm/${id}/run/${FIXTURE_RUN}`,
  );
  return {
    schema_version: 1,
    signal_id: row.id,
    scenario_code: "SCN-001",
    snapshot_id: FIXTURE_SNAPSHOT,
    tenant_id: FIXTURE_TENANT,
    created_at: FIXTURE_CREATED_AT,
    trust_marking: "unreleased",
    rub_assessment: { value_rub: row.moneyAtRisk, method: "revenue" },
    source_refs: [
      FIXTURE_EVIDENCE,
      ...row.nmIds.map((id) => `table://fact_nm_daily/nm/${id}/run/${FIXTURE_RUN}`),
      ...subjectRefs,
      FIXTURE_CALC,
    ],
    detection_data: {
      level: known(row.level),
      nm_id: sku && nmId !== undefined ? known(nmId) : UNKNOWN,
      supplier_article: sku && row.subjectName !== null && nmId !== undefined ? known(`fixture-art-${nmId}`) : UNKNOWN,
      brand: sku && row.subjectName !== null ? known("fixture-brand") : UNKNOWN,
      subject_name: row.subjectName === null ? UNKNOWN : known(row.subjectName),
      sku_count: known(row.nmIds.length),
      evaluation_day: known(FIXTURE_EVALUATION_DAY),
      triggered_by: known(triggeredBy),
      orders_actual: known(row.ordersActual),
      orders_norm_median: known(row.ordersNorm),
      orders_deviation_pct: known(row.ordersDeviationPct),
      revenue_actual: known(row.revenueActual),
      revenue_norm_median: known(row.revenueNorm),
      revenue_deviation_pct: known(row.revenueDeviationPct),
      norm_window_days: known(14),
      norm_sample_days: known(14),
      norm_status: known("ok"),
      threshold_pct: UNKNOWN,
      threshold_source: UNKNOWN,
      threshold_date: UNKNOWN,
      funnel_weeks: known(0),
      funnel_stage: UNKNOWN,
    },
  };
}

const FIXTURE_ROWS: readonly FixtureRow[] = [
  {
    id: "fixture-signal-subject-dress",
    level: "subject",
    nmIds: [2001, 2002],
    subjectName: "Платье",
    ordersNorm: "30.00",
    ordersActual: 17,
    ordersDeviationPct: -43.3,
    revenueNorm: "3000.00",
    revenueActual: "1700.00",
    revenueDeviationPct: -43.3,
    moneyAtRisk: "1300.00",
  },
  {
    id: "fixture-signal-sku-2002",
    level: "sku",
    nmIds: [2002],
    subjectName: "Платье",
    ordersNorm: "20.00",
    ordersActual: 12,
    ordersDeviationPct: -40,
    revenueNorm: "2000.00",
    revenueActual: "1200.00",
    revenueDeviationPct: -40,
    moneyAtRisk: "800.00",
  },
  {
    id: "fixture-signal-sku-2001",
    level: "sku",
    nmIds: [2001],
    subjectName: "Платье",
    ordersNorm: "10.00",
    ordersActual: 5,
    ordersDeviationPct: -50,
    revenueNorm: "1000.00",
    revenueActual: "500.00",
    revenueDeviationPct: -50,
    moneyAtRisk: "500.00",
  },
  {
    id: "fixture-signal-sku-2004",
    level: "sku",
    nmIds: [2004],
    subjectName: "Юбка",
    ordersNorm: "20.00",
    ordersActual: 15,
    ordersDeviationPct: -25,
    revenueNorm: "2000.00",
    revenueActual: "1500.00",
    revenueDeviationPct: -25,
    moneyAtRisk: "500.00",
  },
  {
    id: "fixture-signal-sku-2006-unknown-subject",
    level: "sku",
    nmIds: [2006],
    subjectName: null,
    ordersNorm: "6.00",
    ordersActual: 3,
    ordersDeviationPct: -50,
    revenueNorm: "600.00",
    revenueActual: "300.00",
    revenueDeviationPct: -50,
    moneyAtRisk: "300.00",
  },
  {
    id: "fixture-signal-sku-2003",
    level: "sku",
    nmIds: [2003],
    subjectName: "Юбка",
    ordersNorm: "8.00",
    ordersActual: 7,
    ordersDeviationPct: -12.5,
    revenueNorm: "800.00",
    revenueActual: "900.00",
    revenueDeviationPct: 12.5,
    moneyAtRisk: "-100.00",
  },
  {
    id: "fixture-signal-subject-skirt",
    level: "subject",
    nmIds: [2003, 2004, 2005],
    subjectName: "Юбка",
    ordersNorm: "48.00",
    ordersActual: 47,
    ordersDeviationPct: -2.1,
    revenueNorm: "4800.00",
    revenueActual: "4900.00",
    revenueDeviationPct: 2.1,
    moneyAtRisk: "-100.00",
  },
];

/** `signals[]` образца: предмет, четыре SKU словаря, один SKU с предметом UNKNOWN, предмет с ростом выручки. */
export const FIXTURE_BRIEF_SIGNALS: readonly SignalV1[] = FIXTURE_ROWS.map(fixtureSignal);

function moscowDateIso(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Moscow" }).format(now);
}

/**
 * Структурный образец сводки «вчера против нормы» (DEC-006: fixture-дни).
 * Числа повторяют синтетику контракта brief (verify_brief): 27 против 34.5
 * и 41 141 против 34 595 - с теми же знаками отклонений. Аномалии дня -
 * из `FIXTURE_BRIEF_SIGNALS`; quiet-редакция - «критичных нет» (Story 4.3).
 */
export function getSummary(variant: BriefVariant = "daily"): BriefSummary {
  return {
    status: "ok",
    briefDay: FIXTURE_EVALUATION_DAY,
    orders: { actual: 27, norm: "34.50", deviationPct: -21.7 },
    revenue: { actual: "41141.00", norm: "34595.00", deviationPct: 18.9 },
    normProgress: { sampleDays: 14, windowDays: 14 },
    dataStatus: {
      lastFullDay: FIXTURE_EVALUATION_DAY,
      collectedAt: "2026-08-30T02:41:12.000Z",
      stale: false,
    },
    threshold: { value: null, source: null, date: null },
    anomalies: variant === "quiet" ? [] : anomaliesFromSignals(FIXTURE_BRIEF_SIGNALS),
  };
}

/** Геттер брифа: daily — редакционный день с critical-строками, quiet — «критичных нет» (R06.1). */
export function getBrief(variant: BriefVariant = "daily"): BriefData {
  if (variant === "quiet") {
    return {
      variant,
      dateIso: moscowDateIso(),
      signals: [],
      attentionCount: 3,
      digest: [...BASE_DIGEST, ...QUIET_DIGEST_EXTRA],
      dataMode: "fixtures",
    };
  }
  return {
    variant,
    dateIso: moscowDateIso(),
    signals: DAILY_SIGNALS,
    attentionCount: 5,
    digest: BASE_DIGEST,
    dataMode: "fixtures",
  };
}
