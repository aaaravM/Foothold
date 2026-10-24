# Inspiration: aaaravm.github.io + theapexrobotics.com, translated for Foothold

The user's verdict: "too much information", "too AI generated", wants "amazing UI, lots of complex animations, but works perfectly", in the spirit of aaaravm.github.io and theapexrobotics.com.

## Sources and method

- **aaaravm.github.io** (the user's own portfolio). It is blocked on this network. The public repo is mirrored on jsDelivr (`/gh/aaaravm/aaaravm.github.io@HEAD/`), but only as Next 16 **source** (static export via GitHub Actions; there is no built `out/` or gh-pages branch). Building it needs `three`, `lenis`, `geist` and `dither-plugin`, which aren't installed, and npm installs aren't allowed. So I read every component (about 50 files) and rebuilt the core techniques in a small motion study page I wrote myself, then captured that with CDP at 1440x900.
- **theapexrobotics.com**: fetched remotely with WebFetch (`/`, `/robot`, `/code`). Its markup reveals structure and interactions but not class names.
- **Key finding:** Foothold's current "drawing set" look (DWG-001, REV, SCALE NTS, SHEET 01 OF 07, `[ C1 / TRY ] 01 / 06`, title-block footer) is lifted from **Apex**: Apex's pages are "sheets" and its footer is a title block. That's the part the user is asking "what is all of this?" about. The parts of Apex worth taking are its **interactive explainers** (scroll-driven 3D, live playgrounds, step-through playback), not its drafting metadata.

### Screenshots (`C:/Users/MUTTA/OneDrive/Desktop/Foothold/.logs/shots/inspo/`)

| File | Shows |
|---|---|
| `study-01-hero-t180ms.png` | Hero mask wipe starting; lines still blurred (blur-lift entrance) |
| `study-02-hero-t600ms-scramble.png` | Mid-animation: headline wiped in, mono subline decoding from glyph noise, tagline/CTAs still blurred, ambient dot field rippling near the pointer |
| `study-03-hero-settled-button-roll-mid.png` | Settled hero; primary button letters mid "text roll" |
| `study-04-manifesto-words-lighting.png`, `study-05-manifesto-lit.png` | Scroll-linked word-by-word lighting (dim 0.3 to 1) |
| `study-06-card-hover-tilt-scan.png` | Card hover: 3D tilt, accent scan sweep, arrow disc fills with signal color |
| `aaaravm-og.png`, `aaaravm-mentolab-thumb.webp`, `aaaravm-formation-graph.webp` | The portfolio's real art (dot-particle "formations" on near-black) |
| `foothold-now-home.png`, `foothold-now-sim.png`, `foothold-now-path.png`, `foothold-now-footer.png` | Foothold before the redesign, for contrast (dense uppercase mono labels, boxed grids) |

## What the portfolio actually does (exact values from source)

- **Palette:** one ink and one signal color. `--ink #050505`, `--ink-2 #0c0c0c`, `--ink-3 #141413`, `--fg #ecebe7`, `--fg-dim #9a9994`, `--fg-faint #5d5c58`, hairlines `rgba(255,255,255,.08)` and `.16`, signal `#ff5b1f`. The source's own comment: "One ink, one signal colour. Everything else is grey dots."
- **Easing:** almost everything uses `cubic-bezier(0.16,1,0.3,1)` (expo-out). Overlays and the menu wipe use `cubic-bezier(0.76,0,0.24,1)`.
- **Durations:** entrances 1.1 to 1.4s, hovers 0.5s, image zoom 1.4s, stagger 35 to 80ms, springs `{stiffness:220, damping:16, mass:0.4}` (magnetic) and `{160, 18}` (card tilt).
- **Type:** Geist Sans for body. Display uses five Geist Pixel faces that the letters cycle through before settling on one. Mono "hud" labels are used sparingly: 10.5px, tracking 0.14em, uppercase, tabular numbers. Hero name `clamp(88px,15.8vw,268px)`, leading 0.78, tracking -0.03em. Section h2 `clamp(34px,4.4vw,68px)`, tracking -0.04em. Body 17 to 23px.
- **Layout:** side gutter `3.2vw` (20 to 32px on mobile), sections `min-h-svh` with `py-[14svh]` to `18svh`, bento grid `gap-3` with 2 wide cards. Text takes about 44% of the width; the art owns the other half.
- **Global chrome:** Lenis smooth scroll (lerp 0.085), a reticle cursor (`mix-blend-difference`, rotates 45 degrees over links), film grain at 7% overlay, a radial vignette, and progressive blur bands at the top and bottom edges. The nav hides on scroll down and returns on scroll up.
- **Signature:** a single fixed WebGL particle field that **morphs into a different "formation" for each section**. Sections declare it with `data-formation` and `data-fx/fy/fs` for layout; the morph runs 1.5s with a noise burst in the middle.
- **Reduced motion:** honored everywhere (`MotionConfig reducedMotion="user"`, a CSS kill switch, and per-component checks).

## 14 patterns to borrow in spirit

All of these work with what's installed: Next + `motion/react` + CSS. No three.js and no Lenis (neither is installed). Use one shared easing constant: `EASE = [0.16, 1, 0.3, 1]`.

1. **Blur-lift entrance** (every first view). `initial {opacity:0, y:24, filter:"blur(10px)"}` to `{opacity:1, y:0, filter:"blur(0px)"}`, 1.1s EASE. `whileInView` with `viewport {once:true, margin:"0px 0px -12% 0px"}`. Stagger siblings 0.08 to 0.12s. Build one `<Reveal>` component and use it for page headers, cards and panels.
2. **Mask-wipe headline.** Wrap the page title in `motion.div` with `clipPath: "inset(0 0 100% 0)"` and `y: 40`, animating to `inset(0 0 -10% 0)` and `y: 0` over 1.4s EASE. The negative bottom inset keeps descenders visible. One per page, on the page title only.
3. **Split-word rise** for section headings. Wrap each word in `span.inline-block.overflow-hidden` (pb 0.12em) with an inner `motion.span` going from `{y:"115%", rotate:4}` to `{y:0, rotate:0}`, 1s, stagger 45ms. Set `aria-label` on the parent and `aria-hidden` on the pieces.
4. **Scramble decode** for short labels: the career name on Sim cards, the end-of-shift verdict, a number that changes. Use the glyph set `01#%&*+=<>/|_-:;[]{}?!$@`. Resolve character i once `t >= (i/n)*0.65 + 0.35`. Repaint at most every 32ms with rAF, 700 to 1300ms total, and replay on hover. Keep it to 30 characters or fewer, and to one or two per screen.
5. **Text roll on buttons and links.** Two stacked letter rows inside an overflow-hidden span. On hover each letter moves y 0 to -100% while its twin moves 100% to 0, easeInOut, 35ms per-letter stagger (or a centre-out stagger for centred labels). Skiper58 `TextRoll` is this pattern; use it on the nav and primary CTAs.
6. **Swap arrow.** Two copies of the arrow SVG in a `size-[0.8em] overflow-hidden` box. On group-hover the first exits in the arrow's direction and the second enters from the opposite side, 500ms EASE. Use it on every Start/Open/Next link.
7. **Magnetic primary CTA.** Spring-follow the pointer: offset times 0.25 to 0.32, `useSpring {stiffness:220, damping:16, mass:0.4}`, mouse pointer only, reset on leave. Use it only on the one primary action per screen (Start workday, Build my path, Sign up).
8. **Card hover: tilt, scan, fill.** Wrap in `perspective:1200`, set rotateX/Y from pointer position (±3 to 6 degrees, spring `{160,18}`). An accent gradient band 1/4 wide sweeps across the card media on hover (translateX to 620%, 1.1s). The arrow disc fills with the signal color, the border goes from hairline to strong, and the media scales 1.06 over 1.4s. **Use this on the Sim career picker** (see `study-06`), with fewer words per card (title, one line, wage) so the motion does the work.
9. **Scroll-lit paragraph.** On the landing "how it works" statement, each word goes from opacity 0.34 to 1 as `useScroll({target, offset:["start 0.88","end 0.7"]})` passes its slot (window = slot × 1.7, so neighbours overlap). An optional 2px signal caret blinks at the frontier (`steps(1)`, 1.05s). Landing page only.
10. **Section-aware ambient dot field (Foothold's signature, replacing the elevation profile).** One fixed 2D `<canvas>`: an 18px dot grid at about 6% white. Near the pointer, dots brighten toward the accent with a ripple `sin(r/40 - t/600)` within 320px, and the grid drifts at 0.15× scroll. Each page can pass a formation prop that changes what the dots form, morphed over 1.2s: a dot map of the Central Valley with the user's chosen location pulsing (Path, location picker), clustered nodes (Skills), a ring (Circles), a clock filling hour by hour (Workday). Cap it at 30fps, pause it on `visibilitychange`, render it static for reduced motion, and keep it behind content with `pointer-events:none`.
11. **Live step-through playback** (from Apex `/code` "The Loop" and its solver). Show how the system reasons as a short animated sequence with Pause/Replay. In Foothold this is the "Behind the scenes" TracePanel, **collapsed by default**. When opened, steps reveal one at a time (120ms stagger, height via `layout`, 0.5s EASE), and Replay re-runs them. Explain things by showing the motion, not with paragraphs.
12. **Interactive playground over static specs** (from Apex `/robot` aim playground). Where Foothold has numbers, let people move them. On Path: drag weekly hours or budget and watch the plan re-solve (debounce 250ms; numbers count up with `animate(from, to, {duration:0.6, ease:EASE})`). Use one bar or ring instead of a table.
13. **Hide-on-scroll nav plus a full-screen mobile menu.** The header drops to y -90 after 240px when scrolling down (delta > 2) and returns on scroll up (delta < -4), 0.8s EASE. The mobile menu wipes in with clipPath `inset(0 0 100% 0)` to `inset(0)` over 0.7s `[0.76,0,0.24,1]`, links rise from y 110% with a 60ms stagger, Escape closes it, and `main` is inert while it's open.
14. **Shared-layout active indicators.** The active nav tab, current Sim step, selected career and selected chip use `motion.span layoutId="..."` (0.6s EASE) so the highlight glides between items instead of blinking. Use one thin accent bar or underline.

**Optional polish** if time allows: grain at 5 to 7% overlay (Foothold already has `--grain-image`); a soft fade under the sticky header; a reticle cursor only on fine pointers and only on the landing page.

## Recommended visual direction for Foothold

**Idea: "a quiet dark room with one warm light."** Keep the near-black base and gold accent Foothold already has (`--bg #050505`, `--accent #e7b24a`; the light theme keeps its own tokens). Cut everything else back to grey, so that color and motion mean "this is the thing to do now."

- **Color:** 1 ink, 3 greys, 1 signal. Use semantic colors (success, warning, danger) only for real states like errors and saved toasts, never as decoration or badges. Hairlines at 8% and 16% instead of boxed grids. Remove the background grid and column overlay from app pages.
- **Type:**
  - **Hubot Sans** for the page title: large and tight (`clamp(48px,7vw,112px)`, leading 0.9, tracking -0.04em), one per page.
  - **Mona Sans** at 17 to 18px, sentence case, for everything people read.
  - **Martian Mono** only for numbers (wages, hours, clock times) and at most one small kicker per section (accent dot, word, and a hairline that draws in over 1.2s).
  - **No uppercase letter-spaced mono on card metadata, nav items or buttons.** The `7 EVENTS`, `MEDIAN WAGE · STOCKTON-LODI MSA` and `WORKDAY PATH SKILLS` rows are the main source of noise in `foothold-now-sim.png`.
- **Spacing and rhythm:** gutter `clamp(20px,3.2vw,48px)`. Page header gets pt about 12svh; sections get py about 10svh. Card grid gap 12px, radius 16px, padding 24px. A screen shows **one primary action, one heading and at most about 3 supporting facts**. Everything else goes into a disclosure ("More about this job", "Behind the scenes", closed by default).
- **Layout:**
  - **Desktop pages:** asymmetric two columns (text about 44%, live art or interactive about 56%). Stack them on mobile, with no horizontal scroll at 390px.
  - **Workday sim:** a single centred column, max 680px. Scene text first, then the choices as big rows with the text roll and swap arrow on hover. Coworker reactions slide in (x -16 to 0, 0.5s EASE). Progress is a thin top bar plus "3 of 5", not a labelled stepper.
- **Motion language:**
  - **Entrances** are slow and soft (1.1 to 1.4s expo-out, blur 10px to 0).
  - **Hovers** are quick and physical (0.4 to 0.5s, springs).
  - **State changes** glide (`layoutId`).
  - **Numbers** count up.
  - **Only the ambient field runs continuously**, and it stays at the edge of attention.
  - **Reduced motion** is respected everywhere (`<MotionConfig reducedMotion="user">` in the root layout plus a CSS kill switch).
- **Footer:** one quiet block. "Foothold", then small dim credits: the O*NET 31.0 attribution (USDOL/ETA, CC BY 4.0 link, modified notice), the UI library credits and the font credits. 12px in `--ink-faint`. Nothing else.

## Do NOT

- **No drafting metadata anywhere:** DWG, REV, SCALE, SHEET, DRAWN BY, `[ C1 / TRY ] 01 / 06`, coordinates, live clocks, "SCHEMATIC · NTS" or title blocks. This is Apex's identity, and the user rejected it.
- **No provenance badges or disclaimers in the app:** no REAL/SAMPLE/SYNTHETIC/FICTIONAL badges and no "fictional/fake" notes. A source tooltip on a wage is the maximum; honesty notes go on `/about`.
- **No uppercase letter-spaced mono** for body, card metadata, nav or buttons. At most one kicker per section.
- **Don't box everything:** no visible grid backgrounds, no bordered table cells for picking careers, no nested borders.
- **No generic AI tells:**
  - centred hero with a gradient blob and 3 feature cards
  - purple or blue gradients
  - glass panels everywhere
  - emoji icons
  - "unlock your potential" copy
  - long rows of identical cards
- **Don't animate everything at once.** One signature effect per viewport. Scramble and pixel effects are for short labels only, never paragraphs or long lists. No infinite loops in the content area except the ambient field.
- **No scroll-jacking, Lenis or three.js** (not installed, and they'd risk the demo). Use native scroll with `useScroll`.
- **Don't hide content behind animation:** if JS is slow, content must still appear (use `once` and a generous viewport margin, and never leave a permanent `opacity:0`).
- **No open-by-default "Behind the scenes", no elevation profile,** and no decorative charts that carry no data.
- **No custom cursor in app flows** (Sim, Path, forms).
- **Copy nothing verbatim:** none of the portfolio's text, images, pixel fonts or code. Re-implement the techniques in Foothold's own type and colors (the motion study uses only self-written code).
