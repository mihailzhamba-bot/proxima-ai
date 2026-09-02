import type { BriefData, BriefVariant, DataMode, Metric } from "@/lib/data/view-model";

/*
 * Шов между UI и источником данных (PA-50, критерий приёмки №3).
 * Методы асинхронные с первого дня: Postgres-реализация не должна менять сигнатуры,
 * иначе «переключение конфигом» превратится в правку компонентов.
 */
export type DataProvider = {
  readonly mode: DataMode;
  getBrief(variant: BriefVariant): Promise<BriefData>;
  getMetrics(): Promise<readonly Metric[]>;
};

export const DATA_MODES: readonly DataMode[] = ["fixtures", "postgres"];

export const DATA_MODE_ENV = "WEBAPP_DATA_MODE";

export function isDataMode(value: unknown): value is DataMode {
  return typeof value === "string" && (DATA_MODES as readonly string[]).includes(value);
}

/**
 * Режим данных из окружения. Fail-closed: неизвестное значение — ошибка,
 * а не молчаливый откат на fixtures (иначе продовый промах выглядит как рабочий экран).
 */
export function resolveDataMode(
  env: Readonly<Record<string, string | undefined>> = process.env,
): DataMode {
  const raw = env[DATA_MODE_ENV];
  if (raw === undefined || raw === "") {
    return "fixtures";
  }
  if (!isDataMode(raw)) {
    throw new Error(
      `webapp: ${DATA_MODE_ENV}="${raw}" не поддерживается. Допустимые значения: ${DATA_MODES.join(", ")}.`,
    );
  }
  return raw;
}
