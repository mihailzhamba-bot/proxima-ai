# 01 — Токены Warm Precision + шрифты + примитивы

**Требования:** R01, R02, R03, R08 (focus-ring/::selection/skeleton-примитивы), R14i
**Blocked by:** —
**Зона:** `services/webapp/src/app/globals.css`, `src/app/layout.tsx`, `src/components/ui/`, `src/lib/gyr.ts`, `src/tests/`
**Волна:** 1
**Status:** ready

## Что должно заработать

Фундамент канона Warm Precision: обе палитры (светлая ivory + тёмная тёплая stone), шрифты Inter и IBM Plex Mono через next/font (self-hosted), обновлённые примитивы (Button/Card/Badge/GyrBadge с радиусами 4/8px и hairline-границами) и новые: FxBadge («FX» на демо-цифрах), Skeleton (пульс), EmptyState, SectionError. Focus-ring 2px violet на всех интерактивных, ::selection violet-тинт. Существующие экраны продолжают работать на новых токенах (слейт-переход, не переписывание).

## Из брифа, дословно

> «хочется чего-то более погружённого и продуманного»
> «Явный бейдж на каждой» — каждая демо-цифра несёт явный бейдж «FX»
> «Обе темы в этом прогоне» — тёмная тёплый stone, калибровка контраста в обеих

## Разделы спецификации

Истории 1, 2, 3, 6, 22, 23; Решения «Палитра light», «Палитра dark», «Шрифты», «Радиусы/тени», «FX-бейдж», «Крафт»; Границы: `tokens`, `components/ui`.

## Критерии приёмки

- [ ] globals.css: точные hex из спеки (light: #f7f4ef/#ffffff/#e7e5e4/#57534e/#0f172a/#6d28d9/#ddd6fe; dark: #1c1917/#292524/#44403c/#a8a29e/#e7e5e4/#a78bfa/#f5f5f4 + статусы 300-step с текстом #1c1917 на чипах); никаких сырых hex вне globals.css в компонентах
- [ ] Inter (variable) + IBM Plex Mono подключены next/font, weight оптимизирован; SSR без мигании темы (next-themes уже стоит)
- [ ] FxBadge: uppercase 10px mono, muted-фон, рендерится рядом с числом (демо на styleguide-странице временно или в тесте)
- [ ] Skeleton пульсирует в тонах surface, уважает prefers-reduced-motion
- [ ] Focus-ring 2px violet + offset на всех интерактивных примитивах; ::selection violet-тинт
- [ ] Обе темы переключаются без потери контраста GYR-чипов (AA)
- [ ] vitest: тесты gyr/rub зелёные + новый тест токенов/FX (маппинг статусов/классов)
- [ ] typecheck + lint + next build зелёные; make verify PASS
