# Skiper UI: research notes for Foothold

- **Retrieved:** Sat Oct 24 2026, 13:28 to 13:42 PDT, by the UI library integrator.
- **Scope:** how to install, which components are FREE (as marked on the site), dependencies, license terms, and which free items fit the drawing-set language in `docs/DESIGN_DIRECTION.md`.
- **Labels:** VERIFIED = fetched and confirmed. UNVERIFIED = not confirmed, with the reason.
- **Hard rule (brief + CONTRACTS section 1):** FREE components only. Never install a premium item, never use the Pro registry entry, never work around the paywall.

## 1. Install (VERIFIED, quoted from https://skiper-ui.com/docs/quick-start)

> skiper-UI is part of trusted shadcn registries. [...] just copy the command and paste it in your terminal

```bash
npx shadcn add @skiper-ui/skiper40
```

The page shows this CLI output:

```
✔ Checking registry.
✔ Created 1 file:
  - src/components/ui/skiper-ui/skiper40.tsx
```

and then says `import { Skiper40 } from '@/components/v1/skiper40';`. That import path does not match the file it just created; use the created path (`@/components/ui/skiper-ui/skiper40`). VERIFIED in this repo: the CLI wrote `src/components/ui/skiper-ui/<name>.tsx`.

- **Namespace:** `@skiper-ui` is in the official shadcn directory (VERIFIED in `https://ui.shadcn.com/r/registries.json`, status "healthy") with URL `https://skiper-ui.com/registry/{name}.json`. No `components.json` edit is needed for free items. When we installed, shadcn CLI 4.22.1 wrote `"@skiper-ui": "https://skiper-ui.com/registry/{name}.json"` into `web/components.json` by itself (public URL, no auth header).
- **Pro only (do NOT use):** the quick-start also documents a Pro setup: a `SKIPER_LICENSE_KEY` in `.env.local` plus a `registries["@skiper-ui"]` entry pointing at `https://skiper-ui.com/r/{name}.json` with an `Authorization: Bearer ${SKIPER_LICENSE_KEY}` header. Foothold has no license and must not add this.
- **Manual path (not used):** `pnpm add clsx framer-motion lucide-react tailwind-merge` plus a `cn` helper. Prerequisites listed: framer-motion, tailwindcss, react, clsx, lucide-react, react-use-measure, gsap.
- Versions: the page states no Tailwind/React/Next requirements (UNVERIFIED beyond what the CLI installed).

## 2. Free vs premium (VERIFIED)

How the site marks it: the quick-start says "you can see the premium symbol next to the paid components" on `/components`. In a headless-Edge screenshot of https://skiper-ui.com/components, paid cards carry a `$` coin icon in the top-right corner; free cards show a dashed circle instead. The page's data bundle (`/_next/static/chunks/2746-*.js`) has a `tier` field per component (`"free"` or `"paid"`), and the site's own Free/Pro filter maps `{free:"free", pro:"paid"}`. The two agree for every card checked (skiper2 Dynamic island `$`, skiper19/40/58/37/101/106 dashed circle).

**37 free items** (id, name): skiper3 Apple play button · skiper4 Theme toggle buttons · skiper16 Card stack scroll · skiper17 Card stack with gsap and rotate · skiper19 Svg follow scroll · skiper25 Music toggle btn · skiper26 Theme toggle btn · skiper28 3D perspective text · skiper30 Oliver parallax · skiper31 Text Scroll animation · skiper34 Scroll images reveal 003 · skiper37 Animated number · skiper39 Canvas crowd · skiper40 CssLink · skiper41 Progressive Blur · skiper47 Perspective carousel · skiper48 Card swipe carousel · skiper49 Inverted perspective carousel · skiper50 Creative carousel 001 · skiper51 Creative carousel 002 · skiper52 ExpandOnHover · skiper53 ExpandOnHover vertical · skiper54 Shadcn clipPath Carousal · skiper58 Text roll navigation · skiper61 Mouse follow animations · skiper62 Loop animation hook · skiper63 Apple squicircle effect · skiper64 Gooey Effect · skiper65 Breakpoint indicator · skiper66 SVG clip path mask · skiper67 Video player 001 · skiper87 Scroll with fade effect · skiper89 Scroll progress 001 · skiper99 Animated icons 002 · skiper101 Custom tooltip · skiper102 Debug Pannel · skiper106 Smooth caret input.

**Premium (never install):** everything else, including skiper2 **Dynamic island** (so the sim-status island comes from Cult UI instead), skiper27 Rolling text, skiper59 Drawing cursor effect, skiper70 Text reveal box, skiper72 Horizontal Text reveal, skiper92 Vercel Command Search.

## 3. Picks for Foothold (installed)

| Item | Why it fits | npm deps (registry JSON) | Files written |
|---|---|---|---|
| `skiper19` Svg follow scroll | a stroke drawn by scroll progress (`useScroll` → `pathLength`) is the plotter-draw move | `framer-motion` | `src/components/ui/skiper-ui/skiper19.tsx` |
| `skiper58` Text roll navigation | staggered letter roll on hover for nav items and mono labels | `framer-motion` | `src/components/ui/skiper-ui/skiper58.tsx` |
| `skiper40` CssLink | links whose underline draws left to right (DESIGN_DIRECTION section 4 "links draw their underline") | none (`next/link`) | `src/components/ui/skiper-ui/skiper40.tsx` |

```bash
cd web
npx shadcn@latest add @skiper-ui/skiper19 @skiper-ui/skiper58 @skiper-ui/skiper40 --dry-run
npx shadcn@latest add @skiper-ui/skiper19 @skiper-ui/skiper58 @skiper-ui/skiper40 --yes
```

- `framer-motion` resolved to **14.6.0**, the same version `motion@14.6.0` already depends on, so npm dedupes it (`npm ls framer-motion`).
- Rejected free items: skiper31 (pulls in `lenis` smooth scrolling for the whole page), skiper37 (four deps and 28 hard-coded colors), carousels (swiper), image effects (need photos; Foothold uses none).

## 4. License and attribution (VERIFIED)

- Quick-start, "License & Usage": "Free to use and modify in both personal and commercial projects. **Attribution to Skiper UI is required when using the free version.** No attribution required with Skiper UI Pro." The same text is in the header comment of every installed file.
- The quick-start also says most components "are recreations of the best out there" and credits the originals; skiper19's header credits comgio.ai and skiper40's credits cursor.com.
- Terms of Service (https://skiper-ui.com/docs/terms-of-service, last updated September 07, 2025) restrict republishing or redistributing *website material* "unless otherwise stated"; the component license above is the "otherwise stated" part. We do not republish the site's demos, videos or copy.
- **Action for Foothold:** keep the header comments, and show a visible credit "Motion effects: Skiper UI (free components)" with a link to https://skiper-ui.com on a public page (About credits or the site footer; the owners of those files decide where).

## 5. Sources (retrieved 2026-10-24)

- https://skiper-ui.com/docs/quick-start
- https://skiper-ui.com/components (HTML, data chunk, and two headless-Edge screenshots)
- https://skiper-ui.com/docs/terms-of-service
- https://skiper-ui.com/registry/skiper19.json, skiper31, skiper37, skiper40, skiper58, skiper61, skiper89 (registry items read before installing)
- https://ui.shadcn.com/r/registries.json (`@skiper-ui` entry)
