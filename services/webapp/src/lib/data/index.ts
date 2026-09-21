import { createFixturesProvider } from "@/lib/data/fixtures-provider";
import { createPostgresProvider } from "@/lib/data/postgres-provider";
import { type DataProvider, resolveDataMode } from "@/lib/data/provider";
import type { DataMode } from "@/lib/data/view-model";

export type { DataProvider } from "@/lib/data/provider";
export { DATA_MODE_ENV, DATA_MODES, isDataMode, resolveDataMode } from "@/lib/data/provider";
export * from "@/lib/data/view-model";

const FACTORIES: Record<DataMode, () => DataProvider> = {
  fixtures: createFixturesProvider,
  postgres: createPostgresProvider,
};

let cached: DataProvider | undefined;

/**
 * Единственная точка входа UI к данным. Провайдер выбирается по WEBAPP_DATA_MODE
 * и кэшируется на процесс: режим — свойство деплоя, внутри рантайма он не меняется.
 */
export function getDataProvider(): DataProvider {
  if (!cached) {
    const provider = FACTORIES[resolveDataMode()]();
    if (provider.mode === "postgres") {
      const authorize = async () => {
        const { currentMember } = await import("@/lib/loop/access");
        await currentMember();
      };
      cached = { ...provider,
        async getBrief(v) { await authorize(); return provider.getBrief(v); },
        async getSummary(v) { await authorize(); return provider.getSummary(v); },
        async getMetrics() { await authorize(); return provider.getMetrics(); },
      };
    } else cached = provider;
  }
  return cached;
}

/** Для тестов: сбросить выбранный провайдер, чтобы перечитать окружение. */
export function resetDataProvider(): void {
  cached = undefined;
}
