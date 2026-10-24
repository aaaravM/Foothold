/**
 * The drawing set: every route is a numbered sheet (docs/CONTRACTS.md section 8).
 * Nav, TitleBlock, SheetFrame and the hero's sheet band all read from here.
 */

export type SheetId = "home" | "sim" | "path" | "graph" | "employers" | "inbox" | "circle" | "lab" | "about" | "demo";

/** Who the sheet is issued to (CONTRACTS section 13): learners, employers, or everyone. */
export type SheetAudience = "learner" | "employer" | "public";

/** Signed-in account kind as the nav sees it; null = signed out (or still loading). */
export type NavAccountKind = "learner" | "employer" | null;

export interface Chapter {
  /** 1-based */
  index: number;
  total: number;
  /** short uppercase word, e.g. "TRY" */
  label: string;
}

export interface SheetMeta {
  id: SheetId;
  href: string;
  /** "01".."07"; "00" for the cover (landing); "DEMO" for the demo sheet */
  sheet: string;
  /** short uppercase code for nav and sheet headers, e.g. "SIM" */
  code: string;
  /** human title, e.g. "Sim" */
  title: string;
  dwg: string;
  /** one-line purpose (mobile sheet index, placeholders) */
  description: string;
  chapter?: Chapter;
  /** shown in the main sheet nav (for its audience) */
  inNav: boolean;
  /** number printed before the code in mobile lists ("01"); null prints the code alone (INBOX) */
  navNumber: string | null;
  /** app-first label shown in the top nav ("Workday"); falls back to title */
  navLabel?: string;
  audience: SheetAudience;
  /** counts toward "SHEET x OF 07" */
  numbered: boolean;
}

/** Number of numbered sheets in the set ("SHEET x OF 07"). */
export const TOTAL_SHEETS = 7;

/** Story chapters for the six working sheets; About is the appendix. */
export const TOTAL_CHAPTERS = 6;

/** Title-block constants. DATE is the revision date of this drawing set. */
export const DRAWING = {
  rev: "B",
  scale: "NTS",
  drawnBy: "Foothold team",
  date: "2026-10-24",
} as const;

/** Stockton, CA: the sheet coordinates printed in the hero band. */
export const STOCKTON = {
  name: "STOCKTON",
  lat: "37.9577° N",
  lon: "121.2908° W",
  timeZone: "America/Los_Angeles",
} as const;

export const SHEETS: readonly SheetMeta[] = [
  {
    id: "home",
    href: "/",
    sheet: "00",
    code: "COVER",
    title: "Foothold",
    dwg: "DWG-000",
    description: "Cover sheet: what Foothold is",
    inNav: false,
    navNumber: "00",
    audience: "public",
    numbered: true,
  },
  {
    id: "sim",
    navLabel: "Workday",
    href: "/sim",
    sheet: "01",
    code: "SIM",
    title: "Sim",
    dwg: "DWG-001",
    description: "Try a shift in a Central Valley career",
    chapter: { index: 1, total: TOTAL_CHAPTERS, label: "TRY" },
    inNav: true,
    navNumber: "01",
    audience: "learner",
    numbered: true,
  },
  {
    id: "path",
    navLabel: "Path",
    href: "/path",
    sheet: "02",
    code: "PATH",
    title: "Path",
    dwg: "DWG-002",
    description: "Plan a route that fits your hours, budget and commute",
    chapter: { index: 2, total: TOTAL_CHAPTERS, label: "PLAN" },
    inNav: true,
    navNumber: "02",
    audience: "learner",
    numbered: true,
  },
  {
    id: "graph",
    navLabel: "Skills",
    href: "/graph",
    sheet: "03",
    code: "GRAPH",
    title: "Graph",
    dwg: "DWG-003",
    description: "See how skills, courses and jobs connect",
    chapter: { index: 3, total: TOTAL_CHAPTERS, label: "LEARN" },
    inNav: true,
    navNumber: "03",
    audience: "learner",
    numbered: true,
  },
  {
    id: "employers",
    navLabel: "Employers",
    href: "/employers",
    sheet: "04",
    code: "EMPLOYERS",
    title: "Employers",
    dwg: "DWG-004",
    description: "Blind, consent-gated talent view for employers",
    chapter: { index: 4, total: TOTAL_CHAPTERS, label: "PROVE" },
    inNav: true,
    navNumber: "04",
    audience: "employer",
    numbered: true,
  },
  {
    id: "circle",
    navLabel: "Circles",
    href: "/circle",
    sheet: "05",
    code: "CIRCLE",
    title: "Circle",
    dwg: "DWG-005",
    description: "Peer circles and a practice coach",
    chapter: { index: 5, total: TOTAL_CHAPTERS, label: "BELONG" },
    inNav: true,
    navNumber: "05",
    audience: "learner",
    numbered: true,
  },
  {
    id: "inbox",
    navLabel: "Inbox",
    href: "/inbox",
    sheet: "04",
    code: "INBOX",
    title: "Inbox",
    dwg: "DWG-004",
    description: "Approve or decline employer contact requests",
    chapter: { index: 4, total: TOTAL_CHAPTERS, label: "PROVE" },
    inNav: true,
    navNumber: null,
    audience: "learner",
    numbered: true,
  },
  {
    id: "lab",
    href: "/lab",
    sheet: "06",
    code: "LAB",
    title: "Lab",
    dwg: "DWG-006",
    description: "Models, metrics and fairness checks",
    chapter: { index: 6, total: TOTAL_CHAPTERS, label: "VERIFY" },
    inNav: false,
    navNumber: "06",
    audience: "public",
    numbered: true,
  },
  {
    id: "about",
    href: "/about",
    sheet: "07",
    code: "ABOUT",
    title: "About",
    dwg: "DWG-007",
    description: "Sources, methods, licenses and limits",
    inNav: false,
    navNumber: "07",
    audience: "public",
    numbered: true,
  },
  {
    id: "demo",
    href: "/demo",
    sheet: "DEMO",
    code: "DEMO",
    title: "Demo",
    dwg: "DWG-008",
    description: "Presenter run of show (unlinked)",
    inNav: false,
    navNumber: null,
    audience: "public",
    numbered: false,
  },
];

/** Every sheet that can appear in the nav, in nav order (filter with navSheetsFor). */
export const NAV_SHEETS: readonly SheetMeta[] = SHEETS.filter((s) => s.inNav);

/**
 * App-first nav (user decision): the tabs are the product, not how it was built.
 * Signed out sees the features (each asks to sign in); learners and employers see their own tools.
 * Lab and About live in the footer.
 */
const NAV_BY_KIND: Record<"public" | "learner" | "employer", readonly SheetId[]> = {
  public: ["sim", "path", "graph", "circle", "employers"],
  learner: ["sim", "path", "graph", "circle", "inbox"],
  employer: ["employers", "graph"],
};

export function navSheetsFor(kind: NavAccountKind): readonly SheetMeta[] {
  return NAV_BY_KIND[kind ?? "public"].map((id) => getSheet(id));
}

const BY_ID = new Map<SheetId, SheetMeta>(SHEETS.map((s) => [s.id, s]));

export function getSheet(id: SheetId): SheetMeta {
  const s = BY_ID.get(id);
  if (!s) throw new Error(`Unknown sheet: ${id}`);
  return s;
}

/** Sheet for a pathname: exact match, else the longest matching prefix ("/sim/abc" -> sim), else the cover. */
export function sheetForPath(pathname: string | null | undefined): SheetMeta {
  const home = BY_ID.get("home") as SheetMeta;
  if (!pathname) return home;
  const clean = pathname.split(/[?#]/)[0].replace(/\/+$/, "") || "/";
  if (clean === "/") return home;
  let best: SheetMeta | undefined;
  for (const s of SHEETS) {
    if (s.href === "/") continue;
    if (clean === s.href || clean.startsWith(`${s.href}/`)) {
      if (!best || s.href.length > best.href.length) best = s;
    }
  }
  return best ?? home;
}

/** True if `pathname` belongs to `sheet` (nav active state). */
export function isSheetActive(sheet: SheetMeta, pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  return sheetForPath(pathname).id === sheet.id;
}

/** "SHEET 01 OF 07", "SHEET 00 OF 07" (cover) or "SHEET DEMO" (outside the numbered set). */
export function sheetOfLabel(meta: SheetMeta): string {
  return meta.numbered ? `SHEET ${meta.sheet} OF ${String(TOTAL_SHEETS).padStart(2, "0")}` : `SHEET ${meta.sheet}`;
}

/** Props for <SheetFrame> straight from the registry: <SheetFrame {...sheetFrameProps("sim")}>. */
export function sheetFrameProps(id: SheetId): { sheet: string; dwg: string; title: string; code: string; chapter?: Chapter } {
  const s = getSheet(id);
  return { sheet: s.sheet, dwg: s.dwg, title: s.title, code: s.code, chapter: s.chapter };
}

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}
