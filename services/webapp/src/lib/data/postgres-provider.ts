import type { DataProvider } from "@/lib/data/provider";
import type { BriefData, Metric } from "@/lib/data/types";

/*
 * Заглушка боевого источника. Реализуется, когда сойдутся два условия:
 *  1. PMM-29 принял канонический контракт сигнала (contracts/ + codegen);
 *  2. на VPS заведена роль webapp_readonly (деплой-сессия PA-49, сессия 2).
 *
 * До тех пор режим postgres обязан падать явно: показать пустой экран вместо данных
 * означало бы выдать «данных нет» за факт о кабинете (AGENTS.md, fail-closed).
 */

const NOT_IMPLEMENTED =
  "webapp: режим данных postgres ещё не реализован (ждёт контракт PMM-29 и роль webapp_readonly). " +
  "Оставьте WEBAPP_DATA_MODE=fixtures.";

export function createPostgresProvider(): DataProvider {
  return {
    mode: "postgres",
    getBrief(): Promise<BriefData> {
      return Promise.reject(new Error(NOT_IMPLEMENTED));
    },
    getMetrics(): Promise<readonly Metric[]> {
      return Promise.reject(new Error(NOT_IMPLEMENTED));
    },
  };
}
