import { CabinetSwitcher } from "@/components/shell/cabinet-switcher";
import { getDataProvider, type DataProvider } from "@/lib/data";
import { MetricCard } from "@/components/metrics/metric-card";
import { SectionErrorBoundary } from "@/components/ui/section-error";

type MetricStripProps = {
  /** Тестовый шов: провайдер вместо getDataProvider() (шелл его не передаёт). */
  provider?: DataProvider;
};

/**
 * Метрическая полоса шелла: здоровье кабинета за 5 секунд (R05). SSR, без клиента.
 * В postgres-режиме карточки без доступного источника не занимают место; fixtures
 * сохраняют все пять состояний дизайн-системы, включая «нет данных» у OOS.
 */
export async function MetricStrip({ provider = getDataProvider() }: MetricStripProps = {}) {
  if (!provider.supportsMetrics) {
    return null;
  }
  const metrics = await provider.getMetrics();
  const visibleMetrics = provider.mode === "postgres"
    ? metrics.filter((metric) => metric.value !== null)
    : metrics;

  if (visibleMetrics.length === 0) {
    return null;
  }

  return (
    <section aria-label="Показатели кабинета" className="px-4 pt-4 lg:px-6 lg:pt-6">
      <div className="flex items-center justify-between gap-3">
        <CabinetSwitcher />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        {visibleMetrics.map((metric) => (
          <SectionErrorBoundary key={metric.id} title={metric.label}>
            <MetricCard metric={metric} />
          </SectionErrorBoundary>
        ))}
      </div>
    </section>
  );
}
