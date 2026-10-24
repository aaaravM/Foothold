# Watermelon UI: research notes for Foothold

- **Retrieved:** Sat Oct 24 2026, 11:55 to 12:32 PDT (`date` was run at the start). Every source listed at the bottom was fetched in that window.
- **Scope:** registry setup, install commands, npm dependencies, license, and which items fit (a) the `/employers` portal dashboard and (b) the landing page sections. The last part covers retheming for the dark `#050505` / paper `#f4f4f1` drawing-set look.
- **Method:** I read the site pages (llms.txt, installation, cli, framework-support, guides), the public JSON API, the full registry index, and **144 registry item JSONs** fetched with curl. I installed nothing. The color and coupling numbers below come from a static scan of each item's source (`content` field).
- **Labels:** VERIFIED = I fetched it and confirmed it. UNVERIFIED = not confirmed, with the reason given.

---

## 0. TL;DR

| Question | Answer |
|---|---|
| What is it | It is a free, open-source catalog of React and Tailwind v4 components, blocks, and dashboards. It ships as a **shadcn registry**, so the CLI copies source into your repo and you own the code. |
| License | **MIT** for both repos (VERIFIED via the GitHub API `license.spdx_id`). Keep the MIT notice when you copy code. |
| Install one item | `npx shadcn@latest add https://registry.watermelon.sh/r/<name>.json` |
| Namespace | `@watermelon` is listed in the official shadcn directory (VERIFIED in `https://ui.shadcn.com/r/registries.json`, status "healthy", itemCount 1178), so `npx shadcn@latest add @watermelon/<name>` works with no config. |
| Requirements | React 18 or 19, **Tailwind v4**, the latest shadcn, Next.js 14+ (App Router supported). Source: `/framework-support`. |
| Catalog size | 849 entries in the public catalog: components 516, animated-components 131, blocks 189, dashboards 12, templates 1. Registry index: 1178 items. |
| Best for `/employers` | **`medesk-dashboard`**: sidebar, topbar, 4 KPI cards, bar chart, table, and list. Colors are 100% token-driven. Runner-up: `tallie-dashboard` (table-centric, serif headings with mono numbers). |
| Best landing blocks | `feature-4`, `stats-4`, `hero-3`, `footer-2`, plus `widget-4` for chart cards. The faq-1..6 / footer-1..5 / pricing-1..5 families have zero hard-coded colors. |
| Biggest gotchas | (1) Many items lack `"use client"`. (2) The bundled dashboard ThemeProvider reads `localStorage` and `window` during render, which breaks SSR. (3) Dashboards use the `.dark` class, but Foothold uses `data-theme`. (4) Several items use Radix-style `asChild`. (5) Some items pull in `react-router-dom`. (6) `testimonials-2` uses real people's GitHub avatars. |

---

## 1. Setup: exact commands

### 1.1 Current `web/` state (read-only check, 12:30 PDT; another agent owns this folder)
- `next 16.4.2`, `react 19.3.0`, `tailwindcss ^4`, `@tailwindcss/turbopack ^4`, `typescript 5.9.3`.
- `src/` layout, with `@/*` mapped to `./src/*` in tsconfig.
- **No `components.json` yet**, so shadcn has not been initialized.

### 1.2 Initialize shadcn (shell owner runs this once, inside `web/`)
```bash
cd web
npx shadcn@latest init --base radix
```
- `-b, --base <base>` accepts `base | radix | aria`. This is VERIFIED in the shadcn CLI docs (`https://ui.shadcn.com/docs/cli`). Other verified init flags: `-t, --template` (`next | vite | start | react-router | laravel | astro`), `-p, --preset`, `-d, --defaults` (= `--template=next --preset=nova`), `--css-variables` (default true), `-f, --force`.
- **Why radix:** these Watermelon items use the Radix-flavored shadcn prop `asChild`: `medesk-dashboard` (5 uses), `tallie-dashboard` (4), `astrix-dashboard` (2), `agndex-dashboard` (1), `widget-1` (1), `cta-1` (1), `faq-4` (1). None of the scanned items use the Base UI `render={...}` prop. With a Base UI init, those `asChild` props will fail type-checks.
- **UNVERIFIED:** which base `init` picks by default. Watermelon's own comparison page says shadcn "now defaults to Base UI". I did not confirm that in the shadcn docs; the options list I read shows no default for `--base`.
- Watermelon's installation page gives these commands for a new project: `npx shadcn@latest init --template next` or `npx shadcn@latest init --template vite`. `web/` already exists, so run plain `init` in it.
- Package-manager variants (per `/installation`): replace `npx` with `pnpm dlx`, `yarn dlx`, or `bunx --bun`.

### 1.3 Optional: pin the namespace in `web/components.json`
```json
{
  "registries": {
    "@watermelon": "https://registry.watermelon.sh/r/{name}.json"
  }
}
```
This is optional because `@watermelon` is already in the official directory and the CLI resolves it automatically. Pinning makes it explicit and lets the shadcn MCP server see it.

### 1.4 Add, preview, search
```bash
# install by URL (no config needed)
npx shadcn@latest add https://registry.watermelon.sh/r/feature-4.json
# install by namespace
npx shadcn@latest add @watermelon/feature-4
# PREVIEW FIRST: shows target paths without writing (verified flag)
npx shadcn@latest add @watermelon/medesk-dashboard --dry-run
npx shadcn@latest add @watermelon/hero-3 --view components/ui/hero-3.tsx
# inspect / search the registry
npx shadcn@latest view @watermelon/widget-4
npx shadcn@latest search @watermelon -q "hero"
```
- Verified `add` flags: `-y/--yes`, `-o/--overwrite`, `-c/--cwd`, `-a/--all`, `-p/--path <path>`, `-s/--silent`, `--dry-run`, `--diff [path]`, `--view [path]`.
- The CLI asks before overwriting existing files; pass `--overwrite` to skip the prompt (per `/cli` FAQ).
- **`-base` variants:** 135 items have a `<name>-base` twin that uses theme tokens instead of fixed colors, for example `https://registry.watermelon.sh/r/card-split-accordian-base.json` (VERIFIED, HTTP 200). The base and normal variants **write the same file path**, so install only one of the two.
- **Manual path** (per `/installation`): install the deps the item lists, for example `npm install motion`, then paste the source into `components/ui`.

### 1.5 Optional agent tooling (changes the user's Claude config, so ask the user first)
- Hosted MCP, no API key (from llms.txt): `claude mcp add --transport http watermelon https://mcp.watermelon.sh/mcp`. llms.txt names the tools `search`, `get_inspiration`, `get_component`, `compose_page`, and `list_categories`. **UNVERIFIED:** I did not call the MCP server.

---

## 2. Registry facts (VERIFIED with curl, no install)

| URL | HTTP | Size | Notes |
|---|---|---|---|
| `https://registry.watermelon.sh/r/hero-3.json` | 200 | 14,131 B | `registry:ui`. Writes `components/ui/hero-3.tsx` **and** `assets/logo-icon.tsx`. |
| `https://registry.watermelon.sh/r/agndex-dashboard.json` | 200 | 90,247 B | `registry:block`, 14 files under `components/watermelon/agndex-dashboard/` |
| `https://registry.watermelon.sh/r/medesk-dashboard.json` | 200 | 197,888 B | rechecked at 12:32 PDT |
| `https://registry.watermelon.sh/r/card-split-accordian.json` / `-base.json` | 200 / 200 | 6,732 / 6,831 B | animated component and its token twin |
| `https://registry.watermelon.sh/r/accordion-1.json` | 200 | 2,001 B | component, registryDependencies `["accordion"]` |
| `https://registry.watermelon.sh/registry.json` (same as `/r/registry.json`) | 200 | 732,993 B | full index; `$schema` is `https://ui.shadcn.com/schema/registry.json`, `name: "watermelon"` |
| `https://registry.watermelon.sh/r/index.json` | **404** | n/a | does not exist; do not use |

- **Index composition:** 1178 items: 778 `registry:component`, 359 `registry:ui`, 33 `registry:block`, 5 `registry:hook`, 2 `registry:lib`, 1 `registry:page`. All 189 site blocks and all 131 animated components resolve to a registry name with the same slug.
- **Where files land, by declared target:**
  - Landing blocks: `components/ui/<name>.tsx`.
  - Animated components: `components/watermelon/<name>.tsx`.
  - Dashboards: `components/watermelon/<dash>/...`, 11 to 16 files including `dashboard.css`, `data.tsx`, and `demo.tsx`.
  - Some heroes and footers, plus `cta-5`, also write `assets/logo-icon.tsx` and import it as `@/assets/logo-icon`. In this repo that import resolves to `web/src/assets/logo-icon.tsx`. **Run `--dry-run` and move the file if the CLI puts it elsewhere.** UNVERIFIED: how the CLI maps `target` paths in a `src/` project.
- **`registryDependencies`** such as `button`, `card`, `sidebar`, `table`, `chart`, `utils`, and `use-mobile` are plain names. Per the shadcn registry-item docs (VERIFIED), plain names mean **shadcn/ui registry items**, so the CLI installs shadcn's own `button`, `sidebar`, and so on.
- **Most common npm deps across the registry** (count = items that use the dep):

  | Dep | Items |
  |---|---|
  | `lucide-react` | 540 |
  | `motion` | 390 |
  | `react-icons` | 367 |
  | `framer-motion` | 75 |
  | `@hugeicons/react` | 59 |
  | `@hugeicons/core-free-icons` | 54 |
  | `class-variance-authority` | 45 |
  | `@tabler/icons-react` | 36 |
  | `react-use-measure` | 35 |
  | `sonner` | 33 |
  | `next-themes` | 30 |
  | `recharts` | 16 |
  | `zod` | 16 |

  Prefer items that only need `lucide-react` (and `motion` or `recharts`) so you avoid shipping four icon libraries.
- **Public catalog API** (read-only, no auth; base `https://ui.watermelon.sh/api/v1`):
  - `GET /catalog/summary`
  - `GET /catalog/entries?kind=<animated-components|blocks|dashboards|templates>&category=&query=&limit=` (limit 1 to 50, **no offset**)
  - `GET /catalog/entries/{kind}/{slug}`
  - The category filter is **case-sensitive**: `hero`, `footer`, `widget`, `navigation`, `pricing`, `testimonials`, `integrations` are lowercase; `Stats`, `Feature`, `CTA`, `Bento` are capitalized. I got 0 FAQ entries for `faq`, `Faq`, and `FAQ`.
  - For complete listings, use `registry.json`.

---

## 3. What exists (catalog)

**Block categories and counts** (from the sitemap):

| Category | Count | Category | Count | Category | Count |
|---|---|---|---|---|---|
| hero | 43 | contact | 7 | feature | 5 |
| footer | 31 | faq | 6 | cta | 5 |
| auth | 13 | team | 5 | testimonials | 4 |
| widget | 9 | pricing | 5 | stats | 4 |
| announcement | 9 | newsletter | 5 | notification | 4 |
| navigation | 7 | integrations | 5 | career | 4 |
| error | 7 | file-upload | 5 | blog | 4 |
| | | | | bento | 2 |

Browse a category at `https://ui.watermelon.sh/blocks/<category>` and a single block at `https://ui.watermelon.sh/block/<slug>`.

**Dashboards (12 public).** Browse at `https://ui.watermelon.sh/dashboard/<slug>`.

How to read the columns:
- **Hard colors** = hard-coded colors (Tailwind palette classes + hex + arbitrary `[#..]` values).
- **Tokens** = shadcn token classes such as `bg-background` and `text-muted-foreground`.
- **UC** = files that start with `"use client"`.

| Slug | What it is (catalog summary) | npm deps | Tokens / hard colors | UC | Notes |
|---|---|---|---|---|---|
| **medesk-dashboard** | healthcare ops: appointments, staff, dept load | lucide-react, `recharts@2.15.4`, @fontsource geist / geist-mono / instrument-serif (declared but not imported) | 107 / **0** | 0 of 11 | **top pick**: KPI cards with sparkbars, grouped BarChart, AreaChart, HTML table, list, ⌘K search |
| **tallie-dashboard** | expense audit: live controls, exceptions, transaction table | lucide-react, @fontsource geist / geist-mono / instrument-serif (imported in its CSS) | 57 / 16 | 0 of 12 | serif display heading with mono amounts; table plus detail sheet; no charts |
| library-dashboard | library metrics, circulation charts, alerts | lucide-react, recharts (+ shadcn `chart`) | 87 / 58 | 4 | AreaChart and PieChart via shadcn ChartContainer |
| agndex-dashboard | developer portal: API keys, billing | lucide-react | 70 / **0** | 0 | simplest, fully token-driven; no charts |
| astrix-dashboard | trade-compliance pipeline | lucide-react | 97 / 39 | 0 | 232 KB (118 KB sample data file) |
| gridline-dashboard | electrical grid planning | lucide-react | 141 / 36 | 0 | |
| jobtracker-dashboard | jobs, customers, estimates, drag-and-drop | @dnd-kit/*, lucide-react, next-themes | 77 / 131 | 0 | heavy retheme |
| bionis / capitalio | health / wealth analytics | `recharts@2.15.4` (+ `@base-ui/react` for capitalio) | 88 / 69, 67 / 90 | 0 | bionis CSS loads fonts from cdn.jsdelivr |
| demostack-dashboard | product-demo workspace | lucide-react | 60 / 18 | 4 | remote images (unsplash, assets.watermelon.sh) |
| portfolio / web3 | insurance / DeFi | recharts, next-themes; portfolio also needs **react-router-dom** | 85 / 51, 60 / 38 | 2 / 4 | avoid portfolio in Next |

- **Registry-only dashboards** (in `registry.json`, not in the public catalog): business-management, business-operations-dashboard, e-commerce-dashboard, erp-dashboard, hrm, incident-management, invoice-generator-dashboard, invoice-manager-dashboard, issue-tracking, lead-dashboard, mail-dashboard, meetings-dashboard, payment-operations-dashboard, project-management-dashboard, sales-dashboard, task-management-dashboard, workflow-management-dashboard.
  - business-management, incident-management, and sales-dashboard depend on **react-router-dom**, so avoid them.
- **Template:** `landing-01` has 25 files and depends on **react-router-dom**, with 265 palette classes and 77 `dark:` classes. **Not recommended.**

---

## 4. Fit analysis

### 4a. Employer portal (`/employers`, SHEET 04): sidebar, stat cards, tables, charts
- **`medesk-dashboard`** covers all four needs in one install. Its layout, from the catalog thumbnail:
  - Collapsible grouped sidebar.
  - Topbar with search and ⌘K.
  - Greeting header with Export, a date range, and a primary button.
  - 4 KPI cards with mini bar sparklines and mono captions.
  - "Volume" grouped bar chart with summary figures beside it.
  - Segmented "load" bar with a breakdown list.
  - Table with Import and Filter actions.
  - "Performance" list.

  Map the content to Foothold: KPIs become postings / blind matches / consent requests / acceptance rate. The volume chart becomes matches per week. The load bar becomes the talent pool by pathway (college / cert / apprenticeship / direct). The table becomes blind talent cards. The list becomes the fairness and gap report.
- **`tallie-dashboard`** is the alternative if the portal is mainly a **table** (consent inbox, candidate pipeline). Its Instrument Serif headings and Geist Mono numbers are the closest match to a drawing-set title block.
- **Widget cards** for extra stat or chart tiles:

  | Widget | Component | Hard colors | Needs |
  |---|---|---|---|
  | `widget-1` | ApiUsageWidget: progress quota card | 0 | |
  | `widget-2` | StorageWidget | 0 | |
  | `widget-3` | SalesBreakdownWidget | 4 hex | recharts |
  | `widget-4` | RevenueWidget: donut with legend | 0 | recharts |
  | `widget-5` | RevenueOverviewWidget | 1 | recharts |
  | `widget-9` | EngagementsWidget | 0 | motion |

  widget-6, -7, and -8 need both `framer-motion` and `motion`.
- **Blind talent cards** (Connect): start from `profile-card-base` (0 hard colors, 36 token classes, has `"use client"`) or `expandable-profile-card-base` (3 palette classes, 1 Unsplash image), and add the consent-gating logic yourself.

### 4b. Landing page sections
- **Zero hard-coded colors**, so they inherit Foothold tokens directly: faq-1..6, footer-1..5, pricing-1..5, feature-4, widget-1/2/4/6/7/8/9.
- **Near zero:** testimonials-2 and -4 (2 each), stats-4 (3), cta-1 and cta-4 (4 each), feature-5 (6).
- **Heroes:** every hero hard-codes colors. The best options:
  - `hero-3`: 32 token classes plus 7 distinct white/black/zinc classes (9 matches).
  - `hero-41`: 5 palette + 3 hex, a serif "winter" theme, and a remote background image.
- **Navigation-1..7:** 87 to 162 palette classes plus 52 to 105 `dark:` classes each. **Build the nav yourself** (the shell already owns `CommandPalette` and `ThemeToggle`), or use the nav built into `hero-3`.
- **Animated product bits** (all have `-base` token twins):

  | Component | Use in Foothold |
  |---|---|
  | `step-indicator-base` | Plan pathway steps |
  | `labeled-progress-indicator-base` | |
  | `onboarding-checklist-base` | Prove |
  | `tags-base` | skill chips |
  | `continuous-tabs-base` | |
  | `status-picker-base` | |
  | `create-community` (+ `-base`) | Belong / circles |

---

## 5. Recommendations (6 items, exact commands, retheme effort)

Before any of these, run 1.2 and then `@custom-variant` / tokens from section 6, then preview with `--dry-run`.

### R1. `medesk-dashboard`: `/employers` shell. **Retheme: Medium** (colors Low, integration Medium)
```bash
npx shadcn@latest add @watermelon/medesk-dashboard --dry-run
npx shadcn@latest add @watermelon/medesk-dashboard
```
- **Installs:** npm `lucide-react`, `recharts@2.15.4` (pinned), `@fontsource/geist`, `@fontsource/geist-mono`, `@fontsource/instrument-serif`. The fonts are declared but this item never imports them, so you can uninstall them. shadcn: `avatar button collapsible dropdown-menu input-group sheet sidebar utils`.
- **Files:** 11 under `components/watermelon/medesk-dashboard/`:
  - `demo.tsx` and `dashboard-layout.tsx`
  - `dashboard.css` (4.1 KB)
  - `data.tsx` (33.5 KB of healthcare demo data, to replace)
  - `components/medesk/{dashboard-content, sidebar, topbar, navigation, theme-provider, icons, logo}.tsx`
- **Colors:** 0 hex, 0 palette classes. All colors come from tokens set in `dashboard.css`, in a light block `.medesk-dashboard` and a dark block `.medesk-dashboard.dark, .dark .medesk-dashboard`. To retheme:
  - (a) Delete the standard shadcn token lines from **both** blocks so the dashboard inherits Foothold's global tokens.
  - (b) Keep the 4 custom chart vars (`--dashboard-scheduled`, `--dashboard-completed`, `--dashboard-no-show`, `--dashboard-secondary`) and point them at the Foothold ink/grey ramp or accent. The bar chart and legend use them through `var(--dashboard-*)`.
  - (c) Change the dark selector to `[data-theme="dark"] .medesk-dashboard`.
- **Integration fixes:**
  - **No `"use client"` in any file.** The bundled ThemeProvider reads `localStorage` and `window.matchMedia` inside `useState` initializers, which crashes during SSR. It also writes `dark`/`light` classes on `<html>`, which fights Foothold's `data-theme`. **Delete the ThemeProvider wrapper from `demo.tsx`** and let the Foothold theme drive it.
  - Mount the dashboard from a client wrapper with `next/dynamic(..., { ssr: false })`. Watermelon's framework-support page recommends a ClientOnly boundary or `ssr: false` for SSR frameworks. Note that `ssr: false` must be called inside a Client Component.
  - Unscoped rules in `dashboard.css` (`[data-slot="dropdown-menu-content"] ...` padding) leak to every dropdown in the app. Prefix them with `.medesk-dashboard` or delete them.
  - Navigation is an internal context (`useDashboardNavigation`) with no router. Swap it for Next `Link` + `usePathname`, or keep it for one-page tabs.
  - For square drawing-set corners: set `--radius: 0`, then replace the 36 hard-coded `rounded-*` classes (`rounded-xl`, `rounded-2xl`, `rounded-lg`, etc.).
  - The 5 `asChild` uses mean you need a Radix-based shadcn init (see 1.2).

Sketch of the mount (my own code; paths assume the CLI writes under `web/src/components/watermelon/`, so confirm with `--dry-run`):
```tsx
// web/src/components/employer/EmployerDashboard.tsx
"use client";
import dynamic from "next/dynamic";
const Medesk = dynamic(() => import("@/components/watermelon/medesk-dashboard/demo"), { ssr: false });
export default function EmployerDashboard() { return <Medesk />; }
```

### R2. `widget-4` (RevenueWidget): donut chart card for "talent pool by pathway" or fairness. **Retheme: Low**
```bash
npx shadcn@latest add @watermelon/widget-4
```
- **Installs:** npm `lucide-react`, `recharts` (unpinned); shadcn `button`, `card`. Writes `components/ui/widget-4.tsx`.
- **Colors:** 0 hard-coded; uses token classes.
- **Fixes:** uses `useMemo` but has no `"use client"`, so add it as line 1. Flatten 3 rounded classes (`rounded-3xl`, `rounded-[30px]`).
- **Props:** `RevenueWidgetProps` with `title` and `data[]` (`id, label, value, numericValue, colorClass, fill, opacity`), so you can feed it API data directly.
- **Version risk:** if R1 is installed, npm resolves `recharts@2.15.4`, because only one version can live in `package.json`. UNVERIFIED whether the current shadcn `chart` expects v2 or v3, so run `npm ls recharts` after installing.

### R3. `feature-4` (Features4): landing "Try / Prove / Plan" three-card section with mini data viz. **Retheme: Low-Medium**
```bash
npx shadcn@latest add @watermelon/feature-4
```
- **Installs:** npm `lucide-react`, `react-icons`; shadcn `button`, `card`. Writes `components/ui/feature-4.tsx`. Has `"use client"`.
- **What it shows:** three cards, each with a mini viz: bar sparkline, ring percentage, and progress bars.
- **Colors:** 0 hard-coded. Bars and progress use `bg-primary`/`text-primary`. Watermelon's previews show lime green because of **their site theme**; with Foothold `--primary` set to ink, the cards render ink on paper.
- **Copy:** hard-coded (no props), so edit the text in the file.
- **Corners:** flatten 18 rounded classes (`rounded-3xl`, `rounded-4xl`, `rounded-[40px]`).

### R4. `stats-4` (FinanceSplitSection): landing "Central Valley by the numbers" split section. **Retheme: Low-Medium**
```bash
npx shadcn@latest add @watermelon/stats-4
```
- **Installs:** npm `lucide-react`; shadcn `badge`, `button`. Writes `components/ui/stats-4.tsx`. Has `"use client"` (uses `useRef`/`useState`).
- **Layout:** headline and two CTAs on the left, metric tiles on the right.
- **Colors:** 3 hard-coded icon tints (`text-blue-500`, `text-emerald-500`, `text-purple-500`). Swap them to `text-foreground` or the Foothold accent. The rest is tokens.
- **Copy:** fintech demo copy is hard-coded. Replace every number with a **cited** statistic and use `SourceLink`/`ProvenanceBadge`.
- **Corners:** flatten 9 rounded classes.

### R5. `hero-3` (Hero3): landing hero with built-in nav. **Retheme: Medium**
```bash
npx shadcn@latest add @watermelon/hero-3 --dry-run   # check where assets/logo-icon.tsx lands
npx shadcn@latest add @watermelon/hero-3
```
- **Installs:** npm `lucide-react`, `motion`, `react-icons`; shadcn `button`. Writes `components/ui/hero-3.tsx` + `assets/logo-icon.tsx`. The second file must resolve as `@/assets/logo-icon`, which means `web/src/assets/logo-icon.tsx`.
- **Props:** all copy is passed as props: `logo, logoText, navItems, signInText/Href, tagline, titleLine1, titleLine2, description, primaryCta*/secondaryCta*, backgroundImage, stats, scrollText/Href`.
- **Background:** the default `backgroundImage` is a remote Unsplash photo, and it only renders when truthy. Pass `backgroundImage=""` and draw a CSS grid or blueprint background instead.
- **Colors:** 7 distinct palette classes (`text-white`, `text-white/90`, `bg-white`, `text-black`, `text-zinc-100`, `text-zinc-300`, `divide-white/50`) assume dark imagery. Either keep the hero always ink (`#050505`) in both themes, or swap those classes to tokens.
- **Fixes:** uses `useState` + `motion/react` with no `"use client"`, so add it.
- **No preview:** the catalog thumbnail (`.../watermelonoriginalassets/hero-3.webp`) returned **404**, so I could not check how it looks. View it live at `https://ui.watermelon.sh/block/hero-3` before you commit to it.

### R6. `footer-2` (Footer2): landing footer with newsletter input. **Retheme: Low**
```bash
npx shadcn@latest add @watermelon/footer-2
```
- **Installs:** npm `lucide-react`; shadcn `button`, `input`. Writes `components/ui/footer-2.tsx`. No hooks, so it is server-safe.
- **Colors:** 0 hard-coded. The brand panel is `bg-primary`, so it turns into a solid ink block on paper (or paper on dark), which suits a title block.
- **Props:** fully prop-driven (`brandName, tagline, linkGroups, socialLinks, socialText, newsletterTitle/Subtitle/Placeholder`).
- **Corners:** flatten `rounded-[2.5rem]` and `rounded-xl`.

**Alternates:**
- `tallie-dashboard`: table-first portal, Medium effort. Same ThemeProvider/SSR fixes as R1. Its CSS `@import`s `@fontsource/*`; replace those with `next/font` if they fail to resolve.
- `widget-1`: quota/progress card, Low effort, 1 `asChild`.
- `faq-2`: FAQ with category tabs, Low effort, 0 hard colors.
- `cta-4`: CTA with a metrics phone mock, Low-Medium effort, 4 palette classes.
- `profile-card-base`: blind talent card base, Low effort.

**Avoid:**
- `landing-01`, `portfolio-dashboard` (react-router-dom).
- `navigation-*` (heavy palette use).
- `testimonials-2`: default avatars are **real developers' GitHub photos** (`github.com/gaearon.png`, `kentcdodds`, `leerob`, `rauchg`). Replace them with fictional personas tagged `FictionalTag` if you use it.
- `bento-02`: 311 KB (mostly the inline map component, `map.tsx`).

---

## 6. Retheme recipe: dark `#050505` / paper `#f4f4f1` drawing-set

The values below are my **suggested** tokens, not taken from Watermelon. The shell owner applies them in `web/src/app/globals.css`. Check AA contrast in both themes, as the contract requires.

```css
/* Tailwind v4: make every Watermelon `dark:` class follow Foothold's data-theme (syntax verified in Tailwind docs) */
@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));

:root, [data-theme="light"] {           /* paper */
  --background: #f4f4f1;  --foreground: #050505;
  --card: #f4f4f1;        --card-foreground: #050505;
  --popover: #f4f4f1;     --popover-foreground: #050505;
  --primary: #050505;     --primary-foreground: #f4f4f1;   /* turns Watermelon's lime accents into ink */
  --secondary: color-mix(in oklab, #050505 6%, #f4f4f1);   --secondary-foreground: #050505;
  --muted: color-mix(in oklab, #050505 6%, #f4f4f1);       --muted-foreground: color-mix(in oklab, #050505 62%, #f4f4f1);
  --accent: color-mix(in oklab, #050505 8%, #f4f4f1);      --accent-foreground: #050505;
  --border: color-mix(in oklab, #050505 22%, #f4f4f1);     --input: var(--border); --ring: #050505;
  --radius: 0rem;                                            /* square drawing-set corners */
  --sidebar: var(--background); --sidebar-foreground: var(--foreground); --sidebar-border: var(--border);
  --sidebar-accent: var(--accent); --sidebar-accent-foreground: var(--foreground);
  --sidebar-primary: var(--primary); --sidebar-primary-foreground: var(--primary-foreground); --sidebar-ring: var(--ring);
  --chart-1: #050505; --chart-2: color-mix(in oklab, #050505 70%, #f4f4f1); --chart-3: color-mix(in oklab, #050505 45%, #f4f4f1);
  --chart-4: color-mix(in oklab, #050505 25%, #f4f4f1); --chart-5: color-mix(in oklab, #050505 12%, #f4f4f1);
}
[data-theme="dark"] {                    /* ink */
  --background: #050505;  --foreground: #f4f4f1;
  --card: #050505;        --card-foreground: #f4f4f1;
  --popover: #0b0b0b;     --popover-foreground: #f4f4f1;
  --primary: #f4f4f1;     --primary-foreground: #050505;
  --secondary: color-mix(in oklab, #f4f4f1 8%, #050505);   --secondary-foreground: #f4f4f1;
  --muted: color-mix(in oklab, #f4f4f1 8%, #050505);       --muted-foreground: color-mix(in oklab, #f4f4f1 62%, #050505);
  --accent: color-mix(in oklab, #f4f4f1 10%, #050505);     --accent-foreground: #f4f4f1;
  --border: color-mix(in oklab, #f4f4f1 20%, #050505);     --input: var(--border); --ring: #f4f4f1;
  --chart-1: #f4f4f1; --chart-2: color-mix(in oklab, #f4f4f1 70%, #050505); --chart-3: color-mix(in oklab, #f4f4f1 45%, #050505);
  --chart-4: color-mix(in oklab, #f4f4f1 25%, #050505); --chart-5: color-mix(in oklab, #f4f4f1 12%, #050505);
}
```

**Per-item checklist:**
1. Delete or override any scoped token blocks in dashboard `dashboard.css` files. Remap their custom vars:
   - medesk: `--dashboard-*`
   - tallie: `--status-*`, `--source-*`, `--live`, `--trend`, `--sidebar-muted*`, `--font-*`
   - agndex: `--card-hover`, `--info`, `--input-addon-foreground`, `--sidebar-badge`, `--sidebar-muted*`
2. Replace `.dark` selectors with `[data-theme="dark"]`.
3. Search for leftover hard-coded colors: `grep -nE "(bg|text|border|fill|stroke)-(white|black|(zinc|neutral|gray|slate|stone|blue|emerald|purple|rose|lime|green)-[0-9]{2,3})|#[0-9a-fA-F]{6}" <file>`.
4. Flatten corners: `rounded-(lg|xl|2xl|3xl|4xl|\[[^]]+\])` → `rounded-none` (keep `rounded-full` for dots and avatars if you want).
5. Typography: medesk captions use the `font-mono` class. Map `--font-mono` in `@theme` to the shell's mono font so captions match `MonoLabel`.
6. Charts: recharts accepts SVG `<defs><pattern>` fills. Hatch patterns in `var(--chart-*)` read as drafting rather than colored bars, and they do not depend on color, which helps accessibility.
7. Motion: Watermelon guides say to tune reduced motion yourself. Gate `motion` animations on `useReducedMotion()` from `motion/react`, as required by the contract (`prefers-reduced-motion`).

---

## 7. License and attribution
- `WatermelonCorp/watermellon-registry`: MIT, "Copyright (c) 2025-present Watermelon Contributors" (`LICENSE` on `main`; 102 stars; last push 2026-09-30).
- `WatermelonCorp/watermelon-platform`: MIT, "Copyright (c) 2026 Watermelon Platform Contributors" (last push 2026-10-24).
- MIT requires keeping the copyright and permission notice in copies or substantial portions. Add one line to a `web/THIRD_PARTY_NOTICES.md` (or a header comment in each copied file) naming Watermelon UI (MIT) and linking the LICENSE URL above.
- The site's `/copyright` policy says some designs are inspired by other creators and get credited under "Inspired By" on the item page. Check the item page of anything you ship.
- `/terms` could not be fetched (repeated connection resets): **UNVERIFIED**.

## 8. Open items (UNVERIFIED)
- Which base `shadcn init` uses by default (Base UI vs Radix). Decide explicitly with `--base radix`.
- Exact on-disk paths the CLI chooses for `components/watermelon/...` and `assets/...` targets in a `src/` project. Use `--dry-run`.
- Whether `recharts@2.15.4` (medesk) conflicts with the recharts version the current shadcn `chart` component expects.
- The visual look of `hero-3`: its catalog preview image is 404.
- Watermelon MCP tool behavior: not exercised.

## 9. Sources (all retrieved 2026-10-24, 11:55 to 12:32 PDT)

**Watermelon site**
- https://ui.watermelon.sh/llms.txt
- https://ui.watermelon.sh/installation
- https://ui.watermelon.sh/cli
- https://ui.watermelon.sh/framework-support
- https://ui.watermelon.sh/guides/shadcn-registry
- https://ui.watermelon.sh/developers
- https://ui.watermelon.sh/copyright
- https://ui.watermelon.sh/sitemap.xml

**Watermelon API**
- https://ui.watermelon.sh/api/docs
- https://ui.watermelon.sh/openapi.json
- https://ui.watermelon.sh/api/v1/catalog/summary
- https://ui.watermelon.sh/api/v1/catalog/entries?kind=dashboards&limit=50 (plus `kind=templates` and `kind=blocks&category=...`)

**Watermelon registry**
- https://registry.watermelon.sh/registry.json
- https://registry.watermelon.sh/r/{name}.json: 144 block and dashboard items plus 12 animated items fetched

**Dashboard thumbnails**
- https://assets.watermelon.sh/components/medesk-dashboard-thumbnail.png
- https://assets.watermelon.sh/components/tallie-dashboard-thumbnail.png

**shadcn**
- https://ui.shadcn.com/r/registries.json (`@watermelon` entry)
- https://ui.shadcn.com/docs/cli
- https://ui.shadcn.com/docs/registry/registry-item-json

**Tailwind**
- https://tailwindcss.com/docs/dark-mode (`@custom-variant dark` syntax)

**GitHub**
- https://github.com/WatermelonCorp/watermellon-registry (license via `api.github.com/repos/WatermelonCorp/watermellon-registry/license`)
- https://github.com/WatermelonCorp/watermelon-platform (license via the API)
