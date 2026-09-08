/*
 * Минимальное объявление `react-dom/server` для тестов рендера (Story 4.3).
 * `react-dom` уже зависимость webapp, а `@types/react-dom` - нет; новые
 * зависимости запрещены, поэтому тестам хватает одной сигнатуры. Рантайм -
 * настоящий react-dom, объявление только закрывает typecheck.
 */
declare module "react-dom/server" {
  import type { ReactNode } from "react";

  export function renderToStaticMarkup(node: ReactNode): string;
}
