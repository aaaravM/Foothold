/*
 * Watermelon UI "medesk-dashboard" (MIT, Watermelon Contributors), adapted for Foothold.
 *
 * The original healthcare demo data (patients, doctors, remote profile photos, invented
 * KPIs) is gone. This file now holds:
 *   1. the employer-portal navigation (CONTRACTS section 13: postings, talent, consent
 *      requests, fairness, gap report), and
 *   2. the data shape the dashboard widgets render, with one real data set: the regional
 *      gap report. Every number below is copied from docs/research/stats.md (VERIFIED,
 *      provenance REAL) with its source URL. Do not add numbers that are not sourced.
 *
 * Employer pages feed their own API data through the same types.
 */
import type { ComponentType, SVGProps } from "react";
import {
  FileTextIcon,
  InboxIcon,
  LandmarkIcon,
  LayoutListIcon,
  ScaleIcon,
  UsersRoundIcon,
} from "lucide-react";
import type { Provenance } from "@/lib/types";

export type NavIcon = ComponentType<SVGProps<SVGSVGElement>>;

export type NavigationItem = {
  name: string;
  href: string;
  icon: NavIcon;
  badge?: string;
  /** API that feeds this view (shown in the not-wired state) */
  api?: string;
};

export type NavigationGroup = {
  label: string;
  collapsible?: boolean;
  items: NavigationItem[];
};

export const navigationGroups: NavigationGroup[] = [
  {
    label: "Hiring",
    collapsible: false,
    items: [
      { name: "Gap report", href: "/", icon: LandmarkIcon, api: "/api/employer/gap-report" },
      { name: "Postings", href: "/postings", icon: FileTextIcon, api: "/api/employer/postings" },
      { name: "Talent", href: "/talent", icon: UsersRoundIcon, api: "/api/employer/talent" },
      {
        name: "Consent requests",
        href: "/consent",
        icon: InboxIcon,
        api: "/api/employer/consent-requests",
      },
    ],
  },
  {
    label: "Audit",
    collapsible: true,
    items: [
      { name: "Fairness", href: "/fairness", icon: ScaleIcon, api: "/api/employer/fairness" },
      { name: "Method notes", href: "/method", icon: LayoutListIcon },
    ],
  },
];

/** The signed-in organization shown in the sidebar footer (all Foothold employers are fictional). */
export type DashboardOrg = {
  name: string;
  initials: string;
  role?: string;
  fictional?: boolean;
};

export const defaultOrg: DashboardOrg = {
  name: "Tri-Valley Freight",
  initials: "TV",
  role: "Employer",
  fictional: true,
};

/* ------------------------------------------------------------------ */
/* Widget data shapes                                                  */
/* ------------------------------------------------------------------ */

export type DashboardSource = {
  /** short citation, e.g. "PPIC, Aug 2024, Fig. 5" */
  label: string;
  href: string;
  provenance: Provenance;
  /** method / derivation note shown in the source panel */
  note?: string;
};

export type DashboardMetric = {
  /** short mono label above the number */
  label: string;
  value: string;
  suffix?: string;
  /** comparison line under the number, e.g. "vs 35% rest of CA" */
  compare?: string;
  /** the display sentence, word for word from stats.md */
  caption: string;
  source: DashboardSource;
  /** at most one emphasized metric per view (gold accent) */
  emphasis?: boolean;
};

export type DashboardSeries = {
  key: string;
  label: string;
  /** "accent" = gold solid, "ink" = ink solid, "hatch" = hatched outline */
  tone: "accent" | "ink" | "hatch";
};

export type DashboardVolume = {
  title: string;
  /** x-axis key in each datum */
  xKey: string;
  series: DashboardSeries[];
  data: Array<Record<string, string | number>>;
  yMax: number;
  yTicks: number[];
  /** big figures in the left rail: [value, label] */
  stats: Array<[string, string]>;
  source: DashboardSource;
};

export type DashboardSegment = {
  label: string;
  value: number;
  tone: "ink" | "muted" | "faint" | "strong" | "line";
};

export type DashboardLoad = {
  title: string;
  totalLabel: string;
  unit: string;
  data: DashboardSegment[];
  source: DashboardSource;
};

export type DashboardTableRow = {
  label: string;
  value: number;
  highlight?: boolean;
};

export type DashboardTable = {
  title: string;
  columns: [string, string];
  /** values are percentages 0..100 */
  rows: DashboardTableRow[];
  source: DashboardSource;
};

export type DashboardLink = {
  name: string;
  place?: string;
  href: string;
};

export type DashboardLinks = {
  title: string;
  items: DashboardLink[];
  source: DashboardSource;
};

export type DashboardComparisonRow = {
  label: string;
  /** percentages 0..100 */
  valley: number;
  state: number;
};

export type DashboardComparison = {
  title: string;
  legend: [string, string];
  rows: DashboardComparisonRow[];
  source: DashboardSource;
};

export type EmployerDashboardData = {
  kicker: string;
  title: string;
  subtitle: string;
  metrics: DashboardMetric[];
  volume: DashboardVolume;
  load: DashboardLoad;
  table: DashboardTable;
  links: DashboardLinks;
  comparison: DashboardComparison;
};

/* ------------------------------------------------------------------ */
/* Real data: regional gap report (docs/research/stats.md)             */
/* ------------------------------------------------------------------ */

const PPIC_URL =
  "https://www.ppic.org/publication/pathways-to-college-completion-in-the-san-joaquin-valley/";
const P2P_URL = "https://p2p.californiacompetes.org/p2p/regions?region=san-joaquin-valley-region";

const ppicFig5: DashboardSource = {
  label: "PPIC, Aug 2024, Figure 5",
  href: PPIC_URL,
  provenance: "REAL",
  note: "PPIC's synthetic cohort of 1,000 ninth graders at current rates of high school graduation, college enrollment and completion. A projection, not one measured class.",
};

const ppicFig3: DashboardSource = {
  label: "PPIC, Aug 2024, Figure 3 (ACS 2021)",
  href: PPIC_URL,
  provenance: "REAL",
  note: "Percent of 25–54 year olds with at least a bachelor's degree, 2021. Figure 3 shows these 7 regions and the state.",
};

const p2p: DashboardSource = {
  label: "California Competes, P2P (ACS 2019)",
  href: P2P_URL,
  provenance: "REAL",
  note: "Highest educational attainment, adults 25–54, American Community Survey 2019. Bachelor's includes graduate degrees. Group labels are the dashboard's own terms.",
};

export const gapReportData: EmployerDashboardData = {
  kicker: "SHEET 04 / EMPLOYERS · REGIONAL CONTEXT",
  title: "Where the Valley's degree gap opens",
  subtitle:
    "Eight counties, Stanislaus to Kern. Read this before you write a posting that asks for a bachelor's degree.",
  metrics: [
    {
      label: "Ninth graders on a BA path",
      value: "26",
      suffix: "%",
      compare: "vs 35% rest of California",
      caption:
        "At current rates, only 26% of San Joaquin Valley ninth graders are on a path to a bachelor's degree, compared with 35% in the rest of California.",
      source: { ...ppicFig5, label: "PPIC, Aug 2024" },
      emphasis: true,
    },
    {
      label: "Adults 25–54 with a BA or more",
      value: "19",
      suffix: "%",
      compare: "vs 40% statewide",
      caption:
        "Among California's regions, the San Joaquin Valley has the lowest share of adults ages 25–54 with at least a bachelor's degree: 19%, vs. 40% statewide (2021 data).",
      source: ppicFig3,
    },
    {
      label: "Associate's degree, adults 25–54",
      value: "9",
      suffix: "%",
      compare: "vs 8% statewide",
      caption:
        "In the San Joaquin Valley, associate's degree attainment is on par with the state (9% vs. 8% of adults ages 25–54), but bachelor's attainment is about half (18% vs. 37%).",
      source: p2p,
    },
    {
      label: "Valley BA rate ÷ state rate",
      value: "0.49",
      suffix: "×",
      compare: "18.1% ÷ 37.1%, adults 25–54",
      caption:
        "Derived from the same dashboard: bachelor's or higher, San Joaquin Valley 18.1% divided by statewide 37.1% (ACS 2019).",
      source: { ...p2p, label: "Derived from California Competes, P2P" },
    },
  ],
  volume: {
    title: "1,000 ninth graders, four steps",
    xKey: "step",
    series: [
      { key: "valley", label: "San Joaquin Valley", tone: "accent" },
      { key: "rest", label: "Rest of California", tone: "hatch" },
    ],
    data: [
      { step: "HS diploma", valley: 868, rest: 873 },
      { step: "Enroll", valley: 512, rest: 567 },
      { step: "4-year", valley: 298, rest: 385 },
      { step: "Earn a BA", valley: 257, rest: 353 },
    ],
    yMax: 1000,
    yTicks: [0, 250, 500, 750, 1000],
    stats: [
      ["257", "Valley BAs per 1,000"],
      ["353", "Rest of state"],
      ["868", "Valley diplomas"],
    ],
    source: ppicFig5,
  },
  load: {
    title: "Where the Valley cohort stops",
    totalLabel: "Ninth graders",
    unit: "of 1,000",
    // Derived by subtraction from Figure 5 (each step minus the next); sums to 1,000.
    data: [
      { label: "No diploma", value: 132, tone: "line" },
      { label: "Diploma, no college", value: 356, tone: "faint" },
      { label: "College, not 4-year", value: 214, tone: "strong" },
      { label: "4-year, no BA", value: 41, tone: "muted" },
      { label: "Earn a BA", value: 257, tone: "ink" },
    ],
    source: {
      ...ppicFig5,
      label: "Derived from PPIC Figure 5",
      note: "REAL, derived: each Figure 5 step minus the next (1,000 − 868, 868 − 512, 512 − 298, 298 − 257, 257). Valley cohort only.",
    },
  },
  table: {
    title: "Adults 25–54 with at least a BA",
    columns: ["Region", "Share, 2021"],
    rows: [
      { label: "Bay Area", value: 57 },
      { label: "Orange County", value: 48 },
      { label: "San Diego County", value: 45 },
      { label: "Los Angeles County", value: 42 },
      { label: "Sacramento Metro", value: 39 },
      { label: "Inland Empire", value: 25 },
      { label: "San Joaquin Valley", value: 19, highlight: true },
      { label: "State", value: 40 },
    ],
    source: ppicFig3,
  },
  links: {
    title: "Official program maps nearby",
    items: [
      { name: "San Joaquin Delta College", place: "Stockton", href: "https://programmap.deltacollege.edu/" },
      { name: "Modesto Junior College", place: "Modesto", href: "https://programmap.mjc.edu/" },
      { name: "Merced College", place: "Merced", href: "https://merced.programmapper.com/" },
      { name: "Bakersfield College", place: "Bakersfield", href: "https://programmap.bakersfieldcollege.edu/" },
    ],
    source: {
      label: "Program Pathways Mapper",
      href: "https://programmapper.org/ppm-schools/",
      provenance: "REAL",
      note: "Hosts from the official PPM schools list; each returned HTTP 200 on 2026-10-24. Foothold works alongside these maps and does not replace a counselor.",
    },
  },
  comparison: {
    title: "Bachelor's or higher, by group",
    legend: ["Valley", "State"],
    rows: [
      { label: "All adults", valley: 18.1, state: 37.1 },
      { label: "Latinx", valley: 10.1, state: 16.0 },
      { label: "White", valley: 26.1, state: 50.3 },
      { label: "Asian", valley: 37.7, state: 63.4 },
      { label: "Black", valley: 17.9, state: 29.9 },
      { label: "Native American or Alaska Native", valley: 10.7, state: 17.3 },
    ],
    source: p2p,
  },
};

/** CSV of every figure on the gap report, with sources, for the Export button. */
export function buildDashboardCsv(data: EmployerDashboardData): string {
  const esc = (v: string | number) => {
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const rows: Array<Array<string | number>> = [["section", "label", "value", "comparison", "source", "url"]];
  for (const m of data.metrics) {
    rows.push(["metric", m.label, `${m.value}${m.suffix ?? ""}`, m.compare ?? "", m.source.label, m.source.href]);
  }
  for (const d of data.volume.data) {
    for (const s of data.volume.series) {
      rows.push([data.volume.title, `${d[data.volume.xKey]} (${s.label})`, d[s.key] ?? "", "", data.volume.source.label, data.volume.source.href]);
    }
  }
  for (const seg of data.load.data) {
    rows.push([data.load.title, seg.label, seg.value, data.load.unit, data.load.source.label, data.load.source.href]);
  }
  for (const r of data.table.rows) {
    rows.push([data.table.title, r.label, `${r.value}%`, "", data.table.source.label, data.table.source.href]);
  }
  for (const r of data.comparison.rows) {
    rows.push([data.comparison.title, r.label, `${r.valley}%`, `${r.state}% state`, data.comparison.source.label, data.comparison.source.href]);
  }
  return rows.map((r) => r.map(esc).join(",")).join("\n");
}
