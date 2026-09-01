import { resolveDataMode } from "@/lib/data/provider";

/**
 * Next.js запускает register один раз при старте server runtime.
 * Проверяем конфигурацию до первого запроса: неверный режим не может выглядеть
 * как успешно поднявшийся webapp.
 */
export function register(): void {
  resolveDataMode();
}
