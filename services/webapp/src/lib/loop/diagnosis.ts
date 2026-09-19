import type { SignalV1 } from "@/lib/contracts/signal";

/** Explicit boundary: a deterministic assessment, never diagnosis.draft.v1 or LLM output. */
export type PilotDiagnosis = {
  kind: "deterministic-pilot-v1";
  facts: { name: string; value: string | number; sourceRefs: string[]; date: string }[];
  hypothesis: string;
  alternatives: string[];
  unknowns: string[];
  verification: string;
};

const PLAIN_DECIMAL = /^-?[0-9]+(?:\.[0-9]+)?$/;

function isVerifiedNumericValue(value: unknown): value is string | number {
  return typeof value === "number"
    ? Number.isFinite(value)
    : typeof value === "string" && PLAIN_DECIMAL.test(value);
}

function isEvaluationDay(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (year === 0 || month < 1 || month > 12) return false;

  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day >= 1 && day <= daysInMonth[month - 1];
}

export function diagnoseSignal(signal: SignalV1, evaluationDay: string): PilotDiagnosis {
  const labels: Record<string, string> = {
    orders_actual: "Заказы за день", orders_norm_median: "Норма заказов", orders_deviation_pct: "Отклонение заказов, %",
    revenue_actual: "Выручка за день, ₽", revenue_norm_median: "Норма выручки, ₽", revenue_deviation_pct: "Отклонение выручки, %",
  };
  const facts: PilotDiagnosis["facts"] = [];
  const sourceRefs = Array.isArray(signal.source_refs)
    ? signal.source_refs.filter((sourceRef): sourceRef is string => typeof sourceRef === "string" && sourceRef.trim().length > 0)
    : [];
  const validEvaluationDay = isEvaluationDay(evaluationDay);
  if (validEvaluationDay && sourceRefs.length) {
    for (const [key, name] of Object.entries(labels)) {
      const entry = signal.detection_data[key];
      const value = entry?.value;
      if (entry && entry.is_unknown === false && isVerifiedNumericValue(value)) {
        facts.push({ name, value, sourceRefs: [...sourceRefs], date: evaluationDay });
      }
    }
  }
  const unknowns = ["Нет подтверждения изменения остатков.", "Не проверены изменения цены и рекламы."];
  if (!validEvaluationDay) unknowns.push("Дата оценки не является корректным календарным днём YYYY-MM-DD.");
  if (!sourceRefs.length) unknowns.push("Нет непустого подтверждённого SourceRef.");
  if (!facts.length) unknowns.push("Нет проверенных числовых фактов для вывода.");
  return {
    kind: "deterministic-pilot-v1", facts,
    hypothesis: facts.length
      ? "Отклонение показателей может быть связано с доступностью товара. Причина пока не подтверждена."
      : "Недостаточно проверенных данных для гипотезы.",
    alternatives: ["Мог измениться спрос или приток посетителей.", "Могла измениться конверсия карточки или состав заказов."],
    unknowns,
    verification: "Сверить остатки, цену и рекламные изменения за день сигнала с их историей. Приложить источники к задаче.",
  };
}
