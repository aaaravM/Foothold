import Link from "next/link";
import { Hero } from "@/components/landing/hero";
import { MonoLabel } from "@/components/foothold/mono-label";
import { ProvenanceBadge, PROVENANCE_META } from "@/components/foothold/provenance-badge";

const CHAPTERS = [
  {
    id: "try",
    label: "TRY",
    title: "Work a shift before you commit to a career.",
    body: "Stockton, 7:02 a.m. A simulated workday in one of eight Valley careers: each event is a real decision, and an adaptive selector picks the next one that tells the most about how you work.",
    href: "/sim",
    cta: "Start a workday",
  },
  {
    id: "prove",
    label: "PROVE",
    title: "Your choices become skill evidence.",
    body: "The workday scores 21 O*NET work styles and the skills you showed. They land on a blind skill card that employers can rank without seeing your name, school or photo.",
    href: "/sim",
    cta: "See your fit result",
  },
  {
    id: "plan",
    label: "PLAN",
    title: "A route that fits your actual week.",
    body: "Hours, budget, commute and dependents go in as hard limits. A constraint solver returns a schedule of real programs that satisfies all of them, or says no plan exists, and compares itself with a greedy plan.",
    href: "/path",
    cta: "Plan a path",
  },
  {
    id: "learn",
    label: "LEARN",
    title: "Courses ranked from the skills graph.",
    body: "A graph recommender ranks courses and jobs for you, shows the path that explains each pick, and states its measured recall against simpler models.",
    href: "/graph",
    cta: "Explore the graph",
  },
  {
    id: "connect",
    label: "CONNECT",
    title: "Employers ask. You decide.",
    body: "Employers post a role and see ranked blind cards. To learn who you are, they send a request to your inbox; your name and contact appear only if you accept.",
    href: "/employers",
    cta: "Employer desk",
    alt: { href: "/inbox", label: "Learner inbox" },
  },
  {
    id: "belong",
    label: "BELONG",
    title: "A circle of people on the same climb.",
    body: "Small support circles by career and city, a coach for hard conversations, and practice scenarios with feedback. Crisis resources are one tap away.",
    href: "/circle",
    cta: "Open your circle",
  },
] as const;

const NOT_CHATBOT = [
  "Two-sided consent network: employers see blind cards; identity is released only by the learner.",
  "Trained models, each measured against a baseline on held-out data, with a reproduce command.",
  "A CP-SAT solver that guarantees every constraint you set, or proves none can be met.",
  "Checkpointed agent loops with parallel steps and human approval; every stated number is verified.",
  "Works alongside the Program Pathways Mapper and ASSIST, linking to them instead of replacing them.",
];

export default function Home() {
  return (
    <div className="flex flex-col">
      <Hero />

      <div className="page-container space-y-0 border-t border-line">
        {CHAPTERS.map((c, i) => (
          <section key={c.id} id={c.id} aria-labelledby={`${c.id}-title`} className="grid grid-cols-1 scroll-mt-24 gap-4 border-b border-line py-10 lg:grid-cols-12 lg:gap-8">
            <div className="lg:col-span-3">
              <MonoLabel as="p" tone={i % 2 === 0 ? "accent" : "muted"}>
                Chapter {String(i + 1).padStart(2, "0")} / 06 · {c.label}
              </MonoLabel>
            </div>
            <div className={i % 2 === 0 ? "lg:col-span-7" : "lg:col-span-7 lg:col-start-5"}>
              <h2 id={`${c.id}-title`} className="type-display-md text-ink">
                {c.title}
              </h2>
              <p className="mt-3 max-w-[60ch] text-[17px] leading-relaxed text-ink-muted">{c.body}</p>
              <p className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
                <Link href={c.href} className="label-mono text-ink underline decoration-line-strong underline-offset-4 hover:text-accent hover:decoration-accent">
                  {c.cta} →
                </Link>
                {"alt" in c ? (
                  <Link href={c.alt.href} className="label-mono text-ink-muted underline decoration-line-strong underline-offset-4 hover:text-ink">
                    {c.alt.label} →
                  </Link>
                ) : null}
              </p>
            </div>
          </section>
        ))}
      </div>

      <section aria-labelledby="not-chatbot" className="page-container grid grid-cols-1 gap-8 py-14 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <MonoLabel as="p">Drawing notes</MonoLabel>
          <h2 id="not-chatbot" className="type-display-md mt-1 text-ink">
            Why this isn&rsquo;t a chatbot
          </h2>
          <Link href="/about" className="label-mono mt-4 inline-block text-ink-muted underline underline-offset-4 hover:text-ink">
            The full case →
          </Link>
        </div>
        <ol className="space-y-4 lg:col-span-8">
          {NOT_CHATBOT.map((n, i) => (
            <li key={n} className="grid grid-cols-[3.5rem_1fr] gap-3 border-t border-line pt-3">
              <span className="font-mono text-xs text-accent">NOTE {i + 1}</span>
              <span className="text-[16px] leading-relaxed text-ink-muted">{n}</span>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="legend" className="page-container border-t border-line py-10">
        <h2 id="legend" className="label-mono text-ink-faint">
          Provenance legend
        </h2>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {(["REAL", "SAMPLE", "SYNTHETIC", "FICTIONAL"] as const).map((p) => (
            <div key={p} className="space-y-2">
              <dt>
                <ProvenanceBadge status={p} />
              </dt>
              <dd className="text-sm text-ink-muted">{PROVENANCE_META[p].explain}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
