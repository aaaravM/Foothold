"use client";

import * as React from "react";
import { QuietLabel as MonoLabel } from "@/components/sim/fx";
import { getJSON, putJSON } from "@/lib/api";
import { cn } from "@/lib/utils";
import { errorMessage } from "@/components/sim/use-tapped-trace";

type Column = "todo" | "doing" | "done";
interface KanbanItem {
  id: string;
  title: string;
  column: Column;
  term?: string | null;
  kind?: string | null;
  days?: string[];
  start?: string | null;
  end?: string | null;
  modality?: string | null;
  custom?: boolean;
  [k: string]: unknown;
}
interface KanbanResponse {
  items: KanbanItem[];
  updated_at: string | null;
}

const COLUMNS: { id: Column; label: string }[] = [
  { id: "todo", label: "To do" },
  { id: "doing", label: "Doing" },
  { id: "done", label: "Done" },
];

/** Pathway steps board, persisted per learner via GET/PUT /api/path/kanban. */
export function PathKanban({ version }: { version: number }) {
  const [items, setItems] = React.useState<KanbanItem[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [draft, setDraft] = React.useState("");

  React.useEffect(() => {
    let live = true;
    getJSON<KanbanResponse>("/api/path/kanban")
      .then((r) => live && setItems(r.items))
      .catch((e) => live && setError(errorMessage(e)));
    return () => {
      live = false;
    };
  }, [version]);

  const save = async (next: KanbanItem[]) => {
    const prev = items;
    setItems(next);
    setSaving(true);
    setError(null);
    try {
      const r = await putJSON<KanbanResponse>("/api/path/kanban", { items: next });
      setItems(r.items);
    } catch (e) {
      setItems(prev);
      setError(errorMessage(e));
    }
    setSaving(false);
  };

  const move = (id: string, dir: -1 | 1) => {
    if (!items) return;
    const order: Column[] = ["todo", "doing", "done"];
    void save(
      items.map((it) => {
        if (it.id !== id) return it;
        const i = Math.min(2, Math.max(0, order.indexOf(it.column) + dir));
        return { ...it, column: order[i] };
      }),
    );
  };

  const add = () => {
    const title = draft.trim();
    if (!title || !items) return;
    setDraft("");
    void save([...items, { id: `custom-${Date.now().toString(36)}`, title, column: "todo", custom: true, kind: "custom" }]);
  };

  return (
    <section aria-label="Your board" className="space-y-4">
      <MonoLabel as="p" aria-live="polite">{saving ? "Saving…" : items ? `${items.length} steps · saved` : ""}</MonoLabel>
      {error ? (
        <p role="alert" className="text-danger">
          {error}
        </p>
      ) : null}
      {items && items.length === 0 ? (
        <p className="text-ink-muted">Approve a plan to fill your board.</p>
      ) : null}
      <div className="grid gap-3 md:grid-cols-3">
        {COLUMNS.map((col, ci) => {
          const list = (items ?? []).filter((i) => i.column === col.id);
          return (
            <div key={col.id} className="border border-line">
              <div className="flex items-center justify-between border-b border-line px-3 py-2">
                <MonoLabel as="h3" tone="ink">
                  {col.label}
                </MonoLabel>
                <MonoLabel>{list.length}</MonoLabel>
              </div>
              <ul className="space-y-2 p-2" aria-label={col.label}>
                {list.map((it) => (
                  <li key={it.id} className={cn("border border-line bg-bg p-2", col.id === "done" && "opacity-70")}>
                    <p className={cn("text-sm text-ink", col.id === "done" && "line-through")}>{it.title}</p>
                    <MonoLabel as="p">{[it.term, it.days?.join(" "), it.start && it.end && !(it.start === "00:00" && it.end === "23:59") ? `${it.start}–${it.end}` : null].filter(Boolean).join(" · ") || it.kind}</MonoLabel>
                    <div className="mt-1 flex justify-end gap-1">
                      <button
                        type="button"
                        disabled={ci === 0 || saving}
                        onClick={() => move(it.id, -1)}
                        aria-label={`Move “${it.title}” to ${COLUMNS[ci - 1]?.label ?? ""}`}
                        className="h-7 border border-line px-2 font-mono text-xs text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-30 rounded-full"
                      >
                        ←
                      </button>
                      <button
                        type="button"
                        disabled={ci === 2 || saving}
                        onClick={() => move(it.id, 1)}
                        aria-label={`Move “${it.title}” to ${COLUMNS[ci + 1]?.label ?? ""}`}
                        className="h-7 border border-line px-2 font-mono text-xs text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-30 rounded-full"
                      >
                        →
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
      {items ? (
        <div className="flex max-w-xl gap-2">
          <label htmlFor="path-board-add" className="sr-only">
            Add your own step
          </label>
          <input
            id="path-board-add"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                add();
              }
            }}
            placeholder="Add your own step (e.g. Ask counselor about FAFSA)"
            className="h-10 flex-1 border border-line-strong bg-bg px-3 text-sm text-ink placeholder:text-ink-faint focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent rounded-full"
          />
          <button type="button" onClick={add} disabled={!draft.trim() || saving} className="h-10 border border-line-strong px-3 text-sm text-ink hover:bg-surface focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50 rounded-full">
            Add
          </button>
        </div>
      ) : null}
    </section>
  );
}
