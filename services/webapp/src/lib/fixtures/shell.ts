/*
 * Structural fixtures for the webapp skeleton (PA-49/PA-50, fixtures-first decision 2026-08-25).
 * Rules: обезличенные значения, никаких реальных cabinet ID / SKU / цен из боевого кабинета.
 * Помечены `fixture-*` чтобы случайно не перепутать с боевыми данными (DEC-006: unreleased).
 */

export type FixtureCabinet = {
  id: string;
  label: string;
};

export const FIXTURE_CABINETS: readonly FixtureCabinet[] = [
  { id: "fixture-cabinet-pilot", label: "Пилотный кабинет (fixtures)" },
];

export type FixtureShellCounters = {
  red: number;
  yellow: number;
  green: number;
  dataMode: "fixtures";
};

export const FIXTURE_SHELL_COUNTERS: FixtureShellCounters = {
  red: 2,
  yellow: 5,
  green: 137,
  dataMode: "fixtures",
};
