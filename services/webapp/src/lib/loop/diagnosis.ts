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

export function diagnoseSignal(signal: SignalV1, evaluationDay: string): PilotDiagnosis {
  const labels: Record<string, string> = {
    orders_actual: "Заказы за день", orders_norm_median: "Норма заказов", orders_deviation_pct: "Отклонение заказов, %",
    revenue_actual: "Выручка за день, ₽", revenue_norm_median: "Норма выручки, ₽", revenue_deviation_pct: "Отклонение выручки, %",
  };
  const facts: PilotDiagnosis["facts"] = [];
  if (signal.source_refs.length) {
    for (const [key, name] of Object.entries(labels)) {
      const entry = signal.detection_data[key];
      if (entry && entry.is_unknown === false && (typeof entry.value === "string" || typeof entry.value === "number")) {
        facts.push({ name, value: entry.value, sourceRefs: [...signal.source_refs], date: evaluationDay });
      }
    }
  }
  return {
    kind: "deterministic-pilot-v1", facts,
    hypothesis: "Отклонение показателей может быть связано с доступностью товара. Причина пока не подтверждена.",
    alternatives: ["Мог измениться спрос или приток посетителей.", "Могла измениться конверсия карточки или состав заказов."],
    unknowns: ["Нет подтверждения изменения остатков.", "Не проверены изменения цены и рекламы.", ...(facts.length ? [] : ["Нет фактов с подтверждённым источником."])],
    verification: "Сверить остатки, цену и рекламные изменения за день сигнала с их историей. Приложить источники к задаче.",
  };
}
