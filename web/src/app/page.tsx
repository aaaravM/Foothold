// Landing placeholder (the landing slice replaces this page). Renders inside the layout's <main>.
export default function Home() {
  return (
    <div className="hairline-grid flex min-h-[70vh] flex-1 flex-col items-center justify-center gap-6 p-8 text-ink">
      <p className="font-mono text-xs uppercase tracking-[0.3em] text-accent">
        [ SHEET 00 / SETUP ] · DWG-000 · REV A
      </p>
      <h1 className="text-6xl font-semibold tracking-tight md:text-8xl">Foothold</h1>
      <p className="text-lg text-ink-muted">Try the job. Prove the skill. Get the foothold.</p>
      <p className="font-mono text-xs uppercase tracking-widest text-ink-faint">
        Under construction · building live
      </p>
    </div>
  );
}
