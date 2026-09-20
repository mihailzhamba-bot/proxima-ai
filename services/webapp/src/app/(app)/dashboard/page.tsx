import type { Metadata } from "next";
import { ChartColumn } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionErrorBoundary } from "@/components/ui/section-error";
import { FutureBlock } from "@/components/empty/future-block";

export const metadata: Metadata = {
  title: "Дашборд",
};

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <SectionErrorBoundary title="Дашборд">
        <EmptyState
          icon={ChartColumn}
          title="Дашборд оживёт в PA-52"
          description="Выручка и заказы за 7, 28 и 90 дней, здоровье по SKU, и каждая цифра раскрывается до источника."
          footnote="каркас будущих блоков — ниже"
        />
      </SectionErrorBoundary>
      <SectionErrorBoundary title="Выручка и заказы">
        <FutureBlock
          title="Выручка и заказы"
          note="графики за 7 / 28 / 90 дней с переключателем диапазона"
          shape="chart"
        />
      </SectionErrorBoundary>
      <div className="grid gap-4 sm:grid-cols-2">
        <SectionErrorBoundary title="Здоровье по SKU">
          <FutureBlock
            title="Здоровье по SKU"
            note="какие товары держат выручку, а какие тянут вниз"
            shape="sku"
          />
        </SectionErrorBoundary>
        <SectionErrorBoundary title="Пути до источника">
          <FutureBlock
            title="Пути до источника"
            note="любая цифра раскрывается до артефакта с хэшем"
            shape="source"
          />
        </SectionErrorBoundary>
      </div>
    </div>
  );
}
