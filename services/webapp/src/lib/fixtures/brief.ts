/*
 * Structural fixtures для утреннего брифа (PA-49/PA-50, fixtures-first 2026-08-25).
 * Обезличено: fixture-* идентификаторы, структурные суммы без привязки к боевому кабинету (DEC-006).
 * UI-типы живут в @/lib/presentation; boundary-контракты генерируются отдельно.
 */

import type {
  BriefData,
  BriefDigestItem,
  BriefSignal,
  BriefVariant,
} from "@/lib/presentation";

export type {
  BriefData,
  BriefDigestItem,
  BriefSignal,
  BriefVariant,
} from "@/lib/presentation";

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

function moscowDateIso(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Moscow" }).format(now);
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
