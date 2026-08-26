import { CabinetSwitcher } from "@/components/shell/cabinet-switcher";
import { getMetrics } from "@/lib/fixtures/metrics";
import { MetricCard } from "@/components/metrics/metric-card";
import { SectionErrorBoundary } from "@/components/ui/section-error";

/** Метрическая полоса шелла: здоровье кабинета за 5 секунд (R05). SSR, без клиента. */
export function MetricStrip() {
  const metrics = getMetrics();

  return (
    <section aria-label="Показатели кабинета" className="px-4 pt-4 lg:px-6 lg:pt-6">
      <div className="flex items-center justify-between gap-3">
        <CabinetSwitcher />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        {metrics.map((metric) => (
          <SectionErrorBoundary key={metric.id} title={metric.label}>
            <MetricCard metric={metric} />
          </SectionErrorBoundary>
        ))}
      </div>
    </section>
  );
}
