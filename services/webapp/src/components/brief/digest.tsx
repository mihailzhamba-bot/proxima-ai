import { FxBadge } from "@/components/ui/fx-badge";
import type { BriefDigestItem } from "@/lib/fixtures/brief";
import { gyrDotClass } from "@/lib/gyr";
import { cn } from "@/lib/utils";

type DigestProps = {
  items: readonly BriefDigestItem[];
};

/** Дайджест дня: 2-3 демо-пункта под hairline-разделителями; без critical занимает их место (R06.1). */
export function Digest({ items }: DigestProps) {
  return (
    <section aria-labelledby="brief-digest-title" className="flex flex-col">
      <h2
        id="brief-digest-title"
        className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground"
      >
        Дайджест дня
        <FxBadge />
      </h2>
      <ul className="mt-1 border-t border-border">
        {items.map((item) => (
          <li key={item.id} className="flex min-h-9 items-center gap-3 border-b border-border">
            <span aria-hidden="true" className={cn("size-1.5 shrink-0 rounded-full", gyrDotClass(item.tone))} />
            <span className="text-sm">{item.text}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
