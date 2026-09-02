import type { BriefV1 } from "@/lib/contracts/brief";
import type { DataProvider } from "@/lib/data/provider";
import type { BriefData, Metric } from "@/lib/data/view-model";

/*
 * Заглушка боевого источника. Реализуется, когда сойдутся два условия:
 *  1. контракты norm/brief приняты (Story 2.2): проводной payload брифа -
 *     BriefWirePayload ниже, сгенерирован из contracts/brief.schema.json;
 *  2. на VPS заведена роль webapp_readonly (деплой-сессия PA-49, сессия 2).
 *
 * До тех пор режим postgres обязан падать явно: показать пустой экран вместо данных
 * означало бы выдать «данных нет» за факт о кабинете (AGENTS.md, fail-closed).
 */

/** Payload брифа как он лежит в brief_current.payload (AD-9); маппинг в BriefData - Story 2.4. */
export type BriefWirePayload = BriefV1;

export const POSTGRES_PROVIDER_NOT_IMPLEMENTED = "NOT_IMPLEMENTED";

const NOT_IMPLEMENTED =
  `${POSTGRES_PROVIDER_NOT_IMPLEMENTED}: webapp: режим данных postgres ещё не реализован (ждёт роль webapp_readonly и маппинг BriefWirePayload -> BriefData, Story 2.4). ` +
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
