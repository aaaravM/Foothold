# Foothold design direction (binding for all UI work)

> **User decisions (latest):** no ⌘K command palette, no "API online" indicator, no persona dropdown. It's an app with **real accounts**: sign in per tab (see CONTRACTS §13). The nav's right side holds only the account menu (initials, name, role, sign out) and the theme toggle.

The user's verdict on the first pass: **"looks so AI generated, no animations, nothing."** This document exists to fix that. Every UI decision should make the site feel like a small studio drew it by hand for this one product, not like a template.

## 1. Concept: a drawing set for a life, plotted live

Foothold is presented as an **engineering drawing set being plotted in front of you**. The signature graphic is a **pen-plotter elevation profile**: a schematic cross-section that starts on the flat Central Valley floor (Stockton, Lodi) and climbs east into the **Sierra foothills**, the literal "foothold". The six product chapters are **survey benchmarks** along that climb:

`TRY → PROVE → PLAN → LEARN → CONNECT → BELONG` (left to right, rising).

The profile is labeled `SCHEMATIC · NTS` (not to scale, a real drawing convention), so it carries no invented elevation numbers. Place names may appear as labels; no elevations.

## 2. Layout: editorial, asymmetric, gridded

- Strict 12-column technical grid with a visible hairline column overlay that can be toggled with the `G` key (like a design tool). Default: faint.
- Left-anchored hero and section heads. **No centered "title + tagline + two buttons" hero.** Content sits on the grid with deliberate empty columns.
- Right-margin annotations: notes, sources and figures sit in a margin column, connected to what they explain by thin **leader lines** and **numbered callouts** (①, ②; or `NOTE 1`).
- Details sit in **"DETAIL A" bubbles/frames** (a circle-and-tag convention from drawings), not generic cards.
- Vary scale dramatically: an 18vw wordmark next to 11px mono labels. Not every block is the same size.

## 3. Type

- **Hubot Sans** (display) uses its variable **width axis**. The wordmark is set wide (`wdth` ~125) and very large. **Mona Sans** for body at 17–18px, line height ~1.55. **Martian Mono** for labels, numbers, coordinates and the title block: 11–12px, uppercase, tracking ~0.12em, tabular numerals.
- Big numbers (real ones only) are set in Martian Mono or Hubot condensed, with a footnote mark linking to the source.

## 4. Motion system (Motion for React, `motion/react`)

Motion is not decoration. Each move should either draw something, reveal structure or respond to the user.

| Move | Where | Spec |
|---|---|---|
| **Plotter draw** | elevation profile, frames, dimension lines, diagrams | SVG `pathLength` 0→1, ease `[0.65, 0, 0.35, 1]`, 1.2–2.4 s, staggered; a small gold **pen head** dot rides the leading tip |
| **Kinetic wordmark** | hero "Foothold" | letters reveal by clip and stagger (~40 ms) while `font-variation-settings: "wdth"` eases from condensed (75) to wide (125) |
| **Scroll climb** | landing | `useScroll` + `useSpring` drive the pen head up the profile; each benchmark "pings" (survey-marker ring) when its chapter becomes active; the chapter's detail frame draws in |
| **Crosshair cursor** | hero / landing sheet area (pointer: fine only) | thin full-bleed crosshair lines plus a mono readout of x/y in mm on the sheet (like CAD); hidden on touch and for reduced motion |
| **Count-up** | real metrics only (from API / metrics.json / verified stats) | 600–900 ms, tabular numerals; never animate placeholders |
| **Bracket hover** | buttons, interactive frames, nav items | corner brackets snap in (120–160 ms); links draw their underline left to right |
| **Sheet intro** | each page load | registration marks and sheet border draw first (~400 ms), then content; total under 1 s |
| **Live readouts** | header / title block | ticking Valley clock ("STOCKTON 13:22 PDT"), sheet coordinates (37.9577° N, 121.2908° W for Stockton) |

Every move respects `prefers-reduced-motion`: show the final state instantly, with no crosshair or pen head. Animate only `transform`, `opacity`, `pathLength`, `clip-path` and font variations. Keep the main thread free and lazy-load heavy visuals.

## 5. Surface and color

- Dark default `#050505` and paper `#f4f4f1`, both with subtle **film grain** (SVG `feTurbulence` overlay, 3–5% opacity) and a hairline grid **radially masked** so it fades toward the edges.
- **One accent: sunlit gold (~#E7B24A).** Use it for the pen head, active benchmark, focus rings, and at most one emphasized word per view. Everything else is ink, its tints and hairlines. Semantic colors appear only for status.
- No drop shadows, no glassmorphism, no gradients except the grain/mask. Radius 0–2px. Borders are 1px hairlines.

## 6. Copy voice

Concrete, local and scene-based, never slogans. ✅ "Stockton, 7:02 a.m. The forklift alarm starts before you've found your gloves." ❌ "Empower your future with AI-driven career insights." Every number carries its source as a footnote. Fictional people are tagged FICTIONAL.

## 7. Banned "AI-generated" tells

Centered hero + tagline + two pill buttons · purple/blue gradients · glass blobs · emoji as icons · a row of three identical icon feature cards · "Unlock/Empower/Revolutionize" copy · rounded-2xl cards with shadows everywhere · stock illustrations · random sparkles · identical section rhythm (title, subtitle, grid) repeated down the page · placeholder numbers.

## 8. Hero composition (target)

1. **Top band** (mono): `SHEET 00 · COVER · DWG-000 · REV B` on the left; the ticking Stockton clock and coordinates on the right.
2. **Wordmark**: kinetic "Foothold", very large, left-aligned across ~9 columns.
3. **Thesis**: "Try the job. Prove the skill. Get the foothold." in large Mona Sans, each sentence revealing in turn.
4. **Margin note** (right column): the verified PPIC statistic as `NOTE 1` with a two-bar comparison drawn by the plotter (Valley vs rest of CA), plus a source link. Use only figures marked VERIFIED in `docs/research/stats.md`.
5. **Elevation profile**: spans the full width at the bottom of the hero and is plotted on load. Six benchmarks carry leader-line labels (TRY … BELONG), with Stockton and Lodi labeled on the valley floor and the foothills labeled at the right. It doubles as navigation: each benchmark scrolls to its chapter.
6. **Primary action**: a technical button "Start a workday ↵" with bracket corners, plus a quiet text link "See the measured models →" to /lab.

## 9. Visual verification (required)

Agents can't see the browser, so take screenshots with headless Edge and look at them with the Read tool:

```bash
E="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
"$E" --headless=new --disable-gpu --hide-scrollbars --user-data-dir="C:\\Users\\MUTTA\\AppData\\Local\\Temp\\edge-$RANDOM" \
  --window-size=1440,900 --virtual-time-budget=8000 \
  --screenshot="C:\\Users\\MUTTA\\OneDrive\\Desktop\\Foothold\\.logs\\shots\\<name>.png" "http://localhost:3000/<route>"
```

- Capture desktop 1440×900, a tall full page (1440×4200), mobile 390×844, and the paper theme. `?theme=light` must force the paper theme so screenshots can show it, which means ThemeScript reads the query param.
- `--virtual-time-budget` lets animations finish; use ~600 to catch a mid-animation frame.
- After each meaningful change: screenshot, look, critique against §7, iterate. Ship only what you'd be proud to show.
