import { createFixturesProvider } from "@/lib/data/fixtures-provider";
import { createPostgresProvider } from "@/lib/data/postgres-provider";
import { type DataProvider, resolveDataMode } from "@/lib/data/provider";
import type { DataMode } from "@/lib/contracts/presentation";

export type { DataProvider } from "@/lib/data/provider";
export { DATA_MODE_ENV, DATA_MODES, isDataMode, resolveDataMode } from "@/lib/data/provider";
export * from "@/lib/contracts/presentation";

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
    cached = FACTORIES[resolveDataMode()]();
  }
  return cached;
}

/** Для тестов: сбросить выбранный провайдер, чтобы перечитать окружение. */
export function resetDataProvider(): void {
  cached = undefined;
}
