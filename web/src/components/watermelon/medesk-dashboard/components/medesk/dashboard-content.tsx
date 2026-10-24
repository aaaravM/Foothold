"use client";

/*
 * Watermelon UI "medesk-dashboard" (MIT, Watermelon Contributors), rethemed for Foothold.
 * Kept from the original: the card grid, KPI row, grouped bar chart with a custom tooltip,
 * segmented load bar, table, list and progress rows, and the right-hand Sheet.
 * Changed: drawing-set frames (hairlines, 0-2px corners, no shadows or gradients), mono
 * figures with footnote marks, hatch instead of a second color, and every value comes from
 * the typed data prop with its source (no demo data, no photos).
 */
import { useId, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { ArrowUpRightIcon, DownloadIcon, FileSearchIcon, XIcon } from "lucide-react";
import type { TooltipContentProps } from "recharts";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet";
import { ProvenanceBadge } from "@/components/foothold/provenance-badge";
import { cn } from "@/lib/utils";
import {
  buildDashboardCsv,
  type DashboardComparison,
  type DashboardLinks,
  type DashboardLoad,
  type DashboardMetric,
  type DashboardSegment,
  type DashboardSource,
  type DashboardTable,
  type DashboardVolume,
  type EmployerDashboardData,
  type NavigationItem,
} from "../../data";

const SEGMENT_TONE: Record<DashboardSegment["tone"], string> = {
  ink: "bg-ink",
  muted: "bg-ink-muted",
  strong: "bg-line-strong",
  faint: "bg-ink-faint/50",
  line: "bg-line",
};

const CIRCLED = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"];

/* ------------------------------------------------------------------ */
/* Frames                                                              */
/* ------------------------------------------------------------------ */

function DashboardCard({
  children,
  className,
  fig,
}: {
  children: ReactNode;
  className?: string;
  /** drawing callout on the top border, e.g. "FIG. 2" */
  fig?: string;
}) {
  return (
    <section
      className={cn(
        "relative min-w-0 border border-line bg-background p-4 text-card-foreground",
        className,
      )}
    >
      {fig ? (
        <span className="label-mono absolute -top-2 left-3 bg-background px-1.5 leading-4 text-ink-faint">
          {fig}
        </span>
      ) : null}
      {children}
    </section>
  );
}

function CardHeader({
  title,
  action,
  className,
}: {
  title: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-4", className)}>
      <h2 className="font-display text-lg leading-6 font-semibold tracking-tight text-ink">
        {title}
      </h2>
      {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
    </div>
  );
}

/** Mono source row under a figure: citation (opens the source panel) + provenance badge. */
function SourceLine({
  source,
  onOpen,
  mark,
  className,
}: {
  source: DashboardSource;
  onOpen: (source: DashboardSource) => void;
  mark?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-x-3 gap-y-1.5", className)}>
      <button
        type="button"
        onClick={() => onOpen(source)}
        className="label-mono inline-flex items-center gap-1.5 text-ink-faint underline decoration-line-strong underline-offset-4 transition-colors hover:text-ink hover:decoration-accent"
      >
        {mark ? <span aria-hidden="true">{mark}</span> : null}
        <span>SRC · {source.label}</span>
      </button>
      <ProvenanceBadge status={source.provenance} href={source.href} note={source.label} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* KPI row                                                             */
/* ------------------------------------------------------------------ */

function MetricCard({
  metric,
  index,
  onSource,
}: {
  metric: DashboardMetric;
  index: number;
  onSource: (source: DashboardSource) => void;
}) {
  const mark = CIRCLED[index] ?? `${index + 1}`;
  return (
    <article
      className={cn(
        "relative flex min-w-0 flex-col justify-between gap-5 border border-line bg-background p-4",
        metric.emphasis && "before:absolute before:inset-x-0 before:-top-px before:h-0.5 before:bg-accent",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <h2 className="label-mono text-ink-muted">{metric.label}</h2>
        <span className="label-mono text-ink-faint tabular-nums">{String(index + 1).padStart(2, "0")}</span>
      </div>

      <div className="flex flex-col gap-2">
        <p className="flex items-baseline gap-1 font-mono text-[2.125rem] leading-none font-medium tracking-tight text-ink tabular-nums">
          {metric.value}
          {metric.suffix ? <span className="text-xl text-ink-muted">{metric.suffix}</span> : null}
          <button
            type="button"
            onClick={() => onSource(metric.source)}
            aria-label={`Source for ${metric.label}: ${metric.source.label}`}
            className="ml-1 self-start font-sans text-sm leading-none text-ink-faint transition-colors hover:text-accent"
          >
            {mark}
          </button>
        </p>
        {metric.compare ? (
          <p className="label-mono text-ink-faint">{metric.compare}</p>
        ) : null}
      </div>

      <p className="text-[13px] leading-5 text-ink-muted">{metric.caption}</p>

      <SourceLine source={metric.source} onOpen={onSource} />
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* Grouped bar chart                                                    */
/* ------------------------------------------------------------------ */

function ChartTooltip({
  active,
  payload,
  label,
}: Partial<TooltipContentProps>) {
  if (!active || !payload?.length) {
    return null;
  }

  return (
    <div className="min-w-44 border border-line-strong bg-background px-3 py-2 font-mono text-[11px] text-ink">
      <p className="mb-2 tracking-[0.12em] text-ink-muted uppercase">{label}</p>
      <div className="flex flex-col gap-1.5">
        {payload.map((item, index) => (
          <div
            key={`${String(item.dataKey)}-${index}`}
            className="flex items-center justify-between gap-6"
          >
            <span className="flex items-center gap-2 text-ink-muted">
              <span
                aria-hidden="true"
                className="size-2 border border-line-strong"
                style={{ backgroundColor: item.color }}
              />
              {item.name}
            </span>
            <span className="text-ink tabular-nums">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function VolumeCard({
  volume,
  onSource,
}: {
  volume: DashboardVolume;
  onSource: (source: DashboardSource) => void;
}) {
  const hatchId = `hatch-${useId().replace(/:/g, "")}`;
  const fillFor = (tone: DashboardVolume["series"][number]["tone"]) =>
    tone === "accent"
      ? "var(--accent)"
      : tone === "ink"
        ? "var(--ink)"
        : `url(#${hatchId})`;
  const summary = volume.data
    .map(
      (d) =>
        `${d[volume.xKey]}: ${volume.series.map((s) => `${s.label} ${d[s.key]}`).join(", ")}`,
    )
    .join("; ");

  return (
    <DashboardCard fig="FIG. 2" className="flex flex-col gap-4">
      <CardHeader title={volume.title} />

      <div className="grid flex-1 gap-6 md:grid-cols-[7.5rem_minmax(0,1fr)]">
        <dl className="grid grid-cols-3 gap-4 md:flex md:flex-col md:justify-center md:gap-7">
          {volume.stats.map(([value, label]) => (
            <div key={label} className="flex min-w-0 flex-col gap-2 border-l border-line pl-3">
              <dd className="font-mono text-[1.625rem] leading-none text-ink tabular-nums">{value}</dd>
              <dt className="label-mono text-ink-faint">{label}</dt>
            </div>
          ))}
        </dl>

        <div className="min-h-0 min-w-0">
          <div className="mb-3 flex flex-wrap items-center justify-end gap-4">
            {volume.series.map((series) => (
              <div key={series.key} className="label-mono flex items-center gap-2 text-ink-muted">
                <svg aria-hidden="true" width="12" height="12" className="shrink-0">
                  <rect
                    x="0.5"
                    y="0.5"
                    width="11"
                    height="11"
                    fill={fillFor(series.tone)}
                    stroke="var(--line-strong)"
                  />
                </svg>
                {series.label}
              </div>
            ))}
          </div>
          <div
            className="h-64 min-w-md md:min-w-0"
            role="img"
            aria-label={`${volume.title}. ${summary}.`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={volume.data} barGap={4} barCategoryGap="22%">
                <defs>
                  <pattern
                    id={hatchId}
                    width="5"
                    height="5"
                    patternUnits="userSpaceOnUse"
                    patternTransform="rotate(45)"
                  >
                    <line x1="0" y1="0" x2="0" y2="5" stroke="var(--dashboard-hatch)" strokeWidth="1.5" />
                  </pattern>
                </defs>
                <CartesianGrid vertical={false} stroke="var(--line)" strokeDasharray="2 4" />
                <XAxis
                  dataKey={volume.xKey}
                  axisLine={{ stroke: "var(--line-strong)" }}
                  tickLine={false}
                  tick={{ fill: "var(--ink-muted)", fontSize: 10 }}
                  dy={8}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  domain={[0, volume.yMax]}
                  ticks={volume.yTicks}
                  tick={{ fill: "var(--ink-faint)", fontSize: 10 }}
                  width={44}
                />
                <Tooltip
                  cursor={{ fill: "var(--surface-2)", opacity: 0.6 }}
                  content={(props) => <ChartTooltip {...props} />}
                />
                {volume.series.map((series) => (
                  <Bar
                    key={series.key}
                    dataKey={series.key}
                    name={series.label}
                    fill={fillFor(series.tone)}
                    stroke={series.tone === "hatch" ? "var(--line-strong)" : undefined}
                    strokeWidth={series.tone === "hatch" ? 1 : 0}
                    radius={0}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      <SourceLine source={volume.source} onOpen={onSource} className="border-t border-line pt-3" />
    </DashboardCard>
  );
}

/* ------------------------------------------------------------------ */
/* Segmented bar                                                        */
/* ------------------------------------------------------------------ */

function LoadCard({
  load,
  onSource,
}: {
  load: DashboardLoad;
  onSource: (source: DashboardSource) => void;
}) {
  const total = load.data.reduce((sum, segment) => sum + segment.value, 0);

  return (
    <DashboardCard fig="FIG. 3" className="flex flex-col gap-5">
      <CardHeader title={load.title} />

      <div className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between gap-4">
          <span className="label-mono text-ink-faint">{load.totalLabel}</span>
          <span className="font-mono text-sm text-ink tabular-nums">
            {total.toLocaleString("en-US")} <span className="text-ink-faint">{load.unit}</span>
          </span>
        </div>
        <div
          className="flex h-6 items-stretch gap-px border border-line-strong p-px"
          role="img"
          aria-label={load.data.map((s) => `${s.label} ${s.value}`).join(", ")}
        >
          {load.data.map((segment, index) => (
            <span
              key={segment.label}
              className={cn("dashboard-load-segment h-full min-w-1", SEGMENT_TONE[segment.tone])}
              style={
                {
                  width: `${(segment.value / total) * 100}%`,
                  animationDelay: `${index * 90}ms`,
                } as CSSProperties
              }
            />
          ))}
        </div>
      </div>

      <ul className="flex flex-col gap-3.5">
        {load.data.map((segment) => (
          <li key={segment.label} className="flex min-w-0 items-center gap-3 text-sm">
            <span className="flex min-w-0 shrink-0 items-center gap-2">
              <span aria-hidden="true" className={cn("size-3 border border-line-strong", SEGMENT_TONE[segment.tone])} />
              <span className="truncate text-ink-muted">{segment.label}</span>
            </span>
            <span aria-hidden="true" className="min-w-0 flex-1 border-t border-dashed border-line" />
            <span className="w-10 shrink-0 text-right font-mono text-[13px] text-ink tabular-nums">
              {segment.value}
            </span>
            <span className="w-12 shrink-0 text-right font-mono text-[11px] text-ink-faint tabular-nums">
              {((segment.value / total) * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
      <SourceLine source={load.source} onOpen={onSource} className="mt-auto border-t border-line pt-3" />
    </DashboardCard>
  );
}

/* ------------------------------------------------------------------ */
/* Table                                                                */
/* ------------------------------------------------------------------ */

function TableCard({
  table,
  onSource,
}: {
  table: DashboardTable;
  onSource: (source: DashboardSource) => void;
}) {
  const max = Math.max(...table.rows.map((r) => r.value), 1);
  return (
    <DashboardCard fig="FIG. 4" className="flex flex-col gap-4 px-0 pb-0">
      <CardHeader className="px-4" title={table.title} />

      <div className="overflow-x-auto no-scrollbar">
        <table className="w-full min-w-120 table-fixed text-left">
          <caption className="sr-only">
            {table.title}. Source: {table.source.label}.
          </caption>
          <thead>
            <tr className="label-mono h-10 border-y border-line text-ink-faint">
              <th scope="col" className="w-[40%] px-4 font-normal">{table.columns[0]}</th>
              <th scope="col" className="w-[18%] px-4 text-right font-normal">{table.columns[1]}</th>
              <th scope="col" className="w-[42%] px-4 font-normal">
                <span className="sr-only">Bar</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row) => (
              <tr
                key={row.label}
                className={cn(
                  "h-11 border-b border-line/70 transition-colors hover:bg-surface",
                  row.highlight && "bg-surface",
                )}
              >
                <th
                  scope="row"
                  className={cn(
                    "px-4 text-sm font-normal text-ink-muted",
                    row.highlight && "font-semibold text-ink",
                  )}
                >
                  {row.label}
                  {row.highlight ? <span className="label-mono ml-2 text-ink-faint">◀</span> : null}
                </th>
                <td className="px-4 text-right font-mono text-[13px] text-ink tabular-nums">{row.value}%</td>
                <td className="px-4">
                  <span className="relative block h-2 border border-line">
                    <span
                      className={cn(
                        "dashboard-resource-progress absolute inset-y-0 left-0 block",
                        row.highlight ? "bg-ink" : "bg-line-strong",
                      )}
                      style={{ width: `${(row.value / max) * 100}%` }}
                    />
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <SourceLine source={table.source} onOpen={onSource} className="px-4 pb-4" />
    </DashboardCard>
  );
}

/* ------------------------------------------------------------------ */
/* Link list                                                            */
/* ------------------------------------------------------------------ */

function LinksCard({
  links,
  onSource,
}: {
  links: DashboardLinks;
  onSource: (source: DashboardSource) => void;
}) {
  return (
    <DashboardCard fig="FIG. 5" className="flex flex-col gap-3 px-0 pb-0">
      <CardHeader className="px-4" title={links.title} />
      <ol className="flex flex-col">
        {links.items.map((item, index) => (
          <li key={item.href} className={cn(index > 0 && "border-t border-line/70")}>
            <a
              href={item.href}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-center justify-between gap-4 px-4 py-3 transition-colors hover:bg-surface"
            >
              <span className="flex min-w-0 items-baseline gap-3">
                <span className="label-mono text-ink-faint tabular-nums">{String(index + 1).padStart(2, "0")}</span>
                <span className="min-w-0">
                  <span className="block truncate text-sm text-ink">{item.name}</span>
                  {item.place ? <span className="label-mono mt-0.5 block text-ink-faint">{item.place}</span> : null}
                </span>
              </span>
              <ArrowUpRightIcon
                aria-hidden="true"
                className="size-4 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-ink"
              />
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          </li>
        ))}
      </ol>
      <SourceLine source={links.source} onOpen={onSource} className="border-t border-line px-4 py-3" />
    </DashboardCard>
  );
}

/* ------------------------------------------------------------------ */
/* Comparison rows                                                       */
/* ------------------------------------------------------------------ */

function ComparisonCard({
  comparison,
  onSource,
}: {
  comparison: DashboardComparison;
  onSource: (source: DashboardSource) => void;
}) {
  const max = Math.max(...comparison.rows.flatMap((r) => [r.valley, r.state]), 1);
  return (
    <DashboardCard fig="FIG. 6" className="flex flex-col gap-5">
      <CardHeader
        title={comparison.title}
        action={
          <span className="label-mono flex items-center gap-3 text-ink-faint">
            <span className="flex items-center gap-1.5">
              <span aria-hidden="true" className="h-2 w-3 bg-ink" />
              {comparison.legend[0]}
            </span>
            <span className="flex items-center gap-1.5">
              <span aria-hidden="true" className="h-3 w-px bg-ink" />
              {comparison.legend[1]}
            </span>
          </span>
        }
      />
      <ul className="flex flex-col gap-4">
        {comparison.rows.map((row, index) => (
          <li key={row.label} className={cn("flex flex-col gap-2", index > 0 && "border-t border-line/70 pt-4")}>
            <div className="flex items-baseline justify-between gap-4 text-sm">
              <span className="truncate text-ink">{row.label}</span>
              <span className="shrink-0 font-mono text-[12px] text-ink-muted tabular-nums">
                <span className="text-ink">{row.valley}%</span> / {row.state}%
              </span>
            </div>
            <div className="relative h-2 border border-line">
              <span
                className="dashboard-resource-progress absolute inset-y-0 left-0 block bg-ink"
                style={{ width: `${(row.valley / max) * 100}%` }}
              />
              <span
                aria-hidden="true"
                className="absolute -inset-y-1 w-px bg-ink"
                style={{ left: `${(row.state / max) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
      <SourceLine source={comparison.source} onOpen={onSource} className="mt-auto border-t border-line pt-3" />
    </DashboardCard>
  );
}

/* ------------------------------------------------------------------ */
/* Source panel (the original staff-details Sheet, repurposed)          */
/* ------------------------------------------------------------------ */

function SourceSheet({
  source,
  onOpenChange,
}: {
  source: DashboardSource | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Sheet open={source !== null} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        showCloseButton={false}
        className="medesk-portal w-full! max-w-full! gap-0 border-l border-line bg-background p-0 shadow-none sm:w-112! sm:max-w-112!"
      >
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-line px-5">
          <span className="label-mono text-ink-faint">DETAIL · SOURCE</span>
          <SheetClose asChild>
            <Button type="button" variant="ghost" size="icon" aria-label="Close source panel">
              <XIcon />
            </Button>
          </SheetClose>
        </header>
        {source ? (
          <div className="flex flex-col gap-5 overflow-y-auto px-5 py-6">
            <SheetTitle className="font-display text-xl leading-tight font-semibold text-ink">{source.label}</SheetTitle>
            <div className="flex items-center gap-3">
              <ProvenanceBadge status={source.provenance} href={source.href} note={source.label} />
            </div>
            <SheetDescription className="text-sm leading-6 text-ink-muted">
              {source.note ?? "Read from the publisher's page and data files."}
            </SheetDescription>
            <a
              href={source.href}
              target="_blank"
              rel="noopener noreferrer"
              className="label-mono inline-flex w-fit items-center gap-1.5 border border-line-strong px-3 py-2 text-ink transition-colors hover:border-accent hover:text-accent"
            >
              Open the source <ArrowUpRightIcon aria-hidden="true" className="size-3.5" />
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
            <p className="label-mono break-all text-ink-faint">{source.href}</p>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

/* ------------------------------------------------------------------ */
/* Not-wired view                                                        */
/* ------------------------------------------------------------------ */

export function NotWiredPanel({ item }: { item: NavigationItem }) {
  const Icon = item.icon;
  return (
    <div className="p-4 md:p-6">
      <DashboardCard fig="DETAIL" className="flex min-h-80 flex-col items-start justify-center gap-4 p-8 hairline-grid">
        <Icon aria-hidden="true" className="size-6 text-ink-faint" />
        <h2 className="font-display text-2xl font-semibold tracking-tight text-ink">{item.name}</h2>
        <p className="max-w-lg text-sm leading-6 text-ink-muted">
          {item.api ? (
            <>
              This view is drawn from <code className="font-mono text-[12px] text-ink">{item.api}</code>. Until
              it answers, the portal shows nothing here rather than sample numbers.
            </>
          ) : (
            <>Method notes live with each figure: open any SRC line to see where a number comes from.</>
          )}
        </p>
      </DashboardCard>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                  */
/* ------------------------------------------------------------------ */

export function DashboardPage({
  data,
  actions,
}: {
  data: EmployerDashboardData;
  /** extra header actions (e.g. "New posting") */
  actions?: ReactNode;
}) {
  const [openSource, setOpenSource] = useState<DashboardSource | null>(null);

  const exportCsv = () => {
    const blob = new Blob([buildDashboardCsv(data)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "foothold-gap-report.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col gap-7 p-4 md:p-6">
      <section className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div className="flex max-w-3xl flex-col gap-3">
          <p className="label-mono text-ink-faint">{data.kicker}</p>
          <h1 className="type-display-md text-ink">{data.title}</h1>
          <p className="max-w-2xl text-[15px] leading-6 text-ink-muted">{data.subtitle}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" className="h-9 gap-2 px-3" onClick={exportCsv}>
            <DownloadIcon className="size-4" />
            <span className="label-mono">Export CSV</span>
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-9 gap-2 px-3"
            onClick={() => setOpenSource(data.volume.source)}
          >
            <FileSearchIcon className="size-4" />
            <span className="label-mono">Method</span>
          </Button>
          {actions}
        </div>
      </section>

      <section className="@container" aria-label="Key figures">
        <div className="grid grid-cols-1 gap-3 @min-[36rem]:grid-cols-2 @min-[72rem]:grid-cols-4">
          {data.metrics.map((metric, index) => (
            <MetricCard key={metric.label} metric={metric} index={index} onSource={setOpenSource} />
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,25rem)]">
        <div className="min-w-0 overflow-x-auto no-scrollbar pt-2">
          <VolumeCard volume={data.volume} onSource={setOpenSource} />
        </div>
        <div className="pt-2">
          <LoadCard load={data.load} onSource={setOpenSource} />
        </div>
      </section>

      <section className="grid items-start gap-4 pt-2 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,25rem)]">
        <TableCard table={data.table} onSource={setOpenSource} />
        <div className="grid min-w-0 gap-6 self-start">
          <LinksCard links={data.links} onSource={setOpenSource} />
          <ComparisonCard comparison={data.comparison} onSource={setOpenSource} />
        </div>
      </section>

      <SourceSheet
        source={openSource}
        onOpenChange={(open) => {
          if (!open) setOpenSource(null);
        }}
      />
    </div>
  );
}
