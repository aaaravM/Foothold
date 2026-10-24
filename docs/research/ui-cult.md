# Cult UI: research notes for Foothold

- **Retrieved:** Sat Oct 24 2026, 13:28 to 13:42 PDT, by the UI library integrator.
- **Scope:** install commands, the candidate components (dynamic island, globe, kanban, analytics chart, cards), their dependencies, the license, and how each maps to a Foothold page.
- **Labels:** VERIFIED = fetched and confirmed. UNVERIFIED = not confirmed, with the reason.

## 1. Install (VERIFIED, from https://www.cult-ui.com/docs/installation, "Updated Oct 1, 2026")

- Needs what `shadcn init` creates: `components.json`, the `cn` helper in `lib/utils.ts`, an `@/` alias and theme tokens. Foothold already has these (radix-nova).
- Add a component: `pnpm dlx shadcn@latest add @cult-ui/halo-button` (the npm tab is `npx shadcn@latest add ...`). "The `@cult-ui` namespace is listed in the shadcn registry directory, so this works without editing components.json. The CLI writes the component to `components/ui/<name>.tsx`, installs its npm dependencies, and adds any shadcn/ui components it builds on."
- Several at once: `npx shadcn@latest add @cult-ui/a @cult-ui/b ...`
- Search / preview: `npx shadcn@latest search @cult-ui --query card`, `npx shadcn@latest view @cult-ui/<name>`.
- Optional pin (documented for CLIs older than 3.0, blocked directory access, or to be explicit). We added it to `web/components.json`:
  ```json
  { "registries": { "@cult-ui": "https://www.cult-ui.com/r/{name}.json" } }
  ```
  (The shadcn directory lists `https://cult-ui.com/r/{name}.json`; both hosts served the items.)
- By URL with any CLI: `npx shadcn@latest add https://www.cult-ui.com/r/<name>.json`. Update: re-add with `--overwrite` and review the diff.

## 2. License (VERIFIED)

- `nolly-studio/cult-ui` `LICENSE.md` on `main`: **MIT License, Copyright (c) 2023 Jordan-Gilliam**. Keep the notice (see `web/src/components/LIBRARIES.md`).
- Every component is free. The "Paid" / "One-time purchase" labels on the docs pages belong to a separate product (AI SDK Agents blocks), not to Cult UI components.

## 3. Candidates (registry JSON read before install, then installed)

| Item | What it is (registry description) | npm deps | Notes from the source scan | Foothold use |
|---|---|---|---|---|
| `dynamic-island` | iOS-style island with size presets and animated content | `motion` | exports `DynamicIslandProvider`, `DynamicIsland`, `DynamicContainer`, `DynamicTitle`, `DynamicDescription`, `DynamicDiv`, `useDynamicIslandSize`, `useScheduledAnimations`, `SIZE_PRESETS`; black pill, radii up to 46px, a missing `#squircle-*` clip-path reference, blur exits | sim status plate (SHEET 01) |
| `globe` | COBE-powered 3D globe with markers, arcs and DOM overlays | `cobe` (2.0.1), `motion`, `next-themes` | 40 KB, mostly world-city demo data with emoji stickers; reads `next-themes` `resolvedTheme` (Foothold has no next-themes provider, so it would always render the light look); labels use CSS anchor positioning | Central Valley marker map; client-only + lazy |
| `kanban-board` | columns with native HTML drag and drop + Motion | `motion` | exports `Column` and types only (no board wrapper); hard-coded tag colors, shadows, 14px radius, blur | pathway tracking (SHEET 02) |
| `analytics-chart` | line chart with a dash-offset draw and floating tooltip cards | none | `AnalyticsLineChart`; orange→green gradient line and dots; tooltips formatted as dates; demo data | lab curves (SHEET 06) |
| `folded-card` | card with a folded-corner clip-path | none (`next/link`) | parts: `FoldedCard`, `FoldedCardFold`, `FoldedCardLink`, `FoldedCardBorder`, `FoldedCardPreview`, `FoldedCardGrid`, `FoldedCardFooter`, `FoldedCardHeading`, `FoldedCardTitle`, `FoldedCardBadge`, `FoldedCardDescription`; fold uses a gradient | career cards: a dog-eared drawing sheet with a dashed drafting grid |
| `shift-card`, `texture-card`, `minimal-card` | other card styles | `motion` / none | heavy shadows, 11-29 hard-coded colors (texture) | not installed (folded-card fits the drawing set better) |

Docs pages read (VERIFIED, all show the same `pnpm dlx shadcn@latest add @cult-ui/<name>` command): dynamic-island (props table and the 14 size presets), globe ("drag to rotate, theme colors, markers, and arcs"; colors follow the theme through next-themes), kanban-board ("native HTML drag and drop and Motion"), analytics-chart (props `data`, `gradientStops`, `dotColors`, `gridLines`, `pinnedIndices`, `valueLabel`).

## 4. Commands that were run (in `web/`)

```bash
npx shadcn@latest add @cult-ui/dynamic-island @cult-ui/globe @cult-ui/kanban-board @cult-ui/analytics-chart @cult-ui/shift-card @cult-ui/folded-card --dry-run
npx shadcn@latest add @cult-ui/dynamic-island @cult-ui/globe @cult-ui/kanban-board @cult-ui/analytics-chart @cult-ui/folded-card --yes
```

Result: 5 files in `src/components/ui/`, one new npm dependency (`cobe@^2.0.1`; `motion` and `next-themes` were already present). The CLI did not touch `globals.css`.

## 5. Sources (retrieved 2026-10-24)

- https://www.cult-ui.com/docs/installation
- https://www.cult-ui.com/docs/components/dynamic-island, /globe, /kanban-board, /analytics-chart
- https://www.cult-ui.com/r/{dynamic-island,globe,kanban-board,analytics-chart,shift-card,folded-card,texture-card,minimal-card,rolling-number,text-animate,stripe-bg-guides,squiggle-arrow,sortable-list,typewriter}.json
- https://raw.githubusercontent.com/nolly-studio/cult-ui/main/LICENSE.md
- https://ui.shadcn.com/r/registries.json (`@cult-ui` entry)
