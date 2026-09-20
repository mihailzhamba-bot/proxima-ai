---
name: Proxima AI
description: Design system for the Proxima AI WB data platform (control plane UI, reports, internal tools)
colors:
  primary: "#0f172a"
  secondary: "#57534e"
  tertiary: "#6d28d9"
  neutral: "#f7f4ef"
  surface: "#ffffff"
  on-surface: "#0f172a"
  error: "#b91c1c"
  success: "#15803d"
  warning: "#b45309"
  info: "#1d4ed8"
  tertiary-container: "#ddd6fe"
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.55
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: 0.06em
  data-md:
    fontFamily: IBM Plex Mono
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.45
rounded:
  sm: 4px
  md: 8px
  lg: 12px
  full: 9999px
spacing:
  base: 16px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 48px
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: 10px 16px
  button-primary-hover:
    backgroundColor: "{colors.primary}"
  status-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.md}"
    padding: 24px
  page:
    backgroundColor: "{colors.neutral}"
  badge-success:
    backgroundColor: "{colors.success}"
    textColor: "{colors.surface}"
    rounded: "{rounded.full}"
    padding: 4px 12px
  badge-error:
    backgroundColor: "{colors.error}"
    textColor: "{colors.surface}"
    rounded: "{rounded.full}"
    padding: 4px 12px
  badge-warning:
    backgroundColor: "{colors.warning}"
    textColor: "{colors.surface}"
    rounded: "{rounded.full}"
    padding: 4px 12px
  badge-info:
    backgroundColor: "{colors.info}"
    textColor: "{colors.surface}"
    rounded: "{rounded.full}"
    padding: 4px 12px
---

# DESIGN — Proxima AI

> Base: `_ai/DESIGN-BASE.md` (MILV, Warm Precision), inlined 2026-08-25, v2.
> Spec-before-UI: written before any frontend exists. Colors extracted from the project
> map artifact (2026-08-22); status hues moved from 600- to 700-step Tailwind for WCAG AA.
> v2 (2026-08-25): canvas migrated cool → warm ivory per Warm Precision meta-style;
> chrome grays moved to the warm stone family. Typography approved by Mike 2026-08-25:
> Inter (narrative) + IBM Plex Mono (data).
> Format: Google DESIGN.md spec (alpha). Validate: `npx @google/design.md lint DESIGN.md`.

## Overview

Built on the **Warm Precision** meta-style (see base): paper-warm surfaces, numbers as
heroes, hairline structure, measured motion. An analytical instrument, not a dashboard
toy. The platform serves agency analysts and WB sellers who read numbers for a living:
the UI must feel dense, calm and precise — a laboratory bench for marketplace data, with
the warmth of paper rather than the cold of chrome. Trustworthy over playful; every pixel
of chrome must justify itself against the data it frames. When a rule does not cover a
case, choose the option that maximizes data legibility and minimizes decoration.

## Colors

Warm ivory neutrals with a single violet accent. Initial palette came from the project
map artifact (cool); v2 warms the ground per the meta-style — violet, ink and statuses
carry over unchanged.

- **Primary (#0f172a):** Slate ink for headings and primary text — near-black, never pure #000000.
- **Secondary (#57534e):** Warm stone for metadata, captions, borders, secondary labels.
  Same family as the canvas — no cool grays anywhere in chrome.
- **Tertiary (#6d28d9):** Proxima violet. Sole interaction driver: primary buttons, active
  states, key links. Never as background tint, divider or decoration.
- **Neutral (#f7f4ef):** Warm ivory canvas for page background; content sits on white surfaces.
- **Status (success #15803d / error #b91c1c / warning #b45309 / info #1d4ed8):** Tailwind
  status palette at 700-step for AA text contrast (artifact used 600-step; adjusted).
  Semantic use only — deltas in tables, badges, alerts; never brand decoration.

## Typography

Two families (approved): **Inter** for interface narrative, **IBM Plex Mono** for all
numeric data — SKUs, prices, revenue, dates in tables. Mono numerals align in columns
and signal "measured value, not marketing copy". Micro-labels are uppercase with wide
tracking. 2 weights per screen max; data tables use regular weight only.

## Layout

Data-dense grid: 12-column desktop, comfortable minimum 1280px, content max-width 1440px.
8px spacing rhythm. Tables and charts get priority real estate; navigation stays narrow
(240px sidebar). Cards use 24px internal padding; group related metrics inside one
surface rather than scattering tiles. Filters live above the data they filter, always
visible, never hidden behind icons.

## Elevation & Depth

Tonal layers, not shadows: canvas (#f7f4ef) → surface (#ffffff) → subtle border
(#e7e5e4, warm) for boundaries. Shadows only for transient layers (dropdowns, modals,
popovers) and even there: one soft shadow, never stacked glows. Depth signals layering,
not decoration.

## Shapes

Engineered restraint: 4px radius on controls (buttons, inputs, tabs), 8px on containers
(cards, panels), never mixed within one component class. Pills only on status badges.
Charts and tables are square-edged — data geometry stays crisp.

## Components

- **Buttons:** primary = violet fill, white text, 4px radius, 10px/16px padding, hover
  darkens to slate ink. Secondary = white surface, warm stone border. Destructive = error
  red, used only for irreversible actions.
- **Tables (core component):** mono numerals, tabular figures, right-aligned numbers,
  left-aligned text, zebra-free — row separation via 1px warm hairlines. Sticky headers on scroll.
- **Status badges:** pill radius, solid status fill, white text, uppercase micro-label.
  Violet-tinted variant (#ddd6fe) reserved for selection states.
- **Invisible details (craft checklist):** visible focus ring (2px violet, 2px offset) on
  every interactive element; `::selection` in violet tint; thin warm scrollbar on data
  surfaces; skeleton loaders in surface tones; designed empty/error states per view.

## Do's and Don'ts

- Do use violet only for the single most important action per screen.
- Do render every number, SKU and price in the mono data font.
- Don't add decoration that competes with data: gradients, glows, illustrated empty states.
- Don't color entire table rows — status is a badge in one cell, not a row wash.
- Don't invent new grays; the neutral/surface/secondary trio covers all chrome.

## Motion

Per DESIGN-BASE: respond on pointer-down; springs (damping 1.0) for anything draggable;
interruptible transitions; never lock input. Data views animate value changes with short
count-ups (300-500ms) so updates are noticed but not theatrical. Respect
prefers-reduced-motion everywhere. Charts transition between states, never replay from zero.
