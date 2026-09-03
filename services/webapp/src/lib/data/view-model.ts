/*
 * Доменный view-model данных web-кабинета (PA-50). UI зависит только от этих типов,
 * а не от конкретного источника: fixtures сегодня, Postgres после деплой-сессии.
 *
 * Это ФОРМА ЭКРАНА, а не проводной контракт. Канонические контракты конвейера
 * (AD-9/AD-10) живут в contracts/*.schema.json; их TS-типы генерируются
 * `make codegen` в @/lib/contracts и не редактируются руками. Postgres-провайдер
 * читает проводной payload по @/lib/contracts и маппит его в эти типы (Story 2.4).
 *
 * Имена полей выровнены по уже существующим в репо источникам:
 *  - trust / unknowns{question,whyItMatters} / primaryCause / alternatives
 *    - services/control-plane/src/proxima_control_plane/diagnosis/schema/diagnosis.draft.v1.json
 *  - RiskLevel R0..R3 - services/control-plane/src/proxima/ai/contracts.py:30
 */

import type { GyrStatus } from "@/lib/gyr";
import type { BriefV1 } from "@/lib/contracts/brief";

/** Откуда UI берёт данные. Переключается конфигом, не правкой компонентов. */
export type DataMode = "fixtures" | "postgres";

/** Маркер доверия DEC-006: держится, пока M1 release pointer не сдвинут. */
export type TrustMarker = "unreleased";

/** Уровень риска действия по сигналу; таксономия scenario engine (contracts.py RiskLevel). */
export type RiskLevel = "R0" | "R1" | "R2" | "R3";

export const RISK_LEVELS: readonly RiskLevel[] = ["R0", "R1", "R2", "R3"];

/**
 * Ссылка на источник факта: данные + период + источник (PA-38).
 * Без неё число на экране показывать нельзя.
 */
export type SourceRef = {
  id: string;
  /** Что за факт: «Заказы, шт» — человекочитаемо, для подписи. */
  label: string;
  /** За какой период факт посчитан: «7 дней к предыдущим 7». */
  period: string;
  /** Чем произведён факт: витрина, отчёт, детектор. */
  source: string;
};

/** Гипотеза причины: primary или альтернатива; каждая опирается на источники. */
export type SignalHypothesis = {
  id: string;
  text: string;
  sourceRefIds: readonly string[];
};

/** «Что неизвестно»: вопрос + почему он меняет решение (diagnosis.draft.v1 unknowns). */
export type SignalUnknown = {
  id: string;
  question: string;
  whyItMatters: string;
};

/** Критичный сигнал брифа. Поля - объединение карточки из PA-38 и скоупа PA-50. */
export type BriefSignal = {
  id: string;
  status: GyrStatus;
  /** Что изменилось - заголовок строки. */
  title: string;
  /** Однострочная причина для свёрнутой строки; развёрнутая версия - primaryCause. */
  cause: string;
  /** С чем сравнили: окно наблюдения и база сравнения. */
  period: string;
  /** «Стоимость молчания», ₽/день, пока сигнал не обработан. */
  costEstimate: number;
  riskLevel: RiskLevel;
  trust: TrustMarker;
  primaryCause: SignalHypothesis;
  /** 2-3 альтернативы (PA-38); пустой список означал бы «причина одна» - так не бывает. */
  alternatives: readonly SignalHypothesis[];
  unknowns: readonly SignalUnknown[];
  /** Что предлагается сделать. Решение принимает AM, не UI. */
  recommendation: string;
  sourceRefs: readonly SourceRef[];
};

export type BriefVariant = "daily" | "quiet";

export type BriefDigestItem = {
  id: string;
  tone: GyrStatus;
  text: string;
};

export type BriefData = {
  variant: BriefVariant;
  dateIso: string;
  signals: readonly BriefSignal[];
  attentionCount: number;
  digest: readonly BriefDigestItem[];
  dataMode: DataMode;
};

/** Payload брифа как он лежит в brief_current.payload (AD-9); читается postgres-провайдером. */
export type BriefWirePayload = BriefV1;

/**
 * Сводка «вчера против нормы» (AD-9). Значения - как они лежат в payload
 * `brief_current`: деньги строками с двумя знаками (AD-10), отклонение -
 * уже округлённое число (D27). Форматирование и цвет - дело компонента,
 * не провайдера.
 */
export type SummaryMetric = {
  /** Факт дня: заказы в штуках, выручка строкой AD-10. */
  actual: number | string;
  /** Норма строкой AD-10 (медиана с дробной частью); null - нормы нет (blocked). */
  norm: string | null;
  /** Отклонение %; null - отклонение не называется (insufficient/blocked). */
  deviationPct: number | null;
};

/** Почему на экране нет (или есть) цифры: статусы `brief_daily` + режим «только статус» (AD-9). */
export type SummaryStatus = "ok" | "insufficient" | "blocked" | "no-brief";

export type BriefSummary = {
  status: SummaryStatus;
  /** День сводки (brief_day / evaluation_day), ISO. */
  briefDay: string | null;
  orders: SummaryMetric | null;
  revenue: SummaryMetric | null;
  /** «норма копится: 9/14 дней» - из payload.norm.sample_days/window_days. */
  normProgress: { sampleDays: number; windowDays: number } | null;
  /**
   * Статус данных (AD-7): из `data_status_current`. null - строк в view нет вовсе,
   * сбор не проходил никогда; тогда цифр на экране не бывает.
   */
  dataStatus: DataStatusInfo | null;
};

export type DataStatusInfo = {
  lastFullDay: string;
  collectedAt: string;
  stale: boolean;
};

export type MetricId = "signals" | "revenue-day" | "orders-day" | "oos-risks" | "freshness";

export type MetricFormat = "count" | "rub-compact" | "clock";

export type Metric = {
  id: MetricId;
  label: string;
  value: number | null;
  format: MetricFormat;
  status: GyrStatus | null;
  deltaPercent: number | null;
  deltaGoodWhen: "up" | "down" | null;
  points: readonly number[];
};
